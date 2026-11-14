"""Local IFC validation (no LLM): parse, check schema, check for spatial data."""

from collections.abc import Collection
from dataclasses import dataclass

import ifcopenshell

from blueprint_qa.contracts.validation import ValidationReason


@dataclass(frozen=True)
class IfcCheck:
    reason: ValidationReason
    schema: str | None


def check_ifc(data: bytes, supported_schemas: Collection[str]) -> IfcCheck:
    """Validate an IFC-SPF file.

    Returns ``OK`` if it parses, uses a supported schema and contains at least
    one ``IfcSpace`` or ``IfcWall`` (subtypes such as ``IfcWallStandardCase``
    included).
    """
    try:
        model = ifcopenshell.file.from_string(_decode(data))
        schema = str(model.schema)
    except Exception:  # untrusted input: any parser failure means unreadable
        return IfcCheck(ValidationReason.UNREADABLE, None)

    if schema not in supported_schemas:
        return IfcCheck(ValidationReason.UNREADABLE, schema)

    try:
        has_spatial_data = bool(model.by_type("IfcSpace")) or bool(model.by_type("IfcWall"))
    except Exception:  # untrusted input: any parser failure means unreadable
        return IfcCheck(ValidationReason.UNREADABLE, schema)
    if not has_spatial_data:
        return IfcCheck(ValidationReason.NO_SPATIAL_DATA, schema)
    return IfcCheck(ValidationReason.OK, schema)


def _decode(data: bytes) -> str:
    # IFC-SPF is nominally ASCII with escape sequences, but real files often
    # contain raw UTF-8 or Latin-1 in string values.
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("latin-1")
