import numpy as np
from ml.uncertainty.calibration import select_calibrator, ece, brier
from ml.uncertainty.selective_prediction import decide, CostModel, risk_coverage
from ml.review.prioritization import ReviewItem, rank, entropy

def test_calibration_reduces_ece_on_overconfident_scores():
    rng = np.random.default_rng(0); s = rng.uniform(0, 1, 4000); y = (rng.uniform(0, 1, 4000) < 0.5 * s + 0.25).astype(int)
    cal, _ = select_calibrator(s[:2000], y[:2000]); assert ece(y[2000:], cal.predict(s[2000:])) < ece(y[2000:], s[2000:])

def test_decision_policy_thresholds():
    cm = CostModel(1, 5, .4); assert decide(.95, cm) == "flag" and decide(.01, cm) == "clear" and decide(.3, cm) == "review"

def test_risk_coverage_monotone_inputs():
    cov, risk, aurc = risk_coverage([0, 1, 1, 0], [.1, .9, .6, .45]); assert cov[-1] == 1 and 0 <= aurc <= 1

def test_review_priority_prefers_uncertain_and_cheap():
    a, b, c = ReviewItem("a", "u", .5, 1), ReviewItem("b", "u", .95, 1), ReviewItem("c", "u", .5, 4)
    assert [i.finding_id for i, _ in rank([b, c, a])] == ["a", "b", "c"] and entropy(.5) == 1
