"""Run all baselines/ablations on VerifyBench and write metrics, plots and tables.

Everything reported is computed here; nothing is typed in by hand.
"""
from __future__ import annotations
import hashlib, json, random, sys, time
from collections import defaultdict
from pathlib import Path
import numpy as np
import yaml
from sklearn.metrics import average_precision_score

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from benchmarks.generators.verifybench import generate, dataset_hash, GENERATOR_VERSION            # noqa: E402
from ml.schemas import DocumentRecord                                                              # noqa: E402
from ml.verification.engines import system_a, system_b, system_d, expected_pair_count              # noqa: E402
from ml.verification.learned import PairScorer                                                     # noqa: E402
from ml.verification.comparison import FEATURE_NAMES                                               # noqa: E402
from ml.extraction.deterministic import normalize_value, FIELD_KIND                                # noqa: E402
from ml.uncertainty.calibration import select_calibrator, brier, nll, ece, reliability             # noqa: E402
from ml.uncertainty.selective_prediction import CostModel, decide, risk_coverage                   # noqa: E402
from ml.review.prioritization import ReviewItem, entropy                                           # noqa: E402


def recs(c):
    return [DocumentRecord(d["document_id"], d["kind"], d["pages"], d["version"], d["superseded"], d["supersedes"], d["metadata"]) for d in c["documents"]]


def pair_label(case, p) -> int:
    ids = {d["document_id"]: d for d in case["documents"]}
    da, db = p["a_doc"], p["b_doc"]
    if ids[da]["superseded"] or ids[db]["superseded"]:
        return 0
    T, E = case["truth"], case["entities"]
    if p["kind"] == "temporal":
        dob = T[da].get("date_of_birth"); q = T[db].get("qualification_year")
        return int(dob is not None and q is not None and not (15 <= q - int(dob[:4]) <= 70))
    f = p["field"]
    et = "person" if f in ("person_name", "date_of_birth", "national_id", "qualification_year") else "institution"
    if E[da].get(et) != E[db].get(et) or E[da].get(et) is None:
        return 0
    return int(T[da].get(f) != T[db].get(f))


VARIANTS = {
    "A": lambda d: system_a(d), "B": lambda d: system_b(d), "D": lambda d: system_d(d),
    "D_noentity": lambda d: system_d(d, use_entities=False), "D_notemporal": lambda d: system_d(d, use_temporal=False),
}


def light(case, an, elapsed):
    pairs = [{"unit": p.unit, "status": p.status, "features": p.features, "kind": p.kind, "field": p.a.field_name, "a_doc": p.a.document_id,
              "b_doc": p.b.document_id, "a_claim": p.a.claim_id, "b_claim": p.b.claim_id, "min_ocr": min([c.ocr_confidence for c in (p.a, p.b) if c.ocr_confidence is not None] or [None]) if any(c.ocr_confidence is not None for c in (p.a, p.b)) else None,
              "a_raw": p.a.raw_value, "b_raw": p.b.raw_value} for p in an.pairs]
    for q in pairs:
        q["label"] = pair_label(case, q)
    rule_flag = any(f.unit == "doc.date_order" for f in an.rule_findings)
    units = {q["unit"] for q in pairs} | set(case["units"])
    exp = {u: expected_pair_count(an.documents, an.claims, u) for u in units if u not in ("doc.date_order", "person.dob_vs_qualification")}
    claims_by = defaultdict(set)
    for c in an.claims:
        claims_by[c.field_name].add(c.document_id)
    out = {"pairs": pairs, "rule_flag": rule_flag, "exp": exp, "elapsed": elapsed, "claims": [(c.document_id, c.field_name, c.raw_value, c.normalized_value, c.source_bbox, c.alternatives) for c in an.claims],
           "date_order_ok": all(any(cid == d["document_id"] and fld == "issue_date" for cid, fld, *_ in [(c.document_id, c.field_name) for c in an.claims]) for d in case["documents"] if d["kind"] == "certificate" and not d["superseded"]) if True else True}
    # evidence availability for the two rule/temporal units
    has = lambda f: {c.document_id for c in an.claims if c.field_name == f}
    cert_ids = {d["document_id"] for d in case["documents"] if d["kind"] == "certificate" and not d["superseded"]}
    out["date_order_missing"] = bool(cert_ids) and not (cert_ids & has("issue_date") & has("expiry_date")) and not rule_flag
    out["unresolved"] = sorted(getattr(an, "unresolved", set()))
    return out


