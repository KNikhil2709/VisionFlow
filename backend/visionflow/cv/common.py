"""Shared CV helpers: image loading, a jet colormap, and heatmap overlays.
Pure numpy + Pillow — no torch, runs on any CPU."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

IMG_SIZE = 256


def load_gray(path: str | Path, size: int = IMG_SIZE) -> np.ndarray:
    """Load an image as a float grayscale array in [0,1], resized to size×size."""
    img = Image.open(path).convert("L").resize((size, size))
    return np.asarray(img, dtype=np.float64) / 255.0


def load_rgb(path: str | Path, size: int = IMG_SIZE) -> np.ndarray:
    img = Image.open(path).convert("RGB").resize((size, size))
    return np.asarray(img, dtype=np.float64) / 255.0


def jet(x: np.ndarray) -> np.ndarray:
    """Minimal jet-like colormap. x in [0,1] -> RGB uint8 (no matplotlib)."""
    x = np.clip(x, 0, 1)
    r = np.clip(1.5 - np.abs(4 * x - 3), 0, 1)
    g = np.clip(1.5 - np.abs(4 * x - 2), 0, 1)
    b = np.clip(1.5 - np.abs(4 * x - 1), 0, 1)
    return (np.stack([r, g, b], axis=-1) * 255).astype(np.uint8)


def save_overlay(gray: np.ndarray, anomaly: np.ndarray, out_path: str | Path,
                 alpha: float = 0.6) -> None:
    """Blend a per-pixel anomaly map (0..1) over the grayscale image and save."""
    base = np.stack([gray] * 3, axis=-1)
    heat = jet(anomaly).astype(np.float64) / 255.0
    a = (np.clip(anomaly, 0, 1)[..., None]) * alpha
    out = np.clip(base * (1 - a) + heat * a, 0, 1)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((out * 255).astype(np.uint8)).save(out_path)
