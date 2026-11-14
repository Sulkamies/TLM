"""Measures (AREA, LENGTH, PERIMETER, HEIGHT, VOLUME), DISTANCE, RATIO, COMPARISON, units."""

from __future__ import annotations

import math

import pytest
from reasoning_fakes import analysis, box, fixture, opening, question, ref, room, storey

from blueprint_qa.contracts import (
    Aggregation,
    Answer,
    AnswerStatus,
    BlueprintAnalysis,
    Comparison,
    FixtureType,
    Intent,
    RoomType,
    StoreyLevel,
)
from blueprint_qa.reasoning import answer

BED = ref("ROOM", room_type=RoomType.BEDROOM)
KITCHEN = ref("ROOM", room_type=RoomType.KITCHEN)


def _ok(result: object) -> Answer:
    assert isinstance(result, Answer)
    return result


def _metric_plan() -> BlueprintAnalysis:
    """PIXEL plan with a scale of 100 px/m."""
    return analysis(
        metric=True,
        ppm=100.0,
        rooms=[
            room(1, RoomType.BEDROOM, polygon=box(0, 0, 300, 400), area=12.0, conf=0.8),
            room(2, RoomType.BEDROOM, polygon=box(300, 0, 500, 300), area=6.0, conf=0.7),
            room(3, RoomType.KITCHEN, polygon=box(0, 400, 300, 700), area=9.0, height=2.5),
        ],
        openings=[opening(1, "DOOR", position=(150.0, 1000.0))],
        fixtures=[fixture(1, FixtureType.SINK, position=(150.0, 550.0))],
    )


# ----------------------------------------------------------------------------- AREA


@pytest.mark.parametrize(
    ("agg", "expected"),
    [
        (Aggregation.SUM, 18.0),
        (Aggregation.MAX, 12.0),
        (Aggregation.MIN, 6.0),
        (Aggregation.MEAN, 9.0),
    ],
)
def test_area_aggregations(agg: Aggregation, expected: float) -> None:
    result = _ok(answer(question(Intent.AREA, [BED], aggregation=agg), _metric_plan()))
    assert result.status is AnswerStatus.ANSWERED
    assert result.value == expected
    assert result.unit == "m2"
    assert result.evidence == ["room_1", "room_2"]
    assert result.confidence == 0.7


def test_area_single_zero_one_several() -> None:
    plan = _metric_plan()
    one = _ok(answer(question(Intent.AREA, [KITCHEN], aggregation=Aggregation.SINGLE), plan))
    assert (one.value, one.evidence) == (9.0, ["room_3"])
    several = _ok(answer(question(Intent.AREA, [BED], aggregation=Aggregation.SINGLE), plan))
    assert several.status is AnswerStatus.NEEDS_CLARIFICATION
    assert several.value is None
    assert several.unit == "m2"
    assert "2" in several.explanation
    none = _ok(
        answer(
            question(
                Intent.AREA,
                [ref("ROOM", room_type=RoomType.SAUNA)],
                aggregation=Aggregation.SINGLE,
            ),
            plan,
        )
    )
    assert none.status is AnswerStatus.CANNOT_ANSWER


def test_area_does_not_need_scale_but_needs_area_m2() -> None:
    labelled = analysis(rooms=[room(1, RoomType.KITCHEN, area=8.5)])
    result = _ok(answer(question(Intent.AREA, [KITCHEN]), labelled))
    assert result.value == 8.5
    unlabelled = analysis(rooms=[room(1, RoomType.KITCHEN), room(2, RoomType.KITCHEN, area=3.0)])
    missing = _ok(answer(question(Intent.AREA, [KITCHEN]), unlabelled))
    assert missing.status is AnswerStatus.CANNOT_ANSWER
    assert "unknown" in missing.explanation


