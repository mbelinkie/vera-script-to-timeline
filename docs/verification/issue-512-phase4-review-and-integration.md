# #512 Phase 4 — independent review, Mac read-only postmortem, integration handoff

## Scope, provenance, and independent verdict

Reviewed the entire isolated #512 change set against issue #512, including the
pure diagnostic contract, O_EXCL/fsynced writer, read-only incident reporter,
the **unapplied** frozen-#499 three-module integration patch, and their tests.
Implementation source and tests as independently reviewed: commit
`c91ac3840bab78f87c7808ee0321d7648d26263e` (based on `3852a5c7`).
The subsequent documentation-only phase-4 commit and exact release SHA are
in the Conductor's final handoff. **Review verdict: approve with a corrected
test gap, not native acceptance.**

Independent review observations:

- A preclaim journal failure denies startup; after a one-use claim, journal or
  native errors preserve the original UNKNOWN and cannot initiate a second
  carrier. The separate patch adds events around original host verification
  and ingestion; it never treats a diagnostic as a signed native or M4 receipt.
- Writer locks, private directories, exclusive filenames, canonical closed
  records, SHA-256 chaining, fsync, quotas and fail-poisoning are intentional
  fail-closed boundaries. A partially written log stays partial and **never**
  becomes permission to replay. No previous signed evidence is rewritten.
- The reader uses owner-private descriptor-relative no-follow reads, validates
  exact identity and chain order, refuses malformed/cross-case records, exposes
  only sanitized hashes for MOV/PCM, and makes no SDK, GUI or verifier calls.
  Its claimed proof layers are explicitly distinct from independent proof.
- Review found **one test gap**: the old clock test combined PID change and
  monotonic rollback. Inverting the monotonic guard still passed. Added a
  same-PID rollback test, committed as `c91ac384`, and repeated the mutation:
  the test now fails as required (negative duration is rejected by the
  original implementation). Redaction equality, cross-case identity and
  poisoned-writer guard mutations also fail the focused tests in isolated
  scratch copies. No original #499 files were edited for these mutations.

## Independent Mac postmortem — NO EFFECTS

On 2026-11-11, read-only Mac Bridge commands inspected the **original**
seventh case `vera499phase26h2426ee095c73443d` (Studio 21.1.1.10).
This was a fresh check of the original Mac evidence, **not merely the
historical map**. We examined retained read-only scripts before invoking
them. `phase26h-readonly-verify-op.py` uses original
`carrier.status` and `verify_native_result` in the frozen #499 source
tree, never a native worker, GUI, Resolve SDK, or fresh M4 operation.

| Original native sequence | Original action | Independently rechecked |
| --- | --- | --- |
| 0 | construct | authenticated `complete` |
| 1 | save_reopen | authenticated `complete` |
| 2 | capture_pre | authenticated `complete` |
| 3 | queue_render | authenticated `complete` |
| 4 | start_render | authenticated `complete` |
| 5 | poll_render | **original request and result absent** |

Read-only `phase26h-status-readonly.py` also showed launch claimed,
`unknown-after-claim`, original runner not matched, and no M4 stage
receipt: pristine `awaiting_operator`, edited/revision/rebuild `pending`.
Thus **0/4 signed M4 receipts**, strict #312 unrun, original case permanently
spent. Operation 5's absence identifies the **first missing evidence
boundary**, **not** the root cause. The swallowed exception remains unknown.

Source and actor provenance compared directly against the original Mac files:

| Frozen field | Independently observed SHA-256 or commit |
| --- | --- |
| Frozen source checkout HEAD | `91e260291ed279a3789e1022afc2e0250c2d5b0a` |
| Source graph / pointer | `cfa1407c14572d1b5135bd1b5ac0b60d7523862054aa4514c30bbdfeaf71bee3` |
| Helper source manifest / original actor field | `aa2ec2334eaf7ab048c3915bb31da87e072b61629283266058c49f88172c5c5e` |
| Installed helper binary | `76cbbbad909bef0fa9f123126c171824e2cb408ff68f855de994489dbb138a7f` |
| Frozen launch actorPin canonical JSON **with newline** | `0671b06a0cafcf15723084e1bc9fb5a9508f70e07c3822269c32f064d951433a` |
| Existing phase26h pointer file | `af593351675d6c47e388a05abfae01d56fdd456a2139cff70295f329f51ee09e` |
| Existing phase26h bootstrap file | `31bcfd02533cd932006825acb1c13b35a5b7a9636f2fd793da8aff4ac02eba16` |

