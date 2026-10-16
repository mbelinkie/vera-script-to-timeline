# Claude engineering frontier review — full-suite performance

Advisory review, 2026-10-12. Claude Opus (`claude-opus-5-5`), xhigh;
session `dadb4e00-76ba-4aa8-a4cc-03245fb5147f`. Tools disabled. Packet included
public #184/#144/#35 bodies, #184's plan/per-test measurements and accepted
composition, WI-flow and omission-generation test source. No new benchmark,
test run, source modification or frozen-test approval occurred.

This note retains the useful review conclusions rather than adopting them.
Counts and timings below are the #184 calibration baseline, not the present
suite's required counts. A source-based hypothesis is not a measured root cause.

## Findings and smallest next checks

1. **The missing measurement is inside each test.** The TSV combines setup,
   call and teardown. Fixture setup called as a normal function inside a test
   remains call time, so pytest durations do not distinguish synthetic input
   creation, Node/compiler children, codecs/probes, hash/evidence analysis and
   polling. The supplied cost concentration is real; the dominant mechanism
   remains unmeasured.

   Claude proposes a bounded profile of four existing cases: a generation
   pre-provider refusal, a no-omission preparation refusal, an audio-evidence
   structural refusal and a compile/package reference. Retain plain wall time
   and separately profile setup, process counts/waits, Python self-time and
   sleeps. Profiler overhead must be calibrated; do not claim the proposed
   experiment duration before measuring it. Run only after coordinator release.

2. **Repeated omission setup may be expensive, but sharing it is risky.**
   The generation, decisions, preparation and composition suites repeatedly
   construct equivalent-looking setup. Claude estimated a rough 14-minute
   ceiling from minimum per-case costs, explicitly not a forecast. Those costs
   include each case's own operations; profiling must establish actual reuse.

   Copying prepared trees can invalidate absolute-path/hash/identity bindings.
   Same-path snapshot restoration also risks stale leases/nonces, shared fake
   counters, changed metadata and cross-test state. Do not adopt that technique
   or the claim that it is the only viable option without isolation proof.
   Any accepted-test/helper change needs an approved change note and failure-
   detection parity, not merely an unchanged green JUnit set.

3. **Cache synthetic inputs before considering product/output caching.**
   Audio-evidence tests show a fairly uniform ~1.2-second floor in the baseline.
   If profiling attributes it to deterministic test-side PCM construction,
   immutable input bytes could be reused while each test gets fresh writable
   JSON/state/files. Never cache codec results, verification or mutable receipts
   just to lower runtime. Claimed ~50-second savings are an unmeasured hypothesis.

4. **Replay verification is deliberate coverage.** Existing cases replay
   decide/generate/rebuild/promote, assert stable receipts and unchanged side-
   effect counters/pointers, and deliberately tamper with retained bytes.
   Skipping fresh verification to make replay fast would undermine the boundary
   the suite proves. Preserve the real CLI/process path and the repeated tamper
   checks; optimization must keep them sensitive to the same regressions.

5. **Node startup is not yet demonstrated to dominate.** An accepted compile-
   plus-package case is only a few seconds on the supplied baseline. Explaining
   a ~55-second setup by startup would require many repeated calls; count them
   before introducing persistent workers or compilation caches. Those changes
   have environment, boundary-pin and subprocess-coverage consequences.

## Important limitations and corrections

- Timing differences between the issue's older measurement and the #184 plan
  do not establish a statistical 15% noise floor; they may involve different
  source revisions/workloads. Use repeated same-source controlled measurements.
- The 419/237 Python counts describe #184's frozen calibration, not a forever-
  fixed inventory. Present-source comparison must use present collected IDs.
- Differences between #180-branch and #184/main test counts are not evidence
  that accepted tests were dropped. Verify baselines, installed features and
  test identities before making that claim.
- Fixture helpers and product implementations were outside the packet. All
  setup, cache and spawn interpretations require checking those callers.
- Python profiling/audit hooks and proposed library behavior were not verified
  against primary documentation/runtime in this review.

## Recommended bounded follow-up (not launched)

One measure-first hotspot investigation, then only demonstrated low-risk
optimization. Prefer immutable synthetic-input generation if it is actually
hot. Preserve required review, test inventory/assertions, per-test isolation,
real process/media and replay coverage, frozen deadlines and byte goldens.
Use a producer-approved note before accepted helper/test changes. Do not reopen
closed #184 or create a parallel testing platform; #196 separately owns cloud
acceptance qualification and does not solve these CPU costs.

Sources: public issues [#184](https://github.com/mbelinkie/vera-script-to-timeline/issues/184),
[#144](https://github.com/mbelinkie/vera-script-to-timeline/issues/144),
[#35](https://github.com/mbelinkie/vera-script-to-timeline/issues/35);
`docs/plans/issue-184-fast-validation.md`,
`docs/investigations/issue-184/python-durations.tsv`,
`tests/test_issue144_composition.py`, `tests/test_issue144_wi_flow.py`,
`tests/test_issue144_omission_generation.py` in the inspected #193 worktree.
