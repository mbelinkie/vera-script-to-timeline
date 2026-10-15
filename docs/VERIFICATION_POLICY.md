# Verification and review policy

Producer-approved 2026-10-12; qualified cloud scope activated 2026-10-12
(#196). Applies to VERA Script-to-Timeline owners,
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

### Producer review and waiting rules (2026-10-15)

Every ticket requires a separate adversarial Claude CLI review with read-only
tools and no unauthorized private inputs. Retain the candidate revision/diff,
prompt, result and finding dispositions. Review before final expensive testing;
fix findings and review the fix delta as needed. No blocking findings is a valid
result. An earlier Claude authoring conversation is not this review. If Claude
is unavailable, rate-limited, unauthenticated or produces no usable review, stop
at that gate and ask the Producer whether review may be skipped for that exact
issue/revision. Never substitute another reviewer or self-waive the gate.

After initial inspection and the first substantive check, report a rough
remaining active-work range, confidence and main uncertainty. If a range lacks
support, name unresolved work and the next reassessment checkpoint instead.
Notify the Producer promptly of material changes or likely multi-session
expansion. Separate active work from Producer/external waits; there is no
arbitrary 24-hour threshold.

For unattended tests or queue waits expected to take at least ten minutes,
retain a durable job/log/exit status or queue-owner record and a reassessment
checkpoint. Confirm one recurring 15-minute thread heartbeat, tell the Producer
the next check, then end the active turn completely. Do no active polling,
log-tail, monitoring-helper or other work during that wait. Check once per
wake-up and end again if still running. Cancel the heartbeat on completion,
failure or blocker. A heartbeat must never launch another suite or steal a queue
slot. Missing results or stalled progress past the checkpoint require a report,
not indefinite waiting or unauthorized termination. If durable execution or
scheduling is unavailable, stop and ask how to proceed.

### Existing execution limits

Honor the current expensive-check coordinator/queue. Before a new full or
heavy test run, check for actual competing validation/pytest/media jobs and
wait for the existing owner's explicit release where a queue is established.
Read-only review can happen while waiting; it must not start competing tests.

Full acceptance still requires the local locked-toolchain gate, except within
the qualified cloud scope below. Other CI equivalence/capacity and
test-performance optimizations need separate qualification. No timeout, assertion, test inventory, golden, required external
check, privacy boundary or approval gate is relaxed by this policy. Do not
repeat an unchanged resource/deadline failure indefinitely: retain the failure,
resolve host capacity or report a bounded blocker; failed runs remain failed.

## Qualified cloud substitution (activated 2026-10-12, #196)

Activated under Producer instruction, relayed by the coordinator: "I approve
196 if Claude is happy with it". The #196 owner reported GO. The receipt and
evidence are in
[docs/verification/issue-196/GO-NO-GO.md](verification/issue-196/GO-NO-GO.md).
Within this scope, one complete passing `Validate` run on GitHub-hosted
`ubuntu-24.04` replaces the Intel-Mac rerun of
`VITEST_MAX_WORKERS=1 npm run validate`. Every condition must hold. If any
fails, use the local full gate. Never retry until something looks green.

1. **Validate from accepted `main`.** In a clean checkout of accepted `main`,
   run:

   ```sh
   node scripts/cloud-evidence-validate.mjs --repo mbelinkie/vera-script-to-timeline \
     --run <id> --attempt <n> --event pull_request --pr <N> --delivered <candidate-rev> \
     --profile docs/verification/issue-196/cloud/profile-qualified.json \
     --scope excluding-media-sensitive
   ```

   Exit 0 is required. Use `--event push` without `--pr` for a branch that has
   no PR, and prefer the PR run when one exists. Use the default
   `--scope full` only while the run's runner image is in the profile.
2. **Check the report.** It must name profile digest
   `1d6b3c41d0bfbba1c9e012796a1067ebba7944e6a8615ecf96e77444071257c7`.
   `manifest.source` must be the run artifact, never `local-file`. The tested
   tree must equal the delivered tree on the ticket's required integration
   baseline. Every attempt on that source must be green or carry a retained,
   reviewer-audited disposition.
3. **Check eligibility.** The candidate must not change the profile or
   approval files, `scripts/cloud-evidence*`, the workflow, any package or
   Python manifest, lockfiles, or tool configs. The validator rejects changed
   controls itself. Such changes take the local full gate, plus requalification
   if they should stay cloud-eligible. The diff must touch no media-processing
   path (FFmpeg/FFprobe callers, rendering, probing); those changes keep their
   affected slow tests, run serially on the Mac's installed tools.
4. **Keep the other gates.** Focused/fast local checks, required
   independent/Claude review, frozen-boundary and generated-currentness
   audits, and post-merge integration checks all remain required. CI evidence
   never certifies #174's Mac media-tool qualification, real Resolve runtime,
   private media, transcripts, provider calls, or human listening, visual and
   design judgment.
5. **Requalify, never self-certify.** Hosted image rollovers suspend
   media-sensitive scope automatically, and pure-logic scope is unaffected.
   Restoring full scope, or changing any control, needs two new complete
   same-tree runs, a new profile digest and a new approval. A green run on a
   changed gate is never its own approval.

This policy authorizes verification reuse, not merging, deployment, uploads,
issue-scope expansion, new dispatch or continuation past existing user gates.

