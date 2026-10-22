import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, ForeignKey, UniqueConstraint, JSON, DateTime, Boolean, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base

def now(): return datetime.now(timezone.utc)
def uid(): return str(uuid.uuid4())
class Row:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
class Institution(Row, Base):
    __tablename__ = 'institutions'
    name: Mapped[str] = mapped_column(String(200))
    identifier: Mapped[str] = mapped_column(String(100), unique=True)
    address: Mapped[str] = mapped_column(Text, default='')
class User(Row, Base):
    __tablename__ = 'users'
    email: Mapped[str] = mapped_column(String(254), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(20))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
class Membership(Row, Base):
    __tablename__ = 'institution_memberships'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    institution_id: Mapped[str] = mapped_column(ForeignKey('institutions.id'), index=True)
    __table_args__ = (UniqueConstraint('user_id','institution_id'),)
class Session(Row, Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf: Mapped[str] = mapped_column(String(100))
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
class Application(Row, Base):
    __tablename__ = 'applications'
    institution_id: Mapped[str] = mapped_column(ForeignKey('institutions.id'), index=True)
    title: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(100))
    reference_date: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(50), default='Draft', index=True)
    declaration: Mapped[dict] = mapped_column(JSON, default=dict)
class Assignment(Row, Base):
    __tablename__ = 'reviewer_assignments'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    __table_args__ = (UniqueConstraint('application_id','user_id'),)
class Programme(Row, Base):
    __tablename__ = 'programme_declarations'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    name: Mapped[str] = mapped_column(String(200))
    intake: Mapped[int] = mapped_column(Integer)
class Document(Row, Base):
    __tablename__ = 'documents'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    kind: Mapped[str] = mapped_column(String(50))
class DocumentVersion(Row, Base):
    __tablename__ = 'document_versions'
    document_id: Mapped[str] = mapped_column(ForeignKey('documents.id'), index=True)
    version: Mapped[int] = mapped_column(Integer)
    filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(100), unique=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    mime: Mapped[str] = mapped_column(String(50))
    pages: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[str] = mapped_column(ForeignKey('users.id'))
    __table_args__ = (UniqueConstraint('document_id','version'),)
class ExtractedField(Row, Base):
    __tablename__ = 'extracted_fields'
    version_id: Mapped[str] = mapped_column(ForeignKey('document_versions.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    value: Mapped[str | None] = mapped_column(Text)
    page: Mapped[int] = mapped_column(Integer)
    bbox: Mapped[list | None] = mapped_column(JSON)
    excerpt: Mapped[str] = mapped_column(Text)
    method: Mapped[str] = mapped_column(String(50))
    ocr_confidence: Mapped[float | None]
    __table_args__ = (UniqueConstraint('version_id','name','page'),)
class PageText(Row, Base):
    __tablename__ = 'document_pages'
    version_id: Mapped[str] = mapped_column(ForeignKey('document_versions.id'), index=True)
    page: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    words: Mapped[list] = mapped_column(JSON)
    method: Mapped[str] = mapped_column(String(50))
    __table_args__ = (UniqueConstraint('version_id','page'),)
class Correction(Row, Base):
    __tablename__ = 'field_corrections'
    version_id: Mapped[str] = mapped_column(ForeignKey('document_versions.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    value: Mapped[str] = mapped_column(Text)
    reason: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
class ChecklistTemplate(Row, Base):
    __tablename__ = 'checklist_templates'
    category: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint('category','version'),)
class ChecklistItem(Row, Base):
    __tablename__ = 'checklist_items'
    template_id: Mapped[str] = mapped_column(ForeignKey('checklist_templates.id'))
    kind: Mapped[str] = mapped_column(String(50))
    description: Mapped[str] = mapped_column(Text)
class RuleSet(Row, Base):
    __tablename__ = 'rule_sets'
    name: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer, unique=True)
    active: Mapped[bool] = mapped_column(Boolean, default=False)
class RuleVersion(Row, Base):
    __tablename__ = 'rule_versions'
    rule_set_id: Mapped[str] = mapped_column(ForeignKey('rule_sets.id'), index=True)
    rule_id: Mapped[str] = mapped_column(String(100))
    version: Mapped[int] = mapped_column(Integer)
    definition: Mapped[dict] = mapped_column(JSON)
    __table_args__ = (UniqueConstraint('rule_set_id','rule_id'),)
class ReferenceSnapshot(Row, Base):
    __tablename__ = 'reference_record_snapshots'
    label: Mapped[str] = mapped_column(String(150))
    records: Mapped[dict] = mapped_column(JSON)
class ValidationRun(Row, Base):
    __tablename__ = 'validation_runs'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    rule_set_id: Mapped[str] = mapped_column(ForeignKey('rule_sets.id'))
    snapshot_id: Mapped[str] = mapped_column(ForeignKey('reference_record_snapshots.id'))
    input_snapshot: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(30), default='Queued')
    stage: Mapped[str] = mapped_column(String(200), default='Waiting for worker')
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    heartbeat: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    idempotency_key: Mapped[str] = mapped_column(String(64))
    __table_args__ = (UniqueConstraint('application_id','idempotency_key'),)
class Finding(Row, Base):
    __tablename__ = 'findings'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    run_id: Mapped[str] = mapped_column(ForeignKey('validation_runs.id'), index=True)
    rule_version_id: Mapped[str] = mapped_column(ForeignKey('rule_versions.id'))
    rule_id: Mapped[str] = mapped_column(String(100))
    rule_version: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(200))
    severity: Mapped[str] = mapped_column(String(20))
    result: Mapped[str] = mapped_column(String(40))
    explanation: Mapped[str] = mapped_column(Text)
    observed: Mapped[dict] = mapped_column(JSON)
    expected: Mapped[dict] = mapped_column(JSON)
    next_action: Mapped[str] = mapped_column(Text)
    limitations: Mapped[str] = mapped_column(Text)
    review_status: Mapped[str] = mapped_column(String(40), default='Open')
    released: Mapped[bool] = mapped_column(Boolean, default=False)
    comparison: Mapped[str] = mapped_column(String(30), default='New')
