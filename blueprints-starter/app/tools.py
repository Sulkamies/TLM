"""Tool layer between Claude and the handlers.

Each tool returns (result_for_llm, evidence_for_viewer). Geometry stays out of
the LLM context (cheaper, and the LLM doesn't need it); the viewer gets it.
"""
from __future__ import annotations

import ast
import base64
import operator as op
import os

from handlers.swiss import SwissPlan

DATA_ROOT = os.environ.get("BP_DATA_ROOT", ".")   # folder that contains data/...


def resolve(path: str) -> str:
    return path if os.path.isabs(path) else os.path.join(DATA_ROOT, path)


def file_kind(path: str) -> str:
    p = resolve(path)
    base, ext = os.path.splitext(p)
    ext = ext.lower()
    if ext == ".ifc":
        return "ifc"
    if ext == ".pdf" and os.path.exists(base + ".dxf"):
        return "swiss"
    if ext == ".pdf" and "_plan-" in os.path.basename(p) and os.path.exists(base + ".svg"):
        return "ifc_plan"
    if ext == ".pdf":
        return "schedule"
    if ext in (".png", ".jpg", ".jpeg"):
        return "raster"
    return "unknown"


# ---------------- safe arithmetic for counting/summing ----------------
_OPS = {ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul, ast.Div: op.truediv,
        ast.USub: op.neg, ast.Pow: op.pow}


def _eval(node):
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp):
        return _OPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp):
        return _OPS[type(node.op)](_eval(node.operand))
    if isinstance(node, ast.Call) and getattr(node.func, "id", "") == "sum":
        return sum(_eval(a) for a in node.args[0].elts)
    raise ValueError("only numbers, + - * / ** and sum([...]) are allowed")


def calc(expression: str):
    return {"value": _eval(ast.parse(expression, mode="eval").body)}, []


# ---------------- per-format tools ----------------
def _swiss(path):
    return SwissPlan(resolve(path))


def swiss_summary(path):
    return _swiss(path).summary(), []


def swiss_count(path, kind):
    r = _swiss(path).count(kind)
    return {"value": r["value"]}, r["evidence"]


def swiss_rooms_named(path, name):
    r = _swiss(path).count_rooms_named(name)
    return {"count": r["value"], "rooms": [e["label"] for e in r["evidence"]],
            "total_area_m2": _swiss(path).total_area_named(name)["value"]}, r["evidence"]


def swiss_area(path, what, value=None):
    p = _swiss(path)
    r = {"room": lambda: p.area_of_room(number=value),
         "apartment": lambda: p.apartment_area(value),
         "indoor_total": p.total_indoor_area}[what]()
    return {"value": r["value"], "rooms": [(e["label"], e["area"]) for e in r["evidence"]]}, r["evidence"]


def _ifc(path):
    from handlers.ifc import open_model
    return open_model(resolve(path))


def ifc_overview(path):
    return _ifc(path).overview(), []


def ifc_spaces(path, storey=None):
    rows = _ifc(path).spaces(storey)
    return {"spaces": rows}, [{"guid": r["guid"]} for r in rows]


def ifc_space_area(path, label, storey=None):
    r = _ifc(path).space_area(label, storey)
    return {"value": r["value"], "matches": r["result"]}, r["evidence"]


def ifc_count(path, ifc_class, storey=None):
    r = _ifc(path).count(ifc_class, storey)
    return {"value": r["value"]}, r["evidence"]


def ifc_quantity_sum(path, ifc_class, quantity, storey=None):
    r = _ifc(path).quantity_sum(ifc_class, quantity, storey)
    ev = r.pop("evidence")
    return r, ev


def ifc_elements(path, ifc_class, storey=None, limit=100):
    r = _ifc(path).elements(ifc_class, storey, limit)
    return {"elements": r["result"]}, r["evidence"]


def schedule_tables(path):
    from handlers.schedules import table_regions
    regs = table_regions(resolve(path))
    return {"tables": [{"id": r["id"], "text": r["text"][:6000]} for r in regs]}, \
           [{"pdf_bbox": r["bbox"], "page_size": r["page_size"], "label": f"table {r['id']}"} for r in regs]


def schedule_find(path, contains):
    from handlers.schedules import find_lines
    import pdfplumber
    with pdfplumber.open(resolve(path)) as pdf:
        size = [pdf.pages[0].width, pdf.pages[0].height]
    rows = find_lines(resolve(path), contains)
    return {"lines": [r["text"] for r in rows]}, \
           [{"pdf_bbox": r["bbox"], "page_size": size, "label": r["text"][:40]} for r in rows]


def _raster(path):
    from handlers.raster import RasterPlan
    return RasterPlan(resolve(path))


def plan_summary(path):
    return _raster(path).summary(), []


def plan_count(path, kind):
    r = _raster(path).count(kind)
    return {"value": r["value"]}, r["evidence"]


def plan_room_labels(path, category):
    r = _raster(path).room_labels(category)
    return {"value": r["value"], "labels": [e["label"] for e in r["evidence"]]}, r["evidence"]


