"""Floor-plan classifier adapter interface.

The raw labels defined here are internal to ``blueprint_qa.validation``; they are
mapped to ``ValidationReason`` by the validator and never leave this package.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from blueprint_qa.contracts.common import ErrorEnvelope


class FloorPlanLabel(str, Enum):
    HOUSE_FLOOR_PLAN = "HOUSE_FLOOR_PLAN"
    OTHER_FLOOR_PLAN = "OTHER_FLOOR_PLAN"
    OTHER_DRAWING = "OTHER_DRAWING"
    NOT_A_DRAWING = "NOT_A_DRAWING"


class FloorPlanClassification(BaseModel):
    """Structured output requested from the classifier (also the LLM output schema)."""

    model_config = ConfigDict(extra="forbid")

    label: FloorPlanLabel
    confidence: float = Field(ge=0.0, le=1.0)


@dataclass(frozen=True)
class ClassifierVerdict:
    classification: FloorPlanClassification
    provider: str
    """Value for ``ValidationResult.provider``, e.g. ``llm:<model-id>:<prompt>@v1``."""


class FloorPlanClassifier(Protocol):
    def classify(self, request_id: str, image_png: bytes) -> ClassifierVerdict | ErrorEnvelope:
        """Decide whether the PNG image is a house floor plan."""
        ...
