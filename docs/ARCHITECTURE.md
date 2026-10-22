# Architecture and invariants

## Request and processing path

Browser → Next.js same-origin streaming proxy → FastAPI → SQLAlchemy/PostgreSQL.
Uploads are validated then stored privately under random UUID keys. Metadata preserves SHA-256, original filename, MIME, uploader and version. Upload endpoints do not perform OCR. Submission/validation queues a Celery task through Redis. The worker extracts native text or OCR per page, persists pages/word coordinates and structured fields, then runs pinned rules. The UI polls stored run status; it never generates progress from timers.

The Next.js proxy reads `API_INTERNAL_URL` at request time, including in production Docker. It forwards the session cookie and CSRF header to the API. The backend remains authoritative for all access checks. Direct backend document routes enforce the same checks.

## Independent state machines

- Application: Draft → Submitted → Under Review → Preliminary Review Completed; Under Review → Clarification Requested → Resubmitted → Under Review. Applicants may withdraw Draft, Submitted, Resubmitted or Clarification Requested applications.
- Processing run: Queued → Extracting → Validating → Completed; errors → Failed; explicit safe retry → Queued. Celery retries at most twice per dispatch. Manual retry is capped at six attempts; stale jobs become retryable after 15 minutes. Soft/hard limits are 540/600 seconds. A worker killed without a terminal update remains visibly active/stale until retry; it is not falsely shown completed.
- Finding disposition: Open, Acknowledged, Clarification Requested, Resolved, Dismissed with Reason. A reviewer can revisit dispositions with a required reason; actions remain in history.
- Verification: Verified, Mismatch Detected, Verification Pending, Source Unavailable, Manual Review Required, Not Supported.
- Original extracted document validity: Valid for Reference Date, Expired, Validity Unknown, Not Applicable. Separately recorded corrections affect subsequent validation findings, not this original-source display.

No Approved/Rejected statutory state exists.

## Authorization

Applicants need institution membership. Reviewers need an explicit application assignment. Administrators manage configuration and assignments and can inspect records, but cannot perform reviewer-only finding actions. Routes for preview, downloads, fields, corrections, report generation and audit apply application access checks. A missing authorization returns 404 to avoid confirming record existence.

Applicant findings are filtered by `released`; reviewer observations are excluded from their workspace/report. Application audit details redact workflow reasons for applicants. Duplicate/similarity checks operate only on current versions within the authorized application: another institution's identity or file is never exposed through a duplicate check.

## History, snapshots and concurrency

New evidence creates a document version. No API overwrites file bytes, extracted facts, rule definitions, previous run results, reference snapshots, reviewer actions or audit records. Type/field corrections are separate actor/reason/timestamp records. A validation run pins version IDs, original declared kinds, corrections, application reference date/institution/intake/facility declarations, checklist version/items, rule-set ID and reference-snapshot ID.

Application row locks serialize competing version increments and run scheduling in PostgreSQL. An idempotency key is unique per application; an active run blocks a different overlapping run. Findings/evidence commit together after all rules finish; repeat delivery of a completed task exits. Extraction is reused per immutable document version. A unique page/field constraint prevents duplicate extraction rows.

Run comparison marks a rule New, Unchanged or Changed based on its prior result. It is intentionally not a semantic diff of all evidence. Review dispositions are not automatically copied to a newer run. Superseded source versions remain visible.

A JobDispatch outbox row is committed with each validation run. The dispatcher retries queued delivery every 60 seconds and recovers worker leases older than 15 minutes. Delivery is at least once; worker claims and completed-run guards avoid duplicate results. Automatic recovery stops at the six-attempt execution ceiling. Keep the dispatcher running alongside Celery.

## Extraction and rule scope

- Native text page extraction; Tesseract fallback on low-text pages.
- Engine-provided OCR token confidence only. No calibration/fraud percentages.
- Label-driven structured parsing; fields absent in text remain unknown.
- Exact SHA-256 duplicate detection and lexical similarity (90% SequenceMatcher ratio, first 10,000 characters) as a disclosed aid.
- Presence, date validity/order, normalized name/identifier comparisons, reference consistency, intake versus registry, structured facility declaration validation, and conflicting cross-document values.
- The facility check validates declaration shape and nonnegative capacity; it does not measure room size or establish adequacy.
- Rules are Pydantic validated and interpreted by an explicit allowlist. Parameters are data, not executable code.

Uploaded content is untrusted. Deterministic extraction never evaluates it, makes a tool call from it, follows URLs, or treats embedded instructions as system prompts. No model provider is configured. The future `AIProvider` protocol must validate all proposed facts against stored page evidence, keep provider credentials server-side, and require explicit external-processing configuration.

## Source verification

The synthetic provider looks up actual extracted reference numbers in a separate immutable registry snapshot and compares only supported present fields. It records provider/mode/method/timestamp, outcome, matched/mismatched field names, source/snapshot and a sanitized reason. Unknown reference is not Verified; unsupported types return Not Supported. The manual route requires source, reference, observation and an allowed outcome, attributed to the reviewer.

A future live provider must use a fixed trusted endpoint, authorization, timeouts, response schema validation and field allowlists. Do not derive request hosts from document/QR text. No live provider, restricted-portal scraping or arbitrary URL-fetch feature exists.

## Limits of the initial implementation

The parser is deliberately narrow, and English OCR can misread unusual layouts or languages. File/page/dimension limits are configurable. Basic tables replace decorative charts. UI navigation is client-side within one Next.js page; refresh restores the user's dashboard rather than the exact workspace tab. API list endpoints are paginated; the UI initially shows at most 50 applications/admin records and 100 verification/audit items. There is no email notification service: notifications are stored in-app.
