#!/usr/bin/env bash
# Usage: run_charsiu.sh --segments F --audio-dir D --out F [--variant V]
# Paths must lie under ~/.local/share/vera/word-timing-v2 (mounted at the same path).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
DATA="${VERA_WT_DATA:-$HOME/.local/share/vera/word-timing-v2}"
IMG=vera-wt2-charsiu:1
mkdir -p "$DATA/cache/hf"
docker image inspect "$IMG" >/dev/null 2>&1 || docker build --platform linux/amd64 -t "$IMG" "$HERE"
exec docker run --rm --platform linux/amd64 -v "$DATA:$DATA" -v "$DATA/cache/hf:/cache/hf" "$IMG" "$@"
