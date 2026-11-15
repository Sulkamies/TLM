# TLM: Blueprint Q&A

Upload a house floor plan and ask a question about it in plain language: "How many bedrooms are there?",
"Onko asunnossa saunaa?", "Wie viele Bäder gibt es?". The program answers with a number and its unit
(`3 count`, `1 boolean` for yes), a short explanation in the language of the question, and the parts of the
drawing it counted, shown as boxes on the picture.

- **Input:** a PNG, JPEG or single-page PDF floor plan. IFC (BIM) files are validated but not analysed yet.
- **Questions:** any language. English, German and Finnish are tested.
- **Interfaces:** a browser page (laptop and phone), a command line, and an HTTP API that an Android app can use.

**Agents and humans: read [`AGENTS.md`](AGENTS.md) first.** It defines the roles, ownership, contracts (§4) and
workflow. `blueprints-starter/` and `README-training.md` belong to an old prototype that will be deleted. Ignore them.

## How it works

```
picture + question ─► A1 Input Validator         is this a floor plan?  (Gemini, gemini-3.5-flash-lite)
                      ├─► A2 Question Interpreter  what is being asked?   (Gemini, gemini-3.8-flash)
                      └─► A3 Blueprint Analyzer    what is in the plan?   (local: CubiCasa YOLO11 + EasyOCR, CPU)
                          A4 Answer Reasoner       the number             (deterministic code, no LLM)
```

- A2 and A3 run at the same time. A2 never sees the plan and A3 never sees the question.
- Language models only classify and interpret. **The number is always computed by code** in A4, never by an LLM.
- The plan has no scale, so areas and lengths give `CANNOT_ANSWER`. Counts and yes/no questions work.
- A typical question takes 5–7 s on a CPU (the first one about 15 s while the model loads).

## Current results

Measured on `main` in November 2026 on 51 CubiCasa floor plans that were never used for training or tuning
(932 count questions, half in English and half in Finnish):

- **Accuracy:** 84.5 % of answers exactly right. Rooms and fixtures score 84–97 % (bathrooms, balconies, floors,
  saunas, WC rooms, kitchens, bedrooms, toilets, sinks, showers and bathtubs). Doors (74 %) and windows (55 %) are
  the weak spots, which comes from the detector. English and Finnish questions gave identical answers.
- **Gemini cost:** about $0.024 for one picture with five questions (about $0.005 per question), at November 2026
  prices. About 98 % of it is the question prompt; the picture check costs about $0.0005.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then set GEMINI_API_KEY (never commit .env)
```

Python 3.11+ is required. CI runs 3.11 and 3.12.

To analyse floor plans and run the server you also need the detector (a few GB, not needed for CI):

```bash
pip install "torch>=2.15,<2.16" --index-url https://download.pytorch.org/whl/cpu   # CPU build is enough
pip install -e ".[dev,vision,server]"
python models/fetch.py                  # best.pt + EasyOCR files, sha256-checked
```

> **Windows with Smart App Control / WDAC:** if `mypy` fails with "DLL load failed",
> reinstall it as pure Python: `pip install --force-reinstall --no-deps --no-binary mypy "mypy>=2.4,<2.5"`
> and run it as `python -m mypy`.

## Check (same as CI)

```bash
ruff format --check src tests
ruff check src tests
mypy                                                    # strict, configured in pyproject.toml
python -m blueprint_qa.contracts.generate_schema --check
pytest --cov=blueprint_qa                                # mocks only, no network
pytest -m live                                           # opt-in: real Gemini calls, needs GEMINI_API_KEY
```

## Browser

```bash
python -m blueprint_qa.api.server                              # http://localhost:8000/
python -m blueprint_qa.api.server --host 0.0.0.0 --port 8000   # also reachable from phones on the network
```

Open `http://localhost:8000/` on the PC running the server, or `http://<PC-IP>:8000/` from a phone or another
computer on the same network (find the address with `ipconfig` → IPv4, and allow Python through the Windows
firewall for private networks).

1. Choose, drop or paste a floor plan picture.
2. Optional: tap the crop button in the zoom bar, drag the frame or its corners and choose **Use selection**.
   Only the cut-out is analysed. **Original picture** undoes the crop.
3. Ask questions in the chat. Each answer shows the number; **Show on the drawing** marks what was counted.
   Hover or tap a box to see what it is. Zoom with the wheel, the buttons or a pinch.
4. **New drawing** starts over with another picture.

On phones the page uses a phone layout with touch zoom and a full-screen button. The design is by at; the served
page is `src/blueprint_qa/api/web/index.html`.

`--host 0.0.0.0` makes the server reachable from your network, and every question uses your `GEMINI_API_KEY`.
The default is localhost only. Settings: `config/default.yaml` → `api`.

## Command line

