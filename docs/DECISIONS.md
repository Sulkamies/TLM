# Decisions

Append-only. Stack variations (R3.3) MUST be recorded here with human approval.

### D-001 · 2026-11-14 · A0 · approved by ry · LLM provider: Google Gemini
All LLM calls use the Google Gemini API through the official `google-genai` SDK, wrapped in
`src/blueprint_qa/common/llm.py`. The Question Interpreter uses `gemini-2.5-flash` (cheap, fast, enough for
temperature-0 structured extraction). Changing provider or model is an edit to `config/llm.yaml` (R7.6).

### D-002 · 2026-11-14 · A0 · `bytes` fields are base64 in JSON
`PipelineRequest.input_bytes`, `PlanImage.image_png` and `ValidationResult.ifc_bytes` serialise as base64
(`ConfigDict(ser_json_bytes="base64", val_json_bytes="base64")`). Pydantic's default (UTF-8) cannot carry
binary data, which R3.3 non-Python components need. This is a serialisation setting only: field names and
types are unchanged from §4.2. The generated schemas mark these fields `"format": "base64"`.

### D-003 · 2026-11-14 · A0 · Retries are owned by the wrapper, not the SDK
The SDK's built-in HTTP retry is disabled (`HttpRetryOptions(attempts=1)`). `LlmClient` retries retryable
transport errors (timeout, 5xx, 429) with exponential backoff from `config/default.yaml: llm`, so that R7.2
and R3.9 are honoured in one place. 4xx other than 429 is never retried. Schema-validation re-asks (R7.8) are
counted separately (`max_validation_retries`) and send the validation errors back to the model as a follow-up turn.

### D-004 · 2026-11-14 · A0 · Cassette format
Recorded LLM responses live in `<cassette dir>/<prompt-name>@v<N>.json`, one file per prompt version (R7.12),
keyed by a hash of the conversation turns and image hashes. The system prompt is not part of the key, because the
version is in the filename. Each component keeps its cassette directory next to its tests and selects it with
`BP_LLM_CASSETTE_DIR` (or injects `CassetteBackend(path)` directly).

### D-005 · 2026-11-14 · A0 · Gemini "thinking" disabled by default
`thinking_budget: 0` in `config/llm.yaml` for lower latency and cost on extraction tasks. A component can
override it in its `components.<name>` block.

### D-006 · 2026-11-14 · A0 · Cassette key includes rendered prompt and output schema (supersedes part of D-004)
The cassette key now also hashes the rendered system instruction and the response JSON Schema. Prompts can contain
`{{PLACEHOLDERS}}` filled from contracts at runtime (`Prompt.render`, strict about missing or unexpected values), so the same
`<name>@v<N>` can render differently after a vocabulary change. Old recordings must then miss loudly rather than
replay stale answers. The file layout (`<prompt>@v<N>.json`) is unchanged. The model id is still not part of the key.

### D-007 · 2026-11-14 · A0 · approved by ry · Vocabulary-driven interpreter
Plan-element values live only in `contracts/vocabulary.py` (change 003). The Question Interpreter derives its LLM
schema and prompt from it, and never hard-codes values (design: `docs/requests/A2-question-interpreter-design.md`).
Goal: when the analyzer's structure changes, only contracts and language data change.

### D-008 · 2026-11-14 · A0 · approved by ry · Model: gemini-3.8-flash (supersedes the model choice in D-001)
The live test showed Google returns 404 for `gemini-2.5-flash`: *"no longer available to new users … use
models/gemini-3.8-flash"*. `gemini-3.8-flash` was verified with the wrapper's exact settings (JSON schema, temperature 0,
`thinking_budget: 0`). `config/llm.yaml` (defaults and `components.question`) now uses it. Note: `gemini-3.5-flash-lite`
rejects `thinking_budget: 0` (HTTP 400). If it is ever used, set `thinking_budget: null` for that component.
