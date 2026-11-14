"""Field-by-field mapping (spec §C) on small hand-made detector outputs."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from blueprint_qa.contracts import BlueprintAnalysis, RoomType, StoreyLevel

from ._support import run

UseDetector = Callable[[dict[str, Any] | Exception], None]


def det(cls: str, box: list[float], conf: float = 0.9) -> dict[str, Any]:
    return {"cls": cls, "conf": conf, "box": box}


def text(t: str, x0: float, y0: float, x1: float, y1: float, conf: float = 0.9) -> dict[str, Any]:
    return {"text": t, "conf": conf, "poly": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]}


def analyse(
    use_detector: UseDetector, dets: list[dict[str, Any]], ocr: list[dict[str, Any]] | None = None
) -> BlueprintAnalysis:
    raw = {"size": [400, 200], "detections": dets, "ocr": ocr or []}
    use_detector(raw)
    result = run(raw)
    assert isinstance(result, BlueprintAnalysis), result
    return result


def test_no_floor_box_gives_one_fallback_storey(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector,
        [det("door", [10, 10, 20, 30]), det("floor", [0, 0, 400, 200], conf=0.3)],  # below 0.45
        [text("2. KERROS", 5, 5, 60, 15)],
    )
    assert [(s.id, s.name, s.level) for s in a.storeys] == [
        ("storey_1", "2. KERROS", StoreyLevel.UPPER_1)
    ]
    assert "NO_FLOOR_BOX" in a.warnings
    assert a.openings[0].storey_id == "storey_1"


def test_fallback_storey_name_needs_exactly_one_storey_text(use_detector: UseDetector) -> None:
    a = analyse(use_detector, [], [text("1. krs", 5, 5, 60, 15), text("2 KRS", 205, 5, 260, 15)])
    assert a.storeys[0].name is None and a.storeys[0].level is None


def test_storeys_named_from_text_inside_their_box(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector,
        [
            det("floor", [200, 0, 400, 200], conf=0.8),
            det("floor", [0, 0, 200, 200], conf=0.9),
            det("toilet", [250, 50, 260, 60]),
            det("window", [100, 199, 110, 200]),
        ],
        [
            text("1,KERROS", 10, 150, 90, 160),
            text("KERROSALA 54", 210, 150, 290, 160),  # floor area, not a storey
            text("7 KRS", 220, 170, 280, 180),  # 7 -> no level
        ],
    )
    s1, s2 = a.storeys
    assert (s1.name, s1.level) == ("1,KERROS", StoreyLevel.GROUND)
    assert (s2.name, s2.level) == ("7 KRS", None)
    assert a.fixtures[0].storey_id == "storey_2"
    assert a.openings[0].storey_id == "storey_1"
    assert "MULTIPLE_STOREYS:2" in a.warnings


def test_element_outside_every_floor_box_has_no_storey(use_detector: UseDetector) -> None:
    a = analyse(use_detector, [det("floor", [0, 0, 100, 100]), det("door", [300, 10, 310, 30])])
    assert a.openings[0].storey_id is None
    assert "NO_STOREY_FOR:door_1" in a.warnings


def test_overlapping_floor_boxes_pick_the_most_confident(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector,
        [
            det("floor", [0, 0, 400, 200], conf=0.6),  # storey_1 in reading order
            det("floor", [0, 10, 300, 200], conf=0.95),  # storey_2
            det("sink", [10, 10, 20, 20]),  # centre inside both
        ],
    )
    assert a.fixtures[0].storey_id == "storey_2"


def test_rooms_ids_polygons_and_labels(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector,
        [
            det("room_kitchen", [200, 10, 300, 90]),
            det("room_bedroom", [10, 10, 100, 90]),
            det("room_balcony", [10, 100, 100, 190]),
        ],
        [
            text("2", 60, 40, 70, 50),
            text("MH", 20, 20, 40, 30),
            text("K", 240, 40, 250, 50),
            text("noise", 20, 20, 40, 30, conf=0.0),
        ],
    )
    by_id = {r.id: r for r in a.rooms}
    assert [by_id[i].room_type for i in ("room_1", "room_2", "room_3")] == [
        RoomType.BEDROOM,
        RoomType.KITCHEN,
        RoomType.BALCONY,
    ]
    assert by_id["room_1"].polygon == [(10, 10), (100, 10), (100, 90), (10, 90)]
    assert by_id["room_1"].label_text == "MH noise 2"  # reading order: y, then x
    assert by_id["room_2"].label_text == "K"
    assert by_id["room_3"].label_text is None
    assert len(a.texts) == 4


def test_fixture_room_is_the_smallest_containing_room(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector,
        [
            det("room_bedroom", [0, 0, 200, 200]),
            det("room_bath", [10, 10, 60, 60]),
            det("sink", [20, 20, 30, 30]),
            det("sink", [300, 20, 310, 30]),
        ],
    )
    bath = next(r for r in a.rooms if r.room_type == RoomType.BATHROOM)
    assert [f.room_id for f in a.fixtures] == [bath.id, None]
    assert [f.position for f in a.fixtures] == [(25.0, 25.0), (305.0, 25.0)]
    assert "FIXTURE_ROOM_FROM_BOX_CENTRE" in a.warnings


def test_sauna_from_benches_is_flagged(use_detector: UseDetector) -> None:
    a = analyse(
        use_detector, [det("sauna_bench", [10, 10, 50, 20]), det("sauna_bench", [10, 25, 50, 35])]
    )
    (sauna,) = a.rooms
    assert sauna.room_type == RoomType.SAUNA and sauna.polygon[0] == (10, 10)
    assert f"SAUNA_FROM_BENCHES:{sauna.id}" in a.warnings
    assert len(a.fixtures) == 2


def test_out_of_bounds_boxes_are_dropped_with_a_warning(use_detector: UseDetector) -> None:
    a = analyse(use_detector, [det("door", [390, 10, 450, 30]), det("door", [10, 10, 20, 30])])
    assert len(a.openings) == 1
    assert "BOX_OUT_OF_BOUNDS:1" in a.warnings


def test_empty_plan_still_gives_a_valid_analysis(use_detector: UseDetector) -> None:
    a = analyse(use_detector, [])
    assert len(a.storeys) == 1 and a.rooms == [] and a.openings == [] and a.fixtures == []
    assert "NO_OPENING_CONNECTIVITY" not in a.warnings
    assert "FIXTURE_ROOM_FROM_BOX_CENTRE" not in a.warnings
