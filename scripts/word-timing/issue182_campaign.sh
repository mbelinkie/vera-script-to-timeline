#!/usr/bin/env bash
# Issue #182 real-Polly timing campaign driver.
#
# Usage:  scripts/word-timing/issue182_campaign.sh CACHE_DIR OUT_DIR
# Env:    LIVE=1       actually call Amazon Polly (default: preflight only)
#         LEDGER=PATH  override the cost ledger (default: ~/Library/Application
#                      Support/VERA/polly-campaign/ledger.json)
#         VOICE=ID     voice profile (default: the campaign default, Matthew)
#         SKIP_MFA=1   skip the local MFA reference step
#
# Rows (public text, tests/data/issue182/campaign/):
#   baseline: "... crosses the harbor, slowly, toward ..."  (omission target "slowly")
#   revised : same block id, version 2, comma-free whole-row regeneration.
# Each row has a v1 ScriptDocument (generation) and a v2 ScriptDocument holding the
# same block id/text/tokens (frozen tokens for measurement).
#
# Idempotent: generation reuses the cache (cache hits cost and record nothing), and
# measurement/omission/MFA outputs are rewritten deterministically under OUT_DIR.
# Without LIVE=1 no provider call is ever made and --confirm-provider-call is
# never passed; preflight prints the estimate and ledger and tolerates the
# "needs confirmation" exit.
#
# Exact live commands this script runs when LIVE=1 (shown for review):
#   python -m vera_timeline_agent.narration.campaign generate \
#     --doc tests/data/issue182/campaign/baseline.v1.script-document.json --cache "$CACHE" \
#     --aws-data-policy provider_terms_accepted --confirm-provider-call
#   python -m vera_timeline_agent.narration.campaign generate \
#     --doc tests/data/issue182/campaign/revised.v1.script-document.json --cache "$CACHE" \
#     --aws-data-policy provider_terms_accepted --confirm-provider-call

set -euo pipefail

if [ "$#" -ne 2 ]; then
  sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' >&2
  exit 64
fi
CACHE=$1
OUT=$2
ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DATA="$ROOT/tests/data/issue182/campaign"
cd "$ROOT"
mkdir -p "$CACHE" "$OUT"

campaign() { uv run --frozen python -m vera_timeline_agent.narration.campaign "$@"; }
extra=()
[ -n "${LEDGER:-}" ] && extra+=(--ledger "$LEDGER")
[ -n "${VOICE:-}" ] && extra+=(--voice-profile "$VOICE")

generate() { # ROW ; prints generate output to OUT/ROW.generate.txt and stdout
  local row=$1 live=${LIVE:-0} rc=0 flags=()
  [ "$live" = 1 ] && flags+=(--confirm-provider-call)
  campaign generate --doc "$DATA/$row.v1.script-document.json" --cache "$CACHE" \
    --aws-data-policy provider_terms_accepted \
    ${extra[@]+"${extra[@]}"} ${flags[@]+"${flags[@]}"} \
    >"$OUT/$row.generate.txt" || rc=$?
  cat "$OUT/$row.generate.txt"
  # Preflight-only: exit 64 (USAGE) just means "live call needs confirmation".
  if [ "$live" != 1 ] && [ "$rc" -ne 0 ] && [ "$rc" -ne 64 ]; then return "$rc"; fi
  if [ "$live" = 1 ] && [ "$rc" -ne 0 ]; then return "$rc"; fi
  return 0
}

if [ "${LIVE:-0}" = 1 ]; then echo "== 1/2. generate (LIVE: real Polly calls)"; else echo "== 1/2. generate (preflight only; set LIVE=1 for real Polly calls)"; fi
for row in baseline revised; do
  echo "-- $row"
  generate "$row"
done

# Asset key = BLOCK_ID/ASSET_ID, parsed from the generate report line
# "block=<id> revision=N asset=<id> generated|reused ...".
asset_key() {
  sed -n 's/^block=\([^ ]*\) revision=[0-9]* asset=\([^ ]*\) \(generated\|reused\).*/\1\/\2/p' \
    "$OUT/$1.generate.txt" | head -n 1
}

if [ "${LIVE:-0}" != 1 ] && ! grep -q '^block=' "$OUT/baseline.generate.txt" 2>/dev/null; then
  echo "Preflight only: no cached assets yet; stopping before measurement."
  echo "Set LIVE=1 (after reviewing the estimate above) to generate and measure."
  exit 0
fi

echo "== 3. measure"
for row in baseline revised; do
  key=$(asset_key "$row")
  [ -n "$key" ] || { echo "no asset for $row (generation failed?)" >&2; exit 1; }
  mkdir -p "$OUT/$row"
  campaign measure --cache "$CACHE" --asset "$key" \
    --block "$DATA/$row.v2.script-document.json" --out "$OUT/$row"
  echo "$key" >"$OUT/$row/asset-key.txt"
done

echo "== 4. omission envelope for \"slowly\" (baseline)"
base_asset=$(cut -d/ -f2 "$OUT/baseline/asset-key.txt")
campaign omission \
  --evidence "$OUT/baseline/narration-measurements/$base_asset.boundary-evidence.json" \
  --token slowly --out "$OUT/baseline/omission-slowly.json"

if [ "${SKIP_MFA:-0}" != 1 ]; then
  echo "== 5. MFA reference (local, needs micromamba env 'mfa')"
  for row in baseline revised; do
    key=$(cat "$OUT/$row/asset-key.txt")
    asset=${key#*/}
    uv run --frozen python scripts/word-timing/mfa_reference.py \
      --measurement "$OUT/$row/narration-measurements/$asset.measurement.json" \
      --wav "$CACHE/v1/assets/$key/narration.wav" \
      --out "$OUT/$row/mfa-report.json"
  done
fi
echo "Done. Outputs under $OUT"
