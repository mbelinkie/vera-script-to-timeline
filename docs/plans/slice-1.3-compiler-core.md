# Slice 1.3 — Compiler core plan

## Status and gate

**Agent implementation and local verification complete; acceptance pending.**
D-0014 was authorized on 2026-08-26. Slices 1.1 and 1.2 and the Text+
follow-up are accepted. The accepted minimal and torture ScriptDocuments
remain frozen and are reused read-only. Two consecutive full local validation
gates and final independent no-findings review pass; two CI runs and producer
acceptance remain.

This plan records the complete decision bundle so implementation can proceed
without question-by-question producer involvement after the contract gate.

## Bounded scope

1. Add the approved shared compiler-dependency contract and regenerate types.
2. Add a pure TypeScript compiler library in the contracts/API-side workspace:
   frozen `ScriptDocument` plus validated `CompilerDependencies v1` in;
   `TimelineManifest v1` plus `BuildReport v1` out.
3. Validate the ScriptDocument structurally and semantically before compiling,
   then validate dependency identity, revisions, hashes, timing, ordering, and
   media coverage without mutating either input.
4. Use active narration as a contiguous timing spine; excluded narration emits
   no source, event, duration, or marker movement.
5. Resolve half-open token anchors through verified word/sentence marks and
   compile shared millisecond boundaries to integer frames with exact rational
   arithmetic.
6. Emit OC presenter placeholders, authored local-media visuals, overlays,
   explicit unresolved visual placeholders, narration audio, requested source
   audio, section/direction markers, and representable hard cuts on the
   adjustable section 9.2 track map.
7. Emit deterministic manifest/report bytes and byte-identical goldens for the
   accepted torture ScriptDocument.
8. Add a small Python adapter/test that maps the accepted narration cache record
   into the narrow shared narration dependency. It does not alter cache layout
   or identity.

## Explicit exclusions

- OTIO/package writing or package verification (Slice 1.4).
- Resolve Free import or Studio assembly (Slices 1.4–1.5).
- Durable jobs, editor/API persistence, UI, collaboration, or build submission.
- Voice generation, provider calls, normalization, cache mutation, or voice
  choice changes.
- Media copying, probing, resolution, download, or research-project access.
- Transition types other than hard cuts, timing overrides, retiming, motion,
  graphics, subtitles, music/SFX, or recorded performance conform.
- Changes to `ScriptDocument v1`, `BuildReport v1`, `/fixtures`, accepted Slice
  1.1 inputs/tests, accepted Slice 0.2 data/tests, or existing goldens.
- Any dependency or lockfile addition.

## Deterministic compiler decisions

These decisions become D-0014 when the producer approves the contract note.

### Input, order, and invalid-input result

- Require one dependency bundle whose document-facing IDs and revisions exactly
  match the frozen ScriptDocument.
- Traverse every block in `activeDraft.blocks` by `orderKey`; duplicate
  `orderKey` values anywhere in that surface are a blocking diagnostic rather
  than an arbitrary UUID tie-break. Excluded rows still participate in order
  validation even when they emit no duration.
- Both accepted visual-event storage forms remain real occurrences. Visual
  event IDs and media-reference keys must resolve uniquely.
- Ignore excluded narration and excluded note/draft blocks for compilation;
  retain their structural validation.
- A visual event anchored to excluded narration is a blocking
  `ANCHOR_TARGET_EXCLUDED` precondition diagnostic and returns `ok: false` with
  no outputs; excluded narration has no timeline range on which an honest slate
  or event could be placed.
- A document with no active narration cannot produce the schema's positive
  timeline duration. Structural/dependency/order failures return a deterministic
  `CompileResult { ok: false, diagnostics }` with no manifest/report rather than
  inventing a one-frame edit. Valid inputs return `ok: true` with both outputs;
  a failed narration asset may still yield a schema-valid blocked report as
  described below.

### Narration spine and frame math

