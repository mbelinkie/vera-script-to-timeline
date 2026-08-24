# Slice 0.1 Contracts Workstream Plan

## Scope

- Add first-draft JSON Schema Draft 2020-12 contracts for
  `ScriptDocument v1`, `TimelineManifest v1`, and `BuildReport v1`.
- Keep the contracts bounded to Phase 0/Phase 1 canonical semantics: stable
  identities, canonical narration/token anchors and OC/VO spans,
  still/local-video/placeholder visual events, integer-frame timeline
  placements, hard cuts, markers, provenance, and traceable build outcomes.
- Use the JSON Schemas as the single source of truth and reproducibly generate
  checked-in TypeScript types and Python `TypedDict` models from them.
- Add schema meta-validation, positive and negative instance validation,
  generated-model smoke checks, and generated-output currentness checks.
- Extend the top-level `npm run validate` ratchet and document the generation
  and validation commands.

## Exclusions

- No compiler or Phase 1 semantic validator. Cross-range rules such as full
  OC/VO token coverage, VO visual coverage, anchor resolution, and source
  handle sufficiency remain Slice 1.1 and later work.
- No OTIO/FCPXML writer, Resolve integration, package writer, UI, persistence,
  collaboration, media acquisition, provider adapter, or durable job behavior.
- No fixtures, fixture media, golden files, or research-project data.
- No later-phase clip, subtitle, webpage-capture, template/music, shoot,
  conform, or regeneration-review models.
- No changes to `docs/IMPLEMENTATION_PROGRESS.md`, `DECISIONS.md`, or
  `CAPABILITIES.md`.

## Contract creation note

This workstream is the producer-authorized initial creation of `/contracts`
for Slice 0.1, not a change to an accepted/frozen contract. It adds the three
contracts named by the authoritative specification. Generated TypeScript and
Python outputs are derived artifacts and must be regenerated whenever an
authorized schema change occurs. Producer acceptance of Slice 0.1 freezes
these contracts between later slices under section 12's contract-change rule.

The schemas enforce structural and local scalar constraints only. Assertions
that require comparing arrays, resolving token IDs, checking complete range
coverage, or matching source duration against placements intentionally do not
appear as misleading JSON Schema guarantees; those belong to the Slice 1.1
semantic validator.

## Owned files

- Contracts: `contracts/*.schema.json`.
- TypeScript package and generated outputs: `packages/contracts/**`.
- Python generated outputs: `python/vera_timeline_agent/generated/**`.
- Contract tests and test data: `packages/contracts/test/**` and
  `tests/test_generated_contracts.py`.
- Root integration/docs: `package.json`, `package-lock.json`, `pyproject.toml`,
  `uv.lock`, and `README.md`.
- This plan.

No `/fixtures` files are touched.

## Dependency justifications

- `ajv` and `ajv-formats` provide standards-compliant JSON Schema Draft
  2020-12 validation, format checks, and explicit cross-schema reference
  resolution in the TypeScript test suite.
- `json-schema-to-typescript` reproducibly derives usable TypeScript types
  directly from the schemas rather than maintaining handwritten copies.
- `datamodel-code-generator` reproducibly derives Python 3.12 `TypedDict`
  models directly from the same schemas without adding a product runtime
  validation framework.

All versions are exactly pinned in the applicable lockfile.

## Automated checks

1. All three schemas validate against their declared Draft 2020-12
   metaschema and compile together with every external `$ref` resolved.
2. A representative valid document, manifest, and report are accepted.
3. Focused negative cases are rejected, including unknown properties,
   malformed identities/hashes, invalid discriminators, non-positive event
   durations, invalid track/source pairings, and unresolved cross-schema
   references.
4. Checked-in TypeScript and Python generated models import and typecheck in
   their normal language checks.
5. `npm run check:contracts-generated` regenerates into a temporary directory
   and byte-compares every expected generated file, failing on stale, missing,
   or unexpected output.
6. `npm run validate` runs generated-output currentness before the existing
   TypeScript and Python lint, typecheck, and test checks.
7. `npm ci` and `uv sync --frozen` accept the updated lockfiles from a clean
   dependency state.

## Producer acceptance portion

1. From a fresh clone, install the pinned runtimes and run `npm ci` plus
   `uv sync --frozen`.
2. Run `npm run generate:contracts`; confirm it deterministically recreates
   the checked-in TypeScript and Python outputs.
3. Run `npm run validate`; confirm schema validation, generated currentness,
   and both language toolchains pass.
4. Add a harmless line to one generated file and rerun
   `npm run check:contracts-generated`; confirm it reports the stale file.
5. Run `npm run generate:contracts` to restore it, then rerun
   `npm run validate`.
6. Review the positive samples and focused negative cases to confirm the
   first-draft contracts represent the requested Phase 0/1 boundary.

Producer acceptance remains authoritative for closing Slice 0.1.
