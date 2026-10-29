"""WorkflowContext — the object a workflow function uses to do everything.

The whole determinism story lives here. On every advance the worker re-runs the
workflow function from the top against the run's history:

  * call_activity(name, arg):
      - if this call position is already in history -> return the recorded
        result WITHOUT executing (replay).
      - otherwise -> execute the activity exactly once, persist its result, and
        continue inline.
  * wait_for_signal(name):
      - if a matching signal is already in history -> return its payload.
      - otherwise -> raise Suspend; the worker parks the run durably.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .. import events as E
from .. import store
from . import crash, sdk
from .errors import Suspend


@dataclass
class ActivityContext:
    run_id: str
    key: str


class WorkflowContext:
    def __init__(self, run_id: str, history: list[E.Event]):
        self.run_id = run_id
        self._history = history

        # Recorded activity results, keyed by call_index.
        self._completed: dict[int, Any] = {}
        # Recorded signal payloads, grouped by signal name, in arrival order.
        self._signals: dict[str, list[Any]] = {}

        for ev in history:
            if ev.event_type == E.ACTIVITY_COMPLETED:
                self._completed[ev.payload["call_index"]] = ev.payload["result"]
            elif ev.event_type == E.SIGNAL_RECEIVED:
                self._signals.setdefault(ev.payload["name"], []).append(
                    ev.payload["data"])

        # Live cursors, advanced as the workflow function runs this pass.
        self._act_counter = 0
        self._sig_cursor: dict[str, int] = {}

        # The workflow input, taken from WORKFLOW_STARTED.
        started = next(e for e in history if e.event_type == E.WORKFLOW_STARTED)
        self.workflow_name: str = started.payload["workflow"]
        self.input: dict = started.payload["input"]

    # --- API used by workflow code ------------------------------------------

    def call_activity(self, name: str, arg: Any = None) -> Any:
        idx = self._act_counter
        self._act_counter += 1

        if idx in self._completed:          # replay: do not execute again
            return self._completed[idx]

        # Frontier: execute exactly once.
        key = f"{self.run_id}:{idx}:{name}"
        fn = sdk.get_activity(name)
        actx = ActivityContext(run_id=self.run_id, key=key)

        crash.maybe_crash(f"before_execute:{name}")
        result = fn(arg, actx)
        crash.maybe_crash(f"after_sideeffect:{name}")

        store.record_activity(self.run_id, name, idx, result, key)
        crash.maybe_crash(f"after_record:{name}")

        self._completed[idx] = result
        return result

    def wait_for_signal(self, name: str) -> Any:
        cursor = self._sig_cursor.get(name, 0)
        pending = self._signals.get(name, [])
        if cursor < len(pending):
            self._sig_cursor[name] = cursor + 1
            return pending[cursor]
        raise Suspend(name)
