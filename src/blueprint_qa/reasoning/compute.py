"""Deterministic computation of the answer value per intent (AGENTS.md §6 A4, A0 decisions).

All values are SI. No LLM is involved (principle 3). Anything that cannot be computed
raises ``Stop``; a number is only returned with evidence behind it (R5.3).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from blueprint_qa.contracts import (
    Aggregation,
    BlueprintAnalysis,
    EntityRef,
    Intent,
    ParsedQuestion,
    Room,
    Storey,
)
from blueprint_qa.reasoning import geometry
from blueprint_qa.reasoning.outcome import Msg, Outcome, cannot, clarify
from blueprint_qa.reasoning.resolve import Element, Match, resolve, zero_is_covered

# SI unit of each measure, as used in explanations.
MEASURE_SI_UNIT: dict[str, str | None] = {
    "COUNT": None,
    "AREA": "m2",
    "LENGTH": "m",
    "PERIMETER": "m",
    "HEIGHT": "m",
    "VOLUME": "m3",
    "DISTANCE": "m",
}

_GEOMETRIC = frozenset({"LENGTH", "PERIMETER", "DISTANCE"})
_SUMMABLE_OVER_ROOMS = frozenset({"AREA", "VOLUME"})

_OPERATORS: dict[str, Callable[[float, float], bool]] = {
    "GT": lambda a, b: a > b,
    "GE": lambda a, b: a >= b,
    "LT": lambda a, b: a < b,
    "LE": lambda a, b: a <= b,
    "EQ": lambda a, b: a == b,
}


@dataclass(frozen=True)
class _Subject:
    """One thing a measure is taken of: an element, or the whole plan (rooms in scope)."""

    ref: EntityRef
    key: str
    element: Element | None
    rooms: tuple[Room, ...] = ()


@dataclass
class _Value:
    value: float
    evidence: list[str]
    confidences: list[float]
    rooms_summed: int = 0


# ------------------------------------------------------------------------------ helpers


def metres_per_unit(analysis: BlueprintAnalysis) -> float:
    """Factor from the analysis' coordinates to metres; Stop if no scale is known."""
    if not analysis.metric_available:
        raise cannot("no_metric")
    if analysis.coordinate_space == "METRIC":
        return 1.0
    ppm = analysis.scale.pixels_per_meter
    if ppm is None or not math.isfinite(ppm) or ppm <= 0.0:
        raise cannot("no_metric")
    return 1.0 / ppm


def _confidences(elements: Sequence[Element]) -> list[float]:
    return [e.confidence for e in elements if not isinstance(e, Storey)]


def _dedupe(ids: Sequence[str]) -> list[str]:
    return list(dict.fromkeys(ids))


def _storey_note(question: ParsedQuestion, analysis: BlueprintAnalysis) -> list[Msg]:
    """Note when no storey is named, the plan has several and the answer spans them all."""
    if len(analysis.storeys) <= 1:
        return []
    if any(t.storey is not None for t in question.targets):
        return []
    if all(t.category == "STOREY" for t in question.targets):
        return []
    return [Msg("note_all_storeys", n=len(analysis.storeys))]


def _resolve_all(question: ParsedQuestion, analysis: BlueprintAnalysis) -> list[Match]:
    if not question.targets:
        raise cannot("bad_question")
    return [resolve(t, analysis) for t in question.targets]


def _require_countable(match: Match) -> None:
    if match.ref.category == "WHOLE_PLAN":
        raise cannot("measure_not_applicable", what=(match.ref,), measure="COUNT")


# ------------------------------------------------------------------------ COUNT / EXISTS


def _count_one(match: Match, analysis: BlueprintAnalysis) -> int:
    """Number of elements of one target; a zero must be covered by the analysis."""
    _require_countable(match)
    if not match.elements:
        if match.narrowed:
            raise cannot("no_match", what=(match.ref,))
        if not zero_is_covered(match, analysis):
            raise cannot("not_detectable", what=(match.ref,))
    return len(match.elements)


