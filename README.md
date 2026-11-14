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

## Layout status

| Path | Owner | Status |
|---|---|---|
| `src/blueprint_qa/contracts/` + `schema/*.json` | A0 | v1.0.1, matches AGENTS.md §4.2. Plan vocabulary lives only in `vocabulary.py` |
| `src/blueprint_qa/common/` (`config`, `log`, `llm`) | A0 | Done: Gemini wrapper with structured output, retries and cassettes |
| `config/default.yaml`, `config/llm.yaml` | A0 | Done (question → `gemini-3.8-flash`) |
| `src/blueprint_qa/orchestrator/`, `api/` | A0 | Not started |
| `src/blueprint_qa/question/` | A2 | Not started. Binding design: `docs/requests/A2-question-interpreter-design.md` |
| `validation/`, `analysis/`, `reasoning/` | A1, A3, A4 | Not started |

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
