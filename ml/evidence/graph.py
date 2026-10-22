"""Typed evidence graph rebuilt from persisted claims (never held only in memory/LLM state)."""
from __future__ import annotations
from dataclasses import dataclass, field
from ..schemas import EDGE_TYPES, EvidenceClaim, EvidenceRegion


@dataclass
class EvidenceGraph:
    nodes: dict[str, dict] = field(default_factory=dict)
    edges: list[dict] = field(default_factory=list)

    def add_node(self, nid: str, ntype: str, **attrs):
        self.nodes.setdefault(nid, {"id": nid, "type": ntype, **attrs})

    def add_edge(self, src: str, dst: str, etype: str, **attrs):
        assert etype in EDGE_TYPES, etype
        e = {"source": src, "target": dst, "type": etype, **attrs}
        if e not in self.edges:
            self.edges.append(e)

    def to_json(self) -> dict:
        return {"nodes": list(self.nodes.values()), "edges": self.edges,
                "stats": {"nodes": len(self.nodes), "edges": len(self.edges),
                          "contradictions": sum(e["type"] == "CONTRADICTS" for e in self.edges)}}

    def to_networkx(self):
        import networkx as nx
        g = nx.MultiDiGraph()
        for n in self.nodes.values():
            g.add_node(n["id"], **{k: v for k, v in n.items() if k != "id"})
        for e in self.edges:
            g.add_edge(e["source"], e["target"], **{k: v for k, v in e.items() if k not in ("source", "target")})
        return g


def build_graph(documents, claims: list[EvidenceClaim], clusters, regions: dict[str, EvidenceRegion]) -> EvidenceGraph:
    g = EvidenceGraph()
    for d in documents:
        g.add_node(d.document_id, "Document", kind=d.kind, version=d.version, superseded=d.superseded)
        if d.supersedes:
            g.add_edge(d.document_id, d.supersedes, "SUPERSEDES")
    for c in claims:
        g.add_node(c.claim_id, "Claim", field=c.field_name, raw=c.raw_value, normalized=c.normalized_value,
                   page=c.source_page, ocr_confidence=c.ocr_confidence, flags=c.flags)
        g.add_edge(c.claim_id, c.document_id, "EXTRACTED_FROM", page=c.source_page)
        r = regions.get(c.claim_id)
        if r:
            g.add_node(r.evidence_id, "EvidenceRegion", page=r.page, bbox=r.bbox, excerpt=r.excerpt)
            g.add_edge(c.claim_id, r.evidence_id, "DERIVED_FROM")
    for i, cluster in enumerate(clusters):
        etype = cluster[0].entity_type
        eid = f"entity:{etype}:{i + 1}"
        g.add_node(eid, "Entity", entity_type=etype, mentions=len(cluster))
        for m in cluster:
            for c in m.claims.values():
                g.add_edge(c.claim_id, eid, "REFERS_TO")
    return g
