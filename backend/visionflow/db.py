"""Postgres access: a small connection pool, schema creation, and a
transaction context manager. Kept intentionally thin — the interesting logic
lives in store.py and the engine, not here.
"""
from __future__ import annotations

import atexit
from contextlib import contextmanager
from typing import Iterator

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings

# A modest pool: the API process and the worker thread share it.
_pool: ConnectionPool | None = None


class DatabaseUnavailable(RuntimeError):
    """Raised with a human-readable hint when Postgres can't be reached."""


def pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        # Probe first with a short timeout so a missing/stopped database fails
        # in ~5s with an actionable message, not a 30s pool timeout + traceback.
        try:
            psycopg.connect(settings.database_url, connect_timeout=5).close()
        except psycopg.OperationalError as e:
            raise DatabaseUnavailable(
                "Cannot connect to Postgres at "
                f"{settings.database_url.split('@')[-1]}.\n"
                "  - Is it running?  With Docker:  docker compose up -d\n"
                "  - Does the role/db exist?  Default expects "
                "visionflow/visionflow on database 'visionflow'.\n"
                "  - Different credentials?  Set VF_DATABASE_URL.\n"
                f"  Underlying error: {str(e).strip()}"
            ) from None
        _pool = ConnectionPool(
            settings.database_url,
            min_size=1,
            max_size=10,
            timeout=10,
            kwargs={"row_factory": dict_row, "autocommit": False},
            open=True,
        )
        # Close cleanly on interpreter exit so short-lived CLI/script runs don't
        # print the pool's "couldn't stop thread" warnings.
        atexit.register(close_pool)
    return _pool


@contextmanager
def tx() -> Iterator[psycopg.Connection]:
    """A transaction: commits on success, rolls back on exception."""
    with pool().connection() as conn:
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise


SCHEMA = """
-- The append-only event log: the single source of truth for every run.
CREATE TABLE IF NOT EXISTS events (
    id              BIGSERIAL PRIMARY KEY,
    run_id          UUID        NOT NULL,
    seq             INT         NOT NULL,
    event_type      TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    idempotency_key TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (run_id, seq)
);
CREATE INDEX IF NOT EXISTS idx_events_run ON events (run_id, seq);
CREATE INDEX IF NOT EXISTS idx_events_id  ON events (id);

-- Derived read-model cache. ALWAYS rebuildable from `events` — never the
-- source of truth. The worker refreshes it; the API may read it for speed.
CREATE TABLE IF NOT EXISTS run_status (
    run_id      UUID PRIMARY KEY,
    workflow    TEXT        NOT NULL,
    status      TEXT        NOT NULL,   -- RUNNING | PAUSED | COMPLETED | FAILED
    waiting_for TEXT,
    verdict     TEXT,                   -- pass | reject | null
    score       DOUBLE PRECISION,
    image_id    TEXT,
    heatmap     TEXT,
    auto        BOOLEAN,
    stage       TEXT,
    n_events    INT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Side-effect sinks. The PRIMARY KEY on the deterministic idempotency key is
-- what makes side effects exactly-once even if the worker crashes AFTER the
-- effect fired but BEFORE its ACTIVITY_COMPLETED event was persisted.
CREATE TABLE IF NOT EXISTS alerts (
    idem_key   TEXT PRIMARY KEY,
    run_id     UUID NOT NULL,
    payload    JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS verdicts (
    idem_key   TEXT PRIMARY KEY,
    run_id     UUID NOT NULL,
    verdict    TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Toy sink for the crash-recovery tests: a side effect we can prove fired
-- exactly once even across an injected crash + replay.
CREATE TABLE IF NOT EXISTS toy_calls (
    idem_key   TEXT PRIMARY KEY,
    run_id     UUID NOT NULL,
    value      INT  NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Engine-level effect cache: short-circuits re-execution of an activity whose
-- result is already known, so completed (especially expensive) activities such
-- as inference are never recomputed on replay.
CREATE TABLE IF NOT EXISTS effect_log (
    idem_key   TEXT PRIMARY KEY,
    result     JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def init_schema() -> None:
    with tx() as conn:
        conn.execute(SCHEMA)


def reset_all() -> None:
    """Drop all rows (used by tests and the demo seeder). Keeps schema."""
    with tx() as conn:
        conn.execute("TRUNCATE events, run_status, alerts, verdicts, effect_log, toy_calls")
