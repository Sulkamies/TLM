"""Answer contract (AGENTS.md §4.2, v1.2.0). Custodian: A0."""

from enum import Enum
from typing import Literal

from pydantic import BaseModel

from blueprint_qa.contracts.common import Confidence


class AnswerStatus(str, Enum):
    ANSWERED = "ANSWERED"
    CANNOT_ANSWER = "CANNOT_ANSWER"
    NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
    UNSUPPORTED_QUESTION = "UNSUPPORTED_QUESTION"


class Answer(BaseModel):
    schema_version: str = "1.2.0"
    request_id: str
    status: AnswerStatus
    value: float | None  # THE answer; non-null iff status == ANSWERED
    unit: Literal["count", "ratio", "boolean", "m", "m2", "m3", "ft", "ft2", "ft3"]
    confidence: Confidence
    evidence: list[str]  # element ids from BlueprintAnalysis used
    explanation: str  # short reasoning / reason for no value, in ParsedQuestion.language
    language: str  # language of `explanation`
