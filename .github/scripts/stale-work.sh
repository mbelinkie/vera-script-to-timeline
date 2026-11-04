#!/usr/bin/env bash
# Weekly stale-work check (replaces the Codex steward). Free; runs in Actions.
# Flags: branches with unmerged work (quiet 3-30 days) and no open PR, PRs idle for 3+ days,
# and issues closed in the last 14 days without a merged PR.
# Posts one comment on the "Weekly stale-work check" issue only when it finds something.
# Env: GH_TOKEN, GITHUB_REPOSITORY. DRY=1 prints instead of posting.
set -euo pipefail
R=${GITHUB_REPOSITORY:?}
DAYS=3
cutoff=$(date -u -d "-$DAYS days" +%Y-%m-%dT%H:%M:%SZ)
# Branches quiet for longer than 30 days were reported once on 2026-11-04;
# only newly stranded work is reported after that.
window=$(date -u -d "-30 days" +%Y-%m-%dT%H:%M:%SZ)
recent=$(date -u -d "-14 days" +%Y-%m-%dT%H:%M:%SZ)
report=$(mktemp)

open_heads=$(gh api "repos/$R/pulls?state=open&per_page=100" --jq '.[].head.ref')

# 1. Branches ahead of main, quiet for 3-30 days, with no open PR.
for page in 1 2 3; do
  gh api "repos/$R/branches?per_page=100&page=$page" --jq '.[].name'
done | sort -u | while read -r branch; do
  case "$branch" in main | vera-ci-queue-state) continue ;; esac
  grep -qxF "$branch" <<<"$open_heads" && continue
  info=$(gh api "repos/$R/compare/main...$(jq -rn --arg b "$branch" '$b|@uri')" \
    --jq '[.ahead_by, (.commits[-1].commit.committer.date // "")] | @tsv' 2>/dev/null) || continue
  ahead=${info%%$'\t'*}; last=${info#*$'\t'}
  if [ "$ahead" -gt 0 ] && [[ "$last" < "$cutoff" ]] && [[ "$last" > "$window" ]]; then
    echo "- Branch \`$branch\`: $ahead unmerged commit(s), last on ${last:0:10}, no open PR" >>"$report"
  fi
done

# 2. Open PRs with no activity for 3+ days.
gh api "repos/$R/pulls?state=open&per_page=100" \
  --jq ".[] | select(.updated_at < \"$cutoff\") | \"- PR #\(.number) idle since \(.updated_at[0:10])\(if .draft then \" (draft)\" else \"\" end): \(.title)\"" >>"$report"

# 3. Issues closed in the last 14 days with no merged PR that references them.
gh api "repos/$R/issues?state=closed&since=$recent&per_page=100" \
  --jq ".[] | select(.pull_request | not) | select(.closed_at >= \"$recent\") | select(.state_reason == \"completed\") | .number" |
  while read -r n; do
    merged=$(gh api "repos/$R/issues/$n/timeline?per_page=100" \
      --jq '[.[] | select(.event == "cross-referenced") | .source.issue | select(.pull_request.merged_at != null)] | length')
    closed_by_commit=$(gh api "repos/$R/issues/$n/events?per_page=100" --jq '[.[] | select(.event == "closed" and .commit_id != null)] | length')
    if [ "$merged" = 0 ] && [ "$closed_by_commit" = 0 ]; then
      echo "- Issue #$n was closed as completed but no merged PR references it" >>"$report"
    fi
  done

if [ ! -s "$report" ]; then
  echo "Nothing stale."
  exit 0
fi
body=$(printf 'Stale work found on %s:\n\n%s\n\nAgents: finish, merge or close these; Matthew does not need to act.' "$(date -u +%Y-%m-%d)" "$(cat "$report")")
if [ "${DRY:-}" = 1 ]; then
  echo "$body"
  exit 0
fi
title="Weekly stale-work check"
issue=$(gh api "repos/$R/issues?state=open&per_page=100" --jq ".[] | select(.title == \"$title\") | .number" | head -1)
if [ -z "$issue" ]; then
  issue=$(gh api "repos/$R/issues" -f title="$title" \
    -f body="A free weekly GitHub Action comments here when it finds stranded branches, idle PRs, or issues closed without merged work." --jq .number)
fi
gh api "repos/$R/issues/$issue/comments" -f body="$body" >/dev/null
echo "Reported on #$issue"
