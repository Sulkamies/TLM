from __future__ import annotations

from collections.abc import Iterator

import pytest

from blueprint_qa.common import config


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """No orchestrator test reaches the network or depends on the developer's shell env."""
    for var in (
        "BP_CONFIG_DIR",
        "BP_LLM_PROVIDER",
        "BP_LLM_CASSETTE_DIR",
        "BP_LLM_RECORD",
        "GEMINI_API_KEY",
        "GOOGLE_API_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    config.clear_cache()
    yield
    config.clear_cache()
