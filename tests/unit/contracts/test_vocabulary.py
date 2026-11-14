"""The plan-element vocabulary is complete, described, and the only source of values."""

from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

from blueprint_qa.contracts import (
    DESCRIPTIONS,
    VOCABULARIES,
    EntityCategory,
    EntityRef,
    Fixture,
    FixtureType,
    Opening,
    OpeningKind,
    Room,
    RoomType,
    Storey,
    StoreyLevel,
    analysis,
)

CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "src" / "blueprint_qa" / "contracts"


def test_every_value_has_exactly_one_description() -> None:
    assert set(DESCRIPTIONS) == set(VOCABULARIES)
    for name, values in VOCABULARIES.items():
        assert set(DESCRIPTIONS[name]) == set(values), f"{name}: descriptions out of sync"
        assert all(text.strip() for text in DESCRIPTIONS[name].values())


def test_registry_matches_the_types() -> None:
    assert VOCABULARIES["RoomType"] == tuple(m.value for m in RoomType)
    assert VOCABULARIES["EntityCategory"] == get_args(EntityCategory)
    assert VOCABULARIES["OpeningKind"] == get_args(OpeningKind)
    assert VOCABULARIES["FixtureType"] == tuple(m.value for m in FixtureType)
    assert VOCABULARIES["StoreyLevel"] == tuple(m.value for m in StoreyLevel)


def test_models_use_the_vocabulary_types() -> None:
    assert EntityRef.model_fields["category"].annotation == EntityCategory
    assert Opening.model_fields["kind"].annotation == OpeningKind
    assert Room.model_fields["room_type"].annotation is RoomType
    assert analysis.RoomType is RoomType  # backwards-compatible import path
    assert Fixture.model_fields["fixture_type"].annotation is FixtureType
    assert EntityRef.model_fields["fixture_type"].annotation == FixtureType | None
    assert Storey.model_fields["level"].annotation == StoreyLevel | None


def test_v1_1_0_vocabulary_values() -> None:
    # contract changes 001 (revision 2) and 004 (lighter option)
    assert VOCABULARIES["FixtureType"] == (
        "TOILET",
        "SINK",
        "SHOWER",
        "BATHTUB",
        "SAUNA_BENCH",
        "OTHER",
    )
    assert VOCABULARIES["StoreyLevel"] == (
        "BASEMENT",
        "GROUND",
        "UPPER",
        "UPPER_1",
        "UPPER_2",
        "UPPER_3",
        "ATTIC",
    )
    assert VOCABULARIES["EntityCategory"][-1] == "FIXTURE"


def test_no_other_contract_module_redeclares_plan_values() -> None:
    """Room/entity values may only be spelled out in vocabulary.py."""
    pattern = re.compile(r'"(BEDROOM|WHOLE_PLAN|STAIR|OPENING|FIXTURE|SAUNA_BENCH|UPPER_1)"')
    for path in CONTRACTS_DIR.glob("*.py"):
        if path.name == "vocabulary.py":
            continue
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
