"""Calibration (isotonic / Platt) fitted on a split separate from training and test, plus metrics."""
from __future__ import annotations
import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold


def _logit(p):
    p = np.clip(np.asarray(p, float), 1e-4, 1 - 1e-4)
    return np.log(p / (1 - p))


def brier(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return float(np.mean((p - y) ** 2))


def nll(y, p):
    y, p = np.asarray(y, float), np.clip(np.asarray(p, float), 1e-6, 1 - 1e-6)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def ece(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    tot, n = 0.0, len(y)
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            tot += m.sum() / n * abs(y[m].mean() - p[m].mean())
    return float(tot)


def reliability(y, p, bins=10):
    y, p = np.asarray(y, float), np.asarray(p, float)
    edges = np.linspace(0, 1, bins + 1)
    out = []
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (p >= lo) & ((p < hi) if hi < 1 else (p <= hi))
        if m.any():
            out.append({"bin": [float(lo), float(hi)], "n": int(m.sum()), "mean_pred": float(p[m].mean()), "frac_pos": float(y[m].mean())})
    return out


class Calibrator:
    """method in {'isotonic','platt'}; fit on a held-out calibration set ONLY."""
    version = "calibrator/1"

    def __init__(self, method: str):
        self.method, self.model = method, None

    def fit(self, scores, y):
        s, y = np.asarray(scores, float), np.asarray(y, int)
        if self.method == "isotonic":
            self.model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(s, y)
        else:
            self.model = LogisticRegression(C=1e6, max_iter=1000).fit(_logit(s).reshape(-1, 1), y)
        return self

    def predict(self, scores):
        s = np.asarray(scores, float)
        if self.method == "isotonic":
            return np.clip(self.model.predict(s), 0.0, 1.0)
        return self.model.predict_proba(_logit(s).reshape(-1, 1))[:, 1]


def select_calibrator(scores, y, seed=0):
    """Choose method by cross-validated NLL on the calibration set (never the test set)."""
    s, y = np.asarray(scores, float), np.asarray(y, int)
    res = {}
    if y.sum() < 5 or (1 - y).sum() < 5:
        return Calibrator("platt").fit(s, y), {"note": "too few positives/negatives for CV; defaulted to platt"}
    skf = StratifiedKFold(5, shuffle=True, random_state=seed)
    for method in ("isotonic", "platt"):
        losses = []
        for tr, te in skf.split(s, y):
            cal = Calibrator(method).fit(s[tr], y[tr])
            losses.append(nll(y[te], cal.predict(s[te])))
        res[method] = float(np.mean(losses))
    best = min(res, key=res.get)
    return Calibrator(best).fit(s, y), {"cv_nll": res, "selected": best}
