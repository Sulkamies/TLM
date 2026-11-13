"""Modal: download CubiCasa5K, convert to YOLO format, fine-tune a detector.

    pip install modal && modal setup          # once per laptop
    modal run modal_train.py::discover        # print SVG class names, fix CLASS_RULES
    modal run modal_train.py::prepare         # download + convert (CPU, ~20-40 min)
    modal run --detach modal_train.py::train  # fine-tune on an H100 (keeps running if laptop sleeps)
    modal volume ls blueprints-data runs/     # see results / weights

Everything persists in the Modal Volume "blueprints-data".
"""
import subprocess

import modal

app = modal.App("blueprints-train")
vol = modal.Volume.from_name("blueprints-data", create_if_missing=True)

# Check the exact file name on https://zenodo.org/records/2613548 before running.
CUBICASA_URL = "https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"

image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("libgl1", "libglib2.0-0", "wget", "unzip")
    .pip_install("ultralytics>=8.3", "pillow")
    .add_local_dir("train", remote_path="/root/train")      # converter + exclude list
)


def _download():
    import os
    if not os.path.exists("/data/cubicasa5k"):
        subprocess.run(["wget", "-q", "-O", "/tmp/cc.zip", CUBICASA_URL], check=True)
        subprocess.run(["unzip", "-q", "/tmp/cc.zip", "-d", "/data"], check=True)
        vol.commit()


@app.function(image=image, volumes={"/data": vol}, cpu=4, timeout=3600)
def discover():
    _download()
    subprocess.run(["python", "/root/train/cubicasa_to_yolo.py",
                    "--src", "/data/cubicasa5k", "--discover"], check=True)


@app.function(image=image, volumes={"/data": vol}, cpu=8, memory=16384, timeout=3 * 3600)
def prepare():
    _download()
    subprocess.run(["rm", "-rf", "/data/yolo"], check=True)
    subprocess.run(["python", "/root/train/cubicasa_to_yolo.py", "--src", "/data/cubicasa5k",
                    "--out", "/data/yolo", "--exclude", "/root/train/exclude_ids.txt"], check=True)
    vol.commit()


@app.function(image=image, volumes={"/data": vol}, gpu="H100", cpu=16, memory=65536,
              timeout=8 * 3600)
def train(model: str = "yolo11m.pt", epochs: int = 80, imgsz: int = 1280, batch: int = 16,
          name: str = "cubicasa_v1", data: str = "/data/yolo/data.yaml"):
    from ultralytics import YOLO

    YOLO(model).train(
        data=data, epochs=epochs, imgsz=imgsz, batch=batch, workers=12,
        project="/data/runs", name=name, exist_ok=True, patience=20,
        # drawings: flips/rotations are valid, colour jitter mostly is not
        fliplr=0.5, flipud=0.5, degrees=5.0, mosaic=1.0, hsv_h=0.0, hsv_s=0.2, hsv_v=0.3,
    )
    vol.commit()
    print(f"weights: /data/runs/{name}/weights/best.pt")
