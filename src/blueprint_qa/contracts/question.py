"""Parsed question contract (AGENTS.md §4.2, v1.2.0). Custodian: A0."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from blueprint_qa.contracts.common import Confidence
from blueprint_qa.contracts.vocabulary import EntityCategory, FixtureType, RoomType


class Intent(str, Enum):
    COUNT = "COUNT"  # "how many bedrooms"
    AREA = "AREA"  # "area of the kitchen", "total floor area"
    LENGTH = "LENGTH"  # "how long/wide is the living room"
    PERIMETER = "PERIMETER"  # "perimeter of the house"
    HEIGHT = "HEIGHT"  # "ceiling height" (usually IFC only)
    VOLUME = "VOLUME"  # "volume of the garage" (usually IFC only)
    DISTANCE = "DISTANCE"  # "distance from kitchen to front door"
    RATIO = "RATIO"  # "what share of the area is bedrooms"
    EXISTENCE = "EXISTENCE"  # "is there a sauna" → 1.0 / 0.0
    COMPARISON = "COMPARISON"  # "is the kitchen bigger than 10 m²" → 1.0 / 0.0
    UNSUPPORTED = "UNSUPPORTED"  # cannot be answered with a number, e.g. "where is the kitchen"


class Aggregation(str, Enum):
    SINGLE = "SINGLE"
    SUM = "SUM"
    MAX = "MAX"
    MIN = "MIN"
    MEAN = "MEAN"


class Comparison(BaseModel):
    measure: Literal["COUNT", "AREA", "LENGTH", "PERIMETER", "HEIGHT", "VOLUME"]
    operator: Literal["GT", "GE", "LT", "LE", "EQ"]
    threshold: float | None  # in SI units (A2 converts); None = compare targets[0] vs targets[1]


class EntityRef(BaseModel):
    category: EntityCategory
    room_type: RoomType | None = None  # shared enum, see vocabulary.py
    label: str | None = None  # literal text, e.g. "Bedroom 2"
    ordinal: int | None = None  # "the second bedroom"
    storey: str | None = None  # holds a StoreyLevel value (vocabulary.py); str by decision 004
    fixture_type: FixtureType | None = None  # set iff category is FIXTURE; since v1.1.0


class ParsedQuestion(BaseModel):
    schema_version: str = "1.2.0"
    request_id: str
    original_question: str
    language: str  # detected BCP-47 code, e.g. "en", "de", "fi"
    intent: Intent
    aggregation: Aggregation
    targets: list[EntityRef]  # ≥1; exactly 2 for DISTANCE; numerator+denominator for RATIO
    comparison: Comparison | None  # required iff intent == COMPARISON
    requested_unit: Literal["m", "m2", "m3", "ft", "ft2", "ft3"] | None
    confidence: Confidence
    provider: str  # "llm:<model-id>:prompt@vN", "local:rules", "mock"
    clarification_needed: str | None
