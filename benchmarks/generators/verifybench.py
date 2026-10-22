"""ApprovalLens VerifyBench generator (synthetic, fictional data, fully seeded).

Every case records: truth values per document, entity identity per document, per-unit ground-truth label
and reason, transformation provenance, and document hashes. Splits are grouped by *identity family*
(same base person/institution never crosses splits). `test_ood` uses an unseen template for all documents.

LIMITATIONS (also stated in results): documents are generated *text with simulated OCR noise*, not
photographed scans; OCR confidences are simulated; results measure this generator's difficulty only.
"""
from __future__ import annotations
import hashlib, json, random
from datetime import date

GENERATOR_VERSION = "verifybench/1.0"
GIVEN = ["Rajesh", "Priya", "Anita", "Suresh", "Kavita", "Mohammed", "Lakshmi", "Arjun", "Meera", "Vikram", "Sunita", "Ramesh",
         "Divya", "Karthik", "Neha", "Imran", "Deepa", "Harish", "Pooja", "Sanjay", "Fatima", "Gopal", "Rekha", "Naveen"]
MIDDLE = ["Kumar", "Lal", "Devi", "Raj", "Prasad", "Anand", "Mohan", "Chand"]
SURN = ["Sharma", "Iyer", "Nair", "Reddy", "Khan", "Patel", "Singh", "Menon", "Gupta", "Srinivasan", "Verma", "Pillai", "Das", "Joshi", "Rao", "Bose"]
CITY = ["Pune", "Coimbatore", "Jaipur", "Nagpur", "Mysuru", "Kochi", "Indore", "Bhopal"]
STREET = ["MG", "Gandhi", "Nehru", "Temple", "Lake", "Station", "College", "Market"]
INST_A = ["Sunrise", "Greenfield", "Crescent", "Lotus", "Pinnacle", "Horizon", "Harmony", "Evergreen"]
INST_B = ["Institute of Technology", "College of Engineering", "Institute of Management", "Polytechnic College"]
TRANSLIT = [("Mohammed", "Muhammad"), ("Srinivasan", "Sreenivasan"), ("Lakshmi", "Laxmi"), ("Priya", "Priyaa"), ("Kavita", "Kavitha"), ("Reddy", "Reddi"), ("Sharma", "Sarma")]

TEMPLATES = {
 "T1": dict(fmt="%d/%m/%Y", labels=dict(person_name="Full Name", date_of_birth="Date of Birth", national_id="National ID", institution_name="Institution Name", institution_id="Institution ID", address="Address", reference_number="Reference Number", issue_date="Issue Date", expiry_date="Expiry Date", qualification_year="Year of Passing")),
 "T2": dict(fmt="%d %B %Y", labels=dict(person_name="Applicant Name", date_of_birth="DOB", national_id="ID Number", institution_name="Institution", institution_id="Institution Code", address="Registered Address", reference_number="Ref No", issue_date="Date of Issue", expiry_date="Valid Until", qualification_year="Passing Year")),
 "T3": dict(fmt="%m/%d/%Y", labels=dict(person_name="Name", date_of_birth="Birth Date", national_id="Identity No", institution_name="College Name", institution_id="College Code", address="Campus Address", reference_number="Certificate No", issue_date="Issued On", expiry_date="Valid Till", qualification_year="Graduation Year")),
 "T4": dict(fmt="%Y-%m-%d", labels=dict(person_name="Candidate Name", date_of_birth="Born On", national_id="ID No", institution_name="Name of Institution", institution_id="Institution ID", address="Address", reference_number="Approval Ref", issue_date="Issue Date", expiry_date="Expires On", qualification_year="Qualification Year")),
 # unseen layout: mostly unseen labels + Roman-numeral months the parser does not support
 "T5": dict(fmt="ROMAN", labels=dict(person_name="Name", date_of_birth="Birth Details", national_id="ID No", institution_name="Establishment", institution_id="Institution Code", address="Premises", reference_number="File Ref", issue_date="Commencement", expiry_date="Valid Till", qualification_year="Pass Year")),
}
SEEN_TEMPLATES = ["T1", "T2", "T3", "T4"]
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]
DOC_FIELDS = {
 "identity_document": ["person_name", "date_of_birth", "national_id"],
 "application_form": ["person_name", "date_of_birth", "national_id", "institution_name", "institution_id", "address"],
 "certificate": ["institution_name", "institution_id", "reference_number", "issue_date", "expiry_date", "address"],
 "qualification_certificate": ["person_name", "qualification_year"],
 "guarantor_declaration": ["person_name", "date_of_birth", "national_id"],
}
DATE_FIELDS = {"date_of_birth", "issue_date", "expiry_date"}
PERSON_F = {"person_name", "date_of_birth", "national_id", "qualification_year"}
SCENARIOS = {"clean": .17, "format_variation": .12, "ocr_noise": .14, "entity_trap": .09, "version_supersede": .08, "conflict_exact": .17,
             "conflict_temporal": .07, "conflict_noisy": .05, "conflict_intradoc": .04, "date_ambiguity": .06, "date_swap_conflict": .02, "missing_field": .03}
