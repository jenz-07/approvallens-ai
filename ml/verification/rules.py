"""Deterministic, versioned, independently testable rules shared by every baseline."""
from __future__ import annotations
from ..schemas import VerificationFinding, DocumentRecord, EvidenceClaim
from .requirements import EXPECTED_FIELDS, RULESET_VERSION
from ..extraction.normalization import parse_date

RULES = {"R-DATE-ORDER": 1, "R-REQUIRED-FIELDS": 1, "R-MULTI-CANDIDATE": 1}


def run_rules(docs: list[DocumentRecord], claims: list[EvidenceClaim]) -> list[VerificationFinding]:
    out: list[VerificationFinding] = []
    by_doc: dict[str, dict[str, list[EvidenceClaim]]] = {}
    for c in claims:
        by_doc.setdefault(c.document_id, {}).setdefault(c.field_name, []).append(c)
    for d in docs:
        if d.superseded:
            continue
        f = by_doc.get(d.document_id, {})
        for fld in EXPECTED_FIELDS.get(d.kind, []):
            if fld not in f:
                out.append(VerificationFinding(f"R-REQUIRED-FIELDS:{d.document_id}:{fld}", "missing_evidence", f"missing.{fld}", [], [],
                           f"Expected field '{fld}' was not found in {d.kind}. This is missing evidence, not proof the value is wrong.",
                           "review_required", method=f"rule:R-REQUIRED-FIELDS/v{RULES['R-REQUIRED-FIELDS']}", details={"document_id": d.document_id}))
        for fld, cs in f.items():
            if len(cs) > 1 and len({c.normalized_value for c in cs}) > 1:
                out.append(VerificationFinding(f"R-MULTI-CANDIDATE:{d.document_id}:{fld}", "inconclusive", f"doc.multi.{fld}",
                           [c.claim_id for c in cs], ["ev:" + c.claim_id for c in cs],
                           f"{d.kind} lists several different values for '{fld}'; the intended value is unclear.", "review_required",
                           method="rule:R-MULTI-CANDIDATE/v1"))
        if "issue_date" in f and "expiry_date" in f:
            i, e = f["issue_date"][0], f["expiry_date"][0]
            pi, pe = parse_date(i.raw_value), parse_date(e.raw_value)
            if pi.valid and pe.valid and not set(pi.candidates) & set(pe.candidates) and min(pe.candidates) < min(pi.candidates):
                out.append(VerificationFinding(f"R-DATE-ORDER:{d.document_id}", "rule_violation", "doc.date_order",
                           [i.claim_id, e.claim_id], ["ev:" + i.claim_id, "ev:" + e.claim_id],
                           f"Expiry date {e.raw_value} is earlier than issue date {i.raw_value} in the same document.",
                           "supported", raw_score=1.0, method="rule:R-DATE-ORDER/v1"))
    return out
