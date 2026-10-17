# CN-167-P1 — proposed semantic highlight cue boundary

**Unapproved. Design acceptance does not approve this note.** No frozen surface
changes in #167. Later implementation requires explicit Producer approval of
this exact note/revision and a reconciled integration baseline.

## Fields and rationale

The existing narration range, #7 semantic snapshot and #166 provenance snapshot
cannot express occurrence-local ordered state changes. Preserve them; add
the `GraphicCueSet`, `ResolvedGraphicTargetBinding` and
`ResolvedGraphicCueSchedule` shapes and algorithms in
[design §§3–4](../design/issue-167-semantic-highlight-cues.md).
This note adopts those exact definitions, not a second competing shape.

The first target profile is #219's exact synthetic Table. Existing #7 and
CN-166-P1 only allow `ev24-lower-third` and its typed semantic snapshot. Extend
their discriminated template/content types with `templateKey:"ev24-table"`,
`semanticInputs:{tableData:string}` and resolved
`{values:{tableData:string},badgeAsset:null}`. The corresponding #166 template
pin accepts this key only with that snapshot branch. No arbitrary JSON input,
new country/badge semantics or renderer. #7's existing semantic hash algorithm
and #166's whole-snapshot provenance hash are unchanged; Table adds an explicitly
typed input domain. The exact data-byte hash, manifest-byte hash, setting-byte
hash, canonical semantic hash, provenance hash and package digest stay distinct.
The accepted #219 setting alone is not a registered package/revision.

All objects are closed; receiving ID/hash/version/rational constraints remain.
New authoring requires explicit manual/derived classification under #218.
The new v1 Table source requires `provenance`; it never inherits the optional
legacy lower-third omission rule.
Legacy-unclassified content cannot carry cues. A real source-backed Table must
meet #166 source/evidence/derivation rules; synthetic manual data makes no claim
of external provenance. #218 implements the provenance core once; the runtime
owner adds only this approved typed applicability after #218 is Done.

### Concrete output shape details

Add v1 `$defs/GraphicCuePointAnchor` as the closed union
`{kind:"word",anchor:{blockId,tokenId,affinity:"before",quotedWord,anchorVersion}}`
or `{kind:"audible_word_end",anchor:{blockId,tokenId,affinity:"after",quotedWord,anchorVersion}}`.
Copy the exact v2 `WordInpointAnchor` / `WordAudibleEndAnchor` field constraints
into these named v1 definitions: block/token are UUID EntityId, quotedWord is
nonempty exact text, anchorVersion positive EntityVersion equal to the frozen
block version. No cross-root schema reference or other PointAnchor kind is used.
`GraphicCueTiming` is the exact closed timed/start-only union from design §3,
referencing this anchor; add both definitions to v1 generated-type consequences.
The v1 graphic owner is its containing `NarrationBlock` and `VisualEvent.range`
must bind only that block; any cross-block range/anchor refuses this profile.
The accepted v1 timing format has word onsets and derived ends only. Its current
word marks can resolve onset intent after existing exact text/offset/audio checks;
resolve anchor.tokenId against the frozen `NarrationBlock.tokens[].id`, require
`token.value === anchor.quotedWord`, and exactly one `kind:"word"` mark with
`startUtf16 === token.startOffset`, `endUtf16 === token.endOffset` and
`value === token.value`. `exactTime=timeMs/1000`, reduced, block-local.
Missing/duplicate token identity, stale anchor/version/text or zero/multiple
matching marks refuse `GRAPHIC_CUE_TIMING_UNQUALIFIED`; repeated words never
match by text alone. These existing v1 token/range types are present at accepted
#7's `script-document-v1.schema.json` (`NarrationToken`, `TextAnchorRange`).
audible-end cue anchors explicitly refuse until a separately approved timing
extension supplies actual support. This note adds no timing provider or guessed
audible boundary. v2's equivalent anchor subset is deferred as stated below.

`ResolvedGraphicCueSchedule.cues[]` has exactly
`{id,version,targetIds,state,start,end,endPolicy}`. Target IDs are lexical-sorted;
cue array retains authored order. `endPolicy` is null for ordinary timed intent
or the authored start-only policy. Each endpoint is
`{blockId,anchor,exactTime,basis,evidenceHash,delta,recordFrame,localFrame}`:

- `anchor`: the original current PointAnchor or null for derived time.
- `exactTime`: reduced rational `{numerator,denominator}` block-local seconds;
  nonnegative safe-integer numerator and positive safe-integer denominator.
