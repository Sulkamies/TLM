"""The detector's raw output (spec §A), parsed into typed models before anything uses it.

Shape, as written by ``Vision.analyze()``::

    {"size": [w, h],
     "detections": [{"cls": "toilet", "conf": 0.91, "box": [x0, y0, x1, y1]}],
     "ocr": [{"text": "MH", "conf": 0.97, "poly": [[x, y], [x, y], [x, y], [x, y]]}]}

Internal to A3: these models never cross the component boundary (R3.2).
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

Box = tuple[float, float, float, float]  # x_min, y_min, x_max, y_max
Point = tuple[float, float]


class RawDetection(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    cls: str
    conf: float = Field(ge=0.0, le=1.0)
    box: Box


class RawText(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    conf: float = Field(ge=0.0, le=1.0)
    poly: tuple[Point, ...] = Field(min_length=1)


class RawOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    size: tuple[int, int]
    detections: tuple[RawDetection, ...]
    ocr: tuple[RawText, ...]
