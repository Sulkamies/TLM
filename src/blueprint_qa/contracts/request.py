"""Pipeline request contract (AGENTS.md §4.2, v1.2.0). Custodian: A0."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from blueprint_qa.contracts.common import InputFormat


class PipelineRequest(BaseModel):
    # bytes travel as base64 in JSON (R3.3 interoperability); see docs/DECISIONS.md
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    schema_version: str = "1.2.0"
    request_id: str
    input_bytes: bytes
    input_format: InputFormat  # declared by the caller; A1 verifies it
    filename: str | None = None
    question: str = Field(min_length=1)
    locale_hint: str | None = None  # BCP-47 UI locale if known; A2 detects the real language
    received_at: datetime
    # Receipt from an earlier ValidationResult for the same picture (change 006, since v1.2.0).
    # Opaque to everyone but A1, which verifies it and may then skip its LLM classification.
    validation_token: str | None = None
