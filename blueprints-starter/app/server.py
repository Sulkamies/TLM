"""Web app: ask a question about a file, get the answer with highlighted evidence.

    pip install -r requirements.txt
    export ANTHROPIC_API_KEY=... BP_DATA_ROOT=/path/to/junction-dataset-preview
    uvicorn app.server:app --reload --port 8000      # open http://localhost:8000
"""
from __future__ import annotations

import io
import os
import re

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, Response
from pydantic import BaseModel

from app.agent import ask
from app.tools import DATA_ROOT, file_kind, resolve

app = FastAPI(title="Make Blueprints Talk")
HERE = os.path.dirname(__file__)


class Ask(BaseModel):
    path: str
    question: str


@app.get("/")
def index():
    return HTMLResponse(open(os.path.join(HERE, "static", "index.html"), encoding="utf-8").read())


@app.get("/api/files")
def files():
    out = []
    for sub in ("cubicasa5k", "swiss_dwellings", "ifc_models", "ifc_bench", "opening_design"):
        root = os.path.join(DATA_ROOT, "data", sub)
        for dp, _, fs in os.walk(root):
            for f in fs:
                if f.lower().endswith((".png", ".pdf", ".ifc")):
                    rel = os.path.relpath(os.path.join(dp, f), DATA_ROOT).replace(os.sep, "/")
                    if file_kind(rel) != "unknown":
                        out.append(rel)
    return sorted(out)


@app.post("/api/ask")
def api_ask(q: Ask):
    return ask(q.path, q.question)


@app.get("/api/view")
def view(path: str):
    """What the viewer should draw. Evidence coordinates match each kind:
    raster: image pixels | swiss: DXF metres | ifc_plan: guid | schedule: PDF points."""
    kind = file_kind(path)
    p = resolve(path)
    if kind == "swiss":
        from handlers.swiss import SwissPlan, render_svg
        return {"kind": "svg", "svg": render_svg(SwissPlan(p))}
    if kind == "ifc_plan":
        return {"kind": "svg", "svg": open(os.path.splitext(p)[0] + ".svg", encoding="utf-8").read()}
    if kind == "raster":
        from PIL import Image
        w, h = Image.open(p).size
        return {"kind": "image", "url": f"/api/raw?path={path}", "width": w, "height": h, "scale": 1}
    if kind == "schedule":
        import pypdfium2 as pdfium
        page = pdfium.PdfDocument(p)[0]
        w, h = page.get_size()
        return {"kind": "image", "url": f"/api/pdfpng?path={path}", "width": w * 2, "height": h * 2, "scale": 2}
    return {"kind": "none"}


@app.get("/api/raw")
def raw(path: str):
    p = resolve(path)
    if not os.path.abspath(p).startswith(os.path.abspath(DATA_ROOT)):
        raise HTTPException(403)
    return FileResponse(p)


@app.get("/api/pdfpng")
def pdfpng(path: str):
    import pypdfium2 as pdfium
    img = pdfium.PdfDocument(resolve(path))[0].render(scale=2).to_pil()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return Response(buf.getvalue(), media_type="image/png")
