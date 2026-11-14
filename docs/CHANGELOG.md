# Changelog

Append-only (R10.3): role, initials, date, what changed, and any contract or prompt version touched.

### 2026-11-14 · A0 · ry · Repository scaffolding and Gemini LLM wrapper
- `pyproject.toml` (src layout, pinned minor ranges, ruff, `mypy --strict`, pytest with a `live` marker excluded by default).
- Contracts **v1.0.0** in `src/blueprint_qa/contracts/`, transcribed from AGENTS.md §4.2. JSON Schemas generated
  into `contracts/schema/` by `python -m blueprint_qa.contracts.generate_schema` (`--check` in CI). Bytes are base64 in JSON (D-002).
- `common/config.py` (YAML loader, `BP_CONFIG_DIR`, `BP_LLM_PROVIDER`), `common/log.py` (JSON lines with
  `request_id`/`stage`, secret masking), `common/llm.py` (Gemini backend, structured output, re-asks, retry/backoff,
  injection-safe data block, cassette replay/record, never raises).
- `config/default.yaml` (LLM timeouts/retries, validation thresholds), `config/llm.yaml` (question → `gemini-2.5-flash`).
- Unit tests for `common` and `contracts`: 46 passing, 98 % line coverage. The live Gemini test was **not run** (no key available).
- CI workflow, README, `.env.example`, `.gitignore`. Docs: TASKS, OPEN_QUESTIONS (Q1–Q4), DECISIONS (D-001–D-005),
  EXTERNAL_SERVICES (Gemini, question text only), requests for A2 and A3, contract-change proposal 001 (not applied).
- No prompt versions touched.

### 2026-11-14 · A0 · ry · Contracts v1.0.1: confidence range enforced
- Contract change 002 (approved by ry): new `Confidence = Annotated[float, Field(ge=0.0, le=1.0)]` type used by all 7
  `confidence` fields. `schema_version` is now 1.0.1 on all top-level contracts. Schemas regenerated. AGENTS.md §4.2 updated (doc 1.2.1).
- Tests: 53 passing, 98 % coverage. Recorded ry's answers to OPEN_QUESTIONS Q1–Q3.

### 2026-11-14 · A0 · ry · Vocabulary module and vocabulary-driven interpreter design
- Contract change 003: new `contracts/vocabulary.py` (single source of `RoomType`, `EntityCategory`, `OpeningKind`,
  `DESCRIPTIONS`, `VOCABULARIES`). JSON Schemas byte-identical, contracts stay at 1.0.1. AGENTS.md §4.2 updated (doc 1.2.2).
- `common/llm.py`: `Prompt.render()` / `Prompt.placeholders` (strict `{{NAME}}` templating). The cassette key now covers the
  rendered system instruction and the response schema (D-006).
- Binding A2 design `docs/requests/A2-question-interpreter-design.md` (file map, rules Q1–Q7, change playbook, merge notes).
  A3 addendum. Proposal 001 on hold.
- Tests: 60 passing, 98 % coverage. No prompt versions touched.

### 2026-11-14 · A0 · ry · Switch to gemini-3.8-flash; first live Gemini run
- `config/llm.yaml`: `gemini-2.5-flash` → `gemini-3.8-flash` (D-008, approved by ry). The old model returns 404 for new users.
- `tests/unit/common/conftest.py`: opt-in `live` tests now keep `GEMINI_API_KEY`. Before this, the live test was always skipped.
- **Live test `pytest -m live` passed** against the real Gemini API through `common/llm.py`.
- Offline suite unchanged: 60 passing.

### 2026-11-14 · A0 · ry · Wrapper ready for A1 (images)
- Live check: a synthetic PNG through `common/llm.py` (`get_llm_client("validation")`, `images_png=[...]`) on `gemini-3.8-flash` gave a
  validated verdict in about 6 s, about 1.2k input tokens. No user data sent.
- `config/llm.yaml`: explicit `components.validation` slot (same model as default).
- New `tests/unit/common/test_llm_boundary.py`: CI fails if any module outside `common/` imports a vendor LLM SDK (R7.5).
- Brief and merge checklist for A1: `docs/requests/A1-use-shared-llm-wrapper.md`. Plan images still need R7.4 approval.
- Tests: 63 passing.