- `basis`: `word_onset`, `audible_word_end`, `duration_derived`,
  `next_cue_start` or `graphic_end`; `evidenceHash` identifies the verified
  frozen timing/boundary evidence, including exact audio and text binding.
  Derived endpoints use the closed addressed record below. They never claim
  to be newly measured word edges.
- `delta`: signed reduced rational frame-time minus exact time; integer frames
  and origin mapping follow design §4. No re-quantization of local frames.

Every endpoint addresses one closed `GraphicCueEndpointEvidence` record by
`evidenceHash=H(record)`. Fields (all required, explicit nulls retained):

```text
{schemaVersion:"graphic-cue-endpoint-evidence/v1", basis,
 blockId, blockRevision, tokenId, timingHash, audioHash, textHash,
 timingInputHash, exactTime, durationMs, nextCueId, occurrence,
 causeEvidenceHash, occurrenceBoundaryHash}
```

`basis` equals its endpoint; block ID/revision are the frozen owner UUID/version;
`exactTime` equals the endpoint's block-local reduced rational. Hashes use
prefixed `Hash`. `timingInputHash=H(frozen NarrationDependency with only audio.locator omitted)` for v1,
or `H(full frozen NarrationTokenTimingMapV2)` for the deferred v2 seam.
`timingHash` copies v1 `narration[].timing.contentHash` or v2
`narrationTimingMaps[].timingHash`; `audioHash`/`textHash` copy the exact same
record's fields, independently verified against the frozen narration/audio.
For **every** basis, blockId/blockRevision/timingHash/audioHash/textHash/
timingInputHash are non-null and copied from that single owning frozen timing
input. In v1 it must be `status:"ready"`; missing/failed/ambiguous dependencies
refuse `GRAPHIC_CUE_TIMING_UNQUALIFIED`. Only tokenId and the explicitly listed
causal fields may be null. Omit only v1 audio.locator before timingInputHash,
retaining the full audio `{durationSamples,sampleRate,channels}` and all other
dependency fields; location is resolved and audited separately. No other
normalization/field omission is allowed. The package retains the frozen timing
record **and exact narration audio bytes**, verifies declared timing artifact
hash and audioHash, and separately retains the original locator-bearing build
dependency. Relinking identical bytes does not change this cue evidence hash
(the existing whole-build dependencies hash may still change).
These mappings preserve the original hash domains rather than redefining them.

For `word_onset`/`audible_word_end`, `tokenId` equals the anchor token; all five
causal fields (`durationMs,nextCueId,occurrence,causeEvidenceHash,
occurrenceBoundaryHash`) are null. v1 `audible_word_end` cannot currently produce
such a record and must refuse. For `duration_derived`, tokenId is null,
durationMs is authored positive integer, causeEvidenceHash addresses the supplied
opposite endpoint; other causal fields are null. For `next_cue_start`, tokenId
and durationMs are null, nextCueId selects the first authored cue in the next
strictly-later start group, causeEvidenceHash addresses that cue's start, other
causal fields null. Equal-start tie selection is for evidence only and does not
change grouped timing. For `graphic_end`, tokenId/durationMs/nextCueId/
causeEvidenceHash are null, occurrence equals the cue-set occurrence, and
occurrenceBoundaryHash=H({schemaVersion:"graphic-cue-occurrence-boundary/v1",
occurrence,blockId,blockRevision,blockRecordStartFrame,
recordRange,frameRate,timingInputHash}); retain this exact boundary record too.
Its exactTime is `(recordRange.endFrame-blockRecordStartFrame)/fps`, reduced.
When all three timed values exist, preserve independently resolved start/end
evidence and check duration; do not derive one endpoint again. This makes the
evidence graph acyclic. Sort/deduplicate evidence inventory by computed hash;
the package verifier recomputes every record/hash/cause and interval from frozen
inputs. No undefined evidence material feeds cueScheduleHash.

`segments[]` is `{localRange:{startFrame,endFrame},states:[{targetId,state}]}`,
covering `[0,N)` with no gap, overlap or adjacent equal vectors; states contains
every manifest target in lexical ID order. Cue identity/evidence is retained
even when adjacent segments merge. The semantic schedule contains no private
node name, locator or execution status. Addressed schedule bytes use existing
canonical JSON; manifest pointers hash those bytes. Cue-set normalization and
hashing precede compiler resolution as specified in the design.

