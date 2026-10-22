# ApprovalLens VerifyBench — measured results

> **Generated automatically** by `scripts/reproduce_results.py` (code hash `fd25342471e4`, dataset hash `786f62007ea5`, seed 42, Python 3.12.14, scikit-learn 1.9.1). Do not edit by hand. **QUICK MODE: reduced sizes — do not cite.**

## Read this first: what these numbers are and are not

- The benchmark is **synthetic**: fictional documents rendered as text with **simulated** OCR noise and simulated OCR confidences. It measures how the systems behave on the failure modes *this generator* injects, not real-world accuracy.
- The generator, the systems and the metrics were written by the same team. Treat advantages as *internal-validity evidence*, not a claim of state of the art. Real scanned documents and an independent annotator are required before any real-world claim.
- Costs (FP=1, FN=5, review=0.4) are **illustrative assumptions**, not stakeholder-validated; see the sensitivity analysis.
- Splits are grouped by identity family (no family appears in two splits). Calibration is fitted on a separate calibration split; test data was never used to choose methods or thresholds.
- System C (LLM-assisted) was **not run**: no model/credentials were available, and the adapter refuses to fabricate output. Visual tampering (RQ3 multimodal fusion) was **not evaluated**.

Dataset: {'train': 480, 'test': 160, 'calibration': 160, 'test_ood': 160} submissions; ground-truth contradiction units per split: {'train': 170, 'test': 57, 'calibration': 50, 'test_ood': 48} of {'train': 3831, 'test': 1276, 'calibration': 1272, 'test_ood': 1277} units.

## 1. Main comparison — in-distribution held-out test

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| A — exact compare | 0.121 | 0.877 | 0.213 [0.172, 0.254] | 0.213 | 7 | 362 | 0.000 | 0.3054 [0.274, 0.334] |
| B — independent, normalized | 0.304 | 0.842 | 0.447 [0.370, 0.512] | 0.447 | 9 | 110 | 0.000 | 0.1192 [0.091, 0.141] |
| D — evidence graph (rules) | 0.703 | 0.789 | 0.744 [0.661, 0.797] | 0.744 | 12 | 19 | 0.000 | 0.0608 [0.041, 0.081] |
| D+LR — graph + learned scorer | 0.917 | 0.772 | 0.838 [0.779, 0.893] | 0.838 | 13 | 4 | 0.000 | 0.0541 [0.031, 0.076] |
| E — graph + calibration + abstention | 0.935 | 0.754 | 0.835 [0.777, 0.889] | 0.909 | 7 | 3 | 0.111 | 0.0743 [0.057, 0.091] |

*Strict* counts every abstention as “not flagged”. *If reviews resolved* assumes the human reviewer resolves each reviewed unit correctly (an assumption, not a measurement). Unit = one comparison (e.g. `person.date_of_birth`) within a submission. When nearly every unit is reviewed (unseen template), “if reviews resolved” approaches 1.0 trivially and says nothing about the model.

### Paired differences (cluster bootstrap over identity families)

