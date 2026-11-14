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
    assert 'fetch("ask", { method: "POST"' in PAGE  # relative: works at any host and port
    for field in ('"image"', '"question"', '"locale"'):
        assert f"body.append({field}" in PAGE


def test_the_page_reads_only_contract_fields() -> None:
    read = set(re.findall(r"\b(?:a|json)\.(\w+)", PAGE)) - {"length"}
    assert read <= ANSWER_FIELDS | ERROR_FIELDS, read - (ANSWER_FIELDS | ERROR_FIELDS)
    box = set(re.findall(r"\bbox\.(\w+)", PAGE))  # the page names each evidence box `box`
    assert box == BOX_FIELDS, box ^ BOX_FIELDS


def test_the_android_app_reads_only_contract_fields() -> None:
    assert ANDROID_READS <= ANSWER_FIELDS | ERROR_FIELDS
    assert ANDROID_EVIDENCE == BOX_FIELDS


def test_the_page_is_self_contained_and_safe() -> None:
    assert not re.search(r'(src|href)="(https?:)?//', PAGE)  # no CDN: works offline on a LAN
    assert "innerHTML" not in PAGE and "outerHTML" not in PAGE  # server text is inserted as text
    assert "eval(" not in PAGE


def test_the_spec_lists_every_field() -> None:
    for name in sorted(ANSWER_FIELDS | ERROR_FIELDS):
        assert f"| `{name}` |" in SPEC or f'"{name}"' in SPEC, name
    for name in BOX_FIELDS:
        assert f'"{name}"' in SPEC, name
    for path in ("POST /ask", "GET /", "GET /health"):
        assert path in SPEC
