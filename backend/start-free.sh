#!/bin/sh
set -eu
export PROCESSING_MODE=embedded
export OMP_THREAD_LIMIT=1
export OPENBLAS_NUM_THREADS=1
python -m app.free_startup
unset BOOTSTRAP_ADMIN_EMAIL BOOTSTRAP_ADMIN_PASSWORD
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers 1
