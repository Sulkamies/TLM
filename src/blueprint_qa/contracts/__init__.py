"""Inter-component data contracts, v1.1.0 (AGENTS.md §4). Custodian: A0.

These Pydantic models are the only way data crosses a component boundary (R3.2).
The JSON Schemas in ``schema/`` are generated from them by ``generate_schema.py``;
never edit the JSON by hand.
"""

from blueprint_qa.contracts.analysis import (
    BlueprintAnalysis,
    Fixture,
    Opening,
    Room,
    Scale,
    Storey,
    TextAnnotation,
)
from blueprint_qa.contracts.answer import Answer, AnswerStatus
from blueprint_qa.contracts.common import Confidence, ErrorEnvelope, InputFormat, Stage
from blueprint_qa.contracts.question import (
    Aggregation,
    Comparison,
    EntityRef,
    Intent,
    ParsedQuestion,
)
from blueprint_qa.contracts.request import PipelineRequest
from blueprint_qa.contracts.validation import PlanImage, ValidationReason, ValidationResult
from blueprint_qa.contracts.vocabulary import (
    DESCRIPTIONS,
    VOCABULARIES,
    EntityCategory,
    FixtureType,
    OpeningKind,
    RoomType,
    StoreyLevel,
)

CONTRACT_VERSION = "1.1.0"

__all__ = [
    "CONTRACT_VERSION",
    "DESCRIPTIONS",
    "VOCABULARIES",
    "Aggregation",
    "Answer",
    "AnswerStatus",
    "BlueprintAnalysis",
    "Comparison",
    "Confidence",
    "EntityCategory",
    "EntityRef",
    "ErrorEnvelope",
    "Fixture",
    "FixtureType",
    "InputFormat",
    "Intent",
    "Opening",
    "OpeningKind",
    "ParsedQuestion",
    "PipelineRequest",
    "PlanImage",
    "Room",
    "RoomType",
    "Scale",
    "Stage",
    "Storey",
    "StoreyLevel",
    "TextAnnotation",
    "ValidationReason",
    "ValidationResult",
]
