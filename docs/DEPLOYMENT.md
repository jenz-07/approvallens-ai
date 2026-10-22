# Deploy ApprovalLens AI v3

This package is configured for a single Linux Docker host and a public HTTPS hostname. It is an independent preliminary-review prototype, not a regulatory certification service. The production Compose configuration is separate from the local demo configuration.

## Requirements

Use Docker Engine with the Compose v2 plugin, Python 3 for generating configuration, a DNS hostname pointing to the host, inbound TCP 80/443 (UDP 443 optional), and outbound HTTPS for images, packages and certificate issuance. Start with 4 GB RAM; budget more for concurrent OCR and disk growth. Do not publish database, Redis, worker or API ports. Only the Caddy gateway is public.

From the extracted `approvallens` directory:

```bash
python3 scripts/configure_production.py --domain review.your-domain.example --email operator@your-domain.example
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod config --quiet
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod up -d --build
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod exec api python -m app.bootstrap
```

Replace the example hostname/email. The generator creates separate random database and Redis credentials, disables demo accounts, and refuses to overwrite an existing configuration. Keep `.env.production` private. Caddy obtains a certificate when DNS and ports are correct. The bootstrap command prompts for the first administrator password without putting it in shell history and refuses to overwrite existing accounts.

Open `https://YOUR_HOSTNAME`. Sign in, create institutions and applicant/reviewer accounts in Administration, and assign each submitted application to a reviewer. Assignment forms show application titles and reviewer emails. The clean bootstrap includes illustrative presence rules and checklists; it deliberately contains no synthetic reference records or known demo credentials. Review and extend the rule configuration before a pilot. The full illustrative rule examples are in `backend/app/seed.py`; run the seed command only in a separate local demo, never on the production database.

## Reference data

Missing reference data remains insufficient evidence. To load an explicitly authorized local snapshot, prepare a JSON object keyed by certificate reference, for example:

```json
{"SAMPLE-001":{"institution_identifier":"EXAMPLE-001","institution_name":"Example Institution","intake":"60"}}
```

The example is illustrative only. Import your own authorized data:

```bash
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod cp references.json api:/tmp/references.json
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod exec api python -m app.import_references /tmp/references.json --label "Operator reference snapshot 2026-10-22"
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod exec api rm /tmp/references.json
```

Every import creates a new snapshot. Earlier validation runs keep their earlier snapshot. The issuing-authority adapter remains explicitly simulated and disabled by default in clean production; importing records does not create a live connection or change that disclosure. Manual verification records a reviewer-consulted source. No arbitrary URLs are fetched.

## Operations and recovery

```bash
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod ps
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod logs --tail=100 api worker dispatcher gateway
```

`GET /api/v1/ready` checks database and Redis connectivity; it is not a worker-health assertion. Monitor worker and dispatcher service status as well as queued-job age and failed runs. The dispatcher republishes queued jobs after a 60-second delivery interval and recovers worker leases older than 15 minutes. Worker execution has a ten-minute limit and a six-attempt ceiling. Failed runs show a safe retry action. Core extraction needs no external model key.

Caddy bounds incoming bodies to 16 MB; application uploads remain limited to 15 MB. API/worker run as an unprivileged user. The worker has a 2 GB memory limit and concurrency 2. The API trusts forwarded headers because its port is only accessible on the private Compose network behind the gateway; do not expose it or attach untrusted workloads to that network. If adding another proxy, explicitly configure trusted proxy forwarding and verify client-IP rate limiting.

## Backup and upgrade

Back up database and private documents together during a maintenance window. Protect backups as sensitively as live data. These commands pause application services but keep PostgreSQL running:

```bash
mkdir -p backups
chmod 700 backups
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod stop gateway frontend api worker dispatcher
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod exec -T db pg_dump -U approval -d approval -Fc > backups/database.dump
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod run --rm --no-deps -T api tar -C /data/private -czf - . > backups/documents.tar.gz
chmod 600 backups/*
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod start api worker dispatcher frontend gateway
```

Use dated backup directories to avoid overwriting prior backups. Also retain `.env.production` securely and a copy of the release ZIP. For S3 storage use coordinated object backups/versioning instead of the document-volume archive. Test a restore in an isolated environment before relying on backups.

To upgrade, stop application services, back up, replace source while retaining configuration and volumes, then run:

```bash
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod build
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod run --rm migrate
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod up -d
```

The v3 migration adds a durable dispatch outbox and backfills pending v2 runs. Do not copy a demo database to production. For rollback, restore the matching database and document backup with the prior release in an isolated host first; downgrading code without its matching schema/data is not a rollback plan.

For a fresh isolated restore with database and Redis running but application services stopped:

```bash
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod exec -T db pg_restore -U approval -d approval --clean --if-exists < backups/database.dump
docker compose --env-file .env.production -f compose.production.yaml -p approvallens-prod run --rm --no-deps -T api tar -C /data/private -xzf - < backups/documents.tar.gz
```

Restore only trusted backups into an empty document volume. Never run `down -v` on a live installation unless intentionally deleting its data. The application database role owns the schema in this single-host template; deployments needing separation of duties should use distinct migration/runtime roles with least privileges.

## Release acceptance

The v3 backend checks and frontend build were executed. Docker/PostgreSQL/Caddy were not available for a full host deployment in the authoring environment; live TLS and S3 remain environment-specific acceptance checks. Before inviting users, verify login, an upload through the public gateway, completed worker processing, reviewer assignment, replacement/revalidation, report export and backup restore on the target host. Do not advertise official endorsement, unrestricted public-production security certification, or live authority integration.
