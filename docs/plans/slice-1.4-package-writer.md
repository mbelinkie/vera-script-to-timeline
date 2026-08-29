# Slice 1.4 — Package writer and verification plan

> Live status and routing: [GitHub issue #2](https://github.com/mbelinkie/vera-script-to-timeline/issues/2). This plan retains detailed design and acceptance evidence.

## Status and gate

**In progress.** Slice 1.3 is producer-accepted at `fdb026e`; its compiler
dependency inputs and manifest/report goldens are frozen. Slice 1.4 starts
from that accepted local `main`, not the stale `origin/main` ref.

This is a mixed automated/manual slice. Automated implementation and package
verification may reach agent-complete, but only the producer's Resolve Free
import, playback, and checklist comparison can close the slice.

## Bounded scope

1. Add a Python production package API and CLI that consume an already-compiled
   `TimelineManifest v1`, its matching `BuildReport v1`, and an explicit
   slice-owned source map from manifest source IDs to resolved origin files.
   This keeps cache/research origin locators separate from immutable
   project-relative manifest destinations. Voice generation and script
   compilation remain upstream.
2. Reject `blocked` or `failed` compiler reports, report/manifest identity or
   hash mismatches, incomplete event results, unsafe locators, unavailable or
   corrupt media, and unsupported timeline semantics before publishing a
   `ready_to_import` build.
3. Materialize non-placeholder media into the section 8.2 project layout,
   preferring a filesystem copy-on-write clone when supported and otherwise
   making an independent copy. Verify content hashes after materialization;
   never move or hard-link canonical input.
4. Render each manifest placeholder into a deterministic, visibly labeled
   package-local PNG slate at the timeline dimensions, place it as a still in
   OTIO for the exact record range, and retain the original placeholder
   identity, reason, timing, and provenance as OTIO metadata.
5. Publish the verified project layout atomically for the bounded one-build
   workflow:

   ```text
   Authoring Project/
     Media/
       Narration/...
       Resolved/...
       Placeholders/<source-id>.png
     Builds/<build-id>/
       timeline-manifest.json
       build-report.json
       timeline.otio
       IMPORT_INSTRUCTIONS.md
       package-verification.json
   ```

6. Preserve the compiler report byte-for-byte, including its issues and exact
   manual-completion list. Write a slice-owned verification receipt with
   `ready_to_import`, hashes, rate/duration/sample-rate facts, materialization
   modes and locators, and the manual-item IDs proven by verification.
7. Verify project/build structure, containment, regular-file independence,
   manifest/report canonical serialization and hashes, media hashes, FFprobe
   parseability and declared stream/rate/duration compatibility, placeholder
   slate identity, timeline rate and total duration, every parsed OTIO event,
   tracks, hard cuts, and markers before publishing or reusing a result.
8. Produce one retained Resolve Free acceptance project/package plus exact
   producer import and observation steps.

## Explicit exclusions

- Script validation, anchor/frame compilation, compiler semantics, or changes
  to Slice 1.3 outputs.
- Voice synthesis, provider calls, cache writes, normalization, or voice
  selection.
- Media search, download, transcoding, research-project access, handle repair,
  or substitution of unrelated footage.
- Fusion semantic-input mutation (Slice 1.5), Resolve Studio automation
  (Slice 1.6), durable jobs (Slice 1.7), UI, persistence, collaboration,
  review rendering, or uploads.
- FCPXML; D-P005 keeps it parked. Only hard cuts are supported.
- Multi-build project mutation/reconciliation. This slice publishes one new
  project root and idempotently reuses that exact verified result; later build
  lifecycle work owns incremental project mutation.
- Any change to `/contracts`, generated contract types, `/fixtures`, accepted
  Slice 0.2 data/tests, accepted Slice 1.1 data/tests, or frozen Slice 1.3
  dependency inputs and goldens.

## Contracts, fixtures, data, and dependencies

- No shared-contract change is required. Compiler readiness remains
  `ready | ready_with_warnings | blocked | failed`; `ready_to_import` is a
  package-verification state in the new internal receipt/result and CLI.
- The compiler's manifest and report are copied canonically and never rewritten
  to describe adapter-created placeholder PNGs. The verification receipt owns
  those package-local materialization facts.
- The source map is an internal invocation boundary, not a shared contract or
  package artifact. Relative origin paths resolve against the map file; origin
  paths never enter output identity or the verification receipt.
- Tests create Slice-1.4-owned media and derived manifest/report values under
  temporary directories. Accepted data and fixture bytes remain read-only.
- No dependency or lockfile addition. Placeholder PNG generation, hashing,
  safe copying, clone attempts, JSON, and receipt handling use the Python
  standard library; the existing exact-pinned OpenTimelineIO/jsonschema stack
  remains the interchange boundary. FFprobe is the existing Slice 0.1/1.2
  system prerequisite used for actual-media inspection.
- The section 8.2 authoring-project root is the portable self-contained import
  package. Build artifacts intentionally live below `Builds/<build-id>` while
  their OTIO media references resolve to the sibling project-root `Media/`
  tree; moving only the build subdirectory is unsupported and stated in the
  instructions.

## Test-first implementation order

1. Add failing tests for a ready compiler manifest/report with narration,
   resolved media, placeholders, and manual-completion items.
2. Add failures for blocked/failed or mismatched reports, corrupt/missing or
   linked inputs, unsafe paths, and existing unrelated output.
3. Add placeholder-slate generation and visible-label/identity tests.
4. Add section 8.2 materialization and receipt tests, including clone fallback,
   post-copy hash verification, exact inventory, and idempotent reuse.
5. Add parsed-OTIO event/rate/duration/track/marker/hard-cut tests and tamper
   tests for each verified artifact.
6. Add CLI tests and the retained acceptance project generation path.

## Automated verification

- Focused package tests, Ruff formatting/lint, and strict mypy.
- Existing Slice 0.2 package tests unchanged and green.
- Full `npm run validate` twice consecutively under the pinned toolchain.
- `git diff --check`, generated-contract currentness, both lockfiles unchanged,
  and explicit frozen-boundary diffs.
- Independent Terra read-only review with no unresolved correctness, safety,
  contract, or acceptance finding.

## Producer acceptance

1. Open the retained project root and read
   `Builds/<build-id>/IMPORT_INSTRUCTIONS.md` and `build-report.json`.
2. Confirm `package-verification.json` says `ready_to_import` and lists the
   same manual-completion item IDs as the compiler report.
3. In the tested Resolve Free installation choose **File → Import → Timeline…**
   and import `Builds/<build-id>/timeline.otio` without substituting media.
4. Play the complete rough cut and confirm temporary narration is audible,
   resolved media is linked, placeholder slates are visible and labeled, the
   duration/rate/tracks/markers match the instructions, and there are hard cuts
   only.
5. Compare each visible unresolved item with the report's manual-completion
   list and record every discrepancy. Explicitly accept Slice 1.4 only if the
   observed list matches.

## Proposed follow-up work

- Incremental multi-build reuse and rematerialization belongs with durable
  build lifecycle work rather than this one-build package publication slice.
- Any Resolve Free-specific import discrepancy discovered by the producer is
  bounded as a Slice 1.4 correction or recorded capability limitation before
  [Slice 1.5](curated-fusion-graphics.md) begins; it is not silently hidden in
  the report.
