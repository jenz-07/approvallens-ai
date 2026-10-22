"""Verification systems compared in the experiment.

A  : exact raw-string comparison of same-named fields across all documents (+ shared rules)
B  : independent extraction + normalization, pairwise across all documents, no entity graph (+ rules)
D  : evidence graph: conservative entity resolution, supersession, cross-field temporal checks,
     status-aware comparison that keeps ambiguity as 'inconclusive' (+ rules)
All three emit PairRecord candidates; the learned scorer / calibration / selective prediction
(system E) consume D's candidates and live in other modules.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from itertools import combinations
from ..schemas import DocumentRecord, EvidenceClaim, VerificationFinding
from ..extraction.deterministic import extract_claims, evidence_for
from ..entity_resolution.resolver import build_mentions, resolve
from ..evidence.graph import build_graph, EvidenceGraph
from .comparison import compare_claims, temporal_dob_qualification, finalize_features, PairComparison
from .requirements import EXPECTED_FIELDS
from .rules import run_rules


@dataclass
class Analysis:
    documents: list[DocumentRecord]
    claims: list[EvidenceClaim]
    regions: dict
    pairs: list[PairComparison] = field(default_factory=list)
    rule_findings: list[VerificationFinding] = field(default_factory=list)
    graph: EvidenceGraph | None = None
    links: list = field(default_factory=list)
    unresolved: set = field(default_factory=set)       # units whose evidence hinges on an unresolved entity link
    extraction_diag: dict = field(default_factory=dict)


def extract_all(docs: list[DocumentRecord]) -> tuple[list[EvidenceClaim], dict]:
    claims, diag = [], {}
    for d in docs:
        cs, info = extract_claims(d)
        claims += cs
        diag[d.document_id] = info
    return claims, diag


def _group(claims):
    g: dict[str, list[EvidenceClaim]] = {}
    for c in claims:
        g.setdefault(c.field_name, []).append(c)
    return g


def _cross_doc_pairs(cs: list[EvidenceClaim]):
    for a, b in combinations(cs, 2):
        if a.document_id != b.document_id:
            yield a, b


def system_a(docs) -> Analysis:
    claims, diag = extract_all(docs)
    an = Analysis(docs, claims, evidence_for(claims), extraction_diag=diag)
    for fld, cs in _group(claims).items():
        for a, b in _cross_doc_pairs(cs):
            p = compare_claims(a, b)
            p.status = "equal" if a.raw_value.strip() == b.raw_value.strip() else "conflict"   # exact comparison only
            an.pairs.append(finalize_features(p))
    an.rule_findings = run_rules(docs, claims)
    return an


def system_b(docs) -> Analysis:
    claims, diag = extract_all(docs)
    an = Analysis(docs, claims, evidence_for(claims), extraction_diag=diag)
    for fld, cs in _group(claims).items():
        for a, b in _cross_doc_pairs(cs):
            an.pairs.append(finalize_features(compare_claims(a, b)))      # status kept; flag rule applied in evaluation
    an.rule_findings = run_rules(docs, claims)
    return an


def system_d(docs, use_entities: bool = True, use_supersession: bool = True, use_temporal: bool = True) -> Analysis:
    """Evidence-graph system. Flags exist only so ablations A2/A5 can switch components off."""
    claims, diag = extract_all(docs)
    superseded = {d.document_id for d in docs if d.superseded} if use_supersession else set()
    live = [c for c in claims if c.document_id not in superseded]
    regions = evidence_for(claims)
    mentions = build_mentions(live)
    clusters, links = resolve(mentions)
    if not use_entities:                         # ablation: every same-type mention is assumed to be the same entity
        merged: dict[str, list] = {}
        for m in mentions:
            merged.setdefault(m.entity_type, []).append(m)
        clusters = list(merged.values())
    an = Analysis(docs, claims, regions, links=links, extraction_diag=diag)
    cluster_of = {m.mention_id: i for i, cl in enumerate(clusters) for m in cl}
    mention_by_id = {m.mention_id: m for m in mentions}
    for l in links:
        a_id, b_id = l.entity_pair
        if l.status == "requires_resolution" and cluster_of.get(a_id) != cluster_of.get(b_id):
            ma, mb = mention_by_id[a_id], mention_by_id[b_id]
            for fld in set(ma.claims) & set(mb.claims):
                an.unresolved.add(f"{ma.entity_type}.{fld}")
    an.graph = build_graph(docs, claims, clusters, regions)
    for cluster in clusters:
        etype = cluster[0].entity_type
        n_m = len(cluster)
        # link strength of the cluster = mean strength over its linked pairs (1.0 for a single mention)
        ids = {m.mention_id for m in cluster}
        strengths = [l.strength for l in links if l.status == "linked" and l.entity_pair[0] in ids and l.entity_pair[1] in ids]
        ls = sum(strengths) / len(strengths) if strengths else 1.0
        by_field: dict[str, list[EvidenceClaim]] = {}
        for m in cluster:
            for c in m.claims.values():
                by_field.setdefault(c.field_name, []).append(c)
        for fld, cs in by_field.items():
            cmps = [compare_claims(a, b) for a, b in _cross_doc_pairs(cs)]
            for p in cmps:
                sa = sum(1 for c in cs if c not in (p.a, p.b) and any(q.status in ("equal", "variant") for q in cmps if {q.a.claim_id, q.b.claim_id} == {p.a.claim_id, c.claim_id}))
                sb = sum(1 for c in cs if c not in (p.a, p.b) and any(q.status in ("equal", "variant") for q in cmps if {q.a.claim_id, q.b.claim_id} == {p.b.claim_id, c.claim_id}))
                p.link_strength, p.corroboration, p.n_group = ls, float(abs(sa - sb)), len(cs)
                an.pairs.append(finalize_features(p))
                et = "CONTRADICTS" if p.status == "conflict" else ("SUPPORTS" if p.status in ("equal", "variant") else None)
                if et:
                    an.graph.add_edge(p.a.claim_id, p.b.claim_id, et, unit=p.unit, status=p.status)
        if use_temporal and etype == "person" and "date_of_birth" in by_field and "qualification_year" in by_field:
            for d in by_field["date_of_birth"]:
                for q in by_field["qualification_year"]:
                    t = temporal_dob_qualification(d, q)
                    t.link_strength, t.n_group = ls, len(by_field["date_of_birth"]) + 1
                    an.pairs.append(finalize_features(t))
                    if t.status == "conflict":
                        an.graph.add_edge(d.claim_id, q.claim_id, "CONTRADICTS", unit=t.unit, status="temporal")
    an.rule_findings = run_rules(docs, claims)
    return an


def expected_pair_count(docs: list[DocumentRecord], claims: list[EvidenceClaim], unit: str) -> tuple[int, int]:
    """(documents expected to carry this unit's field, documents actually carrying a claim) among live docs."""
    fld = unit.split(".", 1)[1]
    live = [d for d in docs if not d.superseded]
    exp = sum(1 for d in live if fld in EXPECTED_FIELDS.get(d.kind, []))
    got = len({c.document_id for c in claims if c.field_name == fld and c.document_id in {d.document_id for d in live}})
    return exp, got
