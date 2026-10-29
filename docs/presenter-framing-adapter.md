# Presenter framing adapter — #119

This is independent implementation work for #119, not native qualification or
completed delivery. The accepted behavior is in the
[Wide/Tight contract](investigations/issue-118-wide-tight-framing-contract.md).
RK-19 still bounds the existing native evidence: temporary-still composition
does not establish non-neutral continuous-video framing.

## Input boundary

`packages/contracts/src/presenter-framing.ts` validates the immutable paired
profile. The hash covers the schema, exact source/timeline/Resolve/adapter
context, both raw transform tuples, and neutral invariants. Identity and version
are separate pin fields. Evidence locators belong outside the snapshot.

`presenterFramingProfileContentJson` emits the exact canonical content string
that other runtimes must retain. Python verifies those UTF-8 bytes against the
profile hash and parsed content; it does not recreate JavaScript number
formatting using Python JSON serialization.

`createPresenterFramingRequest` binds a profile to a #43 registered source,
explicit upstream source intervals, reviewed color evidence, and one independently
synchronized processed-dialogue placement. It checks exact picture adjacency,
including covered intervals, and preserves the dialogue placement in the
request. Names use `OC WIDE <eventId>` / `OC TIGHT <eventId>` and auxiliary Blue /
Orange colors. It returns `requested`, never a claim of native completion.

The initial native item boundary supports exact 1:1 source/timeline frames at
matching rates. It refuses retiming. The Python `presenter_framing_mapping`
bridge calls #44's public `ReviewIngestAdapter.map_proxy_frame_range`, which
revalidates the registered source and derivative receipts before mapping. It
returns master frame bounds and the exact mapping evidence. The request pins
that evidence for every interval and checks source identity, generation and
exact boundaries. Direct master playback retains #44's `mappingHash: null`;
the framing request's `mappingEvidenceHash` separately hashes retained evidence.
Synthetic tests exercise the delivered verifier and mapper without media tools.

`snapshotPresenterFramingCalibration` creates the first paired snapshot or the
next version from completed sample readback. It preserves prior snapshots and
uses the existing canonical hash and validator. The Python adapter captures
already-authored raw properties from two disposable samples, then checks their
immediate and reopened readback. It can also apply explicit test tuples. The
adapter verifies native item/media identities, source intervals, exact clip names
and optional clip colors. TypeScript owns profile creation and versioning;
Python consumes its pinned bytes. These operations add no visual qualification.

DeepSeek supplied the bounded `snapshotPresenterFramingCalibration` implementation
against frozen tests. The controller retained its response after rejecting a
multiline declaration where an exact signature was required. Parent integration
normalized that declaration, corrected three TypeScript casts and added an
explicit `unknown` annotation for prototype inspection. Its 19 focused behavior
checks passed; package typecheck and lint passed after those parent changes.
This provenance is code-generation evidence only.

For a captured Python `CalibrationResult` serialized with `dataclasses.asdict`,
the profile CLI reads `{ "calibration": ..., "prior": null, "id": "<UUID>" }`
from stdin. Supply the exact prior snapshot instead of `null` for a revision.
Run `node packages/contracts/src/presenter-framing-profile-cli.ts` with the
repository's pinned Node runtime. Its stdout contains `profile` and the exact
`profileContentJson` string. It writes no files or native targets. The caller
stores a new immutable artifact and passes both returned fields to Python;
it must not overwrite a prior build. The process-level bridge test checks this
TypeScript-to-Python numeric/hash boundary using the real CLI.

`prepare_presenter_master` consumes the request and caller-resolved media-pool
handles. Resolve's native project UID is checked separately from the logical
registration project ID. It verifies the exact `requestContentJson` bytes and
hash before creating timelines, checks handle identity/path/rate against the
resolved inputs, creates a new continuous Master and a separate generated
framing target, and verifies source/record placement. Every Master video/audio
track is locked and read back. This protects tracks; it is not a claim that the
whole project is read-only. Hidden presenter intervals remain present on V1.
The caller adds the independent B-roll overlay and runs the framing adapter
against the returned generated target items.

