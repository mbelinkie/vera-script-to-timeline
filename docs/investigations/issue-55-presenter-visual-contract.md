# Issue #55 contract-change note — presenter stills, undefined visuals, and visual-only duration

## 1. Status and bounded authorization

This note is **proposed for Producer acceptance**. It defines the smallest
production-contract change that carries the accepted issue #14 S01–S03 intent
into canonical authoring and compiler boundaries. It does not itself amend a
schema or authorize implementation until the Producer accepts it.

Scope:

- a Project presenter-still default and optional Script override;
- deterministic temporary-voice picture for authored On Camera ranges;
- three-second Project defaults and per-event overrides for visual-only
  still-like events;
- distinct `Visual Undefined`, unresolved request, and intentional Placeholder
  behavior;
- authoring defaults between visual selection and host visibility while keeping
  those canonical lanes independent; and
- the exact future schema, generated-type, validator, compiler, manifest,
  report, compatibility, migration, and acceptance effects.

Exclusions:

- no schema, fixture, golden, generated-type, compiler, UI, media, Resolve, or
  migration edit in issue #55;
- no change to the accepted #14 artifact or S01–S03 interaction design;
- no ordered-inpoint, hierarchy, return-to-parent, source-trim, or inferred
  coverage design owned by #56; and
- no recorded-presenter take ingest, approval, alignment, assignment, or Phase
  7 conform redesign.

Touched contracts and fixtures in this design issue: none. A later, separately
claimed implementation issue may make only the changes authorized in sections
3–7 after this note is accepted.

Dependencies: None. No package or service dependency is proposed.

Automated checks for this design issue: `git diff --check`, the full
`npm run validate` repository gate, and a final roadmap inspection proving the
issue remains Producer-owned and is moved only to `In review`.

Required evidence read for this note:

- `docs/Script-to-Timeline Product Spec - Fable Rev2.md`, especially §§4,
  6.2–6.4, 6.14–6.15, 7, 8.3–8.4, 9.1, 13, and 16;
- accepted #14 S01–S03 evidence in commit
  `11cef62fad9800bdca2934343515dd9a0c3d5172`, including
  `docs/prototypes/issue-14/producer-acceptance.md`, the accepted plan,
  design-presence checklist, and traceability ledger;
- current `ScriptDocument v1`, `CompilerDependencies v1`,
  `TimelineManifest v1`, and `BuildReport v1`; and
- the current validator/compiler behavior that requires authored host state,
  treats a placeholder source as unresolved, advances the timeline only with
  narration, and emits an unresolved presenter slate for every On Camera span.

## 2. Normative decisions

### D55-01 — Project default and Script override are separate persisted scopes

Add a narrow `authoring-project-settings/v1` contract. It is a versioned input,
not an editor preference or a field copied into every Script.

```ts
type AuthoringProjectSettingsV1 = {
  schemaVersion: "authoring-project-settings/v1";
  id: UUID;
  projectId: UUID;
  version: PositiveInteger;
  settingsHash: `sha256:${string}`;
  presenterStill?: PresenterStillReference;
  visualOnlyStillDurationMs?: PositiveInteger;
};

type PresenterStillReference = {
  mediaReferenceId: UUID;
  artifactId: UUID;
  artifactVersion: PositiveInteger;
  contentHash: `sha256:${string}`;
  projectRelativeLocator: ProjectRelativePath;
  width: PositiveInteger;
  height: PositiveInteger;
  provenance:
    | {
        origin: "local_import";
        originalFilename: string;
      }
    | {
        origin: "captured_frame";
        sourceMediaReferenceId: UUID;
        sourceFrame: NonNegativeInteger;
      };
};
```

`settingsHash` hashes the canonical settings payload (the two optional setting
values), excluding the envelope identity, version, and hash field itself.
`artifactId` plus `artifactVersion` identifies the immutable still revision;
`contentHash` verifies its bytes; the project-relative locator is only a
locator. Replacing or editing the bytes creates a new artifact identity or
version and a new settings version. Filename, path, timestamp, and display name
never identify the still. The two provenance variants are intentionally narrow;
new origins require a later accepted contract change rather than an untyped
string.

Add one optional object to `ScriptDocument v1`:

