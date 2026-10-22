# Experiment protocol

1. `benchmarks/generators/verifybench.py` creates fictional submissions (seeded). Each records truth per document, entity identity, per-unit ground truth, transformations and hashes.
2. Scenarios: clean, format variation, simulated OCR noise, similar-name different-person traps (including a hard same-DOB trap), superseded versions, exact conflicts, cross-field temporal conflicts, intra-document date order, ambiguous day/month dates, day/month-swap conflicts, missing fields. Unseen template T5 (unrecognised labels, Roman-numeral dates) forms `test_ood`.
3. Systems: A exact compare · B independent+normalized · C LLM-assisted (**not run**: no model available) · D evidence graph (rules) · D+LR learned pair scorer · E calibrated + cost-sensitive abstention.
4. Training uses `train` only; calibration method (isotonic vs Platt) is chosen by cross-validated NLL on `calibration` only; `test` is never used to select anything. Decision thresholds follow from the declared cost model (Bayes-optimal given calibrated p), not tuned on test.
5. Statistics: cluster bootstrap over identity families (2,000 resamples), paired for differences; 3 independent dataset draws for replication.
6. Ablations: A1 graph, A2 temporal reasoning, A3 calibration, A4 abstention, A5 entity resolution. (A6–A9 not run as decision ablations.)
7. Not measured: real OCR error rates (noise is simulated), real-document performance, visual forensics accuracy, LLM baseline.
8. Run `python scripts/reproduce_results.py`; outputs `artifacts/metrics/results.json`, `artifacts/plots/*.png`, `research/results.md`, `artifacts/reports/index.html`.
