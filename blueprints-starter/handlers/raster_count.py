"""Counting rules for raster floor plans, shared by the app and eval/cubicasa_check.py.

Input: one cached analysis dict (vision/analyze.py output) + settings
{"thresholds": {...}, "strategies": {...}} tuned by eval/cubicasa_check.py --tune.
Every count function returns (value, evidence) so the app can highlight what was counted.
"""
from __future__ import annotations

import re

from handlers.raster import ROOM_CODES, _norm

DEFAULT_THR = {"window": 0.3, "door": 0.3, "toilet": 0.35, "sink": 0.35, "bathtub": 0.35, "shower": 0.35,
               "sauna_bench": 0.35, "room_kitchen": 0.35, "room_bedroom": 0.35, "room_bath": 0.35,
               "room_balcony": 0.35, "room_sauna": 0.35, "floor": 0.4}
# "<class>_iou": extra duplicate removal (1.0 = off). Tuned per class.

TEMPLATES = [  # (question type, English question pattern)
    ("windows", r"^How many windows"),
    ("floors", r"^How many floors"),
    ("toilets", r"^How many toilet bowls"),
    ("sinks", r"^How many sinks"),
    ("shower_tub", r"^How many showers and bathtubs"),
    ("doors", r"^How many doors"),
    ("saunas", r"^How many saunas"),
    ("kitchens", r"^How many kitchens"),
    ("bedrooms", r"^How many bedrooms"),
    ("wc_rooms", r"^How many separate WC rooms"),
    ("bathrooms", r"^How many bathrooms"),
    ("balconies", r"^How many balconies"),
]


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def det(d, cls, thr):
    """Detections of one class above its threshold, with optional extra duplicate removal."""
    xs = sorted((x for x in d["detections"] if x["cls"] == cls and x["conf"] >= thr.get(cls, 0.35)),
                key=lambda x: -x["conf"])
    lim = thr.get(cls + "_iou", 1.0)
    if lim >= 1.0:
        return xs
    keep = []
    for x in xs:
        if all(_iou(x["box"], k["box"]) < lim for k in keep):
            keep.append(x)
    return keep


def ocr_hits(d, category):
    pat = re.compile(rf"^({ROOM_CODES[category]})$")
    return [o for o in d["ocr"] if pat.match(_norm(o["text"]))]


def _center(box):
    return (box[0] + box[2]) / 2, (box[1] + box[3]) / 2


def _inside(pt, box):
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def clusters(boxes, grow=0.5):
    """Group boxes that touch after growing each by `grow` x its size (bench tiers -> one sauna)."""
    bb = []
    for b in boxes:
        x0, y0, x1, y1 = b["box"]
        gw, gh = (x1 - x0) * grow, (y1 - y0) * grow
        bb.append((x0 - gw, y0 - gh, x1 + gw, y1 + gh))
    parent = list(range(len(bb)))

    def f(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for i in range(len(bb)):
        for j in range(i + 1, len(bb)):
            a, b = bb[i], bb[j]
            if a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]:
                parent[f(i)] = f(j)
    groups = {}
    for i, b in enumerate(boxes):
        groups.setdefault(f(i), []).append(b)
    return list(groups.values())


def bath_rooms(d, thr):
    """Classify each detected bathroom-type box by the fixtures inside it.
    Returns (wet_rooms, wc_only_rooms): wet = contains shower/bathtub; wc_only = toilet, no shower/tub."""
    wet, wc_only = [], []
    showers = [_center(x["box"]) for c in ("shower", "bathtub") for x in det(d, c, thr)]
    toilets = [_center(x["box"]) for x in det(d, "toilet", thr)]
    for r in det(d, "room_bath", thr):
        if any(_inside(p, r["box"]) for p in showers):
            wet.append(r)
        elif any(_inside(p, r["box"]) for p in toilets):
            wc_only.append(r)
        else:
            wet.append(r)      # no fixtures recognised: treat as a washroom
    return wet, wc_only


def _boxes(xs):
    return [{"box": x["box"], "label": f"{x['cls']} {x['conf']:.2f}"} for x in xs]


def _polys(os_):
    return [{"poly": o["poly"], "label": o["text"]} for o in os_]


def _n(xs, ev):
    return len(xs), ev


