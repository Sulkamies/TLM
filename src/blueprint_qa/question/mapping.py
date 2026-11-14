"""Pure, deterministic ``LlmParse`` -> ``ParsedQuestion`` (design §2, rule Q5).

Fills the code-owned fields, converts comparison thresholds to SI, normalises the
language tag and drops a ``requested_unit`` that cannot apply. No I/O, no LLM.
"""

from __future__ import annotations

from pydantic import ValidationError

from blueprint_qa.contracts import Comparison, ErrorEnvelope, ParsedQuestion, Stage
from blueprint_qa.question.llm_output import (
    INTENT_DIMENSION,
    MEASURE_DIMENSION,
    SI_UNIT,
    UNITS,
    LlmParse,
)


def normalize_language(tag: str) -> str:
    """BCP-47 casing: language lower case, region upper case (``DE-de`` -> ``de-DE``)."""
    parts = tag.strip().replace("_", "-").split("-")
    out = [parts[0].lower()]
    for part in parts[1:]:
        if len(part) == 2:
            out.append(part.upper())
        elif len(part) == 4:
            out.append(part.title())
        else:
            out.append(part.lower())
    return "-".join(out)


def threshold_to_si(comparison: Comparison, unit: str | None) -> Comparison:
    """Return ``comparison`` with its threshold in SI units.

    A threshold written without a unit is taken to be in the SI unit of the measure.
    """
    if comparison.threshold is None:
        return comparison
    dim = MEASURE_DIMENSION[comparison.measure]
    unit_dim, factor = UNITS[unit or SI_UNIT[dim]]
    if unit_dim != dim:
        raise ValueError(f"unit {unit} does not fit measure {comparison.measure}")
    return comparison.model_copy(update={"threshold": comparison.threshold * factor})


def to_parsed_question(
    llm: LlmParse, *, request_id: str, question: str, provider: str
) -> ParsedQuestion | ErrorEnvelope:
    """Build the contract output; returns ``QUESTION_PARSE_FAILED`` if that is impossible."""
    try:
        comparison = threshold_to_si(llm.comparison, llm.threshold_unit) if llm.comparison else None
        requested_unit = llm.requested_unit if llm.intent in INTENT_DIMENSION else None
        clarification = (llm.clarification_needed or "").strip() or None
        return ParsedQuestion(
            request_id=request_id,
            original_question=question,
            language=normalize_language(llm.language),
            intent=llm.intent,
            aggregation=llm.aggregation,
            targets=[t.model_copy() for t in llm.targets],
            comparison=comparison,
            requested_unit=requested_unit,
            confidence=llm.confidence,
            provider=provider,
            clarification_needed=clarification,
        )
    except (ValidationError, ValueError, KeyError) as exc:
        return ErrorEnvelope(
            request_id=request_id,
            stage=Stage.QUESTION,
            code="QUESTION_PARSE_FAILED",
            message="The question could not be interpreted.",
            retryable=False,
            details={"detail": type(exc).__name__, "provider": provider},
        )
