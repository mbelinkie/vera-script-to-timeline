# Issue #10 plan — Resolve Free baked EV24 fallback investigation

## Bounded slice

Add an opt-in package adapter for exactly the hash-pinned EV24
`fusion_graphic` event already emitted by issue #7. The adapter accepts a
producer-rendered alpha-media candidate and emits an independently verified
Resolve Free package whose OTIO clip retains the original Fusion event,
template, semantic-snapshot, and placeholder-report provenance.

It does not render or alter the EV24 template, change compiler contracts or
goldens, automate Resolve, replace the existing Free placeholder report, or
support arbitrary templates or graphs. A missing real Studio render is an
explicit non-result, not a substitute that this adapter may invent.

## Inputs and output boundary

- Inputs are canonical issue-#7 manifest/report bytes, the normal
  source-materialization plan, and one internal baked-candidate plan.
- The baked-candidate plan names the exact event, source/template identities,
  semantic snapshot hash, original manual-completion item, renderer/version,
  and one independent alpha-capable media file.
- The package receipt records the candidate content hash, dimensions, exact
  rate/duration, alpha pixel format, renderer declaration, template identity,
  semantic snapshot hash, and retained report outcome. OTIO uses the baked
  media only after those facts validate and preserves the original graphic
  provenance in metadata.

## Contracts, fixtures, and dependencies

- No shared schema, generated type, frozen fixture, golden, or accepted test
  changes. The candidate plan and receipt are internal package-adapter data.
- No dependency is added. The existing package FFprobe prerequisite verifies
  the supplied media; it is not used as a renderer.
- Tests create a short alpha-capable video only as a local verification
  harness. It is not a claimed EV24 render or retained production candidate.

## Automated checks

Add issue-owned tests for valid placement/provenance and for missing alpha,
duration or rate mismatch, corrupt media, stale template or semantic identity,
and absence of the original explicit manual item. Verify parsed OTIO and
receipt hashes after publication.

## External operator checklist

1. Use Resolve Studio to render the approved EV24 revision at its declared
   semantic snapshot to an alpha-capable file. Record the exact renderer and
   tool versions. Do not create a substitute render with VERA or FFmpeg.
2. Generate the candidate plan with the exact event/source/template identities
   and original report manual-item ID, then build the package with
   `uv run python -m vera_timeline_agent.resolve_import_package.baked_graphics
   <manifest> <report> <materialization-plan> <baked-graphic-plan> --output
   <authoring-project>`.
3. In the selected compatible Resolve Free 20.2.3 / macOS Sequoia 15.8
   external-boot baseline from issue #134, import the retained `timeline.otio`
   without relinking or replacing media. That selection is not import/playback
   evidence; this step retains the pending external acceptance result.
4. Play the complete graphic range. Confirm entrance, hold, exit, text/badge
   values, rate, duration, and transparent regions against the Studio result.
5. Record `ACCEPT #10` only if all checks match, otherwise record `FAIL #10`
   with the observed alpha or animation discrepancy. Either outcome leaves the
   first live Studio release unchanged.
