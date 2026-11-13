"""Schedule sheets (door/window/finish schedules) in vector PDFs.

Splits the page into table regions (pdfplumber.find_tables) and returns each
region's text plus its bounding box, so the LLM can read one table at a time
and the viewer can highlight the table/rows that the answer came from.
Counting/summing is done with the `calc` tool, never by the LLM's head.
"""
from __future__ import annotations

import pdfplumber


def table_regions(path: str, page_no: int = 0, min_chars: int = 40) -> list[dict]:
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no]
        regions = []
        page_area = page.width * page.height
        for i, t in enumerate(page.find_tables()):
            x0, y0, x1, y1 = t.bbox
            if (x1 - x0) * (y1 - y0) > 0.8 * page_area:   # sheet border, not a table
                continue
            text = page.crop(t.bbox).extract_text() or ""
            if len(text) >= min_chars:
                regions.append({"id": i, "bbox": list(t.bbox), "text": text,
                                "page_size": [page.width, page.height]})
        if not regions:  # no ruled tables: fall back to the whole page
            regions.append({"id": 0, "bbox": [0, 0, page.width, page.height],
                            "text": page.extract_text() or "", "page_size": [page.width, page.height]})
        return regions


def find_lines(path: str, contains: str, page_no: int = 0) -> list[dict]:
    """Every text line containing `contains` (case-insensitive), with its bbox."""
    with pdfplumber.open(path) as pdf:
        page = pdf.pages[page_no]
        out = []
        for ln in page.extract_text_lines():
            if contains.casefold() in ln["text"].casefold():
                out.append({"text": ln["text"], "bbox": [ln["x0"], ln["top"], ln["x1"], ln["bottom"]]})
        return out