```ts
type ScriptSettings = {
  presenterStillOverride?: PresenterStillReference;
};

interface ScriptDocumentV1 {
  // Existing fields remain unchanged.
  scriptSettings?: ScriptSettings;
}
```

Resolution order is exact:

1. `ScriptDocument.scriptSettings.presenterStillOverride`, when present;
2. `AuthoringProjectSettings.presenterStill`, when present; otherwise
3. the pinned generic-torso fallback in the application package.

Omission means inherit. `null` is not accepted and a Script cannot silently
disable a valid Project default. When neither persisted scope has a still, the
generic fallback is a successful deterministic resolution, not a guessed user
asset or a missing-media placeholder.

The authoring UI's display-only **Show presenter thumbnail** preference remains
outside canonical build contracts. Turning that preference off never changes
which picture the compiler emits.

### D55-02 — The generic torso is a pinned immutable build input

The fallback is one checked-in 16:9 still with a stable artifact ID, version,
content hash, dimensions, and package-relative source. Build preparation
verifies and materializes it like any other required still. A missing or
hash-mismatched fallback fails preparation; the compiler never substitutes a
different icon, initials, or blank frame.

The build-time settings snapshot records exactly one effective choice:

```ts
type AuthoringDefaultsSnapshot = {
  projectSettings: {
    id: UUID;
    version: PositiveInteger;
    settingsHash: `sha256:${string}`;
  };
  visualOnlyStillDurationMs: PositiveInteger;
  presenterStill: {
    resolvedFrom:
      | "script_override"
      | "project_default"
      | "generic_torso_fallback";
    reference?: PresenterStillReference;
    source: StillSource;
    fallbackAssetVersion?: PositiveInteger;
  };
};
```

For `script_override` or `project_default`, `reference` is required and must
match `source` by artifact identity, hash, locator, and dimensions. For
`generic_torso_fallback`, `reference` is forbidden and
`fallbackAssetVersion` is required. If the Script contains an override, a
snapshot claiming either lower-precedence choice is invalid.

### D55-03 — Temporary voice produces a real presenter StillEvent

For every authored `HostVisibilitySpan` whose state is `on_camera` in a
temporary-voice build, the compiler emits:

- one `StillEvent` on the configured presenter video track;
- the existing stable event identity `presenter-event:<spanId>`;
- a record range resolved from that span's exact text anchor;
- the single effective presenter `StillSource`, reused by every applicable
  span rather than duplicated per span;
- full-frame composition with `contain`, centered horizontally and vertically
  on an opaque black `#000000` canvas, preserving aspect ratio, with no crop,
  stretch, motion, transition, or source audio; and
- event provenance back to the document, narration block, and host span.

“Full-screen” therefore means that the presenter event owns the full raster;
the still itself is never silently cropped or stretched. The exact composition
is frozen in the manifest rather than left to a Resolve import default.

The build report emits one `TEMPORARY_PRESENTER_STILL` warning and one
`REPLACE_TEMPORARY_PRESENTER` manual-completion item per generated presenter
event. A configured still and the generic torso have the same temporary status:
neither pretends to be recorded presenter footage.

Later approved presenter picture does not mutate the temp build, its source, or
its timeline. The existing recorded-performance conform creates a new build and
timeline from frozen take/assignment evidence; its recorded event replaces the
temporary presenter event only in that new output. This note does not choose or
change Phase 6/7 take identity, alignment, or conform rules.

### D55-04 — Visual-only placement is an additive event variant

Refactor the JSON Schema definition into a shared visual-event base plus two
variants while keeping every current serialized anchored event valid:

```ts
type VisualEvent = NarrationAnchoredVisualEvent | VisualOnlyEvent;

type NarrationAnchoredVisualEvent = VisualEventBase & {
  range: TextAnchorRange;
  visualOnlyTiming?: never;
};

type VisualOnlyEvent = VisualEventBase & {
  range?: never;
  visualOnlyTiming: {
    kind: "visual_only";
    visualKind: "image" | "capture" | "graphic" | "placeholder" | "clip";
    durationOverrideMs?: PositiveInteger;
  };
};
```

A `VisualOnlyEvent` is legal only as `VisualBlock.event`. It is forbidden in a
`NarrationBlock.visualEvents` array because it has no narration target. Its
owning block's existing `orderKey` determines program order. Existing anchored
events keep `range` and cannot also carry `visualOnlyTiming`; no existing event
is reinterpreted.

