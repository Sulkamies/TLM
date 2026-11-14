"""The ``POST /ask`` response format shared by every client. Custodian: A0.

Spec: ``docs/API.md``. Clients: the Android app (``android-app/``, ``HttpRecognizer``) and the
browser page served at ``/`` (``api/web/index.html``). Both read only these models.

This module only *presents* a pipeline result (§4.2: rounding and display belong to the
presentation layer). It computes nothing: the number comes from A4, the boxes from A3's
analysis. Changes must stay additive (clients ignore unknown fields).
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    ErrorEnvelope,
    ValidationResult,
)
from blueprint_qa.orchestrator.pipeline import PipelineTrace


class EvidenceBox(BaseModel):
    """Where an answer came from, in fractions (0..1) of the picture after EXIF rotation."""

    label: str
    x: float
    y: float
    w: float
    h: float


class AskAnswer(BaseModel):
    """HTTP 200: an answer. ``answer`` is a number, a yes/no word, or a reason text."""

    answer: float | str
    unit: str | None  # display unit ("m²"); "count" is not shown by the clients
    type: str  # count | area | length | volume | ratio | boolean | text
    working: str | None  # A4's explanation, in the question's language
    evidence: list[EvidenceBox]
    status: str  # AnswerStatus value
    value: float | None  # the raw value (1.0/0.0 for yes/no); null iff not ANSWERED
    language: str
    confidence: float
    request_id: str


class AskError(BaseModel):
    """HTTP 4xx/5xx: a message safe to show to the user."""

    error: str
    code: str | None = None


# Display units (clients show any unit except "count" next to the number).
DISPLAY_UNITS: dict[str, str] = {"m2": "m²", "m3": "m³", "ft2": "ft²", "ft3": "ft³"}
# Answer kind by unit (clients only treat "text" specially).
TYPES: dict[str, str] = {
    "count": "count",
    "ratio": "ratio",
    "boolean": "boolean",
    "m": "length",
    "ft": "length",
    "m2": "area",
    "ft2": "area",
    "m3": "volume",
    "ft3": "volume",
}
# Yes/no in the explanation's language (Answer.language); English otherwise.
YES_NO: dict[str, tuple[str, str]] = {
    "en": ("Yes", "No"),
    "de": ("Ja", "Nein"),
    "fi": ("Kyllä", "Ei"),
}


def present(trace: PipelineTrace, point_size: float) -> tuple[int, dict[str, Any]]:
    """HTTP status and JSON body. Never includes ``ErrorEnvelope.details``."""
    result = trace.result
    if isinstance(result, ErrorEnvelope):
        status = 503 if result.retryable else 500
        return status, AskError(error=result.message, code=result.code).model_dump()
    return 200, to_answer(result, trace, point_size).model_dump()


def to_answer(a: Answer, trace: PipelineTrace, point_size: float) -> AskAnswer:
    common: dict[str, Any] = {
        "status": a.status.value,
        "value": a.value,
        "language": a.language,
        "confidence": a.confidence,
        "request_id": a.request_id,
    }
    if a.status is not AnswerStatus.ANSWERED or a.value is None:
        # Not answerable / needs clarification / unsupported: the reason is the answer text.
        return AskAnswer(
            answer=a.explanation, unit=None, type="text", working=None, evidence=[], **common
        )
    shown: float | str
    if a.unit == "boolean":
        yes, no = YES_NO.get(a.language, YES_NO["en"])
        shown, unit = (yes if a.value == 1.0 else no), None
    else:
        shown, unit = a.value, DISPLAY_UNITS.get(a.unit, a.unit)
    return AskAnswer(
        answer=shown,
        unit=unit,
        type=TYPES.get(a.unit, "count"),
        working=a.explanation,
        evidence=evidence_boxes(a.evidence, trace, point_size),
        **common,
    )


def evidence_boxes(ids: list[str], trace: PipelineTrace, point_size: float) -> list[EvidenceBox]:
    """The answer's evidence ids as boxes in fractions (0..1) of the plan image.

    Rooms use their polygon's bounding box; doors, windows and fixtures are points and get a
    square of ``point_size`` times the shorter image side. Only for PIXEL analyses (raster plans).
    """
    plan = next((o for _, o in trace.stages if isinstance(o, ValidationResult)), None)
    analysis = next((o for _, o in trace.stages if isinstance(o, BlueprintAnalysis)), None)
    if plan is None or plan.plan_image is None or analysis is None:
        return []
    if analysis.coordinate_space != "PIXEL":
        return []
    w, h = plan.plan_image.width_px, plan.plan_image.height_px
    if w <= 0 or h <= 0:
        return []
    half = point_size * min(w, h) / 2
    rooms = {r.id: r for r in analysis.rooms}
    points: dict[str, tuple[str, tuple[float, float]]] = {
        o.id: (o.kind, o.position) for o in analysis.openings
    }
    points.update({f.id: (f.fixture_type.value, f.position) for f in analysis.fixtures})

    boxes: list[EvidenceBox] = []
    for element_id in ids:
        if element_id in rooms:
            room = rooms[element_id]
            xs = [x for x, _ in room.polygon]
            ys = [y for _, y in room.polygon]
            if not xs:
                continue
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
            label = _label(room.room_type.value, room.label_text)
        elif element_id in points:
            kind, (cx, cy) = points[element_id]
            x0, y0, x1, y1 = cx - half, cy - half, cx + half, cy + half
            label = _label(kind, None)
        else:
            continue
        x0, x1 = _clamp(x0 / w), _clamp(x1 / w)
        y0, y1 = _clamp(y0 / h), _clamp(y1 / h)
        boxes.append(EvidenceBox(label=label, x=x0, y=y0, w=x1 - x0, h=y1 - y0))
    return boxes


def _label(kind: str, text: str | None) -> str:
    name = kind.replace("_", " ").capitalize()
    return f"{name} ({text})" if text else name


def _clamp(v: float) -> float:
    return min(1.0, max(0.0, v))
