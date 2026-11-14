"""analyze(): regression against A3's tuned counts, contract rules and every error path."""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from blueprint_qa.analysis import analyze
from blueprint_qa.analysis.analyzer import ANALYZER_VERSION
from blueprint_qa.analysis.raster import detector as detector_module
from blueprint_qa.contracts import (
    CONTRACT_VERSION,
    BlueprintAnalysis,
    ErrorEnvelope,
    InputFormat,
    RoomType,
    Stage,
)

from ._support import RECORDINGS, REQUEST_ID, recorded, run, validation_for

UseDetector = Callable[[dict[str, Any] | Exception], None]

# A0 ran A3's rules at 35597e2 on the three recordings (spec phase 3 brief). Order:
# windows, floors, toilets, sinks, showers+bathtubs, doors, saunas, kitchens, bedrooms,
# WC rooms, bathrooms, balconies.
EXPECTED_COUNTS = {
    "colorful-11397": (13, 2, 2, 3, 3, 12, 1, 0, 1, 0, 1, 1),
    "colorful-12200": (1, 1, 1, 2, 1, 3, 0, 0, 0, 0, 1, 0),
    "colorful-2002": (4, 1, 1, 2, 1, 7, 1, 1, 2, 0, 1, 1),
}


def _counts(a: BlueprintAnalysis) -> tuple[int, ...]:
    kinds = Counter(o.kind for o in a.openings)
    fix = Counter(f.fixture_type.value for f in a.fixtures)
    rooms = Counter(r.room_type for r in a.rooms)
    return (
        kinds["WINDOW"],
        len(a.storeys),
        fix["TOILET"],
        fix["SINK"],
        fix["SHOWER"] + fix["BATHTUB"],
        kinds["DOOR"],
        rooms[RoomType.SAUNA],
        rooms[RoomType.KITCHEN],
        rooms[RoomType.BEDROOM],
        rooms[RoomType.TOILET],
        rooms[RoomType.BATHROOM],
        rooms[RoomType.BALCONY],
    )


def _analysis(name: str, use_detector: UseDetector) -> BlueprintAnalysis:
    raw = recorded(name)
    use_detector(raw)
    result = run(raw)
    assert isinstance(result, BlueprintAnalysis), result
    return result


# ------------------------------------------------------------------ regression and contract


@pytest.mark.parametrize("name", RECORDINGS)
def test_counts_reproduce_tuned_rules(name: str, use_detector: UseDetector) -> None:
    assert _counts(_analysis(name, use_detector)) == EXPECTED_COUNTS[name]


@pytest.mark.parametrize("name", RECORDINGS)
def test_output_follows_the_contract(name: str, use_detector: UseDetector) -> None:
    a = _analysis(name, use_detector)
    w, h = recorded(name)["size"]
    again = BlueprintAnalysis.model_validate_json(a.model_dump_json())
    assert again == a
    assert a.request_id == REQUEST_ID
    assert a.schema_version == CONTRACT_VERSION
    assert a.source_format == InputFormat.PNG
    assert a.coordinate_space == "PIXEL"
    assert a.analyzer_version == ANALYZER_VERSION
    assert a.metric_available is False
    assert a.scale.source == "NONE" and a.scale.pixels_per_meter is None
    assert a.adjacency == []

    ids = [s.id for s in a.storeys] + [r.id for r in a.rooms]
    ids += [o.id for o in a.openings] + [f.id for f in a.fixtures]
    assert len(ids) == len(set(ids))
    storey_ids = {s.id for s in a.storeys}
    room_ids = {r.id for r in a.rooms}

    points = [p for r in a.rooms for p in r.polygon]
    points += [o.position for o in a.openings] + [f.position for f in a.fixtures]
    points += [(t.bbox[0], t.bbox[1]) for t in a.texts] + [(t.bbox[2], t.bbox[3]) for t in a.texts]
    assert all(0 <= x <= w and 0 <= y <= h for x, y in points)

    confs = [r.confidence for r in a.rooms] + [o.confidence for o in a.openings]
    confs += [f.confidence for f in a.fixtures] + [t.confidence for t in a.texts]
    assert all(0.0 <= c <= 1.0 for c in confs)

    for r in a.rooms:
        assert r.area_m2 is None and r.height_m is None and r.area_source is None
        assert r.storey_id is None or r.storey_id in storey_ids
        assert len(r.polygon) == 4
    for o in a.openings:
        assert o.connects == [] and o.width_m is None
        assert o.id.startswith(o.kind.lower() + "_")
    for f in a.fixtures:
        assert f.room_id is None or f.room_id in room_ids
        assert f.id.startswith("fixture_")


@pytest.mark.parametrize("name", RECORDINGS)
def test_coverage_warnings_are_present(name: str, use_detector: UseDetector) -> None:
    warnings = _analysis(name, use_detector).warnings
    assert "ROOM_TYPES_DETECTED:BALCONY,BATHROOM,BEDROOM,KITCHEN,SAUNA,TOILET" in warnings
    assert "FIXTURE_TYPES_DETECTED:BATHTUB,SAUNA_BENCH,SHOWER,SINK,TOILET" in warnings
    assert "OPENING_KINDS_DETECTED:DOOR,WINDOW" in warnings
    assert "ROOMS_ARE_BOXES" in warnings and "NO_ADJACENCY" in warnings


