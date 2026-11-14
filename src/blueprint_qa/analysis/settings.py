"""Typed view of ``config/default.yaml -> analysis`` (R3.9: nothing limit-like is hard-coded)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from blueprint_qa.common.config import config_dir, load_section


class DetectorSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    weights_path: str = Field(min_length=1)
    weights_env: str = Field(min_length=1)
    conf: float = Field(ge=0.0, le=1.0)
    imgsz: int = Field(gt=0)
    max_det: int = Field(gt=0)
    device: Literal["auto", "cpu", "cuda"]


class OcrSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    enabled: bool
    languages: tuple[str, ...] = Field(min_length=1)
    rotation_info: tuple[int, ...]
    min_confidence: float = Field(ge=0.0, le=1.0)
    model_dir: str = Field(min_length=1)
    download_enabled: bool


class AnalysisSettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    detector: DetectorSettings
    ocr: OcrSettings
    default_threshold: float = Field(ge=0.0, le=1.0)
    thresholds: dict[str, float]
    duplicate_iou: dict[str, float]
    sauna_cluster_grow: float = Field(ge=0.0)
    bounds_tolerance_px: float = Field(ge=0.0)

    def threshold(self, cls: str) -> float:
        return self.thresholds.get(cls, self.default_threshold)

    def dup_iou(self, cls: str) -> float:
        """Greedy duplicate-removal IoU for ``cls``; 1.0 (the default) means off."""
        return self.duplicate_iou.get(cls, 1.0)


def repo_root() -> Path:
    """Relative paths in the config are relative to the directory that holds ``config/``."""
    return config_dir().resolve().parent


def resolve_path(path: str) -> Path:
    p = Path(os.path.expanduser(path))
    return p if p.is_absolute() else repo_root() / p


def weights_file(settings: AnalysisSettings) -> Path:
    """The weights file: env var ``detector.weights_env`` if set, else ``detector.weights_path``."""
    override = os.environ.get(settings.detector.weights_env)
    return resolve_path(override or settings.detector.weights_path)


def load_settings() -> AnalysisSettings:
    return AnalysisSettings.model_validate(load_section("analysis"))