| Comparison | ΔF1 (strict) [95% CI] | ΔCost/unit [95% CI] | ΔF1 if reviews resolved [95% CI] |
|---|---|---|---|
| D_evidence_graph - B_independent_normalized | 0.297 [0.207, 0.387] | -0.0585 [-0.090, -0.026] | 0.297 [0.207, 0.387] |
| D_evidence_graph - A_exact_compare | 0.531 [0.464, 0.596] | -0.2446 [-0.279, -0.213] | 0.531 [0.464, 0.596] |
| E_graph_calibrated_selective - D_evidence_graph | 0.091 [0.029, 0.147] | 0.0135 [0.001, 0.029] | 0.165 [0.108, 0.220] |
| E_graph_calibrated_selective - D+LR_raw_threshold | -0.003 [-0.032, 0.021] | 0.0202 [0.004, 0.036] | 0.071 [0.028, 0.119] |
| E_graph_calibrated_selective - B_independent_normalized | 0.388 [0.294, 0.487] | -0.0449 [-0.069, -0.015] | 0.463 [0.372, 0.545] |
| E_graph_calibrated_selective - A1_no_evidence_graph | 0.347 [0.240, 0.444] | -0.0191 [-0.030, -0.005] | 0.002 [-0.041, 0.050] |
| E_graph_calibrated_selective - A3_no_calibration | 0.035 [0.000, 0.085] | -0.0009 [-0.002, 0.000] | 0.000 [0.000, 0.000] |
| E_graph_calibrated_selective - A4_no_selective_prediction | -0.003 [-0.032, 0.021] | 0.0202 [0.004, 0.036] | 0.071 [0.028, 0.119] |
| E_graph_calibrated_selective - A5_no_entity_resolution | -0.071 [-0.132, 0.000] | 0.0230 [0.011, 0.039] | -0.046 [-0.084, -0.014] |
| E_graph_calibrated_selective - A2_no_cross_field_temporal | 0.055 [0.019, 0.099] | -0.0321 [-0.036, -0.028] | 0.008 [0.000, 0.028] |
| D+LR_raw_threshold - D_evidence_graph | 0.094 [0.048, 0.140] | -0.0067 [-0.014, 0.002] | 0.094 [0.048, 0.140] |

## 2. Unseen template (`test_ood`)

Unseen layout T5: mostly unrecognised labels and Roman-numeral dates the parser does not support. Deterministic extraction therefore *misses* many fields.

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| A — exact compare | 0.096 | 0.375 | 0.153 [0.090, 0.218] | 0.153 | 30 | 170 | 0.000 | 0.2481 [0.208, 0.286] |
| B — independent, normalized | 0.172 | 0.354 | 0.231 [0.144, 0.324] | 0.231 | 31 | 82 | 0.000 | 0.1837 [0.143, 0.223] |
| D — evidence graph (rules) | 1.000 | 0.208 | 0.345 [0.230, 0.468] | 0.345 | 38 | 0 | 0.000 | 0.1473 [0.104, 0.190] |
| D+LR — graph + learned scorer | 1.000 | 0.208 | 0.345 [0.230, 0.468] | 0.345 | 38 | 0 | 0.000 | 0.1488 [0.106, 0.192] |
| E — graph + calibration + abstention | 1.000 | 0.208 | 0.345 [0.230, 0.468] | 1.000 | 0 | 0 | 0.667 | 0.2669 [0.261, 0.273] |

Extraction field recall: in-distribution 1.000 vs unseen template 0.462.

## 3. Ablations (in-distribution test)

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| E — graph + calibration + abstention | 0.935 | 0.754 | 0.835 [0.777, 0.889] | 0.909 | 7 | 3 | 0.111 | 0.0743 [0.057, 0.091] |
| A1 — E without evidence graph | 0.724 | 0.368 | 0.488 [0.385, 0.590] | 0.908 | 3 | 8 | 0.189 | 0.0934 [0.081, 0.109] |
| A2 — E without cross-field temporal | 0.907 | 0.684 | 0.780 [0.698, 0.843] | 0.901 | 7 | 4 | 0.190 | 0.1064 [0.090, 0.123] |
| A3 — E without calibration | 0.930 | 0.702 | 0.800 [0.727, 0.860] | 0.909 | 7 | 3 | 0.114 | 0.0752 [0.058, 0.092] |
| A4 — E without abstention | 0.917 | 0.772 | 0.838 [0.779, 0.893] | 0.838 | 13 | 4 | 0.000 | 0.0541 [0.031, 0.076] |
| A5 — E without entity resolution | 0.980 | 0.842 | 0.906 [0.847, 0.952] | 0.955 | 4 | 1 | 0.087 | 0.0513 [0.038, 0.068] |

**Ablations that scored a lower expected cost than the full system E (point estimates):** A4 — E without abstention; A5 — E without entity resolution. A component whose removal does not hurt is not justified by this benchmark; this is reported rather than hidden. Ablation A6 (source-region grounding) and A7–A9 were not run as decision ablations.

