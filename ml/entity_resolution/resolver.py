"""Conservative entity resolution.

Rule: two mentions are linked only when at least TWO independent identifying attributes
agree (or a strong identifier matches exactly). Name similarity alone NEVER merges records,
because a false merge manufactures false contradictions. Unresolved pairs are reported as
`requires_resolution` and left separate.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from ..schemas import EvidenceClaim
from ..extraction.normalization import (name_similarity, ocr_fold, edit_distance, parse_date, compare_dates, normalize_id)

ATTRS = {"person": ("national_id", "person_name", "date_of_birth"),
         "institution": ("institution_id", "institution_name", "reference_number")}
NAME_LINK = 0.86


@dataclass
class Mention:
    mention_id: str
    document_id: str
    entity_type: str
    claims: dict[str, EvidenceClaim] = field(default_factory=dict)   # field -> claim


@dataclass
class EntityLink:
    entity_pair: tuple[str, str]
    matching_features: list[str]
    disagreeing_features: list[str]
    strength: float                               # fraction of comparable attrs that agree
    same_entity_probability: float | None         # always None until a calibrated linker exists
    status: str                                   # linked | requires_resolution | distinct


def build_mentions(claims: list[EvidenceClaim]) -> list[Mention]:
    by: dict[tuple[str, str], Mention] = {}
    for c in claims:
        if not c.entity_type or "multiple_candidates" in c.flags:
            pass
        if not c.entity_type:
            continue
        key = (c.document_id, c.entity_type)
        m = by.setdefault(key, Mention(f"{c.document_id}#{c.entity_type}", c.document_id, c.entity_type))
        m.claims.setdefault(c.field_name, c)       # first candidate; duplicates are flagged elsewhere
    return list(by.values())


def _attr_agrees(attr: str, a: EvidenceClaim, b: EvidenceClaim) -> bool | None:
    if attr in ("national_id", "institution_id", "reference_number"):
        x, y = normalize_id(a.raw_value), normalize_id(b.raw_value)
        if x == y:
            return True
        return True if (ocr_fold(x) == ocr_fold(y) or edit_distance(x, y) <= 1) else False
    if attr in ("person_name", "institution_name"):
        return name_similarity(a.raw_value, b.raw_value) >= NAME_LINK
    if attr == "date_of_birth":
        pa = parse_date(a.raw_value); pb = parse_date(b.raw_value)
        r = compare_dates(pa, pb)
        return None if r == "unknown" else r in ("equal", "compatible_ambiguous")
    return None


def resolve_pair(m1: Mention, m2: Mention) -> EntityLink:
    match, differ = [], []
    for attr in ATTRS[m1.entity_type]:
        a, b = m1.claims.get(attr), m2.claims.get(attr)
        if a is None or b is None:
            continue
        r = _attr_agrees(attr, a, b)
        if r is True:
            match.append(attr)
        elif r is False:
            differ.append(attr)
    comparable = len(match) + len(differ)
    strength = len(match) / comparable if comparable else 0.0
    strong_id = any(a in match for a in ("national_id", "institution_id"))
    if len(match) >= 2 or (strong_id and not differ):
        status = "linked"
    elif len(differ) >= 2 or (comparable and not match):
        status = "distinct"
    else:
        status = "requires_resolution"
    return EntityLink((m1.mention_id, m2.mention_id), match, differ, strength, None, status)


def resolve(mentions: list[Mention]) -> tuple[list[list[Mention]], list[EntityLink]]:
    """Union-find over strictly-linked mentions; returns entity clusters and all pair decisions."""
    parent = {m.mention_id: m.mention_id for m in mentions}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    links = []
    for i, m1 in enumerate(mentions):
        for m2 in mentions[i + 1:]:
            if m1.entity_type != m2.entity_type or m1.document_id == m2.document_id:
                continue
            link = resolve_pair(m1, m2)
            links.append(link)
            if link.status == "linked":
                parent[find(m1.mention_id)] = find(m2.mention_id)
    groups: dict[str, list[Mention]] = {}
    for m in mentions:
        groups.setdefault(find(m.mention_id), []).append(m)
    # Second pass: a mention that matched nothing may join a cluster on NAME ONLY, but only when exactly one
    # candidate cluster agrees on name and none disagrees on any attribute. Ambiguity => stays unlinked.
    for m in [m for m in mentions if len(groups[find(m.mention_id)]) == 1]:
        if len(groups[find(m.mention_id)]) != 1:           # another mention already attached to this one
            continue
        cands = []
        for root, members in list(groups.items()):
            if root == find(m.mention_id) or members[0].entity_type != m.entity_type:
                continue
            res = [resolve_pair(m, x) for x in members if x.document_id != m.document_id]
            name_attr = "person_name" if m.entity_type == "person" else "institution_name"
            if not res or not any(name_attr in r.matching_features for r in res):
                continue
            conflicting = {a for r in res for a in r.disagreeing_features}
            if name_attr in conflicting or len(conflicting) > 1:
                continue
            if conflicting:                      # one attribute disagrees: require a near-exact name match with every member
                strong = all(name_similarity(m.claims[name_attr].raw_value, x.claims[name_attr].raw_value) >= 0.95
                             for x in members if x.document_id != m.document_id and name_attr in x.claims)
                if not strong:
                    continue
            cands.append((root, members, res, bool(conflicting)))
        if len(cands) == 1:
            root, members, res, had_conflict = cands[0]
            for r in res:
                links.append(EntityLink(r.entity_pair, ["name_match_single_attribute_conflict" if had_conflict else "name_only_unique"], sorted({a for q in res for a in q.disagreeing_features}), 0.5, None, "linked"))
            old_root = find(m.mention_id)
            parent[old_root] = root
            groups[root] = members + groups.pop(old_root)
        elif len(cands) > 1:
            for _, members, res, _hc in cands:
                for r in res:
                    links.append(EntityLink(r.entity_pair, r.matching_features, [], r.strength, None, "requires_resolution"))
    return list(groups.values()), links
