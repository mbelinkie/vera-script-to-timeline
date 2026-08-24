# Slice 0.1 Fixtures Workstream Plan

## Scope

- Create one compact canonical synthetic media kit under `/fixtures` containing
  exactly three short video clips, two still images, and one audio bed.
- Give every asset a stable fixture ID, a unique intended test role, explicit
  synthetic provenance, a SHA-256 digest, a byte size, and inspectable media
  expectations.
- Use the producer-approved D-0004 defaults for the canonical kit: 24000/1001
  fps, 1920x1080 pixels, and 48 kHz audio. These are fixture generation
  parameters, not product or project invariants.
- Own the descriptor format, strict descriptor validation, deterministic
  generation recipe, verification command, and tests entirely within the
  fixture workstream.
- Make pytest verify the descriptor, exact inventory, hashes, sizes, and
  FFprobe metadata when FFprobe is installed. The existing top-level
  `npm run validate` already invokes pytest, so no package-script change is
  needed.

## Exclusions

- No changes to `/contracts`, generated contract types, `DECISIONS.md`,
  `CAPABILITIES.md`, `docs/IMPLEMENTATION_PROGRESS.md`, or accepted tests.
- No compiler, OTIO, FCPXML, Resolve, local-agent product, or UI behavior.
- No real production media, downloaded media, credentials, uploads, or
  changes to external data.
- No promise that alternate project settings or different encoder builds
  produce hash-equivalent media.

## Owned files and fixture-change note

- `/fixtures/**`
- `/tests/test_fixtures.py` and `/tests/conftest.py` (repository-root import setup)
- `/docs/plans/slice-0.1-fixtures.md`

This is the producer-authorized initial creation of the Slice 0.1 fixture
surface. It does not modify a previously accepted fixture or golden file.
After Slice 0.1 producer acceptance, the checked-in bytes, descriptor, and
hashes become frozen under the repository fixture-change policy.

## Descriptor and generation requirements

- The descriptor has a versioned, closed shape: unknown or missing fields are
  errors, IDs/roles/paths are unique, paths must remain below `fixtures/media`,
  and the kind inventory is exact.
- SHA-256 identifies the checked-in bytes; paths remain locators.
- Generation uses only Python's standard library plus FFmpeg. PNG and WAV
  bytes are emitted directly by deterministic integer/stdlib routines. MP4
  clips are single-threaded, synthetic FFmpeg filter/encoder outputs with
  metadata stripped or fixed.
- Canonical MP4 byte reproduction requires FFmpeg/FFprobe 8.1.2 and the same
  linked libx264/build configuration used to create the checked-in kit. The
  generator rejects another tool version. Even with the same FFmpeg version, a
  different linked codec build may differ; checked-in hashes are authoritative.
  FFprobe metadata verification intentionally checks media semantics rather
  than tool-banner text.

## Dependency justification

No dependency is added. Python stdlib supplies JSON, hashing, PNG/WAV writing,
and subprocess handling; installed FFmpeg/FFprobe supply video generation and
media inspection.

## Automated checks

1. Strict descriptor validation rejects missing/unknown fields and malformed
   identities, provenance, hashes, settings, paths, and media expectations.
2. The descriptor and `fixtures/media` both contain exactly three videos, two
   stills, and one audio file, with no undeclared media.
3. Every checked-in byte size and SHA-256 digest matches the descriptor.
4. FFprobe, when available, confirms stream count/type, codec, dimensions,
   rational frame rate/frame count, duration, pixel/sample format, channel
   layout, and 48 kHz sample rate as relevant to each kind.
5. The standalone verifier succeeds with `--require-ffprobe` on the acceptance
   toolchain, and all tests are collected by the existing pytest invocation.

## Producer acceptance

From a fresh clone with the repository's pinned Node/Python prerequisites and
FFmpeg/FFprobe installed:

1. Run `uv run --frozen python fixtures/validate_fixtures.py --require-ffprobe`.
2. Confirm it reports exactly 3 video clips, 2 stills, and 1 audio bed.
3. Open `fixtures/fixture-kit.json` and confirm all six items say they are
   procedurally generated and contain no third-party or production media.
4. Run `npm run validate` and confirm the fixture tests run within pytest and
   the complete repository validation passes.

Producer execution of this checklist is authoritative; an agent report does
not close Slice 0.1.
