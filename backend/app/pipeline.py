"""Orchestrates one job through the six stages. CLI doubles as the end-to-end smoke test:
    python pipeline.py "why sleep matters" tech en 30"""
import json
import secrets
import shutil
import subprocess
import sys
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from . import llm, media, render
from .presets import COMMUNITIES, LANGUAGES, MUSIC, MUSIC_CREDIT

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


def make_video(topic, community="general", progress=lambda stage: None, job_id=None, language="en", duration=30, plan=None, style="photo", source=None,
               layout="scenes"):
    """Returns the meta dict that is also written to out/<id>/<id>.json. Raises on unrecoverable failure.
    plan: a previewed plan from llm.plan (hook possibly swapped by the user); None plans from scratch.
    style: a key of presets.STYLES, the look of the AI stills.
    source: id of a finished sibling job in another language; its script is translated and its stills reused.
    A photo at out/<id>/photo.png (a 9:16 portrait put there by the API) puts the user in the video: the first and last
    scenes are that photo talking full-screen; layout (presets.LAYOUTS) says whether the middle scenes show the user
    inside the AI picture, a talking bubble over it, or both."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    photo = d / "photo.png"
    presenter = photo.exists()
    if presenter:
        head, ref = media.head_png(photo, d / "head.png"), media.ref_png(photo, d / "ref.png")
        with_you, bubble = layout in ("both", "scenes"), layout in ("both", "bubble")

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
    if presenter:
        ends = {0, len(scenes) - 1}  # the user talks full-screen there, so those scenes need no picture
        # with the user inside the picture, one per scene: FLUX.2 edits cost more quota than the plain stills
        tasks = [tk for tk in tasks if tk[0] not in ends and not (with_you and tk[1])]
    you = ref if presenter and with_you else None
    with ThreadPoolExecutor(2) as vpool, ThreadPoolExecutor(3) as ipool:
        voices = [vpool.submit(media.tts, sc["narration"], community, w, language) for sc, w in zip(scenes, wavs)]
        if sib:
            got = _copy_stills(OUT / source, d, tasks, sib[1].get("image_model"))
        else:
            got = list(ipool.map(lambda tk: media.gen_image(tk[2], d / f"gen{tk[0]}{tk[1]}.png", style, you), tasks))
    images = {(i, sfx): (d / f"gen{i}{sfx}.png", cr) for (i, sfx, _), cr in zip(tasks, got) if cr}  # (scene, "" or "b") -> (png, credit)

    progress("voice")
    engines = [f.result() for f in voices]  # a voice line that failed every engine surfaces here, at the voice stage
    secs = [media.duration(w) for w in wavs]
    (d / "voices.txt").write_text("".join(f"file '{w.name}'\n" for w in wavs))
    # silence under the end card keeps the voice track as long as the video, so -shortest cuts nothing
    media._run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", "voices.txt",
                "-af", f"apad=pad_dur={render.OUTRO_SEC}", "-c:a", "pcm_s16le", "voice.wav"], cwd=d)

    progress("visuals")  # sequential: ffmpeg work on 2 vCPUs, more processes would only fight for cores and memory
    clips, sources, splits, credits, faces = [], [], [], [], []
    for i, (sc, sec) in enumerate(zip(scenes, secs)):  # ponytail: talking scenes one at a time, the free GPU queue is per user anyway
        c = d / f"clip{i}.mp4"
        if presenter and i in ends:
            faces.append(media.presenter_clip(photo, head, wavs[i], c, sec) or "photo")
            clips.append((c, sec))
            sources.append("you")
            splits.append(False)
            credits.append("")
            continue
        a, b = images.get((i, "")), images.get((i, "b"))
        credit = (a or b)[1] if (a or b) else None
        src = media.stock_clip(sc["query"], sec, c, image=a[0] if a else None, credit=credit, image_b=b[0] if b else None)
        clips.append((c if src else None, sec))
        sources.append(src["source"] if src else "card")
        splits.append(bool(src and src.get("split")))
        credits.append(src["credit"] if src else "")
        # a title card is drawn later by compose, so it gets no bubble
        faces.append((media.bubble_clip(c, head, wavs[i], sec) or "photo") if presenter and bubble and src else None)
    if any(f in ("leaptalk", "moda") for f in faces):
        credits += sorted({f"Talking face: {dict((n, l) for n, l, _ in media.FACE_CHAIN)[f]} via Hugging Face Spaces"
                           for f in faces if f in ("leaptalk", "moda")})

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
    # all scenes at once: Groq's queue time, not the audio, is the wait (3-70 s per call), and a video's
    # at most 9 requests sit under the free tier's 20 a minute
    with ThreadPoolExecutor(len(scenes)) as pool:
        timed = [w for ws in pool.map(scene_words, range(len(scenes))) for w in ws]
    words = render.align([s["narration"] for s in scenes], bounds, timed)
    overlays = [(0.0, min(2.5, bounds[0][1]), render.ass_text(p["hook"]), "Hook")]
    overlays += [(s, e, render.ass_text(sc["title"]), "Title") for sc, (s, e), (clip, _) in zip(scenes, bounds, clips) if clip is None]
    overlays.append((t, t + render.OUTRO_SEC, render.OUTRO, "Outro"))
    ass = render.subtitles(words, community, d / "captions.ass", overlays, hook_low=presenter)  # scene 1 is the user's face

    progress("render")
    mfile, mtitle = MUSIC[COMMUNITIES[community]["mood"]]
    track = MUSIC_DIR / mfile
    if track.exists():
        credits.append(f"Music: {mtitle}, {MUSIC_CREDIT}")
    render.compose(clips, d / "voice.wav", ass, d, job_id, music=track if track.exists() else None)

    chosen = next((h for h in p["hooks"] if h["text"].strip() == p["hook"].strip()), {})
    meta = {
        "id": job_id, "topic": topic, "community": community, "language": language, "target": duration,
        "style": style, "presenter": presenter, "layout": layout if presenter else None,
        "review": p.get("review"),
        "source": source if sib else None,
        "hook": p["hook"], "hook_formula": chosen.get("formula"), "hook_score": chosen.get("score"), "hook_why": chosen.get("why"),
        "caption": p["caption"], "hashtags": p["hashtags"], "posts": p.get("posts"),
        "scenes": [dict(sc, seconds=round(s, 2), voice=e, visual=v, split=sp, credit=cr, face=f)
                   for sc, s, e, v, sp, cr, f in zip(scenes, secs, engines, sources, splits, credits, faces)],
        "credits": [cr for cr in credits if cr], "music": mtitle if track.exists() else None,
        "duration": round(sum(secs), 2), "llm": p.get("model", "preview"), "whisper_words": len(timed),
        "image_model": next((cr.split(", ", 1)[1] for _, cr in images.values()), None),
        "seconds_to_make": round(time.time() - t0, 1),
        "video": f"/out/{job_id}/{job_id}.mp4", "thumb": f"/out/{job_id}/{job_id}.jpg",
    }
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


IMAGE_STAGES = ["plan", "image", "poster"]


def _picture(prompt, query, d, style, i=0):
    """(png path or None, credit, source) for slide i of an image post: the AI still, else a Wikimedia photo, else None (a plain card)."""
    png = d / f"gen{i}.png"  # gen*.png: the live card shows it the moment it lands
    cr = media.gen_image(prompt, png, style)
    if cr:
        return png, cr, "ai"
    try:
        url, cr = media._wikimedia(query, 0)
        media._download(url, d / f"photo{i}.jpg")
        return d / f"photo{i}.jpg", cr, "wikimedia"
    except Exception as e:
        print(f"image post wikimedia {query!r}: {type(e).__name__}: {str(e)[:120]}", file=sys.stderr)
        return None, "", "card"


def _prompt(meta, i):
    """Slide i's picture prompt, led by the look every slide of a carousel shares so the set reads as one series."""
    look, own = meta.get("look"), meta["slides"][i]["image_prompt"]
    return f"{look}. {own}" if look else own


