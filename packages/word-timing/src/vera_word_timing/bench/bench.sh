#!/bin/sh
# VERA word-timing benchmark: one command on any Mac, nothing pre-installed.
#
#   sh bench.sh
#
# Everything (package manager, Python environments, models, caches, audio)
# goes into ./.bench next to this script. No admin password, no Homebrew, no
# changes elsewhere on the machine. Delete this folder to remove it all.
# Needs: macOS (Apple Silicon or Intel), internet, ~5 GB free, ~20-40 min.
# Result: bench-results.json in this folder (public test audio only).
set -eu

KIT=$(cd "$(dirname "$0")" && pwd)
W="$KIT/.bench"
mkdir -p "$W/bin" "$W/envs" "$W/downloads"
export MAMBA_ROOT_PREFIX="$W/mamba" HF_HOME="$W/hf" XDG_CACHE_HOME="$W/cache" \
  PIP_CACHE_DIR="$W/pip-cache" TORCH_HOME="$W/torch" MFA_ROOT_DIR="$W/mfa" \
  PIP_DISABLE_PIP_VERSION_CHECK=1 HF_HUB_DISABLE_TELEMETRY=1
START=$(date +%s)
log() { printf '\n== %s (%ss)\n' "$1" "$(( $(date +%s) - START ))"; }

verify() { # verify FILE ALGO EXPECTED
  got=$(shasum -a "$2" "$1" | cut -d' ' -f1)
  [ "$got" = "$3" ] || { echo "Checksum mismatch for $1: expected $3, got $got" >&2; exit 1; }
}

case "$(uname -s)-$(uname -m)" in
  Darwin-arm64)  MM_ARCH=osx-arm64; MM_SHA=ec2a072f028e1a7cf20f3e2e74d5a8127cf5a5f27636375b5359811565f4e5be ;;
  Darwin-x86_64) MM_ARCH=osx-64;    MM_SHA=1e71054bb3ac9a076e21f7ec48acfef536f9b3f1408f371a942784bf5ef83d8a ;;
  *) echo "This benchmark supports macOS only." >&2; exit 1 ;;
esac

log "1/6 package manager (micromamba 2.9.0)"
MM="$W/bin/micromamba"
if [ ! -x "$MM" ]; then
  curl -fsSL -o "$MM" "https://github.com/mamba-org/micromamba-releases/releases/download/2.9.0-0/micromamba-$MM_ARCH"
  verify "$MM" 256 "$MM_SHA"
  chmod +x "$MM"
fi

log "2/6 environments (MFA 3.4.3, tools, Parakeet)"
[ -x "$W/envs/mfa/bin/mfa" ] || "$MM" create -y -q -p "$W/envs/mfa" -c conda-forge \
  python=3.12 montreal-forced-aligner=3.4.3
if [ ! -x "$W/envs/tools/bin/python" ]; then
  "$MM" create -y -q -p "$W/envs/tools" -c conda-forge python=3.12 pip
  "$W/envs/tools/bin/python" -m pip install -q silero-vad==6.2.1 torch==2.2.2 torchaudio==2.2.2 \
    numpy==1.26.4 soundfile==0.14.0 onnxruntime==1.23.2 soxr jsonschema==4.25.1
fi
if [ ! -x "$W/envs/parakeet/bin/python" ]; then
  "$MM" create -y -q -p "$W/envs/parakeet" -c conda-forge python=3.12 pip
  "$W/envs/parakeet/bin/python" -m pip install -q onnx-asr==0.12.0 onnxruntime==1.23.2 huggingface-hub
fi

log "3/6 MFA models (english_us_arpa acoustic 3.0.0, dictionary 3.0.0, g2p 2.0.0)"
PM="$MFA_ROOT_DIR/pretrained_models"
[ -f "$PM/acoustic/english_us_arpa.zip" ] || "$W/envs/mfa/bin/mfa" model download acoustic english_us_arpa --version 3.0.0
[ -f "$PM/dictionary/english_us_arpa.dict" ] || "$W/envs/mfa/bin/mfa" model download dictionary english_us_arpa --version 3.0.0
[ -f "$PM/g2p/english_us_arpa.zip" ] || "$W/envs/mfa/bin/mfa" model download g2p english_us_arpa --version 2.0.0
verify "$PM/acoustic/english_us_arpa.zip" 256 d35ce271ded357d833d2f4b8d1041dc3748b9538567ba13f2c697f4e4126711b
verify "$PM/dictionary/english_us_arpa.dict" 256 e8c6c7b036ae2b7c78d2768b8dc6b1f9359175b842956d00b48c53c9c332e6b0

log "4/6 Parakeet TDT 0.6B v3 (int8 ONNX, pinned revision)"
"$W/envs/parakeet/bin/python" - <<'PY'
import hashlib, os, pathlib
from huggingface_hub import snapshot_download
path = pathlib.Path(snapshot_download("istupakov/parakeet-tdt-0.6b-v3-onnx",
                                      revision="8f23f0c03c8761650bdb5b40aaf3e40d2c15f1ce",
                                      allow_patterns=["*.int8.onnx", "nemo128.onnx", "vocab.txt", "config.json"]))
want = {"decoder_joint-model.int8.onnx": "eea7483ee3d1a30375daedc8ed83e3960c91b098812127a0d99d1c8977667a70",
        "encoder-model.int8.onnx": "6139d2fa7e1b086097b277c7149725edbab89cc7c7ae64b23c741be4055aff09",
        "nemo128.onnx": "a9fde1486ebfcc08f328d75ad4610c67835fea58c73ba57e3209a6f6cf019e9f"}
for name, sha in want.items():
    if hashlib.sha256((path / name).read_bytes()).hexdigest() != sha:
        raise SystemExit(f"Checksum mismatch for {name}")
print("Parakeet model verified at", path)
PY

log "5/6 public-domain test audio (LibriVox: The Gettysburg Address, 2:41)"
MP3="$W/downloads/gettysburg.mp3"
[ -f "$MP3" ] || curl -fsSL -o "$MP3" "https://archive.org/download/gettysburg_address_librivox/gettysburg_address_lincoln_64kb.mp3"
verify "$MP3" 1 211d2bc10bf97ca6fc39ef20aefe1f843d9d36a0

log "6/6 benchmark"
"$W/envs/tools/bin/python" "$KIT/bench_run.py" --kit "$KIT" --work "$W" --mp3 "$MP3" \
  --setup-seconds "$(( $(date +%s) - START ))"
