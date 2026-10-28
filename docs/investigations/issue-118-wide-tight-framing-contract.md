# Single-camera Wide/Tight framing contract — #118

**Status:** Bounded technical contract for handoff; proposed schema and behavior,
not implemented or native-qualified. Delivery of #118 requires this document's
PR to merge after green CI; production implementation belongs to its successors.

## Authority and scope

- [#118](https://github.com/mbelinkie/vera-script-to-timeline/issues/118)
  owns this document-only technical contract.
- [#117's accepted product choices](https://github.com/mbelinkie/vera-script-to-timeline/issues/117#issuecomment-5629523489)
  and the accepted v3-design evidence are on main through
  [PR #346](https://github.com/mbelinkie/vera-script-to-timeline/pull/346),
  at **34d432d37b20c8332cf263951536b0d5db263d5d**. The design is accepted; no
  further design approval is needed for this contract.
- The accepted [#55 presenter-still contract](https://github.com/mbelinkie/vera-script-to-timeline/issues/55)
  and [#56 ordered-visual contract](https://github.com/mbelinkie/vera-script-to-timeline/issues/56) remain
  authoritative except for the narrow temporary On Camera preview amendment
  explicitly accepted in #117 and described below.
- [RK-19](../RESOLVE_KNOWLEDGE_GUIDE.md#rk-19--transparent-presenter-proof-is-not-continuous-presenter-reframing)
  and the [#250 qualification record](../verification/issue-250/PRESENTER_QUALIFICATION.md)
  bound what is currently proved in Resolve. They do not prove the new
  continuous-footage transform behavior.
- The current [verification policy](../VERIFICATION_POLICY.md) supersedes
  historical review or test rituals. This is documentation-only; under D-0016
  it does not need Claude review or a full local suite. The PR's cloud Validate
  check remains the full repository gate.

This contract uses the words **wide** and **tight** for exactly two treatments
of the same camera. An ordinary On Camera appearance stores one explicit
choice. A return to an On Camera parent stores a separate explicit choice and
can therefore return with a different treatment. A return to any other visual
has no presenter-framing value. Framing describes picture only: it does not
select the visible host, create a take, restart or skip source frames, or cut,
duplicate, retime, or otherwise change processed dialogue.

The format names and structures below are proposals, not claims that those
versions or types have shipped.

## Authoring semantics

The key has one closed domain:

    PresenterFramingKey = "wide" | "tight"

In the proposed script-document/v3, the On Camera payload carries the key on
that appearance:

    OnCameraPayloadV3:
      kind: "on_camera"
      presenterChoiceId: EntityId | null
      presenterFramingKey: PresenterFramingKey

The field is required for every On Camera appearance, whether the selected
presenter is a recorded take or the temporary preview still. A missing value
or any value outside the two-key domain makes a v3 document invalid for build;
the system must not guess from the previous appearance, media, or host
visibility. A source can still be unresolved while the author continues to
edit: the explicit framing value remains valid authoring data, and ordinary
unresolved-source handling determines whether a build can proceed.

The proposed v3 ReturnSlot retains its existing identity, parent, inpoint and
version, and adds one conditional field:

    ReturnSlotV3:
      id: EntityId
      kind: "return"
      parentSlotId: EntityId
      inpoint: WordInpointAnchor | WordAudibleEndAnchor | null
      returnPresenterFramingKey?: PresenterFramingKey
      version: EntityVersion

The field is required when the referenced parent currently has an On Camera
payload, and forbidden when the parent is any other visual. This is a
cross-reference rule: validation must resolve parentSlotId and inspect the
parent payload, rather than validate the return object in isolation. A return's
value is independent of the parent's value.

Changing a choice changes only that occurrence. The editor may carry its
most-recently authored On Camera choice to a new appearance; without a prior
local choice, the first value is wide. This is an editor-local authoring
preference, not project settings or compiler input. The new occurrence stores
the chosen value explicitly, and later edits to earlier appearances do not
cascade into it.

Creation of an appearance and its initial key are one undoable operation.
Undo and Redo restore the exact appearance and key together. Swapping a
return's parent payload is also one atomic, reversible edit. If the new parent
is On Camera and the return has no valid key, the editor seeds an explicit key
from that newly selected parent's current key and reports the correction as
part of the edit. If the new parent is not On Camera, the editor removes the
return key in the same edit and reports the correction. It must not leave a
stale hidden key, silently infer a value, or expose an invalid intermediate
document to save/build.

The primary visual sequence remains authoritative for which visual covers the
frame and whether the host is visible. Wide/Tight does not add a visible-host
flag, modify a cutaway relation, or change the one-level cutaway/return
ordering accepted in #56. If a cutaway temporarily covers the presenter, the
presenter source continues underneath it and the return value controls only the
picture treatment when the presenter is revealed.

## Versioning, compatibility, and migration

The implementation successor is a coordinated set of closed contracts:

- script-document/v3 adds explicit On Camera and conditional return framing
  fields while preserving every v2 field and its meaning;
- compiler-dependencies/v3 pins the build inputs described below;
- timeline-manifest/v3 carries explicit authored keys, source continuity, and
  the same applicable profile snapshot and pin;
- build-report/v3 reports framing preparation and delivery states without
  claiming unperformed native work;
- authoring-project-settings/v2 adds only an optional framingProfile reference
  to the paired snapshot. It does not store a last-used framing value.

Existing v2 contracts and authoring-project-settings/v1 remain unchanged. Old
builds replay from their old pins; migration never rewrites or reinterprets
them. Unrelated row editing, ordered visuals, timings, boundaries,
preparations, source records and report semantics carry forward into v3.

Migration is explicit and deterministic. Converting a v2 document to v3 copies
all existing content and assigns wide to every legacy On Camera payload and to
each legacy return whose parent is On Camera. It does not consult a mutable
last-used setting, infer tight from an adjacent appearance, or copy a parent's
future value into a return. The migration result records that the Wide
initialization is a semantic change and identifies the affected occurrences;
the implementation should use the v3 report's normal diagnostic/notice
vocabulary rather than invent a shipped diagnostic name here. The v2 source
document and any old build remain intact.

Migrating authoring-project-settings/v1 to v2 preserves its presenter still,
visual-only duration, identity, and other existing values. The new optional
framingProfile reference is absent unless the user explicitly associates a
qualified snapshot. No last-used treatment is added. A project without a
profile can still author and preview explicit keys; a recorded-footage build
that needs the unqualified transform remains blocked. A v3 document with
unresolved media remains recoverable under the current authoring model; this
contract does not make a missing source imply a missing framing choice.

## Paired, versioned Resolve profile

The project profile is one immutable PresenterFramingProfileSnapshot/v1 with
one id, one version, one content hash, and exactly two fixed members: wide and
tight. It is a pair calibrated under the same source and timeline context, not
two unrelated, independently mutable presets. The proposed shape is:

    PresenterFramingProfileSnapshotV1:
      schemaVersion: "presenter-framing-profile-snapshot/v1"
      id: UUID
      version: PositiveInteger
      profileHash: "sha256:" + 64 lowercase hex digits
      context:
        sourceRaster:
          width: PositiveInteger
          height: PositiveInteger
          pixelAspect: Rational
          orientation: captured source orientation
          scalingContext: captured Resolve source-scaling context
          frameRate: Rational
        timelineRaster:
          width: PositiveInteger
          height: PositiveInteger
          pixelAspect: Rational
          frameRate: Rational
        resolve: exact product, version, build and relevant API context
        adapter: exact adapter release/source identity used for calibration
      invariants:
        TransformEnabled: true
        DynamicZoomEnabled: false
        RotationAngle: 0
        AnchorPointX: 0
        AnchorPointY: 0
        FlipX: false
        FlipY: false
      wide:
        ZoomX: finite number
        ZoomY: finite number
        Pan: finite number
        Tilt: finite number
      tight:
        ZoomX: finite number
        ZoomY: finite number
        Pan: finite number
        Tilt: finite number

The four transform values are the raw Resolve API property names and numeric
values. ZoomX and ZoomY must both be positive and equal so the profile preserves
aspect ratio. Pan and Tilt must be finite. The profile does not rename these
properties as pixels, percentages, Inspector strings, or another unit. Their
unit interpretation and mapping to visible raster position are not established
by the retained evidence. No sample non-neutral values, ranges, tolerance, or
conversion formula is supplied here. #119 must qualify those facts before any
Studio automation or Free manual instructions can use the snapshot.

The context captures source and timeline raster/pixel aspect, source
orientation/scaling, relevant frame rates, and Resolve/adapter versions. Missing
context is not guessed. Raster, pixel-aspect, orientation, or scaling mismatch
blocks application; raw values are never proportionally adjusted for another
raster.

Compute profileHash with the existing canonical JSON and SHA-256 helpers. Hash
the snapshot schema version, full context, both transform tuples and all
invariants. Exclude the snapshot id/version/hash and external receipt
paths/locators. Evidence references may sit alongside the snapshot, but
machine-specific paths are not profile content. A changed transform, context,
invariant, or relevant tool version creates a new version and hash; old builds
remain pinned to the earlier pair.

Authoring-project-settings/v2 may hold an optional reference with the
snapshot's id, version and profileHash. When a build consumes that reference,
compiler-dependencies/v3 embeds the complete immutable pair, recomputes its
canonical hash, and verifies that the embedded identity/version/hash exactly
matches the settings reference. timeline-manifest/v3 records that same pin and
snapshot so an event's authored key resolves to the matching wide or tight
member. A missing snapshot is allowed for temporary preview but cannot support
a claim that continuous recorded footage has been reframed. A missing member,
stale hash, incomplete context, or context mismatch blocks that recorded
handoff; there is no unpinned fallback to guessed numbers.

## Temporary presenter preview

#117 narrowly supersedes #55's no-crop temporary-presenter rule for the
temporary On Camera preview only. The precedence for choosing the configured
presenter still remains the #55 precedence: a script override takes priority
over the project presenter still, followed by the application's pinned
fallback. Other uses of stills and the rest of #55 remain unchanged.

The proposed normalized temporary-preview policy is
temporary-presenter-preview/v1. It operates on the same configured still for
both keys. First aspect-fit and center the still on an opaque black output
frame. Then apply the key-specific uniform preview scale around normalized
center (0.5, 0.5): wide uses 1.0 and tight uses 1.35. Crop only at the final
output-frame boundary; do not stretch, animate, transition, or carry a crop
onto B-roll. The policy version and exact values are pinned with the build.
These numbers are deterministic preview engineering defaults, not measured
Resolve properties and not a producer-approved numeric look for recorded
footage. They must never be copied into a recording profile, particularly when
the preview and recording rasters differ.

When no configured presenter still is available, select one of two distinct
checked-in silhouette assets by the explicit key: a wider body composition for
wide and a closer head-and-shoulders composition for tight. Each fallback is
already framed artwork. Pin its artifact id, version, content hash, width,
height and package-relative locator. Contain it once; do not apply the
custom-still crop policy a second time. Do not put a silhouette overlay over a
configured custom still. Do not invent placeholder identifiers or substitute
an arbitrary icon, color, or unpinned asset. A missing or hash-mismatched
fallback is a preparation failure.

The accepted v3 design evidence records configured-still and no-still
interaction checks and treats its temporary Wide fallback art as a
non-blocking production-quality follow-up. This two-asset policy supplies
reproducible preview inputs without claiming the prototype art is production
quality. Temporary-presenter replacement warning/recovery remains independent:
replacing the still does not change the key, and changing the key does not
suppress the replacement requirement.

## Continuous source and dialogue invariants

The manifest must preserve one immutable source-continuity mapping for
continuous presenter footage. That mapping identifies the master/take and media
identity, source origin, record origin, rational playback-rate mapping, and
explicit boundary evidence. All treatment intervals derived from that
continuous take use the same mapping. Calculate boundaries with exact rational
frame/time arithmetic; do not independently round intervals in a way that can
skip or repeat a source frame. Do not assert continuity across intentionally
different takes.

The following 25 fps example is illustrative contract data, not a Resolve test
or evidence of supported transforms. Half-open intervals make adjacency
explicit. The synthetic master maps record frames [0,250) to source frames
[1000,1250) at rate 1:1:

| Appearance | Record interval | Source interval | Authored treatment |
| --- | --- | --- | --- |
| First row | [0,125) | [1000,1125) | wide |
| Adjacent second row | [125,250) | [1125,1250) | tight |

The intervals meet exactly at record frame 125 and source frame 1125. The
picture treatment changes at that boundary, but the source identity, take,
rate mapping and continuity group do not. No new take, source restart, skipped
frame, or repeated frame is implied.

For a cutaway over record interval [75,150), the parent presenter remains on
the continuous root underneath it. Its visible first segment is record [0,75)
to source [1000,1075), still wide. The hidden-under-B-roll segment is record
[75,150) to source [1075,1150); source time continues even while the root is
covered. The return is record [150,250) to source [1150,1250), with the
return's independently stored tight key. The B-roll occupies its overlay
interval and does not replace the parent source mapping. The return reveals
the same parent take; it does not create another presenter take or restart.

An adapter may represent a treatment boundary as two or more physical picture
items if that is what the qualified Resolve path requires. One uninterrupted
physical Resolve item is not a contract requirement. If items are split, each
boundary must preserve exact record/source adjacency, stable media identity,
and the same continuity mapping. A split is not permission to cut, relink,
duplicate, or restart the picture source.

Processed dialogue is independent of picture framing and cutaways. In the
example it remains one processed-dialogue event over record [0,250), with one
stable processed-audio identity and its unchanged authored source mapping. The
Wide/Tight boundary at 125 and return at 150 do not split or modify that
placement. The audio's source coordinate system may differ from video; the
manifest preserves the audio mapping as authored rather than assuming the
same media or frame rate. A regression check compares the audio event and its
source mapping before and after adding picture framing.

The proposed manifest records each continuity group with its immutable
master/take/media identity and content/probe hashes, record/source origins,
rational rate mapping, and the independent processed-dialogue event identity.
Each picture-treatment interval names its document/block/slot or return,
parent, continuity group, half-open record and derived source ranges, framing
key, profile pin (or temporary-preview policy/asset pin), and generated event
identity. Covered intervals retain their source range and visibility state;
they are not discarded as absent presenter media. A physical item split maps
back to these same logical intervals.

The report lists each row or return boundary with the expected source-frame
adjacency, unchanged dialogue-event identity, requested key and pinned profile.
Native observations, when actually obtained, are recorded separately from
those expectations with the target/readback result and completion state. An
expected range or a string saying continuous cannot substitute for observed
native evidence. The compiler emits deterministic expectations now specified
by this contract; only the qualified adapter can later add actual readback.

## Delivery names and truthful status

The selected key remains authoritative even when the delivery route cannot yet
apply it. For target grouping, the text labels have exact authoritative
prefixes OC WIDE and OC TIGHT followed by the stable event id. The key/event
identity is what determines the requested treatment. Blue for OC WIDE and
Orange for OC TIGHT are auxiliary grouping colors only. If the target or API
cannot retain a color, record that limitation; it does not change authored
semantics. A missing or changed text prefix blocks grouping verification.

The proposed v3 report state vocabulary distinguishes intent, work and proof:

- **requested** records the authored key and target route;
- **pending** means the adapter has begun but has not completed verified work;
- **applied_verified** is emitted only by the native adapter after setting the
  qualified properties, reading them back, saving and reopening the target,
  and reading back the same values again;
- **manual_required** is available for a Free target only when a matching
  snapshot and target-specific Inspector mapping have already been qualified.
  It supplies instructions from that snapshot, never invented or preview
  values;
- **manual_reported** records that a user says they entered the values. It is
  not native readback or proof that the timeline retained them;
- **blocked** records a missing profile, unqualified API/Inspector mapping,
  context mismatch, stale hash, absent labels, or other unmet prerequisite.

Automatic completion belongs to the adapter because only it can observe the
current target, perform the mutation, read back the properties and verify the
saved/reopened timeline. The compiler may report requested or blocked work but
must never set applied_verified from a profile snapshot or a historical
receipt. A historical receipt is not current target readback. Do not silently
downgrade a Studio automatic request into a Free manual path. A Free manual
path is explicit and available only after the corresponding mapping is
qualified. Without that mapping or the exact raster-matched snapshot, report
blocked rather than manual_required.

## Current evidence and unresolved capability

The retained records establish these limited facts:

| Evidence | What it actually proves | What remains unproved |
| --- | --- | --- |
| #117 accepted design and retained run evidence ([prompt](../prototypes/issue-117/claude-s01-s03-wide-tight-amendment-prompt.md), [run record](../prototypes/issue-117/claude-run-evidence.md)) | Accepted per-appearance Wide/Tight semantics, return independence, preview interaction, carry-forward, Undo/Redo and picture-only continuity intent | Production asset quality, implementation, compiler contracts and Resolve transforms |
| Current v2 authoring contract ([script-document-v2](../../contracts/script-document-v2.schema.json)) | On Camera payload has nullable presenterChoiceId; ReturnSlot stores parent/inpoint; neither stores framing | v3 fields, persistence and parent-swap validation |
| Current project settings ([authoring-project-settings-v1](../../contracts/authoring-project-settings-v1.schema.json)) | Project presenter-still reference and visual-only still duration; script can override the still | A framed project profile reference |
| Current adapter ([workflow_v2.py](../../python/vera_timeline_agent/workflow_v2.py#L1206)) | Still-composition path writes and immediately reads back neutral ZoomX=1, ZoomY=1, Pan=0, Tilt=0 plus neutral rotation/anchor/flip and dynamic-zoom-off settings; timeline verification checks expected properties again | Non-neutral transforms on continuous video, their numeric units/raster mapping, Studio/Free Inspector mapping, and per-appearance persistence after a framing boundary |
| RK-19 and [#250 qualification](../RESOLVE_KNOWLEDGE_GUIDE.md#rk-19--transparent-presenter-proof-is-not-continuous-presenter-reframing) | On Studio 21.1.1 build 10, the exact 320×720 RGBA temporary still composes over a continuing root with an independent overlay; retained checks include decoded pixels, save/reopen geometry and same-MOV PCM | Wide/Tight on continuous footage, a non-neutral ZoomX/Y/Pan/Tilt profile, or general motion/focus behavior |
| Current v2 compiler ([compiler-core-v2.ts](../../packages/contracts/src/compiler-core-v2.ts#L671)) | Recorded presenter selections are refused with a blocking migration-review diagnostic; temporary still composition is contain/center/black/no motion and emits its replacement warning/recovery | A qualified continuous-recorded-media provider or its framing route |

The existing native setter uses ZoomX, ZoomY, Pan and Tilt, but evidence
exercises only their neutral values for still composition. It establishes no
units or formula mapping them to Inspector values or output pixels. #250's
raster measurements verify still geometry, not a non-neutral transform.
RK-19 leaves continuous reframing to #118/#119; native capability remains
bounded by #47/#119.

The smallest useful #119 delta is a protected disposable project with one
continuous synthetic presenter source and one exact interval. Put two labeled
samples, OC WIDE and OC TIGHT, on one timeline, bound to that same interval and
source. Capture source/timeline raster, pixel aspect, orientation/scaling and
relevant frame rates. Set/read back the four raw transform properties and
neutral invariants; save, reopen and read them again. Render only after
readback succeeds, then verify distinct crops and advancing source content
across the boundary. Add B-roll/return to test that delta, not before. Verify
dialogue is one unchanged event. If Resolve needs physical item splits, verify
exact adjacency rather than requiring one item. Qualify Free Inspector mapping
separately before emitting manual instructions. This proposed proof has not
been run for #118.

## Focused acceptance and test coverage for implementation

The following are contract checks for later implementation. This task has not
run them.

| Area | Minimum acceptance check |
| --- | --- |
| v3 structure | Accept only wide/tight on On Camera payloads; reject a missing/other value, an On Camera return without its own value, and a non-On-Camera return with a value. Validate parent references across sequence entities. |
| Editing and history | Creating an appearance persists the local seed once; first appearance defaults wide; changing an earlier value does not cascade. Verify creation, parent swap, return-key repair/removal, Undo and Redo each restore the whole atomic state. |
| Migration/replay | Migrate legacy On Camera payloads and their On Camera returns to wide deterministically; record the semantic initialization. Preserve all unrelated v2 fields and leave old builds/replay bytes unchanged. Migrate project settings without adding last-used state. |
| Snapshot integrity | Verify fixed wide/tight members, finite values, positive equal zoom axes, neutral invariants, canonical hash inputs/exclusions and pin identity. Mutating a transform/context changes the hash; changing excluded external locator or identity does not. Missing/stale snapshots and raster mismatches block without rescaling. |
| Continuity/audio | Verify exact adjacent record/source intervals across Wide→Tight and Wide→B-roll→Tight return. Permit an exact-contiguous item split. Assert source identity and mapping continue and the one processed-dialogue placement and source mapping remain byte/equivalent unchanged. |
| Preview determinism | Same configured still yields the pinned wide/tight normalized previews; no custom still selects the matching pinned silhouette, with no overlay or second crop. Hash failures fail preparation; temporary-still warning/recovery remains independent of the key. |
| Report and grouping | Verify exact OC WIDE/OC TIGHT prefixes with stable event ids; absent color records only a limitation, absent label blocks grouping. Test each proposed report state and prove only adapter readback plus save/reopen can yield applied_verified; manual_reported is never native proof, and there is no silent Studio-to-Free downgrade. |
| Native delta | Keep non-neutral calibration, target raster matching, save/reopen property readback and rendered continuity as #119 real-Resolve evidence. A fixture or mock alone cannot mark this capability qualified. |

These checks cover the #118 handoff's closed key domain, independent return
state, picture-only semantics, immutable profile pins, deterministic preview,
source/dialogue continuity, truthful delivery states, and native proof
boundary. Implementations may refine field names while preserving these
semantics. Non-neutral values and a claim that Resolve applies them remain
out of scope until #119 supplies evidence.

## Analysis provenance

DeepSeek-V4-Pro supplied the initial bounded technical draft. Codex verified
and corrected it against the accepted #117 records, current v2 contracts and
compiler/adapter source, RK-19, the #250 qualification, and the current
verification policy. The initial model text was input to this review, not
authority or Resolve evidence. No private account, billing, credential or local
artifact details belong in this record.
