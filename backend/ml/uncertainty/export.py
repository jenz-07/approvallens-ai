"""numpy-only export/import of the trained pair scorer + calibrator, so the API needs no scikit-learn."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np
from ..verification.comparison import FEATURE_NAMES


def export_model(scorer, calibrator, path: Path, provenance: dict):
    cal = {"method": calibrator.method}
    if calibrator.method == "isotonic":
        m = calibrator.model
        cal.update(x=[float(v) for v in m.X_thresholds_], y=[float(v) for v in m.y_thresholds_])
    else:
        cal.update(a=float(calibrator.model.coef_[0][0]), b=float(calibrator.model.intercept_[0]))
    doc = {"features": FEATURE_NAMES, "coef": [float(v) for v in scorer.model.coef_[0]], "intercept": float(scorer.model.intercept_[0]),
           "calibrator": cal, "provenance": provenance,
           "warning": "Trained and calibrated on SYNTHETIC VerifyBench data only. Not validated on real documents."}
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(json.dumps(doc, indent=1))


class LoadedScorer:
    def __init__(self, d):
        self.coef, self.b, self.version = np.array(d["coef"]), d["intercept"], "pair_logreg/1(json)"

    def predict_proba(self, X):
        z = np.asarray(X, float) @ self.coef + self.b
        return 1 / (1 + np.exp(-z))


class LoadedCalibrator:
    def __init__(self, c):
        self.c, self.method = c, c["method"]; self.version = f"calibrator/{self.method}(json)"

    def predict(self, s):
        s = np.asarray(s, float)
        if self.method == "isotonic":
            return np.clip(np.interp(s, self.c["x"], self.c["y"]), 0, 1)
        p = np.clip(s, 1e-4, 1 - 1e-4)
        return 1 / (1 + np.exp(-(self.c["a"] * np.log(p / (1 - p)) + self.c["b"])))


def load_model(path: Path):
    d = json.loads(Path(path).read_text())
    return LoadedScorer(d), LoadedCalibrator(d["calibrator"]), d
