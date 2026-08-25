# Slice 1.1 — ScriptDocument validator planning brief

## Status and gate

This is a planning-only artifact prepared while Slice 0.4 awaits the
producer's real Resolve Studio run. Slice 1.1 has no technical dependency on
Resolve, but the specification requires the Phase 0 gate to pass before Phase
1 formally begins. Implementation therefore remains queued unless the
producer explicitly authorizes provisional parallel work.

This planning pass does **not** modify the accepted `ScriptDocument v1`
schema, generated contract types, `/fixtures`, accepted test data, or any
Phase 0 acceptance evidence.

## Audit conclusion

The current schema already represents all structures named by Slice 1.1:

- section, narration, direction, visual, and note/draft blocks;
- narration tokens and host-visibility spans;
- anchored visual events; and
- local still, local video, and unresolved-placeholder sources.

The generated TypeScript and Python types are current with that schema. The
missing product surface is semantic rather than structural: there is no pure
TypeScript semantic validator, CLI, semantic test suite, minimal script input,
or torture script input.

No schema change is presently justified. The preferred path is to retain
`script-document/v1` byte-for-byte and add the required semantic layer. If a
producer decision later requires a structural change, work stops for a
separate contract-change note and approval before implementation.

## Bounded implementation scope

1. Add a pure TypeScript library that structurally and semantically validates
   an unknown input without filesystem access, mutation, repair, or inferred
   defaults.
2. Add a thin file-oriented CLI that emits deterministic human-readable
   pass/fail output with block-row and entity references and exits nonzero on
   failure.
3. Enforce the Slice 1.1 rules:
   - anchors resolve to a real narration block and real tokens;
   - token offsets and values agree with narration text;
   - anchor ordering, duration, and quoted text are valid;
   - every applicable spoken token has exactly one host-visibility state;
   - duplicate or contradictory host coverage is an error;
   - every voiceover interval has qualifying visual coverage;
   - overlay-only coverage cannot satisfy a voiceover interval; and
   - zero-duration visual events are errors.
4. Add two hand-authored inputs under `tests/data/slice_1_1/`:
   - `minimal.script-document.json`; and
   - `torture.script-document.json`, including mid-sentence cuts, overlapping
     overlay plus on-camera coverage, and back-to-back voiceover visuals.
5. Add positive and negative library/CLI tests and include them in the root
   `npm run validate` ratchet.
6. Document one producer acceptance command and a deliberate fixture break
   that demonstrates the exact row-level complaint.

The two new script inputs are not part of the accepted `/fixtures` media
boundary. Producer acceptance of Slice 1.1 will freeze them as semantic inputs
for reuse by the Slice 1.3 compiler goldens.

## Proposed internal API

The validator result is an internal TypeScript API, not a new shared JSON
contract in this slice.

```ts
interface ValidationResult {
  valid: boolean;
  diagnostics: ValidationDiagnostic[];
}

interface ValidationDiagnostic {
  code: string;
  message: string;
  jsonPath: string;
  blockIndex?: number;
  orderKey?: string;
  blockId?: string;
  entityKind?: "token" | "visibility_span" | "visual_event" | "anchor";
  entityId?: string;
  tokenId?: string;
}
```

Diagnostics will have stable codes and deterministic ordering. Proposed codes
include `SCHEMA_INVALID`, `TOKEN_ID_DUPLICATE`, `TOKEN_OFFSET_INVALID`,
`TOKEN_TEXT_MISMATCH`, `ANCHOR_BLOCK_NOT_FOUND`, `ANCHOR_TOKEN_NOT_FOUND`,
`ANCHOR_RANGE_REVERSED`, `ANCHOR_RANGE_EMPTY`, `ANCHOR_QUOTE_MISMATCH`,
`HOST_VISIBILITY_GAP`, `HOST_VISIBILITY_OVERLAP`,
`VOICEOVER_VISUAL_GAP`, and `VISUAL_EVENT_ZERO_DURATION`.

## Recommended semantic decisions

These recommendations avoid a schema change and make validation deterministic.
They require producer approval before tests or script inputs freeze them.

1. **Token authority and offsets**
   - The supplied narration token list is authoritative for Slice 1.1.
   - Offsets are UTF-16 code-unit indices, matching TypeScript string slicing.
   - Tokens must be ordered, non-overlapping, uniquely identified within their
     narration block, and exactly match the indicated text slice.
   - Independent linguistic tokenization is deferred to the authoring/import
     boundary rather than invented by this validator.
2. **Anchor boundaries**
   - Resolve anchors to half-open token intervals `[start, end)`.
   - Start `before` includes the start token; start `after` excludes it.
   - End `before` excludes the end token; end `after` includes it.
   - Empty or reversed intervals are invalid where an authored span/event
     requires duration.
3. **Quoted text**
   - `quotedText` must exactly equal the narration character slice selected by
     the resolved anchor. Fuzzy repair belongs to a later authoring workflow.
