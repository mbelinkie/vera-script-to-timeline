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
Legacy-unclassified content cannot carry cues. A real source-backed Table must
meet #166 source/evidence/derivation rules; synthetic manual data makes no claim
of external provenance. #218 implements the provenance core once; the runtime
owner adds only this approved typed applicability after #218 is Done.

### Concrete output shape details

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
  Derived endpoints retain the causal anchor evidence plus authored duration,
  next cue ID, or occurrence ID in an addressed evidence record. They never
  claim to be newly measured word edges.
- `delta`: signed reduced rational frame-time minus exact time; integer frames
  and origin mapping follow design §4. No re-quantization of local frames.

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
| v1 ScriptDocument | Add `ev24-table` to the accepted curated source union with the typed fields above, preserving existing provenance binding. Optional top-level `graphicCueSets:GraphicCueSet[]`; omitted or empty array means no cues; each present set must have nonempty cues. Only a matching curated graphic `VisualEvent` owner is legal |
| v2 ScriptDocument | Optional top-level `graphicCueSets` as above; keep `GraphicRevisionSource` unchanged. Match overlay or primary payload identity/source revision. Non-graphic, orphan, duplicate, legacy-unclassified and interrupted-primary cue owners block. Source-reference adjacency never binds a cue |
| v1/v2 CompilerDependencies | Optional `graphicTargetBindings:ResolvedGraphicTargetBinding[]`, omission/empty means none. Referenced manifests and evidence are retained by exact addressed bytes; reject duplicate, extra/unused, unauthorized or missing records. Reuse #7 `resolvedGraphics` plus #218 `resolvedGraphicContents/graphicProvenanceSnapshots`; extend their template/snapshot unions only for typed Table |
| v1 TimelineManifest | Optional `FusionGraphicEvent.graphicCueScheduleHash:Hash`; Table uses existing `fusion_template`/`fusion_graphic` variants with the new typed template/snapshot branch. Addressed semantic schedule shipped in package; existing event/use/source hash meanings unchanged. No native names added to the editor-neutral manifest |
| v1 BuildReport | Optional graphic result `graphicCueResult:{cueScheduleHash,outcome,executionPlanHash}`; hashes null when no valid schedule/plan exists. Outcome one of `planned_supported`, `verified`, `blocked`, `unqualified`, `manual_required`, `failed`. Compiler can emit only planned/blocked/unqualified/manual; adapter owns verified/failed replacement evidence. Existing live/placeholder/baked and manual fields retain meaning and must agree; manual remains unresolved |
| v2 BuildReport | Same per-owner cue result in a new optional top-level `graphicCueResults:[{occurrence,cueScheduleHash,outcome,executionPlanHash}]`, plus design §6 codes in closed `DiagnosticCodeV2` enum. Compiler must emit an explicit unsupported/unqualified result for cue-bearing media until a separately approved materialization contract is implemented. Never silently compile a static media asset as successful cues |
| v2 media/manifest | **No live Fusion variant or media realization field change authorized by this note.** Current media-only output cannot claim cue execution. A later bounded materializer must propose/approve the asset-content↔content-pin↔schedule-hash binding and manifest propagation before that path is enabled. This is a gated extension, not an unspecified field that an executor may invent |
| Package writer/reader/verifier and Studio adapter | Inventory exact manifest, schedule, binding and plan hashes/bytes with authorized project-owned template bytes and #218 provenance evidence; derive aggregate writes independently and reject discrepancies. Rehash at consumed stages; verify graph/type before semantic writes, exact origins before translated timing, and retain actual save/reopen evidence. #8's accepted security/target/audit guards remain required; this note grants no new native authority |

The compiler's ordinary successful manifest cannot contain a partial schedule.
When semantic validation blocks, emit the normal failure diagnostics plus a
non-success build/authoring result, not a fabricated manifest pointer. For valid
semantics but unsupported delivery, retain the valid schedule and explicit
unqualified/manual result without claiming verified placement. All diagnostic
codes and outcomes in design §6 are required consumer vocabulary. v1 uses its
existing open diagnostic-code pattern; v2 enum additions require regeneration.

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
`compiler-core.ts` and `compiler-core-v2.ts`, package writer/reader/verifier,
Studio adapter and report/diagnostic/Free manual readers, later #9 form and #99
registration. No new software dependency is needed. Regenerate
`packages/contracts/src/generated/contracts.ts`, `contracts-v2.ts` and affected
`python/vera_timeline_agent/generated/contracts/` models from changed v1/v2
script/dependency/manifest/report roots. v2 manifest is unchanged by this note
and must remain generated-identical. Do not hand-edit generated output.

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
