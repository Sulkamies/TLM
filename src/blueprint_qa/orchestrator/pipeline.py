"""Pipeline orchestration (AGENTS.md §6 A0). Custodian: A0.

``run(request) -> Answer | ErrorEnvelope`` is the only public entry point.

Stage order (``STAGE_ORDER``)::

    1. VALIDATION  A1 validate()          is_valid=False -> stop (R5.2); A2/A3 are not called
    2. QUESTION    A2 interpret()      ┐  run concurrently (MERGE_PLAN phase 4);
       ANALYSIS    A3 analyze()        ┘  A3 gets the ValidationResult, never the raw upload
    3. REASONING   A4 answer()            computes the number (phase 5)

The orchestrator never produces a number itself: only A4 does. It returns an
*interim answer* without a number (``INTERIM_TEXTS``) only when a stage stops the
pipeline early. This module contains no image, NLP, IFC or calculation logic: it
calls the component entry points, checks their outputs against the contracts, and
never lets an exception escape (R5.1).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from blueprint_qa.analysis import analyze
from blueprint_qa.common.log import get_logger, log_event
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    ErrorEnvelope,
    InputFormat,
    Intent,
    ParsedQuestion,
    PipelineRequest,
    Stage,
    ValidationResult,
)
from blueprint_qa.question import interpret
from blueprint_qa.reasoning import answer
from blueprint_qa.validation import validate

ValidateFn = Callable[[PipelineRequest], ValidationResult | ErrorEnvelope]
InterpretFn = Callable[[str, str, str | None], ParsedQuestion | ErrorEnvelope]
AnalyzeFn = Callable[[ValidationResult], BlueprintAnalysis | ErrorEnvelope]
ReasonFn = Callable[[ParsedQuestion, BlueprintAnalysis], Answer | ErrorEnvelope]

# The stage steps in order. Stages in one tuple run concurrently.
STAGE_ORDER: tuple[tuple[Stage, ...], ...] = (
    (Stage.VALIDATION,),
    (Stage.QUESTION, Stage.ANALYSIS),
    (Stage.REASONING,),
)

# Fixed texts of the interim answers (used only when a stage stops the pipeline early). English.
INTERIM_TEXTS: dict[str, str] = {
    "invalid_input": "This picture is invalid for our program",
    "unsupported_question": "This question cannot be answered with a number.",
    "analysis_unavailable": "Plan analysis is not available yet.",
    "reasoning_unavailable": "Answer computation is not available yet.",
}
INTERIM_LANGUAGE = "en"
# Answer.unit is required even when value is None. A4 sets the intent's unit (OPEN_QUESTIONS Q9,
# option c); the orchestrator's own interim answers keep this placeholder.
PLACEHOLDER_UNIT = "count"

_logger = get_logger(__name__)
_T = TypeVar("_T", bound=BaseModel)


@dataclass(frozen=True)
class Components:
    """The component entry points the pipeline calls. Tests replace them with fakes."""

    validate: ValidateFn = validate
    interpret: InterpretFn = interpret
    analyze: AnalyzeFn | None = analyze  # None = stage skipped (interim answer)
    reason: ReasonFn | None = answer  # None = stage skipped (interim answer)


@dataclass
class PipelineTrace:
    """The final result plus each stage's (contract-checked) output, for ``--debug``."""

    result: Answer | ErrorEnvelope
    stages: list[tuple[Stage, BaseModel]] = field(default_factory=list)


def new_request(
    input_bytes: bytes,
    input_format: InputFormat,
    question: str,
    *,
    filename: str | None = None,
    locale_hint: str | None = None,
) -> PipelineRequest:
    """Build a request with a fresh UUID4 ``request_id`` and ``received_at`` (§6 A0)."""
    return PipelineRequest(
        request_id=str(uuid.uuid4()),
        input_bytes=input_bytes,
        input_format=input_format,
        filename=filename,
        question=question,
        locale_hint=locale_hint,
        received_at=datetime.now(UTC),
    )


