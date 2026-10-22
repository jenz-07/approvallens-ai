"""Value normalization that never discards the original text.

Ambiguity is tracked, not guessed away: "03/04/2002" yields two candidate dates.
"""
from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date

MONTHS = {m: i + 1 for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


@dataclass
class DateParse:
    raw: str
    iso: str | None = None                       # primary reading
    candidates: list[str] = field(default_factory=list)
    ambiguous: bool = False
    valid: bool = False
    note: str = ""


def _mk(y, m, d):
    try:
        return date(int(y), int(m), int(d)).isoformat()
    except ValueError:
        return None


def parse_date(raw: str, dayfirst: bool = True) -> DateParse:
    s = (raw or "").strip()
    out = DateParse(raw=raw or "")
    if not s:
        out.note = "empty"
        return out
    low = s.lower().replace(",", " ")
    low = re.sub(r"\s+", " ", low)
    m = re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", low)
    if m:
        iso = _mk(*m.groups())
        return _done(out, [iso] if iso else [], "ymd")
    m = re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", low)
    if m:
        a, b, y = m.groups()
        dmy, mdy = _mk(y, b, a), _mk(y, a, b)
        cands = [c for c in ([dmy, mdy] if dayfirst else [mdy, dmy]) if c]
        cands = list(dict.fromkeys(cands))
        res = _done(out, cands, "numeric")
        res.ambiguous = len(cands) > 1
        if res.ambiguous:
            res.note = "ambiguous day/month order"
        return res
    m = re.fullmatch(r"(\d{1,2})(?:st|nd|rd|th)?[ \-]([a-z]{3,9})[ \-](\d{4})", low)
    if m and m.group(2)[:3] in MONTHS:
        iso = _mk(m.group(3), MONTHS[m.group(2)[:3]], m.group(1))
        return _done(out, [iso] if iso else [], "d-mon-y")
    m = re.fullmatch(r"([a-z]{3,9})[ \-](\d{1,2})(?:st|nd|rd|th)?[ \-](\d{4})", low)
    if m and m.group(1)[:3] in MONTHS:
        iso = _mk(m.group(3), MONTHS[m.group(1)[:3]], m.group(2))
        return _done(out, [iso] if iso else [], "mon-d-y")
    out.note = "unparseable date format"
    return out


def _done(out: DateParse, cands: list[str], fmt: str) -> DateParse:
    if cands:
        out.iso, out.candidates, out.valid, out.note = cands[0], cands, True, fmt
    else:
        out.note = "impossible calendar date"
    return out


def compare_dates(a: DateParse, b: DateParse) -> str:
    """equal | compatible_ambiguous | conflict | unknown"""
    if not (a.valid and b.valid):
        return "unknown"
    if a.iso == b.iso:
        return "equal"
    if set(a.candidates) & set(b.candidates):
        return "compatible_ambiguous"
    return "conflict"


# ---- identifiers -------------------------------------------------------
_FOLD = str.maketrans({"O": "0", "Q": "0", "D": "0", "I": "1", "L": "1", "S": "5", "B": "8", "Z": "2", "G": "6"})


def normalize_id(raw: str) -> str:
    return re.sub(r"[^A-Za-z0-9]", "", raw or "").upper()


def ocr_fold(raw: str) -> str:
    """Collapse characters OCR commonly confuses, for *detecting* possible OCR artifacts only."""
    return normalize_id(raw).translate(_FOLD)


def edit_distance(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ---- names -------------------------------------------------------------
HONORIFICS = {"mr", "mrs", "ms", "dr", "shri", "smt", "prof", "sri", "kumari", "miss"}
_PHON = [("mohammed", "muhammad"), ("mohamed", "muhammad"), ("mohd", "muhammad"), ("mohammad", "muhammad"),
         ("ee", "i"), ("oo", "u"), ("aa", "a"), ("ph", "f"), ("ck", "k"), ("ou", "u"), ("w", "v"), ("z", "s")]


def name_tokens(raw: str) -> list[str]:
    s = re.sub(r"[^a-z\s]", " ", (raw or "").lower())
    toks = [t for t in s.split() if t not in HONORIFICS]
    out = []
    for t in toks:
        for a, b in _PHON:
            t = t.replace(a, b)
        t = re.sub(r"(.)\1+", r"\1", t) if len(t) > 1 else t
        out.append(t)
    return out


def normalize_name(raw: str) -> str:
    return " ".join(name_tokens(raw))


def jaro_winkler(s1: str, s2: str) -> float:
    if s1 == s2:
        return 1.0
    l1, l2 = len(s1), len(s2)
    if not l1 or not l2:
        return 0.0
    rng = max(l1, l2) // 2 - 1
    m1, m2 = [False] * l1, [False] * l2
    matches = 0
    for i, c in enumerate(s1):
        for j in range(max(0, i - rng), min(l2, i + rng + 1)):
            if not m2[j] and s2[j] == c:
                m1[i] = m2[j] = True
                matches += 1
                break
    if not matches:
        return 0.0
    t, k = 0, 0
    for i in range(l1):
        if m1[i]:
            while not m2[k]:
                k += 1
            t += s1[i] != s2[k]
            k += 1
    jaro = (matches / l1 + matches / l2 + (matches - t / 2) / matches) / 3
    p = 0
    for a, b in zip(s1[:4], s2[:4]):
        if a != b:
            break
        p += 1
    return jaro + p * 0.1 * (1 - jaro)


def name_similarity(a: str, b: str) -> float:
    """Initial-aware, order-tolerant similarity in [0,1]. Similar names alone never imply the same person."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    short, long_ = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    scores = []
    for t in short:
        best = 0.0
        for u in long_:
            if len(t) == 1 or len(u) == 1:
                s = 0.9 if t[0] == u[0] else 0.0
            else:
                s = jaro_winkler(t, u)
            best = max(best, s)
        scores.append(best if best >= 0.85 else 0.0)      # unrelated tokens must not earn partial credit
    return (sum(scores) / len(scores)) * (0.9 + 0.1 * len(short) / len(long_))


# ---- addresses ---------------------------------------------------------
_ABBR = {"rd": "road", "st": "street", "ave": "avenue", "blk": "block", "no": "number", "nr": "near",
         "apt": "apartment", "ln": "lane", "dist": "district", "cir": "circle", "bldg": "building"}


def normalize_address(raw: str) -> str:
    toks = re.sub(r"[^a-z0-9\s]", " ", (raw or "").lower()).split()
    return " ".join(_ABBR.get(t, t) for t in toks)


def address_similarity(a: str, b: str) -> float:
    ta, tb = normalize_address(a).split(), normalize_address(b).split()
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    jacc = len(sa & sb) / len(sa | sb)
    nums_a, nums_b = {t for t in ta if t.isdigit()}, {t for t in tb if t.isdigit()}
    if nums_a != nums_b:                       # different house/plot numbers matter
        jacc *= 0.6
    return jacc


def parse_int(raw: str) -> int | None:
    m = re.search(r"\d+", (raw or "").replace(",", ""))
    return int(m.group()) if m else None