CONFUSE = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "6": "G"}
QUALITY = {"high": (0.01, 93), "medium": (0.07, 86), "low": (0.22, 74)}


def _pick(rng, xs): return xs[rng.randrange(len(xs))]


def _person(rng):
    return f"{_pick(rng, GIVEN)} {_pick(rng, MIDDLE)} {_pick(rng, SURN)}"


def _nid(rng): return rng.choice("ABCDEFGHJKMNPRTUVWXY") + rng.choice("ABCDEFGHJKMNPRTUVWXY") + "".join(str(rng.randrange(10)) for _ in range(8))


def _base_identity(rng):
    y = rng.randint(1985, 2003)
    dob = date(y, rng.randint(1, 12), rng.randint(1, 28))
    q = y + rng.randint(21, 27)
    issue = date(rng.randint(2018, 2024), rng.randint(1, 12), rng.randint(1, 28))
    exp = date(issue.year + rng.randint(3, 5), issue.month, issue.day)
    return {"person_name": _person(rng), "date_of_birth": dob.isoformat(), "national_id": _nid(rng), "qualification_year": min(q, 2026),
            "institution_name": f"{_pick(rng, INST_A)} {_pick(rng, INST_B)}", "institution_id": f"INST-{rng.randint(10000, 99999)}",
            "address": f"{rng.randint(1, 240)} {_pick(rng, STREET)} Road, {_pick(rng, CITY)}", "reference_number": f"REF/{rng.randint(2015, 2024)}/{rng.randint(1000, 9999)}",
            "issue_date": issue.isoformat(), "expiry_date": exp.isoformat()}


def _digits_change(rng, v):
    idx = [i for i, ch in enumerate(v) if ch.isdigit()]
    i = rng.choice(idx)
    if rng.random() < .35 and len(idx) > 1:                      # transposition
        j = rng.choice([k for k in idx if k != i and v[k] != v[i]] or [i])
        s = list(v); s[i], s[j] = s[j], s[i]
        if "".join(s) != v: return "".join(s)
    d = rng.choice([c for c in "0123456789" if c != v[i]])
    return v[:i] + d + v[i + 1:]


def _mutate(rng, field, v, base):
    if field == "date_of_birth":
        y, m, d = map(int, v.split("-"))
        return (date(y + rng.choice([-3, -2, -1, 1, 2]), m, d) if rng.random() < .55 else date(y, (m % 12) + 1, min(d + 1, 28))).isoformat()
    if field in ("national_id", "institution_id", "reference_number"): return _digits_change(rng, v)
    if field == "person_name": return _person(rng) if _person(rng) != v else v + " Jr"
    if field == "institution_name":
        n = f"{_pick(rng, INST_A)} {_pick(rng, INST_B)}"
        return n if n != v else n + " Annex"
    if field == "address": return f"{rng.randint(241, 480)} {_pick(rng, STREET)} Road, {_pick(rng, CITY)}"
    if field == "qualification_year": return v + rng.choice([-2, -1, 1])
    return v


def _fmt_date(iso, fmt):
    y, m, d = map(int, iso.split("-"))
    if fmt == "ROMAN": return f"{d}.{ROMAN[m - 1]}.{y}"
    return date(y, m, d).strftime(fmt)


def _name_variant(rng, v):
    t = v.split()
    kind = rng.choice(["translit", "initial", "case", "honorific", "drop_middle"])
    if kind == "translit":
        for a, b in TRANSLIT:
            if a in v: return v.replace(a, b)
        kind = "initial"
    if kind == "initial" and len(t) == 3: return f"{t[0]} {t[1][0]}. {t[2]}"
    if kind == "drop_middle" and len(t) == 3: return f"{t[0]} {t[2]}"
    if kind == "case": return v.upper()
    return "Mr. " + v


def _addr_variant(rng, v):
    return v.replace("Road", "Rd.").replace(",", "") if rng.random() < .7 else v.upper()