This variant does not introduce the later full Image, Capture, Graphic, or Clip
authoring payloads. `visualKind` supplies only the timing class needed here;
the source remains an existing verified local-media or placeholder reference
until the source-owning contract is introduced. The bounded mapping is exact:

- `image` and `capture` require ready local still media;
- `graphic` requires ready local still media in this contract (animated
  graphics remain with their source-owning contract);
- `clip` requires ready local video media; and
- `placeholder` requires the intentional placeholder pair in D55-06.

That avoids pulling #24, #27, graphics, Research, or #56 payload design into
this slice.

### D55-05 — Still-like events derive duration; clips never do

`AuthoringProjectSettings.visualOnlyStillDurationMs` defaults to `3000` when
omitted. New Project-settings records materialize `3000`; legacy reads may
derive it without rewriting stored data. A visual-only `image`, `capture`,
`graphic`, or intentional `placeholder` resolves duration in this order:

1. `VisualOnlyEvent.visualOnlyTiming.durationOverrideMs`, when present;
2. the build's frozen Project `visualOnlyStillDurationMs`; otherwise
3. the compatibility default `3000`.

Milliseconds are authoring intent independent of frame rate. The compiler
converts the effective duration to integer timeline frames with:

```text
ceil(durationMs * frameRate.numerator /
     (1000 * frameRate.denominator))
```

At 24000/1001, the three-second default is therefore 72 frames. The manifest
freezes both the resulting `recordRange.durationFrames` and its duration basis.

A visual-only `clip` forbids `durationOverrideMs`. It requires a verified
`selectedSourceRange { startFrame, durationFrames }` in
`ResolvedVisualDependency`; the record duration equals that selected source
duration exactly. Existing frame-rate compatibility checks remain. A mismatch
blocks as unsupported retiming. The compiler never fills a requested duration
by changing speed, freezing, looping, extending, or trimming a clip, and never
invents duration from neighboring narration.

In canonical block order, active narration advances the cursor by narration
duration, and a visual-only block advances it by its effective hold or selected
source duration. Sections, directions, notes, excluded blocks, and ordinary
narration-anchored visual blocks do not acquire duration from row position.

### D55-06 — Undefined, unresolved, and intentional are three different states

| State | Canonical authoring representation | Preview | Release |
| --- | --- | --- | --- |
| `Visual Undefined` | No `VisualEvent` covers an authored VO interval. It is absence, not a placeholder source. | Normal preview blocks. An explicit forced preview emits a full-frame `VISUAL UNDEFINED` slate for each exact uncovered interval and retains a blocking report issue. | Blocks. It can never be accepted as an intentional output. |
| Unresolved visual request | Existing `PlaceholderVisualSource` with `unresolvedVisual: true`, author description, and event status `unresolved`. | Emits an `UNRESOLVED VISUAL: <description>` remediation slate under the existing unresolved-asset policy. | Blocks under the current product-spec default; any future per-Project release policy is separate. |
| Intentional Placeholder | `PlaceholderVisualSource` with `unresolvedVisual: false`, nonempty author description, and event status `ready`. | Buildable full-frame slate whose visible text is the exact author description. | Buildable with the same exact text; no unresolved or manual-completion issue. |

Widen `PlaceholderVisualSource.unresolvedVisual` from the constant `true` to a
required boolean and add semantic pair checks:

- `true` requires event status `unresolved`;
- `false` requires event status `ready`, full-frame presentation, native
  framing, no motion, muted audio, and nonempty author text; and
- neither form may be inferred from capitalization, label text, row position,
  or a build-report message.

An intentional Placeholder may be narration-anchored or visual-only. In both
cases its output is a `PlaceholderEvent` with `EventBuildResult.disposition`
`placed`, because it is the selected build result, not missing work.

Forced preview is explicit in `CompilerDependencies.build`:

```ts
type UndefinedVisualPolicy = "block" | "render_forced_preview";
```

