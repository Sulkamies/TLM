"""Plain 2D geometry on contract polygons (coordinates in the analysis' own space).

Polygons are lists of ``(x, y)``, implicitly closed (AGENTS.md §4.1). These helpers do
not know about units; ``compute.py`` multiplies by the metres-per-unit factor.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

Point = tuple[float, float]


def is_usable(polygon: Sequence[Point]) -> bool:
    """At least 3 finite vertices."""
    return len(polygon) >= 3 and all(math.isfinite(x) and math.isfinite(y) for x, y in polygon)


def bbox_long_side(polygon: Sequence[Point]) -> float:
    """Longer side of the axis-aligned bounding box."""
    xs = [p[0] for p in polygon]
    ys = [p[1] for p in polygon]
    return max(max(xs) - min(xs), max(ys) - min(ys))


def perimeter(polygon: Sequence[Point]) -> float:
    """Length of the closed outline."""
    total = 0.0
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


def centroid(polygon: Sequence[Point]) -> Point:
    """Area centroid (shoelace); the vertex mean for a zero-area polygon."""
    twice_area = 0.0
    cx = 0.0
    cy = 0.0
    for i, (x1, y1) in enumerate(polygon):
        x2, y2 = polygon[(i + 1) % len(polygon)]
        cross = x1 * y2 - x2 * y1
        twice_area += cross
        cx += (x1 + x2) * cross
        cy += (y1 + y2) * cross
    if twice_area == 0.0:
        n = len(polygon)
        return (sum(p[0] for p in polygon) / n, sum(p[1] for p in polygon) / n)
    return (cx / (3.0 * twice_area), cy / (3.0 * twice_area))


def distance(a: Point, b: Point) -> float:
    return math.hypot(b[0] - a[0], b[1] - a[1])
