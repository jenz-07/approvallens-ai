"""Turn pair comparisons into schema-valid, evidence-linked findings with explanations built only from the claims."""
from __future__ import annotations
from ..schemas import VerificationFinding
from .comparison import PairComparison


def explain(p: PairComparison) -> str:
    a, b = p.a, p.b
    if p.kind == "temporal":
        return (f"Date of birth {a.raw_value} (document {a.document_id}) and qualification year {b.raw_value} "
                f"(document {b.document_id}) imply an implausible age. A contradiction needs investigation; it is not proof of intent.")
    if p.status == "conflict":
        return (f"{a.field_name} differs: '{a.raw_value}' in {a.document_id} vs '{b.raw_value}' in {b.document_id}. "
                "This is evidence requiring review, not proof of wrongdoing.")
    if p.status == "ambiguous":
        return f"{a.field_name} values '{a.raw_value}' and '{b.raw_value}' may agree under an alternative reading (format or order). Needs human confirmation."
    if p.status == "ocr_confusable":
        return f"{a.field_name} values '{a.raw_value}' and '{b.raw_value}' differ only by characters OCR commonly confuses; possible extraction error."
    return f"{a.field_name} could not be compared automatically ('{a.raw_value}' vs '{b.raw_value}')."


def to_finding(p: PairComparison, status: str, method: str, score: float | None = None,
               prob: float | None = None, ftype: str | None = None) -> VerificationFinding:
    ftype = ftype or ("contradiction" if p.status == "conflict" or p.kind == "temporal" and p.status == "conflict" else "inconclusive")
    return VerificationFinding(
        finding_id=f"F:{p.unit}:{p.a.claim_id}|{p.b.claim_id}", finding_type=ftype, unit=p.unit,
        claim_ids=[p.a.claim_id, p.b.claim_id], evidence_ids=["ev:" + p.a.claim_id, "ev:" + p.b.claim_id],
        explanation=explain(p), status=status, calibrated_probability=prob, raw_score=score, method=method,
        details={"comparison_status": p.status, "similarity": round(p.similarity, 3)}).validate()
