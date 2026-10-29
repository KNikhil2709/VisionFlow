"""Central configuration for VisionFlow.

All runtime knobs live here so the rest of the code never reads os.environ
directly. Values can be overridden with VF_* environment variables.
"""
from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo-root/data lives two levels up from this file's package dir by default.
_DEFAULT_DATA = Path(__file__).resolve().parents[2] / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="VF_", env_file=".env", extra="ignore")

    # --- Storage ---------------------------------------------------------
    database_url: str = "postgresql://visionflow:visionflow@127.0.0.1:5432/visionflow"

    # --- File storage for images / heatmaps ------------------------------
    data_dir: Path = _DEFAULT_DATA

    # --- CV backend ------------------------------------------------------
    # "local"     -> REAL CPU anomaly detector on actual pixels (default).
    # "simulate"  -> deterministic synthetic scorer (fastest, not real CV).
    # "patchcore" -> deep PatchCore (requires torch + an MVTec AD category).
    cv_backend: str = "local"
    mvtec_root: Path | None = None          # e.g. /data/mvtec/bottle
    mvtec_category: str = "bottle"

    # --- Decision thresholds (score in [0, 1]) ---------------------------
    # score < t_low  -> auto-pass; score > t_high -> auto-reject;
    # otherwise -> route to a human reviewer.
    t_low: float = 0.35
    t_high: float = 0.65

    # --- Demo pacing -----------------------------------------------------
    # Artificial per-activity delay so the live flow is visible in the UI.
    sim_delay_ms: int = 350

    # --- Deployment ------------------------------------------------------
    # Allowed CORS origins: "*" for local dev, or a comma-separated list of
    # your deployed frontend origin(s), e.g. "https://visionflow.vercel.app".
    cors_origins: str = "*"

    @property
    def images_dir(self) -> Path:
        return self.data_dir / "images"

    @property
    def heatmaps_dir(self) -> Path:
        return self.data_dir / "heatmaps"

    @property
    def samples_dir(self) -> Path:
        return self.data_dir / "samples"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def bank_path(self) -> Path:
        return self.data_dir / "detector.npz"


settings = Settings()

# Ensure storage dirs exist at import time (cheap, idempotent).
for _d in (settings.images_dir, settings.heatmaps_dir,
           settings.samples_dir, settings.uploads_dir):
    _d.mkdir(parents=True, exist_ok=True)