def test_two_floor_boxes_give_two_storeys(use_detector: UseDetector) -> None:
    a = _analysis("colorful-11397", use_detector)
    assert [s.id for s in a.storeys] == ["storey_1", "storey_2"]
    assert "MULTIPLE_STOREYS:2" in a.warnings and "STOREY_FROM_BOX_CENTRE" in a.warnings


def test_same_input_gives_same_output(use_detector: UseDetector) -> None:
    assert _analysis("colorful-2002", use_detector) == _analysis("colorful-2002", use_detector)


def test_request_id_passed_through_unchanged(use_detector: UseDetector) -> None:
    raw = recorded("colorful-12200")
    use_detector(raw)
    result = run(raw, request_id="not-a-uuid but kept as is")
    assert isinstance(result, BlueprintAnalysis)
    assert result.request_id == "not-a-uuid but kept as is"


def test_jpeg_and_pdf_keep_their_source_format(use_detector: UseDetector) -> None:
    raw = recorded("colorful-12200")
    use_detector(raw)
    for fmt in (InputFormat.JPEG, InputFormat.PDF):
        result = run(raw, fmt=fmt)
        assert isinstance(result, BlueprintAnalysis) and result.source_format == fmt


def test_vision_packages_are_never_imported() -> None:
    assert not {"torch", "ultralytics", "easyocr"} & set(sys.modules)


# ------------------------------------------------------------------ errors (never raises)


def _error(result: object, code: str) -> ErrorEnvelope:
    assert isinstance(result, ErrorEnvelope), result
    assert result.code == code
    assert result.stage == Stage.ANALYSIS
    assert result.request_id == REQUEST_ID
    assert result.retryable is False
    return result


def test_missing_plan_image_is_invalid_input() -> None:
    _error(analyze(validation_for(None, with_image=False)), "INVALID_INPUT")


def test_ifc_is_not_supported_yet() -> None:
    env = _error(
        analyze(validation_for(None, fmt=InputFormat.IFC, with_image=False)), "ANALYSIS_FAILED"
    )
    assert "not supported yet" in env.message


def test_missing_weights_give_model_load_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("BP_WEIGHTS", str(tmp_path / "absent.pt"))
    env = _error(run(recorded("colorful-12200")), "MODEL_LOAD_FAILED")
    assert "absent.pt" in env.details["reason"]
    assert str(tmp_path) not in env.message


def test_detector_exception_gives_analysis_failed(use_detector: UseDetector) -> None:
    use_detector(RuntimeError("CUDA error"))
    env = _error(run(recorded("colorful-12200")), "ANALYSIS_FAILED")
    assert env.details == {"exception": "RuntimeError"}


def test_malformed_detector_output_gives_analysis_failed(use_detector: UseDetector) -> None:
    raw = recorded("colorful-12200")
    use_detector({"size": raw["size"], "detections": [{"cls": "door"}], "ocr": []})
    env = _error(run(raw), "ANALYSIS_FAILED")
    assert env.details["reason"] == "detector_output_invalid"


def test_confidence_outside_unit_interval_gives_analysis_failed(use_detector: UseDetector) -> None:
    raw = recorded("colorful-12200")
    bad = dict(raw, detections=[{"cls": "door", "conf": 1.5, "box": [1, 1, 5, 5]}])
    use_detector(bad)
    _error(run(raw), "ANALYSIS_FAILED")


def test_size_mismatch_gives_analysis_failed(use_detector: UseDetector) -> None:
    raw = recorded("colorful-12200")
    use_detector(dict(raw, size=[raw["size"][0] + 1, raw["size"][1]]))
    env = _error(run(raw), "ANALYSIS_FAILED")
    assert env.details["reason"] == "size_mismatch"


def test_unexpected_failure_gives_internal_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> None:
        raise KeyError("analysis")

    monkeypatch.setattr("blueprint_qa.analysis.analyzer.load_settings", boom)
    env = _error(run(recorded("colorful-12200")), "INTERNAL_ERROR")
    assert env.details == {"exception": "KeyError"}


def test_detector_is_loaded_once_per_process(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    built: list[Path] = []

    class Stub:
        def __init__(self, weights: Path, **kwargs: Any) -> None:
            built.append(weights)

    weights = tmp_path / "w.pt"
    weights.write_bytes(b"x")
    monkeypatch.setenv("BP_WEIGHTS", str(weights))
    monkeypatch.setattr(detector_module, "Detector", Stub)
    from blueprint_qa.analysis.settings import load_settings

    s = load_settings()
    first = detector_module.get_detector(s)
    assert detector_module.get_detector(s) is first
    assert built == [weights]


def test_contract_violation_gives_analysis_failed(
    use_detector: UseDetector, monkeypatch: pytest.MonkeyPatch
) -> None:
    from blueprint_qa.contracts import Scale

    def invalid(**kwargs: Any) -> BlueprintAnalysis:
        Scale.model_validate({"pixels_per_meter": None, "source": "GUESS", "confidence": 0.0})
        raise AssertionError("unreachable")

    raw = recorded("colorful-12200")
    use_detector(raw)
    monkeypatch.setattr("blueprint_qa.analysis.analyzer.build_analysis", invalid)
    env = _error(run(raw), "ANALYSIS_FAILED")
    assert env.details["reason"] == "contract_violation"
