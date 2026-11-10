# #499 phase 19 — real-Mac reentry / frozen source / NEW authority gate

**Verdict: BLOCKED for native M4; no new live-effect authority.** This is a
read-only physical-Mac and source-attestation assessment plus a *non-native*
two-target name reservation. It is **not** a successful SDK reentry, selected
project check, native owner admission, held-still source-in observation, M4
campaign, or authorization to advance to phase 20.

## Independently observed on the physical Mac (Nov 9, 2026 EST)

- DaVinci Resolve GUI was **not running**. The installed app bundle reported
  `CFBundleShortVersionString=21.1.1` and `CFBundleVersion=21.1.10010`.
  A live official SDK `GetVersion()` or project/render-idle result therefore
  **was not** obtained. Do not launch Resolve automatically into an unknown
  current project, call `LoadProject`, save an unrelated Producer project, or
  run the old one-use calibration again.
- Three surviving `ResolvePython` processes were observed: PIDs `59035` and
  `59244` belonged to a Codex app-server parent, PID `73268` to a Claude
  parent. They were live (`S`/`S+`, not zombies); their purposes and safety to
  stop were **unknown**. No process was killed, signaled, adopted, or reused.
- The existing native-owner lock file was present on internal APFS with
  mode `0600`, and `lsof` did not report a holder in a point-in-time sample.
  **This is not owner admission**: the actual read-only
  `resolve_native_owner.preflight_native_owner()` on the clean current-source
  Mac checkout refused with `output_operation_unresolved`, caused by a
  historical native result referring to an `operator-approval-v2/approval.json`
  on the currently absent `/Volumes/Family 1A` drive. The guard was **not**
  weakened, bypassed, or repaired by fabricating missing evidence. Other
  historical records may also need assessment after the drive is restored.
- No external `Family 1A` mount was present. Fresh `shutil.disk_usage` on the
  existing private staging root returned **17,946,468,352 bytes free** on
  device `16777223`, staging mode `0700`. Phase 18's estimated four-stage
  peak of `6,883,932,036` bytes plus an untouched 8 GiB reserve totals
  `15,473,866,628` bytes: **space-only GO at that moment** with
  `2,472,601,724` estimated spare bytes, *not* a hard output quota.
  Re-measure immediately before any later native stage. Phase 18's immutable
  storage manifest still had SHA-256
  `81edf0d41f6ec7a753be12494c135625a8865193a6a80c361724ca73a9286a8d`.
  The full individual input inventory was verified in phase 18, not rehashed
  comprehensively here; no source substitution is authorized.

## Source freeze and source-in semantics

- Preserved original adopted PR **#474**, branch `zodex/499-adopt-pr474`,
  candidate source HEAD entering this docs-only phase `ce85de8c`.
  A new **clean detached Mac worktree** at
  `/private/tmp/vera499-phase19-ce85de8c` was created from exactly this
  pre-phase-19 commit, leaving the Producer's dirty normal checkout intact.
  Linux and physical Mac independently computed the exact same 245-input
  production source graph:
  `14ea634ac58f774b6d58f2af9d76d758446cd47cd9548fe29c05ddce1d41a545`.
- Independently evaluated `ROLL_APPLESCRIPT` on each machine: both returned
  `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`,
  equal to the code's fixed literal. The Phase 14 no-effect metadata script
  itself still hashes to
  `b452eae885b3486672432e456266228e1a37895f73f82dff773845ba7600bf15`.
  **But its embedded 245-file graph pin is the obsolete calibration-era**
  `54ffaaeef7d5f21a631f9aa478a98c431e0cd3e0a9831f454306b170b5821ba1`.
  It would refuse current code; do not silently repin or run it on a
  different/native-current project. With Resolve quit and native preflight
  blocked, the raw metadata inquiry was not executed.
- Phase 13's source question consequently stays **unresolved**: saved moving
  H.264 calibration's right raw `0→24` does not prove the source-in behavior
  of held-still original M4. No `0/+24` exception was added to capture,
  package, TS inference or strict reverse verification. A fresh, independently
  authenticated held-still SDK observation remains required.
- The tracked artifact added in this phase is **documentation only**. The
  authoritative final frozen commit must be the commit containing this report
  and must be re-present in a clean actual-Mac checkout before any use of
  `_frozen_source`. The 245-input graph and fixed actor must remain unchanged.
  No native proof has been source-sealed against that future commit yet.

## One new sacrificial case name reservation — not project creation

The reviewed `resolve_test_queue_m4_provision reserve` operation wrote one
private, canonical `0600` `provision/plan.json` inside the already-private
phase-18 internal staging root; it reported `nativeEffects:false`. The plan
has SHA-256 `410825fe5da1997af9cef1b0e98eefa3223db55f55fcd680117c6cc710461816`.
The *only* reserved project/timeline names are:

- Initial: `VERA Delivery 62dc56a2-dd2e-4a9f-85bb-01e3b85136fe cec5ce4911d1`
- Distinct rebuild: `VERA Delivery 35136dac-8f27-4dbb-85fc-d542c8140bdd b3a59ce97469`

These are **names, not official SDK project/timeline UIDs**. No actual
project/timeline was created, selected or saved. No `intent-*`, `complete-*`,
M4 queue, operation/GUI journal, render, PCM, actual target UIDs or new M4
receipt was created. Phase 20 may use this reservation *once* after gates
pass, never regenerate the names or infer missing SDK UIDs.

## Unfulfilled authorization / admission

The detailed case-specific **non-executable proposal** is kept privately in
`.pipeline/499/phase19-m4-authorization-packet.json` and tied to the final
docs-only commit, source graph, AppleScript SHA and the above reservation.
It intentionally has **no Producer approval reference, issuance/expiry,
official target UIDs, or executable `AUTHORITY_SCHEMA` record**. The old
H.264 calibration permission is spent; #491 is only the product exception.

Before any fresh phase-20 effect: restore genuine missing historical evidence
by reconnecting the original drive (or conduct a separately approved,
cryptographically sound recovery; never fake approval); require the physical
read-only native-owner history check to pass; resolve helper ownership and
render/UNKNOWN; safely open Resolve only after any unrelated work is saved;
check exact installed SDK build, current disposable project/UIDs, permissions,
Edit/V1/lock state and true still-source metadata; verify full internal media
and remaining capacity, actor and final frozen source on the Mac. Provision
the two named targets **exactly once** under explicit case permission and
bind actual four SDK project/timeline UIDs to a fresh separately attributed
Producer approval issued within 30 minutes of the one-use command. Strict
M4 `327→351` one-click Roll and four receipts/strict #312 remain unrun.

**Disposition:** halt at phase 19. Do not hand the Conductor a `phase-done`
handoff that would automatically dispatch phase 20 without these physical
and Producer-authority gates. Original PR #474 remains draft; #473, #312 and
#313 are not unblocked. Full `validate:fast` is deferred to post-native phase
21 as Producer directed, not falsely reported green.