# question type -> strategy name -> f(analysis, thresholds) -> (count, evidence)
STRATEGIES = {
    "windows": {"det": lambda d, t: _n(det(d, "window", t), _boxes(det(d, "window", t)))},
    "floors": {"det_min1": lambda d, t: (max(1, len(det(d, "floor", t))), _boxes(det(d, "floor", t)))},
    "toilets": {"det": lambda d, t: _n(det(d, "toilet", t), _boxes(det(d, "toilet", t)))},
    "sinks": {"det": lambda d, t: _n(det(d, "sink", t), _boxes(det(d, "sink", t)))},
    "shower_tub": {"det": lambda d, t: _n(det(d, "shower", t) + det(d, "bathtub", t),
                                          _boxes(det(d, "shower", t) + det(d, "bathtub", t)))},
    "doors": {"det": lambda d, t: _n(det(d, "door", t), _boxes(det(d, "door", t)))},
    "saunas": {
        "bench_clusters": lambda d, t: (len(clusters(det(d, "sauna_bench", t))), _boxes(det(d, "sauna_bench", t))),
        "room": lambda d, t: _n(det(d, "room_sauna", t), _boxes(det(d, "room_sauna", t))),
        "ocr": lambda d, t: _n(ocr_hits(d, "sauna"), _polys(ocr_hits(d, "sauna"))),
    },
    "kitchens": {"det": lambda d, t: _n(det(d, "room_kitchen", t), _boxes(det(d, "room_kitchen", t))),
                 "ocr": lambda d, t: _n(ocr_hits(d, "kitchen"), _polys(ocr_hits(d, "kitchen")))},
    "bedrooms": {"det": lambda d, t: _n(det(d, "room_bedroom", t), _boxes(det(d, "room_bedroom", t))),
                 "ocr": lambda d, t: _n(ocr_hits(d, "bedroom"), _polys(ocr_hits(d, "bedroom")))},
    "wc_rooms": {
        "ocr": lambda d, t: _n(ocr_hits(d, "wc"), _polys(ocr_hits(d, "wc"))),
        "bath_fixtures": lambda d, t: _n(bath_rooms(d, t)[1], _boxes(bath_rooms(d, t)[1])),
        "max_fixtures_ocr": lambda d, t: (max(len(bath_rooms(d, t)[1]), len(ocr_hits(d, "wc"))),
                                          _boxes(bath_rooms(d, t)[1]) + _polys(ocr_hits(d, "wc"))),
    },
    "bathrooms": {
        "det": lambda d, t: _n(det(d, "room_bath", t), _boxes(det(d, "room_bath", t))),
        "det_minus_wc": lambda d, t: (max(0, len(det(d, "room_bath", t)) - len(ocr_hits(d, "wc"))),
                                      _boxes(det(d, "room_bath", t))),
        "bath_fixtures": lambda d, t: _n(bath_rooms(d, t)[0], _boxes(bath_rooms(d, t)[0])),
        "ocr": lambda d, t: _n(ocr_hits(d, "bathroom"), _polys(ocr_hits(d, "bathroom"))),
    },
    "balconies": {"det": lambda d, t: _n(det(d, "room_balcony", t), _boxes(det(d, "room_balcony", t))),
                  "ocr": lambda d, t: _n(ocr_hits(d, "balcony"), _polys(ocr_hits(d, "balcony")))},
}

# classes whose thresholds matter for each question type (for tuning)
CLASSES_USED = {
    "windows": ["window"], "floors": ["floor"], "toilets": ["toilet"], "sinks": ["sink"],
    "shower_tub": ["shower", "bathtub"], "doors": ["door"], "saunas": ["sauna_bench", "room_sauna"],
    "kitchens": ["room_kitchen"], "bedrooms": ["room_bedroom"],
    "wc_rooms": ["room_bath", "toilet", "shower", "bathtub"],
    "bathrooms": ["room_bath", "toilet", "shower", "bathtub"], "balconies": ["room_balcony"],
}
DEFAULT_STRATEGY = {t: next(iter(s)) for t, s in STRATEGIES.items()}


def count(d, qtype, settings=None):
    """Answer one question type for one analysed image: (count, evidence)."""
    settings = settings or {}
    thr = {**DEFAULT_THR, **settings.get("thresholds", {})}
    strat = settings.get("strategies", {}).get(qtype, DEFAULT_STRATEGY[qtype])
    return STRATEGIES[qtype][strat](d, thr)
