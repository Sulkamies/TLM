"""A1 Input Validator entry point (AGENTS.md §6, A1)."""

import logging

from blueprint_qa.common.log import get_logger, log_event
from blueprint_qa.contracts.common import ErrorEnvelope, InputFormat, Stage
from blueprint_qa.contracts.request import PipelineRequest
from blueprint_qa.contracts.validation import (
    PlanImage,
    ValidationReason,
    ValidationResult,
)
from blueprint_qa.validation.formats import sniff_format
from blueprint_qa.validation.ifc import check_ifc
from blueprint_qa.validation.pdf import (
    MultiPagePdfError,
    UnreadablePdfError,
    render_single_page,
)
from blueprint_qa.validation.providers import build_classifier
from blueprint_qa.validation.providers.base import (
    ClassifierVerdict,
    FloorPlanClassifier,
    FloorPlanLabel,
)
from blueprint_qa.validation.raster import UnreadableImageError, normalize_raster
from blueprint_qa.validation.receipt import (
    ReceiptContext,
    Rejected,
    issue_receipt,
    load_receipt_settings,
    receipt_key,
    verify_receipt,
)
from blueprint_qa.validation.settings import ValidationSettings, load_settings

_STAGE = Stage.VALIDATION
_LOCAL_PROVIDER = "local:checks"
_IFC_PROVIDER = "local:ifc"
_RECEIPT_PROVIDER_PREFIX = "receipt:"
# Facts established by deterministic local checks are certain.
_CERTAIN = 1.0

_logger = get_logger(__name__)


def validate(request: PipelineRequest) -> ValidationResult | ErrorEnvelope:
    """Verify the input format, normalise the plan and decide whether it is a house floor plan.

    Never raises: unexpected failures are returned as an ``INTERNAL_ERROR`` envelope.
    """
    try:
        settings = load_settings()
        receipt_settings = load_receipt_settings()
        receipts = ReceiptContext(
            key=receipt_key(receipt_settings.key_env), ttl_s=receipt_settings.ttl_s
        )
        return run_validation(request, settings, build_classifier(settings), receipts)
    except Exception as exc:
        log_event(
            _logger,
            "validation_failed",
            request_id=request.request_id,
            stage=_STAGE,
            level=logging.ERROR,
            exception=type(exc).__name__,
        )
        return ErrorEnvelope(
            request_id=request.request_id,
            stage=_STAGE,
            code="INTERNAL_ERROR",
            message="The file could not be checked because of an internal error.",
            retryable=False,
            details={"exception": type(exc).__name__},
        )


def run_validation(
    request: PipelineRequest,
    settings: ValidationSettings,
    classifier: FloorPlanClassifier,
    receipts: ReceiptContext | None = None,
) -> ValidationResult | ErrorEnvelope:
    """Run the checks. ``receipts=None`` disables validation receipts (no issue, no verify)."""
    result = _run(request, settings, classifier, receipts)
    if isinstance(result, ValidationResult):
        log_event(
            _logger,
            "validation_finished",
            request_id=request.request_id,
            stage=_STAGE,
            is_valid=result.is_valid,
            reason=result.reason.value,
            input_format=result.input_format.value,
            provider=result.provider,
            confidence=result.confidence,
        )
    return result


