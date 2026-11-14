"""A2 entry point (AGENTS.md §6 A2): ``interpret(request_id, question, locale_hint)``.

Picks the provider and guarantees that no exception crosses the boundary (R5.1).
It contains no parsing logic.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from blueprint_qa.common.log import get_logger, log_event
from blueprint_qa.contracts import ErrorEnvelope, ParsedQuestion, Stage
from blueprint_qa.question.providers import LlmQuestionProvider, QuestionProvider

_log = get_logger(__name__)

# Builds the provider for each request. The default is the LLM provider (§6 A2).
# Tests replace it; built per call so config/env changes take effect (stateless, R3.7).
provider_factory: Callable[[], QuestionProvider] = LlmQuestionProvider


def _error(request_id: str, code: str, message: str, **details: str) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=request_id,
        stage=Stage.QUESTION,
        code=code,
        message=message,
        retryable=False,
        details=details,
    )


def interpret(
    request_id: str, question: str, locale_hint: str | None
) -> ParsedQuestion | ErrorEnvelope:
    """Interpret one natural-language question. Never raises."""
    try:
        if not isinstance(question, str) or not question.strip():
            return _error(request_id, "INVALID_INPUT", "The question is empty.", field="question")
        result = provider_factory().parse(request_id, question, locale_hint)
        if isinstance(result, ParsedQuestion):
            if result.request_id != request_id:
                return _error(
                    request_id,
                    "INTERNAL_ERROR",
                    "The question could not be interpreted.",
                    detail="provider changed request_id",
                )
            log_event(
                _log,
                "question_interpreted",
                request_id=request_id,
                stage=Stage.QUESTION,
                provider=result.provider,
                language=result.language,
                intent=result.intent.value,
                targets=len(result.targets),
                clarification=result.clarification_needed is not None,
                confidence=result.confidence,
            )
        else:
            log_event(
                _log,
                "question_failed",
                request_id=request_id,
                stage=Stage.QUESTION,
                level=logging.WARNING,
                code=result.code,
            )
        return result
    except Exception as exc:  # R5.1: last line of defence
        log_event(
            _log,
            "question_internal_error",
            request_id=request_id,
            stage=Stage.QUESTION,
            level=logging.ERROR,
            exc_type=type(exc).__name__,
        )
        return _error(
            request_id,
            "INTERNAL_ERROR",
            "The question could not be interpreted.",
            detail=type(exc).__name__,
        )
