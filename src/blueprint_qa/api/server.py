"""HTTP front door for the Android app (AGENTS.md §2.1 ``api/``). Custodian: A0.

    python -m blueprint_qa.api.server [--host 127.0.0.1] [--port 8000]

* ``POST /ask`` (multipart/form-data): ``image`` (PNG, JPEG, PDF or IFC file), ``question``
  (text), optional ``locale`` (BCP-47; else the first ``Accept-Language`` tag). Response format:
  :mod:`blueprint_qa.api.mobile`.
* ``GET /health``: ``{"status": "ok"}``, to check the address from a browser or the phone.

It only builds a ``PipelineRequest`` and calls the orchestrator; it has no pipeline logic.
Defaults come from ``config/default.yaml -> api``. Needs the ``server`` extra
(``pip install -e ".[server]"``); raster plans also need the ``vision`` extra and model files.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from blueprint_qa.api import mobile
from blueprint_qa.api.cli import EXTENSIONS
from blueprint_qa.common.config import load_section
from blueprint_qa.common.log import configure_logging
from blueprint_qa.contracts import InputFormat
from blueprint_qa.orchestrator import new_request, run_traced

# Uploaded content type -> declared format (A1 still verifies the real format from the bytes).
CONTENT_TYPES: dict[str, InputFormat] = {
    "image/png": InputFormat.PNG,
    "image/jpeg": InputFormat.JPEG,
    "image/jpg": InputFormat.JPEG,
    "application/pdf": InputFormat.PDF,
}


def create_app() -> FastAPI:
    settings = load_section("api")
    max_bytes: int | None = settings.get("max_upload_bytes")
    point_size = float(settings.get("evidence_point_size", 0.04))

    app = FastAPI(title="Blueprint Q&A", docs_url=None, redoc_url=None, openapi_url=None)

    @app.exception_handler(RequestValidationError)
    def bad_form(_request: Request, _exc: RequestValidationError) -> JSONResponse:
        # Missing form fields: answer in the app's {"error": ...} format, not FastAPI's 422.
        return _error(400, "Send a picture of the plan ('image') and a question ('question').")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/ask")
    def ask(
        image: Annotated[UploadFile, File()],
        question: Annotated[str, Form()],
        locale: Annotated[str | None, Form()] = None,
        accept_language: Annotated[str | None, Header()] = None,
    ) -> JSONResponse:
        if not question.strip():
            return _error(400, "Please type a question.")
        fmt = declared_format(image.filename, image.content_type)
        if fmt is None:
            return _error(
                415, "Unsupported file type. Send a PNG, JPEG or PDF picture of the plan."
            )
        data = image.file.read() if max_bytes is None else image.file.read(max_bytes + 1)
        if not data:
            return _error(400, "The picture is empty.")
        if max_bytes is not None and len(data) > max_bytes:
            return _error(413, "The picture is too large.")
        request = new_request(
            data,
            fmt,
            question,
            filename=image.filename,
            locale_hint=locale or first_language(accept_language),
        )
        status, body = mobile.present(run_traced(request), point_size)
        return JSONResponse(body, status_code=status)

    return app


def declared_format(filename: str | None, content_type: str | None) -> InputFormat | None:
    """The format the client declares: file extension first, then the content type."""
    if filename:
        fmt = EXTENSIONS.get(Path(filename).suffix.lower())
        if fmt is not None:
            return fmt
    return CONTENT_TYPES.get((content_type or "").split(";")[0].strip().lower())


def first_language(header: str | None) -> str | None:
    """First tag of an Accept-Language header (``"fi-FI,fi;q=0.9"`` -> ``"fi-FI"``)."""
    if not header:
        return None
    tag = header.split(",")[0].split(";")[0].strip()
    return tag if tag and tag != "*" else None


def _error(status: int, message: str) -> JSONResponse:
    body: dict[str, Any] = {"error": message}
    return JSONResponse(body, status_code=status)


def main(argv: Sequence[str] | None = None) -> int:
    settings = load_section("api")
    p = argparse.ArgumentParser(prog="python -m blueprint_qa.api.server", description=__doc__)
    p.add_argument("--host", default=settings.get("host", "127.0.0.1"))
    p.add_argument("--port", type=int, default=int(settings.get("port", 8000)))
    args = p.parse_args(argv)
    configure_logging()

    import uvicorn

    uvicorn.run(create_app(), host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
