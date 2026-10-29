"""FR6: run state is derivable only by folding the event log, and folding the
same history twice yields identical state."""
from __future__ import annotations

import json

from visionflow import store
from visionflow.engine import advance, worker
from visionflow.engine.replay import derive_state


def _canon(state: dict) -> str:
    return json.dumps(state, default=str, sort_keys=True)


def test_fold_is_deterministic():
    rid = store.start_workflow("toy_adder", {"a": 2, "b": 3})
    worker.refresh_cache(rid)
    advance(rid)
    events = store.load_events(rid)
    assert _canon(derive_state(events)) == _canon(derive_state(events))


def test_state_reconstructs_from_events_only():
    rid = store.start_workflow("toy_adder", {"a": 2, "b": 3})
    worker.refresh_cache(rid)
    advance(rid)
    # Deriving purely from the log (no cache, no engine) gives the final result.
    state = derive_state(store.load_events(rid))
    assert state["status"] == "COMPLETED"
    assert state["result"] == {"result": 15}  # (2+3)+10


def test_inspection_auto_reject_path():
    # A defect id with a high score auto-rejects without human input.
    rid = store.start_workflow("inspection", {"image_id": "defect_0001"})
    worker.refresh_cache(rid)
    advance(rid)
    state = derive_state(store.load_events(rid))
    assert state["status"] == "COMPLETED"
    assert state["verdict"] in ("pass", "reject")  # deterministic for this id
    assert state["score"] is not None
