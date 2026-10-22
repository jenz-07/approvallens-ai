# ApprovalLens VerifyBench — measured results

> **Generated automatically** by `scripts/reproduce_results.py` (code hash `e5fc853662d0`, dataset hash `6b855ad13e15`, seed 42, Python 3.12.3, scikit-learn 1.8.0). Do not edit by hand. 

## Read this first: what these numbers are and are not

- The benchmark is **synthetic**: fictional documents rendered as text with **simulated** OCR noise and simulated OCR confidences. It measures how the systems behave on the failure modes *this generator* injects, not real-world accuracy.
- The generator, the systems and the metrics were written by the same team. Treat advantages as *internal-validity evidence*, not a claim of state of the art. Real scanned documents and an independent annotator are required before any real-world claim.
- Costs (FP=1, FN=5, review=0.4) are **illustrative assumptions**, not stakeholder-validated; see the sensitivity analysis.
- Splits are grouped by identity family (no family appears in two splits). Calibration is fitted on a separate calibration split; test data was never used to choose methods or thresholds.
- System C (LLM-assisted) was **not run**: no model/credentials were available, and the adapter refuses to fabricate output. Visual tampering (RQ3 multimodal fusion) was **not evaluated**.

Dataset: {'train': 1800, 'test': 600, 'calibration': 600, 'test_ood': 600} submissions; ground-truth contradiction units per split: {'train': 602, 'test': 201, 'calibration': 217, 'test_ood': 201} of {'train': 14357, 'test': 4780, 'calibration': 4785, 'test_ood': 4786} units.

## 1. Main comparison — in-distribution held-out test

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| A — exact compare | 0.093 | 0.751 | 0.165 [0.146, 0.184] | 0.165 | 50 | 1477 | 0.000 | 0.3524 [0.335, 0.371] |
| B — independent, normalized | 0.223 | 0.736 | 0.342 [0.303, 0.382] | 0.342 | 53 | 516 | 0.000 | 0.1594 [0.143, 0.177] |
| D — evidence graph (rules) | 0.737 | 0.836 | 0.783 [0.742, 0.820] | 0.783 | 33 | 60 | 0.000 | 0.0459 [0.035, 0.058] |
| D+LR — graph + learned scorer | 0.948 | 0.821 | 0.880 [0.841, 0.912] | 0.880 | 36 | 9 | 0.000 | 0.0395 [0.028, 0.053] |
| E — graph + calibration + abstention | 0.982 | 0.801 | 0.882 [0.844, 0.915] | 0.970 | 9 | 3 | 0.099 | 0.0495 [0.043, 0.057] |

*Strict* counts every abstention as “not flagged”. *If reviews resolved* assumes the human reviewer resolves each reviewed unit correctly (an assumption, not a measurement). Unit = one comparison (e.g. `person.date_of_birth`) within a submission. When nearly every unit is reviewed (unseen template), “if reviews resolved” approaches 1.0 trivially and says nothing about the model.

### Paired differences (cluster bootstrap over identity families)

