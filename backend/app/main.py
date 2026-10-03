"""FastAPI front: job dict + one worker thread + static UI.
ponytail: in-memory jobs (Redis/SQLite if history is ever needed); ephemeral out/ (HF persistent volume if videos must survive restarts)."""
import base64
import io
import json
import queue
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import llm, media, pipeline
from .presets import COMMUNITIES, DURATIONS, LANGUAGES, LAYOUTS, OUTFIT_FOR, OUTFITS, STYLES

pipeline.OUT.mkdir(exist_ok=True)
JOBS, LOCK, Q = {}, threading.Lock(), queue.Queue()


class Cancelled(Exception):
    pass


def _worker():
    while True:
        jid, scene = Q.get()  # scene is None for a new video, or the index of a scene to redo on a finished one
        with LOCK:
            job = JOBS.get(jid)
        if job is None or job.get("stopped"):  # deleted or stopped while queued
            shutil.rmtree(pipeline.OUT / jid, ignore_errors=True)
            continue

        def progress(stage):
            with LOCK:
                if jid not in JOBS or job.get("stopped"):  # ponytail: delete/stop mid-run ends at the next stage boundary, not mid-ffmpeg
                    raise Cancelled
                job["status"], job["stage"] = "running", stage
                job.setdefault("started", time.time())

        try:
            if scene is None:
                meta = pipeline.make_video(job["topic"], job["community"], progress, job_id=jid,
                                           language=job["language"], duration=job["duration"], plan=job.get("plan"),
                                           style=job.get("style", "photo"), source=job.get("source"), layout=job.get("layout", "scenes"))
            else:
                meta = pipeline.redo_scene(jid, scene, progress)
            with LOCK:
                if not job.get("stopped"):  # a stop during the last stage still wins
                    job.update(status="done", stage=None, result=meta)
        except Cancelled:
            pass
        except Exception as e:  # one bad job never kills the worker
            with LOCK:
                if not job.get("stopped"):
                    job.update(status="failed", error=f"{job['stage']}: {e}"[:500])
        with LOCK:
            gone = jid not in JOBS or job.get("stopped")
        if gone:  # the worker owns out/<id>/ while a job is on the line, so it cleans up a deleted or stopped one
            shutil.rmtree(pipeline.OUT / jid, ignore_errors=True)


def load_done_jobs():
    """Rebuild the gallery from out/<id>/<id>.json so a restart keeps finished videos (and a Railway volume at
    /app/out keeps them across deploys). Older metas lack language/target; they get the old defaults."""
    for f in sorted(pipeline.OUT.glob("*/*.json")):
        if f.parent.name.startswith("_") or f.stem != f.parent.name or not f.with_suffix(".mp4").exists():
            continue
        try:
            meta = json.loads(f.read_text())
        except (OSError, ValueError):
            continue
        with LOCK:
            JOBS.setdefault(meta["id"], {"id": meta["id"], "topic": meta["topic"], "community": meta.get("community", "general"),
                                         "language": meta.get("language", "en"), "duration": meta.get("target", 30), "style": meta.get("style", "photo"),
                                         "status": "done", "stage": None, "created": f.stat().st_mtime, "result": meta, "error": None,
                                         "saved": (f.parent / "saved").exists()})


@asynccontextmanager
async def lifespan(_app):
    load_done_jobs()
    threading.Thread(target=_worker, daemon=True).start()  # ponytail: single worker = serialised ffmpeg on 2 vCPUs
    yield


app = FastAPI(title="Qoneqt Video Factory", lifespan=lifespan)
app.mount("/out", StaticFiles(directory=pipeline.OUT), name="out")


class GenerateIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    community: str = "general"
    language: str = "en"
    duration: int = 30
    style: str = "photo"
    all_languages: bool = False  # one job per language per topic; the siblings translate the first job's script and reuse its stills
    plan: dict | None = None  # a previewed plan (from POST /plan, hook possibly swapped); only used for a single topic
    photo: str | None = Field(None, max_length=12_000_000)  # data URL of the user's photo (restyled or not): the user is in the video
    photo_consent: bool = False  # the user confirms the face is theirs or they may use it
    layout: str = "scenes"  # presets.LAYOUTS; the form sends none: the user inside the middle scenes' pictures, no bubble


class RestyleIn(BaseModel):
    photo: str = Field(max_length=12_000_000)
    outfit: str = "smart"


def _photo_png(data_url):
    """Data URL -> PNG bytes of a 9:16 portrait (media.PORTRAIT), cropped from the top of a tall photo and the middle
    of a wide one, where faces are. ffmpeg doubles as the validator: anything it cannot decode is refused."""
    try:
        raw = base64.b64decode(data_url.split(",", 1)[-1], validate=True)
    except ValueError:
        raise HTTPException(400, "photo is not base64")
    with tempfile.TemporaryDirectory() as t:
        src, dst = f"{t}/in", f"{t}/photo.png"
        open(src, "wb").write(raw)
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-frames:v", "1", "-vf",
                            "crop='min(iw,ih*9/16)':'min(ih,iw*16/9)':'(iw-ow)/2':'(ih-oh)/4',scale=%d:%d" % media.PORTRAIT, dst],
                           capture_output=True, timeout=30)
        if r.returncode:
            raise HTTPException(400, "photo is not an image ffmpeg can read")
        return open(dst, "rb").read()


