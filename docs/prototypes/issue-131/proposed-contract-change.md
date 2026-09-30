# Proposed reconciliation contract change — NOT approved or implemented

This note completes #131's impact audit. It does not amend any contract,
accepted design, fixture, golden, generated type or migration. Producer
approval and a separately Ready bounded issue are required before coding.

## What would change, and why

Prefer additive, versioned reconciliation records outside the frozen v1
compiler input. Do not stuff opaque Resolve metadata into `VisualEvent` or
weaken `additionalProperties:false` to accept unknown state.

| Proposed boundary | Required facts / reason | Compatibility consequence |
|---|---|---|
| Immutable baseline and observation records | Script head/hash, applied build/manifest hash, project/timeline identity, product/version/time base, bounded coverage, capabilities, source hashes and raw observation references. Observations distinguish unavailable, unbounded, stale, changed and verified; they never assert editorial equivalence from matching positions. | New versioned schemas/persistence; old v1 packages remain immutable and readable. Legacy packages are **unlinked/unverified**, not automatically trustworthy baselines. |
| Identity/lineage and appearance registry | Separate authored row/token/event/slot, logical item, asset bytes, Resolve occurrence and observation IDs. Explicit many-to-many row/token lineage and item appearances; unique binding evidence and ambiguity. Preserve interruption intervals. No filename/quote identity fallback. | New sidecar relation; no reinterpretation of a manifest event ID as a Resolve UID. Duplicate/copy creates distinct appearances, not new source bytes. Ambiguous legacy binding requires review. |
| Dormant/preserved item registry | Logical identity, availability, former anchor/range, source edit/time base, fixed duration, original timeline reference, linked appearance/audio and opaque/effect evidence. Dormant ranges never count as active coverage. Unknown/unreadable effects remain opaque and protected. | Requires durable authoring/preservation state, not ad-hoc client memory. Keep original timeline and evidence; do not flatten unknown items into compilable v1 events. Extras alone are not a complete migration target. |
| Verified audio/visibility evidence | Program coverage and routing, token-to-source interval provenance/precision, piecewise source→record map and residual-word/unknown states. Distinguish derived ends from verified sample intervals; exact A/V boundaries and visibility facts cannot be inferred from track layout. | Current `word_start_with_derived_end` stays valid for its existing compilation purpose. It must not be relabeled “verified deletion evidence.” Add a distinct evidence version; no backfilled sample-exact precision. |
| Durable review record | Baseline, Script and observation revision hashes; stable group IDs; evidence/classification, one group decision if finally approved, unresolved/deferred state, pending correction, scope and optimistic-concurrency token. | Separate inbound decision from outbound selection/result. New source revision invalidates applicability, not historical decisions/evidence. Defer never means resolved; Keep Script never means Resolve changed. |

These are required information boundaries, not five mandated services/classes
or a final schema layout. One additive evidence bundle plus a durable review
record may suffice; settle storage/retention and minimum trusted observations
before defining schemas. Retain references to originals rather than inventing
complete effect serialization where the API cannot expose it.

### Authoring/manifest changes only if separately adopted

Current `TextAnchorRange` has one `blockId`; strict `VisualEvent` has one range
and null timing overrides. A general linked/spanning visual cannot be encoded
by pretending its two endpoints belong to the same row. A visual-only row in
the audited v1 still targets narration. Independently timed preserved visuals,
document-wide beds, cross-row segments and merge/split relationships require
either an approved companion authoring model or `script-document/v2` with
explicit discriminated anchor forms, not permissive optional fields.

If those authoring forms are adopted, specify logical event versus occurrence
IDs, segment order, token affinities, ownership, heading restrictions, fixed
source duration and duration-driven endpoints with **no fabricated out-word**.
Audit already accepted #55/#56 decisions and future #89/#100 instead of
creating a competing authoring proposal. I01 remains blocked even if a registry
can display linked appearances. Inbound row split/section-marker edits are
not unlocked by schema expressiveness.

Likewise, a future compiler/manifest version may need multiple record/source
segments and preserved-event references. This must not change v1 compiler
bytes. Regrouping rows requires valid new narration dependencies under today's
block ID/revision/text-hash contract; preserving cut audio needs an explicit
approved audio-edit representation, not automatic TTS regeneration.

