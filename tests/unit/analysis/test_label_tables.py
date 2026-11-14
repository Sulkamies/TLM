"""Label tables are validated against contracts.VOCABULARIES when loaded (criterion 4)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from blueprint_qa.analysis import label_tables
from blueprint_qa.analysis.label_tables import load_detector_table, load_language
from blueprint_qa.contracts import VOCABULARIES, StoreyLevel


def test_finnish_table_loads_and_uses_contract_values() -> None:
    fi = load_language("fi")
    assert {t.value for t in fi.room_codes} <= set(VOCABULARIES["RoomType"])
    assert fi.storey_levels["1"] == StoreyLevel.GROUND
    assert fi.storey_levels["2"] == StoreyLevel.UPPER_1


@pytest.mark.parametrize(
    ("label", "number"),
    [
        ("1. KERROS", "1"),
        ("2 krs", "2"),
        ("1,KERROS", "1"),
        ("3.kerr", "3"),
        ("KERROSALA 54", None),
        ("KERROS", None),
        ("KRS 1-6", None),
    ],
)
def test_storey_word(label: str, number: str | None) -> None:
    m = load_language("fi").storey_regex().search(label)
    assert (m.group(1) if m else None) == number


def test_room_codes_compile_and_match_whole_codes() -> None:
    fi = load_language("fi")
    bedroom = re.compile("^(" + "|".join(fi.room_codes[next(iter(fi.room_codes))]) + ")$")
    assert bedroom.match("MH2") and not bedroom.match("XMH")


def test_detector_table_matches_the_vocabulary() -> None:
    t = load_detector_table()
    assert t.room_types() == ["BALCONY", "BATHROOM", "BEDROOM", "KITCHEN", "SAUNA", "TOILET"]
    assert t.fixture_types() == ["BATHTUB", "SAUNA_BENCH", "SHOWER", "SINK", "TOILET"]
    assert t.opening_kinds() == ["DOOR", "WINDOW"]
    assert len(t.classes) == 13


def _with_table(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, name: str, body: str) -> None:
    (tmp_path / f"{name}.yaml").write_text(body, encoding="utf-8")
    monkeypatch.setattr(label_tables, "LABELS_DIR", tmp_path)


def test_unknown_room_type_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_table(
        tmp_path,
        monkeypatch,
        "xx",
        "room_codes: {ATTIC_ROOM: [A]}\nstorey_word: '(\\d)'\nstorey_levels: {}\n",
    )
    with pytest.raises(ValueError, match="not RoomType values"):
        load_language("xx")


def test_storey_word_needs_a_group(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_table(
        tmp_path, monkeypatch, "xy", "room_codes: {}\nstorey_word: 'KRS'\nstorey_levels: {}\n"
    )
    with pytest.raises(ValueError, match="group"):
        load_language("xy")


def test_table_must_be_a_mapping(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _with_table(tmp_path, monkeypatch, "xz", "- a list\n")
    with pytest.raises(ValueError, match="mapping"):
        load_language("xz")


def test_unknown_fixture_type_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = (label_tables.LABELS_DIR / "cubicasa_v2.yaml").read_text(encoding="utf-8")
    _with_table(tmp_path, monkeypatch, "bad", body.replace("sink: SINK", "sink: WASHBASIN"))
    with pytest.raises(ValueError, match="FixtureType"):
        load_detector_table("bad")


def test_unknown_detector_class_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    body = (label_tables.LABELS_DIR / "cubicasa_v2.yaml").read_text(encoding="utf-8")
    _with_table(tmp_path, monkeypatch, "bad2", body.replace("  sink: SINK", "  basin: SINK"))
    with pytest.raises(ValueError, match="unknown detector classes"):
        load_detector_table("bad2")
