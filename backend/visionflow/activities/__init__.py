"""Activity implementations.

Activities are the only place non-determinism and side effects are allowed.
Each takes (arg, actx) where actx carries the run_id and the deterministic
idempotency key for this call position. Importing this module registers them.
"""
from __future__ import annotations

import time

from .. import store
from ..config import settings
from ..engine.context import ActivityContext
from ..engine.sdk import activity


def _pace():
    if settings.sim_delay_ms:
        time.sleep(settings.sim_delay_ms / 1000.0)


# Process-local counter of how many times an activity body actually ran. Used
# by tests to show a side effect can be *executed* twice (crash + replay) yet
# land in its sink exactly once.
EXEC_COUNTS: dict[str, int] = {}


@activity("toy_add", side_effecting=True)
def toy_add(arg, actx: ActivityContext) -> dict:
    EXEC_COUNTS[actx.key] = EXEC_COUNTS.get(actx.key, 0) + 1
    s = arg["x"] + arg["y"]
    store.sink_toy(actx.key, actx.run_id, s)
    return {"sum": s}


def _safe(image_id: str) -> str:
    stem = image_id.replace("/", "_").replace("\\", "_")
    return stem.rsplit(".", 1)[0]


@activity("ingest")
def ingest(arg, actx: ActivityContext) -> dict:
    """Resolve the image for a run. For the real 'local' backend, image_id is a
    path under data/samples (e.g. 'test/defect/scratch_003.png')."""
    image_id = arg if isinstance(arg, str) else arg["image_id"]
    _pace()
    backend = arg.get("policy", {}).get("backend", settings.cv_backend) if isinstance(arg, dict) else settings.cv_backend
    if isinstance(arg, dict) and arg.get("source") == "upload":
        return {"image_id": image_id, "src": str(settings.data_dir / image_id),
                "image": image_id, "backend": backend}
    if backend == "local":
        src = str(settings.samples_dir / image_id)
        return {"image_id": image_id, "src": src, "image": f"samples/{image_id}", "backend": backend}
    return {"image_id": image_id, "src": None, "image": f"images/{image_id}.png", "backend": backend}


@activity("run_inference")
def run_inference(arg, actx: ActivityContext) -> dict:
    """Run the CV model -> {score, heatmap, image, label}. Pure compute, but
    recorded so it is never recomputed on replay."""
    image_id = arg["image_id"]
    _pace()
    backend = arg.get("backend", settings.cv_backend)
    if backend == "local":
        from ..cv import service
        res = service.inspect_path(arg["src"], _safe(image_id))
        res["image"] = arg.get("image")
        res["label"] = None if image_id.startswith("uploads/") else (
            "defect" if "defect" in image_id.lower() else "normal")
        return res
    if backend == "patchcore":
        from ..cv.patchcore import PatchCore  # lazy: avoids torch import otherwise
        model = PatchCore().fit((settings.mvtec_root or ".") / "train" / "good")
        return model.score_and_heatmap(image_id)
    from ..cv import simulate
    return simulate.score_and_heatmap(image_id)


@activity("write_verdict", side_effecting=True)
def write_verdict(arg, actx: ActivityContext) -> dict:
    """Persist the final verdict. Exactly-once via the verdicts table PK on the
    idempotency key — re-running after a crash cannot write a duplicate."""
    verdict = arg["verdict"]
    first = store.sink_verdict(actx.key, actx.run_id, verdict)
    return {"written": True, "verdict": verdict, "first_write": first}


@activity("send_alert", side_effecting=True)
def send_alert(arg, actx: ActivityContext) -> dict:
    """Fire a reject alert. Exactly-once via the alerts table PK on the
    idempotency key."""
    first = store.sink_alert(actx.key, actx.run_id,
                             {"score": arg.get("score"), "reason": "defect"})
    return {"alerted": True, "first_fire": first}
