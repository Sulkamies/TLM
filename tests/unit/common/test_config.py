from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from blueprint_qa.common import config


def test_repo_config_question_uses_gemini_flash() -> None:
    s = config.llm_settings("question")
    assert s.model.provider == "gemini"
    assert s.model.model == "gemini-3.8-flash"
    assert s.model.temperature == 0.0
    assert s.runtime.max_validation_retries == 2


def test_validation_component_has_its_own_slot() -> None:
    s = config.llm_settings("validation")
    assert (s.component, s.model.model) == ("validation", "gemini-3.5-flash-lite")
    # D-009: the lite model rejects thinking_budget 0, so the component sets null,
    # overriding the default 0 (no thinking config is sent then).
    assert s.model.thinking_budget is None
    assert config.llm_settings("question").model.thinking_budget == 0


def test_unknown_component_falls_back_to_defaults() -> None:
    s = config.llm_settings("not_configured")
    assert s.component == "not_configured"
    assert s.model.model == "gemini-3.8-flash"


def test_env_overrides_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BP_LLM_PROVIDER", "mock")
    assert config.llm_settings("question").model.provider == "mock"


def test_bad_provider_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BP_LLM_PROVIDER", "openai")
    with pytest.raises(ValidationError):
        config.llm_settings("question")


def test_component_override_and_sections(tmp_config: Path) -> None:
    (tmp_config / "llm.yaml").write_text(
        "defaults: {provider: gemini, model: base, temperature: 0.0}\n"
        "components: {question: {model: special, thinking_budget: 128}}\n"
    )
    config.clear_cache()
    s = config.llm_settings("question")
    assert (s.model.model, s.model.thinking_budget) == ("special", 128)
    assert config.load_section("validation")["min_confidence"] == 0.7
    assert config.load_section("missing") == {}


def test_non_mapping_yaml_rejected(tmp_config: Path) -> None:
    (tmp_config / "default.yaml").write_text("- a\n- b\n")
    config.clear_cache()
    with pytest.raises(ValueError):
        config.load_section("llm")


def test_bad_section_type_rejected(tmp_config: Path) -> None:
    (tmp_config / "default.yaml").write_text("validation: 3\n")
    config.clear_cache()
    with pytest.raises(ValueError):
        config.load_section("validation")


def test_empty_yaml_is_empty_mapping(tmp_config: Path) -> None:
    (tmp_config / "default.yaml").write_text("")
    config.clear_cache()
    assert config.load_section("validation") == {}