def run(request: PipelineRequest) -> Answer | ErrorEnvelope:
    """Answer one question about one plan. Never raises (R5.1)."""
    return run_traced(request).result


def run_traced(request: PipelineRequest, components: Components | None = None) -> PipelineTrace:
    """Like :func:`run`, but also returns every stage output. Never raises."""
    comps = components or Components()
    request_id = str(getattr(request, "request_id", "") or "unknown")
    trace = PipelineTrace(result=_interim(request_id, AnswerStatus.CANNOT_ANSWER, ""))
    try:
        trace.result = _run(request, comps, trace)
    except Exception as exc:  # last line of defence; each stage is guarded as well
        trace.result = _envelope(request_id, "INTERNAL_ERROR", Stage.ORCHESTRATOR, exc)
    _log(request_id, Stage.ORCHESTRATOR, "pipeline_done", trace.result, 0.0)
    return trace


# --------------------------------------------------------------------------- internals


def _run(
    request: PipelineRequest, comps: Components, trace: PipelineTrace
) -> Answer | ErrorEnvelope:
    try:
        request = PipelineRequest.model_validate(request.model_dump())
    except (ValidationError, AttributeError) as exc:
        return _violation(
            str(getattr(request, "request_id", "") or "unknown"), Stage.ORCHESTRATOR, exc
        )
    rid = request.request_id

    # 1. VALIDATION (A1)
    validation = _call(
        Stage.VALIDATION, rid, ValidationResult, trace, lambda: comps.validate(request)
    )
    if isinstance(validation, ErrorEnvelope):
        return validation
    if not validation.is_valid:  # R5.2: an invalid input is not an error, and A2 is not called
        return _interim(rid, AnswerStatus.CANNOT_ANSWER, INTERIM_TEXTS["invalid_input"])

    # 2. QUESTION (A2) || ANALYSIS (A3), concurrently. Recorded in a fixed order for --debug.
    def ask() -> ParsedQuestion | ErrorEnvelope:
        return _invoke(
            Stage.QUESTION,
            rid,
            ParsedQuestion,
            lambda: comps.interpret(rid, request.question, request.locale_hint),
        )

    analyze_fn = comps.analyze
    analysis: BlueprintAnalysis | ErrorEnvelope | None = None
    if analyze_fn is None:
        question = ask()
    else:
        with ThreadPoolExecutor(max_workers=2, thread_name_prefix=f"bp-{rid[:8]}") as pool:
            q_future = pool.submit(ask)
            a_future = pool.submit(
                _invoke, Stage.ANALYSIS, rid, BlueprintAnalysis, lambda: analyze_fn(validation)
            )
            question, analysis = q_future.result(), a_future.result()
    trace.stages.append((Stage.QUESTION, question))
    if analysis is not None:
        trace.stages.append((Stage.ANALYSIS, analysis))
    if isinstance(question, ErrorEnvelope):
        return question

    # Without a usable analysis, questions that need no plan are still answered.
    if not isinstance(analysis, BlueprintAnalysis):
        if question.intent is Intent.UNSUPPORTED:
            return _interim(
                rid, AnswerStatus.UNSUPPORTED_QUESTION, INTERIM_TEXTS["unsupported_question"]
            )
        if question.clarification_needed:
            return _interim(
                rid,
                AnswerStatus.NEEDS_CLARIFICATION,
                question.clarification_needed,
                language=question.language,
            )
        if isinstance(analysis, ErrorEnvelope):  # an A3 error is returned even if A2 succeeded
            return analysis
        return _interim(rid, AnswerStatus.CANNOT_ANSWER, INTERIM_TEXTS["analysis_unavailable"])

    # 3. REASONING (A4): the only place a number is produced.
    reason_fn = comps.reason
    if reason_fn is None:
        return _interim(rid, AnswerStatus.CANNOT_ANSWER, INTERIM_TEXTS["reasoning_unavailable"])
    plan = analysis
    return _call(Stage.REASONING, rid, Answer, trace, lambda: reason_fn(question, plan))


