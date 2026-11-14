"""A4 entry point: guards before computing, error envelopes, never raises (R5.1)."""

from __future__ import annotations

import pytest
from reasoning_fakes import RID, analysis, question, ref, room

import blueprint_qa.reasoning as reasoning_pkg
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    ErrorEnvelope,
    Intent,
    RoomType,
    Stage,
)
from blueprint_qa.reasoning import answer, reasoner


def test_package_exports_only_answer() -> None:
    assert reasoning_pkg.__all__ == ["answer"]
    assert reasoning_pkg.answer is reasoner.answer


def test_request_id_mismatch_is_invalid_input() -> None:
    q = question(Intent.COUNT, [ref("ROOM")])
    a = analysis(request_id="00000000-0000-4000-8000-000000000000")
    result = answer(q, a)
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "INVALID_INPUT"
    assert result.stage is Stage.REASONING
    assert result.request_id == RID
    assert result.retryable is False


def test_wrong_input_types_are_invalid_input() -> None:
    result = answer("not a question", analysis())  # type: ignore[arg-type]
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "INVALID_INPUT"
    assert result.request_id == "unknown"


def test_unsupported_intent() -> None:
    q = question(Intent.UNSUPPORTED, [ref("ROOM", room_type=RoomType.KITCHEN)], language="de")
    result = answer(q, analysis())
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.UNSUPPORTED_QUESTION
    assert result.value is None
    assert result.unit == "count"  # placeholder, OPEN_QUESTIONS Q9
    assert result.language == "de"
    assert "Zahl" in result.explanation


def test_clarification_needed_passes_text_through() -> None:
    q = question(
        Intent.AREA,
        [ref("ROOM", room_type=RoomType.BEDROOM)],
        language="fi-FI",
        clarification="Mitä makuuhuonetta tarkoitat?",
        confidence=0.6,
    )
    result = answer(q, analysis(rooms=[room(1, RoomType.BEDROOM, area=12.0)]))
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.NEEDS_CLARIFICATION
    assert result.value is None
    assert result.explanation == "Mitä makuuhuonetta tarkoitat?"
    assert result.language == "fi-FI"
    assert result.unit == "m2"
    assert result.confidence == 0.6
    assert result.evidence == []


def test_unexpected_exception_is_reasoning_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object) -> None:
        raise ZeroDivisionError("boom")

    monkeypatch.setattr(reasoner, "compute", boom)
    result = answer(question(Intent.COUNT, [ref("ROOM")]), analysis())
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "REASONING_FAILED"
    assert result.details == {"exc_type": "ZeroDivisionError"}
    assert "boom" not in result.message


def test_non_finite_value_is_cannot_answer() -> None:
    huge = 1e308
    rooms = [room(1, RoomType.BEDROOM, area=huge), room(2, RoomType.BEDROOM, area=huge)]
    q = question(Intent.AREA, [ref("ROOM", room_type=RoomType.BEDROOM)], requested_unit="ft2")
    result = answer(q, analysis(rooms=rooms))
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.value is None


@pytest.mark.parametrize("intent", list(Intent))
@pytest.mark.parametrize("targets", [[], [ref("WALL")], [ref("ROOM"), ref("STOREY")]])
def test_never_raises_and_value_iff_answered(intent: Intent, targets: list[object]) -> None:
    q = question(intent, targets)  # type: ignore[arg-type]
    for a in (analysis(), analysis(rooms=[room(1, RoomType.KITCHEN, area=9.0)], warnings=[])):
        result = answer(q, a)
        assert isinstance(result, Answer | ErrorEnvelope)
        if isinstance(result, Answer):
            assert (result.value is not None) == (result.status is AnswerStatus.ANSWERED)
            Answer.model_validate(result.model_dump())
