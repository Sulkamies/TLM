"""The browser UI and the shared API contract (docs/API.md) stay in sync with api/ask.py."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from blueprint_qa.api import server
from blueprint_qa.api.ask import AskAnswer, AskError, EvidenceBox

ROOT = Path(__file__).resolve().parents[3]
PAGE = (ROOT / "src" / "blueprint_qa" / "api" / "web" / "index.html").read_text(encoding="utf-8")
SPEC = (ROOT / "docs" / "API.md").read_text(encoding="utf-8")

# Fields the Android app reads (android-app/.../Recognizer.kt, HttpRecognizer, at's branch e760e58).
ANDROID_READS = {"answer", "unit", "type", "working", "evidence", "error"}
ANDROID_EVIDENCE = {"label", "x", "y", "w", "h"}

ANSWER_FIELDS = set(AskAnswer.model_fields)
ERROR_FIELDS = set(AskError.model_fields)
BOX_FIELDS = set(EvidenceBox.model_fields)


@pytest.fixture
def client() -> TestClient:
    return TestClient(server.create_app())


def test_the_page_is_served_at_the_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/html")
    assert "<title>Blueprint Q&amp;A</title>" in r.text
    assert r.text == PAGE


def test_the_page_calls_the_shared_endpoint() -> None:
    assert "fetch('/ask', {method: 'POST'" in PAGE
    for field in ("'image'", "'question'", "'locale'"):
        assert f"fd.append({field}" in PAGE


def _function(name: str) -> str:
    start = PAGE.index(f"function {name}(")
    return PAGE[start : PAGE.index("\n}\n", start)]


def test_the_page_reads_only_contract_fields() -> None:
    # The page calls a /ask response `j` (and keeps it as `it.a`).
    read = set(re.findall(r"\bj\.(\w+)", PAGE)) | set(re.findall(r"\bit\.a\.(\w+)", PAGE))
    assert read <= ANSWER_FIELDS | ERROR_FIELDS, read - (ANSWER_FIELDS | ERROR_FIELDS)
    # Evidence boxes (`e`): drawn in drawOverlay(), named in the hover tooltip showTip().
    used = _function("drawOverlay") + _function("showTip")
    box = set(re.findall(r"\be\.(\w+)", used))
    assert box == BOX_FIELDS, box ^ BOX_FIELDS


def test_the_android_app_reads_only_contract_fields() -> None:
    assert ANDROID_READS <= ANSWER_FIELDS | ERROR_FIELDS
    assert ANDROID_EVIDENCE == BOX_FIELDS


def test_server_text_is_always_escaped_before_it_becomes_html() -> None:
    # The page builds HTML strings; every value that comes from the server (or the user) must go
    # through esc(), which escapes & < > " ' (so it is safe in text and in attributes).
    assert "const esc = s => String(s).replace(/[&<>\"']/g" in PAGE
    # (`.length` only reads the size, e.g. whether "How it was counted" starts open; no text.)
    untrusted = re.compile(r"\b(j\.(answer|unit|working|error)|e\.label|it\.(err|q))\b(?!\.length)")
    # Innermost interpolations (no nested template), i.e. the ones whose value becomes text.
    exprs = re.findall(r"\$\{([^{}`]*)\}", PAGE)
    assert len(exprs) > 10
    for expr in exprs:
        if untrusted.search(expr):
            assert expr.strip().startswith("esc("), expr


def test_the_page_is_self_contained() -> None:
    assert not re.search(r'(src|href)="(https?:)?//', PAGE)  # no CDN: works offline on a LAN
    assert "eval(" not in PAGE and "outerHTML" not in PAGE


def test_sample_plans_are_served_with_their_licence(client: TestClient) -> None:
    for name in ("colorful-11397.png", "colorful-12200.png", "colorful-2002.png"):
        assert name not in PAGE  # no longer offered on the landing page (ry, 2026-11-14)
        r = client.get(f"/samples/{name}")
        assert r.status_code == 200 and r.headers["content-type"] == "image/png"
        assert r.content[:8] == b"\x89PNG\r\n\x1a\n"
    licence = (ROOT / "src" / "blueprint_qa" / "api" / "web" / "samples" / "LICENSE.md").read_text(
        encoding="utf-8"
    )
    assert "CC BY-NC-SA 4.0" in licence
    assert client.get("/samples/../server.py").status_code == 404  # no path traversal


def test_the_spec_lists_every_field() -> None:
    for name in sorted(ANSWER_FIELDS | ERROR_FIELDS):
        assert f"| `{name}` |" in SPEC or f'"{name}"' in SPEC, name
    for name in BOX_FIELDS:
        assert f'"{name}"' in SPEC, name
    for path in ("POST /ask", "GET /", "GET /health"):
        assert path in SPEC


def test_the_page_does_not_show_the_explanation() -> None:
    # ry, 2026-11-14: the web page shows the answer and its boxes, not "How it was counted".
    # The API still sends `working` (docs/API.md); the Android app may show it.
    body = PAGE.split("-->", 1)[1]  # skip the provenance comment, which mentions the removal
    assert "j.working" not in PAGE and "it.a.working" not in PAGE
    assert "How it was counted" not in body
    assert "Counted on the drawing" not in body and "legend" not in body


def test_the_page_has_no_suggested_questions() -> None:
    # ry, 2026-11-14: no suggestion chips; the user types the question.
    body = PAGE.split("-->", 1)[1]
    assert "SUGGESTIONS" not in body and "chips" not in body and "suggestion" not in body


def test_the_page_sends_the_receipt_back_for_the_same_picture_only() -> None:
    # change 006: A1 checks a picture with its LLM once; later questions carry the receipt.
    assert "fd.append('validation_token', receipt)" in PAGE
    assert "receipt = j.validation_token" in PAGE
    assert (
        PAGE.count("receipt = null") >= 3
    )  # declared, reset on a new picture, reset on "New drawing"
    assert "it.file === file" in PAGE  # a late answer for an old picture never sets the new receipt


def test_landing_page_has_no_badge_and_no_camera_button_and_a_smaller_answer() -> None:
    # ry, 2026-11-14: no "Every answer shows where it came from" badge, no "Take a photo" button,
    # and the answer (number or yes/no word) at 34px instead of 46px.
    body = PAGE.split("-->", 1)[1]
    assert "Every answer shows" not in body and "pill" not in body
    assert (
        "Take a photo" not in body
        and 'id="camera"' not in body
        and 'capture="environment"' not in body
    )
    assert ".num{font-size:34px;" in body
    assert 'id="choose"' in body  # choosing a picture still works (plus drag and drop, paste)
    assert "sample" not in body.lower() and "/samples/" not in body  # no sample plans either
