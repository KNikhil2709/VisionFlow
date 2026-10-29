"""Deterministic simulated anomaly scorer.

This is the default CV backend so the whole system runs end-to-end with no torch
and no MVTec download. Scores are a stable function of the image id, arranged so
that "normal" parts cluster low, "defect" parts cluster high, with a deliberate
overlap band that lands some runs in the human-review queue (exactly what the
orchestration layer exists to handle). A matching heatmap PNG is rendered so the
UI has something real to show. Swap VF_CV_BACKEND=patchcore for the real model.
"""
from __future__ import annotations

import hashlib

import numpy as np
from PIL import Image

from ..config import settings


def _u(image_id: str, salt: str = "") -> float:
    """Stable uniform in [0,1) from an id."""
    h = hashlib.sha256((salt + image_id).encode()).digest()
    return int.from_bytes(h[:8], "big") / 2**64


def is_defect(image_id: str) -> bool:
    return "defect" in image_id.lower()


def score_for(image_id: str) -> float:
    u = _u(image_id, "score")
    if is_defect(image_id):
        return round(0.45 + 0.50 * u, 4)      # ~[0.45, 0.95]
    return round(0.08 + 0.42 * u, 4)          # ~[0.08, 0.50]


def _jet(x: np.ndarray) -> np.ndarray:
    """Minimal jet-like colormap (no matplotlib). x in [0,1] -> RGB uint8."""
    x = np.clip(x, 0, 1)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def _base_image(image_id: str, size: int = 256) -> np.ndarray:
    """A synthetic grayscale 'part' surface with subtle texture."""
    rng = np.random.default_rng(int(_u(image_id, "img") * 1e9))
    yy, xx = np.mgrid[0:size, 0:size] / size
    surface = 0.5 + 0.12 * np.sin(12 * xx) * np.cos(9 * yy)
    surface += 0.04 * rng.standard_normal((size, size))
    # A circular 'part' mask so it reads as an object, not a plain square.
    cx, cy, r = 0.5, 0.5, 0.42
    mask = ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2
    surface = np.where(mask, surface, 0.06)
    return np.clip(surface, 0, 1)


def score_and_heatmap(image_id: str, size: int = 256) -> dict:
    """Produce the image, an anomaly heatmap overlay, and a score. Writes PNGs
    and returns their paths relative to the data dir."""
    score = score_for(image_id)
    base = _base_image(image_id, size)

    # Anomaly field: a hot gaussian blob for defects (at a stable location),
    # faint diffuse noise for normals.
    yy, xx = np.mgrid[0:size, 0:size] / size
    field = np.zeros((size, size), dtype=np.float64)
    if is_defect(image_id):
        bx, by = _u(image_id, "bx") * 0.5 + 0.25, _u(image_id, "by") * 0.5 + 0.25
        sigma = 0.05 + 0.04 * _u(image_id, "sig")
        field = np.exp(-(((xx - bx) ** 2 + (yy - by) ** 2) / (2 * sigma ** 2)))
        field *= score
    field += 0.06 * np.random.default_rng(7).random((size, size)) * score

    # Compose overlay: grayscale part + translucent heatmap.
    base_rgb = np.stack([base] * 3, axis=-1)
    heat_rgb = _jet(field).astype(np.float64) / 255.0
    alpha = np.clip(field, 0, 1)[..., None] * 0.75
    overlay = (base_rgb * (1 - alpha) + heat_rgb * alpha)
    overlay = (np.clip(overlay, 0, 1) * 255).astype(np.uint8)

    image_rel = f"images/{image_id}.png"
    heat_rel = f"heatmaps/{image_id}.png"
    Image.fromarray((base * 255).astype(np.uint8)).save(settings.data_dir / image_rel)
    Image.fromarray(overlay).save(settings.data_dir / heat_rel)

    return {
        "score": score,
        "image": image_rel,
        "heatmap": heat_rel,
        "backend": "simulate",
        "label": "defect" if is_defect(image_id) else "normal",
    }
