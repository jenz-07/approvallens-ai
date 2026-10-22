"""Secondary analyses (calibration, risk-coverage, extraction, entity resolution, latency, errors, review policy)."""
from __future__ import annotations
import random, time
from collections import Counter, defaultdict
import numpy as np
from .run import *                                           # noqa: F401,F403
from .run import (recs, unit_scores, unit_universe, scored_decisions, binary_decisions, counts, metrics_from, COLS)
from ml.verification.engines import extract_all
from ml.entity_resolution.resolver import build_mentions, resolve
from ml.extraction.normalization import normalize_id
from ml.uncertainty.calibration import brier, nll, ece, reliability
from ml.uncertainty.selective_prediction import risk_coverage, CostModel, decide
from ml.review.prioritization import ReviewItem, priority, entropy


def calibration_block(res, cm):
    cs, L, (src, sc, cal, info) = res["_cases_test"], res["_L"], res["_fits"]["E"]
    out = {}
    for split, cases in (("test", cs), ("test_ood", res["_by"]["test_ood"])):
        y, raw, lowq = [], [], []
        for c in cases:
            for u, s in unit_scores(c, L[c["submission_id"]][src], sc).items():
                if u == "doc.date_order": continue
                y.append(c["units"].get(u, {}).get("label", 0)); raw.append(s["raw"])
                mo = [p["min_ocr"] for p in s["pairs"] if p["min_ocr"] is not None]
                lowq.append(bool(mo) and min(mo) < 80)
        y, raw, lowq = np.array(y), np.array(raw), np.array(lowq)
        calp = cal.predict(raw)
        blk = {"n_units_with_candidates": int(len(y)), "positives": int(y.sum()),
               "raw": {"brier": brier(y, raw), "nll": nll(y, raw), "ece": ece(y, raw)},
               "calibrated": {"brier": brier(y, calp), "nll": nll(y, calp), "ece": ece(y, calp)},
               "reliability_raw": reliability(y, raw), "reliability_calibrated": reliability(y, calp)}
        for name, m in (("low_ocr_quality", lowq), ("high_ocr_quality", ~lowq)):
            if m.sum() >= 20:
                blk[name] = {"n": int(m.sum()), "positives": int(y[m].sum()), "ece_calibrated": ece(y[m], calp[m]), "brier_calibrated": brier(y[m], calp[m])}
        out[split] = blk
    out["method"] = info
    return out


def risk_coverage_block(res, cm):
    cs, L, (src, sc, cal, _) = res["_cases_test"], res["_L"], res["_fits"]["E"]
    y, p_raw, p_cal, conf_ocr, pred_d = [], [], [], [], []
    for c in cs:
        lt = L[c["submission_id"]][src]; us = unit_scores(c, lt, sc); dflags = binary_decisions(c, lt, "graph")
        for u in unit_universe(c, L):
            lab = c["units"].get(u, {}).get("label", 0)
            if u == "doc.date_order": r = 1.0 if lt["rule_flag"] else 0.0; pc = r
            elif u in us: r = us[u]["raw"]; pc = float(cal.predict([r])[0])
            else:
                r = pc = 0.5 if (u in lt["unresolved"] or lt["exp"].get(u, (0, 0))[0] >= 2 and lt["exp"].get(u, (0, 0))[1] < 2) else 0.0
            mo = [q["min_ocr"] for q in lt["pairs"] if q["unit"] == u and q["min_ocr"] is not None]
            y.append(lab); p_raw.append(r); p_cal.append(pc); conf_ocr.append(min(mo) / 100 if mo else 1.0); pred_d.append(int(dflags[u]))
    y = np.array(y)
    def curve(conf, pred):
        order = np.argsort(-np.asarray(conf), kind="stable"); err = (np.asarray(pred) != y)[order].astype(float)
        n = np.arange(1, len(y) + 1); cov, risk = n / len(y), np.cumsum(err) / n
        idx = np.unique(np.linspace(0, len(y) - 1, 160).astype(int))
        return {"coverage": cov[idx].tolist(), "risk": risk[idx].tolist(), "aurc": float(risk.mean()), "risk_at_full_coverage": float(risk[-1])}
    pr, pc = np.array(p_raw), np.array(p_cal)
    out = {"calibrated_probability": curve(np.maximum(pc, 1 - pc), pc >= .5), "raw_score": curve(np.maximum(pr, 1 - pr), pr >= .5),
           "ocr_confidence_only": curve(conf_ocr, pred_d), "always_predict_risk": float(((pc >= .5) != y).mean()), "n_units": int(len(y))}
    a = res["test"]["systems"]["E_graph_calibrated_selective"]
    out["E_operating_point"] = {"coverage": a["coverage"], "selective_risk": (a["fp"] + a["fn"]) / max(a["tp"] + a["fp"] + a["fn"] + a["tn"], 1)}
    return out


