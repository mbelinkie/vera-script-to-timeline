# #499 phase 16 — one-command Roll, original four-stage host integration

**Scope:** code-only completion on the adopted original PR #474. There has been
**no** new Resolve project, UI action, track setter, M4 native stage, media
render, synthetic receipt, source re-seal or use of expired authorization.
Live acceptance remains **0/4**, and strict #312 is **NOT RUN**.

## Source-contract decision

Phase 13's independent retained audit does **not** demonstrate a held-still
source-in change. The +24 raw right-source counter was from a distinct moving
H.264 calibration. Preserve all four existing strict gates unchanged:

1. `qualification_output_native_v2.py` official-SDK capture/observed-edit
   permits held-still counter normalization only with its narrow authenticated
   one-frame timing/source-kind proof; unknown source time stops.
2. `qualification_output_v2.py` package source mapping retains its admitted
   still-source constraints. The generic subrange alternative is not proof of
   an approved held source-in shift.
3. `qualification-output-proposals-v2.ts` inference requires the actual held
   picture events' canonical unchanged source-in and exactly two changed UIDs.
4. `resolve_test_queue_reverse.py` strictly verifies same 11 native UIDs and
   six tracks, only the 327→351 boundary and durations ±24, right end/media,
   links and other nine unchanged, and **unchanged right sourceStart**.

No speculative 0/23/24/25 allowance or moving-picture extrapolation was added.
Physical held-still raw SDK evidence remains a phase 19/20 prerequisite.

## Original host and receipt chain

`resolve_test_bench_full_loop.start` remains the sole owner-gated, frozen-source,
case-approved one-start path. It verifies the canonical new config, separate
fresh target and exact operation authority, writes a durable one-start intent,
and runs the original `resolve_test_queue_m4` state machine:

- **Pristine:** original official-SDK construct, SaveProject/CloseProject/
  LoadProject and capture/readback, real MOV/PCM comparison, signed immutable
  original M4 receipt. The host now journals five separate native
  `Timeline.SetTrackLock` effects during *new synthetic-312 construction only*,
  after all 11 events are placed and before the first capture. V1 stays
  unlocked; V2–V5 and A1 must lock and read back as true. Any stale existing
  lock, wrong track inventory, uncertain SDK return or project switch refuses;
  a partially spent intent is not retried.
- **Edited:** original single 351-playhead `Trim > Roll > Start to Playhead`
  hash-pinned GUI actor remains owner-held, exactly once with its fsynced
  one-use `gui-intent.json`. Its OS return is UNKNOWN, never a receipt.
  `resolve_test_bench_edited_stage` independently verifies that spent intent,
  initial target and signed pristine UIDs, then runs the official SDK
  `observe_edited`, save/reopen, capture and genuine MOV/decoded PCM host.
- **Revision:** `resolve_test_bench_revision_stage` still requires two
  independently authenticated same-target captures, strict #312 boundary,
  deterministic picture-only A inference, accepted revision, canonical
  source-bound proof and original CAS/operation/deadline before receipt.
- **Rebuild:** same original stage constructs only on the **distinct already
  provisioned** fresh project/timeline, with five journaled non-V1 locks,
  official save/reopen, media/PCM and independent reverse receipts. The queue
  now rejects unsigned/missing/unlocked/misassigned lock topology in both
  pristine and rebuilt captures before certifying those stages; edited stage
  maintains exact unchanged six-track signed geometry. Final completion still
  requires all four genuine original receipts and strict `readyFor312Phase2`.

The only production behavior added in phase 16 is **new-case-native track lock
isolation** and **signed-receipt track-isolation verification**. No general
Resolve constructor, historical target or approved GUI script was loosened.
Each setter remains within the existing durable native-effect ledger and its
closed method allowlist, restricted to matrix `synthetic-312` pristine/rebuild
construction.

## Pin and test boundary

- Candidate proof-source graph: `0aa0196dc72acae250320ec94ef9b8e3b68dc5194d00df80e8d981abf1dd4831`
  (**245** tracked Python/TS/contract/lock inputs as enumerated by
  `proof_source_hashes_v2` before the commit; re-hash at final frozen HEAD).
- Fixed script SHA-256 (literal and actual AppleScript bytes agree):
  `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`.
  This hash is **not** a new Producer authorization, native evidence, or source
  seal; any later source edit requires a new graph and separately approved case.
- Phase 16 tests use only injected Python/SDK/queue fixtures; no native effect.
  They cover new-case lock selection, journals and readback, wrong case/profile/
  phase, extra/missing track, stale lock, project drift, failed/unreadable setter,
  signed capture topology, and strict reverse-boundary negatives. The combined
  focused run of the new tests and adjacent M4/reverse/GUI/SDK suites passed
  **420/420**. Targeted Ruff check and formatting, mypy (3 explicit files),
  and `git diff --check` passed.

**Deferred, not waived:** phase 17 independent review and further targeted
fault/mutation checks; phase 18 internal-only storage/media feasibility;
phase 19 safe Mac SDK held-still audit/source freeze and **new, exact-case
Producer consent**; phase 20 one-use native original M4 4/4 and strict #312;
phase 21 full `validate:fast`, current-source independent review, CI, and
Conductor-only original PR #474 merge. No current-head CI or full fast gate is
claimed by this phase; the Producer explicitly prioritized physical native
prerequisites over repeating broad validation now.
