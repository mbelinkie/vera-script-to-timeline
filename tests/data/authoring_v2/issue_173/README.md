# Issue #173 fixture package

This package is new CN-3 evidence for the pure P4 compiler. Existing v1 and
accepted P2/P3 fixtures are unchanged. All identities, narration bytes and
verified media-preparation attestations here are synthetic; no file or provider
was acquired, prepared or qualified by these fixtures.

`python/narration-timing-map-v2.json` freezes the projection of
`go, can't élan 🌍 go?` onto the supplied stable tokens at exact original UTF-16
offsets. Provider word starts yield `next_word_derived` timing; the final audible
end remains unknown. The adapter preserves cache identity and derives its v2
asset UUID using UUID5 without regenerating token IDs.

`compiler/*.input.golden.json` freezes each compiler scenario's complete document and
dependencies. Matching `*.manifest.golden.json` and `*.report.golden.json`
retain canonical bytes, including original source cover, delivered playback
ranges, exact audio endpoints, composition, boundary evidence, default/slate
choices and report accounting. The test suite constructs each scenario,
compares its input bytes to the frozen snapshot, and checks output goldens.
Repeated compilation must preserve the caller's inputs and output bytes.

Only explicit `UPDATE_COMPILER_V2_GOLDENS=1` regenerates issue-owned snapshots.
Acceptance runs omit that variable. `sha256.json` pins every JSON fixture other
than the inventory itself. The compiler source/test and fixture hashes in the
verification package bind these bytes to the exact tested source.

The generic torso SVG and immutable descriptor live under
`packages/contracts/src/assets/`; the bindings test verifies the actual asset
hash and fixed contain/center/black/no-motion composition. P5 and P7 retain
responsibility for real prepared media and native realization.
