"""The detector wrapper with stand-in torch/ultralytics/easyocr modules (no model, no download)."""

from __future__ import annotations

import io
import sys
import types
from pathlib import Path
from typing import Any, ClassVar

import pytest
from PIL import Image

from blueprint_qa.analysis.raster import detector as detector_module
from blueprint_qa.analysis.raster.detector import Detector, ModelLoadError
from blueprint_qa.analysis.settings import load_settings

numpy = pytest.importorskip(
    "numpy"
)  # comes with Pillow's array support; torch brings it in production


class _Tensor:
    def __init__(self, values: list[Any]) -> None:
        self.values = values

    def tolist(self) -> list[Any]:
        return self.values


class _Result:
    names: ClassVar[dict[int, str]] = {0: "door", 1: "toilet"}

    def __init__(self) -> None:
        self.boxes = types.SimpleNamespace(
            xyxy=_Tensor([[1.0, 2.0, 5.0, 6.0], [3.0, 3.0, 4.0, 4.0]]),
            cls=_Tensor([0.0, 1.0]),
            conf=_Tensor([0.9, 0.5]),
        )


class _Yolo:
    calls: ClassVar[list[dict[str, Any]]] = []

    def __init__(self, path: str) -> None:
        if Path(path).read_bytes() == b"corrupt":
            raise RuntimeError("bad weights")

    def predict(self, arr: Any, **kwargs: Any) -> list[_Result]:
        _Yolo.calls.append({"shape": arr.shape, **kwargs})
        return [_Result()]


class _Reader:
    def __init__(self, langs: list[str], **kwargs: Any) -> None:
        if not kwargs["download_enabled"] and not Path(kwargs["model_storage_directory"]).is_dir():
            raise FileNotFoundError("model missing and downloads disabled")
        self.kwargs = kwargs

    def readtext(self, arr: Any, rotation_info: list[int]) -> list[Any]:
        return [([[0, 0], [4, 0], [4, 2], [0, 2]], "MH", 0.8)]


@pytest.fixture
def fake_vision(monkeypatch: pytest.MonkeyPatch) -> None:
    torch = types.ModuleType("torch")
    torch.cuda = types.SimpleNamespace(is_available=lambda: False)  # type: ignore[attr-defined]
    ultralytics = types.ModuleType("ultralytics")
    ultralytics.YOLO = _Yolo  # type: ignore[attr-defined]
    easyocr = types.ModuleType("easyocr")
    easyocr.Reader = _Reader  # type: ignore[attr-defined]
    for name, mod in (("torch", torch), ("ultralytics", ultralytics), ("easyocr", easyocr)):
        monkeypatch.setitem(sys.modules, name, mod)
    _Yolo.calls.clear()


def _png(w: int, h: int) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (w, h), "white").save(buf, format="PNG")
    return buf.getvalue()


def _make(
    tmp_path: Path, weights: bytes = b"ok", ocr: bool = True, ocr_dir: bool = True
) -> Detector:
    w = tmp_path / "best.pt"
    w.write_bytes(weights)
    model_dir = tmp_path / "easyocr"
    if ocr_dir:
        model_dir.mkdir(exist_ok=True)
    return Detector(
        w,
        device="auto",
        ocr_enabled=ocr,
        ocr_languages=("en",),
        ocr_model_dir=model_dir,
        ocr_download=False,
    )


def test_output_has_the_recorded_shape(fake_vision: None, tmp_path: Path) -> None:
    out = _make(tmp_path).analyze(_png(30, 20), load_settings())
    assert out["size"] == [30, 20]
    assert out["detections"] == [
        {"cls": "door", "conf": 0.9, "box": [1.0, 2.0, 5.0, 6.0]},
        {"cls": "toilet", "conf": 0.5, "box": [3.0, 3.0, 4.0, 4.0]},
    ]
    assert out["ocr"] == [{"text": "MH", "conf": 0.8, "poly": [[0, 0], [4, 0], [4, 2], [0, 2]]}]
    call = _Yolo.calls[0]
    assert call["shape"] == (20, 30, 3)
    assert (call["conf"], call["imgsz"], call["max_det"], call["device"]) == (
        0.15,
        1280,
        1000,
        "cpu",
    )


def test_ocr_can_be_disabled(fake_vision: None, tmp_path: Path) -> None:
    assert _make(tmp_path, ocr=False).analyze(_png(5, 5), load_settings())["ocr"] == []


def test_missing_weights(tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError, match="not found"):
        Detector(
            tmp_path / "absent.pt",
            device="cpu",
            ocr_enabled=False,
            ocr_languages=("en",),
            ocr_model_dir=tmp_path,
            ocr_download=False,
        )


def test_missing_vision_packages(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", None)  # import torch -> ImportError
    with pytest.raises(ModelLoadError, match="vision packages missing"):
        _make(tmp_path)


def test_corrupt_weights(fake_vision: None, tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError, match="weights could not be loaded"):
        _make(tmp_path, weights=b"corrupt")


def test_missing_ocr_model_with_downloads_off(fake_vision: None, tmp_path: Path) -> None:
    with pytest.raises(ModelLoadError, match="OCR model"):
        _make(tmp_path, ocr_dir=False)


def test_get_detector_resolves_paths_from_config(
    fake_vision: None, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    weights = tmp_path / "w.pt"
    weights.write_bytes(b"ok")
    monkeypatch.setenv("BP_WEIGHTS", str(weights))
    base = load_settings()
    model_dir = tmp_path / "ocr-models"
    model_dir.mkdir()
    settings = base.model_copy(
        update={"ocr": base.ocr.model_copy(update={"model_dir": str(model_dir)})}
    )
    det = detector_module.get_detector(settings)
    assert det.reader is not None
    assert det.reader.kwargs["model_storage_directory"] == str(model_dir)
    assert det.reader.kwargs["download_enabled"] is False
    assert det.gpu is False
