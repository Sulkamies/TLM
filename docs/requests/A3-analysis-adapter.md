# Request to A3: the analysis adapter (`analyze()`) and acceptance criteria

- **From:** A0 (session launched by ry), 2026-11-14. Part of `docs/MERGE_PLAN.md` (v2), phase 3.
- **To:** the A3 session (SS). This replaces the "Steps" in A3's own integration note where they differ.

## Answers to A3's questions

- **Does A0's code exist?** Yes. `src/blueprint_qa/contracts/` (v1.0.1), `common/` (config, log, LLM wrapper),
  A1 (`validation/`) and A2 (`question/`) are all merged in `main`. **Build on the code in `main`, not on the text
  in AGENTS.md.** The vocabulary lives only in `contracts/vocabulary.py`.
- **Fixtures (A3's change 1):** agreed in substance. Proposal `docs/contract-changes/001-fixture-entities.md` already
  exists; revision 2 there is the final diff, aligned with your list (`FixtureType`: TOILET, SINK, SHOWER, BATHTUB,
  SAUNA_BENCH, OTHER; `BlueprintAnalysis.fixtures`; `EntityRef` category `FIXTURE` + `fixture_type`). **Do not write
  a new 001 file.** A0 applies it after approval (plan phase 2), together with storey levels (004: `Storey.level`).
- **Original file passthrough (A3's change 2):** recorded as proposal 005 for a team decision. **Not part of this
  integration.** A3 works from `ValidationResult.plan_image` (raster) and `ValidationResult.ifc_bytes` (IFC) only.
- **Thresholds:** go to `config/default.yaml → analysis:` (A0). File `docs/requests/A0-detector-thresholds.md` with the
  tuned values (`eval/thresholds_vision_v2.json`) and strategies. Read them with
  `blueprint_qa.common.config.load_section("analysis")`. Do not read them from `models/` once A0 has merged them.
- **Visualisation / `--debug-overlay`:** not required for this integration (ry). If it already exists, keep it; it is not reviewed.

## Branch

`a3/SS/analysis-adapter`, created from `main`. Rebase it onto `main` after A0's phase 2 lands (it brings `Fixture`,
`StoreyLevel` and the `analysis:` config). Keep `a3/SS/cubicasa-detector` as an archive; it will not be merged.
Do not change `blueprints-starter/` on the new branch.

## Where the code goes (A3-owned paths only)

| From (prototype) | To |
|---|---|
| `vision/analyze.py` | `src/blueprint_qa/analysis/raster/detector.py` |
| `handlers/raster_count.py` (rules) | `src/blueprint_qa/analysis/raster/rules.py`, as *element selection*, not counting |
| `handlers/raster.py` `ROOM_CODES` | `src/blueprint_qa/analysis/labels/fi.yaml` (+ others), validated against `contracts.VOCABULARIES` |
| `handlers/ifc.py` (optional this round) | `src/blueprint_qa/analysis/ifc/` |
| model documentation | `models/cubicasa_v2/MODEL_CARD.md`, `models/fetch.py` (checksums; weights never in git) |
| training/eval scripts (if kept) | under `models/cubicasa_v2/` (A3-owned), not in a new top-level folder (R2.4) |

## Acceptance criteria (the A0 validity check in phase 4 tests exactly these)

1. **Entry point:** `analysis/analyzer.py :: analyze(validation: ValidationResult) -> BlueprintAnalysis | ErrorEnvelope`,
   exported only through `analysis/__init__.py`. **Never raises** (R5.1). The question is never an input.
2. **Element mapping** (as A3 proposed):
   - floor boxes → `storeys` (at least 1; if none is detected, one storey **with a warning**); rooms, openings and
     fixtures get the `storey_id` of the box they lie in. Set `Storey.level` when the label allows it, otherwise `None`.
   - kitchen / bedroom / balcony boxes → `Room` with `room_type` KITCHEN / BEDROOM / BALCONY and the OCR text inside as `label_text`.
   - bathroom boxes + fixture rule → `BATHROOM` if it contains a shower or bathtub, `TOILET` if a toilet but neither.
   - sauna bench groups → one `Room` of type `SAUNA` per group.
   - doors and windows after the duplicate filter → `Opening` DOOR / WINDOW, `position` = box centre, `connects=[]`.
   - toilets, sinks, showers, bathtubs, sauna benches → `fixtures` (with `room_id` if inside a room box).
   - OCR → `texts`. Room polygons = the 4 box corners, clockwise.
   - No scale → `metric_available=False`, `scale.source="NONE"`, all metric fields `None`. **Never guess a scale.**
   - `adjacency=[]` plus a warning, unless computed. Box-derived relations (storey, room) are flagged in `warnings`.
3. **Contract rules:** IDs `<type>_<n>` (`room_1`, `door_3`, `fixture_2`); `coordinate_space="PIXEL"` in the
   `PlanImage` pixel space (map back if resized); every box checked against `[0,w]×[0,h]`; confidences in `[0,1]`;
   `analyzer_version` equals the model card version; `request_id` passed through unchanged.
4. **Vocabulary:** no room or fixture value hard-coded outside the label tables; tables validated against
   `contracts.VOCABULARIES` at load time (a test, like A2's).
5. **Thresholds:** per-class thresholds applied before elements are emitted; all values from config (R3.9).
6. **Errors:** missing or corrupt weights → `MODEL_LOAD_FAILED`; detector failure → `ANALYSIS_FAILED`; IFC input
   without an IFC path implemented → a clean `ErrorEnvelope` (`ANALYSIS_FAILED`, message saying IFC is not supported yet).
7. **CI without weights or GPU:** torch/ultralytics/easyocr are imported **lazily** inside the detector. Unit tests use
   recorded detector output (the JSON format from `vision/analyze.py`) and never load the model or download anything.
   Coverage ≥ 80 % for `analysis/`. The model is loaded once per process (R3.7).
8. **No LLM** unless through `common/llm.py` (the boundary test enforces this).
9. **Checks pass:** ruff format/check, `mypy --strict`, schema check, the full `pytest`.
10. **Docs:** CHANGELOG entry; MODEL_CARD with source, licence (**CubiCasa5K CC BY-NC-SA 4.0**), training data
    (the 241 question images excluded), version and limitations; measured accuracy in `docs/METRICS.md` via A5.

---
## Update (A0 · ry · 2026-11-14): status of this brief

- The element mapping in "Acceptance criteria" item 2 comes from the A3 agent's own description and is **not yet
  verified against A3's code**. The integration agent analyses the A3 branch (`origin/a3/SS/cubicasa-detector`,
  not `blueprints-starter/` on `main`) and appends a **"Verified mapping spec (phase 0)"** section below. Where the
  two differ, the verified spec wins.
- Contract changes **001 (fixtures, revision 2)** and **004 (storey levels, lighter option)** are **approved** and are
  applied in plan phase 2 (contracts 1.1.0). Start the adapter branch from `main` after that lands.

---
## Verified mapping spec (phase 0)

- **By:** A0 (integration agent, session launched by ry), 2026-11-14. **This section wins where it differs from
  "Acceptance criteria" item 2 above.** Target contract: `BlueprintAnalysis` **v1.1.0** (001 rev. 2 + 004 lighter option).
- **Source analysed:** `origin/a3/SS/cubicasa-detector` at **`35597e2`** (read with `git show` only):
  `vision/analyze.py`, `handlers/raster_count.py`, `handlers/raster.py`, `eval/thresholds_vision_v2.json`,
  `eval/cubicasa_check.py`, `train/cubicasa_to_yolo.py`, `train/train.py`.
- **Version decision (ry, 2026-11-14):** implement against this **older version, not `origin/a3/SS/cubicasa-v3`**
  (`d871800`). v3 differences are listed at the end for information only. Do not implement them in this round.
- **Tags:** **[ran]** = verified by running A3's own `raster_count.py`/`raster.py` (unchanged) on hand-made detector
  output; **[read]** = verified by reading the code; **[A0 decision]** = A3's code has no equivalent, so A0 specifies it
  (R10.2; SS may object through a request to A0).
- **What could not be run:** the detector itself (`Vision.analyze()`). No weights and no recorded detector output exist
  in git, and torch/ultralytics/easyocr are not installed on the integration machine. Everything about the detector's
  output is therefore **[read]**, not observed. **First task in phase 3:** record at least 3 real outputs (a single
  floor, two floor boxes, a sauna) as JSON test data under `tests/unit/analysis/data/`, and check them against §A below.

### A. Detector output (`Vision.analyze(image_bytes, conf=0.15, imgsz=1280)`)

| Item | Finding | Tag |
|---|---|---|
| Shape | `{"size": [w, h], "detections": [{"cls", "conf", "box"}], "ocr": [{"text", "conf", "poly"}]}`; nothing else | read |
| `size` | `PIL.Image.size` of the decoded input, i.e. `[width, height]` px | read |
| `box` | `[x_min, y_min, x_max, y_max]` floats in the pixel space of the **input image** (ultralytics maps results from `imgsz` back to the input; origin top-left, y down) | read (the mapping back is library behaviour, assumed) |
| `conf` | float, already ≥ the global `conf` (0.15). Per-class thresholds are **not** applied by the detector | read |
| `cls` | exactly 13 names, from `data.yaml` written by `cubicasa_to_yolo.py` (`NAMES`): `window, door, toilet, sink, bathtub, shower, sauna_bench, room_balcony, room_kitchen, room_bedroom, room_bath, room_sauna, floor` | read |
| Class meanings | `door` = a door with a leaf (leafless doorways, "Door None", were **dropped** from training, so this version never detects them); `shower` excludes shower screens; `room_balcony` = CubiCasa "Space Outdoor" **minus** garden/porch/patio/terrace/veranda/pergola/covered area/outdoor kitchen; `floor` = one storey drawing on the sheet | read |
| `ocr` | EasyOCR, **English model only**, `rotation_info=[90, 270]`; `poly` = 4 points TL, TR, BR, BL; `[]` when OCR is disabled | read |
| Model load | once per process (`lru_cache`); GPU if `torch.cuda.is_available()` | read |
| Weights | default `models/cubicasa_v1.pt` or env `BP_WEIGHTS`; `IMGSZ` from env `BP_IMGSZ` (default 1280, "must match training: v2 1280") | read |

### B. What A3's tuned rules select (`raster_count.py` + `thresholds_vision_v2.json`)

`det(cls)` = the detections of `cls` with `conf ≥ thresholds[cls]` (0.35 when absent), sorted by confidence, then a
greedy duplicate removal at IoU ≥ `thresholds[cls + "_iou"]` (1.0 = off). **[read, ran]**

| Question type | Tuned strategy | Selection | Tag |
|---|---|---|---|
| windows | `det` | `det(window)`, thr 0.40, dup-IoU 0.4 | ran |
| doors | `det` | `det(door)`, thr 0.25, dup-IoU 0.3 | ran |
| floors | `det_min1` | `max(1, len(det(floor)))`, thr 0.45. **OCR floor words are not used** (unlike `RasterPlan.storeys()`) | ran |
| toilets | `det` | `det(toilet)`, thr 0.30 | ran |
| sinks | `det` | `det(sink)`, thr 0.20 | ran |
| shower_tub | `det` | `det(shower)` (0.25) + `det(bathtub)` (0.75) | ran |
| saunas | `bench_clusters` | clusters of `det(sauna_bench)` (0.35): each box grown by 0.5 × its size on each side, touching boxes joined (union-find). **`room_sauna` boxes are not used** | ran |
| kitchens / bedrooms / balconies | `det` | `det(room_kitchen)` 0.30 / `det(room_bedroom)` 0.15 / `det(room_balcony)` 0.45 | ran |
| bathrooms, wc_rooms | `bath_fixtures` | each `det(room_bath)` box (0.15) is **wet** if the centre of a selected shower or bathtub lies inside it; otherwise **WC-only** if a selected toilet centre lies inside; otherwise (**no fixtures**) **wet** | ran |

The unused strategies (`ocr`, `room`, `det_minus_wc`, `max_fixtures_ocr`) are **not** part of the adapter. No tuned
strategy creates elements from OCR. The measured accuracy of this configuration is 84.5 % on the held-out test split
(from the commit message; not re-measured by A0).

### C. Field-by-field mapping to `BlueprintAnalysis` 1.1.0

Principle: **counting the emitted elements in A4 must reproduce the tuned counts in §B exactly.** Each detection
becomes at most one element, and nothing is created that the tuned rules would not count. **[A0 decision]**

**Top level**

| Field | Value | Tag |
|---|---|---|
| `request_id` | `validation.request_id`, unchanged | — |
| `source_format` | `validation.input_format` (PNG/JPEG/PDF) | — |
| `coordinate_space` | `"PIXEL"`, the pixel space of `validation.plan_image` | — |
| `metric_available` | `False` | read (no scale code exists) |
| `scale` | `Scale(pixels_per_meter=None, source="NONE", confidence=0.0)`. 0.0 means "no scale determined"; it is a confidence, not a sentinel standing in for a value | A0 decision |
| `analyzer_version` | e.g. `"cubicasa-yolo11m-v2+rules-v2"`; must equal the version in the model card (open point 1) | A0 decision |
| `adjacency` | `[]` + warning `NO_ADJACENCY` | read (not computed) |
| `schema_version` | `"1.1.0"` (the model default) | — |

**Input checks.** `plan_image` is `None` → `ErrorEnvelope(INVALID_INPUT)`. `input_format == IFC` →
`ErrorEnvelope(ANALYSIS_FAILED)` with the message "IFC plans are not supported yet". Feed the detector
`plan_image.image_png` unchanged (never resize it yourself; `imgsz` is the detector's internal size). After the detector
runs, `size` must equal `(plan_image.width_px, plan_image.height_px)`, otherwise `ANALYSIS_FAILED`. **[A0 decision]**

**Bounds (every box and OCR polygon).** Clamp coordinates that lie within `bounds_tolerance_px` outside
`[0, w] × [0, h]`. Drop anything further out, or with `x_max ≤ x_min` or `y_max ≤ y_min`, and add warning
`BOX_OUT_OF_BOUNDS:<count>`. Apply this **before** the thresholds. **[A0 decision]**

**Storeys** (`floor`, after its threshold): one `Storey` per box. If none pass, exactly one storey `storey_1` and the
warning `NO_FLOOR_BOX` (this is `det_min1`). **[ran]**
- `name`: the verbatim OCR text that matches A3's `FLOOR_WORD` (`(\d)\s*\.?\s*(KERROS|KRS|KERR)`, case-insensitive) and
  whose polygon centre lies inside the floor box (the first in reading order). For the fallback storey, only if exactly
  one such text exists on the sheet. Otherwise `None`. **[read: regex; A0 decision: assignment]**
- `level` (004): from that text's digit, using Finnish numbering: `1 → GROUND`, `2 → UPPER_1`, `3 → UPPER_2`,
  `4 → UPPER_3`. Any other digit, or no text → `None`. Never guess a level from the drawing order. **[A0 decision]**
- `elevation_m`: `None`. With more than one storey: warning `MULTIPLE_STOREYS:<count>`.

**Assigning `storey_id`** (rooms, openings, fixtures): the storey whose floor box contains the element's box centre;
if several do, the one with the highest confidence; if none, `None` and the warning `NO_STOREY_FOR:<id>`. With the
fallback storey every element gets `storey_1`. With more than one storey, add the warning `STOREY_FROM_BOX_CENTRE`.
**[A0 decision]**

**Rooms** (each detection passes its own threshold first):

| Detector | `room_type` | Polygon / confidence | Tag |
|---|---|---|---|
| `room_kitchen` | `KITCHEN` | the box; `conf` | ran (selection) |
| `room_bedroom` | `BEDROOM` | the box; `conf` | ran |
| `room_balcony` | `BALCONY` | the box; `conf` | ran |
| `room_bath`, wet (including "no fixtures") | `BATHROOM` | the box; `conf` | ran |
| `room_bath`, WC-only | `TOILET` | the box; `conf` | ran |
| one cluster of `sauna_bench` | `SAUNA` | the smallest `room_sauna` box (at or above its threshold) that contains the centre of the cluster's union box; otherwise the cluster's union box and the warning `SAUNA_FROM_BENCHES:<id>`. Confidence = the highest bench `conf` in the cluster | ran (clusters); A0 decision (polygon) |
| `room_sauna` with no bench cluster | **not emitted** (the tuned rule does not count it) | — | ran |

- `polygon`: `[(x_min, y_min), (x_max, y_min), (x_max, y_max), (x_min, y_max)]`, clockwise on screen (y down).
- `label_text`: the verbatim OCR texts whose polygon centre lies in the room polygon, joined by one space in reading
  order (by `y_min`, then `x_min`); `None` if there are none. Informational only: it never changes `room_type`. **[A0 decision]**
- `area_m2`, `area_source`, `height_m`, `source_ref`: `None`.
- **Not emitted:** rooms that exist only as OCR codes (e.g. `OH`, living room). No detector class covers LIVING_ROOM,
  DINING_ROOM, HALLWAY, GARAGE, STORAGE, CLOSET, LAUNDRY, OFFICE or TECHNICAL. Add the warning
  `ROOM_TYPES_DETECTED:BALCONY,BATHROOM,BEDROOM,KITCHEN,SAUNA,TOILET` to every raster analysis (open point 3).
- Add the warning `ROOMS_ARE_BOXES` (polygons are axis-aligned boxes, not outlines).

**Openings:** `det(window)` → `Opening(kind="WINDOW")`, `det(door)` → `Opening(kind="DOOR")`, after the dup-IoU
filters. `position` = box centre; `width_m=None`; `connects=[]` and the warning `NO_OPENING_CONNECTIVITY`;
`source_ref=None`; confidence = `conf`. Kind `OPENING` is never emitted (this model does not detect leafless
doorways). **[ran]**

**Fixtures (001):** `det(toilet)` → `TOILET`, `det(sink)` → `SINK`, `det(shower)` → `SHOWER`, `det(bathtub)` →
`BATHTUB`, `det(sauna_bench)` → `SAUNA_BENCH` (**one fixture per bench**, not per cluster). `OTHER` is never emitted.
`position` = box centre. `room_id` = the emitted room (any type) whose polygon contains the centre, the smallest by area
if several, otherwise `None`; add the warning `FIXTURE_ROOM_FROM_BOX_CENTRE`. `source_ref=None`; confidence = `conf`.
**[ran: selection; A0 decision: room_id]** The fixtures used to classify a `room_bath` box are the same selected
fixtures (same thresholds), so the two always agree.

**Texts:** every OCR result → `TextAnnotation(text verbatim, bbox = min/max of the poly's x and y, confidence = conf)`,
after the bounds check. No confidence filter (the tuned rules use none); the config key `ocr.min_confidence` defaults
to 0.0. **[read]**

**IDs:** per prefix `storey_`, `room_`, `door_`, `window_`, `fixture_`, numbered from 1 in the reading order of the box
(`y_min`, then `x_min`), so equal input gives equal IDs. **[A0 decision]**

**Errors:** weights missing or corrupt, or a torch/ultralytics import failure → `MODEL_LOAD_FAILED`; any detector or
OCR exception → `ANALYSIS_FAILED` (user-safe message, the exception class in `details`); output that fails contract
validation → `ANALYSIS_FAILED`. Never raise. **[A0 decision, consistent with criteria 1 and 6]**

### D. Config (`config/default.yaml → analysis:`, added by A0 in phase 2; read with `load_section("analysis")`)

```yaml
analysis:                      # A3; values from thresholds_vision_v2.json at 35597e2
  detector:
    weights_path: models/cubicasa_v2/best.pt   # [to confirm with SS, open point 1]
    weights_env: BP_WEIGHTS    # env var that overrides weights_path
    conf: 0.15                 # detector pre-filter
    imgsz: 1280                # must match the training size of the weights
    max_det: 1000
    device: auto               # auto | cpu | cuda
  ocr:
    enabled: true
    languages: [en]
    rotation_info: [90, 270]
    min_confidence: 0.0
  default_threshold: 0.35      # for classes without an entry
  thresholds:                  # per class, applied before any element is emitted
    window: 0.4
    door: 0.25
    toilet: 0.3
    sink: 0.2
    bathtub: 0.75
    shower: 0.25
    sauna_bench: 0.35
    room_kitchen: 0.3
    room_bedroom: 0.15
    room_bath: 0.15
    room_balcony: 0.45
    room_sauna: 0.35
    floor: 0.45
  duplicate_iou:               # 1.0 = off
    window: 0.4
    door: 0.3
    toilet: 1.0
    sink: 1.0
    shower: 1.0
    bathtub: 1.0
  sauna_cluster_grow: 0.5
  bounds_tolerance_px: 1.0
```

The per-question "strategies" are not config. A3 is question-agnostic, so the tuned choices are fixed in §C as
element-selection rules (documented in `analysis/raster/rules.py`). Changing them means changing this spec.

### E. Differences from the earlier descriptions

| # | Earlier text | Verified | Consequence |
|---|---|---|---|
| 1 | "Per-class thresholds (`THRESH` in `handlers/raster.py`)" (cubicasa-detector brief) | The tuned rules use `raster_count.DEFAULT_THR` overlaid with `thresholds_vision_v2.json`, plus `<cls>_iou` duplicate filters. `THRESH` in `raster.py` is the old untuned set | Use §D only |
| 2 | Bathroom rule: `BATHROOM` if shower/bathtub, `TOILET` if toilet only (criterion 2) | A `room_bath` box with **no** fixtures also counts as **BATHROOM** | §C follows the code |
| 3 | Storeys from floor boxes (both briefs) | Same, but `RasterPlan.storeys()` prefers OCR "N. krs" texts; the tuned rule (`det_min1`) ignores them | Count from boxes; use OCR only for `name`/`level` |
| 4 | "sauna bench groups → one Room SAUNA per group" | Same (grow 0.5). `room_sauna` boxes are not used by the tuned rule | Not emitted on their own; used only as the polygon |
| 5 | Room codes `MH, KH/PH/KPH/PESUH/SH, WC, K/KK/KT/AVOK, S/SAUNA, OH, PARVEKE` as a room source | `ROOM_CODES` is used only by the untuned `ocr` strategies | Copy to `labels/fi.yaml` for later use; do not create rooms from OCR this round |
| 6 | Weights `models/cubicasa_v1.pt`, model card `models/cubicasa_v1/` (first brief) vs `models/cubicasa_v2/` (this brief) | The code default is still `cubicasa_v1.pt`, but the thresholds were tuned on cache `vision_v2` at imgsz 1280 | Open point 1 |
| 7 | "`door`" | Doors **with** a leaf only; leafless doorways were dropped from training | No `OPENING` kind |
| 8 | OCR reads the labels (MH, KH, …) | English OCR model only, so `Ä/Ö/Å` are likely misread (`ROOM_CODES` contains `KEITTIÖ`) | A limitation for the model card |

### F. Open points (A3 / SS to answer in the phase 3 PR)

1. **Which weights** belong to `thresholds_vision_v2.json`: the v2 run at imgsz 1280? Name the model card directory,
   the file name and `analyzer_version` to match, and put the checksum in `models/fetch.py`.
2. Real detector output was not observed by A0 (see the top of this section). Confirm §A against the recorded JSON.
3. **For A4 (later, not A3):** `warnings` are not machine-readable coverage. An EXISTENCE question about a room type
   this detector cannot see (e.g. a living room) must give `CANNOT_ANSWER`, not `0.0`. A4 will need either the
   `ROOM_TYPES_DETECTED` warning convention or a contract field. A0 records this when A4 starts.

### G. For information only: `origin/a3/SS/cubicasa-v3` (`d871800`), not to be implemented now

Same JSON shape. It adds a 14th class `opening` (a leafless doorway, which would map to `Opening(kind="OPENING")`),
optional tiled inference (`BP_TILE`) and test-time augmentation (`BP_TTA`), `--reuse-ocr`, and imgsz 1600 for the v3
weights. `raster_count.py` and the thresholds file are unchanged there. Adopting v3 later needs updates to §A, §C
(openings) and §D, and re-tuned thresholds.
