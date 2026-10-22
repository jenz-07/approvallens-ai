"""Active review: rank unresolved findings by expected uncertainty reduction per unit review cost.

Uses a binary-outcome model of a finding's resolution (a reviewer inspecting it reveals the label).
Information gain of a perfect inspection = H(p). Baseline = plain uncertainty sampling = same ordering
when costs are equal; the cost/impact terms are where they differ.
"""
from __future__ import annotations
import math
from dataclasses import dataclass


def entropy(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


@dataclass
class ReviewItem:
    finding_id: str
    unit: str
    probability: float
    review_cost: float = 1.0        # e.g. minutes; low OCR quality or multi-page lookups cost more
    decision_impact: float = 1.0    # weight: does the outcome change the submission recommendation?


def priority(item: ReviewItem, reviewer_reliability: float = 1.0) -> float:
    return entropy(item.probability) * item.decision_impact * reviewer_reliability / max(item.review_cost, 1e-6)


def rank(items: list[ReviewItem]) -> list[tuple[ReviewItem, float]]:
    return sorted(((i, priority(i)) for i in items), key=lambda t: -t[1])


def uncertainty_sampling_rank(items):
    return sorted(items, key=lambda i: abs(i.probability - 0.5))
