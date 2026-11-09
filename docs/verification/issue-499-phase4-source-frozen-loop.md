# #499 Phase 4 — source-frozen completion of original #473 Test Bench PR #474

**State: source code and injected tests only. No Phase-4 GUI attempt, native
mutation, MOV rendering, PCM decoding, external provider call or #312
acceptance has occurred.** This document describes an implementation for one
separately authorized **new** sacrificial campaign in Phase 5. The previously
retained original PR head `daec386bdccd243402dc3d358dbd19b783d1a318`,
the original Codex branch, Resolve targets, operation IDs and receipts have
not been replaced, replayed or amended. The Conductor alone owns PR checkpoint
pushes and final promotion. This worktree must not independently push, merge,
close issues or alter PR #474.

## Fixed, bounded workflow

1. The Conductor first prepares a **new, unique root and two real disposable
   targets** with `resolve_test_bench_fresh_setup.py`. The approved source
   package, original #312 six preparation receipts and three original
   narration assets are reauthenticated by the existing preflight. An old
   source-sealed pristine or source-graph-incompatible campaign is **not** a
   candidate for recovery. No new target is inferred from a name or fabricated.
2. An independently obtained **case-specific Producer instruction** must be
   represented by a private canonical JSON record with schema
   `vera.test-bench-473-case-specific-authority/v1`, the exact new config SHA,
   Phase-4 frozen Git commit, the current proof source-graph SHA, both
   independently provisioned target identities, the actual consent reference
   and instruction, the unambiguous fixed operation
   `M4.edited.one-use-gui-roll`, frame `327 → 351` and the reviewed #495
   script SHA. A caller must independently verify the Producer's actual
   permission; a locally generated record does **not** cryptographically
   authenticate chat consent. Existing #491 product approval is not this
   new case-specific permission.
3. `resolve_test_bench_full_loop.py start` requires the exact frozen **clean
   checkout HEAD** and source graph, validates the private new root, and
   durably writes `complete-loop-intent.json` with `O_EXCL` **before any
   native/preflight effects**. Any interruption, partial output, UNKNOWN or
   second start is terminal for this attempt. `inspect` is a separate
   **read-only** queue audit; it never dispatches, creates/reinitializes the
   queue, substitutes receipts or resumes an operation. Any needed new live
   trial requires a new approved sacrificial campaign and root, not a replay.
4. The original M4 queue creates its *original* `pristine` operation and
   authenticates the existing seven-operation official SDK host and real
   terminal MOV/decoded PCM. Only then does the original M4 `edited` stage
   become eligible. Under the same shared native owner, a tightly limited SDK
   preflight checks the exact pristine source seal, selected disposable UID,
   full native inventory, Studio 21.1.1.10, original M4 one-use edited intent
   and idle state. It sets **only that timeline's playhead** to 327 if needed
   using the official `SetCurrentTimecode`, then independently rechecks the
   exact offset and unchanged inventory. The separately reviewed #495 F1
   dispatcher performs at most one GUI 24-frame roll; a successful OS exit
   **always remains UNKNOWN** until verified. The native owner is released
   before the edited stage official host (preventing carrier deadlock). The
   Phase-3 same-UID, all-11-item independent SDK save/reopen/readback and
   terminal MOV/decoded PCM proof must pass before the original M4 edited
   receipt can become verified.
5. The original `revision` stage reauthenticates **both** completed native
   output sessions and verifies the precise picture boundary. The actual
   revision controller may automatically accept only the fully measured,
   unambiguous picture-only inference: exactly `caseKinds=["A"]`, no omission,
   no boundary conflicts or audio trim, no provider regeneration, no external
   media or creative decision. The existing TypeScript bridge validates the
   exact empty-history decision hash, proposal hash, accepted revision and
   source derivation. The host prepares and independently verifies the signed
   revised-package preflight before submitting the **original** revision
   operation ID and proof reference. An ambiguous case fails closed.
6. Only after the revision receipt passes the original verifier, the original
   provisioner selects the **already provisioned distinct fresh UID**, and
   the original M4 rebuild worker performs its empty-target check. The signed
   revised-package session reserves that exact target, then the official SDK
   native carrier runs its existing host through save/reopen, terminal rendered
   MOV and decoded PCM verification. The separate strict
   `verify_reverse_receipts` #312 final verifier must pass *before* the
   immutable original M4 rebuild receipt is submitted. Only four authenticated
   original M4 stage receipts, the final `completed_verified` state and its
   private handoff can report `readyFor312Phase2=true`. Neither this artifact
   nor a fake-host test makes that claim for a real run.

## Command contract for Phase 5 (not executed in Phase 4)

Use a private **new** config created by the approved fresh setup, an **actual
independently approved** case-specific canonical authorization file, and the
literal source commit in `.pipeline/499/source-freeze.json` (not the example
placeholder below). The same file also pins `sourceGraphSha256`. These paths
must be readable exclusively by the trusted local caller.

```sh
uv run --frozen python -m vera_timeline_agent.resolve_test_bench_full_loop start \
  --config /absolute/new-sacrificial-root/config.json \
  --authority /absolute/new-sacrificial-root/producer-approval.json \
  --frozen-commit EXACT_40_HEX_PHASE4_COMMIT

# No operations, no implicit recovery or replay:
uv run --frozen python -m vera_timeline_agent.resolve_test_bench_full_loop inspect \
  --config /absolute/new-sacrificial-root/config.json
```

Source pin publication follows **the final source commit**. During Phase 5,
never change the hashed Python code, TypeScript compiler/contract inputs or
lock inputs after the source-pinned admission. The signed native host and
proof sessions recompute source identities; code needing changes instead
requires **stopping**, starting a *separately authorized* fresh campaign only
after a new reviewed source freeze, never resealing/replaying an old one.

## Phase-4 verification evidence, not live native acceptance

- New tests exercise original M4 SQLite queue/operation IDs (not a replacement
  queue), end-to-end fake SDK/GUI transport, distinct fresh provisioning,
  sealed revision policy, bounds/deadline and CAS, wrong native target,
  malformed/changed authority, source drift, partial/UNKNOWN, lost/failed
  rebuild, immutable duplicate start, actual read-only inspection and
  bounded 24-nominal playhead targeting.
- Four reversible guard mutations (frozen HEAD, authority graph identity,
  policy case kind, strict final verifier) each caused its targeted negative
  test to **fail** and were restored byte-for-byte. Tests never open Resolve,
  perform a real GUI action, issue an unowned receipt or accept mock proof as
  #312 operational evidence.
- Focused suite, fast gate and review status are recorded in the pipeline's
  `progress.md` and terminal Phase-4 evidence; any unrelated pre-existing
  repository gate failure must remain explicitly unverified rather than being
  relabeled as a Phase-4 success.

## Permanent safety distinctions

`verified source code/test` ≠ `native observed` ≠ `M4 all-four accepted` ≠
`#312 real Phase-2 acceptance`. A dead, previously admitted or UNKNOWN
operation cannot be replayed under a newly compiled graph. All original
project/timeline names, item identities and signed receipts remain untouched.
