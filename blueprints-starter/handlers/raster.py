"""Raster floor plans (CubiCasa PNGs and other scans).

Reads the cached detector + OCR output written by `python -m vision.analyze`
(or runs vision/analyze.py locally if no cache exists) and answers counts with
pixel boxes as evidence.
"""
from __future__ import annotations

import json
import os
import re

CACHE_DIR = os.environ.get("BP_VISION_CACHE", "cache/vision")

# Per-class confidence thresholds: tune these on the answered questions
# (eval/run_eval.py prints per-class errors). Lower = more recall.
THRESH = {"window": 0.30, "door": 0.30, "toilet": 0.35, "sink": 0.35, "bathtub": 0.35,
          "shower": 0.35, "sauna_bench": 0.35, "floor": 0.40}
# Tuned values from eval/cubicasa_check.py --tune (set BP_THRESHOLDS to that JSON file)
if os.environ.get("BP_THRESHOLDS") and os.path.exists(os.environ["BP_THRESHOLDS"]):
    THRESH.update(json.load(open(os.environ["BP_THRESHOLDS"]))["thresholds"])

# Finnish room-label codes as they are written on plans (uppercase, no dots).
ROOM_CODES = {
    "bedroom": r"MH\d*|MAKUUHUONE|MAKUUH",
    "bathroom": r"KH|KPH|PH|PESUH|PESUHUONE|SH|KYLPYHUONE",
    "wc": r"WC",
    "kitchen": r"K|KK|KT|TK|AVOK|KEITTIÖ|KEITTIO|KEITTOKOMERO",
    "sauna": r"S|SAUNA",
    "balcony": r"PARV|PARVEKE|LASIT|LASITETTU|LASPARV",
    "living": r"OH|OLOHUONE",
}
FLOOR_WORD = re.compile(r"(\d)\s*\.?\s*(KERROS|KRS|KERR)", re.I)


def _norm(t: str) -> str:
    return re.sub(r"[^A-ZÄÖÅ0-9]", "", t.upper())


class RasterPlan:
    def __init__(self, path: str):
        self.path = path
        cache = os.path.join(CACHE_DIR, os.path.basename(path) + ".json")
        if os.path.exists(cache):
            self.data = json.load(open(cache))
        else:  # run detector + OCR locally (CPU is fine for single images)
            from vision.analyze import get_vision
            with open(path, "rb") as fh:
                self.data = get_vision().analyze(fh.read())
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(cache, "w") as fh:
                json.dump(self.data, fh)

    def detections(self, kind: str):
        t = THRESH.get(kind, 0.35)
        return [d for d in self.data["detections"] if d["cls"] == kind and d["conf"] >= t]

    def count(self, kind: str) -> dict:
        hits = self.detections(kind)
        return {"value": len(hits),
                "evidence": [{"box": d["box"], "label": f"{kind} {d['conf']:.2f}"} for d in hits]}

    def room_labels(self, category: str) -> dict:
        pat = re.compile(rf"^({ROOM_CODES[category]})$")
        hits = [o for o in self.data["ocr"] if pat.match(_norm(o["text"]))]
        return {"value": len(hits),
                "evidence": [{"poly": o["poly"], "label": o["text"]} for o in hits]}

    def storeys(self) -> dict:
        nums = {}
        for o in self.data["ocr"]:
            m = FLOOR_WORD.search(o["text"])
            if m:
                nums.setdefault(m.group(1), o)
        if nums:
            return {"value": len(nums), "evidence": [{"poly": o["poly"], "label": o["text"]} for o in nums.values()]}
        floors = self.count("floor")
        if floors["value"]:
            return floors
        return {"value": 1, "evidence": [], "note": "no storey labels or floor boxes found; assumed 1"}

    def count_question(self, qtype: str) -> dict:
        """Answer a CubiCasa-style count question with the tuned rules shared with
        eval/cubicasa_check.py. qtype: windows, floors, toilets, sinks, shower_tub, doors,
        saunas, kitchens, bedrooms, wc_rooms, bathrooms, balconies."""
        from handlers.raster_count import count
        settings = {}
        if os.environ.get("BP_THRESHOLDS") and os.path.exists(os.environ["BP_THRESHOLDS"]):
            settings = json.load(open(os.environ["BP_THRESHOLDS"]))
        value, evidence = count(self.data, qtype, settings)
        return {"value": value, "evidence": evidence}

    def text(self) -> list[dict]:
        return [{"text": o["text"], "conf": round(o["conf"], 2)} for o in self.data["ocr"]]

    def summary(self) -> dict:
        kinds = sorted({d["cls"] for d in self.data["detections"]})
        return {"image_size": self.data["size"],
                "detector_counts": {k: self.count(k)["value"] for k in kinds},
                "room_label_counts": {c: self.room_labels(c)["value"] for c in ROOM_CODES},
                "storeys": self.storeys()["value"]}

    def crop_png(self, box) -> bytes:
        """For the vision-model fallback: crop a region (pixel box) as PNG bytes."""
        import io
        from PIL import Image
        img = Image.open(self.path).convert("RGB")
        x0, y0, x1, y1 = [int(v) for v in box]
        buf = io.BytesIO()
        img.crop((x0, y0, x1, y1)).save(buf, format="PNG")
        return buf.getvalue()
