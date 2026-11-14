# Request to A0: validation config keys and image libraries

- **From:** A1, OT, 2026-11-14
- **Branch:** `a1/ot/validator-gemini` (A1 ported onto `main` after PR #1; it uses `common.llm` as described in `docs/requests/A1-use-shared-llm-wrapper.md`)
- **Blocking:** yes. Without the dependencies, CI cannot import `blueprint_qa.validation`. Without the keys, `validate()` returns `INTERNAL_ERROR`, because A1's settings model requires every key (R3.9: nothing hard-coded).

## 1. `pyproject.toml` dependencies (R3.4)

A1 tested with these versions:

```toml
"pillow>=13.0,<13.1",       # decode PNG/JPEG, EXIF orientation, PNG encoding
"pypdfium2>=5.15,<5.16",    # PDF page count and rendering (Apache-2.0/BSD-3, no system deps)
"ifcopenshell>=0.9,<0.10",  # IFC parsing (LGPL-3.0)
```

No mypy override is needed. `pypdfium2` has no `py.typed`, and A1 uses one scoped `# type: ignore[import-untyped]` on its import; an override would make that ignore "unused" under `--strict`. `ifcopenshell` ships `py.typed`.

## 2. `config/default.yaml → validation`

`min_confidence` and `pdf_render_dpi` are already there. Please add:

```yaml
validation:                    # A1
  min_confidence: 0.7          # [ASSUMPTION]
  pdf_render_dpi: 200          # [ASSUMPTION]
  max_image_pixels: null       # reject larger decoded/rendered images as UNREADABLE; null = no limit (R3.9)
  llm_image_max_side_px: null  # longest side of the copy sent to the LLM; null = full size (PlanImage is never resized)
  llm_image_max_bytes: 7500000 # LLM copy only: larger PNGs are shrunk until they fit; null = no limit
  supported_ifc_schemas: [IFC2X3, IFC4, IFC4X3]   # as reported by ifcopenshell (IFC4X3_ADD2 -> IFC4X3)
```

Why `llm_image_max_bytes`: in a live test on real drawings, a 1.9 MB JPEG scan became a 9.8 MB PNG after normalisation, and the API rejected the request. The value 7.5 MB raw (10 MB as base64) keeps one image well under Gemini's limit for inline request data (20 MB per request, as commonly documented; not verified by A1). It is a setting, so it can be corrected without a code change.

## 3. `tests/unit/common/test_config.py`

If a test pins the contents of the `validation` section, please update it to match.
