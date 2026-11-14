"""Fine-tune the floor-plan detector on any machine with a GPU (Verda VM, laptop, ...).

    python train/train.py --data ~/yolo/data.yaml --epochs 1 --name smoke      # quick check
    python train/train.py --data ~/yolo/data.yaml --name cubicasa_v1           # full run
    python train/train.py --data ~/yolo/data.yaml --model yolo11l.pt --imgsz 1600 \
        --device 0,1,2,3 --batch 32 --cache ram --name cubicasa_v3                 # 4-GPU quality run

Results go to ~/runs/<name>/ (weights/best.pt, results.png, train_batch0.jpg, ...).
"""
import argparse
import os

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True, help="data.yaml written by cubicasa_to_yolo.py")
    ap.add_argument("--model", default="yolo11m.pt", help="pretrained start point (downloaded automatically)")
    ap.add_argument("--epochs", type=int, default=80)
    ap.add_argument("--imgsz", type=int, default=1280)
    ap.add_argument("--batch", type=int, default=16, help="lower to 8 if you run out of GPU memory")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--project", default=os.path.expanduser("~/runs"))
    ap.add_argument("--name", default="cubicasa_v1")
    ap.add_argument("--device", default="0",
                    help="GPU(s): '0', or '0,1,2,3' to spread one run over 4 GPUs (batch is the total)")
    ap.add_argument("--cache", default="false", choices=["false", "ram", "disk"],
                    help="ram: keep decoded images in memory (faster; needs ~30-60 GB RAM at imgsz 1600)")
    a = ap.parse_args()

    YOLO(a.model).train(
        data=os.path.expanduser(a.data), epochs=a.epochs, imgsz=a.imgsz, batch=a.batch,
        workers=a.workers, project=a.project, name=a.name, exist_ok=True, patience=20,
        device=a.device, cache=False if a.cache == "false" else a.cache,
        # drawings: flips/rotations are valid, colour jitter mostly is not
        fliplr=0.5, flipud=0.5, degrees=5.0, mosaic=1.0, hsv_h=0.0, hsv_s=0.2, hsv_v=0.3,
    )
    print(f"\nweights: {a.project}/{a.name}/weights/best.pt")


if __name__ == "__main__":
    main()
