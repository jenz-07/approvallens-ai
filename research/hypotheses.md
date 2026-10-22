# Hypotheses (predeclared before the final run)

Hypotheses, not results. Verdicts are generated into `research/results.md` from measured data.

| ID | Hypothesis | Primary metric (predeclared) | Decision rule |
|---|---|---|---|
| RQ1 | Evidence-graph reasoning (entity resolution + supersession + cross-field temporal checks) detects cross-document inconsistencies better than independent/normalized comparison (B) and exact comparison (A) | Strict unit-level F1, test split | Paired cluster-bootstrap 95% CI of ΔF1 (D−B) excludes 0 |
| RQ2 | Calibrated probabilities + abstention lower expected cost vs forced decisions (D+LR) | Expected cost per unit under the assumed cost model; missed contradictions | CI of Δcost (E−D+LR) excludes 0; sensitivity reported |
| RQ3 | Multimodal fusion improves verification | — | **Not evaluated in v1** |
| RQ4 | Information-gain / cost ordering of the review queue finds true contradictions faster than uncertainty sampling or random order | Area under confirmed-contradictions-vs-effort curve | Descriptive (assumed reviewer costs) |

Splits: grouped by identity family; train / calibration / test, plus an unseen-template split (`test_ood`).
Costs (FP 1, FN 5, review 0.4) are illustrative assumptions and must be replaced with stakeholder-defined values.
