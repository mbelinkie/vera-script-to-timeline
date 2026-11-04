#!/usr/bin/env bash
# One adversarial Claude review of this branch's diff against origin/main.
#
#   npm run review -- notes.md           # Opus, high effort (default)
#   npm run review -- notes.md --small   # Sonnet, medium: <150 lines, one module, well tested
#
# notes.md is 5-10 lines: the goal, what changed, what you tested and could not
# test, and the 2-3 places you are least sure about. Triage the findings
# yourself (fix, or one-line reason it is wrong) and list them in the PR body.
set -euo pipefail
notes=${1:?usage: npm run review -- <notes.md> [--small]}
model=opus effort=high
if [ "${2:-}" = --small ]; then model=sonnet effort=medium; fi

git fetch -q origin main
base=$(git merge-base origin/main HEAD)
exclude=(':!**/package-lock.json' ':!**/uv.lock' ':!**/*.golden*' ':!**/generated/**')
lines=$(git diff "$base"...HEAD -- . "${exclude[@]}" | wc -l)

{
  cat <<'EOF'
You are an adversarial reviewer. Find defects that would cause wrong
behaviour, data loss, crashes, races, or broken contracts in this diff.
Ignore style, naming, and nits. Before reporting a finding, confirm it by
reading the relevant code; drop anything you cannot tie to a concrete
failing input or sequence.

Output at most 8 findings, most severe first, each as:
[severity: high|medium|low] path:line — defect — concrete failure scenario
— suggested fix (one line)
No preamble, no summary, no praise. If nothing survives, output exactly:
NO FINDINGS
EOF
  echo
  cat "$notes"
  echo
  if [ "$lines" -gt 3000 ]; then
    echo "## Changed files (diff too large to inline; read the riskiest files)"
    git diff --stat "$base"...HEAD -- . "${exclude[@]}"
  else
    echo '## Diff'
    echo '```diff'
    git diff "$base"...HEAD -- . "${exclude[@]}"
    echo '```'
  fi
} | claude -p \
  --model "$model" --effort "$effort" \
  --tools "Read,Grep,Glob" \
  --strict-mcp-config \
  --disable-slash-commands \
  --settings '{"disableAllHooks": true}' \
  --no-session-persistence
