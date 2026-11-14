# Request to A2: Question Interpreter on Gemini + terminal chat

- **From:** A0 (session launched by ry), 2026-11-14
- **Requested by human:** ry, who asked for "a chat interface linked to the Gemini API, i.e. the
  question interpreter". ry chose to have A0 build the scaffolding first and A2 build the interpreter
  in a separate session.

## What exists now (A0)

- Contracts v1.0.1 in `src/blueprint_qa/contracts/` (`ParsedQuestion`, `EntityRef`, `Intent`, ...).
- `blueprint_qa.common.llm`: `load_prompt`, `get_llm_client("question")`,
  `LlmClient.generate_structured(...) -> LlmResult[T] | ErrorEnvelope`. It handles structured
  output, R7.8 re-asks, retries/backoff, R7.10 data delimiting, R7.11 logging, and cassettes
  (`BP_LLM_PROVIDER=mock`, `BP_LLM_RECORD=1`, `BP_LLM_CASSETTE_DIR`).
- `config/llm.yaml`: `components.question.model = gemini-3.8-flash`, temperature 0, thinking off.
- `GEMINI_API_KEY` is read from the environment (`.env.example`).

## What ry asked for (A2 scope, all inside `src/blueprint_qa/question/` and `tests/unit/question/`)

1. `interpreter.py :: interpret(request_id, question, locale_hint) -> ParsedQuestion | ErrorEnvelope` per §6 A2.
2. Provider adapter: `LlmQuestionProvider` (default, Gemini via the wrapper) and `MockQuestionProvider`.
3. **Terminal chat REPL:** `python -m blueprint_qa.question` (a `__main__.py`). Type a question in any
   language and it prints the resulting `ParsedQuestion` JSON (or the `ErrorEnvelope`). This is a developer
   tool, not a second public entry point.
4. Prompt `prompts/interpret.v1.md`, synonyms `synonyms/{en,de,fi}.yaml`, recorded cassettes for tests.

## Hint: what the plan side can actually see

The first raster analyzer (CubiCasa detector, see `docs/requests/A3-cubicasa-detector-adapter.md`) detects
doors, windows, kitchens, bedrooms, bathrooms, saunas and balconies, plus fixtures (toilet, sink, bathtub,
shower, sauna bench). Fixtures cannot yet be expressed in `EntityRef`; see
`docs/contract-changes/001-fixture-entities.md` (proposal, not approved). Until then, "how many
toilets?" should map to `ROOM` + `RoomType.TOILET`, per the current contract.
