#!/bin/sh
# Host runner: builds the image if missing, runs the contract CLI in Docker (CPU, linux/amd64).
# Usage: run_qwen.sh --segments S.json --audio-dir DIR --out R.json [--variant NAME]
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
DATA="${VERA_QWEN_CACHE_HOME:-$HOME/.local/share/vera/word-timing-v2}"
IMG=${VERA_QWEN_IMAGE:-vera-wt2-qwen:2}
mkdir -p "$DATA/cache/hf"
docker image inspect "$IMG" >/dev/null 2>&1 || docker build --platform linux/amd64 -t "$IMG" "$HERE"
abs() { (cd "$1" && pwd); }
while [ $# -gt 0 ]; do
  case "$1" in
    --segments) SEG=$2; shift 2;;
    --audio-dir) AUD=$2; shift 2;;
    --out) OUT=$2; shift 2;;
    --variant) VAR=$2; shift 2;;
    *) echo "unknown arg $1" >&2; exit 2;;
  esac
done
SEGD=$(abs "$(dirname "$SEG")"); OUTD=$(abs "$(dirname "$OUT")"); AUDD=$(abs "$AUD")
exec docker run --rm --platform linux/amd64 ${VERA_QWEN_LANGUAGE:+-e VERA_QWEN_LANGUAGE="$VERA_QWEN_LANGUAGE"} \
  -v "$SEGD":/in/seg:ro -v "$AUDD":/in/audio:ro -v "$OUTD":/out -v "$DATA/cache/hf":/cache/hf \
  "$IMG" --segments "/in/seg/$(basename "$SEG")" --audio-dir /in/audio \
  --out "/out/$(basename "$OUT")" ${VAR:+--variant "$VAR"}
