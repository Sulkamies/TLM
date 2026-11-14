from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from question_cases import CASSETTES

from blueprint_qa.common import config
from blueprint_qa.common.llm import CassetteBackend, LlmClient, get_llm_client
from blueprint_qa.question import interpreter
from blueprint_qa.question.providers import LlmQuestionProvider, QuestionProvider
from blueprint_qa.question.vocabulary_view import load_synonyms


@pytest.fixture(autouse=True)
def _isolated_env(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """No test reaches the network or depends on the shell env (R7.3).

    Opt-in ``@pytest.mark.live`` tests keep the API key.
    """
    names = ["BP_CONFIG_DIR", "BP_LLM_PROVIDER", "BP_LLM_CASSETTE_DIR", "BP_LLM_RECORD"]
    if request.node.get_closest_marker("live") is None:
        names += ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    for var in names:
        monkeypatch.delenv(var, raising=False)
    config.clear_cache()
    load_synonyms.cache_clear()
    yield
    config.clear_cache()
    load_synonyms.cache_clear()


@pytest.fixture
def cassette_client() -> LlmClient:
    return get_llm_client("question", backend=CassetteBackend(CASSETTES))


@pytest.fixture
def llm_provider(cassette_client: LlmClient) -> LlmQuestionProvider:
    return LlmQuestionProvider(client=cassette_client)


@pytest.fixture
def use_provider(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Make ``interpret()`` use the given provider."""

    def _use(provider: QuestionProvider) -> None:
        monkeypatch.setattr(interpreter, "provider_factory", lambda: provider)

    return _use
