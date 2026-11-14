# Response from A0: faster image validation

- **From:** A0 (session launched by OT), 2026-11-14
- **Answers:** `docs/requests/A0-validation-speed.md` (A1, approved by OT)
- **Branch:** `a0/ot/validation-config-deps`, new commit on top of a0d1ff9. Local only, not merged.

## Done, as requested

1. `config/default.yaml → validation.llm_image_max_side_px: 1024`, with your comment. The other validation keys are unchanged.
2. `config/llm.yaml → components.validation`: `model: gemini-3.5-flash-lite` and `thinking_budget: null`
   (commented as required because the model rejects 0 with HTTP 400). Defaults and `question` are unchanged.
3. `tests/unit/common/test_config.py::test_validation_component_has_its_own_slot` now pins `gemini-3.5-flash-lite`.

## Checked in code (no live call)

- `common/config.py` merges `components.<name>` over `defaults` with a plain dict update, so an explicit `null` overrides
  the default `0`. `llm_settings("validation").model.thinking_budget is None` is now asserted in the test above, and
  `question` still resolves to `0`.
- `GeminiBackend` sends no `thinking_config` when the budget is `None` (model default). A new unit test,
  `test_gemini_backend_omits_thinking_config_when_budget_is_none`, covers this.
- Recorded as D-009, with your measurements. A0 did not reproduce them.

## For A1

- Re-record your validation cassettes with the new model, as you planned.
- `docs/EXTERNAL_SERVICES.md` has an update row for the model change. Your plan-image approval row is still only on your
  branch; it must reach `main` before or together with this one.
