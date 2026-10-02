"""FastAPI front: job dict + one worker thread + static UI.
ponytail: in-memory jobs (Redis/SQLite if history is ever needed); ephemeral out/ (HF persistent volume if videos must survive restarts)."""
import json
import queue
import secrets
import shutil
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import llm
import pipeline
from presets import COMMUNITIES, DURATIONS, LANGUAGES

ROOT = Path(__file__).parent
pipeline.OUT.mkdir(exist_ok=True)
JOBS, LOCK, Q = {}, threading.Lock(), queue.Queue()


def _worker():
    while True:
        jid, scene = Q.get()  # scene is None for a new video, or the index of a scene to redo on a finished one
        job = JOBS[jid]

        def progress(stage):
            with LOCK:
                job["status"], job["stage"] = "running", stage

        try:
            if scene is None:
                meta = pipeline.make_video(job["topic"], job["community"], progress, job_id=jid,
                                           language=job["language"], duration=job["duration"], plan=job.get("plan"))
            else:
                meta = pipeline.redo_scene(jid, scene, progress)
            with LOCK:
                job.update(status="done", stage=None, result=meta)
        except Exception as e:  # one bad job never kills the worker
            with LOCK:
                job.update(status="failed", error=f"{job['stage']}: {e}"[:500])


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
                                         "language": meta.get("language", "en"), "duration": meta.get("target", 30),
                                         "status": "done", "stage": None, "created": f.stat().st_mtime, "result": meta, "error": None})


@asynccontextmanager
async def lifespan(_app):
    load_done_jobs()
    threading.Thread(target=_worker, daemon=True).start()  # ponytail: single worker = serialised ffmpeg on 2 vCPUs
    yield


app = FastAPI(title="Qoneqt Video Factory", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/out", StaticFiles(directory=pipeline.OUT), name="out")


class GenerateIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    community: str = "general"
    language: str = "en"
    duration: int = 30
    plan: dict | None = None  # a previewed plan (from POST /plan, hook possibly swapped); only used for a single topic


class PlanIn(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    community: str = "general"
    language: str = "en"
    duration: int = 30


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/presets")
def presets():
    return {"communities": [{"slug": k, "label": v["label"], "language": v["language"]} for k, v in COMMUNITIES.items()],
            "languages": [{"slug": k, "label": v["label"]} for k, v in LANGUAGES.items()],
            "durations": DURATIONS}


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


@app.post("/generate")
def generate(body: GenerateIn):
    if body.community not in COMMUNITIES or body.language not in LANGUAGES or body.duration not in DURATIONS:
        raise HTTPException(400, "unknown community, language or duration")
    topics = [t.strip()[:200] for t in body.topics if t.strip()]
    plan = body.plan if len(topics) == 1 else None
    if plan is not None:
        try:
            llm.validate_plan(plan, (3, 9))
        except ValueError as e:
            raise HTTPException(400, f"bad plan: {e}")
    ids = []
    for t in topics:
        jid = secrets.token_hex(4)
        with LOCK:
            JOBS[jid] = {"id": jid, "topic": t, "community": body.community, "language": body.language,
                         "duration": body.duration, "status": "queued", "stage": None, "created": time.time(),
                         "result": None, "error": None, "plan": plan}
        Q.put((jid, None))
        ids.append(jid)
    if not ids:
        raise HTTPException(400, "no topics")
    return {"job_ids": ids}


@app.get("/jobs")
def jobs():
    with LOCK:
        return sorted(({k: v for k, v in j.items() if k != "plan"} for j in JOBS.values()), key=lambda j: -j["created"])


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


@app.delete("/jobs/{jid}")
def delete_job(jid: str):
    with LOCK:
        j = JOBS.get(jid)  # only ids we minted reach rmtree, so no path traversal
        if not j:
            raise HTTPException(404, "no such job")
        if j["status"] in ("queued", "running"):
            raise HTTPException(409, "job still on the line")
        del JOBS[jid]
    shutil.rmtree(pipeline.OUT / jid, ignore_errors=True)
    return {"deleted": jid}
