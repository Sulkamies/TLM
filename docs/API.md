# HTTP API for user interfaces (`POST /ask`)

- **Custodian:** A0. **Server:** `python -m blueprint_qa.api.server` (`src/blueprint_qa/api/server.py`).
- **Source of truth in code:** the Pydantic models `AskAnswer`, `AskError` and `EvidenceBox` in
  `src/blueprint_qa/api/ask.py`. This document describes them; a unit test checks that it lists every field.
- **Clients:** the Android app (`android-app/`, `HttpRecognizer`) and the browser page served at `/`
  (`src/blueprint_qa/api/web/index.html`). Both use only what is described here, so either can be used against the
  same server at the same time, and a new client needs nothing else.

## Changing this API

Only A0 changes it. Changes are **additive only**: new optional response fields, new optional request fields. Clients
must ignore fields they do not know. Renaming or removing a field, or changing its meaning, needs a new endpoint
(e.g. `/v2/ask`) and agreement from the client owners, recorded in `docs/DECISIONS.md`.

## Endpoints

| Method and path | Purpose |
|---|---|
| `POST /ask` | Answer one question about one plan picture |
| `GET /` | The browser UI |
| `GET /health` | `{"status": "ok"}`, to check that the address is reachable |

## `POST /ask` request

`multipart/form-data`:

| Field | Required | Meaning |
|---|---|---|
| `image` | yes | The plan: PNG, JPEG, single-page PDF or IFC. The format is taken from the file name's extension, else the part's content type. The server checks the real format from the bytes. |
| `question` | yes | The question in natural language (English, German and Finnish are tested). |
| `locale` | no | BCP-47 locale of the user interface, e.g. `fi-FI`. If missing, the first tag of the `Accept-Language` header is used. A hint only: the question's language is detected. |

## `POST /ask` responses

**HTTP 200**: an answer (`AskAnswer`). Questions the system cannot answer also come back as 200, with the reason as
the answer text, so clients show them as answers, not as failures.

| Field | Type | Meaning |
|---|---|---|
| `answer` | number or string | What to show: the number; for yes/no questions a word in the answer's language (`Kyllä`/`Ei`, `Ja`/`Nein`, `Yes`/`No`); otherwise the reason text |
| `unit` | string or null | Display unit next to the number: `count`, `ratio`, `m`, `m²`, `m³`, `ft`, `ft²`, `ft³`. Clients do not show `count`. Null for yes/no and text |
| `type` | string | `count`, `area`, `length`, `volume`, `ratio`, `boolean` or `text`. Show `text` as a sentence, the others as a big value |
| `working` | string or null | How the answer was reached, in the question's language. Null for `text` answers |
| `evidence` | list of boxes | Where on the picture the answer came from (see below). Empty if there is nothing to show |
| `status` | string | `ANSWERED`, `CANNOT_ANSWER`, `NEEDS_CLARIFICATION` or `UNSUPPORTED_QUESTION` |
| `value` | number or null | The raw value (yes = 1.0, no = 0.0). Null exactly when `status` is not `ANSWERED`. Never rounded |
| `language` | string | Language of `answer` (when text) and `working`, e.g. `fi` |
| `confidence` | number | 0..1 |
| `request_id` | string | Id of this request, for support and logs |

Evidence box (`EvidenceBox`): `{"label", "x", "y", "w", "h"}`. `x`, `y` are the top-left corner and `w`, `h` the size,
as **fractions (0..1) of the picture's width and height after EXIF rotation** (as browsers and Android display it).
Rooms are boxes around the room; doors, windows and fixtures are small squares around their position. `label` is a
short English name, with the plan's own room label in brackets when it was read, e.g. `Bedroom (MH 2)`.

**HTTP 4xx/5xx**: `{"error": "<message safe to show to the user>", "code": "<code or null>"}` (`AskError`).

| Status | When |
|---|---|
| 400 | `image` or `question` missing, empty question, empty file |
| 413 | File larger than `api.max_upload_bytes` (if configured) |
| 415 | Not PNG, JPEG, PDF or IFC (e.g. HEIC, GIF) |
| 500 | Internal error that will not go away by retrying |
| 503 | Temporary problem (e.g. an external service timed out); retrying may help |

## Examples

```json
{"answer": 2.0, "unit": "count", "type": "count", "working": "Täsmäävien kohteiden määrä (makuuhuone): 2.",
 "evidence": [{"label": "Bedroom (MH 2)", "x": 0.078, "y": 0.150, "w": 0.235, "h": 0.189}],
 "status": "ANSWERED", "value": 2.0, "language": "fi", "confidence": 0.84, "request_id": "…"}

{"answer": "Kyllä", "unit": null, "type": "boolean", "working": "Kyllä: täsmääviä kohteita löytyi 1 (sauna).",
 "evidence": [{"label": "Sauna", "x": 0.086, "y": 0.346, "w": 0.117, "h": 0.117}],
 "status": "ANSWERED", "value": 1.0, "language": "fi", "confidence": 0.9, "request_id": "…"}

{"answer": "The area of at least one matching room is unknown (kitchen).", "unit": null, "type": "text",
 "working": null, "evidence": [], "status": "CANNOT_ANSWER", "value": null, "language": "en",
 "confidence": 0.9, "request_id": "…"}

{"error": "Unsupported file type. Send a PNG, JPEG or PDF picture of the plan.", "code": null}
```

## Timing

The first question after the server starts takes about 15 s (the plan model loads), later ones 5–10 s on a CPU.
Clients should allow at least 60 s before giving up (the Android app allows 120 s).
