# Slice 0.2 — Handcrafted manifest to OTIO package

## Bounded scope

Implement a Python contract consumer that turns one schema-valid handcrafted
`TimelineManifest v1` into a deterministic, self-contained OTIO import
package. The reusable API and CLI will:

1. validate the manifest schema and the cross-record/path/range facts needed
   for safe OTIO materialization;
2. write the canonical manifest, one `.otio` timeline, a schema-valid build
   report, human-readable import instructions, and copied media addressed by
   project-relative paths;
3. hash-verify copied media and parse-verify OTIO events, track metadata,
   markers, and the absence of unintended transitions before publishing the
   output directory; and
4. expose one documented producer command over Slice 0.2 test data outside
   the frozen fixture tree.

The handcrafted manifest uses the adjustable D-0005 default map and the
accepted synthetic media. Track IDs, names, indices, kinds, and counts are
read from the manifest and are not converter constants. The accepted ambient
WAV is explicitly described as synthetic test narration in the report and
instructions.

## Explicit exclusions

- Script-to-manifest compilation, anchor resolution, voice generation, and
  semantic authoring validation.
- FCPXML, Resolve Free capability claims, Resolve Studio scripting, Fusion,
  rendering, or uploads.
- UI, jobs, persistence, collaboration, and later-phase package layouts.
- Any edit under `/contracts`, generated contract outputs, or `/fixtures`.

## Contracts and fixtures

This slice consumes the producer-accepted `TimelineManifest v1` and
`BuildReport v1` contracts without changing them. Handcrafted manifest data
lives under `tests/data/slice_0_2/`. The package writer reads but never edits
the frozen bytes under `fixtures/media/`.

## Dependencies

- `opentimelineio==0.18.1`: the exact-pinned official OTIO object model and
  JSON adapter are required to write and parse the interoperability artifact.
- `jsonschema==4.25.1`: exact-pinned Draft 2020-12 runtime validation ensures
  the Python boundary consumes and emits the accepted schemas rather than
  relying on static generated `TypedDict` hints.

## Automated checks

- Validate the handcrafted input and emitted report against the frozen
  schemas, including referenced schemas and UUID formats.
- Parse the emitted OTIO and compare every manifest event's record range,
  source range, source kind, track, and relative media locator.
- Compare manifest track order, IDs, names, indices, and kinds to OTIO
  metadata; separately prove an adjusted track map works.
- Verify marker frame/name/note/color, hard-cut boundaries, and that no OTIO
  transition object was introduced.
- Verify exact package inventory, canonical manifest bytes, copied-media
  SHA-256 values, report completeness, and deterministic output bytes where
  practical.
- Exercise actionable failures for invalid schemas, unsafe/missing/corrupt
  media, incompatible tracks, overlapping/out-of-bounds record ranges, and
  invalid source ranges.
- Exercise the producer CLI and run Ruff, strict mypy, pytest, generated-type
  currentness, fixture verification, and the top-level `npm run validate`.

## Producer acceptance

From a locked install, run the documented command in the repository README.
Open the generated folder, read `IMPORT_INSTRUCTIONS.md`, inspect
`build-report.json` and `timeline-manifest.json`, and confirm the listed five
events and one marker. Slice 0.3—not this slice—records the actual Resolve Free
import result. Producer observation remains authoritative and this plan does
not mark the slice accepted.