def extraction_block(res):
    L, by = res["_L"], res["_by"]; out = {}
    for split in ("test", "test_ood"):
        tot = Counter(); fid = Counter()
        for c in by[split]:
            claims = {(d, f): (raw, norm, bbox, alts) for d, f, raw, norm, bbox, alts in L[c["submission_id"]]["D"]["claims"]}
            for did, exp in c["expected"].items():
                for f, e in exp.items():
                    tot["expected"] += 1
                    got = claims.get((did, f))
                    if not got: continue
                    raw, norm, bbox, alts = got; tot["found"] += 1
                    tot["exact_text"] += raw == e["rendered"]
                    tot["grounded"] += bbox is not None and list(bbox) == list(e["bbox"])
                    kind = FIELD_KIND.get(f)
                    if kind in ("date", "id", "int"):
                        fid["n"] += 1
                        truth = e["truth"]
                        ok = (norm == truth) if kind == "date" else (norm == (normalize_id(truth) if kind == "id" else truth))
                        fid["primary_ok"] += ok
                        fid["ambiguous"] += bool(alts)
                        fid["truth_in_alternatives"] += bool(ok or (kind == "date" and truth in alts))
        out[split] = {"field_recall": tot["found"] / tot["expected"], "exact_text_match_of_found": tot["exact_text"] / max(tot["found"], 1),
                      "source_grounding_accuracy": tot["grounded"] / max(tot["found"], 1),
                      "value_fidelity_primary_reading": fid["primary_ok"] / max(fid["n"], 1), "ambiguous_value_rate": fid["ambiguous"] / max(fid["n"], 1),
                      "truth_in_candidate_readings": fid["truth_in_alternatives"] / max(fid["n"], 1), "fields_expected": tot["expected"],
                      "note": "OCR noise is simulated; CER/WER are not measured because no OCR engine is benchmarked here."}
    return out


def entity_block(res):
    out = {}
    for split in ("test", "test_ood"):
        tp = fp = fn = tn = 0; trap_merge = trap_total = 0
        for c in res["_by"][split]:
            r = recs(c); claims, _ = extract_all(r)
            live = [x for x in claims if x.document_id not in {d.document_id for d in r if d.superseded}]
            ms = build_mentions(live); clusters, _ = resolve(ms)
            cid = {m.mention_id: i for i, cl in enumerate(clusters) for m in cl}
            for i, a in enumerate(ms):
                for b in ms[i + 1:]:
                    if a.entity_type != b.entity_type or a.document_id == b.document_id: continue
                    same_truth = c["entities"][a.document_id].get(a.entity_type) == c["entities"][b.document_id].get(b.entity_type)
                    same_pred = cid[a.mention_id] == cid[b.mention_id]
                    tp += same_truth and same_pred; fp += (not same_truth) and same_pred; fn += same_truth and not same_pred; tn += (not same_truth) and (not same_pred)
                    if not same_truth: trap_total += 1; trap_merge += same_pred
        out[split] = {"pairwise_precision": tp / max(tp + fp, 1), "pairwise_recall": tp / max(tp + fn, 1), "false_merge_rate": fp / max(fp + tn, 1),
                      "false_split_rate": fn / max(fn + tp, 1), "pairs": tp + fp + fn + tn, "different_entity_pairs": trap_total, "false_merges": int(fp),
                      "note": "same_entity_probability is not emitted: no calibrated linker exists."}
    return out


def latency_block(res, cm):
    L = res["_L"]; cs = res["_cases_test"]; out = {}
    for v in ("A", "B", "D"):
        ms = np.array([L[c["submission_id"]][v]["elapsed"] * 1000 for c in cs])
        out[v] = {"median_ms": float(np.median(ms)), "p95_ms": float(np.percentile(ms, 95))}
    src, sc, cal, _ = res["_fits"]["E"]
    ms = []
    for c in cs[:300]:
        t = time.perf_counter(); scored_decisions(c, L[c["submission_id"]]["D"], sc, cal, cm, "policy_cal"); ms.append((time.perf_counter() - t) * 1000)
    out["E_scoring_calibration_decision"] = {"median_ms": float(np.median(ms)), "p95_ms": float(np.percentile(ms, 95))}
    out["note"] = "Single-process CPU timings on generated text (no OCR/PDF rendering); not end-to-end production latency."
    return out


def error_analysis(res):
    out = {}
    for name in ("D_evidence_graph", "E_graph_calibrated_selective", "B_independent_normalized"):
        dec = res["_dec_test"][name]; fpc, fnc = Counter(), Counter(); ex_fp, ex_fn = [], []
        for c in res["_cases_test"]:
            lt = res["_L"][c["submission_id"]]["D" if name != "B_independent_normalized" else "B"]
            for u, a in dec[c["submission_id"]].items():
                a = a if isinstance(a, str) else a[0]
                y = c["units"].get(u, {}).get("label", 0)
                if a == "flag" and not y:
                    fpc[c["scenario"]] += 1
                    if len(ex_fp) < 8: ex_fp.append({"submission": c["submission_id"], "scenario": c["scenario"], "unit": u})
                if a == "clear" and y:
                    fnc[(c["scenario"], c["units"][u]["reason"])] += 1
                    pr = [(p["a_raw"], p["b_raw"], p["status"]) for p in lt["pairs"] if p["unit"] == u][:2]
                    if len(ex_fn) < 8: ex_fn.append({"submission": c["submission_id"], "scenario": c["scenario"], "unit": u, "reason": c["units"][u]["reason"], "pairs": pr})
        out[name] = {"false_positives_by_scenario": dict(fpc), "false_negatives_by_scenario_reason": {f"{k[0]}|{k[1]}": v for k, v in fnc.items()}, "examples_fp": ex_fp, "examples_fn": ex_fn}
    return out


