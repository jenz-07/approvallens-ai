# ApprovalLens AI — Unified v4

One project: application, cross-document evidence engine, research experiments and setup guides.

## Windows + Ubuntu (WSL)

Save this ZIP in your Windows Downloads folder. In your Ubuntu terminal:

```bash
sudo apt update
sudo apt install -y unzip
mkdir -p ~/projects/approvallens-v4
unzip -n /mnt/c/Users/Jenisha/Downloads/ApprovalLens_AI_Unified_v4.zip -d ~/projects/approvallens-v4
cd ~/projects/approvallens-v4/approvallens
```

Use this fresh folder; do not overwrite an older project's database or environment files.

## Run locally

Install/start Docker Desktop with WSL integration enabled for Ubuntu, then:

```bash
bash start.sh
```

Open http://localhost:3000. Demo password: `DemoOnly!2026`.
Accounts: `applicant@demo.local`, `reviewer@demo.local`, `admin@demo.local`.

The six synthetic applications exercise the review workflow. As reviewer, select a validation run and open **Evidence Intelligence** for its saved claims, contradictions and evidence graph. New validations create new analysis snapshots. Earlier runs without analysis must be revalidated.

## Deploy manually

Follow `docs/HOSTED_SETUP.md`: Vercel frontend, Render API/worker/dispatcher and Redis, Supabase PostgreSQL/private storage. Services and credentials must be configured in your own accounts; this ZIP is not already deployed.

For one Ubuntu server instead, use `docs/DEPLOYMENT.md` and the production Compose configuration.

## Included research

Open `artifacts/reports/index.html` or `artifacts/reports/results.md` for the fresh quick benchmark. It uses synthetic data and is not a real-world accuracy claim. Original supplied results are retained in `research/supplied-artifacts` for comparison.

See `docs/TEST_RESULTS.md` for verification and `docs/REQUIREMENTS_STATUS.md` for implemented versus future features.