def _poster(d, job_id, meta, i, pic):
    """Draw slide i: <id>.png for a single picture, <id>-<n>.png in a carousel with its "2/3 →" mark; slide 1 also makes
    the <id>.jpg thumbnail. A single picture and a carousel's last slide send the reader to the caption (and, on the
    carousel, ask for a follow) in the post's language. Returns the slide's URL."""
    n, text = len(meta["slides"]), meta.get("headline_on", True)
    png = f"{job_id}.png" if n == 1 else f"{job_id}-{i + 1}.png"
    page = f"{i + 1}/{n}" + (" →" if i < n - 1 else "") if n > 1 else None
    one, last, follow = LANGUAGES[meta.get("language", "en")]["cta"]
    cta = None if not text or i < n - 1 else one if n == 1 else f"{last}\n{follow}"
    render.poster(pic, meta["slides"][i]["text"] if text else "", d / png,
                  d / f"{job_id}.jpg" if i == 0 else None, page=page, body=i > 0, cta=cta)
    return f"/out/{job_id}/{png}"


def _finish(d, job_id, meta):
    """Credits, the zip of a carousel's slides (what Download gets) and the meta file, from the slides as they now are."""
    sl = meta["slides"]
    if len(sl) > 1:
        with zipfile.ZipFile(d / f"{job_id}.zip", "w") as z:  # PNGs are compressed already: stored, not deflated
            for i in range(len(sl)):
                z.write(d / f"{job_id}-{i + 1}.png", f"{job_id}-{i + 1}.png")
        meta["zip"] = f"/out/{job_id}/{job_id}.zip"
    meta.update(image=sl[0]["image"], visual=sl[0]["visual"], credits=list(dict.fromkeys(x["credit"] for x in sl if x["credit"])),
                image_model=next((x["credit"].split(", ", 1)[1] for x in sl if x["visual"] == "ai"), None))
    (d / f"{job_id}.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False))
    return meta


def make_image(topic, community="general", progress=lambda stage: None, job_id=None, language="en", style="photo", headline=True, slides=1):
    """An image post: one 4:5 picture with its headline, or a carousel of `slides` pictures (2-4) whose texts read as one
    story, plus caption, hashtags and alt text. Returns the meta dict that is also written to out/<id>/<id>.json (kind 'image').
    Raises when the text cannot be written or is blocked."""
    job_id = job_id or secrets.token_hex(4)
    d = OUT / job_id
    d.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    progress("plan")
    p = llm.review_post(llm.image_plan(topic, community, language, slides), language)
    (d / "plan.json").write_text(json.dumps(p, ensure_ascii=False))
    meta = {
        "id": job_id, "kind": "image", "topic": topic, "community": community, "language": language, "style": style,
        "headline": p["headline"], "headline_on": headline, "hook": p["headline"],  # hook: the search and card code read it on every job
        "caption": p["caption"], "hashtags": p["hashtags"], "alt": p["alt"], "review": p.get("review"),
        "look": p["look"], "query": p["query"], "slides": [dict(x) for x in p["slides"]], "llm": p.get("model"),
        "thumb": f"/out/{job_id}/{job_id}.jpg",
    }

    progress("image")  # 3 at a time, like the video stills
    with ThreadPoolExecutor(3) as pool:
        pics = list(pool.map(lambda i: _picture(_prompt(meta, i), p["query"], d, style, i), range(len(meta["slides"]))))

    progress("poster")
    for i, (pic, credit, source) in enumerate(pics):
        meta["slides"][i].update(image=_poster(d, job_id, meta, i, pic), visual=source, credit=credit)
    meta["seconds_to_make"] = round(time.time() - t0, 1)
    return _finish(d, job_id, meta)


def redo_image(job_id, progress=lambda stage: None, slide=0):
    """A new picture for one slide of a finished image post, same text. Rewrites and returns the meta dict."""
    d = OUT / job_id
    meta = json.loads((d / f"{job_id}.json").read_text())
    if "slides" not in meta:  # a single picture made before carousels
        meta["slides"] = [{"text": meta["headline"], "image_prompt": meta["image_prompt"], "image": meta["image"],
                           "visual": meta.get("visual"), "credit": (meta.get("credits") or [""])[0]}]
    progress("image")
    take = secrets.token_hex(2)  # FLUX is deterministic per prompt on some providers, so a fresh suffix gives a different picture
    pic, credit, source = _picture(f"{_prompt(meta, slide)} (take {take})", meta["query"], d, meta.get("style", "photo"), slide)
    progress("poster")
    meta["slides"][slide].update(image=_poster(d, job_id, meta, slide, pic), visual=source, credit=credit)
    meta["updated"] = round(time.time())
    return _finish(d, job_id, meta)


def redo_scene(job_id, n, progress=lambda stage: None):
    """New visual for scene n of a finished video, then re-render from the files still in out/<id>/
    (voice, captions, the other clips). Rewrites and returns the meta dict."""
    d = OUT / job_id
    meta = json.loads((d / f"{job_id}.json").read_text())
    scenes = meta["scenes"]
    sc = scenes[n]
    style = meta.get("style", "photo")  # older metas were all photographic
    clip = d / f"clip{n}.mp4"
    layout = meta.get("layout") if meta.get("presenter") else None
    voice, head = d / f"voice{n}.wav", d / "head.png"
    if layout and n in (0, len(scenes) - 1):  # the user's full-screen scene: another try at the talking face
        progress("visuals")
        sc["face"] = media.presenter_clip(d / "photo.png", head, voice, clip, sc["seconds"]) or "photo"
        return _rerender(d, meta, job_id, progress)
    you = d / "ref.png" if layout in ("both", "scenes") else None
    progress("images")
    take = secrets.token_hex(2)  # FLUX is deterministic per prompt on some providers, so a fresh suffix is what makes the picture different
    png, png_b = d / f"gen{n}.png", d / f"gen{n}b.png"
    cr = media.gen_image(f"{sc.get('image_prompt') or sc['query']} (take {take})", png, style, you)
    split = sc.get("image_prompt_b") and sc["seconds"] >= media.SPLIT_MIN_SEC and not you  # a short scene never cuts, so skip its second picture
    cr_b = media.gen_image(f"{sc['image_prompt_b']} (take {take})", png_b, style) if split else None
    progress("visuals")
    src = media.stock_clip(sc["query"], sc["seconds"], clip, image=png if cr else None, credit=cr or cr_b, image_b=png_b if cr_b else None)
    sc["visual"], sc["credit"], sc["split"] = (src["source"], src["credit"], bool(src.get("split"))) if src else ("card", "", False)
    if layout in ("both", "bubble") and src:
        sc["face"] = media.bubble_clip(clip, head, voice, sc["seconds"]) or "photo"
    return _rerender(d, meta, job_id, progress)


def _rerender(d, meta, job_id, progress):
    scenes = meta["scenes"]
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
