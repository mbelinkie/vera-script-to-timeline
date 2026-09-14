# Issue 123 design evidence status

## Exploratory artifact only

The checked-in `timeline-to-script-reconciliation.html`, its checker, and the
screenshots under `evidence/` were created before the Producer reframed the
workflow. They are retained as exploratory design input only.

They are not acceptance evidence because they incorrectly present script-only
changes for inbound approval, treat protected Resolve work as review-only rather
than durable Resolve-only script rows, and end by creating a new timeline rather
than reconciling the script.

## Acceptance authority

Acceptance requires a new Claude Design artifact in the existing
`VERA design feedback` project. The artifact must follow
`claude-resolve-to-script-reconciliation-brief.md`, reuse the accepted S05 design
wherever possible, and preserve the accepted S01–S05 artifacts unchanged.

No Claude prompt has been sent and no successor artifact exists yet. Issue #123
must remain **In progress** until the exact prompt is approved, Claude's design
questions are resolved, the artifact is created, and required evidence is
retained. It may then move to **In review** for explicit Producer acceptance.

## Current retained inputs

- #14 accepted S03 plan, prompts, and Producer acceptance at commit `11cef62`.
- #58 accepted S05 plan, briefs, and Producer evidence at commit `7eb71ca`.
- The pre-reframing local prototype at commit `3f8a095`.
- The revised issue plan and exact unsent Claude brief in this directory.

No production code, contract, fixture, golden file, generated type, or accepted
Claude artifact is changed by this preparatory work.
