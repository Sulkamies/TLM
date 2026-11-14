"""Validation receipts (contract change 006): issue, verify, reject quietly. No network."""

import base64
import hashlib
import hmac
import json
import logging

import pytest

from blueprint_qa.common.llm import get_llm_client
from blueprint_qa.contracts.common import ErrorEnvelope, InputFormat, Stage
from blueprint_qa.contracts.validation import ValidationReason, ValidationResult
from blueprint_qa.validation import validate, validator
from blueprint_qa.validation.providers.base import FloorPlanLabel
from blueprint_qa.validation.providers.llm import LlmFloorPlanClassifier
from blueprint_qa.validation.receipt import (
    ReceiptContext,
    ReceiptSettings,
    Rejected,
    RejectReason,
    Verified,
    issue_receipt,
    load_receipt_settings,
    receipt_key,
    verify_receipt,
)
from blueprint_qa.validation.validator import run_validation

from ._support import (
    FakeBackend,
    RecordingClassifier,
    make_ifc,
    make_pdf,
    make_png,
    make_request,
    make_settings,
    verdict_json,
)

KEY = b"k" * 32
NOW = 1_800_000_000.0
TTL = 3600
KEY_ENV = "BP_VALIDATION_RECEIPT_KEY"


def _ctx(key: bytes = KEY, now: float = NOW, ttl: int = TTL) -> ReceiptContext:
    return ReceiptContext(key=key, ttl_s=ttl, clock=lambda: now)


def _valid(outcome: ValidationResult | ErrorEnvelope) -> ValidationResult:
    assert isinstance(outcome, ValidationResult)
    return ValidationResult.model_validate(outcome.model_dump())


def _first(
    data: bytes, fmt: InputFormat, classifier: RecordingClassifier, ctx: ReceiptContext
) -> ValidationResult:
    result = _valid(run_validation(make_request(data, fmt), make_settings(), classifier, ctx))
    assert result.is_valid and result.validation_token is not None
    return result


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _signed(payload_obj: object, key: bytes = KEY) -> str:
    """A correctly signed token around an arbitrary payload (to test payload checks)."""
    payload = _b64(json.dumps(payload_obj).encode("utf-8"))
    sig = _b64(hmac.new(key, f"v1.{payload}".encode(), hashlib.sha256).digest())
    return f"v1.{payload}.{sig}"


# --- round trip ---------------------------------------------------------------


@pytest.mark.parametrize(
    ("data", "fmt"), [(make_png(), InputFormat.PNG), (make_pdf(), InputFormat.PDF)]
)
def test_round_trip_skips_classifier(data: bytes, fmt: InputFormat) -> None:
    classifier = RecordingClassifier(confidence=0.9)
    ctx = _ctx()
    first = _first(data, fmt, classifier, ctx)
    token = first.validation_token
    assert token is not None and token.startswith("v1.") and token.count(".") == 2

    second_request = make_request(data, fmt, validation_token=token)
    second = _valid(run_validation(second_request, make_settings(), classifier, ctx))

    assert len(classifier.calls) == 1  # one LLM classification for two requests
    assert second.is_valid and second.reason is ValidationReason.OK
    assert second.request_id == second_request.request_id
    assert second.confidence == 0.9
    assert second.provider == "receipt:test:recording"
    assert second.validation_token == token
    assert second.input_format is fmt
    # A3 still gets the normalised picture.
    assert second.plan_image is not None and first.plan_image is not None
    assert second.plan_image == first.plan_image
    assert second.ifc_bytes is None and second.ifc_schema is None


def test_payload_contents() -> None:
    data = make_png()
    token = issue_receipt(_ctx(), data, InputFormat.PNG, "llm:m:p@v1", 0.8)
    payload = token.split(".")[1]
    claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    assert claims == {
        "h": hashlib.sha256(data).hexdigest(),
        "f": "PNG",
        "p": "llm:m:p@v1",
        "c": 0.8,
        "e": int(NOW) + TTL,
    }
    assert "=" not in token


# --- quiet rejection ----------------------------------------------------------


