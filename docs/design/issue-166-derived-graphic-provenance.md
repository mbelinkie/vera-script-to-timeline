# #166 — derived graphic provenance

Proposed design, 2026-10-15. Acceptance: Producer. No runtime acceptance or
schema approval is implied by this file's presence.

## 1. Decision to review

Keep the existing graphic-use, semantic-snapshot and project-template identities.
For a source-backed graphic, add one immutable **provenance snapshot** binding
the resolved semantic values to the exact project template revision/package,
retained source evidence, citation and derivation. A separate `provenanceHash`
identifies that relationship. Never redefine an existing snapshot hash.

Ordinary manually entered lower-thirds need no invented source citation. A
source-backed graphic is explicitly declared `derived`; typing a value copied
from a source still counts as derived. Template-owned auto-fill alone does not.
Replay uses frozen semantic values. Refreshing data and migrating a template
are separate explicit operations that create a new graphic revision and retain
the prior relationship. Reproducible does not mean factually current.

The exact proposed wire deltas and defaults are in the separate
[CN-166-P1 proposal](../plans/issue-166-proposed-contract-change.md). They require
Producer approval before any frozen schema/type/test changes.

## 2. Authority and observed interfaces

Starting main/HEAD: `22f65c4f2b4ff61e7b08f530cdda3d92fea11d08`. Accepted source
revisions below are separate evidence; this issue does not integrate them.

