# Make Blueprints Talk: starter repo

Answers natural-language questions (any language) about construction drawings and
models. Every answer comes with the evidence highlighted on the drawing.

```
question + file ──► Claude (router + answer writer, cheap model)
                      │ calls tools, never estimates numbers itself
      ┌───────────────┼──────────────────┬───────────────────┬──────────────────┐
  raster PNG      Swiss PDF          IFC / IFC plan      schedule PDF          calc
  detector+OCR    DXF geometry       IfcOpenShell        pdfplumber tables     exact math
  (Modal GPU,     (exact, no ML)     (exact, no ML)      (vector text)
   precomputed)
      └──────────── evidence: pixel boxes | DXF polygons | IFC GUIDs | PDF boxes ──► viewer
```

| Path | What it is | Status |
|---|---|---|
| `handlers/swiss.py`, `handlers/dxf_lite.py` | Swiss Dwellings answers from the sibling DXF | **Tested: 1131/1179 (96%) of the English Swiss questions, no LLM** |
| `handlers/schedules.py` | Table regions + line search on schedule sheets | Tested on A700 |
| `handlers/ifc.py` | IfcOpenShell queries (spaces, counts, quantities, elements) | Written, **not run**: test first |
| `handlers/raster.py` | Counts from cached detector + OCR output | Written, not run (needs trained model) |
| `train/cubicasa_to_yolo.py` | CubiCasa5K SVG labels → YOLO format | Smoke-tested on a fake plan |
| `modal_train.py`, `modal_infer.py` | Modal training and GPU inference service | Written, not run |
| `app/agent.py`, `app/tools.py` | Claude tool-use loop | Written, not run |
| `app/server.py`, `app/static/index.html` | FastAPI + viewer with highlights | Written, not run |
| `eval/swiss_check.py` | Scores the Swiss handler alone | Working |
| `eval/run_eval.py` | End-to-end scoring + cost per question | Written, not run |
| `train/exclude_ids.txt` | The 241 CubiCasa plans used in questions, kept out of training | Generated |

---

