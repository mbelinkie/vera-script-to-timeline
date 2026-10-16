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

# Invoke separately AFTER actual identity capture and independent target inspection.
invocation=$("$python" -B -c 'import json,sys,uuid; v=json.load(open(sys.argv[1])); i=v["invocationId"]; assert str(uuid.UUID(i))==i; print(i)' "$host/identity-authority.json")
result="$attempt/identity-evidence/result-$invocation.json"
hashes="$attempt/identity-evidence/hashes-$invocation.json"
result_sha=$("$python" -B -c 'import json,sys; print(json.load(open(sys.argv[1]))["resultSha256"])' "$hashes")
IFS= read -r -p 'Operator name: ' operator_name
printf '%s\n' 'Personally re-confirm: same saved disposable NONproduction current target, READ ONLY, External Scripting None, no concurrent UI/jobs.'
IFS= read -r -p 'Type CONFIRM to continue to the independent displayed-target acknowledgement: ' answer
[[ "$answer" == CONFIRM ]] || exit 1
"$python" -B -m vera_timeline_agent.workflow_v2_cli capability-authorize-from-identity \
  "$result" --result-sha256 "$result_sha" --acknowledge-result-sha256 "$result_sha" \
  --approval '/Users/matthewbelinkie/Library/Application Support/VERA/private-preparation/issue-145/advance-inputs/issue178-producer-cn178q1-approval.json' --operator "$operator_name" \
  --output "$host/capability-authority.json" --evidence-dir "$attempt/capability-evidence" \
  --confirm-displayed-target --confirm-saved-disposable-nonproduction \
  --confirm-read-only --external-scripting-none
"$python" -B -m vera_timeline_agent.workflow_v2_cli capability-request \
  "$host/capability-authority.json" --output "$host/capability-request.json"
printf '%s\n' 'STOP. Preserve identity lineage. Follow the granted #109 quit/archive/request/restart flow; reopen and confirm the SAME saved target within expiry.'
printf 'Request: %s\nEvidence: %s\n' "$host/capability-request.json" "$attempt/capability-evidence"
