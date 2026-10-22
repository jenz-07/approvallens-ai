"""EXPERIMENTAL visual/metadata anomaly signals. They never authenticate a document and never establish fraud."""
from __future__ import annotations
import re, io

EDITOR_HINTS = ("photoshop", "gimp", "canva", "pixlr", "paint", "illustrator", "inkscape")


def pdf_metadata_signals(data: bytes) -> list[dict]:
    out = []
    txt = data.decode("latin-1", "ignore")
    prod = re.findall(r"/(?:Producer|Creator)\s*\((.*?)\)", txt)
    for p in prod:
        if any(h in p.lower() for h in EDITOR_HINTS):
            out.append({"signal": "editing_software_in_metadata", "value": p, "note": "weak signal; legitimate workflows also use editors"})
    c, m = re.search(r"/CreationDate\s*\(D:(\d{14})", txt), re.search(r"/ModDate\s*\(D:(\d{14})", txt)
    if c and m and m.group(1) > c.group(1):
        out.append({"signal": "modified_after_creation", "value": f"{c.group(1)} -> {m.group(1)}", "note": "common for benign re-saves"})
    if txt.count("%%EOF") > 1:
        out.append({"signal": "incremental_updates", "value": txt.count("%%EOF"), "note": "file has appended revisions"})
    return out