## Step 0: Setup (everyone, 15 min)

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-...                        # pool the team's Claude credits
export BP_DATA_ROOT=/path/to/junction-dataset-preview  # folder that contains data/
modal setup                                            # log in to Modal once per laptop
```

Check: `python eval/swiss_check.py questions.jsonl $BP_DATA_ROOT` should print `TOTAL 1131 / 1179`.

## Step 1: Train the CubiCasa detector on Modal (person A)

1. **Find the class names.** Download CubiCasa5K into a Modal Volume and list every SVG class:
   ```bash
   modal run modal_train.py::discover
   ```
   Check the exact Zenodo file name on https://zenodo.org/records/2613548 first and fix
   `CUBICASA_URL` if it differs. In the output, every class is printed with the target it
   maps to. Edit `CLASS_RULES` in `train/cubicasa_to_yolo.py` until windows, doors,
   toilets, sinks, bathtubs, showers and sauna benches all map correctly.
2. **Convert the labels** (CPU, excludes the 241 question plans):
   ```bash
   modal run modal_train.py::prepare
   ```
   It prints box counts per class. If a class has 0 boxes, go back to step 1.
   - **Coordinate check:** the converter rescales SVG coordinates to `F1_scaled.png`
     using the SVG's width/height. Draw the labels for 3 plans
     (`modal volume get blueprints-data yolo/labels/...`) and check the boxes line up.
     If they don't, try `--image F1_original.png`.
3. **Train** (H100, about 1–2 h; `--detach` keeps it running if your laptop sleeps):
   ```bash
   modal run --detach modal_train.py::train --epochs 80 --imgsz 1280 --name cubicasa_v1
   ```
   Watch it on the Modal dashboard. Weights land in `/data/runs/cubicasa_v1/weights/best.pt`.
   If it runs out of memory, use `--batch 8`.
   If small fixtures are missed, retrain with `--imgsz 1600` or `--model yolo11l.pt`.
4. **Deploy inference and precompute** all question images (OCR + detections cached as JSON):
   ```bash
   modal deploy modal_infer.py
   modal run modal_infer.py::precompute --folder $BP_DATA_ROOT/data/cubicasa5k --out cache/vision
   ```
   From then on, answering a CubiCasa question needs **no GPU**: it reads `cache/vision/*.json`.
5. **Tune thresholds:** run `python -m eval.run_eval --questions questions.jsonl --source cubicasa5k --n 300`,
   look at the worst templates, and adjust `THRESH` and `ROOM_CODES` in `handlers/raster.py`.
   Tuning takes minutes because nothing is recomputed.

**v2 (optional):** render the Swiss DXFs to PNG together with their door, window and fixture
boxes (reuse `handlers/swiss.py`, which already has every box) and add them to
`/data/yolo`. Then measure on the Swiss PNGs. They have answers, because they are the
same floors as the Swiss PDFs.

## Step 2: Structured handlers (person B)

- **Swiss:** done. The remaining misses are listed by `eval/swiss_check.py`. Most are
  "indoor total" areas where some unnamed small rooms are excluded, and a few fixture
  shapes `classify_fixture` doesn't know yet. Open the PNG next to the DXF to see what's drawn.
- **IFC:** test `handlers/ifc.py` first:
  ```python
  from handlers.ifc import IfcModel
  m = IfcModel("data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc")
  m.overview(); m.space_area("TUALETTRUUM (55-3)", "4.korrus")   # expect 4.35
  m.quantity_sum("IfcSlab", "NetVolume", "1. Sal")               # molio: expect 146.572
  ```
  Write a small `eval/ifc_check.py` like the Swiss one for the templated IFC questions.
  The free-text `ifc_bench` questions go through the agent (`ifc_overview` + `ifc_elements`).
- **Schedules:** `schedule_tables` gives one table at a time. Claude must add things up with
  `calc` (e.g. the 418 SWING door leaves = sum of the Count column), never in its head.

## Step 3: Agent, server and viewer (person C)

```bash
python -m app.agent data/swiss_dwellings/site274_bldg500_floor1980.pdf "Wie viele Fenster hat dieser Plan?"
uvicorn app.server:app --reload --port 8000    # http://localhost:8000
```
- The **agent** (`app/agent.py`) gives Claude only the tools for the file's type, keeps
  geometry out of the prompt (cheaper), and collects the evidence of the tool calls Claude
  cites in `final_answer`.
- The **viewer** draws the evidence in each format's own coordinates: Swiss plans are
  re-drawn from the DXF, so their polygons need no mapping. IFC plans use the generated
  SVG, where elements have `data-guid`. Images and schedule pages are shown with boxes on top.
- The **cost** per question is shown in the UI. Set `BP_PRICE_IN/OUT` to the real per-million-token
  prices of `BP_MODEL`.

## Step 4: Measure, then polish (everyone, day 2)

```bash
python -m eval.run_eval --questions questions.jsonl --n 300 --split dev    # tune on dev
python -m eval.run_eval --questions questions.jsonl --n 300 --split test   # report this
```
The split is **by file**, so the Finnish and English versions of a question never sit on both sides.

**Cost lever:** most questions follow ~20 templates. A regex fast path (see the patterns in
`eval/swiss_check.py`) can answer those with **zero LLM calls**. Send only unknown phrasings
to Claude. Show both numbers in the pitch: accuracy, and cost per question compared with
sending the whole image to a frontier model.

## Known gaps / TODO
- Ask Stoa whether using the sibling DXF/SVG/IFC files is allowed. If not, the same geometry
  is in the vector PDF (PyMuPDF `page.get_drawings()`).
- Historical scans (wikimedia, europeana, finna, habs) have no questions. The `look_at_region`
  tool lets Claude inspect a crop itself, and the answer should say when it is unsure.
- Licences: CubiCasa5K is CC BY-NC-SA (fine for the hackathon, non-commercial). Swiss and IFC
  files are CC BY / MIT (see each folder's LICENSE.md).
