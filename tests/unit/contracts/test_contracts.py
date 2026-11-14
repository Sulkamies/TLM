"""Contract models: JSON round-trips, enum values, and generated schemas in sync."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from blueprint_qa.contracts import (
    CONTRACT_VERSION,
    Aggregation,
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    EntityRef,
    ErrorEnvelope,
    InputFormat,
    Intent,
    ParsedQuestion,
    PipelineRequest,
    PlanImage,
    Room,
    RoomType,
    Scale,
    Stage,
    ValidationReason,
    ValidationResult,
    generate_schema,
)


def test_schemas_are_up_to_date() -> None:
    assert generate_schema.main(["--check"]) == 0, (
        "run: python -m blueprint_qa.contracts.generate_schema"
    )


def test_schema_files_are_valid_json() -> None:
    for path, _ in generate_schema.expected_files().items():
        assert json.loads(path.read_text(encoding="utf-8"))["type"] == "object"


def test_bytes_round_trip_as_base64() -> None:
    raw = bytes(range(256))  # not valid UTF-8
    req = PipelineRequest(
        request_id="r1",
        input_bytes=raw,
        input_format=InputFormat.PNG,
        question="How many bedrooms?",
        received_at=datetime(2026, 11, 14, tzinfo=UTC),
    )
    text = req.model_dump_json()
    assert PipelineRequest.model_validate_json(text).input_bytes == raw

    vr = ValidationResult(
        request_id="r1",
        is_valid=True,
        reason=ValidationReason.OK,
        confidence=0.9,
        input_format=InputFormat.PNG,
        provider="mock",
        plan_image=PlanImage(image_png=raw, width_px=10, height_px=10),
        ifc_bytes=None,
        ifc_schema=None,
    )
    back = ValidationResult.model_validate_json(vr.model_dump_json())
    assert back.plan_image is not None and back.plan_image.image_png == raw


def test_question_must_not_be_empty() -> None:
    with pytest.raises(ValidationError):
        PipelineRequest(
            request_id="r1",
            input_bytes=b"x",
            input_format=InputFormat.PNG,
            question="",
            received_at=datetime.now(UTC),
        )


def test_parsed_question_round_trip_and_enum_strings() -> None:
    pq = ParsedQuestion(
        request_id="r1",
        original_question="Wie viele Schlafzimmer?",
        language="de",
        intent=Intent.COUNT,
        aggregation=Aggregation.SUM,
        targets=[EntityRef(category="ROOM", room_type=RoomType.BEDROOM)],
        comparison=None,
        requested_unit=None,
        confidence=0.95,
        provider="mock",
        clarification_needed=None,
    )
    data = json.loads(pq.model_dump_json())
    assert data["intent"] == "COUNT"
    assert data["targets"][0]["room_type"] == "BEDROOM"
    assert data["schema_version"] == CONTRACT_VERSION
    assert ParsedQuestion.model_validate(data) == pq


def test_unknown_fields_are_ignored_by_consumers() -> None:
    # R4.4: consumers MUST ignore unknown optional fields
    env = ErrorEnvelope.model_validate(
        {
            "request_id": "r1",
            "stage": "QUESTION",
            "code": "INTERNAL_ERROR",
            "message": "x",
            "retryable": False,
            "future_field": 1,
        }
    )
    assert env.stage is Stage.QUESTION
    assert "future_field" not in env.model_dump()


def test_rejects_unknown_enum_value() -> None:
    with pytest.raises(ValidationError):
        EntityRef.model_validate({"category": "FIXTURE"})


def test_analysis_and_answer_round_trip() -> None:
    ba = BlueprintAnalysis(
        request_id="r1",
        source_format=InputFormat.PNG,
        coordinate_space="PIXEL",
        metric_available=False,
        scale=Scale(pixels_per_meter=None, source="NONE", confidence=0.0),
        storeys=[],
        rooms=[
            Room(
                id="room_1",
                storey_id=None,
                room_type=RoomType.SAUNA,
                label_text="S",
                polygon=[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0)],
                area_m2=None,
                area_source=None,
                height_m=None,
                source_ref=None,
                confidence=0.8,
            )
        ],
        openings=[],
        adjacency=[],
        texts=[],
        analyzer_version="test",
        warnings=[],
    )
    assert BlueprintAnalysis.model_validate_json(ba.model_dump_json()) == ba

    ans = Answer(
        request_id="r1",
        status=AnswerStatus.ANSWERED,
        value=1.0,
        unit="boolean",
        confidence=0.8,
        evidence=["room_1"],
        explanation="Onko saunaa: kyllä.",
        language="fi",
    )
    assert Answer.model_validate_json(ans.model_dump_json()) == ans


@pytest.mark.parametrize("value", [-0.01, 1.01, 2.0])
def test_confidence_outside_unit_interval_is_rejected(value: float) -> None:
    # v1.0.1: every confidence is a float in [0.0, 1.0] (§4.1)
    with pytest.raises(ValidationError):
        Scale(pixels_per_meter=None, source="NONE", confidence=value)
    with pytest.raises(ValidationError):
        ParsedQuestion(
            request_id="r",
            original_question="q",
            language="en",
            intent=Intent.COUNT,
            aggregation=Aggregation.SUM,
            targets=[EntityRef(category="ROOM")],
            comparison=None,
            requested_unit=None,
            confidence=value,
            provider="mock",
            clarification_needed=None,
        )


@pytest.mark.parametrize("value", [0.0, 0.5, 1.0])
def test_confidence_bounds_are_inclusive(value: float) -> None:
    assert Scale(pixels_per_meter=None, source="NONE", confidence=value).confidence == value


def test_confidence_range_is_in_json_schema() -> None:
    for path in generate_schema.expected_files():
        text = path.read_text(encoding="utf-8")
        if '"confidence"' in text:
            schema = json.loads(text)
            props = [schema.get("properties", {})] + [
                d.get("properties", {}) for d in schema.get("$defs", {}).values()
            ]
            for p in props:
                if "confidence" in p:
                    assert p["confidence"]["minimum"] == 0.0
                    assert p["confidence"]["maximum"] == 1.0
