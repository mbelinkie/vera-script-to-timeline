#!/bin/bash
set -euo pipefail
umask 077
# HELD: run personally only after the coordinator's exact installation/runtime grant.
# This host helper never installs a plugin, selects a target, or calls Resolve.
repo='/Users/matthewbelinkie/.codex/worktrees/3754/VERA Script to Timeline'
python="$repo/.venv/bin/python"
release='/Users/matthewbelinkie/.codex/worktrees/3754/VERA Script to Timeline/out/issue208/release-r2'
attempt='/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation/issue-208/operator-attempt-01'
host="$attempt/host"
cd "$repo"
"$python" -B - <<'PY'
import hashlib, json
from pathlib import Path
from vera_timeline_agent.target_identity_v2 import ti_source_pins
from vera_timeline_agent.workflow_v2_cli import _verify_release
m=json.loads(Path('docs/verification/issue-208/operator/handoff.json').read_text())
assert ti_source_pins(Path(m['repositoryRoot']))==m['repositorySourcePins'], 'source drift'
p=_verify_release(Path(m['releaseRoot']))
assert hashlib.sha256(p.read_bytes()).hexdigest()==m['releaseSha256'], 'release drift'
PY

IFS= read -r -p 'Exact visible current project name: ' project_name
IFS= read -r -p 'Exact visible current timeline name: ' timeline_name
IFS= read -r -p 'Operator name: ' operator_name
printf '%s\n' 'Confirm: already SAVED, disposable NONproduction current target; READ ONLY; External Scripting None; no concurrent UI/jobs.'
IFS= read -r -p 'Type CONFIRM to personally issue identity authority: ' answer
[[ "$answer" == CONFIRM ]] || exit 1
mkdir -p "$host"
"$python" -B -m vera_timeline_agent.workflow_v2_cli identity-authorize \
  --release "$release" --installed-root '/Library/Application Support/Blackmagic Design/DaVinci Resolve/Workflow Integration Plugins' \
  --approval '/Users/matthewbelinkie/.codex/worktrees/3754/VERA Script to Timeline/docs/verification/issue-207/acceptance.json' --operator "$operator_name" \
  --project-name "$project_name" --timeline-name "$timeline_name" \
  --output "$host/identity-authority.json" --evidence-dir "$attempt/identity-evidence" \
  --confirm-saved-disposable-nonproduction --confirm-read-only --external-scripting-none
"$python" -B -m vera_timeline_agent.workflow_v2_cli identity-request \
  "$host/identity-authority.json" --output "$host/identity-request.json"
printf '%s\n' 'STOP. Preserve authority/request hashes. Follow the granted #109 manual installation and one-launch flow.'
printf 'Request: %s\nEvidence: %s\n' "$host/identity-request.json" "$attempt/identity-evidence"