4. **Visual-event ownership**
   - Both currently valid storage forms are real authored occurrences:
     `NarrationBlock.visualEvents[]` and the event inside a top-level
     `VisualBlock`.
   - Event IDs must be unique across the active draft, and each occurrence is
     counted once against the narration block named by its anchor.
   - A standalone visual event reports both its visual-block row and target
     narration row when a diagnostic needs that context.
5. **Excluded narration**
   - Always validate structural, ID, token, and anchor integrity.
   - Apply host-visibility and voiceover-visual coverage only to narration
     whose state is `active`.
6. **Qualifying voiceover coverage**
   - A local-media event qualifies only when `presentationMode` is
     `full_frame` and `status` is `ready`.
   - An explicit placeholder qualifies only when `presentationMode` is
     `full_frame`, `source.kind` is `placeholder`,
     `source.unresolvedVisual` is true, and `status` is `unresolved`.
   - Overlay events never satisfy voiceover full-frame coverage.
   - Full-frame events overlapping on-camera text are allowed as explicit
     authored exceptions; Slice 1.1 reports coverage contradictions, not
     editorial-style warnings not required by the specification.
7. **Uniqueness scope**
   - Block IDs are unique across `activeDraft`.
   - Token IDs are unique within their narration block.
   - Visibility-span IDs and visual-event IDs are each unique across
     `activeDraft`, preventing ambiguous diagnostics and double counting.

## Explicit exclusions

- Voice synthesis, timing marks, normalization, and cache work (Slice 1.2).
- Anchor-to-time/frame compilation and manifest goldens (Slice 1.3).
- Manifest/build-report generation, OTIO/FCPXML, Resolve, or package changes.
- Editor, collaboration, persistence, API, or durable-job work.
- Anchor repair, automatic token insertion, inferred visibility, gap filling,
  or automatic placeholder creation.
- Media probing, source-duration validation, or media-reference resolution.
- Any change to `TimelineManifest v1`, `BuildReport v1`, `/fixtures`, accepted
  Phase 0 data/tests, dependencies, or lockfiles.

## Proposed file boundary

Subject to implementation review, Slice 1.1 is expected to add one focused
TypeScript workspace and test data, for example:

```text
packages/script-validator/
  package.json
  tsconfig.json
  src/index.ts
  src/semantic-validator.ts
  src/cli.ts
  test/semantic-validator.test.ts
  test/cli.test.ts
tests/data/slice_1_1/
  minimal.script-document.json
  torture.script-document.json
```

Existing contract files and generated models remain unchanged unless a later
approved contract-change note identifies an exact unavoidable delta.

## Test matrix

Positive coverage must prove:

- both canonical script inputs pass;
- all Phase 1 block and source variants are traversed;
- every active spoken token has one visibility assignment;
- full-frame local media and an explicit unresolved placeholder can cover VO;
- overlay plus on-camera overlap is accepted; and
- back-to-back VO visuals cover adjacent intervals without a gap.

Negative coverage must prove diagnostics for:

- missing and duplicate visibility coverage;
- voiceover gaps and overlay-only voiceover coverage;
- empty and reversed anchors;
- missing target blocks/start tokens/end tokens;
- wrong nested target block;
- token offset/value mismatch and quoted-text mismatch;
- duplicate IDs in the approved scopes; and
- CLI input, parse, schema, semantic, and usage failures.

Tests will assert stable diagnostic codes, deterministic order, relevant JSON
paths, row references, and exit status without freezing incidental prose more
than producer acceptance requires.

## Verification and acceptance

Automated completion requires:

1. focused validator lint, typecheck, and tests pass;
2. root locked-install and `npm run validate` pass;
3. accepted contracts, generated contract outputs, `/fixtures`, Phase 0 test
   data, and lockfiles have no unintended diff; and
4. an independent review reports no unresolved correctness or boundary issue.

Producer acceptance requires:

1. run the documented CLI against both canonical script inputs and see a
   human-readable pass with row references;
2. copy one input to a temporary location and deliberately remove visual
   coverage from a voiceover interval;
3. run the CLI against the broken copy;
4. confirm a nonzero exit and a precise `VOICEOVER_VISUAL_GAP` complaint naming
   the affected narration row/token range; and
5. explicitly accept the semantic decisions, canonical inputs, and Slice 1.1.

## Contract-change trigger

If implementation discovers that the accepted schema cannot express an
approved semantic decision, stop before modifying it. The required note must
list every changed JSON pointer, rationale, compatibility/migration impact,
generated TypeScript and Python outputs, affected tests/data, schema-version
choice, and producer-acceptance impact. The producer must approve that note
before the contract or generated files change.

## Authorization needed to start implementation

Before implementation agents are dispatched, the producer must approve:

1. the seven recommended semantic decisions above; and
2. either normal sequencing after Slice 0.4 acceptance, or an explicit
   exception allowing Slice 1.1 implementation to proceed provisionally while
   the formal Phase 0 gate remains open.