- Place active narration blocks contiguously from `timeline.startFrame` in
  sorted block order.
- Derive each block duration from exact normalized `durationSamples` and
  `sampleRate`, never from rounded `durationMs`.
- Convert every relative time boundary with one exact rational ceiling:
  `ceil(timeMs * fpsNumerator / (1000 * fpsDenominator))`.
- Convert sample duration with
  `ceil(durationSamples * fpsNumerator / (sampleRate * fpsDenominator))`.
- Reuse the same compiled boundary for both sides of adjacent events. This
  prevents gaps/overlaps and never truncates narration to an earlier frame.
- Set `timeline.durationFrames` to the final active narration end minus
  `timeline.startFrame`.
- Do not use binary floating point in identity-bearing frame calculations.

### Anchor resolution and precision

- Retain D-0006's half-open affinity semantics: start `before` includes the
  start token, start `after` advances past it; end `before` ends before the end
  token, and end `after` includes it.
- Map each word mark's UTF-16 source range to exactly one accepted token and
  require monotonic mark time/range order. Do not require provider mark `value`
  to equal token `value`: inline alias/phoneme controls may legitimately change
  spoken display text while preserving the mapped authored source range.
- For word timing, a token begins at its observed provider word start and ends
  at the next observed word start or exact block audio end. Emit
  `word_start_with_derived_end`.
- Sentence timing may resolve only an anchor whose accepted-token interval is
  exactly the full token coverage of one or more complete, contiguous sentence
  marks. Sentence punctuation/whitespace may extend outside the first/last
  token offsets, but a qualifying mark may contain no accepted token outside
  the selected interval. Derive the final end from the next sentence start or
  audio end and emit `sentence_start_with_derived_end`.
- Missing, duplicate, ambiguous, nonmonotonic, out-of-range, or token/source-
  range-mismatched marks are blocking diagnostics. `none` precision never invents
  proportional word timing.
- A ready asset whose marks are malformed, or whose sentence-only evidence
  cannot resolve every required anchor in its block, follows the same blocked
  output path as failed narration: keep its exact-duration A1 audio, label the
  narration/timing-slate events `unavailable`, suppress every other anchored
  event for the block, and emit a blocked report. This is `ok: true` because
  valid diagnostic outputs exist; the report status, not the result
  discriminant, prevents package promotion.

### Failed narration

- A failed Slice 1.2 asset still contributes its exact duration-preserving
  audible placeholder on A1 with timing precision `unavailable`, so later
  narration never shifts earlier.
- Because its word anchors cannot be resolved honestly, emit one whole-block V5
  timing-failure slate, suppress every other anchored picture/presenter/source-
  audio event for that block, add blocking issues for those authored events,
  and set the build report status to `blocked`.
- Still emit deterministic manifest/report evidence for diagnosis; Slice 1.4
  must not promote a blocked report to `ready_to_import`.

### Placeholder source payloads

Every placeholder occurrence owns one UUIDv5-derived source; sources are not
shared across authoring occurrences. Templates are exact and deterministic:

- OC presenter: event UUIDv5 name `presenter-event:<spanId>`, source UUIDv5 name
  `placeholder-source:presenter:<spanId>`, label
  `PRESENTER: <quotedText>`, reason
  `Presenter/A-roll footage is unresolved for on-camera span <spanId>.`, and
  the anchor's resolved word/sentence precision.
- Authored unresolved visual: the authored visual-event ID, source UUIDv5 name
  `placeholder-source:visual:<eventId>`, label
  `UNRESOLVED VISUAL: <description>`, reason
  `Authored visual event <eventId> is unresolved.`, and the anchor's resolved
  precision.
- Failed visual: the authored visual-event ID, source UUIDv5 name
  `placeholder-source:visual:<eventId>`, label
  `FAILED VISUAL: <authored label-or-description>`, reason
  `Authored visual event <eventId> has status failed.`, and the anchor's
  resolved precision.