An addressed package execution plan has exactly
`{schemaVersion:"graphic-cue-execution/v1",cueScheduleHash,targetManifestHash,
bindingHash,writes:[{localFrame,aggregateValue}]}`; writes are strictly increasing
and include frame 0. `bindingHash=H(ResolvedGraphicTargetBinding)`; native control
names/types are taken only from the pinned manifest. `executionPlanHash=H(plan)`
is recorded in the report/package inventory, not substituted for cue schedule
hash. The actual adapter receipt adds actual timeline/comp origins and translated
write/readback evidence to the existing audited #8 result envelope. That envelope
is provisional until #8 acceptance; reconcile field names there before runtime
Ready, preserving these identities and separate planned/actual meanings.

| Frozen surface proposed | Precise delta and consumers |
| --- | --- |
| v1 ScriptDocument | Add `ev24-table` to the accepted curated source union with the typed fields above, requiring explicit provenance on that new branch. Optional top-level `graphicCueSets:GraphicCueSet[]`; omitted or empty array means no cues; writers omit rather than emit an empty array, preserving canonical no-cue bytes. Each present set must have nonempty cues. Only `occurrence.kind:"visual_event"` and `contentPin.kind:"v1_curated"` are included in the v1 schema, bound to a matching curated graphic owner |
| v2 ScriptDocument | Optional top-level `graphicCueSets` as above; keep `GraphicRevisionSource` unchanged. Match overlay or primary payload identity/source revision. Non-graphic, orphan, duplicate, legacy-unclassified and interrupted-primary cue owners block. Source-reference adjacency never binds a cue |
| v1/v2 CompilerDependencies | Optional `graphicTargetBindings:ResolvedGraphicTargetBinding[]`, omission/empty means none. Referenced manifests and evidence are retained by exact addressed bytes; reject duplicate, extra/unused, unauthorized or missing records. Reuse #7 `resolvedGraphics` plus #218 `resolvedGraphicContents/graphicProvenanceSnapshots`; extend their template/snapshot unions only for typed Table |
| v1 TimelineManifest | Optional `FusionGraphicEvent.graphicCueScheduleHash:Hash`; Table uses existing `fusion_template`/`fusion_graphic` variants with the new typed template/snapshot branch. Addressed semantic schedule shipped in package; existing event/use/source hash meanings unchanged. No native names added to the editor-neutral manifest |
| v1 BuildReport | Optional graphic result `graphicCueResult:{cueScheduleHash,outcome,executionPlanHash}`; hashes null when no valid schedule/plan exists. Outcome one of `planned_supported`, `verified`, `blocked`, `unqualified`, `manual_required`, `failed`. Compiler emits planned/blocked/unqualified/manual only. Adapter replaces a planned result with verified, failed, blocked or unqualified according to design §6 and retains stage/zero-write or partial-write evidence; only compiler chooses manual_required. Existing live/placeholder/baked and manual fields retain meaning and must agree; manual remains unresolved |
| v2 BuildReport (deferred) | Proposed per-owner cue result in optional top-level `graphicCueResults:[{occurrence,cueScheduleHash,outcome,executionPlanHash}]`, plus design §6 codes in closed `DiagnosticCodeV2` enum. Same compiler/adapter outcome permissions as v1. If this extension is later adopted, compiler must explicitly refuse unsupported cue-bearing media until a separately approved materialization contract exists. Current closed-schema rejection remains in force; no silent static success |
| v2 media/manifest | **No live Fusion variant or media realization field change authorized by this note.** Current media-only output cannot claim cue execution. A later bounded materializer must propose/approve the asset-content↔content-pin↔schedule-hash binding and manifest propagation before that path is enabled. This is a gated extension, not an unspecified field that an executor may invent |
| Package writer/reader/verifier and Studio adapter | Inventory exact manifest, schedule, binding and plan hashes/bytes with authorized project-owned template bytes and #218 provenance evidence; derive aggregate writes independently and reject discrepancies. Rehash at consumed stages; verify graph/type before semantic writes, exact origins before translated timing, and retain actual save/reopen evidence. #8's accepted security/target/audit guards remain required; this note grants no new native authority |

The compiler's ordinary successful manifest cannot contain a partial schedule.
When semantic validation blocks, emit the normal failure diagnostics plus a
non-success build/authoring result, not a fabricated manifest pointer. For valid
semantics but unsupported delivery, retain the valid schedule and explicit
unqualified/manual result without claiming verified placement. All diagnostic
codes and outcomes in design §6 are required consumer vocabulary. v1 uses its
existing open diagnostic-code pattern; v2 enum additions require regeneration.

Report hashes are deterministic by stage/outcome:

| Stage/outcome | cueScheduleHash | executionPlanHash |
| --- | --- | --- |
| Compiler `planned_supported` | Non-null valid schedule hash | Non-null; compiler derives the exact package-owned plan algorithm from the trusted binding and semantic segments before emitting this outcome |
| Compiler `unqualified` or `manual_required`, with valid semantics | Non-null valid schedule hash | Null; no executable plan is authorized for that delivery |
| Compiler `blocked` from semantic/integration refusal | Null | Null; do not issue a partial schedule/plan pointer |
| Adapter replacement: `verified`, `failed`, `blocked` or `unqualified` | Preserve compiler hash unchanged | Preserve compiler hash unchanged; receipt records observed refusal/failure, never rewrites a planned identity |

Package writer/verifier independently rederives the compiler's plan; a mismatch
refuses. Outcome provenance/stage remains in the existing result envelope so an
adapter-blocked result with hashes is distinct from a compiler-blocked refusal.
No adapter can turn a compiler refusal into verified delivery.

**Approval scope is v1 only.** Every v2 row and v2 union branch above is a
deferred interface proposal, without an implementation owner or wire-change
authority. #220 owns the complete required v1 runtime, not a v2 materializer.
Before v2 adoption the steward must retain a bounded duplicate-checked owner
and separate contract-change approval. Existing v2 schema refusal covers the
present unsupported case; do not add fields merely to imply it is supported.

## Compatibility and migration

Old no-cue documents/dependencies preserve accepted behavior and byte-identical
output. New fields default to no cues only when omitted/empty at top level;
present empty cue sets or stripped cue references fail. Omission is not allowed
to erase a stored new-format cue-bearing revision on persistence round-trip.
New closed-schema readers/validators must deploy before writers. Older consumers
must reject new branches/fields explicitly; no silent downgrade to static data,
missing cue or unclassified provenance. Removing cues is a deliberate edit/new
revision retaining its prior history, never a parser compatibility fallback.

Dataset/label/order changes invalidate the whole binding; a new manifest revision
and explicit author-approved target mapping/cue-set rebind are required. Source
refresh, template migration and project copy follow #166/#20 authorization,
new immutable content and receipt rules. Destination copy rebinds occurrence,
project revision/content pins and new cue hashes; old hashes remain lineage.
No hidden current-template selection or label match. Every implementation must
audit exhaustive consumers on its actual accepted-source integration baseline.

Affected consumers: authoring serializer/validator/persistence/resolver,
`compiler-core.ts`, package writer/reader/verifier,
Studio adapter and report/diagnostic/Free manual readers, later #9 form and #99
registration. No new software dependency is needed. Regenerate
`packages/contracts/src/generated/contracts.ts` and affected
`python/vera_timeline_agent/generated/contracts/` models from changed
script/dependency/manifest/report v1 roots, including the new named anchor/timing
definitions. All v2 schemas, `contracts-v2.ts`, v2 Python generated modules and
`compiler-core-v2.ts` stay unchanged under this note. If deferred v2 deltas are
later approved, enumerate/regenerate their script/dependency/report roots then;
v2 manifest needs its own approved realization boundary. Do not hand-edit types.

## Acceptance consequences and owners

Runtime must start from an explicit integration of accepted #7/#20/#166/#218
and accepted #8, preserve later main, and reconcile #8's actual result/package
seam. #99 owns the required registered Table package/revision/profile availability;
no public/proprietary distribution permission is inferred from the local probe.
The runtime Inbox owner is named in
[the handoff](../verification/issue-167/runtime-handoff.md); it is blocked by
#8, #167, #218 and #99. No implementation/dispatch follows from this note.

Before frozen edits, approval must name CN-167-P1 and the exact added typed
branches/defaults/readers, integration baseline, generated effects and new
test inventory. Preserve existing accepted fixtures/goldens/tests unchanged;
add issue-owned synthetic Table input/schedule/manifest/report goldens and
negative tests for every design §§5–6 row. Any necessary alteration to an
accepted test requires a separately enumerated amended note before editing.
Retain #218's separately approved legacy migration boundaries; do not widen them.

Required runtime evidence: deterministic exact repeated bytes, legacy no-cue
goldens, all timing/state/hash/authorization refusals, no semantic writes on
preflight/graph refusal, exact aggregate writes, strict profile gating and honest
Free manual accounting; then adversarial Claude review/fixes and applicable full
verification under the current policy. Actual Studio profile/schedule save/reopen
and visual boundaries/visibility require External acceptance; v2 cue realization,
broader datasets/profiles/transitions/Free remain unqualified until separately
approved and proved. Approval of this note cannot serve as that runtime proof.

Separate response: `Approve CN-167-P1 at <commit>` or identify the field/consumer/
migration decision to revise. Accepting #167 design alone leaves this unapproved.