### 2026-11-14 · A2 · ry · Question Interpreter (prompt `interpret@v1`)
- New `src/blueprint_qa/question/` per the binding design: `interpret()` entry point (never raises), `QuestionProvider`
  protocol, `LlmQuestionProvider` (default, `get_llm_client("question")`, `gemini-3.8-flash` from config) and
  `MockQuestionProvider`. `LlmParse` is composed from contract types; its validator enforces the §4.2 invariants so the
  wrapper re-asks on violations. `mapping.py` converts comparison thresholds to SI in code (e.g. 120 sq ft → 11.148 m²).
- Prompt `prompts/interpret.v1.md` with `{{PLAN_VOCABULARY}}`, `{{SYNONYMS}}`, `{{EXAMPLES}}`, rendered from
  `contracts.VOCABULARIES`/`DESCRIPTIONS` and `synonyms/{en,de,fi}.yaml` (validated against the vocabulary; Finnish and
  German plan abbreviations included).
- Terminal chat REPL: `python -m blueprint_qa.question` (also reads piped stdin).
- Tests: 105 offline in `tests/unit/question/` on 45 recorded cassettes (`cassettes/interpret@v1.json`); EN/DE/FI
  equality for 8 held-out questions; Q1 guard; opt-in live test passed. Re-record with
  `tests/unit/question/record_cassettes.py`. Full suite: 168 passed, coverage 98 % (question/ ≥ 82 % per file).
- No contract, config or `pyproject.toml` change. Open questions Q5 (storey text) and Q6 (unitless thresholds).

### 2026-11-14 · A2 · ry · Fixed storey levels (Q5) and unitless thresholds (Q6), prompt `interpret@v1`
- Storeys: interim `StoreyLevel` values in `question/interim_vocabulary.yaml`, rendered into the prompt, covered by
  EN/DE/FI synonyms and validated on every LLM reply. Proposal 004 and a request to A0 make them official.
  Deviation recorded.
- A measured comparison threshold without a unit now requires `clarification_needed` (validator, so the wrapper re-asks).
- `interpret.v1.md` edited in place: it was not merged yet, so R7.7 still allows that. Cassettes re-recorded (53, all
  valid on the first ask). New EN/DE/FI cases: upper-floor area, and "bigger than 10" without a unit.
- No contract, config or `pyproject.toml` change.

### 2026-11-14 · A2 · ry · Storey levels: support the lighter option of contract change 004
- ry chose the lighter option (`EntityRef.storey` stays `str`). `vocabulary_view.py` now uses the contract's
  `StoreyLevel` values and descriptions once they exist, and keeps the `storey` link and its validation. The entry is
  dropped only if a contract types the field. Before this, the lighter option would have silently disabled the
  storey constraint.
- Tests for both cases. Prompt text unchanged (`interpret@v1`), cassettes still valid.
### 2026-11-14 · A0 · OT · Validation config keys and image libraries for A1
- `pyproject.toml`: new runtime dependencies `pillow>=13.0,<13.1`, `pypdfium2>=5.15,<5.16`, `ifcopenshell>=0.9,<0.10`
  (A1 request `docs/requests/A0-validation-config-and-deps.md`). No mypy override: A1 keeps its scoped
  `# type: ignore[import-untyped]` for `pypdfium2`.
- `config/default.yaml → validation`: new keys `max_image_pixels: null`, `llm_image_max_side_px: null`,
  `llm_image_max_bytes: 7500000`, `supported_ifc_schemas: [IFC2X3, IFC4, IFC4X3]`. Existing keys unchanged.
- No test pinned the `validation` section, so no test changed. Response: `docs/requests/A0-validation-config-and-deps.response.md`.
- No contract or prompt versions touched.

### 2026-11-14 · A0 · OT · Faster image validation (D-009)
- `config/default.yaml → validation.llm_image_max_side_px`: `null` → `1024` (LLM copy only).
- `config/llm.yaml → components.validation`: `model: gemini-3.5-flash-lite`, `thinking_budget: null` (the model rejects 0
  with HTTP 400). Defaults and `question` unchanged.
- Tests: `test_validation_component_has_its_own_slot` now pins `gemini-3.5-flash-lite` and checks that the `thinking_budget`
  override resolves to `None`. New `test_gemini_backend_omits_thinking_config_when_budget_is_none`. 64 passing, 98 % coverage.