| Comparison | ΔF1 (strict) [95% CI] | ΔCost/unit [95% CI] | ΔF1 if reviews resolved [95% CI] |
|---|---|---|---|
| D_evidence_graph - B_independent_normalized | 0.441 [0.391, 0.492] | -0.1135 [-0.135, -0.094] | 0.441 [0.391, 0.492] |
| D_evidence_graph - A_exact_compare | 0.618 [0.577, 0.658] | -0.3065 [-0.328, -0.286] | 0.618 [0.577, 0.658] |
| E_graph_calibrated_selective - D_evidence_graph | 0.099 [0.068, 0.129] | 0.0036 [-0.006, 0.014] | 0.186 [0.147, 0.227] |
| E_graph_calibrated_selective - D+LR_raw_threshold | 0.002 [-0.015, 0.018] | 0.0100 [-0.001, 0.020] | 0.090 [0.058, 0.123] |
| E_graph_calibrated_selective - B_independent_normalized | 0.540 [0.485, 0.595] | -0.1098 [-0.128, -0.093] | 0.628 [0.584, 0.671] |
| E_graph_calibrated_selective - A1_no_evidence_graph | 0.382 [0.312, 0.459] | -0.0341 [-0.041, -0.026] | 0.041 [0.013, 0.072] |
| E_graph_calibrated_selective - A3_no_calibration | 0.002 [0.000, 0.008] | 0.0007 [-0.002, 0.002] | 0.005 [0.000, 0.013] |
| E_graph_calibrated_selective - A4_no_selective_prediction | 0.002 [-0.015, 0.018] | 0.0100 [-0.001, 0.020] | 0.090 [0.058, 0.123] |
| E_graph_calibrated_selective - A5_no_entity_resolution | -0.026 [-0.061, 0.011] | 0.0126 [0.007, 0.019] | 0.002 [-0.018, 0.023] |
| E_graph_calibrated_selective - A2_no_cross_field_temporal | 0.162 [0.120, 0.207] | -0.0342 [-0.039, -0.030] | 0.005 [-0.006, 0.017] |
| D+LR_raw_threshold - D_evidence_graph | 0.097 [0.071, 0.123] | -0.0064 [-0.010, -0.002] | 0.097 [0.071, 0.123] |

## 2. Unseen template (`test_ood`)

Unseen layout T5: mostly unrecognised labels and Roman-numeral dates the parser does not support. Deterministic extraction therefore *misses* many fields.

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| A — exact compare | 0.105 | 0.373 | 0.164 [0.132, 0.197] | 0.164 | 126 | 638 | 0.000 | 0.2626 [0.244, 0.282] |
| B — independent, normalized | 0.196 | 0.363 | 0.254 [0.208, 0.302] | 0.254 | 128 | 300 | 0.000 | 0.1947 [0.175, 0.214] |
| D — evidence graph (rules) | 0.970 | 0.159 | 0.274 [0.202, 0.347] | 0.274 | 169 | 1 | 0.000 | 0.1752 [0.153, 0.198] |
| D+LR — graph + learned scorer | 0.970 | 0.159 | 0.274 [0.202, 0.347] | 0.274 | 169 | 1 | 0.000 | 0.1768 [0.155, 0.200] |
| E — graph + calibration + abstention | 1.000 | 0.159 | 0.275 [0.203, 0.347] | 0.967 | 13 | 0 | 0.663 | 0.2789 [0.272, 0.287] |

Extraction field recall: in-distribution 1.000 vs unseen template 0.466.

## 3. Ablations (in-distribution test)

| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |
|---|---|---|---|---|---|---|---|---|
| E — graph + calibration + abstention | 0.982 | 0.801 | 0.882 [0.844, 0.915] | 0.970 | 9 | 3 | 0.099 | 0.0495 [0.043, 0.057] |
| A1 — E without evidence graph | 0.758 | 0.373 | 0.500 [0.429, 0.562] | 0.929 | 6 | 24 | 0.181 | 0.0836 [0.079, 0.089] |
| A2 — E without cross-field temporal | 0.959 | 0.577 | 0.720 [0.663, 0.772] | 0.965 | 9 | 5 | 0.183 | 0.0838 [0.078, 0.091] |
| A3 — E without calibration | 0.976 | 0.801 | 0.880 [0.841, 0.913] | 0.965 | 10 | 4 | 0.094 | 0.0489 [0.042, 0.057] |
| A4 — E without abstention | 0.948 | 0.821 | 0.880 [0.841, 0.912] | 0.880 | 36 | 9 | 0.000 | 0.0395 [0.028, 0.053] |
| A5 — E without entity resolution | 0.961 | 0.861 | 0.908 [0.875, 0.937] | 0.968 | 6 | 7 | 0.073 | 0.0369 [0.032, 0.043] |

**Ablations that scored a lower expected cost than the full system E (point estimates):** A3 — E without calibration; A4 — E without abstention; A5 — E without entity resolution. A component whose removal does not hurt is not justified by this benchmark; this is reported rather than hidden. Ablation A6 (source-region grounding) and A7–A9 were not run as decision ablations.

