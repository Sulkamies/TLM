"""COUNT and EXISTENCE, the zero-evidence rule and the CubiCasa-style regression."""

from __future__ import annotations

import pytest
from reasoning_fakes import (
    FIXTURE_TYPES_RASTER,
    OPENING_KINDS_RASTER,
    ROOM_TYPES_RASTER,
    analysis,
    box,
    fixture,
    opening,
    question,
    ref,
    room,
    storey,
)

from blueprint_qa.contracts import (
    VOCABULARIES,
    Aggregation,
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    EntityRef,
    FixtureType,
    Intent,
    RoomType,
    StoreyLevel,
)
from blueprint_qa.reasoning import answer


def _ok(result: object) -> Answer:
    assert isinstance(result, Answer)
    return result


# ------------------------------------------------------------------ CubiCasa regression


def cubicasa_like() -> BlueprintAnalysis:
    """Two floor boxes, as A3's raster adapter would emit for a typical Finnish plan."""
    s1, s2 = "storey_1", "storey_2"
    windows = [opening(i, "WINDOW", storey=s1 if i <= 7 else s2) for i in range(1, 14)]
    doors = [opening(i, "DOOR", storey=s1 if i <= 8 else s2) for i in range(1, 13)]
    fixtures = [
        fixture(1, FixtureType.TOILET, storey=s1),
        fixture(2, FixtureType.TOILET, storey=s2),
        fixture(3, FixtureType.SINK, storey=s1),
        fixture(4, FixtureType.SINK, storey=s1),
        fixture(5, FixtureType.SINK, storey=s2),
        fixture(6, FixtureType.SHOWER, storey=s1),
        fixture(7, FixtureType.SHOWER, storey=s2),
        fixture(8, FixtureType.BATHTUB, storey=s2),
        fixture(9, FixtureType.SAUNA_BENCH, storey=s1),
        fixture(10, FixtureType.SAUNA_BENCH, storey=s1),
    ]
    rooms = [
        room(1, RoomType.SAUNA, storey=s1, polygon=box(10, 10, 60, 50), label="S", conf=0.66),
        room(2, RoomType.BEDROOM, storey=s2, polygon=box(500, 10, 640, 120), label="MH"),
        room(3, RoomType.BATHROOM, storey=s1, polygon=box(60, 10, 110, 50), label="KPH"),
        room(4, RoomType.BALCONY, storey=s2, polygon=box(500, 200, 600, 240)),
    ]
    return analysis(
        storeys=[
            storey(1, StoreyLevel.GROUND, "1. KRS"),
            storey(2, StoreyLevel.UPPER_1, "2. KRS"),
        ],
        rooms=rooms,
        openings=windows + doors,
        fixtures=fixtures,
        warnings=[
            ROOM_TYPES_RASTER,
            FIXTURE_TYPES_RASTER,
            OPENING_KINDS_RASTER,
            "ROOMS_ARE_BOXES",
            "MULTIPLE_STOREYS:2",
            "STOREY_FROM_BOX_CENTRE",
            "NO_ADJACENCY",
            "NO_OPENING_CONNECTIVITY",
            "FIXTURE_ROOM_FROM_BOX_CENTRE",
        ],
    )


CUBICASA_CASES: list[tuple[str, list[EntityRef], float]] = [
    ("windows", [ref("WINDOW")], 13.0),
    ("doors", [ref("DOOR")], 12.0),
    ("toilets", [ref("FIXTURE", fixture_type=FixtureType.TOILET)], 2.0),
    ("sinks", [ref("FIXTURE", fixture_type=FixtureType.SINK)], 3.0),
    (
        "showers or bathtubs",
        [
            ref("FIXTURE", fixture_type=FixtureType.SHOWER),
            ref("FIXTURE", fixture_type=FixtureType.BATHTUB),
        ],
        3.0,
    ),
    ("saunas", [ref("ROOM", room_type=RoomType.SAUNA)], 1.0),
    ("bedrooms", [ref("ROOM", room_type=RoomType.BEDROOM)], 1.0),
    ("bathrooms", [ref("ROOM", room_type=RoomType.BATHROOM)], 1.0),
    ("balconies", [ref("ROOM", room_type=RoomType.BALCONY)], 1.0),
    ("kitchens (covered zero)", [ref("ROOM", room_type=RoomType.KITCHEN)], 0.0),
    ("storeys", [ref("STOREY")], 2.0),
]


@pytest.mark.parametrize(("name", "targets", "expected"), CUBICASA_CASES)
def test_cubicasa_counts(name: str, targets: list[EntityRef], expected: float) -> None:
    result = _ok(answer(question(Intent.COUNT, targets), cubicasa_like()))
    assert result.status is AnswerStatus.ANSWERED, name
    assert result.value == expected
    assert result.unit == "count"
    assert len(result.evidence) == int(expected)


