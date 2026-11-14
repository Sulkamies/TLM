"""mapping.py and the LlmParse invariants: pure, deterministic, no LLM."""

from __future__ import annotations

from typing import Any, get_args

import pytest
from pydantic import ValidationError

from blueprint_qa.contracts import CONTRACT_VERSION, Comparison, ErrorEnvelope, ParsedQuestion
from blueprint_qa.question.llm_output import UNITS, LlmParse, RequestedUnit
from blueprint_qa.question.mapping import normalize_language, threshold_to_si, to_parsed_question

ROOM = {"category": "ROOM"}


def parse(**overrides: Any) -> LlmParse:
    base: dict[str, Any] = {
        "language": "en",
        "intent": "COUNT",
        "aggregation": "SUM",
        "targets": [ROOM],
        "confidence": 0.8,
    }
    return LlmParse.model_validate({**base, **overrides})


def comparison(measure: str = "AREA", threshold: float | None = 10.0) -> dict[str, Any]:
    return {"measure": measure, "operator": "GT", "threshold": threshold}


def run(llm: LlmParse) -> ParsedQuestion:
    out = to_parsed_question(llm, request_id="r1", question="q?", provider="test")
    assert isinstance(out, ParsedQuestion), out
    return out


def test_code_owned_fields_are_filled() -> None:
    pq = run(parse())
    assert (pq.request_id, pq.original_question, pq.provider) == ("r1", "q?", "test")
    assert pq.schema_version == CONTRACT_VERSION


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (120, "ft2", 11.1483648),
        (12, "m2", 12.0),
        (12, None, 12.0),  # no unit written -> SI best guess, with clarification
    ],
)
def test_area_threshold_converted_to_si(value: float, unit: str | None, expected: float) -> None:
    pq = run(
        parse(
            intent="COMPARISON",
            aggregation="SINGLE",
            comparison=comparison(threshold=value),
            threshold_unit=unit,
            clarification_needed=None if unit else "Which unit?",
        )
    )
    assert pq.comparison is not None
    assert pq.comparison.threshold == pytest.approx(expected)


@pytest.mark.parametrize(
    ("measure", "unit", "expected"),
    [
        ("LENGTH", "cm", 1.0),
        ("LENGTH", "mm", 0.1),
        ("HEIGHT", "ft", 30.48),
        ("PERIMETER", "in", 2.54),
        ("VOLUME", "ft3", 2.8316846592),
        ("VOLUME", "l", 0.1),
        ("COUNT", "count", 100.0),
    ],
)
def test_other_units(measure: str, unit: str, expected: float) -> None:
    pq = run(parse(intent="COMPARISON", comparison=comparison(measure, 100.0), threshold_unit=unit))
    assert pq.comparison is not None
    assert pq.comparison.threshold == pytest.approx(expected)


def test_unitless_count_threshold_needs_no_clarification() -> None:
    pq = run(parse(intent="COMPARISON", comparison=comparison("COUNT", 3.0)))
    assert pq.comparison is not None and pq.comparison.threshold == 3.0
    assert pq.clarification_needed is None


@pytest.mark.parametrize("clarification", [None, "  "])
def test_unitless_measured_threshold_requires_clarification(clarification: str | None) -> None:
    """Q6 (ry): 'bigger than 10' without a unit must ask which unit is meant."""
    with pytest.raises(ValidationError, match="threshold has no unit"):
        parse(
            intent="COMPARISON",
            comparison=comparison("AREA", 10.0),
            clarification_needed=clarification,
        )


def test_storey_must_be_a_fixed_value() -> None:
    """Q5 (ry): storeys take fixed values (interim vocabulary until contract change 004)."""
    ok = run(parse(targets=[{"category": "STOREY", "storey": "GROUND"}]))
    assert ok.targets[0].storey == "GROUND"
    with pytest.raises(ValidationError, match="storey must be null or one of"):
        parse(targets=[{"category": "STOREY", "storey": "ground floor"}])


def test_fixture_target_carries_its_fixture_type() -> None:
    """Contract change 001: fixture_type is set iff category == FIXTURE (field_rules.yaml)."""
    pq = run(parse(targets=[{"category": "FIXTURE", "fixture_type": "TOILET"}]))
    assert (pq.targets[0].category, pq.targets[0].fixture_type) == ("FIXTURE", "TOILET")
    room = run(parse(targets=[{"category": "ROOM", "room_type": "TOILET"}]))
    assert room.targets[0].fixture_type is None


