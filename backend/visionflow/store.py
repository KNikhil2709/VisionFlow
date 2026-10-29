"""Event store: the only module that writes to the event log.

Key invariants:
  * `seq` is allocated atomically as MAX(seq)+1 per run; the UNIQUE(run_id, seq)
    constraint turns any concurrent double-append into a retryable conflict.
  * Appending an ACTIVITY_COMPLETED event and writing the engine effect cache
    happen in ONE transaction, so an activity is never recorded as done without
    its result also being cached (and vice versa).
"""
from __future__ import annotations

import json
import uuid
from typing import Any

import psycopg

from . import events as E
from .db import tx
from .events import Event


def _json(x: Any) -> str:
    return json.dumps(x, default=str)


# --- Writing -----------------------------------------------------------------

def _append(conn: psycopg.Connection, run_id: str, event_type: str,
            payload: dict, idempotency_key: str | None = None) -> int:
    """Atomically append one event, allocating the next seq. Retries once on a
    concurrent seq collision."""
    sql = """
        INSERT INTO events (run_id, seq, event_type, payload, idempotency_key)
        SELECT %s, COALESCE(MAX(seq), 0) + 1, %s, %s::jsonb, %s
        FROM events WHERE run_id = %s
        RETURNING seq
    """
    for attempt in range(5):
        try:
            cur = conn.execute(sql, (run_id, event_type, _json(payload),
                                     idempotency_key, run_id))
            return cur.fetchone()["seq"]
        except psycopg.errors.UniqueViolation:
            conn.rollback()
            if attempt == 4:
                raise
    raise RuntimeError("unreachable")


def start_workflow(workflow: str, wf_input: dict) -> str:
    """Create a new run by appending WORKFLOW_STARTED. Returns the run id."""
    if workflow == "inspection":
        from .config import settings
        wf_input = {**wf_input, "policy": {
            "t_low": settings.t_low, "t_high": settings.t_high,
            "backend": settings.cv_backend,
        }}
    run_id = str(uuid.uuid4())
    with tx() as conn:
        _append(conn, run_id, E.WORKFLOW_STARTED,
                {"workflow": workflow, "input": wf_input})
        # Publish runnable work atomically with its start event.
        conn.execute(
            "INSERT INTO run_status (run_id, workflow, status, image_id, stage, n_events) "
            "VALUES (%s, %s, 'RUNNING', %s, 'ingest', 1)",
            (run_id, workflow, wf_input.get("image_id")))
    return run_id


def record_activity(run_id: str, name: str, call_index: int,
                    result: Any, idem_key: str) -> None:
    """Persist an activity's completion: cache its result AND append its event
    in a single transaction."""
    with tx() as conn:
        conn.execute(
            "INSERT INTO effect_log (idem_key, result) VALUES (%s, %s::jsonb) "
            "ON CONFLICT (idem_key) DO NOTHING",
            (idem_key, _json(result)))
        _append(conn, run_id, E.ACTIVITY_COMPLETED,
                {"name": name, "call_index": call_index, "result": result},
                idempotency_key=idem_key)


def append_simple(run_id: str, event_type: str, payload: dict) -> int:
    with tx() as conn:
        return _append(conn, run_id, event_type, payload)


def effect_get(idem_key: str) -> Any | None:
    with tx() as conn:
        row = conn.execute(
            "SELECT result FROM effect_log WHERE idem_key = %s", (idem_key,)
        ).fetchone()
        return row["result"] if row else None


# --- Side-effect sinks (exactly-once via PRIMARY KEY on the idempotency key) --

def sink_alert(idem_key: str, run_id: str, payload: dict) -> bool:
    """Returns True if this call actually inserted (i.e. first time)."""
    with tx() as conn:
        cur = conn.execute(
            "INSERT INTO alerts (idem_key, run_id, payload) VALUES (%s, %s, %s::jsonb) "
            "ON CONFLICT (idem_key) DO NOTHING",
            (idem_key, run_id, _json(payload)))
        return cur.rowcount == 1


