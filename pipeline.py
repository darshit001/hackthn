"""Orchestrates one job through the six stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech en 30"""
import json
import secrets
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import llm
import media
import render
from presets import COMMUNITIES, MUSIC, MUSIC_CREDIT

OUT = Path(__file__).parent / "out"
MUSIC_DIR = Path(__file__).parent / "assets" / "music"
STAGES = ["plan", "images", "voice", "visuals", "captions", "render"]


def make_video(topic, community="general", progress=lambda stage: None, job_id=None, language="en", duration=30, plan=None):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure.
    plan: a previewed plan from llm.plan (hook possibly swapped by the user); None plans from scratch."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    p = plan or llm.plan(topic, community, language, duration)
    scenes = p["scenes"]

    progress("images")  # AI still per scene, 3 at a time (well inside Cloudflare Workers AI limits); None -> stock later
    with ThreadPoolExecutor(3) as pool:
        ai_credits = list(pool.map(lambda a: media.gen_image(a[1].get("image_prompt") or a[1]["query"], d / f"gen{a[0]}.png"), enumerate(scenes)))
    images = [(d / f"gen{i}.png", cr) if cr else None for i, cr in enumerate(ai_credits)]

    progress("voice")  # 2 at a time: the ElevenLabs free tier allows 2 concurrent; a third 429s into a second voice mid-video
    wavs = [d / f"voice{i}.wav" for i in range(len(scenes))]
    with ThreadPoolExecutor(2) as pool:
        engines = list(pool.map(lambda a: media.tts(a[0]["narration"], community, a[1], language), zip(scenes, wavs)))
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    # silence under the end card keeps the voice track as long as the video, so -shortest cuts nothing
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt",
                "-af", f"apad=pad_dur={render.OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)

    progress("visuals")  # sequential: ffmpeg work on 2 vCPUs, more processes would only fight for cores and memory
    clips, sources, credits = [], [], []
    for i, (sc, sec) in enumerate(zip(scenes, secs)):
        c = d / f"clip{i}.mp4"
        img = images[i]
        src = media.stock_clip(sc["query"], sec, c, image=img[0] if img else None, credit=img[1] if img else None)
        clips.append((c if src else None, sec))
        sources.append(src["source"] if src else "card")
        credits.append(src["credit"] if src else "")

    progress("captions")
    bounds, t = [], 0.0
    for sec in secs:
        bounds.append((t, t + sec))
        t += sec
    try:
        timed = media.words(d / "voice.wav", language)
    except Exception:  # ponytail: Whisper down -> align() spreads script words evenly
        timed = []
    words = render.align([s["narration"] for s in scenes], bounds, timed)
    overlays = [(0.0, min(2.5, bounds[0][1]), render.ass_text(p["hook"]), "Hook")]
    overlays += [(s, e, render.ass_text(sc["title"]), "Title") for sc, (s, e), (clip, _) in zip(scenes, bounds, clips) if clip is None]
    overlays.append((t, t + render.OUTRO_SEC, render.OUTRO, "Outro"))
    ass = render.subtitles(words, community, d / "captions.ass", overlays)

    progress("render")
    mfile, mtitle = MUSIC[COMMUNITIES[community]["mood"]]
    track = MUSIC_DIR / mfile
    if track.exists():
        credits.append(f"Music: {mtitle}, {MUSIC_CREDIT}")
    render.compose(clips, d / "voice.wav", ass, d, job_id, music=track if track.exists() else None)

    chosen = next((h for h in p.get("hooks", []) if isinstance(h, dict) and h.get("text", "").strip() == p["hook"].strip()), {})
    meta = {
        "id": job_id, "topic": topic, "community": community, "language": language, "target": duration,
        "hook": p["hook"], "hook_formula": chosen.get("formula"), "hook_score": chosen.get("score"), "hook_why": chosen.get("why"),
        "caption": p["caption"], "hashtags": p["hashtags"], "posts": p.get("posts"),
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v, credit=cr) for sc, s, e, v, cr in zip(scenes, secs, engines, sources, credits)],
        "credits": [cr for cr in credits if cr], "music": mtitle if track.exists() else None,
        "duration": round(sum(secs), 2), "llm": p.get("model", "preview"), "whisper_words": len(timed),
        "image_model": next((cr.split(", ", 1)[1] for _, cr in filter(None, images)), None),
        "seconds_to_make": round(time.time() - t0, 1),
        "video": f"/out/{job_id}/{job_id}.mp4", "thumb": f"/out/{job_id}/{job_id}.jpg",
    }
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def redo_scene(job_id, n, progress=lambda stage: None):
    """New visual for scene n of a finished video, then re-render from the files still in out/<id>/
    (voice, captions, the other clips). Rewrites and returns the meta dict."""
    d = OUT / job_id
    meta = json.loads((d / f"{job_id}.json").read_text())
    scenes = meta["scenes"]
    sc = scenes[n]
    progress("images")
    png = d / f"gen{n}.png"
    # FLUX is deterministic per prompt on some providers, so a fresh suffix is what makes the picture different
    cr = media.gen_image(f"{sc.get('image_prompt') or sc['query']} (take {secrets.token_hex(2)})", png)
    progress("visuals")
    clip = d / f"clip{n}.mp4"
    src = media.stock_clip(sc["query"], sc["seconds"], clip, image=png if cr else None, credit=cr)
    sc["visual"], sc["credit"] = (src["source"], src["credit"]) if src else ("card", "")
    # ponytail: a scene that flips between card and picture keeps the title overlay state baked into captions.ass
    clips = [(d / f"clip{i}.mp4" if s["visual"] != "card" and (d / f"clip{i}.mp4").exists() else None, s["seconds"]) for i, s in enumerate(scenes)]
    progress("render")
    mfile, _ = MUSIC[COMMUNITIES[meta["community"]]["mood"]]
    track = MUSIC_DIR / mfile
    render.compose(clips, d / "voice.wav", d / "captions.ass", d, job_id, music=track if track.exists() else None)
    meta["credits"] = [s["credit"] for s in scenes if s["credit"]] + [c for c in meta.get("credits", []) if c.startswith("Music:")]
    meta["updated"] = round(time.time())
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    language = sys.argv[3] if len(sys.argv) > 3 else "en"
    duration = int(sys.argv[4]) if len(sys.argv) > 4 else 30
    m = make_video(topic, community, progress=lambda s: print(f"[{s}]", flush=True), language=language, duration=duration)
    print(json.dumps(m, indent=2, ensure_ascii=False))
    mp4 = OUT / m["id"] / f"{m['id']}.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration", "-of", "json", mp4],
                                      capture_output=True, text=True, check=True).stdout)
    streams = probe["streams"]
    assert any(s["codec_type"] == "audio" for s in streams), "no audio stream"
    v = next(s for s in streams if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (render.W, render.H), (v["width"], v["height"])
    assert abs(m["duration"] - duration) <= 0.3 * duration, f"spoke {m['duration']}s for a {duration}s target"
    total = float(probe["format"]["duration"])
    assert abs(total - (m["duration"] + render.OUTRO_SEC)) < 0.5, f"video {total}s vs speech {m['duration']}s + {render.OUTRO_SEC}s card"
    print(f"SMOKE OK -> {mp4}  ({m['duration']}s speech for {duration}s target, made in {m['seconds_to_make']}s)")
