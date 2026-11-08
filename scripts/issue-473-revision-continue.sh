#!/bin/zsh
# Continue only the already-observed, source-pinned A picture boundary.
# Every individual host command retains its own durable one-use intent and
# refuses a different case, conflicting choice or unsanctioned audio change.
set -euo pipefail
root="$HOME/.local/state/vera/issue-473-studio-05"
source_root="$root/pinned-code"
script="$HOME/.local/state/vera/issue-473-studio-01/checkout/scripts/issue-473-revision-stage.py"
export PATH="$HOME/.local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
export PYTHONPATH="$source_root/python"
cd "$source_root"
if [[ ! -f "$root/run/revision/evidence-receipt.json" ]]; then
  print -u2 -- 'Original authenticated observation has not completed; refuse to continue.'
  exit 2
fi
for action in inspect accept-inference propose accept-proposal submit; do
  print -- "original_revision_step_start $action"
  .venv/bin/python "$script" "$action"
  print -- "original_revision_step_completed $action"
done