- Docs: D-009, EXTERNAL_SERVICES update row, response `docs/requests/A0-validation-speed.response.md`. No live call made by A0.
- No contract or prompt versions touched. A1 must re-record its validation cassettes for the new model.
### 2026-11-14 · A1 · OT · Input Validator ported onto `main` (Gemini via the shared wrapper)
- `src/blueprint_qa/validation/`: entry point `validate(request) -> ValidationResult | ErrorEnvelope`, never raises.
  Real format from magic bytes (`FORMAT_MISMATCH`). PNG/JPEG decoded with EXIF orientation applied and re-encoded as PNG, never resized.
  PDFs must have exactly one page (`MULTI_PAGE_PDF`) and are rendered at `pdf_render_dpi`. IFC files are checked locally, with no LLM
  (schema, at least one `IfcSpace`/`IfcWall*`, else `NO_SPATIAL_DATA`). Images are classified through
  `get_llm_client("validation").generate_structured(...)`; confidence below `min_confidence` gives `LOW_CONFIDENCE`.
  Raw labels stay inside `validation/`.
- **Size limit for the LLM copy:** a normalised PNG can be far larger than the upload (a 1.9 MB JPEG scan became 9.8 MB,
  and the API rejected it). PNGs over `validation.llm_image_max_bytes` are shrunk until they fit. Smaller images are sent
  byte-identical, and `PlanImage` is never changed.
- Prompt `validation/prompts/floor_plan_classifier.v1.md` (new, v1). No user text is sent (`data={}`).
- Tests: 157 unit tests, run through the real `LlmClient` with a fake backend or recorded cassettes; validation coverage 99 %.
  Cassettes `tests/unit/validation/cassettes/floor_plan_classifier@v1.json` were recorded live with `gemini-3.8-flash` on 6 synthetic
  images, all correct (about 1,600 input tokens each). Re-record with the opt-in test: `pytest -m live tests/unit/validation/test_llm_cassettes.py`.
- **Live check on 22 real Junction drawings** (11 should be accepted, 11 rejected; full `validate()` path; drawings not committed):
  `gemini-3.8-flash` 22/22 correct, 33,705 input and 3,376 output tokens for 21 calls (one multi-page PDF is rejected locally).
  For comparison, earlier Claude runs on the same set: Opus 5.5 22/22, Haiku 5.5 21/22, each about 111k input tokens.
- Requires A0 branch `a0/ot/validation-config-deps` (a0d1ff9: image libraries and validation config keys). Merge it first or together.
- Earlier work on `a1/ot/input-validator` used Claude through an A0 branch that PR #1 superseded. Its measurements (22 real
  Junction drawings: Opus 5.5 22/22, Haiku 5.5 21/22) are not Gemini results.
- Recorded OT's approval of plan images for Gemini in `docs/EXTERNAL_SERVICES.md` (OPEN_QUESTIONS Q2).

### 2026-11-14 · A1 · OT · Faster validation: re-recorded with gemini-3.5-flash-lite, end-to-end check with A0
- Requested from A0 `docs/requests/A0-validation-speed.md`: LLM copy limited to 1024 px, validation model `gemini-3.5-flash-lite`
  with `thinking_budget: null`. A0 implemented it in 1abbc37 (D-009) on `a0/ot/validation-config-deps`.
- Re-recorded the cassettes `floor_plan_classifier@v1.json` with `gemini-3.5-flash-lite`: 6/6 correct, 17–25 output tokens each.
  The prompt is unchanged (v1).
- End-to-end check on A0 1abbc37 combined with A1, using CI's commands offline: ruff and mypy clean, schemas OK, 158 passed, coverage 98.27 %.
- Live, real config, 22 Junction drawings, 8 in parallel: 21/22 correct in 10.0 s (median 1.7 s per picture, slowest 3.0 s),
  33,705 input and 426 output tokens. The miss is the borderline "Kremsier Wohnhaus Parterre", which also flips between runs on
  `gemini-3.8-flash`. Before this change, sequential calls with full-size images took 177 s.

### 2026-11-14 · A0 · ry · Merge plan for A0 + A1 + A2
- New `docs/MERGE_PLAN.md`: binding plan for the A0 session that integrates A1 → A2 into `orchestrator.run()` and a CLI
  front door. It covers the invalid-picture message ry asked for, interim answers without numbers, contract checks, tests and a live demo.
  A3 (unfinished), A4 (not implemented), the architecture decision and proposals 001/004 are explicitly out of scope.
