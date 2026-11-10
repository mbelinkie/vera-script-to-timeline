# #499 phase 18 — physical Mac no-drive storage and provenance gate

**Decision: `GO_STAGING_ONLY`; `NO-GO` for an M4 native effect in this phase.**
Observed on the physical Mac at **2026-11-10 00:55:41 UTC** (November 9, EST), not inferred from the earlier pre-unplug free-space reading. The existing synthetic-312 source set is intact on internal APFS without `/Volumes/Family 1A`. A single new, empty private internal staging directory was created. No project, Roll, render, consent, native receipt, old artifact or code-source seal was created/replayed.

## Independently checked physical state

- `/Volumes/Family 1A` **does not exist and is not mounted**. No creation, mounting or writing to this path. All input roots and the new stage report the same internal APFS Data device `16777223`.
- Conservatively available space at audit: **17,484,009,472 bytes (16.28 GiB)**, from live `disk_usage` of HOME and `/System/Volumes/Data`; the measurements can change. A subsequent read-only `df` at the staging directory also identified `/dev/disk1s2` mounted on `/System/Volumes/Data`. Do **not** use these samples as Phase 19/20 admission.
- Source package: `$HOME/.local/state/vera/issue-472-guarded-m4-02/package`, **30 files / 177,872,977 logical bytes**, with each relative filename/size/SHA-256 recorded in the private manifest. Package geometry is **11 events, six exact preparation bindings, 1,407 frames**. Sources include six original preparation MP4s and three published narration WAVs. Historical admitted package and source are not interchangeable identities.
- Preparation receipts: `$HOME/Library/Application Support/VERA/qualification-output-preparation/issue178-20261016-01/cases/issue312-package-current-S-approved-v2/published`, **21 files / 12,622,557 bytes**. All **six** required published `receipt.json` files are byte-identical to their individually addressed original package receipts.
- Narration evidence: `$HOME/.codex/worktrees/f861/VERA Script to Timeline/out/issue312/rehearsal-speech-v1`, **107 files / 43,884,472 bytes**. All **three** original narration WAV digests match their pinned compiler-dependency hashes; accompanying timing and measurement files were present, SHA-256 recorded.
- Historical pristine admitted package: `$HOME/.local/state/vera/issue-473-native-20261108-2319/pristine/admitted/package`, **54 files / 178,864,880 bytes**. **53/53** expected `package-inventory.json` files matched declared SHA-256 and size. It remains historical evidence, NOT a new source seal or authority.
- Historical signed evidence is retained at `.../pristine/session.json`, `.../pristine/admitted/qualification-output-package-admission.json`, the old `config.json`, `m4-plan.json`, and original project/timeline UIDs (represented by hashes in the private manifest). Nothing was rebased or made eligible for replay.
- The adopted original PR #474 source HEAD entering this docs-only phase was `9a2984365932c6b8845fe9b78ae341c9f73eb1e5`. The current `ROLL_APPLESCRIPT` was independently rehashed from the module bytes as `9595f41eb5a943e245628d0f537aead0e6cc49447554294153aa7281314c0845`, equal to the hardcoded literal; this is a **candidate**, not a new final signed source freeze.

Key SHA-256 anchors (the private manifest has the full relative-file inventory and original identity digests):

| Artifact | SHA-256 |
| --- | --- |
| Old `config.json` | `596fe125a67277c3b41699694c7ba09c0a7d307fbb02ea22c8b0c5ac8e2c0269` |
| Old `m4-plan.json` | `0306fdc7f3b2446415838ac3f17cb2d64f12a25045d0659a9dc03f16f1babaaf` |
| Admitted package inventory | `a16e7478fe7993ad6ebd8efc1d9fb304be19fb2b0a72e5bf757927b9755ae141` |
| Pristine session | `0c946e31941e2ca9ebdb7169053156c5851948cfc0ffc4d9464d20eb73dea4d0` |
| Package admission | `45dd5daf8ddef20598919f31d3a7d1561bc2245a5a47b439b4314198e3091a2b` |
| **Private phase-18 JSON manifest** | **`81edf0d41f6ec7a753be12494c135625a8865193a6a80c361724ca73a9286a8d`** |
| Read-only physical audit script | `21766cd8862b5b699118a9912e2ded12c6481160ef3a6a76ad7199b89eb2bbda` |

