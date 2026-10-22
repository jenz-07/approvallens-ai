# Implementation status — Unified v4

The master technical specification is a target, not a claim that every feature exists.

| Area | Delivered status |
|---|---|
| Applicant/reviewer/administrator workflow | Implemented with access checks, clarification, revision history and PDF reports |
| Extraction | Native PDF text and English Tesseract OCR; deterministic labelled-field parsing |
| Durable jobs | Celery/Redis, database outbox, dispatcher, retries and idempotency |
| Evidence intelligence | Per-run persisted claims, typed graph, deterministic cross-document contradictions, source links and audited reviewer status |
| Uncertainty | Missing/conflicting/low-confidence evidence routed to review; no production fraud probabilities |
| Revision comparison | Snapshot-based comparison across validation runs |
| Database/storage | Alembic schema; filesystem or S3-compatible adapter; hosted setup examples |
| Research | Synthetic generators, baselines, calibration/ablation experiments, tests and quick reports |
| Learned OCR/layout/LLM extraction | Not connected to the application |
| Multimodal forensic authenticity, trained forgery detection | Not delivered |
| Official live regulatory verification | Not connected; simulated/manual providers only |
| QR/signature verification | Not delivered |
| Full production/load/security certification | Not performed |

Applicant reports exclude unreleased reviewer-only evidence intelligence. Reviewer evidence dispositions are annotations; they do not themselves send a clarification or complete an application. Use the workflow controls for those actions.

Synthetic benchmark model/calibration files are offline research artifacts. The app uses the deterministic pipeline and does not load synthetic-calibrated scores as decision probabilities.