@pytest.mark.parametrize(
    ("target", "message"),
    [
        ({"category": "FIXTURE"}, "category FIXTURE requires fixture_type"),
        (
            {"category": "ROOM", "room_type": "TOILET", "fixture_type": "TOILET"},
            "fixture_type must be null unless category is FIXTURE",
        ),
        ({"category": "WHOLE_PLAN", "fixture_type": "SINK"}, "must be null unless"),
    ],
)
def test_fixture_type_iff_fixture_category(target: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse(targets=[target])


def test_threshold_none_compares_two_targets() -> None:
    pq = run(
        parse(intent="COMPARISON", targets=[ROOM, ROOM], comparison=comparison(threshold=None))
    )
    assert pq.comparison is not None and pq.comparison.threshold is None


def test_threshold_to_si_rejects_wrong_dimension() -> None:
    with pytest.raises(ValueError):
        threshold_to_si(Comparison(measure="AREA", operator="GT", threshold=1.0), "m")


def test_mapping_failure_returns_question_parse_failed() -> None:
    bad = LlmParse.model_construct(
        language="en",
        intent="COMPARISON",
        aggregation="SINGLE",
        targets=[],
        comparison=Comparison(measure="AREA", operator="GT", threshold=1.0),
        threshold_unit="m",
        requested_unit=None,
        confidence=0.5,
        clarification_needed=None,
    )
    out = to_parsed_question(bad, request_id="r1", question="q", provider="p")
    assert isinstance(out, ErrorEnvelope)
    assert out.code == "QUESTION_PARSE_FAILED" and out.stage.value == "QUESTION"


def test_requested_unit_kept_for_measures_and_dropped_otherwise() -> None:
    assert run(parse(intent="AREA", requested_unit="ft2")).requested_unit == "ft2"
    assert run(parse(intent="COUNT", requested_unit="ft2")).requested_unit is None


def test_blank_clarification_becomes_none() -> None:
    assert run(parse(clarification_needed="  ")).clarification_needed is None
    assert run(parse(clarification_needed="Which room?")).clarification_needed == "Which room?"


@pytest.mark.parametrize(
    ("tag", "expected"),
    [
        ("EN", "en"),
        ("de-de", "de-DE"),
        ("fi_FI", "fi-FI"),
        ("zh-hant-tw", "zh-Hant-TW"),
        ("sl-rozaj", "sl-rozaj"),
    ],
)
def test_language_normalisation(tag: str, expected: str) -> None:
    assert normalize_language(tag) == expected


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"intent": "COMPARISON"}, "requires comparison"),
        ({"comparison": comparison()}, "must be null unless"),
        ({"intent": "DISTANCE"}, "exactly 2 targets"),
        ({"intent": "RATIO"}, "exactly 2 targets"),
        ({"intent": "COMPARISON", "comparison": comparison(threshold=None)}, "exactly 2 targets"),
        (
            {
                "intent": "COMPARISON",
                "targets": [ROOM, ROOM],
                "comparison": comparison(threshold=None),
                "threshold_unit": "m2",
            },
            "threshold is null",
        ),
        (
            {"intent": "COMPARISON", "comparison": comparison(), "threshold_unit": "m"},
            "does not fit",
        ),
        ({"threshold_unit": "m2"}, "without a comparison"),
        ({"intent": "AREA", "requested_unit": "m"}, "not a area unit"),
        ({"language": "english!"}, "BCP-47"),
        ({"targets": []}, "at least 1"),
        ({"confidence": 1.5}, "less than or equal"),
        ({"extra": 1}, "Extra inputs"),
    ],
)
def test_invariants_rejected(overrides: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        parse(**overrides)


def test_requested_unit_literal_matches_contract() -> None:
    contract = ParsedQuestion.model_fields["requested_unit"].annotation
    (literal,) = [a for a in get_args(contract) if a is not type(None)]
    assert set(get_args(RequestedUnit)) == set(get_args(literal))
    assert all(unit in UNITS for unit in get_args(RequestedUnit))


def test_schema_is_composed_from_contract_types() -> None:
    """Rule Q2: targets/intent/comparison reuse the contract models."""
    defs = LlmParse.model_json_schema()["$defs"]
    assert {"EntityRef", "Intent", "Aggregation", "Comparison"} <= set(defs)
