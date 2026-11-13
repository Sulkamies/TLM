"""Modal: detector + OCR as one GPU service, plus a batch job that precomputes
results for every raster plan so answering a question needs no GPU at all.

    modal deploy modal_infer.py                                   # service the app calls
    modal run modal_infer.py::precompute --folder ../data/cubicasa5k --out cache/vision

From Python:  Vision = modal.Cls.from_name("blueprints-infer", "Vision")
              Vision().analyze.remote(png_bytes)
"""
import json
import os

import modal

app = modal.App("blueprints-infer")
vol = modal.Volume.from_name("blueprints-data", create_if_missing=True)
WEIGHTS = "/data/runs/cubicasa_v1/weights/best.pt"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0")
    .pip_install("ultralytics>=8.3", "easyocr", "pillow", "numpy")
)


@app.cls(image=image, gpu="L4", volumes={"/data": vol}, scaledown_window=300)
class Vision:
    @modal.enter()
    def load(self):
        import easyocr
        from ultralytics import YOLO

        self.det = YOLO(WEIGHTS)
        # Room labels are short Latin-alphabet abbreviations (MH, KH, OH, PARVEKE...)
        self.ocr = easyocr.Reader(["en"], gpu=True)

    @modal.method()
    def analyze(self, image_bytes: bytes, conf: float = 0.15, imgsz: int = 1280) -> dict:
        import io

        import numpy as np
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        arr = np.array(img)
        res = self.det.predict(arr, conf=conf, imgsz=imgsz, verbose=False)[0]
        names = res.names
        dets = [{"cls": names[int(c)], "conf": float(s), "box": [float(v) for v in b]}
                for b, c, s in zip(res.boxes.xyxy.tolist(), res.boxes.cls.tolist(),
                                   res.boxes.conf.tolist())]
        # rotation_info: also read labels written at 90/270 degrees
        ocr = [{"text": t, "conf": float(p), "poly": [[float(x), float(y)] for x, y in box]}
               for box, t, p in self.ocr.readtext(arr, rotation_info=[90, 270])]
        return {"size": list(img.size), "detections": dets, "ocr": ocr}


@app.local_entrypoint()
def precompute(folder: str, out: str = "cache/vision"):
    """Run every PNG/JPG in a local folder through the service, in parallel."""
    os.makedirs(out, exist_ok=True)
    files = [f for f in sorted(os.listdir(folder)) if f.lower().endswith((".png", ".jpg", ".jpeg"))]
    todo = [f for f in files if not os.path.exists(os.path.join(out, f + ".json"))]
    blobs = [open(os.path.join(folder, f), "rb").read() for f in todo]
    v = Vision()
    for f, result in zip(todo, v.analyze.map(blobs)):
        with open(os.path.join(out, f + ".json"), "w") as fh:
            json.dump(result, fh)
        print("done", f, len(result["detections"]), "detections")
