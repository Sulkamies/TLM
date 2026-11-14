"""Detector + OCR for raster floor plans. Runs anywhere: GPU if available, else CPU.

Output format (same as documented for the team):
    {"size": [w, h],
     "detections": [{"cls": "toilet", "conf": 0.91, "box": [x0, y0, x1, y1]}],
     "ocr": [{"text": "MH", "conf": 0.97, "poly": [[x, y] x4]}]}

Batch-precompute a folder (do this on a GPU VM, then copy cache/ home):
    python -m vision.analyze --weights ~/runs/cubicasa_v3/weights/best.pt \
        --folder ~/plans --out ~/cache/vision_v3 --imgsz 1600 [--tile] [--tta] \
        [--reuse-ocr ~/cache/vision_v2]

--tile   large plans are also analysed in overlapping full-resolution tiles; small
         symbols (windows, doors, fixtures) from the tiles are merged with the full
         view. Rooms and storeys always come from the full view.
--tta    test-time augmentation (the model also looks at flipped/scaled copies).
--reuse-ocr DIR   copy the OCR results from an earlier cache instead of re-running OCR
         (OCR does not depend on the detector, and it is the slow part).
"""
from __future__ import annotations

import argparse
import functools
import io
import json
import os

WEIGHTS = os.environ.get("BP_WEIGHTS", "models/cubicasa_v1.pt")
# Use the resolution the model was trained at (v2: 1280, v3: 1600).
IMGSZ = int(os.environ.get("BP_IMGSZ", "1280"))
TILE = os.environ.get("BP_TILE", "0") == "1"
TTA = os.environ.get("BP_TTA", "0") == "1"

SMALL = {"window", "door", "opening", "toilet", "sink", "bathtub", "shower", "sauna_bench"}


def _iou(a, b):
    ix = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
    iy = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
    inter = ix * iy
    ua = (a[2] - a[0]) * (a[3] - a[1]) + (b[2] - b[0]) * (b[3] - b[1]) - inter
    return inter / ua if ua > 0 else 0.0


def merge_dets(dets, iou=0.5):
    """Per-class non-maximum suppression: keep the most confident of overlapping boxes."""
    out = []
    for cls in {d["cls"] for d in dets}:
        keep = []
        for d in sorted((d for d in dets if d["cls"] == cls), key=lambda d: -d["conf"]):
            if all(_iou(d["box"], k["box"]) < iou for k in keep):
                keep.append(d)
        out += keep
    return out


def tile_grid(W, H, size, overlap):
    """Top-left corners of overlapping tiles covering a W x H image."""
    def starts(n):
        if n <= size:
            return [0]
        step = size - overlap
        xs = list(range(0, n - size, step)) + [n - size]
        return sorted(set(xs))
    return [(x, y) for y in starts(H) for x in starts(W)]


def drop_cut(dets, tx, ty, size_w, size_h, W, H, margin=3):
    """Drop tile detections touching an inner tile edge (the object was cut off;
    another tile, or the full view, sees it whole)."""
    out = []
    for d in dets:
        x0, y0, x1, y1 = d["box"]
        if (x0 <= tx + margin and tx > 0) or (y0 <= ty + margin and ty > 0) \
                or (x1 >= tx + size_w - margin and tx + size_w < W) \
                or (y1 >= ty + size_h - margin and ty + size_h < H):
            continue
        out.append(d)
    return out


class Vision:
    def __init__(self, weights: str = WEIGHTS, device: str | None = None, ocr: bool = True):
        import torch
        from ultralytics import YOLO

        self.gpu = torch.cuda.is_available() if device is None else device != "cpu"
        self.det = YOLO(os.path.expanduser(weights))
        self.ocr = None
        if ocr:
            import easyocr
            # Room labels are short Latin-alphabet abbreviations (MH, KH, OH, PARVEKE...)
            self.ocr = easyocr.Reader(["en"], gpu=self.gpu)

    def _predict(self, arr, conf, imgsz, tta, ox=0, oy=0):
        res = self.det.predict(arr, conf=conf, imgsz=imgsz, verbose=False, max_det=1000,
                               augment=tta, device=0 if self.gpu else "cpu")[0]
        names = res.names
        return [{"cls": names[int(c)], "conf": float(s),
                 "box": [float(b[0]) + ox, float(b[1]) + oy, float(b[2]) + ox, float(b[3]) + oy]}
                for b, c, s in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(), res.boxes.conf.tolist())]

    def analyze(self, image_bytes: bytes, conf: float = 0.15, imgsz: int = IMGSZ,
                tile: bool = TILE, tta: bool = TTA, ocr_result: list | None = None) -> dict:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        W, H = img.size
        dets = self._predict(arr, conf, imgsz, tta)

        if tile and max(W, H) > 1.15 * imgsz:
            size, overlap = imgsz, imgsz // 4
            small = [d for d in dets if d["cls"] in SMALL]
            for tx, ty in tile_grid(W, H, size, overlap):
                crop = arr[ty:ty + size, tx:tx + size]
                th, tw = crop.shape[:2]
                td = self._predict(crop, conf, imgsz, tta, tx, ty)
                small += drop_cut([d for d in td if d["cls"] in SMALL], tx, ty, tw, th, W, H)
            dets = [d for d in dets if d["cls"] not in SMALL] + merge_dets(small)

        if ocr_result is not None:
            ocr = ocr_result
        elif self.ocr is not None:
            # rotation_info: also read labels written at 90/270 degrees
            ocr = [{"text": t, "conf": float(p), "poly": [[float(x), float(y)] for x, y in box]}
                   for box, t, p in self.ocr.readtext(arr, rotation_info=[90, 270])]
        else:
            ocr = []
        return {"size": [W, H], "detections": dets, "ocr": ocr}


@functools.lru_cache(maxsize=1)
def get_vision() -> Vision:
    """Loaded once per process (model loading takes a few seconds)."""
    return Vision()


def precompute(weights: str, folder: str, out: str, conf: float = 0.15, imgsz: int = IMGSZ,
               tile: bool = False, tta: bool = False, reuse_ocr: str | None = None) -> None:
    os.makedirs(out, exist_ok=True)
    v = Vision(weights, ocr=reuse_ocr is None)
    folder = os.path.expanduser(folder)
    files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    for i, f in enumerate(files, 1):
        target = os.path.join(out, f + ".json")
        if os.path.exists(target):
            continue
        ocr_result = None
        if reuse_ocr:
            src = os.path.join(os.path.expanduser(reuse_ocr), f + ".json")
            ocr_result = json.load(open(src))["ocr"] if os.path.exists(src) else []
        with open(os.path.join(folder, f), "rb") as fh:
            result = v.analyze(fh.read(), conf=conf, imgsz=imgsz, tile=tile, tta=tta, ocr_result=ocr_result)
        with open(target, "w") as fh:
            json.dump(result, fh)
        print(f"[{i}/{len(files)}] {f}: {len(result['detections'])} detections, {len(result['ocr'])} texts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=WEIGHTS)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--out", default="cache/vision")
    ap.add_argument("--conf", type=float, default=0.15)
    ap.add_argument("--imgsz", type=int, default=IMGSZ, help="must match training: v2 1280, v3 1600")
    ap.add_argument("--tile", action="store_true", help="also analyse large plans in full-resolution tiles")
    ap.add_argument("--tta", action="store_true", help="test-time augmentation")
    ap.add_argument("--reuse-ocr", default=None, help="cache folder whose OCR results to copy")
    a = ap.parse_args()
    precompute(a.weights, a.folder, a.out, a.conf, a.imgsz, a.tile, a.tta, a.reuse_ocr)
