# 004: Fixed storey levels (`StoreyLevel`)

- **Proposed by:** A2 (session launched by ry), 2026-11-14
- **Requested by human:** ry, answering OPEN_QUESTIONS Q5: "For now, create fixed values."
- **Status:** PROPOSED. Needs A0 to apply it (R4.1) and the approvals below.
- **Affected roles:** A0 (contracts, schemas, AGENTS.md §4.2), A2 (producer of `EntityRef.storey`),
  A3 (producer of `Storey`), A4 (matches question storeys to plan storeys), A5 (fixtures).
- **Breaking:** part 2 is breaking (type change); parts 1 and 3 are additive. See "Approval" below.

## Motivation

`EntityRef.storey` is free text, so "alakerta", "Erdgeschoss" and "ground floor" are three different
values, and A4 would have to match them against plan labels such as "1. krs" or "EG" in any language.
That breaks design principle 1 (language-independent output). Floor numbering also differs by language:
Finnish "1. kerros" and US "first floor" are the ground floor, while German "1. OG" and British
"first floor" are one floor above it. A fixed set of levels removes both problems: A2 maps the question
to a level, A3 maps each plan storey to a level, and A4 compares the two values.

## Diff

1. `contracts/vocabulary.py` (additive):

```python
class StoreyLevel(str, Enum):
    BASEMENT = "BASEMENT"; GROUND = "GROUND"; UPPER = "UPPER"
    UPPER_1 = "UPPER_1"; UPPER_2 = "UPPER_2"; UPPER_3 = "UPPER_3"; ATTIC = "ATTIC"

DESCRIPTIONS["StoreyLevel"] = {
    "BASEMENT": "Floor below ground level (cellar, basement).",
    "GROUND": "Floor at ground or entrance level. Finnish '1. kerros' and US English 'first floor' mean this level.",
    "UPPER": "A floor above ground named without a number ('upstairs', 'the upper floor').",
    "UPPER_1": "First floor above ground level (British/European 'first floor', German '1. OG', Finnish '2. kerros').",
    "UPPER_2": "Second floor above ground level (German '2. OG', Finnish '3. kerros').",
    "UPPER_3": "Third floor above ground level (German '3. OG', Finnish '4. kerros').",
    "ATTIC": "Attic or loft floor directly under the roof.",
}
VOCABULARIES["StoreyLevel"] = _values(StoreyLevel)
```

2. `contracts/question.py`, **breaking** (type change):

```diff
-    storey: str | None = None           # "ground floor", "2nd floor"
+    storey: StoreyLevel | None = None   # shared enum, see vocabulary.py
```

3. `contracts/analysis.py` (additive, optional field):

```diff
 class Storey(BaseModel):
     id: str; name: str | None; elevation_m: float | None
+    level: StoreyLevel | None = None    # A3 maps the plan's storey label / elevation to a level
```

Then regenerate `schema/*.json`, update AGENTS.md §4.2, and bump the contract version.

## Semantics for A4

- A question storey `UPPER` matches the only storey above `GROUND` when there is exactly one.
  Otherwise A4 returns `NEEDS_CLARIFICATION`.
- A plan storey with `level=None` matches no question storey. If that leaves the target unresolved,
  A4 returns `CANNOT_ANSWER`, never `0.0`.

## Approval

- Part 2 changes a field type, so R4.3 makes it a MAJOR change that needs **2 of the 4 humans**.
- Lower-cost alternative (MINOR, A0 + 1 human): keep `storey: str | None` and document that A2 only
  emits `StoreyLevel` values in it. Add part 3 as is. The schema then does not enforce the values, but
  A2 already validates them.

## A2 status (works with either option)

A2 already emits only these values. They live in `src/blueprint_qa/question/interim_vocabulary.yaml`,
and A2's LLM output validator rejects anything else. Once `StoreyLevel` exists in
`contracts.VOCABULARIES`, `vocabulary_view.py` ignores the interim entry automatically (a unit test
covers this). After that, A2 only has to delete the entry and re-record its cassettes.

## Decision (ry, 2026-11-14, recorded by A2)

ry chose the **lighter option** (MINOR): apply part 1 (`StoreyLevel` in `vocabulary.py`) and part 3
(`Storey.level`). **Do not apply part 2**: `EntityRef.storey` stays `str | None`, and AGENTS.md §4.2 should say that
it holds a `StoreyLevel` value. This still needs A0's approval under R4.3 (ry is the 1 human). A2 now takes the
values from `contracts.VOCABULARIES` as soon as they exist there, and keeps enforcing them on `EntityRef.storey`.
