"""Pipeline orchestration (AGENTS.md §6 A0). Custodian: A0.

``run(request) -> Answer | ErrorEnvelope`` is the only public entry point.

Stage order (``STAGE_ORDER``)::

    1. VALIDATION  A1 validate()          is_valid=False -> stop (R5.2), A2 is not called
    2. QUESTION    A2 interpret()      ┐  run concurrently once A3 exists
       ANALYSIS    A3 analyze()        ┘  <- A3 SLOT, empty until MERGE_PLAN phase 4
    3. REASONING   A4 answer()            <- A4 SLOT, empty (A4 not implemented)

Until A3 and A4 exist the pipeline returns *interim answers* without a number
(``INTERIM_TEXTS``). This module contains no image, NLP, IFC or calculation logic:
it only calls the component entry points, checks their outputs against the
contracts, and never lets an exception escape (R5.1).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TypeVar

from pydantic import BaseModel, ValidationError

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
from blueprint_qa.validation import validate

ValidateFn = Callable[[PipelineRequest], ValidationResult | ErrorEnvelope]
InterpretFn = Callable[[str, str, str | None], ParsedQuestion | ErrorEnvelope]
AnalyzeFn = Callable[[ValidationResult], BlueprintAnalysis | ErrorEnvelope]
ReasonFn = Callable[[ParsedQuestion, BlueprintAnalysis], Answer | ErrorEnvelope]

# The stage steps in order. Stages in one tuple run concurrently.
STAGE_ORDER: tuple[tuple[Stage, ...], ...] = (
    (Stage.VALIDATION,),
    (Stage.QUESTION, Stage.ANALYSIS),  # ANALYSIS = A3 slot (phase 4)
    (Stage.REASONING,),  # A4 slot (not implemented)
)

# Fixed texts of the interim answers (MERGE_PLAN phase 1). All in English.
INTERIM_TEXTS: dict[str, str] = {
    "invalid_input": "This picture is invalid for our program",
    "unsupported_question": "This question cannot be answered with a number.",
    "analysis_unavailable": "Plan analysis is not available yet.",
}
INTERIM_LANGUAGE = "en"
# Answer.unit is required even when value is None; placeholder until OPEN_QUESTIONS Q9 is decided.
PLACEHOLDER_UNIT = "count"

_logger = get_logger(__name__)
_T = TypeVar("_T", bound=BaseModel)


@dataclass(frozen=True)
class Components:
    """The component entry points the pipeline calls. Tests replace them with fakes."""

    validate: ValidateFn = validate
    interpret: InterpretFn = interpret
    analyze: AnalyzeFn | None = None  # A3 SLOT: empty until MERGE_PLAN phase 4
    reason: ReasonFn | None = None  # A4 SLOT: empty (A4 not implemented)


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

    # 2. QUESTION (A2) || ANALYSIS (A3 slot: phase 4 runs comps.analyze(validation) concurrently)
    question = _call(
        Stage.QUESTION,
        rid,
        ParsedQuestion,
        trace,
        lambda: comps.interpret(rid, request.question, request.locale_hint),
    )
    if isinstance(question, ErrorEnvelope):
        return question

    # 3. REASONING (A4 slot): until it exists, return an interim answer without a number.
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
    return _interim(rid, AnswerStatus.CANNOT_ANSWER, INTERIM_TEXTS["analysis_unavailable"])


def _call(
    stage: Stage,
    rid: str,
    expected: type[_T],
    trace: PipelineTrace,
    fn: Callable[[], object],
) -> _T | ErrorEnvelope:
    """Call one component, contract-check its output, log one event, never raise."""
    start = time.perf_counter()
    try:
        raw = fn()
    except Exception as exc:  # R5.1: components must not raise; contain it if one does
        result: BaseModel = _envelope(rid, "INTERNAL_ERROR", stage, exc)
    else:
        result = _checked(raw, expected, stage, rid)
    trace.stages.append((stage, result))
    _log(rid, stage, "stage_done", result, (time.perf_counter() - start) * 1000)
    if isinstance(result, expected):
        return result
    assert isinstance(result, ErrorEnvelope)
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
    elif isinstance(result, Answer):
        fields.update(outcome=result.status.value)
    level = logging.WARNING if isinstance(result, ErrorEnvelope) else logging.INFO
    log_event(_logger, event, request_id=rid, stage=stage, level=level, **fields)
