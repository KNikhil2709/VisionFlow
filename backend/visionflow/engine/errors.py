"""Control-flow signals used internally by the engine. These are NOT errors in
the normal sense — they unwind the workflow call stack to hand control back to
the worker."""
from __future__ import annotations


class Suspend(Exception):
    """Raised by WorkflowContext.wait_for_signal when the awaited signal is not
    yet in history. The worker catches it and parks the run durably."""

    def __init__(self, signal: str):
        self.signal = signal
        super().__init__(f"suspended waiting for signal: {signal}")


class CrashInjected(Exception):
    """Raised by the crash hook to simulate a process dying at a precise point.
    Propagates out of the worker so nothing after it runs (mimicking kill -9),
    while everything already committed to Postgres survives."""
