"""Minimal, dependency-free DXF reader for the Swiss Dwellings drawings.

Reads the ENTITIES section and returns LWPOLYLINE / CIRCLE / ARC / TEXT / LINE
entities with their layer, points and text. (ezdxf works too; this avoids the
dependency and is all these files need.)
"""
from __future__ import annotations


def read_entities(path: str) -> list[dict]:
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = [l.strip() for l in f.read().splitlines()]
    pairs = list(zip(lines[0::2], lines[1::2]))  # (group code, value)

    # only look inside the ENTITIES section
    start = end = None
    for i, (c, v) in enumerate(pairs):
        if c == "2" and v == "ENTITIES" and start is None:
            start = i + 1
        elif start is not None and c == "0" and v == "ENDSEC":
            end = i
            break
    pairs = pairs[start:end] if start is not None else pairs

    wanted = {"LWPOLYLINE", "CIRCLE", "ARC", "TEXT", "MTEXT", "LINE"}
    ents, cur = [], None
    for c, v in pairs:
        if c == "0":
            cur = {"type": v, "layer": None, "pts": [], "text": None,
                   "r": None, "closed": False} if v in wanted else None
            if cur is not None:
                ents.append(cur)
            continue
        if cur is None:
            continue
        if c == "8":
            cur["layer"] = v
        elif c in ("10", "11"):
            cur["pts"].append([float(v), 0.0])
        elif c in ("20", "21") and cur["pts"]:
            cur["pts"][-1][1] = float(v)
        elif c == "40":
            cur["r"] = float(v)
        elif c == "1":
            cur["text"] = v
        elif c == "70" and cur["type"] == "LWPOLYLINE":
            cur["closed"] = bool(int(v) & 1)
    return ents
