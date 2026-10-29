"""The tiny workflow/activity SDK.

A *workflow* is deterministic orchestration code: it may only branch on values
it got from the context (activity results, signals). It must never call a model,
read the clock, or use randomness directly — otherwise replay would diverge.

An *activity* is where all non-determinism and side effects live: model
inference, file I/O, sending an alert. Activities are executed at most once and
their results are recorded in the event log.
"""
from __future__ import annotations

from typing import Callable

_WORKFLOWS: dict[str, Callable] = {}
_ACTIVITIES: dict[str, Callable] = {}

# Activities whose side effect is external (not just compute) and therefore
# must dedupe at their sink using the idempotency key.
_SIDE_EFFECTING: set[str] = set()


def workflow(name: str):
    def deco(fn: Callable) -> Callable:
        _WORKFLOWS[name] = fn
        fn._vf_workflow_name = name  # type: ignore[attr-defined]
        return fn
    return deco


def activity(name: str, *, side_effecting: bool = False):
    def deco(fn: Callable) -> Callable:
        _ACTIVITIES[name] = fn
        if side_effecting:
            _SIDE_EFFECTING.add(name)
        fn._vf_activity_name = name  # type: ignore[attr-defined]
        return fn
    return deco


def get_workflow(name: str) -> Callable:
    return _WORKFLOWS[name]


def get_activity(name: str) -> Callable:
    return _ACTIVITIES[name]


def is_side_effecting(name: str) -> bool:
    return name in _SIDE_EFFECTING
