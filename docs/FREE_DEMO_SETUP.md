# Free-tier demo deployment

This patch adds an optional embedded processing mode to Unified v4. Use it for small synthetic demonstrations, within provider free quotas. It is not an always-on production deployment. Existing Celery mode remains the default for the original deployments.

## Apply to your existing checkout

Extract the patch ZIP into the repository root (the folder containing backend/ and frontend/), allowing replacement of the included files, then commit and push. No environment values or credentials are included. Do not merge the patch into another version of ApprovalLens.

## Services

- Vercel: existing frontend/ project, Next.js, npm ci / npm run build.
- Render: ONE Free Docker web service, root directory backend, Dockerfile ./Dockerfile, Docker Command `sh start-free.sh`, health path `/api/v1/health`.
- Render: ONE Free Key Value instance, same region as the API, maxmemory policy noeviction. Copy its internal Redis URL. Do not expose it externally. It is used for login throttling; processing jobs are persisted in PostgreSQL.
- Supabase: existing free project, PostgreSQL session pooler (5432), private approvallens-private bucket, existing S3 credentials.

No separate Render worker or dispatcher service is needed in this mode. Do not run Celery/dispatcher services against the same queue while embedded mode is enabled. Keep one API worker and one web-service instance.

## Render configuration

Copy the key names from deploy/render-free.env.example into Render and supply real values there. Use the session-pooler database URI, URL-encode the password, and append sslmode=require (use & if a query already exists). PostgreSQL session advisory locks require session pooling or a direct connection; transaction pooling on port 6543 is unsuitable.

Set ALLOWED_ORIGIN to the exact Vercel HTTPS origin, with no trailing slash. Set Vercel's server-only API_INTERNAL_URL to the Render HTTPS API URL, with no trailing slash. Redeploy after changing environment variables.

The free start command runs migrations automatically before opening the API port. On an empty database it can create your administrator from BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD (unique password, 12+ characters). These are private Render environment values, not frontend values. Remove both from Render after your first successful administrator login. An existing user's password is never overwritten. No shared demo accounts are created; DEMO_ENABLED remains false.

The API login still depends on Redis. /api/v1/ready checks database and Redis availability. /api/v1/health is the lightweight Render health path. Sign in as administrator and create institution, applicant and reviewer accounts and assignments before submitting documents.

## Processing and recovery

A background thread polls the durable database queue. Only one extraction child process runs at a time. Each child has a ten-minute wall-clock limit, and its process group (including OCR) is stopped before retry. PostgreSQL session locks serialize embedded runners during overlapping deployments. Interrupted runs left by a hard restart are recovered after their 15-minute lease expires. Automatic task failures are capped at three attempts in this mode. Completed runs are not replayed.

No browser request waits for extraction to finish. Supabase holds the database and uploaded objects; Render's ephemeral disk is used only for temporary processing. The runner operates only while the web service is awake. A user request wakes a sleeping service; the first attempt may need to be retried after it starts. We do not add artificial keep-alive requests.

Demo limits: 4 MiB files, 5 pages per document, 12 versions per application and 12 million pixels per uploaded image. Start with native-text PDFs and one or two documents. Heavy scans can exceed the free instance memory; test your exact demonstration inputs before presenting. Vercel's function proxy also limits request/response sizes, so keep previews and reports small.

## Free-tier limits

Render Free web services sleep after 15 idle minutes, can restart, have no shell/pre-deploy support, and share a 750-instance-hour monthly workspace allowance. Startup migrations and optional bootstrap replace the need for a paid service shell. Free Key Value is nonpersistent: a reset clears login-limit counters, but not the database job queue. Supabase and Vercel also impose usage limits. Free-tier selection does not guarantee unlimited use or absence of overage billing when a payment method is attached; review account spending controls.

Sources checked 2026-10-22:
https://render.com/docs/free
https://render.com/docs/faq
https://render.com/docs/key-value
https://supabase.com/docs/guides/database/connecting-to-postgres
https://vercel.com/docs/functions/limitations

## Verification

Backend regression tests plus free-mode tests cover real child-process execution, persisted evidence output, stale-job recovery, retry caps, timeout process cleanup, fresh migrations and noninteractive administrator bootstrap. Live Render/Supabase/Vercel acceptance and PostgreSQL advisory-lock behavior on hosted infrastructure still require deployment testing. The frontend is unchanged from Unified v4.
