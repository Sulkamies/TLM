# Recorded detector output (A3 test data)

Raw `Vision.analyze()` output (JSON, unchanged), recorded from the real model. It lets unit tests run without
weights, a GPU or network access (AGENTS.md §8).

- **Model:** `cubicasa_v2` weights, sha256 `2093bef2b2322dbc23c402d7e7beafe00245d6e9144905b1cd54ed0eaef3337d`,
  imgsz 1280, conf 0.15, max_det 1000, EasyOCR English with `rotation_info [90, 270]`, no tiling or TTA.
- **Input images:** CubiCasa5K plans from the challenge preview `data/cubicasa5k/` (licence **CC BY-NC-SA 4.0**). These
  files are derived data. The images themselves are not included.

| File | Why it is here |
|---|---|
| `colorful-12200.png.json` | one floor box, no sauna (600 × 849 px) |
| `colorful-11397.png.json` | two floor boxes at conf ≥ 0.45, three sauna-bench boxes (475 × 650 px) |
| `colorful-2002.png.json` | one floor box with a sauna (3 bench boxes) (855 × 745 px) |
