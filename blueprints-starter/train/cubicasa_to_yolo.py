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
    ("door", ["door"]),                       # only top-level "Door ..." (see classify)
    ("toilet", ["toilet"]),
    ("sink", ["sink", "doublesink", "roundsink", "sidesink", "cornersink"]),
    ("bathtub", ["bathtub"]),
    ("shower", ["shower"]),                   # Shower, ShowerCab, ShowerPlatform (not ShowerScreen*)
    ("sauna_bench", ["saunabench"]),
    ("room_balcony", ["space outdoor"]),      # before kitchen: "Space Outdoor Kitchen" is outdoors
    ("room_kitchen", ["space kitchen"]),
    ("room_bedroom", ["space bedroom"]),
    ("room_bath", ["space bath"]),
    ("room_sauna", ["space sauna"]),
    ("opening", []),                           # 'Door None ...' = doorway without a door leaf (never counted)
]
# Outdoor spaces the questions do NOT count as balconies
NOT_BALCONY = {"garden", "porch", "patio", "terrace", "veranda", "pergola", "coveredarea", "kitchen"}
NAMES = [c for c, _ in CLASS_RULES] + ["floor"]
NUM = re.compile(r"-?\d+(?:\.\d+)?")


def strip_ns(tag):
    return tag.split("}")[-1]


def _parse_transform(t):
    """SVG transform attribute -> 2x3 affine (a, b, c, d, e, f)."""
    M = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
    for name, args in re.findall(r"(matrix|translate|scale|rotate)\s*\(([^)]*)\)", t or ""):
        v = [float(x) for x in NUM.findall(args)]
        if name == "matrix" and len(v) == 6:
            N = tuple(v)
        elif name == "translate":
            N = (1, 0, 0, 1, v[0], v[1] if len(v) > 1 else 0)
        elif name == "scale":
            N = (v[0], 0, 0, v[1] if len(v) > 1 else v[0], 0, 0)
        elif name == "rotate":
            import math
            r = math.radians(v[0])
            cx, cy = (v[1], v[2]) if len(v) == 3 else (0, 0)
            c, s_ = math.cos(r), math.sin(r)
            N = (c, s_, -s_, c, cx - c * cx + s_ * cy, cy - s_ * cx - c * cy)
        else:
            continue
        M = _mul(M, N)
    return M


def _mul(A, B):
    a, b, c, d, e, f = A
    a2, b2, c2, d2, e2, f2 = B
    return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2,
            a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def _apply(M, x, y):
    a, b, c, d, e, f = M
    return (a * x + c * y + e, b * x + d * y + f)


def poly_points(el, M):
    """All polygon/polyline/rect points under el, with transforms applied."""
    pts = []
    M = _mul(M, _parse_transform(el.get("transform")))
    t = strip_ns(el.tag)
    if t in ("polygon", "polyline") and el.get("points"):
        v = [float(x) for x in NUM.findall(el.get("points"))]
        pts += [_apply(M, x, y) for x, y in zip(v[0::2], v[1::2])]
    elif t == "rect":
        x, y = float(el.get("x", 0)), float(el.get("y", 0))
        w, h = float(el.get("width", 0)), float(el.get("height", 0))
        pts += [_apply(M, x, y), _apply(M, x + w, y + h), _apply(M, x + w, y), _apply(M, x, y + h)]
    for ch in el:
        pts += poly_points(ch, M)
    return pts


def classify(cls_attr):
    """Map an SVG class attribute to a target class (or None = ignore).

    Token-based, so 'Space Outdoor' never matches 'door'. Special cases from the
    CubiCasa label list:
      - 'Doors' is a container around all doors -> ignored
      - 'Door None ...' is a doorway without a door leaf -> 'opening' (learnt, never counted)
      - 'Floor' is one storey; 'FloorsCompose' / 'Floorplan ...' wrap several -> only 'Floor'
    """
    tokens = [t for t in re.split(r"[\s_\-]+", cls_attr.lower()) if t]
    if not tokens:
        return None
    if tokens == ["floor"]:
        return "floor"
    if tokens[0] in ("door", "window"):
        if tokens[0] == "door" and len(tokens) > 1 and tokens[1] == "none":
            return "opening"   # learnt separately so the model stops counting doorways as doors
        return tokens[0]
    is_space = tokens[0] == "space"
    for name, keys in CLASS_RULES:
        if name in ("door", "window") or name.startswith("room_") != is_space:
            continue
        for k in keys:
            ktoks = k.split()
            if all(any(t == kt or t.startswith(kt) for t in tokens) for kt in ktoks):
                if name == "room_balcony" and NOT_BALCONY & set(tokens):
                    return None
                if name == "shower" and any(t.startswith("showerscreen") for t in tokens):
                    return None   # glass screen beside a shower, not a second shower
                return name
    return None


def plan_boxes(svg_path):
    root = ET.parse(svg_path).getroot()
    boxes = []
    I = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)

    def walk(el, M):
        M2 = _mul(M, _parse_transform(el.get("transform")))
        if strip_ns(el.tag) == "g" and el.get("class"):
            name = classify(el.get("class"))
            if name:
                pts = []
                for ch in el:
                    pts += poly_points(ch, M2)
                if len(pts) >= 2:
                    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                    boxes.append((name, min(xs), min(ys), max(xs), max(ys)))
        for ch in el:
            walk(ch, M2)

    walk(root, I)
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
    ap.add_argument("--svg-scale", choices=["none", "fit"], default="none",
                    help="none: SVG coordinates are F1_scaled.png pixels (CubiCasa's own loader); "
                         "fit: stretch SVG width/height onto the image (WRONG for CubiCasa, kept for other data)")
    a = ap.parse_args()

    plans = []
    for dirpath, _, files in os.walk(a.src):
        if "model.svg" in files and a.image in files:
            plans.append(dirpath)
    plans.sort()   # fixed order -> the same train/val split on every machine
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
        # CubiCasa: SVG coordinates are already pixels of F1_scaled.png (the image has
        # extra margin, so stretching width/height onto it shifts every box).
        if a.svg_scale == "fit":
            sx = W / sw if sw else 1.0
            sy = H / sh if sh else 1.0
        else:
            sx = sy = 1.0
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
