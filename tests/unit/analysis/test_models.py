"""Model card and ``models/fetch.py`` (no network: downloads are never attempted here)."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from blueprint_qa.analysis.analyzer import ANALYZER_VERSION
from blueprint_qa.analysis.settings import load_settings, repo_root

MODELS = repo_root() / "models"


def _fetch() -> ModuleType:
    spec = importlib.util.spec_from_file_location("bp_models_fetch", MODELS / "fetch.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(mod)
    return mod


def test_model_card_names_the_analyzer_version() -> None:
    card = (MODELS / "cubicasa_v2" / "MODEL_CARD.md").read_text(encoding="utf-8")
    assert f"`{ANALYZER_VERSION}`" in card
    assert "CC BY-NC-SA 4.0" in card
    assert "241" in card


def test_fetch_covers_the_configured_files() -> None:
    fetch = _fetch()
    paths = {f.path for f in fetch.FILES}
    settings = load_settings()
    assert settings.detector.weights_path == "models/" + "cubicasa_v2/best.pt"
    assert "cubicasa_v2/best.pt" in paths
    assert {"easyocr/craft_mlt_25k.pth", "easyocr/english_g2.pth"} <= paths
    weights = next(f for f in fetch.FILES if f.path == "cubicasa_v2/best.pt")
    assert weights.sha256 == "2093bef2b2322dbc23c402d7e7beafe00245d6e9144905b1cd54ed0eaef3337d"
    assert weights.size == 40_587_180


def test_every_model_file_has_a_download_url() -> None:
    for f in _fetch().FILES:
        assert f.url is not None and f.url.startswith("https://"), f.path


def test_fetch_verifies_checksums(tmp_path: Path) -> None:
    fetch = _fetch()
    data = b"weights"
    f = fetch.ModelFile(
        path="m/x.pt", sha256=hashlib.sha256(data).hexdigest(), size=len(data), url=None
    )
    assert not fetch.is_valid(f, tmp_path)
    (tmp_path / "m").mkdir()
    (tmp_path / "m" / "x.pt").write_bytes(b"other!!")
    assert not fetch.is_valid(f, tmp_path)
    (tmp_path / "m" / "x.pt").write_bytes(data)
    assert fetch.is_valid(f, tmp_path)
    with pytest.raises(RuntimeError, match="no download URL"):
        fetch.download(f, tmp_path)