def _corrupt(rng, field, s):
    """Simulated OCR corruption; returns (new_string, changed)."""
    if field in ("national_id", "institution_id", "reference_number", "date_of_birth", "issue_date", "expiry_date", "qualification_year"):
        idx = [i for i, ch in enumerate(s) if ch in CONFUSE]
        if idx:
            i = rng.choice(idx); return s[:i] + CONFUSE[s[i]] + s[i + 1:], True
        return s, False
    swaps = [("rn", "m"), ("m", "rn"), ("l", "1"), ("a", "o"), ("e", "c")]
    rng.shuffle(swaps)
    for a, b in swaps:
        if a in s: return s.replace(a, b, 1), True
    return s, False


def _render(rng, doc_id, kind, tmpl, vals, quality, forced_corrupt=None, variants=True):
    T = TEMPLATES[tmpl]
    p_corrupt, mu = QUALITY[quality]
    lines = [{"text": f"REPUBLIC OF NOWHERE - {kind.replace('_', ' ').upper()}", "bbox": [60, 40, 520, 62], "conf": 96.0}]
    expected, transforms = {}, []
    order = list(vals.keys()); rng.shuffle(order)
    y = 100
    for f in order:
        v = vals[f]
        shown = _fmt_date(v, T["fmt"]) if f in DATE_FIELDS else str(v)
        clean_shown = shown
        if variants:
            if f in ("person_name",) and rng.random() < .2: shown = _name_variant(rng, shown); transforms.append(f"{f}:name_variant")
            if f == "address" and rng.random() < .2: shown = _addr_variant(rng, shown); transforms.append(f"{f}:address_variant")
        corrupted = False
        if f == forced_corrupt or rng.random() < p_corrupt:
            shown, corrupted = _corrupt(rng, f, shown)
            if corrupted: transforms.append(f"{f}:ocr_corruption")
        conf = rng.gauss(mu - 22, 12) if corrupted else rng.gauss(mu, 4)
        conf = round(max(25.0, min(99.0, conf)), 1)
        text = f"{T['labels'][f]}: {shown}"
        bbox = [60, y, 60 + 8 * len(text), y + 22]
        lines.append({"text": text, "bbox": bbox, "conf": conf})
        expected[f] = {"rendered": shown, "clean_rendered": clean_shown, "truth": v, "bbox": bbox, "corrupted": corrupted}
        y += 32
    for extra in rng.sample(["Place: " + _pick(rng, CITY), "Remarks: none", "Prepared by: Registry Office", "Seal: affixed"], 2):
        lines.append({"text": extra, "bbox": [60, y, 60 + 8 * len(extra), y + 22], "conf": 90.0}); y += 32
    text = "\n".join(l["text"] for l in lines)
    doc = {"document_id": doc_id, "kind": kind, "version": 1, "superseded": False, "supersedes": None,
           "pages": [{"page": 1, "text": text, "lines": lines}], "metadata": {"template": tmpl, "quality": quality, "sha256": hashlib.sha256(text.encode()).hexdigest()}}
    return doc, expected, transforms


