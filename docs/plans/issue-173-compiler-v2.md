# Issue #173 — pure v2 narration and programme compiler

Owner: `gpt-6.1-sol/xhigh`, task
`01a11f37-9631-7be0-a8d5-3fa692e48e91/root/owner_173`, dedicated branch
`codex/issue-173-compiler-v2`, baseline
`792b09bc2c1c91867fca99eb558ee6250bbd4cdd`.

## Scope and acceptance

Implement accepted #156 P4 (§§3.2, 4, 5.2, 7, 8.1) under CN-1–3 approved at
`e32727f0c0e65dc5a8561e0f470ed28e59bd1809`. Public seams are
`@vera/contracts/compiler-core-v2` (`compileTimelineV2`,
`resolveMediaRequirementsV2`) and
`narration/compiler_dependencies_v2.py:narration_v2_dependency_from_asset`.
Both are pure: no media acquisition, synthesis, transcoding, filesystem access,
persistence, delivery, UI or Resolve operation. Synthetic verified preparation
bindings test the compiler boundary; they do not qualify P5 or real media.
No dependencies are added; installed generators, BigInt and Fraction suffice.

Acceptance is Automated. Run the new TS/Python tests first, generated-currentness,
lint/type checks, existing relevant regressions and the full locked-toolchain
`VITEST_MAX_WORKERS=1 npm run validate`. Retain byte-repeat manifest/report
goldens, source/tool/profile hashes and frozen v1/#144 source inventory.
Producer has already authorized Automated closure; no deterministic check is
delegated back to the producer. No v1 source/contract/fixture/accepted test or
existing P2/P3 fixture is edited. New data lives in an issue-owned subdirectory
of `tests/data/authoring_v2/`.

## Additive v2 serialization correction

The existing timing map has asset/hash identity but no exact audio duration or
locator, and the manifest's only source shape describes picture frames. The
accepted P4 semantics require narration samples, not invented duration. CN-1
and CN-3 authorize this narrow realization correction.

Add `NarrationAudioBindingV2` with `narrationAssetId`, `audioHash`, `timingHash`, `cacheAssetId`
(64 lowercase hex cache identity), immutable project-relative `locator`,
positive safe-integer `durationSamples`, `sampleRate`, `channels`. Add optional
`audio` to `NarrationTokenTimingMapV2`; semantic compilation requires it for
positive narration and verifies its asset/hash identity against the map.
Preserve old dependencies as schema-valid; missing audio refuses compilation.
The binding freezes the cache-verified timing hash independently of the map;
semantic compilation rejects differing timing hashes rather than accepting a
changed token map label. Add optional `build.forcePreviewVisuals` (false by
default, true forbidden for Release) to freeze the already-approved explicit
undefined/request Preview choice; its presence never clears a blocking report
or overrides stale anchors, collapsed frames, or source/preparation failure.
The Python adapter maps cache identity to deterministic UUID5 without changing
any frozen token ID. Add a manifest source alternative
`NarrationManifestSourceV2` containing `id` and `narrationAudio` (the same binding).
Existing visual source shapes retain their exact meaning and required fields.

