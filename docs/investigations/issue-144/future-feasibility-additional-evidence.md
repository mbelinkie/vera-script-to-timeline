# Feasibility evidence supplement

Read-only primary-source check after the initial risk prompt was sent. No code
or roadmap change. The initial note's statement that #63 "owns follow-up" needs
qualification: that specific follow-up is already closed/Done and also found
no adequate selection. The primary supported-path risk remains unresolved.

## 2026-09-07T13:59:23Z

https://github.com/mbelinkie/vera-script-to-timeline/issues/63#issuecomment-5571727925

Implementation is ready for acceptance review.

Evidence: Commit a001b94 on branch codex/issue-63-ctc-disagreement records the aggregate report at https://github.com/mbelinkie/vera-script-to-timeline/blob/codex/issue-63-ctc-disagreement/docs/investigations/issue-63-ctc-disagreement.md . Result: no adequate selection. Synthetic-only calibration tested greedy and forced spans, score thresholds, boundary-disagreement thresholds, and required or optional lexical agreement; no nonempty rule met the 40/120 ms timing gates. The fail-closed result accepts 0 of 439 words and explicitly rejects or leaves unaligned 100 percent, failing the 5 percent coverage gate. Before rejection, 54 three-way lexical agreements had median onset/offset 36/37 ms, p95 124/175 ms, and 7 unsafe boundaries above 120 ms. All 14 Producer-marked events are explicit: 4 abandoned phrases remain in Parakeet, 9 are explicitly missing or ambiguous, and the previously omitted repeated-speech occurrence is preserved as a timed CTC disagreement without repairing Parakeet text. Twenty-eight CTC-only spans remain explicit, including 1 partial-word candidate and 27 unmatched-audio spans; hints are not truth claims. Full model/input/adapter/parameter/rule fingerprints and detailed words/spans/timings remain private; published evidence is aggregate only. Full-source CTC runtime was 1.034 s initialization, 46.117 s inference, 50.037 s total, and 941752320 bytes peak memory on x86_64; retained Parakeet runtime was 3.657 s initialization, 1.895 s VAD, 19.485 s recognition, and 1013415936 bytes peak memory. No Apple Silicon claim is made. Checks: 11 private unit tests passed; final offline synthetic and real runs had zero comparable greedy-text parity failures; privacy/permission checks passed; frozen-boundary diff was empty; pinned Node 24.19.0/npm 11.17.0 npm run validate passed with 141 contract tests, 1 tooling test, 6 progress tests, 23 roadmap tests, and 175 Python tests. Producer checklist: (1) open the local Run A Issue 63 packet and scoring/evaluation-06/aggregate-safe.json; expect no adequate selection and null rather than zero timing metrics; (2) open evaluation-private.json eventLedger; expect exactly 14 explicit events and the single repeated event absent from Parakeet but retained as a timed lexical CTC disagreement; (3) inspect modelFingerprints, targetArtifact, and ctcArtifact; expect separate unchanged hypotheses, full private fingerprints, no reference repair, and no interpolated edit boundary; (4) open runs/real-02/safe-summary.json; expect 32 completed segments, zero comparable parity failures, runtime and peak memory; (5) review the aggregate branch report; expect no private material or out-of-scope production/Research/take/edit/Apple-Silicon claim. Accept with exactly: Accept #63 no adequate selection. Otherwise report the first failing step. Proposed follow-up, not started: a separate boundary-first acoustic-estimator investigation on independently human-timed natural-speech calibration data, with license, size, runtime, and packaging justification before any model acquisition.

## 2026-09-07T14:06:26Z

https://github.com/mbelinkie/vera-script-to-timeline/issues/63#issuecomment-5571812773

Accepted by Producer.

Acceptance evidence: Producer explicitly responded Accept #63 no adequate selection after the Issue 63 review handoff. This accepts the aggregate no-adequate-selection result in commit a001b94 and the retained local evidence; it does not approve any production integration or proposed follow-up.

## 2026-09-07T14:40:52Z

https://github.com/mbelinkie/vera-script-to-timeline/issues/63#issuecomment-5572261207

Post-acceptance verification correction (issue remains closed/Done): while preparing the external LLM handoff, two private-harness defects were found, fixed, regression-tested, and rerun in fresh immutable offline outputs. CTC-only insertion hints now use local edit-alignment neighbors, changing only the non-truth hint split from 1 partial / 27 unmatched to 2 partial / 26 unmatched (28 total unchanged). The exact-agreement rule now correctly rejects substitutions; the corrected exhaustive 30,976-rule calibration still found zero nonempty timing-safe candidates. The no-adequate-selection result, fail-closed rule, word/disagreement counts, real timing diagnostics, and event outcomes are unchanged. Thirteen private tests now pass. The sanitized exact protocol, full aggregate results, limitations, corrections, and requested external-evaluator response are documented in commit bfbe1d9: https://github.com/mbelinkie/vera-script-to-timeline/blob/codex/issue-63-ctc-disagreement/docs/investigations/issue-63-llm-evaluation-handoff.md

## Exact preservation scope

Product Spec §6.14 and Slice10.4 require carrying compatible recognized Resolve
work into a new timeline and protecting unprovable/orphaned work, not claiming
all arbitrary effects are semantically observable or transferable. The first
probe should therefore test one bounded untouched graded/effected row across a
neighbor duration change and reorder, with native/render evidence. Unknown or
incompatible attachments must be explicit, and the old timeline remains intact.
A failed tested fresh-compilation/copy approach cannot prove every possible
preservation mechanism impossible: qualify the exact supported mechanism.

## Presenter implementation boundary

#45 still requires a locally running selected profile with actual word timing;
it explicitly excludes a hidden hosted or cue-only fallback. #63 acceptance of
a no-adequate-selection experiment is not acceptance of that production ability.
This risk should be kept distinct from temp narration marks and application
lock/export state. No new provider acquisition or investigation is authorized
by this assessment.
