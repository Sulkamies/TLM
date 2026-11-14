# Request to A3: adapt the CubiCasa detector to `BlueprintAnalysis`

- **From:** A0 (session launched by ry), 2026-11-14
- **Source:** interface description supplied by ry (recorded here so it is not lost). The detector code
  lives in the prototype `blueprints-starter/` (`vision/analyze.py`, `handlers/raster.py`), outside
  `src/blueprint_qa/`.

## Detector interface (as supplied)

YOLO11 fine-tuned on CubiCasa5K, plus EasyOCR (English model). Axis-aligned boxes, not outlines.
GPU if available, otherwise CPU (a few seconds per image).

- Call: `from vision.analyze import get_vision; get_vision().analyze(png_or_jpeg_bytes)`.
  Options: `conf` (default 0.15), `imgsz` (default 1280; output coordinates are always in the original image).
- Weights: `models/cubicasa_v1.pt` (not in git; override with `BP_WEIGHTS`).
- PDFs are not accepted. Render to PNG first. Under §6 A1 already does this; A3 receives `PlanImage`.
- Output:

```json
{"size": [1236, 835],
 "detections": [{"cls": "toilet", "conf": 0.91, "box": [412.3, 220.8, 448.1, 270.5]}],
 "ocr": [{"text": "MH", "conf": 0.97, "poly": [[510,300],[540,300],[540,318],[510,318]]}]}
```

- `box` = `[x_min, y_min, x_max, y_max]` px, origin top-left, y down. `poly` = TL, TR, BR, BL (text may be rotated 90/270°).
- Classes: symbols `window, door, toilet, sink, bathtub, shower, sauna_bench`; rooms (box around the whole room)
  `room_kitchen, room_bedroom, room_bath, room_sauna, room_balcony`; `floor` = one box per storey on the sheet.
- Per-class thresholds (`THRESH` in `handlers/raster.py`) MUST be applied before counting.
- Not provided: scale/areas/lengths, room outlines, relations (symbol→room, room→storey, adjacency).

Rules supplied with the model: do not change the output format or class names without updating the doc and
telling the A3 owner; check every box lies within `[0,w]×[0,h]`; report per-class threshold tuning in
`docs/METRICS.md` (A5); never train on the 241 question images; licence CubiCasa5K **CC BY-NC-SA 4.0** goes
in `models/cubicasa_v1/MODEL_CARD.md`.

## Mapping notes for A3 (suggestions, A3 decides)

| Detector | `BlueprintAnalysis` |
|---|---|
| `size` | `coordinate_space="PIXEL"`, bounds check |
| `floor` boxes | `storeys` (one per box; warning if >1) |
| `room_*` boxes / OCR codes (MH, KH/PH/KPH/PESUH/SH, WC, K/KK/KT/AVOK, S/SAUNA, OH, PARVEKE) | `rooms` with `room_type`, verbatim `label_text`, polygon = 4 box corners (clockwise), `area_m2=None` |
| `door`, `window` | `openings` (`position` = box centre, `connects` from geometry, flagged uncertain) |
| `ocr` | `texts` (`bbox` from `poly`) |
| `toilet, sink, bathtub, shower, sauna_bench` | **no place in v1.0.0**, see `docs/contract-changes/001-fixture-entities.md` |
| no scale | `metric_available=False`, `scale.source="NONE"` (never assume a scale) |

The detector imports `ultralytics`/`easyocr`. Adding them to `pyproject.toml` goes through §4.3. A3 should
request it from A0.

## Addendum (A0 · ry · 2026-11-14): use the vocabulary module

Since change 003, every value A3 may emit is defined in `blueprint_qa.contracts.vocabulary` (`RoomType`,
`OpeningKind`, and their meanings in `DESCRIPTIONS`). Label tables (`analysis/labels/<lang>.yaml`) should map
to those values and be validated against `VOCABULARIES` at load time, as A2 does with synonyms. If the
detector's classes need a value that does not exist (e.g. fixtures), ask A0 for a vocabulary change. Don't
add it locally.