## 4. Hypotheses

- **RQ1 (graph reasoning beats independent/rule baselines):** D vs B ΔF1 = 0.297 [0.207, 0.387] → supported (CI excludes 0 in the favourable direction). D vs A ΔF1 = 0.531 [0.464, 0.596] → supported (CI excludes 0 in the favourable direction). Mechanisms in this benchmark: supersession handling, entity-aware comparison (similar-name traps), cross-field temporal checks.
- **RQ2 (calibration + abstention):** E vs D+LR cost Δ = 0.0202 [0.004, 0.036] → contradicted (CI excludes 0 in the unfavourable direction) (in-distribution). E missed 7 true contradictions vs 13 for D+LR, at a review rate of 0.111. On the unseen template E missed 0 vs 38, with review rate 0.667; under the assumed costs its expected cost there is 0.2669 vs 0.1488 (see sensitivity).
- **RQ3 (multimodal fusion):** *not evaluated.* Only a metadata/ELA forensic module exists; it is unit-tested only and makes no performance claim.
- **RQ4 (evidence-efficient review):** area under the confirmed-contradictions curve — information-gain/cost 1377.0, uncertainty sampling 1380.1, random 944.6, oracle 1803.2 (queue of 142 items, 7 true contradictions). Reviewer costs are assumed. Verdict: **not supported** — information-gain/cost ordering did not beat uncertainty sampling in this queue. Likely reason: most queue items are missing-evidence/unresolved-link units whose probability is a base rate, so entropy cannot rank them; a better priority model for such items is needed.

## 5. Uncertainty

Calibrator selected on the calibration split by cross-validated NLL: `platt` (CV NLL {'isotonic': 0.049524884562171176, 'platt': 0.03630556934984318}).

| Split | Score | Brier | NLL | ECE |
|---|---|---|---|---|
| test | raw | 0.0106 | 0.0570 | 0.0098 |
| test | calibrated | 0.0102 | 0.0610 | 0.0090 |
| test_ood | raw | 0.0097 | 0.0507 | 0.0101 |
| test_ood | calibrated | 0.0089 | 0.0539 | 0.0103 |

Units with candidate pairs: test 1094 (47 positive). Calibration by OCR quality (calibrated ECE): low_ocr_quality: 0.0091 (n=500), high_ocr_quality: 0.0103 (n=594). ECE with few positives is noisy; calibration under distribution shift (unseen template) is not guaranteed.

Risk–coverage (test, area under risk curve; lower is better): calibrated probability 0.0092, raw score 0.0092, OCR-confidence-only ranking of D's decisions 0.0198. Always-predict error rate 0.0169; E operating point: coverage 0.889, selective risk 0.0088.

![reliability](../artifacts/plots/reliability.png)
![risk-coverage](../artifacts/plots/risk_coverage.png)

## 6. Cost sensitivity (FP cost fixed at 1)

