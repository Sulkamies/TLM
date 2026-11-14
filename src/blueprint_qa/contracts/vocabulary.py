"""Plan-element vocabulary (AGENTS.md §4.2, v1.1.0). Custodian: A0.

THE SINGLE PLACE that defines what a floor plan can contain, as seen by both sides
of the pipeline:

* A3 (Blueprint Analyzer) may only *emit* these values.
* A2 (Question Interpreter) may only *ask about* these values. A2 builds its LLM
  prompt and output schema from this module at runtime, so it never re-declares them.
* A4 (Answer Reasoner) matches questions to plan elements by these values.

To change what the analyzer can report (e.g. contract change 001, fixtures), edit
this module through the AGENTS.md §4.3 process (001 and 004 were applied this way in v1.1.0):

1. Add or remove the value in the type below.
2. Add or remove its entry in ``DESCRIPTIONS`` (a unit test enforces 1:1 coverage).
3. Register any new vocabulary in ``VOCABULARIES`` and ``DESCRIPTIONS``.
4. Regenerate the schemas and update AGENTS.md §4.2.

No other contract module defines plan-element values.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import Enum
from typing import Literal, get_args


class RoomType(str, Enum):
    BEDROOM = "BEDROOM"
    BATHROOM = "BATHROOM"
    TOILET = "TOILET"
    KITCHEN = "KITCHEN"
    LIVING_ROOM = "LIVING_ROOM"
    DINING_ROOM = "DINING_ROOM"
    HALLWAY = "HALLWAY"
    GARAGE = "GARAGE"
    STORAGE = "STORAGE"
    CLOSET = "CLOSET"
    LAUNDRY = "LAUNDRY"
    SAUNA = "SAUNA"
    BALCONY = "BALCONY"
    OFFICE = "OFFICE"
    TECHNICAL = "TECHNICAL"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class FixtureType(str, Enum):  # since v1.1.0 (contract change 001)
    TOILET = "TOILET"
    SINK = "SINK"
    SHOWER = "SHOWER"
    BATHTUB = "BATHTUB"
    SAUNA_BENCH = "SAUNA_BENCH"
    OTHER = "OTHER"


class StoreyLevel(str, Enum):  # since v1.1.0 (contract change 004)
    BASEMENT = "BASEMENT"
    GROUND = "GROUND"
    UPPER = "UPPER"
    UPPER_1 = "UPPER_1"
    UPPER_2 = "UPPER_2"
    UPPER_3 = "UPPER_3"
    ATTIC = "ATTIC"


# Kinds of plan element a question can target (EntityRef.category).
EntityCategory = Literal[
    "ROOM", "DOOR", "WINDOW", "WALL", "STAIR", "STOREY", "WHOLE_PLAN", "FIXTURE"
]

# Kinds of opening the analyzer reports (Opening.kind).
OpeningKind = Literal["DOOR", "WINDOW", "OPENING"]


# --------------------------------------------------------------------------- semantics
# The agreed meaning of every value. A2 puts these in its LLM prompt; A3 uses them to
# decide what to emit. Keep them short, language-neutral and in English.

DESCRIPTIONS: Mapping[str, Mapping[str, str]] = {
    "RoomType": {
        "BEDROOM": "Room mainly for sleeping.",
        "BATHROOM": "Room with a shower or bathtub (may also contain a WC).",
        "TOILET": "Separate WC room without shower or bathtub. A room, not the toilet bowl.",
        "KITCHEN": "Cooking room or kitchen area, including kitchenettes.",
        "LIVING_ROOM": "Main living or lounge room.",
        "DINING_ROOM": "Room or area mainly for eating.",
        "HALLWAY": "Entrance hall, corridor or lobby.",
        "GARAGE": "Room for parking vehicles.",
        "STORAGE": "Storage room or walk-in storage.",
        "CLOSET": "Wardrobe or small closet.",
        "LAUNDRY": "Utility or laundry room.",
        "SAUNA": "Sauna room.",
        "BALCONY": "Balcony, terrace, loggia or similar outdoor space attached to the dwelling.",
        "OFFICE": "Study or work room.",
        "TECHNICAL": "Technical or plant room (heating, ventilation, electrical).",
        "OTHER": "A known room type not covered by the other values.",
        "UNKNOWN": "Room whose type cannot be determined.",
    },
    "EntityCategory": {
        "ROOM": "A room; narrow it down with room_type, label, ordinal or storey.",
        "DOOR": "A door.",
        "WINDOW": "A window.",
        "WALL": "A wall.",
        "STAIR": "A staircase.",
        "STOREY": "A whole floor level of the building.",
        "WHOLE_PLAN": "The whole plan or building (e.g. total floor area).",
        "FIXTURE": "A sanitary fixture (toilet bowl, sink, shower, bathtub, sauna bench); "
        "narrow it down with fixture_type.",
    },
    "OpeningKind": {
        "DOOR": "A door.",
        "WINDOW": "A window.",
        "OPENING": "An opening without a door or window leaf.",
    },
    "FixtureType": {
        "TOILET": "A toilet bowl (WC fixture). Not the TOILET room type.",
        "SINK": "A washbasin or kitchen sink.",
        "SHOWER": "A shower.",
        "BATHTUB": "A bathtub.",
        "SAUNA_BENCH": "A sauna bench (lauteet).",
        "OTHER": "A sanitary fixture not covered by the other values.",
    },
    "StoreyLevel": {
        "BASEMENT": "Floor below ground level (cellar, basement).",
        "GROUND": "Floor at ground or entrance level. Finnish '1. kerros' and US English "
        "'first floor' mean this level.",
        "UPPER": "A floor above ground named without a number ('upstairs', 'the upper floor').",
        "UPPER_1": "First floor above ground level (British/European 'first floor', "
        "German '1. OG', Finnish '2. kerros').",
        "UPPER_2": "Second floor above ground level (German '2. OG', Finnish '3. kerros').",
        "UPPER_3": "Third floor above ground level (German '3. OG', Finnish '4. kerros').",
        "ATTIC": "Attic or loft floor directly under the roof.",
    },
}


def _values(vocab: object) -> tuple[str, ...]:
    if isinstance(vocab, type) and issubclass(vocab, Enum):
        return tuple(str(member.value) for member in vocab)
    return tuple(str(v) for v in get_args(vocab))


# Name -> allowed values, in declaration order. Iterate over this rather than
# listing values by hand.
VOCABULARIES: Mapping[str, tuple[str, ...]] = {
    "RoomType": _values(RoomType),
    "EntityCategory": _values(EntityCategory),
    "OpeningKind": _values(OpeningKind),
    "FixtureType": _values(FixtureType),
    "StoreyLevel": _values(StoreyLevel),
}
