"""Fake component outputs for the orchestrator tests (A0)."""

from __future__ import annotations

from datetime import UTC, datetime

from blueprint_qa.contracts import (
    Aggregation,
    EntityRef,
    ErrorEnvelope,
    InputFormat,
    Intent,
    ParsedQuestion,
    PipelineRequest,
    PlanImage,
    RoomType,
    Stage,
    ValidationReason,
    ValidationResult,
)

RID = "11111111-1111-4111-8111-111111111111"


def make_request(question: str = "How many bedrooms?") -> PipelineRequest:
    return PipelineRequest(
        request_id=RID,
        input_bytes=b"\x89PNG fake",
        input_format=InputFormat.PNG,
        filename="plan.png",
        question=question,
        locale_hint=None,
        received_at=datetime(2026, 11, 14, tzinfo=UTC),
    )


def validation(is_valid: bool = True, rid: str = RID) -> ValidationResult:
    return ValidationResult(
        request_id=rid,
        is_valid=is_valid,
        reason=ValidationReason.OK if is_valid else ValidationReason.NOT_A_BLUEPRINT,
        confidence=0.9,
        input_format=InputFormat.PNG,
        provider="fake",
        plan_image=PlanImage(image_png=b"png-bytes", width_px=10, height_px=10)
        if is_valid
        else None,
        ifc_bytes=None,
        ifc_schema=None,
    )


def parsed(
    rid: str = RID,
    intent: Intent = Intent.COUNT,
    clarification: str | None = None,
    language: str = "en",
) -> ParsedQuestion:
    return ParsedQuestion(
        request_id=rid,
        original_question="How many bedrooms?",
        language=language,
        intent=intent,
        aggregation=Aggregation.SUM,
        targets=[EntityRef(category="ROOM", room_type=RoomType.BEDROOM)],
        comparison=None,
        requested_unit=None,
        confidence=0.95,
        provider="fake",
        clarification_needed=clarification,
    )


def envelope(stage: Stage, code: str = "EXTERNAL_API_TIMEOUT", rid: str = RID) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=rid,
        stage=stage,
        code=code,
        message="The service did not answer in time.",
        retryable=True,
        details={"internal": "debug info"},
    )
