# ApprovalLens AI

A runnable independent prototype for evidence-linked preliminary institutional document review. Next.js + FastAPI + SQLAlchemy/Alembic + PostgreSQL + Celery/Redis + PyMuPDF/Tesseract. Actual uploaded bytes are processed; no model key is needed.

> ApprovalLens AI provides preliminary decision support. Official scrutiny, required inspections, and final regulatory decisions remain with competent authorities.

No official AICTE endorsement, live regulatory portal access, statutory approval decision, or compliance certification is implied. Every seeded rule is labelled **“Illustrative prototype rule — not an official AICTE requirement.”**

For the shortest setup, open `START_HERE.md`. Windows users can run `START_WINDOWS.bat`; macOS/Linux users can run `bash start.sh`.

## Unified release v4

This release connects the v3 application to the cross-document evidence engine, with immutable run snapshots, reviewer-only claims/graphs, audited dispositions and report evidence. Start with `START_HERE.md`; the chosen hosted setup is in `docs/HOSTED_SETUP.md`. Research experiments are separate from production decisions. See `docs/MERGE_NOTES.md`.

### Inherited self-hosting option

For a public HTTPS installation, follow `docs/DEPLOYMENT.md` using the standalone `compose.production.yaml`. For the product assessment and recommended competition demo, see `docs/V3_REVIEW.md`. Local demo instructions below remain supported.

## Start with Docker Compose

Prerequisites: Docker Desktop or Docker Engine with Compose v2, 4 GB available RAM, internet for the initial image/package downloads. Windows: use Docker Desktop with Linux containers. Run these commands from the extracted `approvallens` directory.

```bash
cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
# Windows Command Prompt: copy .env.example .env
docker compose up --build -d
docker compose exec api python -m app.seed
```

Open **http://localhost:3000**. API/OpenAPI documentation: **http://localhost:8000/api/v1/docs**.

The seed command is explicit, reproducible in scenario dates, and refuses to run unless `DEMO_ENABLED=true` and `ENVIRONMENT` is not production. It generates real synthetic PDFs and a PNG facility diagram, including an image-only PDF that exercises OCR; it processes the files using the same pipeline. Repeating the seed command is a no-op once demo accounts exist. The six applications are assigned to the demo reviewer.

| Role | Email | Development-only password |
|---|---|---|
| Applicant | applicant@demo.local | DemoOnly!2026 |
| Reviewer | reviewer@demo.local | DemoOnly!2026 |
| Administrator | admin@demo.local | DemoOnly!2026 |

For new applications, sign in as administrator and create a reviewer assignment. User IDs are shown in Administration → users; application IDs are shown in Administration → assignments or the application API. No reviewer receives all applications automatically.

## Try the complete workflow

1. Applicant: create a draft through the five steps, declare a programme/intake, upload evidence, and submit.
2. Administrator: assign the new application to a reviewer.
3. Reviewer: start review; open Validation Findings and click a finding title to show the exact source version/page. Available coordinates highlight an evidence token; other fields show the page and excerpt.
4. Reviewer: request clarification from a finding. This releases that finding to the applicant.
5. Applicant: reply in Clarifications. In Documents, choose the existing document, its existing type, and a replacement file. Resubmit.
6. Watch real worker states in Overview. Select previous/new runs in Validation Findings. Old findings, original files, and reviewer actions remain available.
7. Reviewer: start review of the resubmission, record a finding disposition/reason and a preliminary completion reason. Export a PDF from Reports.

Applicants see released findings only. The demo seed explicitly releases its generated findings for walkthrough purposes. Reviewer-only observations are excluded from applicant reports.

## Sample extraction format

The deterministic parser reads labelled lines anywhere on a page, case-insensitively. Missing fields remain unknown. It does not infer values from filenames. For predictable demonstration input, include lines such as:

```text
SYNTHETIC DEMONSTRATION MATERIAL
Institution Name: Synthetic Institute of Technology
Institution Identifier: SYN-001
Document Type: certificate
Issuing Authority: Synthetic Education Registry
Reference Number: CERT-001
Issue Date: 2025-01-01
Expiry Date: 2027-12-31
Academic Year: 2026-2027
Programme: Synthetic Engineering
Intake: 60
```

Supported labels are in `backend/app/extraction.py`. Dates use ISO `YYYY-MM-DD`. A native page with fewer than 30 non-whitespace text characters is OCRed at 150 DPI with English Tesseract. Word boxes are normalized page coordinates; only exact matching value tokens currently receive field-level bounding boxes. No invented confidence percentages are produced. Tesseract token confidence is included only where supplied by that engine.

