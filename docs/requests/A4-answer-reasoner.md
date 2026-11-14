# Request to A4: the Answer Reasoner (`answer()`) and A0's binding decisions

- **From:** A0 (integration agent, session launched by ry), 2026-11-14.
- **To:** the A4 session (launched by ry), branch `a4/ry/answer-reasoner` from `main` (contracts 1.1.0).
- **Scope change:** MERGE_PLAN v3 had A4 out of scope. ry brought it into scope on 2026-11-14 (D-011). A4 is built in
  parallel with A3. Wiring A4 into the orchestrator is A0's job (MERGE_PLAN update, phase 5), not A4's.
- Where this brief is more specific than AGENTS.md §6 A4, this brief applies (A0 decides interface questions, R10.2).

## 1. Entry point and inputs

`src/blueprint_qa/reasoning/reasoner.py :: answer(question: ParsedQuestion, analysis: BlueprintAnalysis) -> Answer | ErrorEnvelope`,
exported only through `reasoning/__init__.py`. Never raises (R5.1). The only knowledge of the plan is the
`BlueprintAnalysis`; never import `blueprint_qa.analysis` or call A3. What a raster analysis looks like (PIXEL space,
`metric_available=False`, boxes as polygons, warning codes) is specified in `docs/requests/A3-analysis-adapter.md`,
"Verified mapping spec (phase 0)", sections C and I.

## 2. Binding decisions

1. **No LLM in A4 this round.** `value` is computed by deterministic code. `explanation` comes from fixed templates
   (a Python module) in **en, de and fi**, chosen by the primary subtag of `ParsedQuestion.language`. Any other language:
   English text and `Answer.language = "en"` (`Answer.language` is the language of the explanation). See Q10.
2. **Before computing:** `question.request_id != analysis.request_id` → `INVALID_INPUT`. Intent `UNSUPPORTED` →
   `UNSUPPORTED_QUESTION`. `clarification_needed` set → `NEEDS_CLARIFICATION` with that text, language = question.language.
3. **Unit by intent, also when `value` is None** (Q9, option c): COUNT → `count`; AREA → `m2`; LENGTH, PERIMETER,
   DISTANCE, HEIGHT → `m`; VOLUME → `m3`; RATIO → `ratio`; EXISTENCE, COMPARISON → `boolean`. Convert only if
   `requested_unit` is set (1 m = 3.28084 ft; 1 m² = 10.7639 ft²; 1 m³ = 35.3147 ft³). Never round.
4. **Targets by category:** ROOM → rooms (filter `room_type` if set); DOOR / WINDOW → openings of that kind; FIXTURE →
   fixtures (filter `fixture_type` if set); STOREY → storeys; WHOLE_PLAN → the whole plan; WALL / STAIR → the contract
   has no such data → `CANNOT_ANSWER`.
5. **Resolution order** storey → room_type/fixture_type → label → ordinal:
   - **storey:** `EntityRef.storey` holds a `StoreyLevel` value; match `Storey.level`. `UPPER` matches the only storey
     above `GROUND` if there is exactly one, else `NEEDS_CLARIFICATION`. A storey with `level=None` matches nothing. If a
     storey is requested and none matches, or a candidate element has `storey_id=None` → `CANNOT_ANSWER`.
   - **label:** `EntityRef.label` vs `Room.label_text`, case-insensitive, non-alphanumerics ignored, equality.
   - **ordinal n:** the n-th match ordered by the number in the element id (`room_3` before `room_10`); too few → `CANNOT_ANSWER`.
   - **no storey named, several storeys:** aggregate over all storeys and say so in the explanation.
6. **Aggregation:** COUNT is always the number of matching elements, summed over all targets (aggregation ignored).
   Measures: SINGLE needs exactly one match (several → `NEEDS_CLARIFICATION`, none → `CANNOT_ANSWER`); SUM / MAX / MIN /
   MEAN over the matches.
