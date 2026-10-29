"""Shared test fixtures. Requires a reachable Postgres (see README). Each test
starts from a clean schema."""
from __future__ import annotations

import os

import pytest

os.environ.setdefault(
    "VF_DATABASE_URL", "postgresql://visionflow:visionflow@127.0.0.1:5432/visionflow")
os.environ.setdefault("VF_SIM_DELAY_MS", "0")  # no artificial delay in tests
# Engine tests are CV-agnostic: use the deterministic simulated scorer so they
# don't depend on the sample dataset. The 'local' backend is covered separately.
os.environ.setdefault("VF_CV_BACKEND", "simulate")

import visionflow.bootstrap  # noqa: E402,F401
from visionflow import db  # noqa: E402
from visionflow.engine import crash  # noqa: E402
from visionflow.activities import EXEC_COUNTS  # noqa: E402


@pytest.fixture(autouse=True)
def clean_db():
    db.init_schema()
    db.reset_all()
    crash.disarm_all()
    EXEC_COUNTS.clear()
    yield
    crash.disarm_all()