def test_whole_plan_area_is_sum_of_rooms() -> None:
    result = _ok(answer(question(Intent.AREA, [ref("WHOLE_PLAN")]), _metric_plan()))
    assert result.value == 27.0
    assert result.evidence == ["room_1", "room_2", "room_3"]
    assert "sum over 3 room" in result.explanation
    empty = _ok(answer(question(Intent.AREA, [ref("WHOLE_PLAN")]), analysis()))
    assert empty.status is AnswerStatus.CANNOT_ANSWER
    raster = analysis(rooms=[room(1, RoomType.BEDROOM)])
    assert _ok(answer(question(Intent.AREA, [ref("WHOLE_PLAN")]), raster)).value is None


def test_storey_area_and_whole_plan_on_storey() -> None:
    plan = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[
            room(1, RoomType.KITCHEN, storey="storey_1", area=10.0),
            room(2, RoomType.BEDROOM, storey="storey_2", area=14.0),
            room(3, RoomType.BEDROOM, storey="storey_2", area=11.0),
        ],
    )
    up = _ok(answer(question(Intent.AREA, [ref("STOREY", storey="UPPER_1")]), plan))
    assert up.value == 25.0
    assert up.evidence == ["storey_2", "room_2", "room_3"]
    whole_up = _ok(answer(question(Intent.AREA, [ref("WHOLE_PLAN", storey="UPPER")]), plan))
    assert whole_up.value == 25.0
    total = _ok(answer(question(Intent.AREA, [ref("WHOLE_PLAN")]), plan))
    assert total.value == 35.0
    assert "all 2 storeys" in total.explanation
    per_storey_max = _ok(
        answer(question(Intent.AREA, [ref("STOREY")], aggregation=Aggregation.MAX), plan)
    )
    assert per_storey_max.value == 25.0


def test_storey_area_with_unassigned_rooms() -> None:
    two = analysis(
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[room(1, RoomType.KITCHEN, storey=None, area=10.0)],
    )
    q = question(Intent.AREA, [ref("STOREY", storey="GROUND")])
    assert _ok(answer(q, two)).status is AnswerStatus.CANNOT_ANSWER
    one = analysis(rooms=[room(1, RoomType.KITCHEN, storey=None, area=10.0)])
    assert _ok(answer(question(Intent.AREA, [ref("STOREY")]), one)).value == 10.0
    no_rooms = analysis(storeys=[storey(1, StoreyLevel.GROUND), storey(2)], rooms=[])
    q2 = question(Intent.AREA, [ref("STOREY", storey="GROUND")])
    assert _ok(answer(q2, no_rooms)).status is AnswerStatus.CANNOT_ANSWER


def test_area_of_door_not_applicable() -> None:
    result = _ok(answer(question(Intent.AREA, [ref("DOOR")]), _metric_plan()))
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert "cannot be computed" in result.explanation


# ------------------------------------------------------------------- LENGTH, PERIMETER


def test_length_is_longer_bbox_side_in_metres() -> None:
    q = question(Intent.LENGTH, [BED], aggregation=Aggregation.MAX)
    result = _ok(answer(q, _metric_plan()))
    assert result.value == pytest.approx(4.0)
    assert result.unit == "m"


def test_perimeter_pixel_and_metric() -> None:
    q = question(Intent.PERIMETER, [KITCHEN], aggregation=Aggregation.SINGLE)
    assert _ok(answer(q, _metric_plan())).value == pytest.approx(12.0)
    metric = analysis(
        metric=True,
        space="METRIC",
        rooms=[room(1, RoomType.KITCHEN, polygon=box(0, 0, 3, 4))],
    )
    assert _ok(answer(q, metric)).value == pytest.approx(14.0)