```bash
python -m blueprint_qa.api <file> "<question>" [--format PNG|JPEG|PDF|IFC] [--locale fi-FI] [--json] [--debug]

python -m blueprint_qa.api plan.jpg "Montako makuuhuonetta?"
# 2 count
# Täsmäävien kohteiden määrä (makuuhuone): 2.
python -m blueprint_qa.api plan.jpg "Wie groß ist die Küche?"
# Die Fläche mindestens eines passenden Raums ist unbekannt (Küche).
# [CANNOT_ANSWER]
python -m blueprint_qa.api tests/unit/validation/data/bar_chart.png "How many bedrooms?"
# This picture is invalid for our program
# [CANNOT_ANSWER]
```

- The format comes from the file extension unless `--format` is given. A1 still checks the real format from the bytes.
- `--json` prints the `Answer` (or the `ErrorEnvelope` without its internal `details`) as JSON.
- `--debug` prints every stage output to stderr (file bytes as `<N bytes>`, the plan analysis as a summary) and logs at INFO.
- Exit code 0 = an `Answer` (any status), 1 = an error, 2 = usage error.
- Offline: `BP_LLM_PROVIDER=mock` with a cassette directory replays recorded Gemini responses.
- Without the `vision` extra or the model files, floor plans give `MODEL_LOAD_FAILED`.

## HTTP API and Android app

The server offers `POST /ask` (a picture and a question in, the answer and its evidence boxes out), `GET /health`
and the browser page at `/`. The spec is [`docs/API.md`](docs/API.md); the response models are in
`src/blueprint_qa/api/ask.py`.

The Android app (Kotlin/Compose) uses the same API. It is in `android-app/` on at's branch `ui/at/webpage` and is
**not merged into `main` yet** (see [`docs/requests/UI-android-app.md`](docs/requests/UI-android-app.md)). To use it,
start the server with `--host 0.0.0.0`, check `http://<PC-IP>:8000/health` from the phone's browser
(`{"status":"ok"}`), then tap the gear icon in the app and enter `http://<PC-IP>:8000`. In Android Studio, set the
Gradle JDK to 17–21.

## Project status

| Path | Owner | Status |
|---|---|---|
| `src/blueprint_qa/contracts/` + `schema/*.json` | A0 | v1.1.0, matches AGENTS.md §4.2. Plan vocabulary lives only in `vocabulary.py` |
| `src/blueprint_qa/common/` (`config`, `log`, `llm`) | A0 | Done: Gemini wrapper with structured output, retries and cassettes |
| `config/default.yaml`, `config/llm.yaml` | A0 | Done: models per component, thresholds, server settings |
| `src/blueprint_qa/orchestrator/`, `api/` | A0 | Done: `run()` A1 → (A2 ∥ A3) → A4 with contract checks; CLI; HTTP server and browser page |
| `src/blueprint_qa/validation/` | A1 | Done: `validate()`, PNG/JPEG/PDF via Gemini, IFC locally |
| `src/blueprint_qa/question/` | A2 | Done: `interpret()`, Gemini and mock providers, en/de/fi |
| `src/blueprint_qa/analysis/`, `models/` | A3 | Done for raster plans: `analyze()`, CubiCasa YOLO + OCR (weights via `python models/fetch.py`). IFC not yet |
| `src/blueprint_qa/reasoning/` | A4 | Done: `answer()`, deterministic, en/de/fi explanations |
| `android-app/` | (no role; at) | On branch `ui/at/webpage`, not in `main` yet; needs one human's approval to merge (R2.4, D-013) |

Open work: IFC analysis (A3), scale detection for areas and lengths (A3), door and window accuracy (A3), and
checking the picture only once per chat (`a0/ry/validation-receipt`, open PR). Team coordination lives in
[`docs/TASKS.md`](docs/TASKS.md), [`docs/OPEN_QUESTIONS.md`](docs/OPEN_QUESTIONS.md) and
[`docs/DECISIONS.md`](docs/DECISIONS.md).

## Using the LLM wrapper (A1, A2, A3)

All LLM calls go through `blueprint_qa.common.llm` (R7.5). See the module docstring for a
full example. In short:

```python
prompt = load_prompt(Path(__file__).parent / "prompts", "interpret", 1)   # interpret.v1.md
client = get_llm_client("question")                                       # reads config/llm.yaml
result = client.generate_structured(request_id=rid, stage=Stage.QUESTION, prompt=prompt,
                                    data={"question": q}, output_model=MyLlmOutput)
# -> LlmResult[MyLlmOutput] (with .provider = "llm:<model>:interpret@v1") or ErrorEnvelope
```

* Mock mode: `BP_LLM_PROVIDER=mock BP_LLM_CASSETTE_DIR=<dir>` replays recorded responses.
* Recording: `BP_LLM_RECORD=1 BP_LLM_CASSETTE_DIR=<dir>` with a real key stores responses as
  `<dir>/<prompt>@v<N>.json` (R7.12).
