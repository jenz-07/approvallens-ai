"""Deterministic label-based claim extractor (regex-free label lookup + normalization).

Only labels in LEXICON are recognised. Unknown labels are *reported*, never guessed,
so an unseen template degrades to missing evidence instead of fabricated claims.
"""
from __future__ import annotations
import re
from typing import Iterable
from ..schemas import EvidenceClaim, DocumentRecord, EvidenceRegion
from .normalization import (parse_date, normalize_id, normalize_name, normalize_address, parse_int)

EXTRACTOR_VERSION = "deterministic_label_parser/1"

LEXICON: dict[str, list[str]] = {
    "person_name": ["person name", "full name", "name of applicant", "applicant name", "name", "holder name", "candidate name"],
    "date_of_birth": ["date of birth", "dob", "birth date", "born on"],
    "national_id": ["national id", "id number", "identity no", "id no"],
    "institution_name": ["institution name", "institution", "name of institution", "college name"],
    "institution_id": ["institution id", "institution identifier", "institution code", "college code"],
    "address": ["address", "registered address", "campus address"],
    "reference_number": ["reference number", "ref no", "certificate no", "approval ref"],
    "issue_date": ["issue date", "date of issue", "issued on"],
    "expiry_date": ["expiry date", "valid until", "valid till", "expires on"],
    "qualification_year": ["year of passing", "passing year", "qualification year", "graduation year"],
    "academic_year": ["academic year"],
    "intake": ["intake", "sanctioned intake"],
}
LABEL_TO_FIELD = {l: f for f, ls in LEXICON.items() for l in ls}
FIELD_ENTITY = {"person_name": "person", "date_of_birth": "person", "national_id": "person",
                "qualification_year": "person", "institution_name": "institution", "institution_id": "institution",
                "address": "institution", "reference_number": "institution", "issue_date": "institution",
                "expiry_date": "institution", "academic_year": "institution", "intake": "institution"}
FIELD_KIND = {"date_of_birth": "date", "issue_date": "date", "expiry_date": "date", "national_id": "id",
              "institution_id": "id", "reference_number": "id", "person_name": "name", "institution_name": "name",
              "address": "address", "qualification_year": "int", "intake": "int", "academic_year": "text"}


def normalize_value(field: str, raw: str):
    kind = FIELD_KIND.get(field, "text")
    if kind == "date":
        p = parse_date(raw)
        return (p.iso, p.candidates if p.ambiguous else [], ([] if p.valid else ["unparseable_date"]) + (["ambiguous_date"] if p.ambiguous else []))
    if kind == "id":
        return normalize_id(raw), [], []
    if kind == "name":
        return normalize_name(raw), [], []
    if kind == "address":
        return normalize_address(raw), [], []
    if kind == "int":
        v = parse_int(raw)
        return v, [], ([] if v is not None else ["unparseable_number"])
    return re.sub(r"\s+", " ", raw.strip().lower()), [], []


def extract_claims(doc: DocumentRecord) -> tuple[list[EvidenceClaim], dict]:
    claims: list[EvidenceClaim] = []
    unrecognized: list[str] = []
    seen: dict[str, int] = {}
    for page in doc.pages:
        pno = page.get("page", 1)
        lines = page.get("lines") or [{"text": t, "bbox": None, "conf": None} for t in page.get("text", "").splitlines()]
        for ln in lines:
            text = (ln.get("text") or "").strip()
            if ":" not in text:
                continue
            label, value = text.split(":", 1)
            label = re.sub(r"[_\s]+", " ", label.strip().lower())
            value = value.strip()
            if not value:
                continue
            fld = LABEL_TO_FIELD.get(label)
            if fld is None:
                unrecognized.append(label)
                continue
            norm, alts, flags = normalize_value(fld, value)
            seen[fld] = seen.get(fld, 0) + 1
            c = EvidenceClaim(
                claim_id=f"{doc.document_id}:{fld}:{seen[fld]}", document_id=doc.document_id, field_name=fld,
                raw_value=value, normalized_value=norm, source_page=pno,
                source_bbox=tuple(ln["bbox"]) if ln.get("bbox") else None, extractor_name=EXTRACTOR_VERSION,
                ocr_confidence=ln.get("conf"), entity_type=FIELD_ENTITY[fld], document_kind=doc.kind,
                alternatives=alts, flags=flags)
            claims.append(c.validate())
    for fld, n in seen.items():
        if n > 1:
            for c in claims:
                if c.field_name == fld and c.document_id == doc.document_id:
                    c.flags.append("multiple_candidates")
    return claims, {"unrecognized_labels": sorted(set(unrecognized))}


def evidence_for(claims: Iterable[EvidenceClaim]) -> dict[str, EvidenceRegion]:
    return {c.claim_id: EvidenceRegion(evidence_id="ev:" + c.claim_id, claim_id=c.claim_id, document_id=c.document_id,
                                        page=c.source_page, bbox=c.source_bbox, excerpt=f"{c.field_name}: {c.raw_value}")
            for c in claims}
