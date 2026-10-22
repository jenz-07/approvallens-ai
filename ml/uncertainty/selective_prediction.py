"""Selective prediction: risk-coverage analysis and cost-sensitive accept/abstain decisions."""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class CostModel:
    """Illustrative costs (NOT stakeholder-validated). Sensitivity is reported in results."""
    c_fp: float = 1.0      # false alarm raised to a reviewer/applicant
    c_fn: float = 5.0      # missed true contradiction
    c_review: float = 0.4  # sending a unit to human review


def decide(p: float, cm: CostModel) -> str:
    """argmin_a E[C | x, a] over {flag, clear, review}."""
    costs = {"flag": (1 - p) * cm.c_fp, "clear": p * cm.c_fn, "review": cm.c_review}
    return min(costs, key=costs.get)


def risk_coverage(y, p, threshold=0.5):
    """Sort by confidence max(p,1-p); returns arrays (coverage, selective_risk) plus AURC."""
    import numpy as np
    y, p = np.asarray(y, int), np.asarray(p, float)
    pred = (p >= threshold).astype(int)
    conf = np.maximum(p, 1 - p)
    order = np.argsort(-conf, kind="stable")
    err = (pred != y)[order].astype(float)
    n = np.arange(1, len(y) + 1)
    risk = np.cumsum(err) / n
    cov = n / len(y)
    return cov, risk, float(np.mean(risk))


def evaluate_decisions(y, decisions, cm: CostModel):
    import numpy as np
    y = np.asarray(y, int)
    d = np.asarray(decisions)
    flag, clear, rev = d == "flag", d == "clear", d == "review"
    tp, fp = int((flag & (y == 1)).sum()), int((flag & (y == 0)).sum())
    fn, tn = int((clear & (y == 1)).sum()), int((clear & (y == 0)).sum())
    accepted = flag | clear
    n = len(y)
    return {"n": n, "coverage": float(accepted.mean()) if n else 0.0, "review_rate": float(rev.mean()) if n else 0.0,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "selective_risk": float((fp + fn) / accepted.sum()) if accepted.sum() else 0.0,
            "reviewed_positives": int((rev & (y == 1)).sum()), "reviewed_negatives": int((rev & (y == 0)).sum()),
            "expected_cost": float((fp * cm.c_fp + fn * cm.c_fn + rev.sum() * cm.c_review) / n) if n else 0.0}
