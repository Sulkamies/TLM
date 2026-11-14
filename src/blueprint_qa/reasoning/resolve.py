"""Target resolution: ``EntityRef`` → plan elements (A0 binding decisions, R10.2).

Order: storey → room_type / fixture_type → label → ordinal. Raises ``Stop`` when the
target cannot be resolved (never returns a silent zero for an unresolvable target).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from blueprint_qa.contracts import (
    VOCABULARIES,
    BlueprintAnalysis,
    EntityRef,
    Fixture,
    Opening,
    Room,
    Storey,
    StoreyLevel,
)
from blueprint_qa.reasoning.outcome import cannot, clarify

Element = Room | Opening | Fixture | Storey

# Storey levels that lie above GROUND (used for the question level UPPER, decision 004).
ABOVE_GROUND: frozenset[StoreyLevel] = frozenset(
    {
        StoreyLevel.UPPER,
        StoreyLevel.UPPER_1,
        StoreyLevel.UPPER_2,
        StoreyLevel.UPPER_3,
        StoreyLevel.ATTIC,
    }
)

# Warnings by which an analysis declares what it can see (zero-evidence rule).
ROOM_TYPES_WARNING = "ROOM_TYPES_DETECTED"
FIXTURE_TYPES_WARNING = "FIXTURE_TYPES_DETECTED"
OPENING_KINDS_WARNING = "OPENING_KINDS_DETECTED"

# Values that need not be listed for an untyped target to count as covered.
_UNTYPED_EXEMPT = frozenset({"OTHER", "UNKNOWN"})

_ID_NUMBER = re.compile(r"(\d+)$")


@dataclass(frozen=True)
class Match:
    """The elements one target resolved to."""

    ref: EntityRef
    elements: tuple[Element, ...]  # for WHOLE_PLAN: the rooms in scope
    narrowed: bool  # a label or ordinal filter was applied


def id_sort_key(element_id: str) -> tuple[int, int, str]:
    """``room_3`` before ``room_10``; ids without a trailing number go last, by text."""
    found = _ID_NUMBER.search(element_id)
    if found is None:
        return (1, 0, element_id)
    return (0, int(found.group(1)), element_id)


def normalize_label(text: str) -> str:
    """Case-insensitive, ignoring everything that is not alphanumeric."""
    return "".join(ch for ch in text.casefold() if ch.isalnum())


def storey_scope(ref: EntityRef, analysis: BlueprintAnalysis) -> frozenset[str] | None:
    """Ids of the storeys the target names, or None if it names no storey."""
    if ref.storey is None:
        return None
    try:
        level = StoreyLevel(ref.storey)
    except ValueError:
        raise cannot("storey_not_found", storey=ref.storey) from None
    if level is StoreyLevel.UPPER:
        matched = [s for s in analysis.storeys if s.level in ABOVE_GROUND]
        if len(matched) > 1:
            raise clarify("upper_ambiguous", what=(ref,))
    else:
        matched = [s for s in analysis.storeys if s.level is level]
    if not matched:
        raise cannot("storey_not_found", storey=ref.storey)
    return frozenset(s.id for s in matched)


def _candidates(ref: EntityRef, analysis: BlueprintAnalysis) -> list[Element]:
    category = ref.category
    if category in ("ROOM", "WHOLE_PLAN"):
        return [
            r
            for r in analysis.rooms
            if category == "WHOLE_PLAN" or ref.room_type is None or r.room_type is ref.room_type
        ]
    if category in ("DOOR", "WINDOW"):
        return [o for o in analysis.openings if o.kind == category]
    if category == "FIXTURE":
        return [
            f
            for f in analysis.fixtures
            if ref.fixture_type is None or f.fixture_type is ref.fixture_type
        ]
    if category == "STOREY":
        return list(analysis.storeys)
    # WALL, STAIR: the contract carries no such elements.
    raise cannot("no_category_data", what=(ref,))


def _label_of(element: Element) -> str | None:
    if isinstance(element, Room):
        return element.label_text
    if isinstance(element, Storey):
        return element.name
    return None


def resolve(ref: EntityRef, analysis: BlueprintAnalysis) -> Match:
    """Resolve one target. Raises ``Stop`` (CANNOT_ANSWER / NEEDS_CLARIFICATION)."""
    candidates = _candidates(ref, analysis)
    scope = storey_scope(ref, analysis)
    if scope is not None:
        if ref.category == "STOREY":
            candidates = [e for e in candidates if e.id in scope]
        else:
            if any(_storey_id(e) is None for e in candidates):
                raise cannot("storey_unknown", what=(ref,))
            candidates = [e for e in candidates if _storey_id(e) in scope]
    if ref.category == "WHOLE_PLAN":
        return Match(ref, tuple(candidates), narrowed=False)
    narrowed = False
    if ref.label is not None:
        narrowed = True
        wanted = normalize_label(ref.label)
        candidates = [
            e
            for e in candidates
            if wanted and (label := _label_of(e)) is not None and normalize_label(label) == wanted
        ]
    if ref.ordinal is not None:
        narrowed = True
        ordered = sorted(candidates, key=lambda e: id_sort_key(e.id))
        if ref.ordinal < 1 or ref.ordinal > len(ordered):
            raise cannot("ordinal_too_few", what=(ref,), n=len(ordered), ordinal=ref.ordinal)
        candidates = [ordered[ref.ordinal - 1]]
    return Match(ref, tuple(candidates), narrowed=narrowed)


def _storey_id(element: Element) -> str | None:
    return element.id if isinstance(element, Storey) else element.storey_id


# ----------------------------------------------------------------- zero-evidence rule


def detected_values(analysis: BlueprintAnalysis, warning: str, vocabulary: str) -> frozenset[str]:
    """Values listed in ``<warning>:<A,B,...>`` warnings, restricted to the vocabulary."""
    allowed = set(VOCABULARIES[vocabulary])
    prefix = f"{warning}:"
    found: set[str] = set()
    for line in analysis.warnings:
        if line.startswith(prefix):
            found.update(v.strip() for v in line[len(prefix) :].split(","))
    return frozenset(found & allowed)


def _covers_all(detected: frozenset[str], vocabulary: str) -> bool:
    return all(v in detected for v in VOCABULARIES[vocabulary] if v not in _UNTYPED_EXEMPT)


def zero_is_covered(match: Match, analysis: BlueprintAnalysis) -> bool:
    """True if the analysis declares it can see this kind of element (a 0 is evidence)."""
    if match.narrowed:
        return False  # a label/ordinal miss is not evidence of absence
    ref = match.ref
    if ref.category == "STOREY":
        # Covered because every analysis has at least one storey. An analysis with no
        # storeys at all breaks that premise, so its 0 is not evidence.
        return bool(analysis.storeys)
    if ref.category == "ROOM":
        rooms = detected_values(analysis, ROOM_TYPES_WARNING, "RoomType")
        if ref.room_type is None:
            return _covers_all(rooms, "RoomType")
        return ref.room_type.value in rooms
    if ref.category == "FIXTURE":
        fixtures = detected_values(analysis, FIXTURE_TYPES_WARNING, "FixtureType")
        if ref.fixture_type is None:
            return _covers_all(fixtures, "FixtureType")
        return ref.fixture_type.value in fixtures
    if ref.category in ("DOOR", "WINDOW"):
        return ref.category in detected_values(analysis, OPENING_KINDS_WARNING, "OpeningKind")
    return False