## 4. Hypotheses

- **RQ1 (graph reasoning beats independent/rule baselines):** D vs B ΔF1 = 0.441 [0.391, 0.492] → supported (CI excludes 0 in the favourable direction). D vs A ΔF1 = 0.618 [0.577, 0.658] → supported (CI excludes 0 in the favourable direction). Mechanisms in this benchmark: supersession handling, entity-aware comparison (similar-name traps), cross-field temporal checks.
- **RQ2 (calibration + abstention):** E vs D+LR cost Δ = 0.0100 [-0.001, 0.020] → not supported (CI includes 0) (in-distribution). E missed 9 true contradictions vs 36 for D+LR, at a review rate of 0.099. On the unseen template E missed 13 vs 169, with review rate 0.663; under the assumed costs its expected cost there is 0.2789 vs 0.1768 (see sensitivity).
- **RQ3 (multimodal fusion):** *not evaluated.* Only a metadata/ELA forensic module exists; it is unit-tested only and makes no performance claim.
- **RQ4 (evidence-efficient review):** area under the confirmed-contradictions curve — information-gain/cost 10600.3, uncertainty sampling 10648.2, random 13160.0, oracle 25838.9 (queue of 472 items, 31 true contradictions). Reviewer costs are assumed. Verdict: **not supported** — information-gain/cost ordering did not beat random order in this queue. Likely reason: most queue items are missing-evidence/unresolved-link units whose probability is a base rate, so entropy cannot rank them; a better priority model for such items is needed.

## 5. Uncertainty

Calibrator selected on the calibration split by cross-validated NLL: `platt` (CV NLL {'isotonic': 0.055966913395677276, 'platt': 0.04931615780492551}).

| Split | Score | Brier | NLL | ECE |
|---|---|---|---|---|
| test | raw | 0.0060 | 0.0384 | 0.0048 |
| test | calibrated | 0.0064 | 0.0385 | 0.0079 |
| test_ood | raw | 0.0137 | 0.0918 | 0.0133 |
| test_ood | calibrated | 0.0137 | 0.0819 | 0.0110 |

Units with candidate pairs: test 4110 (170 positive). Calibration by OCR quality (calibrated ECE): low_ocr_quality: 0.0106 (n=1922), high_ocr_quality: 0.0061 (n=2188). ECE with few positives is noisy; calibration under distribution shift (unseen template) is not guaranteed.

Risk–coverage (test, area under risk curve; lower is better): calibrated probability 0.0041, raw score 0.0041, OCR-confidence-only ranking of D's decisions 0.0139. Always-predict error rate 0.0151; E operating point: coverage 0.901, selective risk 0.0028.

![reliability](../artifacts/plots/reliability.png)
![risk-coverage](../artifacts/plots/risk_coverage.png)

## 6. Cost sensitivity (FP cost fixed at 1)

