"""A3 Blueprint Analyzer entry point (AGENTS.md §6 A3; spec docs/requests/A3-analysis-adapter.md).

``analyze()`` never raises (R5.1) and never sees the question. Raster plans go through the
CubiCasa detector (``raster/``); IFC is not supported in this round.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from pydantic import ValidationError

from blueprint_qa.analysis.label_tables import load_detector_table, load_language
from blueprint_qa.analysis.raster import detector as detector_module
from blueprint_qa.analysis.raster.detector import ModelLoadError
from blueprint_qa.analysis.raster.mapping import build_analysis
from blueprint_qa.analysis.raster.raw import RawOutput
from blueprint_qa.analysis.raster.rules import check_bounds, select
from blueprint_qa.analysis.settings import AnalysisSettings, load_settings
from blueprint_qa.common.log import get_logger, log_event
from blueprint_qa.contracts import (
    BlueprintAnalysis,
    ErrorEnvelope,
    InputFormat,
    Stage,
    ValidationResult,
)

# Must equal the version in models/cubicasa_v2/MODEL_CARD.md (A3-Q12).
ANALYZER_VERSION = "cubicasa-yolo11m-v2+rules-v2"
PLAN_LANGUAGE = "fi"  # label table for storey words (the CubiCasa plans are Finnish)

_STAGE = Stage.ANALYSIS
_logger = get_logger(__name__)


class _Failure(Exception):
    def __init__(self, code: str, message: str, **details: str) -> None:
        super().__init__(code)
        self.code = code
        self.message = message
        self.details = details


def _envelope(request_id: str, failure: _Failure) -> ErrorEnvelope:
    return ErrorEnvelope(
        request_id=request_id,
        stage=_STAGE,
        code=failure.code,
        message=failure.message,
        retryable=False,
        details=failure.details,
    )


def analyze(validation: ValidationResult) -> BlueprintAnalysis | ErrorEnvelope:
    """Describe everything the plan contains as a ``BlueprintAnalysis``, or an ``ErrorEnvelope``."""
    rid = validation.request_id
    started = time.perf_counter()
    try:
        result = _analyze(validation)
    except _Failure as failure:
        log_event(
            _logger,
            "analysis_failed",
            request_id=rid,
            stage=_STAGE,
            level=logging.WARNING,
            code=failure.code,
            **failure.details,
        )
        return _envelope(rid, failure)
    except Exception as exc:  # last line of defence: never raise (R5.1)
        log_event(
            _logger,
            "analysis_failed",
            request_id=rid,
            stage=_STAGE,
            level=logging.ERROR,
            code="INTERNAL_ERROR",
            exception=type(exc).__name__,
        )
        return _envelope(
            rid,
            _Failure(
                "INTERNAL_ERROR",
                "The plan could not be analysed because of an internal error.",
                exception=type(exc).__name__,
            ),
        )
    log_event(
        _logger,
        "analysis_done",
        request_id=rid,
        stage=_STAGE,
        duration_ms=round((time.perf_counter() - started) * 1000),
        storeys=len(result.storeys),
        rooms=len(result.rooms),
        openings=len(result.openings),
        fixtures=len(result.fixtures),
        texts=len(result.texts),
    )
    return result


def _analyze(validation: ValidationResult) -> BlueprintAnalysis:
    if validation.input_format == InputFormat.IFC:
        raise _Failure("ANALYSIS_FAILED", "IFC plans are not supported yet.", reason="ifc")
    plan = validation.plan_image
    if plan is None:
        raise _Failure("INVALID_INPUT", "No plan image was provided.", reason="plan_image_missing")
    settings = load_settings()
    try:
        detector = detector_module.get_detector(settings)
    except ModelLoadError as exc:
        raise _Failure(
            "MODEL_LOAD_FAILED", "The plan recognition model is not available.", reason=str(exc)
        ) from exc
    try:
        raw_dict = detector.analyze(plan.image_png, settings)
    except Exception as exc:
        raise _Failure(
            "ANALYSIS_FAILED", "The plan could not be recognised.", exception=type(exc).__name__
        ) from exc
    return analysis_from_raw(
        raw_dict,
        request_id=validation.request_id,
        source_format=validation.input_format,
        expected_size=(plan.width_px, plan.height_px),
        settings=settings,
    )


def analysis_from_raw(
    raw_dict: Any,
    *,
    request_id: str,
    source_format: InputFormat,
    expected_size: tuple[int, int],
    settings: AnalysisSettings,
) -> BlueprintAnalysis:
    """Detector output (§A JSON) -> ``BlueprintAnalysis``. Raises ``_Failure`` on bad output."""
    try:
        raw = RawOutput.model_validate(raw_dict)
    except ValidationError as exc:
        raise _Failure(
            "ANALYSIS_FAILED", "The plan could not be recognised.", reason="detector_output_invalid"
        ) from exc
    if tuple(raw.size) != expected_size:
        raise _Failure(
            "ANALYSIS_FAILED",
            "The plan could not be recognised.",
            reason="size_mismatch",
            detector_size=f"{raw.size[0]}x{raw.size[1]}",
            plan_size=f"{expected_size[0]}x{expected_size[1]}",
        )
    table = load_detector_table()
    items, texts, dropped = check_bounds(raw, settings.bounds_tolerance_px)
    try:
        analysis = build_analysis(
            request_id=request_id,
            source_format=source_format,
            analyzer_version=ANALYZER_VERSION,
            selection=select(items, settings, table),
            texts=texts,
            dropped=dropped,
            settings=settings,
            table=table,
            lang=load_language(PLAN_LANGUAGE),
        )
        # Re-validate the whole object: catches anything the constructors let through.
        return BlueprintAnalysis.model_validate(analysis.model_dump())
    except ValidationError as exc:
        raise _Failure(
            "ANALYSIS_FAILED", "The plan could not be recognised.", reason="contract_violation"
        ) from exc
