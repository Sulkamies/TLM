# Model card: CubiCasa floor-plan detector v2

| | |
|---|---|
| **analyzer_version** | `cubicasa-yolo11m-v2+rules-v2` (must equal `ANALYZER_VERSION` in `src/blueprint_qa/analysis/analyzer.py`) |
| **Used by** | A3 raster path, `src/blueprint_qa/analysis/` (PNG, JPEG, single-page PDF) |
| **Weights** | `models/cubicasa_v2/best.pt`, sha256 `2093bef2b2322dbc23c402d7e7beafe00245d6e9144905b1cd54ed0eaef3337d`, 40,587,180 bytes. Not in git; `python models/fetch.py` (hosting URL still a placeholder, see `fetch.py`) |
| **OCR** | EasyOCR 1.7, English model (`craft_mlt_25k.pth` + `english_g2.pth`, fetched by `models/fetch.py`, Apache-2.0) |
| **Owner** | A3 (Blueprint Analyzer), SS |

The version string has two parts: the **model** (`cubicasa-yolo11m-v2`, the weights above) and the **rules**
(`rules-v2`, the thresholds in `config/default.yaml -> analysis` plus the selection rules in
`analysis/raster/rules.py`, tuned on these weights). Changing either means a new version and a new card.

## Source and licence

- **Architecture:** Ultralytics YOLO11m, fine-tuned from the COCO-pretrained `yolo11m.pt` (Ultralytics, AGPL-3.0).
- **Training data:** CubiCasa5K, Zenodo record 2613548, `cubicasa5k.zip` (md5 `0ce0b203d1e3c125b51087b219bd23b9`).
  Licence **CC BY-NC-SA 4.0** (non-commercial, share-alike). The weights are derived from this data, so the same
  terms apply to them.

## Training

| Item | Value |
|---|---|
| Run | `cubicasa_v2`, 2026-11-14, 1× A100-SXM4-80GB (Verda), Ultralytics 8.4.212, torch 2.15.0+cu132 |
| Settings | imgsz **1280**, 50 epochs (all completed), batch 16, patience 20, default LR schedule |
| Augmentation | `fliplr 0.5, flipud 0.5, degrees 5, mosaic 1.0, hsv_h 0, hsv_s 0.2, hsv_v 0.3` |
| Labels | from each plan's `model.svg`, converted with `train/cubicasa_to_yolo.py` (SVG coordinates are `F1_scaled.png` pixels, no scaling) |
| Split | 4,268 train / 491 val. **The 241 images used by the challenge questions were excluded** from both (`train/exclude_ids.txt`) |

The v2 train/val split followed the file-system order on the training machine: reproducible in content (the excluded
IDs), but not exactly in its validation membership.

**Classes (13):** `window, door, toilet, sink, bathtub, shower, sauna_bench, room_balcony, room_kitchen, room_bedroom,
room_bath, room_sauna, floor`. `door` = a door with a leaf (leafless doorways were dropped from training);
`shower` excludes shower screens; `room_balcony` = CubiCasa outdoor space without garden/porch/patio/terrace and
similar; `floor` = one storey drawing on the sheet.

## Evaluation

**Detector (validation split, mAP50):** 0.817 overall. window 0.907, door 0.931, toilet 0.713, sink 0.930, bathtub
0.813, shower 0.528, sauna_bench 0.889, room_balcony 0.840, room_kitchen 0.898, room_bedroom 0.961, room_bath 0.935,
room_sauna 0.328, floor 0.950.

**Detector + rules (count questions):** **84.5 %** exact match on the held-out test split (394/466), 82.9 % on dev
(1,384/1,669). Measured on the 2,135 English CubiCasa questions over the 241 excluded images; split by image,
`md5(filename) % 4 == 0` is test; thresholds and rules were tuned on dev only. Per question type (test): windows 55 %,
floors 92 %, toilets 88 %, sinks 86 %, showers + bathtubs 85 %, doors 74 %, saunas 92 %, kitchens 89 %, bedrooms
88 %, WC rooms 90 %, bathrooms 97 %, balconies 94 %. This measures recognition and counting only, not question parsing
(A2) or the reasoner (A4); A5 re-measures end to end in `docs/METRICS.md`.

## Limitations

- **Boxes, not outlines.** Rooms are axis-aligned boxes (`ROOMS_ARE_BOXES`); no walls, no adjacency, and openings
  are not connected to rooms.
- **No scale.** `metric_available` is always `False`: no areas, lengths or other measures.
- **Six room types only:** kitchen, bedroom, balcony, bathroom, WC (`TOILET`) and sauna. Living rooms, hallways,
  storage and others are never emitted (`ROOM_TYPES_DETECTED:…` warning).
- **English OCR without diacritics:** e.g. `KEITTIÖ` is read as `KEITTIO`. OCR text is informational only
  (`label_text`, storey names).
- **Weak spots:** windows (55 % of window counts exact), shower recall (mAP50 0.53), toilet recall (0.71; a WC whose
  toilet is missed becomes a `BATHROOM`), sauna rooms (0.33; a sauna's polygon usually comes from its benches,
  `SAUNA_FROM_BENCHES`).
- **Doorways without a door leaf are not detected** (no `OPENING` kind).
- **Domain:** trained on CubiCasa5K (mostly Finnish apartment plans). Other drawing styles, tilted scans or photos
  are untested and likely worse.
