"""R7.5 guard: only blueprint_qa.common may talk to an LLM vendor SDK.

Catches components (e.g. an independently built A1) that call Gemini directly instead
of going through common/llm.py. Fix by switching to get_llm_client(...); see
docs/requests/A1-use-shared-llm-wrapper.md.
"""

from __future__ import annotations

import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[3] / "src" / "blueprint_qa"
VENDOR_IMPORT = re.compile(
    r"^\s*(from|import)\s+(google\.genai|google\.generativeai|google\s+import\s+genai|"
    r"openai|anthropic|vertexai)\b",
    re.MULTILINE,
)


def test_no_vendor_llm_sdk_outside_common() -> None:
    offenders = [
        str(path.relative_to(SRC))
        for path in SRC.rglob("*.py")
        if path.parent.name != "common" and VENDOR_IMPORT.search(path.read_text(encoding="utf-8"))
    ]
    assert offenders == [], (
        f"R7.5: use blueprint_qa.common.llm instead of a vendor SDK in {offenders}"
    )


def test_the_guard_detects_violations() -> None:
    assert VENDOR_IMPORT.search("from google import genai\n")
    assert VENDOR_IMPORT.search("import anthropic\n")
    assert not VENDOR_IMPORT.search("from blueprint_qa.common.llm import get_llm_client\n")
