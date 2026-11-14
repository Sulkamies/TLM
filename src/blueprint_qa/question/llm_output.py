"""The structured output the LLM must fill (design rule Q2: schema by composition).

``LlmParse`` reuses the contract types (``Intent``, ``Aggregation``, ``EntityRef``,
``Comparison``), so a vocabulary or ``EntityRef`` change reaches the LLM schema with no
edit here. Fields that code owns (``request_id``, ``provider``, ``original_question``)
are deliberately absent.

The LLM reports a comparison threshold *as written* plus its unit (``threshold_unit``);
``mapping.py`` converts it to SI (rule Q5). The cross-field invariants of §4.2 are
checked in a model validator. The wrapper validates every reply with this model, so a
violation makes it re-ask the LLM with the error message (R7.8).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from blueprint_qa.contracts import Aggregation, Comparison, Confidence, EntityRef, Intent

Dimension = Literal["count", "length", "area", "volume"]

# Units a threshold may be written in. Unit symbols are not plan vocabulary (rule Q1).
ThresholdUnit = Literal["count", "mm", "cm", "m", "in", "ft", "m2", "ft2", "m3", "ft3", "l"]

# Units a measured answer may be requested in (mirrors ParsedQuestion.requested_unit;
# a unit test keeps the two in sync).
RequestedUnit = Literal["m", "m2", "m3", "ft", "ft2", "ft3"]

# unit -> (dimension, factor to the SI unit of that dimension). Exact definitions.
UNITS: dict[str, tuple[Dimension, float]] = {
    "count": ("count", 1.0),
    "mm": ("length", 0.001),
    "cm": ("length", 0.01),
    "m": ("length", 1.0),
    "in": ("length", 0.0254),
    "ft": ("length", 0.3048),
    "m2": ("area", 1.0),
    "ft2": ("area", 0.3048**2),
    "m3": ("volume", 1.0),
    "ft3": ("volume", 0.3048**3),
    "l": ("volume", 0.001),
}

# SI unit assumed when a threshold is written without a unit.
SI_UNIT: dict[Dimension, str] = {"count": "count", "length": "m", "area": "m2", "volume": "m3"}

# Comparison.measure -> dimension.
MEASURE_DIMENSION: dict[str, Dimension] = {
    "COUNT": "count",
    "AREA": "area",
    "LENGTH": "length",
    "PERIMETER": "length",
    "HEIGHT": "length",
    "VOLUME": "volume",
}

# Intents whose answer is a physical measure, and its dimension. Other intents
# answer with a count, ratio or boolean and take no requested_unit.
INTENT_DIMENSION: dict[Intent, Dimension] = {
    Intent.AREA: "area",
    Intent.LENGTH: "length",
    Intent.PERIMETER: "length",
    Intent.HEIGHT: "length",
    Intent.DISTANCE: "length",
    Intent.VOLUME: "volume",
}

_LANGUAGE_TAG = re.compile(r"^[A-Za-z]{2,3}(-[A-Za-z0-9]{2,8})*$")


class LlmParse(BaseModel):
    """What the LLM returns for one question."""

    model_config = ConfigDict(extra="forbid")

    language: str = Field(description="BCP-47 code of the question's language, e.g. en, de, fi.")
    intent: Intent
    aggregation: Aggregation
    targets: list[EntityRef] = Field(min_length=1)
    comparison: Comparison | None = Field(
        default=None,
        description="Only for intent COMPARISON. threshold is the number exactly as written.",
    )
    threshold_unit: ThresholdUnit | None = Field(
        default=None, description="Unit of comparison.threshold as written; null if none given."
    )
    requested_unit: RequestedUnit | None = None
    confidence: Confidence
    clarification_needed: str | None = None

    @model_validator(mode="after")
    def _check_invariants(self) -> LlmParse:
        if not _LANGUAGE_TAG.match(self.language.strip()):
            raise ValueError("language must be a BCP-47 code such as 'en', 'de' or 'fi'")
        is_comparison = self.intent is Intent.COMPARISON
        if is_comparison and self.comparison is None:
            raise ValueError("intent COMPARISON requires comparison")
        if not is_comparison and self.comparison is not None:
            raise ValueError("comparison must be null unless intent is COMPARISON")
        if self.intent is Intent.DISTANCE and len(self.targets) != 2:
            raise ValueError("intent DISTANCE requires exactly 2 targets")
        if self.intent is Intent.RATIO and len(self.targets) != 2:
            raise ValueError("intent RATIO requires exactly 2 targets (numerator, denominator)")
        if self.comparison is not None:
            self._check_comparison(self.comparison)
        elif self.threshold_unit is not None:
            raise ValueError("threshold_unit must be null without a comparison")
        dim = INTENT_DIMENSION.get(self.intent)
        if (
            dim is not None
            and self.requested_unit is not None
            and UNITS[self.requested_unit][0] != dim
        ):
            raise ValueError(f"requested_unit {self.requested_unit} is not a {dim} unit")
        return self

    def _check_comparison(self, comparison: Comparison) -> None:
        if comparison.threshold is None:
            if len(self.targets) != 2:
                raise ValueError("a comparison without threshold needs exactly 2 targets")
            if self.threshold_unit is not None:
                raise ValueError("threshold_unit must be null when threshold is null")
            return
        if self.threshold_unit is not None:
            dim = MEASURE_DIMENSION[comparison.measure]
            if UNITS[self.threshold_unit][0] != dim:
                raise ValueError(
                    f"threshold_unit {self.threshold_unit} does not fit measure "
                    f"{comparison.measure} ({dim})"
                )
