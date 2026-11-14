# Request to A3: the analysis adapter (`analyze()`) and acceptance criteria

- **From:** A0 (session launched by ry), 2026-11-14. Part of `docs/MERGE_PLAN.md` (v2), phase 3.
- **To:** the A3 session (SS). This replaces the "Steps" in A3's own integration note where they differ.

## Answers to A3's questions

- **Does A0's code exist?** Yes. `src/blueprint_qa/contracts/` (v1.0.1), `common/` (config, log, LLM wrapper),
  A1 (`validation/`) and A2 (`question/`) are all merged in `main`. **Build on the code in `main`, not on the text
  in AGENTS.md.** The vocabulary lives only in `contracts/vocabulary.py`.
- **Fixtures (A3's change 1):** agreed in substance. Proposal `docs/contract-changes/001-fixture-entities.md` already
  exists; revision 2 there is the final diff, aligned with your list (`FixtureType`: TOILET, SINK, SHOWER, BATHTUB,
  SAUNA_BENCH, OTHER; `BlueprintAnalysis.fixtures`; `EntityRef` category `FIXTURE` + `fixture_type`). **Do not write
  a new 001 file.** A0 applies it after approval (plan phase 2), together with storey levels (004: `Storey.level`).
- **Original file passthrough (A3's change 2):** recorded as proposal 005 for a team decision. **Not part of this
  integration.** A3 works from `ValidationResult.plan_image` (raster) and `ValidationResult.ifc_bytes` (IFC) only.
- **Thresholds:** go to `config/default.yaml → analysis:` (A0). File `docs/requests/A0-detector-thresholds.md` with the
  tuned values (`eval/thresholds_vision_v2.json`) and strategies. Read them with
  `blueprint_qa.common.config.load_section("analysis")`. Do not read them from `models/` once A0 has merged them.
- **Visualisation / `--debug-overlay`:** not required for this integration (ry). If it already exists, keep it; it is not reviewed.

## Branch

`a3/SS/analysis-adapter`, created from `main`. Rebase it onto `main` after A0's phase 2 lands (it brings `Fixture`,
`StoreyLevel` and the `analysis:` config). Keep `a3/SS/cubicasa-detector` as an archive; it will not be merged.
Do not change `blueprints-starter/` on the new branch.

## Where the code goes (A3-owned paths only)

| From (prototype) | To |
|---|---|
| `vision/analyze.py` | `src/blueprint_qa/analysis/raster/detector.py` |
| `handlers/raster_count.py` (rules) | `src/blueprint_qa/analysis/raster/rules.py`, as *element selection*, not counting |
| `handlers/raster.py` `ROOM_CODES` | `src/blueprint_qa/analysis/labels/fi.yaml` (+ others), validated against `contracts.VOCABULARIES` |
| `handlers/ifc.py` (optional this round) | `src/blueprint_qa/analysis/ifc/` |
| model documentation | `models/cubicasa_v2/MODEL_CARD.md`, `models/fetch.py` (checksums; weights never in git) |
| training/eval scripts (if kept) | under `models/cubicasa_v2/` (A3-owned), not in a new top-level folder (R2.4) |

## Acceptance criteria (the A0 validity check in phase 4 tests exactly these)

1. **Entry point:** `analysis/analyzer.py :: analyze(validation: ValidationResult) -> BlueprintAnalysis | ErrorEnvelope`,
   exported only through `analysis/__init__.py`. **Never raises** (R5.1). The question is never an input.
2. **Element mapping** (as A3 proposed):
   - floor boxes → `storeys` (at least 1; if none is detected, one storey **with a warning**); rooms, openings and
     fixtures get the `storey_id` of the box they lie in. Set `Storey.level` when the label allows it, otherwise `None`.
   - kitchen / bedroom / balcony boxes → `Room` with `room_type` KITCHEN / BEDROOM / BALCONY and the OCR text inside as `label_text`.
   - bathroom boxes + fixture rule → `BATHROOM` if it contains a shower or bathtub, `TOILET` if a toilet but neither.
   - sauna bench groups → one `Room` of type `SAUNA` per group.
   - doors and windows after the duplicate filter → `Opening` DOOR / WINDOW, `position` = box centre, `connects=[]`.
   - toilets, sinks, showers, bathtubs, sauna benches → `fixtures` (with `room_id` if inside a room box).
   - OCR → `texts`. Room polygons = the 4 box corners, clockwise.
   - No scale → `metric_available=False`, `scale.source="NONE"`, all metric fields `None`. **Never guess a scale.**
   - `adjacency=[]` plus a warning, unless computed. Box-derived relations (storey, room) are flagged in `warnings`.
3. **Contract rules:** IDs `<type>_<n>` (`room_1`, `door_3`, `fixture_2`); `coordinate_space="PIXEL"` in the
   `PlanImage` pixel space (map back if resized); every box checked against `[0,w]×[0,h]`; confidences in `[0,1]`;
   `analyzer_version` equals the model card version; `request_id` passed through unchanged.
4. **Vocabulary:** no room or fixture value hard-coded outside the label tables; tables validated against
   `contracts.VOCABULARIES` at load time (a test, like A2's).
5. **Thresholds:** per-class thresholds applied before elements are emitted; all values from config (R3.9).
6. **Errors:** missing or corrupt weights → `MODEL_LOAD_FAILED`; detector failure → `ANALYSIS_FAILED`; IFC input
   without an IFC path implemented → a clean `ErrorEnvelope` (`ANALYSIS_FAILED`, message saying IFC is not supported yet).
7. **CI without weights or GPU:** torch/ultralytics/easyocr are imported **lazily** inside the detector. Unit tests use
   recorded detector output (the JSON format from `vision/analyze.py`) and never load the model or download anything.
   Coverage ≥ 80 % for `analysis/`. The model is loaded once per process (R3.7).
8. **No LLM** unless through `common/llm.py` (the boundary test enforces this).
9. **Checks pass:** ruff format/check, `mypy --strict`, schema check, the full `pytest`.
10. **Docs:** CHANGELOG entry; MODEL_CARD with source, licence (**CubiCasa5K CC BY-NC-SA 4.0**), training data
    (the 241 question images excluded), version and limitations; measured accuracy in `docs/METRICS.md` via A5.