| Split | FN cost | Review cost | E | D+LR | D | E lowest? |
|---|---|---|---|---|---|---|
| test | 2.0 | 0.1 | 0.0237 | 0.0235 | 0.0331 | no |
| test | 2.0 | 0.2 | 0.0362 | 0.0235 | 0.0331 | no |
| test | 2.0 | 0.4 | 0.0531 | 0.0235 | 0.0331 | no |
| test | 2.0 | 0.8 | 0.0903 | 0.0235 | 0.0331 | no |
| test | 2.0 | 1.2 | 0.1276 | 0.0235 | 0.0331 | no |
| test | 5.0 | 0.1 | 0.0401 | 0.0541 | 0.0608 | yes |
| test | 5.0 | 0.2 | 0.0531 | 0.0541 | 0.0608 | yes |
| test | 5.0 | 0.4 | 0.0743 | 0.0541 | 0.0608 | no |
| test | 5.0 | 0.8 | 0.1124 | 0.0541 | 0.0608 | no |
| test | 5.0 | 1.2 | 0.1495 | 0.0541 | 0.0608 | no |
| test | 10.0 | 0.1 | 0.0676 | 0.1050 | 0.1069 | yes |
| test | 10.0 | 0.2 | 0.0806 | 0.1050 | 0.1069 | yes |
| test | 10.0 | 0.4 | 0.1017 | 0.1050 | 0.1069 | yes |
| test | 10.0 | 0.8 | 0.1459 | 0.1050 | 0.1069 | no |
| test | 10.0 | 1.2 | 0.1848 | 0.1050 | 0.1069 | no |
| test_ood | 2.0 | 0.1 | 0.0675 | 0.0595 | 0.0589 | no |
| test_ood | 2.0 | 0.2 | 0.1341 | 0.0595 | 0.0589 | no |
| test_ood | 2.0 | 0.4 | 0.2662 | 0.0595 | 0.0589 | no |
| test_ood | 2.0 | 0.8 | 0.5309 | 0.0595 | 0.0589 | no |
| test_ood | 2.0 | 1.2 | 0.7956 | 0.0595 | 0.0589 | no |
| test_ood | 5.0 | 0.1 | 0.0675 | 0.1488 | 0.1473 | yes |
| test_ood | 5.0 | 0.2 | 0.1345 | 0.1488 | 0.1473 | yes |
| test_ood | 5.0 | 0.4 | 0.2669 | 0.1488 | 0.1473 | no |
| test_ood | 5.0 | 0.8 | 0.5333 | 0.1488 | 0.1473 | no |
| test_ood | 5.0 | 1.2 | 0.7980 | 0.1488 | 0.1473 | no |
| test_ood | 10.0 | 0.1 | 0.0675 | 0.2976 | 0.2946 | yes |
| test_ood | 10.0 | 0.2 | 0.1345 | 0.2976 | 0.2946 | yes |
| test_ood | 10.0 | 0.4 | 0.2669 | 0.2976 | 0.2946 | yes |
| test_ood | 10.0 | 0.8 | 0.5338 | 0.2976 | 0.2946 | no |
| test_ood | 10.0 | 1.2 | 0.7987 | 0.2976 | 0.2946 | no |

## 7. Extraction and entity resolution

| Split | Field recall | Exact text match | Source-grounding | Value fidelity (primary reading) | Truth among candidate readings | Ambiguous rate |
|---|---|---|---|---|---|---|
| test | 1.000 | 1.000 | 1.000 | 0.881 | 0.915 | 0.073 |
| test_ood | 0.462 | 1.000 | 1.000 | 0.725 | 0.732 | 0.017 |

CER/WER were **not measured** (no OCR engine benchmarked; noise is simulated). Source regions are generator-supplied line boxes, so grounding accuracy here is optimistic.

| Split | Pairwise precision | Pairwise recall | False-merge rate | False-split rate | False merges / different-entity pairs |
|---|---|---|---|---|---|
| test | 0.997 | 0.953 | 0.0952 | 0.047 | 2 / 21 |
| test_ood | 1.000 | 0.901 | 0.0000 | 0.099 | 0 / 54 |

## 8. Latency (single-process CPU, generated text)

| Stage | Median ms | p95 ms |
|---|---|---|
| A | 0.36 | 0.67 |
| B | 0.34 | 0.59 |
| D | 0.71 | 1.26 |
| E_scoring_calibration_decision | 0.90 | 1.41 |

Excludes PDF rendering and OCR, so it is not end-to-end production latency.

## 9. Error analysis (in-distribution test)

**D — evidence graph (rules)** — false positives by scenario: {'clean': 7, 'conflict_noisy': 2, 'entity_trap': 1, 'ocr_noise': 4, 'conflict_exact': 2, 'format_variation': 2, 'missing_field': 1}; false negatives by scenario|reason: {'conflict_exact|injected_value_conflict': 8, 'conflict_intradoc|expiry_before_issue': 2, 'conflict_noisy|injected_value_conflict': 2}.

