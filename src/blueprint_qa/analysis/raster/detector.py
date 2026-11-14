"""YOLO detector + EasyOCR for raster plans (ported from ``vision/analyze.py`` at ``35597e2``).

torch, ultralytics, easyocr and numpy come from the optional ``vision`` extra. They are imported
lazily, inside :class:`Detector`, so CI and the unit tests (which use recorded output) never need
them. The model is loaded once per process (R3.7) by :func:`get_detector`.
"""

from __future__ import annotations

import importlib
import io
from functools import lru_cache
from pathlib import Path
from typing import Any

from blueprint_qa.analysis.settings import AnalysisSettings, resolve_path, weights_file


class ModelLoadError(Exception):
    """Weights or OCR model missing or unloadable, or the vision packages are not installed."""


class Detector:
    """Runs the detector (and OCR, if enabled) on one image. Construct via :func:`get_detector`."""

    def __init__(
        self,
        weights: Path,
        *,
        device: str,
        ocr_enabled: bool,
        ocr_languages: tuple[str, ...],
        ocr_model_dir: Path,
        ocr_download: bool,
    ) -> None:
        if not weights.is_file():
            raise ModelLoadError(f"weights file not found: {weights.name}")
        try:
            import torch
            from ultralytics import YOLO
        except ImportError as exc:  # the `vision` extra is not installed
            raise ModelLoadError(f"vision packages missing: {exc.name}") from exc
        self.gpu = torch.cuda.is_available() if device == "auto" else device == "cuda"
        try:
            self.model: Any = YOLO(str(weights))
        except Exception as exc:  # corrupt or incompatible weights
            raise ModelLoadError(f"weights could not be loaded: {type(exc).__name__}") from exc
        self.reader: Any = None
        if ocr_enabled:
            try:
                import easyocr

                self.reader = easyocr.Reader(
                    list(ocr_languages),
                    gpu=self.gpu,
                    model_storage_directory=str(ocr_model_dir),
                    download_enabled=ocr_download,
                )
            except Exception as exc:  # missing model files with downloads off, or import failure
                raise ModelLoadError(
                    f"OCR model could not be loaded: {type(exc).__name__}"
                ) from exc

    def analyze(self, image_png: bytes, settings: AnalysisSettings) -> dict[str, Any]:
        """Raw output in the §A format; boxes and polygons in the pixel space of the input image."""
        from PIL import Image

        # numpy comes with the `vision` extra; imported by name so CI type checks need no stubs.
        np: Any = importlib.import_module("numpy")
        img = Image.open(io.BytesIO(image_png)).convert("RGB")
        # Exactly as when the thresholds were tuned: an RGB array (Ultralytics reads arrays as BGR;
        # changing this would change the detections the tuned rules were fitted to).
        arr = np.array(img)
        det = settings.detector
        res = self.model.predict(
            arr,
            conf=det.conf,
            imgsz=det.imgsz,
            max_det=det.max_det,
            verbose=False,
            device=0 if self.gpu else "cpu",
        )[0]
        names = res.names
        detections = [
            {"cls": names[int(c)], "conf": float(s), "box": [float(v) for v in b]}
            for b, c, s in zip(
                res.boxes.xyxy.tolist(),
                res.boxes.cls.tolist(),
                res.boxes.conf.tolist(),
                strict=True,
            )
        ]
        ocr: list[dict[str, Any]] = []
        if self.reader is not None:
            ocr = [
                {"text": t, "conf": float(p), "poly": [[float(x), float(y)] for x, y in box]}
                for box, t, p in self.reader.readtext(
                    arr, rotation_info=list(settings.ocr.rotation_info)
                )
            ]
        return {"size": list(img.size), "detections": detections, "ocr": ocr}


@lru_cache(maxsize=2)
def _cached_detector(
    weights: str,
    device: str,
    ocr_enabled: bool,
    ocr_languages: tuple[str, ...],
    ocr_model_dir: str,
    ocr_download: bool,
) -> Detector:
    return Detector(
        Path(weights),
        device=device,
        ocr_enabled=ocr_enabled,
        ocr_languages=ocr_languages,
        ocr_model_dir=Path(ocr_model_dir),
        ocr_download=ocr_download,
    )


def get_detector(settings: AnalysisSettings) -> Detector:
    """The process-wide detector for these settings. Raises :class:`ModelLoadError`."""
    return _cached_detector(
        str(weights_file(settings)),
        settings.detector.device,
        settings.ocr.enabled,
        settings.ocr.languages,
        str(resolve_path(settings.ocr.model_dir)),
        settings.ocr.download_enabled,
    )
