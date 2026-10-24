---
name: vera-roadmap-coordination
description: Coordinate VERA Script-to-Timeline work through its GitHub Project, including routing labels, claims, dependencies, acceptance and closure, under the lightweight 2026-10-16 workflow.
---

# VERA Script-to-Timeline roadmap coordination

The GitHub Project configured in `.github/vera-roadmap.json` is the live
roadmap: scope, status, priority, dependencies, ownership and routing. The
product spec, `DECISIONS.md` and accepted plans hold durable product truth.
`AGENTS.md` and `docs/VERIFICATION_POLICY.md` define how work is done; this
skill covers the board mechanics. Keep it light: the Producer wants speed and
should only see product and taste questions.

## Flow

1. Inspect: `npm run roadmap -- inspect <issue>`.
2. Dependencies: one `- Blocked by #123` or `- Blocked by owner/repo#123` line
   per prerequisite under `## Dependencies`, or `None`. Parent/sub-issue
   hierarchy does not imply order. `npm run roadmap -- ready <issue>` promotes
   to `Ready` once every dependency is closed and `Done`.
3. Claim with the running profile, task and branch:
   `npm run roadmap -- claim <issue> --model <model> --effort <effort> --task <task> --branch <branch>`.
   If the labels clearly do not fit the work, fix them with `gh issue edit`,
   note why in a comment, and claim. No steward approval is needed.
4. Build, test, review and merge per `AGENTS.md` and
   `docs/VERIFICATION_POLICY.md`. Before any Claude CLI review, read and follow
   `docs/CLAUDE_REVIEW_PLAYBOOK.md`, including for in-flight issues with older
   review instructions. Evidence is the PR plus CI result.
5. Out-of-scope discoveries go to Inbox as new issues; small, low-risk fixes in
   files already being touched may just be done.
6. Close according to the acceptance field (below), then re-inspect to confirm
   Closed and Done.

## Acceptance field

Choose by the judgment needed, not by issue size.

- `Automated` (default): anything an agent can check objectively, including
  contract, schema, fixture, sidecar and other technical decisions. The owning
  agent closes it after merge with green CI:
  `npm run roadmap -- complete <issue> --accepted-by Automated --evidence <PR link>`.
- `External`: needs real application or service evidence (Resolve, Fusion, a
  provider). The agent runs the check itself where tooling allows and records
  one result comment. It asks the Producer only for steps he must physically
  do.
- `Producer`: only for taste and product judgments (look, sound, timing,
  workflow feel, product direction). Finish everything else first, then give
  a short checklist with what to open, what to judge and the exact reply
  wanted. Leave it `In review` until he answers.

A bare agent claim of success without a merged PR and green CI is not
evidence. No issue closes, under any acceptance class, until its work is
merged into `main`. Closing an issue does not authorize starting the next one.

For audio timing or word-boundary review, follow
`docs/AUDIO_TIMING_REVIEW_WORKFLOW.md` regardless of acceptance class.

Use a separate design-first issue only when the design itself is a product or
taste decision. Technical design is decided and built in the same issue.

## Routing labels

Each Ready issue has exactly one `model:*` and one `effort:*` label (the claim
command checks this).

- Luna low/medium: mechanical docs, formatting, fixture updates, small tests,
  renames, generated output, narrow fixes.
- Terra medium/high: bounded multi-file features, standard debugging, UI,
  established adapters, ordinary integration tests.
- Sol high/xhigh/max: architecture, contracts, migrations, privacy,
  concurrency/recovery, destructive change, cross-boundary ambiguity.

Pick the cheapest profile that fits; relabel when reality differs.

## Steward boundary

Scheduled steward passes may tidy scope, labels, dependencies and stale claims.
Each pass also checks delivery. It flags any closed issue whose PR is not
merged into `main`, and any branch with unmerged work older than three days.
It comments on the issue (reopening it if closed), so stranded work is found
in days, not weeks.
They do not reprioritize goals, implement code, close implementation issues or
dispatch work. A direct Producer invocation of the personal
`$vera-roadmap-dispatch` skill may start exactly one Ready issue. Stay quiet
when nothing meaningful changed.

Optional, never blocking: after a closure, the steward may post the claimed
task's final session token total, and may add a genuinely unresolved
engineering risk to `docs/POSSIBLE_ISSUES_FOR_ASTRA.md`.