The standalone builder currently accepts explicitly reviewed synthetic identity
color inputs and an independently prepared dialogue artifact. It applies no
grade or audio processor. Picture and dialogue media frame rates must match the
timeline on this bounded path; sample offsets must convert to exact integral
source frames, with no rounding. A different audio placement route needs native
qualification. Registration/ingest verification belongs to #43/#44 and the caller;
passing a media handle does not replace those source checks. Track locks,
placement and media APIs are covered by mocks here and still require live proof.

The checked-in profile fixture contains synthetic test values and synthetic
context labels. It is neither a calibrated look nor an Inspector conversion
table. Do not use those values as production defaults.

## Remaining delivery gates

- Finish end-to-end build integration of the #44 bridge. Its code is merged
  and the bridge has focused synthetic coverage; #44 still needs Producer
  acceptance and Closed/Done before #119 delivery.
- Connect the builder to the registered synthetic inputs and run its protected
  Master/separate-generated-target workflow in the disposable real project.
  Verify its track locks and preserved old targets after save/reopen.
- Qualify the unanswered RK-19/#118 delta: non-neutral native transform
  calibration, immediate and save/reopen readback, exact raster matching,
  distinct rendered crops, advancing source frames at direct boundaries and
  cutaway returns, unchanged B-roll/dialogue, grouping and old-build invariance.
- Free Inspector qualification and the retained manual checklist are deferred
  to #355 by Producer direction on 2026-10-28; they do not block #119 delivery.
  Missing mapping must remain blocked; Studio values and temporary preview
  scales cannot be guessed into Inspector instructions.
- Complete focused/fast checks, required Claude review, and the current-head
  full cloud gate after the Steward releases publication. Final merge and
  External closure require the positive Studio/native criteria above. Free
  manual completion remains explicitly unverified pending #355.

No Resolve operation, media render, publication, or CI run is authorized by
this document. The issue's coordinated resource holds still apply.

## Next bounded native delta

Use RK-19 and the smallest proof specified in #118. The unanswered questions are
non-neutral continuous-video transforms, exact retained raster context,
save/reopen persistence, source-frame continuity, protected master handling,
and the separate Free Inspector mapping. Reuse prior qualification conclusions;
do not repeat the transparent-still campaign.

After the Steward releases the native/media window, first check actual Resolve
ownership and outstanding operations. Use a new uniquely named disposable
project and synthetic media only. Record the application's actual product,
version and build. Register the continuous picture through #43 and open a
verified #44 mapping session. Retain explicit reviewed synthetic identity-color
and processed-dialogue inputs with synchronization evidence; a registration
record alone is insufficient dialogue evidence.

Start with two disposable calibration samples using the same source interval.
Capture the authored raw values and neutral invariants, then verify immediate
readback and save/reopen readback. These samples qualify the property path;
repeating an interval for calibration does not prove continuous playback.

Use a separate generated timeline for continuity: direct Wide-to-Tight with
adjacent record/source frames, followed by a Wide/B-roll/Tight-return case.
Keep the presenter source advancing beneath B-roll, with one processed-dialogue
item spanning the full sequence. Compare observed native source ranges and media
identities to the #44 mapping. Verify clip names, record clip-color limitations,
and verify the master track locks. Render only after exact native readback
passes. Decoded frame samples must show the two distinct crops and advancing
source content across the direct boundary and return; compare the continuous
audio and B-roll to their baseline. Save/reopen and repeat readback. Build from
a revised calibration into new targets and confirm prior artifact bytes and
timeline semantics remain unchanged.

The deferred Free check (#355) uses the actual supported import route and edition:
retain authored choices and names, qualify the raw-property-to-Inspector
controls/values for the exact context, and follow the resulting pinned checklist.
Without that positive mapping evidence the implementation must stay `blocked`.
An API stub, Studio-only import, or mock cannot establish Free manual completion.