class PlanIn(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    community: str = "general"
    language: str = "en"
    duration: int = 30


@app.get("/presets")
def presets():
    return {"communities": [{"slug": k, "label": v["label"], "language": v["language"], "accent": "#" + v["accent"], "examples": v["examples"]} for k, v in COMMUNITIES.items()],
            "languages": [{"slug": k, "label": v["label"]} for k, v in LANGUAGES.items()],
            "durations": DURATIONS,
            "styles": [{"slug": k, "label": v[0]} for k, v in STYLES.items()],
            "outfits": [{"slug": k, "label": v[0]} for k, v in OUTFITS.items()], "outfit_for": OUTFIT_FOR,
            "layouts": [{"slug": k, "label": v} for k, v in LAYOUTS.items()]}


@app.get("/suggest")
def suggest(community: str = "general", language: str = "en", trends_only: bool = False):
    if community not in COMMUNITIES or language not in LANGUAGES:
        raise HTTPException(400, "unknown community or language")
    try:
        return llm.suggest(community, language, trends_only)
    except Exception as e:  # every model down: the user can still type a topic
        raise HTTPException(503, f"suggestions unavailable: {str(e)[:120]}")


@app.post("/plan")
def plan(body: PlanIn):
    """Script preview: the same plan the pipeline would use, returned without rendering (~3 s)."""
    if body.community not in COMMUNITIES or body.language not in LANGUAGES or body.duration not in DURATIONS:
        raise HTTPException(400, "unknown community, language or duration")
    try:
        return llm.plan(body.topic.strip(), body.community, body.language, body.duration)
    except Exception as e:
        raise HTTPException(503, f"script unavailable: {str(e)[:120]}")


@app.post("/photo/restyle")
def restyle(body: RestyleIn):
    """The user's photo in better clothes, posture and light, same face (~10 s). The form shows it beside the original."""
    if body.outfit not in OUTFITS:
        raise HTTPException(400, "unknown outfit")
    with tempfile.TemporaryDirectory() as t:
        src = f"{t}/photo.png"
        open(src, "wb").write(_photo_png(body.photo))
        try:
            out = media.restyle(src, body.outfit, f"{t}/restyled.png")
        except Exception as e:
            if "429" in str(e):  # every Cloudflare key has spent its 10,000 free neurons; they come back at 00:00 UTC
                raise HTTPException(503, "The free daily AI image limit is used up. It resets at 05:30 IST. Your original photo works meanwhile.")
            if "timed out" in str(e):  # seen 3 Oct 2026: FLUX.2 hangs on an account where FLUX.1 still answers
                raise HTTPException(503, "The AI restyle service is not answering right now. Try again in a few minutes, or use your original photo.")
            raise HTTPException(503, f"Restyle failed: {str(e)[:120]}")
        return {"photo": "data:image/jpeg;base64," + base64.b64encode(out.read_bytes()).decode()}


@app.post("/generate")
def generate(body: GenerateIn):
    if body.community not in COMMUNITIES or body.language not in LANGUAGES or body.duration not in DURATIONS or body.style not in STYLES \
            or body.layout not in LAYOUTS:
        raise HTTPException(400, "unknown community, language, duration, look or layout")
    topics = [t.strip()[:200] for t in body.topics if t.strip()]
    plan = body.plan if len(topics) == 1 else None
    if plan is not None:
        try:
            llm.validate_plan(plan, (3, 9))
        except ValueError as e:
            raise HTTPException(400, f"bad plan: {e}")
    photo = None
    if body.photo:
        if not body.photo_consent:
            raise HTTPException(400, "confirm the photo is you, or that you may use this face")
        photo = _photo_png(body.photo)
    langs = [body.language] + [k for k in LANGUAGES if k != body.language] if body.all_languages else [body.language]
    ids = []
    for t in topics:
        source = None
        for lang in langs:
            jid = secrets.token_hex(4)
            with LOCK:
                JOBS[jid] = {"id": jid, "topic": t, "community": body.community, "language": lang,
                             "duration": body.duration, "style": body.style, "status": "queued", "stage": None, "created": time.time(),
                             "result": None, "error": None, "plan": None if source else plan, "source": source, "presenter": bool(photo), "layout": body.layout}
            if photo:  # make_video finds it there and turns the video into a talking presenter
                (pipeline.OUT / jid).mkdir(exist_ok=True)
                (pipeline.OUT / jid / "photo.png").write_bytes(photo)
            Q.put((jid, None))
            ids.append(jid)
            source = source or jid  # the first language of a topic is the source the rest follow
    if not ids:
        raise HTTPException(400, "no topics")
    return {"job_ids": ids}


def _live(j):
    """While a video is made the page shows its script and every still as it lands; both are read from out/<id>/."""
    if j["status"] != "running":
        return j
    d = pipeline.OUT / j["id"]
    j = {**j, "stills": sorted(p.name for p in d.glob("gen*.png")) or (["photo.png"] if (d / "photo.png").exists() else [])}
    if j.get("presenter"):
        j["faces"] = len(list(d.glob("clip*.mp4")))  # talking scenes finished so far
    try:
        p = json.loads((d / "plan.json").read_text())
        shot = p["scenes"][1:-1] if j.get("presenter") else p["scenes"]  # the user talks over the first and last scene
        one = j.get("presenter") and j.get("layout") != "bubble"  # the user inside the picture: one per scene
        j.update(hook=p["hook"], scenes=[sc.get("title") or sc["query"] for sc in p["scenes"]],
                 shots=sum(1 + bool(sc.get("image_prompt_b") and not one) for sc in shot))
    except (OSError, ValueError, KeyError):
        pass  # not planned yet, or an older job: the page shows the stage alone
    return j


@app.get("/jobs")
def jobs():
    with LOCK:
        snap = [{k: v for k, v in j.items() if k != "plan"} for j in JOBS.values()]
    return sorted(map(_live, snap), key=lambda j: -j["created"])


@app.get("/jobs/{jid}")
def job(jid: str):
    with LOCK:
        if jid not in JOBS:
            raise HTTPException(404, "no such job")
        return JOBS[jid]


@app.post("/jobs/{jid}/redo/{scene}")
def redo(jid: str, scene: int):
    """Regenerate one scene's visual on a finished video and re-render; runs on the same worker."""
    with LOCK:
        j = JOBS.get(jid)
        if not j:
            raise HTTPException(404, "no such job")
        if j["status"] != "done":
            raise HTTPException(409, "video is not finished")
        if not 0 <= scene < len(j["result"]["scenes"]):
            raise HTTPException(400, "no such scene")
        j.update(status="queued", stage=None, error=None)
    Q.put((jid, scene))
    return {"job_id": jid, "scene": scene}


@app.post("/jobs/{jid}/stop")
def stop_job(jid: str):
    """Stop a queued or running new video; its card stays as a stopped one the user can retry or delete."""
    with LOCK:
        j = JOBS.get(jid)
        if not j:
            raise HTTPException(404, "no such job")
        if j["status"] not in ("queued", "running") or j.get("result"):  # a redo half-done would break the finished video
            raise HTTPException(409, "nothing to stop")
        j.update(status="failed", stopped=True, error=f"{j['stage'] or 'queue'}: Stopped by you")
    return {"stopped": jid}


def _set_saved(jid, on):
    """Instagram-style save. The flag is an empty out/<id>/saved file, not a key in <id>.json, because a redo rewrites
    the meta; deleting the video removes the folder and the save with it."""
    with LOCK:
        j = JOBS.get(jid)
        if not j:
            raise HTTPException(404, "no such job")
        if not j.get("result"):  # a redo keeps its result, so a video being redone can still be saved
            raise HTTPException(409, "video is not finished")
        j["saved"] = on
    marker = pipeline.OUT / jid / "saved"
    try:
        marker.touch() if on else marker.unlink(missing_ok=True)
    except OSError:
        pass  # deleted in the same instant: nothing left to save
    return {"id": jid, "saved": on}


@app.post("/jobs/{jid}/save")
def save_job(jid: str):
    return _set_saved(jid, True)


@app.delete("/jobs/{jid}/save")
def unsave_job(jid: str):
    return _set_saved(jid, False)


@app.delete("/jobs/{jid}")
def delete_job(jid: str):
    with LOCK:
        j = JOBS.pop(jid, None)  # only ids we minted reach rmtree, so no path traversal
        if not j:
            raise HTTPException(404, "no such job")
    if j["status"] not in ("queued", "running") and not j.get("stopped"):  # the worker cleans up a job on the line or a stopped one
        shutil.rmtree(pipeline.OUT / jid, ignore_errors=True)
    return {"deleted": jid}


@app.get("/jobs/{jid}/download")
def download_job(jid: str):
    """One zip to post from: the video, its cover and the post text (the same text the Copy button gives)."""
    with LOCK:
        j = JOBS.get(jid)
        m = j and j.get("result")
    if not m:
        raise HTTPException(404, "no finished video")
    # a Gujarati or Hindi topic has no ASCII letters for a file name, so the id stands in
    name = re.sub(r"[^a-z0-9]+", "-", m["topic"].lower()).strip("-")[:60] or f"video-{jid}"
    d, buf = pipeline.OUT / jid, io.BytesIO()
    # ponytail: built in memory, fine for a 60 s short; stream from a temp file if videos ever reach hundreds of MB
    with zipfile.ZipFile(buf, "w") as z:  # stored, not deflated: mp4 and jpg are already compressed
        for ext in ("mp4", "jpg"):
            if (d / f"{jid}.{ext}").exists():
                z.write(d / f"{jid}.{ext}", f"{name}.{ext}")
        z.writestr(f"{name}.txt", f"{m['hook']}\n\n{m['caption']}\n\n{' '.join(m['hashtags'])}\n")
    return Response(buf.getvalue(), media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{name}.zip"'})


# The React build (frontend/dist, from `npm run build`) is served last so it never shadows an API route.
# In development Vite serves the UI on :8000 and proxies the API here, so the folder may not exist.
WEB = pipeline.BACKEND.parent / "frontend" / "dist"
if WEB.is_dir():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