def sink_verdict(idem_key: str, run_id: str, verdict: str) -> bool:
    with tx() as conn:
        cur = conn.execute(
            "INSERT INTO verdicts (idem_key, run_id, verdict) VALUES (%s, %s, %s) "
            "ON CONFLICT (idem_key) DO NOTHING",
            (idem_key, run_id, verdict))
        return cur.rowcount == 1


def sink_toy(idem_key: str, run_id: str, value: int) -> bool:
    with tx() as conn:
        cur = conn.execute(
            "INSERT INTO toy_calls (idem_key, run_id, value) VALUES (%s, %s, %s) "
            "ON CONFLICT (idem_key) DO NOTHING",
            (idem_key, run_id, value))
        return cur.rowcount == 1


def count_toy(run_id: str) -> int:
    with tx() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM toy_calls WHERE run_id = %s", (run_id,)
        ).fetchone()["n"]


def count_alerts(run_id: str) -> int:
    with tx() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM alerts WHERE run_id = %s", (run_id,)
        ).fetchone()["n"]


def count_verdicts(run_id: str) -> int:
    with tx() as conn:
        return conn.execute(
            "SELECT count(*) AS n FROM verdicts WHERE run_id = %s", (run_id,)
        ).fetchone()["n"]


# --- Reading -----------------------------------------------------------------

def load_events(run_id: str) -> list[Event]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT run_id, seq, event_type, payload, idempotency_key, created_at "
            "FROM events WHERE run_id = %s ORDER BY seq", (run_id,)
        ).fetchall()
    return [Event.from_row(r) for r in rows]


def all_run_ids() -> list[str]:
    with tx() as conn:
        rows = conn.execute(
            "SELECT DISTINCT run_id, MIN(id) AS first FROM events "
            "GROUP BY run_id ORDER BY first").fetchall()
    return [str(r["run_id"]) for r in rows]


def runnable_run_ids() -> list[str]:
    """Runs whose cached status is RUNNING (fast path for the worker)."""
    with tx() as conn:
        rows = conn.execute(
            "SELECT run_id FROM run_status WHERE status = 'RUNNING' "
            "ORDER BY created_at").fetchall()
    return [str(r["run_id"]) for r in rows]


# --- Derived read-model cache ------------------------------------------------

def upsert_status(run_id: str, state: dict) -> None:
    with tx() as conn:
        conn.execute(
            """
            INSERT INTO run_status
                (run_id, workflow, status, waiting_for, verdict, score,
                 image_id, heatmap, auto, stage, n_events, updated_at)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s, now())
            ON CONFLICT (run_id) DO UPDATE SET
                status=EXCLUDED.status, waiting_for=EXCLUDED.waiting_for,
                verdict=EXCLUDED.verdict, score=EXCLUDED.score,
                image_id=EXCLUDED.image_id, heatmap=EXCLUDED.heatmap,
                auto=EXCLUDED.auto, stage=EXCLUDED.stage,
                n_events=EXCLUDED.n_events, updated_at=now()
            """,
            (run_id, state.get("workflow"), state["status"], state.get("waiting_for"),
             state.get("verdict"), state.get("score"), state.get("image_id"),
             state.get("heatmap"), state.get("auto"), state.get("stage"),
             state.get("n_events")))


def list_status() -> list[dict]:
    with tx() as conn:
        return conn.execute(
            "SELECT * FROM run_status ORDER BY created_at").fetchall()


def review_queue() -> list[dict]:
    with tx() as conn:
        return conn.execute(
            "SELECT s.*, e.payload->'input'->'policy' AS policy "
            "FROM run_status s JOIN events e ON e.run_id=s.run_id "
            "AND e.event_type='WORKFLOW_STARTED' WHERE s.status='PAUSED' "
            "AND s.waiting_for='human_verdict' ORDER BY s.created_at").fetchall()
