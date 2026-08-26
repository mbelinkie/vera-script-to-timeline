# Slice 1.3 contract-change note — compiler dependencies and timing precision

## Status and authorization gate

**Approved by the producer on 2026-08-26.** Slice 1.3 is
the first TypeScript consumer of the Python narration cache. Slice 1.2
deliberately kept `NarrationAudioAsset` internal and requires an explicit
contract-change note if a later slice needs cross-language serialization. That
condition is now met.

Approval of this note authorizes only the changes listed below. It does not
authorize edits to `ScriptDocument v1`, `BuildReport v1`, `/fixtures`, the
accepted Slice 1.1 script inputs, accepted Slice 0.2 data/tests, or unrelated
accepted tests.

## What changes

### 1. Add `CompilerDependencies v1`

Add `/contracts/compiler-dependencies-v1.schema.json` and generate matching
TypeScript and Python types. The schema is the smallest persistent boundary
needed by the pure compiler; it does not expose the full narration cache.

The top-level record contains:

- `schemaVersion: compiler-dependencies/v1`;
- deterministic build identity and settings: build, manifest, and report UUIDs;
  build class; rational frame rate; dimensions; audio sample rate; start frame;
- an adjustable track list plus explicit logical role bindings for presenter,
  unresolved placeholders, narration, and source audio;
- one narration dependency for every active narration block; and
- one resolved visual dependency for every ready local-media reference used by
  an active visual event.

A narration dependency contains only compiler-relevant verified facts:

- block ID/revision, asset identity, ready/failed status, text and audio hashes;
- project-relative audio locator, exact duration samples, sample rate, and
  channel count;
- timing-record version/hash, alignment version, declared source precision, and
  ordered word/sentence marks with millisecond starts and UTF-16 ranges; and
- a failure reason only when status is `failed`.

A resolved visual dependency is keyed by `mediaReferenceId` and contains:

- a schema-valid manifest still or video source with verified relative path,
  content hash, and media metadata;
- the verified video source start frame available to the occurrence; and
- when source audio is requested, a schema-valid companion audio source and
  source start frame.

The contract will reject duplicate dependency keys semantically in the
compiler because JSON Schema cannot express the required keyed uniqueness.

### 2. Widen `TimelineManifest v1` timing precision

Add these honest compiled precision values to
`TimelineManifestV1.$defs.TimingPrecision`:

- `word_start_with_derived_end`; and
- `sentence_start_with_derived_end`; and
- `unavailable`.

Existing values (`word`, `sentence`, `cue`, `frame`) remain valid. The manifest
schema version remains `timeline-manifest/v1`: this is an additive producer
capability during the pre-release Phase 1 contract-hardening period, and every
repository consumer and generated type is regenerated and retested together.
Consumers with exhaustive enum handling must add the three values.

The compiler will not map provider-internal `none` to a false semantic
precision. A narration asset with no usable alignment becomes a blocked
manifest/report with its duration-preserving audio and one whole-block timing
slate, while anchored picture events for that block are suppressed.
`unavailable` appears only on those narration audio/timing-slate events whose
placement duration is known but whose text alignment is not.

### 3. Regenerate shared types

Regenerate:

- `packages/contracts/src/generated/contracts.ts`; and
- `python/vera_timeline_agent/generated/contracts/*`.

The hard-coded `schemaFiles`/aggregate-required inventory in
`packages/contracts/scripts/generate-contracts.mjs`, generated Python
`__init__.py` exports, and the Ajv schema registry/test inventory will be
extended to include the new schema. Existing generated names may shift
mechanically when the deterministic generator includes the new file; generated
output is reviewed as part of this change.

## What does not change

- `ScriptDocument v1` structure or its accepted Slice 1.1 semantics.
- `BuildReport v1`. A narration `EventBuildResult` will use the block's stable
  event identity, exact frame range, and a deterministic message containing the
  quoted sentence/block text. Together with the manifest provenance, this
  satisfies the Slice 1.3 human trace without adding a second report structure.
- `TimelineManifest v1` event/source/track/transition/marker shapes other than
  the three additive precision enum values.
- `/fixtures`, accepted Slice 1.1 script files, accepted Slice 0.2 data/tests,
  or any existing golden.
- Slice 1.2 cache layout or immutable cache identity. A narrow adapter may map
  its verified record into `CompilerDependencies v1`; the cache record itself
  does not become the public contract.

## Why the change is necessary

The TypeScript compiler cannot derive audio paths, hashes, sample-accurate
durations, or speech timing from `ScriptDocument`. Those facts are produced by
the Python local agent and must cross a serialized boundary. Treating the
Python `asset.json` and `timing.json` formats as an undocumented TypeScript API
would freeze an accidental contract and violate the Slice 1.2 gate.

The accepted Polly timing record provides observed word starts and derives word
ends from the next word start or audio end. Mapping that evidence to the current
bare `word` enum would overstate what the provider supplied. The derived-end
manifest values preserve the distinction, while `unavailable` prevents a
failed audible placeholder from claiming text alignment it does not have.

## Compatibility and breakage

- Existing ScriptDocuments, manifests, reports, fixtures, and packages remain
  schema-valid.
- Existing manifest consumers that ignore or pass through timing precision are
  unaffected.
- Exhaustive TypeScript/Python consumers of `TimingPrecision` must handle the
  three new values; repository consumers will be updated in the same slice.
- `CompilerDependencies v1` is new and has no prior serialized consumers or
  migration burden.
- No provider call, cache rewrite, media copy, Resolve action, or real-world
  mutation is caused by this contract work.

## Acceptance impact

Approval adds these automated requirements to Slice 1.3:

1. positive and negative schema tests for every compiler-dependency variant;
2. byte-current generated TypeScript and Python types;
3. a Python-to-JSON-to-TypeScript fixture proving the narrow narration mapping;
4. output validation using all three new honest precision values;
5. frozen-boundary audits proving no change to excluded contracts/data/tests;
6. two consecutive byte-identical golden runs; and
7. the full repository validation gate twice plus two consecutive CI passes.

Producer acceptance remains the specification's small human check: read the
generated build report and trace one quoted narration sentence/block to its
integer frame range. No Resolve, cloud, listening, or visual-media action is
part of Slice 1.3 acceptance.

## Producer decision

The producer explicitly approved D-0014 on 2026-08-26. This authorizes creation of
`CompilerDependencies v1`, the three additive manifest precision values,
generated-type regeneration, and the acceptance changes above. Any further
shared-contract change discovered during implementation requires a new note.
