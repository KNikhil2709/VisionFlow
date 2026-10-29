"""Turn a run's derived state into a plain-English sentence for non-technical
users. Pure function of the derived state dict from engine.replay."""
from __future__ import annotations


def caption(state: dict) -> str:
    status = state.get("status")
    score = state.get("score")
    verdict = state.get("verdict")
    stage = state.get("stage")
    s = f"{score:.2f}" if isinstance(score, (int, float)) else "—"

    if status == "PAUSED":
        return (f"The AI wasn't sure (score {s}), so a person needs to decide "
                f"pass or reject.")
    if status == "FAILED":
        return "Something went wrong while checking this item."
    if status == "COMPLETED":
        how = "automatically" if state.get("auto") else "after a person reviewed it"
        if verdict == "pass":
            return f"Looks fine (score {s}) — passed {how}."
        if verdict == "reject":
            return f"Defect found (score {s}) — rejected {how} and an alert was sent."
        return f"Finished (score {s})."
    # still running
    if stage == "ingest":
        return "Loading the image…"
    if stage == "inference":
        return "The AI is checking the image…"
    if stage in ("decision", "finalize"):
        return "Recording the result…"
    return "Waiting to be checked…"
