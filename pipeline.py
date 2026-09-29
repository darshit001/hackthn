"""Orchestrates one job through the five stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech"""
import json
import secrets
import subprocess
import sys
import time
from pathlib import Path

import llm
import media
import render

OUT = Path(__file__).parent / "out"
STAGES = ["plan", "images", "voice", "visuals", "captions", "render"]


def make_video(topic, community="general", progress=lambda stage: None, job_id=None):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    p = llm.plan(topic, community)

    progress("images")  # AI still per scene; None when Hugging Face is unavailable, then visuals falls back to stock
    images = []
    for i, sc in enumerate(p["scenes"]):
        png = d / f"gen{i}.png"
        cr = media.gen_image(sc.get("image_prompt") or sc["query"], png)
        images.append((png, cr) if cr else None)

    progress("voice")
    wavs, engines = [], []
    for i, sc in enumerate(p["scenes"]):
        w = d / f"voice{i}.wav"
        engines.append(media.tts(sc["narration"], community, w))
        wavs.append(w)
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt", "-c", "copy", "voice.wav"], cwd=d)

    progress("visuals")
    clips, sources, credits = [], [], []
    for i, (sc, sec) in enumerate(zip(p["scenes"], secs)):
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
        timed = media.words(d / "voice.wav")
    except Exception:  # ponytail: Whisper down -> align() spreads script words evenly
        timed = []
    words = render.align([s["narration"] for s in p["scenes"]], bounds, timed)
    ass = render.subtitles(words, community, d / "captions.ass")

    progress("render")
    render.compose(clips, d / "voice.wav", ass, d, job_id)

    meta = {
        "id": job_id, "topic": topic, "community": community,
        "hook": p["hook"], "caption": p["caption"], "hashtags": p["hashtags"],
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v, credit=cr) for sc, s, e, v, cr in zip(p["scenes"], secs, engines, sources, credits)],
        "credits": [cr for cr in credits if cr],
        "duration": round(sum(secs), 2), "llm": p["model"], "whisper_words": len(timed),
        "image_model": next((cr.split(", ", 1)[1] for _, cr in filter(None, images)), None),
        "seconds_to_make": round(time.time() - t0, 1),
        "video": f"/out/{job_id}/{job_id}.mp4", "thumb": f"/out/{job_id}/{job_id}.jpg",
    }
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


if __name__ == "__main__":
    topic = sys.argv[1] if len(sys.argv) > 1 else "why sleep matters"
    community = sys.argv[2] if len(sys.argv) > 2 else "general"
    m = make_video(topic, community, progress=lambda s: print(f"[{s}]", flush=True))
    print(json.dumps(m, indent=2, ensure_ascii=False))
    mp4 = OUT / m["id"] / f"{m['id']}.mp4"
    probe = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height", "-of", "json", mp4],
                                      capture_output=True, text=True, check=True).stdout)["streams"]
    assert any(s["codec_type"] == "audio" for s in probe), "no audio stream"
    v = next(s for s in probe if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (render.W, render.H), (v["width"], v["height"])
    assert 20 <= m["duration"] <= 60, f"duration {m['duration']}s outside 20-60"
    print(f"SMOKE OK -> {mp4}")
