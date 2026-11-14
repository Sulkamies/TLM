"""CLI front door (MERGE_PLAN phase 1): argument handling, output modes, no details leak."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from blueprint_qa.api import cli, main
from blueprint_qa.contracts import (
    Answer,
    AnswerStatus,
    ErrorEnvelope,
    InputFormat,
    PipelineRequest,
    PlanImage,
    Stage,
    ValidationReason,
    ValidationResult,
)
from blueprint_qa.orchestrator.pipeline import PipelineTrace

RID = "22222222-2222-4222-8222-222222222222"


def answer(status: AnswerStatus = AnswerStatus.CANNOT_ANSWER, value: float | None = None) -> Answer:
    return Answer(
        request_id=RID,
        status=status,
        value=value,
        unit="count",
        confidence=0.0,
        evidence=[],
        explanation="This picture is invalid for our program",
        language="en",
    )


ENVELOPE = ErrorEnvelope(
    request_id=RID,
    stage=Stage.QUESTION,
    code="EXTERNAL_API_TIMEOUT",
    message="The service did not answer in time.",
    retryable=True,
    details={"internal": "do-not-show"},
)

VALIDATION = ValidationResult(
    request_id=RID,
    is_valid=True,
    reason=ValidationReason.OK,
    confidence=0.9,
    input_format=InputFormat.PNG,
    provider="fake",
    plan_image=PlanImage(image_png=b"\x00" * 1234, width_px=3, height_px=4),
    ifc_bytes=None,
    ifc_schema=None,
)


@pytest.fixture
def plan(tmp_path: Path) -> Path:
    path = tmp_path / "plan.PNG"
    path.write_bytes(b"\x89PNG fake")
    return path


class FakeRun:
    """Stands in for the orchestrator: records requests, returns a preset trace."""

    def __init__(self) -> None:
        self.requests: list[PipelineRequest] = []
        self.trace = PipelineTrace(result=answer())

    def __call__(self, request: PipelineRequest) -> PipelineTrace:
        self.requests.append(request)
        return self.trace


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeRun:
    stub = FakeRun()
    monkeypatch.setattr(cli, "run_traced", stub)
    return stub


def test_default_output_is_human_readable(
    plan: Path, fake: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(plan), "How many bedrooms?"]) == 0
    out = capsys.readouterr().out
    assert out == "This picture is invalid for our program\n[CANNOT_ANSWER]\n"
    req = fake.requests[0]
    assert (req.input_format, req.filename, req.question) == (
        InputFormat.PNG,
        "plan.PNG",
        "How many bedrooms?",
    )
    assert req.input_bytes == b"\x89PNG fake"


def test_format_and_locale_options(plan: Path, fake: FakeRun) -> None:
    main([str(plan), "Wie viele?", "--format", "jpeg", "--locale", "de-DE"])
    assert (fake.requests[0].input_format, fake.requests[0].locale_hint) == (
        InputFormat.JPEG,
        "de-DE",
    )


@pytest.mark.parametrize(
    ("name", "fmt"),
    [
        ("a.png", InputFormat.PNG),
        ("a.jpg", InputFormat.JPEG),
        ("a.JPEG", InputFormat.JPEG),
        ("a.pdf", InputFormat.PDF),
        ("a.ifc", InputFormat.IFC),
    ],
)
def test_format_from_extension(name: str, fmt: InputFormat) -> None:
    assert cli._format(Path(name), None) is fmt


def test_json_output(plan: Path, fake: FakeRun, capsys: pytest.CaptureFixture[str]) -> None:
    assert main([str(plan), "q?", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["explanation"] == "This picture is invalid for our program"
    assert data["value"] is None and data["status"] == "CANNOT_ANSWER"


def test_error_envelope_hides_details(
    plan: Path, fake: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.trace = PipelineTrace(result=ENVELOPE)
    assert main([str(plan), "q?", "--json"]) == 1
    data = json.loads(capsys.readouterr().out)
    assert "details" not in data and data["code"] == "EXTERNAL_API_TIMEOUT"
    assert main([str(plan), "q?"]) == 1
    out = capsys.readouterr().out
    assert out.startswith("Error EXTERNAL_API_TIMEOUT: The service did not answer in time.")
    assert "do-not-show" not in out


def test_answered_value_is_printed() -> None:
    assert cli.human(answer(AnswerStatus.ANSWERED, 3.0)).startswith("3.0 count\n")


def test_debug_prints_stage_outputs_without_bytes(
    plan: Path, fake: FakeRun, capsys: pytest.CaptureFixture[str]
) -> None:
    fake.trace = PipelineTrace(result=answer(), stages=[(Stage.VALIDATION, VALIDATION)])
    main([str(plan), "q?", "--debug"])
    err = capsys.readouterr().err
    assert "--- VALIDATION: ValidationResult" in err
    assert "<1234 bytes>" in err and "\\u0000" not in err
    stage_json = err.split("--- VALIDATION: ValidationResult\n", 1)[1]
    assert json.loads(stage_json[: stage_json.rindex("}") + 1])["plan_image"]["width_px"] == 3


def test_redacted_handles_nested_values() -> None:
    data = cli.redacted(VALIDATION)
    assert data["plan_image"]["image_png"] == "<1234 bytes>"
    assert data["reason"] == "OK"


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["missing.png", "q?"], "file not found"),
        (["{plan_txt}", "q?"], "cannot tell the format"),
        (["{plan}", "   "], "question is empty"),
    ],
)
def test_usage_errors_exit_2(
    args: list[str],
    message: str,
    plan: Path,
    tmp_path: Path,
    fake: FakeRun,
    capsys: pytest.CaptureFixture[str],
) -> None:
    txt = tmp_path / "plan.txt"
    txt.write_text("x")
    argv = [a.format(plan=plan, plan_txt=txt) for a in args]
    assert main(argv) == 2
    assert message in capsys.readouterr().err
    assert fake.requests == []


def test_module_help_runs() -> None:
    done = subprocess.run(
        [sys.executable, "-m", "blueprint_qa.api", "--help"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert done.returncode == 0
    assert "python -m blueprint_qa.api" in done.stdout
