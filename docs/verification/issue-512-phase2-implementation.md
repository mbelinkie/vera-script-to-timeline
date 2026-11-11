# #512 Phase 2 — crash-safe diagnostic capture and separately gated #499 hooks

Phase 2 changes **no Mac state** and does not touch the shared #499 adopted
PR/worktree. The four #499 runner/host modules remain absent from `main` at the
#512 base. Production hooks are therefore carried as a **source-pinned patch**
for controlled integration by #499's owner; the #512 branch adds the standalone
writer and tests. The patch is **not** automatically installed or activated.

## New writer

`resolve_test_bench_diagnostic_journal.DiagnosticJournal` publishes the closed
v1 schema from phase 1 in the already-admitted **new** case/stage root, in
`diagnostics-v1/records/record-NNNNNN.json`. Each record is exclusive (`O_EXCL`,
`O_NOFOLLOW`, 0600), privately scoped (0700 owner directories), canonical,
bounded, independently validated, SHA-256 chained, and flushed with both
file and parent-directory `fsync`. A separate owner-only lock serializes
appenders. Record chains reject gaps, torn files, unexpected names, altered
case/phase/stage/pins, unknown versions, symlinks, foreign owners, and more
than 8192 records. The hard free-space floor is 256 MiB. There is no deletion,
truncation, repair or automatic retry of existing records.

If a record write/flush fails, the in-process writer is poisoned and must not
publish again. An **ambiguous** fully written record after fsync failure is not
treated as proof of any native outcome: the original one-use launch/stage or
carrier intent remains the replay barrier. On restart, a valid diagnostic
record is only explanatory evidence; it is never native authorization.
Logging failure **before** claim refuses native startup; failure **after**
claim preserves UNKNOWN even if the error record itself is impossible to write.

## Integration patch for frozen #499 runner

File: `issue-512-phase2-499-hooks.patch` (unified diff, three modules). Its
expected exact source is commit `91e260291ed279a3789e1022afc2e0250c2d5b0a`.
The patch instruments the original files without adding any native carrier:

- `resolve_test_bench_conductor_launch.py`: admission/currentness first,
  immutable preclaim diagnostic, original one-use launch intent, durable
  postclaim event, then the original full loop. Catch `BaseException` with
  bounded sanitized traceback while retaining the original
  `unknown-after-claim` launch result; a diagnostic failure never calls the
  native host again.
- `resolve_test_bench_campaign.py`: stage admission and claim events, stage
  target hash, and a single shared diagnostic journal passed to the original
  output driver. Only a claim fsynced by the original carrier enables running
  the stage. Failing or ambiguous logging cannot consume additional carrier
  slots; no stage retry helper is added.
- `resolve_test_bench_output.py`: before/after request preparation and native
  dispatch, independently authenticated carrier result, pre/post original
  host ingestion, render queue/start/poll/capture and terminal markers.
  `lastVerified` advances only **after original host-ingested receipt is
  checked**, and a signed native result must have status `complete`. Already
  ingested past actions update only the in-memory cursor, not an unbounded
  replay of diagnostic events each polling interval. Exceptions preserve
  the last ingested action and next pending action, **not** a signed M4 PASS.

**Adoption order:** controlled #499 owner first brings the #512 writer and
contract module into the original pinned #499 tree; checks the complete
source/currentness/actor provenance and any changes since the pinned commit;
then applies the three-module patch with `git apply --check` and verifies
focused/full gates on the resulting exact tree. If head has drifted, rebase
and review each hunk, never apply blindly or update frozen seventh case.
Do **not** run native case 8 under #512. #499 alone controls new authorization,
original adopted PR #474 and any fresh attempt.

## Fault-injection evidence

Tests in `tests/test_resolve_test_bench_diagnostic_journal.py` simulate
exclusive publication, cross-case collision, torn records, symlinks,
write failure, file fsync failure, directory fsync failure and no-free-space.
`tests/test_resolve_test_bench_phase2_overlay.py` reconstructs only the three
frozen source files in a temporary fixture, applies the patch, and executes
simulated launch and output action paths **without** Resolve/GUI/SDK. Checks:

- A deliberately failed postclaim `full_loop.start` yields durable exception
  class/message/frame evidence and the original UNKNOWN result; a second
  launch is refused by the original immutable claim.
- Failing diagnostics before claim prevents all native calls; failure after
  claim still yields authoritative UNKNOWN with zero native calls.
- Signed mock operations 0–4 and ingested `start_render` followed by an injected
  failure before `poll_render` produce an exception with `lastVerified=4`,
  `nextPending=5`, no native operation-5 intent, and zero new carrier calls.

These are **simulation/contract tests**, not an eighth native attempt, a Mac
read-only re-audit or verification of any raw original seventh-case file.
Phase 3 adds read-only report/inventory; Phase 4 independently checks Mac
evidence and integrates the new commit/patch with #499 before a new attempt.