| Authority | Exact accepted source / evidence | Consequence |
| --- | --- | --- |
| Product spec §§7, 8.2, Phase 9 | [spec at starting main](https://github.com/mbelinkie/vera-script-to-timeline/blob/22f65c4f2b4ff61e7b08f530cdda3d92fea11d08/docs/Script-to-Timeline%20Product%20Spec%20-%20Fable%20Rev2.md) | Conceptual `GraphicUse` pins immutable template revision and resolved snapshot; new revisions never silently rewrite a use/checkpoint/build; locators are not byte identity. |
| #24 D24-07; D24-09/15 | `e72aa2436fa49d6b256b7cf811d5c1dea39120c3`, [accepted](https://github.com/mbelinkie/vera-script-to-timeline/issues/24#issuecomment-5500767669); [coverage §5](https://github.com/mbelinkie/vera-script-to-timeline/blob/e72aa2436fa49d6b256b7cf811d5c1dea39120c3/docs/investigations/issue-24-representative-script-coverage.md) | Inputs, citation, snapshot/version, derivation and pinned template survive together; citations gain no screen time; examples remain synthetic. Stale “awaiting acceptance” prose does not supersede this acceptance. |
| #7 contract/compiler | `7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab`, [accepted](https://github.com/mbelinkie/vera-script-to-timeline/issues/7#issuecomment-5778374370); [approved contract note](https://github.com/mbelinkie/vera-script-to-timeline/blob/7cb942e4d9b8d75d87ae6adc8aac97fba5d5d6ab/docs/plans/issue-7-fusion-graphics-contract-change.md) | `VisualEvent.id` is the use identity. `CuratedFusionGraphicSource` pins `templateKey`, `projectRevisionId`, `packageDigest` and typed `semanticInputs`. Compiler resolves trusted project-scoped dependencies. |
| #20 template library | `951c658bf06fc9b06caeab88c9d43809c41cef94`, [accepted](https://github.com/mbelinkie/vera-script-to-timeline/issues/20#issuecomment-5504417300); [service](https://github.com/mbelinkie/vera-script-to-timeline/blob/951c658bf06fc9b06caeab88c9d43809c41cef94/packages/contracts/src/template-library.ts) | Project-local revision/package identity and authorization survive copying and lifecycle changes. `TemplateUse` is internal, not a shared `GraphicUse` schema. |
| #147 completion roadmap N11 | `75029de57baa594d3dfc7f509a09cfc21943e088`, [audit](https://github.com/mbelinkie/vera-script-to-timeline/blob/75029de57baa594d3dfc7f509a09cfc21943e088/docs/investigations/issue-147-completion-roadmap-audit.md) and live #166 | Bounded provenance design; existing identities retained; no new library/renderer. Live refined #166 supplies this ticket's criteria. |

#20's accepted commit is an ancestor of #7's accepted commit. Neither is an
ancestor of starting main. Main lacks their `template-library.ts` service and
curated-graphic schema/compiler additions. Future integration must consume the
accepted sources explicitly; rebuilding a lookalike from main is not equivalent.
The [curated-Fusion plan](../plans/curated-fusion-graphics.md),
[#24 plan](../plans/issue-24-representative-script-content-model-audit.md) and
[historical record](../IMPLEMENTATION_PROGRESS.md) provide context, not live
ownership or evidence for arbitrary graphics.

Important hash boundaries in accepted #7:

- `semanticSnapshotHash = sha256CanonicalJson({values, badgeAsset})`, where
  `values` retains the typed authored semantic inputs and explicit nulls;
  `badgeAsset` is null or the trusted `{assetId, contentHash}`. This hash excludes
  use ID, timing, citation, template key, project revision and package digest.
- `FusionTemplateSource` separately pins template key, project revision, package
  digest and trusted entry-asset hash. Its source ID is derived from project
  revision and package digest. The compiler rejects duplicate/missing/stale,
  cross-project and mismatched dependencies. These rules remain binding.
- #20's `TemplateUse.resolvedSnapshotHash` stores a caller-supplied hash; #20
  does not specify its material. Do not equate it with #7's semantic hash or the
  new provenance hash. Its copy `selectionSnapshotHash` describes template
  selection, not graphic data.

Current main v2 has `GraphicRevisionSource {kind:"graphic_revision", graphicId,
revisionId}` in `contracts/script-document-v2.schema.json`. This is a revision
reference, not a semantic/template/provenance payload. `SupportingItemV2` with
`role:"citation"` has generic content/placement and optional source; adjacency
is not a graphic-evidence relationship. Media dependency
`OccurrenceMediaResolutionV2.sourceSnapshot` identifies materialized media
bytes, not the source dataset that justified its labels. No v2 live Fusion
compiler support is inferred from these shapes.

## 3. Minimal relationship and fields

`use → pinned graphic content → semantic snapshot + pinned template tuple`
and, only for declared derived content, `→ provenanceHash → provenance snapshot
→ retained sources + citation snapshots + derivation`.

Provenance belongs to immutable graphic content, not narration timing. Several
uses may share the same content/provenance. Each build freezes its exact use,
range, graphic revision and provenance binding. Changing timing need not change
provenance; it still changes the compiled build as usual.

| Proposed field / meaning | Manual entry | Derived graphic |
| --- | --- | --- |
| `provenance.kind` on graphic content: `manual` or `derived` | Required for newly authored content; legacy absence remains legacy, without a derived-evidence claim | Required; never inferred from empty citation text |
| `provenance.snapshotHash` | Inapplicable | Required `sha256:` digest of the canonical provenance snapshot |
| Snapshot `schemaVersion: "graphic-provenance/v1"`, `projectId` | No snapshot required | Required; project scope is part of binding, not authorization by itself |
| `template`: `templateKey`, `projectRevisionId`, `packageDigest`, `entryAssetHash` | Existing #7 pins remain required | All required and must equal trusted resolved template identities |
| `semanticSnapshot`, `semanticSnapshotHash` | Existing #7 snapshot/hash remains unchanged | Required full resolved snapshot and its existing #7 hash, equal to compiler resolution; preserves values, null/default intent and asset hashes |
| `sources[]`: nonempty, unique `sourceKey` | Inapplicable | Required; every used external source has one entry |
| Each source `citation`: readable `title`, `publisher` (or explicit `unknown`), `originalLocator` (string or null), `versionLabel` (string or null) | Optional editorial citation cards stay independent | Required immutable citation value. A missing publisher/version must be honest; never synthesize a publisher version from retrieval time |
| Each source `snapshot`: `artifactId`, `contentHash`, `mediaType` | Inapplicable | Required verified retained bytes of sufficient evidence to audit the selected inputs; artifact ID is durable, locator is separate. An exact extract is allowed if citation + derivation identify its selection/context; it must not be labeled a complete original |
| `derivation`: `mode`, `version`, `note`, `method`, `parameters` | Inapplicable | Required; `note` identifies source keys, selected rows/fields, units, transformations and output fields, including rounding/exclusions or “none” |
| `derivation.mode: "manual"` | Inapplicable | Valid: versioned explanation/selection is sufficient for human audit; `method:null`, `parameters:{}`. Replay uses the frozen result; this makes no executable re-derivation claim |
| `derivation.mode: "deterministic"` | Inapplicable | `method:{id,version,artifactId,contentHash}` and canonical parameters required; retain exact method bytes. Only a separately implemented trusted method may run; never execute supplied code/expressions |
| Audit receipt: actor, creation/retrieval/verification time, operation kind, prior/new content hashes | Existing history rules | Required for create/refresh/migrate decisions, stored outside content-hash material. Time proves when a check occurred, never currentness or byte identity |

This is sufficient to reproduce the graphic from retained values and template
assets, and audit how its data was chosen. Exact original-source recovery is
claimed only when the original bytes were retained. A URL or publisher label
without verified retained evidence is insufficient for a new derived graphic.
Sensitive source bytes remain in authorized project storage; a share/export
does not gain permission to publish them merely because a hash is present.

## 4. Identity and lifecycle rules

Use the existing `canonicalJson` / `sha256CanonicalJson` in
`packages/contracts/src/compiler-core.ts`: recursively sorted object keys,
array order preserved, two-space JSON, trailing newline, UTF-8, SHA-256 with
lowercase hex and `sha256:` prefix. No alternative JSON canonicalizer is implied.
Reject non-JSON values, nonfinite numbers, malformed hashes, duplicate source
keys and unknown fields at the later schema boundary. Preserve string bytes;
no silent Unicode/whitespace/number normalization. Keep explicit nulls. Sort
`sources` by `sourceKey` before freezing; derivation references those keys.
Use decimal strings in source evidence when exact decimal precision is needed;
the destination semantic type still controls its accepted value.

Let `S` be #7's semantic hash. Let `P = H(snapshot)` using the whole proposed
snapshot, excluding the hash itself and external audit receipt. The snapshot
contains the full semantic snapshot, `S`, template tuple, project ID, source
artifact/hash/citation values and derivation. Changing a citation, source bytes,
derivation, semantic value, badge hash or template pin changes `P`, even if the
visible graphic happens to look the same. Artifact IDs remain durable references;
the hashes verify bytes. Storage-path relinking does not change either hash.

`P` identifies content, not a use, timeline or render. Never use `P` as a new
`VisualEvent.id`, template revision ID, asset-byte hash or #20 copy hash. Compare
the entire trusted tuple, not a matching name or `S` alone. A digest verifies
integrity after trusted resolution; it does not grant access or authenticate a
publisher. Source availability/currentness observations remain separate receipts.

1. **Repeat generation:** verify retained source and template bytes, project
   authorization and semantic binding; use the same `P`, `S`, values and pins.
   With identical complete compiler inputs, expect identical deterministic
   output. A new build/timeline identity or changed timing can change a manifest;
   no pixel/render equivalence across Resolve versions is claimed.
2. **Refresh data:** explicitly acquire/retain a new source snapshot and review
   its derivation/result. Create new graphic content and `P2`, preserving template
   pin by default. The decision receipt binds old/new hashes. A changed source
   version can yield the same visible values and `S` but a different `P2`. Select
   the new revision explicitly; old uses/checkpoints/builds remain pinned.
3. **Migrate template:** explicitly select an approved compatible project revision,
   verify its package/entry bytes, validate all semantic fields, resolve its new
   snapshot, then create new content/`P3`. Keep source snapshots unless a separate
   refresh is requested. Do not guess renamed fields, drop values or swap badge
   assets. Missing mapping is a repairable blocker; #167 owns any cue migration.
4. **Copy project/template:** #20 creates destination-owned revision IDs while
   retaining package digest and copy lineage. Template copying does not copy or
   authorize a source dataset. Any later graphic-content copy must separately
   authorize/retain evidence in the destination, rebind project/template IDs and
   produce a new `P`; a source project's `P` is historical lineage only.

## 5. Synthetic worked examples

All names/data below are fictional. `H(x)` means the exact canonical hash above;
symbols `R1`, `D1`, `E1`, `A1` stand for actual verified project revision, package
digest, entry hash and artifact ID when implemented. They are deliberately not
wire-valid hashes or a claim of registered/available assets. These examples
live here, outside frozen fixtures. `T1` is the trusted tuple
`{templateKey:"ev24-lower-third", projectRevisionId:R1, packageDigest:D1,
entryAssetHash:E1}` in project `demo`.

**Manual lower-third.** Existing EV24 inputs:

```json
{"country":"otis","topLineOverride":"Demo Presenter","bottomLineOverride":"Synthetic example","badgeOverrideAssetId":null}
```

`year` is absent for Otis, preserving #7. Let `M = {values:<above>,
badgeAsset:null}`. `Smanual=H(M)`. New content declares `{kind:"manual"}`;
there is no source array/derivation/provenance snapshot. The existing use ID,
template tuple, anchor and 64-frame minimum still apply. Template auto-fill is
owned by the pinned package; blank override behavior is not reimplemented.

**Derived lower-third.** A retained synthetic source JSON contains
`{"unit":"observations","rows":[{"id":"east","count":18},{"id":"west","count":27}]}`.
Its exact retained bytes have `B1=H(<source JSON>)` when stored with the canonical
serializer. Citation is `{title:"Demo station tally",publisher:"Fictional Lab",
originalLocator:"https://example.invalid/demo-tally",versionLabel:"demo-v1"}`.
Source key `tally` refers to `{artifactId:A1,contentHash:B1,mediaType:"application/json"}`.
Resolved values are `{country:"otis",topLineOverride:"Demo total",
bottomLineOverride:"45 observations",badgeOverrideAssetId:null}` with
`badgeAsset:null`, giving `S1`. Derivation is
`{mode:"manual",version:"1",note:"Source tally: select east and west count;
18 + 27 = 45 observations; set bottomLineOverride to 45 observations and
topLineOverride to Demo total; country otis is presentation only; no rounding
or exclusions",method:null,parameters:{}}`.
The full snapshot contains `schemaVersion`, project `demo`, `T1`, resolved
semantic snapshot/`S1`, that source entry and derivation; `P1=H(snapshot)`.
The authored binding is `{kind:"derived",snapshotHash:P1}`. This uses EV24
text overrides, not a new chart renderer or unsupported template field.

**Repeat.** The same source bytes, tuple, values and derivation resolve to `P1`
and `S1`. No network fetch is necessary. An unavailable URL yields a historical
snapshot status; it cannot cause the result to be relabeled current or refreshed.

**Refresh.** Explicit refresh retains `demo-v2`, where west is 30. After review,
45 becomes 48, source bytes become `B2`, citation version becomes `demo-v2`,
and derivation version `2` records `18 + 30 = 48`. Produce `S2/P2`, still using
`T1`. The author selects the new content revision; the old build retains
`A1/B1/S1/P1/T1`. If the refreshed counts were unchanged, a new citation/source
snapshot would still produce a new `P` without requiring a new `S`.

**Template migration.** Explicitly migrate the refreshed content to verified
project revision `R2` and package/entry pins `D2/E2`. If schema-compatible,
retain `B2` and derivation; resolve values under `T2`, producing `P3` even if
`S2` stays equal. `R2` is illustrative, not an actually approved revision. If
it is absent or incompatible, migration stops with `P2/T1` still selected;
the operation never picks the current library revision automatically.

## 6. Success, refusal and recovery

“Block” below means no new derived-ready output/placement. Authoring may retain
an unresolved draft; a report must identify the use and repair action. Existing
builds are historical evidence and are never rewritten by a failed operation.

| Condition | Outcome | Recovery |
| --- | --- | --- |
| New explicit manual content, valid #7 pins/values | Ordinary manual graphic; no derived-evidence claim | Existing #7/#8 checks still apply |
| Declared derived; complete matching `P/S/template/source` and verified bytes | Ready as retained snapshot | Record verification receipt; do not claim upstream currentness |
| Derived declaration missing `P`, sources, citation or derivation | Block: provenance incomplete | Retain missing evidence and create a new complete revision; never downgrade silently to manual |
| Hash valid syntactically but does not match retained record/bytes, resolved values, project or template tuple | Block: provenance mismatch | Restore exact verified evidence or deliberately author a corrected revision; never overwrite evidence to fit the hash |
| URL/service unavailable, but retained source evidence, semantic snapshot and template bytes verify | Reproducible historical snapshot; freshness unknown | Keep snapshot; offer later explicit refresh |
| Publisher reports a newer version, old retained evidence verifies | Historical snapshot; update available | Keep, compare or explicitly refresh; no automatic replacement |
| Source bytes lost; values remain | Block new derived-ready generation/audit claim | Relink exact hash-verified bytes; otherwise new explicit source-backed revision. An existing verified render can be viewed, but is not proof of recoverable derivation |
| Manual derivation cannot be executed | Frozen semantic replay allowed; human-readable audit only | Human reviews note/source. Do not label it an automatic re-derivation |
| Deterministic method bytes unavailable, while source/result/template verify | Frozen graphic replay allowed; executable re-derivation unavailable | Restore exact method hash before running re-derivation; refresh needing that method blocks |
| Changed semantic input with old `P` | Block mismatch | Review derivation and create new content/`P`; preserve old revision |
| Missing/mismatched/incompatible pinned template or package-owned asset | Block, even if data/citation valid | Restore exact approved bytes or explicitly migrate; never select a nearby/current revision |
| Name/URL/time/version label exists but byte identity cannot be verified | Block: unverifiable identity | Acquire/retain permitted bytes and verify, then create a complete revision |
| Source/template access denied; cross-project pin | Block unauthorized resolution; hashes grant no access | Restore authorized access or use an explicitly authorized destination-owned copy |
| Legacy input without new declaration | Preserve accepted legacy manual behavior, labeled no derived provenance | Explicitly classify during later edit; no backfilled citation or retrospective source-backed claim |

## 7. Compatibility and bounded handoff

CN-166-P1 adds an explicit derived declaration and hash-bound record; free-form
citation cards or only a package provenance file cannot encode the per-graphic
source/result relationship. New wire fields are therefore proposed, not applied.
Old non-derived #7 inputs retain identical legacy output bytes; new fields do
not change the material of `semanticSnapshotHash` or invent a meaning for #20's
`resolvedSnapshotHash`. v2 `graphicId/revisionId` stays a stable reference into
graphic content, with provenance frozen by its revision. Rendering a v2 graphic
as a media asset must retain a verified binding from that asset's content hash
to the provenance snapshot; a media hash alone is not semantic provenance.

| Later owner | Exact responsibility and acceptance boundary |
| --- | --- |
| Missing provenance core implementation (Inbox handoff; see evidence README) | Adopt accepted #7/#20 source explicitly; implement CN-166-P1 schemas/resolution/hash/diagnostics and pure create/refresh/migrate operations. Do not reopen or replace closed #7/#20 implementations. Automated tests cover the matrix, canonical permutation/identity cases, unchanged legacy goldens and v1/v2 mapping. Separate Producer approval precedes frozen changes. |
| #64 project/document persistence | Durable authorized artifact/provenance storage and immutable graphic revisions, atomic selection/history, retention of use/checkpoint/build references, exact relinking. No permission/publication inferred from a citation. Coordinate core interfaces before storage integration. |
| #9 authoring form, #67 visual cards, #69 citations | Manual/derived declaration, evidence input/summary, explicit keep/refresh/migrate review and visible blocker repair. Citation cards remain editorial support with zero implied picture duration. UI implementation stays with these owners. |
| #8 live Studio placement | Preserve accepted EV24 constraints; consume verified values/package and retain the use-to-`P` mapping in build evidence. Real save/reopen verification of exact values/template/range remains required. Adding provenance support must be scoped before Ready; no new renderer is implied. |
| #99 template registration | Supply only approved template/schema/asset revisions and compatibility evidence. Does not manufacture data provenance or accept arbitrary templates. |
| #167 highlight targets/cues | Own all target/state/timing/reset/overlap and cue-migration rules. `P` binds data/template content only; it never replaces #167's resolved cue schedule/hash or accepts its runtime behavior. |
| #10 Free fallback | Preserve truthful placeholder/manual or separately verified baked outcome. A verified provenance record does not prove baked or live delivery. |

Core automated acceptance must include missing/duplicate/wrong-project/hash
refusals, source unavailable versus bytes lost, manual versus derived defaults,
refresh with changed data but equal visible output, incompatible migration and
independent source/template updates. Repeated identical compiler snapshots
must be byte-identical; legacy goldens remain unchanged. Verify the actual bytes
at materialization; no test should substitute URL reachability for identity.

Later real-application acceptance: an authorized operator builds one manual
EV24 and the synthetic derived EV24 example, saves/reopens, confirms values and
pinned package identity; repeats from retained evidence with source unavailable;
then deliberately refreshes and migrates one compatible registered revision.
New timelines show selected revisions; prior timelines/build receipts retain
their old values and `P`. Missing bytes/template and mismatch cases refuse before
placement. No real application, provider or external service is invoked here.

## 8. Producer acceptance

1. Review §§1–4 of this exact design. Accept or revise the distinction between
   manual and derived content, required retained source/citation/derivation,
   separate provenance hash, and historical replay versus freshness claims.
2. Review §5–6. Expected: repeat uses frozen values; refresh and template
   migration each create an explicitly selected revision; failure never swaps
   data/template or rewrites prior builds. Decide whether those recovery rules
   match the intended product.
3. Review [CN-166-P1](../plans/issue-166-proposed-contract-change.md) and §7.
   Accept or revise the proposed compatibility/default/interface mapping and
   bounded later-owner handoff. Acceptance of this design records a proposal;
   frozen wire changes still require explicit approval of CN-166-P1 before
   implementation, and runtime/External acceptance remains outstanding.

Record: `Accept issue #166 design at <commit>; CN-166-P1 proposal accepted for
handoff` or `Revise issue #166 step <number>: <change>`. To authorize later
frozen-boundary implementation, separately state `Approve CN-166-P1 at <commit>`.
Keep #166 In review until the exact design receives explicit Producer acceptance.
