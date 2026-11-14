"""Orchestrator pipeline (MERGE_PLAN phase 1): A1 -> A2, interim answers, contract checks."""

from __future__ import annotations

import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from orch_fakes import RID, envelope, make_request, parsed, validation

from blueprint_qa import orchestrator
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    ErrorEnvelope,
    InputFormat,
    Intent,
    ParsedQuestion,
    PipelineRequest,
    Stage,
    ValidationResult,
)
from blueprint_qa.orchestrator import pipeline
from blueprint_qa.orchestrator.pipeline import (
    INTERIM_TEXTS,
    STAGE_ORDER,
    Components,
    run_traced,
)
from blueprint_qa.question import interpret
from blueprint_qa.validation import validate

SRC = Path(__file__).resolve().parents[3] / "src" / "blueprint_qa"


class Recorder:
    """Fake component that records its calls."""

    def __init__(self, result: object = None, exc: Exception | None = None) -> None:
        self.result, self.exc, self.calls = result, exc, 0

    def __call__(self, *args: Any) -> Any:
        self.calls += 1
        if self.exc is not None:
            raise self.exc
        return self.result


def comps(a1: object, a2: object = None) -> tuple[Components, Recorder, Recorder]:
    v = a1 if isinstance(a1, Recorder) else Recorder(a1)
    q = a2 if isinstance(a2, Recorder) else Recorder(a2)
    return Components(validate=v, interpret=q), v, q


def run(c: Components, question: str = "How many bedrooms?") -> Answer | ErrorEnvelope:
    return run_traced(make_request(question), c).result


# --------------------------------------------------------------------------- happy paths


def test_invalid_picture_gives_exactly_the_fixed_text_and_skips_a2() -> None:
    c, v, q = comps(validation(is_valid=False), parsed())
    result = run(c)
    assert isinstance(result, Answer)
    assert result.explanation == "This picture is invalid for our program"
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.value is None and result.language == "en"
    assert (v.calls, q.calls) == (1, 0)  # R5.2: A2 is not called


def test_valid_plan_and_parsed_question_give_analysis_unavailable() -> None:
    c, v, q = comps(validation(), parsed())
    result = run(c)
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.explanation == INTERIM_TEXTS["analysis_unavailable"]
    assert result.explanation == "Plan analysis is not available yet."
    assert (v.calls, q.calls) == (1, 1)


def test_unsupported_question() -> None:
    c, _, _ = comps(validation(), parsed(intent=Intent.UNSUPPORTED))
    result = run(c, "Where is the kitchen?")
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.UNSUPPORTED_QUESTION
    assert result.explanation == INTERIM_TEXTS["unsupported_question"]


def test_clarification_uses_a2_text_and_language() -> None:
    c, _, _ = comps(validation(), parsed(clarification="Mikä huone?", language="fi"))
    result = run(c, "Kuinka iso se on?")
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.NEEDS_CLARIFICATION
    assert (result.explanation, result.language) == ("Mikä huone?", "fi")


def test_unsupported_wins_over_clarification() -> None:
    c, _, _ = comps(validation(), parsed(intent=Intent.UNSUPPORTED, clarification="?"))
    result = run(c)
    assert isinstance(result, Answer)
    assert result.status is AnswerStatus.UNSUPPORTED_QUESTION


def test_the_orchestrator_never_produces_a_number() -> None:
    cases = [
        (validation(False), parsed()),
        (validation(), parsed()),
        (validation(), parsed(intent=Intent.UNSUPPORTED)),
        (validation(), parsed(clarification="?")),
    ]
    for a1, a2 in cases:
        result = run(comps(a1, a2)[0])
        assert isinstance(result, Answer)
        assert result.value is None and result.request_id == RID
        assert result.unit == "count" and result.evidence == []


def test_trace_holds_each_stage_output() -> None:
    trace = run_traced(make_request(), comps(validation(), parsed())[0])
    assert [stage for stage, _ in trace.stages] == [Stage.VALIDATION, Stage.QUESTION]
    assert isinstance(trace.stages[0][1], ValidationResult)
    assert isinstance(trace.stages[1][1], ParsedQuestion)


# --------------------------------------------------------------------------- errors


def test_a1_error_envelope_is_returned_and_a2_skipped() -> None:
    env = envelope(Stage.VALIDATION)
    c, _, q = comps(env, parsed())
    assert run(c) == env
    assert q.calls == 0


def test_a2_error_envelope_is_returned() -> None:
    env = envelope(Stage.QUESTION, "LLM_OUTPUT_INVALID")
    assert run(comps(validation(), env)[0]) == env


