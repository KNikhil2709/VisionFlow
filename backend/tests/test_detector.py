"""Covers the real CPU anomaly detector: it must separate good from defective
sample images (this is the actual computer-vision guarantee)."""
from __future__ import annotations

import numpy as np

from visionflow.cv import classical, samples


from visionflow.cv.evaluate import auroc


def test_detector_separates_good_from_defect(tmp_path):
    samples.generate()  # deterministic
    det = classical.fit(samples.list_split("train/good"))

    def sc(p):
        return det.score_and_heatmap(p, tmp_path / "hm.png")["score"]

    good = np.array([sc(p) for p in samples.list_split("test/good")])
    defect = np.array([sc(p) for p in samples.list_split("test/defect")])

    assert good.mean() < defect.mean()           # normals score lower
    assert auroc(good, defect) >= 0.9           # strong separation
    assert good.mean() < 0.5                      # normals sit low
    assert defect.mean() > 0.6                    # defects sit high
