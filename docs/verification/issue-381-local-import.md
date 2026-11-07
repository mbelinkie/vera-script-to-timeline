# #381 verified local import — phase-four evidence

**Scope and host (2026-11-07):** The execution host for this Zodex pipeline
phase is **Linux**, not Matthew's Mac. All touched source files below were
synthetic and disposable; no private Producer footage, real Resolve target,
external service, browser pairing, or user media was accessed. The companion
readiness diagnostic from #158 is not import permission. All results below
distinguish injected synthetic decoding from real FFmpeg verification.

## Repeatable real-filesystem synthetic proof (Linux only)

Run: `uv run --frozen python ../../.pipeline/381/synthetic_fs_acceptance.py`
from the #381 worktree. The script creates fresh owner-private source, project,
outside and receipt directories in a temporary root, generates an internally
valid-structure 64×64 RGB PNG, imports it through the **real descriptor-based
filesystem engine** but an **injected synthetic decoder**, then verifies actual
bytes, inode identity, receipt, read-only replay and refusals. The source is
deleted only by the temporary-directory owner after all checks finish.

| Observation | Recorded outcome |
| --- | --- |
| Synthetic original | 168 bytes; `sha256:fb59293297bbed4792e45b1e8a353c63f942d86ac3b235a8c5c38b81ab75e09a` |
| Original before/after import and refusals | Identical bytes and SHA-256; never moved/unlinked by engine |
| Default clone attempt on this Linux fixture volume | `completedMode:copy` (native clone unsupported on this volume; **not** a Mac CoW pass) |
| Explicit clone-unsupported injection | Verified independent `completedMode:copy` |
| Publication | Destination exactly matches source; different `(device,inode)`; both link counts 1; destination owner-only; exact project-relative locator |
| Immutable receipt / idempotency | Owner-only receipt present; replay `duplicate`, no replacement publication |
| Downstream source handoff | Fresh target rehash/reprobe succeeds but remains `buildQualification:unqualified` |
| Refusals actually injected in disposable host proof | `content_mismatch`, `publication_conflict`, `source_unsafe` (outside symlink), `permission_denied` |
| Privacy canaries | Neither source nor private-state root name in portable JSON; fixed codes, no private paths on refusal |

The 104 Python model/engine/CLI focused tests also use real temporary files
and include more injected failure/collision/recovery paths: root/intermediate
symlinks, FIFO, directory, unsafe source and source swaps, changed digest and
size, malformed/unsupported media, source frame handles, staged crash before
publication, crash after publication, inspected reconciliation, replaced inode,
destination tampering, concurrent duplicate import, read-only reverify,
unapproved grants and private CLI stdout. Fake decoder/probe/clone tests are
**not** evidence of actual codec support, native CoW, or 25 fps video import.

## Guard mutation audit — clean / red / restored

Run: `python3 ../../.pipeline/381/mutation_audit.py`. A temporary independent
copy of the package is used for every mutation, so tracked source files are
never altered. For each row the named negative test **passed before mutation,
failed against deliberately disabled guard, and passed after restoration**.

| Mutated guard | Selected negative test (in `tests/`) | Audit |
| --- | --- | --- |
| Trusted root `O_NOFOLLOW` | `test_unsafe_roots_and_overlaps_refused` | PASS / RED / PASS |
| Source file `O_NOFOLLOW` | `test_unsafe_source_refused_without_reading_external[file_symlink]` | PASS / RED / PASS |
| Expected source SHA-256 comparison | `test_wrong_hash_and_size_do_not_publish` | PASS / RED / PASS |
| No-replace atomic publication replaced with overwrite rename | `test_no_overwrite_if_concurrent_file_appears_during_copy` | PASS / RED / PASS |
| Pending-attempt idempotency refusal | `test_crash_before_publish_is_pending_and_never_auto_removed` | PASS / RED / PASS |
| Import/replay authorization callback | `test_replay_rechecks_current_permission` | PASS / RED / PASS |
| CLI independent `operatorApproved` grant | `test_unapproved_and_insecure_policy_refuse_before_mutation` | PASS / RED / PASS |

