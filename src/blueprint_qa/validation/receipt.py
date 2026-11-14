"""Validation receipts (contract change 006, ``docs/requests/A1-validation-receipt.md``).

After the LLM has classified a picture as a valid house floor plan, A1 issues a signed
receipt ``v1.<payload>.<signature>``. A later request for the *same* bytes that carries
the receipt skips the LLM classification. The server stores nothing (R3.7): the client
holds the receipt, and only A1 can create or check one.

* ``payload`` = base64url (no padding) of compact JSON
  ``{"h": sha256 hex of the input bytes, "f": verified format, "p": classifier provider,
  "c": classification confidence, "e": expiry in Unix seconds}``.
* ``signature`` = base64url (no padding) of HMAC-SHA256(key, ``"v1." + payload``).

The key comes from the environment variable named in ``config/default.yaml ->
validation_receipt.key_env``; if it is unset or empty, a random key is generated once per
process. The key and the token are never logged, echoed or returned in errors (R3.8).
"""

import base64
import binascii
import hashlib
import hmac
import json
import os
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from functools import cache

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictFloat,
    StrictInt,
    StrictStr,
    ValidationError,
)

from blueprint_qa.common import config
from blueprint_qa.contracts.common import InputFormat

_VERSION = "v1"
_PROCESS_KEY_BYTES = 32


class ReceiptSettings(BaseModel):
    """The ``validation_receipt`` section of ``config/default.yaml`` (nothing hard-coded, R3.9)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ttl_s: int = Field(gt=0)
    """Receipt lifetime in seconds."""

    key_env: str = Field(min_length=1)
    """Name of the environment variable holding the HMAC key."""


def load_receipt_settings() -> ReceiptSettings:
    return ReceiptSettings.model_validate(config.load_section("validation_receipt"))


@cache
def _process_key() -> bytes:
    return secrets.token_bytes(_PROCESS_KEY_BYTES)


def receipt_key(key_env: str) -> bytes:
    """The HMAC key: the bytes of ``$key_env``, or a per-process random key if it is unset/empty."""
    value = os.environ.get(key_env)
    if value:
        return value.encode("utf-8")
    return _process_key()


class RejectReason(str, Enum):
    """Short reason codes for the ``receipt_rejected`` log event."""

    MALFORMED = "MALFORMED"
    BAD_SIGNATURE = "BAD_SIGNATURE"
    OTHER_PICTURE = "OTHER_PICTURE"
    FORMAT_CHANGED = "FORMAT_CHANGED"
    EXPIRED = "EXPIRED"
    PROVIDER_CHANGED = "PROVIDER_CHANGED"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"


class ReceiptClaims(BaseModel):
    """The signed payload. Strict, so a token can only carry exactly these fields."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    h: StrictStr
    f: InputFormat
    p: StrictStr
    c: StrictFloat | StrictInt
    e: StrictInt


@dataclass(frozen=True)
class ReceiptContext:
    """Everything needed to issue and verify receipts for one request."""

    key: bytes = field(repr=False)
    ttl_s: int
    clock: Callable[[], float] = time.time


@dataclass(frozen=True)
class Verified:
    claims: ReceiptClaims


@dataclass(frozen=True)
class Rejected:
    reason: RejectReason


def _b64encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(key: bytes, payload: str) -> str:
    message = f"{_VERSION}.{payload}".encode("ascii")
    return _b64encode(hmac.new(key, message, hashlib.sha256).digest())


def picture_hash(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def issue_receipt(
    ctx: ReceiptContext,
    data: bytes,
    input_format: InputFormat,
    provider: str,
    confidence: float,
) -> str:
    claims = {
        "h": picture_hash(data),
        "f": input_format.value,
        "p": provider,
        "c": confidence,
        "e": int(ctx.clock()) + ctx.ttl_s,
    }
    payload = _b64encode(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    return f"{_VERSION}.{payload}.{_sign(ctx.key, payload)}"


def verify_receipt(
    ctx: ReceiptContext,
    token: str,
    data: bytes,
    input_format: InputFormat,
    provider: str,
    min_confidence: float,
) -> Verified | Rejected:
    """Check ``token`` against this request. Never raises."""
    parts = token.split(".")
    if len(parts) != 3 or parts[0] != _VERSION or not parts[1] or not parts[2]:
        return Rejected(RejectReason.MALFORMED)
    _, payload, signature = parts
    try:
        expected = _sign(ctx.key, payload)
    except UnicodeEncodeError:
        return Rejected(RejectReason.MALFORMED)
    if not hmac.compare_digest(expected.encode("ascii"), signature.encode("utf-8")):
        return Rejected(RejectReason.BAD_SIGNATURE)
    try:
        claims = ReceiptClaims.model_validate(json.loads(_b64decode(payload)))
    except (binascii.Error, ValueError, ValidationError):
        return Rejected(RejectReason.MALFORMED)

    if not hmac.compare_digest(claims.h, picture_hash(data)):
        return Rejected(RejectReason.OTHER_PICTURE)
    if claims.f is not input_format:
        return Rejected(RejectReason.FORMAT_CHANGED)
    if claims.e <= ctx.clock():
        return Rejected(RejectReason.EXPIRED)
    if claims.p != provider:
        return Rejected(RejectReason.PROVIDER_CHANGED)
    if not 0.0 <= claims.c <= 1.0 or claims.c < min_confidence:
        return Rejected(RejectReason.LOW_CONFIDENCE)
    return Verified(claims)
