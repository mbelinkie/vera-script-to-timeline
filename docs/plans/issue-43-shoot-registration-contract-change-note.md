# Issue 43 contract-change note — immutable shoot-session registration

## Approval and bounded change

The Producer authorized this note on 2026-09-09. This is the only approved
shared-contract boundary for issue #43. It adds an additive
`shoot-registration/v1` project record and generated TypeScript/Python types.
It does not alter `script-document/v1`, `prompter-export/v1`, compiler output,
or an existing fixture or golden.

## Proposed record

`ShootRegistrationProjectV1` contains a project ID; a `mediaLibrary` strategy;
sessions; and their sources. A session has a stable UUID, name, frozen
`PrompterExportReference` (canonical sidecar SHA-256 plus the sidecar's source
document reference and beat-map SHA-256), processing-profile version, and
sources. A source has a stable UUID, its immutable `sha256:` media hash, byte
size, inspection evidence (container/streams, duration, frame rate, timecode,
resolution, color metadata, and audio layout), a safe display name,
root-relative locator/provenance, authorization, status, and append-only
relink evidence.

`mediaLibrary` is either `{ kind: "project_local", libraryId }` or
`{ kind: "unconfigured" }`. `unconfigured` means VERA has no authorized
project-local root: records retain identity and inspection evidence but offer
no retrievable master to a job until an authorized root is configured and a
hash-verified scan relinks it. The local mapping from `libraryId` to an
absolute root is not part of this contract or any handoff inventory. Schema
validation rejects absolute paths, traversal, empty path segments, control
characters, and unsafe display names wherever a locator or display name is
serialized. A source hash, not its filename, path, timecode, or session
position, is its identity.

`LocalSourceHandoffInventoryV1` is a separate non-media JSON artifact. It
includes the project/session/source identities, hash, byte size, inspection
facts, safe display name, and optional root-relative locator evidence needed
to recognize an authorized byte-identical copy. It contains no absolute root,
media bytes, transferable credential, or cloud locator.

## Compatibility, generated types, and migration

- This is a new, additive v1 artifact; existing project documents and all
  accepted contracts remain valid and byte-identical.
- Add the schema to the contract generator's TypeScript aggregate and Python
  exports, then regenerate both checked-in outputs.
- No stored-data migration is required because there is no prior shoot-session
  record. Future persistence can introduce a migration only if it adopts an
  older experimental format, which this issue will not create.
- The registration API keeps absolute roots and resolved local paths in a
  local-only configuration/runtime object. It accepts a future job capability
  only when its project and source match; it never serializes that capability.

## Acceptance impact

The contract adds focused deterministic tests for serialization safety,
idempotent registration, incomplete/corrupt/unsupported inspection rejection,
hash-verified relink, wrong-byte refusal, handoff-inventory sanitization, and
job scoping. `npm run validate` remains the full acceptance command. No source
master is uploaded, copied, moved, renamed, transcoded, relabeled, or deleted
by the implementation.
