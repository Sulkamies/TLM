"""Convert CubiCasa5K (model.svg per plan) to YOLO detection format.

    python cubicasa_to_yolo.py --src /data/cubicasa5k --out /data/yolo \
        --exclude /data/exclude_ids.txt            # our 241 question images
    python cubicasa_to_yolo.py --src ... --discover   # print every class name found

Each plan folder looks like  <style>/<id>/{F1_original.png, F1_scaled.png, model.svg}.
Check with --discover which SVG class names exist and adjust CLASS_RULES below:
the first rule whose keyword appears in an element's class string wins.
"""
import argparse
import os
import random
import re
import shutil
from collections import Counter
from xml.etree import ElementTree as ET

from PIL import Image

# (target class, keywords to look for in the lowercased SVG class attribute)
# Fixtures/openings answer the count questions; room boxes are a useful second
# signal next to OCR of the room labels; "floor" boxes answer the storey count.
CLASS_RULES = [
    ("window", ["window"]),
    ("door", ["door"]),
    ("toilet", ["toilet", "wc"]),
    ("sink", ["sink", "washbasin", "basin"]),
    ("bathtub", ["bathtub"]),
    ("shower", ["shower"]),
    ("sauna_bench", ["saunabench", "sauna bench", "saunabenchhigh", "saunabenchlow"]),
    ("room_kitchen", ["space kitchen"]),
    ("room_bedroom", ["space bedroom"]),
    ("room_bath", ["space bath"]),
    ("room_sauna", ["space sauna"]),
    ("room_balcony", ["space outdoor", "space balcony"]),
]
NAMES = [c for c, _ in CLASS_RULES] + ["floor"]
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def strip_ns(tag):
    return tag.split("}")[-1]


def poly_points(el):
    pts = []
    for sub in el.iter():
        t = strip_ns(sub.tag)
        if t in ("polygon", "polyline") and sub.get("points"):
            v = [float(x) for x in NUM.findall(sub.get("points"))]
            pts += list(zip(v[0::2], v[1::2]))
        elif t == "rect":
            x, y = float(sub.get("x", 0)), float(sub.get("y", 0))
            w, h = float(sub.get("width", 0)), float(sub.get("height", 0))
            pts += [(x, y), (x + w, y + h)]
    return pts


def classify(cls_attr):
    """Token-based: 'Space Outdoor' must not match 'door'; 'Space Toilet' is a room, not a fixture."""
    tokens = [t for t in re.split(r"[\s_\-]+", cls_attr.lower()) if t]
    is_space = "space" in tokens
    for name, keys in CLASS_RULES:
        if name.startswith("room_") != is_space:
            continue
        for k in keys:
            ktoks = k.split()
            if all(any(t == kt or t.startswith(kt) for t in tokens) for kt in ktoks):
                return name
    return None


def plan_boxes(svg_path):
    root = ET.parse(svg_path).getroot()
    boxes = []
    for el in root.iter():
        if strip_ns(el.tag) != "g":
            continue
        cls_attr = (el.get("class") or "") + " " + (el.get("id") or "")
        if cls_attr.strip().lower().startswith("floor"):
            name = "floor"
        else:
            name = classify(cls_attr)
        if not name:
            continue
        pts = poly_points(el)
        if len(pts) >= 2:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            boxes.append((name, min(xs), min(ys), max(xs), max(ys)))
    w = float(NUM.findall(root.get("width", "0"))[0]) if root.get("width") else None
    h = float(NUM.findall(root.get("height", "0"))[0]) if root.get("height") else None
    return boxes, (w, h)


def dedupe(boxes):
    """Nested <g> elements can match the same rule twice: keep one per identical box."""
    seen, out = set(), []
    for b in boxes:
        k = (b[0],) + tuple(round(v, 1) for v in b[1:])
        if k not in seen:
            seen.add(k)
            out.append(b)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", default="/data/yolo")
    ap.add_argument("--exclude", default=None, help="file with ids like high_quality_architectural/1000")
    ap.add_argument("--image", default="F1_scaled.png")
    ap.add_argument("--val", type=float, default=0.1)
    ap.add_argument("--discover", action="store_true")
    a = ap.parse_args()

    plans = []
    for dirpath, _, files in os.walk(a.src):
        if "model.svg" in files and a.image in files:
            plans.append(dirpath)
    print(f"found {len(plans)} plans")

    if a.discover:
        c = Counter()
        for p in plans[:300]:
            for el in ET.parse(os.path.join(p, "model.svg")).getroot().iter():
                if strip_ns(el.tag) == "g" and el.get("class"):
                    c[el.get("class")] += 1
        for k, v in c.most_common(150):
            print(f"{v:6}  {k}   -> {classify(k)}")
        return

    excl = set()
    if a.exclude and os.path.exists(a.exclude):
        excl = {l.strip() for l in open(a.exclude) if l.strip()}
    random.seed(0)
    stats = Counter()
    for p in plans:
        rel = os.path.relpath(p, a.src).replace(os.sep, "/")
        key = "/".join(rel.split("/")[-2:])            # e.g. high_quality_architectural/1000
        if key in excl:
            stats["excluded"] += 1
            continue
        split = "val" if random.random() < a.val else "train"
        img_path = os.path.join(p, a.image)
        W, H = Image.open(img_path).size
        boxes, (sw, sh) = plan_boxes(os.path.join(p, "model.svg"))
        # SVG coordinates may be in original-image pixels: rescale to the chosen image
        sx = W / sw if sw else 1.0
        sy = H / sh if sh else 1.0
        stem = key.replace("/", "_")
        os.makedirs(f"{a.out}/images/{split}", exist_ok=True)
        os.makedirs(f"{a.out}/labels/{split}", exist_ok=True)
        shutil.copy(img_path, f"{a.out}/images/{split}/{stem}.png")
        with open(f"{a.out}/labels/{split}/{stem}.txt", "w") as f:
            for name, x0, y0, x1, y1 in dedupe(boxes):
                x0, x1 = max(0, x0 * sx), min(W, x1 * sx)
                y0, y1 = max(0, y0 * sy), min(H, y1 * sy)
                if x1 - x0 < 2 or y1 - y0 < 2:
                    continue
                f.write(f"{NAMES.index(name)} {(x0 + x1) / 2 / W:.6f} {(y0 + y1) / 2 / H:.6f} "
                        f"{(x1 - x0) / W:.6f} {(y1 - y0) / H:.6f}\n")
                stats[name] += 1
        stats[split] += 1
    with open(f"{a.out}/data.yaml", "w") as f:
        f.write(f"path: {a.out}\ntrain: images/train\nval: images/val\nnames:\n")
        for i, n in enumerate(NAMES):
            f.write(f"  {i}: {n}\n")
    print(dict(stats))


if __name__ == "__main__":
    main()
