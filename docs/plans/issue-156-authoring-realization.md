# Issue #156 — authoring-contract realization plan

Status: **proposed for Producer acceptance**. Documentation only, on
`codex/issue-156-authoring-realization`; baseline
`96978919616df0148d9c4b06781aeb80acfa85e4`. Planning acceptance does not approve
the change notes below, implement a contract, qualify media/Resolve behavior,
or authorize follow-up issue creation, promotion, dispatch or external effects.

## 1. Outcome, authority and boundary

Deliver the finite schema, compiler, media, migration and application handoffs
needed for Q1 authoring with per-row temporary narration and a new
24000/1001-fps Studio timeline. Ordinary supported Research/local CFR clips
must work without author preconversion. Preserve v1 replay and immutable prior
builds. New implementation packages are proposed once in §8, not dispatched.

Canonical dependencies for this planning issue:

- Blocked by #55
- Blocked by #56
- Blocked by #127

Rationale: these accepted notes and successor rules supply the defaults,
structural timing and presentation semantics being realized. All were Closed
and Done at claim and resume. No library dependency is proposed; installed
JSON-schema generators, rational arithmetic, FFmpeg/FFprobe and existing
artifact/job machinery are sufficient.

Authoritative source pins are listed in
[source-pins.json](../verification/issue-156/source-pins.json). Accepted notes
absent from this baseline checkout must be read at their pinned Git revisions;
their presence in Git does not mean main contains their implementation.

