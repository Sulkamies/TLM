"""Blueprint analysis contract (AGENTS.md §4.2, v1.1.0). Custodian: A0."""

from typing import Literal

from pydantic import BaseModel

from blueprint_qa.contracts.common import Confidence, InputFormat
from blueprint_qa.contracts.vocabulary import FixtureType, OpeningKind, RoomType, StoreyLevel

__all__ = [
    "BlueprintAnalysis",
    "Fixture",
    "FixtureType",  # re-exported; defined in vocabulary.py
    "Opening",
    "Room",
    "RoomType",  # re-exported; defined in vocabulary.py
    "Scale",
    "Storey",
    "StoreyLevel",  # re-exported; defined in vocabulary.py
    "TextAnnotation",
]


class Scale(BaseModel):
    pixels_per_meter: float | None  # None for METRIC space or unknown scale
    source: Literal["SCALE_BAR", "DIMENSION_TEXT", "KNOWN_OBJECT", "IFC_MODEL", "NONE"]
    confidence: Confidence


class Storey(BaseModel):
    id: str
    name: str | None
    elevation_m: float | None
    level: StoreyLevel | None = None  # A3 maps the plan's storey label / elevation; since v1.1.0


class Room(BaseModel):
    id: str
    storey_id: str | None
    room_type: RoomType
    label_text: str | None  # verbatim, original language (e.g. "MH 2", "Schlafzimmer")
    polygon: list[tuple[float, float]]
    area_m2: float | None
    area_source: Literal["COMPUTED", "LABEL_TEXT", "IFC_PROPERTY"] | None
    height_m: float | None
    source_ref: str | None  # IFC GlobalId, if any
    confidence: Confidence


class Opening(BaseModel):
    id: str
    storey_id: str | None
    kind: OpeningKind
    position: tuple[float, float]
    width_m: float | None
    connects: list[str]  # room ids; "EXTERIOR" allowed
    source_ref: str | None
    confidence: Confidence


class Fixture(BaseModel):  # since v1.1.0 (contract change 001)
    id: str  # "fixture_<n>"
    storey_id: str | None
    room_id: str | None  # containing room if determined
    fixture_type: FixtureType
    position: tuple[float, float]  # box centre, in coordinate_space
    source_ref: str | None
    confidence: Confidence


class TextAnnotation(BaseModel):
    text: str
    bbox: tuple[float, float, float, float]  # x_min, y_min, x_max, y_max
    confidence: Confidence


class BlueprintAnalysis(BaseModel):
    schema_version: str = "1.1.0"
    request_id: str
    source_format: InputFormat
    coordinate_space: Literal["PIXEL", "METRIC"]
    metric_available: bool  # True if real-world measures can be derived
    scale: Scale
    storeys: list[Storey]
    rooms: list[Room]
    openings: list[Opening]
    adjacency: list[tuple[str, str]]  # room-id pairs sharing a wall; sorted, unique
    texts: list[TextAnnotation]
    analyzer_version: str  # model/parser version, matches its model card
    warnings: list[str]
    fixtures: list[Fixture] = []  # since v1.1.0
