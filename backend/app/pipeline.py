"""Orchestrates one job through the six stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech en 30"""
import json
import secrets
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import llm, media, render
from .presets import COMMUNITIES, MUSIC, MUSIC_CREDIT

BACKEND = Path(__file__).resolve().parent.parent  # backend/: out/ and assets/ live beside the app package
OUT = BACKEND / "out"
MUSIC_DIR = BACKEND / "assets" / "music"
STAGES = ["plan", "images", "voice", "visuals", "captions", "render"]


def _source(job_id):
    """(plan, meta) of the sibling job this one follows: its script is translated and its stills reused.
    None when there is no source or it never wrote a plan; the job then plans itself and makes its own stills."""
    if not job_id:
        return None
    sd = OUT / job_id
    if (sd / "blocked.txt").exists():  # re-planning the topic in another language might slip past the review
        raise RuntimeError("blocked by the safety review in the first language: "
                           + (sd / "blocked.txt").read_text().removeprefix("blocked by the safety review: "))
    try:
        p = json.loads((sd / "plan.json").read_text())
    except (OSError, ValueError):
        print(f"source {job_id}: no plan to translate, planning afresh", file=sys.stderr)
        return None
    try:
        meta = json.loads((sd / f"{job_id}.json").read_text())
    except (OSError, ValueError):
        meta = {}  # the source failed after its stills were made: they are still worth reusing
    return p, meta


def _copy_stills(sd, d, tasks, image_model):
    """The source's gen*.png into this job's directory, one credit per task in order, None where the source had no still.
    Copies, not links: deleting the source must not break a redo here."""
    got = []
    for i, sfx, _ in tasks:
        f = sd / f"gen{i}{sfx}.png"
        try:
            shutil.copy(f, d / f.name)
        except FileNotFoundError:  # never made, or the source was deleted mid-copy: no still for this scene
            got.append(None)
            continue
        got.append(f"AI image, {image_model or 'shared from the first language'}")  # the meta's image_model splits on ", "
    return got


