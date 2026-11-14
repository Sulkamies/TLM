# 001: Fixture entities (toilet, sink, bathtub, shower, sauna bench)

- **Proposed by:** A0 (session launched by ry), 2026-11-14
- **Status:** PROPOSED. Not applied. Needs A0 + 1 human approval (R4.3, MINOR).
- **Affected roles:** A2 (can emit the new category), A3 (produces fixtures), A4 (counts/existence), A5 (fixtures/tests)
- **Breaking:** no (additive, optional). Version 1.0.0 → **1.1.0**.

## Motivation

The first raster analyzer (CubiCasa detector, `docs/requests/A3-cubicasa-detector-adapter.md`) detects
sanitary fixtures: `toilet, sink, bathtub, shower, sauna_bench`. Users ask "How many sinks are there?",
"Gibt es eine Badewanne?" and "Onko saunassa lauteet?". v1.0.0 cannot express these:
`EntityRef.category` has no fixture value and `BlueprintAnalysis` has no list to carry the detections.
Today such questions would be wrongly mapped to rooms (`TOILET` room ≠ toilet bowl) or be `UNSUPPORTED`.

## Exact diff

```python
# src/blueprint_qa/contracts/analysis.py
+class FixtureType(str, Enum):
+    TOILET = "TOILET"; SINK = "SINK"; BATHTUB = "BATHTUB"; SHOWER = "SHOWER"
+    SAUNA_BENCH = "SAUNA_BENCH"; OTHER = "OTHER"
+
+class Fixture(BaseModel):
+    id: str                              # "fixture_<n>"
+    storey_id: str | None
+    room_id: str | None                  # containing room if determined, else None
+    fixture_type: FixtureType
+    position: tuple[float, float]        # centre, in coordinate_space
+    source_ref: str | None
+    confidence: float

 class BlueprintAnalysis(BaseModel):
-    schema_version: str = "1.0.0"
+    schema_version: str = "1.1.0"
     ...
+    fixtures: list[Fixture] = []

# src/blueprint_qa/contracts/question.py
 class EntityRef(BaseModel):
-    category: Literal["ROOM", "DOOR", "WINDOW", "WALL", "STAIR", "STOREY", "WHOLE_PLAN"]
+    category: Literal["ROOM", "DOOR", "WINDOW", "WALL", "STAIR", "STOREY", "WHOLE_PLAN", "FIXTURE"]
     room_type: RoomType | None = None
+    fixture_type: FixtureType | None = None   # set iff category == "FIXTURE"
```

`schema_version` of `ParsedQuestion` also becomes `"1.1.0"`.

## Compatibility note

Adding an enum/Literal value is classed as additive by R4.3. However, a consumer still pinned to v1.0.0
would reject a `ParsedQuestion` with `category="FIXTURE"`. Because all components live in one repo and
R4.5 merges the change together with the adapting code, this is safe in practice.

## On approval

A0 applies the diff, regenerates `schema/*.json`, updates AGENTS.md §4.2 and merges everything together (R4.5).

---
_Note (A0 · ry · 2026-11-14):_ contracts are now at 1.0.1 (change 002), so this proposal would take them from
**1.0.1 → 1.1.0**. The `schema_version` lines in the diff above should read `"1.0.1"` → `"1.1.0"`.

_Note (A0 · ry · 2026-11-14):_ **ON HOLD** until the Blueprint Analyzer's output is final (decided by ry).
After change 003, `FixtureType` and the `"FIXTURE"` category go into `contracts/vocabulary.py` (with `DESCRIPTIONS`
entries). The `Fixture` model and `fixture_type` field stay in `analysis.py`/`question.py`. The diff above will be
revised to match the analyzer's final output before approval.

---
## Revision 2 (A0 · ry · 2026-11-14): final diff, aligned with the A3 detector

The analyzer's output is now known (A3 note, 2026-11-14), so the hold is lifted. Status: **PROPOSED, awaiting approval**
(A0 + 1 human, MINOR). Contracts **1.0.1 → 1.1.0** (with 004 applied in the same change).

```python
# contracts/vocabulary.py
class FixtureType(str, Enum):
    TOILET = "TOILET"; SINK = "SINK"; SHOWER = "SHOWER"; BATHTUB = "BATHTUB"
    SAUNA_BENCH = "SAUNA_BENCH"; OTHER = "OTHER"
DESCRIPTIONS["FixtureType"] = {
    "TOILET": "A toilet bowl (WC fixture). Not the TOILET room type.",
    "SINK": "A washbasin or kitchen sink.",
    "SHOWER": "A shower.",
    "BATHTUB": "A bathtub.",
    "SAUNA_BENCH": "A sauna bench (lauteet).",
    "OTHER": "A sanitary fixture not covered by the other values.",
}
EntityCategory = Literal[..., "WHOLE_PLAN", "FIXTURE"]          # + DESCRIPTIONS["EntityCategory"]["FIXTURE"]

# contracts/analysis.py
class Fixture(BaseModel):
    id: str                               # "fixture_<n>"
    storey_id: str | None
    room_id: str | None                   # containing room if determined
    fixture_type: FixtureType
    position: tuple[float, float]         # box centre, in coordinate_space
    source_ref: str | None
    confidence: Confidence
class BlueprintAnalysis(BaseModel):
    ...
    fixtures: list[Fixture] = []

# contracts/question.py
class EntityRef(BaseModel):
    ...
    fixture_type: FixtureType | None = None   # set iff category == "FIXTURE"
```

Notes: A3 suggested the name `fixture_kind`; `fixture_type` is kept for consistency with `room_type`. SHOWER and
BATHTUB stay separate values ("showers and bathtubs" = two targets with SUM). Applying this makes A2's synonym
coverage test fail until A2 adds en/de/fi words (MERGE_PLAN phase 2b, merged together per R4.5).

_Approval (2026-11-14):_ revision 2 **APPROVED** by human ry and by A0 (R4.3, MINOR). To be applied in MERGE_PLAN phase 2.

_Applied (A0 · ry · 2026-11-14):_ revision 2 **APPLIED** on branch `a0/ry/contracts-1.1` (MERGE_PLAN phase 2), together
with 004: `FixtureType` and `"FIXTURE"` in `vocabulary.py` (with `DESCRIPTIONS`), `Fixture` + `BlueprintAnalysis.fixtures`
in `analysis.py`, `EntityRef.fixture_type` in `question.py`. Contracts **1.1.0**, schemas regenerated, AGENTS.md §4.2
updated. Merged together with A2's phase 2b PR (R4.5).
