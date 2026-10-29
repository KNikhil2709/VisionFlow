import pytest

from visionflow.cv.evaluate import auroc, decision_metrics


def test_auroc_ties():
    assert auroc([0.5, 0.5], [0.5, 0.5]) == 0.5
    assert auroc([0.1, 0.5], [0.5, 0.9]) == 0.875
    assert auroc([0.1], [0.9]) == 1.0
    assert auroc([0.9], [0.1]) == 0.0
    with pytest.raises(ValueError):
        auroc([], [0.5])


def test_operating_metrics_include_threshold_boundaries_in_review():
    metrics = decision_metrics([0.1, 0.8], [0.2, 0.35, 0.65, 0.9], 0.35, 0.65)
    assert metrics["missed_defect_rate"] == 0.25
    assert metrics["false_reject_rate"] == 0.5
    assert metrics["review_rate"] == pytest.approx(2 / 6)