def make_video(topic, community="general", progress=lambda stage: None, job_id=None, language="en", duration=30, plan=None, style="photo", source=None):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure.
    plan: a previewed plan from llm.plan (hook possibly swapped by the user); None plans from scratch.
    style: a key of presets.STYLES, the look of the AI stills.
    source: id of a finished sibling job in another language; its script is translated and its stills reused."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    sib = _source(source)
    if sib:
        p = llm.translate(sib[0], language, duration)  # the source's review comes along with it
    else:
        p = plan or llm.plan(topic, community, language, duration)
        try:
            p = llm.review(p, language)  # softened or blocked before an image or a voice line is spent
        except RuntimeError as e:
            if str(e).startswith("blocked by the safety review"):
                (d / "blocked.txt").write_text(str(e))  # siblings read it in _source and fail too
            raise
    scenes = p["scenes"]
    (d / "plan.json").write_text(json.dumps(p, ensure_ascii=False))  # the page shows the script while the video is made; siblings in other languages translate it from here

    progress("images")  # AI stills 3 at a time, every scene's first picture before any second one, so a quota hit never leaves a scene bare;
    # the voice lines record meanwhile in their own 2-thread pool (the ElevenLabs free tier allows 2 concurrent): both waits are network, so they overlap
    wavs = [d / f"voice{i}.wav" for i in range(len(scenes))]
    tasks = [(i, "", sc.get("image_prompt") or sc["query"]) for i, sc in enumerate(scenes)]
    tasks += [(i, "b", sc["image_prompt_b"]) for i, sc in enumerate(scenes) if sc.get("image_prompt_b")]
    with ThreadPoolExecutor(2) as vpool, ThreadPoolExecutor(3) as ipool:
        voices = [vpool.submit(media.tts, sc["narration"], community, w, language) for sc, w in zip(scenes, wavs)]
        if sib:
            got = _copy_stills(OUT / source, d, tasks, sib[1].get("image_model"))
        else:
            got = list(ipool.map(lambda tk: media.gen_image(tk[2], d / f"gen{tk[0]}{tk[1]}.png", style), tasks))
    images = {(i, sfx): (d / f"gen{i}{sfx}.png", cr) for (i, sfx, _), cr in zip(tasks, got) if cr}  # (scene, "" or "b") -> (png, credit)

    progress("voice")
    engines = [f.result() for f in voices]  # a voice line that failed every engine surfaces here, at the voice stage
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    # silence under the end card keeps the voice track as long as the video, so -shortest cuts nothing
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt",
                "-af", f"apad=pad_dur={render.OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)

    progress("visuals")  # sequential: ffmpeg work on 2 vCPUs, more processes would only fight for cores and memory
    clips, sources, splits, credits = [], [], [], []
    for i, (sc, sec) in enumerate(zip(scenes, secs)):
        c = d / f"clip{i}.mp4"
        a, b = images.get((i, "")), images.get((i, "b"))
        credit = (a or b)[1] if (a or b) else None
        src = media.stock_clip(sc["query"], sec, c, image=a[0] if a else None, credit=credit, image_b=b[0] if b else None)
        clips.append((c if src else None, sec))
        sources.append(src["source"] if src else "card")
        splits.append(bool(src and src.get("split")))
        credits.append(src["credit"] if src else "")

    progress("captions")  # Whisper per scene with that scene's script as its prompt: exact spelling, no bleed across scenes
    bounds, t = [], 0.0
    for sec in secs:
        bounds.append((t, t + sec))
        t += sec

    def scene_words(i):
        try:
            return [dict(w, start=w["start"] + bounds[i][0], end=w["end"] + bounds[i][0])
                    for w in media.words(wavs[i], language, scenes[i]["narration"])]
        except Exception as e:  # ponytail: align() spreads this scene's script evenly; the other scenes keep Whisper's timings
            print(f"whisper scene {i}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
            return []
    with ThreadPoolExecutor(2) as pool:  # Groq free tier: 20 Whisper requests a minute; a video needs at most 9
        timed = [w for ws in pool.map(scene_words, range(len(scenes))) for w in ws]
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

    chosen = next((h for h in p["hooks"] if h["text"].strip() == p["hook"].strip()), {})
    meta = {
        "id": job_id, "topic": topic, "community": community, "language": language, "target": duration,
        "style": style,
        "review": p.get("review"),
        "source": source if sib else None,
        "hook": p["hook"], "hook_formula": chosen.get("formula"), "hook_score": chosen.get("score"), "hook_why": chosen.get("why"),
        "caption": p["caption"], "hashtags": p["hashtags"], "posts": p.get("posts"),
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v, split=sp, credit=cr)
                   for sc, s, e, v, sp, cr in zip(scenes, secs, engines, sources, splits, credits)],
        "credits": [cr for cr in credits if cr], "music": mtitle if track.exists() else None,
        "duration": round(sum(secs), 2), "llm": p.get("model", "preview"), "whisper_words": len(timed),
        "image_model": next((cr.split(", ", 1)[1] for _, cr in images.values()), None),
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
    style = meta.get("style", "photo")  # older metas were all photographic
    progress("images")
    take = secrets.token_hex(2)  # FLUX is deterministic per prompt on some providers, so a fresh suffix is what makes the picture different
    png, png_b = d / f"gen{n}.png", d / f"gen{n}b.png"
    cr = media.gen_image(f"{sc.get('image_prompt') or sc['query']} (take {take})", png, style)
    split = sc.get("image_prompt_b") and sc["seconds"] >= media.SPLIT_MIN_SEC  # a short scene never cuts, so skip its second picture
    cr_b = media.gen_image(f"{sc['image_prompt_b']} (take {take})", png_b, style) if split else None
    progress("visuals")
    clip = d / f"clip{n}.mp4"
    src = media.stock_clip(sc["query"], sc["seconds"], clip, image=png if cr else None, credit=cr or cr_b, image_b=png_b if cr_b else None)
    sc["visual"], sc["credit"], sc["split"] = (src["source"], src["credit"], bool(src.get("split"))) if src else ("card", "", False)
    # ponytail: a scene that flips between card and picture keeps the title overlay state baked into captions.ass
    clips = [(d / f"clip{i}.mp4" if s["visual"] != "card" and (d / f"clip{i}.mp4").exists() else None, s["seconds"]) for i, s in enumerate(scenes)]
    progress("render")
    mfile, _ = MUSIC[COMMUNITIES[meta["community"]]["mood"]]
    track = MUSIC_DIR / mfile
    render.compose(clips, d / "voice.wav", d / "captions.ass", d, job_id, music=track if track.exists() else None)
    meta["credits"] = [s["credit"] for s in scenes if s.get("credit")] + [c for c in meta.get("credits", []) if c.startswith("Music:")]
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
