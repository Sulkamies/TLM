"""Score cached detector+OCR output against the CubiCasa questions (no LLM, seconds).

    python eval/cubicasa_check.py --questions questions.jsonl --cache cache/vision_v2
    python eval/cubicasa_check.py --questions questions.jsonl --cache cache/vision_v2 --tune --errors
    python eval/cubicasa_check.py ... --settings eval/thresholds_vision_v2.json   # score saved settings

--tune searches, on the DEV images only, per-class confidence thresholds, an extra
duplicate filter per class, and the best counting strategy per question type; it
saves them to eval/thresholds_<cache>.json and reports held-out TEST accuracy.
The app uses the same rules (handlers/raster_count.py) with that file via BP_THRESHOLDS.
"""
import argparse
import hashlib
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from handlers.raster_count import CLASSES_USED, DEFAULT_STRATEGY, DEFAULT_THR, STRATEGIES, TEMPLATES  # noqa: E402

GRID = [round(0.05 * i, 2) for i in range(1, 17)]          # 0.05 .. 0.80
IOU_GRID = [1.0, 0.7, 0.6, 0.5, 0.4, 0.3]                  # 1.0 = no extra duplicate filter
IOU_CLASSES = {"window", "door", "toilet", "sink", "shower", "bathtub"}


def is_test(path):
    return int(hashlib.md5(os.path.basename(path).encode()).hexdigest(), 16) % 4 == 0   # 25% test


def load(qfile, cache):
    items, missing = [], set()
    for line in open(qfile, encoding="utf-8"):
        r = json.loads(line)
        if "cubicasa5k" not in r["path"]:
            continue
        tpl = next((n for n, p in TEMPLATES if re.match(p, r["question"])), None)
        if tpl is None:      # non-English duplicates: same image + same answer as the English one
            continue
        f = os.path.join(cache, os.path.basename(r["path"]) + ".json")
        if not os.path.exists(f):
            missing.add(f)
            continue
        items.append((tpl, json.load(open(f)), int(r["answer"]), is_test(r["path"]), os.path.basename(r["path"])))
    if missing:
        print(f"warning: {len(missing)} images have no cache file (e.g. {next(iter(missing))})")
    return items


def score(items, tpl, strat, thr, split):
    rows = [(d, a) for t, d, a, te, _ in items if t == tpl and te == (split == "test")]
    fn = STRATEGIES[tpl][strat]
    return sum(fn(d, thr)[0] == a for d, a in rows), len(rows)


def tune(items, thr, choice):
    for tpl, _ in TEMPLATES:
        best = (-1, None, None)
        for strat in STRATEGIES[tpl]:
            classes = [] if strat == "ocr" else CLASSES_USED[tpl]
            local = dict(thr)
            for _ in range(2):   # coordinate search, two passes
                for c in classes:
                    local[c] = max(GRID, key=lambda v: (score(items, tpl, strat, {**local, c: v}, "dev")[0],
                                                        -abs(v - 0.35)))
                    if c in IOU_CLASSES:
                        local[c + "_iou"] = max(IOU_GRID, key=lambda v: (
                            score(items, tpl, strat, {**local, c + "_iou": v}, "dev")[0], v))
            ok, _ = score(items, tpl, strat, local, "dev")
            if ok > best[0]:
                keys = classes + [c + "_iou" for c in classes if c in IOU_CLASSES]
                best = (ok, strat, {k: local[k] for k in keys if k in local})
        choice[tpl] = best[1]
        # only adopt thresholds for classes this question type owns (shared classes keep the
        # value tuned by their own question type, e.g. 'toilet' by the toilet question)
        own = {"wc_rooms": ["room_bath"], "bathrooms": ["room_bath"]}.get(tpl)
        for k, v in best[2].items():
            if own is None or k.split("_iou")[0] in own:
                thr[k] = v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--cache", required=True)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--settings", "--thresholds", dest="settings", help="JSON from a previous --tune run")
    ap.add_argument("--errors", action="store_true",
                    help="per question type: how far off the wrong answers are (prediction - answer)")
    ap.add_argument("--worst", type=int, default=0, help="list N images with the most wrong answers")
    a = ap.parse_args()
    items = load(a.questions, a.cache)
    print(f"{len(items)} English CubiCasa questions with cache "
          f"({sum(1 for i in items if not i[3])} dev / {sum(1 for i in items if i[3])} test)\n")

    thr, choice = dict(DEFAULT_THR), dict(DEFAULT_STRATEGY)
    if a.settings:
        saved = json.load(open(a.settings))
        thr.update(saved["thresholds"])
        choice.update(saved["strategies"])
    if a.tune:
        tune(items, thr, choice)
        out = os.path.join("eval", f"thresholds_{os.path.basename(os.path.normpath(a.cache))}.json")
        os.makedirs("eval", exist_ok=True)
        json.dump({"thresholds": thr, "strategies": choice}, open(out, "w"), indent=2)
        print(f"saved tuned settings -> {out}\n")

    tot = {"dev": [0, 0], "test": [0, 0]}
    print(f"{'question type':12} {'strategy':18} {'dev':>12} {'test':>12}")
    for tpl, _ in TEMPLATES:
        cells = []
        for split in ("dev", "test"):
            ok, n = score(items, tpl, choice[tpl], thr, split)
            tot[split][0] += ok
            tot[split][1] += n
            cells.append(f"{ok}/{n} {ok / n:.0%}" if n else "-")
        print(f"{tpl:12} {choice[tpl]:18} {cells[0]:>12} {cells[1]:>12}")
    for split in ("dev", "test"):
        ok, n = tot[split]
        print(f"TOTAL {split}: {ok}/{n} = {ok / max(n, 1):.1%}")
    print("\nsettings:", json.dumps({k: thr[k] for k in sorted(thr)}))

    if a.errors:
        print("\nError distribution (prediction - answer) over ALL images, wrong answers only:")
        for tpl, _ in TEMPLATES:
            fn = STRATEGIES[tpl][choice[tpl]]
            diffs = defaultdict(int)
            for t, d, ans, _te, _f in items:
                if t == tpl:
                    diff = fn(d, thr)[0] - ans
                    if diff:
                        diffs[diff] += 1
            if diffs:
                over = sum(v for k, v in diffs.items() if k > 0)
                under = sum(v for k, v in diffs.items() if k < 0)
                spread = ", ".join(f"{k:+d}:{v}" for k, v in sorted(diffs.items()))
                print(f"  {tpl:12} too high {over:3}  too low {under:3}   [{spread}]")
    if a.worst:
        bad = defaultdict(list)
        for t, d, ans, _te, f in items:
            p = STRATEGIES[t][choice[t]](d, thr)[0]
            if p != ans:
                bad[f].append(f"{t} {p} vs {ans}")
        print(f"\nImages with the most wrong answers (prediction vs answer):")
        for f, errs in sorted(bad.items(), key=lambda kv: -len(kv[1]))[:a.worst]:
            print(f"  {f}: " + "; ".join(errs))


if __name__ == "__main__":
    main()
