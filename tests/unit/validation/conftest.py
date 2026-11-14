"""Test isolation for A1: no test may reach the network or depend on the shell env."""

from collections.abc import Iterator

import pytest

from blueprint_qa.common import config


@pytest.fixture(autouse=True)
def _isolated_env(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    names = ["BP_CONFIG_DIR", "BP_LLM_PROVIDER", "BP_LLM_CASSETTE_DIR"]
    if request.node.get_closest_marker("live") is None:
        names += ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    for var in names:
        monkeypatch.delenv(var, raising=False)
    config.clear_cache()
    yield
    config.clear_cache()
