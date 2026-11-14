import io

import pypdfium2 as pdfium  # type: ignore[import-untyped]  # no py.typed upstream
import pytest
from PIL import Image

from blueprint_qa.validation.pdf import (
    MultiPagePdfError,
    UnreadablePdfError,
    render_single_page,
)

from ._support import make_pdf


def test_single_page_rendered_at_dpi() -> None:
    # 144 x 72 pt = 2 x 1 in -> 400 x 200 px at 200 DPI
    plan = render_single_page(make_pdf(width_pt=144, height_pt=72), dpi=200, max_pixels=None)
    assert (plan.width_px, plan.height_px) == (400, 200)
    img = Image.open(io.BytesIO(plan.image_png))
    assert img.format == "PNG"
    assert img.size == (400, 200)


def test_dpi_is_configurable() -> None:
    plan = render_single_page(make_pdf(width_pt=144, height_pt=72), dpi=72, max_pixels=None)
    assert (plan.width_px, plan.height_px) == (144, 72)


def test_page_rotation_applied() -> None:
    pdf = pdfium.PdfDocument(make_pdf(width_pt=144, height_pt=72))
    pdf[0].set_rotation(90)
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    plan = render_single_page(buf.getvalue(), dpi=72, max_pixels=None)
    assert (plan.width_px, plan.height_px) == (72, 144)


def test_multi_page_rejected() -> None:
    with pytest.raises(MultiPagePdfError) as info:
        render_single_page(make_pdf(pages=3), dpi=200, max_pixels=None)
    assert info.value.page_count == 3


def test_zero_pages_unreadable() -> None:
    pdf = pdfium.PdfDocument.new()
    buf = io.BytesIO()
    pdf.save(buf)
    pdf.close()
    with pytest.raises(UnreadablePdfError):
        render_single_page(buf.getvalue(), dpi=200, max_pixels=None)


def test_corrupt_pdf_unreadable() -> None:
    with pytest.raises(UnreadablePdfError):
        render_single_page(b"%PDF-1.7\ngarbage", dpi=200, max_pixels=None)


def test_pixel_limit_checked_before_render() -> None:
    with pytest.raises(UnreadablePdfError):
        render_single_page(make_pdf(width_pt=144, height_pt=72), dpi=200, max_pixels=79_999)
    plan = render_single_page(make_pdf(width_pt=144, height_pt=72), dpi=200, max_pixels=80_000)
    assert plan.width_px == 400
