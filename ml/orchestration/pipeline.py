"""verify_submission: deterministic, idempotent pipeline returning evidence-linked findings.

Works on DocumentRecord objects built from persisted records (see backend/app/evidence_bridge.py).
Failure policy: a failing stage is reported in `stages`; completed results are preserved and the
status becomes 'incomplete'. Nothing is declared 'supported' without evidence ids.
"""
from __future__ import annotations
from ..schemas import DocumentRecord, VerificationFinding
from ..verification.engines import system_d, expected_pair_count
from ..verification.findings import to_finding
from ..verification.comparison import PairComparison
from ..uncertainty.selective_prediction import CostModel, decide

PIPELINE_VERSION = "pipeline/2"


class ModelUnavailable(RuntimeError):
    """Raised by optional model adapters (LLM extractor, semantic verifier) instead of fabricating output."""


def verify_submission(submission_id: str, documents: list[DocumentRecord], scorer=None, calibrator=None, cost_model: CostModel | None = None) -> dict:
    stages: dict[str, str] = {}
    try:
        an = system_d(documents); stages["extract_resolve_graph_rules"] = "ok"
    except Exception as e:                                            # explicit incomplete state, no fabricated result
        return {"submission_id": submission_id, "status": "incomplete", "stages": {"extract_resolve_graph_rules": f"failed: {type(e).__name__}"},
                "findings": [], "claims": [], "graph": None, "pipeline_version": PIPELINE_VERSION}
    cm = cost_model or CostModel()
    findings: list[VerificationFinding] = list(an.rule_findings)
    calibrated = scorer is not None and calibrator is not None
    stages["scoring"] = "calibrated" if calibrated else "uncalibrated_rules_only"
    by_unit: dict[str, list[PairComparison]] = {}
    for p in an.pairs:
        by_unit.setdefault(p.unit, []).append(p)
    for unit, ps in by_unit.items():
        if scorer is not None:
            import numpy as np
            raws = scorer.predict_proba(np.array([p.features for p in ps]))
        for i, p in enumerate(ps):
            if p.status in ("equal", "variant"):
                continue
            if scorer is not None:
                raw = float(raws[i]); prob = float(calibrator.predict([raw])[0]) if calibrator else None
                action = "review" if p.status == "unknown" else decide(prob if prob is not None else raw, cm)
                status = {"flag": "supported", "clear": "resolved", "review": "review_required"}[action]
                if action == "clear":
                    continue
                findings.append(to_finding(p, status, f"{scorer.version}+{getattr(calibrator, 'version', 'uncalibrated')}", raw, prob,
                                           "contradiction" if status == "supported" else "inconclusive"))
            else:                                                     # no calibrated model: never label a score a probability
                low_quality = any(c.ocr_confidence is not None and c.ocr_confidence < 60 for c in (p.a,p.b))
                status = "supported" if p.status == "conflict" and not low_quality else "review_required"
                findings.append(to_finding(p, status, "deterministic_graph_rules", 1.0 if p.status == "conflict" else None, None,
                                           "contradiction" if status == "supported" else "inconclusive"))
    unresolved = sorted(an.unresolved)
    for u in unresolved:
        findings.append(VerificationFinding(f"UNRESOLVED:{u}", "inconclusive", u, [], [], f"Documents may refer to different or the same entity for '{u}'; automatic linking was not safe. Human confirmation required.", "review_required", method="entity_resolution/requires_resolution"))
    for f in findings:
        f.validate()
    return {"submission_id": submission_id, "status": "complete", "stages": stages, "pipeline_version": PIPELINE_VERSION,
            "findings": [f.to_dict() for f in findings], "claims": [c.to_dict() for c in an.claims], "graph": an.graph.to_json(),
            "disclaimer": "A contradiction is evidence requiring review, not proof of fraud or intent."}
