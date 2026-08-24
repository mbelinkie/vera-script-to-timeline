# Slice 0.1 Integration Review and Repair Plan

## Scope

- Independently review the integrated Slice 0.1 tooling, three JSON Schema
  contracts, generated TypeScript/Python models, deterministic fixture kit,
  tests, CI, and fresh-clone documentation as one production boundary.
- Correct the producer-identified D-P004 leak in `TimelineManifest v1`: track
  IDs become bounded opaque strings, track media kind remains an explicit
  discriminator, and every track kind uses an unbounded positive index.
- Remove the related five-layer ceiling from the Phase 1 authoring event and
  make timeline event/report track compatibility explicit with a structural
  `trackKind`, rather than deriving kind from an ID prefix.
- Encode D-0004's 24000/1001, 1920x1080, and 48 kHz values as representative
  JSON Schema defaults while proving that alternate positive settings remain
  valid.
- Repair only integration defects found while auditing fixture inventory,
  FFprobe-absence reporting, and the documented one-command validation path.
- Reproduce clean installs, generation/currentness, schema/type tests, fixture
  hash and FFprobe checks, offline post-bootstrap checks, top-level validation,
  lockfile stability, and a fresh-worktree bootstrap.

## Exclusions

- No compiler, semantic validator, OTIO/FCPXML writer, Resolve automation, UI,
  persistence, collaboration, or delivery-job implementation.
- No decision about the eventual D-P004 names or purposes. Section 9.2 names
  may appear only as representative sample/default labels.
- No changes to fixture media bytes, fixture hashes, or the descriptor's
  canonical D-0004 media settings.
- No edits to `DECISIONS.md`, `docs/IMPLEMENTATION_PROGRESS.md`, frozen
  producer decisions, archived specifications, or the authoritative spec.
- No new dependencies.

## Contract-change note

This is a producer-requested correction before Slice 0.1 acceptance, while the
initial contracts are still unfrozen.

- **What changes:** `TrackId` stops enumerating `V1`-`V5`, `A1`-`A5`, and
  `S1`; it becomes a non-empty opaque string with a finite length bound.
  `VideoTrack`, `AudioTrack`, and `SubtitleTrack` retain their `kind`
  discriminators and accept any positive `index`. Timeline events add a
  required kind discriminator for their target track; build-report event
  results carry the same structural evidence. The unrelated authoring
  `VisualEvent.layer` upper bound is removed. Timeline-setting properties gain
  representative D-0004 defaults, not `const` restrictions.
- **Why:** D-P004 is pending. Encoding section 9.2 example names and five-track
  ceilings as invariants silently decides that question and prevents valid
  alternate layouts. Event compatibility must remain visible after IDs become
  opaque.
- **What it breaks:** pre-acceptance sample manifests/reports and any early
  consumer prototype that omitted `trackKind` must be updated. Existing
  `V*`/`A*`/`S*` strings remain syntactically valid IDs, but no longer carry
  contract semantics. No accepted downstream slice exists yet.
- **Generated outputs:** regenerate
  `packages/contracts/src/generated/contracts.ts` and every module under
  `python/vera_timeline_agent/generated/contracts/` from the three schemas.
- **Acceptance impact:** schema tests must accept opaque IDs, indices above
  five (including subtitle indices above one), an authoring layer above five,
  and non-default timeline settings; they must reject an event whose declared
  target-track kind is incompatible. Generated-output byte-currentness remains
  mandatory.

## Fixture-code integration note

The six accepted candidate media files, descriptor, hashes, and metadata are
not changed. Verification code/tests may be tightened if an undeclared nested
media file can evade the exact-inventory promise or if absent FFprobe behavior
is not explicitly proven. Such a verifier-only repair does not redefine the
fixture contract or canonical bytes.

## Dependency justification

No dependency is added. Existing Node, JSON Schema, Python standard-library,
and FFmpeg/FFprobe tooling are sufficient.

## Automated checks

1. Contract tests cover opaque bounded IDs, structural track kinds, positive
   unbounded indices/layers, D-0004 defaults plus configurable alternatives,
   closed shapes, and resolved offline references.
2. Both generated language outputs regenerate byte-for-byte and pass strict
   TypeScript/Python checks.
3. Fixture tests reject undeclared media anywhere below `fixtures/media`,
   verify all sizes/hashes, verify metadata with FFprobe, and explicitly report
   skipped metadata (or fail under `--require-ffprobe`) when FFprobe is absent.
4. `npm ci`, `uv sync --frozen`, standalone fixture verification with
   `--require-ffprobe`, offline post-bootstrap generated-currentness, and the
   pinned-Node `npm run validate` all pass without lockfile changes.
5. The same bootstrap and validation succeed in a fresh detached worktree,
   demonstrating that ignored local state is not required.

## Producer acceptance

1. Check out the integration commit on the pinned Node/npm, Python/uv, and
   FFmpeg/FFprobe toolchain documented in `README.md`.
2. Run `npm ci` and `uv sync --frozen`; confirm neither lockfile changes.
3. Run `npm run generate:contracts`, then
   `npm run check:contracts-generated`; confirm both generated language trees
   are byte-current.
4. Run
   `uv run --frozen python fixtures/validate_fixtures.py --require-ffprobe` and
   confirm exactly three clips, two stills, one audio bed, all hashes, and all
   metadata verify.
5. Run `npm run validate`; confirm schema/currentness, TypeScript, Python, and
   fixture checks all pass and CI uses this same command.
6. Inspect `TimelineManifest v1` and its generated types: track IDs are opaque
   and bounded, media kind is structural, indices have no maximum, and the
   section 9.2 labels are examples rather than required names.
7. Inspect `TimelineSettings`: the D-0004 values are defaults, and the test
   suite accepts explicit alternate rate, dimensions, and sample rate.

Producer execution of this checklist remains authoritative; this review does
not close Slice 0.1 by self-report.