def test_cubicasa_living_rooms_cannot_answer() -> None:
    q = question(Intent.COUNT, [ref("ROOM", room_type=RoomType.LIVING_ROOM)])
    result = _ok(answer(q, cubicasa_like()))
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.value is None
    assert result.unit == "count"
    assert "cannot reliably detect" in result.explanation


def test_cubicasa_multi_storey_note_and_storey_filter() -> None:
    a = cubicasa_like()
    all_windows = _ok(answer(question(Intent.COUNT, [ref("WINDOW")]), a))
    assert "all 2 storeys" in all_windows.explanation
    upstairs = _ok(answer(question(Intent.COUNT, [ref("WINDOW", storey="UPPER")]), a))
    assert upstairs.value == 6.0
    assert "storeys are included" not in upstairs.explanation
    ground = _ok(answer(question(Intent.COUNT, [ref("DOOR", storey="GROUND")]), a))
    assert ground.value == 8.0
    storeys = _ok(answer(question(Intent.COUNT, [ref("STOREY")]), a))
    assert "storeys are included" not in storeys.explanation


def test_cubicasa_sauna_existence_and_confidence() -> None:
    q = question(Intent.EXISTENCE, [ref("ROOM", room_type=RoomType.SAUNA)], confidence=0.97)
    result = _ok(answer(q, cubicasa_like()))
    assert result.value == 1.0
    assert result.unit == "boolean"
    assert result.evidence == ["room_1"]
    assert result.confidence == 0.66


# --------------------------------------------------------------------------- COUNT


def test_count_confidence_is_min_of_question_and_elements() -> None:
    rooms = [room(1, RoomType.BEDROOM, conf=0.8), room(2, RoomType.BEDROOM, conf=0.4)]
    q = question(Intent.COUNT, [ref("ROOM", room_type=RoomType.BEDROOM)], confidence=0.9)
    result = _ok(answer(q, analysis(rooms=rooms)))
    assert result.value == 2.0
    assert result.confidence == 0.4
    assert result.evidence == ["room_1", "room_2"]


def test_count_ignores_aggregation() -> None:
    rooms = [room(1, RoomType.BEDROOM), room(2, RoomType.BEDROOM)]
    for agg in Aggregation:
        q = question(Intent.COUNT, [ref("ROOM", room_type=RoomType.BEDROOM)], aggregation=agg)
        assert _ok(answer(q, analysis(rooms=rooms))).value == 2.0


def test_count_all_rooms_needs_full_room_coverage() -> None:
    rooms = [room(1, RoomType.BEDROOM)]
    q = question(Intent.COUNT, [ref("ROOM")])
    assert _ok(answer(q, analysis(rooms=rooms))).value == 1.0  # positive count: fine
    empty = _ok(answer(q, analysis()))
    assert empty.status is AnswerStatus.CANNOT_ANSWER  # raster list is not complete
    full = ",".join(v for v in VOCABULARIES["RoomType"] if v not in ("OTHER", "UNKNOWN"))
    covered = _ok(answer(q, analysis(warnings=[f"ROOM_TYPES_DETECTED:{full}"])))
    assert covered.status is AnswerStatus.ANSWERED
    assert covered.value == 0.0
    assert covered.evidence == []
    assert covered.confidence == 0.95


def test_count_all_fixtures_coverage() -> None:
    q = question(Intent.COUNT, [ref("FIXTURE")])
    raster = _ok(answer(q, analysis()))  # the raster list has every type except OTHER
    assert (raster.status, raster.value) == (AnswerStatus.ANSWERED, 0.0)
    partial = ["FIXTURE_TYPES_DETECTED:BATHTUB,SAUNA_BENCH,SHOWER,TOILET"]  # no SINK
    assert _ok(answer(q, analysis(warnings=partial))).status is AnswerStatus.CANNOT_ANSWER


def test_zero_rule_parses_warnings_with_vocabulary() -> None:
    q = question(Intent.COUNT, [ref("ROOM", room_type=RoomType.SAUNA)])
    noisy = ["ROOM_TYPES_DETECTED: SAUNA , HOT_TUB", "SOMETHING_ELSE:SAUNA"]
    assert _ok(answer(q, analysis(warnings=noisy))).value == 0.0
    missing = _ok(answer(q, analysis(warnings=["OPENING_KINDS_DETECTED:DOOR"])))
    assert missing.status is AnswerStatus.CANNOT_ANSWER
    unknown_only = _ok(answer(q, analysis(warnings=["ROOM_TYPES_DETECTED:HOT_TUB"])))
    assert unknown_only.status is AnswerStatus.CANNOT_ANSWER


