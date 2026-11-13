"""Score the Swiss handler on the English Swiss questions (no LLM involved).

Usage: python eval/swiss_check.py <questions.jsonl> <dataset_root>
dataset_root is the folder that contains data/swiss_dwellings/...
"""
import json, os, re, sys
from collections import Counter
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from handlers.swiss import SwissPlan

qfile, root = sys.argv[1], sys.argv[2]
KIND = [("toilets", "toilet"), ("washbasins", "washbasin"), ("bathtubs", "bathtub"),
        ("showers", "shower"), ("windows", "window"), ("doors", "door"), ("apartments", "apartment")]

def answer(p, q):
    m = re.search(r"How many rooms labelled '(.+)' are there", q)
    if m: return p.count_rooms_named(m.group(1))["value"]
    m = re.search(r"net floor area of room (\S+) \('(.+)'\)", q)
    if m: return p.area_of_room(number=m.group(1))["value"]
    m = re.search(r"total net area in m² of all rooms labelled '(.+)' on", q)
    if m: return p.total_area_named(m.group(1))["value"]
    m = re.search(r"net floor area of apartment (\w+) in m²", q)
    if m: return p.apartment_area(m.group(1))["value"]
    if "all numbered indoor rooms" in q: return p.total_indoor_area()["value"]
    for word, kind in KIND:
        if q.startswith("How many " + word): return p.count(kind)["value"]
    return "UNPARSED"

ok, n, bad, cache = Counter(), Counter(), [], {}
for line in open(qfile, encoding="utf-8"):
    r = json.loads(line)
    if "swiss_dwellings" not in r["path"] or not r["question"].startswith(("How", "What")):
        continue
    path = os.path.join(root, r["path"])
    if not os.path.exists(os.path.splitext(path)[0] + ".dxf"):
        continue
    p = cache.setdefault(path, None) or cache.__setitem__(path, SwissPlan(path)) or cache[path]
    pred = answer(p, r["question"])
    key = re.sub(r"'.+?'|\d+\.\d+|apartment \w", "#", r["question"])[:60]
    n[key] += 1
    good = (pred == r["answer"]) if isinstance(r["answer"], int) else (
        isinstance(pred, (int, float)) and abs(pred - r["answer"]) <= 0.011)
    ok[key] += good
    if not good: bad.append((os.path.basename(r["path"]), r["question"][:90], r["answer"], pred))

for k in n: print(f"{ok[k]:4}/{n[k]:<4} {k}")
print("TOTAL", sum(ok.values()), "/", sum(n.values()))
for b in bad[:25]: print("  MISS", b)
