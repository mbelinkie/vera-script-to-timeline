# Curated Fusion Graphics

> Live Slice 1.5 status and routing: [GitHub issue #3](https://github.com/mbelinkie/vera-script-to-timeline/issues/3). This plan retains detailed design and acceptance evidence.

**Sequencing approved by the producer on 26 August 2026 and recorded as
D-0015.** The authoritative roadmap placement is in the
[Phase 1 ladder](<../Script-to-Timeline Product Spec - Fable Rev2.md>).

## Summary and sequencing decision

Do **not** implement the complete Fusion-graphics feature before Slice 1.4.

Slice 1.3 is accepted and Slice 1.4 is active. The authoritative sequence is:

1. Complete and accept Slice 1.4 unchanged.
2. Run Slice 1.5, the bounded Fusion semantic-input capability spike.
3. Continue with Slice 1.6's basic Studio assembly.
4. Implement Slice 1.7's durable build jobs.
5. Build a real script through both delivery modes in Slice 1.8.
6. Productize curated Fusion graphics as separate contract, compiler, and
   Studio follow-ups.
7. Add the authoring form during Phase 2 before Slice 2.7.

This preserves the walking-skeleton milestone while testing Fusion parameter
mutation before the production Studio adapter becomes difficult to reshape.

## Proposed architecture

- VERA owns an immutable registry of curated Fusion template revisions.
- Each revision contains:
  - a hash-pinned `.drb` or equivalent Fusion asset;
  - a semantic field schema;
  - a trusted mapping from semantic fields to stable Fusion tool/input
    identifiers;
  - an expected graph fingerprint;
  - the validated Resolve version; and
  - default V4 placement and a minimum-duration policy.
- A graphic occurrence stores the pinned revision, typed values, narration
  anchor, duration policy, and resolved snapshot hash.
- The compiler emits a deterministic `fusion_graphic` event.
- The Studio adapter imports the asset, places it at the compiled range,
  populates its controls, and verifies the result after save/reopen.
- The first lower third exposes:
  - required primary text;
  - optional secondary text; and
  - accent color.
- User data supplies values only. It cannot inject scripts, expressions,
  Fusion tool names, or filesystem paths.
- Resolve Free initially receives a labeled placeholder and manual-completion
  item. A baked alpha-video fallback remains a separate later slice.

## Bounded work

### Slice 1.5 — Fusion semantic-input capability spike

Run after Slice 1.4 and before Slice 1.6.

- Use a producer-authored lower-third template and an internal test request;
  do not change shared contracts.
- Import and place it through the accepted pinned-template path.
- Discover the expected Fusion composition and controls through documented
  APIs.
- Set the three typed inputs, read them back, save, reopen, and verify again.
- Validate the animation visually at two durations.
- Record exact Resolve 21.0.4 behavior in `CAPABILITIES.md`.
- Add no dependencies and do not modify frozen fixtures or accepted tests.

### GF-1 — Explicit contract and compiler change

Run only after Slice 1.5 producer acceptance and basic Slice 1.6 acceptance.

- Add a producer-approved contract-change note.
- Extend `ScriptDocument v1` with a curated graphic-template source/use.
- Extend `TimelineManifest v1` with a `fusion_graphic` event.
- Extend `BuildReport v1` with live, placeholder, baked, and
  manual-completion outcomes.
- Regenerate TypeScript and Python types.
- Update exhaustive consumers while leaving existing canonical inputs
  byte-identical.
- Add new slice-owned graphic fixtures and deterministic compiler goldens.

### GF-2 — Studio graphic placement

- Package the pinned template and provenance with the verified build.
- Import it into a deterministic VERA template bin.
- Place the occurrence on the configured graphics track, normally V4.
- Resolve only the trusted semantic mapping from the pinned revision.
- Verify graph fingerprint, values, start, duration, track, template hash,
  and stable graphic-use identity after reopen.
- Fail visibly if any control or graph identity differs.
- Never overwrite an existing timeline.

### Phase 2 authoring integration

Place after Slice 2.4 and before Slice 2.7.

- Add a curated-template picker to visual-event cards.
- Generate the form from the template's semantic schema.
- Anchor the graphic to a selected narration range.
- Show inline validation, a compact data summary, template revision, and
  timing.
- Editing data creates a new document revision and subsequently a new
  generated timeline.
- Arbitrary custom templates and in-place Resolve updates remain excluded.

## Verification and producer acceptance

- Unit-test semantic types, required fields, color normalization, unknown
  fields, stale revisions, hashes, and minimum duration.
- Prove deterministic semantic snapshots, manifests, and build reports.
- Prove missing or renamed Fusion controls fail instead of targeting another
  control.
- Verify exact V4 placement and input persistence after save/reopen.
- Verify Free mode never invokes Resolve scripting or silently drops the
  graphic.
- Run focused tests, generated-type checks, full validation, dependency
  audit, and frozen-boundary audit.
- Producer acceptance:
  1. Enter lower-third data.
  2. Anchor it to narration.
  3. Build a new Studio timeline.
  4. Confirm the data and animation visually.
  5. Change one field and rebuild.
  6. Confirm the previous timeline remains unchanged and the new timeline
     contains the revision.

## Explicit exclusions

- No expansion of Slice 1.4 or its acceptance criteria.
- No arbitrary uploaded Fusion templates.
- No generated free-form Fusion node graphs.
- No in-place timeline rewriting before Regeneration Review.
- No baked Free fallback in the first graphics release.
- No agent-side installation into Resolve or mutation of real production
  projects.
