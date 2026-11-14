"""Orchestrator phases 4 and 5: A2 || A3 concurrently, then A4 computes the number."""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

import pytest
from orch_fakes import RID, envelope, make_request, parsed, validation

from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    EntityRef,
    ErrorEnvelope,
    FixtureType,
    Intent,
    ParsedQuestion,
    RoomType,
    Stage,
    ValidationResult,
)
from blueprint_qa.orchestrator import pipeline
from blueprint_qa.orchestrator.pipeline import INTERIM_TEXTS, Components, run_traced
from blueprint_qa.reasoning import answer

DATA = Path(__file__).resolve().parent / "data"


def snapshot(name: str = "colorful-2002") -> BlueprintAnalysis:
    """A3's real output for a recorded CubiCasa plan (see data/README.md)."""
    return BlueprintAnalysis.model_validate_json(
        (DATA / f"{name}.analysis.json").read_text(encoding="utf-8")
    )


class Fake:
    """Fake component: records its arguments, returns a preset result or raises."""

    def __init__(self, result: object = None, exc: Exception | None = None) -> None:
        self.result, self.exc = result, exc
        self.calls: list[tuple[Any, ...]] = []

    def __call__(self, *args: Any) -> Any:
        self.calls.append(args)
        if self.exc is not None:
            raise self.exc
        return self.result


def question(*targets: EntityRef, **kw: Any) -> ParsedQuestion:
    pq = parsed(**kw)
    return pq.model_copy(update={"targets": list(targets)}) if targets else pq


def run(
    a2: object = None, a3: object = None, a4: object = answer, a1: object = None
) -> tuple[pipeline.PipelineTrace, dict[str, Fake]]:
    fakes = {
        "a1": a1 if isinstance(a1, Fake) else Fake(a1 if a1 is not None else validation()),
        "a2": a2 if isinstance(a2, Fake) else Fake(a2 if a2 is not None else parsed()),
        "a3": a3 if isinstance(a3, Fake) else Fake(a3 if a3 is not None else snapshot()),
    }
    reason = a4 if (a4 is None or isinstance(a4, Fake) or a4 is answer) else Fake(a4)
    comps = Components(
        validate=fakes["a1"], interpret=fakes["a2"], analyze=fakes["a3"], reason=reason
    )
    return run_traced(make_request(), comps), fakes


# --------------------------------------------------------------------------- full chain


@pytest.mark.parametrize(
    ("target", "expected"),
    [
        (EntityRef(category="ROOM", room_type=RoomType.BEDROOM), 2.0),
        (EntityRef(category="ROOM", room_type=RoomType.SAUNA), 1.0),
        (EntityRef(category="WINDOW"), 4.0),
        (EntityRef(category="DOOR"), 7.0),
        (EntityRef(category="FIXTURE", fixture_type=FixtureType.SINK), 2.0),
        (EntityRef(category="ROOM", room_type=RoomType.TOILET), 0.0),  # covered zero
    ],
)
def test_real_a4_counts_on_a3_output(target: EntityRef, expected: float) -> None:
    trace, _ = run(a2=question(target))
    result = trace.result
    assert isinstance(result, Answer)
    assert (result.status, result.value, result.unit) == (AnswerStatus.ANSWERED, expected, "count")


def test_two_storey_plan_and_fixture_sum() -> None:
    shower_tub = question(
        EntityRef(category="FIXTURE", fixture_type=FixtureType.SHOWER),
        EntityRef(category="FIXTURE", fixture_type=FixtureType.BATHTUB),
    )
    result = run(a2=shower_tub, a3=snapshot("colorful-11397"))[0].result
    assert isinstance(result, Answer) and result.value == 3.0
    storeys = run(a2=question(EntityRef(category="STOREY")), a3=snapshot("colorful-11397"))
    assert isinstance(storeys[0].result, Answer) and storeys[0].result.value == 2.0


def test_uncovered_room_type_is_never_zero() -> None:
    result = run(a2=question(EntityRef(category="ROOM", room_type=RoomType.LIVING_ROOM)))[0]
    assert isinstance(result.result, Answer)
    assert result.result.status is AnswerStatus.CANNOT_ANSWER and result.result.value is None


def test_a4_handles_unsupported_and_clarification_when_the_plan_is_analysed() -> None:
    unsupported = run(a2=parsed(intent=Intent.UNSUPPORTED, language="de"))[0].result
    assert isinstance(unsupported, Answer)
    assert unsupported.status is AnswerStatus.UNSUPPORTED_QUESTION
    assert unsupported.language == "de"  # worded by A4, not the orchestrator's English text
    clar = run(a2=parsed(clarification="Mikä huone?", language="fi"))[0].result
    assert isinstance(clar, Answer) and clar.status is AnswerStatus.NEEDS_CLARIFICATION


def test_stage_order_and_arguments() -> None:
    trace, fakes = run()
    assert [s for s, _ in trace.stages] == [
        Stage.VALIDATION,
        Stage.QUESTION,
        Stage.ANALYSIS,
        Stage.REASONING,
    ]
    (a3_arg,) = fakes["a3"].calls[0]
    assert isinstance(a3_arg, ValidationResult)  # never the raw upload (§6 A0)
    assert a3_arg.plan_image is not None