Omission means `block`. `render_forced_preview` is valid only with
`buildClass: "preview"`. The validator retains the existing
`VOICEOVER_VISUAL_GAP` diagnostic for compatibility. The compiler may continue
past that diagnostic only when forced preview is selected and every otherwise
blocking document diagnostic is a VO visual gap. Every derived gap produces a
manifest `PlaceholderSource` with label exactly `VISUAL UNDEFINED`, an exact
range-derived `PlaceholderEvent`, and a blocking `VISUAL_UNDEFINED` build
issue. Event and source UUIDs derive from the document ID, block ID, and exact
first/last uncovered token IDs through the existing stable UUIDv5 facility, so
the same frozen input produces the same slate identities. Any other validation
failure still prevents manifest creation. Release never accepts the
forced-preview policy.

### D55-07 — Visual selection proposes host state; it never derives canonical state

No `HostVisibilitySpan` schema or compiler inference is added. The authoring UI
applies these defaults when the writer makes a visual selection over spoken
words:

| Selection | Proposed explicit host state |
| --- | --- |
| On Camera | `on_camera` for the selected range |
| Full-frame non-host visual | `voiceover` for the selected range |
| Explicit overlay over an existing range | Preserve the range's current host state, including `on_camera` |
| Explicit overlay over an unassigned range | Propose `on_camera`, then require ordinary coverage validation |
| Visual-only event | No host span; there is no narration range |

The selection transaction persists the visual event and host span as separate
canonical entities. Either may be edited later without rewriting the other.
The validator continues to require exactly one explicit host state for every
spoken token, and an overlay still cannot satisfy full-frame VO coverage. The
compiler reads the independent lanes and never recomputes host visibility from
visual kind, layer, or presentation mode.

## 3. Exact contract-file changes authorized after acceptance

### 3.1 New contract

Add `contracts/authoring-project-settings-v1.schema.json` with the exact fields,
closed objects, conditionals, and defaults in D55-01. Register it in the schema
inventory and aggregate contract generator. Define its project-relative-path
constraint locally rather than referencing `TimelineManifest`, so the new
Project contract does not create a circular Script ↔ Manifest schema graph.

### 3.2 `contracts/script-document-v1.schema.json`

- Add optional `scriptSettings` and the cross-schema
  `PresenterStillReference` reuse described in D55-01.
- Split the current `VisualEvent` definition into the byte-compatible anchored
  variant and new `VisualOnlyEvent` variant in D55-04.
- Widen required `unresolvedVisual` to boolean and enforce the source/status/
  presentation pairs in D55-06.
- Keep all IDs, anchors, host states, layers, transitions, and existing source
  payloads unchanged.

### 3.3 `contracts/compiler-dependencies-v1.schema.json`

- Add optional `authoringDefaults: AuthoringDefaultsSnapshot` at the top level.
- Add optional `build.undefinedVisualPolicy`, defaulting semantically to
  `block` when omitted.
- Add optional `selectedSourceRange` to `ResolvedVisualDependency`, required
  exactly for a visual-only clip and forbidden for still sources.
- Retain all existing narration, role, track, source-start, and source-audio
  fields.

`authoringDefaults` is optional only to preserve replay of accepted legacy
compiler fixtures. Every newly prepared production build must supply it. Build
preparation, not the pure compiler, resolves locators or reads Project storage.

### 3.4 `contracts/timeline-manifest-v1.schema.json`

Add these optional, backward-compatible fields; the new compiler emits them
whenever applicable:

```ts
type PlaceholderPurpose =
  | "timing_unavailable"
  | "unresolved_visual"
  | "undefined_visual"
  | "intentional_placeholder"
  | "legacy_presenter_unresolved";

type DurationBasis =
  | { kind: "narration_anchor" }
  | {
      kind: "project_default";
      durationMs: PositiveInteger;
      projectSettingsId: UUID;
      projectSettingsVersion: PositiveInteger;
      projectSettingsHash: `sha256:${string}`;
    }
  | { kind: "event_override"; durationMs: PositiveInteger }
  | { kind: "selected_source_range" };

type FrameComposition = {
  presentationMode: "full_frame";
  framingPolicy: "contain";
  horizontalAlignment: "center";
  verticalAlignment: "center";
  backgroundColor: "#000000";
  motionPreset: "none";
};

type PresenterStillProvenance =
  | {
      resolvedFrom: "script_override" | "project_default";
      projectSettingsId: UUID;
      projectSettingsVersion: PositiveInteger;
      projectSettingsHash: `sha256:${string}`;
      mediaReferenceId: UUID;
      artifactId: UUID;
      artifactVersion: PositiveInteger;
    }
  | {
      resolvedFrom: "generic_torso_fallback";
      projectSettingsId: UUID;
      projectSettingsVersion: PositiveInteger;
      projectSettingsHash: `sha256:${string}`;
      fallbackAssetVersion: PositiveInteger;
    };
```

