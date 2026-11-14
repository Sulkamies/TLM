"""Validator settings, loaded from the ``validation`` section of ``config/default.yaml``.

No limit-like value is hard-coded here (AGENTS.md R3.9): every field is required
and must come from configuration. LLM settings (model, retries, timeouts) live in
``config/llm.yaml`` and ``config/default.yaml → llm`` and are applied by ``common.llm``.
"""

from pydantic import BaseModel, ConfigDict, Field

from blueprint_qa.common import config


class ValidationSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    min_confidence: float = Field(ge=0.0, le=1.0)
    """``is_valid=True`` requires the classifier confidence to be at least this."""

    pdf_render_dpi: float = Field(gt=0)
    """Resolution used to render the single PDF page to PNG."""

    max_image_pixels: int | None = Field(gt=0)
    """Reject decoded/rendered images with more pixels than this. ``None`` = no limit."""

    llm_image_max_side_px: int | None = Field(gt=0)
    """Longest side of the copy sent to the LLM. ``None`` = send at full size.
    The ``PlanImage`` handed downstream is never resized."""

    llm_image_max_bytes: int | None = Field(gt=0)
    """Largest size of the PNG copy sent to the LLM, in bytes; larger copies are
    shrunk until they fit. ``None`` = no limit (the API may then reject large images)."""

    supported_ifc_schemas: tuple[str, ...] = Field(min_length=1)
    """IFC schemas accepted, as reported by ifcopenshell (e.g. ``IFC4X3``)."""


def load_settings() -> ValidationSettings:
    return ValidationSettings.model_validate(config.load_section("validation"))
