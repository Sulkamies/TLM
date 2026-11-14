"""Generate JSON Schemas for the top-level contracts into ``schema/``.

    python -m blueprint_qa.contracts.generate_schema          # write files
    python -m blueprint_qa.contracts.generate_schema --check  # exit 1 if out of date

Only A0 runs this (R3.3). The output is committed and never edited by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from pydantic import BaseModel

from blueprint_qa.contracts import (
    Answer,
    BlueprintAnalysis,
    ErrorEnvelope,
    ParsedQuestion,
    PipelineRequest,
    ValidationResult,
)

SCHEMA_DIR = Path(__file__).parent / "schema"
TOP_LEVEL: tuple[type[BaseModel], ...] = (
    PipelineRequest,
    ValidationResult,
    ParsedQuestion,
    BlueprintAnalysis,
    Answer,
    ErrorEnvelope,
)


def render(model: type[BaseModel]) -> str:
    """Return the canonical JSON Schema text for one contract model."""
    schema = model.model_json_schema(mode="validation")
    return json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True) + "\n"


def expected_files() -> dict[Path, str]:
    return {SCHEMA_DIR / f"{model.__name__}.json": render(model) for model in TOP_LEVEL}


def main(argv: list[str]) -> int:
    check = "--check" in argv
    stale: list[str] = []
    for path, text in expected_files().items():
        current = path.read_text(encoding="utf-8") if path.exists() else None
        if current == text:
            continue
        if check:
            stale.append(path.name)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="\n")
            print(f"wrote {path.name}")
    if stale:
        print("out-of-date schema files: " + ", ".join(stale), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