def test_a2_and_a3_run_concurrently() -> None:
    barrier = threading.Barrier(2, timeout=10)

    class Waiting(Fake):
        def __call__(self, *args: Any) -> Any:
            barrier.wait()  # raises BrokenBarrierError unless both stages run at the same time
            return super().__call__(*args)

    trace, _ = run(a2=Waiting(parsed()), a3=Waiting(snapshot()))
    assert isinstance(trace.result, Answer)
    assert trace.result.status is AnswerStatus.ANSWERED


def test_invalid_picture_calls_neither_a2_nor_a3() -> None:
    trace, fakes = run(a1=validation(is_valid=False))
    assert isinstance(trace.result, Answer)
    assert trace.result.explanation == INTERIM_TEXTS["invalid_input"]
    assert fakes["a2"].calls == [] and fakes["a3"].calls == []


# --------------------------------------------------------------------------- A3 errors


def test_a3_error_is_returned_even_if_a2_succeeded() -> None:
    a4 = Fake(None)
    env = envelope(Stage.ANALYSIS, "MODEL_LOAD_FAILED")
    trace, _ = run(a3=env, a4=a4)
    assert trace.result == env
    assert a4.calls == []


def test_without_analysis_unsupported_and_clarification_are_still_answered() -> None:
    env = envelope(Stage.ANALYSIS, "ANALYSIS_FAILED")
    unsupported = run(a2=parsed(intent=Intent.UNSUPPORTED), a3=env)[0].result
    assert isinstance(unsupported, Answer)
    assert unsupported.explanation == INTERIM_TEXTS["unsupported_question"]
    clar = run(a2=parsed(clarification="Which room?"), a3=env)[0].result
    assert isinstance(clar, Answer) and clar.explanation == "Which room?"


def test_a2_error_wins_over_everything() -> None:
    env = envelope(Stage.QUESTION, "LLM_OUTPUT_INVALID")
    a4 = Fake(None)
    trace, _ = run(a2=env, a3=envelope(Stage.ANALYSIS), a4=a4)
    assert trace.result == env and a4.calls == []


def test_raising_a3_becomes_internal_error() -> None:
    result = run(a3=Fake(exc=RuntimeError("boom")))[0].result
    assert isinstance(result, ErrorEnvelope)
    assert (result.code, result.stage) == ("INTERNAL_ERROR", Stage.ANALYSIS)


def test_a3_with_changed_request_id_is_a_violation() -> None:
    other = snapshot().model_copy(update={"request_id": "other"})
    result = run(a3=other)[0].result
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "INVALID_INPUT" and result.details["producer"] == "ANALYSIS"


# --------------------------------------------------------------------------- A4 checks


def test_a4_error_envelope_is_returned() -> None:
    env = envelope(Stage.REASONING, "REASONING_FAILED")
    assert run(a4=Fake(env))[0].result == env


def test_raising_a4_becomes_internal_error() -> None:
    result = run(a4=Fake(exc=ValueError("x")))[0].result
    assert isinstance(result, ErrorEnvelope)
    assert (result.code, result.stage) == ("INTERNAL_ERROR", Stage.REASONING)


@pytest.mark.parametrize(
    ("status", "value"),
    [(AnswerStatus.ANSWERED, None), (AnswerStatus.CANNOT_ANSWER, 3.0)],
)
def test_a4_value_status_mismatch_is_a_violation(status: AnswerStatus, value: float | None) -> None:
    bad = Answer(
        request_id=RID,
        status=status,
        value=value,
        unit="count",
        confidence=0.5,
        evidence=[],
        explanation="x",
        language="en",
    )
    result = run(a4=Fake(bad))[0].result
    assert isinstance(result, ErrorEnvelope)
    assert result.details == {"producer": "REASONING", "violation": "ValueError"}


def test_skipped_stages_give_interim_answers() -> None:
    no_a4 = run(a4=None)[0].result
    assert isinstance(no_a4, Answer)
    assert no_a4.explanation == INTERIM_TEXTS["reasoning_unavailable"]
    comps = Components(validate=Fake(validation()), interpret=Fake(parsed()), analyze=None)
    no_a3 = run_traced(make_request(), comps).result
    assert isinstance(no_a3, Answer)
    assert no_a3.explanation == INTERIM_TEXTS["analysis_unavailable"]


def test_one_log_event_per_stage(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, Stage, str]] = []
    monkeypatch.setattr(
        pipeline,
        "log_event",
        lambda _l, event, **kw: events.append((event, kw["stage"], kw.get("outcome", ""))),
    )
    run()
    stages = sorted((s.value, o) for e, s, o in events if e == "stage_done")
    assert stages == [
        ("ANALYSIS", "analysed"),
        ("QUESTION", "parsed"),
        ("REASONING", "ANSWERED"),
        ("VALIDATION", "valid"),
    ]
