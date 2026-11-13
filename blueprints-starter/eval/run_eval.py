"""End-to-end evaluation of the agent on the answered questions.

    python -m eval.run_eval --questions questions.jsonl --n 200 --split dev
    python -m eval.run_eval --questions questions.jsonl --source cubicasa5k --n 100

Files (not questions) are split into dev/test, so the Finnish and English versions
of one question never land on both sides. Tune on dev; report test numbers.
"""
import argparse
import hashlib
import json
import random
import re
from collections import defaultdict

from app.agent import ask


def split_of(path):
    return "test" if int(hashlib.md5(path.encode()).hexdigest(), 16) % 5 == 0 else "dev"


def correct(pred, gold):
    if isinstance(gold, (int, float)):
        try:
            p = float(str(pred).replace(",", ".").split()[0])
        except (ValueError, IndexError):
            return False
        return p == gold if isinstance(gold, int) else abs(p - gold) <= max(0.011, 0.005 * abs(gold))
    return None   # free-text answers: judge separately (LLM-as-judge or by hand)


def template(q):
    return re.sub(r"'[^']*'|„[^“]*“|«[^»]*»|\d+(\.\d+)?", "#", q)[:70]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--questions", required=True)
    ap.add_argument("--n", type=int, default=100)
    ap.add_argument("--split", default="dev")
    ap.add_argument("--source", default=None, help="e.g. cubicasa5k, swiss_dwellings, ifc_models")
    ap.add_argument("--out", default="eval/results.jsonl")
    a = ap.parse_args()

    rows = [json.loads(l) for l in open(a.questions, encoding="utf-8")]
    rows = [r for r in rows if split_of(r["path"]) == a.split
            and (a.source is None or f"/{a.source}/" in r["path"])]
    random.seed(0)
    rows = random.sample(rows, min(a.n, len(rows)))

    by_src, by_tpl = defaultdict(lambda: [0, 0]), defaultdict(lambda: [0, 0])
    cost = 0.0
    with open(a.out, "w", encoding="utf-8") as f:
        for i, r in enumerate(rows):
            res = ask(r["path"], r["question"])
            ok = correct(res.get("answer"), r["answer"])
            cost += res.get("cost_usd", 0) or 0
            src = r["path"].split("/")[1]
            if ok is not None:
                by_src[src][0] += ok
                by_src[src][1] += 1
                by_tpl[template(r["question"])][0] += ok
                by_tpl[template(r["question"])][1] += 1
            f.write(json.dumps({**r, "pred": res.get("answer"), "ok": ok,
                                "trace": res.get("trace"), "cost": res.get("cost_usd")},
                               ensure_ascii=False, default=str) + "\n")
            print(f"[{i + 1}/{len(rows)}] {'OK ' if ok else 'BAD' if ok is False else '?? '} "
                  f"gold={r['answer']} pred={res.get('answer')} | {r['question'][:70]}")
    print("\nper source:")
    for k, (g, n) in sorted(by_src.items()):
        print(f"  {k:18} {g}/{n} = {g / n:.1%}")
    print("\nworst templates:")
    for k, (g, n) in sorted(by_tpl.items(), key=lambda kv: kv[1][0] / kv[1][1])[:15]:
        print(f"  {g}/{n}  {k}")
    print(f"\ntotal cost ${cost:.3f}  (${cost / max(1, len(rows)):.5f} per question)")


if __name__ == "__main__":
    main()
