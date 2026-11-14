"""The terminal chat REPL only calls interpret() and prints JSON (rule Q7)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from question_cases import CASSETTES

from blueprint_qa.contracts import ErrorEnvelope, ParsedQuestion
from blueprint_qa.question import __main__ as repl

REPO = Path(__file__).resolve().parents[3]


def _reader(lines: list[str]) -> Callable[[str], str]:
    it: Iterator[str] = iter(lines)

    def read(prompt: str) -> str:
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return read


def test_repl_prints_one_json_per_question(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    seen: list[tuple[str, str | None]] = []

    def fake_interpret(rid: str, question: str, hint: str | None) -> ErrorEnvelope:
        seen.append((question, hint))
        return ErrorEnvelope(
            request_id=rid, stage="QUESTION", code="X", message="m", retryable=False
        )

    monkeypatch.setattr(repl, "interpret", fake_interpret)
    code = repl.main(
        ["--locale", "fi-FI"], read=_reader(["", "  first? ", "second?", ":q", "never"])
    )
    assert code == 0
    assert seen == [("first?", "fi-FI"), ("second?", "fi-FI")]
    out = capsys.readouterr().out
    assert out.count('"code": "X"') == 2


def test_repl_stops_on_eof(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(repl, "interpret", lambda *a: pytest.fail("not called"))
    assert repl.main([], read=_reader([])) == 0


def test_repl_as_module_with_piped_questions_offline() -> None:
    env = {
        **{k: v for k, v in os.environ.items() if not k.startswith(("BP_", "GEMINI"))},
        "BP_LLM_PROVIDER": "mock",
        "BP_LLM_CASSETTE_DIR": str(CASSETTES),
        "PYTHONIOENCODING": "utf-8",
    }
    proc = subprocess.run(
        [sys.executable, "-m", "blueprint_qa.question"],
        input=b"Onko talossa saunaa?\n",
        capture_output=True,
        env=env,
        cwd=REPO,
        timeout=120,
        check=True,
    )
    pq = ParsedQuestion.model_validate(json.loads(proc.stdout.decode("utf-8")))
    assert (pq.language, pq.intent.value) == ("fi", "EXISTENCE")