| Split | FN cost | Review cost | E | D+LR | D | E lowest? |
|---|---|---|---|---|---|---|
| test | 2.0 | 0.1 | 0.0141 | 0.0169 | 0.0257 | yes |
| test | 2.0 | 0.2 | 0.0243 | 0.0169 | 0.0257 | no |
| test | 2.0 | 0.4 | 0.0400 | 0.0169 | 0.0257 | no |
| test | 2.0 | 0.8 | 0.0744 | 0.0169 | 0.0257 | no |
| test | 2.0 | 1.2 | 0.1080 | 0.0169 | 0.0257 | no |
| test | 5.0 | 0.1 | 0.0200 | 0.0395 | 0.0459 | yes |
| test | 5.0 | 0.2 | 0.0283 | 0.0395 | 0.0459 | yes |
| test | 5.0 | 0.4 | 0.0495 | 0.0395 | 0.0459 | no |
| test | 5.0 | 0.8 | 0.0831 | 0.0395 | 0.0459 | no |
| test | 5.0 | 1.2 | 0.1170 | 0.0395 | 0.0459 | no |
| test | 10.0 | 0.1 | 0.0276 | 0.0772 | 0.0796 | yes |
| test | 10.0 | 0.2 | 0.0385 | 0.0772 | 0.0796 | yes |
| test | 10.0 | 0.4 | 0.0551 | 0.0772 | 0.0796 | yes |
| test | 10.0 | 0.8 | 0.0988 | 0.0772 | 0.0796 | no |
| test | 10.0 | 1.2 | 0.1343 | 0.0772 | 0.0796 | no |
| test_ood | 2.0 | 0.1 | 0.0724 | 0.0708 | 0.0702 | no |
| test_ood | 2.0 | 0.2 | 0.1382 | 0.0708 | 0.0702 | no |
| test_ood | 2.0 | 0.4 | 0.2711 | 0.0708 | 0.0702 | no |
| test_ood | 2.0 | 0.8 | 0.5335 | 0.0708 | 0.0702 | no |
| test_ood | 2.0 | 1.2 | 0.7958 | 0.0708 | 0.0702 | no |
| test_ood | 5.0 | 0.1 | 0.0806 | 0.1768 | 0.1752 | yes |
| test_ood | 5.0 | 0.2 | 0.1464 | 0.1768 | 0.1752 | yes |
| test_ood | 5.0 | 0.4 | 0.2789 | 0.1768 | 0.1752 | no |
| test_ood | 5.0 | 0.8 | 0.5475 | 0.1768 | 0.1752 | no |
| test_ood | 5.0 | 1.2 | 0.8102 | 0.1768 | 0.1752 | no |
| test_ood | 10.0 | 0.1 | 0.0941 | 0.3533 | 0.3502 | yes |
| test_ood | 10.0 | 0.2 | 0.1600 | 0.3533 | 0.3502 | yes |
| test_ood | 10.0 | 0.4 | 0.2924 | 0.3533 | 0.3502 | yes |
| test_ood | 10.0 | 0.8 | 0.5578 | 0.3533 | 0.3502 | no |
| test_ood | 10.0 | 1.2 | 0.8198 | 0.3533 | 0.3502 | no |

## 7. Extraction and entity resolution

| Split | Field recall | Exact text match | Source-grounding | Value fidelity (primary reading) | Truth among candidate readings | Ambiguous rate |
|---|---|---|---|---|---|---|
| test | 1.000 | 1.000 | 1.000 | 0.873 | 0.915 | 0.088 |
| test_ood | 0.466 | 1.000 | 1.000 | 0.728 | 0.737 | 0.023 |

CER/WER were **not measured** (no OCR engine benchmarked; noise is simulated). Source regions are generator-supplied line boxes, so grounding accuracy here is optimistic.

| Split | Pairwise precision | Pairwise recall | False-merge rate | False-split rate | False merges / different-entity pairs |
|---|---|---|---|---|---|
| test | 0.985 | 0.956 | 0.2764 | 0.044 | 34 / 123 |
| test_ood | 0.998 | 0.905 | 0.0292 | 0.095 | 5 / 171 |

## 8. Latency (single-process CPU, generated text)

| Stage | Median ms | p95 ms |
|---|---|---|
| A | 0.56 | 0.95 |
| B | 0.54 | 0.90 |
| D | 1.08 | 1.80 |
| E_scoring_calibration_decision | 1.19 | 1.97 |

Excludes PDF rendering and OCR, so it is not end-to-end production latency.

## 9. Error analysis (in-distribution test)

**D — evidence graph (rules)** — false positives by scenario: {'clean': 10, 'ocr_noise': 16, 'conflict_exact': 6, 'entity_trap': 12, 'format_variation': 6, 'conflict_noisy': 4, 'missing_field': 2, 'version_supersede': 2, 'conflict_intradoc': 1, 'date_ambiguity': 1}; false negatives by scenario|reason: {'conflict_exact|injected_value_conflict': 20, 'conflict_noisy|injected_value_conflict': 8, 'conflict_intradoc|expiry_before_issue': 2, 'date_swap_conflict|day_month_swap': 3}.

