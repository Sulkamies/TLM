"""Builders for hand-made A4 inputs, shaped like A3's raster spec (A3-analysis-adapter.md,
"Verified mapping spec (phase 0)"): PIXEL space, no scale, boxes as polygons, warning codes."""

from __future__ import annotations

from typing import Any

from blueprint_qa.contracts import (
    Aggregation,
    BlueprintAnalysis,
    Comparison,
    EntityRef,
    Fixture,
    FixtureType,
    InputFormat,
    Intent,
    Opening,
    ParsedQuestion,
    Room,
    RoomType,
    Scale,
    Storey,
    StoreyLevel,
)

RID = "8f2d3c1e-5b4a-4c6d-9e7f-0a1b2c3d4e5f"

ROOM_TYPES_RASTER = "ROOM_TYPES_DETECTED:BALCONY,BATHROOM,BEDROOM,KITCHEN,SAUNA,TOILET"
FIXTURE_TYPES_RASTER = "FIXTURE_TYPES_DETECTED:BATHTUB,SAUNA_BENCH,SHOWER,SINK,TOILET"
OPENING_KINDS_RASTER = "OPENING_KINDS_DETECTED:DOOR,WINDOW"
RASTER_WARNINGS = [
    ROOM_TYPES_RASTER,
    FIXTURE_TYPES_RASTER,
    OPENING_KINDS_RASTER,
    "ROOMS_ARE_BOXES",
    "NO_ADJACENCY",
    "NO_OPENING_CONNECTIVITY",
]


def box(x0: float, y0: float, x1: float, y1: float) -> list[tuple[float, float]]:
    """Axis-aligned box, clockwise on screen (y down), as A3 emits it."""
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]


def room(
    n: int,
    room_type: RoomType,
    *,
    storey: str | None = "storey_1",
    polygon: list[tuple[float, float]] | None = None,
    area: float | None = None,
    height: float | None = None,
    label: str | None = None,
    conf: float = 0.9,
) -> Room:
    return Room(
        id=f"room_{n}",
        storey_id=storey,
        room_type=room_type,
        label_text=label,
        polygon=polygon if polygon is not None else box(0, 0, 10, 10),
        area_m2=area,
        area_source="LABEL_TEXT" if area is not None else None,
        height_m=height,
        source_ref=None,
        confidence=conf,
    )


def opening(
    n: int,
    kind: str,
    *,
    storey: str | None = "storey_1",
    position: tuple[float, float] = (5.0, 5.0),
    conf: float = 0.8,
) -> Opening:
    return Opening(
        id=f"{kind.lower()}_{n}",
        storey_id=storey,
        kind=kind,  # type: ignore[arg-type]
        position=position,
        width_m=None,
        connects=[],
        source_ref=None,
        confidence=conf,
    )


def fixture(
    n: int,
    fixture_type: FixtureType,
    *,
    storey: str | None = "storey_1",
    position: tuple[float, float] = (5.0, 5.0),
    conf: float = 0.7,
) -> Fixture:
    return Fixture(
        id=f"fixture_{n}",
        storey_id=storey,
        room_id=None,
        fixture_type=fixture_type,
        position=position,
        source_ref=None,
        confidence=conf,
    )


def storey(n: int, level: StoreyLevel | None = None, name: str | None = None) -> Storey:
    return Storey(id=f"storey_{n}", name=name, elevation_m=None, level=level)


def analysis(
    *,
    rooms: list[Room] | None = None,
    openings: list[Opening] | None = None,
    fixtures: list[Fixture] | None = None,
    storeys: list[Storey] | None = None,
    warnings: list[str] | None = None,
    metric: bool = False,
    space: str = "PIXEL",
    ppm: float | None = None,
    request_id: str = RID,
) -> BlueprintAnalysis:
    if metric and space == "METRIC":
        scale = Scale(pixels_per_meter=None, source="IFC_MODEL", confidence=1.0)
    elif metric:
        scale = Scale(pixels_per_meter=ppm, source="SCALE_BAR", confidence=0.9)
    else:
        scale = Scale(pixels_per_meter=None, source="NONE", confidence=0.0)
    return BlueprintAnalysis(
        request_id=request_id,
        source_format=InputFormat.IFC if space == "METRIC" else InputFormat.PNG,
        coordinate_space=space,  # type: ignore[arg-type]
        metric_available=metric,
        scale=scale,
        storeys=storeys if storeys is not None else [storey(1)],
        rooms=rooms or [],
        openings=openings or [],
        adjacency=[],
        texts=[],
        analyzer_version="test-analyzer",
        warnings=list(RASTER_WARNINGS) if warnings is None else warnings,
        fixtures=fixtures or [],
    )


def ref(category: str, **kwargs: Any) -> EntityRef:
    return EntityRef(category=category, **kwargs)  # type: ignore[arg-type]


def question(
    intent: Intent,
    targets: list[EntityRef],
    *,
    aggregation: Aggregation = Aggregation.SUM,
    language: str = "en",
    comparison: Comparison | None = None,
    requested_unit: str | None = None,
    confidence: float = 0.95,
    clarification: str | None = None,
    request_id: str = RID,
) -> ParsedQuestion:
    return ParsedQuestion(
        request_id=request_id,
        original_question="(test question)",
        language=language,
        intent=intent,
        aggregation=aggregation,
        targets=targets,
        comparison=comparison,
        requested_unit=requested_unit,  # type: ignore[arg-type]
        confidence=confidence,
        provider="mock",
        clarification_needed=clarification,
    )
