from __future__ import annotations

import json
import logging

import pytest

from blueprint_qa.common.log import JsonFormatter, get_logger, log_event
from blueprint_qa.contracts import Stage


def _capture(logger: logging.Logger) -> list[str]:
    lines: list[str] = []

    class _H(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            lines.append(JsonFormatter().format(record))

    logger.addHandler(_H())
    return lines


def test_log_line_has_request_id_and_stage() -> None:
    log = get_logger("test.log1")
    lines = _capture(log)
    log_event(log, "hello", request_id="r-1", stage=Stage.QUESTION, tokens=3)
    rec = json.loads(lines[-1])
    assert rec["event"] == "hello"
    assert rec["request_id"] == "r-1"
    assert rec["stage"] == "QUESTION"
    assert rec["tokens"] == 3
    assert rec["logger"] == "blueprint_qa.test.log1"


def test_secrets_are_masked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSECRETSECRET")
    log = get_logger("blueprint_qa.test.log2")
    lines = _capture(log)
    log_event(log, "oops", request_id="r", stage=Stage.ORCHESTRATOR, detail="AIzaSECRETSECRET")
    assert "AIzaSECRETSECRET" not in lines[-1]
    assert "***" in lines[-1]


def test_plain_record_and_exception_type() -> None:
    log = get_logger("test.log3")
    lines = _capture(log)
    try:
        raise KeyError("x")
    except KeyError:
        log.exception("boom")
    rec = json.loads(lines[-1])
    assert rec["request_id"] is None
    assert rec["exc_type"] == "KeyError"
