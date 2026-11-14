"""Input validation contract (AGENTS.md §4.2, v1.0.1). Custodian: A0."""

from enum import Enum

from pydantic import BaseModel, ConfigDict

from blueprint_qa.contracts.common import Confidence, InputFormat


class ValidationReason(str, Enum):
    OK = "OK"
    NOT_A_BLUEPRINT = "NOT_A_BLUEPRINT"
    FORMAT_MISMATCH = "FORMAT_MISMATCH"
    UNREADABLE = "UNREADABLE"
    NO_SPATIAL_DATA = "NO_SPATIAL_DATA"  # e.g. IFC without spaces/walls
    MULTI_PAGE_PDF = "MULTI_PAGE_PDF"  # PDFs must have exactly 1 page
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class PlanImage(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    image_png: bytes  # normalized PNG, EXIF-rotated, NOT resized
    width_px: int
    height_px: int


class ValidationResult(BaseModel):
    model_config = ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")

    schema_version: str = "1.0.1"
    request_id: str
    is_valid: bool
    reason: ValidationReason
    confidence: Confidence
    input_format: InputFormat  # verified format (from magic bytes / header)
    provider: str  # e.g. "llm:<model-id>:prompt@v3", "local:ifc", "mock"
    plan_image: PlanImage | None  # PNG/JPEG/PDF only; None for IFC or when invalid
    ifc_bytes: bytes | None  # IFC only, passed through unchanged
    ifc_schema: str | None  # e.g. "IFC2X3", "IFC4", "IFC4X3"