def precompute(cases, names):
    L = {}
    for c in cases:
        r = recs(c); row = {}
        for n in names:
            t = time.perf_counter(); an = VARIANTS[n](r); row[n] = light(c, an, time.perf_counter() - t)
        L[c["submission_id"]] = row
    return L


def X_y(L, cases, variant):
    X, y = [], []
    for c in cases:
        for p in L[c["submission_id"]][variant]["pairs"]:
            X.append(p["features"]); y.append(p["label"])
    return np.array(X), np.array(y)


def unit_scores(case, lt, scorer):
    """max pair probability per unit (None when the unit has no candidate pair)."""
    by = defaultdict(list)
    for p in lt["pairs"]:
        by[p["unit"]].append(p)
    out = {}
    for u, ps in by.items():
        probs = scorer.predict_proba(np.array([p["features"] for p in ps])) if scorer else None
        out[u] = {"raw": float(probs.max()) if probs is not None else None, "pairs": ps,
                  "unknown": any(p["status"] == "unknown" for p in ps)}
    return out


def unit_universe(case, L):
    u = set(case["units"])
    for v in L[case["submission_id"]].values():
        u |= {p["unit"] for p in v["pairs"]}
        u |= {k for k, (e, g) in v["exp"].items() if e >= 2 and g < 2}
    return sorted(u)


def binary_decisions(case, lt, rule):
    """unit -> (flag bool) for A/B/D families using explicit rules only."""
    flags = defaultdict(bool)
    for p in lt["pairs"]:
        if rule == "exact" and p["status"] == "conflict": flags[p["unit"]] = True
        if rule == "normalized" and p["status"] not in ("equal", "variant", "unknown"): flags[p["unit"]] = True
        if rule == "graph" and p["status"] == "conflict": flags[p["unit"]] = True
    if lt["rule_flag"]: flags["doc.date_order"] = True
    return flags


def scored_decisions(case, lt, scorer, calibrator, cm, mode):
    """mode: raw05 | cal05 | policy_raw | policy_cal . Returns unit -> (action, p_raw, p_cal)."""
    us = unit_scores(case, lt, scorer)
    out = {}
    for u in unit_universe(case, {case["submission_id"]: {"v": lt}}):
        if u == "doc.date_order":
            if lt["rule_flag"]: out[u] = ("flag", 1.0, 1.0)
            elif lt["date_order_missing"] and mode.startswith("policy"): out[u] = ("review", None, None)
            else: out[u] = ("clear", 0.0, 0.0)
            continue
        s = us.get(u)
        e, g = lt["exp"].get(u, (0, 0))
        if s is None:
            missing = (u == "person.dob_vs_qualification" and u in case["units"]) or (e >= 2 and g < 2) or (u in lt["unresolved"])
            out[u] = ("review" if missing and mode.startswith("policy") else "clear", None, None); continue
        raw = s["raw"]; cal = float(calibrator.predict([raw])[0]) if calibrator else raw
        if mode == "raw05": act = "flag" if raw >= .5 else "clear"
        elif mode == "cal05": act = "flag" if cal >= .5 else "clear"
        else:
            p = cal if mode == "policy_cal" else raw
            act = "review" if s["unknown"] else decide(p, cm)
            if act == "clear" and u in lt["unresolved"]:       # an unresolved entity link means the comparison may be incomplete
                act = "review"
        out[u] = (act, raw, cal)
    return out


def counts(case, L, decisions):
    gt = case["units"]; c = dict(tp=0, fp=0, fn=0, tn=0, rp=0, rn=0)
    for u, act in decisions.items():
        y = gt.get(u, {}).get("label", 0)
        if act == "flag": c["tp" if y else "fp"] += 1
        elif act == "clear": c["fn" if y else "tn"] += 1
        else: c["rp" if y else "rn"] += 1
    return c


