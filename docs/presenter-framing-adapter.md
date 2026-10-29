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

The checked-in profile fixture contains synthetic test values and synthetic
context labels. It is neither a calibrated look nor an Inspector conversion
table. Do not use those values as production defaults.

## Remaining delivery gates

- Finish end-to-end build integration of the #44 bridge. Its code is merged
  and the bridge has focused synthetic coverage; #44 still needs Producer
  acceptance and Closed/Done before #119 delivery.
- Construct a new disposable protected Presenter Master using a registered
  continuous synthetic picture, explicitly reviewed upstream color and an
  independently synchronized processed-dialogue artifact. Preserve old targets.
- Qualify the unanswered RK-19/#118 delta: non-neutral native transform
  calibration, immediate and save/reopen readback, exact raster matching,
  distinct rendered crops, advancing source frames at direct boundaries and
  cutaway returns, unchanged B-roll/dialogue, grouping and old-build invariance.
- Qualify the exact Free Inspector mapping and retained manual checklist
  separately. Missing mapping must remain blocked; Studio values and temporary
  preview scales cannot be guessed into Inspector instructions.
- Complete focused/fast checks, required Claude review, and the current-head
  full cloud gate after the Steward releases publication. Final merge and
  External closure require the positive native and Free criteria above.

No Resolve operation, media render, publication, or CI run is authorized by
this document. The issue's coordinated resource holds still apply.
