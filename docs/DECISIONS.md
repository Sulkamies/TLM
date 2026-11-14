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

### D-009 · 2026-11-14 · A0 · approved by OT · Faster image validation: 1024 px LLM copy, gemini-3.5-flash-lite
Request: `docs/requests/A0-validation-speed.md` (A1). `config/default.yaml → validation.llm_image_max_side_px: 1024`, and
`config/llm.yaml → components.validation`: `model: gemini-3.5-flash-lite`, `thinking_budget: null`. This model rejects
`thinking_budget: 0` with HTTP 400 (see D-008); with `null` the wrapper sends no thinking config, so the model default applies.
`question` and the defaults are unchanged. Only the copy sent to the LLM is shrunk; the `PlanImage` passed to A3 is never resized.

A1's measurements (2026-11-14; 22 real Junction drawings, 11 accept / 11 reject, one multi-page PDF rejected locally;
21 LLM calls through `validate()`, 8 in parallel):

| Model | LLM copy | Batch time | Median per picture | Correct | Upload | Input / output tokens |
|---|---|---|---|---|---|---|
| gemini-3.8-flash | full size | 50 s | 12.4 s | 22/22 | 46 MB | 33,705 / 3,777 |
| gemini-3.8-flash | 1024 px | 21 s | 5.0 s | 22/22 | 9.7 MB | 33,705 / 3,045 |
| gemini-3.8-flash | 768 px | 20 s | 3.9 s | 22/22 | 5.8 MB | 33,705 / 2,714 |
| gemini-3.5-flash-lite | 1024 px | 12–14 s | 2.2–2.6 s | 22/22, then 21/22 | 9.7 MB | 33,705 / ~410 |

Reason: input tokens were identical at every image size (Gemini resizes images itself), so the smaller copy costs no tokens
and lost no accuracy on this set while uploading far less. The lite model is about 2× faster and uses about 7× fewer output
tokens. Its only miss ("Kremsier Wohnhaus Parterre") also flips between runs on gemini-3.8-flash, so that drawing is borderline.
The set is small (22 drawings); A5 should confirm on the labelled fixtures. These numbers were measured by A1, not by A0.
A1 re-records its validation cassettes with the new model.

### D-010 · 2026-11-14 · A0 · approved by ry · Architecture for integration = AGENTS.md as written
A3 is question-agnostic (`analyze(ValidationResult) -> BlueprintAnalysis`), A2 and A3 run concurrently, A4 computes the
answer later. ry's earlier description (A3 receives the question) is not adopted. The A3 team designed for this too.
A3 writes its own adapter from a spec by A0 (R2.1). The integration agent opens the pull requests but never merges them.

### D-011 · 2026-11-14 · A0 · approved by ry · A4 (Answer Reasoner) is in scope now
MERGE_PLAN v3 had A4 out of scope. ry brought it in: A4 is built in parallel with A3 by an A4 session launched by ry
(branch `a4/ry/answer-reasoner`), from the brief `docs/requests/A4-answer-reasoner.md`. A0 wires it into the
orchestrator afterwards (MERGE_PLAN update, phase 5).

### D-012 · 2026-11-14 · A0 · approved by ry · Coverage warnings as positive evidence for zero answers
A4 may give a COUNT of 0 or an EXISTENCE of 0.0 only if the analysis declares, through the warnings
`ROOM_TYPES_DETECTED:`, `FIXTURE_TYPES_DETECTED:` and `OPENING_KINDS_DETECTED:`, that it can see that kind of element;
otherwise `CANNOT_ANSWER`. A convention in `warnings`, not a contract field, so no contract change is needed now
(A3 spec §I). A contract field is the cleaner long-term option (OPEN_QUESTIONS Q13).

### D-013 · 2026-11-14 · A0 · requested by ry · One HTTP API for all user interfaces; A0 approves `android-app/`
The Android app (`android-app/`, branch `ui/at/android-app`, author at) is a **client of the HTTP front door**, not a
pipeline component, so R3.3 (stack variation for components) does not apply: it never sees the contracts, only the
JSON of `POST /ask`. A0 serves that endpoint in `src/blueprint_qa/api/server.py` to the app's existing contract
(`android-app/README.md`), presented by `api/ask.py`: numbers with display units, yes/no as words in the question's
language, non-answers as text, user-safe errors, evidence boxes from A3's analysis. Server libraries are the optional
`server` extra (FastAPI, uvicorn, python-multipart), installed in CI. **A0 approves `android-app/` as a new top-level
directory (R2.4)**; one human must still approve before it is merged, and not its author (§9).
**Browser UI (ry chose "shared API, add web page"):** the same server serves a self-contained web page at `/`
(`api/web/index.html`) that uses the same `POST /ask`. The contract is written once: `docs/API.md`, backed by the
Pydantic models in `api/ask.py`; a unit test checks that both clients read only those fields and that the spec lists
them all. Changes stay additive; breaking ones need a new endpoint. The Android app is unchanged.
