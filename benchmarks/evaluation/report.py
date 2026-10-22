"""Orchestrates the full experiment and writes artifacts/{metrics,plots,reports}. Used by scripts/reproduce_results.py."""
from __future__ import annotations
import base64, hashlib, json, math, platform, sys, time
from pathlib import Path
import numpy as np, yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from .run import ROOT, run_one, CostModel
from . import analysis as A
from .html_report import build_html

SHORT = {"A_exact_compare": "A exact", "B_independent_normalized": "B normalized", "D_evidence_graph": "D graph", "D+LR_raw_threshold": "D+LR",
         "E_graph_calibrated_selective": "E calibrated+selective", "A1_no_evidence_graph": "A1 no graph", "A2_no_cross_field_temporal": "A2 no temporal",
         "A3_no_calibration": "A3 no calibration", "A4_no_selective_prediction": "A4 no selective", "A5_no_entity_resolution": "A5 no entity res."}


def clean(o):
    if isinstance(o, dict): return {k: clean(v) for k, v in o.items() if not k.startswith("_")}
    if isinstance(o, (list, tuple)): return [clean(v) for v in o]
    if isinstance(o, (np.floating, float)): return None if (math.isnan(o) or math.isinf(o)) else float(o)
    if isinstance(o, np.integer): return int(o)
    if isinstance(o, np.bool_): return bool(o)
    return o


def code_hash():
    h = hashlib.sha256()
    for p in sorted(list((ROOT / "ml").rglob("*.py")) + list((ROOT / "benchmarks").rglob("*.py")) + list((ROOT / "ml/config").glob("*.yaml"))):
        h.update(p.name.encode()); h.update(p.read_bytes())
    return h.hexdigest()


