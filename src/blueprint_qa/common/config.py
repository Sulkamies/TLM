"""Configuration loader for ``config/default.yaml`` and ``config/llm.yaml`` (§3.9, R7.6).

The config directory is ``$BP_CONFIG_DIR`` if set, otherwise ``<repo>/config``.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["gemini", "mock"]


class LlmRuntimeSettings(BaseModel):
    """Timeouts and retries for LLM calls (``default.yaml: llm``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    timeout_s: float = Field(gt=0)
    max_transport_retries: int = Field(ge=0)
    backoff_initial_s: float = Field(ge=0)
    backoff_max_s: float = Field(ge=0)
    max_validation_retries: int = Field(ge=0)


class LlmModelSettings(BaseModel):
    """Provider and model for one component (``llm.yaml``)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider: ProviderName
    model: str = Field(min_length=1)
    temperature: float = 0.0
    thinking_budget: int | None = None


class LlmComponentSettings(BaseModel):
    """Everything the LLM wrapper needs for one component."""

    model_config = ConfigDict(frozen=True)

    component: str
    model: LlmModelSettings
    runtime: LlmRuntimeSettings


def config_dir() -> Path:
    override = os.environ.get("BP_CONFIG_DIR")
    if override:
        return Path(override)
    # src/blueprint_qa/common/config.py -> repository root is three levels above the package
    return Path(__file__).resolve().parents[3] / "config"


def _read_yaml(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ValueError(f"{path.name}: top level must be a mapping")
    return data


@lru_cache(maxsize=8)
def _load_raw(directory: str) -> tuple[dict[str, Any], dict[str, Any]]:
    base = Path(directory)
    return _read_yaml(base / "default.yaml"), _read_yaml(base / "llm.yaml")


def load_section(name: str) -> dict[str, Any]:
    """Return one top-level section of ``default.yaml`` (e.g. ``"validation"``)."""
    default, _ = _load_raw(str(config_dir()))
    section = default.get(name, {})
    if not isinstance(section, dict):
        raise ValueError(f"default.yaml: section {name!r} must be a mapping")
    return dict(section)


def llm_settings(component: str) -> LlmComponentSettings:
    """Resolve LLM settings for ``component`` (e.g. ``"question"``).

    Component values in ``llm.yaml`` override ``defaults``; ``BP_LLM_PROVIDER``
    overrides the provider for every component.
    """
    default, llm = _load_raw(str(config_dir()))
    merged: dict[str, Any] = dict(llm.get("defaults") or {})
    merged.update((llm.get("components") or {}).get(component) or {})
    env_provider = os.environ.get("BP_LLM_PROVIDER")
    if env_provider:
        merged["provider"] = env_provider
    return LlmComponentSettings(
        component=component,
        model=LlmModelSettings.model_validate(merged),
        runtime=LlmRuntimeSettings.model_validate(default.get("llm") or {}),
    )


def clear_cache() -> None:
    """Forget cached YAML (tests, or after editing config at runtime)."""
    _load_raw.cache_clear()
