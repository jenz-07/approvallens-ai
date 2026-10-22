"""Render research/results.md purely from computed metrics (no hand-typed numbers)."""
from __future__ import annotations

S = {"A_exact_compare": "A — exact compare", "B_independent_normalized": "B — independent, normalized", "D_evidence_graph": "D — evidence graph (rules)",
     "D+LR_raw_threshold": "D+LR — graph + learned scorer", "E_graph_calibrated_selective": "E — graph + calibration + abstention",
     "A1_no_evidence_graph": "A1 — E without evidence graph", "A2_no_cross_field_temporal": "A2 — E without cross-field temporal",
     "A3_no_calibration": "A3 — E without calibration", "A4_no_selective_prediction": "A4 — E without abstention", "A5_no_entity_resolution": "A5 — E without entity resolution"}


def f(x, d=3): return "n/a" if x is None else f"{x:.{d}f}"
def ci(c): return "n/a" if not c else f"[{c[0]:.3f}, {c[1]:.3f}]"


def table(R, split, names):
    rows = ["| System | Precision | Recall (strict) | F1 (strict) 95% CI | F1 if reviews resolved | Missed contradictions | False alarms | Review rate | Cost/unit 95% CI |", "|---|---|---|---|---|---|---|---|---|"]
    for n in names:
        m = R[split]["systems"][n]
        rows.append(f"| {S[n]} | {f(m['precision'])} | {f(m['recall'])} | {f(m['f1'])} {ci(m['ci95']['f1'])} | {f(m['f1_if_reviews_resolved'])} | {m['missed_true_contradictions']} | {m['false_alarms']} | {f(m['review_rate'])} | {f(m['expected_cost_per_unit'], 4)} {ci(m['ci95']['cost'])} |")
    return "\n".join(rows)


def verdict(d, lower_is_better=False):
    lo, hi = d["ci95"]
    if lower_is_better: return "supported (CI excludes 0 in the favourable direction)" if hi < 0 else ("contradicted (CI excludes 0 in the unfavourable direction)" if lo > 0 else "not supported (CI includes 0)")
    return "supported (CI excludes 0 in the favourable direction)" if lo > 0 else ("contradicted (CI excludes 0 in the unfavourable direction)" if hi < 0 else "not supported (CI includes 0)")


