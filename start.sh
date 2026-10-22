#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if ! docker info >/dev/null 2>&1; then
  echo 'Start Docker with Compose v2, then run this script again.'
  exit 1
fi
if [ ! -f .env ]; then cp .env.example .env; fi
docker compose up --build -d
docker compose exec -T api python -m app.seed
echo 'Open http://localhost:3000'
echo 'Demo accounts: applicant@demo.local, reviewer@demo.local, admin@demo.local'
echo 'Development password: DemoOnly!2026'
