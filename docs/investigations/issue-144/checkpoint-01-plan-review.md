# Issue 144 — Claude checkpoint 1: plan before implementation

Review the [published bounded plan](https://github.com/mbelinkie/vera-script-to-timeline/issues/144#issuecomment-5973780301),
also committed as `d055f90` on `codex/issue-144-roundtrip-harness`.
This checkpoint contains no implementation, new frozen data, native Resolve
action, transcript generation, real-script preparation or real run.

## Confirmed setup and checks

- #144 revalidated Open/Ready, Automated, Size L, exact Sol/xhigh labels, no
  claim, and #34/#35/#131/#141 Closed/Done. Claimed by this actual task after
  the Producer-authorized ordinary branch setup.
- Clean committed baseline is `9c8973de6b02eb89cb57a03c0bd50480af73f9e1`.
  Accepted #34 and #35 implementation bytes match their source commits and
  their integrations are ancestors; exact hashes are in the plan.
- `python3 docs/investigations/issue-141/verify-publication.py` passed:
  5,670 records verified, 5,530 sanitized text records, zero native actions.
- Locked bootstrap succeeded using Node24.19.0/npm11.17.0 and uv0.12.5/
  Python3.12.14: `npm ci`, `uv sync --frozen`. Existing dependency advisories
  remain with #142; locks/dependencies are unchanged.
- Planning only is committed and pushed. Focused new tests and full validation
  have not yet been run. No integrated or real-run success is claimed.
- Initial remaining forecast: 6–12 active-work hours, low confidence, likely
  multi-session; reassess after the first proposal→decision→rebuild test.

## Questions for adversarial technical review

1. **Canonical mapping:** v1 permits text anchors but requires
   `timingOverrides: null`. Can a unique compiler-confirmed anchor map support
   the bounded +25-frame linked move and 25-frame end trim without quietly
   changing spoken order, losing coverage, shortening unrelated source edits
   or implying general frame-bound support? Which preflight requirements must
   #148 satisfy? If this is impossible for a required positive, identify the
   precise Producer decision or contract-change blocker rather than substitute
   an all-refused test.
2. **Rendered omission:** assess the actual W1 linked-cut output and independent
   audio measurements, source word-support manifest, render receipt, snapshots
   and publication hashes. Does consuming these retained records support only
   the intended bounded Charlie deletion, with complete relevant 399-frame/
   766,080-sample edited output and A1/A2/A3 routes? Picture-only/residual speech
   must preserve text. Do not use source/subtitle/missing-transcript inference.
   Identify missing freshness, routing, partial-edge or attribution gates.
3. **Executable rebuild:** the plan requires a new canonical script produced
   by decisions and new verified narration bytes/timing/dependencies before
   rebuilding. Specify any missing deterministic seam needed so #148/#145 can
   execute it without a manually rewritten script JSON or paid synthesis.
   Check token identity, quoted anchors, versions, audio preservation and
   canonical compiler validation together.
4. **Build boundary and versions:** #35 has no real stage adapters; #34 creates
   a new project and verifies pristine assembly, not edited occurrence ancestry.
   Does the proposed injected WI seam safely reuse these exact implementations?
   Check actual target/UID/source binding and the split between Studio21.1.0/14
   move/trim evidence and WI21.1.1.10 omission evidence. Do not infer current-build
   support or a three-edit live run from mixed historical lanes.
5. **Safety/recovery:** identify holes in stale decisions, equal-read/ABA limits,
   local overlap prevention, duplicate/unknown IDs, changed/offline source bytes,
   immutable replay, interrupted native stages and promotion only after verified
   fresh rebuild. No automatic repeated native creation or prior-baseline loss.
6. **Acceptance:** are the test/runbook/evidence requirements sufficient for
   Automated #144 while leaving actual real-script acceptance with #145 and
   full production reconciliation with #101–#104? Flag unresolved executable
   prerequisites or product decisions explicitly.

Review is read-only. Return ranked actionable findings with source file/section,
failure scenario, required correction and whether each blocks implementation.
Do not change code, contracts, roadmap state or Resolve; do not dispatch work.
