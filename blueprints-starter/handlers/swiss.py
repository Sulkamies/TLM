"""Swiss Dwellings handler: answers from the DXF that sits next to each PDF/PNG.

Everything is exact geometry: room areas are polygon areas, labels are text
entities, fixtures are recognised by their (very regular) drawing signature.
Each result carries the geometry so the viewer can highlight it.
"""
from __future__ import annotations

import os
import re
from collections import Counter, defaultdict

from .dxf_lite import read_entities

# Room names that are outdoor / not counted in "net indoor area" questions.
# Extend this list as you see more names in the questions file.
OUTDOOR = {"balkon", "balcone", "balcon", "loggia", "terrasse", "terrazza",
           "sitzplatz", "dachterrasse", "veranda", "gartensitzplatz"}
NOT_ROOM = {"schacht", "luftraum", "cavedio", "vide", "gaine", "shaft", "void"}
# Lifts/elevators: counted as rooms by label, but check whether the "indoor area"
# answers include them (see eval/swiss_check.py).
LIFT = {"lift", "ascensore", "ascenseur", "aufzug"}

ROOM_NO = re.compile(r"^[A-Z]{0,2}\d+\.\d+$")          # e.g. 0.05, 1.22
UNIT_LABEL = re.compile(r"^(Whg\.|App\.|Appartamento|Appartement|Wohnung)\s*(\w+)$", re.I)


def polygon_area(pts):
    n = len(pts)
    return abs(sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
                   for i in range(n))) / 2.0


def point_in_polygon(x, y, pts):
    inside = False
    j = len(pts) - 1
    for i in range(len(pts)):
        xi, yi = pts[i]
        xj, yj = pts[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi + 1e-12) + xi:
            inside = not inside
        j = i
    return inside


def bbox(e):
    if e["type"] == "CIRCLE":
        (x, y), r = e["pts"][0], e["r"]
        return [x - r, y - r, x + r, y + r]
    xs = [p[0] for p in e["pts"]]
    ys = [p[1] for p in e["pts"]]
    return [min(xs), min(ys), max(xs), max(ys)]