def plan_storeys(path):
    r = _raster(path).storeys()
    return {"value": r["value"], "note": r.get("note")}, r["evidence"]


def plan_text(path):
    return {"ocr": _raster(path).text()}, []


def look_at_region(path, x0, y0, x1, y1):
    """Vision fallback: returns the crop as an image for Claude to inspect."""
    png = _raster(path).crop_png([x0, y0, x1, y1])
    return {"__image__": base64.b64encode(png).decode()}, [{"box": [x0, y0, x1, y1], "label": "inspected"}]


FUNCS = {f.__name__: f for f in [calc, swiss_summary, swiss_count, swiss_rooms_named, swiss_area,
                                 ifc_overview, ifc_spaces, ifc_space_area, ifc_count, ifc_quantity_sum,
                                 ifc_elements, schedule_tables, schedule_find, plan_summary, plan_count,
                                 plan_room_labels, plan_storeys, plan_text, look_at_region]}


def S(name, desc, props=None, required=None):
    return {"name": name, "description": desc,
            "input_schema": {"type": "object", "properties": props or {}, "required": required or []}}


STOREY = {"storey": {"type": "string", "description": "storey name exactly as in the model, optional"}}
SCHEMAS = {
    "common": [
        S("calc", "Exact arithmetic. Use for every sum/count you compute yourself, e.g. 'sum([256,1,21])'.",
          {"expression": {"type": "string"}}, ["expression"]),
    ],
    "swiss": [
        S("swiss_summary", "All numbered rooms (number, name, net area m²), apartments and their rooms, and counts of doors/windows/fixtures."),
        S("swiss_count", "Count drawn items.", {"kind": {"type": "string", "enum": [
            "door", "window", "toilet", "washbasin", "bathtub", "shower", "apartment"]}}, ["kind"]),
        S("swiss_rooms_named", "Rooms whose label equals `name` exactly (e.g. 'Zimmer', 'Cucina'): count and total area.",
          {"name": {"type": "string"}}, ["name"]),
        S("swiss_area", "Net floor area. what=room (value=room number like '0.05'), apartment (value=letter like 'A'; excludes balconies etc.), indoor_total (all numbered indoor rooms).",
          {"what": {"type": "string", "enum": ["room", "apartment", "indoor_total"]}, "value": {"type": "string"}}, ["what"]),
    ],
    "ifc": [
        S("ifc_overview", "Schema, authoring software, building info, storeys (names, elevations) and element counts."),
        S("ifc_spaces", "Spaces/rooms with names, storey and net/gross floor area.", STOREY),
        S("ifc_space_area", "Net floor area of one room given as in the question, e.g. 'TUALETTRUUM (55-3)'.",
          {"label": {"type": "string"}, **STOREY}, ["label"]),
        S("ifc_count", "Count elements of an IFC class (IfcDoor, IfcWindow, IfcWall, IfcSpace, IfcColumn, IfcBeam, IfcStair, IfcSlab...).",
          {"ifc_class": {"type": "string"}, **STOREY}, ["ifc_class"]),
        S("ifc_quantity_sum", "Sum a base quantity over elements, e.g. IfcSlab NetVolume, IfcWall Length / NetSideArea / NetVolume.",
          {"ifc_class": {"type": "string"}, "quantity": {"type": "string"}, **STOREY}, ["ifc_class", "quantity"]),
        S("ifc_elements", "List elements of a class with type names, sizes and property sets (for type/width/fire-rating questions).",
          {"ifc_class": {"type": "string"}, "limit": {"type": "integer"}, **STOREY}, ["ifc_class"]),
    ],
    "schedule": [
        S("schedule_tables", "Text of each table on the sheet (door/window/finish schedules), one table per entry."),
        S("schedule_find", "All text lines containing a string (case-insensitive).",
          {"contains": {"type": "string"}}, ["contains"]),
    ],
    "raster": [
        S("plan_summary", "Detector counts per class, Finnish room-label counts per category, storey estimate."),
        S("plan_count", "Count detected symbols.", {"kind": {"type": "string", "enum": [
            "window", "door", "toilet", "sink", "bathtub", "shower", "sauna_bench"]}}, ["kind"]),
        S("plan_room_labels", "Count rooms by their written label (MH=bedroom, KH/PH/KPH=bathroom, WC, K/KK/AVOK=kitchen, S=sauna, PARVEKE=balcony).",
          {"category": {"type": "string", "enum": ["bedroom", "bathroom", "wc", "kitchen", "sauna", "balcony", "living"]}}, ["category"]),
        S("plan_storeys", "Number of storeys drawn on the sheet."),
        S("plan_text", "All OCR text on the plan."),
        S("look_at_region", "Look at a region of the image yourself (pixel box) when the tools disagree or are unsure.",
          {"x0": {"type": "number"}, "y0": {"type": "number"}, "x1": {"type": "number"}, "y1": {"type": "number"}},
          ["x0", "y0", "x1", "y1"]),
    ],
}
SCHEMAS["ifc_plan"] = SCHEMAS["ifc"]


def schemas_for(kind):
    return SCHEMAS["common"] + SCHEMAS.get(kind, [])
