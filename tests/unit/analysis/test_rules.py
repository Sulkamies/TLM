"""The tuned selection rules (spec §B) and the bounds check (spec §C), on hand-made detections."""

from __future__ import annotations

import pytest

from blueprint_qa.analysis.label_tables import load_detector_table
from blueprint_qa.analysis.raster.raw import RawOutput
from blueprint_qa.analysis.raster.rules import (
    Item,
    check_bounds,
    clusters,
    det,
    iou,
    select,
    union_box,
)
from blueprint_qa.analysis.settings import AnalysisSettings, load_settings
from blueprint_qa.contracts import FixtureType, RoomType


@pytest.fixture
def settings() -> AnalysisSettings:
    return load_settings()


def item(cls: str, conf: float, box: tuple[float, float, float, float]) -> Item:
    return Item(cls, conf, box)


def test_settings_match_the_tuned_values(settings: AnalysisSettings) -> None:
    assert settings.threshold("window") == 0.4
    assert settings.threshold("not_a_class") == settings.default_threshold == 0.35
    assert settings.dup_iou("door") == 0.3
    assert settings.dup_iou("floor") == 1.0  # absent = off


def test_det_applies_threshold_and_sorts_by_confidence(settings: AnalysisSettings) -> None:
    xs = [
        item("sink", 0.19, (0, 0, 1, 1)),
        item("sink", 0.3, (2, 2, 3, 3)),
        item("sink", 0.9, (5, 5, 6, 6)),
    ]
    assert [x.conf for x in det(xs, "sink", settings)] == [0.9, 0.3]


def test_det_removes_duplicates_greedily(settings: AnalysisSettings) -> None:
    a = item("door", 0.9, (0, 0, 10, 10))
    dup = item("door", 0.8, (1, 0, 11, 10))  # IoU ~0.82 >= 0.3
    other = item("door", 0.7, (20, 0, 30, 10))
    assert det([dup, a, other], "door", settings) == [a, other]


def test_iou_of_disjoint_and_degenerate_boxes() -> None:
    assert iou((0, 0, 1, 1), (2, 2, 3, 3)) == 0.0
    assert iou((0, 0, 0, 0), (0, 0, 0, 0)) == 0.0
    assert iou((0, 0, 2, 2), (0, 0, 2, 2)) == 1.0


def test_bench_clusters_join_touching_boxes() -> None:
    a = item("sauna_bench", 0.9, (0, 0, 10, 4))
    b = item("sauna_bench", 0.9, (0, 6, 10, 10))  # gap 2 < grown 2 + 2
    far = item("sauna_bench", 0.9, (100, 100, 110, 104))
    groups = clusters([a, b, far], grow=0.5)
    assert sorted(len(g) for g in groups) == [1, 2]
    assert len(clusters([a, b], grow=0.0)) == 2


def test_bath_room_rule(settings: AnalysisSettings) -> None:
    table = load_detector_table()
    wet = item("room_bath", 0.9, (0, 0, 10, 10))
    wc = item("room_bath", 0.9, (20, 0, 30, 10))
    empty = item("room_bath", 0.9, (40, 0, 50, 10))
    fixtures = [
        item("shower", 0.9, (1, 1, 3, 3)),
        item("toilet", 0.9, (2, 5, 4, 7)),  # in the wet room too: still wet
        item("toilet", 0.9, (22, 2, 24, 4)),
        item("bathtub", 0.5, (41, 1, 49, 4)),  # below the bathtub threshold 0.75: ignored
    ]
    sel = select([wet, wc, empty, *fixtures], settings, table)
    types = {r.box: t for r, t in sel.rooms}
    assert types == {
        wet.box: RoomType.BATHROOM,
        wc.box: RoomType.TOILET,
        empty.box: RoomType.BATHROOM,
    }
    assert sorted(t.value for _, t in sel.fixtures) == ["SHOWER", "TOILET", "TOILET"]


def test_sauna_polygon_prefers_smallest_containing_sauna_room(settings: AnalysisSettings) -> None:
    table = load_detector_table()
    benches = [
        item("sauna_bench", 0.8, (10, 10, 20, 14)),
        item("sauna_bench", 0.6, (10, 16, 20, 20)),
    ]
    big = item("room_sauna", 0.9, (0, 0, 100, 100))
    small = item("room_sauna", 0.9, (5, 5, 25, 25))
    sel = select([*benches, big, small], settings, table)
    assert len(sel.saunas) == 1
    group = sel.saunas[0]
    assert group.box == small.box and not group.from_benches and group.conf == 0.8
    assert [t for _, t in sel.fixtures] == [FixtureType.SAUNA_BENCH] * 2
    # room_sauna on its own is not a sauna (the tuned rule counts bench clusters only)
    assert select([big], settings, table).saunas == ()


def test_sauna_without_room_box_uses_bench_union(settings: AnalysisSettings) -> None:
    benches = [
        item("sauna_bench", 0.8, (10, 10, 20, 14)),
        item("sauna_bench", 0.6, (12, 16, 22, 20)),
    ]
    group = select(benches, settings, load_detector_table()).saunas[0]
    assert group.from_benches and group.box == union_box(b.box for b in benches) == (10, 10, 22, 20)


def _raw(dets: list[dict[str, object]], ocr: list[dict[str, object]] | None = None) -> RawOutput:
    return RawOutput.model_validate({"size": [100, 50], "detections": dets, "ocr": ocr or []})


def test_bounds_clamp_small_overshoot_and_drop_the_rest() -> None:
    raw = _raw(
        [
            {"cls": "door", "conf": 0.9, "box": [-0.5, 0, 10, 50.8]},  # clamped
            {"cls": "door", "conf": 0.9, "box": [-5, 0, 10, 10]},  # too far out
            {"cls": "door", "conf": 0.9, "box": [10, 10, 10, 20]},  # degenerate
        ],
        [
            {"text": "MH", "conf": 0.9, "poly": [[1, 1], [9, 1], [9, 5], [1, 5]]},
            {"text": "X", "conf": 0.9, "poly": [[1, 1], [200, 1], [200, 5], [1, 5]]},
            {"text": "-", "conf": 0.9, "poly": [[1, 1], [9, 1], [9, 1], [1, 1]]},
        ],
    )
    items, texts, dropped = check_bounds(raw, tolerance=1.0)
    assert [i.box for i in items] == [(0.0, 0.0, 10.0, 50.0)]
    assert [t.text for t in texts] == ["MH"]
    assert dropped == 4