- FN example `S0039-3` (conflict_exact, institution.institution_name): []
- FN example `S0073-3` (conflict_exact, institution.institution_name): [['Horizon Institutc of Technology Annex', 'Horizon Institute of Technology', 'variant']]
- FN example `S0094-0` (conflict_intradoc, doc.date_order): []
- FP example `S0024-3` (clean, person.dob_vs_qualification)
- FP example `S0027-2` (clean, person.person_name)
- FP example `S0027-3` (clean, person.person_name)

**E — graph + calibration + abstention** — false positives by scenario: {'clean': 1, 'entity_trap': 1, 'format_variation': 1}; false negatives by scenario|reason: {'conflict_exact|injected_value_conflict': 4, 'conflict_intradoc|expiry_before_issue': 2, 'conflict_noisy|injected_value_conflict': 1}.

- FN example `S0073-3` (conflict_exact, institution.institution_name): [['Horizon Institutc of Technology Annex', 'Horizon Institute of Technology', 'variant']]
- FN example `S0094-0` (conflict_intradoc, doc.date_order): []
- FN example `S0111-0` (conflict_exact, person.person_name): [['Mohammed Lal Pillai', 'Mohammed Lal Pillai', 'equal']]
- FP example `S0027-3` (clean, person.person_name)
- FP example `S0036-2` (entity_trap, institution.address)
- FP example `S0118-0` (format_variation, person.person_name)

**B — independent, normalized** — false positives by scenario: {'clean': 19, 'date_ambiguity': 11, 'ocr_noise': 15, 'format_variation': 12, 'conflict_intradoc': 4, 'missing_field': 3, 'entity_trap': 15, 'conflict_exact': 8, 'version_supersede': 13, 'conflict_temporal': 1, 'conflict_noisy': 7, 'date_swap_conflict': 2}; false negatives by scenario|reason: {'conflict_exact|injected_value_conflict': 1, 'conflict_intradoc|expiry_before_issue': 2, 'conflict_temporal|implausible_age_at_qualification': 5, 'conflict_noisy|injected_value_conflict': 1}.

- FN example `S0073-3` (conflict_exact, institution.institution_name): [['Horizon Institutc of Technology Annex', 'Horizon Institute of Technology', 'variant']]
- FN example `S0094-0` (conflict_intradoc, doc.date_order): []
- FN example `S0094-3` (conflict_temporal, person.dob_vs_qualification): []
- FP example `S0004-0` (clean, institution.address)
- FP example `S0004-0` (clean, institution.institution_id)
- FP example `S0009-0` (date_ambiguity, person.date_of_birth)

## 10. Replication across independent dataset draws

Seeds [42, 43]; mean ± sd (n=2, so sd is a rough guide only).

| System | F1 (strict) test | Cost/unit test | F1 (strict) unseen | Cost/unit unseen |
|---|---|---|---|---|
| A — exact compare | 0.192 ± 0.029 | 0.3310 ± 0.0363 | 0.149 ± 0.006 | 0.2532 ± 0.0073 |
| B — independent, normalized | 0.396 ± 0.072 | 0.1413 ± 0.0312 | 0.238 ± 0.010 | 0.1815 ± 0.0032 |
| D — evidence graph (rules) | 0.719 ± 0.035 | 0.0647 ± 0.0055 | 0.249 ± 0.135 | 0.1590 ± 0.0165 |
| D+LR — graph + learned scorer | 0.835 ± 0.005 | 0.0541 ± 0.0001 | 0.249 ± 0.135 | 0.1605 ± 0.0166 |
| E — graph + calibration + abstention | 0.811 ± 0.034 | 0.0597 ± 0.0207 | 0.231 ± 0.161 | 0.2734 ± 0.0092 |

## 11. Reproduce

```sh
python scripts/reproduce_results.py        # full run (≈ a few minutes on CPU)
python scripts/reproduce_results.py --quick # smoke run, reduced sizes
```

Config: `ml/config/evaluation.yaml`, `ml/config/thresholds.yaml`. Learned scorer coefficients are in `artifacts/metrics/results.json`. Runtime of the generating run: 26.7 s.
