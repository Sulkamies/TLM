"""Terminal chat REPL: ``python -m blueprint_qa.question`` (developer tool, rule Q7).

Type a question in any language; the ``ParsedQuestion`` (or ``ErrorEnvelope``) is
printed as JSON. Reads stdin line by line, so questions can also be piped in.
Offline replay: set ``BP_LLM_PROVIDER=mock`` and ``BP_LLM_CASSETTE_DIR``.
This module only calls ``interpret()``; it has no logic of its own.
"""

from __future__ import annotations

import argparse
import sys
import uuid
from collections.abc import Callable, Sequence

from blueprint_qa.question import interpret

QUIT = frozenset({":q", "quit", "exit"})


def main(argv: Sequence[str] | None = None, read: Callable[[str], str] = input) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m blueprint_qa.question",
        description="Interpret floor-plan questions and print the ParsedQuestion JSON.",
    )
    parser.add_argument("--locale", default=None, help="BCP-47 UI locale hint, e.g. fi-FI")
    args = parser.parse_args(argv)
    interactive = sys.stdin.isatty()
    if interactive:
        print("Ask a question about a floor plan (any language). Ctrl-D/Ctrl-Z or :q quits.")
    while True:
        try:
            line = read("> " if interactive else "")
        except (EOFError, KeyboardInterrupt):
            break
        question = line.strip()
        if not question:
            continue
        if question.casefold() in QUIT:
            break
        result = interpret(str(uuid.uuid4()), question, args.locale)
        print(result.model_dump_json(indent=2), flush=True)
    return 0


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