def plots(R, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    main = ["A_exact_compare", "B_independent_normalized", "D_evidence_graph", "D+LR_raw_threshold", "E_graph_calibrated_selective"]
    fig, axs = plt.subplots(1, 2, figsize=(11, 4))
    for ax, split in zip(axs, ("test", "test_ood")):
        S = R[split]["systems"]; f = [S[m]["f1"] for m in main]; ci = [S[m]["ci95"]["f1"] for m in main]
        ax.bar(range(len(main)), f, yerr=[[a - c[0] for a, c in zip(f, ci)], [c[1] - a for a, c in zip(f, ci)]], color="#3b6ea5", capsize=4)
        ax.set_xticks(range(len(main))); ax.set_xticklabels([SHORT[m] for m in main], rotation=25, ha="right"); ax.set_ylim(0, 1.05)
        ax.set_title(f"Strict F1 ({'in-distribution' if split == 'test' else 'unseen template'}), 95% CI"); ax.set_ylabel("F1 (abstentions count as not flagged)")
    fig.tight_layout(); fig.savefig(out / "f1_by_system.png", dpi=130); plt.close(fig)
    cal = R["calibration"]["test"]
    fig, axs = plt.subplots(1, 2, figsize=(9, 4))
    for ax, key, t in zip(axs, ("reliability_raw", "reliability_calibrated"), ("Raw logistic score", f"Calibrated ({R['calibration']['method'].get('selected', 'platt')})")):
        b = cal[key]; ax.plot([0, 1], [0, 1], "k--", lw=1)
        ax.scatter([x["mean_pred"] for x in b], [x["frac_pos"] for x in b], s=[10 + x["n"] ** .5 * 3 for x in b], color="#c0392b")
        ax.set_xlabel("Predicted probability"); ax.set_ylabel("Observed frequency"); ax.set_title(t)
    fig.tight_layout(); fig.savefig(out / "reliability.png", dpi=130); plt.close(fig)
    rc = R["risk_coverage"]; fig, ax = plt.subplots(figsize=(6, 4))
    for k, lab, c in (("calibrated_probability", "calibrated probability", "#27ae60"), ("raw_score", "raw LR score", "#8e44ad"), ("ocr_confidence_only", "OCR confidence only (D)", "#e67e22")):
        ax.plot(rc[k]["coverage"], rc[k]["risk"], label=f"{lab} (AURC {rc[k]['aurc']:.3f})", color=c)
    ax.scatter([rc["E_operating_point"]["coverage"]], [rc["E_operating_point"]["selective_risk"]], marker="*", s=140, color="k", label="E operating point", zorder=5)
    ax.set_xlabel("Coverage"); ax.set_ylabel("Selective risk (error rate on accepted units)"); ax.set_title("Risk–coverage (test)"); ax.legend(fontsize=7); ax.set_ylim(bottom=0)
    fig.tight_layout(); fig.savefig(out / "risk_coverage.png", dpi=130); plt.close(fig)
    rp = R["review_policy"]; fig, ax = plt.subplots(figsize=(6, 4))
    for k, lab in (("found_by_oracle", "oracle"), ("found_by_ig_per_cost", "information gain / cost"), ("found_by_uncertainty_sampling", "uncertainty sampling"), ("found_by_random_mean", "random (mean of 30)")):
        ax.plot(rp["budget_grid"], rp[k], label=lab)
    ax.set_xlabel("Reviewer effort (assumed minutes)"); ax.set_ylabel("True contradictions confirmed"); ax.set_title("Review prioritization (E review queue)"); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(out / "review_budget.png", dpi=130); plt.close(fig)
    rows = [r for r in R["sensitivity"] if r["split"] == "test" and r["c_fn"] == 5.0]
    ood = [r for r in R["sensitivity"] if r["split"] == "test_ood" and r["c_fn"] == 5.0]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot([r["c_review"] for r in rows], [r["cost_E"] for r in rows], "o-", label="E (test)"); ax.plot([r["c_review"] for r in rows], [min(r["cost_D+LR"], r["cost_D"]) for r in rows], "s--", label="best baseline D / D+LR (test)")
    ax.plot([r["c_review"] for r in ood], [r["cost_E"] for r in ood], "o-", label="E (unseen template)", color="#c0392b"); ax.plot([r["c_review"] for r in ood], [min(r["cost_D+LR"], r["cost_D"]) for r in ood], "s--", label="best baseline (unseen)", color="#e67e22")
    ax.set_xlabel("Assumed cost of one review (FP=1, FN=5)"); ax.set_ylabel("Expected cost per unit"); ax.set_title("Cost sensitivity"); ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(out / "cost_sensitivity.png", dpi=130); plt.close(fig)


def replication(cfg, cm):
    rows = []
    for s in cfg["experiment"]["replication_seeds"]:
        r = run_one(s, cfg, cm, full=False)
        rows.append({"seed": s, "dataset_hash": r["dataset_hash"], "test": {k: {m: v[m] for m in ("f1", "precision", "recall", "expected_cost_per_unit", "review_rate", "f1_if_reviews_resolved", "missed_true_contradictions")} for k, v in r["test"]["systems"].items()},
                     "test_ood": {k: {m: v[m] for m in ("f1", "expected_cost_per_unit", "review_rate", "missed_true_contradictions")} for k, v in r["test_ood"]["systems"].items()}})
    summ = {}
    for split in ("test", "test_ood"):
        summ[split] = {}
        for sysname in rows[0][split]:
            summ[split][sysname] = {m: {"mean": float(np.mean([r[split][sysname][m] for r in rows])), "sd": float(np.std([r[split][sysname][m] for r in rows], ddof=1))} for m in rows[0][split][sysname]}
    return {"seeds": cfg["experiment"]["replication_seeds"], "per_seed": rows, "summary": summ}


def main(outdir: Path | None = None, quick: bool = False):
    t0 = time.time()
    cfg = yaml.safe_load((ROOT / "ml/config/evaluation.yaml").read_text()); th = yaml.safe_load((ROOT / "ml/config/thresholds.yaml").read_text())
    if quick: cfg["experiment"].update(n_submissions=800, n_ood_submissions=160, bootstrap_resamples=200, replication_seeds=[42, 43])
    cm = CostModel(th["costs"]["false_positive"], th["costs"]["false_negative"], th["costs"]["review"])
    out = outdir or (ROOT / "artifacts")
    (out / "reports").mkdir(parents=True, exist_ok=True)
    res = run_one(cfg["experiment"]["primary_seed"], cfg, cm, full=not quick)
    from ml.uncertainty.export import export_model
    _src, _sc, _cal, _info = res["_fits"]["E"]
    export_model(_sc, _cal, ROOT / "ml/models/e_model.json", {"dataset_hash": res["dataset_hash"], "seed": res["seed"], "quick_mode": quick, "calibration": clean(_info)})
    R = {k: v for k, v in res.items() if not k.startswith("_")}
    R["calibration"] = A.calibration_block(res, cm); R["risk_coverage"] = A.risk_coverage_block(res, cm)
    R["extraction"] = A.extraction_block(res); R["entity_resolution"] = A.entity_block(res); R["latency"] = A.latency_block(res, cm)
    R["error_analysis"] = A.error_analysis(res); R["sensitivity"] = A.sensitivity_block(res, cm); R["review_policy"] = A.review_policy_block(res, cm)
    R["replication"] = replication(cfg, cm)
    R["config"] = cfg; R["cost_model"] = {"false_positive": cm.c_fp, "false_negative": cm.c_fn, "review": cm.c_review, "status": "illustrative assumption, not stakeholder validated"}
    import sklearn, scipy
    R["environment"] = {"python": platform.python_version(), "numpy": np.__version__, "scikit_learn": sklearn.__version__, "scipy": scipy.__version__, "code_sha256": code_hash(),
                        "generator": "verifybench/1.0", "runtime_seconds": round(time.time() - t0, 1), "quick_mode": quick}
    R = clean(R)
    (out / "metrics").mkdir(parents=True, exist_ok=True)
    (out / "metrics/results.json").write_text(json.dumps(R, indent=1))
    plots(R, out / "plots")
    from .results_md import render
    (ROOT / "research/results.md").write_text(render(R)); (out / "reports/results.md").write_text(render(R))
    (out / "reports/index.html").write_text(build_html(R, out / "plots"))
    print(f"done in {time.time() - t0:.0f}s -> {out}")
    return R


if __name__ == "__main__":
    main(quick="--quick" in sys.argv)