@pytest.mark.parametrize("stage", [Stage.VALIDATION, Stage.QUESTION])
def test_a_raising_component_becomes_internal_error(stage: Stage) -> None:
    boom = Recorder(exc=RuntimeError("secret detail"))
    c = comps(boom, parsed())[0] if stage is Stage.VALIDATION else comps(validation(), boom)[0]
    result = run(c)
    assert isinstance(result, ErrorEnvelope)
    assert (result.code, result.stage) == ("INTERNAL_ERROR", stage)
    assert result.details == {"producer": stage.value, "exception": "RuntimeError"}
    assert "secret detail" not in result.message


def test_changed_request_id_is_a_contract_violation() -> None:
    other = str(uuid.uuid4())
    result = run(comps(validation(), parsed(rid=other))[0])
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "INVALID_INPUT" and result.stage is Stage.ORCHESTRATOR
    assert result.details["producer"] == "QUESTION"


def test_wrong_type_is_a_contract_violation() -> None:
    result = run(comps({"is_valid": True}, parsed())[0])
    assert isinstance(result, ErrorEnvelope)
    assert result.code == "INVALID_INPUT"
    assert result.details == {"producer": "VALIDATION", "violation": "TypeError"}


def test_unvalidated_model_is_rechecked_against_the_contract() -> None:
    bad = validation().model_copy(update={"confidence": 2.0})  # skips validation
    c, _, q = comps(bad, parsed())
    result = run(c)
    assert isinstance(result, ErrorEnvelope)
    assert result.details == {"producer": "VALIDATION", "violation": "ValidationError"}
    assert q.calls == 0


def test_invalid_request_is_rejected_by_the_orchestrator() -> None:
    bad = PipelineRequest.model_construct(**{**make_request().model_dump(), "question": ""})
    result = run_traced(bad, comps(validation(), parsed())[0]).result
    assert isinstance(result, ErrorEnvelope)
    assert result.details["producer"] == "ORCHESTRATOR"


def test_unexpected_failure_inside_the_orchestrator_is_contained(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(*_: Any) -> Any:
        raise KeyError("x")

    monkeypatch.setattr(pipeline, "_run", broken)
    result = run_traced(make_request(), comps(validation(), parsed())[0]).result
    assert isinstance(result, ErrorEnvelope)
    assert (result.code, result.stage) == ("INTERNAL_ERROR", Stage.ORCHESTRATOR)


# --------------------------------------------------------------------------- logging


def test_one_log_event_per_stage_without_question_text(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[tuple[str, dict[str, Any]]] = []
    monkeypatch.setattr(pipeline, "log_event", lambda _l, event, **kw: events.append((event, kw)))
    run(comps(validation(), parsed())[0], "How many bedrooms in Villa Secret?")
    assert [(e, kw["stage"]) for e, kw in events] == [
        ("stage_done", Stage.VALIDATION),
        ("stage_done", Stage.QUESTION),
        ("pipeline_done", Stage.ORCHESTRATOR),
    ]
    assert all(kw["request_id"] == RID for _, kw in events)
    assert "Villa Secret" not in repr(events)


# --------------------------------------------------------------------------- structure


def test_new_request_generates_uuid4_and_utc_time() -> None:
    req = orchestrator.new_request(b"x", InputFormat.PDF, "q?", filename="a.pdf", locale_hint="de")
    assert uuid.UUID(req.request_id).version == 4
    assert req.received_at.tzinfo is not None
    assert (req.filename, req.locale_hint) == ("a.pdf", "de")


def test_default_components_and_empty_slots() -> None:
    c = Components()
    assert c.validate is validate and c.interpret is interpret
    assert c.analyze is None and c.reason is None  # A3 and A4 slots
    assert STAGE_ORDER == (
        (Stage.VALIDATION,),
        (Stage.QUESTION, Stage.ANALYSIS),
        (Stage.REASONING,),
    )


def test_run_uses_default_components(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "Components", lambda: comps(validation(False))[0])
    result = orchestrator.run(make_request())
    assert isinstance(result, Answer)
    assert result.explanation == INTERIM_TEXTS["invalid_input"]


def test_only_the_orchestrator_imports_component_entry_points() -> None:
    """§2.1: only orchestrator may import validation/question/analysis/reasoning."""
    pattern = re.compile(
        r"^\s*(from|import)\s+blueprint_qa\.(validation|question|analysis|reasoning)\b", re.M
    )
    offenders = []
    for path in SRC.rglob("*.py"):
        component = path.relative_to(SRC).parts[0]
        for match in pattern.finditer(path.read_text(encoding="utf-8")):
            if component not in ("orchestrator", match.group(2)):
                offenders.append(f"{path.relative_to(SRC)} imports {match.group(2)}")
    assert offenders == []
