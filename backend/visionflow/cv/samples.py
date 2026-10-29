"""Generate a small, REAL image dataset so the detector has actual pixels to
work on with no external download. Images are synthetic but genuine PNGs: a
consistent 'brushed-metal part' texture for normal pieces, plus visible defects
(scratch, stain, hole, dent) for the defective ones.

Layout under <data>/samples/:
    train/good/*.png     (normal only — used to learn 'normal')
    test/good/*.png      (normal, held out)
    test/defect/*.png    (one visible defect each)
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from ..config import settings
from .common import IMG_SIZE


def _part_mask(size: int) -> np.ndarray:
    yy, xx = np.mgrid[0:size, 0:size] / size
    return ((xx - 0.5) ** 2 + (yy - 0.5) ** 2) < 0.45 ** 2


def _good_surface(rng: np.random.Generator, size: int = IMG_SIZE) -> np.ndarray:
    """A consistent brushed-metal look: horizontal grain + mild noise."""
    yy, xx = np.mgrid[0:size, 0:size] / size
    grain = 0.5 + 0.10 * np.sin(2 * np.pi * (6 * yy + 0.15 * np.sin(8 * xx)))
    grain += 0.03 * rng.standard_normal((size, size))
    grain += 0.04 * np.sin(2 * np.pi * 40 * yy)          # fine brushing
    surf = np.where(_part_mask(size), grain, 0.05)
    return np.clip(surf, 0, 1)


def _add_defect(img: np.ndarray, rng: np.random.Generator, kind: str) -> np.ndarray:
    size = img.shape[0]
    yy, xx = np.mgrid[0:size, 0:size] / size
    mask = _part_mask(size)
    out = img.copy()
    if kind == "scratch":
        x0, y0 = rng.uniform(0.3, 0.7, 2)
        ang = rng.uniform(0, np.pi)
        dist = np.abs((xx - x0) * np.sin(ang) - (yy - y0) * np.cos(ang))
        line = (dist < 0.004) & (np.hypot(xx - x0, yy - y0) < 0.25) & mask
        out[line] = rng.choice([0.95, 0.02])
    elif kind == "stain":
        cx, cy = rng.uniform(0.3, 0.7, 2)
        r = rng.uniform(0.05, 0.1)
        blob = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r ** 2)))
        out = np.where(mask, np.clip(out - 0.5 * blob, 0, 1), out)
    elif kind == "hole":
        cx, cy = rng.uniform(0.35, 0.65, 2)
        r = rng.uniform(0.04, 0.07)
        hole = ((xx - cx) ** 2 + (yy - cy) ** 2) < r ** 2
        out[hole & mask] = 0.0
    elif kind == "dent":
        cx, cy = rng.uniform(0.3, 0.7, 2)
        r = rng.uniform(0.07, 0.12)
        d = np.exp(-(((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * r ** 2)))
        out = np.where(mask, np.clip(out + 0.35 * d * np.sin(60 * xx), 0, 1), out)
    return out


DEFECT_KINDS = ["scratch", "stain", "hole", "dent"]


def _save(arr: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(arr, 0, 1) * 255).astype(np.uint8)).save(path)


def generate(n_train: int = 40, n_test_good: int = 20, n_test_defect: int = 20,
             seed: int = 0) -> dict:
    """Write the sample dataset; returns the counts and root path."""
    root = settings.samples_dir
    rng = np.random.default_rng(seed)
    for i in range(n_train):
        _save(_good_surface(rng), root / "train" / "good" / f"{i:03d}.png")
    for i in range(n_test_good):
        _save(_good_surface(rng), root / "test" / "good" / f"{i:03d}.png")
    for i in range(n_test_defect):
        kind = DEFECT_KINDS[i % len(DEFECT_KINDS)]
        img = _add_defect(_good_surface(rng), rng, kind)
        _save(img, root / "test" / "defect" / f"{kind}_{i:03d}.png")
    return {"root": str(root), "train": n_train,
            "test_good": n_test_good, "test_defect": n_test_defect}


def list_split(split: str) -> list[Path]:
    """split like 'train/good' or 'test/defect' -> sorted png paths."""
    d = settings.samples_dir / split
    return sorted(d.glob("*.png")) if d.exists() else []
