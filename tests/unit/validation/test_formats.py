import pytest

from blueprint_qa.contracts.common import InputFormat
from blueprint_qa.validation.formats import sniff_format

from ._support import make_ifc, make_jpeg, make_pdf, make_png


def test_sniff_real_files() -> None:
    assert sniff_format(make_png()) is InputFormat.PNG
    assert sniff_format(make_jpeg()) is InputFormat.JPEG
    assert sniff_format(make_pdf()) is InputFormat.PDF
    assert sniff_format(make_ifc()) is InputFormat.IFC


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (b"junk-before-header\n%PDF-1.7\n...", InputFormat.PDF),
        (b"\xef\xbb\xbfISO-10303-21;\nHEADER;", InputFormat.IFC),
        (b"\r\n  ISO-10303-21;\nHEADER;", InputFormat.IFC),
    ],
)
def test_sniff_tolerated_headers(data: bytes, expected: InputFormat) -> None:
    assert sniff_format(data) is expected


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"hello world",
        b"PK\x03\x04 zip archive, e.g. ifcZIP",
        b"<?xml version='1.0'?><ifcXML/>",
        b"GIF89a....",
        b"x" * 2000 + b"%PDF-1.7",
    ],
)
def test_sniff_unknown(data: bytes) -> None:
    assert sniff_format(data) is None