def render(R):
    t, o = R["test"], R["test_ood"]; T = t["systems"]; O = o["systems"]; pd_ = t["paired_differences"]; pdo = o["paired_differences"]
    rc, cal, ex, er, lat = R["risk_coverage"], R["calibration"], R["extraction"], R["entity_resolution"], R["latency"]
    env = R["environment"]
    L = []
    L.append("# ApprovalLens VerifyBench — measured results\n")
    L.append(f"> **Generated automatically** by `scripts/reproduce_results.py` (code hash `{env['code_sha256'][:12]}`, dataset hash `{R['dataset_hash'][:12]}`, seed {R['seed']}, "
             f"Python {env['python']}, scikit-learn {env['scikit_learn']}). Do not edit by hand. {'**QUICK MODE: reduced sizes — do not cite.**' if env['quick_mode'] else ''}\n")
    L.append("## Read this first: what these numbers are and are not\n")
    L.append("- The benchmark is **synthetic**: fictional documents rendered as text with **simulated** OCR noise and simulated OCR confidences. It measures how the systems behave on the failure modes *this generator* injects, not real-world accuracy.\n"
             "- The generator, the systems and the metrics were written by the same team. Treat advantages as *internal-validity evidence*, not a claim of state of the art. Real scanned documents and an independent annotator are required before any real-world claim.\n"
             "- Costs (FP=1, FN=5, review=0.4) are **illustrative assumptions**, not stakeholder-validated; see the sensitivity analysis.\n"
             "- Splits are grouped by identity family (no family appears in two splits). Calibration is fitted on a separate calibration split; test data was never used to choose methods or thresholds.\n"
             "- System C (LLM-assisted) was **not run**: no model/credentials were available, and the adapter refuses to fabricate output. Visual tampering (RQ3 multimodal fusion) was **not evaluated**.\n")
    L.append(f"Dataset: {R['split_sizes']} submissions; ground-truth contradiction units per split: {R['positives']} of {R['units']} units.\n")
    L.append("## 1. Main comparison — in-distribution held-out test\n")
    L.append(table(R, "test", ["A_exact_compare", "B_independent_normalized", "D_evidence_graph", "D+LR_raw_threshold", "E_graph_calibrated_selective"]))
    L.append("\n*Strict* counts every abstention as “not flagged”. *If reviews resolved* assumes the human reviewer resolves each reviewed unit correctly (an assumption, not a measurement). Unit = one comparison (e.g. `person.date_of_birth`) within a submission. When nearly every unit is reviewed (unseen template), “if reviews resolved” approaches 1.0 trivially and says nothing about the model.\n")
    d1, d2, d3 = pd_["D_evidence_graph - B_independent_normalized"], pd_["D_evidence_graph - A_exact_compare"], pd_["E_graph_calibrated_selective - D+LR_raw_threshold"]
    L.append("### Paired differences (cluster bootstrap over identity families)\n")
    L.append("| Comparison | ΔF1 (strict) [95% CI] | ΔCost/unit [95% CI] | ΔF1 if reviews resolved [95% CI] |\n|---|---|---|---|")
    for k, v in pd_.items():
        L.append(f"| {k} | {f(v['f1']['diff'])} {ci(v['f1']['ci95'])} | {f(v['cost']['diff'], 4)} {ci(v['cost']['ci95'])} | {f(v['f1_if_reviews_resolved']['diff'])} {ci(v['f1_if_reviews_resolved']['ci95'])} |")
    L.append("\n## 2. Unseen template (`test_ood`)\n")
    L.append("Unseen layout T5: mostly unrecognised labels and Roman-numeral dates the parser does not support. Deterministic extraction therefore *misses* many fields.\n")
    L.append(table(R, "test_ood", ["A_exact_compare", "B_independent_normalized", "D_evidence_graph", "D+LR_raw_threshold", "E_graph_calibrated_selective"]))
    L.append(f"\nExtraction field recall: in-distribution {f(ex['test']['field_recall'])} vs unseen template {f(ex['test_ood']['field_recall'])}.\n")
    L.append("## 3. Ablations (in-distribution test)\n")
    L.append(table(R, "test", ["E_graph_calibrated_selective", "A1_no_evidence_graph", "A2_no_cross_field_temporal", "A3_no_calibration", "A4_no_selective_prediction", "A5_no_entity_resolution"]))
    worse = [(n, T[n]["expected_cost_per_unit"]) for n in ("A1_no_evidence_graph", "A2_no_cross_field_temporal", "A3_no_calibration", "A4_no_selective_prediction", "A5_no_entity_resolution")]
    e_cost = T["E_graph_calibrated_selective"]["expected_cost_per_unit"]
    better = [S[n] for n, c in worse if c < e_cost]
    L.append("\n**Ablations that scored a lower expected cost than the full system E (point estimates):** " + ("; ".join(better) if better else "none") + ". "
             "A component whose removal does not hurt is not justified by this benchmark; this is reported rather than hidden. Ablation A6 (source-region grounding) and A7–A9 were not run as decision ablations.\n")
    L.append("## 4. Hypotheses\n")
    L.append(f"- **RQ1 (graph reasoning beats independent/rule baselines):** D vs B ΔF1 = {f(d1['f1']['diff'])} {ci(d1['f1']['ci95'])} → {verdict(d1['f1'])}. D vs A ΔF1 = {f(d2['f1']['diff'])} {ci(d2['f1']['ci95'])} → {verdict(d2['f1'])}. "
             "Mechanisms in this benchmark: supersession handling, entity-aware comparison (similar-name traps), cross-field temporal checks.")
    L.append(f"- **RQ2 (calibration + abstention):** E vs D+LR cost Δ = {f(d3['cost']['diff'], 4)} {ci(d3['cost']['ci95'])} → {verdict(d3['cost'], True)} (in-distribution). "
             f"E missed {T['E_graph_calibrated_selective']['missed_true_contradictions']} true contradictions vs {T['D+LR_raw_threshold']['missed_true_contradictions']} for D+LR, at a review rate of {f(T['E_graph_calibrated_selective']['review_rate'])}. "
             f"On the unseen template E missed {O['E_graph_calibrated_selective']['missed_true_contradictions']} vs {O['D+LR_raw_threshold']['missed_true_contradictions']}, with review rate {f(O['E_graph_calibrated_selective']['review_rate'])}; under the assumed costs its expected cost there is {f(O['E_graph_calibrated_selective']['expected_cost_per_unit'], 4)} vs {f(O['D+LR_raw_threshold']['expected_cost_per_unit'], 4)} (see sensitivity).")
    L.append("- **RQ3 (multimodal fusion):** *not evaluated.* Only a metadata/ELA forensic module exists; it is unit-tested only and makes no performance claim.")
    rp = R["review_policy"]
    def auc(k): return sum((rp["budget_grid"][i + 1] - rp["budget_grid"][i]) * (rp[k][i + 1] + rp[k][i]) / 2 for i in range(len(rp["budget_grid"]) - 1))
    L.append(f"- **RQ4 (evidence-efficient review):** area under the confirmed-contradictions curve — information-gain/cost {f(auc('found_by_ig_per_cost'), 1)}, uncertainty sampling {f(auc('found_by_uncertainty_sampling'), 1)}, random {f(auc('found_by_random_mean'), 1)}, oracle {f(auc('found_by_oracle'), 1)} "
             f"(queue of {rp['queue_items']} items, {rp['positives_in_queue']} true contradictions). Reviewer costs are assumed. "
             + ("Verdict: **supported** — information-gain/cost beats uncertainty sampling and random order." if auc('found_by_ig_per_cost') > max(auc('found_by_uncertainty_sampling'), auc('found_by_random_mean')) else
                "Verdict: **not supported** — information-gain/cost ordering did not beat " + ("random order" if auc('found_by_ig_per_cost') < auc('found_by_random_mean') else "uncertainty sampling") + " in this queue. Likely reason: most queue items are missing-evidence/unresolved-link units whose probability is a base rate, so entropy cannot rank them; a better priority model for such items is needed.") + "\n")
    L.append("## 5. Uncertainty\n")
    c = cal["test"]
    L.append(f"Calibrator selected on the calibration split by cross-validated NLL: `{cal['method'].get('selected', cal['method'].get('note'))}` (CV NLL {cal['method'].get('cv_nll')}).\n")
    L.append("| Split | Score | Brier | NLL | ECE |\n|---|---|---|---|---|")
    for sp in ("test", "test_ood"):
        for k in ("raw", "calibrated"):
            L.append(f"| {sp} | {k} | {f(cal[sp][k]['brier'], 4)} | {f(cal[sp][k]['nll'], 4)} | {f(cal[sp][k]['ece'], 4)} |")
    L.append(f"\nUnits with candidate pairs: test {c['n_units_with_candidates']} ({c['positives']} positive). Calibration by OCR quality (calibrated ECE): " +
             ", ".join(f"{k}: {f(v['ece_calibrated'], 4)} (n={v['n']})" for k, v in c.items() if k.endswith("ocr_quality")) + ". ECE with few positives is noisy; calibration under distribution shift (unseen template) is not guaranteed.\n")
    L.append(f"Risk–coverage (test, area under risk curve; lower is better): calibrated probability {f(rc['calibrated_probability']['aurc'], 4)}, raw score {f(rc['raw_score']['aurc'], 4)}, OCR-confidence-only ranking of D's decisions {f(rc['ocr_confidence_only']['aurc'], 4)}. "
             f"Always-predict error rate {f(rc['always_predict_risk'], 4)}; E operating point: coverage {f(rc['E_operating_point']['coverage'])}, selective risk {f(rc['E_operating_point']['selective_risk'], 4)}.\n")
    L.append("![reliability](../artifacts/plots/reliability.png)\n![risk-coverage](../artifacts/plots/risk_coverage.png)\n")
    L.append("## 6. Cost sensitivity (FP cost fixed at 1)\n")
    L.append("| Split | FN cost | Review cost | E | D+LR | D | E lowest? |\n|---|---|---|---|---|---|---|")
    for r in R["sensitivity"]:
        L.append(f"| {r['split']} | {r['c_fn']} | {r['c_review']} | {f(r['cost_E'], 4)} | {f(r['cost_D+LR'], 4)} | {f(r['cost_D'], 4)} | {'yes' if r['E_better_than_best_baseline'] else 'no'} |")
    L.append("\n## 7. Extraction and entity resolution\n")
    L.append("| Split | Field recall | Exact text match | Source-grounding | Value fidelity (primary reading) | Truth among candidate readings | Ambiguous rate |\n|---|---|---|---|---|---|---|")
    for sp in ("test", "test_ood"):
        e = ex[sp]; L.append(f"| {sp} | {f(e['field_recall'])} | {f(e['exact_text_match_of_found'])} | {f(e['source_grounding_accuracy'])} | {f(e['value_fidelity_primary_reading'])} | {f(e['truth_in_candidate_readings'])} | {f(e['ambiguous_value_rate'])} |")
    L.append("\nCER/WER were **not measured** (no OCR engine benchmarked; noise is simulated). Source regions are generator-supplied line boxes, so grounding accuracy here is optimistic.\n")
    L.append("| Split | Pairwise precision | Pairwise recall | False-merge rate | False-split rate | False merges / different-entity pairs |\n|---|---|---|---|---|---|")
    for sp in ("test", "test_ood"):
        e = er[sp]; L.append(f"| {sp} | {f(e['pairwise_precision'])} | {f(e['pairwise_recall'])} | {f(e['false_merge_rate'], 4)} | {f(e['false_split_rate'])} | {e['false_merges']} / {e['different_entity_pairs']} |")
    L.append("\n## 8. Latency (single-process CPU, generated text)\n")
    L.append("| Stage | Median ms | p95 ms |\n|---|---|---|")
    for k, v in lat.items():
        if isinstance(v, dict): L.append(f"| {k} | {f(v['median_ms'], 2)} | {f(v['p95_ms'], 2)} |")
    L.append("\nExcludes PDF rendering and OCR, so it is not end-to-end production latency.\n")
    L.append("## 9. Error analysis (in-distribution test)\n")
    for name, e in R["error_analysis"].items():
        L.append(f"**{S.get(name, name)}** — false positives by scenario: {e['false_positives_by_scenario'] or 'none'}; false negatives by scenario|reason: {e['false_negatives_by_scenario_reason'] or 'none'}.\n")
        for x in e["examples_fn"][:3]: L.append(f"- FN example `{x['submission']}` ({x['scenario']}, {x['unit']}): {x['pairs']}")
        for x in e["examples_fp"][:3]: L.append(f"- FP example `{x['submission']}` ({x['scenario']}, {x['unit']})")
        L.append("")
    L.append("## 10. Replication across independent dataset draws\n")
    seeds = R["replication"]["seeds"]
    L.append(f"Seeds {seeds}; mean ± sd (n={len(seeds)}, so sd is a rough guide only).\n")
    L.append("| System | F1 (strict) test | Cost/unit test | F1 (strict) unseen | Cost/unit unseen |\n|---|---|---|---|---|")
    for n in ("A_exact_compare", "B_independent_normalized", "D_evidence_graph", "D+LR_raw_threshold", "E_graph_calibrated_selective"):
        a, b = R["replication"]["summary"]["test"][n], R["replication"]["summary"]["test_ood"][n]
        L.append(f"| {S[n]} | {f(a['f1']['mean'])} ± {f(a['f1']['sd'])} | {f(a['expected_cost_per_unit']['mean'], 4)} ± {f(a['expected_cost_per_unit']['sd'], 4)} | {f(b['f1']['mean'])} ± {f(b['f1']['sd'])} | {f(b['expected_cost_per_unit']['mean'], 4)} ± {f(b['expected_cost_per_unit']['sd'], 4)} |")
    L.append("\n## 11. Reproduce\n\n```sh\npython scripts/reproduce_results.py        # full run (≈ a few minutes on CPU)\npython scripts/reproduce_results.py --quick # smoke run, reduced sizes\n```\n")
    L.append(f"Config: `ml/config/evaluation.yaml`, `ml/config/thresholds.yaml`. Learned scorer coefficients are in `artifacts/metrics/results.json`. Runtime of the generating run: {env['runtime_seconds']} s.\n")
    return "\n".join(L)
