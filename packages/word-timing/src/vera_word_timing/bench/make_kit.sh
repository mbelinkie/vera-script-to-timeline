#!/bin/sh
# Build a self-contained benchmark kit (zip) from this repository.
#   sh packages/word-timing/src/vera_word_timing/bench/make_kit.sh [OUT_DIR]
# The kit holds only the vera_word_timing package (with its contract copies),
# the public-domain text and the Intel reference. No private audio or transcripts.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
PKG=$(cd "$HERE/.." && pwd)
OUT=${1:-$PWD}
STAGE=$(mktemp -d)/vera-bench-kit
mkdir -p "$STAGE/code"
cp "$HERE/bench.sh" "$HERE/bench_run.py" "$HERE/gettysburg.txt" "$HERE/README.txt" "$STAGE/"
[ -f "$HERE/reference-intel.json" ] && cp "$HERE/reference-intel.json" "$STAGE/"
(cd "$(dirname "$PKG")" && tar cf - --exclude '__pycache__' --exclude 'bench' vera_word_timing) | (cd "$STAGE/code" && tar xf -)
(cd "$(dirname "$STAGE")" && zip -qr "$OUT/vera-bench-kit.zip" vera-bench-kit)
echo "Kit written to $OUT/vera-bench-kit.zip"
