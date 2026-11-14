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
