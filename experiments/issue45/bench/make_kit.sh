#!/bin/sh
# Build a self-contained benchmark kit (zip) from this repository.
#   sh experiments/issue45/bench/make_kit.sh [OUT_DIR]
# The kit holds only code, the public-domain text and (if present) the Intel
# reference results. No private audio or transcripts.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../../.." && pwd)
OUT=${1:-$PWD}
STAGE=$(mktemp -d)/vera-bench-kit
mkdir -p "$STAGE/code/experiments"
cp "$HERE/bench.sh" "$HERE/bench_run.py" "$HERE/gettysburg.txt" "$HERE/README.txt" "$STAGE/"
[ -f "$HERE/reference-intel.json" ] && cp "$HERE/reference-intel.json" "$STAGE/"
cp "$REPO/experiments/__init__.py" "$STAGE/code/experiments/"
(cd "$REPO/experiments" && tar cf - --exclude '__pycache__' --exclude 'bench' --exclude 'schemas' issue45) | (cd "$STAGE/code/experiments" && tar xf -)
mkdir -p "$STAGE/code/experiments/issue45/schemas"
for s in recognition-artifact-v1 alignment-artifact-v1 script-reconciliation-v1 port-refusal-v1; do
  cp "$REPO/contracts/$s.schema.json" "$STAGE/code/experiments/issue45/schemas/"
done
(cd "$(dirname "$STAGE")" && zip -qr "$OUT/vera-bench-kit.zip" vera-bench-kit)
echo "Kit written to $OUT/vera-bench-kit.zip"
