"""Classical patch-based anomaly detector (CPU-only, no torch).

This is a lightweight, honest cousin of PatchCore:

  1. Learn "normal" from defect-free images only.
  2. Cut each image into a grid of patches; describe each patch with a small
     hand-crafted feature vector (intensity, texture/gradient, colour).
  3. Keep all normal patch features in a memory bank.
  4. Score a new image per patch by distance to its nearest normal neighbour.
     A patch unlike anything normal = high distance = anomalous. The image
     score is a high percentile of the patch distances; the heatmap is the
     upsampled patch-distance grid.

It runs anywhere numpy runs. For the deep version, see patchcore.py (opt-in).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .common import IMG_SIZE, load_gray, load_rgb, save_overlay

PATCH = 16                      # patch size in pixels
GRID = IMG_SIZE // PATCH        # 16 x 16 = 256 patches per image
BANK_CAP = 3000                 # max patches kept in the memory bank


# --- feature extraction ------------------------------------------------------

def _patch_features(path: str | Path) -> np.ndarray:
    """Return an (GRID*GRID, dim) array of per-patch features for one image."""
    gray = load_gray(path)
    rgb = load_rgb(path)
    gy, gx = np.gradient(gray)
    gmag = np.hypot(gy, gx)
    gori = np.arctan2(gy, gx)  # -pi..pi

    feats = []
    for i in range(GRID):
        for j in range(GRID):
            ys, xs = slice(i * PATCH, (i + 1) * PATCH), slice(j * PATCH, (j + 1) * PATCH)
            g = gray[ys, xs]
            m = gmag[ys, xs]
            o = gori[ys, xs]
            col = rgb[ys, xs].reshape(-1, 3).mean(axis=0)  # mean R,G,B
            # 4-bin gradient-orientation histogram (weighted by magnitude)
            bins = np.clip(((o + np.pi) / (2 * np.pi) * 4).astype(int), 0, 3)
            hist = np.bincount(bins.ravel(), weights=m.ravel(), minlength=4)
            hist = hist / (hist.sum() + 1e-9)
            feats.append(np.concatenate([
                [g.mean(), g.std(), m.mean(), m.std()], col, hist,
            ]))
    return np.asarray(feats, dtype=np.float64)   # (256, 11)


# --- the detector ------------------------------------------------------------

@dataclass
class Detector:
    bank: np.ndarray            # (N, dim) normalised normal-patch features
    feat_mean: np.ndarray       # (dim,) feature normalisation
    feat_std: np.ndarray        # (dim,)
    calib_mean: float           # raw-score mean over held-out normal images
    calib_std: float            # raw-score std over held-out normal images
    suggested_t_low: float = 0.35
    suggested_t_high: float = 0.65

    # --- persistence ---
    def save(self, path: str | Path) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        np.savez_compressed(
            path, bank=self.bank, feat_mean=self.feat_mean, feat_std=self.feat_std,
            calib_mean=self.calib_mean, calib_std=self.calib_std,
            t_low=self.suggested_t_low, t_high=self.suggested_t_high)

    @classmethod
    def load(cls, path: str | Path) -> "Detector":
        d = np.load(path)
        return cls(d["bank"], d["feat_mean"], d["feat_std"],
                   float(d["calib_mean"]), float(d["calib_std"]),
                   float(d["t_low"]), float(d["t_high"]))

    # --- scoring ---
    def _raw_and_map(self, path: str | Path) -> tuple[float, np.ndarray]:
        f = (_patch_features(path) - self.feat_mean) / self.feat_std
        # nearest-neighbour distance per patch to the normal bank
        d = np.sqrt(((f[:, None, :] - self.bank[None, :, :]) ** 2).sum(axis=2))
        patch_dist = d.min(axis=1)                       # (256,)
        raw = float(np.percentile(patch_dist, 99))       # robust image score
        return raw, patch_dist.reshape(GRID, GRID)

    def _normalise(self, raw: float) -> float:
        # Map so a typical normal image sits low and clear anomalies approach 1.
        z = (raw - (self.calib_mean + 2 * self.calib_std)) / (self.calib_std + 1e-9)
        return float(1 / (1 + np.exp(-z)))               # sigmoid -> [0,1]

    def score_and_heatmap(self, path: str | Path, heatmap_out: str | Path) -> dict:
        raw, grid = self._raw_and_map(path)
        score = self._normalise(raw)
        # upsample the 16x16 distance grid to full image, normalise for display
        from PIL import Image
        hm = np.asarray(Image.fromarray(grid).resize((IMG_SIZE, IMG_SIZE),
                        Image.BILINEAR), dtype=np.float64)
        hm = (hm - hm.min()) / (np.ptp(hm) + 1e-9)
        save_overlay(load_gray(path), hm, heatmap_out)
        return {"score": round(score, 4), "raw": round(raw, 4)}


# --- fitting -----------------------------------------------------------------

def fit(train_good: list[str | Path], calib_good: list[str | Path] | None = None,
        seed: int = 0) -> Detector:
    """Build a detector from defect-free images. `calib_good` is a held-out set
    of normal images used only to calibrate the score scale (defaults to a
    split of train_good)."""
    train_good = list(train_good)
    if calib_good is None and len(train_good) >= 10:
        rng = np.random.default_rng(seed)
        idx = rng.permutation(len(train_good))
        k = max(1, len(train_good) // 5)
        calib_good = [train_good[i] for i in idx[:k]]
        train_good = [train_good[i] for i in idx[k:]]
    calib_good = list(calib_good or train_good)

    all_feats = np.vstack([_patch_features(p) for p in train_good])
    feat_mean = all_feats.mean(axis=0)
    feat_std = all_feats.std(axis=0) + 1e-9
    bank = (all_feats - feat_mean) / feat_std
    if bank.shape[0] > BANK_CAP:                          # random subsample
        rng = np.random.default_rng(seed)
        bank = bank[rng.choice(bank.shape[0], BANK_CAP, replace=False)]

    det = Detector(bank=bank, feat_mean=feat_mean, feat_std=feat_std,
                   calib_mean=0.0, calib_std=1.0)
    raws = [det._raw_and_map(p)[0] for p in calib_good]
    det.calib_mean = float(np.mean(raws))
    det.calib_std = float(np.std(raws) + 1e-9)
    return det