def make_case(rng: random.Random, sid: str, family: str, base: dict, scenario: str, ood: bool = False) -> dict:
    tmpls = ["T5"] * 1 if ood else SEEN_TEMPLATES

    def tpl(): return "T5" if ood else _pick(rng, tmpls)

    def qual():
        r = rng.random()
        return "high" if r < .5 else "medium" if r < .85 else "low"
    kinds = ["identity_document", "application_form", "certificate", "qualification_certificate"]
    truth: dict[str, dict] = {}
    ent: dict[str, dict] = {}
    docs_meta = {}
    for i, k in enumerate(kinds):
        did = f"{sid}-d{i + 1}"
        vals = {f: base[f] for f in DOC_FIELDS[k]}
        if k == "qualification_certificate":
            if rng.random() < .7: vals["date_of_birth"] = base["date_of_birth"]
        truth[did] = vals
        ent[did] = {"person": "P1", "institution": "I1"}
        docs_meta[did] = {"kind": k, "template": tpl(), "quality": qual()}
    ids = list(truth)
    d_id, d_form, d_cert, d_qual = ids
    reason: dict[str, str] = {}
    forced: dict[tuple, bool] = {}
    superseded: dict[str, str] = {}
    extra_docs = []
    if scenario == "conflict_exact" or scenario == "conflict_noisy":
        cands = [(d, f) for d in (d_form, d_cert, d_qual, d_id) for f in truth[d] if f in ("date_of_birth", "national_id", "person_name", "institution_id", "institution_name", "address")]
        d, f = _pick(rng, cands)
        truth[d][f] = _mutate(rng, f, truth[d][f], base); reason[f"{'person' if f in PERSON_F else 'institution'}.{f}"] = "injected_value_conflict"
        if scenario == "conflict_noisy":
            docs_meta[d]["quality"] = "low"
            for d2 in ids:
                if rng.random() < .5: docs_meta[d2]["quality"] = "low"
    elif scenario == "date_swap_conflict":
        y, m, dd = map(int, base["date_of_birth"].split("-")); m = rng.randint(1, 12); dd = rng.randint(1, 12)
        while m == dd: dd = rng.randint(1, 12)
        a, b = date(y, m, dd), date(y, dd, m)
        truth[d_id]["date_of_birth"], truth[d_form]["date_of_birth"] = a.isoformat(), b.isoformat()
        docs_meta[d_id]["template"], docs_meta[d_form]["template"] = "T1", "T1"; reason["person.date_of_birth"] = "day_month_swap"
    elif scenario == "date_ambiguity":
        y = int(base["date_of_birth"][:4]); m = rng.randint(1, 12); dd = rng.randint(1, 12)
        while m == dd: dd = rng.randint(1, 12)
        for d in (d_id, d_form, d_qual):
            if "date_of_birth" in truth[d]: truth[d]["date_of_birth"] = date(y, m, dd).isoformat()
        docs_meta[d_id]["template"], docs_meta[d_form]["template"] = "T1", "T3"
    elif scenario == "conflict_temporal":
        y = int(base["date_of_birth"][:4]); truth[d_qual]["qualification_year"] = y + rng.randint(5, 12); reason["person.dob_vs_qualification"] = "implausible_age_at_qualification"
    elif scenario == "conflict_intradoc":
        iy = int(base["issue_date"][:4]); truth[d_cert]["expiry_date"] = f"{iy - rng.randint(1, 3)}{base['expiry_date'][4:]}"; reason["doc.date_order"] = "expiry_before_issue"
    elif scenario == "missing_field":
        d = _pick(rng, [d_form, d_cert]); f = _pick(rng, [x for x in truth[d] if x != "person_name"]); truth[d].pop(f)
    elif scenario == "ocr_noise":
        for d in ids:
            if rng.random() < .6: docs_meta[d]["quality"] = _pick(rng, ["medium", "low"])
        d = _pick(rng, ids); f = _pick(rng, [x for x in truth[d] if x not in ("person_name", "qualification_year", "address")] or list(truth[d])); forced[(d, f)] = True
    elif scenario == "entity_trap":
        did = f"{sid}-d5"; sib = base["person_name"].split()
        same_dob = rng.random() < .2
        p2 = {"person_name": f"{sib[0]} {sib[1]} {sib[2]}" if rng.random() < .5 else f"{sib[0]} {sib[2]}",
              "date_of_birth": base["date_of_birth"] if same_dob else date(rng.randint(1960, 1985), rng.randint(1, 12), rng.randint(1, 28)).isoformat(),
              "national_id": _nid(rng)}
        truth[did] = p2; ent[did] = {"person": "P2"}; docs_meta[did] = {"kind": "guarantor_declaration", "template": tpl(), "quality": qual()}
        reason["trap"] = "same_dob_hard_trap" if same_dob else "similar_name_different_person"
    elif scenario == "version_supersede":
        did = f"{sid}-d6"; v1 = dict(truth[d_cert]); f = _pick(rng, ["institution_id", "institution_name", "address", "reference_number"])
        old_bad = rng.random() < .7
        if old_bad:                          # old version wrong, corrected version supersedes -> NOT a contradiction
            v1[f] = _mutate(rng, f, v1[f], base); truth[did] = v1
            superseded[did] = d_cert
        else:                                # new version introduces a conflict with other documents -> IS a contradiction
            truth[d_cert][f] = _mutate(rng, f, truth[d_cert][f], base); truth[did] = v1
            superseded[did] = d_cert                              # did is old (consistent) and cert is new
            superseded = {did: d_cert}
        ent[did] = {"person": "P1", "institution": "I1"}; docs_meta[did] = {"kind": "certificate", "template": docs_meta[d_cert]["template"], "quality": qual()}
        if not old_bad: reason[f"institution.{f}"] = "new_version_conflicts"
    # --- render ---
    documents, expected, transforms = [], {}, {}
    order = list(truth)
    for did in order:
        m = docs_meta[did]
        fc = next((f for (d, f) in forced if d == did), None)
        doc, exp, tr = _render(rng, did, m["kind"], m["template"], truth[did], m["quality"], fc, variants=scenario != "date_ambiguity" or True)
        documents.append(doc); expected[did] = exp; transforms[did] = tr
    # supersession metadata: dict maps old_doc_id -> new_doc_id
    by_id = {d["document_id"]: d for d in documents}
    if scenario == "version_supersede":
        did = f"{sid}-d6"
        if old_bad:
            by_id[did]["superseded"] = True; by_id[did]["version"] = 1; by_id[d_cert]["supersedes"] = did; by_id[d_cert]["version"] = 2
        else:
            by_id[d_cert]["superseded"] = True; by_id[d_cert]["version"] = 1; by_id[did]["supersedes"] = d_cert; by_id[did]["version"] = 2
    units = compute_units(documents, truth, ent)
    for u in units:
        if units[u]["label"] and not units[u].get("reason"): units[u]["reason"] = reason.get(u, "truth_value_differs")
    return {"submission_id": sid, "family_id": family, "scenario": scenario, "ood": ood, "documents": documents, "truth": truth, "entities": ent,
            "units": units, "expected": expected, "transformations": transforms, "generator": GENERATOR_VERSION}