@pytest.mark.parametrize("intent", [Intent.LENGTH, Intent.PERIMETER, Intent.DISTANCE])
def test_geometry_without_scale_cannot_answer(intent: Intent) -> None:
    plan = analysis(rooms=[room(1, RoomType.KITCHEN), room(2, RoomType.BEDROOM)])
    targets = [KITCHEN, BED] if intent is Intent.DISTANCE else [KITCHEN]
    result = _ok(answer(question(intent, targets, aggregation=Aggregation.SINGLE), plan))
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert result.unit == "m"
    assert "scale" in result.explanation
    no_ppm = analysis(metric=True, ppm=None, rooms=plan.rooms)
    assert _ok(answer(question(intent, targets), no_ppm)).status is AnswerStatus.CANNOT_ANSWER


def test_degenerate_polygon_cannot_answer() -> None:
    plan = analysis(
        metric=True, ppm=10.0, rooms=[room(1, RoomType.KITCHEN, polygon=[(0, 0), (1, 1)])]
    )
    result = _ok(answer(question(Intent.LENGTH, [KITCHEN]), plan))
    assert result.status is AnswerStatus.CANNOT_ANSWER


def test_length_of_storey_not_applicable() -> None:
    result = _ok(answer(question(Intent.LENGTH, [ref("STOREY")]), _metric_plan()))
    assert result.status is AnswerStatus.CANNOT_ANSWER


# ---------------------------------------------------------------------- HEIGHT, VOLUME


def test_height_and_volume() -> None:
    plan = _metric_plan()
    h = _ok(answer(question(Intent.HEIGHT, [KITCHEN], aggregation=Aggregation.SINGLE), plan))
    assert (h.value, h.unit) == (2.5, "m")
    v = _ok(answer(question(Intent.VOLUME, [KITCHEN]), plan))
    assert (v.value, v.unit) == (22.5, "m3")
    no_h = _ok(answer(question(Intent.HEIGHT, [BED]), plan))
    assert no_h.status is AnswerStatus.CANNOT_ANSWER
    assert "height" in no_h.explanation
    no_v = _ok(answer(question(Intent.VOLUME, [BED]), plan))
    assert no_v.status is AnswerStatus.CANNOT_ANSWER
    no_area = analysis(rooms=[room(1, RoomType.KITCHEN, height=2.5)])
    assert _ok(answer(question(Intent.VOLUME, [KITCHEN]), no_area)).value is None


# --------------------------------------------------------------------------- DISTANCE


def test_distance_between_centroid_and_positions() -> None:
    plan = _metric_plan()
    q = question(Intent.DISTANCE, [KITCHEN, ref("DOOR")], aggregation=Aggregation.SINGLE)
    result = _ok(answer(q, plan))
    # kitchen centroid (150, 550) px, door (150, 1000) px, 100 px/m
    assert result.value == pytest.approx(4.5)
    assert result.evidence == ["room_3", "door_1"]
    sink = question(Intent.DISTANCE, [ref("FIXTURE", fixture_type=FixtureType.SINK), KITCHEN])
    assert _ok(answer(sink, plan)).value == pytest.approx(0.0)


def test_distance_needs_two_unique_targets() -> None:
    plan = _metric_plan()
    one = _ok(answer(question(Intent.DISTANCE, [KITCHEN]), plan))
    assert one.status is AnswerStatus.CANNOT_ANSWER
    several = _ok(answer(question(Intent.DISTANCE, [BED, KITCHEN]), plan))
    assert several.status is AnswerStatus.NEEDS_CLARIFICATION
    missing = _ok(
        answer(question(Intent.DISTANCE, [ref("ROOM", room_type=RoomType.SAUNA), KITCHEN]), plan)
    )
    assert missing.status is AnswerStatus.CANNOT_ANSWER
    whole = _ok(answer(question(Intent.DISTANCE, [ref("WHOLE_PLAN"), KITCHEN]), plan))
    assert whole.status is AnswerStatus.CANNOT_ANSWER


