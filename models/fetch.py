"""Download the A3 model files and check their sha256 (AGENTS.md §6 A3; weights never in git).

    python models/fetch.py            # fetch everything missing, verify everything
    python models/fetch.py --check    # only verify what is there (exit 1 on a missing/bad file)

Files land next to this script, where ``config/default.yaml -> analysis`` expects them:
``models/cubicasa_v2/best.pt`` (detector.weights_path) and ``models/easyocr/`` (ocr.model_dir).
Standard library only, so it runs before ``pip install .[vision]``.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import shutil
import sys
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

MODELS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ModelFile:
    path: str  # relative to models/
    sha256: str  # of the final file (not of a zip it comes in)
    size: int
    url: str | None  # None = not hosted yet
    member: str | None = None  # file inside a zip download


FILES: tuple[ModelFile, ...] = (
    # CubiCasa detector v2 (models/cubicasa_v2/MODEL_CARD.md).
    # PLACEHOLDER: the hosting URL does not exist yet. Until it does, copy best.pt here by hand
    # (A3 / SS has it) and run `python models/fetch.py --check`.
    ModelFile(
        path="cubicasa_v2/best.pt",
        sha256="2093bef2b2322dbc23c402d7e7beafe00245d6e9144905b1cd54ed0eaef3337d",
        size=40_587_180,
        url=None,
    ),
    # EasyOCR (Apache-2.0) text detector and English recogniser, from the official releases.
    ModelFile(
        path="easyocr/craft_mlt_25k.pth",
        sha256="4a5efbfb48b4081100544e75e1e2b57f8de3d84f213004b14b85fd4b3748db17",
        size=83_152_330,
        url="https://github.com/JaidedAI/EasyOCR/releases/download/pre-v1.1.6/craft_mlt_25k.zip",
        member="craft_mlt_25k.pth",
    ),
    ModelFile(
        path="easyocr/english_g2.pth",
        sha256="e2272681d9d67a04e2dff396b6e95077bc19001f8f6d3593c307b9852e1c29e8",
        size=15_143_997,
        url="https://github.com/JaidedAI/EasyOCR/releases/download/v1.3/english_g2.zip",
        member="english_g2.pth",
    ),
)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def is_valid(f: ModelFile, base: Path = MODELS_DIR) -> bool:
    target = base / f.path
    return target.is_file() and target.stat().st_size == f.size and sha256_of(target) == f.sha256


def download(f: ModelFile, base: Path = MODELS_DIR) -> None:
    if f.url is None:
        raise RuntimeError(f"{f.path}: no download URL yet; copy the file into models/ by hand")
    target = base / f.path
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(target.suffix + ".part")
    with urllib.request.urlopen(f.url) as resp:  # fixed https URLs (FILES)
        data = resp.read()
    if f.member is not None:
        data = zipfile.ZipFile(io.BytesIO(data)).read(f.member)
    tmp.write_bytes(data)
    if hashlib.sha256(data).hexdigest() != f.sha256:
        tmp.unlink()
        raise RuntimeError(f"{f.path}: checksum mismatch after download")
    shutil.move(str(tmp), target)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true", help="verify only, download nothing")
    args = ap.parse_args(argv)
    ok = True
    for f in FILES:
        if is_valid(f):
            print(f"ok       {f.path}")
            continue
        if args.check:
            print(f"MISSING  {f.path} (absent or wrong checksum)")
            ok = False
            continue
        try:
            download(f)
            print(f"fetched  {f.path}")
        except Exception as exc:
            print(f"FAILED   {f.path}: {exc}")
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
