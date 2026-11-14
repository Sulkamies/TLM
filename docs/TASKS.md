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