def _assert_rejected_then_revalidated(
    data: bytes,
    token: str,
    reason: RejectReason,
    *,
    classifier: RecordingClassifier | None = None,
    ctx: ReceiptContext | None = None,
    caplog: pytest.LogCaptureFixture,
    **settings: object,
) -> ValidationResult:
    classifier = classifier or RecordingClassifier(confidence=0.9)
    ctx = ctx or _ctx()
    request = make_request(data, InputFormat.PNG, validation_token=token)
    with caplog.at_level(logging.INFO, logger="blueprint_qa.validation.validator"):
        result = _valid(run_validation(request, make_settings(**settings), classifier, ctx))
    assert len(classifier.calls) == 1  # validated normally, one LLM call
    events = [(r.getMessage(), getattr(r, "bp_fields", {})) for r in caplog.records]
    rejected = [fields for msg, fields in events if msg == "receipt_rejected"]
    assert rejected == [
        {"request_id": request.request_id, "stage": Stage.VALIDATION.value, "reason": reason.value}
    ]
    if token:
        assert all(token not in str(r.__dict__) for r in caplog.records)
    return result


def test_tampered_payload(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(data, InputFormat.PNG, RecordingClassifier(), _ctx()).validation_token
    assert token is not None
    version, payload, sig = token.split(".")
    tampered = f"{version}.{payload[:-2]}{'A' if payload[-2] != 'A' else 'B'}{payload[-1]}.{sig}"
    result = _assert_rejected_then_revalidated(
        data, tampered, RejectReason.BAD_SIGNATURE, caplog=caplog
    )
    # A fresh receipt is issued for the valid picture.
    assert result.provider == "test:recording"
    assert result.validation_token is not None and result.validation_token != tampered


def test_tampered_signature(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(data, InputFormat.PNG, RecordingClassifier(), _ctx()).validation_token
    assert token is not None
    flipped = token[:-1] + ("A" if token[-1] != "A" else "B")
    _assert_rejected_then_revalidated(data, flipped, RejectReason.BAD_SIGNATURE, caplog=caplog)


def test_other_picture(caplog: pytest.LogCaptureFixture) -> None:
    token = _first(
        make_png(40, 20), InputFormat.PNG, RecordingClassifier(), _ctx()
    ).validation_token
    assert token is not None
    _assert_rejected_then_revalidated(
        make_png(41, 20), token, RejectReason.OTHER_PICTURE, caplog=caplog
    )


def test_expired(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(data, InputFormat.PNG, RecordingClassifier(), _ctx()).validation_token
    assert token is not None
    # Still valid one second before expiry ...
    almost = verify_receipt(
        _ctx(now=NOW + TTL - 1), token, data, InputFormat.PNG, "test:recording", 0.7
    )
    assert isinstance(almost, Verified)
    # ... and rejected at expiry.
    _assert_rejected_then_revalidated(
        data, token, RejectReason.EXPIRED, ctx=_ctx(now=NOW + TTL), caplog=caplog
    )


def test_provider_changed(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(data, InputFormat.PNG, RecordingClassifier(), _ctx()).validation_token
    assert token is not None
    result = _assert_rejected_then_revalidated(
        data,
        token,
        RejectReason.PROVIDER_CHANGED,
        classifier=RecordingClassifier(provider="llm:new-model:floor_plan_classifier@v2"),
        caplog=caplog,
    )
    assert result.provider == "llm:new-model:floor_plan_classifier@v2"


def test_key_changed(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(data, InputFormat.PNG, RecordingClassifier(), _ctx()).validation_token
    assert token is not None
    _assert_rejected_then_revalidated(
        data, token, RejectReason.BAD_SIGNATURE, ctx=_ctx(key=b"another key"), caplog=caplog
    )


def test_confidence_below_new_threshold(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    token = _first(
        data, InputFormat.PNG, RecordingClassifier(confidence=0.8), _ctx()
    ).validation_token
    assert token is not None
    _assert_rejected_then_revalidated(
        data,
        token,
        RejectReason.LOW_CONFIDENCE,
        classifier=RecordingClassifier(confidence=0.95),
        caplog=caplog,
        min_confidence=0.85,
    )


@pytest.mark.parametrize(
    "token",
    [
        "",
        "garbage",
        "v1.only-two",
        "v2.abc.def",
        "v1..sig",
        "v1.payload.",
        "v1.a.b.c",
        "v1.päyload.sig",
        "v1.payload.sïg",
    ],
)
def test_malformed_tokens(token: str, caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    expected = RejectReason.BAD_SIGNATURE if token == "v1.payload.sïg" else RejectReason.MALFORMED
    _assert_rejected_then_revalidated(data, token, expected, caplog=caplog)


@pytest.mark.parametrize(
    "payload",
    [
        "not an object",
        {"h": "x", "f": "PNG", "p": "p", "c": 0.9},  # missing expiry
        {"h": "x", "f": "PNG", "p": "p", "c": 0.9, "e": 1, "extra": 1},
        {"h": "x", "f": "GIF", "p": "p", "c": 0.9, "e": 1},
        {"h": "x", "f": "PNG", "p": "p", "c": "0.9", "e": 1},
        {"h": "x", "f": "PNG", "p": "p", "c": 0.9, "e": 1.5},
    ],
)
def test_signed_but_invalid_payload(payload: object) -> None:
    check = verify_receipt(_ctx(), _signed(payload), make_png(), InputFormat.PNG, "p", 0.7)
    assert check == Rejected(RejectReason.MALFORMED)


def test_signed_payload_that_is_not_json() -> None:
    payload = _b64(b"\xff\xfe not json")
    sig = _b64(hmac.new(KEY, f"v1.{payload}".encode(), hashlib.sha256).digest())
    check = verify_receipt(_ctx(), f"v1.{payload}.{sig}", make_png(), InputFormat.PNG, "p", 0.7)
    assert check == Rejected(RejectReason.MALFORMED)


def test_out_of_range_confidence_in_signed_payload() -> None:
    data = make_png()
    claims = {
        "h": hashlib.sha256(data).hexdigest(),
        "f": "PNG",
        "p": "p",
        "c": 1.5,
        "e": int(2 * NOW),
    }
    check = verify_receipt(_ctx(), _signed(claims), data, InputFormat.PNG, "p", 0.7)
    assert check == Rejected(RejectReason.LOW_CONFIDENCE)


def test_format_changed() -> None:
    data = make_png()
    token = issue_receipt(_ctx(), data, InputFormat.PNG, "p", 0.9)
    check = verify_receipt(_ctx(), token, data, InputFormat.JPEG, "p", 0.7)
    assert check == Rejected(RejectReason.FORMAT_CHANGED)


# --- no receipt where none is due --------------------------------------------


def test_ifc_gets_no_receipt_and_ignores_token() -> None:
    classifier = RecordingClassifier()
    request = make_request(make_ifc(spaces=1), InputFormat.IFC, validation_token="v1.a.b")
    result = _valid(run_validation(request, make_settings(), classifier, _ctx()))
    assert result.is_valid and result.validation_token is None
    assert classifier.calls == []


@pytest.mark.parametrize(
    ("label", "confidence"),
    [(FloorPlanLabel.NOT_A_DRAWING, 0.95), (FloorPlanLabel.HOUSE_FLOOR_PLAN, 0.5)],
)
def test_invalid_picture_gets_no_receipt(label: FloorPlanLabel, confidence: float) -> None:
    classifier = RecordingClassifier(label=label, confidence=confidence)
    result = _valid(
        run_validation(
            make_request(make_png(), InputFormat.PNG), make_settings(), classifier, _ctx()
        )
    )
    assert not result.is_valid and result.validation_token is None


def test_local_rejection_gets_no_receipt() -> None:
    result = _valid(
        run_validation(
            make_request(make_png(), InputFormat.JPEG),
            make_settings(),
            RecordingClassifier(),
            _ctx(),
        )
    )
    assert result.reason is ValidationReason.FORMAT_MISMATCH
    assert result.validation_token is None


def test_classifier_error_passes_through() -> None:
    error = ErrorEnvelope(
        request_id="r",
        stage=Stage.VALIDATION,
        code="EXTERNAL_API_TIMEOUT",
        message="m",
        retryable=True,
    )
    outcome = run_validation(
        make_request(make_png(), InputFormat.PNG),
        make_settings(),
        RecordingClassifier(error=error),
        _ctx(),
    )
    assert outcome is error


def test_valid_receipt_for_invalid_local_input_still_rejects() -> None:
    """A receipt never bypasses the local checks."""
    data = make_pdf(pages=2)
    token = issue_receipt(_ctx(), data, InputFormat.PDF, "test:recording", 0.9)
    classifier = RecordingClassifier()
    request = make_request(data, InputFormat.PDF, validation_token=token)
    result = _valid(run_validation(request, make_settings(), classifier, _ctx()))
    assert result.reason is ValidationReason.MULTI_PAGE_PDF
    assert classifier.calls == []


def test_receipts_disabled() -> None:
    classifier = RecordingClassifier()
    data = make_png()
    token = issue_receipt(_ctx(), data, InputFormat.PNG, "test:recording", 0.9)
    result = _valid(
        run_validation(
            make_request(data, InputFormat.PNG, validation_token=token), make_settings(), classifier
        )
    )
    assert result.validation_token is None and result.provider == "test:recording"
    assert len(classifier.calls) == 1


# --- logging ------------------------------------------------------------------


def test_receipt_used_is_logged_without_token(caplog: pytest.LogCaptureFixture) -> None:
    data = make_png()
    classifier = RecordingClassifier()
    token = _first(data, InputFormat.PNG, classifier, _ctx()).validation_token
    assert token is not None
    request = make_request(data, InputFormat.PNG, validation_token=token)
    with caplog.at_level(logging.INFO, logger="blueprint_qa.validation.validator"):
        run_validation(request, make_settings(), classifier, _ctx())
    used = [getattr(r, "bp_fields", {}) for r in caplog.records if r.getMessage() == "receipt_used"]
    assert used == [{"request_id": request.request_id, "stage": Stage.VALIDATION.value}]
    assert all(token not in str(r.__dict__) for r in caplog.records)
    assert all(KEY.decode() not in str(r.__dict__) for r in caplog.records)


# --- key and settings ---------------------------------------------------------


def test_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(KEY_ENV, "secret-value")
    assert receipt_key(KEY_ENV) == b"secret-value"


@pytest.mark.parametrize("value", [None, ""])
def test_key_env_unset_gives_stable_random_key(
    value: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    if value is not None:
        monkeypatch.setenv(KEY_ENV, value)
    key = receipt_key(KEY_ENV)
    assert len(key) == 32
    assert receipt_key(KEY_ENV) == key  # once per process


def test_context_repr_hides_key() -> None:
    assert repr(KEY) not in repr(_ctx())


def test_settings_from_config() -> None:
    assert load_receipt_settings() == ReceiptSettings(ttl_s=3600, key_env=KEY_ENV)


@pytest.mark.parametrize(
    "values",
    [
        {"ttl_s": 0, "key_env": "X"},
        {"ttl_s": 1, "key_env": ""},
        {"ttl_s": 1, "key_env": "X", "y": 1},
    ],
)
def test_settings_validation(values: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        ReceiptSettings.model_validate(values)


# --- through the public entry point -------------------------------------------


def _patch_classifier(monkeypatch: pytest.MonkeyPatch, classifier: RecordingClassifier) -> None:
    monkeypatch.setattr(validator, "build_classifier", lambda settings: classifier)


def test_validate_round_trip_with_random_key(monkeypatch: pytest.MonkeyPatch) -> None:
    classifier = RecordingClassifier()
    _patch_classifier(monkeypatch, classifier)
    data = make_png()
    first = _valid(validate(make_request(data, InputFormat.PNG)))
    assert first.validation_token is not None
    for _ in range(2):
        later = _valid(validate(make_request(data, InputFormat.PNG, first.validation_token)))
        assert later.provider == "receipt:test:recording"
    assert len(classifier.calls) == 1


def test_validate_key_change_invalidates(monkeypatch: pytest.MonkeyPatch) -> None:
    classifier = RecordingClassifier()
    _patch_classifier(monkeypatch, classifier)
    data = make_png()
    monkeypatch.setenv(KEY_ENV, "key-one")
    token = _valid(validate(make_request(data, InputFormat.PNG))).validation_token
    monkeypatch.setenv(KEY_ENV, "key-two")
    again = _valid(validate(make_request(data, InputFormat.PNG, token)))
    assert again.provider == "test:recording"
    assert again.validation_token not in (None, token)
    assert len(classifier.calls) == 2


def test_llm_classifier_reports_provider_without_calling() -> None:
    backend = FakeBackend(verdict_json("HOUSE_FLOOR_PLAN", 0.9))
    classifier = LlmFloorPlanClassifier(
        max_side_px=None, max_bytes=None, client=get_llm_client("validation", backend=backend)
    )
    provider = classifier.provider
    assert backend.calls == []
    verdict = classifier.classify("r", make_png())
    assert not isinstance(verdict, ErrorEnvelope)
    assert verdict.provider == provider