def sensitivity_block(res, cm0):
    src, sc, cal, _ = res["_fits"]["E"]; cs, L = res["_cases_test"], res["_L"]; rows = []
    base = {}
    for split, cases in (("test", cs), ("test_ood", res["_by"]["test_ood"])):
        for c_fn in (2.0, 5.0, 10.0):
            for c_rev in (0.1, 0.2, 0.4, 0.8, 1.2):
                cm = CostModel(1.0, c_fn, c_rev); tot = Counter(); totD = Counter(); totLR = Counter()
                for c in cases:
                    lt = L[c["submission_id"]]["D"]
                    for t, d in ((tot, scored_decisions(c, lt, sc, cal, cm, "policy_cal")), (totLR, scored_decisions(c, lt, sc, None, cm, "raw05"))):
                        for k, v in counts(c, L, {u: x[0] for u, x in d.items()}).items(): t[k] += v
                    dd = {u: ("flag" if binary_decisions(c, lt, "graph")[u] else "clear") for u in unit_universe(c, L)}
                    for k, v in counts(c, L, dd).items(): totD[k] += v
                e, lr, d_ = metrics_from(dict(tot), cm), metrics_from(dict(totLR), cm), metrics_from(dict(totD), cm)
                rows.append({"split": split, "c_fn": c_fn, "c_review": c_rev, "cost_E": e["expected_cost_per_unit"], "cost_D+LR": lr["expected_cost_per_unit"], "cost_D": d_["expected_cost_per_unit"],
                             "E_better_than_best_baseline": e["expected_cost_per_unit"] < min(lr["expected_cost_per_unit"], d_["expected_cost_per_unit"])})
    return rows


def review_policy_block(res, cm, seed=0):
    """Simulate a reviewer working through E's review queue; compare ordering policies."""
    src, sc, cal, _ = res["_fits"]["E"]; L, cs = res["_L"], res["_cases_test"]
    cal_units = defaultdict(list)
    items = []
    miss_rate = np.mean([c["units"].get(u, {}).get("label", 0) for c in res["_by"]["calibration"] for u in c["units"]])
    for c in cs:
        lt = L[c["submission_id"]][src]; us = unit_scores(c, lt, sc)
        for u, act in res["_dec_test"]["E_graph_calibrated_selective"][c["submission_id"]].items():
            act = act if isinstance(act, str) else act[0]
            if act != "review": continue
            s = us.get(u); p = float(cal.predict([s["raw"]])[0]) if s else float(miss_rate)
            mo = [q["min_ocr"] for q in lt["pairs"] if q["unit"] == u and q["min_ocr"] is not None]
            cost = 2.0 if (s is None or (mo and min(mo) < 78)) else 1.0           # low-quality / missing evidence costs more reviewer time
            items.append((ReviewItem(f"{c['submission_id']}:{u}", u, p, cost), c["units"].get(u, {}).get("label", 0)))
    def curve(order):
        t = f = 0; pts = [(0.0, 0)]
        for it, y in order:
            t += it.review_cost; f += y; pts.append((t, f))
        return pts
    ig = sorted(items, key=lambda t: -priority(t[0])); us_ = sorted(items, key=lambda t: abs(t[0].probability - .5)); orc = sorted(items, key=lambda t: (-t[1], t[0].review_cost))
    rnd = []
    for k in range(30):
        o = items[:]; random.Random(seed + k).shuffle(o); rnd.append(curve(o))
    total_cost = sum(i.review_cost for i, _ in items)
    grid = np.linspace(0, total_cost, 40)
    def at(pts, g):
        xs, ys = zip(*pts); return [float(np.interp(v, xs, ys)) for v in g]
    return {"queue_items": len(items), "positives_in_queue": int(sum(y for _, y in items)), "total_review_minutes": total_cost,
            "budget_grid": grid.tolist(), "found_by_ig_per_cost": at(curve(ig), grid), "found_by_uncertainty_sampling": at(curve(us_), grid),
            "found_by_random_mean": np.mean([at(c, grid) for c in rnd], 0).tolist(), "found_by_oracle": at(curve(orc), grid),
            "note": "Review costs are assumed (1.0 normal, 2.0 low-OCR/missing evidence). Queue probabilities for missing-evidence items use the calibration-split base rate."}
