"""Target resolution: storey (incl. UPPER and level None), label, ordinal, categories."""

from __future__ import annotations

import pytest
from reasoning_fakes import analysis, fixture, opening, question, ref, room, storey

from blueprint_qa.contracts import (
    Aggregation,
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    FixtureType,
    Intent,
    RoomType,
    StoreyLevel,
)
from blueprint_qa.reasoning import answer
from blueprint_qa.reasoning.resolve import id_sort_key, normalize_label


def _ok(result: object) -> Answer:
    assert isinstance(result, Answer)
    return result


def _count(plan: BlueprintAnalysis, **kwargs: object) -> Answer:
    category = str(kwargs.pop("category", "ROOM"))
    return _ok(answer(question(Intent.COUNT, [ref(category, **kwargs)]), plan))


def _three_storeys(attic: StoreyLevel | None = StoreyLevel.UPPER_1) -> BlueprintAnalysis:
    storeys = [storey(1, StoreyLevel.BASEMENT), storey(2, StoreyLevel.GROUND)]
    if attic is not None:
        storeys.append(storey(3, attic))
    else:
        storeys.append(storey(3, None))
    return analysis(
        storeys=storeys,
        rooms=[
            room(1, RoomType.SAUNA, storey="storey_1"),
            room(2, RoomType.KITCHEN, storey="storey_2"),
            room(3, RoomType.BEDROOM, storey="storey_3"),
            room(4, RoomType.BEDROOM, storey="storey_3"),
        ],
    )


# ---------------------------------------------------------------------------- storeys


def test_storey_level_filter() -> None:
    plan = _three_storeys()
    assert _count(plan, room_type=RoomType.BEDROOM, storey="UPPER_1").value == 2.0
    assert _count(plan, room_type=RoomType.SAUNA, storey="BASEMENT").value == 1.0
    assert _count(plan, room_type=RoomType.BEDROOM, storey="GROUND").value == 0.0  # covered
    assert _count(plan, category="STOREY", storey="GROUND").value == 1.0


def test_upper_matches_the_only_storey_above_ground() -> None:
    plan = _three_storeys()
    result = _count(plan, room_type=RoomType.BEDROOM, storey="UPPER")
    assert result.value == 2.0
    assert result.evidence == ["room_3", "room_4"]
    attic = _three_storeys(StoreyLevel.ATTIC)
    assert _count(attic, room_type=RoomType.BEDROOM, storey="UPPER").value == 2.0


def test_upper_with_several_upper_storeys_needs_clarification() -> None:
    plan = analysis(
        storeys=[
            storey(1, StoreyLevel.GROUND),
            storey(2, StoreyLevel.UPPER_1),
            storey(3, StoreyLevel.ATTIC),
        ],
        rooms=[room(1, RoomType.BEDROOM, storey="storey_2")],
    )
    result = _count(plan, room_type=RoomType.BEDROOM, storey="UPPER")
    assert result.status is AnswerStatus.NEEDS_CLARIFICATION
    assert result.value is None
    assert result.unit == "count"


def test_upper_without_upper_storey_cannot_answer() -> None:
    plan = analysis(storeys=[storey(1, StoreyLevel.GROUND)], rooms=[room(1, RoomType.BEDROOM)])
    result = _count(plan, room_type=RoomType.BEDROOM, storey="UPPER")
    assert result.status is AnswerStatus.CANNOT_ANSWER


def test_storey_with_level_none_matches_nothing() -> None:
    plan = _three_storeys(attic=None)
    for level in ("UPPER", "UPPER_1"):
        result = _count(plan, room_type=RoomType.BEDROOM, storey=level)
        assert result.status is AnswerStatus.CANNOT_ANSWER, level
        assert result.value is None
    single_unknown = analysis(rooms=[room(1, RoomType.KITCHEN)])  # storey_1, level None
    assert (
        _count(single_unknown, room_type=RoomType.KITCHEN, storey="GROUND").status
        is AnswerStatus.CANNOT_ANSWER
    )


def test_invalid_storey_value_cannot_answer() -> None:
    result = _count(_three_storeys(), room_type=RoomType.BEDROOM, storey="MEZZANINE")
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert "MEZZANINE" in result.explanation


def test_candidate_without_storey_id_cannot_answer() -> None:
    plan = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[
            room(1, RoomType.BEDROOM, storey=None),
            room(2, RoomType.BEDROOM, storey="storey_1"),
        ],
        fixtures=[fixture(1, FixtureType.SINK, storey=None)],
    )
    result = _count(plan, room_type=RoomType.BEDROOM, storey="GROUND")
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert "storey" in result.explanation
    # an unassigned element of another type does not block the question
    plan2 = plan.model_copy(update={"rooms": [room(2, RoomType.BEDROOM, storey="storey_1")]})
    assert _count(plan2, room_type=RoomType.BEDROOM, storey="GROUND").value == 1.0


