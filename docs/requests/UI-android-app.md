# Request to the Android app (branch `ui/at/android-app`): connecting to the real pipeline

- **From:** A0 (session launched by ry), 2026-11-14.
- **To:** at (author of `android-app/`, branch `ui/at/android-app`, commit `e760e58`).

## 1. The server for `POST /ask` exists now (A0, branch `a0/ry/http-api`)

`python -m blueprint_qa.api.server --host 0.0.0.0 --port 8000` serves exactly the contract in `android-app/README.md`, so
**the app needs no code change**. It runs the full pipeline: A1 checks the picture, A2 ∥ A3 read the question and the
plan, A4 computes the number.

The contract is now written down once for all clients in **`docs/API.md`** (the browser page the server shows at `/`
uses the same one); please treat that file as the reference from now on. The response models live in
`src/blueprint_qa/api/ask.py`. In short:

| Pipeline result | JSON sent to the app |
|---|---|
| a number | `{"answer": 2.0, "unit": "count", "type": "count", "working": "<explanation>", "evidence": [...]}` (`m2` is sent as `m²`) |
| yes / no | `{"answer": "Kyllä" \| "Ja" \| "Yes" \| "Ei" \| "Nein" \| "No", "type": "boolean", ...}` in the question's language |
| cannot answer / needs clarification / unsupported / invalid picture | HTTP 200, `{"answer": "<reason>", "type": "text"}` |
| pipeline error | HTTP 500 or 503, `{"error": "<user-safe message>"}` |
| bad upload | 400 (missing field, empty), 413 (too large, if configured), 415 (not PNG/JPEG/PDF/IFC) |

`evidence` boxes are fractions of the picture **after EXIF rotation**, which is how Coil displays it. Rooms are boxes
around the room; doors, windows and fixtures are small squares around their position. Extra fields (`status`, `value`,
`language`, `confidence`, `request_id`) are ignored by the current app and may be used later.

Verified by A0 against the live server with the real model: counts, yes/no, text answers, error bodies, and the
evidence boxes drawn onto the picture land on the right rooms, doors and sinks.

## 2. Approval of the new top-level directory (R2.4)

A0 approves `android-app/` as a top-level directory: it is a self-contained client that touches nothing in `src/`,
`config/` or `tests/`, and it talks to the system only through the HTTP API. **One human must also approve** before
`ui/at/android-app` is merged (R2.4), and the merge approver must not be at (§9). Recorded as DECISIONS D-013.

## 3. Suggestions for the app (at decides; none blocks the merge)

1. **HEIC / WebP pictures from the gallery.** `HttpRecognizer` names every non-PNG upload `blueprint.jpg`. A HEIC or
   WebP picture is then declared JPEG, and A1 rejects it ("This picture is invalid for our program"). Re-encode
   anything that is not JPEG/PNG to JPEG before upload (e.g. `ImageDecoder` + `Bitmap.compress`).
2. **Language hint.** Send `Accept-Language` (or a `locale` form field) with the phone's locale. The server passes it
   to A2 as `locale_hint`; A2 still detects the question's language itself.
3. **README.** It says no `gradlew` is checked in, but `gradlew` and `gradlew.bat` are in the branch.
4. **First request.** The first question after the server starts takes about 15 s (model loading), later ones 5–10 s
   on a CPU. The app's 120 s read timeout is enough; a "this can take a while" hint may help.

## 4. Your web page (`web-app/`, commit `ca8a9da`) is now the served browser UI

ry asked A0 to make the server's browser page match yours. `src/blueprint_qa/api/web/index.html` is now your page,
byte for byte, except for two adaptations (marked in a comment at the top):

1. Pictures that are not PNG/JPEG (WebP from the file picker, HEIC from some cameras) are converted to JPEG in the
   browser before upload. The pipeline reads PNG, JPEG and PDF only, so WebP used to fail with 415.
2. The browser's locale is sent as the optional `locale` field (`docs/API.md`).

Your samples are served at `/samples/` with your licence file. A0 checked the whole flow live: the page loads, the
sample buttons fetch `/samples/…`, and `/ask` answers. A test now checks that every server or user string your page
puts into HTML goes through `esc()` (all 7 do).

**Proposal: keep one copy.** Two copies of the same page will drift. Options for you and the team:
(a) drop `web-app/` from `ui/at/android-app`, and send changes to the served page via a request to A0 (or the team
gives the UI role ownership of `src/blueprint_qa/api/web/` through §4.3); or (b) keep `web-app/` as the only copy and
let the server serve that folder. A0 suggests (a): it keeps the page with the server it needs.

**Suggestion chips.** Tested live on `colorful-2002` (which has a toilet bowl but no separate WC room):
"How many toilets are there?" gives **0**, because "toilets" is read as WC *rooms* (see OPEN_QUESTIONS Q14). "How many
rooms are there?" undercounts with this detector (it sees six room types), and "What is the total floor area?" always
gives "cannot answer" on raster plans (no scale). Chips that show the system at its best: "How many toilet bowls are
there?", "How many bedrooms are there?", "How many windows are there?", "How many doors are there?", "Is there a
sauna?".

**Android Studio note.** New Android Studio versions run Gradle on Java 25, which Gradle 8.11.1 does not support
("Incompatible Gradle JVM version"). Mention "Gradle JDK 17–21" in `android-app/README.md`, or pin it with
`gradle/gradle-daemon-jvm.properties` (`toolchainVersion=21`).