def _cluster(ents, tol=0.01):
    """Group entities whose bounding boxes touch -> one drawn symbol each."""
    boxes = [bbox(e) for e in ents]
    parent = list(range(len(ents)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(boxes)):
        a = boxes[i]
        for j in range(i + 1, len(boxes)):
            b = boxes[j]
            if a[0] <= b[2] + tol and b[0] <= a[2] + tol and a[1] <= b[3] + tol and b[1] <= a[3] + tol:
                parent[find(i)] = find(j)
    groups = defaultdict(list)
    for i in range(len(ents)):
        groups[find(i)].append(i)
    out = []
    for ids in groups.values():
        bs = [boxes[i] for i in ids]
        out.append({"members": [ents[i] for i in ids],
                    "bbox": [min(b[0] for b in bs), min(b[1] for b in bs),
                             max(b[2] for b in bs), max(b[3] for b in bs)]})
    return out


def classify_fixture(cluster):
    """Signatures observed in the generated drawings (verify on more files)."""
    sig = Counter()
    for e in cluster["members"]:
        if e["type"] == "CIRCLE":
            sig["circle_big" if e["r"] >= 0.06 else "circle_small"] += 1
        elif e["type"] == "LWPOLYLINE":
            sig[f"poly{len(e['pts'])}"] += 1
    if sig["poly69"]:
        return "bathtub"
    if sig["poly5"]:
        return "shower"
    if sig["poly48"] and sig["poly2"]:
        return "toilet"
    if sig["poly48"] and sig["circle_small"]:
        return "washbasin"
    if sig["circle_big"] >= 4:
        return "stove"            # kitchen counter with 4 hobs
    if sig["poly2"] >= 2:
        return "stairs"
    return "other"


class SwissPlan:
    def __init__(self, path: str):
        dxf = os.path.splitext(path)[0] + ".dxf"
        self.source = dxf
        E = read_entities(dxf)
        by = defaultdict(list)
        for e in E:
            by[e["layer"]].append(e)

        # --- rooms: outline polygons + the texts that fall inside them.
        # Some rooms are drawn as an outer outline with smaller rooms (lifts,
        # shafts) nested inside it: each text goes to the SMALLEST polygon that
        # contains it, and nested polygons are subtracted from their parent.
        texts = [e for e in by["ROOM_TEXT"] if e["text"]]
        polys = [p["pts"] for p in by["ROOM_OUTLINE"] if len(p["pts"]) >= 3]
        raw_area = [polygon_area(p) for p in polys]
        owner = {}
        for ti, t in enumerate(texts):
            cands = [i for i, p in enumerate(polys) if point_in_polygon(*t["pts"][0], p)]
            if cands:
                owner[ti] = min(cands, key=lambda i: raw_area[i])
        numbered = {o for ti, o in owner.items() if ROOM_NO.match(texts[ti]["text"])}
        self.rooms = []
        for i, pts in enumerate(polys):
            # only labelled rooms nested inside count as holes (e.g. a lift inside a corridor)
            holes = [j for j in numbered if j != i and raw_area[j] < raw_area[i]
                     and point_in_polygon(*_centroid(polys[j]), pts)]
            inside = [texts[ti] for ti, o in owner.items() if o == i]
            name = next((t["text"] for t in inside
                         if not ROOM_NO.match(t["text"]) and not UNIT_LABEL.match(t["text"])), None)
            number = next((t["text"] for t in inside if ROOM_NO.match(t["text"])), None)
            area = raw_area[i] - sum(raw_area[j] for j in holes)
            self.rooms.append({"name": name, "number": number, "area": area, "polygon": pts})

        # --- apartments: unit outlines + "Whg. A" style label inside them
        self.units = []
        for poly in by["UNIT_OUTLINE"]:
            pts = poly["pts"]
            label = next((UNIT_LABEL.match(t["text"]).group(2) for t in texts
                          if UNIT_LABEL.match(t["text"]) and point_in_polygon(*t["pts"][0], pts)), None)
            members = [r for r in self.rooms if r["number"] and
                       point_in_polygon(*_centroid(r["polygon"]), pts)]
            self.units.append({"label": label, "polygon": pts, "rooms": members})

        # --- openings: one 4-point polygon per window, one 5-point leaf per door
        self.windows = [{"bbox": bbox(e)} for e in by["WINDOW"]
                        if e["type"] == "LWPOLYLINE" and len(e["pts"]) == 4]
        self.doors = [{"bbox": bbox(e)} for e in by["DOOR"]
                      if e["type"] == "LWPOLYLINE" and len(e["pts"]) == 5]

        # --- fixtures
        self.fixtures = [{"kind": classify_fixture(c), "bbox": c["bbox"]}
                         for c in _cluster(by["FIXTURE"])]
        self.annotations = [e["text"] for e in by["ANNOTATION"]]

    # ---------- query helpers (each returns value + evidence) ----------
    def count_rooms_named(self, name):
        hits = [r for r in self.rooms if r["name"] and r["name"].casefold() == name.casefold()]
        return {"value": len(hits), "evidence": [_ev(r) for r in hits]}

    def area_of_room(self, number=None, name=None):
        hits = [r for r in self.rooms if (number is None or r["number"] == number)
                and (name is None or (r["name"] or "").casefold() == name.casefold())]
        return {"value": round(sum(r["area"] for r in hits), 2), "evidence": [_ev(r) for r in hits]}

    def total_area_named(self, name):
        return self.area_of_room(name=name)

    def total_indoor_area(self):
        hits = [r for r in self.rooms if r["number"] and _indoor(r["name"])]
        return {"value": round(sum(r["area"] for r in hits), 2), "evidence": [_ev(r) for r in hits]}

    def apartment_area(self, label):
        us = [u for u in self.units if (u["label"] or "").upper() == label.upper()]
        if not us:
            return {"value": None, "evidence": [], "note": f"no apartment labelled {label}"}
        hits = {id(r): r for u in us for r in u["rooms"] if _indoor(r["name"])}.values()
        return {"value": round(sum(r["area"] for r in hits), 2), "evidence": [_ev(r) for r in hits]}

    def count(self, kind):
        """kind: door | window | toilet | washbasin | bathtub | shower | apartment"""
        if kind == "door":
            items = self.doors
        elif kind == "window":
            items = self.windows
        elif kind == "apartment":
            # one item per distinct apartment label (a unit can be drawn as several outlines)
            seen = {}
            for u in self.units:
                if u["label"]:
                    seen.setdefault(u["label"], {"polygon": u["polygon"], "label": u["label"]})
            items = list(seen.values()) or [{"polygon": u["polygon"]} for u in self.units]
        else:
            items = [f for f in self.fixtures if f["kind"] == kind]
        return {"value": len(items), "evidence": items}

    def summary(self):
        return {
            "rooms": [{"name": r["name"], "number": r["number"], "area": round(r["area"], 2)} for r in self.rooms if r["number"]],
            "apartments": [{"label": u["label"], "rooms": [r["number"] for r in u["rooms"]]} for u in self.units],
            "counts": {k: self.count(k)["value"] for k in
                       ("door", "window", "toilet", "washbasin", "bathtub", "shower", "apartment")},
            "annotations": self.annotations,
        }


def _centroid(pts):
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _indoor(name):
    n = (name or "").casefold()
    return not any(o in n for o in OUTDOOR) and not any(o in n for o in NOT_ROOM)


def _ev(r):
    return {"label": f"{r['number']} {r['name']}", "area": round(r["area"], 2), "polygon": r["polygon"]}


def render_svg(plan: "SwissPlan") -> str:
    """Draw the DXF as SVG in DXF coordinates (y flipped by the group transform),
    so evidence polygons from the handler can be overlaid without any mapping."""
    E = read_entities(plan.source)
    xs = [p[0] for e in E for p in e["pts"]]
    ys = [p[1] for e in E for p in e["pts"]]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    pad = 0.5
    style = {"WALL": "stroke:#222;stroke-width:0.08;fill:none",
             "ROOM_OUTLINE": "stroke:#bbb;stroke-width:0.02;fill:none",
             "UNIT_OUTLINE": "stroke:#7a7;stroke-width:0.04;fill:none;stroke-dasharray:0.2 0.1"}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x0 - pad} {-y1 - pad} '
             f'{x1 - x0 + 2 * pad} {y1 - y0 + 2 * pad}"><g id="world" transform="scale(1,-1)">']
    for e in E:
        st = style.get(e["layer"], "stroke:#555;stroke-width:0.02;fill:none")
        if e["type"] == "LWPOLYLINE" and len(e["pts"]) >= 2:
            pts = " ".join(f"{x:.3f},{y:.3f}" for x, y in e["pts"])
            tag = "polygon" if e["closed"] else "polyline"
            parts.append(f'<{tag} points="{pts}" style="{st}"/>')
        elif e["type"] == "CIRCLE":
            (x, y), r = e["pts"][0], e["r"]
            parts.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="{r:.3f}" style="{st}"/>')
        elif e["type"] == "TEXT" and e["text"] and e["layer"] == "ROOM_TEXT":
            x, y = e["pts"][0]
            parts.append(f'<text x="{x:.3f}" y="{-y:.3f}" transform="scale(1,-1)" '
                         f'font-size="0.22" text-anchor="middle" fill="#333">{_esc(e["text"])}</text>')
    parts.append('</g></svg>')
    return "".join(parts)


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
