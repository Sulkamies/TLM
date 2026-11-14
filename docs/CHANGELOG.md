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
