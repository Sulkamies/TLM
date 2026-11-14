"""Detector + OCR for raster floor plans. Runs anywhere: GPU if available, else CPU.

Output format (same as documented for the team):
    {"size": [w, h],
     "detections": [{"cls": "toilet", "conf": 0.91, "box": [x0, y0, x1, y1]}],
     "ocr": [{"text": "MH", "conf": 0.97, "poly": [[x, y] x4]}]}

Batch-precompute a folder (do this on the GPU VM, then copy cache/ home):
    python -m vision.analyze --weights ~/runs/cubicasa_v1/weights/best.pt \
        --folder ~/plans/cubicasa5k --out cache/vision
"""
from __future__ import annotations

import argparse
import functools
import io
import json
import os

WEIGHTS = os.environ.get("BP_WEIGHTS", "models/cubicasa_v1.pt")


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

    def analyze(self, image_bytes: bytes, conf: float = 0.15, imgsz: int = 1280) -> dict:
        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        res = self.det.predict(arr, conf=conf, imgsz=imgsz, verbose=False, max_det=1000,
                               device=0 if self.gpu else "cpu")[0]
        names = res.names
        dets = [{"cls": names[int(c)], "conf": float(s), "box": [float(v) for v in b]}
                for b, c, s in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(),
                                   res.boxes.conf.tolist())]
        ocr = []
        if self.ocr is not None:
            # rotation_info: also read labels written at 90/270 degrees
            ocr = [{"text": t, "conf": float(p), "poly": [[float(x), float(y)] for x, y in box]}
                   for box, t, p in self.ocr.readtext(arr, rotation_info=[90, 270])]
        return {"size": list(img.size), "detections": dets, "ocr": ocr}


@functools.lru_cache(maxsize=1)
def get_vision() -> Vision:
    """Loaded once per process (model loading takes a few seconds)."""
    return Vision()


def precompute(weights: str, folder: str, out: str, conf: float = 0.15) -> None:
    os.makedirs(out, exist_ok=True)
    v = Vision(weights)
    files = [f for f in sorted(os.listdir(os.path.expanduser(folder)))
             if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    for i, f in enumerate(files, 1):
        target = os.path.join(out, f + ".json")
        if os.path.exists(target):
            continue
        with open(os.path.join(os.path.expanduser(folder), f), "rb") as fh:
            result = v.analyze(fh.read(), conf=conf)
        with open(target, "w") as fh:
            json.dump(result, fh)
        print(f"[{i}/{len(files)}] {f}: {len(result['detections'])} detections, {len(result['ocr'])} texts")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default=WEIGHTS)
    ap.add_argument("--folder", required=True)
    ap.add_argument("--out", default="cache/vision")
    ap.add_argument("--conf", type=float, default=0.15)
    a = ap.parse_args()
    precompute(a.weights, a.folder, a.out, a.conf)