| Source | Accepted revision / relevant content |
| --- | --- |
| [#147](https://github.com/mbelinkie/vera-script-to-timeline/issues/147) | `75029de57baa594d3dfc7f509a09cfc21943e088`: completion audit and Producer brief. Q1 is local single-writer Studio, English initial test sources, 23.976, durable build/review/recovery; prompter optional, Free and inbound later. |
| [#55](https://github.com/mbelinkie/vera-script-to-timeline/blob/a561735e7b0c735ccd6185aa407e82581a19b2d9/docs/investigations/issue-55-presenter-visual-contract.md) | `a561735e7b0c735ccd6185aa407e82581a19b2d9`: D55-01–07, presenter defaults, visual-only duration, undefined/request/intentional distinctions. |
| [#56](https://github.com/mbelinkie/vera-script-to-timeline/blob/9e2b8817ffe97fbc9d6fcf31099aca578c5022bb/docs/investigations/issue-56-ordered-visual-contract.md) | `9e2b8817ffe97fbc9d6fcf31099aca578c5022bb`: §§2–14, one primary sequence, hierarchy, edit/trim/anchor rules, complete clip, v2 and migration. |
| [#127](https://github.com/mbelinkie/vera-script-to-timeline/blob/cdaa3106da91fb5a040c8bbde22e2c61c0d3e162/docs/prototypes/issue-127/successor-handoff.md) | `cdaa3106da91fb5a040c8bbde22e2c61c0d3e162`: row-local numbers including independent Graphic overlays, quiet singleton, genuine presenter resumes, separate M namespace. Accepted source HTML hash is retained in the pinned handoff and checkpoint. |
| [D24](https://github.com/mbelinkie/vera-script-to-timeline/blob/e72aa2436fa49d6b256b7cf811d5c1dea39120c3/docs/investigations/issue-24-representative-script-coverage.md) | `e72aa2436fa49d6b256b7cf811d5c1dea39120c3`: D24-01–03, 08–09, 11 and §7 taxonomy/Unplaced/timing invariants. Later D24 features retain existing owners. |
| Product specification | Baseline `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, §§6.1–6.4, 7, 8.1–8.4, 9.1–9.6, 13; `docs/IMPLEMENTATION_PROGRESS.md` retains acceptance/frozen history only. |
| Runtime baseline | Baseline four v1 schemas, compiler/validator, narration, package/Studio and #144 sources. Their observed interfaces are in §7. |
| Research reference | Published `0499666c59167cef9dcd2665845f7ef6090e64df`, export settings/media adapter and completed M5 source records. An implementation selects and pins its actual compatible Research revision; this reference is not current cross-product acceptance. |

Exclusions: actual schemas/generated types/fixtures/goldens/accepted tests,
product code, persistence migrations, Research/private data or original media
changes, acquisition, paid calls, uploads/sharing, Resolve operations,
repository migration and rough HTML. #148 continues unchanged; retained
preparation evidence may supply identities only within its stated limits.
Recorded presenter/conform, music spanning rows, motion/capture/composites,
transitions beyond cuts, collaboration, Free delivery and inbound production
reconciliation are later packages, not hidden Q1 prerequisites.

## 2. Decisions and precedence requiring an explicit change note

These are the plan's selected proposals. CN-1/CN-2 in §9 must be approved
separately before they become production contracts.

1. **Parallel v2 with frozen v1.** Carry #55 defaults and placeholder semantics
   into #56's structural v2, rather than modifying v1. A v2 narrated row has
   one primary sequence; host visibility is derived from topmost primary
   picture. Independent overlays never change that host state. #55's
   independent authored host lane remains the v1 rule, not an additional v2
   authority. Selecting On Camera/full-frame media edits primary payload;
   selecting overlay preserves it. No shadow host span is stored in v2.
2. **Separate ordinal projection from structure.** #56 slot order/IDs remain
   structural. The human visual ordinal follows accepted #127: all non-OC
   primary visual occurrences and independent overlays sorted by start anchor,
   primary before overlay on a coincident start, then stable occurrence ID.
   Reset per narration row; singleton `1` remains visible. An OC payload has
   no visual ordinal; a return has none and reuses its parent's reference.
   Structural slot index is retained separately in manifest resolution. An
   overlay crossing two clips belongs to neither. Music's M namespace stays
   reserved for its later owner. Ordinals are projections, never machine IDs.
3. **D24 timing has three explicit contexts.** Primary picture takes timing
   exclusively from sequence boundaries; no freeform range/duration fields.
   Independent timed overlays use consistent two-of-three authoring timing.
   A visual-only block gets its start from block order and duration from #55.
   Unplaced items have no derived interval; proximity/order is repair evidence,
   not attachment. This scopes the apparent D24/#56 conflict without creating
   competing authorities.
4. **Choose immutable build-time normalization for mismatched CFR.** Use one
   bounded preparation adapter, P5, over existing tool machinery. Deliver
   verified same-rate picture to the package/Studio path. Native mixed-rate
   placement is not the selected Q1 path: current placement/readback assumes
   matching source/record frame counts and has no retained mixed-rate proof.
   Reconsidering native support requires a separate qualified adapter change,
   not a silent fallback. Compatible same-rate media bypasses video encoding.
5. **No silent retime.** CFR sampling changes which picture samples represent
   normal playback time; it does not change playback speed or audio pitch.
   Permit only that explicitly approved sampling/endpoint quantization in
   CN-2. It is not #56 authorization to fill short footage by holding, looping,
   optical flow, speed change or extension.
6. **Q1 schema/type realization does not qualify #145's loop.** Preserve
   #144/#145 v1/25-fps fixtures and source pins. Requalify new v2/23.976 output
   separately through P8 and #160. Application inbound remains later; do not
   port its move/trim/omission inference as a hidden compiler dependency.

## 3. Exact contract and generated-type handoff

The four roots are new Draft 2020-12 schemas with closed objects, explicit
version discriminants and safe integer validation. Internal arithmetic uses
BigInt/Fraction; reject overflow before serialization. Reuse v1 semantics for
identity/hash/anchors through copied/versioned definitions, not permissive
unknown fields or remote `$ref`s. Schema additions cannot reinterpret v1.

| File / root title / schemaVersion | Required realization |
| --- | --- |
| `contracts/script-document-v2.schema.json` / `ScriptDocumentV2` / `script-document/v2` | Keep document/project/live-head identity, stable tokens and active block order. Add `scriptSettings`, `NarrationBlockV2.primaryVisualSequence`, `NarrationBlockV2.overlayEvents`, and `activeDraft.supportingItems[]`. Remove v1 full-frame `visualEvents` and canonical `hostVisibilitySpans` from v2. Add visual-only block and typed Unplaced/supporting items. Draft-invalid states remain serializable. |
| `contracts/compiler-dependencies-v2.schema.json` / `CompilerDependenciesV2` / `compiler-dependencies/v2` | Frozen build/document/compiler/profile identity, required `authoringDefaults`, timeline/tracks/roles, narration with token timing map, occurrence resolutions and preparation attestations. Dependencies are occurrence-keyed, not one trim per media reference. Reject missing/extra active occurrence bindings and stale text/revision/hash. |
| `contracts/timeline-manifest-v2.schema.json` / `TimelineManifestV2` / `timeline-manifest/v2` | Integer record/delivered-source ranges, complete source hashes, root/child/overlay track roles, `visualSequenceResolutions`, `supportingItemResults`, rational source-time mappings, settings/defaults/duration basis, composition and boundary evidence. Returns retain provenance and emit no new source event. |
| `contracts/build-report-v2.schema.json` / `BuildReportV2` / `build-report/v2` | Matching document/build/manifest hashes, event accounting, typed row/item diagnostics and recovery actions, media preparation summary, source sufficiency, migration/Unplaced issues and preview/release readiness. Preserve legacy report envelope meaning; blocked/refused results never claim ready. |

Ancillary `contracts/authoring-project-settings-v1.schema.json` is the narrow
#55 input with `AuthoringProjectSettingsV1`, `PresenterStillReference` and
`settingsHash`. Retain exactly #55's project default/script override/generic
fallback resolution, immutable artifact/version/hash/provenance and 3000-ms
default. Settings omission on a legacy read is inheritance; no eager backfill.
Every newly prepared v2 build freezes effective values plus settings identity.

### 3.1 Document entities and placement authority

Use #56's exact named shapes and field spelling: `WordInpointAnchor`,
`BoundaryBefore`, `ContentSlot`, `ReturnSlot`, `PrimaryVisualSequence`,
`SourceUsage`. `ContentSlot` keeps ID, relation, boundary, payload,
`playoutPolicy` and version. Payload ID/trim/audio/framing/provenance move in a
swap; structural ID/boundary/relation/playout do not. `ReturnSlot.inpoint=null`
is a visible authoring state. Missing/stale anchors are never repaired by
nearest-word, quote search or ordinal fallback.

`PrimaryVisualPayload` discriminants are `on_camera`, `visual`, `undefined`.
The visual payload adds explicit `pictureKind` = `unresolved_visual | clip |
image | capture | graphic | intentional_placeholder` and the verified or
unresolved source reference. A user screenshot is Image unless a real Capture
relationship exists. Capture/Graphic references retain their owning contract
and immutable revision; Q1 does not implement live capture or a graphics
library. Unknown/unimplemented treatment capabilities refuse explicitly.

Narration-free `VisualOnlyBlockV2` owns one payload plus `visualOnlyTiming`:
still-like Image/Capture/static Graphic/intentional Placeholder accepts optional
positive `durationOverrideMs`; otherwise frozen default. A clip has an explicit
selected source interval and forbids duration override. Source-audio standalone
clip duration follows that selected interval. Section/direction/note/citation
blocks and excluded content add no program duration.

Source-clip `audioPolicy` is `mute | quiet | full`, displayed as No/Quiet/Full
as adopted by #127. Proposed `source-clip-level/v1` fixes Quiet at -18 dB and
Full at 0 dB; these are playback gains, not derivative-media processing.
Narrated primary/overlay clips allow No or Quiet and default to Quiet when a
verified audio stream exists. Full requires a narration-free standalone clip;
such a clip defaults to Full. A source without audio defaults to No and cannot
claim either audible mode. No dynamic ducking, gain overrides or mixer is
introduced. CN-1 requires the Producer to approve this concrete Quiet level.
Two enabled source-clip audio occurrences overlapping in record time block
Q1 delivery with `SOURCE_AUDIO_OVERLAP`; repair explicitly mutes one or changes
placement. Picture visibility does not suppress a continuous root's audio.

`activeDraft.supportingItems[]` is one document-owned collection. Each item has
an explicit `orderKey` and optional display attachment evidence; it is not
duplicated in narration blocks. Promotion to a primary/overlay occurrence is
an atomic identity-preserving move, with a lineage record, not a second active
copy. An already placed primary/overlay is not also an active supporting item.
`SupportingItemV2` has stable `id`, `version`, explicit `role`, readable
content/source provenance, and `placement`:

- roles `picture`, `audio_cue`, `citation`, `editor_note`, `draft_note`,
  `reference`; a picture carries the subtype above;
- `unplaced`: reason plus optional prior anchor, source-order and neighboring
  block evidence; forbids a compiled interval;
- `range`: exact `TextAnchorRange` (independent lane only);
- `point`: exact typed word/between-block/event-edge anchor, for Editor marker
  or a designated timed start/end;
- `timed`: `start`, `end`, `durationMs`, with any consistent two required for
  buildable independent Picture/Audio intent. At least one anchor is required;
  duration alone remains Unplaced. All three must agree in exact resolved
  time, not merely round to matching frames.

For the Q1 two-of-three resolver, anchor times use the same authoritative token
map as the compiler. `start+end` derives duration; `start+duration` derives end;
`end+duration` derives start. Reject negative/out-of-row/zero duration and stale
anchors. Quantize resulting endpoints once with §5 rules, retaining original
intent and delta. An independent full-frame Picture cannot bypass primary
structure: explicit promotion inserts a slot at an exact start and previews
the replaced coverage; an imported free interval stays Unplaced until repaired.
No duration-derived overlay boundary becomes an invented word anchor.

Citation/Reference/Draft note have no events. Editor note creates one point
marker only when placed, otherwise a visible warning. Audio-cue execution
remains with #100; Q1 retains a typed unavailable capability and cannot silently
mix it. Unplaced active Picture blocks ordinary Preview and Release; forced
Preview may render existing undefined coverage, retaining the Unplaced
diagnostic/card without pretending it acquired a range. Non-timed supporting
items do not block build solely because they have no interval.

### 3.2 Dependencies, timing maps and output evidence

Proposed exact additional dependency definitions:

| Definition | Required fields / ownership |
| --- | --- |
| `RationalTime` | `numerator` signed safe integer, `denominator` positive safe integer, reduced fraction in seconds. Nonnegative source/record times; signed deltas. Checked rational arithmetic, no decimal rate substitution. |
| `NarrationTokenTimingMapV2` | `blockId`, `blockRevision`, `textHash`, `tokenizationVersion`, `narrationAssetId`, `audioHash`, `timingHash`, `alignmentVersion`, `precision`, `tokens[]`. Each token has `tokenId`, original UTF-16 offsets/quoted spoken text, exact start time, optional evidenced audible end, and end basis. |
| `OccurrenceMediaResolutionV2` | `payloadId`, `slotId` or `overlayEventId` or visual-only `blockId`, `mediaReferenceId`, source-system snapshot/version/package/hash, logical source bounds/rate, `SourceFrameMapV1`, occurrence source in, selected source range where legal, source-audio stream mapping and verified delivered source. Same media reused with different trims has different occurrence resolution. |
| `SourceFrameMapV1` | `packageFrameZeroLogicalFrame` integer, `packageVideoPtsOrigin` exact rational seconds, `loggedTimeAtPackageFrameZero` exact rational seconds, decoded package rate/count and time base, source-audio offset/sample mapping, descriptor/probe hashes. Original catalogue times/frame labels are provenance with their own rate; they cannot be substituted for package-rate frame indices. §5.2 defines the checked transforms. |
| `PreparedMediaBindingV1` | `requirementKey`, `mode=verified_reuse|derived_cfr`, original identity/hash/probe hash, target rate, exact requested origin/duration/handles, policy/profile/tool hashes, original↔delivered time mapping, output hashes/probe/frame-count/audio checks, authorization reference and immutable artifact locator. Derived mode requires derivation record; reuse mode forbids fictional derived identity. |
| `VisualSequenceResolutionV2` | document/row/sequence versions and IDs; structural slot index/relation; payload/return IDs; boundary input and resolved record frame/delta; root continuous ranges, child ranges and topmost appearances; derived host state and ordinal references; event IDs; source range/mapping/preparer identity; presenter choice and alignment precision. |

`PresenterAlignmentResolution` remains a declared versioned port keyed by
slot/take with verified source frame/identity and word evidence as #56 requires.
Q1 supplies only `temporary_still`; recorded-mode requests refuse as unavailable
until #45/Phase 6–7 qualify a provider. That later provider is not a dependency
for temporary narration or generic stills.

V2 event provenance includes `documentId`, `blockId`, `sequenceId` where
applicable, `slotId`, `payloadId`/`overlayEventId`, source original/derived
identity, timing-map hash and compiler version. A root has one continuous event
on a lower managed primary track; children occupy one higher managed track;
independent overlays stay above both. Roles remain configurable but preflight
rejects collisions/inadequate topology. A return reveals the existing advancing
source; no restart event. An opaque child's picture does not implicitly unmute,
duck or suppress a parent's audio policy. Unsupported layered audio intent must
be explicit and fail rather than inferred from visual visibility.
An enabled source-audio event freezes `audioPolicy`, `levelPolicyVersion` and
`gainDb` (-18 or 0), original stream/time mapping and exact sample endpoints.
Mute emits no source-audio event; narration retains its own established level.
P7 must preserve and apply this gain through a qualified Studio/OTIO seam,
or refuse that capability. Merely copying an audio stream does not realize Quiet.

Temporary presenter still = contain/center/opaque black/no motion, source
resolved override > project > pinned torso. Each root/child OC occurrence uses
its structural identity for stable event identity. Report
`TEMPORARY_PRESENTER_STILL` and `REPLACE_TEMPORARY_PRESENTER`. Visual-only duration
uses `ceil(ms*T/1000)`; 3000 ms at 24000/1001 yields 72 frames. Preserve exact
author text for intentional placeholder with `placed` disposition and no
unresolved issue. Undefined and unresolved requests stay separate; forced
Preview retains blocking `VISUAL_UNDEFINED`; Release cannot adopt that policy.

Generated outputs: preserve byte-identical
`packages/contracts/src/generated/contracts.ts` as the `VeraContractsV1`
surface; add `contracts-v2.ts` with `VeraContractsV2` and the four v2 roots plus
settings. Add an explicit `@vera/contracts/v2` export. Python retains existing
v1 modules and adds `script_document_v2_schema.py`,
`compiler_dependencies_v2_schema.py`, `timeline_manifest_v2_schema.py`,
`build_report_v2_schema.py`, `authoring_project_settings_v1_schema.py`; update
`__init__.py` exports without renaming v1 imports. The current generator feeds
all schemas to Python: P2 must separate/pin generation groups so adding v2
cannot renumber/rewrite existing v1 definitions. Currentness checks cover both
surfaces. No hand-edited generated types and no consumer casts to erase version.

## 4. Pure authoring/compiler and source-map handoff

Keep existing `validateScriptDocument` and `compileTimeline` as v1 exports.
Add `validateScriptDocumentV2`, `projectPrimarySequenceV2`,
`applyVisualSequenceEditV2` and `compileTimelineV2` in sibling modules, plus
explicit version dispatch at new application boundaries. Unsupported/mixed
document/dependency/manifest versions refuse before side effects. No global
compiler switch in the #144 harness.

Pin the new public seams: `packages/contracts/src/authoring-v2.ts` exports the
v2 validator, projector and edit command through `@vera/contracts/authoring-v2`;
`compiler-core-v2.ts` exports the v2 compiler and media-needs resolver through
`@vera/contracts/compiler-core-v2`. The generated-only `@vera/contracts/v2`
surface remains separate. The Python token adapter is a sibling
`narration/compiler_dependencies_v2.py:narration_v2_dependency_from_asset`,
consuming the validated asset plus frozen token snapshot. Existing v1 imports
and entry points keep their names and bytes.

`applyVisualSequenceEditV2(document, expectedSequenceVersion, command)` returns
either one new canonical revision with operation evidence or diagnostics and
the original bytes. Commands are exactly #56's insert sequential/cutaway,
add sibling, convert/flatten group, move shared word boundary, swap payloads,
cross-row move with destination/repair, delete and mode switch. Null return is
created atomically with cutaway; failed destination cannot remove source.
Base deletion promotes children and inserts undefined at the former return,
preserving old outpoints. Reattachment is explicit; Undo retains IDs/evidence.

`projectPrimarySequenceV2` is a pure derived view: continuous roots, children,
returns, topmost host state, ordinal/caps and stale/renderability diagnostics.
Exact word intervals drive cap/highlight/OC bold presentation. The accepted
five-word `media_cut_estimate/v1` remains a separate display projection, using
validated preview timings or 400 ms/token fallback, invalidated by all timing
inputs. It never enters dependencies/manifest as an anchor. Media-led resolved
cuts have unnumbered markers and real token relation; no exact-word brackets.

The v2 narration adapter consumes `NarrationAudioAsset` and hash-verified
provider timing from the existing cache. Preserve the existing Polly mapping
from provider UTF-8 SSML ranges to original text to UTF-16 offsets. Bind each
mark to the frozen token ID/text/offsets/revision; do not regenerate token IDs
from ordinal position. Punctuation, repeated words, apostrophes, combining
characters and surrogate pairs must retain their original associations. Word
starts with next-word-derived ends are labeled honestly. Sentence-only timing
cannot satisfy an exact spoken-word structural boundary: emit
`word_timing_required`, keep the document, and obtain an authorized word map.
No paid synthesis is implied by adapter acceptance.

`compileTimelineV2(documentInput, dependenciesInput)` is pure and returns
diagnostics or canonical manifest/report JSON with complete accounting. Order:

1. Validate version/hash/scope, sequence grammar and all occurrence bindings.
2. Resolve word/return boundaries from the frozen token timing map; resolve
   media-end cuts from original logged time, never derived file length alone.
3. Quantize once; assert strictly increasing positive intervals, legal media
   boundaries and consistent independent two-of-three timing.
4. Derive continuous parent/child/overlay needs and required source duration.
   Validate sufficiency against original logged bounds before accepting a
   delivered artifact. P5 preparation uses the same deterministic needs.
5. Validate effective settings, delivered artifact binding/audio mapping and
   preparation verification. Compile duration-bearing blocks in order.
6. Emit events, return/boundary/source-map evidence, markers and diagnostics;
   validate canonical manifest/report accounting and deterministic ordering.

There is no compiler→transcoder cycle: P4 exposes pure
`resolveMediaRequirementsV2(document, timing/defaults/sourceDescriptors)` using
the same boundary resolver. #157 resolves narration and source descriptors,
calls this function, invokes P5 and then compiles with verified bindings. It
does not compute different timing in a service or infer needs from UI ranges.
Changing any frozen input requires a new requirement/snapshot; late stage
results cannot bind to another revision.

Schema-invalid input or unknown narration duration returns `ok:false` with
diagnostics and emits no manifest. A known narration spine permits
`ok:true` with a diagnostic manifest and `report.status=blocked`; that result
is never deliverable. Semantic blocking rows emit no partial
primary events; a deterministic blocked report/resolution explains suppression
and preserves row timing where its narration is known. Delivery refuses any
blocked report. Explicit forced Preview is limited to undefined/request policy;
it cannot override stale/null/collapsed boundaries or inadequate source.

## 5. Mixed-rate temporal policy and bounded profile

### 5.1 Selected support envelope

P5 supports decoded CFR rates `24000/1001`, `24/1`, `25/1`, `30000/1001`, `30/1`
into target `24000/1001`; equivalent reduced rationals compare equal. Same-rate
verified reuse is allowed at other compiler-configured rates, but conversion
to another target is explicitly unsupported until qualified. Initial video
profile: one selected H.264/HEVC 8-bit SDR progressive stream in MP4/MOV/MKV,
square pixels, no unhandled rotation/edit-list/timecode offset, up to 3840×2160;
AAC or PCM mono/stereo source audio at 44.1/48 kHz. Reject unknown color/HDR,
interlacing, ambiguous multiple streams, unhandled offsets or decode failures
with exact remediation. Stream selection must be frozen, not guessed.

Use frame PTS/duration and decoded count across the required range to establish
CFR and offset. `r_frame_rate == avg_frame_rate` alone is insufficient.
Timestamps quantized by container ticks may have bounded one-tick discrepancy
from `origin+k/Fs`; genuine varying intervals, missing/duplicate PTS, drift or
unverifiable rate yield `unsupported_vfr_or_timebase`. VFR/retiming/speed ramps
are refused in Q1; preserve the card/reference and offer a separately audited
normalization policy or another source. Routine supported CFR proceeds through
the visible preparation plan without a manual per-clip conversion step.

### 5.2 Exact arithmetic and trim mapping

Let source rate `Fs=Ns/Ds`, target `T=Nt/Dt`. Frame intervals are half-open.
Logical source-frame bounds are `[L,U)`, occurrence inpoint `I`, all integral
indices at the inspected package rate `Fs`. The proposed `SourceFrameMapV1`
sets `O=packageFrameZeroLogicalFrame`, `P0=packageVideoPtsOrigin`, and
`H=loggedTimeAtPackageFrameZero`. These freeze the checked mapping:

```text
package frame for logical x   p(x) = x - O
expected package video PTS    pts(x) = P0 + p(x)/Fs
original logged source time   log(x) = H + p(x)/Fs
```

Decoded PTS must match this cadence within the container-tick bound. Require
`0 <= L-O < U-O <= decodedFrameCount`. A catalogue frame label at a different
original rate must first resolve to exact original time and the verified export
mapping; it is not a package frame index. An unprovable or non-unit-speed
export mapping refuses. #81/#82's Research descriptor handoff and #85's local
inspection supply this new verified map; no claim is made that today's
millisecond export descriptor already proves it. Local input normally uses
`O=0`; neither PTS nor an original catalogue time is assumed to start at zero.

For a word-driven structural record duration `R` frames:

```text
record duration seconds       D = R * Dt/Nt
package-relative source start a = (I-O) * Ds/Ns
package PTS / logged start    P0+a / H+a
package-relative source end   b = a + D
required exclusive logical    J = O + ceil(b * Fs)
source-frame cover surplus    εs = (J-O)/Fs - b, 0 <= εs < 1/Fs
```

Require `L <= I < U` and `J <= U`; root needs include time under children.
Do not compare `R` directly with `U-I`. `εs` is source-frame read coverage,
not permission to lengthen record playback. A decoded source frame covers its
natural interval; no new editorial content may begin at/after `b`.

Derived normalization is per occurrence requirement, with output origin at
the exact source inpoint `a`. This avoids trimming a global target-grid file
at a rounded offset. At output frame `j`, evaluate package PTS `P0+a+j/T` and
select the source frame whose presentation interval contains that time
(zero-order-hold sampling):

```text
logical selected frame       k(j) = I + floor(j * Fs/T)
decoded package frame        p(j) = k(j) - O
original logged sample time  H + p(j)/Fs
```

Use actual source PTS/origin to verify this relation. The selected frame must
remain inside logged/read bounds. Lower target rate skips samples; a higher
target can display a naturally active source frame on successive target
frames. Q1's selected conversion matrix is downsampling; no interpolation,
motion smoothing, optical flow or playback timestamp scaling. Frame-rate
conversion must never use input `-r` to reinterpret timestamps or stream-copy
metadata as if it produced target-rate frames.

For complete-clip or standalone selected-source duration:

```text
D = (U-I)/Fs                 # or explicit selected out minus in
R = ceil(D*T)
δr = R/T - D, 0 <= δr < 1/T
```

The last output sample starts before the real source end and its normal target
display interval ends at the shared next record frame. Record this terminal
quantization; never generate a new sample starting at/after the real end.
Audio stops at the exact source end (within one output sample); any sub-frame
tail contains no invented speech. The following event begins at that same
record frame. This is the narrow CN-2 endpoint allowance, not indefinite hold.

Word boundary with exact time `w` resolves once to
`rowStart + ceil(w*T)`; store `delta=resolved/T-w`. Two boundaries collapsing
to one frame block. Media-end classification uses actual evidenced token
supports when available: `at_word_start`, `inside_word`, or `between_words`.
Without audible word-end evidence, next-word-derived ends cannot prove a
silence; retain an explicit derived/unknown relation rather than fabricate
`between_words`. That precision refinement needs CN-1 and tests.

At 25 fps into 24000/1001, 240 record frames are 10.01 seconds and need 251
source frames from an integer inpoint. At 30 fps they need 301. A 250-frame
25-fps complete clip lasts exactly 10 seconds and records 240 frames with
10-ms terminal quantization. A 300-frame 30-fps clip has the same result.
Three source frames at 25 fps last 0.12 seconds, producing three target frames
and 5.125-ms terminal quantization. These are arithmetic examples, not observed
runtime behavior.
Nonzero-origin control: `Fs=25`, `O=L=3000`, `P0=2`, `H=120`, `I=3010`,
`U=3300`, `R=240` gives `a=0.4`, `b=10.41`, `J=3261` (package exclusive
frame 261). The first output frame reads package frame 10 at PTS 2.4 and
logged time 120.4; output frame 239 reads package frame 259. Using `I/Fs`
would wrongly seek 120.4 seconds inside this package.

Handles are explicit in requirements, default zero for Q1 hard cuts. Future
requested pre/post handles must be verified inside authorized package bounds;
they cannot widen editorial logged use or fill insufficiency. If encoded with
handles, choose whole target-frame handle offsets so the selected occurrence
origin still lands exactly on a target frame; record any source read expansion.
Refuse missing required handles; requesting a longer immutable Research export
belongs to #81 and its audited flow. P5 never acquires or modifies a clip.

### 5.3 Audio, verification and quality thresholds

Use the same source-time origin for picture and audio. Preserve inspected
audio/video offset; an unqualified offset refuses rather than zeroing each
stream separately. Decode original audio and derive synchronized 48-kHz PCM
WAV through existing tooling; preparation makes no loudness, tempo, pitch,
channel-layout or speech processing changes. The separate manifest playback
gain realizes §3.1's Quiet/Full policy; it does not alter canonical or derived
source audio bytes. If already compatible, reuse verified audio.
Separate immutable PCM avoids encoder priming becoming unexplained sync.
Map original sample start/end through exact rational source time; boundary
rounding is at most one 48-kHz sample and is retained. Container/source delay
must be decoded and evidenced, not guessed.

Derived picture profile `authoring-cfr/v1`: H.264 High/yuv420p, preserve source
dimensions/aspect/qualified SDR metadata, libx264 CRF 18 / preset medium /
one encoding thread, no copied timestamp/creation metadata, and one pinned
implementation/build/platform fingerprint. Proposed precise filter route:
decode and frame-index trim to the verified package interval, subtract only
the selected origin from PTS, then
`fps=fps=24000/1001:start_time=0:round=up:eof_action=pass`, with output truncated
to the exact required `R` frames and no second implicit fps conversion.
This is an implementation inference from the documented rounding/output
algorithm, not measured behavior; P5 must verify the `k(j)` formula on the
actual pinned build and reject discrepancies. Research's current `round=near`
and millisecond range API cannot be used unchanged for this policy. Audio is
trimmed by verified sample bounds from the same origin, then resampled to
PCM-24/48 kHz without the narration normalizer's loudness/compressor stages.
Reuse Research's bounded FFmpeg argument/probe pattern; do not call its
acquisition or source-scratch deletion lifecycle on authoring/canonical media.
The implementation must verify the precise filter/profile against the formula;
the profile is not qualified merely by choosing a CLI flag. FFmpeg documents
timestamp-based sampling and the risk of input rate coercion in its
[filters](https://ffmpeg.org/ffmpeg-filters.html#fps) and
[CLI](https://ffmpeg.org/ffmpeg.html#Video-Options). Those are tool facts, not
VERA acceptance. Pin the installed documentation/tool build used at P5.

Acceptance tolerances are separate and cannot be collapsed into Research's
older 250-ms export tolerance:

- output picture frame count and target rational PTS cadence: exact; original
  source-frame selection matches `k(j)`, with only container-tick probe error;
- word/record boundary: exact chosen integer frame; rational ceil delta less
  than one target frame; no accumulating per-word rounding;
- source cover surplus: less than one source frame, with no new sample beyond
  exact requested end;
- complete-source terminal quantization: less than one target frame, explicitly
  retained; word-driven output duration exactly `R/T`;
- derived PCM duration/sample offset: within one output audio sample of exact
  requested source time; constant sync residual <=1 ms, drift <=1 ms between
  start/middle/end sync probes;
- final Studio review codec delay is measured/compensated in verification:
  aligned audio sync residual <=10 ms and drift <=5 ms across start/middle/end;
  decoded duration differs by at most one target frame. A codec that cannot
  meet that evidence remains unqualified; never relax thresholds silently.
- source-clip playback level: solo rendered PCM compared with the aligned
  original measures Quiet -18 dB / Full 0 dB within 0.5 dB on nonsilent probes;
  No has no source-audio event. Measure with narration disabled for this level
  probe and separately listen to the real narration mix. No inferred ducking.

Use synthetic numbered frames, flash/click/speech markers and waveform checks
to verify picture selection and sound timing; lossy picture hashes cannot be
compared to original frame bytes as if encoding were lossless. Producer
inspection must also reject unacceptable visible sampling judder, quality
loss or audible artifacts. Failed thresholds stop qualification, preserving
the source/build and exact measurements.

### 5.4 Identity, reuse, authority and recovery

Requirement key hashes canonical original artifact/version/content and package
manifest hashes, selected stream/probe/PTS mapping, exact origin/duration/
handles, target rational rate, audio preparation/stream policy, profile/version/tool capability
hash and mapping-policy version. UI name/path/time are never keys. Do not put
build ID in the reusable media key; the immutable build snapshot binds that
key, verified output hashes and preparation receipt. Profile/tool/rate/trim
change invalidates reuse. Original and derived IDs remain distinct in every
dependency, manifest and receipt. Changing a locator only re-verifies bytes.
Playback gain is a compiler/build-snapshot input, not a media-byte cache key;
a level-only edit reuses identical verified picture/PCM instead of encoding.

Compatible same-rate video uses `verified_reuse` and preserves source in/out
at its rate; reuse does not invent a conversion provenance record. Mismatched
video uses `derived_cfr` and delivered sourceRange begins at the documented
derived selected offset, normally zero. Video/source-audio pairs share one
time-mapping identity. Thumbnail derivation stays on original source trim,
with #56's current-key/late-result/decode failure rules; derived frame ordinals
cannot replace original thumbnail or transcript identity.

Build authorization freezes approved read roots, source/package access,
project-managed write root, reuse/media policy and permitted local conversion.
P5 preflights tools, supported streams/PTS, source hashes, required disk and
free-space policy before an attempt. `Reuse only` accepts an existing exact
verified derivative or refuses with an actionable conversion-needed state;
it cannot start encoding secretly. The product displays the preparation plan
and estimated new bytes through #70, no developer terminology required.

Stage under an attempt-owned directory, verify every output and atomically
publish one immutable artifact record. No original/canonical replacement,
ordinary media hard link or deletion. Cancellation/interruption never promotes
partial bytes. Reconciliation distinguishes incomplete staging, verified
unpublished result, exact published result and conflicting result. Retry the
same requirement idempotently; re-probe/hash before reuse. A corrupt derivative
is quarantined by the audited artifact flow and regenerated from verified
source, not overwritten in place. Missing source permits hash-verified relink
or #81 re-export; otherwise keep intent and report missing media. Cleanup acts
only on attempt-owned scratch under the product's retention policy; failed
cleanup is visible. Build/checkpoint/published-artifact references prevent
pruning. Concurrency uses the existing job/requirement lease and immutable
publication, not a new scheduler/cache service.

## 6. Compatibility, migration and recovery

Support v1 validation/replay of immutable documents and packages throughout
Q1 and Q2. No sunset date is selected; retirement needs a separately accepted
inventory/migration gate. New authoring creates v2. Existing v1 opens through
its supported v1 reader until explicit migration; never treat a v1 row as a
v2 primary sequence merely because it looks flat. No dual-write of both models.

P6 proposes `VisualSequenceMigrationReportV1` containing input document/version/
hash, migration algorithm/profile version, candidate v2 hash, per-row state,
original→new entity map, preserved source references, reasons/evidence and
explicit repair/activation decisions. Migration produces a new candidate
revision with lineage; keeps the original readable and buildable via v1.

Auto-convert only exact gap-free non-overlapping word partitions whose host
and picture agree, whose every boundary is a word start/row end and whose
quotes/token IDs/overlay roles are valid. Build flat roots; never infer
hierarchy. OC becomes an authored OC payload; matching full-frame visual
becomes visual payload. Overlays remain independent. Legacy unresolved
placeholders stay requests, never intentional. A legacy referenced visual
block becomes a supporting/overlay occurrence only when role is unambiguous;
it must not acquire standalone duration from table position.

Overlaps/gaps, conflicting host state, sentence/cue-only anchors, ambiguous
shared boundaries/overlay classification, stale quoted text, zero duration,
unsupported source/treatment or possible content loss =>
`migration_needs_review`. Retain all source entities/evidence and require exact
manual reconstruction; no nearest-match proposals are auto-committed. Mixed
rate does not itself block document migration when source identity is known;
actual preparation is a later build gate.
Legacy standalone `use_source` maps to Full; `mute` maps to No. A narrated
legacy `use_source` cannot silently become Quiet because that changes level:
retain it in the report and require an explicit No/Quiet repair decision.

Activation is one optimistic/idempotent authorized transaction bound to source
live-head hash and approved candidate/report hash. New source edits invalidate
activation; retry cannot create duplicate revisions. Cancel discards only the
unactivated candidate reference and leaves v1 active. Restart reloads report/
candidate/decisions. Rollback selects the retained v1 revision as a new
attributed head operation, preserving v2 work/history and all builds; it does
not delete the migration or change old artifacts. Persistence schema changes
belong to #64/#72 with an approved migration note and reversible deployment/
backup evidence, not a plan-side database rewrite.

Prompter remains optional #68. Its v2 input adapter derives OC/VO from exact
word topmost appearance and writes the accepted `prompter-export/v1` shape.
Frozen v1 export goldens remain byte-identical. A media cut inside a word
cannot fabricate a new word/camera cue. Music and other unavailable features
retain typed intent; they cannot enter output merely because migration found
a file mention.

## 7. Existing interface map and consumer ownership

Paths below exist at the baseline unless marked proposed. A reference is not
an assumption that its accepted v1 implementation can consume v2 unchanged.

| Seam | Existing interface and change reach |
| --- | --- |
| TS compiler/validator | `packages/contracts/src/compiler-core.ts:compileTimeline` returns v1 manifest/report/canonical JSON; `script-validator.ts:validateScriptDocument`. Sibling v2 exports/modules and `packages/contracts/package.json` export registry, new callers/tests only. Keep existing helpers and safe integer/rational algorithms. |
| Provider→timings | `python/vera_timeline_agent/narration/polly.py:PollySourceMap`, `utf8_range_to_utf16`, `build_polly_ssml`, `_parse_marks`; `models.py:NarrationAudioAsset`; `compiler_dependencies.py:narration_dependency_from_asset`. P4 adds token-bound v2 projection; no provider/cache rewrite or timing precision inflation. |
| Contract generation | `packages/contracts/scripts/generate-contracts.mjs`, TS aggregate, Python generated modules and `tests/test_generated_contracts.py`; explicit separate registries and currentness tests. Existing imports stay stable. |
| OTIO package | `python/vera_timeline_agent/otio_package/package.py:build_otio_package`, `verify_otio_package`; currently strict v1 schema and rational source/time conversion. P7 adds fail-closed v2 support without erasing sequence/media evidence into a v1-looking manifest. |
| Import package/materialization | `resolve_import_package/package.py:build_resolve_import_package(manifest_path, report_path, materialization_plan_path, project_root, ...)`, `verify_resolve_import_package`; strict report linkage, paths/hashes, source/record semantic and probe checks, OTIO roundtrip and immutable receipt. Extend versioned receipt with mapping/preparation hashes while preserving v1 bytes and copy/clone protections. #81/#82 own Research authorization/resolve/minimum immutable copy, #85 original local import. |
| Studio | `studio_assembly.py:run_studio_assembly`, `StudioAssemblyAdapter`; `studio_spike.py:PublicResolveAdapter.place_events/verify`. Current placement/readback expects source frame ranges, tracks, durations and source starts. P7 validates new lower-root/upper-child topology, delivered rate/audio bounds, slate/composition and stable IDs. No arbitrary project mutation or UI fallback. |
| Durable stages | `build_jobs.py:StageContext`, `StageAdapter.reconcile/execute`, `publish_immutable_output`, `run_one`. The engine stores one opaque immutable output file per stage, digest+size; no generic receipt JSON schema. #157 composes the adapters and writes one versioned summary receipt referencing immutable media records/package hashes. It must not overload the single receipt with unverified data or change generic job semantics. |
| Review/delivery | #71 consumes a verified Studio target and writes/validates MP4 then optional Drive attempt. Bind native render job/settings/output to build/timeline hashes. Upload retry preserves successful local output; sharing remains explicit. P8 qualifies render truth; #160 tests the app path. |
| Application UI | #65–#67 consume v2 model/edit/projector; #69 consumes frozen narration state; #70 reports prep/build/refusal/recovery; #153/related canonical row UI retain their accepted ownership. #64/#72 persistence/auth contracts gate activation/storage, #81 source snapshots/handoff, #85 import. No new duplicate editor or QA owner. |

#144's `issue-144-*` TypeScript and Python `roundtrip_*` callers/hashes remain
v1. P4/P7 cannot alter their frozen source pins as incidental reuse. If a shared
helper extraction would change proof files, prefer using the existing public
helper or local bounded v2 logic; any accepted source/test amendment needs its
own approved note. #145's actual environment/evidence can inform P8 identity
and limitations after acceptance, but does not block independent schema work
or supply v2 runtime qualification.

## 8. Finite implementation packages and gates

These identifiers are planning package names, not new issues. Sizes/routes
are tentative; steward assigns exact supported model/effort on intake. All
need their own one-issue/branch claim and approved change-note boundaries.
No package is Ready because this plan is accepted. Dependencies below are
output dependencies with one-line reasons; replace names by exact canonical
`Blocked by` issues before promotion. No blanket dependency on later D24.

| Package / size / tentative route / authority | Owned outcome, interfaces and dependency reason |
| --- | --- |
| **P1 Document/settings schemas**, M, Sol/high, Automated | New ScriptDocumentV2/settings schema definitions and schema tests only (§3.1); root requires accepted #156 and CN-1. Supplies stable serialization to all consumers. No generated code/compiler/UI. |
| **P2 Dependency/output schemas and types**, M, Sol/high, Automated | Other three v2 schemas, preparation/timing/migration record definitions and generated TS/Python surfaces/registries/currentness. Requires P1 for shared document IDs/definitions, CN-1/CN-2 and CN-3 for permitted new samples. No runtime generation/media/Resolve. |
| **P3 Sequence edits/validator/projection**, M, Sol/high, Automated | Pure edits, structural validator, D24 placement resolver and #127 derived presentation (§4). Requires P1/P2 to prevent drift from serialized contracts. No UI implementation; supplies tested commands/projections to existing UI owners. |
| **P4 Narration map and v2 compiler**, M, Sol/xhigh, Automated | Token timing adapter, pure media-needs resolver, sequence/default/visual-only compiler and report/new goldens. Requires P2/P3 for exact schema/structural invariants. Consumes synthetic verified P5-shaped bindings so compiler development does not require real media prep. Preserve v1 byte regression. No paid calls/native delivery. |
| **P5 Verified CFR media-preparation adapter**, M, Sol/high, External | One selected adapter only (§5), origin/rate/audio/identity/cache/probe/atomic recovery and real-tool synthetic matrix. Requires P2 for attestation contract and P4 for the authoritative media-needs API; CN-2/CN-3 approved. It wraps existing FFmpeg/FFprobe/process/verification patterns; no Research acquisition engine. Does not own #157 stage composition, import/copy or app QA. |
| **P6 Explicit migration and activation**, M, Sol/high, Producer | Candidate/report/repair/activation/cancel/rollback/restart (§6). Pure migration requires P1/P3; actual persistence activation requires accepted #64/#72 version/auth handoff and CN-4. Split pure candidate versus service activation before Ready if those interfaces are not accepted; do not expand into building a service. No historical rewrite. |
| **P7 V2 package/Studio delivery adapter**, M, Sol/high, Automated | Dual-version package validation/OTIO/readback, v2 receipt/media mapping and new-topology assembly through selected #34/#109 boundary. Requires P2/P4 and delivered P5 for real prepared bytes; accepted #34 contract, plus #109 if injected product delivery selected. Unit/fake/readback tests supply adapter readiness, not Studio acceptance. No render/upload implementation. |
| **P8 V2/23.976 Studio qualification**, M, Sol/high, External | Exact accepted P7 build in actual approved Studio save/reopen/render, mixed-rate/audio and refusal/recovery matrix below. Requires P5/P7 and accepted selected native connection/render adapter (#71 or explicitly bounded existing render port). Pin environment from accepted #145 if reused; a different environment needs fresh preflight. No inbound loop, design finalization, Free or app QA duplication. |

P4 may be split into token map/media-needs and manifest compiler before Ready
if its exact test matrix cannot fit one M slice; same interface, no giant v2
ticket. Likewise P6/P7 split only at named service/native seams. A package that
cannot name exact input, gate or acceptance authority stays Backlog/Blocked,
not a vague L implementation placeholder.

Existing UI acceptance packages consume P1/P3, with P4/P6 where they display
timing/migration. #157 must add the exact delivered P4/P5/P7 prerequisites
before Ready and bind them to real `resolving_media → compiling → package →
Studio` receipts. #160 retains integration/QA and adds P8 plus the delivered
runtime packages transitively or directly. #156 alone cannot unlock either.
#81/#82 supply immutable Research descriptor/copy; #85 provides original local
inspection. No production compatibility prerequisite is added to #148.

### 8.1 Deterministic fixture and test packages

New data is proposed under `tests/data/authoring_v2/`, `tests/data/media_cfr_v1/`
and `tests/data/migration_v2/`, never replacing existing fixtures. Each gets
README, frozen source/tool/profile descriptor, SHA-256 inventory, positive/
negative inputs and outputs. Synthetic media generator belongs to P5; no
private source becomes a fixture. Freeze accepted new data only after its
slice accepts; later changes require a note.

| Owner | Required tests / exact expected evidence |
| --- | --- |
| P1/P2 | `packages/contracts/test/schema-v2.test.ts` proposed: every discriminant/closed field/version/context/conditional, safe integers and settings precedence; TS/Python cross-language schema roundtrip; `npm run check:contracts-generated`; v1 generated files unchanged. |
| P3 | `authoring-v2.test.ts` proposed: OC→two children→return; reversed advancing B-roll parent; overlay crossing roots; quiet singleton/overlay start tie; exact shared-boundary edit; swap/base swap/refused mode swap; destination refusal; base deletion; null/stale/equal/crossed boundaries; Unplaced promotion, two-of-three inconsistency; pointer/keyboard projection same data (UI evidence stays its owner). |
| P4 | `compiler-v2.test.ts`, `tests/test_narration_v2_dependencies.py` proposed: byte-identical repeat canonical manifest/report and new goldens for flat, root/child/reversed/overlay, settings inheritance/fallback, all visual-only durations at 24000/1001 and alternate rate, undefined forced/release/request/intentional, complete media cuts at/inside/between/unknown word relation, frame collapse, source shortage and diagnostics. Exact token association across punctuation/repeated words/Unicode and wrong timing hashes/revisions. |
| P5 | `tests/test_media_preparation_v2.py` proposed: real local FFmpeg/FFprobe synthetic 25/30,24,30000/1001→24000/1001; same-rate bypass; 44.1/48-kHz source audio; nonzero origin/trim, root hidden duration, near-end/exact/one-frame-short bounds, explicit handles, all rational rounding examples, audio flash/click start/middle/end, VFR/ambiguous/HDR refusal, output falsely labeled CFR, stale/corrupt source/derived hash, tool/profile/key invalidation, disk/cancel/interrupt/duplicate publish/reconcile. Byte-identical same-input output under pinned deterministic profile; mismatched bytes refuse cache reuse. |
| P6 | `migration-v2.test.ts` plus service tests proposed: safe flat mapping, every #56 review case, original entity retention, unresolved remains request, no inferred hierarchy, standalone `use_source`→Full and `mute`→No, narrated `use_source` requiring explicit No/Quiet repair with original audio intent/evidence preserved, cancellation/restart/duplicate activation/stale-head refusal/rollback. Original v1 bytes and all prior artifact hashes unchanged. Producer sees exact candidate/report and repairs one flagged row. |
| P7 | `tests/test_v2_delivery.py` proposed: full strict manifest/report/prep/media binding, path/symlink/wrong-bytes attacks, OTIO parsed against exact record/source tracks/ranges/hash/metadata, continuous root and return-no-event, overlay topology, No/Quiet/Full gain mapping and overlap refusal, still/default/placeholder composition, wrong/fractional rate refusal, package receipt/retry, fake Studio save/reopen readback mismatch and partial-target preservation. |

Run each proposed focused test first, then existing relevant tests and full
`npm run validate` under locked Node 24.19.0/npm 11.17.0/Python 3.12.14/uv
0.12.5. Proposed test paths are future deliverables, not commands claimed to
exist today. Retain commit/profile/tool versions, canonical artifact hashes
and actual command results on each implementation issue.

Frozen v1 control: all four schemas, v1 generated TS/Python definitions,
`fixtures/`, accepted `tests/data/slice_0_2`, `slice_1_1`, `slice_1_3`,
`issue_37`, accepted #144 sources/tests/data remain unchanged unless their
own note is explicitly approved. Run existing compiler-core/validator/prompter,
generated, fixture, OTIO/import-package/Studio and #144 regression suites.
Compare minimal/torture manifest/report and v1 prompter output **as bytes**;
semantic JSON equality alone is insufficient. Track compiler source pins too:
changing implementation source can invalidate proof evidence even with equal
output. Any necessary registry extension is isolated under CN-1; it cannot
rewrite v1 type bytes or accepted tests.

### 8.2 Real Studio gate P8 and actual application gate #160

P8 freezes STT/Research source commits, schema/type/compiler/preparer/profile/
tool hashes, media source/derivative hashes and mappings, approved roots,
Studio edition/build/platform/connection, project/timeline identities, expected
manifest/report, owned render-job/settings/output hashes and measurement script.
An operator authorizes fresh disposable targets through the product boundary.
No in-place rebuilding or sole-project overwrite. Preserve failed targets.

| Required case | Success / refusal / recovery evidence after save/reopen/render |
| --- | --- |
| Same-rate 24000/1001 | Verified original video reused with no encode invocation; intended trim/duration/word cuts/still/overlay tracks and source hashes exact. |
| Research source-default 25 fps + local 30 fps | Both go through P5 automatically in one 24000/1001 build. Actual original rates confirmed. Native events point to the pinned derived bytes, intended source in/end, normal-speed numbered samples and audio sync meet §5. No author preconversion/JSON edits. |
| Fractional 30000/1001 + 24/1 | Real sampled cadence and nonzero inpoint; no decimal-rate accumulation; flash/audio start/middle/end thresholds met. |
| Continuous root with child/return + independent overlay | Reopened native track order/range/readback and rendered samples prove root advances under child, return restarts nothing and overlay crosses clips independently; transparent composition/presenter contain matches manifest. |
| Visual-only/complete-clip endpoints | 72-frame default, explicit override, and 10-second source end with 10-ms terminal quantization; shared cut frame, no extra source speech, correct exact-text intentional slate. |
| No/Quiet/Full source sound | No emits none; Quiet under narration and Full standalone meet the solo -18/0-dB ±0.5-dB level check plus normal mix listening. Save/reopen retains the effective gain. Overlapping enabled source sound refuses with the named repair. |
| Refusal | VFR/unhandled profile, short source, stale anchor and wrong-derived bytes block before native build; no negative-only acceptance or successful-looking partial timeline. |
| Recovery | Interrupt prep before/after verified output publication, restart/reconcile/reuse; unavailable Studio waits; render failure retries from verified target; readback mismatch retains evidence and fails; prior source/build/timeline intact. |

Operator inspects exact returned project/timeline after save/close/reopen,
checks native identity/source starts/durations/counts/settings/track order and
compares rendered picture/audio to expected samples. Reports actual maxima
for duration, source quantization, audio offset/drift and word/cut frames.
API settings/readback alone cannot prove frame sampling, audible sync or
composition. A render file alone cannot prove which native job produced it.
Bind both. P8 closes only on actual qualified evidence and its named authority.

#160 then repeats the Research clip→ordinary insertion→local import→per-row
temp narration→new Studio timeline→review/recovery path through the **real
application**, retaining exact compatible commits and config. #157 stage
receipts must link authorization/snapshot→prepared media→compiler manifest→
verified package→native target→render. Include source-default Research export,
25/30 inputs across cases, same-rate reuse, VFR actionable failure and interrupted
prep recovery without JSON editing. Its existing Research #21/full M7,
service/setup and UI gates remain. Component P8 evidence cannot close #160.

## 9. Separately approved change-note boundaries

These proposed notes are reviewable specifications, not permission to change
frozen assets. A future implementation issue must retain the exact approved
note revision and response before editing its boundary.

| Note | What changes and why / breakage / regeneration / acceptance |
| --- | --- |
| **CN-1 V2 authority/types** | Add four v2 schemas/settings, structural primary and derived host state, independent overlays/ordinal projection, typed supporting/Unplaced/two-of-three, honest token relation and No/Quiet/Full source-clip playback (-18/0 dB) with overlap refusal. Reconciles #55 with #56/#127/D24 (§§2–4); the Quiet level/defaults need explicit Producer judgment. Breaks v1 full-frame/audio editors/callers for v2 input; retains unchanged v1 replay and explicit narrated `use_source` migration repair. Generate separate TS v2 aggregate and five new Python modules; update registries/exports with frozen-v1 controls. Acceptance adds structural/type/Unicode/source-map/migration goldens, playback gain/readback/render proof and existing UI handoffs; no schema test preaccepts runtime. |
| **CN-2 Normal-rate CFR mapping** | Permit §5's narrowly bounded source sampling and endpoint quantization; add prepared-source identity/time/audio evidence in dependencies/manifest/report and adapter receipts. Supersedes #55's mismatched-rate rejection for v2 and refines #56's no-frame-repeat rule solely for normal-rate sampling, never shortage fill. Existing rate-equality callers must use verified binding, not coerced metadata; source frame counts no longer equal original record counts. Regenerate P2 v2 types only. Acceptance requires exact math/profile matrix plus real-tool and Studio audio/render proof; VFR/speed/unsupported refusal explicit. |
| **CN-3 New fixture/golden packages** | Add only slice-owned sanitized data under §8.1, plus new hash-pinned generic torso asset/descriptor implementing #55 (P4-owned fixture acceptance). Why: v2 semantics and rates cannot be proven by frozen v1/25-fps evidence. No replacement of accepted fixture/golden/test. Regenerate only new expected outputs, record generator/tool/profile, independent byte-repeatability and frozen boundary audits; real Studio gate remains separate. Any old-data correction is a separate note, not this allowance. |
| **CN-4 Migration/persistence activation** | Add candidate/report/lineage and optimistic/idempotent activation/rollback records through #64/#72 (§6). Why: no silent reinterpretation or content loss. New service storage/version API must accept v1 and v2 and retain old heads/builds; old v1 clients cannot write v2. Regenerate the selected service/API types if its owning schema changes, plus migration report v2 surface already in P2; no generic database migration invented here. Acceptance includes stale-head/cancel/restart/rollback and authorized backup/restore at the persistence owner. |

Exact approval for a selected note is `Approve #156 CN-<number> at <plan commit>`.
The Producer may approve separately after accepting the plan. A changed note
needs new approval. Plan acceptance alone never edits any frozen boundary.

## 10. Design verification, forecast and Producer handoff

Retained design evidence is
[design-checks.json](../verification/issue-156/design-checks.json): source blob
pins and interface existence, package dependency DAG and owner allocation,
rational arithmetic examples, artifact references, scope/frozen-boundary audit,
repository checks and tool versions. These checks qualify the **plan and
unchanged baseline**, not new runtime behavior. The inspection history is in
[checkpoint](issue-156-authoring-realization-checkpoint.md); later findings and
selected decisions in this plan supersede its provisional choice.

Forecast: after first substantive inspection, 2–4 remaining active hours,
medium confidence, chiefly mixed-rate interfaces/acceptance. Producer-requested
checkpoint wait excluded. After bounded Luna inventories and design synthesis,
remaining work was revised at 11:58 EDT to **20–40 active minutes**, medium
confidence, for the final correction review, retained checks and handoff.
The baseline Python gate is still running; its elapsed wait is separate from
that effort estimate. Producer approval and future external/Studio execution waits are
separate. No 24-hour threshold or implicit dispatch follows from this estimate.
At final handoff the planning/check work is complete: full baseline validation
passed, including 274 TypeScript/Node and 369 Python tests. The Python gate took
3681.16 seconds elapsed; this is retained test execution, not additional product
implementation. Remaining work is Producer review, followed only by separately
authorized change-note approval/intake/implementation.

Producer checklist (review the exact commit/hash linked on #156):

1. Open this plan §§2–4. Expected: one v2 primary sequence, independent
   overlays, #127 human numbering, #55 defaults/states and D24 Unplaced behavior
   agree; v1 remains intact. Judge the explicit authority reconciliations and
   Quiet's proposed -18-dB playback/default/overlap policy.
2. Review §5, particularly 25/30→24000/1001 and source/audio end examples.
   Expected: normal playback, bounded recorded quantization, original identity,
   verified derivatives, no routine author preconversion; unsupported/VFR
   refusal and retry are concrete. Judge the proposed profile/quality bounds.
3. Review §§6–8. Expected: explicit migration/repair/cancel/rollback; finite
   implementation packages with exact seams and acceptance; #157/#160/#81/#82/
   #85 keep their ownership, and #148 remains unaffected. No giant v2 ticket or
   later-scope dependency is hidden.
4. Review §8.1 versus §8.2 and retained design checks. Expected: unchanged-byte
   v1 regression, new v2 goldens, real 23.976 Studio save/reopen/render and
   actual application QA are separate gates. Accepted #145 evidence cannot
   substitute for them. Judge whether this is enough before Q1 runtime claims.
5. Review §9. Expected: each implementation boundary has a separately approved
   change note with changes, breakage, type regeneration and acceptance; this
   plan creates/dispatches nothing and changes no contract/media/Resolve data.
6. Reply `Accept #156 authoring-contract realization plan at <commit>` or
   `#156 acceptance failed at step <number>: <first decision or interface to change>`.

Leave #156 **In review** until that explicit response. Passing design checks
and a completed agent turn never mark it Done.
