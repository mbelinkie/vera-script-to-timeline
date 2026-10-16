# Issue 141 — same-locator wrong-byte test

Status: bounded plan only; no file replacement or Resolve call has run.

Use only the distinct imported source UID
`81d81dc0-4c37-478b-8079-03debba5e780` and its isolated R4 occurrence
`af55478a-0ba3-458a-a6e1-e47b2544111d`. Preserve the shared original source
`9202163a-8381-43e6-9157-3a60f35c6f79` and all original timelines. Require
accepted unlink/relink results and a new equal two-pass selected-R4 checkpoint
before implementing or staging this action.

The approved `relink/base.mov` currently has SHA-256
`c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942`
and 792,989 bytes. The separately generated `wrong/base.mov` has SHA-256
`771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b`
and 790,489 bytes. Both contain 200 H.264 frames at 25 fps, 640x360, and
384,000 mono PCM16 samples at 48 kHz. Matching stream metadata therefore
cannot establish matching bytes. Manifest uses `sizeBytes`.

## Ordered experiment

1. Verify exact project/build/selected-R4 identity, full source/pool/timeline
   pins, the complete synthetic manifest, both regular non-symlink candidate
   files and parent directories, and their exact hashes/sizes. Prove the
   relink locator is used only by the distinct imported item and its one R4
   occurrence. Retain the original shared source hash separately.
2. Retain a newly owned byte-for-byte recovery copy of relink/base.mov under
   this issue's output directory. Hash it before any replacement. Do not
   change the manifest or accepted fixture; it remains the expected identity.
3. In the reviewed injected native action, journal an atomic replacement of
   only relink/base.mov with a verified temporary copy of wrong/base.mov.
   Recheck the original locator hash immediately before replacement. Retain
   timestamp, source/destination hashes, sizes, and ordered request/result.
   Original base.mov and wrong/base.mov remain untouched. This replacement
   is reversible and confined to the generated copy.
4. Capture two complete native observations and pool inventories without
   mutating expected hashes. Retain the resulting hash mismatch as an actual
   mismatch; never rewrite the expectation to make the observation pass.
   Record the actual media UID, locator, online status, format, source/record
   bounds and markers. Sample the current program frame only through the
   already tested still-export API with pinned playhead/page guards. Native
   metadata can remain unchanged while bytes differ; do not claim cache
   invalidation or visible substitution from the hash alone.
5. If unchanged context remains verified, use the separately reviewed native
   save/close/load path or supported exact-item relink refresh to inspect the
   refreshed program output. The refresh method must be chosen and reviewed
   before execution; no retry, generic UI command or undocumented API.
6. Restore the generated locator using the verified recovery copy only while
   the exact project/item/locator and wrong-byte hash remain pinned. Refresh
   through the same reviewed method and retain matching original hash,
   complete unchanged content/pool state and sampled program output. Preserve
   every evidence/recovery file. If context or bytes differ unexpectedly,
   stop without another replacement, cleanup or Resolve mutation.

A source hash can establish a byte mismatch at the locator; it cannot alone
establish which cached bytes Resolve is displaying. A successful return,
matching filename, online flag, stable UID or matching duration must never
turn the wrong-byte item into verified asset identity. Offline, absent
occurrence and absent pool item remain distinct observations.

## Checks and acceptance

One stdlib fake must verify exact-path/hash guards, no replacement on drift,
ordered replacement/capture/restore, retained hash mismatch, no original-source
change, and refusal with recoverable evidence on partial failures. Native
External evidence must include both source hashes and actual raw before,
wrong-byte, refreshed and restored readbacks/output. This plan adds no
contract, fixture, production implementation, dependency or roadmap change.
