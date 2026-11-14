"""``python -m blueprint_qa.api``: see :mod:`blueprint_qa.api.cli`."""

import sys

from blueprint_qa.api.cli import main

if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
