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
