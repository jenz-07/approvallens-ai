# Merge notes

Foundation: ApprovalLens_AI_Deployment_v3.zip. Research source: ApprovalLens_AI_Final.zip. Target requirements: supplied master technical specification (included verbatim in MASTER_TECHNICAL_SPEC.md).

The archives used incompatible database models. This release retains the v3 schema and adds an evidence_analyses table, rather than replacing application models. A bridge reads each validation run's pinned versions, extracted page text and pinned corrections. Results are saved transactionally and scoped to that run.

The evidence UI now connects to authenticated v3 routes, preserves actual reviewer status labels, links available source pages and avoids recomputing historical analysis on reads. Applicant access remains restricted. The report includes reviewer evidence findings.

The S3 adapter uses path-style SigV4 without forcing AWS-specific encryption headers. PostgreSQL URLs are normalized to psycopg. The deterministic application import path does not require the optional research stack.

Root ml/ is canonical. Run `python scripts/sync_engine.py` after changing it; backend/ml/ is its deployable copy. The final archive includes synchronized copies. Scientific training and calibration belong to the offline research workflow.

Existing deployments must back up their database and private objects before `alembic upgrade head`. The migration enables RLS on application tables in PostgreSQL, with no anonymous client policies. Use the backend database owner connection; Supabase browser clients must not access these tables directly. Old runs do not gain analysis retrospectively; submit a new validation run.

Fresh quick benchmark output is in artifacts/. Supplied historical experiment output is kept under research/supplied-artifacts/. Neither is production accuracy evidence.

## Reproduce research

From the project root in a separate Python virtual environment:

```bash
pip install -r requirements-research.lock
python -m pytest tests -q
python scripts/reproduce_results.py --quick
```

Omit `--quick` for the full synthetic experiment. After intentionally updating root engine code or model artifacts, run `python scripts/sync_engine.py` before deploying.
