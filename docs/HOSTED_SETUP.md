# Manual hosted setup

Target: Vercel frontend + Render backend processes + Supabase database/private objects. These instructions are configuration guidance; this release was not deployed to live accounts.

## 1. Source

Extract to a fresh folder as shown in START_HERE.md. Create an empty private GitHub repository, then from the approvallens folder:

```bash
git init
git add .
git commit -m "ApprovalLens unified v4"
git branch -M main
git remote add origin https://github.com/YOUR_USER/YOUR_REPOSITORY.git
git push -u origin main
```

Use your own repository URL. Environment examples are placeholders. Keep actual secrets out of Git.

## 2. Supabase

Create a project and private Storage bucket named `approvallens-private`. Copy the session pooler connection from Connect (port 5432), replace its password placeholder and use `?sslmode=require`. URL-encode special characters in the password. Use the backend database owner connection for schema migration and application access.

Create Storage S3 credentials and copy the endpoint and region shown by Supabase. These are S3 access/secret credentials, not the public anon key. Only Render services receive them. This application uses its own authentication; Supabase Auth is not wired in.

Reference: https://supabase.com/docs/guides/database/connecting-to-postgres and https://supabase.com/docs/guides/storage/s3/authentication

## 3. Render

Create a Redis-compatible Key Value service in the same region. Use its internal connection URL. Create three Docker services from the repository with root directory `backend` and Dockerfile `Dockerfile`:

| Service | Command |
|---|---|
| Web API | `sh start-render.sh` |
| Background worker | `celery -A app.worker.celery worker --loglevel=info --concurrency=1` |
| Background dispatcher | `python -m app.dispatcher` |

Copy every key from deploy/render.env.example to all three services and replace placeholders. ALLOWED_ORIGIN must be the exact HTTPS frontend URL without a trailing slash. Use separate service instances; the dispatcher recovers queued outbox work and is required. Hosting plans must support persistent background workers and the required shell/pre-deploy operations; check provider pricing before provisioning.

Run `alembic upgrade head` once in the API's backend environment before starting worker/dispatcher processing (a pre-deploy command or service shell). Then run `python -m app.bootstrap` interactively in that environment to create your own administrator. Never run the demo seed in production. Database changes on an existing deployment require a backup first.

## 4. Vercel

Import the same repository. Set Root Directory to `frontend`, framework Next.js, install command `npm ci`, build command `npm run build`. Set server-side `API_INTERNAL_URL=https://YOUR_API.onrender.com` without a trailing slash. Do not prefix it with NEXT_PUBLIC. Deploy, then set the resulting frontend URL as Render ALLOWED_ORIGIN and redeploy the backend services.

The frontend uses a same-origin server proxy, so authenticated cookies stay on the frontend domain. No Supabase service credentials belong in frontend environment variables.

The existing Vercel Functions proxy has a 4.5 MB request/response limit. This hosted configuration sets the backend upload cap to 4 MB to leave multipart overhead. Keep individual files and exported/preview responses small. Larger documents need a separately implemented authenticated direct-upload/download flow; the local/self-hosted 15 MB limit does not bypass Vercel's limit.

Reference: https://vercel.com/docs/functions/limitations

## 5. Verify after deploying

Sign in as the bootstrapped administrator, create applicant/reviewer accounts and institution/assignment records, and submit a small synthetic PDF as applicant. Confirm the run progresses to completion, inspect the Evidence Intelligence tab as reviewer, request and answer a clarification, resubmit, compare runs and export a PDF. Verify applicants cannot read reviewer-only evidence. Restart the worker and check stored objects still load. These live acceptance checks remain to be performed in your accounts.

For an Ubuntu server alternative with fewer cloud services, see DEPLOYMENT.md.
