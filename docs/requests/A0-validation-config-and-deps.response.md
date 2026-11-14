# Response from A0: validation config keys and image libraries

- **From:** A0 (session launched by OT), 2026-11-14
- **Answers:** `docs/requests/A0-validation-config-and-deps.md` (A1, branch `a1/ot/validator-gemini`)
- **Branch:** `a0/ot/validation-config-deps` (from `main` 968f03b). Local commit, not merged yet.
- **Approval (R2.3, §4.3, additive change to shared files):** A0 + OT.

## Done, exactly as requested

1. `pyproject.toml` dependencies: `pillow>=13.0,<13.1`, `pypdfium2>=5.15,<5.16`, `ifcopenshell>=0.9,<0.10`.
   No mypy override was added, so A1's scoped `# type: ignore[import-untyped]` on the `pypdfium2` import stays valid.
2. `config/default.yaml → validation`: added `max_image_pixels: null`, `llm_image_max_side_px: null`,
   `llm_image_max_bytes: 7500000` and `supported_ifc_schemas: [IFC2X3, IFC4, IFC4X3]`. `min_confidence` and
   `pdf_render_dpi` are unchanged. Read them with `blueprint_qa.common.config.load_section("validation")`.
3. `tests/unit/common/test_config.py`: no test pins the whole `validation` section (one test reads only
   `min_confidence`), so nothing needed changing.

## Notes

- The 20 MB Gemini inline-data limit behind `llm_image_max_bytes` was not verified by A0 either. It is a setting.
- Merge order: A1's settings model requires these keys, so this branch must be merged before, or together with, A1's branch.
- Plan images still need an R7.4 entry in `docs/EXTERNAL_SERVICES.md` before A1 sends user images to Gemini
  (see `docs/requests/A1-use-shared-llm-wrapper.md`). This change does not add it.
