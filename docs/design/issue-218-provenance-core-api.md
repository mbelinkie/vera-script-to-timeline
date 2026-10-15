# #218 — pure graphic provenance API and owner handoff

Authority: CN-166-P1 at `0c50a30a4e78fd771b51ee6732e78641ceb3da7b`,
plus the two CN-218-A1 guards approved at `1a7cb50`. This API implements the
accepted EV24 semantic shape only. No production writer or renderer is enabled.

## Injected records and operations

`packages/contracts/src/graphic-provenance.ts` exports:

| Operation | Inputs and result |
| --- | --- |
| `resolveRetainedGraphicRevision(address, records)` | Exact project/graphic/revision address and already authorized retained records → explicit legacy/manual/derived result, verified content/snapshot and method availability, or a blocking diagnostic. Missing/unknown records never become legacy. |
| `createGraphicContent(input, records)` | Caller-selected new IDs, exact template pin, resolved semantic values, explicit manual/derived declaration and actor/time → a proposed immutable content revision plus separate audit receipt. |
| `repeatGraphicContent(input, records)` | Existing exact address and actor/time → same frozen content, values, pins, S and P after retained-byte verification. No upstream access or freshness claim. |
| `refreshGraphicContent(input, records)` | Existing derived address, new revision ID, supplied new source evidence/derivation/resolved values → proposed revision, preserving the template pin. |
| `migrateGraphicTemplate(input, records)` | Existing address, new revision ID and explicitly selected compatible template pin/semantic snapshot → proposed revision, preserving source evidence/derivation. No field or badge mapping is guessed. |

Every operation returns `{ok:true,value}` or `{ok:false,block:{code,message}}`.
Proposals include `content`, canonical `contentHash`, `snapshot`/`provenanceHash`
(null for manual), `methodAvailable`, and `receipt`. Returned JSON is deeply
frozen and caller inputs/older revisions are not modified.

`GraphicProvenanceRetainedRecords` is an injected inventory: `revisions`,
`snapshots`, `sources`, `badges`, `methods`, and `templates`. It is not a storage
implementation. Revision wrappers explicitly distinguish `legacy` (identity,
exact retained bytes and byte hash) from `graphic-content/v1` (closed generated
content shape and its advertised canonical hash). Sources/methods/badges retain
their exact bytes, project and durable identities. Templates supply the exact
project revision, package and a trusted compatibility decision. The resolver
recomputes #20's package digest and verifies every declared file length/hash,
entry bytes and selected badge bytes. It grants no project access or rights.

## Synthetic source-backed example

The caller first authorizes and supplies an approved retained template package
in `records.templates`, and its exact `template` pin. Then these pure operations
can propose fictional content (all UUIDs/data below are synthetic):

```ts
const projectId = "21800000-0000-4000-8000-000000000001";
const artifactId = "21800000-0000-4000-8000-000000000002";
const bytes = new TextEncoder().encode('{"east":18,"west":27,"unit":"observations"}\n');
const contentHash = sha256Bytes(bytes); // hash these exact bytes, without parsing
const source = {
  sourceKey: "tally",
  citation: { title: "Demo station tally", publisher: "Fictional Lab",
    originalLocator: "https://example.invalid/tally", versionLabel: "demo-v1" },
  snapshot: { artifactId, contentHash, mediaType: "application/json" },
};
const proposed = createGraphicContent({
  projectId,
  graphicId: "21800000-0000-4000-8000-000000000003",
  revisionId: "21800000-0000-4000-8000-000000000004",
  template,
  semanticSnapshot: { values: { country: "otis", topLineOverride: "Demo total",
    bottomLineOverride: "45 observations", badgeOverrideAssetId: null }, badgeAsset: null },
  content: { kind: "derived", sources: [source], derivation: {
    mode: "manual", version: "1", method: null, parameters: {},
    note: "Source tally: east 18 + west 27 = 45 observations; set bottomLineOverride; topLineOverride is Demo total; country otis is presentation only; no rounding or exclusions",
  } },
  actorId: "synthetic-author", recordedAt: "2026-10-15T12:00:00Z",
}, { ...records, sources: [...records.sources,
  { projectId, artifactId, contentHash, mediaType: "application/json", bytes }] });
```

Imports are `createGraphicContent` from the module above and `sha256Bytes` from
`template-library.ts`. No code fetches that URL or calculates a result from a
supplied method. The example deliberately supplies the reviewed value 45.
The runnable synthetic create/repeat/refresh/migration examples and refusal
matrix are in `packages/contracts/test/issue-218-provenance.test.ts`.

## Compiler mapping and hash boundaries

v1 copies the validated explicit authored binding to the Fusion graphic event
and report. Omitted v1 binding retains legacy output; a new writer that strips
it cannot be detected from that legacy-compatible wire shape alone.

For v2, the trusted caller sets `graphicContentClass` on each graphic occurrence
resolution. Manual/derived classes require the exact matching
`resolvedGraphicContents` record; derived also requires
`graphicContentBinding:{graphicId,revisionId,provenanceHash}` on the materialized
media resolution and its addressed snapshot. The compiler propagates P into
`EventProvenanceV2.graphicProvenanceHash` across visual-only, primary and overlay
events. Every original media hash and event/use identity remains independent.
Build inventories reject duplicates/unused content and snapshots. A trusted
resolver deliberately lying about legacy format remains an upstream integrity
failure; the compiler cannot infer rendered labels from a file hash.

S remains #7's canonical hash of `{values,badgeAsset}`. P hashes the whole
sorted-source provenance snapshot using #7's canonical serializer (sorted
object keys, preserved array order/nulls/string bytes, two spaces, newline,
UTF-8). Source/method bytes use raw SHA-256. #20 package/use/copy hash meanings
remain unchanged. Audit actor/time/operation and mutable locators stay outside
P. Deterministic method identity is retained, never executable supplied code;
missing method bytes permit frozen repeat with `methodAvailable:false`, while
an operation needing that method blocks. Missing source/template bytes block.

## Storage, rollout and later owners

#64 must authorize every lookup, retain immutable records/bytes, protect all
use/checkpoint/build references from pruning, and atomically publish/select a
proposal with its receipt. It must enforce new-writer declarations, refuse
stripped pointers and distinguish known legacy storage format from unknown
records. This API does not allocate persistent IDs, commit, select, prune or
rewrite data. Failed proposals leave the selected revision unchanged.

Deploy compatible readers/resolvers before enabling writers. Old closed-schema
readers reject new fields; downgrade/export must refuse if provenance cannot
be preserved and verified. Legacy v2 graphic dependencies need an explicit
verified legacy classification; classification remains in the existing complete
dependency hash. Migrated manifests stay byte-identical; reports change their
dependency hash. Original fixture/golden evidence remains retained.

The current v1 adapters already refuse Fusion graphics. The v2 package adapter
now explicitly refuses new-format graphic content/pointers until its own
evidence inventory and cross-language JSON numeric hashing are implemented.
Pure compiler success is not evidence-export permission or runtime acceptance.
No provenance source/method bytes are silently omitted from a claimed package.

#9/#67/#69 own declaration, evidence-summary, citation and explicit refresh/
migration UI. #8 (paused) owns Studio placement/save/reopen proof; #10 owns
truthful Free fallback. Neither is implemented or contacted here. #99 supplies
approved compatible registrations; #167/#220 own cue design/runtime. No new
template, source acquisition, provider call or native application operation
is part of this core. Later consumers must integrate this exact accepted
source explicitly; if #8 lands the same foundations separately, reconcile the
identical deltas and rerun integration checks before use.
