"""FastAPI surface for the frontend.

Exposes the event-sourced state of every run, the human-review queue, batch
submission, metrics, a live SSE stream, and controls for the demo worker
(including the "simulate crash" button). Static images/heatmaps are served from
the data dir.
"""
from __future__ import annotations

import asyncio
import json
import random
import uuid
import io
from contextlib import asynccontextmanager

from PIL import Image, UnidentifiedImageError
from starlette.concurrency import run_in_threadpool

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .. import bootstrap  # noqa: F401 registers workflows/activities
from .. import db, store
from ..config import settings
from ..engine import crash, worker
from ..engine.replay import derive_state
from ..narrate import caption

WORKER = worker.Worker()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Startup: schema, detector warm-up, start the durable worker.
    db.init_schema()
    if settings.cv_backend == "local":
        from ..cv import service
        service.ensure_samples()
        service.get_detector()
    WORKER.start()
    yield
    # Shutdown: stop the worker and close the pool cleanly.
    WORKER.stop()
    db.close_pool()


app = FastAPI(title="VisionFlow", version="0.1.0", lifespan=lifespan)

# CORS: "*" for local dev; set VF_CORS_ORIGINS to your deployed frontend
# origin(s) (comma-separated) in production.
_origins = (["*"] if settings.cors_origins.strip() == "*"
            else [o.strip() for o in settings.cors_origins.split(",") if o.strip()])
app.add_middleware(
    CORSMiddleware, allow_origins=_origins, allow_methods=["*"], allow_headers=["*"]
)


# --- request models ----------------------------------------------------------

class BatchReq(BaseModel):
    count: int = 100
    normal_ratio: float = 0.6
    seed: int | None = None


class VerdictReq(BaseModel):
    verdict: str  # "pass" | "reject"


class CrashReq(BaseModel):
    point: str = "after_record:ingest"


# --- helpers -----------------------------------------------------------------

def _image_ids(count: int, normal_ratio: float, seed: int | None) -> list[str]:
    rng = random.Random(seed)
    if settings.cv_backend == "local":
        # Draw real sample files (paths relative to data/samples).
        from ..cv import samples
        good = [f"test/good/{p.name}" for p in samples.list_split("test/good")]
        defect = [f"test/defect/{p.name}" for p in samples.list_split("test/defect")]
        if not good and not defect:
            samples.generate()
            return _image_ids(count, normal_ratio, seed)
        ids = []
        for _ in range(count):
            pool = good if (rng.random() < normal_ratio and good) or not defect else defect
            ids.append(rng.choice(pool))
        return ids
    # simulate backend: synthetic names encode the label
    ids = []
    for i in range(count):
        kind = "normal" if rng.random() < normal_ratio else "defect"
        ids.append(f"{kind}_{i:04d}")
    rng.shuffle(ids)
    return ids


def _snapshot() -> dict:
    rows = store.list_status()
    by_status: dict[str, int] = {}
    by_stage: dict[str, int] = {}
    by_verdict: dict[str, int] = {}
    for r in rows:
        by_status[r["status"]] = by_status.get(r["status"], 0) + 1
        if r.get("stage"):
            by_stage[r["stage"]] = by_stage.get(r["stage"], 0) + 1
        if r.get("verdict"):
            by_verdict[r["verdict"]] = by_verdict.get(r["verdict"], 0) + 1
    return {
        "total": len(rows),
        "by_status": by_status,
        "by_stage": by_stage,
        "by_verdict": by_verdict,
        "review_pending": by_status.get("PAUSED", 0),
        "worker": WORKER.status(),
    }


# --- endpoints ---------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "cv_backend": settings.cv_backend}


@app.post("/api/batch")
def submit_batch(req: BatchReq) -> dict:
    ids = _image_ids(req.count, req.normal_ratio, req.seed)
    run_ids = []
    for image_id in ids:
        rid = store.start_workflow("inspection", {"image_id": image_id})
        run_ids.append(rid)
    return {"submitted": len(run_ids), "run_ids": run_ids}