7. **Measures (SI):**
   - AREA = `Room.area_m2`; every matched room must have one, else `CANNOT_ANSWER`. WHOLE_PLAN AREA = the sum of all
     rooms' `area_m2`; every room must have one, and the explanation says "sum of the rooms".
   - LENGTH = the longer side of the room polygon's axis-aligned bounding box. PERIMETER = the polygon perimeter.
     DISTANCE = straight line between the polygon centroids (or `Opening.position`) of `targets[0]` and `targets[1]`.
   - Geometry needs `metric_available=True`: METRIC space → coordinates are metres; PIXEL space → divide by
     `scale.pixels_per_meter` (missing → `CANNOT_ANSWER`).
   - HEIGHT = `Room.height_m`; VOLUME = `area_m2 × height_m`; missing → `CANNOT_ANSWER`.
   - RATIO = area(`targets[0]`) / area(`targets[1]`) only (no count ratios this round, see Q11); a zero or missing
     denominator → `CANNOT_ANSWER`.
8. **COMPARISON:** compute `comparison.measure` for `targets[0]` and compare it with `threshold` (SI), or with
   `targets[1]` if `threshold` is None. Operators GT/GE/LT/LE/EQ; EQ is exact. Result 1.0 / 0.0, unit `boolean`. A measure
   that cannot be computed → `CANNOT_ANSWER`. A COUNT comparison follows decision 9.
9. **Positive evidence for zero** (AGENTS §6 A4). A COUNT of 0 or an EXISTENCE of 0.0 is allowed only if the analysis
   declares that it can see that kind of element, through these warnings (comma-separated, see A3 spec §I):
   `ROOM_TYPES_DETECTED:<RoomType,...>`, `FIXTURE_TYPES_DETECTED:<FixtureType,...>`, `OPENING_KINDS_DETECTED:<OpeningKind,...>`.
   - A ROOM target without `room_type` (all rooms) is covered only if `ROOM_TYPES_DETECTED` lists every RoomType except OTHER and UNKNOWN.
   - STOREY counts are always covered (every analysis has at least one storey).
   - Missing warning, or the value not listed → `CANNOT_ANSWER`, never 0.
   - Parse the values with the contract vocabularies and ignore unknown values.
10. **confidence** = min(question.confidence, the confidences of all elements used). With no elements used, it is
    question.confidence. **evidence** = the ids of every element used (empty for a covered zero).
11. **Errors:** an unexpected exception → `REASONING_FAILED` (exception class in `details`, user-safe message).
12. **No hard-coded limits** (R3.9). If a tunable value is needed, request a config key from A0
    (`docs/requests/A0-<title>.md`) and list the interim module constant in the CHANGELOG entry.

## 3. Tests and acceptance (A0's validity check)

- Only `src/blueprint_qa/reasoning/` and `tests/unit/reasoning/` changed (shared docs append-only).
- Unit tests with hand-built `BlueprintAnalysis` objects shaped like the A3 spec; no network and no LLM. Coverage ≥ 80 %
  for `reasoning/`. They cover:
  - every intent, on both the answered and the `CANNOT_ANSWER` paths, and every category;
  - storey resolution (including `UPPER` and `level=None`), label, ordinal, and SINGLE with 0/1/several matches;
  - unit conversion, and the zero-evidence rule;
  - multi-storey aggregation, confidence and evidence;
  - explanations in en/de/fi plus the fallback, a request_id mismatch, and that it never raises.
- **CubiCasa-style regression.** Build an analysis with:
  - 2 storeys, 13 windows, 12 doors;
  - fixtures: 2 toilets, 3 sinks, 2 showers + 1 bathtub;
  - rooms: SAUNA 1, BEDROOM 1, BATHROOM 1, BALCONY 1, KITCHEN 0;
  - the three `*_DETECTED` warnings.

  COUNT must give 13, 12, 2, 3, 3 (SHOWER + BATHTUB, SUM), 1, 1, 1, 1, 0 (kitchens, covered) and 2 (storeys).
  "How many living rooms?" must give `CANNOT_ANSWER`.
- The check sequence from MERGE_PLAN §6 is green on the branch. CHANGELOG and TASKS entries exist.