def test_distance_across_storeys_cannot_answer() -> None:
    plan = analysis(
        metric=True,
        ppm=10.0,
        storeys=[storey(1, StoreyLevel.GROUND), storey(2, StoreyLevel.UPPER_1)],
        rooms=[
            room(1, RoomType.KITCHEN, storey="storey_1"),
            room(2, RoomType.BEDROOM, storey="storey_2"),
        ],
    )
    result = _ok(answer(question(Intent.DISTANCE, [KITCHEN, BED]), plan))
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert "different storeys" in result.explanation


def test_distance_degenerate_room() -> None:
    plan = analysis(
        metric=True,
        ppm=10.0,
        rooms=[room(1, RoomType.KITCHEN, polygon=[]), room(2, RoomType.BEDROOM)],
    )
    assert _ok(answer(question(Intent.DISTANCE, [KITCHEN, BED]), plan)).value is None


# ------------------------------------------------------------------------------ RATIO


def test_ratio_of_areas() -> None:
    q = question(Intent.RATIO, [BED, ref("WHOLE_PLAN")], aggregation=Aggregation.SINGLE)
    result = _ok(answer(q, _metric_plan()))
    assert result.value == pytest.approx(18.0 / 27.0)
    assert result.unit == "ratio"
    assert result.evidence == ["room_1", "room_2", "room_3"]


def test_ratio_cannot_answer_paths() -> None:
    plan = _metric_plan()
    assert _ok(answer(question(Intent.RATIO, [BED]), plan)).status is AnswerStatus.CANNOT_ANSWER
    zero = analysis(
        rooms=[room(1, RoomType.BEDROOM, area=5.0), room(2, RoomType.KITCHEN, area=0.0)]
    )
    result = _ok(answer(question(Intent.RATIO, [BED, KITCHEN]), zero))
    assert result.status is AnswerStatus.CANNOT_ANSWER
    assert "zero" in result.explanation
    no_area = analysis(rooms=[room(1, RoomType.BEDROOM), room(2, RoomType.KITCHEN, area=4.0)])
    assert _ok(answer(question(Intent.RATIO, [BED, KITCHEN]), no_area)).value is None
    requested = question(Intent.RATIO, [BED, ref("WHOLE_PLAN")], requested_unit="ft2")
    assert _ok(answer(requested, plan)).unit == "ratio"


# ------------------------------------------------------------------------- COMPARISON


@pytest.mark.parametrize(
    ("operator", "threshold", "expected"),
    [
        ("GT", 8.0, 1.0),
        ("GT", 9.0, 0.0),
        ("GE", 9.0, 1.0),
        ("LT", 9.0, 0.0),
        ("LE", 9.0, 1.0),
        ("EQ", 9.0, 1.0),
        ("EQ", 9.000001, 0.0),
    ],
)
def test_comparison_area_threshold(operator: str, threshold: float, expected: float) -> None:
    comp = Comparison(measure="AREA", operator=operator, threshold=threshold)  # type: ignore[arg-type]
    q = question(Intent.COMPARISON, [KITCHEN], comparison=comp, aggregation=Aggregation.SINGLE)
    result = _ok(answer(q, _metric_plan()))
    assert (result.value, result.unit) == (expected, "boolean")
    assert result.evidence == ["room_3"]


def test_comparison_between_two_targets() -> None:
    comp = Comparison(measure="AREA", operator="GT", threshold=None)
    q = question(Intent.COMPARISON, [KITCHEN, BED], comparison=comp, aggregation=Aggregation.MAX)
    result = _ok(answer(q, _metric_plan()))
    assert result.value == 0.0  # 9 m² is not greater than 12 m²
    assert result.evidence == ["room_3", "room_1", "room_2"]
    assert "not greater than" in result.explanation


