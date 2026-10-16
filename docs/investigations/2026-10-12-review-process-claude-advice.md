# Review-process consultation with Claude — 2026-10-12

Status: advisory findings only. No gate, acceptance authority, issue, runtime
configuration or dispatch policy changed. The Producer requested this review
because hour-long validation on the Intel Mac can make basic tickets take
several hours.

## Consultation and evidence limits

Asked the installed Claude Code CLI through the existing Claude-account login.
Requested model alias `opus`, effort `high`; reported model
`claude-opus-5-5`, session `a3a2d50a-8269-47d6-a166-fcd583dd2218`.
Tool access was disabled, MCP configuration empty, and execution advisory-only.
Claude received a sanitized process description, exact command/configuration
summaries, measured #184 timings, and #180/#193 retained checkpoints. No private
audio, script, credentials or per-word evidence was supplied. It did not
independently inspect the repository or run tests.

Sources were inspected locally, including committed `origin/main` at
`5d59b2ad560aa18f96554b71fe34ee5b7f30dfed`. The primary checkout is an older
branch with unrelated dirty work; its package scripts are not the current gate
definition. Historical checkpoints below are not live board-status assertions.

## Verified starting facts

- Committed AGENTS requires fast validation during development, relevant slow
  tests when their code changes, and a full gate for acceptance, CI and agent
  handoffs. Full gates must not compete with other heavy tests. Source:
  [AGENTS at inspected baseline](https://github.com/mbelinkie/vera-script-to-timeline/blob/5d59b2ad560aa18f96554b71fe34ee5b7f30dfed/AGENTS.md).
- The fast gate already exists: all generated/lint/type/TypeScript checks,
  then non-slow Python tests with two workers. Full validation retains every
  Python test serially. CI installs pinned dependencies plus FFmpeg and runs
  full validation on push and pull requests. Sources:
  [package scripts](https://github.com/mbelinkie/vera-script-to-timeline/blob/5d59b2ad560aa18f96554b71fe34ee5b7f30dfed/package.json),
  [CI definition](https://github.com/mbelinkie/vera-script-to-timeline/blob/5d59b2ad560aa18f96554b71fe34ee5b7f30dfed/.github/workflows/validate.yml).
- #184 measured one passing full run at 3030.992 seconds (50:31), versus
  three passing fast runs at 97.877–103.491 seconds. Full coverage: 419 Python
  and 274 TypeScript/tooling tests; fast coverage: 237 Python and the same 274
  TypeScript/tooling tests. All had zero skips. On that baseline, 53 slow
  row-narration/composition cases consumed 2459.978 seconds (~41 minutes),
  approximately 81% of full-gate wall time. These are retained baseline
  measurements, not new benchmarks or promises for other branches. Source:
  [#184 plan and measurements](https://github.com/mbelinkie/vera-script-to-timeline/blob/70e8435de69bee09f2266ca9470dee790be73aae/docs/plans/issue-184-fast-validation.md),
  [run records](https://github.com/mbelinkie/vera-script-to-timeline/blob/70e8435de69bee09f2266ca9470dee790be73aae/docs/investigations/issue-184/runs.json),
  [per-test durations](https://github.com/mbelinkie/vera-script-to-timeline/blob/70e8435de69bee09f2266ca9470dee790be73aae/docs/investigations/issue-184/python-durations.tsv).
- #180's retained `2890060` checkpoint has three failed full attempts at
  unchanged CLI deadlines, despite focused passes. A stopped Python run was
  correctly not treated as passing. This demonstrates a reliability concern,
  not proof that every failure is hardware-only. Source:
  [#180 retained local checkpoint](</Users/matthewbelinkie/.codex/worktrees/6484/VERA Script to Timeline/docs/verification/issue-180/automated.md>)
  at `28900607d146643c1771ab011d45878b4232e7dd` (recorded as unpushed).
- #193's local retained checkpoint is a package-lock-only workspace repair;
  clean pinned `npm ci`, generated-currentness and diff checks pass, while its
  full gate and Claude review await the expensive-check slot. Source:
  [#193 retained local checkpoint](</Users/matthewbelinkie/.codex/worktrees/6432/VERA Script to Timeline/docs/verification/issue-193/automated.md>)
  on `codex/issue-193-workspace-lock`.
  A small diff is not justification to ignore lockfile-wide install effects.

## Claude's advice, assessed

Claude's central recommendation is to preserve regression coverage while
reducing repeated execution and hardware contention. Repeat-run counts per
ticket are not yet measured; this is a process risk supported by the wording,
not a finding that every ticket repeats an identical gate.

1. **Review before the final full gate.** Develop with focused and fast tests;
   review the candidate; fix findings; delta-review and rerun affected checks;
   then collect one complete full pass on the final reviewed source. This can
   avoid paying for a full run immediately before a review-driven code fix.
2. **Reuse valid evidence across unchanged handoffs.** Implementer, independent
   reviewer and closure owner should verify a retained pass rather than
   automatically repeat it. A reviewer can inspect assertions and reproduce a
   disputed focused check without owning another whole-suite run. Independence
   means independent judgment; a prescribed independent execution, suspected
   nondeterminism or missing provenance still warrants rerunning.
3. **Match review depth to risk.** A lockfile-only repair needs diff confinement,
   install/lock consistency and exact-revision evidence scrutiny. Authorization,
   rational timing, recovery and media identity deserve broader adversarial
   review. A reviewer may find no blocking defect; unrelated cleanup and a
   manufactured criticism quota add no assurance.
4. **Qualify CI as the full-pass venue for eligible tickets.** Pure logic and
   mechanical tooling/lockfile changes are candidates for focused local checks
   plus an exact-revision full CI pass. Verify capacity, test inventory/skips,
   toolchain and platform differences first. Mac/Resolve observations and
   platform-sensitive media/timing/subprocess behavior remain separately
   required. Current policy must be explicitly amended before substitution;
   an existing failing or absent CI run is not acceptance evidence.
5. **Profile the dominant composition tests before optimizing.** Attribute
   their time to process startup/compilation, media work, fixture creation,
   polling and I/O. Repeated setup, one-time CLI compilation, immutable shared
   fixtures and safe worker counts are hypotheses to measure—not established
   root causes or approved changes. Any optimization retains test discovery,
   assertions, exact timing/golden semantics and zero suppressed failures.

The simplest proposed flow is:

`focused development → fast checks → independent review → fixes/delta checks → final full pass → acceptance/closure`

## Evidence reuse and invalidation proposal

A commit SHA alone is insufficient. Match the tested source/configuration and
test inputs, lockfiles, toolchain, relevant execution settings and OS/architecture,
exact command, completion status and retained log provenance. Use ordinary
retained evidence first; this does not call for a new evidence platform.

- Source/test/configuration/lockfile changes invalidate the applicable pass.
  Review fixes require affected checks, delta review and final full evidence.
- Allow reuse after documentation/evidence-only changes only when the changed
  paths are proven irrelevant to every applicable check. Some docs are inputs
  to dashboard, roadmap or generation checks; "docs-only" is not a blanket
  exemption. Verify the difference from the tested revision explicitly.
- Environment or external-input changes require new applicable qualification;
  CI evidence does not become Mac evidence by matching a source hash.
- Failed, aborted, stopped, skipped or mismatched runs never become a complete
  passing gate. Frozen tests/deadlines cannot be changed opportunistically to
  make the current ticket pass.

These proposals require approval where they alter current acceptance/handoff
rules. No already-required reviewer, external qualification, change note or
Producer judgment has been waived.

## Practical next step and bounded follow-ups

Claude recommends first counting full runs, identical-evidence repeat runs and
queue waiting from retained #174/#180/#184/#191/#193 evidence. That would size
the duplication savings before changing policy; this consultation did not do
that audit. Avoid another sprawling workflow program.

If adopted, keep follow-ups bounded: (1) review-order/evidence-reuse policy,
(2) profiling the composition-test hotspot, (3) CI substitution qualification
and separately assessed CLI timeout reliability. No tickets were created here.

Potential savings: each avoided run costs roughly 50 minutes on the measured
#184 baseline. Halving its composition-test cost would save roughly 20 minutes
per full run, but that is arithmetic on a hypothetical improvement, not a
measured optimization or a delivery estimate.

No new test runs, CI jobs, board mutations, code changes or existing-agent
messages were performed. Documentation whitespace checks are the only local
verification for this findings note.
