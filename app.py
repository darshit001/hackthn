"""FastAPI front: job dict + one worker thread + static UI.
ponytail: in-memory jobs (Redis/SQLite if history is ever needed); ephemeral out/ (HF persistent volume if videos must survive restarts)."""
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

import pipeline
from presets import COMMUNITIES

ROOT = Path(__file__).parent
pipeline.OUT.mkdir(exist_ok=True)
JOBS, LOCK, Q = {}, threading.Lock(), queue.Queue()


def _worker():
    while True:
        jid = Q.get()
        job = JOBS[jid]

        def progress(stage):
            with LOCK:
                job["status"], job["stage"] = "running", stage

        try:
            meta = pipeline.make_video(job["topic"], job["community"], progress, job_id=jid)
            with LOCK:
                job.update(status="done", stage=None, result=meta)
        except Exception as e:  # one bad job never kills the worker
            with LOCK:
                job.update(status="failed", error=f"{job['stage']}: {e}"[:500])


@asynccontextmanager
async def lifespan(_app):
    threading.Thread(target=_worker, daemon=True).start()  # ponytail: single worker = serialised ffmpeg on 2 vCPUs
    yield


app = FastAPI(title="Qoneqt Video Factory", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
app.mount("/out", StaticFiles(directory=pipeline.OUT), name="out")


class GenerateIn(BaseModel):
    topics: list[str] = Field(min_length=1, max_length=10)
    community: str = "general"


@app.get("/")
def index():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/presets")
def presets():
    return [{"slug": k, "label": v["label"]} for k, v in COMMUNITIES.items()]


@app.post("/generate")
def generate(body: GenerateIn):
    if body.community not in COMMUNITIES:
        raise HTTPException(400, "unknown community")
    ids = []
    for t in body.topics:
        t = t.strip()[:200]
        if not t:
            continue
        jid = secrets.token_hex(4)
        with LOCK:
            JOBS[jid] = {"id": jid, "topic": t, "community": body.community, "status": "queued",
                         "stage": None, "created": time.time(), "result": None, "error": None}
        Q.put(jid)
        ids.append(jid)
    if not ids:
        raise HTTPException(400, "no topics")
    return {"job_ids": ids}


@app.get("/jobs")
def jobs():
    with LOCK:
        return sorted(JOBS.values(), key=lambda j: -j["created"])


@app.get("/jobs/{jid}")
def job(jid: str):
    with LOCK:
        if jid not in JOBS:
            raise HTTPException(404, "no such job")
        return JOBS[jid]


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
