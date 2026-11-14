# Request to A1: classify images through the shared LLM wrapper

- **From:** A0 (session launched by ry), 2026-11-14
- **Context:** ry says A1 is implemented independently. This note tells A1, and the agent that merges
  A1 into `main`, how A1 must make its LLM call so that it fits the rest of the system.

## Verified

On 2026-11-14 A0 sent a synthetic test image (no user data) through `common/llm.py` as A1 would.
`gemini-3.8-flash` returned a validated structured verdict in about 6 s, using about 1.2k input tokens for a
256×256 image. Larger plans cost more image tokens.

## How A1 calls Gemini (R7.5: no vendor SDK in `validation/`)

```python
from pathlib import Path
from pydantic import BaseModel, Field
from blueprint_qa.common.llm import LlmResult, get_llm_client, load_prompt
from blueprint_qa.contracts import ErrorEnvelope, Stage

class LlmVerdict(BaseModel):                    # A1-internal; raw labels never leave validation/
    label: Literal["FLOOR_PLAN", "OTHER_DRAWING", "PHOTO", "TEXT_DOCUMENT", "UNKNOWN"]
    confidence: float = Field(ge=0.0, le=1.0)

prompt = load_prompt(Path(__file__).parent / "prompts", "classify", 1)   # validation/prompts/classify.v1.md
result = get_llm_client("validation").generate_structured(
    request_id=request.request_id, stage=Stage.VALIDATION, prompt=prompt,
    data={"filename": request.filename},          # user text goes here as data, never into the prompt (R7.10)
    output_model=LlmVerdict,
    images_png=[normalized_png_bytes],            # the PNG that becomes PlanImage.image_png
)
if isinstance(result, ErrorEnvelope):
    return result                                 # already has a §5 code, user-safe message, retryable flag
# map result.parsed.label -> ValidationReason; compare confidence with validation.min_confidence
# ValidationResult.provider = result.provider     # "llm:gemini-3.8-flash:classify@v1"
```

What A1 gets for free: temperature 0, JSON-schema output with re-asks (R7.8), retries/backoff on timeout,
5xx and 429 (R7.2), token/latency logging (R7.11), and recorded-response mocks keyed by image hash (R7.12).
To record: `BP_LLM_RECORD=1 BP_LLM_CASSETTE_DIR=tests/unit/validation/cassettes`. To replay in tests:
`BP_LLM_PROVIDER=mock` or inject `CassetteBackend(path)`.

Config already in place (A0): `config/llm.yaml → components.validation.model: gemini-3.8-flash`;
`config/default.yaml → validation.min_confidence: 0.7`, `validation.pdf_render_dpi: 200`
(read with `blueprint_qa.common.config.load_section("validation")`). A1 needs a change there? Request it from A0.

## Before A1 sends real plans

**Plan images are not yet approved for Gemini** (R7.4; `docs/EXTERNAL_SERVICES.md` covers question text only).
A human must approve and append a row to `docs/EXTERNAL_SERVICES.md` first.

## Merge checklist (for the merging agent)

1. Merge the A0 branch (`common/`, `contracts/`, `config/`) **before** A1. A1 depends on it.
2. CI test `tests/unit/common/test_llm_boundary.py` fails if any file outside `common/` imports a vendor LLM
   SDK (`google.genai`, `openai`, `anthropic`, ...). If A1 was built with its own Gemini client, replace that
   client with the snippet above inside `validation/`. Do **not** relax the test, and do not move A1 code into `common/`.
3. A1's own retry/timeout constants, if any, must be removed in favour of `config/default.yaml` (R3.9).
4. A1 must return only `ValidationResult | ErrorEnvelope` from `validate()`. Wrapper errors pass through unchanged.
5. Check that the `docs/EXTERNAL_SERVICES.md` image approval exists before enabling live image calls.