- Unusable narration timing: event UUIDv5 name
  `timing-placeholder-event:<blockId>`, source UUIDv5 name
  `placeholder-source:timing:<blockId>`, label
  `TIMING UNAVAILABLE: <blockText>`, reason
  `Narration block <blockId> has no usable text alignment.`, and precision
  `unavailable`.

The matching narration A1 event also uses `unavailable` when its block follows
the timing-failure path; a ready, usable narration block's A1 event uses
`frame`, because its sample-derived record placement is frame-verified while
its anchored picture events carry the derived word/sentence label.

### Track routing

- Use the dependency bundle's adjustable tracks and role bindings; track names,
  IDs, and extra tracks are not contract invariants.
- Every role binding must reference exactly one declared track of the required
  kind; the four role targets are pairwise distinct, and duplicate track IDs or
  same-kind indices are rejected.
- Narration audio uses the configured narration role (default A1).
- Requested source audio uses the configured source-audio role (default A3).
- Every authored ready visual, including overlays, uses the video track whose
  index equals its `layer`; missing, duplicate, or non-video layer targets block
  compilation. V4 is the default overlay layer, not a compiler override.
- An explicit unresolved visual placeholder always uses the configured V5 role,
  regardless of authored layer.
- A visual event whose authored status is `failed` also compiles as a labeled
  V5 placeholder with a warning. It never consumes a resolved local-media
  dependency or masquerades as placed media. Explicit unresolved and failed
  visual slates behave the same for preview and release; release identifies an
  approved rough-cut input, not a promise that placeholders are absent.
- OC spans create labeled presenter/A-roll placeholder events on configured V1.
  They are distinct from unresolved-visual/debug slates on V5.
- Overlay events coexist with presenter picture; the default fixtures author
  layer 4, but the compiler never silently reroutes a different valid layer.

### Sources, events, cuts, and markers

- Use authored visual-event IDs for their picture events. Derive narration,
  presenter, source-audio, marker, transition, and every source UUID with a
  fixed UUIDv5 namespace and stable semantic names. This prevents valid
  cross-kind authoring IDs from colliding in the manifest event namespace.
- A ready video visual uses its verified source start for the compiled record
  duration and blocks if insufficient source duration is available. A resolved
  dependency's still/video kind must equal the authored `mediaKind`. No retime.
- `audioPolicy: use_source` requires a verified companion audio source and emits
  a matching A3 occurrence only when the selected source range fits both video
  and companion-audio durations; `mute` emits none.
- Block overlapping events on the same effective track. Emit one
  `HardCutTransition` for every abutting picture pair on the same track,
  regardless of null authored overrides, because hard cut is the Slice 1.3
  default and the downstream package verifier requires every such boundary.
  Authored non-hard-cut transitions are structurally unavailable in Phase 1.
  A track switch is already a hard cut in the edit but is not misrepresented as
  a same-track transition object; report that fact deterministically.
- Emit a section marker at the current narration-spine cursor with a UUIDv5 ID,
  `name = section.title`, `note = "Section: " + section.title`, color `Blue`,
  and script-marker provenance whose block/authoring IDs are the section ID.
- Emit a `direction` block with `buildBehavior: timeline_marker` at the current
  cursor with a UUIDv5 ID, name `Direction`, note equal to the exact direction
  text, color `Yellow`, and provenance whose block/authoring IDs are the
  direction ID. Other directions and note/draft blocks emit no marker.

### Serialization, IDs, hashes, and report trace

- Canonical JSON is UTF-8, recursive sorted keys, two-space indentation, and one
  trailing newline. Hash exactly those manifest bytes with
  `sha256:<lowercase hex>`.
- Stable inputs produce stable IDs, source/event/transition/marker ordering,
  manifest bytes, report bytes, and hashes. Wall-clock time, request IDs,
  absolute cache paths, and cache dispositions do not participate.
