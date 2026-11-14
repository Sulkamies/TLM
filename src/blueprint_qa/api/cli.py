"""Command-line front door (MERGE_PLAN phase 1). Custodian: A0.

    python -m blueprint_qa.api <file> "<question>" [--format F] [--locale L] [--json] [--debug]

* default output: a short human-readable answer on stdout;
* ``--json``: the ``Answer`` (or ``ErrorEnvelope`` without ``details``) as JSON on stdout;
* ``--debug``: also print every stage output to stderr (file bytes replaced by their size)
  and log at INFO level.

``details`` of an ``ErrorEnvelope`` are internal (§6 A0) and are shown only with ``--debug``.
Exit codes: 0 = an ``Answer`` was returned (any status), 1 = an ``ErrorEnvelope``,
2 = usage error (file missing, unknown format).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from blueprint_qa.common.log import configure_logging
from blueprint_qa.contracts import Answer, AnswerStatus, ErrorEnvelope, InputFormat
from blueprint_qa.orchestrator import new_request, run_traced

# File extension -> declared format. A1 still verifies the real format from the bytes.
EXTENSIONS: dict[str, InputFormat] = {
    ".png": InputFormat.PNG,
    ".jpg": InputFormat.JPEG,
    ".jpeg": InputFormat.JPEG,
    ".pdf": InputFormat.PDF,
    ".ifc": InputFormat.IFC,
}


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    configure_logging("INFO" if args.debug else "WARNING")

    path = Path(args.file)
    if not path.is_file():
        print(f"error: file not found: {path}", file=sys.stderr)
        return 2
    fmt = _format(path, args.format)
    if fmt is None:
        known = ", ".join(sorted(EXTENSIONS))
        print(
            f"error: cannot tell the format of {path.name} ({known}); use --format", file=sys.stderr
        )
        return 2
    if not args.question.strip():
        print("error: the question is empty", file=sys.stderr)
        return 2

    request = new_request(
        path.read_bytes(), fmt, args.question, filename=path.name, locale_hint=args.locale
    )
    trace = run_traced(request)

    if args.debug:
        for stage, output in trace.stages:
            print(f"--- {stage.value}: {type(output).__name__}", file=sys.stderr)
            print(json.dumps(redacted(output), indent=2, ensure_ascii=False), file=sys.stderr)

    result = trace.result
    if args.json:
        print(json.dumps(public(result), indent=2, ensure_ascii=False))
    else:
        print(human(result))
    return 0 if isinstance(result, Answer) else 1


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="python -m blueprint_qa.api",
        description="Ask a numeric question about a floor plan (PNG, JPEG, PDF or IFC).",
    )
    p.add_argument("file", help="the floor plan file")
    p.add_argument("question", help="the question, in any language")
    p.add_argument(
        "--format",
        choices=[f.value for f in InputFormat],
        type=str.upper,
        help="declared input format (default: from the file extension)",
    )
    p.add_argument("--locale", default=None, help="BCP-47 UI locale hint, e.g. fi-FI")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    p.add_argument("--debug", action="store_true", help="print stage outputs to stderr")
    return p


def _format(path: Path, declared: str | None) -> InputFormat | None:
    if declared:
        return InputFormat(declared)
    return EXTENSIONS.get(path.suffix.lower())


def public(result: Answer | ErrorEnvelope) -> dict[str, Any]:
    """The user-facing JSON: an ``ErrorEnvelope`` loses its internal ``details``."""
    if isinstance(result, ErrorEnvelope):
        return result.model_dump(mode="json", exclude={"details"})
    return result.model_dump(mode="json")


def human(result: Answer | ErrorEnvelope) -> str:
    if isinstance(result, ErrorEnvelope):
        retry = " (you can try again)" if result.retryable else ""
        return f"Error {result.code}: {result.message}{retry}"
    if result.status is AnswerStatus.ANSWERED and result.value is not None:
        return f"{result.value} {result.unit}\n{result.explanation}"
    return f"{result.explanation}\n[{result.status.value}]"


def redacted(model: BaseModel) -> Any:
    """A model as JSON-able data with every ``bytes`` value replaced by its size."""

    def walk(value: Any) -> Any:
        if isinstance(value, bytes | bytearray):
            return f"<{len(value)} bytes>"
        if isinstance(value, dict):
            return {k: walk(v) for k, v in value.items()}
        if isinstance(value, list | tuple):
            return [walk(v) for v in value]
        if isinstance(value, BaseModel):
            return walk(value.model_dump())
        return value if isinstance(value, str | int | float | bool | type(None)) else str(value)

    return walk(model.model_dump())
