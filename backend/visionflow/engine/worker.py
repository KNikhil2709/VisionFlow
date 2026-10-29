"""The durable worker.

`advance` drives one run as far as it can go in a single pass (executing any
new activities inline) until the workflow completes, fails, or suspends on a
signal. Because progress is reconstructed from the event log every time, a
crashed worker loses nothing: a fresh worker simply calls `advance` again and
replay skips everything already recorded.
"""
from __future__ import annotations

import threading
import time

from .. import events as E
from .. import store
from .context import WorkflowContext
from .errors import CrashInjected, Suspend
from .replay import derive_state
from .sdk import get_workflow


def refresh_cache(run_id: str) -> dict:
    events = store.load_events(run_id)
    state = derive_state(events)
    store.upsert_status(run_id, state)
    return state


def advance(run_id: str) -> str:
    """Drive a single run forward. Returns a short status string.
    Raises CrashInjected to simulate an abrupt process death."""
    events = store.load_events(run_id)
    state = derive_state(events)
    if state["status"] in ("COMPLETED", "FAILED"):
        return state["status"].lower()

    ctx = WorkflowContext(run_id, events)
    wf = get_workflow(ctx.workflow_name)

    try:
        result = wf(ctx)
        store.append_simple(run_id, E.WORKFLOW_COMPLETED, {"result": result})
        refresh_cache(run_id)
        return "completed"
    except Suspend as s:
        store.append_simple(run_id, E.WORKFLOW_SUSPENDED, {"signal": s.signal})
        refresh_cache(run_id)
        return "suspended"
    except CrashInjected:
        # Mimic kill -9: append nothing, let it propagate. Everything already
        # committed to Postgres survives; the run resumes on the next advance.
        raise
    except Exception as e:  # genuine workflow bug
        store.append_simple(run_id, E.WORKFLOW_FAILED, {"error": repr(e)})
        refresh_cache(run_id)
        return "failed"


class Worker:
    """A controllable background worker thread (used by the API for the live
    demo). The standalone CLI worker uses `advance` directly in a loop too."""

    def __init__(self, poll_interval: float = 0.2):
        self.poll = poll_interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self.state = "stopped"          # stopped | running | crashed
        self.last_crash_point: str | None = None
        self.processed = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self.state = "running"
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)
        self.state = "stopped"

    def _loop(self) -> None:
        while not self._stop.is_set():
            ids = store.runnable_run_ids()
            if not ids:
                time.sleep(self.poll)
                continue
            for run_id in ids:
                if self._stop.is_set():
                    break
                try:
                    advance(run_id)
                    self.processed += 1
                except CrashInjected as c:
                    # Simulated crash: this worker "dies".
                    self.state = "crashed"
                    self.last_crash_point = str(c)
                    return

    def status(self) -> dict:
        return {
            "state": self.state,
            "processed": self.processed,
            "last_crash_point": self.last_crash_point,
        }
