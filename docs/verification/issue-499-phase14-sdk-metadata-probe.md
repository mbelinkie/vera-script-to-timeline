# #499 phase 14 — fixed, read-only SDK metadata observer (DEFERRED)

**Disposition:** code-only **COMPLETE**; real SDK observation **DEFERRED** to a later
safe Phase 19 re-entry. On November 9 the Producer had quit Resolve and unplugged
external storage. Neither was started/remounted or accessed in this phase. This
document is **not** an original #473 M4 receipt, a fresh Roll authority, or
validation of held-still source normalization. Current M4 remains **0/4** and
strict #312 **NOT RUN**. Phase 13's **NO VERIFIER CHANGE** remains in force.

## Reviewed fixed entry point

- `scripts/issue-499-calibration-readonly-metadata.py`: standalone diagnostic,
  deliberately outside the 245-entry proof-source graph; **SHA-256**
  `b452eae885b3486672432e456266228e1a37895f73f82dff773845ba7600bf15`.
  Call with no flags returns `DEFERRED` and does not connect to the SDK.
  The only observing entry requires both `--execute-readonly` and
  `--probe-sha256` equal to these exact reviewed bytes.
- The original calibration remains at `b613cab5b960ce0d750fd33ef9e598fb4f67ae05`,
  with existing proof graph SHA-256
  `54ffaaeef7d5f21a631f9aa478a98c431e0cd3e0a9831f454306b170b5821ba1`.
  The Python calibration, setup actor and **spent** single Roll actor must match
  their three Phase 12 independent SHA-256 values. New SDK probe code never
  imports or dispatches those actors.
- Fixed expected input is the previously authorized, *saved and reopened* v2
  **synthetic H.264** project, never an arbitrary project selected by a CLI
  argument. The original one-case authority and seven immutable case records
  must match exact independently pinned byte digests, canonical JSON encoding,
  file owner/mode, project/timeline IDs, source graph, saved post-Roll geometry,
  and already-consumed one-use intent. No authority is refreshed or reissued.

## SDK observation boundaries

The observer must first hold the existing host-wide `native_owner(output_lane=True)`
lock, verify source pins and **the current** Studio build `[21,1,1,10,""]`, and
require that `GetCurrentProject()` and its current timeline/folder already be
the same project/timeline UUIDs, names and folder recorded in the saved v2
evidence. `IsRenderingInProgress()` must be exactly false. Wrong active
project or absent app is a stop: **never `LoadProject` or switch**.

Within the lock it double-reads the entire six-track/11-UID, media-UID, link,
record-range and raw-source-frame inventory and compares byte-for-byte with
the reopened Phase 12 baseline. It singles out exactly the two original V1
UIDs with left `0/351`, right `351/127`, source frames `0/351` and `24/151`.
Only after this exact match does it query, on those two clips only:

- Raw `GetSourceStartFrame`, `GetSourceEndFrame`, `GetSourceStartTime`,
  `GetSourceEndTime`; `GetStart/GetDuration/GetEnd` both `False` and `True`.
- Media UID and `GetClipProperty` **Frames, FPS, Type, Online Status, File Path**.
  The latter must be the fixed, already-hashed internal `root.mp4` asset, with
  720 frames and ~24000/1001 fps. It cannot redirect the probe to a new media
  path; file bytes must match their original SHA-256.
- A **diagnostic-only** normalized range using the native host's ordinary
  *moving-video, non-EOF* branch: `sourceStart=rawStart`,
  `sourceDuration=rawEnd−rawStart`, `recordDuration=SDK record duration`.
  This **does not invoke the authenticated native host**; it records the exact
  branch that would apply if the remaining official host/context guards pass.
  The output explicitly says `nativeHostAcceptanceClaimed=false` and
  `heldStillTimeNormalizationApplied=false`. Missing time getters stay `null`
  with `available=false` rather than zero. **There is no held-still conclusion.**

SDK results never print raw project/clip/media UIDs or file paths: those fields
are salted-SHA-256 pseudonyms (keyed to the immutable authority digest), and
the full path is replaced with `[REDACTED]`. The result includes a canonical
SHA-256 digest over the redacted evidence itself. Refusal output contains only
`REFUSED_NO_EFFECT` and the exception class, not sensitive exception details.
The diagnostic writes **no file**: a later operator can redirect its already
redacted output to a private, separately named evidence file, without changing
old calibration records. No old Roll/journal path is ever retried.

## Execute only under safe conditions (not now)

1. Later, **only after** Resolve is already running, and the exact original v2
   saved synthetic calibration project/timeline is **already current**, select
   a clean Mac checkout with the same pinned Python source graph and three
   calibration actor hashes. If another/Producer project is active, **STOP**;
   do not load or change it to reach the test target. This phase does not
   authorize project switching, a UI click, save, render, or any Roll/Nudge.
2. Independently check the script SHA and the private v2 case files. Use the
   exact command recorded in `.pipeline/499/phase14-sdk-metadata-execute-packet.md`
   with the reviewed `--probe-sha256`; execute at most one **read-only** SDK
   observation while owner lock is available. If a precondition fails, record
   the refusal and **DEFER** rather than adjusting it or replaying a native action.
3. Phase 19 may attach the redacted JSON trace and report the measured frame,
   time, FPS, media, UID and diagnostic interpretation fields. Even a successful
   H.264 trace does not prove synthetic-312 held-picture source semantics or
   unblock #473/#312/#313; separate authenticated held-still and 4/4 M4/strict
   #312 proof remain required.

## Code-only evidence and adverse review

`uv run --frozen pytest -q tests/test_issue499_calibration_readonly_metadata.py`:
**19 passed**. `uv run --frozen ruff check` and `ruff format --check` on the
two new files **PASS**; `py_compile` **PASS**; targeted `MYPYPATH=python uv run --frozen mypy` **PASS**. Offline
`script_and_source_attested()` **PASS**: all three original actor SHA-256
digests match, and the 245-entry current proof graph is unchanged. The negative
mocks refuse wrong project/timeline, UID/media UID, native geometry, private
evidence/case authorization, absent/mismatched source/media, invalid FPS,
missing owner, active render, altered lock and late readback drift; the absent
time-getter test stays unknown, with no synthetic zero. No `.pipeline/473`
operation, original target, SDK app, external drive, GUI, media or project was
modified or accessed. Broad `validate:fast` was **not run**, following the
Producer's native-prerequisites-first direction (this is not a green gate or CI
claim). Final original-PR checkpoint and Phase 19 live consideration belong
to the Conductor, not to this probe.
