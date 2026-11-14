import io

import pytest
from PIL import Image

from blueprint_qa.contracts.common import InputFormat
from blueprint_qa.validation.raster import (
    ImageTooLargeError,
    UnreadableImageError,
    normalize_raster,
    to_plan_image,
)

from ._support import make_jpeg, make_png


def _decode(png: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    return img


def test_png_kept_at_original_size() -> None:
    plan = normalize_raster(make_png(4000, 3000), InputFormat.PNG, max_pixels=None)
    assert (plan.width_px, plan.height_px) == (4000, 3000)
    assert _decode(plan.image_png).size == (4000, 3000)


def test_jpeg_converted_to_png() -> None:
    plan = normalize_raster(make_jpeg(40, 20), InputFormat.JPEG, max_pixels=None)
    assert _decode(plan.image_png).size == (40, 20)


@pytest.mark.parametrize(("orientation", "size"), [(1, (40, 20)), (3, (40, 20)), (6, (20, 40))])
def test_jpeg_exif_orientation_applied(orientation: int, size: tuple[int, int]) -> None:
    plan = normalize_raster(make_jpeg(40, 20, orientation=orientation), InputFormat.JPEG, None)
    assert (plan.width_px, plan.height_px) == size
    img = _decode(plan.image_png)
    assert img.size == size
    assert img.getexif().get(0x0112) in (None, 1)


def test_cmyk_jpeg_converted_to_rgb() -> None:
    plan = normalize_raster(make_jpeg(mode="CMYK"), InputFormat.JPEG, None)
    assert _decode(plan.image_png).mode == "RGB"


def test_alpha_preserved() -> None:
    plan = normalize_raster(make_png(mode="RGBA"), InputFormat.PNG, None)
    assert _decode(plan.image_png).mode == "RGBA"


@pytest.mark.parametrize(
    ("mode", "expected"),
    [("La", "LA"), ("RGBa", "RGBA"), ("PA", "RGBA"), ("YCbCr", "RGB"), ("CMYK", "RGB")],
)
def test_non_png_modes_converted(mode: str, expected: str) -> None:
    plan = to_plan_image(Image.new(mode, (4, 4)))
    assert _decode(plan.image_png).mode == expected


def test_dpi_written_when_given() -> None:
    plan = to_plan_image(Image.new("RGB", (4, 4)), dpi=200)
    dpi = _decode(plan.image_png).info["dpi"]
    assert dpi == pytest.approx((200, 200), abs=0.1)


def test_pixel_limit_enforced() -> None:
    with pytest.raises(ImageTooLargeError):
        normalize_raster(make_png(100, 100), InputFormat.PNG, max_pixels=9_999)
    assert normalize_raster(make_png(100, 100), InputFormat.PNG, max_pixels=10_000).width_px == 100


@pytest.mark.parametrize(
    ("data", "fmt"),
    [
        (make_png()[:40], InputFormat.PNG),  # truncated
        (make_jpeg()[:30], InputFormat.JPEG),  # truncated
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 50, InputFormat.PNG),  # signature only
        (make_jpeg(), InputFormat.PNG),  # wrong decoder
    ],
)
def test_undecodable_images(data: bytes, fmt: InputFormat) -> None:
    with pytest.raises(UnreadableImageError):
        normalize_raster(data, fmt, None)