- FN example `S0034-1` (conflict_exact, institution.institution_name): []
- FN example `S0039-3` (conflict_exact, institution.institution_name): []
- FN example `S0085-1` (conflict_noisy, institution.institution_name): []
- FP example `S0027-2` (clean, person.person_name)
- FP example `S0027-3` (clean, person.person_name)
- FP example `S0038-1` (ocr_noise, person.dob_vs_qualification)

**E — graph + calibration + abstention** — false positives by scenario: {'clean': 1, 'conflict_noisy': 1, 'conflict_exact': 1}; false negatives by scenario|reason: {'conflict_exact|injected_value_conflict': 3, 'conflict_intradoc|expiry_before_issue': 2, 'conflict_noisy|injected_value_conflict': 2, 'conflict_temporal|implausible_age_at_qualification': 2}.

- FN example `S0111-0` (conflict_exact, person.person_name): [['Mohammed Lal Pillai', 'Mohammed Lal Pillai', 'equal']]
- FN example `S0131-0` (conflict_exact, person.person_name): [['Vikram Kumar Khan', 'Vikram K. Khan', 'variant']]
- FN example `S0150-2` (conflict_intradoc, doc.date_order): []
- FP example `S0027-3` (clean, person.person_name)
- FP example `S0304-1` (conflict_noisy, institution.address)
- FP example `S0353-1` (conflict_exact, person.person_name)

**B — independent, normalized** — false positives by scenario: {'version_supersede': 68, 'ocr_noise': 106, 'entity_trap': 79, 'conflict_exact': 45, 'clean': 58, 'conflict_temporal': 33, 'format_variation': 58, 'missing_field': 7, 'date_ambiguity': 24, 'conflict_noisy': 25, 'conflict_intradoc': 11, 'date_swap_conflict': 2}; false negatives by scenario|reason: {'conflict_temporal|implausible_age_at_qualification': 48, 'conflict_noisy|injected_value_conflict': 1, 'conflict_intradoc|expiry_before_issue': 2, 'date_swap_conflict|day_month_swap': 1, 'conflict_exact|injected_value_conflict': 1}.

- FN example `S0019-1` (conflict_temporal, person.dob_vs_qualification): []
- FN example `S0051-1` (conflict_temporal, person.dob_vs_qualification): []
- FN example `S0052-3` (conflict_temporal, person.dob_vs_qualification): []
- FP example `S0002-0` (version_supersede, institution.address)
- FP example `S0002-0` (version_supersede, institution.institution_name)
- FP example `S0002-1` (ocr_noise, institution.address)

## 10. Replication across independent dataset draws

Seeds [42, 43, 44]; mean ± sd (n=3, so sd is a rough guide only).

| System | F1 (strict) test | Cost/unit test | F1 (strict) unseen | Cost/unit unseen |
|---|---|---|---|---|
| A — exact compare | 0.167 ± 0.006 | 0.3477 ± 0.0088 | 0.182 ± 0.020 | 0.2607 ± 0.0025 |
| B — independent, normalized | 0.345 ± 0.017 | 0.1562 ± 0.0090 | 0.284 ± 0.029 | 0.1915 ± 0.0029 |
| D — evidence graph (rules) | 0.767 ± 0.019 | 0.0517 ± 0.0053 | 0.255 ± 0.048 | 0.1853 ± 0.0088 |
| D+LR — graph + learned scorer | 0.862 ± 0.017 | 0.0466 ± 0.0062 | 0.255 ± 0.049 | 0.1868 ± 0.0087 |
| E — graph + calibration + abstention | 0.849 ± 0.029 | 0.0506 ± 0.0016 | 0.253 ± 0.047 | 0.2851 ± 0.0103 |

## 11. Reproduce

```sh
python scripts/reproduce_results.py        # full run (≈ a few minutes on CPU)
python scripts/reproduce_results.py --quick # smoke run, reduced sizes
```

Config: `ml/config/evaluation.yaml`, `ml/config/thresholds.yaml`. Learned scorer coefficients are in `artifacts/metrics/results.json`. Runtime of the generating run: 155.5 s.