- The report contains one narration event result per active block. Its message
  uses the exact template `Narration "<text>" frames <start>-<endExclusive>;
  precision=<precision>; alignment=<alignmentVersion>.` The matching manifest
  event provenance carries document/block identity.
- Emit one deterministic `ManualCompletionItem` for every presenter placeholder
  (replace with presenter/A-roll), unresolved/failed visual slate (resolve or
  replace the visual), and failed-narration timing slate (regenerate/provide
  aligned narration). IDs are UUIDv5-derived; codes/actions are stable. Each
  such item has a matching warning issue except failed narration, whose issue is
  blocking.
- Summary counts are derived from the final arrays: source/event/marker counts
  from the manifest; `placedCount` and `placeholderCount` from event-result
  dispositions; manual count from manual items; warning/error counts from issue
  severities. Suppressed failed-narration authored events receive issues rather
  than impossible range-bearing `EventBuildResult` records.
- Report status is `ready` only with no warnings/errors, `ready_with_warnings`
  for nonblocking warnings, and `blocked` for any blocking compiler diagnostic.

## Contracts, fixtures, goldens, and dependencies

- Contract changes are limited to the separately approved note.
- The accepted ScriptDocuments in `tests/data/slice_1_1/` are read-only inputs.
- New deterministic dependency inputs and new manifest/report goldens live under
  `tests/data/slice_1_3/`. They become frozen only upon producer acceptance of
  Slice 1.3.
- Existing `/fixtures`, accepted Slice 0.2 data/tests, and existing goldens stay
  byte-identical.
- No dependency or lockfile change. Implementation uses Node/TypeScript standard
  library crypto and the repository's existing Ajv/Vitest toolchain.
- CI explicitly installs the already-required Slice 1.2 system FFmpeg tool on
  the clean Linux runner. This is test-environment provisioning, not a new
  product dependency, and changes neither lockfile.

## Test-first implementation order

1. Add failing schema/generation tests for `CompilerDependencies v1` and the
   three precision values; implement only the approved contract delta.
2. Add failing pure frame/anchor tests covering rational rates, affinities,
   derived ends, sentence-only limits, and malformed timing.
3. Add failing narration-spine and track-routing tests, then sources/events,
   source audio, placeholders, cuts, markers, and report trace.
4. Add negative dependency/identity/revision/hash/duration/order tests.
5. Add minimal and torture end-to-end tests and freeze canonical manifest/report
   goldens only after semantic tests pass.
6. Prove two consecutive compiles are byte-identical and do not mutate inputs.

## Automated verification

- Focused TypeScript lint, typecheck, schema, compiler, and golden tests.
- Focused Python adapter tests plus Ruff and strict mypy.
- Schema validation of every emitted manifest and report.
- Repeated tests at 24000/1001 plus alternate integer and NTSC rational rates.
- Full `npm run validate` twice consecutively under the pinned toolchain.
- `git diff --check`, lockfile audit, generated-type currentness, and explicit
  frozen-boundary diffs.
- Two consecutive green CI runs for the exact golden tests and repository gate.
- Independent read-only review with no unresolved correctness or boundary
  finding.

## Producer acceptance

No Resolve, AWS, listening, import, or visual inspection is required.

1. Read the generated torture `build-report.json`.
2. Choose the quoted narration sentence/block identified in the acceptance
   note and confirm its reported absolute frame range.
3. Find the matching narration event in `timeline-manifest.json` and confirm
   the same range plus document/block provenance.
4. Confirm the report labels derived timing honestly and identifies the V5
   unresolved placeholder.
5. Explicitly accept Slice 1.3. Producer acceptance freezes the new Slice 1.3
   dependency inputs and goldens.

## Proposed follow-up work

- Cross-track cut semantics beyond implied hard cuts, transition policy, and
  handles remain Slice 5 work.
- Package readiness behavior for a blocked compiler report belongs to Slice
  1.4 wiring and verification.
- Durable compiler dependency exchange over build jobs belongs to Slice 1.6.
