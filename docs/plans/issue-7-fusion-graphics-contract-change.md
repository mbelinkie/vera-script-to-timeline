# Issue #7 contract-change proposal — curated EV24 graphics

## Status and approval gate

**Proposed; producer approval pending.** This note is the complete proposed
boundary for issue #7. Do not change shared schemas, generated types, frozen
fixtures, goldens, accepted tests, or compiler behavior until the producer
explicitly approves it. A changed decision requires a revised note and a new
approval before implementation.

The bounded slice adds a typed EV24 Lower Third occurrence and deterministic
compiler output. It does not place a Fusion graphic in Resolve, write Fusion
controls, implement a Free baked fallback, add an authoring picker, accept
arbitrary templates, or reconcile an existing timeline.

## Proposed schema

### `ScriptDocument v1`

Extend `Phase1VisualSource` with one `curated_fusion_graphic` variant. The
existing `VisualEvent.id` is the stable graphic-use identity; its existing
`range` is the narration anchor, and its `layer` selects the configured video
track. A default build targets V4, but the track is resolved structurally from
the adjustable track map, never from a track-name string. A ready graphic must
use `presentationMode: "overlay"`, `framingPolicy: "native"`,
`motionPreset: "none"`, `audioPolicy: "mute"`, and hard cuts or no transitions.

The source contains only:

```ts
type CuratedFusionGraphicSource = {
  kind: "curated_fusion_graphic";
  templateKey: "ev24-lower-third";
  projectRevisionId: string; // opaque project-scoped immutable revision ID
  packageDigest: `sha256:${string}`; // hash-pinned package from the library
  semanticInputs: {
    country: Ev24Country; // exact stable IDs from the accepted EV24 profile
    year?: number; // positive integer required unless country is "otis"
    topLineOverride: string | null;
    bottomLineOverride: string | null;
    badgeOverrideAssetId: string | null; // project asset identity only
  };
};
```

`country: "otis"` forbids `year` entirely. Non-`otis` countries require a
positive integer year. `null` explicitly means no text override or badge
override. Non-null text overrides must be nonempty. The compiler preserves
these nulls in the semantic snapshot; it never writes guessed title, performer,
country name, or year text. At the later trusted Fusion boundary, null text
overrides map to blank controls so the authored macro performs its own auto-fill.
The badge value is an `asset_...` identity that must resolve in the same
project; author data cannot contain an absolute or relative file locator.
Author data also cannot contain a script, expression, Fusion tool/control ID,
graph fingerprint, or arbitrary template name.

Extend `CompilerDependencies v1` with an optional `resolvedGraphics` array,
interpreted as empty when omitted. Each entry is a trusted, project-scoped
snapshot keyed by project revision ID and package digest. It confirms the
registered `ev24-lower-third` revision, immutable package digest, EV24 package
file hash, and any selected badge asset identity/content hash. The compiler
rejects missing, duplicate, stale, cross-project, or hash-mismatched entries;
it does not fall back to a current revision or a machine path. No graphic
dependency is needed for an existing document without graphic occurrences.
Add an optional `build.graphicDeliveryTarget: "studio" | "free"`, required by
the compiler when a graphic is present and omitted for existing non-graphic
builds. It selects a report plan only; it cannot change manifest bytes.

### `TimelineManifest v1`

Add a `fusion_template` source containing only the stable template key,
project revision ID, package digest, and trusted entry-asset content hash. Add
a `fusion_graphic` event with the existing event identity, source ID, video
track ID, integer-frame record range, timing precision, alignment version, and
visual-event provenance, plus the resolved EV24 semantic snapshot and its
canonical SHA-256 hash. The event has no Fusion tool IDs, control names,
expressions, or filesystem paths. Its duration comes from the authored
narration anchor. A ready EV24 occurrence shorter than the accepted 64-frame
minimum fails with an explicit diagnostic; the compiler never silently extends
or truncates the range. The configured default video target is V4.

The manifest describes the editor-neutral graphic intent. It does not say
that a live graphic was placed or a baked graphic was rendered. Identical
document/dependency snapshots produce identical manifest bytes across delivery
editions.

### `BuildReport v1`

Every `fusion_graphic` event gets one `EventBuildResult` with its event/source,
track, and range identities. Only graphic results add
`graphicMaterialization: "live" | "placeholder" | "baked"` and
`manualCompletionRequired: boolean`. Existing `disposition` remains `placed`
for a planned live or baked result and `placeholder` for a placeholder result.
The report distinguishes a **planned compiler outcome** from a later adapter's
verified placement. This slice plans live Studio delivery and a labeled
placeholder plus a linked manual-completion item for Free. `baked` is
schema-representable for a future verified asset path, but this slice does not
render or select one. An absent or invalid template/asset blocks compilation
with a stable diagnostic; it is never silently downgraded to live or baked.

The report's event results, issue list, manual-completion items, and summary
counts must account for every graphic exactly once. A Free placeholder and its
manual item are both visible; the manual item references the original graphic
use. An unsupported downstream adapter must fail visibly on
`fusion_graphic`, with no partial package or claim that it placed the graphic.
Any later adapter result must replace the planned outcome with verified
evidence; #7 does not claim Resolve placement.

## Compatibility, generated types, and migration

- Keep the existing `/v1` schema identifiers. The new source/event variants,
  optional compiler-dependency fields, and graphic report fields are additive.
  Existing accepted inputs and outputs remain valid and byte-identical.
- Regenerate the TypeScript types in
  `packages/contracts/src/generated/contracts.ts` and Python types in
  `python/vera_timeline_agent/generated/contracts/`. Update every exhaustive
  repository consumer to recognize the new variants or reject unsupported
  graphic delivery explicitly. No accepted fixture, golden, or acceptance test
  is edited.
- No stored-document migration or revision rewrite occurs. Older documents
  without graphics omit the new fields and retain their prior compiler bytes.
  Existing package/report readers must continue to accept old v1 data.
- The pre-release v1 extension may break consumers that assume the old closed
  source/event union or that treat every event as placed media. Those consumers
  must be updated in this slice or fail with an explicit unsupported-graphic
  error before materialization. No automatic compatibility coercion is allowed.
- No new package dependency is proposed. The current schema generator, Ajv,
  Node crypto, and existing Python validation tools cover the work.

## Acceptance effect

After approval, issue #7 requires new slice-owned fictional documents,
dependencies, manifests, reports, and byte-identical compiler goldens covering
normal country/year, `otis` with no year, null overrides, explicit overrides,
and project badge identity. Negative tests cover unknown country, illegal
year, missing or stale revision, digest/hash mismatch, path or Fusion syntax,
short duration, and unresolved delivery. The tests must prove event-to-report
accounting and honest live versus placeholder/manual plans; baked remains a
typed future outcome with no Free renderer in #7.

Run the full repository validation, generated-type currentness check,
dependency audit, and frozen-boundary audit. Record exact commands/results and
hashes of the new goldens. Producer acceptance for #7 remains separate from
approval of this note: the final review checklist will let the producer
inspect the schema, representative manifest/report output, and explicit Free
manual outcome, then record `ACCEPT #7` or the failing step. No real Resolve
project or external data is changed in this slice.

## Producer decision requested

Approve this exact boundary, including nullable absent overrides, omission of
Year for `otis`, 64-frame fail-closed timing, editor-neutral manifest intent,
and `baked` as representable but unimplemented. Reply:

`APPROVE #7 CONTRACT — I approve docs/plans/issue-7-fusion-graphics-contract-change.md as the issue #7 schema, compatibility, generated-type, migration, and acceptance boundary.`

Or identify the section and replacement behavior to revise before code work.
