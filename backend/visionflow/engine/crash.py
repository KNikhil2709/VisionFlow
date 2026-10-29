"""Deterministic crash injection.

Used by tests to kill the worker at a precise boundary, and by the API's
"simulate crash" button in the demo. A crash point is a string label such as
``after_sideeffect:send_alert``; arming one makes the next matching boundary
raise CrashInjected exactly once.
"""
from __future__ import annotations

import threading

from .errors import CrashInjected

_lock = threading.Lock()
_armed: set[str] = set()


def arm(point: str) -> None:
    with _lock:
        _armed.add(point)


def disarm_all() -> None:
    with _lock:
        _armed.clear()


def armed_points() -> set[str]:
    with _lock:
        return set(_armed)


def maybe_crash(point: str) -> None:
    """If `point` is armed, consume it and raise CrashInjected."""
    with _lock:
        if point in _armed:
            _armed.discard(point)
            raise CrashInjected(point)
