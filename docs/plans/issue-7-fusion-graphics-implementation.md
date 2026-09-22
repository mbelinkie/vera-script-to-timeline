# Issue #7 implementation plan — curated EV24 graphics

## Slice boundary

Implement only the approved EV24 `ScriptDocument` source, trusted resolved
graphic dependency, `fusion_template` source, `fusion_graphic` event, and
per-delivery graphic report outcome. Keep the canonical manifest independent
of delivery edition. Reject unsupported graphic materialization before any
package or Resolve mutation.

The approved contract-change boundary is
`docs/plans/issue-7-fusion-graphics-contract-change.md`. The existing
`VisualEvent.id` is the stable use identity, and the existing narration anchor
sets the exact frame range. The default graphic target is V4 through the
adjustable track map. Resolve mutation, Fusion-control writes, picker UI,
arbitrary templates, Free baking, and timeline reconciliation are excluded.

## Touched contracts and evidence

- Amend only the three approved v1 schemas and `CompilerDependencies v1`.
  Regenerate TypeScript and Python types. Update the script validator,
  compiler, and exhaustive package readers only as needed to recognize or
  explicitly reject the new variants.
- Create only new issue-owned input fixtures and compiler goldens. Preserve
  accepted `/fixtures`, prior golden files, and acceptance tests byte for
  byte. Check against baseline `cc39f29`.
- Use no new dependency; existing JSON Schema/Ajv, Node crypto, and Python
  tools suffice.

## Automated checks

Add focused positive/negative semantic validation and compiler tests, including
the accepted EV24 country set, Otis without Year, null overrides, project
badge identity, pinned revision/hash matching, 64-frame minimum, exact V4
target, report accounting, and unsupported downstream adapter rejection.
Generate issue-owned goldens twice and compare bytes. Run generated-type
currentness, full `npm run validate`, dependency audit, and frozen-boundary
audit; retain exact commands, versions, results, and artifact hashes.

## Producer acceptance steps

1. Open the approved contract note, then inspect the new EV24 source schema.
   Confirm the author-facing surface contains only pinned revision identity,
   stable country/conditional year, null text overrides, and project badge ID.
2. Open the issue-owned normal and Otis manifest/report goldens. Confirm exact
   V4 range/provenance and that Otis has no Year or invented text.
3. Compare the Studio and Free reports for the same manifest. Confirm the
   Studio plan says live, while Free says placeholder with a linked manual
   completion item; neither claims a verified Resolve placement or baked file.
4. Review the retained validation and frozen-boundary evidence. Reply on #7
   with `ACCEPT #7` and the checklist steps accepted, or `FAIL #7` with the
   failing step and observed mismatch. Leave the issue In review until then.
