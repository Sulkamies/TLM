"""Shared contract types (AGENTS.md §4.2, v1.1.0). Custodian: A0."""

from enum import Enum
from typing import Annotated

from pydantic import BaseModel, Field

# Type of every `confidence` field (§4.1): a float in [0.0, 1.0]. Since v1.0.1.
Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class Stage(str, Enum):
    ORCHESTRATOR = "ORCHESTRATOR"
    VALIDATION = "VALIDATION"
    QUESTION = "QUESTION"
    ANALYSIS = "ANALYSIS"
    REASONING = "REASONING"


class InputFormat(str, Enum):
    PNG = "PNG"
    JPEG = "JPEG"
    PDF = "PDF"
    IFC = "IFC"


class ErrorEnvelope(BaseModel):
    schema_version: str = "1.1.0"
    request_id: str
    stage: Stage
    code: str  # from the registry in §5
    message: str  # safe to show to the end user
    retryable: bool
    details: dict[str, str] = {}  # internal debug info; never user data or secrets
