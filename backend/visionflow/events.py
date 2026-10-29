"""Event vocabulary for the event-sourced engine.

The event log is the single source of truth for a run. Every other view of a
run's state (status, score, verdict, current stage) is *derived* by folding
these events — never stored authoritatively elsewhere.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

# --- Event types -------------------------------------------------------------
WORKFLOW_STARTED = "WORKFLOW_STARTED"      # payload: {workflow, input}
ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"  # payload: {name, call_index, result}
WORKFLOW_SUSPENDED = "WORKFLOW_SUSPENDED"  # payload: {signal}  (waiting on a human/signal)
SIGNAL_RECEIVED = "SIGNAL_RECEIVED"        # payload: {name, data}
WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"  # payload: {result}
WORKFLOW_FAILED = "WORKFLOW_FAILED"        # payload: {error}

TERMINAL = {WORKFLOW_COMPLETED, WORKFLOW_FAILED}


@dataclass
class Event:
    run_id: str
    seq: int
    event_type: str
    payload: dict[str, Any]
    idempotency_key: str | None
    created_at: datetime | None = None

    @classmethod
    def from_row(cls, row: dict[str, Any]) -> "Event":
        return cls(
            run_id=str(row["run_id"]),
            seq=row["seq"],
            event_type=row["event_type"],
            payload=row["payload"],
            idempotency_key=row.get("idempotency_key"),
            created_at=row.get("created_at"),
        )