The helper actor digest requires the canonical JSON trailing newline; a
SHA-256 of JSON without that newline is **not** the source-pinned actor.
No native actions, project changes, signatures, media reads, new cases, or
retries were produced by the audit. The observed signed/verifier originals
remain read-only on the Mac; the Linux reporter's earlier map-only mode
continues to label its own result as historically sourced, not freshly
authenticated by that CLI.

## Gates and limits

- Current implementation's full `npm run validate:fast` executed on
  `b72f7afa` before the phase-4 regression-test-only commit:
  contracts PASS; TS lint PASS; TS types PASS; TS fast tests PASS;
  Ruff PASS; mypy PASS (377 Python files). Python fast suite:
  **3058 passed, 43 skipped, 17 failed**, so **the full gate is NOT green**.
  The 17 failures are in untouched narration, word timing, campaign/queue,
  and issue-208 tests; exact log is
  `.pipeline/512/validate-fast-phase4.log`.
- An **independent unmodified baseline checkout** at original base `3852a5c7`
  ran the same fast-Python selector with **eight workers and work stealing**:
  **2984 passed, 43 skipped, 44 failed**. Eleven of the current head's exact
  17 failing node IDs also failed on that baseline, and seven of the current
  failures reproduced in a separate baseline-only, selected-test run. The six
  remaining current-head failures did **not** reproduce in the baseline's
  parallel run; all are in unchanged queue/campaign or issue-208 tests and
  no #512 diagnostic module is imported by those tests. They are not proven
  baseline reproductions; concurrent/resource-sensitive behavior is a
  plausible explanation, not an asserted root cause. All exact failure lists
  and outputs are preserved in
  `.pipeline/512/phase4-baseline-{reproduction,full-python}.log`. This
  explicitly leaves **the full current-head gate non-green**; the PR's
  independent CI status must determine merge eligibility.
- Following the phase-4 test fix, focused contract/writer/report/overlay
  tests: **48 passed**; targeted Ruff check/format PASS; targeted mypy
  **4 source files PASS**; negative clock, privacy, case-identity and
  fail-stop mutations detected; `git diff --check` clean. These checks
  do not erase the full-gate failures. CI on the separate #512 PR is a
  Conductor follow-up, not yet confirmed here.

## Controlled handoff; #499 stays blocked

1. **#512 Conductor:** create the separate #512 PR from
   `zodex/512-test-bench-durable-native-failure-diagno` using the final
   phase-4 handoff. Do not assume it is merged or CI green; preserve the
   full-gate caveat and attached local logs.
2. **#499 owner/Conductor exclusively:** compare source and actor pins on
   **its** adopted PR #474 branch with the original frozen
   `91e26029`; integrate the #512 contract, journal, reporter and
   `docs/verification/issue-512-phase2-499-hooks.patch` in a controlled
   review. The patch targets original launch/campaign/output files and is
   **not installed by #512**. Reconcile drift hunk by hunk;
   `git apply --check` first, then focused/fail-stop tests and current-source
   gates. Rebuild/re-pin any newly changed helper/actor graph and test
   actual diagnostics on a **new** authorized case only. Do not touch the
   seventh case or silently change old manifest, launch intent, or journal.
3. **#499 attempt 8:** remains **blocked** until controlled integration,
   independent currentness/CI review and a **separate explicit Producer
   authorization** for a fresh sacrificial eighth M4 case with new targets
   and one-use action. #512 itself authorizes no native operations.
4. **#510/#511:** incident report fields (case, source/actor/target pins,
   first missing boundary, last verified claim, SHA-only evidence references,
   UNKNOWN) may be included as non-authoritative diagnostics in exact-thread
   terminal events. Do not turn a report into `VERIFIED`, a signed M4
   receipt, or evidence that origin-thread ACK/auto-wake has occurred.
   #510/#511 and then #473/#312 remain separately gated.

## Explicit exclusions

No eighth native run; no effects, GUI, SDK, source-package or signer mutation;
no writes to #499 shared adopted PR #474; no new native PASS, strict #312
PASS, #510 ACK, or claim that the seventh failure's root cause is known.
