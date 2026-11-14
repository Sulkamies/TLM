"""Floor-plan classifier through the REAL shared LLM client, with recorded responses.

``test_recorded_classification`` replays answers from
``cassettes/floor_plan_classifier@v1.json`` and never touches the network (R7.3).

The images in ``data/`` are classified directly as committed bytes, not through
``validate()``, because re-encoding a PNG could change its bytes on another
platform and the cassette key includes a hash of the image.

To re-record after a prompt version change or new images (costs API calls, R7.12):

    GEMINI_API_KEY=... pytest -m live tests/unit/validation/test_llm_cassettes.py

then commit the cassette file.
"""

from pathlib import Path

import pytest

from blueprint_qa.common import config
from blueprint_qa.common.llm import (
    CassetteBackend,
    GeminiBackend,
    LlmBackend,
    RecordingBackend,
    get_llm_client,
)
from blueprint_qa.contracts.common import ErrorEnvelope
from blueprint_qa.validation.providers.base import FloorPlanLabel
from blueprint_qa.validation.providers.llm import (
    PROMPT_NAME,
    PROMPT_VERSION,
    LlmFloorPlanClassifier,
)

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
CASSETTES = HERE / "cassettes"

# (image file, is it a house floor plan?)
CASES = [
    ("house_plan_fi.png", True),
    ("house_plan_de_two_storeys.png", True),
    ("house_elevation.png", False),  # a drawing of a house, but not a plan
    ("bar_chart.png", False),
    ("text_page.png", False),
    ("prompt_injection.png", False),  # text in the image tries to force the label
]


def _check(backend: LlmBackend, image: str, is_house_plan: bool) -> None:
    classifier = LlmFloorPlanClassifier(
        max_side_px=None,  # the committed images are small; they are sent unchanged
        max_bytes=None,
        client=get_llm_client("validation", backend=backend),
    )
    verdict = classifier.classify("cassette-test", (DATA / image).read_bytes())

    assert not isinstance(verdict, ErrorEnvelope), verdict
    assert verdict.provider.startswith("llm:")
    assert verdict.provider.endswith(f":{PROMPT_NAME}@v{PROMPT_VERSION}")

    classification = verdict.classification
    min_confidence = float(config.load_section("validation")["min_confidence"])
    accepted = (
        classification.label is FloorPlanLabel.HOUSE_FLOOR_PLAN
        and classification.confidence >= min_confidence
    )
    assert accepted is is_house_plan, classification


@pytest.mark.parametrize(("image", "is_house_plan"), CASES)
def test_recorded_classification(image: str, is_house_plan: bool) -> None:
    _check(CassetteBackend(CASSETTES), image, is_house_plan)


@pytest.mark.live
@pytest.mark.parametrize(("image", "is_house_plan"), CASES)
def test_record_live(image: str, is_house_plan: bool) -> None:
    _check(RecordingBackend(GeminiBackend(), CASSETTES), image, is_house_plan)