def test_zero_rule_for_openings_and_fixtures() -> None:
    windows = question(Intent.COUNT, [ref("WINDOW")])
    assert _ok(answer(windows, analysis())).value == 0.0
    assert _ok(answer(windows, analysis(warnings=[]))).status is AnswerStatus.CANNOT_ANSWER
    benches = question(Intent.COUNT, [ref("FIXTURE", fixture_type=FixtureType.SAUNA_BENCH)])
    assert _ok(answer(benches, analysis())).value == 0.0
    other = question(Intent.COUNT, [ref("FIXTURE", fixture_type=FixtureType.OTHER)])
    assert _ok(answer(other, analysis())).status is AnswerStatus.CANNOT_ANSWER


def test_count_sum_with_one_uncovered_zero_target_cannot_answer() -> None:
    rooms = [room(1, RoomType.BEDROOM)]
    q = question(
        Intent.COUNT,
        [ref("ROOM", room_type=RoomType.BEDROOM), ref("ROOM", room_type=RoomType.OFFICE)],
    )
    assert _ok(answer(q, analysis(rooms=rooms))).status is AnswerStatus.CANNOT_ANSWER


def test_count_label_miss_is_not_a_zero() -> None:
    rooms = [room(1, RoomType.BEDROOM, label="MH 1")]
    q = question(Intent.COUNT, [ref("ROOM", room_type=RoomType.BEDROOM, label="MH 7")])
    result = _ok(answer(q, analysis(rooms=rooms)))
    assert result.status is AnswerStatus.CANNOT_ANSWER


@pytest.mark.parametrize("category", ["WALL", "STAIR"])
def test_wall_and_stair_have_no_data(category: str) -> None:
    for intent in (Intent.COUNT, Intent.EXISTENCE, Intent.LENGTH):
        result = _ok(answer(question(intent, [ref(category)]), analysis(metric=True, ppm=10)))
        assert result.status is AnswerStatus.CANNOT_ANSWER
        assert result.value is None


def test_whole_plan_cannot_be_counted() -> None:
    for intent in (Intent.COUNT, Intent.EXISTENCE):
        result = _ok(answer(question(intent, [ref("WHOLE_PLAN")]), analysis()))
        assert result.status is AnswerStatus.CANNOT_ANSWER


# ------------------------------------------------------------------------- EXISTENCE


def test_existence_yes_no_and_uncovered() -> None:
    a = analysis(rooms=[room(1, RoomType.SAUNA)])
    yes = _ok(answer(question(Intent.EXISTENCE, [ref("ROOM", room_type=RoomType.SAUNA)]), a))
    assert (yes.value, yes.unit, yes.evidence) == (1.0, "boolean", ["room_1"])
    no = _ok(answer(question(Intent.EXISTENCE, [ref("ROOM", room_type=RoomType.KITCHEN)]), a))
    assert (no.status, no.value, no.evidence) == (AnswerStatus.ANSWERED, 0.0, [])
    unknown = _ok(answer(question(Intent.EXISTENCE, [ref("ROOM", room_type=RoomType.GARAGE)]), a))
    assert unknown.status is AnswerStatus.CANNOT_ANSWER
    assert unknown.unit == "boolean"


def test_existence_any_of_several_targets() -> None:
    a = analysis(fixtures=[fixture(1, FixtureType.BATHTUB)])
    q = question(
        Intent.EXISTENCE,
        [
            ref("FIXTURE", fixture_type=FixtureType.SHOWER),
            ref("FIXTURE", fixture_type=FixtureType.BATHTUB),
        ],
    )
    assert _ok(answer(q, a)).value == 1.0
    # positive evidence wins even if another target could not be confirmed
    q2 = question(
        Intent.EXISTENCE,
        [ref("ROOM", room_type=RoomType.GARAGE), ref("FIXTURE", fixture_type=FixtureType.BATHTUB)],
    )
    assert _ok(answer(q2, a)).value == 1.0


def test_existence_with_label_miss_cannot_answer() -> None:
    a = analysis(rooms=[room(1, RoomType.SAUNA, label="S")])
    q = question(Intent.EXISTENCE, [ref("ROOM", label="Sauna 2")])
    assert _ok(answer(q, a)).status is AnswerStatus.CANNOT_ANSWER


def test_existence_on_named_storey_with_covered_zero() -> None:
    a = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[room(1, RoomType.SAUNA, storey="storey_1")],
    )
    q = question(Intent.EXISTENCE, [ref("ROOM", room_type=RoomType.SAUNA, storey="UPPER_1")])
    result = _ok(answer(q, a))
    assert (result.status, result.value) == (AnswerStatus.ANSWERED, 0.0)
