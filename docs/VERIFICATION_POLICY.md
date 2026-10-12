# Verification and review policy

Producer-approved 2026-10-12. Applies to VERA Script-to-Timeline owners,
reviewers, Testers and handoff/closure agents, including already-started tickets.
This replaces blanket reruns of the full gate at every agent handoff. It does
not waive a ticket's substantive criteria or separately required independent
execution, real-application evidence, contract-change approval or human judgment.

## Default order

1. Develop with focused tests and `npm run validate:fast`; run affected slow
   tests serially when their behavior changes. Compiler work keeps required
   byte-identical golden checks. If an older baseline lacks the accepted fast
   target, run existing focused checks; don't invent a weaker acceptance gate.
2. Perform required independent/Claude review before the final expensive run,
   using the candidate diff, criteria, frozen-boundary audit and fast evidence.
3. Fix findings; rerun affected checks and fast validation. Re-review the fix
   delta rather than restarting an unchanged whole-code review.
4. Obtain a complete passing `VITEST_MAX_WORKERS=1 npm run validate` against
   the final reviewed source and recorded inputs/environment. Reuse an existing
   qualifying pass if the checks below establish equivalence. One valid pass
   can serve implementation, independent review, handoff and closure; these
   labels alone do not require new runs.
5. Retain evidence and complete the ticket's actual acceptance process. A
   post-review source fix needs delta review and fresh applicable full evidence.
   There is no one-attempt limit and no permission to treat a failed run as green.

If a full run is already underway, let it finish and retain its result; don't
cancel and restart merely to change order. A finished qualifying pass from
before review remains usable when review makes no relevant changes. Review
may follow that existing pass; the preferred order avoids unnecessary future
runs, not useful evidence already collected.

## Evidence reuse: prove equivalence

Use ordinary retained logs and Git comparisons, not a new evidence service.
Before reuse, the receiving owner/reviewer records:

- Tested commit/source state, exact command, completed exit-zero result,
  required test inventory/counts and any skips. Required coverage cannot be
  skipped; failed, partial, killed or mismatched runs are not full passes.
- Relevant source, tests, configuration, lockfiles, generated files, fixtures,
  goldens and external-input identities/hashes match the delivered state.
  A clean Git comparison may establish unchanged tracked inputs; include
  untracked/ignored runtime inputs when the check consumes them.
- Toolchain and relevant execution profile match: Node/npm/uv/Python and
  applicable media tools, OS/architecture, worker settings and environment.
  Identify the retained logs and existing input/output hashes. A commit SHA
  alone does not establish equivalent runtime inputs or trustworthy evidence.
- Any post-test differences are listed and explained. Plan, receipt, README,
  instruction or evidence files are not exempt merely by extension/name.
  Prove they are unread by applicable generation, lint/type/test, dashboard,
  roadmap or packaging checks; otherwise rerun affected checks. Reuse full
  evidence only if unaffected coverage remains valid and changed check inputs
  receive fresh passing coverage. Uncertain impact requires a fresh full run.

Source/test/config/lockfile or toolchain/profile/input changes require new
applicable full evidence; lockfile repairs also require clean pinned install
checks. Accepted frozen changes still require their approved note. Review
findings fixed only in non-consumed documentation require diff/link/whitespace
checks, not another expensive suite. A documentation-only ticket that changes
no executable/check inputs uses those checks unless its criteria explicitly
require more.

Reusing results does not remove independent judgment. Reviewers inspect source,
assertions, acceptance coverage and evidence provenance themselves. Run focused
checks to reproduce a disputed claim or fill a gap. Rerun the full suite when
equivalence cannot be established, nondeterminism needs investigation, or the
ticket explicitly requires an independent full execution. Never claim a reused
result was personally rerun.

## Risk-proportionate review

- Mechanical documentation, metadata, workspace-link/lock consistency and
  narrow established fixes: focused diff-confinement, criteria, install/input
  consistency and evidence review. A small lockfile diff still invalidates
  prior install/full evidence; small does not mean exempt.
- Authorization/privacy, identity/hash handling, destructive actions, rational
  timing/compiler semantics, concurrency/recovery and media/Resolve boundaries:
  adversarial review of affected seams, negative cases and failure behavior.

Keep reviewers explicitly required by the issue or selected route. Claude
review remains required where the Producer requested it; depth is proportional
to risk, not an excuse to omit it. "No blocking findings" is a valid result.
Avoid manufactured criticism, unrelated cleanup and repeated full execution
without a concrete evidence gap. Manual design/listening judgments remain human;
real external capability claims still require actual runtime evidence.

## Intel-Mac execution and unchanged limits

Honor the current expensive-check coordinator/queue. Before a new full or
heavy test run, check for actual competing validation/pytest/media jobs and
wait for the existing owner's explicit release where a queue is established.
Read-only review can happen while waiting; it must not start competing tests.

Full acceptance still requires the local locked-toolchain gate. CI continues
unchanged; a CI pass is not yet an approved substitute for local acceptance.
CI equivalence/capacity and test-performance optimizations need separate
qualification. No timeout, assertion, test inventory, golden, required external
check, privacy boundary or approval gate is relaxed by this policy. Do not
repeat an unchanged resource/deadline failure indefinitely: retain the failure,
resolve host capacity or report a bounded blocker; failed runs remain failed.

This policy authorizes verification reuse, not merging, deployment, uploads,
issue-scope expansion, new dispatch or continuation past existing user gates.

