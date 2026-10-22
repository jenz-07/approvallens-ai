# Unified v4 verification — 2026-10-22

| Check | Result |
|---|---|
| Backend integration tests | 22 passed |
| Research engine tests | 28 passed |
| Next.js optimized build and TypeScript | Passed |
| Fresh SQLite Alembic migration through 9c3e12 | Passed |
| Quick research reproduction | Completed; artifacts/reports |
| Backend deterministic engine without optional scientific packages | Passed |
| Supabase S3 request compatibility | Mocked adapter test passed |

Coverage includes access control, review workflow, immutable corrections and run versions, evidence persistence, dispositions, source reports, worker idempotency and low-OCR-confidence abstention.

Not executed for this merged release: browser end-to-end tests, Docker Compose, PostgreSQL concurrency, live S3, or live Vercel/Render/Supabase deployment. Browser test source is included; historical browser results from the supplied v3 archive are not verification of this merge. Research evaluation uses synthetic submissions and simulated OCR corruption, not a representative scanned-document corpus.

## Free-demo patch — 2026-10-22

26 backend tests passed after the adaptation, including actual PDF processing in a child process, persisted evidence, stale-job recovery, retry limits, timeout process cleanup, and fresh migration/administrator bootstrap. Frontend source is unchanged. Hosted PostgreSQL advisory locks, live cloud services and free-instance memory capacity have not been verified on Render.