# ------------------------------------------------------------------------------ labels


def test_label_matching_ignores_case_and_punctuation() -> None:
    plan = analysis(
        rooms=[
            room(1, RoomType.BEDROOM, label="MH 1", area=11.0),
            room(2, RoomType.BEDROOM, label="MH-2", area=9.5),
            room(3, RoomType.BEDROOM, label=None, area=8.0),
        ]
    )
    q = question(Intent.AREA, [ref("ROOM", label="mh2")], aggregation=Aggregation.SINGLE)
    result = _ok(answer(q, plan))
    assert (result.value, result.evidence) == (9.5, ["room_2"])
    empty_label = question(Intent.AREA, [ref("ROOM", label="--")])
    assert _ok(answer(empty_label, plan)).status is AnswerStatus.CANNOT_ANSWER


def test_label_on_storey_name_and_on_openings() -> None:
    plan = analysis(
        storeys=[storey(1, StoreyLevel.GROUND, "1. KRS"), storey(2, StoreyLevel.UPPER_1, "2. KRS")],
        openings=[opening(1, "DOOR", storey="storey_1")],
    )
    assert _count(plan, category="STOREY", label="2 krs").evidence == ["storey_2"]
    door = _count(plan, category="DOOR", label="D1")
    assert door.status is AnswerStatus.CANNOT_ANSWER


def test_normalize_label() -> None:
    assert normalize_label("Schlaf-Zimmer 2") == "schlafzimmer2"
    assert normalize_label("KPH/WC") == "kphwc"
    assert normalize_label("Kylpyhuone ä") == "kylpyhuoneä"


# ---------------------------------------------------------------------------- ordinals


def test_ordinal_uses_numeric_id_order() -> None:
    rooms = [room(n, RoomType.BEDROOM, area=float(n)) for n in (10, 3, 2)]
    plan = analysis(rooms=rooms)
    q = question(
        Intent.AREA,
        [ref("ROOM", room_type=RoomType.BEDROOM, ordinal=2)],
        aggregation=Aggregation.SINGLE,
    )
    result = _ok(answer(q, plan))
    assert (result.value, result.evidence) == (3.0, ["room_3"])
    third = q.model_copy(update={"targets": [ref("ROOM", room_type=RoomType.BEDROOM, ordinal=3)]})
    assert _ok(answer(third, plan)).evidence == ["room_10"]


@pytest.mark.parametrize("ordinal", [0, 4, -1])
def test_ordinal_out_of_range_cannot_answer(ordinal: int) -> None:
    plan = analysis(rooms=[room(n, RoomType.BEDROOM) for n in (1, 2, 3)])
    result = _count(plan, room_type=RoomType.BEDROOM, ordinal=ordinal)
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.value is None


def test_id_sort_key() -> None:
    ids = ["room_10", "room_2", "x", "room_1"]
    assert sorted(ids, key=id_sort_key) == ["room_1", "room_2", "room_10", "x"]


def test_resolution_order_storey_type_label_ordinal() -> None:
    plan = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[
            room(1, RoomType.BEDROOM, storey="storey_1", label="MH"),
            room(2, RoomType.BEDROOM, storey="storey_2", label="MH"),
            room(3, RoomType.KITCHEN, storey="storey_2", label="MH"),
            room(4, RoomType.BEDROOM, storey="storey_2", label="MH"),
        ],
    )
    result = _count(plan, room_type=RoomType.BEDROOM, storey="UPPER_1", label="mh", ordinal=2)
    assert result.evidence == ["room_4"]


# --------------------------------------------------------------------------- categories


def test_categories_select_their_elements() -> None:
    plan = analysis(
        rooms=[room(1, RoomType.KITCHEN), room(2, RoomType.OTHER)],
        openings=[opening(1, "DOOR"), opening(1, "WINDOW"), opening(2, "WINDOW")],
        fixtures=[fixture(1, FixtureType.SINK), fixture(2, FixtureType.TOILET)],
    )
    assert _count(plan, category="ROOM").value == 2.0
    assert _count(plan, category="DOOR").evidence == ["door_1"]
    assert _count(plan, category="WINDOW").evidence == ["window_1", "window_2"]
    assert _count(plan, category="FIXTURE").value == 2.0
    assert _count(plan, category="FIXTURE", fixture_type=FixtureType.SINK).value == 1.0
    assert _count(plan, category="STOREY").value == 1.0


def test_storey_count_without_any_storey_cannot_answer() -> None:
    result = _count(analysis(storeys=[]), category="STOREY")
    assert result.status is AnswerStatus.CANNOT_ANSWER
