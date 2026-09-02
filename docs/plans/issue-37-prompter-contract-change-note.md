# Issue 37 contract-change note — deterministic prompter export and typed annotations

## Approval and bounded change

The Producer authorized this note on 2026-09-02 as the implementation boundary
for issue #37. It introduces only optional `ScriptDocument v1` fields needed to
freeze prompter-policy annotations and performance beats. It does not add UI
markup, provider syntax, a provider call, shoot ingest, or a new document
schema version.

On 2026-09-02 the Producer clarified the mixed-state beat rule: a sentence is
one recording beat even when an OC/VO transition occurs inside it. Such a beat
is `on_camera` when any covered token is on camera; it is `voiceover` only when
every covered token is voiceover. The visible prompter still emits the exact
mid-sentence state transition so editorial B-roll coverage remains explicit.

## Proposed `ScriptDocument v1` additions

Add these optional arrays to an active `NarrationBlock`. Omission means an
empty array, so every accepted v1 document remains valid and canonically
unchanged.

```ts
type NarrationAnnotation = {
  id: UUID;
  kind: "pronunciation_alias" | "pronunciation_phoneme" | "performance_note";
  range: TextAnchorRange;
  value: string;
  includeInPrompter: boolean;
  version: PositiveInteger;
};

type PerformanceBeat = {
  id: UUID;
  range: TextAnchorRange;
  version: PositiveInteger;
};

interface NarrationBlock {
  // Existing fields unchanged.
  annotations?: NarrationAnnotation[];
  performanceBeats?: PerformanceBeat[];
}
```

`range` remains the existing token-anchored `TextAnchorRange`; annotation or
beat text is therefore verified against the narration tokens and may not carry
free-floating or provider-specific instructions. `value` is human-readable
metadata only. A `pronunciation_phoneme` value is a named phoneme value, not
SSML or an engine dialect. `performance_note` is likewise a visible non-spoken
cue, never inserted into narration text or synthesized audio input.

`performanceBeats` must be ordered, non-overlapping, wholly inside its owning
active narration block, and together cover every spoken token exactly once at
export time. A producer may merge or split them before export; their UUIDs are
the stable frozen beat identities. When an older valid v1 document has no
`performanceBeats`, the exporter derives one beat per sentence for that export
only, using deterministic UUIDv5 input of document ID, live-head sequence,
block ID, and token-boundary IDs. The derived IDs are recorded in the sidecar
but do not rewrite the source document.

Annotations must be wholly inside an active narration block, must not overlap a
host-visibility gap, and must have distinct IDs. Multiple annotations may share
a range. An annotation whose `includeInPrompter` is false remains in the
machine-readable sidecar but has no visible cue in the text export.

## New derived export artifact

Issue #37 adds a separate canonical `prompter-export/v1` sidecar rather than
placing export results back into `ScriptDocument`. Its required identity fields
are:

```ts
type PrompterExportV1 = {
  schemaVersion: "prompter-export/v1";
  sourceDocument: DocumentReference;
  settings: {
    includeSectionNavigation: boolean;
    includeBeatNumbers: boolean;
  };
  textSha256: `sha256:${string}`;
  beats: Array<{
    id: UUID;
    expectedText: string;
    hostVisibility: "on_camera" | "voiceover";
    navigationCues: string[];
    annotations: Array<{
      id: UUID;
      kind: NarrationAnnotation["kind"];
      value: string;
      visibleInPrompter: boolean;
    }>;
  }>;
};
```

The visible `.txt` contains only active narration in document order, an
initial `(OC)` or `(VO)` marker, later markers only at state changes, and
opted-in annotations rendered on their own unmistakably non-spoken cue lines.
It contains optional section-navigation labels only when requested. Direction,
citation, visual, note/draft, asset transcript, graphic, and excluded narration
content never enter it. The `textSha256` hashes UTF-8 bytes of the exact text
artifact; the sidecar is canonically serialized and its own content hash is
reported by the CLI.

## Compatibility, generated types, and migration

- This is an additive v1 schema change. Existing v1 fixtures and accepted
  documents remain valid without new fields and must retain their exact bytes.
- Regenerate TypeScript and Python contract types from the amended JSON schema.
- No stored-data migration is required: absent arrays are interpreted as empty.
  No document is rewritten merely to derive legacy sentence beats.
- Slice-owned fictional fixtures and goldens cover explicit beats,
  deterministic legacy derivation, annotations, state transitions, validation
  failures, text bytes, and sidecar bytes. Previously accepted fixtures and
  goldens remain unchanged.
- No API, database, provider, credentials, or deployment migration is part of
  this note.

## Validation and failure behavior

Export blocks with stable diagnostics for an active narration range not covered
by exactly one host-visibility state, invalid/overlapping annotation anchors,
invalid/overlapping/uncovered performance beats, or quoted-text/token mismatch.
It never repairs, expands, or silently retargets an anchor. Identical source
revision and settings must reproduce byte-identical text and sidecar output.

## Acceptance effect

The Project Acceptance authority for #37 is `Automated`: the Producer has
approved this contract boundary, and completion now requires retained command
evidence, generated-type currentness, frozen-boundary checks, and the
deterministic fixture/golden suite. The issue remains scoped to the pure
library/CLI and has no manual UI, Resolve, provider, or real-script acceptance
step.