def _count(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    matches = _resolve_all(question, analysis)
    total = sum(_count_one(m, analysis) for m in matches)
    elements = [e for m in matches for e in m.elements]
    refs = tuple(question.targets)
    msg = Msg("count", what=refs, value=float(total)) if total else Msg("count_zero", what=refs)
    return Outcome(
        value=float(total),
        msg=msg,
        evidence=_dedupe([e.id for e in elements]),
        confidences=_confidences(elements),
        notes=_storey_note(question, analysis),
    )


def _existence(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    matches = _resolve_all(question, analysis)
    for m in matches:
        _require_countable(m)
    elements = [e for m in matches for e in m.elements]
    refs = tuple(question.targets)
    notes = _storey_note(question, analysis)
    if elements:
        return Outcome(
            value=1.0,
            msg=Msg("exists_yes", what=refs, n=len(_dedupe([e.id for e in elements]))),
            evidence=_dedupe([e.id for e in elements]),
            confidences=_confidences(elements),
            notes=notes,
        )
    for m in matches:
        _count_one(m, analysis)  # raises unless this zero is covered
    return Outcome(value=0.0, msg=Msg("exists_no", what=refs), notes=notes)


# ------------------------------------------------------------------------------ measures


def _subjects(matches: Sequence[Match]) -> list[_Subject]:
    subjects: dict[str, _Subject] = {}
    for m in matches:
        if m.ref.category == "WHOLE_PLAN":
            rooms = tuple(e for e in m.elements if isinstance(e, Room))
            subjects.setdefault("WHOLE_PLAN", _Subject(m.ref, "WHOLE_PLAN", None, rooms))
        else:
            for e in m.elements:
                subjects.setdefault(e.id, _Subject(m.ref, e.id, e))
    return list(subjects.values())


def _room_value(measure: str, room: Room, ref: EntityRef, analysis: BlueprintAnalysis) -> float:
    if measure == "AREA":
        if room.area_m2 is None:
            raise cannot("missing_area", what=(ref,))
        return room.area_m2
    if measure == "HEIGHT":
        if room.height_m is None:
            raise cannot("missing_height", what=(ref,))
        return room.height_m
    if measure == "VOLUME":
        if room.area_m2 is None:
            raise cannot("missing_area", what=(ref,))
        if room.height_m is None:
            raise cannot("missing_height", what=(ref,))
        return room.area_m2 * room.height_m
    # LENGTH, PERIMETER
    factor = metres_per_unit(analysis)
    if not geometry.is_usable(room.polygon):
        raise cannot("degenerate_geometry", what=(ref,))
    if measure == "LENGTH":
        return geometry.bbox_long_side(room.polygon) * factor
    return geometry.perimeter(room.polygon) * factor


def _sum_over_rooms(
    measure: str, rooms: Sequence[Room], subject: _Subject, analysis: BlueprintAnalysis
) -> _Value:
    if not rooms:
        raise cannot("no_rooms", what=(subject.ref,))
    values = [_room_value(measure, r, subject.ref, analysis) for r in rooms]
    ids = [r.id for r in rooms]
    if isinstance(subject.element, Storey):
        ids = [subject.element.id, *ids]
    return _Value(sum(values), ids, [r.confidence for r in rooms], rooms_summed=len(rooms))


def _rooms_on_storey(storey: Storey, subject: _Subject, analysis: BlueprintAnalysis) -> list[Room]:
    if len(analysis.storeys) == 1:
        return [r for r in analysis.rooms if r.storey_id in (None, storey.id)]
    if any(r.storey_id is None for r in analysis.rooms):
        raise cannot("storey_unknown", what=(subject.ref,))
    return [r for r in analysis.rooms if r.storey_id == storey.id]


def _subject_value(measure: str, subject: _Subject, analysis: BlueprintAnalysis) -> _Value:
    element = subject.element
    if isinstance(element, Room):
        value = _room_value(measure, element, subject.ref, analysis)
        return _Value(value, [element.id], [element.confidence])
    if measure in _SUMMABLE_OVER_ROOMS:
        if element is None:  # WHOLE_PLAN
            return _sum_over_rooms(measure, subject.rooms, subject, analysis)
        if isinstance(element, Storey):
            rooms = _rooms_on_storey(element, subject, analysis)
            return _sum_over_rooms(measure, rooms, subject, analysis)
    raise cannot("measure_not_applicable", what=(subject.ref,), measure=measure)


def _aggregate(values: Sequence[float], aggregation: Aggregation) -> float:
    if aggregation is Aggregation.SUM:
        return sum(values)
    if aggregation is Aggregation.MAX:
        return max(values)
    if aggregation is Aggregation.MIN:
        return min(values)
    if aggregation is Aggregation.MEAN:
        return sum(values) / len(values)
    return values[0]  # SINGLE: exactly one value (checked by the caller)


def _measure(
    measure: str,
    matches: Sequence[Match],
    aggregation: Aggregation,
    analysis: BlueprintAnalysis,
) -> _Value:
    """Measure over the matched subjects, aggregated. Raises ``Stop``."""
    if measure in _GEOMETRIC:
        metres_per_unit(analysis)  # a missing scale is the most useful explanation
    refs = tuple(m.ref for m in matches)
    subjects = _subjects(matches)
    if not subjects:
        raise cannot("no_match", what=refs)
    if aggregation is Aggregation.SINGLE and len(subjects) > 1:
        raise clarify("several_matches", what=refs, n=len(subjects))
    parts = [_subject_value(measure, s, analysis) for s in subjects]
    return _Value(
        value=_aggregate([p.value for p in parts], aggregation),
        evidence=_dedupe([i for p in parts for i in p.evidence]),
        confidences=[c for p in parts for c in p.confidences],
        rooms_summed=sum(p.rooms_summed for p in parts),
    )


def _measure_intent(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    measure = question.intent.value
    if measure in _GEOMETRIC:
        metres_per_unit(analysis)
    matches = _resolve_all(question, analysis)
    result = _measure(measure, matches, question.aggregation, analysis)
    notes = _storey_note(question, analysis)
    if result.rooms_summed:
        notes.insert(0, Msg("note_sum_over_rooms", n=result.rooms_summed))
    aggregation = None if question.aggregation is Aggregation.SINGLE else question.aggregation
    return Outcome(
        value=result.value,
        msg=Msg(
            "measure",
            what=tuple(question.targets),
            measure=measure,
            aggregation=aggregation.value if aggregation else None,
            value=result.value,
            unit=MEASURE_SI_UNIT[measure],
        ),
        evidence=result.evidence,
        confidences=result.confidences,
        notes=notes,
    )


# ------------------------------------------------------------------- DISTANCE / RATIO


def _single_point(match: Match, analysis: BlueprintAnalysis) -> tuple[tuple[float, float], Element]:
    ref = match.ref
    if ref.category in ("WHOLE_PLAN", "STOREY"):
        raise cannot("measure_not_applicable", what=(ref,), measure="DISTANCE")
    if not match.elements:
        raise cannot("no_match", what=(ref,))
    if len(match.elements) > 1:
        raise clarify("several_matches", what=(ref,), n=len(match.elements))
    element = match.elements[0]
    if isinstance(element, Room):
        if not geometry.is_usable(element.polygon):
            raise cannot("degenerate_geometry", what=(ref,))
        return geometry.centroid(element.polygon), element
    assert not isinstance(element, Storey)  # excluded by the category check above
    return element.position, element


def _distance(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    factor = metres_per_unit(analysis)
    if len(question.targets) != 2:
        raise cannot("bad_question")
    matches = _resolve_all(question, analysis)
    (p1, e1), (p2, e2) = (_single_point(m, analysis) for m in matches)
    s1 = None if isinstance(e1, Storey) else e1.storey_id
    s2 = None if isinstance(e2, Storey) else e2.storey_id
    refs = tuple(question.targets)
    if s1 is not None and s2 is not None and s1 != s2:
        raise cannot("different_storeys", what=refs)
    value = geometry.distance(p1, p2) * factor
    elements = [e1, e2]
    return Outcome(
        value=value,
        msg=Msg("distance", what=refs, value=value, unit="m"),
        evidence=_dedupe([e.id for e in elements]),
        confidences=_confidences(elements),
    )


def _ratio(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    """Area ratio targets[0] / targets[1], each target summed over its matches."""
    if len(question.targets) != 2:
        raise cannot("bad_question")
    num_match, den_match = _resolve_all(question, analysis)
    num = _measure("AREA", [num_match], Aggregation.SUM, analysis)
    den = _measure("AREA", [den_match], Aggregation.SUM, analysis)
    if den.value == 0.0:
        raise cannot("zero_denominator", rhs_what=(den_match.ref,))
    value = num.value / den.value
    notes = _storey_note(question, analysis)
    return Outcome(
        value=value,
        msg=Msg("ratio", what=(num_match.ref,), rhs_what=(den_match.ref,), value=value),
        evidence=_dedupe([*num.evidence, *den.evidence]),
        confidences=[*num.confidences, *den.confidences],
        notes=notes,
    )


# ------------------------------------------------------------------------- COMPARISON


def _side(
    measure: str, ref: EntityRef, aggregation: Aggregation, analysis: BlueprintAnalysis
) -> _Value:
    match = resolve(ref, analysis)
    if measure == "COUNT":
        n = _count_one(match, analysis)
        return _Value(float(n), [e.id for e in match.elements], _confidences(match.elements))
    return _measure(measure, [match], aggregation, analysis)


def _comparison(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    comp = question.comparison
    if comp is None or not question.targets:
        raise cannot("bad_question")
    if comp.threshold is None and len(question.targets) < 2:
        raise cannot("bad_question")
    if comp.measure in _GEOMETRIC:
        metres_per_unit(analysis)
    lhs = _side(comp.measure, question.targets[0], question.aggregation, analysis)
    if comp.threshold is not None:
        rhs = _Value(comp.threshold, [], [])
        rhs_what: tuple[EntityRef, ...] = ()
    else:
        rhs = _side(comp.measure, question.targets[1], question.aggregation, analysis)
        rhs_what = (question.targets[1],)
    result = _OPERATORS[comp.operator](lhs.value, rhs.value)
    return Outcome(
        value=1.0 if result else 0.0,
        msg=Msg(
            "comparison_yes" if result else "comparison_no",
            what=(question.targets[0],),
            rhs_what=rhs_what,
            measure=comp.measure,
            lhs=lhs.value,
            rhs=rhs.value,
            unit=MEASURE_SI_UNIT[comp.measure],
            operator=comp.operator,
        ),
        evidence=_dedupe([*lhs.evidence, *rhs.evidence]),
        confidences=[*lhs.confidences, *rhs.confidences],
        notes=_storey_note(question, analysis),
    )


# ---------------------------------------------------------------------------- dispatch

_HANDLERS: dict[Intent, Callable[[ParsedQuestion, BlueprintAnalysis], Outcome]] = {
    Intent.COUNT: _count,
    Intent.EXISTENCE: _existence,
    Intent.AREA: _measure_intent,
    Intent.LENGTH: _measure_intent,
    Intent.PERIMETER: _measure_intent,
    Intent.HEIGHT: _measure_intent,
    Intent.VOLUME: _measure_intent,
    Intent.DISTANCE: _distance,
    Intent.RATIO: _ratio,
    Intent.COMPARISON: _comparison,
}


def compute(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Outcome:
    """Compute the SI value for an answerable intent. Raises ``Stop``."""
    handler = _HANDLERS.get(question.intent)
    if handler is None:  # UNSUPPORTED is handled by the caller
        raise cannot("bad_question")
    return handler(question, analysis)
