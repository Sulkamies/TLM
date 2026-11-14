"""A4 entry point (AGENTS.md §6 A4): ``answer(question, analysis) -> Answer | ErrorEnvelope``.

Combines what is asked (``ParsedQuestion``) with what is seen (``BlueprintAnalysis``).
The value is computed by deterministic code (``compute.py``); the explanation comes
from fixed templates (``explanations.py``). No LLM, no file access, never raises (R5.1).
"""

from __future__ import annotations

import logging
import math
from dataclasses import replace
from typing import Literal

from blueprint_qa.common.log import get_logger, log_event
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    ErrorEnvelope,
    Intent,
    ParsedQuestion,
    Stage,
)
from blueprint_qa.reasoning.compute import compute
from blueprint_qa.reasoning.explanations import pick_language, render, render_all
from blueprint_qa.reasoning.outcome import Msg, Stop, cannot

Unit = Literal["count", "ratio", "boolean", "m", "m2", "m3", "ft", "ft2", "ft3"]

_log = get_logger(__name__)

# Unit by intent, also when there is no value (OPEN_QUESTIONS Q9, option c).
INTENT_UNIT: dict[Intent, Unit] = {
    Intent.COUNT: "count",
    Intent.AREA: "m2",
    Intent.LENGTH: "m",
    Intent.PERIMETER: "m",
    Intent.DISTANCE: "m",
    Intent.HEIGHT: "m",
    Intent.VOLUME: "m3",
    Intent.RATIO: "ratio",
    Intent.EXISTENCE: "boolean",
    Intent.COMPARISON: "boolean",
}
# UNSUPPORTED has no natural unit; same placeholder as the orchestrator (Q9).
PLACEHOLDER_UNIT: Unit = "count"

# SI unit -> (imperial unit, factor). AGENTS.md §6 A4.
CONVERSIONS: dict[str, tuple[Unit, float]] = {
    "m": ("ft", 3.28084),
    "m2": ("ft2", 10.7639),
    "m3": ("ft3", 35.3147),
}


def output_unit(question: ParsedQuestion) -> tuple[Unit, float]:
    """Unit of the answer and the factor from SI. ``requested_unit`` applies only if it has
    the same dimension as the intent's SI unit; otherwise the SI unit is kept."""
    si = INTENT_UNIT.get(question.intent, PLACEHOLDER_UNIT)
    conversion = CONVERSIONS.get(si)
    if conversion is not None and question.requested_unit == conversion[0]:
        return conversion
    return si, 1.0


def _error(request_id: str, code: str, message: str, **details: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=request_id,
        stage=Stage.REASONING,
        code=code,
        message=message,
        retryable=False,
        details=details,
    )


def _no_value(
    question: ParsedQuestion,
    status: AnswerStatus,
    explanation: str,
    language: str,
    unit: Unit,
) -> Answer:
    return Answer(
        request_id=question.request_id,
        status=status,
        value=None,
        unit=unit,
        confidence=question.confidence,
        evidence=[],
        explanation=explanation,
        language=language,
    )


def _answer(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Answer:
    lang = pick_language(question.language)
    unit, factor = output_unit(question)
    if question.intent is Intent.UNSUPPORTED:
        text = render(Msg("unsupported"), lang)
        return _no_value(question, AnswerStatus.UNSUPPORTED_QUESTION, text, lang, unit)
    if question.clarification_needed is not None:
        return _no_value(
            question,
            AnswerStatus.NEEDS_CLARIFICATION,
            question.clarification_needed,
            question.language,
            unit,
        )
    try:
        outcome = compute(question, analysis)
        value = outcome.value * factor
        if not math.isfinite(value):
            raise cannot("degenerate_geometry", what=tuple(question.targets))
    except Stop as stop:
        return _no_value(question, stop.status, render(stop.msg, lang), lang, unit)
    msg = outcome.msg
    if msg.value is not None and msg.unit is not None:
        msg = replace(msg, value=msg.value * factor, unit=unit)
    return Answer(
        request_id=question.request_id,
        status=AnswerStatus.ANSWERED,
        value=value,
        unit=unit,
        confidence=min([question.confidence, *outcome.confidences]),
        evidence=outcome.evidence,
        explanation=render_all([msg, *outcome.notes], lang),
        language=lang,
    )


def answer(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Answer | ErrorEnvelope:
    """Answer one parsed question about one analysed plan. Never raises."""
    request_id = getattr(question, "request_id", None)
    if not isinstance(request_id, str):
        request_id = "unknown"
    try:
        if not isinstance(question, ParsedQuestion) or not isinstance(analysis, BlueprintAnalysis):
            return _error(
                request_id,
                "INVALID_INPUT",
                "The answer could not be computed.",
                detail="inputs are not ParsedQuestion and BlueprintAnalysis",
            )
        if question.request_id != analysis.request_id:
            return _error(
                request_id,
                "INVALID_INPUT",
                "The answer could not be computed.",
                detail="request_id of question and analysis differ",
            )
        result = _answer(question, analysis)
        log_event(
            _log,
            "answer_computed",
            request_id=request_id,
            stage=Stage.REASONING,
            intent=question.intent.value,
            status=result.status.value,
            unit=result.unit,
            evidence=len(result.evidence),
            confidence=result.confidence,
        )
        return result
    except Exception as exc:  # R5.1: last line of defence
        log_event(
            _log,
            "reasoning_internal_error",
            request_id=request_id,
            stage=Stage.REASONING,
            level=logging.ERROR,
            exc_type=type(exc).__name__,
        )
        return _error(
            request_id,
            "REASONING_FAILED",
            "The answer could not be computed.",
            exc_type=type(exc).__name__,
        )
