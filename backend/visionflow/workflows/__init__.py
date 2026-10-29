"""Workflow definitions. Importing this module registers them.

Workflow code is deterministic: it only branches on values obtained from the
context (activity results, signals). No model calls, clocks, or randomness here.
"""
from __future__ import annotations

from ..config import settings
from ..engine.context import WorkflowContext
from ..engine.sdk import workflow


@workflow("inspection")
def inspection(ctx: WorkflowContext) -> dict:
    """ingest -> inference -> three-way decision -> (optional human review) ->
    finalize. The decision branch is a pure threshold rule on the score."""
    image_id = ctx.input["image_id"]

    # Older histories retain their original input shape and legacy behavior.
    policy = ctx.input.get("policy")
    t_low = policy["t_low"] if policy else settings.t_low
    t_high = policy["t_high"] if policy else settings.t_high
    ingest_arg = {**ctx.input} if policy else image_id
    img = ctx.call_activity("ingest", ingest_arg)
    inf = ctx.call_activity("run_inference", img)
    score = inf["score"]

    if score < t_low:
        verdict, auto = "pass", True
    elif score > t_high:
        verdict, auto = "reject", True
    else:
        # Ambiguous: park until a human submits a verdict signal.
        decision = ctx.wait_for_signal("human_verdict")
        verdict, auto = decision["verdict"], False

    ctx.call_activity("write_verdict", {"verdict": verdict})
    if verdict == "reject":
        ctx.call_activity("send_alert", {"score": score})

    return {"verdict": verdict, "auto": auto, "score": score,
            "heatmap": inf.get("heatmap"), "image": inf.get("image"),
            "label": inf.get("label")}


@workflow("toy_adder")
def toy_adder(ctx: WorkflowContext) -> dict:
    """Minimal workflow used by the crash-recovery tests: two side-effecting
    'add' activities chained, so every step boundary can be crash-tested."""
    a = ctx.input["a"]
    b = ctx.input["b"]
    s1 = ctx.call_activity("toy_add", {"x": a, "y": b})
    s2 = ctx.call_activity("toy_add", {"x": s1["sum"], "y": 10})
    return {"result": s2["sum"]}
