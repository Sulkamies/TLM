"""Helpers for the A3 unit tests: recorded detector output and a fake detector."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from blueprint_qa.analysis import analyzer
from blueprint_qa.analysis.settings import AnalysisSettings
from blueprint_qa.contracts import (
    InputFormat,
    PlanImage,
    ValidationReason,
    ValidationResult,
)

DATA = Path(__file__).parent / "data"
RECORDINGS = ("colorful-11397", "colorful-12200", "colorful-2002")
REQUEST_ID = "3f2b8c1e-7d4a-4c2e-9b1f-0a6d5e4c3b2a"


def recorded(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((DATA / f"{name}.png.json").read_text(encoding="utf-8"))
    return data


def validation_for(
    raw: dict[str, Any] | None,
    *,
    fmt: InputFormat = InputFormat.PNG,
    request_id: str = REQUEST_ID,
    with_image: bool = True,
) -> ValidationResult:
    plan = None
    if with_image:
        w, h = raw["size"] if raw else (10, 10)
        plan = PlanImage(image_png=b"\x89PNG not decoded by the fake", width_px=w, height_px=h)
    return ValidationResult(
        request_id=request_id,
        is_valid=True,
        reason=ValidationReason.OK,
        confidence=0.99,
        input_format=fmt,
        provider="mock",
        plan_image=plan,
        ifc_bytes=b"ISO-10303-21;" if fmt == InputFormat.IFC else None,
        ifc_schema="IFC4" if fmt == InputFormat.IFC else None,
    )


class FakeDetector:
    """Returns recorded output instead of running the model."""

    def __init__(self, output: dict[str, Any] | Exception) -> None:
        self.output = output
        self.calls = 0

    def analyze(self, image_png: bytes, settings: AnalysisSettings) -> dict[str, Any]:
        self.calls += 1
        if isinstance(self.output, Exception):
            raise self.output
        return self.output


def run(raw: dict[str, Any], **kwargs: Any) -> Any:
    return analyzer.analyze(validation_for(raw, **kwargs))
