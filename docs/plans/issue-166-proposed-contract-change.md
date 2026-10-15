# CN-166-P1 — proposed graphic provenance boundary

**Unapproved proposal. No schemas/types/fixtures/tests change in #166.**
Acceptance of [the design](../design/issue-166-derived-graphic-provenance.md)
does not itself authorize these frozen-boundary changes. Explicit approval must
name this note and revision before a later implementation slice begins.

## What and why

Add a versioned, immutable relationship between a source-backed graphic's
resolved semantic values, project-scoped template pins and retained data
evidence/citation/derivation. Existing fields cannot express this relationship:
#7's semantic hash excludes source/template provenance; #20's internal use hash
has caller-defined material; main v2's graphic source contains only two IDs.
A citation's lane position does not bind it to a graphic revision.

Keep all accepted #7/#20 identifiers and hash meanings. Implement against their
accepted source revisions named in the design, with an explicit integration
baseline. Do not replace these implementations from current main.

## Proposed types and exact deltas

All object shapes below are closed (unknown properties refused). `Hash` is
`sha256:` plus exactly 64 lowercase hexadecimal characters; `EntityId` follows
the receiving schema's existing opaque ID rules. `projectId` remains the document's
UUID `EntityId`; a #20 internal project handle is not substituted for it.
`projectRevisionId` reuses #7's `CuratedFusionGraphicSource.projectRevisionId`
pattern (`revision_<hex>` is valid), not `EntityId`. `JsonObject` is finite JSON,
not executable expressions. Required versus conditional fields are exhaustive
in design §3; this note adds no hidden optional evidence.

```ts
type GraphicProvenanceBinding =
  | { kind: "manual" }
  | { kind: "derived"; snapshotHash: Hash };

type GraphicTemplatePin = {
  templateKey: "ev24-lower-third";
  projectRevisionId: string; // exact #7 pattern ^[A-Za-z0-9_-]+$, not UUID
  packageDigest: Hash;
  entryAssetHash: Hash;
};

type GraphicProvenanceSnapshot = {
  schemaVersion: "graphic-provenance/v1";
  projectId: EntityId;
  template: GraphicTemplatePin;
  semanticSnapshot: ResolvedEv24SemanticSnapshot; // exact accepted #7 shape
  semanticSnapshotHash: Hash; // existing #7 calculation, unchanged
  sources: Array<{
    sourceKey: string; // nonempty, unique; sorted before freeze
    citation: {
      title: string; // nonempty
      publisher: string; // nonempty, explicit "unknown" permitted
      originalLocator: string | null;
      versionLabel: string | null;
    };
    snapshot: { artifactId: EntityId; contentHash: Hash; mediaType: string };
  }>; // at least one
  derivation: {
    mode: "manual" | "deterministic";
    version: string; // nonempty, version of explanation/recipe
    note: string; // nonempty; source/output selection, units and operations
    method: null | {
      id: EntityId; version: string; artifactId: EntityId; contentHash: Hash;
    };
    parameters: JsonObject;
  };
};
```

Manual derivation requires `method:null, parameters:{}`. Deterministic mode
requires the non-null method, version, retained bytes and canonical parameters.
The method is trusted registered behavior, never user code to execute.
The snapshot is addressed by `H(snapshot)`; it contains no self-hash. Audit
receipts and mutable artifact locators are separate stored records. This first
proposal supports the accepted EV24 semantic shape only. Other templates may
continue their existing media-only/pre-provenance-format path without a derived
evidence claim; new-format non-EV24 content blocks until its own contract is
approved. Never downgrade a declared derived revision to that legacy path. A later chart/map
template needs its own approved semantic/template contract, not arbitrary JSON
values slipped through this type. That does not change the general provenance
relationship or grant #99 arbitrary-template authority.

