"""Interpretable learned contradiction scorer: logistic regression over pair features (Section 6.2)."""
from __future__ import annotations
import numpy as np
from sklearn.linear_model import LogisticRegression
from .comparison import FEATURE_NAMES


class PairScorer:
    version = "pair_logreg/1"

    def __init__(self, seed: int = 42, C: float = 1.0):
        self.model = LogisticRegression(C=C, max_iter=2000, random_state=seed, class_weight=None)

    def fit(self, X, y):
        self.model.fit(np.asarray(X, float), np.asarray(y, int))
        return self

    def predict_proba(self, X):
        X = np.asarray(X, float)
        return self.model.predict_proba(X)[:, 1] if len(X) else np.array([])

    def coefficients(self):
        return dict(zip(FEATURE_NAMES, map(float, self.model.coef_[0]))) | {"bias": float(self.model.intercept_[0])}