Document type uses recognized extracted `Document Type` values, otherwise the applicant's declared upload type. A separately recorded `document_type` correction can override classification for a subsequent run; it never rewrites original extraction. Field corrections are version-scoped and included in the immutable next-run snapshot.

## Synthetic scenarios

Fixed validation reference date: **2026-07-01**, independent of the current date.

1. Consistent certificate and fields.
2. Required certificate missing.
3. Certificate expired on the reference date.
4. Certificate institution identifier differs from the institution/reference record.
5. Two uploads contain byte-identical facility images.
6. Image-only PDF and a deliberately unavailable synthetic source.

Ground-truth labels are written separately to `backend/evaluation/ground_truth.json` by the seed command. Neither the extraction engine nor the validation engine imports that file. Registry records are separate persisted `reference_record_snapshots`. Unknown reference values return Verification Pending. A known unavailable record returns Source Unavailable. Expired documents can still match a source; verification and validity remain separate.

## Tests

Backend tests in the API container:

```bash
docker compose exec api pytest -q
```

They run against an isolated SQLite database with foreign keys enabled, perform actual PDF/OCR processing, and mock only the login counter/queue dispatch boundary. They cover the full clarification/replacement/revalidation/report flow, tenant isolation, unassigned reviewers, CSRF, session expiry/logout, malformed/encrypted/oversized uploads, retry idempotency, immutable rule snapshots, corrections, source outcomes, and structured facility declarations.

Browser tests against running Compose services:

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

Tests log in through the UI, create/upload/submit, wait for the actual Celery worker, assign a reviewer via the administrator API, request clarification in the UI, reply and replace a document, resubmit, complete a preliminary review, and verify PDF export. A second test checks the mobile layout, source viewer and logout protection. Tests create disposable synthetic applications in the demo database.

Contributor test harness without Docker: install the backend lockfile in a venv, install Tesseract and Redis, run `npm ci`, `npm run build`, `npx playwright install chromium`, then run `python scripts/local_e2e.py` with the venv's Python. It starts the services in one isolated process group using a temporary SQLite database; PostgreSQL remains the standard Compose configuration.

See `docs/TEST_RESULTS.md` for the checks actually executed during delivery and their limits.

## Daily operation

```bash
docker compose logs --tail=100 api worker
docker compose stop
docker compose start
```

PostgreSQL, Redis and private documents use named volumes. `docker compose down` preserves them. Do not delete volumes if you want to retain data. `api` and `worker` run as an unprivileged container user; documents live outside the frontend tree. Migrations run before API/worker startup.

The default environment is explicitly local development. Before any external deployment, read `docs/OPERATIONS.md` and use HTTPS, independent secrets, restricted network access, and a clean database without demo accounts. This package is not a security certification.

## Project map

- `frontend/app/page.tsx`: role-aware product screens and connected workflows.
- `frontend/app/api/v1/[...path]/route.ts`: same-origin streaming proxy; backend address is read at runtime.
- `backend/app/main.py`: authenticated API, authorization, workflow transitions and exports.
- `backend/app/models.py`: relational tables, UUID-form identifiers, UTC timestamps and foreign keys.
- `backend/alembic/versions/`: explicit initial schema migration.
- `backend/app/worker.py`: bounded asynchronous extraction/validation and retry handling.
- `backend/app/rules.py`: schema-validated allowlisted rule engine, no eval.
- `backend/app/providers.py`: simulated/manual verification and future model/provider contracts.
- `backend/app/storage.py`: private filesystem and S3-compatible object storage adapters.
- `backend/app/seed.py`: synthetic files, separate registry and six scenarios.
- `docs/`: architecture, operations, known boundaries and test evidence.

## Explicit boundaries

Model-assisted extraction is disabled. The AI provider protocol is an extension point, not a connected provider. Live regulatory integration, QR decoding/fetching, cryptographic signature verification, forensic forgery detection, and visual compliance inference are not implemented. There are no fake model or fraud scores. Basic lexical similarity is a review aid: shared templates may produce similar text.

Rule activation affects only future runs. Required information that is absent yields Failed for an explicit presence requirement, or Insufficient Evidence/Not Evaluated for dependent checks. Passing an illustrative check is not regulatory approval. A preliminary reviewer completion does not prohibit outstanding issues; the reviewer must record the reason and the report retains all issues.


## Evaluation

After seeding: `python -m app.evaluate` (Docker: `docker compose exec api python -m app.evaluate`). It reads `evaluation/ground_truth.json`, which processing code never reads, and reports finding precision/recall, field accuracy, processing time and simulated-verification outcomes. Results cover a small synthetic set only.