def metrics_from(sums, cm):
    tp, fp, fn, tn, rp, rn = (sums[k] for k in ("tp", "fp", "fn", "tn", "rp", "rn"))
    n = tp + fp + fn + tn + rp + rn
    P = tp + fn + rp
    prec = tp / (tp + fp) if tp + fp else float("nan")
    rec = tp / P if P else float("nan")
    f1 = 2 * tp / (2 * tp + fp + fn + rp) if (2 * tp + fp + fn + rp) else float("nan")
    f1_neg = 2 * (tn + rn) / (2 * (tn + rn) + fn + fp) if (2 * (tn + rn) + fn + fp) else float("nan")
    # human-in-the-loop view: reviewed units are resolved correctly by the reviewer (an assumption)
    tp_h, tn_h = tp + rp, tn + rn
    f1_h = 2 * tp_h / (2 * tp_h + fp + fn) if (2 * tp_h + fp + fn) else float("nan")
    return {"precision": prec, "recall": rec, "f1": f1, "macro_f1": (f1 + f1_neg) / 2, "fpr": fp / (fp + tn + rn) if (fp + tn + rn) else float("nan"),
            "review_rate": (rp + rn) / n, "coverage": 1 - (rp + rn) / n, "f1_if_reviews_resolved": f1_h,
            "missed_true_contradictions": fn, "false_alarms": fp,
            "expected_cost_per_unit": (fp * cm.c_fp + fn * cm.c_fn + (rp + rn) * cm.c_review) / n, "n_units": n, "n_positive": P,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn, "review_pos": rp, "review_neg": rn}


def boot(arrs: dict[str, np.ndarray], families: list[str], cm, B, seed, stat_fns):
    """Cluster bootstrap over identity families; paired because all systems use the same resamples."""
    rng = np.random.default_rng(seed)
    fam_idx = defaultdict(list)
    for i, f in enumerate(families): fam_idx[f].append(i)
    keys = list(fam_idx); res = defaultdict(list)
    fam_sums = {s: np.array([a[fam_idx[k]].sum(0) for k in keys]) for s, a in arrs.items()}
    for _ in range(B):
        pick = rng.integers(0, len(keys), len(keys))
        m = {s: dict(zip(("tp", "fp", "fn", "tn", "rp", "rn"), fs[pick].sum(0))) for s, fs in fam_sums.items()}
        for name, fn in stat_fns.items():
            res[name].append(fn(m, cm))
    return {k: [float(np.nanpercentile(v, 2.5)), float(np.nanpercentile(v, 97.5))] for k, v in res.items()}, res


COLS = ("tp", "fp", "fn", "tn", "rp", "rn")


