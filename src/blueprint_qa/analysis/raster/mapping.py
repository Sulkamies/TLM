"""Selected detections -> ``BlueprintAnalysis`` 1.1.0 (spec §C, field by field).

Principle: counting the emitted elements reproduces A3's tuned counts exactly. Each detection
becomes at most one element, and nothing is emitted that the tuned rules would not count.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from blueprint_qa.analysis.label_tables import DetectorTable, LanguageTable
from blueprint_qa.analysis.raster.raw import Box, Point
from blueprint_qa.analysis.raster.rules import (
    Selection,
    Text,
    area,
    centre,
    inside,
)
from blueprint_qa.analysis.settings import AnalysisSettings
from blueprint_qa.contracts import (
    BlueprintAnalysis,
    Fixture,
    InputFormat,
    Opening,
    Room,
    RoomType,
    Scale,
    Storey,
    TextAnnotation,
)

# Warning codes (spec §C, A3-Q21; A0 addendum for the *_DETECTED coverage codes).
W_NO_FLOOR_BOX = "NO_FLOOR_BOX"
W_MULTIPLE_STOREYS = "MULTIPLE_STOREYS"
W_STOREY_FROM_BOX_CENTRE = "STOREY_FROM_BOX_CENTRE"
W_NO_STOREY_FOR = "NO_STOREY_FOR"
W_BOX_OUT_OF_BOUNDS = "BOX_OUT_OF_BOUNDS"
W_SAUNA_FROM_BENCHES = "SAUNA_FROM_BENCHES"
W_ROOMS_ARE_BOXES = "ROOMS_ARE_BOXES"
W_ROOM_TYPES_DETECTED = "ROOM_TYPES_DETECTED"
W_FIXTURE_TYPES_DETECTED = "FIXTURE_TYPES_DETECTED"
W_OPENING_KINDS_DETECTED = "OPENING_KINDS_DETECTED"
W_NO_ADJACENCY = "NO_ADJACENCY"
W_NO_OPENING_CONNECTIVITY = "NO_OPENING_CONNECTIVITY"
W_FIXTURE_ROOM_FROM_BOX_CENTRE = "FIXTURE_ROOM_FROM_BOX_CENTRE"


def _reading_key(box: Box) -> tuple[float, float]:
    return (box[1], box[0])


def _polygon(box: Box) -> list[tuple[float, float]]:
    """The 4 box corners, clockwise on screen (y down)."""
    x0, y0, x1, y1 = box
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


@dataclass
class _StoreyBox:
    storey: Storey
    box: Box | None  # None for the fallback storey (it covers the whole sheet)
    conf: float


class _Builder:
    def __init__(
        self,
        selection: Selection,
        texts: Sequence[Text],
        settings: AnalysisSettings,
        table: DetectorTable,
        lang: LanguageTable,
    ) -> None:
        self.sel = selection
        self.texts = sorted(
            (t for t in texts if t.conf >= settings.ocr.min_confidence),
            key=lambda t: _reading_key(t.bbox),
        )
        self.table = table
        self.lang = lang
        self.warnings: list[str] = []
        self.storeys: list[_StoreyBox] = []

    # ---------------------------------------------------------- storeys

    def _storey_name(self, box: Box | None) -> tuple[str | None, str | None]:
        """(verbatim storey text, its storey number) for the first matching text in ``box``."""
        regex = self.lang.storey_regex()
        hits: list[tuple[Text, re.Match[str]]] = []
        for t in self.texts:
            m = regex.search(t.text)
            if m and (box is None or inside(t.centre, box)):
                hits.append((t, m))
        if not hits or (box is None and len(hits) != 1):
            return None, None
        text, match = hits[0]
        return text.text, match.group(1)

    def build_storeys(self) -> list[Storey]:
        boxes = sorted(self.sel.storeys, key=lambda x: _reading_key(x.box))
        if not boxes:
            name, digit = self._storey_name(None)
            storey = self._storey(1, name, digit)
            self.storeys = [_StoreyBox(storey, None, 1.0)]
            self.warnings.append(W_NO_FLOOR_BOX)
        else:
            for n, item in enumerate(boxes, 1):
                name, digit = self._storey_name(item.box)
                self.storeys.append(_StoreyBox(self._storey(n, name, digit), item.box, item.conf))
            if len(boxes) > 1:
                self.warnings += [f"{W_MULTIPLE_STOREYS}:{len(boxes)}", W_STOREY_FROM_BOX_CENTRE]
        return [s.storey for s in self.storeys]

    def _storey(self, n: int, name: str | None, digit: str | None) -> Storey:
        level = self.lang.storey_levels.get(digit) if digit is not None else None
        return Storey(id=f"storey_{n}", name=name, elevation_m=None, level=level)

    def storey_of(self, element_id: str, box: Box) -> str | None:
        mid = centre(box)
        hits = [s for s in self.storeys if s.box is None or inside(mid, s.box)]
        if not hits:
            self.warnings.append(f"{W_NO_STOREY_FOR}:{element_id}")
            return None
        return max(hits, key=lambda s: s.conf).storey.id

    # ---------------------------------------------------------- rooms

    def _label(self, box: Box) -> str | None:
        words = [t.text for t in self.texts if inside(t.centre, box)]
        return " ".join(words) if words else None

    def build_rooms(self) -> list[Room]:
        entries: list[tuple[Box, RoomType, float, bool]] = [
            (item.box, rtype, item.conf, False) for item, rtype in self.sel.rooms
        ]
        entries += [(g.box, self.sel.sauna_type, g.conf, g.from_benches) for g in self.sel.saunas]
        entries.sort(key=lambda e: _reading_key(e[0]))
        rooms: list[Room] = []
        for n, (box, rtype, conf, from_benches) in enumerate(entries, 1):
            rid = f"room_{n}"
            if from_benches:
                self.warnings.append(f"{W_SAUNA_FROM_BENCHES}:{rid}")
            rooms.append(
                Room(
                    id=rid,
                    storey_id=self.storey_of(rid, box),
                    room_type=rtype,
                    label_text=self._label(box),
                    polygon=_polygon(box),
                    area_m2=None,
                    area_source=None,
                    height_m=None,
                    source_ref=None,
                    confidence=conf,
                )
            )
        return rooms

    # ---------------------------------------------------------- openings and fixtures

    def build_openings(self) -> list[Opening]:
        out: list[Opening] = []
        counters: dict[str, int] = {}
        for item, kind in sorted(self.sel.openings, key=lambda e: _reading_key(e[0].box)):
            prefix = kind.lower()
            counters[prefix] = counters.get(prefix, 0) + 1
            oid = f"{prefix}_{counters[prefix]}"
            out.append(
                Opening(
                    id=oid,
                    storey_id=self.storey_of(oid, item.box),
                    kind=kind,
                    position=centre(item.box),
                    width_m=None,
                    connects=[],
                    source_ref=None,
                    confidence=item.conf,
                )
            )
        return out

    def build_fixtures(self, rooms: Sequence[Room]) -> list[Fixture]:
        room_boxes: list[tuple[str, Box]] = [
            (r.id, (r.polygon[0][0], r.polygon[0][1], r.polygon[2][0], r.polygon[2][1]))
            for r in rooms
        ]
        out: list[Fixture] = []
        ordered = sorted(self.sel.fixtures, key=lambda e: _reading_key(e[0].box))
        for n, (item, ftype) in enumerate(ordered, 1):
            fid = f"fixture_{n}"
            mid: Point = centre(item.box)
            containing = [(rid, b) for rid, b in room_boxes if inside(mid, b)]
            room_id = min(containing, key=lambda rb: area(rb[1]))[0] if containing else None
            out.append(
                Fixture(
                    id=fid,
                    storey_id=self.storey_of(fid, item.box),
                    room_id=room_id,
                    fixture_type=ftype,
                    position=mid,
                    source_ref=None,
                    confidence=item.conf,
                )
            )
        return out

    def build_texts(self) -> list[TextAnnotation]:
        return [TextAnnotation(text=t.text, bbox=t.bbox, confidence=t.conf) for t in self.texts]


def build_analysis(
    *,
    request_id: str,
    source_format: InputFormat,
    analyzer_version: str,
    selection: Selection,
    texts: Sequence[Text],
    dropped: int,
    settings: AnalysisSettings,
    table: DetectorTable,
    lang: LanguageTable,
) -> BlueprintAnalysis:
    b = _Builder(selection, texts, settings, table, lang)
    if dropped:
        b.warnings.append(f"{W_BOX_OUT_OF_BOUNDS}:{dropped}")
    storeys = b.build_storeys()
    rooms = b.build_rooms()
    openings = b.build_openings()
    fixtures = b.build_fixtures(rooms)
    b.warnings += [
        W_ROOMS_ARE_BOXES,
        f"{W_ROOM_TYPES_DETECTED}:{','.join(table.room_types())}",
        f"{W_FIXTURE_TYPES_DETECTED}:{','.join(table.fixture_types())}",
        f"{W_OPENING_KINDS_DETECTED}:{','.join(table.opening_kinds())}",
        W_NO_ADJACENCY,
    ]
    if openings:
        b.warnings.append(W_NO_OPENING_CONNECTIVITY)
    if fixtures:
        b.warnings.append(W_FIXTURE_ROOM_FROM_BOX_CENTRE)
    return BlueprintAnalysis(
        request_id=request_id,
        source_format=source_format,
        coordinate_space="PIXEL",
        metric_available=False,
        scale=Scale(pixels_per_meter=None, source="NONE", confidence=0.0),
        storeys=storeys,
        rooms=rooms,
        openings=openings,
        adjacency=[],
        texts=b.build_texts(),
        analyzer_version=analyzer_version,
        warnings=b.warnings,
        fixtures=fixtures,
    )
