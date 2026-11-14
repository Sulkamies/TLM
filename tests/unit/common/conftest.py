from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from blueprint_qa.common import config

CONFIG_DIR = Path(__file__).resolve().parents[3] / "config"


@pytest.fixture(autouse=True)
def _isolated_env(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """No test may reach the network or depend on the developer's shell env.

    Exception: opt-in ``@pytest.mark.live`` tests keep the API key so they can call Gemini.
    """
    names = ["BP_CONFIG_DIR", "BP_LLM_PROVIDER", "BP_LLM_CASSETTE_DIR", "BP_LLM_RECORD"]
    if request.node.get_closest_marker("live") is None:
        names += ["GEMINI_API_KEY", "GOOGLE_API_KEY"]
    for var in names:
        monkeypatch.delenv(var, raising=False)
    config.clear_cache()
    yield
    config.clear_cache()


@pytest.fixture
def tmp_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A writable copy of config/ selected through BP_CONFIG_DIR."""
    for name in ("default.yaml", "llm.yaml"):
        (tmp_path / name).write_text(
            (CONFIG_DIR / name).read_text(encoding="utf-8"), encoding="utf-8"
        )
    monkeypatch.setenv("BP_CONFIG_DIR", str(tmp_path))
    config.clear_cache()
    return tmp_path
