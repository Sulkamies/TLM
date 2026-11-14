#!/usr/bin/env bash
# One-time setup on a fresh Verda GPU VM (Ubuntu). Run from the repo folder:
#     bash train/setup_vm.sh
# Installs Python deps, downloads CubiCasa5K (5.5 GB), verifies it, unzips it.
set -euo pipefail

DATA="${DATA:-$HOME/data}"
URL="https://zenodo.org/records/2613548/files/cubicasa5k.zip?download=1"
MD5="0ce0b203d1e3c125b51087b219bd23b9"
SUDO=""; [ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "== system packages"
$SUDO apt-get update -qq
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq \
    python3-venv python3-pip unzip wget tmux libgl1 libglib2.0-0
nvidia-smi

echo "== python environment (~/venv)"
python3 -m venv "$HOME/venv"
# shellcheck disable=SC1091
source "$HOME/venv/bin/activate"
pip install -q --upgrade pip
pip install -q "ultralytics>=8.3" pillow easyocr

echo "== dataset"
mkdir -p "$DATA"
if [ ! -f "$DATA/cubicasa5k.zip" ]; then
    wget -q --show-progress -O "$DATA/cubicasa5k.zip" "$URL"
fi
echo "$MD5  $DATA/cubicasa5k.zip" | md5sum -c -
if [ ! -f "$DATA/.unzipped" ]; then
    unzip -q "$DATA/cubicasa5k.zip" -d "$DATA"
    touch "$DATA/.unzipped"
fi
echo "dataset folders:"; ls "$DATA"

python - <<'PY'
import torch
ok = torch.cuda.is_available()
print("torch", torch.__version__, "| CUDA available:", ok, "|", torch.cuda.get_device_name(0) if ok else "NO GPU")
PY
echo "== done. Next: source ~/venv/bin/activate"
