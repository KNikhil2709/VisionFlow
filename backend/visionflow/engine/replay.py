"""Pure fold: events -> derived run state.

This is the read model. It executes nothing — it only interprets the event log.
Because it is a pure function of the event list, folding the same history twice
always yields identical state (the FR6 determinism guarantee).
"""
from __future__ import annotations

from typing import Any

from .. import events as E
from ..events import Event

STAGES = ["ingest", "inference", "decision", "review", "finalize", "done"]


def derive_state(history: list[Event]) -> dict[str, Any]:
    if not history:
        return {"status": "UNKNOWN", "exists": False}

    started = next((e for e in history if e.event_type == E.WORKFLOW_STARTED), None)
    workflow = started.payload["workflow"] if started else None
    wf_input = started.payload["input"] if started else {}
    image_id = wf_input.get("image_id")

    steps: list[dict] = []
    done_activities: set[str] = set()
    score: float | None = None
    heatmap: str | None = None
    suspended_on: str | None = None
    status = "RUNNING"
    verdict: str | None = None
    auto: bool | None = None
    result: dict | None = None
    error: str | None = None

    for ev in history:
        t = ev.event_type
        if t == E.ACTIVITY_COMPLETED:
            name = ev.payload["name"]
            res = ev.payload["result"]
            done_activities.add(name)
            steps.append({
                "name": name,
                "call_index": ev.payload["call_index"],
                "result": res,
                "at": ev.created_at.isoformat() if ev.created_at else None,
                "seq": ev.seq,
            })
            if name == "run_inference" and isinstance(res, dict):
                score = res.get("score")
                heatmap = res.get("heatmap")
        elif t == E.WORKFLOW_SUSPENDED:
            suspended_on = ev.payload["signal"]
        elif t == E.SIGNAL_RECEIVED:
            suspended_on = None
        elif t == E.WORKFLOW_COMPLETED:
            status = "COMPLETED"
            result = ev.payload["result"]
            if isinstance(result, dict):
                verdict = result.get("verdict")
                auto = result.get("auto")
                score = result.get("score", score)
                heatmap = result.get("heatmap", heatmap)
        elif t == E.WORKFLOW_FAILED:
            status = "FAILED"
            error = ev.payload.get("error")

    if status not in ("COMPLETED", "FAILED"):
        status = "PAUSED" if suspended_on else "RUNNING"

    return {
        "exists": True,
        "workflow": workflow,
        "input": wf_input,
        "image_id": image_id,
        "status": status,
        "waiting_for": suspended_on,
        "score": score,
        "heatmap": heatmap,
        "verdict": verdict,
        "auto": auto,
        "result": result,
        "error": error,
        "steps": steps,
        "stage": _stage(done_activities, status),
        "n_events": len(history),
    }


def _stage(done: set[str], status: str) -> str:
    if status in ("COMPLETED", "FAILED"):
        return "done"
    if "ingest" not in done:
        return "ingest"
    if "run_inference" not in done:
        return "inference"
    if status == "PAUSED":
        return "review"
    if "write_verdict" not in done:
        return "decision"
    return "finalize"
