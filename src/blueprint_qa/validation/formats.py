"""Detect the real input format from magic bytes / file header."""

from blueprint_qa.contracts.common import InputFormat

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_JPEG_SIGNATURE = b"\xff\xd8\xff"
_PDF_MARKER = b"%PDF-"
# ISO 32000 readers accept the %PDF- marker anywhere in the first 1024 bytes.
_PDF_HEADER_WINDOW = 1024
_STEP_MARKER = b"ISO-10303-21;"
_STEP_HEADER_WINDOW = 256
_UTF8_BOM = b"\xef\xbb\xbf"


def sniff_format(data: bytes) -> InputFormat | None:
    """Return the format the bytes actually are, or ``None`` if unrecognised.

    IFC is recognised as an ISO 10303-21 (STEP) physical file; whether it is
    really IFC is confirmed later when the schema is read.
    """
    if data.startswith(_PNG_SIGNATURE):
        return InputFormat.PNG
    if data.startswith(_JPEG_SIGNATURE):
        return InputFormat.JPEG
    if _PDF_MARKER in data[:_PDF_HEADER_WINDOW]:
        return InputFormat.PDF
    head = data[:_STEP_HEADER_WINDOW]
    head = head.removeprefix(_UTF8_BOM)
    if head.lstrip().startswith(_STEP_MARKER):
        return InputFormat.IFC
    return None
