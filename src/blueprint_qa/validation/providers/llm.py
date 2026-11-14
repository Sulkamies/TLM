"""LLM-backed floor-plan classifier. All LLM traffic goes through ``common.llm`` (R7.5)."""

import io
from functools import cache
from pathlib import Path

from PIL import Image

from blueprint_qa.common.llm import LlmClient, Prompt, get_llm_client, load_prompt
from blueprint_qa.contracts.common import ErrorEnvelope, Stage
from blueprint_qa.validation.providers.base import (
    ClassifierVerdict,
    FloorPlanClassification,
)

PROMPT_NAME = "floor_plan_classifier"
PROMPT_VERSION = 1
COMPONENT = "validation"

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# Encoding choice for the LLM copy only (not a limit; the limit is max_bytes).
_SHRINK_FACTOR = 0.8


@cache
def classifier_prompt() -> Prompt:
    return load_prompt(PROMPTS_DIR, PROMPT_NAME, PROMPT_VERSION)


def prepare_llm_image(image_png: bytes, max_side_px: int | None, max_bytes: int | None) -> bytes:
    """Build the PNG copy of the plan that is sent to the LLM.

    The copy is downscaled to ``max_side_px`` if set, then shrunk step by step until
    it is no larger than ``max_bytes``: a normalised PNG can be many times the size
    of the upload, and the API rejects requests over its size limit. Images that
    already fit are returned unchanged (byte-identical), so recorded cassettes stay
    valid. The ``PlanImage`` passed downstream is never changed.
    """
    if max_side_px is None and max_bytes is None:
        return image_png
    with Image.open(io.BytesIO(image_png), formats=["PNG"]) as img:
        if max_side_px is not None and max(img.width, img.height) > max_side_px:
            img.load()
            copy = img.copy()
            copy.thumbnail((max_side_px, max_side_px), Image.Resampling.LANCZOS)
            data = _encode_png(copy)
        else:
            if max_bytes is None or len(image_png) <= max_bytes:
                return image_png
            img.load()
            copy = img.copy()
            data = image_png
    while max_bytes is not None and len(data) > max_bytes and (copy.width > 1 or copy.height > 1):
        size = (max(1, int(copy.width * _SHRINK_FACTOR)), max(1, int(copy.height * _SHRINK_FACTOR)))
        copy = copy.resize(size, Image.Resampling.LANCZOS)
        data = _encode_png(copy)
    return data


def _encode_png(img: Image.Image) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


class LlmFloorPlanClassifier:
    def __init__(
        self,
        *,
        max_side_px: int | None,
        max_bytes: int | None,
        client: LlmClient | None = None,
    ) -> None:
        self._max_side_px = max_side_px
        self._max_bytes = max_bytes
        self._client = client or get_llm_client(COMPONENT)

    def classify(self, request_id: str, image_png: bytes) -> ClassifierVerdict | ErrorEnvelope:
        image = prepare_llm_image(image_png, self._max_side_px, self._max_bytes)
        result = self._client.generate_structured(
            request_id=request_id,
            stage=Stage.VALIDATION,
            prompt=classifier_prompt(),
            # The image is the only user data; nothing textual is needed (R7.10).
            data={},
            output_model=FloorPlanClassification,
            images_png=[image],
        )
        if isinstance(result, ErrorEnvelope):
            return result
        return ClassifierVerdict(classification=result.parsed, provider=result.provider)
