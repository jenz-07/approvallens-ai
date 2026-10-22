# Operations, security and extension points

For the complete v3 HTTPS installation and operator commands, use `DEPLOYMENT.md`. Commands below without a production Compose file refer to the local demo.

## Configuration

Use `.env.example` only for local development. Both API and worker require the same database/storage configuration. Demo credentials are never seeded automatically. Production settings reject `DEMO_ENABLED=true` or a non-HTTPS allowed origin. Use a clean production database; do not promote a seeded demo database with its known accounts.

Set the database URL and password independently from the example, Redis on a private network, `ALLOWED_ORIGIN` to the exact public HTTPS origin, and `ENVIRONMENT=production`. Terminate TLS at a maintained reverse proxy with request body/time limits. Bind PostgreSQL and Redis only to the private network. The sample Compose file binds API/frontend ports to loopback and does not publish PostgreSQL/Redis ports.

Sessions use 48-byte random tokens, SHA-256 token hashes at rest, Argon2 passwords, HttpOnly/SameSite=Strict cookies and Secure in production. Session-bound CSRF tokens protect mutations; origin checks reject mismatched browser origins. Login limiting is shared in Redis, bounded per IP/account and IP; authentication fails closed if Redis is unavailable. Configure trusted proxy handling intentionally before running multiple instances behind a proxy. The example avoids trusting arbitrary X-Forwarded-For headers.

No credentials or source text are intentionally logged; SQLAlchemy hides bind parameters. Worker errors expose an exception type and actionable message rather than document content. Audit rows are append-only through API permissions, not tamper-proof against database administrators. For production, split database migration/application users and grant the application audit-table INSERT/SELECT but not UPDATE/DELETE privileges. The local Compose owner role is intentionally development-only.

The PDF engine is pinned to PyMuPDF 1.28.2; the unused ONNX/layout stack is excluded. Next.js telemetry is disabled in the Docker image and contributor harness. No OpenTelemetry exporter is configured. No model calls or external document transmissions occur in the implemented extraction path.

## Files and storage

Files are private and served only through authenticated routes. Generated UUID keys are validated before filesystem/S3 access. Default limits: 15 MB, 30 PDF pages, 25 million image/render pixels; PDF password protection is explicitly rejected. The HTTP size check is supplemental; set streaming request/body limits at the external reverse proxy to also bound chunked requests and malicious multipart overhead.

S3 mode: set `STORAGE_BACKEND=s3`, `S3_BUCKET`, optional `S3_ENDPOINT` and standard AWS credential/region variables. Use private buckets and deny public ACLs; least-privilege permissions are GetObject/PutObject/DeleteObject for the configured bucket prefix. Uploads request AES256 server-side encryption. Downloads remain proxied through API authorization; no public URLs are returned. The S3 adapter is implemented but not integration-tested with a live service in this delivery. Match encryption support to your S3-compatible provider before enabling it.

Tesseract runs with a 45-second per-page timeout. Celery applies task time limits. The Docker worker is unprivileged. These constraints do not substitute for a hardened file-processing sandbox, malware scanning, resource quotas and operational security review before processing untrusted production submissions.

## Retention

`RETENTION_DAYS` defaults to 365. This prototype does not silently purge evidence. An operator can inspect eligible closed applications and expired sessions:

```bash
docker compose exec api python -m app.cleanup
```

After reviewing the listed synthetic/local records, `--apply` removes original blobs for applications that are Withdrawn or Preliminary Review Completed and whose application creation timestamp is older than the configured cutoff. It also removes expired sessions. All document metadata, checksums, extracts, findings and review history remain; this is **blob retention**, not complete personal-data erasure. Purged local files return HTTP 410 from download/preview. The dry run never deletes.

Choose a suitable retention policy, backup strategy and legal hold process before using this on non-demo data. Full per-person erasure/anonymization and retention measured from final review completion are not implemented. S3 retention deletes original objects; provider error mapping needs deployment-specific integration verification.

## Failure recovery

- Authentication unavailable: ensure Redis is healthy; the app fails closed.
- Queue unavailable: keep Redis, worker and dispatcher running; durable queued delivery resumes automatically. Failed runs retain the explicit Retry processing action.
- Worker terminated mid-run: dispatcher recovers leases after 15 minutes; execution attempts remain bounded and no input snapshot is changed.
- Repeated bad input: replace the evidence during Draft/Clarification Requested and create a new run.
- Rule changes: create a new immutable set and activate it; do not edit a previous definition in the database.
- New references: create a new `ReferenceSnapshot` through an operator migration/import after validating its schema; old runs keep the old snapshot. There is no arbitrary live registry importer UI.

## Production bootstrap without demo

Use `python -m app.bootstrap` inside the production API container, as documented in `DEPLOYMENT.md`. This creates one administrator, an empty reference snapshot and explicitly illustrative starter checklists/rules; no demo accounts are created. It refuses to overwrite existing users. Use `python -m app.import_references` for schema-validated authorized local snapshots.

## Licensing

Review dependency licences before distributing/deploying this prototype. PyMuPDF is available under AGPL/commercial terms; select a compliant licence arrangement for your intended use. This is an implementation note, not a legal opinion.
