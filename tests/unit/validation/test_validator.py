from pathlib import Path

import pytest

from blueprint_qa.common import config
from blueprint_qa.common.llm import LlmClient, get_llm_client
from blueprint_qa.contracts.common import ErrorEnvelope, InputFormat, Stage
from blueprint_qa.contracts.validation import ValidationReason, ValidationResult
from blueprint_qa.validation import validate, validator
from blueprint_qa.validation.providers import build_classifier
from blueprint_qa.validation.providers import llm as llm_provider
from blueprint_qa.validation.providers.base import FloorPlanLabel
from blueprint_qa.validation.providers.llm import LlmFloorPlanClassifier
from blueprint_qa.validation.validator import run_validation

from ._support import (
    FakeBackend,
    RecordingClassifier,
    make_ifc,
    make_jpeg,
    make_pdf,
    make_png,
    make_request,
    make_settings,
    verdict_json,
)


def _result(outcome: ValidationResult | ErrorEnvelope) -> ValidationResult:
    assert isinstance(outcome, ValidationResult)
    # Round-trip through the contract to make sure the output is contract-valid.
    return ValidationResult.model_validate(outcome.model_dump())


# --- raster / PDF happy paths -------------------------------------------------


@pytest.mark.parametrize(
    ("data", "fmt"),
    [
        (make_png(), InputFormat.PNG),
        (make_jpeg(), InputFormat.JPEG),
        (make_pdf(), InputFormat.PDF),
    ],
)
def test_valid_image_inputs(data: bytes, fmt: InputFormat) -> None:
    request = make_request(data, fmt)
    classifier = RecordingClassifier(confidence=0.9)
    result = _result(run_validation(request, make_settings(), classifier))

    assert result.is_valid
    assert result.reason is ValidationReason.OK
    assert result.request_id == request.request_id
    assert result.input_format is fmt
    assert result.confidence == 0.9
    assert result.provider == "test:recording"
    assert result.plan_image is not None
    assert result.ifc_bytes is None and result.ifc_schema is None
    # The classifier sees exactly the normalised PNG that is passed downstream.
    assert classifier.calls == [(request.request_id, result.plan_image.image_png)]


@pytest.mark.parametrize(
    ("label", "confidence", "reason"),
    [
        (
            FloorPlanLabel.HOUSE_FLOOR_PLAN,
            0.7,
            ValidationReason.OK,
        ),  # boundary is inclusive
        (FloorPlanLabel.HOUSE_FLOOR_PLAN, 0.69, ValidationReason.LOW_CONFIDENCE),
        (FloorPlanLabel.OTHER_FLOOR_PLAN, 0.95, ValidationReason.NOT_A_BLUEPRINT),
        (FloorPlanLabel.OTHER_DRAWING, 0.95, ValidationReason.NOT_A_BLUEPRINT),
        (FloorPlanLabel.NOT_A_DRAWING, 0.95, ValidationReason.NOT_A_BLUEPRINT),
        (FloorPlanLabel.NOT_A_DRAWING, 0.5, ValidationReason.LOW_CONFIDENCE),
    ],
)
def test_classifier_verdict_mapping(
    label: FloorPlanLabel, confidence: float, reason: ValidationReason
) -> None:
    request = make_request(make_png(), InputFormat.PNG)
    classifier = RecordingClassifier(label=label, confidence=confidence)
    result = _result(run_validation(request, make_settings(), classifier))

    assert result.reason is reason
    assert result.is_valid is (reason is ValidationReason.OK)
    assert result.confidence == confidence
    assert (result.plan_image is not None) is result.is_valid


def test_min_confidence_is_configurable() -> None:
    request = make_request(make_png(), InputFormat.PNG)
    classifier = RecordingClassifier(confidence=0.8)
    result = _result(run_validation(request, make_settings(min_confidence=0.9), classifier))
    assert result.reason is ValidationReason.LOW_CONFIDENCE


def test_classifier_error_passed_through() -> None:
    request = make_request(make_png(), InputFormat.PNG)
    error = ErrorEnvelope(
        request_id=request.request_id,
        stage=Stage.VALIDATION,
        code="EXTERNAL_API_TIMEOUT",
        message="The service did not respond in time.",
        retryable=True,
    )
    outcome = run_validation(request, make_settings(), RecordingClassifier(error=error))
    assert outcome == error


# --- local rejections (no classifier call) -----------------------------------


@pytest.mark.parametrize(
    ("data", "declared", "reason", "reported_format"),
    [
        (
            make_jpeg(),
            InputFormat.PNG,
            ValidationReason.FORMAT_MISMATCH,
            InputFormat.JPEG,
        ),
        (
            make_png(),
            InputFormat.PDF,
            ValidationReason.FORMAT_MISMATCH,
            InputFormat.PNG,
        ),
        (
            make_ifc(spaces=1),
            InputFormat.PNG,
            ValidationReason.FORMAT_MISMATCH,
            InputFormat.IFC,
        ),
        (
            b"not a known format",
            InputFormat.PNG,
            ValidationReason.UNREADABLE,
            InputFormat.PNG,
        ),
        (
            make_png()[:40],
            InputFormat.PNG,
            ValidationReason.UNREADABLE,
            InputFormat.PNG,
        ),
        (
            b"%PDF-1.7 broken",
            InputFormat.PDF,
            ValidationReason.UNREADABLE,
            InputFormat.PDF,
        ),
        (
            make_pdf(pages=2),
            InputFormat.PDF,
            ValidationReason.MULTI_PAGE_PDF,
            InputFormat.PDF,
        ),
    ],
)
def test_local_rejections(
    data: bytes,
    declared: InputFormat,
    reason: ValidationReason,
    reported_format: InputFormat,
) -> None:
    classifier = RecordingClassifier()
    result = _result(run_validation(make_request(data, declared), make_settings(), classifier))

    assert not result.is_valid
    assert result.reason is reason
    assert result.input_format is reported_format
    assert result.provider == "local:checks"
    assert result.confidence == 1.0
    assert result.plan_image is None and result.ifc_bytes is None
    assert classifier.calls == []