def run_one(seed, cfg, cm, full=True, outdir=None):
    ev = cfg["experiment"]
    cases = generate(ev["n_submissions"], ev["n_ood_submissions"], seed, ev["family_size"])
    by = defaultdict(list)
    for c in cases: by[c["split"]].append(c)
    L = precompute(cases, list(VARIANTS))
    res = {"seed": seed, "dataset_hash": dataset_hash(cases), "split_sizes": {k: len(v) for k, v in by.items()},
           "positives": {k: sum(u["label"] for c in v for u in c["units"].values()) for k, v in by.items()},
           "units": {k: sum(len(c["units"]) for c in v) for k, v in by.items()}}
    # ---- fit scorers & calibrators per pair source (train/calibration splits only) ----
    fits = {}
    for name, src in {"E": "D", "E_nograph": "B", "E_notemporal": "D_notemporal", "E_noentity": "D_noentity"}.items():
        Xtr, ytr = X_y(L, by["train"], src)
        sc = PairScorer(seed).fit(Xtr, ytr)
        # calibration set: units with candidate pairs (not the rule unit), label = ground-truth unit label
        raws, ys = [], []
        for c in by["calibration"]:
            for u, s in unit_scores(c, L[c["submission_id"]][src], sc).items():
                if u == "doc.date_order": continue
                raws.append(s["raw"]); ys.append(c["units"].get(u, {}).get("label", 0))
        cal, info = select_calibrator(raws, ys, seed)
        fits[name] = (src, sc, cal, info)
    res["calibration_selection"] = {k: v[3] for k, v in fits.items()}
    res["scorer_coefficients"] = fits["E"][1].coefficients()
    # ---- evaluate on each eval split ----
    systems = {}
    def mk(split_cases):
        arrs, dec_store, unit_rows = {}, {}, {}
        def add(name, fn, src):
            a, rows = [], []
            for c in split_cases:
                d = fn(c, L[c["submission_id"]][src]); dec_store.setdefault(name, {})[c["submission_id"]] = d
                a.append([counts(c, L, {u: (v if isinstance(v, str) else v[0]) for u, v in d.items()})[k] for k in COLS])
            arrs[name] = np.array(a)
        add("A_exact_compare", lambda c, lt: {u: ("flag" if binary_decisions(c, lt, "exact")[u] else "clear") for u in unit_universe(c, L)}, "A")
        add("B_independent_normalized", lambda c, lt: {u: ("flag" if binary_decisions(c, lt, "normalized")[u] else "clear") for u in unit_universe(c, L)}, "B")
        add("D_evidence_graph", lambda c, lt: {u: ("flag" if binary_decisions(c, lt, "graph")[u] else "clear") for u in unit_universe(c, L)}, "D")
        src, sc, cal, _ = fits["E"]
        add("D+LR_raw_threshold", lambda c, lt: scored_decisions(c, lt, sc, None, cm, "raw05"), "D")
        add("E_graph_calibrated_selective", lambda c, lt: scored_decisions(c, lt, sc, cal, cm, "policy_cal"), "D")
        for nm, mode in (("A3_no_calibration", "policy_raw"), ("A4_no_selective_prediction", "cal05")):
            add(nm, lambda c, lt, mode=mode: scored_decisions(c, lt, sc, cal, cm, mode) if mode != "policy_raw" else scored_decisions(c, lt, sc, None, cm, "policy_raw"), "D")
        for nm, key, srcv in (("A1_no_evidence_graph", "E_nograph", "B"), ("A2_no_cross_field_temporal", "E_notemporal", "D_notemporal"), ("A5_no_entity_resolution", "E_noentity", "D_noentity")):
            _, s2, c2, _ = fits[key]
            add(nm, lambda c, lt, s2=s2, c2=c2: scored_decisions(c, lt, s2, c2, cm, "policy_cal"), srcv)
        return arrs, dec_store
    for split in ("test", "test_ood"):
        cs = by[split]
        arrs, dec = mk(cs)
        fam = [c["family_id"] for c in cs]
        stat = {"f1": lambda m, cm: metrics_from(m, cm)["f1"], "precision": lambda m, cm: metrics_from(m, cm)["precision"],
                "recall": lambda m, cm: metrics_from(m, cm)["recall"], "cost": lambda m, cm: metrics_from(m, cm)["expected_cost_per_unit"],
                "f1_if_reviews_resolved": lambda m, cm: metrics_from(m, cm)["f1_if_reviews_resolved"]}
        sysres = {}
        for name, a in arrs.items():
            tot = dict(zip(COLS, a.sum(0).tolist())); sysres[name] = metrics_from(tot, cm)
        B = ev["bootstrap_resamples"] if full else 200
        # per-system CIs
        for name, a in arrs.items():
            ci, _ = boot({name: a}, fam, cm, B, seed, {k: (lambda m, cm, k=k, name=name: stat[k]({"x": m[name]}["x"], cm)) for k in stat})
            sysres[name]["ci95"] = ci
        # paired differences
        pairs_ = [("D_evidence_graph", "B_independent_normalized"), ("D_evidence_graph", "A_exact_compare"), ("E_graph_calibrated_selective", "D_evidence_graph"),
                  ("E_graph_calibrated_selective", "D+LR_raw_threshold"), ("E_graph_calibrated_selective", "B_independent_normalized"),
                  ("E_graph_calibrated_selective", "A1_no_evidence_graph"), ("E_graph_calibrated_selective", "A3_no_calibration"),
                  ("E_graph_calibrated_selective", "A4_no_selective_prediction"), ("E_graph_calibrated_selective", "A5_no_entity_resolution"),
                  ("E_graph_calibrated_selective", "A2_no_cross_field_temporal"), ("D+LR_raw_threshold", "D_evidence_graph")]
        diffs = {}
        for x, y in pairs_:
            ci, raw = boot({x: arrs[x], y: arrs[y]}, fam, cm, B, seed + 7, {k: (lambda m, cm, k=k, x=x, y=y: stat[k](m[x], cm) - stat[k](m[y], cm)) for k in ("f1", "cost", "f1_if_reviews_resolved")})
            pt = {k: sysres[x][kk] - sysres[y][kk] for k, kk in (("f1", "f1"), ("cost", "expected_cost_per_unit"), ("f1_if_reviews_resolved", "f1_if_reviews_resolved"))}
            diffs[f"{x} - {y}"] = {k: {"diff": pt[k], "ci95": ci[k]} for k in pt}
        res[split] = {"systems": sysres, "paired_differences": diffs}
        if split == "test":
            res["_arrs_test"] = arrs; res["_dec_test"] = dec; res["_cases_test"] = cs
            res["_fits"] = fits; res["_L"] = L; res["_by"] = by
        else:
            res["_dec_ood"] = dec
    return res
