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

```bash
python -m blueprint_qa.api <file> "<question>" [--format PNG|JPEG|PDF|IFC] [--locale fi-FI] [--json] [--debug]

python -m blueprint_qa.api tests/unit/validation/data/house_plan_fi.png "Montako makuuhuonetta?"
# Plan analysis is not available yet.
# [CANNOT_ANSWER]
python -m blueprint_qa.api tests/unit/validation/data/bar_chart.png "How many bedrooms?"
# This picture is invalid for our program
# [CANNOT_ANSWER]
```

- The format comes from the file extension unless `--format` is given. A1 still checks the real format from the bytes.
- `--json` prints the `Answer` (or the `ErrorEnvelope` without its internal `details`) as JSON.
- `--debug` prints every stage output to stderr (file bytes are shown as `<N bytes>`) and logs at INFO.
- Exit code 0 = an `Answer` (any status), 1 = an error, 2 = usage error.
- Needs `GEMINI_API_KEY` (A1 and A2 call Gemini). Offline: `BP_LLM_PROVIDER=mock` with a cassette directory.
- Pipeline today: A1 → A2 (MERGE_PLAN phase 1). A3 (plan analysis) and A4 (the number) are empty slots, so
  every answer is an interim answer **without a number** until they are integrated.

## Layout status

| Path | Owner | Status |
|---|---|---|
| `src/blueprint_qa/contracts/` + `schema/*.json` | A0 | v1.0.1, matches AGENTS.md §4.2. Plan vocabulary lives only in `vocabulary.py` |
| `src/blueprint_qa/common/` (`config`, `log`, `llm`) | A0 | Done: Gemini wrapper with structured output, retries and cassettes |
| `config/default.yaml`, `config/llm.yaml` | A0 | Done (question → `gemini-3.8-flash`) |
| `src/blueprint_qa/orchestrator/`, `api/` | A0 | Phase 1: `run()` A1 → A2 with interim answers; CLI `python -m blueprint_qa.api`. A3/A4 slots empty |
| `src/blueprint_qa/question/` | A2 | Done (`interpret()`, Gemini + mock providers, en/de/fi) |
| `src/blueprint_qa/validation/` | A1 | Done (`validate()`, PNG/JPEG/PDF via Gemini, IFC locally) |
| `analysis/`, `reasoning/` | A3, A4 | A3 in progress (`docs/requests/A3-analysis-adapter.md`); A4 not started |

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