class Evidence(Row, Base):
    __tablename__ = 'evidence_references'
    finding_id: Mapped[str] = mapped_column(ForeignKey('findings.id'), index=True)
    version_id: Mapped[str | None] = mapped_column(ForeignKey('document_versions.id'))
    page: Mapped[int | None] = mapped_column(Integer)
    bbox: Mapped[list | None] = mapped_column(JSON)
    excerpt: Mapped[str] = mapped_column(Text)
    requirement: Mapped[str | None] = mapped_column(String(100))
class VerificationAttempt(Row, Base):
    __tablename__ = 'verification_attempts'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    version_id: Mapped[str] = mapped_column(ForeignKey('document_versions.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    provider_id: Mapped[str] = mapped_column(String(100))
    outcome: Mapped[str] = mapped_column(String(50))
    details: Mapped[dict] = mapped_column(JSON)
class ProviderConfig(Row, Base):
    __tablename__ = 'provider_configurations'
    provider_id: Mapped[str] = mapped_column(String(100), unique=True)
    available: Mapped[bool] = mapped_column(Boolean, default=True)
class Clarification(Row, Base):
    __tablename__ = 'clarification_threads'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    finding_ids: Mapped[list] = mapped_column(JSON)
    question: Mapped[str] = mapped_column(Text)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
class Reply(Row, Base):
    __tablename__ = 'clarification_replies'
    thread_id: Mapped[str] = mapped_column(ForeignKey('clarification_threads.id'), index=True)
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    text: Mapped[str] = mapped_column(Text)
class ReviewerAction(Row, Base):
    __tablename__ = 'reviewer_actions'
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    finding_id: Mapped[str | None] = mapped_column(ForeignKey('findings.id'))
    actor_id: Mapped[str] = mapped_column(ForeignKey('users.id'))
    action: Mapped[str] = mapped_column(String(100))
    reason: Mapped[str] = mapped_column(Text)
class Notification(Row, Base):
    __tablename__ = 'notifications'
    user_id: Mapped[str] = mapped_column(ForeignKey('users.id'), index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'))
    message: Mapped[str] = mapped_column(Text)
class AuditEvent(Row, Base):
    __tablename__ = 'audit_events'
    actor_id: Mapped[str | None] = mapped_column(ForeignKey('users.id'))
    application_id: Mapped[str | None] = mapped_column(ForeignKey('applications.id'), index=True)
    event: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict] = mapped_column(JSON, default=dict)

class JobDispatch(Row, Base):
    __tablename__ = 'job_dispatches'
    run_id: Mapped[str] = mapped_column(ForeignKey('validation_runs.id'), unique=True, index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text)

class EvidenceAnalysis(Row, Base):
    __tablename__ = 'evidence_analyses'
    run_id: Mapped[str] = mapped_column(ForeignKey('validation_runs.id'), unique=True, index=True)
    application_id: Mapped[str] = mapped_column(ForeignKey('applications.id'), index=True)
    pipeline_version: Mapped[str] = mapped_column(String(100))
    result: Mapped[dict] = mapped_column(JSON)