## What breaks / does not break

- **No breaking change now.** Strict v1 readers reject sidecar fields added
  directly to a document; #131 demonstrates that failure and leaves it intact.
- Additive records can coexist with old packages, but old consumers must not
  silently apply a partially understood reconciliation plan. Capability/version
  negotiation must reject unsupported operations before any write.
- Adopting a v2 document/manifest later is breaking for v1 validators/compiler
  consumers. Name affected local agent, package writer, importer, authoring,
  history and review consumers in that implementation plan; either retain a
  validated v1 projection for supported operations or block export.
- Do not map one old row/event onto one new object when lineage is many-to-many.
  Do not carry stale TTS dependencies across a changed block/text revision.
- Original timelines, source media, build packages and accepted design artifacts
  remain immutable. A proposed review record is not permission to delete them.

## Migration and persistence policy

1. Write new immutable evidence records with schema version and content hash;
   retain original v1 bytes/references. Never modify historical packages in place.
2. For legacy timelines, record only observed facts. Absent item-binding data,
   incomplete routing or unknown effects produces unverified/opaque state.
   Producer review cannot manufacture missing technical evidence.
3. Derive row/token lineage only from explicit authoring operations with retained
   before/after IDs and offsets; a text search is a proposal, never identity.
4. Preserve dormant/preserved metadata before applying a reviewed operation.
   Restore requires fresh availability, anchor and collision validation.
5. Persist group decisions with all three source revisions and unresolved
   evidence. Use an atomic compare-and-swap (reject a write if the reviewed
   revisions changed) at application time. Carry deferred work forward without
   treating old choices as automatically applicable to changed observations.
6. Baseline advancement occurs only after the separately specified verified
   apply workflow. Failed, blocked, skipped or deferred work does not disappear
   or become “current.” Keep-Script queued corrections remain outstanding.
7. Rollback is opening the retained old head/timeline and abandoning the new
   proposed record/plan through audited flows. No destructive cleanup migration.

Retention, privacy/redaction, operation identity after copies, unknown-field
handling, crash recovery and storage location need explicit bounded decisions
before schema approval. JSON roundtrip in #131 is not a persistence guarantee.

## Generated types and fixture implications

If approved, add selected schemas to
`packages/contracts/scripts/generate-contracts.mjs` and its aggregate surface.
Regenerate via `npm run generate:contracts`, reviewing changes in
`packages/contracts/src/generated/contracts.ts` and
`python/vera_timeline_agent/generated/contracts/`. No hand-edited generated
types; additive outputs must not silently replace old types or version tags.

Create **new versioned** synthetic/Resolve-observation fixtures only after an
explicit Producer-approved fixture-change note. Keep current minimal/torture
compiler inputs and golden bytes as v1 regressions. Define new goldens for new
compiler versions separately; do not update old goldens to hide compatibility
loss. Real observation fixtures must be version-stamped, redact private paths,
and distinguish observed facts from expected editorial interpretation.

## Changed acceptance requirements

- Schema/semantic validators reject duplicate identities, dangling lineage,
  cross-row misuse, active dormant coverage, invalid source/record time bases,
  stale decisions and precision/coverage claims unsupported by evidence.
- New persistence tests cover serialization, actual reload/recovery, concurrent
  source edits, atomic stale-write rejection and deferred resurfacing. Snapshot
  bytes and old state remain unchanged on every refusal.
- External R1–R5 observations from the feasibility report establish the exact
  version/operation capability matrix. Unsupported operations stay visible and
  retain originals; API signatures and synthetic flags are not acceptance.
- New audio tests distinguish whole-word versus subword residuals, linked versus
  picture-only cuts, second audible tracks, retimes and incomplete observations.
- Preservation tests retain dormant assets/former ranges and manual/opaque
  effects, source duration, links and identities. Fit/collision/missing-byte
  failure leaves source state intact.
- Paired #139 Producer review settles decision grouping, scenario retirements,
  heading restrictions and precise user-facing blocked consequences before
  implementation is promoted. Existing frozen regressions and full validation
  must still pass. Production apply/render/retry acceptance belongs to its own
  issue, not this change note.

Existing future #101–#104 cover production observation, classification, review
and regeneration. This note is evidence for their later refinement, not a
parallel implementation queue or permission to dispatch them.
