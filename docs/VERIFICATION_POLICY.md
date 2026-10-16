# Verification and review policy

Adopted by the Producer on 2026-10-16 ([D-0016](../DECISIONS.md)). This
replaces every earlier version of this policy, including the 2026-10-12
local-full-gate rules, the #196 qualified-cloud-substitution procedure, the
expensive-check queue, the long-test wake-up procedure and Claude-review
waivers.

VERA is a one-person project and the Producer is not a developer. The goal is
to move fast, catch real breakage cheaply, and fix bugs forward. Checks exist to
find problems, not to produce paperwork.

## The checks, in order

1. **While working.** Run focused tests for what you changed, then
   `npm run validate:fast`. That runs generated-contract currentness, all lint
   and type checks, all TypeScript tests and the non-`slow` Python tests on two
   workers, in a few minutes. If you changed code that `slow` tests cover, run
   only those test files, for example
   `uv run --frozen pytest tests/test_issue174_real_media.py`. When a change
   crosses the TypeScript/Python boundary or touches a shared helper, run the
   tests on both sides of that boundary early; that is where late failures
   have come from.
2. **Review.** For any issue that changes code, get one adversarial review of
   the diff from the Claude CLI (read-only tools) before merging. Fix the real
   findings. Small follow-up fixes do not need another review. Documentation-
   or metadata-only changes skip review. If the CLI is unavailable, say so in
   the PR and carry on; no waiver is needed.
3. **Full suite in the cloud.** The GitHub Actions `Validate` workflow runs the
   complete `npm run validate` on every pull request and push to `main`.
   Standard runners are free for this public repository. A green `Validate` check on the PR
   **is** the full regression gate. Do not run the full `npm run validate` on
   the Producer's Mac: it takes one to three hours, occupies the machine and
   duplicates CI.
4. **Merge.** Bring the branch up to date with `main`, then merge when local
   fast checks pass and the PR's `Validate` check is green. An issue is not
   done until its work is merged into `main`. Do not watch CI. Push, then do other work or end the turn and come
   back. If CI fails, reproduce just the failing tests locally, fix and push.
5. **Real-application checks.** Only when the issue changes DaVinci Resolve,
   Fusion or media behaviour that CI cannot exercise. Keep them short and
   targeted. Run them yourself through the available tooling where you can.
   Batch any step that needs the Producer's hands, eyes or ears into one short
   checklist.

## After merge

If `main` goes red, or a bug shows up later, open a bug issue and fix forward.
Do not reopen or retroactively block the original issue. Revert only when
`main` is unusable.

## What counts as evidence

The pull request: its diff, a short description of what changed and how it was
tested, and the CI result. For External or Producer issues, add one comment
with what was checked in the real application and the outcome. Nothing else is
required.

No longer required: evidence-equivalence proofs, input inventories or hash
lists, JSON receipts or evidence bundles, qualification audits, cloud-evidence
validator runs, profile digests, frozen-boundary audits, re-running checks at
handoffs, re-reviewing unchanged code, or Producer waivers for anything in this
policy. Existing evidence tooling such as `scripts/cloud-evidence-*` may stay
in the repository, but nothing has to use it.

## Keep doing

- Never claim something passed when it did not, and never weaken an assertion
  just to get green. If a test is wrong or obsolete, fix or delete it and say
  why in the PR.
- Compiler golden files must still match. When output changes on purpose,
  update the goldens in the same PR and say why.
- Keep the suite fast. Prefer small unit tests; add at most one end-to-end test
  per feature. Mark any test that renders or probes real media, repeatedly
  starts external processes, or takes more than about five seconds with
  `@pytest.mark.slow`. If `npm run validate:fast` creeps past about five
  minutes on the Mac, file an issue to speed it up.
- Only one agent drives Resolve on the Mac at a time.
- Anything irreversible in the real world (deleting, uploading or sharing the
  Producer's media or the research project's data) still happens only through
  the product's own flows.
