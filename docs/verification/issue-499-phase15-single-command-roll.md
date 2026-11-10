# #499 phase 15 — source-only one-command Roll actor

**Decision:** Replace the original #495 24-nudge transport with one fixed
`Trim > Roll > Start to Playhead` menu operation, after deterministic menu
setup, only for a newly source-frozen, specifically authorized sacrificial M4
case. The new `ROLL_APPLESCRIPT` bytes are pinned by independent literal
SHA-256 `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`.
The actor itself has exactly one `click rollItem` and no nudge, generic menu
execution, shell, manual timeline targeting, repeat, or edit retry.

## Admission and execution boundary

1. The original M4 queue/one-start validates a *new* initial and separate
   rebuild target, immutable approval and source graph, fresh operation ID,
   absolute deadline, independently signed pristine result, and held shared
   native-owner lock. Historical cases, the spent direct-Roll calibration,
   and the previous #491 nudge permission do not authorize a new native effect.
2. The original signed eleven distinct item UIDs, six distinct V1–V5/A1
   tracks, 1407-frame extent, 24000/1001 rate, exactly one adjacent V1 cut
   at 327, both boundary clips unlinked, no other 327 cut, **V1 unlocked and
   all other five tracks locked**, and empty selected-clip list are required.
   The official SDK matches the selected project/timeline UID, reads the
   current Edit page, and positions the same pristine timeline's playhead
   at **351** (never 327 for this named command) with unchanged full inventory.
3. Independent OS checks bind the exact installed Studio 21.1.1 build,
   original process PID, bundle path/ID, foreground process, one exact named
   **AXMain** window, no sheet/modal, no-prompt Automation and Accessibility
   permissions, fixed default keyboard provenance, and named setup/roll menu
   existence. A second full signed SDK inventory and target/page/playhead
   check brackets this OS read; late pre-dispatch SDK identity, Edit and frame
   checks run again before the fixed OS command.
4. Under the same owner, the original `OriginalM4GuiJournal` atomically
   consumes a single private `gui-intent.json` with O_EXCL and fsync before
   any possible GUI effect; a partial write or crash is **spent/UNKNOWN**, not
   a recovery token. The script checks PID/bundle/foreground/one named AXMain
   window/no sheet, conditionally clicks Edit/Deselect All, clicks absolute
   Auto Deselect All Tracks, toggles **only V1** once, sets Normal Edit Mode,
   conditionally deselects whole clips again, repeats OS target checks and
   clicks **one** `Roll > Start to Playhead` only if enabled after setup.
5. Any subprocess error, timeout, late SDK mismatch or uncertain result
   remains **UNKNOWN with no second Roll**. Even an exit code of zero is not
   an M4 receipt. The separate official SDK save/close/reopen, signed native
   render/PCM and strict #312 verifier own later acceptance (phase 16 onward).

## Explicit risk tradeoffs and unresolved requirements

- Real Studio Qt did not expose reliable `AXFocused`, selected Edit/V1 or
  Normal-mode AX marks. They are **not fabricated or treated as observed**.
  This route uses separately verified foreground PID + sole AXMain window,
  official SDK Edit/UID/position evidence and one reviewed absolute V1-only
  menu setup instead. The script does not assume menu toggles are already
  selected. `Deselect All` can be disabled when nothing is selected; the SDK
  requires that exact empty selection and the actor treats the menu as a
  conditional idempotent cleanup, not a positive status check.
- The real one-case calibration established the named GUI command and a
  UID-preserving 327→351 on synthetic **H.264 moving-picture source type**,
  not the held-still source used by original M4. Its raw right sourceStart
  +24 does **not** change or relax any of the four canonical M4 source-in
  checks. Native held-still normalization is UNKNOWN pending read-only SDK
  metadata in phase 19. No M4 edited receipt or strict #312 pass is claimed.
- One-shot absolute setup can still encounter a mid-script Qt/Resolve state
  race or a mode/selection action with undocumented behavior; OS identity
  rechecks reduce wrong-window risk but cannot prove native edit geometry.
  Physical one-shot acceptance and independent host postcondition checks
  remain compulsory. All uncertainty permanently blocks replay.
- The existing pristine authoring path must produce **authentically locked**
  V2–V5/A1 tracks in the *fresh* signed M4 case. Phase 15 intentionally
  refuses mismatched signed/live locks rather than changing a historical
  source or secretly locking tracks during the one-effect OS script. Phase 16
  must confirm fresh-case provisioning/capture produces these locks and full
  four-stage integration; a mismatch is a prerequisite failure, not a bypass.
- No Mac/Resolve process, native project, GUI, physical keyboard, media,
  external drive or old calibration evidence was touched by this code phase.
  The new AppleScript was not compiled or run on macOS here (Zodex Linux
  container). No Producer permission for a new M4 operation has been
  received, and no original PR #474 push/merge or #473/#312 unblock occurred.

**Focused evidence:** local injected tests for fixed script hash/one named
Roll, wrong PID/window/bundle/TCC, wrong SDK frame/UID/source/track lock,
whole-clip selection, SDK→OS→SDK drift, consumed/ambiguous fsynced journal,
one-use timeout and repeated call. Broad `validate:fast` deliberately deferred
to phase 21 per Producer's native-prerequisites-first instruction.