**Result:** 7/7 targeted guard mutations were detected. No mutation was left
in the implementation worktree. These targeted red checks complement the
normal focused suite; they do not replace real Mac acceptance.

## Adversarial review and correction

- **[major, fixed]** `local_media_import.py` inspected recovery checked the
  published target *before* decoding but did not rehash it *after* decoding.
  An injected decoder that changed target bytes between those operations could
  still cause a success receipt. The new
  `test_reconcile_refuses_target_changed_while_decoding` was first **RED**
  (`Failed: DID NOT RAISE ImportModelError`), and then passed after adding a
  second destination-byte check and fresh source verification before issuing
  the recovery receipt. The complete focused import suite passed afterwards.
- No public schema, golden fixture, browser route, project permission policy,
  Resolve target or production persistence interface was altered. Browser
  actor authorization and frozen-build preparation remain external boundaries;
  the receipt cannot be treated as an actor permission or `preparedMedia`.

## Validation and acceptance limits

- Focused: `uv run --frozen pytest -q tests/test_local_media_import_model.py
  tests/test_local_media_import.py tests/test_local_media_import_cli.py`:
  **104 passed**. Changed-file Ruff check and format check: pass.
- `npm run validate:fast`: **nonzero**, `22 failed, 2701 passed, 43 skipped`
  (full log `.pipeline/381/phase4-validate-fast.log`). Generated-contract check,
  TypeScript lint/typecheck/fast tests, Python Ruff and full Python mypy passed.
  The 22 failures were confined to **unchanged** narration CLI, #182 campaign,
  #208 native target identity/capability and word-timing modules; **no #381
  focused test failed**. The prior phase-three Linux gate also had 22 failures
  and no #381 failures, but the *individual case names differed* between the
  runs. Therefore this is a repeat of the environment-sensitive failure
  categories, **not an independently proven baseline-equivalent pass**. Do not
  call the full gate green. #208 failures include wall/monotonic clock rollback
  thresholds in this shared Linux host; narration/media failures include the
  missing installed FFmpeg tooling.
- Companion readiness/build-media and #174 non-slow regression test selection:
  `65 passed, 1 deselected`. Three frozen authoring/compiler contract files:
  `50 passed`. All rerun after the recovery-race fix.
- The `npm run review -- notes.md` command was invoked once. Claude returned
  `You've hit your weekly limit` (reset displayed as Nov 9 at 15:00 UTC),
  so **no external review result was obtained**. We instead self-reviewed the
  entire issue diff, corrected the inspected-recovery race, and performed the
  seven independent targeted guard mutation checks. Review remains external
  acceptance work when the limit is available again.
- The Zodex Linux host has no `ffmpeg` or `ffprobe` executable. The available
  isolated macOS Seatbelt workspace has FFmpeg paths, but **FFprobe cannot
  start**: the sandbox denies a linked `libvmaf.3.dylib`. That workspace also
  cannot access this issue worktree. Unrestricted Mac execution requires local
  approval and was not invoked. Thus a **real FFmpeg-decoded synthetic PNG and
  2-second video on the Producer's Mac, actual APFS CoW/fallback, Mac-native
  destination receipt publication and private actor/permission seam have not
  been accepted**. No fabricated pass is recorded.
- The default engine intentionally uses Linux `FICLONE` where available; its
  macOS port defaults to independently verified full copy unless a qualified
  descriptor-native clone implementation is injected. A real Mac clone was
  **not** demonstrated, and should not be advertised as implemented.
- The named issue-specific technical acceptance authority still needs to
  inspect evidence or carry out its deterministic acceptance. Until then this
  work is a backend-only PR **referencing** `#381`, not evidence that #85, a
  browser experience, generic authenticated pairing, or media preparation is
  complete. The PR should use `Refs #381` rather than auto-close when actual
  required Mac checks are outstanding.