- Baseline verified on `main` `c8e8127`: all checks pass, 278 tests.

### 2026-11-14 · A0 · ry · Integration plan v2 (A3 included)
- `docs/MERGE_PLAN.md` rewritten as v2: phases 1 (orchestrator + CLI for A1→A2), 2 (contracts 1.1.0: fixtures 001 +
  storey levels 004, `analysis:` config, `vision` extra), 2b (A2 synonyms), 3 (A3 adapter), 4 (A2 ∥ A3 in the pipeline).
  Gates G1–G5. A4 out of scope. Architecture basis: AGENTS.md (A3 question-agnostic), pending ry's confirmation (Q8).
- New `docs/requests/A3-analysis-adapter.md` (answers A3's questions, acceptance criteria).
- Proposal 001 revision 2: final fixture diff, awaiting approval. A3's source-file passthrough goes to proposal 005 (team decision, not in this integration).

### 2026-11-14 · A0 · ry · Integration plan v3
- `docs/MERGE_PLAN.md` v3: decisions D1–D6 (AGENTS.md architecture; 001 + 004 approved; A3 writes its adapter from A0's
  spec; the integration agent opens PRs but never merges; visualisation and proposal 005 out of scope). New phase 0: the
  integration agent determines A3's real output from `origin/a3/SS/cubicasa-detector` and publishes a verified mapping spec.
- Approvals recorded in proposals 001 and 004; D-010 in DECISIONS; status note in the A3 brief.

### 2026-11-14 · A0 · ry · Phase 0: verified A3 mapping spec
- Analysed A3's branch `origin/a3/SS/cubicasa-detector` at `35597e2` (read-only, via `git show`). ry decided the spec
  follows this version, not `a3/SS/cubicasa-v3`. The counting rules (`raster_count.py` with `thresholds_vision_v2.json`)
  were run unchanged on synthetic detector output; the detector itself could not be run (no weights or recorded output).
- `docs/requests/A3-analysis-adapter.md`: new section "Verified mapping spec (phase 0)": detector output, tuned selection
  rules, field-by-field mapping to `BlueprintAnalysis` 1.1.0, the proposed `analysis:` config, differences from the
  earlier descriptions, open points.
- OPEN_QUESTIONS Q8 answered (D1). Proposal `docs/contract-changes/005-original-file.md` (for team decision, D6).
  Deviation recorded: no `--debug-overlay` in this integration (D5).
- No contract, prompt or code change.
- Added `docs/requests/A3-open-points.md`: all questions to A3/SS (A3-Q1 … A3-Q22: weights, real detector output,
  confirmations of A0's reading of the code, and A0 decisions SS may object to). The spec's §F points to it.

### 2026-11-14 · A0 · ry · Phase 2: contracts 1.1.0, analysis config, vision extra
- **Contracts 1.0.1 → 1.1.0** (MINOR): change 001 revision 2 (`FixtureType`, `"FIXTURE"` category, `Fixture`,
  `BlueprintAnalysis.fixtures`, `EntityRef.fixture_type`) and change 004 lighter option (`StoreyLevel`, `Storey.level`).
  Schemas regenerated, AGENTS.md §4.2 updated (document version 1.3.0), contract tests extended. 001 and 004 marked APPLIED.
- `config/default.yaml → analysis:` (A3 detector thresholds, duplicate filters, detector/OCR options; spec §D + A3-Q20).
- `pyproject.toml`: optional extra `vision` (torch, ultralytics, easyocr; not installed in CI) and a mypy override for them.
- `docs/requests/A2-fixture-vocabulary.md` (phase 2b work items). A3 spec: section H (A3-Q14 regex, A3-Q20 OCR model).
- Expected: 29 A2 tests fail on this branch until A2's phase 2b lands (synonyms, cassettes, interim vocabulary).

### 2026-11-14 · A2 · ry · Phase 2b: Question Interpreter on contracts 1.1.0
- Request `docs/requests/A2-fixture-vocabulary.md`, branch `a2/ry/fixture-vocabulary` (from `a0/ry/contracts-1.1`).
- `synonyms/{en,de,fi}.yaml`: words for `EntityCategory.FIXTURE` and every `FixtureType` value; few-shot examples
  "How many showers and bathtubs?" (en), "Gibt es eine Badewanne?" (de), "Montako suihkua ja kylpyammetta asunnossa
  on?" (fi).
- `fixture_type` iff `category == FIXTURE` enforced in `LlmParse`, with the link as data in the new
  `question/field_rules.yaml` (ry's choice; deviation recorded).
- Storey levels from the contracts: interim `values:` deleted from `interim_vocabulary.yaml`; A2 storey deviation closed.
- **Prompt `interpret.v2.md`** (v1 unchanged): one instruction on fixtures and on WC room vs toilet bowl. `PROMPT_VERSION = 2`.
- **Cassettes re-recorded** (R7.12): `cassettes/interpret@v2.json`, 67 entries; stale `interpret@v1.json` removed.
- Tests: version literals use `CONTRACT_VERSION` / `PROMPT_VERSION`; new held-out en/de/fi cases (WC rooms → `ROOM` +
  `TOILET`, toilet bowls → `FIXTURE` + `TOILET`, washbasins → `FIXTURE` + `SINK`) and A0's acceptance questions verbatim;
  rule tests for `field_rules.yaml`.
- Checks (MERGE_PLAN §6) green on this branch: ruff format/check, mypy, schema check, 297 passed, coverage 98.41 %
  (`question/` 98 %). Live: `pytest -m live tests/unit/question` passed; REPL live check of A0's four acceptance questions
  gave the expected `ParsedQuestion`s.

### 2026-11-14 · A0 · ry · Phase 1: orchestrator and CLI for A1 → A2
- `src/blueprint_qa/orchestrator/pipeline.py`: `run(request) -> Answer | ErrorEnvelope` (plus `run_traced()` for
  `--debug` and `new_request()`, which creates the UUID4 `request_id` and `received_at`). A1 first; on `is_valid=False`
  the answer is exactly "This picture is invalid for our program" and A2 is not called (R5.2). Every component output is
  re-validated against its contract and its `request_id` checked (violation → `INVALID_INPUT`, `details.producer`). No
  exception escapes (R5.1), one log event per stage, never a number. Interim answers in `INTERIM_TEXTS`. Ordered
  `STAGE_ORDER` with an empty A3 slot (concurrent with A2) and A4 slot.
- `src/blueprint_qa/api/`: CLI `python -m blueprint_qa.api <file> "<question>" [--format] [--locale] [--json] [--debug]`.
- Tests: `tests/unit/orchestrator/`, `tests/unit/api/` (37 tests; pipeline.py 100 % covered). Live demo with Gemini:
  `house_plan_fi.png` in fi/en/de gives the same `ParsedQuestion`; `bar_chart.png` and `prompt_injection.png` give the
  invalid text without an A2 call.
- README: CLI usage, layout status. OPEN_QUESTIONS Q9 (`Answer.unit` without a value). No contract or prompt change.

### 2026-11-14 · A3 · SS · Answers to A3-Q1 … A3-Q22
- Appended the answers to `docs/requests/A3-open-points.md`, checked on real data: v2 weights checksum, all 241 recorded
  detector outputs (sizes, bounds, class names), and 84.5 % test re-measured with the code at `35597e2` and
  `thresholds_vision_v2.json`. Disagreements: none. Two corrections: the storey regex (A3-Q14), and the EasyOCR model
  download mapping to `MODEL_LOAD_FAILED` and fetched by `models/fetch.py` (A3-Q20).
- Added three recorded detector outputs under `tests/unit/analysis/data/` (with a README on source and licence).
- No contract, prompt or code change.

### 2026-11-14 · A3 · SS · Phase 3: analysis adapter `analyze()` (raster, contracts 1.1.0)
- **Entry point** `src/blueprint_qa/analysis/analyzer.py :: analyze(validation) -> BlueprintAnalysis | ErrorEnvelope`,
  exported only through `analysis/__init__.py`. Never raises. Logic ported from `35597e2` (not from `cubicasa-v3`),
  implemented per `docs/requests/A3-analysis-adapter.md` §C/§D/§H and A0's addendum.
- `analysis/raster/detector.py`: YOLO + EasyOCR, torch/ultralytics/easyocr/numpy imported lazily, loaded once per
  process; EasyOCR gets `ocr.model_dir` and `ocr.download_enabled`. Same detector input as when the thresholds were
  tuned (an RGB array).
- `analysis/raster/rules.py`: the tuned rules as element selection (thresholds, duplicate IoU, bench clusters,
  bathroom/WC rule) plus the bounds check. `analysis/raster/mapping.py`: §C field by field (IDs in reading order,
  storeys + `Storey.level` from the §H regex, rooms, openings, fixtures, texts, warning codes).
- Warnings include `ROOM_TYPES_DETECTED:BALCONY,BATHROOM,BEDROOM,KITCHEN,SAUNA,TOILET`,
  `FIXTURE_TYPES_DETECTED:BATHTUB,SAUNA_BENCH,SHOWER,SINK,TOILET` and `OPENING_KINDS_DETECTED:DOOR,WINDOW` (A0 addendum).
- Label tables `analysis/labels/fi.yaml` (room codes, storey word, storey levels) and `analysis/labels/cubicasa_v2.yaml`
  (detector class -> room type / opening kind / fixture type), validated against `contracts.VOCABULARIES` at load time.
  No vocabulary value is written in the code. All thresholds come from `config/default.yaml -> analysis`.
- Errors: missing/corrupt weights, missing vision packages or OCR model -> `MODEL_LOAD_FAILED`; detector exception,
  malformed output, size mismatch or contract violation -> `ANALYSIS_FAILED`; no `plan_image` -> `INVALID_INPUT`;
  IFC -> `ANALYSIS_FAILED` "IFC plans are not supported yet."; anything else -> `INTERNAL_ERROR` (exception class in
  `details`).
- `models/cubicasa_v2/MODEL_CARD.md` (version `cubicasa-yolo11m-v2+rules-v2`), `models/fetch.py` (sha256 checks;
  EasyOCR files from the official releases, checksums verified on download), `models/.gitignore`.
  **Placeholder:** the hosting URL for `best.pt` does not exist yet (`url=None` in `fetch.py`); copy the file by hand
  and run `python models/fetch.py --check`.
- Tests `tests/unit/analysis/` (68): the required regression test reproduces A0's counts for all three recordings
  exactly; contract checks (bounds, confidences, unique IDs, request_id), every error path, rules, mapping, label
  tables, the detector wrapper with stand-in modules, model card and fetch checksums. Recorded output only: no weights,
  torch or network.
- **Not done:** no live run with real weights (this environment has no weights, torch or package index), so no timing
  is reported. `--debug-overlay` not implemented (D5). No contract, config, prompt or shared-file change.

### 2026-11-14 · A4 · ry · Answer Reasoner (`reasoning/`)
- `src/blueprint_qa/reasoning/reasoner.py :: answer(question, analysis) -> Answer | ErrorEnvelope`, exported only via
  `reasoning/__init__.py`. Never raises: wrong input types or a `request_id` mismatch → `INVALID_INPUT`, unexpected
  exception → `REASONING_FAILED` (exception class in `details`). Guards: UNSUPPORTED → `UNSUPPORTED_QUESTION`;
  `clarification_needed` → `NEEDS_CLARIFICATION` with that text.
- Deterministic computation per A0's binding decisions (`compute.py`, `resolve.py`, `geometry.py`): all intents,
  categories ROOM/DOOR/WINDOW/FIXTURE/STOREY/WHOLE_PLAN (WALL/STAIR → CANNOT_ANSWER), resolution storey → type → label →
  ordinal (UPPER, level None), SINGLE/SUM/MAX/MIN/MEAN, zero-evidence rule via `ROOM_TYPES_DETECTED`,
  `FIXTURE_TYPES_DETECTED`, `OPENING_KINDS_DETECTED`, unit by intent also without a value (Q9 option c), ft conversion,
  no rounding, confidence = min, evidence = element ids, multi-storey note.
- **No LLM**: explanations from fixed en/de/fi templates (`explanations.py`), English fallback.
- No config keys needed (no tunable limits); unit conversion factors are the constants from AGENTS.md §6 A4.
- Tests: `tests/unit/reasoning/` (150 tests, hand-built analyses shaped like A3's raster spec, incl. the CubiCasa-style
  regression); `reasoning/` coverage 99 %. Edge cases decided provisionally: OPEN_QUESTIONS Q10.
- No contract or prompt change. Not wired into the orchestrator (A0's job).

### 2026-11-14 · A3 · SS · Host the cubicasa_v2 weights; `models/fetch.py` URL set
- Hosting choice (SS): **GitHub Release** on the public repo, tag `models-cubicasa-v2`, asset `best.pt`:
  https://github.com/Sulkamies/TLM/releases/download/models-cubicasa-v2/best.pt. Release notes state the licence
  (derived from CubiCasa5K, **CC BY-NC-SA 4.0**: attribution, non-commercial, share-alike), the version
  `cubicasa-yolo11m-v2+rules-v2` and point to `models/cubicasa_v2/MODEL_CARD.md`. Published by SS (this session may not
  create releases); the uploaded file was checked first: sha256 `2093bef2…3337d`, 40,587,180 bytes.
- `models/fetch.py`: URL set for `cubicasa_v2/best.pt` (sha256 and size unchanged); placeholder comment replaced.
  Model card links the release.
- Proof: in a fresh temporary copy, `python models/fetch.py` fetched all three files in 3.5 s, and
  `python models/fetch.py --check` exited 0 (all verified). In a repo checkout the fetched files are git-ignored.
- Test: every entry in `FILES` has an https URL; the best.pt entry has the expected sha256 and size (no download in tests).

### 2026-11-14 · A0 · ry · A4 in scope: brief, coverage warnings, plan update
- New `docs/requests/A4-answer-reasoner.md`: entry point and A0's binding decisions (no LLM this round; unit by intent
  also without a value; resolution, aggregation, measures, comparison; zero answers only with coverage warnings).
- A3 spec §I: every raster analysis also emits `FIXTURE_TYPES_DETECTED:` and `OPENING_KINDS_DETECTED:`.
- DECISIONS D-011 (A4 in scope) and D-012 (coverage warnings); OPEN_QUESTIONS Q9 answered (c), new Q11–Q13 (Q10 is A4's).
- MERGE_PLAN update v3.1 (actual merge order, phase 3b for A4, phase 5 for wiring A4). README: contracts v1.1.0, A4 status.
- Docs only; no contract, prompt or code change.

### 2026-11-14 · A0 · ry · Phases 4 + 5: A2 ∥ A3, then A4, in the pipeline
- `orchestrator/pipeline.py`: after A1 says valid, A2 and A3 run **concurrently** (A3 gets the `ValidationResult`, never
  the raw upload); then A4 computes the answer. Defaults are the real entry points (`analysis.analyze`,
  `reasoning.answer`); `None` skips a stage (interim answer). Every output is contract-checked, plus the §4.2 invariant
  "`value` non-null iff `status == ANSWERED`" on A4's `Answer` (violation → `INVALID_INPUT`, producer REASONING).
  An A3 error is returned even if A2 succeeded; without an analysis, UNSUPPORTED and clarification are still answered.
  The orchestrator itself still never produces a number.
- CLI: `--debug` shows a compact `BlueprintAnalysis` summary; answers print as `4 count` (display only, never rounded).
- Tests: `tests/unit/orchestrator/test_pipeline_a3_a4.py` (23 tests: real concurrency via a barrier, error priority,
  A4 checks, the full chain with the real A4 on snapshots of A3's real output in `tests/unit/orchestrator/data/`).
  Check sequence: 577 passed, `pipeline.py` 100 %.
- **Live demo with the real model** (CPU torch 2.15, ultralytics 8.4.212, easyocr 1.7.2; weights via `models/fetch.py`),
  the three CubiCasa plans sent as received JPEGs (two of them downscaled), 9 questions each in fi/en/de:
  **27/27 answers equal A3's tuned counts** on the original PNGs (bedrooms, toilet bowls, windows, doors, sauna yes/no,
  showers + bathtubs, balconies; living rooms and kitchen area → CANNOT_ANSWER). Timings: A1 1.2–2.6 s, A2 3–6 s,
  A3 13.5 s on the first call (model load) then 3–5 s, A4 < 1 ms; 5–7 s per question end to end.
- README: setup for raster plans, real CLI output. No contract, config or prompt change.

### 2026-11-14 · A0 · ry · HTTP server for the Android app and the browser
- `src/blueprint_qa/api/server.py`: `python -m blueprint_qa.api.server [--host] [--port]`. `POST /ask` (multipart
  `image`, `question`, optional `locale`; else `Accept-Language`) builds a `PipelineRequest` and runs the orchestrator;
  `GET /health`. Bad uploads → 400/413/415 with `{"error"}`, also for missing fields.
- `src/blueprint_qa/api/ask.py` (Pydantic models `AskAnswer`, `AskError`, `EvidenceBox`): presents a pipeline result in the app's format (`android-app/README.md`): numbers
  with display units, yes/no as words in the answer's language, non-answers as text (HTTP 200), errors as
  `{"error", "code"}` without `details` (503 if retryable, else 500), evidence ids → boxes in image fractions from A3's
  analysis (rooms: bounding box; doors/windows/fixtures: squares of `api.evidence_point_size`).
- `pyproject.toml`: optional extra `server` (fastapi, uvicorn, python-multipart), `httpx` in `dev`; CI installs
  `.[dev,server]`. `config/default.yaml -> api` (host, port, max_upload_bytes, evidence_point_size).
- Tests `tests/unit/api/test_server.py` (19). Live test with the real model over HTTP: correct counts, "Kyllä" / "No",
  text answers, 400/415 bodies; evidence boxes drawn onto the picture land on the right bedrooms, doors and sinks.
  First request 16 s (model load), then 5–11 s.
- **Browser UI** `src/blueprint_qa/api/web/index.html`, served at `GET /`: **at's design** (`web-app/index.html`,
  `ca8a9da`: welcome screen, samples, zoom/pan, suggestion chips, camera, paste) with two adaptations (non-PNG/JPEG
  converted to JPEG in the browser; locale sent). Samples at `GET /samples/` (CC BY-NC-SA 4.0 credit). Same
  `POST /ask` as the app. Test: every server/user string put into HTML goes through `esc()`.
- OPEN_QUESTIONS Q14 ("toilets" read as WC rooms, found via the suggestion chips).
- **One written contract** for all clients: `docs/API.md`; `tests/unit/api/test_web.py` checks that the page and the
  Android app read only contract fields and that the spec lists every field.
- D-013 (one API for all UIs; A0 approves `android-app/`, one human still needed). Request `docs/requests/UI-android-app.md`.

### 2026-11-14 · A0 · ry · Browser UI: at's redesign
- `src/blueprint_qa/api/web/index.html` now follows at's redesigned page (`web-app/index.html`, commit `85524c9` on
  `ui/at/webpage`): new look (dark/light), evidence chips under each answer, hover or tap a red box to see what it marks,
  collapsible "How it was counted", animated answers, better phone layout. Same two adaptations as before (other
  picture formats converted to JPEG in the browser; locale sent). Samples unchanged.
- No change to the API (`docs/API.md`), the server or the Android app. `tests/unit/api/test_web.py` adapted to the new
  page structure (box labels now read in the tooltip; `.length` reads are not text). 601 passed; live check of page,
  samples and answers.

### 2026-11-14 · A0 · ry · Browser UI: no "How it was counted"
- `src/blueprint_qa/api/web/index.html`: the collapsible "How it was counted" explanation is removed (ry). The page shows
  the answer, the evidence chips and the boxes on the drawing. Sentence answers (e.g. why a question cannot be answered)
  still show, since they are the answer itself. No change to the API: `working` is still sent (`docs/API.md`), so the
  Android app is unaffected. Test `test_the_page_does_not_show_the_explanation`.

### 2026-11-14 · A0 · ry · Contract change 006: validation receipt (A0 part)
- **Contracts 1.1.0 → 1.2.0** (MINOR, approved by ry and A0): optional `PipelineRequest.validation_token` and
  `ValidationResult.validation_token`. Schemas regenerated, AGENTS.md §4.2 updated (document 1.4.0). Proposal
  `docs/contract-changes/006-validation-receipt.md`, D-014.
- Pass-through: `orchestrator.new_request(validation_token=...)`; server form field `validation_token`; response field
  `AskAnswer.validation_token` (only for valid pictures); `docs/API.md` section "Validating a picture once".
- Web page keeps the receipt per picture and sends it back (adaptation 4); reset on a new picture.
- Config `validation_receipt: {ttl_s, key_env}` (own section: A1's `validation:` settings forbid extra keys);
  `BP_VALIDATION_RECEIPT_KEY` in `.env.example`.
- Requests: `docs/requests/A1-validation-receipt.md` (implementation), `docs/requests/A3-contract-version-literal.md`
  (one test line), UI request §7 (optional for the app). Until A1 implements it, behaviour is unchanged.
- Stacked on `a0/ry/web-hide-working` (merge that first).
