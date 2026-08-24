# Deterministic synthetic media kit

This directory owns the canonical Slice 0.1 media kit used by the
handcrafted-timeline work in Slice 0.2. It contains exactly:

- 3 short, video-only H.264 MP4 clips at 1920x1080 and 24000/1001 fps;
- 2 RGB PNG stills at 1920x1080; and
- 1 three-second stereo PCM WAV audio bed at 48 kHz.

Every image and sound is procedurally generated. The kit contains no
third-party media, downloaded source material, production media, people,
logos, fonts, or credentials. `fixture-kit.json` gives every item a stable ID
and role and records its provenance, byte size, SHA-256 digest, and relevant
FFprobe metadata.

The canonical settings implement producer decision D-0004 for this fixture
only. Frame rate, dimensions, and sample rate remain adjustable project/build
settings in the product; the validator does not define a product-wide
invariant.

## Verify

Run the fixture acceptance check from the repository root:

```sh
uv run --frozen python fixtures/validate_fixtures.py --require-ffprobe
```

The existing top-level command also collects the fixture tests through
pytest:

```sh
npm run validate
```

Without `--require-ffprobe`, the standalone checker still validates the
descriptor, exact inventory, sizes, and SHA-256 digests, but clearly reports
that metadata inspection was skipped if FFprobe is unavailable. Pytest follows
the same availability rule for its FFprobe-specific test. Producer acceptance
should use `--require-ffprobe`.

## Regenerate

The deterministic recipe is:

```sh
uv run --frozen python -m fixtures.generate_fixtures
uv run --frozen python fixtures/validate_fixtures.py --require-ffprobe
```

The generator stages all outputs before replacing the six declared fixture
files and refuses to run when undeclared files are present in `fixtures/media`.
It uses Python stdlib routines for PNG/WAV construction and single-threaded,
bit-exact-oriented FFmpeg settings for MP4 generation.

The checked-in bytes and hashes are authoritative. Canonical regeneration is
version-gated to FFmpeg and FFprobe 8.1.2 and also requires the same linked
libx264, FFmpeg build configuration, Python, and zlib behavior. A different
encoder or compression build may produce semantically identical media with
different container bytes, and the recipe intentionally does not claim
otherwise. Do not update checked-in hashes after such a run; changing
canonical fixture bytes after Slice 0.1 acceptance requires an approved
fixture-change note.
