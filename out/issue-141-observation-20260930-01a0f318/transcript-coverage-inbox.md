# Task ID: Issue 141 — proposed Inbox placeholder

Title: Define and enforce complete Resolve transcript coverage before transcript-based reconciliation

Classification: Missing exact duplicate; partial overlap with #141, #45, and #123.

Outcome: When VERA relies on Resolve transcripts for reconciliation or word/cut analysis, design and Producer-accept a fail-closed coverage gate covering every source clip and timeline occurrence in scope. Missing, empty, errored, unsupported, unstable, stale, or mismatched coverage must block transcript conclusions and must never imply word deletion or inaudibility.

Scope: coverage enumeration; source-versus-timeline-proxy identity; ordinary/nested getter state; no-speech/no-audio distinction; transcript freshness/version binding; explicit automatic-transcription consent and retention policy; safe evidence and refusal semantics.

Exclusions: production implementation, contract/schema changes, provider selection, automatic transcription, Resolve mutation, media export, and program-routing claims.

## Dependencies

- Blocked by #141

## Routing and acceptance

Tentative routing: `model:sol`, `effort:high`

Acceptance: Producer

## Unresolved decisions

Unresolved: valid no-speech/no-audio versus missing getter; freshness/version keys and invalidation; local/cloud consent and retention for automatic transcription; source-item versus timeline-occurrence coverage granularity.

## Duplicate audit

Duplicate audit: No exact open/closed issue found. #141 is the external observation and adopted conditional requirement; #45 owns VERA word-timed transcription/alignment; #123 owns reconciliation design. None currently defines this all-clips Resolve coverage gate. No issue was created or modified.

Evidence searched: GitHub issues in `mbelinkie/vera-script-to-timeline`, open and closed, using `transcript`, `transcription`, `word timing`, `coverage`, `all clips`, `Resolve transcript`, and `word-level` searches; full bodies reviewed for #141, #123, #45, #124, and #49 on 2026-10-01.


## Acceptance criteria

- [ ] Producer accepts a bounded coverage gate requiring Resolve transcription of every clip when this analysis path is enabled, with explicit treatment of non-speech/no-audio clips.
- [ ] Missing, incomplete, errored or stale coverage visibly blocks transcript-based conclusions and never implies deleted words.
- [ ] The design identifies observable source/timeline identity and freshness evidence, and states any unobservable limits from #141.
- [ ] Remediation identifies how VERA enforces coverage; transcription requires explicit product consent and never happens silently.
- [ ] No production implementation or contract change is included in this design issue.
