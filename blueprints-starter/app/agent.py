"""Claude agent: question (any language) + file -> tool calls -> answer + evidence.

    export ANTHROPIC_API_KEY=...  BP_DATA_ROOT=/path/to/junction-dataset-preview
    python -m app.agent data/swiss_dwellings/site274_bldg500_floor1980.pdf "Wie viele Fenster?"
"""
from __future__ import annotations

import json
import os
import sys
import time

import anthropic

from app.tools import FUNCS, file_kind, schemas_for

MODEL = os.environ.get("BP_MODEL", "claude-haiku-5-5")
# USD per million tokens, for the cost read-out. Set to your model's real prices.
PRICE_IN = float(os.environ.get("BP_PRICE_IN", "1.0"))
PRICE_OUT = float(os.environ.get("BP_PRICE_OUT", "5.0"))

SYSTEM = """You answer questions about construction drawings and building models.
The question may be in any language; answer in the question's language.
Rules:
- Get every number from a tool. Never estimate or count by eye; use `calc` for any arithmetic.
- Prefer the most specific tool (e.g. swiss_area over summing yourself).
- If the data needed is not in the file, say so plainly instead of guessing.
- Finish by calling `final_answer` exactly once. In `evidence_from` list the ids of the
  tool calls whose results the answer is based on (they get highlighted for the user)."""

FINAL = {"name": "final_answer", "description": "Give the final answer.",
         "input_schema": {"type": "object", "properties": {
             "answer": {"description": "number for counts/quantities, otherwise short text"},
             "unit": {"type": "string", "description": "count, m2, m3, m, or empty"},
             "explanation": {"type": "string", "description": "one or two sentences: how it was derived"},
             "evidence_from": {"type": "array", "items": {"type": "string"}}},
             "required": ["answer", "explanation", "evidence_from"]}}

client = anthropic.Anthropic()


def ask(path: str, question: str, max_steps: int = 8) -> dict:
    kind = file_kind(path)
    tools = schemas_for(kind) + [FINAL]
    messages = [{"role": "user", "content": f"File: {path} (type: {kind})\nQuestion: {question}"}]
    evidence, trace, usage = {}, [], {"in": 0, "out": 0}
    t0 = time.time()
    for _ in range(max_steps):
        resp = client.messages.create(model=MODEL, max_tokens=1500, system=SYSTEM,
                                      tools=tools, messages=messages)
        usage["in"] += resp.usage.input_tokens
        usage["out"] += resp.usage.output_tokens
        messages.append({"role": "assistant", "content": resp.content})
        results = []
        for block in resp.content:
            if block.type != "tool_use":
                continue
            if block.name == "final_answer":
                out = dict(block.input)
                out["evidence"] = [e for i in out.pop("evidence_from", []) for e in evidence.get(i, [])]
                out.update(kind=kind, trace=trace, model=MODEL, seconds=round(time.time() - t0, 2),
                           tokens=usage, cost_usd=round(usage["in"] / 1e6 * PRICE_IN + usage["out"] / 1e6 * PRICE_OUT, 5))
                return out
            try:
                result, ev = FUNCS[block.name](path, **block.input) if block.name != "calc" \
                    else FUNCS["calc"](**block.input)
            except Exception as e:  # report tool errors back to the model
                result, ev = {"error": f"{type(e).__name__}: {e}"}, []
            evidence[block.id] = ev
            trace.append({"id": block.id, "tool": block.name, "input": block.input})
            if "__image__" in result:
                content = [{"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                                         "data": result["__image__"]}}]
            else:
                content = json.dumps(result, ensure_ascii=False, default=str)[:30000]
            results.append({"type": "tool_result", "tool_use_id": block.id, "content": content})
        if not results:
            break
        messages.append({"role": "user", "content": results})
    return {"answer": None, "explanation": "no answer within step limit", "evidence": [],
            "kind": kind, "trace": trace, "tokens": usage}


if __name__ == "__main__":
    print(json.dumps(ask(sys.argv[1], sys.argv[2]), indent=2, ensure_ascii=False, default=str)[:5000])
