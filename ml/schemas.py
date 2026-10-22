"""Core evidence contracts for the ApprovalLens verification engine.

Plain dataclasses with explicit validation keep the engine dependency-free so it
can be unit-tested without the web stack. Every claim keeps its raw text, source
page and region. `confidence` stays None unless a *calibrated* probability exists;
raw OCR engine scores live in `ocr_confidence` and are never presented as probabilities.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Literal

FINDING_TYPES = ("contradiction", "missing_evidence", "rule_violation", "visual_anomaly", "inconclusive")
FINDING_STATUSES = ("candidate", "supported", "inconclusive", "review_required", "resolved")
EDGE_TYPES = ("EXTRACTED_FROM", "REFERS_TO", "SUPPORTS", "CONTRADICTS", "DERIVED_FROM",
              "REQUIRES", "SUPERSEDES", "REVIEWED_BY")


class SchemaError(ValueError):
    """Raised when a model output or record violates its schema."""


@dataclass
class EvidenceClaim:
    claim_id: str
    document_id: str
    field_name: str
    raw_value: str
    normalized_value: Any = None
    source_page: int = 1
    source_bbox: tuple[float, float, float, float] | None = None
    extractor_name: str = "deterministic_label_parser"
    extractor_version: str = "1"
    confidence: float | None = None          # calibrated probability ONLY; None otherwise
    ocr_confidence: float | None = None      # raw OCR engine score 0-100, NOT a probability
    entity_type: str | None = None
    document_kind: str | None = None
    alternatives: list[Any] = field(default_factory=list)   # other valid readings (ambiguous dates)
    flags: list[str] = field(default_factory=list)

    def validate(self) -> "EvidenceClaim":
        if not self.claim_id or not self.document_id or not self.field_name:
            raise SchemaError("claim_id, document_id and field_name are required")
        if not isinstance(self.raw_value, str):
            raise SchemaError("raw_value must be the original text")
        if self.confidence is not None and not 0.0 <= self.confidence <= 1.0:
            raise SchemaError("confidence must be within [0, 1] or None")
        if self.source_page < 1:
            raise SchemaError("source_page must be >= 1")
        if self.source_bbox is not None and len(self.source_bbox) != 4:
            raise SchemaError("source_bbox must have four numbers")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EvidenceRegion:
    evidence_id: str
    claim_id: str
    document_id: str
    page: int
    bbox: tuple[float, float, float, float] | None
    excerpt: str


@dataclass
class VerificationFinding:
    finding_id: str
    finding_type: str
    unit: str                                  # comparison unit, e.g. "person.date_of_birth"
    claim_ids: list[str]
    evidence_ids: list[str]
    explanation: str
    status: str = "candidate"
    calibrated_probability: float | None = None
    raw_score: float | None = None             # model score; not a probability unless calibrated
    method: str = "deterministic"
    details: dict = field(default_factory=dict)

    def validate(self) -> "VerificationFinding":
        if self.finding_type not in FINDING_TYPES:
            raise SchemaError(f"unknown finding_type {self.finding_type}")
        if self.status not in FINDING_STATUSES:
            raise SchemaError(f"unknown status {self.status}")
        if self.finding_type in ("contradiction", "rule_violation", "missing_evidence") and self.status == "supported" and not self.evidence_ids:
            raise SchemaError("a supported finding must reference evidence")
        if self.calibrated_probability is not None and not 0.0 <= self.calibrated_probability <= 1.0:
            raise SchemaError("calibrated_probability out of range")
        return self

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DocumentRecord:
    """A document as the engine sees it (decoupled from the database row)."""
    document_id: str
    kind: str
    pages: list[dict]                 # [{"page":1,"text":"...","lines":[{"text","bbox","conf"}]}]
    version: int = 1
    superseded: bool = False
    supersedes: str | None = None     # document_id this version replaces
    metadata: dict = field(default_factory=dict)
