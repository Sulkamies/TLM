"""Floor-plan classifier adapters (private to ``blueprint_qa.validation``).

In tests and CI the shared wrapper's ``mock`` provider replays recorded responses,
so there is no separate mock classifier here.
"""

from blueprint_qa.validation.providers.base import FloorPlanClassifier
from blueprint_qa.validation.providers.llm import LlmFloorPlanClassifier
from blueprint_qa.validation.settings import ValidationSettings


def build_classifier(settings: ValidationSettings) -> FloorPlanClassifier:
    return LlmFloorPlanClassifier(
        max_side_px=settings.llm_image_max_side_px,
        max_bytes=settings.llm_image_max_bytes,
    )