| Frozen boundary proposed for later change | Precise delta / consumer |
| --- | --- |
| `contracts/script-document-v1.schema.json` at accepted #7 | Optional `CuratedFusionGraphicSource.provenance: GraphicProvenanceBinding`. Required for newly authored graphic content; omission accepts legacy documents. Existing required fields and semantic inputs unchanged. |
| `contracts/compiler-dependencies-v1.schema.json` at accepted #7 | Optional top-level `graphicProvenanceSnapshots: GraphicProvenanceSnapshot[]`, default empty; duplicate computed hashes and unused snapshots refused (`GRAPHIC_PROVENANCE_UNEXPECTED`). Manual bindings forbid a snapshot pointer. Resolve derived source pointer by computed hash, project and exact semantic/template tuple. Existing `resolvedGraphics` continues to resolve the template and badge; do not repurpose that template-level array for per-content data evidence. |
| `contracts/timeline-manifest-v1.schema.json` at accepted #7 | Optional `FusionGraphicEvent.graphicProvenance: GraphicProvenanceBinding`. Copy the validated authored binding exactly; no field for legacy absent binding. Derived pointer addresses the verified snapshot included in the build package. No change to `semanticSnapshotHash`, source ID or event ID. |
| `contracts/build-report-v1.schema.json` at accepted #7 | Optional graphic event-result `graphicProvenance: GraphicProvenanceBinding`. Add stable blocking diagnostics `GRAPHIC_PROVENANCE_INCOMPLETE`, `GRAPHIC_PROVENANCE_MISMATCH`, `GRAPHIC_PROVENANCE_UNAVAILABLE`, `GRAPHIC_PROVENANCE_UNAUTHORIZED`, `GRAPHIC_PROVENANCE_UNEXPECTED`; these are compiler/consumer vocabulary accepted by the existing diagnostic-code pattern, not a new enum/schema restriction. Existing planned live/placeholder/baked result semantics stay unchanged. Currentness observations belong to audit receipts, not readiness inferred from time. |
| Main v2 `contracts/script-document-v2.schema.json` | **No field change.** Keep `GraphicRevisionSource {kind,graphicId,revisionId}`. Its immutable referenced graphic-content revision stores the tuple/snapshot/binding below. No citation text or IDs are injected into the reference. |
| `contracts/compiler-dependencies-v2.schema.json` | Optional top-level `graphicProvenanceSnapshots` as above and `resolvedGraphicContents: ResolvedGraphicContent[]`, default empty; unused snapshots/content records refused (`GRAPHIC_PROVENANCE_UNEXPECTED`). Each content is `{graphicId,revisionId,projectId,template,semanticSnapshot,semanticSnapshotHash,provenance}`; unique by `(graphicId,revisionId)`, exact project and source-reference equality required. These are trusted frozen resolver results, not a new renderer. |
| v2 `OccurrenceMediaResolutionV2` in that dependency schema | Add `graphicContentClass: "legacy_unclassified" | "manual" | "derived"`, required for every resolution of a `GraphicRevisionSource`, forbidden otherwise; no omission default. For `manual`/`derived`, require matching `resolvedGraphicContents`; its binding kind must equal this class. For `legacy_unclassified`, require no resolved content and no binding. Missing class/content is `GRAPHIC_PROVENANCE_INCOMPLETE`. Optional `graphicContentBinding:{graphicId,revisionId,provenanceHash}` for derived graphic media; it binds this resolution's existing `sourceSnapshot.contentHash` to the derived content. It must equal the source reference, corresponding resolved content, `P` and project; it is required when `graphicContentClass` is `derived`, forbidden otherwise. The materializer verifies/retains this relationship from generation; the compiler cannot prove rendered labels from a file hash. No repurposing of `probeHash`/`contentHash` as semantic/data hashes. |
| `contracts/timeline-manifest-v2.schema.json` | Optional `EventProvenanceV2.graphicProvenanceHash: Hash` on events resolved from declared derived graphic content, required in that case, absent otherwise. Preserve every existing source/media hash and use/payload/overlay identity. Package includes the addressed verified snapshot. No claim of live Fusion events in v2. |
| `contracts/build-report-v2.schema.json` | Extend the existing `DiagnosticCodeV2` enum with the five provenance codes above (v2 differs from v1's open code pattern). Add compiler/consumer handling; diagnostic owner identifies the source use/payload. Existing manifest hash binds propagated `P`. Do not add an unrelated status claiming upstream data is current. |

`ResolvedGraphicContent` has exactly the fields named in its row; `template`
and `semanticSnapshot` use the types above. The trusted resolver, owned by #64
and the provenance-core follow-up, reads the
immutable stored revision's format/classification. It may emit
`legacy_unclassified` only for a positively identified pre-provenance-format
revision; unknown/missing storage records block resolution. It emits `manual`
or `derived` for a new-format revision, and must supply its matching content
record. The compiler independently enforces the wire class/content/pointer
rules above; dropping a content record cannot turn that dependency into legacy.
The class is not inferred from a timestamp, URL, name or presence of an array.
A deliberately false trusted resolver classification is an upstream integrity
failure, not something hashes or this compiler can discover; test that boundary.

For v1, optional-field omission is necessary for legacy input compatibility.
The schema alone cannot distinguish legacy from a new writer that omitted the
binding. #64/#9 must enforce explicit classification for newly published content
and refuse stripping on round-trip. This residual writer/persistence trust is a
Producer decision; no compiler claim exceeds the declared input evidence.

## Compatibility, migration and affected consumers

- Old validators reject these new optional fields because the schemas are
  closed. Deploy readers/validators and regenerated types before enabling new
  writers; do not silently strip fields on downgrade. A derived document or
  package must refuse export to a consumer that cannot preserve/verify `P`.
- Old v1 documents without graphic provenance keep accepted behavior and identical
  compiler output bytes. Old v2 documents remain unchanged, but graphic media
  dependencies require a resolver migration adding the explicit
  `legacy_unclassified` class after checking retained storage identity. Old
  unclassified dependency inputs fail until migrated; they do not silently pass.
  With the class added, legacy manifest bytes stay unchanged, but report
  `dependenciesHash` changes because `compiler-core-v2.ts` hashes the entire
  dependency input. Any downstream hash over that report also changes; do not
  exclude classification from existing hash material.
  Non-graphic v2 dependencies and output stay unchanged. Legacy absence is
  “no derived-evidence claim,” not proof
  that the author never consulted data. New manual content emits an explicit
  manual binding. Never manufacture citations/source snapshots on import.
- Do not mutate an old graphic revision to add provenance. Explicit enrichment,
  refresh, template migration and deliberate reclassification create a new
  immutable revision and decision receipt. Checkpoints/builds retain old pins.
- Persistence stores source/method bytes and provenance records by durable
  identity under project authorization, freezes the selected content revision
  atomically, and protects referenced records from pruning. Delivery packages
  include addressed snapshots and permitted evidence, or refuse the claimed
  reproducible handoff. Redacted evidence exports must say they are incomplete;
  they cannot be accepted as a full reproducible package.
- Affected TypeScript consumers: schema validators/generator roots;
  `compiler-core.ts` (#7), `compiler-core-v2.ts`, source-resolution/build-snapshot
  assembly, package writers/readers/verifiers, later #9 authoring and #64 storage.
  `template-library.ts` keeps accepted project/template/copy semantics unchanged.
  Python packaging, CLI validators, Studio consumers and report readers must
  preserve and verify the new fields/snapshot inventory before derived support
  is exposed. Search all exhaustive consumers on the implementation baseline.
- Add common definitions under the dependency schemas, with appropriate `$ref`
  use; no new schema root/library is needed. Regenerate
  `packages/contracts/src/generated/contracts.ts` and `contracts-v2.ts`, plus
  affected `python/vera_timeline_agent/generated/contracts/` models for the
  script-document, compiler-dependencies, manifest and report v1/v2 roots.
  v2 script document is unchanged and should remain generated-identical.
  Generator output, not hand-edited types, determines any transitive changes.

## Changed acceptance before implementation

Explicit Producer approval must cover the deltas/defaults, accepted-source
integration baseline and separate new fixtures/goldens/acceptance tests needed
for them. Retain original frozen fixtures/goldens unchanged as accepted historical
evidence. The migration exception requiring approval is limited to the graphic
cases in `packages/contracts/test/compiler-v2.test.ts` (the media-backed
visual-only-kind test) and new migrated copies of these existing fixture stems
under `tests/data/authoring_v2/issue_173/compiler/`:

- `visual-only-graphic-still-ntsc-default`
- `visual-only-graphic-still-25fps-default`
- `visual-only-graphic-still-ntsc-override`

For each, preserve original input/manifest/report goldens; add slice-owned
migrated input/report copies with only the required legacy classification and
resulting `dependenciesHash`/transitive hash changes. Compare the migrated
manifest byte-for-byte to the retained original. Adjust that accepted test's
graphic branch only after explicit approval: old unmigrated dependencies must
refuse; approved migrated copies must compile. Image/capture and all unrelated
cases keep their accepted assertions and bytes. Enumerate any further affected
fixtures/tests on the actual implementation baseline and seek a revised note
before changing them. v1 legacy output stays byte-identical.

Add owned tests for
every design §6 case, canonical hash/array/null behavior, scope/authorization,
missing class/content refusal, legacy classification against retained storage,
v1 writer omission, no stripped pointers, and materialized-media
binding. Deterministic compiler output must retain `P` through both proposed
representations. Update generated-currentness and exhaustive-consumer checks.

Do focused/fast checks, independent Claude review and fixes, then the applicable
full gate/qualified evidence under the current verification policy. Runtime
integration separately needs actual #8/#9 operator save/reopen evidence and
truthful #10 Free output. A contract-design acceptance is not that proof.
No owner is dispatched, issue closed, schema approved or dependency promoted by
this proposal.
