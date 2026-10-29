"""Detector service: lazily builds or loads the memory bank and scores images.

Used by both the durable pipeline (run_inference activity) and the instant
/api/inspect upload endpoint, so a single trained detector backs everything.
"""
from __future__ import annotations

import threading
from pathlib import Path

from ..config import settings
from . import classical, samples
from .classical import Detector

_lock = threading.Lock()
_detector: Detector | None = None


def ensure_samples() -> None:
    """Make sure the sample dataset exists (generates it once if missing)."""
    if not samples.list_split("train/good"):
        samples.generate()


def get_detector() -> Detector:
    """Return the fitted detector, building it on first use and caching to disk."""
    global _detector
    with _lock:
        if _detector is not None:
            return _detector
        if settings.bank_path.exists():
            _detector = Detector.load(settings.bank_path)
            return _detector
        ensure_samples()
        train = samples.list_split("train/good")
        _detector = classical.fit(train)
        _detector.save(settings.bank_path)
        return _detector


def refit() -> dict:
    """Force a rebuild from the current sample set (used by the CLI)."""
    global _detector
    ensure_samples()
    train = samples.list_split("train/good")
    det = classical.fit(train)
    det.save(settings.bank_path)
    with _lock:
        _detector = det
    return {"train_images": len(train), "bank_size": int(det.bank.shape[0]),
            "calib_mean": det.calib_mean, "calib_std": det.calib_std}


def inspect_path(src: str | Path, out_stem: str) -> dict:
    """Score any image file -> {score, heatmap(rel), image(rel)}.
    `out_stem` names the output PNGs under the data dir."""
    det = get_detector()
    heat_rel = f"heatmaps/{out_stem}.png"
    res = det.score_and_heatmap(src, settings.data_dir / heat_rel)
    return {"score": res["score"], "raw": res["raw"],
            "heatmap": heat_rel, "backend": "local"}
