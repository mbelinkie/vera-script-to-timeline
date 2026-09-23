# Issue #10 external acceptance handoff

## Automated evidence

`tests/test_free_baked_fallback.py` proves the opt-in adapter accepts only the
issue-#7 EV24 `fusion_graphic`, its matching template identity, semantic
snapshot hash, and original Free manual-completion item. It rejects missing
alpha, wrong rate/duration, corruption, stale identity, silent substitution,
and post-publication tampering. The ephemeral test video is an alpha-capable
verification harness, not an EV24 render or product candidate.

The adapter receipt records output SHA-256, package-relative path, renderer
name/version, template revision/digests, semantic snapshot hash, manual item,
dimensions, rate, duration, alpha/pixel format, and hashes of the canonical
manifest/report, OTIO, and instructions. OTIO retains this data under
`vera.graphic_bake`; the unchanged compiler report remains the explicit Free
`placeholder` outcome.

## Capability decision

**Pending external result.** No Studio-rendered EV24 alpha file was supplied
or created, so no baked fallback is accepted or claimed. The original Studio
release and Free placeholder behavior remain unchanged.

## Selected Resolve Free acceptance baseline

Issue #134 selected **Resolve Free 20.2.3 on macOS Sequoia 15.8** as the
compatible external-boot baseline for this 2019 Intel Mac. This is the target
environment for the pending acceptance run; it is not evidence that this
package has already imported or played correctly there.

## Resolve Free 20.2.3 checklist

1. Render the approved EV24 revision and exact semantic snapshot in Resolve
   Studio to alpha-capable media; record edition, build, renderer version, and
   render settings.
2. Create a candidate plan with the exact event/template/snapshot/manual-item
   identities and render origin.
3. Run `uv run python -m vera_timeline_agent.resolve_import_package.baked_graphics <manifest> <report> <materialization-plan> <baked-plan> --output <project>`.
4. Import `<project>/Builds/<build-id>/timeline.otio` into the selected Resolve
   Free 20.2.3 / macOS Sequoia 15.8 baseline without media replacement; compare animation, alpha,
   text/badge values, dimensions, rate, and duration to Studio.
5. Record `ACCEPT #10` with receipt path and baseline, or `FAIL #10` with the
   observed discrepancy. A failure must not alter the Studio path.
