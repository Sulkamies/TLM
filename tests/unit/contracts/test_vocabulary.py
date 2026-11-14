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
    Opening,
    OpeningKind,
    Room,
    RoomType,
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


def test_models_use_the_vocabulary_types() -> None:
    assert EntityRef.model_fields["category"].annotation == EntityCategory
    assert Opening.model_fields["kind"].annotation == OpeningKind
    assert Room.model_fields["room_type"].annotation is RoomType
    assert analysis.RoomType is RoomType  # backwards-compatible import path


def test_no_other_contract_module_redeclares_plan_values() -> None:
    """Room/entity values may only be spelled out in vocabulary.py."""
    pattern = re.compile(r'"(BEDROOM|WHOLE_PLAN|STAIR|OPENING)"')
    for path in CONTRACTS_DIR.glob("*.py"):
        if path.name == "vocabulary.py":
            continue
        assert not pattern.search(path.read_text(encoding="utf-8")), path.name