def test_comparison_count_follows_zero_rule() -> None:
    comp = Comparison(measure="COUNT", operator="GE", threshold=2.0)
    q = question(Intent.COMPARISON, [BED], comparison=comp)
    assert _ok(answer(q, _metric_plan())).value == 1.0
    garage = question(Intent.COMPARISON, [ref("ROOM", room_type=RoomType.GARAGE)], comparison=comp)
    assert _ok(answer(garage, _metric_plan())).status is AnswerStatus.CANNOT_ANSWER
    saunas = Comparison(measure="COUNT", operator="LT", threshold=1.0)
    q2 = question(Intent.COMPARISON, [ref("ROOM", room_type=RoomType.SAUNA)], comparison=saunas)
    assert _ok(answer(q2, _metric_plan())).value == 1.0  # covered zero < 1


def test_comparison_cannot_answer_paths() -> None:
    plan = _metric_plan()
    no_comp = question(Intent.COMPARISON, [KITCHEN])
    assert _ok(answer(no_comp, plan)).status is AnswerStatus.CANNOT_ANSWER
    one_target = question(
        Intent.COMPARISON,
        [KITCHEN],
        comparison=Comparison(measure="AREA", operator="GT", threshold=None),
    )
    assert _ok(answer(one_target, plan)).status is AnswerStatus.CANNOT_ANSWER
    length_no_scale = question(
        Intent.COMPARISON,
        [KITCHEN],
        comparison=Comparison(measure="LENGTH", operator="GT", threshold=3.0),
    )
    raster = analysis(rooms=[room(1, RoomType.KITCHEN)])
    assert _ok(answer(length_no_scale, raster)).status is AnswerStatus.CANNOT_ANSWER
    height = question(
        Intent.COMPARISON,
        [BED],
        comparison=Comparison(measure="HEIGHT", operator="GT", threshold=2.0),
    )
    assert _ok(answer(height, plan)).status is AnswerStatus.CANNOT_ANSWER


def test_comparison_length_with_scale() -> None:
    comp = Comparison(measure="LENGTH", operator="GT", threshold=2.5)
    q = question(Intent.COMPARISON, [KITCHEN], comparison=comp)
    assert _ok(answer(q, _metric_plan())).value == 1.0  # 3 m > 2.5 m


# ------------------------------------------------------------------------------ units


def test_requested_unit_conversion_not_rounded() -> None:
    plan = _metric_plan()
    ft2 = _ok(answer(question(Intent.AREA, [KITCHEN], requested_unit="ft2"), plan))
    assert (ft2.value, ft2.unit) == (9.0 * 10.7639, "ft2")
    assert "ft²" in ft2.explanation
    ft = _ok(answer(question(Intent.LENGTH, [KITCHEN], requested_unit="ft"), plan))
    assert ft.unit == "ft"
    assert ft.value == pytest.approx(3.0 * 3.28084)
    ft3 = _ok(answer(question(Intent.VOLUME, [KITCHEN], requested_unit="ft3"), plan))
    assert (ft3.value, ft3.unit) == (22.5 * 35.3147, "ft3")
    m2 = _ok(answer(question(Intent.AREA, [KITCHEN], requested_unit="m2"), plan))
    assert (m2.value, m2.unit) == (9.0, "m2")


def test_mismatched_requested_unit_keeps_si() -> None:
    q = question(Intent.AREA, [KITCHEN], requested_unit="ft")
    result = _ok(answer(q, _metric_plan()))
    assert (result.value, result.unit) == (9.0, "m2")
    count = question(Intent.COUNT, [KITCHEN], requested_unit="ft2")
    assert _ok(answer(count, _metric_plan())).unit == "count"


def test_unit_set_also_without_value() -> None:
    raster = analysis(rooms=[room(1, RoomType.KITCHEN)])
    q = question(Intent.LENGTH, [KITCHEN], requested_unit="ft")
    result = _ok(answer(q, raster))
    assert (result.status, result.value, result.unit) == (
        AnswerStatus.CANNOT_ANSWER,
        None,
        "ft",
    )


def test_value_is_plain_float() -> None:
    result = _ok(answer(question(Intent.AREA, [KITCHEN]), _metric_plan()))
    assert isinstance(result.value, float)
    assert math.isfinite(result.value)
