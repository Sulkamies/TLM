# Request to A0: faster image validation (smaller LLM copy, lite model)

- **From:** A1, OT, 2026-11-14 (approved by OT)
- **Branch:** `a1/ot/validator-gemini`. Please apply this on `a0/ot/validation-config-deps`, on top of a0d1ff9.
- **Goal:** validate plan images as fast as possible without losing accuracy.

## Requested config changes

`config/default.yaml → validation`:
```yaml
  llm_image_max_side_px: 1024  # LLM copy only; Gemini bills the same tokens at any size (measured), so smaller = faster upload
```

`config/llm.yaml → components.validation`:
```yaml
  validation:
    model: gemini-3.5-flash-lite
    thinking_budget: null      # REQUIRED: this model rejects thinking_budget 0 with HTTP 400 (measured)
```

`question` (A2) and the defaults are not affected. `tests/unit/common/test_config.py::test_validation_component_has_its_own_slot`
pins `gemini-3.8-flash` and needs updating.

## Measurements (A1, 2026-11-14)

The set was 22 real drawings from the Junction dataset: 11 should be accepted, 11 rejected, and one is a multi-page PDF that is rejected locally. All 21 LLM calls went through the full `validate()` path, 8 in parallel.

| Model | LLM copy | Batch time | Median per picture | Correct | Upload | Input / output tokens |
|---|---|---|---|---|---|---|
| gemini-3.8-flash | full size | 50 s | 12.4 s | 22/22 | 46 MB | 33,705 / 3,777 |
| gemini-3.8-flash | 1024 px | 21 s | 5.0 s | 22/22 | 9.7 MB | 33,705 / 3,045 |
| gemini-3.8-flash | 768 px | 20 s | 3.9 s | 22/22 | 5.8 MB | 33,705 / 2,714 |
| gemini-3.5-flash-lite | 1024 px | 12–14 s | 2.2–2.6 s | 22/22, then 21/22 | 9.7 MB | 33,705 / ~410 |

For comparison, sequential calls with full-size images took 177 s for the batch.

- **Input tokens** were identical at every image size. Gemini resizes images itself, so the smaller copy loses no accuracy on this set and costs nothing extra.
- **The only miss** in any run is "Kremsier Wohnhaus Parterre", a very large historic house. It also flips between runs on gemini-3.8-flash, so the drawing is borderline; the lite model is not worse on it.
- **The lite model** is about twice as fast and uses about 7× fewer output tokens.

## Notes

- The `PlanImage` passed to A3 is never resized. Only the copy sent to the LLM is.
- After the change, A1 re-records its cassettes with the new model (`pytest -m live tests/unit/validation/test_llm_cassettes.py`).
  The cassette test sends the committed images with `max_side_px=None`, so the keys do not depend on this setting.