def _call(
    stage: Stage,
    rid: str,
    expected: type[_T],
    trace: PipelineTrace,
    fn: Callable[[], object],
) -> _T | ErrorEnvelope:
    """:func:`_invoke` plus recording the output in the trace."""
    result = _invoke(stage, rid, expected, fn)
    trace.stages.append((stage, result))
    return result


def _invoke(
    stage: Stage, rid: str, expected: type[_T], fn: Callable[[], object]
) -> _T | ErrorEnvelope:
    """Call one component, contract-check its output, log one event, never raise.

    Thread-safe: it touches no shared state, so A2 and A3 can run it concurrently.
    """
    start = time.perf_counter()
    try:
        raw = fn()
    except Exception as exc:  # R5.1: components must not raise; contain it if one does
        result: _T | ErrorEnvelope = _envelope(rid, "INTERNAL_ERROR", stage, exc)
    else:
        result = _checked(raw, expected, stage, rid)
    _log(rid, stage, "stage_done", result, (time.perf_counter() - start) * 1000)
    return result


def _checked(raw: object, expected: type[_T], stage: Stage, rid: str) -> _T | ErrorEnvelope:
    """Re-validate a component output against its contract and check the request_id (§6 A0)."""
    model: type[BaseModel] | None = next(
        (m for m in (expected, ErrorEnvelope) if isinstance(raw, m)), None
    )
    if model is None:
        return _violation(rid, stage, TypeError(type(raw).__name__))
    try:
        checked = model.model_validate(raw.model_dump())  # type: ignore[attr-defined]
    except ValidationError as exc:
        return _violation(rid, stage, exc)
    if getattr(checked, "request_id", None) != rid:
        return _violation(rid, stage, ValueError("request_id changed"))
    if isinstance(checked, Answer) and (checked.value is None) == (
        checked.status is AnswerStatus.ANSWERED
    ):  # §4.2 invariant: value is non-null iff status == ANSWERED
        return _violation(rid, stage, ValueError("value/status mismatch"))
    if isinstance(checked, ErrorEnvelope):
        return checked
    assert isinstance(checked, expected)
    return checked


def _violation(rid: str, producer: Stage, exc: Exception) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=rid,
        stage=Stage.ORCHESTRATOR,
        code="INVALID_INPUT",
        message="An internal component returned invalid data. Please try again later.",
        retryable=False,
        details={"producer": producer.value, "violation": type(exc).__name__},
    )


def _envelope(rid: str, code: str, stage: Stage, exc: Exception) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=rid,
        stage=stage,
        code=code,
        message="An internal error occurred. Please try again later.",
        retryable=False,
        details={"producer": stage.value, "exception": type(exc).__name__},
    )


def _interim(
    rid: str, status: AnswerStatus, text: str, *, language: str = INTERIM_LANGUAGE
) -> Answer:
    return Answer(
        request_id=rid,
        status=status,
        value=None,  # the orchestrator never produces a number
        unit=PLACEHOLDER_UNIT,
        confidence=0.0,
        evidence=[],
        explanation=text,
        language=language,
    )


def _log(rid: str, stage: Stage, event: str, result: BaseModel, latency_ms: float) -> None:
    fields: dict[str, object] = {"latency_ms": round(latency_ms, 1)}
    if isinstance(result, ErrorEnvelope):
        fields.update(outcome="error", code=result.code, producer=result.details.get("producer"))
    elif isinstance(result, ValidationResult):
        fields.update(outcome="valid" if result.is_valid else "invalid", reason=result.reason.value)
    elif isinstance(result, ParsedQuestion):
        fields.update(outcome="parsed", intent=result.intent.value, language=result.language)
    elif isinstance(result, BlueprintAnalysis):
        fields.update(
            outcome="analysed",
            storeys=len(result.storeys),
            rooms=len(result.rooms),
            openings=len(result.openings),
            fixtures=len(result.fixtures),
        )
    elif isinstance(result, Answer):
        fields.update(outcome=result.status.value)
    level = logging.WARNING if isinstance(result, ErrorEnvelope) else logging.INFO
    log_event(_logger, event, request_id=rid, stage=stage, level=level, **fields)