- `PlaceholderSource.purpose?: PlaceholderPurpose` distinguishes slate intent;
  omission means an accepted legacy placeholder with behavior recoverable from
  its immutable prior build/report.
- Each new visual `TimelineEvent` carries `durationBasis`.
- A generated presenter `StillEvent` carries `frameComposition`; its reused
  `StillSource` carries `presenterStill?: PresenterStillProvenance`. Other still
  sources omit that property.
- Visual-only events use `timingPrecision: "frame"` and the literal
  `alignmentVersion: "visual-only/v1"`; this is an explicit not-applicable
  marker, never a claim of speech alignment.
- Existing source/event kinds, frame ranges, track binding, and authoring event
  provenance remain unchanged.

### 3.5 `contracts/build-report-v1.schema.json`

No structural change is required. Existing open diagnostic/manual-completion
codes and `EventBuildResult` shapes carry the new behavior. Required exact
codes are:

- `TEMPORARY_PRESENTER_STILL` warning plus
  `REPLACE_TEMPORARY_PRESENTER` manual completion;
- `VISUAL_UNDEFINED` blocking issue for every forced-preview derived slate;
- existing `VISUAL_UNRESOLVED` behavior for unresolved requests; and
- no issue or manual-completion item for an intentional Placeholder.

## 4. Exact validator and compiler changes authorized after acceptance

The semantic validator must:

1. validate Project/Script presenter references and reject hash, dimension,
   provenance, or precedence mismatches in the build snapshot;
2. branch anchored versus visual-only events without inventing anchors;
3. allow visual-only events only in active `VisualBlock`s;
4. enforce the visual-kind/source and duration rules in D55-05;
5. enforce the placeholder state pairs in D55-06;
6. keep host-visibility coverage and overlay rules unchanged; and
7. retain existing diagnostic codes unless this note explicitly adds one.

The pure compiler must:

1. schedule duration-bearing narration and visual-only blocks in canonical
   `orderKey` order;
2. resolve the Project duration default and event override exactly once into
   integer frames;
3. use a clip's verified selected source range 1:1;
4. emit and reuse the effective presenter still for temporary On Camera spans;
5. emit exact placeholder purposes/text and forced-preview blocking evidence;
6. freeze composition, duration basis, source identity, and authoring
   provenance in the manifest/report; and
7. preserve stable ordering, UUID derivation, canonical JSON, and byte-identical
   repeatability for identical inputs.

No build path may inspect editor markup, UI row geometry, filenames, neighboring
card proximity, or a Resolve timeline to fill any of these fields.

## 5. Compatibility and migration behavior

- Existing `ScriptDocument v1`, compiler-dependency, manifest, report, fixture,
  and golden bytes remain valid and are not rewritten.
- Existing anchored visual events are still identified by their required
  `range`; omission of `visualOnlyTiming` changes nothing.
- Existing `PlaceholderVisualSource { unresolvedVisual: true }` remains an
  unresolved request. No legacy placeholder becomes intentional by migration.
- Omitted Script settings inherit the Project setting. Omitted legacy Project
  still means generic fallback. Omitted Project visual-only duration means
  `3000` ms.
- Direct replay of a legacy `CompilerDependencies v1` without
  `authoringDefaults` retains the old presenter-placeholder behavior so accepted
  Slice 1.3 goldens stay byte-identical. A new build-preparation layer always
  supplies the snapshot, including for an old stored Project, so its next new
  build uses the generic torso and three-second default without rewriting the
  old Project or prior build.
- Every prior build snapshot, manifest, report, OTIO/FCPXML package, and Resolve
  timeline remains immutable. New defaults affect only a newly requested build.
- Manifest consumers that ignore unknown optional properties remain compatible.
  Exhaustive generated-type consumers must handle the new event variant,
  placeholder purposes, duration bases, and presenter-still provenance.
- No database backfill or eager JSON rewrite is required. If persistence later
  materializes derived Project defaults, that write is an attributed new
  settings version, not silent migration of history.

## 6. Generated types, fixtures, and accepted-boundary impact