@app.get("/api/runs")
def list_runs() -> dict:
    return {"runs": store.list_status()}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict:
    events = store.load_events(run_id)
    if not events:
        raise HTTPException(404, "run not found")
    state = derive_state(events)
    return {
        "state": state,
        "caption": caption(state),
        "events": [
            {"seq": e.seq, "type": e.event_type, "payload": e.payload,
             "idempotency_key": e.idempotency_key,
             "at": e.created_at.isoformat() if e.created_at else None}
            for e in events
        ],
        "alerts": store.count_alerts(run_id),
        "verdicts": store.count_verdicts(run_id),
    }


@app.get("/api/review")
def review() -> dict:
    return {"queue": store.review_queue()}


@app.post("/api/runs/{run_id}/verdict")
def submit_verdict(run_id: str, req: VerdictReq) -> dict:
    events = store.load_events(run_id)
    if not events:
        raise HTTPException(404, "run not found")
    state = derive_state(events)
    if state["status"] != "PAUSED":
        raise HTTPException(409, f"run is {state['status']}, not awaiting review")
    if req.verdict not in ("pass", "reject"):
        raise HTTPException(400, "verdict must be 'pass' or 'reject'")
    store.append_simple(run_id, "SIGNAL_RECEIVED",
                        {"name": "human_verdict", "data": {"verdict": req.verdict}})
    worker.refresh_cache(run_id)  # flips cache back to RUNNING; worker resumes it
    return {"ok": True, "run_id": run_id, "verdict": req.verdict}


@app.post("/api/inspect", status_code=202)
async def inspect(file: UploadFile = File(...)) -> dict:
    """Validate an upload and submit it to the durable inspection workflow."""
    if settings.cv_backend != "local":
        raise HTTPException(400, "Upload inspection needs VF_CV_BACKEND=local")
    contents = await file.read(10 * 1024 * 1024 + 1)
    if len(contents) > 10 * 1024 * 1024:
        raise HTTPException(413, "Image must be at most 10 MB")

    def submit():
        dest = settings.uploads_dir / f"{uuid.uuid4().hex}.png"
        try:
            with Image.open(io.BytesIO(contents)) as img:
                if img.width * img.height > 20_000_000:
                    raise HTTPException(413, "Image must be at most 20 megapixels")
                img.convert("RGB").save(dest, format="PNG")
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
            dest.unlink(missing_ok=True)
            raise HTTPException(400, "Upload a valid image")
        image_id = f"uploads/{dest.name}"
        rid = store.start_workflow("inspection", {"image_id": image_id, "source": "upload"})
        return {"run_id": rid}

    return await run_in_threadpool(submit)


@app.get("/api/metrics")
def metrics() -> dict:
    snap = _snapshot()
    rows = store.list_status()
    # Score histogram (20 bins) over scored runs, split by decision band.
    bins = [0] * 20
    for r in rows:
        if r.get("score") is not None:
            bins[min(19, int(r["score"] * 20))] += 1
    snap["score_hist"] = bins
    snap["thresholds"] = {"t_low": settings.t_low, "t_high": settings.t_high}
    return snap


# --- worker controls (for the live demo) ------------------------------------

@app.get("/api/worker")
def worker_status() -> dict:
    return WORKER.status()


@app.post("/api/worker/start")
def worker_start() -> dict:
    WORKER.start()
    return WORKER.status()


@app.post("/api/worker/stop")
def worker_stop() -> dict:
    WORKER.stop()
    return WORKER.status()


@app.post("/api/worker/crash")
def worker_crash(req: CrashReq) -> dict:
    """Arm a one-shot crash point; the worker dies the next time it hits it,
    exactly like a kill -9. Restart with /api/worker/start to watch recovery."""
    crash.arm(req.point)
    return {"armed": req.point, "worker": WORKER.status()}


# --- live stream -------------------------------------------------------------

@app.get("/api/stream")
async def stream():
    async def gen():
        while True:
            payload = json.dumps(_snapshot())
            yield f"data: {payload}\n\n"
            await asyncio.sleep(0.5)
    return StreamingResponse(gen(), media_type="text/event-stream")


# Serve generated images + heatmaps.
app.mount("/data", StaticFiles(directory=str(settings.data_dir)), name="data")
