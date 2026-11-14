"""Load and validate the label tables in ``analysis/labels/`` (AGENTS.md §6 A3; criterion 4).

No room, opening or fixture value is written in the analyzer code: it comes from these tables,
and every value is checked against ``contracts.VOCABULARIES`` when the table is loaded.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from blueprint_qa.contracts import VOCABULARIES, FixtureType, OpeningKind, RoomType, StoreyLevel

LABELS_DIR = Path(__file__).resolve().parent / "labels"
DETECTOR_TABLE = "cubicasa_v2"


def _read(name: str) -> dict[str, Any]:
    path = LABELS_DIR / f"{name}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"labels/{name}.yaml: top level must be a mapping")
    return data


def _check(name: str, vocabulary: str, values: list[Any]) -> None:
    allowed = VOCABULARIES[vocabulary]
    bad = sorted(str(v) for v in set(values) - set(allowed))
    if bad:
        raise ValueError(f"labels/{name}.yaml: {bad} are not {vocabulary} values")


class LanguageTable(BaseModel):
    """Room codes and storey words of one plan language (e.g. ``labels/fi.yaml``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    room_codes: dict[RoomType, tuple[str, ...]]
    storey_word: str = Field(min_length=1)
    storey_levels: dict[str, StoreyLevel]

    @model_validator(mode="after")
    def _compile(self) -> LanguageTable:
        if re.compile(self.storey_word).groups < 1:
            raise ValueError("storey_word needs a group for the storey number")
        for patterns in self.room_codes.values():
            for pattern in patterns:
                re.compile(pattern)
        return self

    def storey_regex(self) -> re.Pattern[str]:
        return re.compile(self.storey_word, re.IGNORECASE)


class BathRoomRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    cls: str = Field(alias="class")
    wet_fixtures: tuple[str, ...]
    wc_fixtures: tuple[str, ...]
    wet: RoomType
    wc_only: RoomType


class SaunaRule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    bench_class: str
    room_class: str
    room_type: RoomType


class DetectorTable(BaseModel):
    """What each detector class becomes (``labels/cubicasa_v2.yaml``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    classes: tuple[str, ...] = Field(min_length=1)
    storey_class: str
    rooms: dict[str, RoomType]
    bath_room: BathRoomRule
    sauna: SaunaRule
    openings: dict[str, OpeningKind]
    fixtures: dict[str, FixtureType]

    @model_validator(mode="after")
    def _known_classes(self) -> DetectorTable:
        used = [
            self.storey_class,
            *self.rooms,
            self.bath_room.cls,
            *self.bath_room.wet_fixtures,
            *self.bath_room.wc_fixtures,
            self.sauna.bench_class,
            self.sauna.room_class,
            *self.openings,
            *self.fixtures,
        ]
        unknown = sorted(set(used) - set(self.classes))
        if unknown:
            raise ValueError(f"unknown detector classes {unknown}")
        return self

    def room_types(self) -> list[str]:
        """Every room type this detector can produce, sorted."""
        types = {*self.rooms.values(), self.bath_room.wet, self.bath_room.wc_only}
        types.add(self.sauna.room_type)
        return sorted(t.value for t in types)

    def fixture_types(self) -> list[str]:
        """Every fixture type this detector can produce, sorted."""
        return sorted({t.value for t in self.fixtures.values()})

    def opening_kinds(self) -> list[str]:
        """Every opening kind this detector can produce, sorted."""
        return sorted(set(self.openings.values()))


@lru_cache(maxsize=4)
def load_language(lang: str) -> LanguageTable:
    data = _read(lang)
    _check(lang, "RoomType", list((data.get("room_codes") or {}).keys()))
    _check(lang, "StoreyLevel", list((data.get("storey_levels") or {}).values()))
    return LanguageTable.model_validate(data)


@lru_cache(maxsize=4)
def load_detector_table(name: str = DETECTOR_TABLE) -> DetectorTable:
    data = _read(name)
    bath = data.get("bath_room") or {}
    sauna = data.get("sauna") or {}
    _check(name, "RoomType", [*(data.get("rooms") or {}).values()])
    _check(name, "RoomType", [bath.get("wet"), bath.get("wc_only"), sauna.get("room_type")])
    _check(name, "OpeningKind", list((data.get("openings") or {}).values()))
    _check(name, "FixtureType", list((data.get("fixtures") or {}).values()))
    return DetectorTable.model_validate(data)
