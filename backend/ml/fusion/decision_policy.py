"""Evidence fusion & decision: explicit, transparent rules over calibrated unit probabilities.

Deliberately NOT a product of model confidences (OCR/extraction/reasoning errors are correlated).
"""
from __future__ import annotations
from dataclasses import dataclass
from ..uncertainty.selective_prediction import CostModel, decide


@dataclass
class UnitDecision:
    unit: str
    action: str                 # flag | clear | review
    reason: str
    probability: float | None
    calibration: str | None
    quality: dict


def decide_unit(unit: str, p: float | None, cm: CostModel, *, any_unknown: bool, missing_evidence: bool,
                calibration_name: str | None, quality: dict, use_calibrated: bool = True) -> UnitDecision:
    if missing_evidence:
        return UnitDecision(unit, "review", "missing_evidence", p, calibration_name, quality)
    if any_unknown:
        return UnitDecision(unit, "review", "uncomparable_values", p, calibration_name, quality)
    if p is None:
        return UnitDecision(unit, "clear", "no_candidate_conflict", None, None, quality)
    action = decide(p, cm)
    reason = {"flag": "supported_by_calibrated_probability" if use_calibrated else "supported_by_raw_score",
              "clear": "low_conflict_probability", "review": "probability_in_abstention_band"}[action]
    return UnitDecision(unit, action, reason, p, calibration_name if use_calibrated else None, quality)
