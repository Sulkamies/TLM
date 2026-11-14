# Tasks

Append-only. Claim a task with role, initials and date before starting (R2.0c).
Mark completion by appending a line. Never rewrite someone else's entry.

| # | Task | Role | Claimed by | Date | Status |
|---|------|------|-----------|------|--------|
| 1 | Repository scaffolding: `pyproject.toml`, `config/`, contracts v1.0.0 + generated JSON Schemas, `common/` (config, log, Gemini LLM wrapper), CI, README, docs | A0 | ry | 2026-11-14 | Done (branch `a0/ry/scaffolding-gemini-wrapper`) |
| 2 | Question Interpreter (`question/`): `interpret()` entry point, `QuestionProvider` adapter with `LlmQuestionProvider` (Gemini via `common.llm`, `gemini-2.5-flash`) and `MockQuestionProvider`, versioned prompt, EN/DE/FI synonyms YAML, cassettes, unit tests. Plus a **terminal chat REPL** `python -m blueprint_qa.question` that prints the `ParsedQuestion` for each typed question. Brief: `docs/requests/A2-question-interpreter-gemini.md` | A2 | (unclaimed) | | Open |
| 3 | Orchestrator `pipeline.run()` and `api/` front door | A0 | (unclaimed) | | Open |
| 4 | A3 adapter from the CubiCasa YOLO11 + EasyOCR detector to `BlueprintAnalysis`. Brief: `docs/requests/A3-cubicasa-detector-adapter.md` | A3 | (unclaimed) | | Open |
| 2a | Task #2 MUST follow the binding design `docs/requests/A2-question-interpreter-design.md` (vocabulary-driven schema/prompt, fixed file map, change playbook) | A2 | (unclaimed) | 2026-11-14 | Open (added by A0 · ry) |
| 5 | Vocabulary module `contracts/vocabulary.py` (change 003), `Prompt.render`, cassette key covers prompt + schema (D-006) | A0 | ry | 2026-11-14 | Done |
| 2b | Note for task #2: the model is now `gemini-3.8-flash` (D-008), not `gemini-2.5-flash` | A2 | (unclaimed) | 2026-11-14 | Info (added by A0 · ry) |
| 6 | A1 uses the shared LLM wrapper: `validation` config slot, R7.5 boundary test, live image check through the wrapper, brief `docs/requests/A1-use-shared-llm-wrapper.md` | A0 | ry | 2026-11-14 | Done |
| 2 | Claim: Question Interpreter per task #2 | A2 | ry | 2026-11-14 | In progress (branch `a2/ry/question-interpreter`) |
| 2a | Claim: following the binding design for task #2 | A2 | ry | 2026-11-14 | In progress |
| 2b | Claim: acknowledged, using `gemini-3.8-flash` from `config/llm.yaml` | A2 | ry | 2026-11-14 | In progress |
| 2 | Done: `question/` interpreter, providers (LLM + mock), prompt `interpret@v1`, EN/DE/FI synonyms, REPL, 45 cassettes, tests. `LocalRuleProvider` (optional) not built | A2 | ry | 2026-11-14 | Done (branch `a2/ry/question-interpreter`, awaiting review) |
| 2a | Done: follows the binding design (file map, Q1–Q7) | A2 | ry | 2026-11-14 | Done |
| 2b | Done: `gemini-3.8-flash` via `config/llm.yaml`, live test passed | A2 | ry | 2026-11-14 | Done |
| 7 | A1 dependencies and config: `pillow`, `pypdfium2`, `ifcopenshell` in `pyproject.toml`; `max_image_pixels`, `llm_image_max_side_px`, `llm_image_max_bytes`, `supported_ifc_schemas` in `config/default.yaml → validation`. Request: `docs/requests/A0-validation-config-and-deps.md` | A0 | OT | 2026-11-14 | Done (branch `a0/ot/validation-config-deps`, not merged) |
| 8 | Faster image validation: `validation.llm_image_max_side_px: 1024`, validation model `gemini-3.5-flash-lite` with `thinking_budget: null` (D-009). Request: `docs/requests/A0-validation-speed.md` | A0 | OT | 2026-11-14 | Done (branch `a0/ot/validation-config-deps`, not merged) |
| 9 | Input Validator (`validation/`) ported onto `main`: uses `common.llm` (Gemini) per `docs/requests/A1-use-shared-llm-wrapper.md`; config keys and image libraries requested from A0 (`docs/requests/A0-validation-config-and-deps.md`) | A1 | OT | 2026-11-14 | Done (branch `a1/ot/validator-gemini`; needs A0 branch `a0/ot/validation-config-deps`) |
| 10 | A1 re-records cassettes for `gemini-3.5-flash-lite` and checks A1 end to end with A0's speed config (D-009) | A1 | OT | 2026-11-14 | Done (branch `a1/ot/validator-gemini`; needs A0 branch `a0/ot/validation-config-deps` 1abbc37) |
| 11 | Merge plan for integrating A0, A1 and A2 (orchestrator + CLI; A3/A4 out of scope): `docs/MERGE_PLAN.md` | A0 | ry | 2026-11-14 | Done (branch `a0/ry/merge-plan`) |
| 3 | Claim (partial): orchestrator + CLI for A1→A2 per `docs/MERGE_PLAN.md` | A0 | ry | 2026-11-14 | In progress (branch `a0/ry/integration-a1-a2`) |
| 7 | Status: merged to `main` (PR #4, `c8e8127`) | A0 | ry | 2026-11-14 | Merged (noted by A0 · ry) |
| 8 | Status: merged to `main` (PR #4, `c8e8127`) | A0 | ry | 2026-11-14 | Merged (noted by A0 · ry) |
| 9 | Status: merged to `main` (PR #3, `d8a6fc6`) | A1 | ry | 2026-11-14 | Merged (noted by A0 · ry) |
| 10 | Status: merged to `main` (PR #3, `d8a6fc6`) | A1 | ry | 2026-11-14 | Merged (noted by A0 · ry) |
| 12 | Integration plan v2 (A0+A1+A2+A3, A4 out of scope) replaces v1: `docs/MERGE_PLAN.md`; A3 brief `docs/requests/A3-analysis-adapter.md`; proposal 001 revision 2 | A0 | ry | 2026-11-14 | Done |
| 13 | Phase 2: contracts 1.1.0 (001 rev. 2 + 004 lighter), `analysis:` config, `vision` extra, request `A2-fixture-vocabulary.md`, spec update after A3's answers | A0 | ry | 2026-11-14 | Done (branch `a0/ry/contracts-1.1`, draft PR; merge together with A2 phase 2b) |
| 14 | Claim: Phase 2b, Question Interpreter on contracts 1.1.0 (fixture vocabulary, storey levels from contracts, version literals, prompt v2, re-recorded cassettes). Request: `docs/requests/A2-fixture-vocabulary.md` | A2 | ry | 2026-11-14 | In progress (branch `a2/ry/fixture-vocabulary`) |
| 14 | Done: Phase 2b per `docs/requests/A2-fixture-vocabulary.md` (fixture synonyms, iff rule via `field_rules.yaml`, storey levels from contracts, prompt `interpret@v2`, 67 cassettes re-recorded, live check passed) | A2 | ry | 2026-11-14 | Done (branch `a2/ry/fixture-vocabulary`, awaiting review) |
| 3 | Done (phase 1): `orchestrator/pipeline.py :: run()` A1 → A2 with contract checks, interim answers, marked A3/A4 slots; CLI `python -m blueprint_qa.api` | A0 | ry | 2026-11-14 | Done (branch `a0/ry/orchestrator`, awaiting review) |
| 15 | Claim: phase 3, A3 analysis adapter `analysis/analyzer.py :: analyze()` per `docs/requests/A3-analysis-adapter.md` (spec §A–H, logic from `35597e2`), model card and `models/fetch.py` | A3 | SS | 2026-11-14 | In progress (branch `a3/SS/analysis-adapter`) |
| 15 | Done: A3 analysis adapter, label tables, model card, `models/fetch.py` (best.pt URL still a placeholder), 68 unit tests | A3 | SS | 2026-11-14 | Done (branch `a3/SS/analysis-adapter`, awaiting A0 validity check) |
| 15 | Claim: Answer Reasoner (`reasoning/`): `answer()` entry point, deterministic computation per A0 binding decisions, fixed en/de/fi explanation templates (no LLM), unit tests incl. CubiCasa-style regression | A4 | ry | 2026-11-14 | In progress (branch `a4/ry/answer-reasoner`) |
| 15 | Done: Answer Reasoner per A0 binding decisions (deterministic, template explanations en/de/fi, zero-evidence rule, CubiCasa-style regression); edge cases in OPEN_QUESTIONS Q10 | A4 | ry | 2026-11-14 | Done (branch `a4/ry/answer-reasoner`, awaiting A0 check) |
| 16 | Done: host `cubicasa_v2/best.pt` as GitHub Release `models-cubicasa-v2`, set the URL in `models/fetch.py` (verified download) | A3 | SS | 2026-11-14 | Done (branch `a3/SS/model-hosting`) |
| 17 | A4 scope docs: A4 brief, A3 spec §I (coverage warnings), D-011/D-012, Q9 answer, Q11–Q13, MERGE_PLAN v3.1, README | A0 | ry | 2026-11-14 | Done (branch `a0/ry/a4-scope-docs`) |
| 18 | A4 follow-up: decision 9b in `docs/requests/A4-answer-reasoner.md` §4 (coverage rule also for positive counts of untyped ROOM/FIXTURE targets) | A4 | (unclaimed) | 2026-11-14 | Open (added by A0 · ry) |
