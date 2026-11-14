"""HTTP front door for the Android app: POST /ask in the app's format, GET /health."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from blueprint_qa.api import mobile, server
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    ErrorEnvelope,
    InputFormat,
    PipelineRequest,
    PlanImage,
    Stage,
    ValidationReason,
    ValidationResult,
)
from blueprint_qa.orchestrator.pipeline import PipelineTrace

RID = "11111111-1111-4111-8111-111111111111"  # the request_id inside the analysis snapshot
SNAPSHOT = (
    Path(__file__).resolve().parents[1] / "orchestrator" / "data" / "colorful-2002.analysis.json"
)
ANALYSIS = BlueprintAnalysis.model_validate_json(SNAPSHOT.read_text(encoding="utf-8"))
PLAN = ValidationResult(  # colorful-2002 is 855 x 745 px
    request_id=RID,
    is_valid=True,
    reason=ValidationReason.OK,
    confidence=1.0,
    input_format=InputFormat.PNG,
    provider="fake",
    plan_image=PlanImage(image_png=b"png", width_px=855, height_px=745),
    ifc_bytes=None,
    ifc_schema=None,
)
BEDROOMS = [r.id for r in ANALYSIS.rooms if r.room_type.value == "BEDROOM"]
DOORS = [o.id for o in ANALYSIS.openings if o.kind == "DOOR"]


def answer(
    value: float | None = 2.0,
    unit: str = "count",
    status: AnswerStatus = AnswerStatus.ANSWERED,
    evidence: list[str] | None = None,
    language: str = "en",
    explanation: str = "Number of matching elements (bedroom): 2.",
) -> Answer:
    return Answer(
        request_id=RID,
        status=status,
        value=value,
        unit=unit,  # type: ignore[arg-type]
        confidence=0.9,
        evidence=BEDROOMS if evidence is None else evidence,
        explanation=explanation,
        language=language,
    )


def trace(result: Answer | ErrorEnvelope, with_analysis: bool = True) -> PipelineTrace:
    stages: list[tuple[Stage, Any]] = [(Stage.VALIDATION, PLAN)]
    if with_analysis:
        stages.append((Stage.ANALYSIS, ANALYSIS))
    return PipelineTrace(result=result, stages=stages)


class FakeRun:
    def __init__(self) -> None:
        self.requests: list[PipelineRequest] = []
        self.trace = trace(answer())

    def __call__(self, request: PipelineRequest) -> PipelineTrace:
        self.requests.append(request)
        return self.trace


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeRun:
    stub = FakeRun()
    monkeypatch.setattr(server, "run_traced", stub)
    return stub


@pytest.fixture
def client(fake: FakeRun) -> TestClient:
    return TestClient(server.create_app())


def post(
    client: TestClient,
    question: str = "How many bedrooms?",
    name: str = "plan.jpg",
    data: bytes = b"\xff\xd8 jpeg",
    **extra: Any,
) -> Any:
    form = {"question": question, **extra.pop("form", {})}
    return client.post("/ask", data=form, files={"image": (name, data, "image/jpeg")}, **extra)


# --------------------------------------------------------------------------- happy paths


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_count_answer_in_the_apps_format(client: TestClient, fake: FakeRun) -> None:
    r = post(client)
    assert r.status_code == 200
    body = r.json()
    assert (body["answer"], body["unit"], body["type"]) == (2.0, "count", "count")
    assert body["working"] == "Number of matching elements (bedroom): 2."
    assert body["status"] == "ANSWERED" and body["request_id"] == RID
    # room type + the OCR text inside the room ("MH" = makuuhuone)
    assert [e["label"] for e in body["evidence"]] == ["Bedroom (MH)", "Bedroom (MH)"]
    assert len(body["evidence"]) == len(BEDROOMS) == 2
    for e in body["evidence"]:
        assert 0 <= e["x"] <= 1 and 0 <= e["y"] <= 1 and 0 < e["w"] <= 1 and 0 < e["h"] <= 1


def test_the_request_is_built_from_the_upload(client: TestClient, fake: FakeRun) -> None:
    post(
        client,
        "Montako makuuhuonetta?",
        name="kuva.PNG",
        data=b"\x89PNG data",
        headers={"Accept-Language": "fi-FI,fi;q=0.9,en;q=0.5"},
    )
    req = fake.requests[0]
    assert (req.input_format, req.filename, req.question) == (
        InputFormat.PNG,
        "kuva.PNG",
        "Montako makuuhuonetta?",
    )
    assert req.input_bytes == b"\x89PNG data" and req.locale_hint == "fi-FI"
    post(client, form={"locale": "de"})
    assert fake.requests[1].locale_hint == "de"  # the form field wins over the header


def test_yes_no_answers_are_words_in_the_question_language(
    client: TestClient, fake: FakeRun
) -> None:
    fake.trace = trace(answer(1.0, "boolean", language="fi", explanation="Kyllä: ... (sauna)."))
    body = post(client, "Onko saunaa?").json()
    assert (body["answer"], body["unit"], body["type"], body["value"]) == (
        "Kyllä",
        None,
        "boolean",
        1.0,
    )
    fake.trace = trace(answer(0.0, "boolean", language="de", evidence=[]))
    assert post(client).json()["answer"] == "Nein"
    fake.trace = trace(answer(1.0, "boolean", language="sv"))
    assert post(client).json()["answer"] == "Yes"


def test_measures_get_display_units(client: TestClient, fake: FakeRun) -> None:
    fake.trace = trace(answer(12.5, "m2", evidence=[]))
    body = post(client).json()
    assert (body["answer"], body["unit"], body["type"]) == (12.5, "m²", "area")


@pytest.mark.parametrize(
    "status",
    [
        AnswerStatus.CANNOT_ANSWER,
        AnswerStatus.NEEDS_CLARIFICATION,
        AnswerStatus.UNSUPPORTED_QUESTION,
    ],
)
def test_answers_without_a_value_become_text(
    client: TestClient, fake: FakeRun, status: AnswerStatus
) -> None:
    fake.trace = trace(answer(None, "m2", status=status, evidence=[], explanation="Scale unknown."))
    r = post(client)
    assert r.status_code == 200  # the app shows it as the answer, not as a failure
    body = r.json()
    assert (body["answer"], body["type"], body["unit"], body["evidence"]) == (
        "Scale unknown.",
        "text",
        None,
        [],
    )
    assert body["status"] == status.value


# --------------------------------------------------------------------------- errors


@pytest.mark.parametrize(("retryable", "code"), [(True, 503), (False, 500)])
def test_pipeline_errors_are_user_safe(
    client: TestClient, fake: FakeRun, retryable: bool, code: int
) -> None:
    env = ErrorEnvelope(
        request_id=RID,
        stage=Stage.ANALYSIS,
        code="MODEL_LOAD_FAILED",
        message="The plan recognition model is not available.",
        retryable=retryable,
        details={"reason": "C:/secret/path"},
    )
    fake.trace = trace(env, with_analysis=False)
    r = post(client)
    assert r.status_code == code
    assert r.json() == {
        "error": "The plan recognition model is not available.",
        "code": "MODEL_LOAD_FAILED",
    }
    assert "secret" not in r.text


def test_bad_uploads(client: TestClient, fake: FakeRun) -> None:
    r = post(client, "   ")
    assert (r.status_code, "question" in r.json()["error"]) == (400, True)
    r = client.post(
        "/ask", data={"question": "q"}, files={"image": ("plan.gif", b"GIF89a", "image/gif")}
    )
    assert r.status_code == 415 and "PNG, JPEG or PDF" in r.json()["error"]
    assert post(client, data=b"").status_code == 400
    r = client.post("/ask", data={"question": "q"})  # no image at all
    assert r.status_code == 400 and "error" in r.json()
    assert fake.requests == []


def test_upload_limit_from_config(monkeypatch: pytest.MonkeyPatch, fake: FakeRun) -> None:
    monkeypatch.setattr(server, "load_section", lambda _name: {"max_upload_bytes": 4})
    c = TestClient(server.create_app())
    assert post(c, data=b"12345").status_code == 413
    assert post(c, data=b"1234").status_code == 200


# --------------------------------------------------------------------------- helpers


def test_declared_format_and_language_helpers() -> None:
    assert server.declared_format("a.jpeg", None) is InputFormat.JPEG
    assert server.declared_format("blob", "image/png; charset=x") is InputFormat.PNG
    assert server.declared_format(None, "application/pdf") is InputFormat.PDF
    assert server.declared_format("x.ifc", "application/octet-stream") is InputFormat.IFC
    assert server.declared_format("x.heic", "image/heic") is None
    assert server.first_language("de-AT, en;q=0.5") == "de-AT"
    assert server.first_language("*") is None and server.first_language(None) is None


def test_point_evidence_is_a_square_around_the_position() -> None:
    door = next(o for o in ANALYSIS.openings if o.id == DOORS[0])
    (box,) = mobile.evidence_boxes([door.id], trace(answer()), point_size=0.04)
    side = 0.04 * 745  # px: 4 % of the shorter image side; door_1 lies well inside the image
    cx, cy = door.position
    assert box == pytest.approx(
        {
            "label": "Door",
            "x": (cx - side / 2) / 855,
            "y": (cy - side / 2) / 745,
            "w": side / 855,
            "h": side / 745,
        }
    )


def test_boxes_are_clamped_to_the_image() -> None:
    edge = ANALYSIS.model_copy(
        update={"openings": [ANALYSIS.openings[0].model_copy(update={"position": (0.0, 745.0)})]}
    )
    t = PipelineTrace(result=answer(), stages=[(Stage.VALIDATION, PLAN), (Stage.ANALYSIS, edge)])
    (box,) = mobile.evidence_boxes([edge.openings[0].id], t, 0.04)
    assert box["x"] == 0.0 and box["y"] + box["h"] == pytest.approx(1.0)
    assert 0 < box["w"] < 0.04 and 0 < box["h"] < 0.04  # only the part inside the image


def test_no_boxes_without_a_raster_analysis() -> None:
    assert mobile.evidence_boxes(BEDROOMS, trace(answer(), with_analysis=False), 0.04) == []
    metric = ANALYSIS.model_copy(update={"coordinate_space": "METRIC"})
    t = PipelineTrace(result=answer(), stages=[(Stage.VALIDATION, PLAN), (Stage.ANALYSIS, metric)])
    assert mobile.evidence_boxes(BEDROOMS, t, 0.04) == []
    assert mobile.evidence_boxes(["unknown_1"], trace(answer()), 0.04) == []