def test_pixel_limit_rejects_as_unreadable() -> None:
    classifier = RecordingClassifier()
    request = make_request(make_png(100, 100), InputFormat.PNG)
    result = _result(run_validation(request, make_settings(max_image_pixels=100), classifier))
    assert result.reason is ValidationReason.UNREADABLE
    assert classifier.calls == []


# --- IFC (local only, never the classifier) -----------------------------------


def test_valid_ifc_passes_bytes_through_unchanged() -> None:
    data = make_ifc(schema="IFC4X3_ADD2", spaces=3)
    classifier = RecordingClassifier()
    result = _result(
        run_validation(make_request(data, InputFormat.IFC), make_settings(), classifier)
    )

    assert result.is_valid and result.reason is ValidationReason.OK
    assert result.input_format is InputFormat.IFC
    assert result.provider == "local:ifc"
    assert result.confidence == 1.0
    assert result.ifc_bytes == data
    assert result.ifc_schema == "IFC4X3"
    assert result.plan_image is None
    assert classifier.calls == []


def test_ifc_without_spatial_data() -> None:
    classifier = RecordingClassifier()
    result = _result(
        run_validation(make_request(make_ifc(), InputFormat.IFC), make_settings(), classifier)
    )
    assert result.reason is ValidationReason.NO_SPATIAL_DATA
    assert result.ifc_schema == "IFC4"
    assert result.ifc_bytes is None
    assert classifier.calls == []


# --- public entry point -------------------------------------------------------


def _patch_config(monkeypatch: pytest.MonkeyPatch, **overrides: object) -> None:
    section = make_settings(**overrides).model_dump()

    def load_section(name: str) -> dict[str, object]:
        assert name == "validation"
        return dict(section)

    monkeypatch.setattr(config, "load_section", load_section)


def _patch_backend(monkeypatch: pytest.MonkeyPatch, backend: FakeBackend) -> None:
    def client(component: str) -> LlmClient:
        return get_llm_client(component, backend=backend)

    monkeypatch.setattr(llm_provider, "get_llm_client", client)


def test_validate_end_to_end_through_llm_wrapper(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_config(monkeypatch)
    backend = FakeBackend(verdict_json("HOUSE_FLOOR_PLAN", 0.91))
    _patch_backend(monkeypatch, backend)
    request = make_request(make_png(), InputFormat.PNG)
    result = _result(validate(request))
    assert result.is_valid
    assert result.confidence == 0.91
    assert result.provider.endswith(":floor_plan_classifier@v1")
    assert result.plan_image is not None
    assert backend.calls[0].images_png == (result.plan_image.image_png,)


def test_validate_with_mock_provider_and_no_cassette_fails_safely(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    _patch_config(monkeypatch)
    monkeypatch.setenv("BP_LLM_PROVIDER", "mock")
    monkeypatch.setenv("BP_LLM_CASSETTE_DIR", str(tmp_path))
    outcome = validate(make_request(make_png(), InputFormat.PNG))
    assert isinstance(outcome, ErrorEnvelope)
    assert outcome.code == "INTERNAL_ERROR"
    assert outcome.stage is Stage.VALIDATION


def test_validate_never_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_config(monkeypatch)

    def boom(*args: object) -> ValidationResult:
        raise RuntimeError("secret detail that must not leak")

    monkeypatch.setattr(validator, "run_validation", boom)
    request = make_request(make_png(), InputFormat.PNG)
    outcome = validate(request)

    assert isinstance(outcome, ErrorEnvelope)
    assert outcome.code == "INTERNAL_ERROR"
    assert outcome.stage is Stage.VALIDATION
    assert outcome.request_id == request.request_id
    assert not outcome.retryable
    assert outcome.details == {"exception": "RuntimeError"}
    assert "secret" not in outcome.message


def test_validate_reports_bad_config_as_internal_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def load_section(name: str) -> dict[str, object]:
        return {"min_confidence": 2.0}

    monkeypatch.setattr(config, "load_section", load_section)
    outcome = validate(make_request(make_png(), InputFormat.PNG))
    assert isinstance(outcome, ErrorEnvelope)
    assert outcome.code == "INTERNAL_ERROR"


def test_build_classifier_uses_llm_with_configured_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_backend(monkeypatch, FakeBackend(verdict_json("HOUSE_FLOOR_PLAN", 0.9)))
    classifier = build_classifier(make_settings(llm_image_max_side_px=100))
    assert isinstance(classifier, LlmFloorPlanClassifier)
