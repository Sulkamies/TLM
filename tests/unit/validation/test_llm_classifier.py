"""Tests for the LLM classifier adapter.

The real ``common.llm.LlmClient`` is used with a fake backend, so prompt loading,
user-data rendering, schema validation and re-asks run as in production, but
nothing touches the network (R7.3).
"""

import io

import pytest
from PIL import Image

from blueprint_qa.common.llm import LlmTransportError, get_llm_client
from blueprint_qa.contracts.common import ErrorEnvelope, Stage
from blueprint_qa.validation.providers.base import FloorPlanClassification, FloorPlanLabel
from blueprint_qa.validation.providers.llm import (
    PROMPT_NAME,
    PROMPT_VERSION,
    LlmFloorPlanClassifier,
    classifier_prompt,
    prepare_llm_image,
)

from ._support import FakeBackend, make_png, verdict_json


def _classifier(
    backend: FakeBackend, max_side_px: int | None = None, max_bytes: int | None = None
) -> LlmFloorPlanClassifier:
    return LlmFloorPlanClassifier(
        max_side_px=max_side_px,
        max_bytes=max_bytes,
        client=get_llm_client("validation", backend=backend),
    )


def _noisy_png(width: int, height: int, mode: str = "RGB") -> bytes:
    """Photo-like image: random pixels compress badly as PNG (like a scanned engraving)."""
    img = Image.effect_noise((width, height), 80).convert(mode)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# --- classify -----------------------------------------------------------------


def test_successful_classification() -> None:
    backend = FakeBackend(verdict_json("HOUSE_FLOOR_PLAN", 0.93))
    png = make_png()
    verdict = _classifier(backend).classify("req-1", png)

    assert not isinstance(verdict, ErrorEnvelope)
    assert verdict.classification.label is FloorPlanLabel.HOUSE_FLOOR_PLAN
    assert verdict.classification.confidence == 0.93
    assert verdict.provider.endswith(f":{PROMPT_NAME}@v{PROMPT_VERSION}")
    assert verdict.provider.startswith("llm:")

    (call,) = backend.calls
    assert call.prompt_ref == f"{PROMPT_NAME}@v{PROMPT_VERSION}"
    assert call.system_instruction == classifier_prompt().text
    assert call.images_png == (png,)
    assert call.response_json_schema == FloorPlanClassification.model_json_schema()
    # No user text is sent: the data block is empty JSON.
    assert "<user_data>\n{}\n</user_data>" in call.turns[0].text


def test_invalid_output_is_re_asked() -> None:
    backend = FakeBackend("not json", verdict_json("OTHER_DRAWING", 0.9))
    verdict = _classifier(backend).classify("req-1", make_png())
    assert not isinstance(verdict, ErrorEnvelope)
    assert verdict.classification.label is FloorPlanLabel.OTHER_DRAWING
    assert len(backend.calls) == 2


def test_unknown_label_never_accepted() -> None:
    backend = FakeBackend(verdict_json("MAYBE_A_PLAN", 0.9))
    result = _classifier(backend).classify("req-1", make_png())
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "LLM_OUTPUT_INVALID"


def test_transport_error_becomes_envelope() -> None:
    backend = FakeBackend(LlmTransportError("EXTERNAL_API_AUTH", "no key"))
    result = _classifier(backend).classify("req-1", make_png())
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "EXTERNAL_API_AUTH"
    assert result.stage is Stage.VALIDATION
    assert not result.retryable


def test_llm_receives_downscaled_copy() -> None:
    backend = FakeBackend(verdict_json("HOUSE_FLOOR_PLAN", 0.9))
    _classifier(backend, max_side_px=100).classify("req-1", make_png(400, 200))
    sent = backend.calls[0].images_png[0]
    assert Image.open(io.BytesIO(sent)).size == (100, 50)


def test_prompt_file_is_versioned_and_lists_labels() -> None:
    prompt = classifier_prompt()
    assert prompt.ref == "floor_plan_classifier@v1"
    for label in FloorPlanLabel:
        assert label.value in prompt.text
    assert "untrusted" in prompt.text


def test_output_schema_rejects_unknown_labels_and_fields() -> None:
    with pytest.raises(ValueError):
        FloorPlanClassification.model_validate({"label": "MAYBE", "confidence": 0.5})
    with pytest.raises(ValueError):
        FloorPlanClassification.model_validate({"label": "NOT_A_DRAWING", "confidence": 1.5})
    with pytest.raises(ValueError):
        FloorPlanClassification.model_validate(
            {"label": "NOT_A_DRAWING", "confidence": 0.5, "note": "extra"}
        )


# --- prepare_llm_image ----------------------------------------------------------


def test_small_image_sent_unchanged() -> None:
    png = make_png(200, 100)
    assert prepare_llm_image(png, max_side_px=1000, max_bytes=len(png)) is png


def test_no_limits_sends_original() -> None:
    png = _noisy_png(400, 400)
    assert prepare_llm_image(png, None, None) is png


def test_oversized_png_is_shrunk_until_it_fits() -> None:
    png = _noisy_png(800, 600)
    limit = len(png) // 3
    data = prepare_llm_image(png, max_side_px=None, max_bytes=limit)
    assert len(data) <= limit
    sent = Image.open(io.BytesIO(data))
    assert sent.format == "PNG"
    w, h = sent.size
    assert w < 800 and h < 600
    assert abs(w / h - 800 / 600) < 0.02  # aspect ratio kept


def test_downscale_and_byte_limit_combined() -> None:
    png = _noisy_png(1200, 600)
    data = prepare_llm_image(png, max_side_px=600, max_bytes=60_000)
    sent = Image.open(io.BytesIO(data))
    assert max(sent.size) <= 600
    assert len(data) <= 60_000


def test_tiny_limit_terminates() -> None:
    data = prepare_llm_image(_noisy_png(64, 64), max_side_px=None, max_bytes=1)
    assert Image.open(io.BytesIO(data)).size == (1, 1)


@pytest.mark.parametrize("mode", ["RGBA", "LA", "P", "1", "L"])
def test_any_png_mode_can_be_shrunk(mode: str) -> None:
    png = _noisy_png(300, 200, mode)
    data = prepare_llm_image(png, max_side_px=None, max_bytes=len(png) - 1)
    assert len(data) < len(png)
    assert Image.open(io.BytesIO(data)).format == "PNG"


def test_classifier_sends_shrunk_copy_for_oversized_image() -> None:
    backend = FakeBackend(verdict_json("NOT_A_DRAWING", 0.9))
    png = _noisy_png(600, 400)
    _classifier(backend, max_bytes=len(png) // 2).classify("r", png)
    (sent,) = backend.calls[0].images_png
    assert len(sent) <= len(png) // 2