def _run(
    request: PipelineRequest,
    settings: ValidationSettings,
    classifier: FloorPlanClassifier,
    receipts: ReceiptContext | None,
) -> ValidationResult | ErrorEnvelope:
    data = request.input_bytes
    detected = sniff_format(data)
    if detected is None:
        # Unknown signature: the declared format cannot be verified (see OPEN_QUESTIONS).
        return _rejected(request, ValidationReason.UNREADABLE, request.input_format)
    if detected is not request.input_format:
        return _rejected(request, ValidationReason.FORMAT_MISMATCH, detected)

    if detected is InputFormat.IFC:
        return _validate_ifc(request, settings)

    try:
        if detected is InputFormat.PDF:
            plan_image = render_single_page(
                data, settings.pdf_render_dpi, settings.max_image_pixels
            )
        else:
            plan_image = normalize_raster(data, detected, settings.max_image_pixels)
    except MultiPagePdfError:
        return _rejected(request, ValidationReason.MULTI_PAGE_PDF, detected)
    except (UnreadablePdfError, UnreadableImageError):
        return _rejected(request, ValidationReason.UNREADABLE, detected)

    if receipts is not None and request.validation_token is not None:
        receipted = _from_receipt(
            request,
            request.validation_token,
            detected,
            plan_image,
            classifier,
            settings.min_confidence,
            receipts,
        )
        if receipted is not None:
            return receipted

    verdict = classifier.classify(request.request_id, plan_image.image_png)
    if isinstance(verdict, ErrorEnvelope):
        return verdict
    result = _classified(request, detected, plan_image, verdict, settings.min_confidence)
    if receipts is not None and result.is_valid:
        token = issue_receipt(
            receipts, data, detected, verdict.provider, verdict.classification.confidence
        )
        result = result.model_copy(update={"validation_token": token})
    return result


def _from_receipt(
    request: PipelineRequest,
    token: str,
    input_format: InputFormat,
    plan_image: PlanImage,
    classifier: FloorPlanClassifier,
    min_confidence: float,
    receipts: ReceiptContext,
) -> ValidationResult | None:
    """A valid result from the request's receipt, or ``None`` to validate normally.

    A rejected receipt is never an error: it is logged (without the token) and ignored.
    """
    check = verify_receipt(
        receipts, token, request.input_bytes, input_format, classifier.provider, min_confidence
    )
    if isinstance(check, Rejected):
        log_event(
            _logger,
            "receipt_rejected",
            request_id=request.request_id,
            stage=_STAGE,
            reason=check.reason.value,
        )
        return None
    log_event(_logger, "receipt_used", request_id=request.request_id, stage=_STAGE)
    return ValidationResult(
        request_id=request.request_id,
        is_valid=True,
        reason=ValidationReason.OK,
        confidence=float(check.claims.c),
        input_format=input_format,
        provider=_RECEIPT_PROVIDER_PREFIX + check.claims.p,
        plan_image=plan_image,
        ifc_bytes=None,
        ifc_schema=None,
        validation_token=token,
    )


def _validate_ifc(request: PipelineRequest, settings: ValidationSettings) -> ValidationResult:
    check = check_ifc(request.input_bytes, settings.supported_ifc_schemas)
    is_valid = check.reason is ValidationReason.OK
    return ValidationResult(
        request_id=request.request_id,
        is_valid=is_valid,
        reason=check.reason,
        confidence=_CERTAIN,
        input_format=InputFormat.IFC,
        provider=_IFC_PROVIDER,
        plan_image=None,
        ifc_bytes=request.input_bytes if is_valid else None,
        ifc_schema=check.schema,
    )


def _classified(
    request: PipelineRequest,
    input_format: InputFormat,
    plan_image: PlanImage,
    verdict: ClassifierVerdict,
    min_confidence: float,
) -> ValidationResult:
    classification = verdict.classification
    if classification.confidence < min_confidence:
        reason = ValidationReason.LOW_CONFIDENCE
    elif classification.label is FloorPlanLabel.HOUSE_FLOOR_PLAN:
        reason = ValidationReason.OK
    else:
        reason = ValidationReason.NOT_A_BLUEPRINT
    is_valid = reason is ValidationReason.OK
    return ValidationResult(
        request_id=request.request_id,
        is_valid=is_valid,
        reason=reason,
        confidence=classification.confidence,
        input_format=input_format,
        provider=verdict.provider,
        plan_image=plan_image if is_valid else None,
        ifc_bytes=None,
        ifc_schema=None,
    )


def _rejected(
    request: PipelineRequest, reason: ValidationReason, input_format: InputFormat
) -> ValidationResult:
    return ValidationResult(
        request_id=request.request_id,
        is_valid=False,
        reason=reason,
        confidence=_CERTAIN,
        input_format=input_format,
        provider=_LOCAL_PROVIDER,
        plan_image=None,
        ifc_bytes=None,
        ifc_schema=None,
    )
