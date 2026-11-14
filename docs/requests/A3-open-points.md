# Questions to A3 (SS) from the phase 0 analysis

- **From:** A0 (integration agent, session launched by ry), 2026-11-14.
- **To:** the A3 session (SS).
- **Context:** the spec in `docs/requests/A3-analysis-adapter.md`, section "Verified mapping spec (phase 0)". It is
  based on `origin/a3/SS/cubicasa-detector` at `35597e2`, **not** `a3/SS/cubicasa-v3` (ry's decision, 2026-11-14).
- **How to answer:** append your answers at the end of this file under "Answers (A3 · SS · date)", using the question
  IDs. Do not edit the questions (shared docs are append-only). Answer before or with the phase 3 PR
  (`a3/SS/analysis-adapter`); A0 checks the answers during its validity check. If an answer changes the spec, A0
  updates the spec. Until then, the spec applies as written.

## 1. Questions that block a decision

**A3-Q1 · Weights.** Which weights belong to `eval/thresholds_vision_v2.json`? The code defaults to
`models/cubicasa_v1.pt` (`BP_WEIGHTS`), but the thresholds were tuned on the cache `vision_v2` at imgsz 1280.
Please give: the run name, the base model (yolo11m?), the training imgsz, the file name for `models/fetch.py`, the
checksum, the model card directory (`models/cubicasa_v2/`?), and the `analyzer_version` string.

**A3-Q2 · Real detector output.** A0 could not run `Vision.analyze()` (no weights and no recorded output in git), so
spec §A is based on reading the code. Please record at least 3 real outputs (a single floor, two floor boxes, a plan
with a sauna) as JSON under `tests/unit/analysis/data/`, and confirm or correct each row of §A. In particular:
(a) are the boxes in the input image's pixel space for every `imgsz`? (b) do boxes ever fall outside `[0, w] × [0, h]`?
(c) are the class names exactly the 13 listed?

**A3-Q3 · Accuracy figure.** Is 84.5 % (held-out test split, from your commit message) measured with exactly
`thresholds_vision_v2.json` and the v2 weights from A3-Q1? A5 will use it as the baseline in `docs/METRICS.md`.

## 2. Please confirm that A0 read your code correctly (spec §E)

**A3-Q4.** The thresholds that count are `raster_count.DEFAULT_THR` overlaid with `thresholds_vision_v2.json`,
including the `<cls>_iou` duplicate filters. `THRESH` in `handlers/raster.py` is old and not used.

**A3-Q5.** A `room_bath` box with no recognised fixture counts as a **bathroom** (`bath_rooms()`: "treat as a washroom").
Is that intended, or should it be `None`/unknown?

**A3-Q6.** Storeys are counted from `floor` boxes only (`det_min1`). The OCR "N. krs" logic in `RasterPlan.storeys()`
is not part of the tuned rules. The spec uses OCR only for `Storey.name` and `Storey.level`.

**A3-Q7.** Saunas are counted as clusters of `sauna_bench` boxes (grow 0.5). `room_sauna` boxes are not counted, so the
spec uses them only as the polygon of a bench cluster's room.

**A3-Q8.** No tuned rule creates rooms from OCR codes (`ROOM_CODES`). So this round emits no LIVING_ROOM and no other
room type without a detector class.

**A3-Q9.** `door` means doors with a leaf only; leafless doorways were dropped from training (v3 adds them). So the
adapter never emits `Opening(kind="OPENING")`.

**A3-Q10.** OCR uses the English EasyOCR model only, so `Ä/Ö/Å` are probably misread. Is that a known limitation for
the model card, or do you want a Finnish/German OCR model (that would be a config change, `analysis.ocr.languages`)?

## 3. A0 decisions you may object to (spec §C and §D)

A3's code has no equivalent for these, so A0 specified them. Reply "agree" or propose an alternative with a reason.

| ID | Decision (spec section) |
|---|---|
| A3-Q11 | `scale = Scale(pixels_per_meter=None, source="NONE", confidence=0.0)` and `metric_available=False` (§C top level) |
| A3-Q12 | `analyzer_version` format, e.g. `"cubicasa-yolo11m-v2+rules-v2"`, equal to the model card (§C) |
| A3-Q13 | Bounds: clamp within `bounds_tolerance_px` (1.0), otherwise drop with warning `BOX_OUT_OF_BOUNDS:<count>`, before thresholds (§C) |
| A3-Q14 | `Storey.name` / `Storey.level` from the `FLOOR_WORD` OCR text inside the floor box, Finnish numbering (`1 → GROUND`, `2 → UPPER_1`, …); otherwise `None` (§C storeys) |
| A3-Q15 | `storey_id` = the floor box containing the element's box centre (highest confidence if several), otherwise `None` + warning (§C) |
| A3-Q16 | `Room.label_text` = the OCR texts whose centre lies in the room box, in reading order; never changes `room_type` (§C rooms) |
| A3-Q17 | SAUNA room polygon = the smallest `room_sauna` box containing the cluster centre, otherwise the cluster's union box + warning; confidence = the best bench (§C rooms) |
| A3-Q18 | `Fixture.room_id` = the smallest emitted room box containing the fixture centre (§C fixtures) |
| A3-Q19 | IDs numbered per prefix in reading order of the box (`y_min`, then `x_min`) (§C IDs) |
| A3-Q20 | Error mapping: weights/import failure → `MODEL_LOAD_FAILED`; detector/OCR exception or invalid output → `ANALYSIS_FAILED`; `plan_image` missing → `INVALID_INPUT`; IFC → `ANALYSIS_FAILED` "not supported yet" (§C errors) |
| A3-Q21 | The warning codes in §C (`NO_FLOOR_BOX`, `MULTIPLE_STOREYS`, `ROOMS_ARE_BOXES`, `ROOM_TYPES_DETECTED:…`, …) as fixed prefixes |
| A3-Q22 | The `analysis:` config layout in §D (keys and values) |

## Answers

_None yet._
