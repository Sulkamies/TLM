import pytest

from blueprint_qa.contracts.validation import ValidationReason
from blueprint_qa.validation.ifc import check_ifc

from ._support import make_ifc

SUPPORTED = ("IFC2X3", "IFC4", "IFC4X3")


@pytest.mark.parametrize(
    ("schema", "expected"),
    [("IFC2X3", "IFC2X3"), ("IFC4", "IFC4"), ("IFC4X3_ADD2", "IFC4X3")],
)
def test_supported_schemas_with_spaces(schema: str, expected: str) -> None:
    check = check_ifc(make_ifc(schema=schema, spaces=2), SUPPORTED)
    assert check.reason is ValidationReason.OK
    assert check.schema == expected


def test_walls_only_is_enough() -> None:
    assert check_ifc(make_ifc(walls=1), SUPPORTED).reason is ValidationReason.OK


def test_wall_subtype_counts() -> None:
    data = make_ifc(schema="IFC2X3", walls=1, wall_entity="IfcWallStandardCase")
    assert check_ifc(data, SUPPORTED).reason is ValidationReason.OK


def test_no_spaces_or_walls() -> None:
    check = check_ifc(make_ifc(), SUPPORTED)
    assert check.reason is ValidationReason.NO_SPATIAL_DATA
    assert check.schema == "IFC4"


def test_schema_not_in_supported_list() -> None:
    check = check_ifc(make_ifc(schema="IFC2X3", spaces=1), ("IFC4",))
    assert check.reason is ValidationReason.UNREADABLE
    assert check.schema == "IFC2X3"


def test_unknown_schema_unreadable() -> None:
    data = (
        b"ISO-10303-21;\nHEADER;\nFILE_DESCRIPTION((''),'2;1');\nFILE_NAME('','',(''),(''),'','','');\n"
        b"FILE_SCHEMA(('AUTOMOTIVE_DESIGN'));\nENDSEC;\nDATA;\nENDSEC;\nEND-ISO-10303-21;\n"
    )
    check = check_ifc(data, SUPPORTED)
    assert check.reason is ValidationReason.UNREADABLE
    assert check.schema is None


def test_latin1_bytes_tolerated() -> None:
    data = make_ifc(spaces=1).replace(b"ENDSEC;\nDATA;", b"ENDSEC;\nDATA;\n/* K\xe4ytt\xf6 */", 1)
    assert check_ifc(data, SUPPORTED).reason is ValidationReason.OK
