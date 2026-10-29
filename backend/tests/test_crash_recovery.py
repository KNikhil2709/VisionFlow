"""FR8/FR10: a worker crash at ANY boundary loses no work and causes no
duplicate side effect. We inject a crash, assert the run is mid-flight, then
resume (as a fresh worker would) and assert correct, exactly-once completion."""
from __future__ import annotations

import pytest

from visionflow import store
from visionflow.activities import EXEC_COUNTS
from visionflow.engine import advance, crash, worker
from visionflow.engine.errors import CrashInjected
from visionflow.engine.replay import derive_state


def _fresh_run():
    rid = store.start_workflow("toy_adder", {"a": 1, "b": 2})  # -> (1+2)+10 = 13
    worker.refresh_cache(rid)
    return rid


@pytest.mark.parametrize("point", [
    "before_execute:toy_add",
    "after_sideeffect:toy_add",
    "after_record:toy_add",
])
def test_crash_then_resume_first_activity(point):
    rid = _fresh_run()
    crash.arm(point)

    with pytest.raises(CrashInjected):
        advance(rid)

    # The run is not terminal yet.
    mid = derive_state(store.load_events(rid))
    assert mid["status"] != "COMPLETED"

    # A fresh worker resumes from the log.
    advance(rid)
    done = derive_state(store.load_events(rid))

    assert done["status"] == "COMPLETED"
    assert done["result"] == {"result": 13}
    # Exactly-once at the sink, no matter where we crashed.
    assert store.count_toy(rid) == 2


def test_crash_on_second_activity_recovers():
    rid = _fresh_run()
    # Let the first activity complete, crash during the second.
    crash.arm("after_sideeffect:toy_add")  # fires on first toy_add
    with pytest.raises(CrashInjected):
        advance(rid)
    # resume past the first; now arm a crash for the (new) first frontier add,
    # which is the SECOND logical add after the first is recorded.
    crash.arm("after_sideeffect:toy_add")
    with pytest.raises(CrashInjected):
        advance(rid)
    # Final resume completes cleanly.
    advance(rid)
    done = derive_state(store.load_events(rid))
    assert done["status"] == "COMPLETED"
    assert done["result"] == {"result": 13}
    assert store.count_toy(rid) == 2


def test_side_effect_body_ran_twice_but_effect_once():
    """The crisp exactly-once demonstration: the activity body executes twice
    (crash + replay) yet its sink row appears once."""
    rid = _fresh_run()
    crash.arm("after_sideeffect:toy_add")
    with pytest.raises(CrashInjected):
        advance(rid)
    advance(rid)  # resume

    key0 = next(k for k in EXEC_COUNTS if k.startswith(rid) and ":0:" in k)
    assert EXEC_COUNTS[key0] == 2      # body ran twice
    assert store.count_toy(rid) == 2   # but effects are exactly-once


def test_pause_and_resume_on_signal():
    """FR8/FR11: an ambiguous run parks, survives, and resumes on a verdict."""
    # Find an id whose simulated score lands in the review band.
    from visionflow.cv.simulate import score_for
    from visionflow.config import settings
    img = next(f"defect_{i:04d}" for i in range(500)
               if settings.t_low <= score_for(f"defect_{i:04d}") <= settings.t_high)

    rid = store.start_workflow("inspection", {"image_id": img})
    worker.refresh_cache(rid)
    advance(rid)
    parked = derive_state(store.load_events(rid))
    assert parked["status"] == "PAUSED"
    assert parked["waiting_for"] == "human_verdict"

    # Deliver the verdict (as the API/CLI would) and resume.
    store.append_simple(rid, "SIGNAL_RECEIVED",
                        {"name": "human_verdict", "data": {"verdict": "reject"}})
    advance(rid)
    done = derive_state(store.load_events(rid))
    assert done["status"] == "COMPLETED"
    assert done["verdict"] == "reject"
    assert store.count_verdicts(rid) == 1
    assert store.count_alerts(rid) == 1


def test_saved_policy_survives_configuration_change(monkeypatch):
    from visionflow.config import settings
    from visionflow.cv.simulate import score_for
    img = next(f"defect_{i:04d}" for i in range(500)
               if 0.35 <= score_for(f"defect_{i:04d}") <= 0.65)
    monkeypatch.setattr(settings, "t_low", 0.35)
    monkeypatch.setattr(settings, "t_high", 0.65)
    rid = store.start_workflow("inspection", {"image_id": img})
    assert rid in store.runnable_run_ids()
    crash.arm("after_record:ingest")
    with pytest.raises(CrashInjected):
        advance(rid)
    monkeypatch.setattr(settings, "t_low", 0.99)
    monkeypatch.setattr(settings, "t_high", 1.0)
    monkeypatch.setattr(settings, "cv_backend", "local")
    assert advance(rid) == "suspended"
    store.append_simple(rid, "SIGNAL_RECEIVED",
                        {"name": "human_verdict", "data": {"verdict": "reject"}})
    assert advance(rid) == "completed"
    assert store.count_verdicts(rid) == 1
    assert store.count_alerts(rid) == 1
