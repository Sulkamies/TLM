"""Decode PNG/JPEG, apply EXIF orientation and re-encode as PNG. Never resizes."""

import io

from PIL import Image, ImageOps

from blueprint_qa.contracts.common import InputFormat
from blueprint_qa.contracts.validation import PlanImage

# Pillow's own decompression-bomb guard is a hard-coded limit. It is replaced by
# the configurable ``validation.max_image_pixels`` check below (AGENTS.md R3.9).
# Note: this is a process-wide Pillow setting (see docs/OPEN_QUESTIONS.md).
Image.MAX_IMAGE_PIXELS = None

# Modes the PNG encoder can write without conversion.
_PNG_MODES = frozenset({"1", "L", "LA", "I", "I;16", "P", "RGB", "RGBA"})
# Premultiplied-alpha modes and their straight-alpha equivalents.
_PREMULTIPLIED_ALPHA = {"La": "LA", "RGBa": "RGBA"}

_PIL_FORMAT = {InputFormat.PNG: "PNG", InputFormat.JPEG: "JPEG"}


class UnreadableImageError(Exception):
    """The bytes could not be decoded as an image of the expected format."""


class ImageTooLargeError(UnreadableImageError):
    """The image exceeds the configured pixel limit."""


def check_pixel_limit(width: int, height: int, max_pixels: int | None) -> None:
    if max_pixels is not None and width * height > max_pixels:
        raise ImageTooLargeError(f"{width}x{height} exceeds max_image_pixels")


def normalize_raster(data: bytes, input_format: InputFormat, max_pixels: int | None) -> PlanImage:
    """Decode a PNG or JPEG, apply its EXIF orientation and return it as PNG."""
    try:
        with Image.open(io.BytesIO(data), formats=[_PIL_FORMAT[input_format]]) as img:
            # Dimensions are read from the header; check before decoding pixels.
            check_pixel_limit(img.width, img.height, max_pixels)
            img.load()
            oriented = ImageOps.exif_transpose(img)
    except UnreadableImageError:
        raise
    except Exception as exc:  # any decoder failure means the file is unreadable
        raise UnreadableImageError(type(exc).__name__) from exc
    check_pixel_limit(oriented.width, oriented.height, max_pixels)
    return to_plan_image(oriented)


def to_plan_image(img: Image.Image, dpi: float | None = None) -> PlanImage:
    """Encode ``img`` as PNG without resizing it."""
    if img.mode in _PREMULTIPLIED_ALPHA:
        img = img.convert(_PREMULTIPLIED_ALPHA[img.mode])
    elif img.mode not in _PNG_MODES:
        img = img.convert("RGBA" if "A" in img.getbands() else "RGB")
    buf = io.BytesIO()
    if dpi is not None:
        img.save(buf, format="PNG", dpi=(dpi, dpi))
    else:
        img.save(buf, format="PNG")
    return PlanImage(image_png=buf.getvalue(), width_px=img.width, height_px=img.height)
