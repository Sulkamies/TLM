"""A3's tuned rules as *element selection* (from ``handlers/raster_count.py`` at ``35597e2``).

The prototype counted per question type; here the same rules decide which detections become
elements, so that counting the emitted elements reproduces the tuned counts exactly (spec §B, §C):

- ``det(cls)``: detections of ``cls`` at or above the class threshold, by confidence, then greedy
  duplicate removal at IoU >= ``duplicate_iou[cls]`` (1.0 = off).
- storeys: every selected ``floor`` box (at least one storey; the mapping adds the fallback).
- bathroom boxes: wet if a selected shower/bathtub centre lies inside, else WC-only if a selected
  toilet centre lies inside, else (no fixtures recognised) wet.
- saunas: clusters of selected bench boxes; each box grown by ``sauna_cluster_grow`` x its size on
  every side, touching boxes joined. ``room_sauna`` boxes only give a cluster its polygon.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from blueprint_qa.analysis.label_tables import DetectorTable
from blueprint_qa.analysis.raster.raw import Box, Point, RawDetection, RawOutput, RawText
from blueprint_qa.analysis.settings import AnalysisSettings
from blueprint_qa.contracts import FixtureType, OpeningKind, RoomType


@dataclass(frozen=True)
class Item:
    """One detection that passed the bounds check (coordinates clamped to the image)."""

    cls: str
    conf: float
    box: Box


@dataclass(frozen=True)
class Text:
    """One OCR result that passed the bounds check."""

    text: str
    conf: float
    poly: tuple[Point, ...]

    @property
    def bbox(self) -> Box:
        xs = [p[0] for p in self.poly]
        ys = [p[1] for p in self.poly]
        return (min(xs), min(ys), max(xs), max(ys))

    @property
    def centre(self) -> Point:
        return centre(self.bbox)


@dataclass(frozen=True)
class SaunaGroup:
    benches: tuple[Item, ...]
    box: Box  # the room_sauna box containing the cluster centre, or the benches' union box
    from_benches: bool  # True if no room_sauna box contained the cluster centre

    @property
    def conf(self) -> float:
        return max(b.conf for b in self.benches)


@dataclass(frozen=True)
class Selection:
    storeys: tuple[Item, ...]
    rooms: tuple[tuple[Item, RoomType], ...]
    saunas: tuple[SaunaGroup, ...]
    sauna_type: RoomType
    openings: tuple[tuple[Item, OpeningKind], ...]
    fixtures: tuple[tuple[Item, FixtureType], ...]


# ------------------------------------------------------------------ geometry


def centre(box: Box) -> Point:
    return ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2)


def inside(pt: Point, box: Box) -> bool:
    return box[0] <= pt[0] <= box[2] and box[1] <= pt[1] <= box[3]


def area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])


def iou(a: Box, b: Box) -> float:
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    union = area(a) + area(b) - inter
    return inter / union if union > 0 else 0.0


def union_box(boxes: Iterable[Box]) -> Box:
    bs = list(boxes)
    return (
        min(b[0] for b in bs),
        min(b[1] for b in bs),
        max(b[2] for b in bs),
        max(b[3] for b in bs),
    )


# ------------------------------------------------------------ bounds (spec §C, before thresholds)


def _clamp(v: float, hi: float, tol: float) -> float | None:
    if v < -tol or v > hi + tol:
        return None
    return min(max(v, 0.0), hi)


def _clamp_point(p: Point, w: float, h: float, tol: float) -> Point | None:
    x, y = _clamp(p[0], w, tol), _clamp(p[1], h, tol)
    return None if x is None or y is None else (x, y)


def _clean_detection(d: RawDetection, w: float, h: float, tol: float) -> Item | None:
    a = _clamp_point((d.box[0], d.box[1]), w, h, tol)
    b = _clamp_point((d.box[2], d.box[3]), w, h, tol)
    if a is None or b is None or b[0] <= a[0] or b[1] <= a[1]:
        return None
    return Item(d.cls, d.conf, (a[0], a[1], b[0], b[1]))


def _clean_text(t: RawText, w: float, h: float, tol: float) -> Text | None:
    pts = [_clamp_point(p, w, h, tol) for p in t.poly]
    kept = [p for p in pts if p is not None]
    if len(kept) != len(pts):
        return None
    text = Text(t.text, t.conf, tuple(kept))
    x0, y0, x1, y1 = text.bbox
    return text if x1 > x0 and y1 > y0 else None


def check_bounds(raw: RawOutput, tolerance: float) -> tuple[list[Item], list[Text], int]:
    """Clamp coordinates up to ``tolerance`` px outside the image; drop the rest.

    Returns the kept detections, the kept OCR texts and how many were dropped.
    """
    w, h = float(raw.size[0]), float(raw.size[1])
    items = [_clean_detection(d, w, h, tolerance) for d in raw.detections]
    texts = [_clean_text(t, w, h, tolerance) for t in raw.ocr]
    kept_items = [i for i in items if i is not None]
    kept_texts = [t for t in texts if t is not None]
    dropped = len(items) - len(kept_items) + len(texts) - len(kept_texts)
    return kept_items, kept_texts, dropped


# ------------------------------------------------------------------ the tuned rules


def det(items: Sequence[Item], cls: str, settings: AnalysisSettings) -> list[Item]:
    """Detections of one class above its threshold, with the optional duplicate removal."""
    thr = settings.threshold(cls)
    xs = sorted((x for x in items if x.cls == cls and x.conf >= thr), key=lambda x: -x.conf)
    limit = settings.dup_iou(cls)
    if limit >= 1.0:
        return xs
    keep: list[Item] = []
    for x in xs:
        if all(iou(x.box, k.box) < limit for k in keep):
            keep.append(x)
    return keep


def clusters(boxes: Sequence[Item], grow: float) -> list[list[Item]]:
    """Group boxes that touch after growing each by ``grow`` x its size (bench tiers = 1 sauna)."""
    grown: list[Box] = []
    for b in boxes:
        x0, y0, x1, y1 = b.box
        gw, gh = (x1 - x0) * grow, (y1 - y0) * grow
        grown.append((x0 - gw, y0 - gh, x1 + gw, y1 + gh))
    parent = list(range(len(grown)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(grown)):
        for j in range(i + 1, len(grown)):
            p, q = grown[i], grown[j]
            if p[0] <= q[2] and q[0] <= p[2] and p[1] <= q[3] and q[1] <= p[3]:
                parent[find(i)] = find(j)
    groups: dict[int, list[Item]] = {}
    for i, b in enumerate(boxes):
        groups.setdefault(find(i), []).append(b)
    return list(groups.values())


def _sauna_group(benches: list[Item], rooms: Sequence[Item]) -> SaunaGroup:
    union = union_box(b.box for b in benches)
    mid = centre(union)
    containing = [r for r in rooms if inside(mid, r.box)]
    if containing:
        best = min(containing, key=lambda r: area(r.box))
        return SaunaGroup(tuple(benches), best.box, from_benches=False)
    return SaunaGroup(tuple(benches), union, from_benches=True)


def select(items: Sequence[Item], settings: AnalysisSettings, table: DetectorTable) -> Selection:
    """Apply the tuned rules: which detections become storeys, rooms, openings and fixtures."""
    fixtures = [
        (x, ftype) for cls, ftype in table.fixtures.items() for x in det(items, cls, settings)
    ]
    openings = [
        (x, kind) for cls, kind in table.openings.items() for x in det(items, cls, settings)
    ]

    rooms: list[tuple[Item, RoomType]] = [
        (x, rtype) for cls, rtype in table.rooms.items() for x in det(items, cls, settings)
    ]
    rule = table.bath_room
    wet_pts = [centre(x.box) for c in rule.wet_fixtures for x in det(items, c, settings)]
    wc_pts = [centre(x.box) for c in rule.wc_fixtures for x in det(items, c, settings)]
    for r in det(items, rule.cls, settings):
        if any(inside(p, r.box) for p in wet_pts):
            rooms.append((r, rule.wet))
        elif any(inside(p, r.box) for p in wc_pts):
            rooms.append((r, rule.wc_only))
        else:  # no fixtures recognised: treat as a washroom (tuned, A3-Q5)
            rooms.append((r, rule.wet))

    sauna = table.sauna
    sauna_rooms = det(items, sauna.room_class, settings)
    benches = det(items, sauna.bench_class, settings)
    saunas = [_sauna_group(g, sauna_rooms) for g in clusters(benches, settings.sauna_cluster_grow)]

    return Selection(
        storeys=tuple(det(items, table.storey_class, settings)),
        rooms=tuple(rooms),
        saunas=tuple(saunas),
        sauna_type=sauna.room_type,
        openings=tuple(openings),
        fixtures=tuple(fixtures),
    )
