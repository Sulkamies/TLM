"""Test isolation for A3. No test loads a model, imports torch or downloads anything."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

import pytest

from blueprint_qa.analysis.label_tables import load_detector_table, load_language
from blueprint_qa.analysis.raster import detector as detector_module
from blueprint_qa.common import config

from ._support import FakeDetector


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    for var in ("BP_CONFIG_DIR", "BP_WEIGHTS"):
        monkeypatch.delenv(var, raising=False)
    config.clear_cache()
    load_language.cache_clear()
    load_detector_table.cache_clear()
    detector_module._cached_detector.cache_clear()
    yield
    config.clear_cache()
    detector_module._cached_detector.cache_clear()


@pytest.fixture
def use_detector(monkeypatch: pytest.MonkeyPatch) -> Callable[[dict[str, Any] | Exception], None]:
    """Make ``analyze()`` use a fake detector with the given output (or exception)."""

    def install(output: dict[str, Any] | Exception) -> None:
        fake = FakeDetector(output)
        monkeypatch.setattr(detector_module, "get_detector", lambda settings: fake)

    return install