The complete local manifest is `.pipeline/499/phase18-native-storage-manifest.json`, created once with `O_EXCL`, fsynced and mode `0400` (not committed to the public PR). It records every input file and SHA, root paths/devices, prior UID hashes, the future output paths, assumptions, and `nativeM4AllowedNow: false`. It was independently read and rehashed through the Linux-shared ticket path after the Mac finished.

## Four-stage M4 scratch/output feasibility

The approved 1 GiB `maxDiskBytes` from the historical M4 config is an **admission minimum**, **not** a hard upper limit on output or an OS-enforced quota. For a new four-stage M4 (pristine, edited, revised, rebuilt), the conservative **planning estimate**, without deleting or deduplicating existing proof, is:

| Component | Budget (bytes) |
| --- | ---: |
| Four MOVs × largest of **90 actual retained MOVs** (495,420,170 B) | 1,981,680,680 |
| Four decoded PCM buffers, at 1,407 frames / 23.976 fps, 48 kHz, eight channels, 32-bit + 20% margin | 432,663,064 |
| Four worst-case copies of the source package | 711,491,908 |
| Concurrent Resolve, import and render scratch estimate | 3,221,225,472 |
| Receipts, journals, databases and miscellaneous output estimate | 536,870,912 |
| **Total estimated peak additional space** | **6,883,932,036 (6.41 GiB)** |

At the observed 16.28 GiB free, the *estimated* remaining space is **10,600,077,436 bytes (9.87 GiB)**, above an explicit **8 GiB untouched reserve** by only ~1.87 GiB. This is an **estimate, not a guaranteed maximum**: Resolve can render a larger MOV or consume unanticipated caches, and free APFS space is volatile. The phase-18 check does not enforce a render quota; Phase 19 and immediately before any Phase-20 stage must freshly recheck `free >= estimatedPeak + 8 GiB`, confirm the actual inputs/output volume/device and verify there are no competing writes. If not, **`NO-GO: MEDIA_OR_SPACE` and WAIT FOR DRIVE/SPACE**, preserving all evidence; no native operation starts.

The historical output directory `$HOME/Library/Application Support/VERA/qualification-output-native/v1/renders` already contains **90 MOVs**; the larger `qualification-output-native` tree occupies roughly **13.2 GiB**. Retain these files; this phase deleted or altered none. Actual new render paths are governed by the hashed, native-owner `renders/<new-proof-chain-digest>/*.mov` reservation, not by arbitrary fallback paths.

## Staging disposition and handoff

Created only `$HOME/.local/state/vera/issue-499-phase18-internal-stage-20261109` on internal APFS Data, **mode `0700`, empty (0 children)**. This is a placeholder root, **not** a fresh project, case configuration, native-source admission, Roll journal, producer permission or native output. It must not be treated as proof a future M4 stage has started. No directory in `/Volumes` was touched.

**Phase 19 must** revalidate actual capacity and all SHA/volume paths, inspect SDK metadata only when it can be done without switching Producer projects, freeze exact original-PR code and pinned actor, create fresh distinct target IDs, and obtain **separate new case-specific Producer authority** for the exact one-use M4 effect. The completed H.264 calibration consent was spent; the historical M4 consent is obsolete. Phase 20 remains prohibited until all of those gates and the independent still-source semantics are satisfied. No full `validate:fast`, Resolve launch, GUI edit, SDK effect, CI assertion, PR push/merge or #312/#313 unblocking was attempted in Phase 18.