After Producer acceptance, the implementation issue must regenerate:

- `packages/contracts/src/generated/contracts.ts`;
- `python/vera_timeline_agent/generated/contracts/*`; and
- schema inventory/export registries that enumerate contract files.

Add new issue-owned fixtures and byte-identical goldens under
`tests/data/issue_55/` for:

1. Script override > Project default > generic fallback precedence;
2. one presenter source reused across several On Camera spans;
3. exact contain/center/black/no-motion manifest composition;
4. default and overridden visual-only Image, Capture, Graphic, and intentional
   Placeholder durations at 24000/1001 and one alternate project rate;
5. a visual-only clip whose record/source ranges are identical;
6. rejection of a clip duration override and insufficient/mismatched source;
7. absent undefined state, forced-preview `VISUAL UNDEFINED`, and release block;
8. unresolved request versus intentional Placeholder preview/release results;
9. On Camera, full-frame non-host, overlay, and visual-only host-default
   transactions while lanes remain independently editable; and
10. two consecutive byte-identical manifest/report runs.

Do not edit accepted Slice 1.1 inputs or Slice 1.3 goldens. Legacy replay tests
must prove those bytes remain unchanged; the new behavior lives in issue-owned
fixtures that include `authoringDefaults`.

Expected implementation breakage is limited to generated types and exhaustive
callers of `VisualEvent`, `PlaceholderVisualSource`, compiler dependencies, and
new optional manifest metadata. There is no media mutation, provider call,
Resolve action, or existing artifact rewrite.

## 7. Acceptance changes for the later implementation issue

Acceptance must retain:

- structural positive/negative schema tests for every new union/conditional;
- semantic validator tests for scope, precedence, source/kind, duration, and
  placeholder-state invariants;
- byte-identical compiler goldens for every matrix item in section 6;
- unchanged-byte checks for accepted legacy inputs and goldens;
- exact generated-type currentness;
- the full repository validation gate; and
- a plain-language Producer walkthrough of the output matrix, without requiring
  live media import or Resolve.

This does not change #55's authority: #55 remains `In review` until the Producer
accepts this note. Acceptance authorizes a separate implementation issue to
become dependency-resolved; it does not mark that implementation complete.

## 8. Producer review checklist for issue #55

1. Open this exact file at commit named in the issue's In-review evidence and
   read D55-01 and D55-02. Confirm Script override wins, Project default is
   inherited when no override exists, and the generic torso appears only when
   neither exists. Expected: immutable artifact/version/hash/provenance and a
   frozen effective-source record; no filename or path is identity.
2. Read D55-03. Confirm every temporary-voice On Camera range receives the same
   effective still as a real presenter-track `StillEvent`, framed contain/
   center on black with no motion or crop. Expected: an explicit temporary
   warning/manual item, and later recorded conform creates a new output rather
   than changing the temp build.
3. Read D55-04 and D55-05. Confirm a visual-only event has no narration anchor,
   advances program time by its own duration, and can exist only in a visual
   block. Expected: Image, Capture, Graphic, and intentional Placeholder use
   3000 ms unless overridden; Clip uses its selected source range exactly and
   forbids a duration override or retime.
4. Read the state table in D55-06. Expected: untouched `Visual Undefined` is
   absence and blocks Release; only an explicit forced Preview renders the
   exact `VISUAL UNDEFINED` slate while retaining a blocking issue; unresolved
   requests remain unresolved; intentional Placeholder keeps exact author text
   and is buildable in Preview and Release.
5. Read D55-07. Expected: On Camera proposes OC, full-frame non-host proposes
   VO, an overlay may retain OC, and visual-only creates no host range. Confirm
   the persisted host and visual entities remain independently editable and the
   compiler performs no cross-lane inference.
6. Read sections 3–6. Expected: all future file/type/compiler changes are named,
   old bytes remain valid, accepted fixtures/goldens stay untouched, new tests
   are issue-owned, and no #14, #56, take/conform, UI, media, or Resolve scope
   has entered the design.
7. If every expected result is correct, reply exactly:
   **`Accept #55 contract-change note as written.`** If not, reply
   **`Reject #55: <first failing decision or expected result>.`**

Until that exact acceptance is retained, schemas, fixtures, goldens, generated
types, compiler behavior, UI behavior, and implementation issues remain
unchanged or blocked by #55.