def compute_units(documents, truth, ent) -> dict:
    live = {d["document_id"] for d in documents if not d["superseded"]}
    groups: dict[tuple, list] = {}
    for did in truth:
        if did not in live: continue
        for f, v in truth[did].items():
            et = "person" if f in PERSON_F else "institution"
            key = ent[did].get(et)
            if key is None: continue
            groups.setdefault((et, key, f), []).append((did, v))
    units: dict[str, dict] = {}
    for (et, key, f), lst in groups.items():
        if len(lst) >= 2:
            u = f"{et}.{f}"
            lab = int(len({v for _, v in lst}) > 1)
            units[u] = {"label": max(lab, units.get(u, {}).get("label", 0)), "reason": units.get(u, {}).get("reason", "")}
    # cross-field temporal unit
    dobs = [(d, truth[d]["date_of_birth"]) for d in live if "date_of_birth" in truth[d] and ent[d].get("person") == "P1"]
    quals = [(d, truth[d]["qualification_year"]) for d in live if "qualification_year" in truth[d] and ent[d].get("person") == "P1"]
    if dobs and quals:
        bad = any(not (15 <= q - int(b[:4]) <= 70) for _, b in dobs for _, q in quals)
        units["person.dob_vs_qualification"] = {"label": int(bad), "reason": ""}
    both = [d for d in live if "issue_date" in truth[d] and "expiry_date" in truth[d]]
    if both:
        units["doc.date_order"] = {"label": int(any(truth[d]["expiry_date"] < truth[d]["issue_date"] for d in both)), "reason": ""}
    return units


def generate(n_submissions=3000, n_ood=600, seed=42, family_size=4):
    rng = random.Random(seed)
    names, weights = list(SCENARIOS), list(SCENARIOS.values())
    cases = []
    n_fam = n_submissions // family_size
    for fi in range(n_fam):
        frng = random.Random(rng.randrange(1 << 30)); base = _base_identity(frng)
        for k in range(family_size):
            sc = frng.choices(names, weights)[0]
            cases.append(make_case(frng, f"S{fi:04d}-{k}", f"F{fi:04d}", base, sc))
    # grouped split by identity family
    fams = [f"F{i:04d}" for i in range(n_fam)]; random.Random(seed + 1).shuffle(fams)
    a, b = int(.6 * n_fam), int(.8 * n_fam)
    where = {f: ("train" if i < a else "calibration" if i < b else "test") for i, f in enumerate(fams)}
    for c in cases: c["split"] = where[c["family_id"]]
    orng = random.Random(seed + 2)
    for fi in range(n_ood // family_size):
        frng = random.Random(orng.randrange(1 << 30)); base = _base_identity(frng)
        for k in range(family_size):
            cases.append(dict(make_case(frng, f"O{fi:04d}-{k}", f"OF{fi:04d}", base, frng.choices(names, weights)[0], ood=True), split="test_ood"))
    return cases


def dataset_hash(cases) -> str:
    h = hashlib.sha256()
    for c in cases: h.update(c["submission_id"].encode()); [h.update(d["metadata"]["sha256"].encode()) for d in c["documents"]]
    return h.hexdigest()
