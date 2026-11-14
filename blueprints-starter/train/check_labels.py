"""Draw YOLO labels at full resolution on a few plans, to check alignment.

    python train/check_labels.py --yolo ~/yolo --src ~/data --n 3 --out ~/check

Also prints, for each plan, the SVG root attributes and the image sizes, which
shows whether SVG coordinates and image pixels use the same scale.
"""
import argparse
import glob
import os
import random
from xml.etree import ElementTree as ET

from PIL import Image, ImageDraw

COLORS = ["#e6194b", "#3cb44b", "#ffe119", "#4363d8", "#f58231", "#911eb4", "#46f0f0",
          "#f032e6", "#bcf60c", "#fabebe", "#008080", "#e6beff", "#9a6324"]


def names(yolo):
    out = {}
    for line in open(os.path.join(yolo, "data.yaml")):
        line = line.strip()
        if line[:1].isdigit() and ":" in line:
            i, n = line.split(":", 1)
            out[int(i)] = n.strip()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yolo", default=os.path.expanduser("~/yolo"))
    ap.add_argument("--src", default=os.path.expanduser("~/data"))
    ap.add_argument("--n", type=int, default=3)
    ap.add_argument("--out", default=os.path.expanduser("~/check"))
    ap.add_argument("--small-only", action="store_true", help="draw only symbols (no rooms/floors)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    nm = names(a.yolo)
    imgs = sorted(glob.glob(os.path.join(a.yolo, "images", "val", "*.png")))
    random.seed(1)
    for img_path in random.sample(imgs, min(a.n, len(imgs))):
        stem = os.path.splitext(os.path.basename(img_path))[0]
        style, pid = stem.rsplit("_", 1)
        src_dirs = glob.glob(os.path.join(a.src, "**", style, pid), recursive=True)
        print(f"\n== {stem}")
        if src_dirs:
            d = src_dirs[0]
            root = ET.parse(os.path.join(d, "model.svg")).getroot()
            print("  svg root:", {k: v for k, v in root.attrib.items() if k in ("width", "height", "viewBox", "transform")})
            for f in ("F1_scaled.png", "F1_original.png"):
                p = os.path.join(d, f)
                if os.path.exists(p):
                    print(f"  {f}: {Image.open(p).size}")
        im = Image.open(img_path).convert("RGB")
        W, H = im.size
        dr = ImageDraw.Draw(im)
        lab = os.path.join(a.yolo, "labels", "val", stem + ".txt")
        n = 0
        for line in open(lab):
            c, x, y, w, h = line.split()
            c = int(c)
            if a.small_only and nm.get(c, "").startswith(("room_", "floor")):
                continue
            x, y, w, h = float(x) * W, float(y) * H, float(w) * W, float(h) * H
            col = COLORS[c % len(COLORS)]
            dr.rectangle([x - w / 2, y - h / 2, x + w / 2, y + h / 2], outline=col, width=2)
            dr.text((x - w / 2 + 2, y - h / 2 + 1), nm.get(c, str(c)), fill=col)
            n += 1
        out = os.path.join(a.out, stem + ".png")
        im.save(out)
        print(f"  image used for training: {W}x{H}, {n} boxes drawn -> {out}")


if __name__ == "__main__":
    main()
