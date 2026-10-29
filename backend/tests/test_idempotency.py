"""FR9: side-effecting activities dedupe on a deterministic idempotency key, so
a replay never produces a duplicate side effect."""
from __future__ import annotations

from visionflow import store
from visionflow.config import settings
from visionflow.cv.simulate import score_for
from visionflow.engine import advance, worker
from visionflow.engine.replay import derive_state


def _auto_reject_id() -> str:
    """An id whose simulated score is above t_high (auto-reject, no human)."""
    return next(f"defect_{i:04d}" for i in range(500)
                if score_for(f"defect_{i:04d}") > settings.t_high)


def test_verdict_and_alert_written_once_on_normal_completion():
    rid = store.start_workflow("inspection", {"image_id": _auto_reject_id()})
    worker.refresh_cache(rid)
    advance(rid)
    state = derive_state(store.load_events(rid))

    assert state["status"] == "COMPLETED"
    assert state["verdict"] == "reject"
    # Exactly one verdict row and exactly one alert.
    assert store.count_verdicts(rid) == 1
    assert store.count_alerts(rid) == 1


def test_advance_is_safe_to_call_again_after_completion():
    rid = store.start_workflow("inspection", {"image_id": _auto_reject_id()})
    worker.refresh_cache(rid)
    advance(rid)
    v1, a1 = store.count_verdicts(rid), store.count_alerts(rid)
    # Calling advance again on a terminal run must be a no-op (no new effects).
    advance(rid)
    advance(rid)
    assert store.count_verdicts(rid) == v1
    assert store.count_alerts(rid) == a1
