"""Check that a PDF has exactly one page and render it to PNG."""

import math
import threading

import pypdfium2 as pdfium  # type: ignore[import-untyped]  # no py.typed upstream

from blueprint_qa.contracts.validation import PlanImage
from blueprint_qa.validation.raster import (
    UnreadableImageError,
    check_pixel_limit,
    to_plan_image,
)

_POINTS_PER_INCH = 72.0

# PDFium is not thread-safe; serialise all calls into it.
_PDFIUM_LOCK = threading.Lock()


class UnreadablePdfError(Exception):
    """The PDF could not be opened or rendered (corrupt, encrypted, empty, too large)."""


class MultiPagePdfError(Exception):
    """The PDF has more than one page."""

    def __init__(self, page_count: int) -> None:
        super().__init__(f"PDF has {page_count} pages")
        self.page_count = page_count


def render_single_page(data: bytes, dpi: float, max_pixels: int | None) -> PlanImage:
    """Render the only page of ``data`` at ``dpi``. Page rotation is applied."""
    with _PDFIUM_LOCK:
        try:
            pdf = pdfium.PdfDocument(data)
        except pdfium.PdfiumError as exc:
            raise UnreadablePdfError(str(exc)) from exc
        try:
            page_count = len(pdf)
            if page_count == 0:
                raise UnreadablePdfError("PDF has no pages")
            if page_count > 1:
                raise MultiPagePdfError(page_count)
            page = pdf[0]
            try:
                width_pt, height_pt = page.get_size()
                scale = dpi / _POINTS_PER_INCH
                try:
                    check_pixel_limit(
                        math.ceil(width_pt * scale),
                        math.ceil(height_pt * scale),
                        max_pixels,
                    )
                except UnreadableImageError as exc:
                    raise UnreadablePdfError(str(exc)) from exc
                bitmap = page.render(scale=scale, fill_color=(255, 255, 255, 255))
                image = bitmap.to_pil()
            except pdfium.PdfiumError as exc:
                raise UnreadablePdfError(str(exc)) from exc
            finally:
                page.close()
        finally:
            pdf.close()
    return to_plan_image(image, dpi=dpi)
