"""Pairwise claim comparison and the fixed feature vector used by the learned scorer."""
from __future__ import annotations
from dataclasses import dataclass, field
from ..schemas import EvidenceClaim
from ..extraction.normalization import (DateParse, compare_dates, ocr_fold, normalize_id, edit_distance,
                                        name_similarity, address_similarity)
from ..extraction.deterministic import FIELD_KIND

STATUSES = ("equal", "variant", "ocr_confusable", "ambiguous", "conflict", "unknown")
FEATURE_NAMES = ["link_strength", "st_conflict", "st_ocr_confusable", "st_ambiguous", "st_variant", "st_unknown",
                 "dissimilarity", "min_ocr", "mean_ocr", "ocr_missing", "edit_norm", "is_id", "is_date",
                 "is_name", "is_addr", "is_temporal", "age_margin", "corroboration", "n_group"]
AGE_MIN, AGE_MAX = 15, 70


@dataclass
class PairComparison:
    unit: str
    a: EvidenceClaim
    b: EvidenceClaim
    status: str
    similarity: float
    kind: str
    margin: float = 0.0
    edit_norm: float = 0.0
    link_strength: float = 1.0
    corroboration: float = 0.0
    n_group: int = 2
    features: list[float] = field(default_factory=list)


def _dp(c: EvidenceClaim) -> DateParse:
    ok = c.normalized_value is not None and "unparseable_date" not in c.flags
    return DateParse(raw=c.raw_value, iso=c.normalized_value, candidates=list(c.alternatives) or ([c.normalized_value] if ok else []),
                     ambiguous=bool(c.alternatives), valid=ok)


def compare_claims(a: EvidenceClaim, b: EvidenceClaim) -> PairComparison:
    kind = FIELD_KIND.get(a.field_name, "text")
    unit = f"{a.entity_type}.{a.field_name}"
    same_raw = a.raw_value.strip() == b.raw_value.strip()
    sim, edn, status = 1.0, 0.0, "unknown"
    if kind == "date":
        r = compare_dates(_dp(a), _dp(b))
        status = {"equal": "equal" if same_raw else "variant", "compatible_ambiguous": "ambiguous", "conflict": "conflict", "unknown": "unknown"}[r]
        sim = 1.0 if status in ("equal", "variant") else 0.0
    elif kind == "id":
        x, y = normalize_id(a.raw_value), normalize_id(b.raw_value)
        edn = edit_distance(x, y) / max(len(x), len(y), 1)
        if x == y:
            status = "equal" if same_raw else "variant"
        elif ocr_fold(x) == ocr_fold(y):
            status = "ocr_confusable"
        else:
            status = "conflict"
        sim = 1 - edn
    elif kind == "name":
        sim = name_similarity(a.raw_value, b.raw_value)
        status = ("equal" if same_raw else "variant") if sim >= 0.86 else ("ambiguous" if sim >= 0.7 else "conflict")
    elif kind == "address":
        sim = address_similarity(a.raw_value, b.raw_value)
        status = ("equal" if same_raw else "variant") if sim >= 0.8 else ("ambiguous" if sim >= 0.5 else "conflict")
    else:
        status = "equal" if a.normalized_value == b.normalized_value and a.normalized_value is not None else "conflict"
        if a.normalized_value is None or b.normalized_value is None:
            status = "unknown"
        sim = 1.0 if status == "equal" else 0.0
    return PairComparison(unit, a, b, status, sim, kind, edit_norm=edn)


def temporal_dob_qualification(dob: EvidenceClaim, qual: EvidenceClaim) -> PairComparison:
    """Cross-FIELD check: a person cannot pass a qualification at an implausible age. Needs an entity link."""
    p = _dp(dob)
    year = qual.normalized_value
    if not p.valid or year is None:
        st, margin = "unknown", 0.0
    else:
        age = year - int(p.iso[:4])
        margin = float(min(age - AGE_MIN, AGE_MAX - age))
        st = "conflict" if margin < 0 else "equal"
    return PairComparison("person.dob_vs_qualification", dob, qual, st, 1.0 if st == "equal" else 0.0, "temporal", margin=margin)


def finalize_features(p: PairComparison) -> PairComparison:
    confs = [c.ocr_confidence for c in (p.a, p.b) if c.ocr_confidence is not None]
    lo = min(confs) / 100 if confs else 0.0
    mean = sum(confs) / len(confs) / 100 if confs else 0.0
    p.features = [p.link_strength, p.status == "conflict", p.status == "ocr_confusable", p.status == "ambiguous",
                  p.status == "variant", p.status == "unknown", 1 - p.similarity, lo, mean, not confs, p.edit_norm,
                  p.kind == "id", p.kind == "date", p.kind == "name", p.kind == "address", p.kind == "temporal",
                  max(min(p.margin, 30), -30) / 30, p.corroboration, p.n_group]
    p.features = [float(x) for x in p.features]
    return p
