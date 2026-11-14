# TLM: Blueprint Q&A

Ask a numeric question about a house floor plan (PNG, JPEG, single-page PDF or IFC) in
English, German, Finnish or another language, and get back a float with its unit.

**Agents and humans: read [`AGENTS.md`](AGENTS.md) first.** It defines the roles,
ownership, contracts (§4) and workflow. `blueprints-starter/` is an old prototype that
will be deleted and replaced. Ignore it.

## Install

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows;  macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env            # then set GEMINI_API_KEY (never commit .env)
```

Python 3.11+ is required. CI runs 3.11 and 3.12.

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

## Ask a question (CLI)

One-time setup for raster plans (the A3 detector; a few GB, not needed for CI):

```bash
pip install "torch>=2.15,<2.16" --index-url https://download.pytorch.org/whl/cpu   # CPU build is enough
pip install -e ".[dev,vision]"
python models/fetch.py                  # best.pt + EasyOCR files, sha256-checked
```

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

- Pipeline: A1 (validate) → A2 (question) ∥ A3 (plan analysis), concurrently → A4 (the number).
- The format comes from the file extension unless `--format` is given. A1 still checks the real format from the bytes.
- `--json` prints the `Answer` (or the `ErrorEnvelope` without its internal `details`) as JSON.
- `--debug` prints every stage output to stderr (file bytes as `<N bytes>`, the plan analysis as a summary) and logs at INFO.
- Exit code 0 = an `Answer` (any status), 1 = an error, 2 = usage error.
- Needs `GEMINI_API_KEY` (A1 and A2 call Gemini). Offline: `BP_LLM_PROVIDER=mock` with a cassette directory.
- Without the `vision` extra or the model files, raster plans give `MODEL_LOAD_FAILED`. IFC plans are not analysed yet.
- Raster plans have no scale, so areas and lengths give `CANNOT_ANSWER`; counts and yes/no questions work.
  A typical question takes 5–7 s on a CPU (the first one about 15 s while the model loads).

## User interfaces: browser and Android app

Both talk to the same server through the same API, `POST /ask` (spec: `docs/API.md`), and can be used at the same time.
Start the server (setup as for the CLI above, plus the `server` extra):

```bash
pip install -e ".[server]"
python -m blueprint_qa.api.server --host 0.0.0.0 --port 8000
```

**Browser (laptop):** open `http://localhost:8000/` on the PC running the server, or `http://<PC-IP>:8000/` from
another computer or a phone browser on the network. Choose, drop, paste or photograph a plan (or try one of the three
sample plans), ask or tap a suggestion, and use "Show on the drawing"; hover or tap a red box to see what it marks;
zoom with the wheel, the buttons or a pinch. Design by at (`web-app/` on branch `ui/at/webpage`, commit `85524c9`);
the served copy is `src/blueprint_qa/api/web/`.

**Android app** (`android-app/`, branch `ui/at/android-app`):

1. Phone and PC on the same Wi-Fi. Find the PC's address (`ipconfig` → IPv4, e.g. `192.168.1.20`).
2. Allow Python through the Windows firewall when asked (private networks only).
3. Check from the phone's browser: `http://192.168.1.20:8000/health` → `{"status":"ok"}`.
4. In the app, tap the gear icon and enter `http://192.168.1.20:8000`. Demo mode switches off.

`--host 0.0.0.0` makes the server reachable from your network, and every question uses your `GEMINI_API_KEY`; the
default is localhost only (enough for the browser on the same PC). API spec: `docs/API.md`; response models:
`src/blueprint_qa/api/ask.py`; web page: `src/blueprint_qa/api/web/index.html`. Settings: `config/default.yaml -> api`.

## Layout status

| Path | Owner | Status |
|---|---|---|
| `src/blueprint_qa/contracts/` + `schema/*.json` | A0 | v1.1.0, matches AGENTS.md §4.2. Plan vocabulary lives only in `vocabulary.py` |
| `src/blueprint_qa/common/` (`config`, `log`, `llm`) | A0 | Done: Gemini wrapper with structured output, retries and cassettes |
| `config/default.yaml`, `config/llm.yaml` | A0 | Done (question → `gemini-3.8-flash`) |
| `src/blueprint_qa/orchestrator/`, `api/` | A0 | Done: `run()` A1 → (A2 ∥ A3) → A4 with contract checks; CLI `python -m blueprint_qa.api`; HTTP server (`POST /ask`, browser UI at `/`) |
| `android-app/` | (no role; at) | Kotlin/Compose client on branch `ui/at/android-app`; needs one human's approval to merge (R2.4, D-013) |
| `src/blueprint_qa/question/` | A2 | Done (`interpret()`, Gemini + mock providers, en/de/fi) |
| `src/blueprint_qa/validation/` | A1 | Done (`validate()`, PNG/JPEG/PDF via Gemini, IFC locally) |
| `src/blueprint_qa/analysis/`, `models/` | A3 | Done for raster plans (`analyze()`, CubiCasa YOLO + OCR; weights via `python models/fetch.py`); IFC not yet |
| `src/blueprint_qa/reasoning/` | A4 | Done (`answer()`, deterministic, en/de/fi explanations); called by the orchestrator |

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