The initial P2 event serialization also omitted #55’s exact still composition and
slate text. Add optional closed `pictureTreatment` to v2 events: a `still`
variant carrying the immutable reference and fixed contain/center/opaque-black/
no-motion composition, or a `slate` variant carrying intentional/undefined/
unresolved purpose and exact text. Temporary OC uses a source-free `placeholder`
event whose treatment is a real still, with presenter choice and temporary
diagnostic retained; this avoids fictional clip frame/preparation evidence.
A checked-in 1920×1080 generic torso SVG and descriptor pin the successful
fallback. P5 owns verification/materialization; pure compilation reads no files.
Old events remain schema-valid, while the new compiler emits treatment evidence.
Add optional `BoundaryEvidenceV2.wordRelation` (at-word-start, inside-word,
between-words, or derived/unknown) and nullable `relatedTokenId` so the existing
honest media-cut relation can be frozen explicitly; audible precision alone
cannot distinguish at from inside. Next-word-derived ends never prove silence.
This correction realizes existing #55/#156 semantics rather than adding a new
picture policy. Add optional closed `TimelineEventV2.marker` with
`supportingItemId` and exact authored `text`: the accepted point-marker behavior
previously had an event range but nowhere in the manifest to retain its note.
The new compiler emits this evidence; old events remain valid. This introduces
no marker naming or editorial text policy. Add a closed `still_frame` picture
treatment with `pictureKind=image|capture|graphic` and the authored
`framingPolicy=contain|cover|native`. It explicitly identifies the already-adopted
static hold of one verified prepared frame throughout the record interval;
without it a standalone manifest could not distinguish that hold from forbidden
clip shortage fill. The event retains its existing source/preparation evidence;
no source dimensions, media identity, or motion policy are invented.
Regenerate only v2 TS/Python outputs; check v1 generated bytes unchanged.
This adds serialization evidence, changes no timing/editorial authority, and
requires new cross-language/schema/compiler tests rather than rewrites of old
acceptance tests.

## Ownership and checks

The Python worker owns the new Python adapter/test and issue-owned Python
boundary fixture. After its initial audio additions, the owner owns both v2
schema corrections and all coordinated generation runs, the optional manifest
picture treatment, and generic torso asset/descriptor. The TS
worker owns new compiler/media-needs modules, its public export, new TS tests
and compiler goldens. The owner freezes interfaces, reviews integration,
maintains this plan and verification evidence, and performs acceptance/closure.
Workers preserve others' edits and request shared-file changes through the owner.

Required controls: exact frozen-token UTF-16 association (including repeated
words, punctuation, apostrophes, combining characters and surrogate pairs);
stale/hash/revision/precision refusal; honest unknown final word end. Deterministic
root/child/return/overlay composition and default/intentional/undefined policies;
visual-only duration at 24000/1001 and an alternate rate; complete-clip and
selected-range terminal quantization; at/inside/between/unknown word relation;
collapsed boundaries, shortage and overlapping No/Quiet/Full audio refusal.
Use exact checked rational arithmetic and a single boundary resolver shared by
the compiler and authoritative media needs. Continuous roots advance under
children; returns emit no new source event. No fill or hidden retiming.

## Forecast and checkpoint

Size M. Initial expectation: one implementation session plus an approximately
90-minute unattended baseline gate; reassess after focused tests. Five-hour
sampling reserve is 10%: suspend all workers at 90% used, preserve work and
report the continuation point. Long OS validation may continue unattended.

Saved quota checkpoint: audio schema/generated corrections passed the existing
v2 schema suites (24 TS tests) and generated Python surface (2 tests); adapter
and compiler implementation had not started. Sampling resumed on explicit user
instruction after the allowance reset. The same claim and workers continue.

Current checkpoint: the complete 26-test compiler matrix passes with updates
disabled, together with 30 additive/existing schema tests and 11 Python
adapter/generated/v1-regression tests. Typecheck, lint and generation
currentness pass. There are 33 active frozen compiler input/output scenarios.
Independent owner review and frozen-byte auditing are complete. Remaining active
work is final source/evidence commit and launch, then acceptance/closure after
the separate approximately 90-minute repository OS gate (medium confidence in
that baseline wait; no completion time is guaranteed).
The owner and workers stop sampling immediately after that gate starts; its
launcher saves a complete log and atomic completion status for the parent's
deferred check. No closure occurs until the gate passes.

Review judgment: original integer source read coverage differs from exact
delivered playback duration and audio end. The matrix asserts each separately;
terminal source quantization cannot add source speech. Missing preparation,
unresolved structural boundaries, and unavailable supporting intent must retain
blocking evidence and honest report counts rather than look complete.
