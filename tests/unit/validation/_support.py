"""Shared helpers for A1 unit tests. All sample files are generated in memory
(no fixtures from tests/fixtures/ are needed for unit tests)."""

import io
import json
import uuid
from datetime import UTC, datetime

import ifcopenshell
from PIL import Image

from blueprint_qa.common.llm import BackendCall, BackendResponse
from blueprint_qa.contracts.common import ErrorEnvelope, InputFormat
from blueprint_qa.contracts.request import PipelineRequest
from blueprint_qa.validation.providers.base import (
    ClassifierVerdict,
    FloorPlanClassification,
    FloorPlanLabel,
)
from blueprint_qa.validation.settings import ValidationSettings

EXIF_ORIENTATION_TAG = 0x0112


def make_png(width: int = 40, height: int = 20, mode: str = "RGB") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, (width, height), "white").save(buf, format="PNG")
    return buf.getvalue()


def make_jpeg(
    width: int = 40, height: int = 20, orientation: int | None = None, mode: str = "RGB"
) -> bytes:
    img = Image.new(mode, (width, height), "white")
    buf = io.BytesIO()
    if orientation is None:
        img.save(buf, format="JPEG")
    else:
        exif = Image.Exif()
        exif[EXIF_ORIENTATION_TAG] = orientation
        img.save(buf, format="JPEG", exif=exif.tobytes())
    return buf.getvalue()


def make_pdf(pages: int = 1, width_pt: int = 144, height_pt: int = 72) -> bytes:
    images = [Image.new("RGB", (width_pt, height_pt), "white") for _ in range(pages)]
    buf = io.BytesIO()
    images[0].save(buf, format="PDF", resolution=72, save_all=True, append_images=images[1:])
    return buf.getvalue()


def make_ifc(
    schema: str = "IFC4",
    spaces: int = 0,
    walls: int = 0,
    wall_entity: str = "IfcWall",
) -> bytes:
    # ifcopenshell's annotation omits versioned identifiers like "IFC4X3_ADD2",
    # which it accepts at runtime.
    model = ifcopenshell.file(schema=schema)  # type: ignore[arg-type]
    for _ in range(spaces):
        model.create_entity("IfcSpace", GlobalId=ifcopenshell.guid.new())
    for _ in range(walls):
        model.create_entity(wall_entity, GlobalId=ifcopenshell.guid.new())
    text: str = model.to_string()  # type: ignore[no-untyped-call]
    return text.encode("utf-8")


def make_request(data: bytes, input_format: InputFormat) -> PipelineRequest:
    return PipelineRequest(
        request_id=str(uuid.uuid4()),
        input_bytes=data,
        input_format=input_format,
        question="How many bedrooms are there?",
        received_at=datetime.now(UTC),
    )


def make_settings(**overrides: object) -> ValidationSettings:
    values: dict[str, object] = {
        "min_confidence": 0.7,
        "pdf_render_dpi": 200,
        "max_image_pixels": None,
        "llm_image_max_side_px": None,
        "llm_image_max_bytes": None,
        "supported_ifc_schemas": ["IFC2X3", "IFC4", "IFC4X3"],
    }
    values.update(overrides)
    return ValidationSettings.model_validate(values)


class FakeBackend:
    """Stands in for the Gemini backend behind the real ``LlmClient`` (no network)."""

    name = "fake"

    def __init__(self, *replies: str | Exception) -> None:
        self.replies = list(replies)
        self.calls: list[BackendCall] = []

    def generate(self, call: BackendCall) -> BackendResponse:
        self.calls.append(call)
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]
        if isinstance(reply, Exception):
            raise reply
        return BackendResponse(text=reply, input_tokens=100, output_tokens=10)


def verdict_json(label: str, confidence: float) -> str:
    return json.dumps({"label": label, "confidence": confidence})


class RecordingClassifier:
    """Classifier double that returns a fixed result and records what it was sent."""

    def __init__(
        self,
        label: FloorPlanLabel = FloorPlanLabel.HOUSE_FLOOR_PLAN,
        confidence: float = 0.95,
        error: ErrorEnvelope | None = None,
    ) -> None:
        self.label = label
        self.confidence = confidence
        self.error = error
        self.calls: list[tuple[str, bytes]] = []

    def classify(self, request_id: str, image_png: bytes) -> ClassifierVerdict | ErrorEnvelope:
        self.calls.append((request_id, image_png))
        if self.error is not None:
            return self.error
        return ClassifierVerdict(
            classification=FloorPlanClassification(label=self.label, confidence=self.confidence),
            provider="test:recording",
        )
