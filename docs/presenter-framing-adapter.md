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
`mappingEvidenceContentJson` retains the exact canonical evidence bytes for
Python to verify without reproducing JavaScript number formatting.
Synthetic tests exercise the delivered verifier and mapper without media tools.

Live Studio 21.1.1 build 10 readback on a 24 fps synthetic video and a 48 kHz
synthetic WAV confirms `AppendToTimeline` source intervals are half-open for
this adapter path: source frames `[10,40)` read back as start 10, end 40, and
duration 30. Keep this conclusion scoped to the tested #119 route; historical
workflow endpoint conventions remain unchanged.

`snapshotPresenterFramingCalibration` creates the first paired snapshot or the
next version from completed sample readback. It preserves prior snapshots and
uses the existing canonical hash and validator. The Python adapter captures
already-authored raw properties from two disposable samples, then checks their
immediate and reopened readback. It can also apply explicit test tuples. The
adapter verifies native item/media identities, source intervals, exact clip names
and optional clip colors. TypeScript owns profile creation and versioning;
Python consumes its pinned bytes. These operations add no visual qualification.

Each presenter target carries its owning timeline UID. The adapter requires a
current-timeline UID reader and checks ownership before each write and after
reopening, so an old build's item handles cannot be reused on a new current
timeline. Verified operations require the concrete, single-use
`NativeSaveReopen` lifecycle, bound to that project and timeline. It invokes
Resolve's SaveProject, CloseProject and LoadProject, checks native identities,
and restores the expected timeline when necessary. A generic no-op callback
cannot qualify an operation. Reopened items are fetched from that timeline's
video tracks by UID, with original pre-close handles rejected; unrelated
B-roll items are left alone. Mock lifecycle coverage still requires live proof.

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
framing target, and verifies source/record placement. Each resolved media handle
also carries the positive total source-frame count from its independent source
evidence. Resolve's video `Frames` property must match that count. For audio,
the caller pins the count from processed sample evidence and the adapter checks
the native duration, frame rate, and sample rate. Source intervals cannot exceed
the count. Item readback keeps the exclusive source end at interior boundaries;
when an interval ends exactly at EOF, Resolve reports the last valid frame
(`source_frame_count - 1`) while record duration remains exact. The adapter
accepts that endpoint only with the matching source count and exact duration.
Every Master video/audio track is locked and read back. This protects tracks;
it is not a claim that the whole project is read-only. Hidden presenter
intervals remain present on V1. The caller adds the independent B-roll overlay
and runs the framing adapter against the returned generated target items.

The builder also requires the caller's independently retained expected request
hash and profile pin; self-consistent embedded values alone are insufficient.

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

## Qualification and remaining delivery gates

[Studio qualification](verification/issue-119/STUDIO_QUALIFICATION.md) records
completed synthetic calibration, protected Master/generated builds, exact
save/reopen readback, v2 decoded source-frame continuity and distinct crops,
unchanged PCM/B-roll, v3 profile revision with prior-build preservation, and
actual Edit-page color bulk selection on Studio 21.1.1 build 10. The #44 bridge
was exercised using real UUID registration and verified ingest/mapping evidence;
#44 is Producer-accepted and Closed/Done.

Closing the synthetic project creates a fresh empty `Untitled Project` UID.
The concrete lifecycle admits only the opted-in exact name, a different UID,
and direct empty timeline/media-folder/render-job inventories. It repeats the
full inventory and identity check immediately before loading the saved target.
Unknown/nonempty handoffs remain refused. Earlier failed lifecycles and partial
timelines were preserved, rather than retroactively certified or replayed.

Free Inspector qualification/checklist remain deferred to #355 and blocked.
Matthew also deferred choosing production crops to real-footage integration;
synthetic qualification tuples are never production defaults. All other Studio
mechanical criteria retain their original scope.

Local fast checks passed (2,028 Python tests plus TypeScript/lint/type checks).
The final review's Master-current guard correction passed 42 focused Master
tests, lint and mypy. Current final-head cloud validation and merge remain
required before External closure. The published draft's earlier cloud result
cannot qualify a later code revision.

No Resolve operation, media render, publication, or CI run is authorized by
this document. The issue's coordinated resource holds still apply.

## Retained native qualification protocol

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
