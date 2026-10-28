# #326 — cross-row music proof packet

Status as of 2026-10-28: this issue branch implements the first-interruption
domain correction; local verification is recorded below. This packet records
the smallest later proof seam and consumer limits. No package or native result
is claimed; native and CI publication remain held by the Steward. #326 remains
open until the original external criteria and merged delivery are satisfied.

## Reuse and exact current boundary

- [RK-42](../RESOLVE_KNOWLEDGE_GUIDE.md#rk-42--saved-row-intent-and-native-probes-are-not-normal-product-delivery)
  is authoritative: #307/#310 prove pure row operations, Stash exclusion,
  Undo and guarded acceptance. They preserve or flag intent; they do not place
  spanning music. The compiler refuses active audio spans. This issue tests
  only the corrected first-interruption rule and its audible delta.
- [#173](../plans/issue-173-compiler-v2.md) supplies pure
  `compileTimelineV2` / `resolveMediaRequirementsV2` seams. Its accepted
  evidence uses synthetic prepared bindings; it does not prove independent
  cue timing, real preparation or delivery
  ([verification](../verification/issue-173/automated.md#full-gate-and-consumer-handoff)).
- [#177](../plans/issue-177-v2-package-studio.md) supplies immutable package,
  OTIO readback, attestation and a guarded injected Studio assembly path. Its
  tests use synthetic records and fake/readback adapters; actual Studio
  qualification and rendering were explicitly excluded
  ([handoff limits](../verification/issue-177/README.md#retained-gates-and-external-boundary)).
- [#310](../plans/issue-310-sorting-stash.md#consumers-and-retained-limits)
  is the domain API reference. `applyRowEditV2` produces one immutable
  document result or refusal; the Sorting trial has local Undo and installs an
  accepted changed result once after a full-baseline check. This is not native
  timeline atomicity.

The saved shape is deliberately only intent: `rowAudioSpans[]` carries start
and end row IDs, a media/artifact ID and content hash, opaque `settings`, and
optional review data. It has no typed source trim, fade curve, mix/ducking,
playback extent, or local byte locator
([schema](../../contracts/script-document-v2.schema.json#L2546-L2623)). The
legacy `RowAudioReviewV2.alert` literal “Music now ends with this row. Review”
remains readable. Newly shortened spans use “Music shortened by this move”;
the additive schema/generated-type union accepts both saved forms.

`unsupportedRowIntent` returns `ROW_AUDIO_RUNTIME_UNAVAILABLE` when any span's
`startRowId` is active. Both `compileTimelineV2` and
`resolveMediaRequirementsV2` call it before producing usable output
([guard](../../packages/contracts/src/compiler-core-v2.ts#L201-L207),
[call sites](../../packages/contracts/src/compiler-core-v2.ts#L1365-L1371)).
The regression test asserts that both compiler and media-needs consumers refuse
([test](../../packages/contracts/test/row-edit-consumers-v2.test.ts#L395-L426)).
The document validator checks that span endpoints exist; it does not infer
audible duration from row order
([validator](../../packages/contracts/src/authoring-v2-validation.ts#L258-L262)).

The v2 manifest source union is visual media plus narration audio; its
`source_audio` event represents verified sound from a visual source clip, not
an independent music cue. That clip-sound path requires one verified stream,
aligned sample mapping, and fixed policy gain (Quiet −18 dB, Full −0.1 or 0 dB);
it has no fade or arbitrary-mix controls
([manifest sources](../../contracts/timeline-manifest-v2.schema.json#L119-L128),
[source-audio event](../../contracts/timeline-manifest-v2.schema.json#L324-L358),
[compiler mapping](../../packages/contracts/src/compiler-core-v2.ts#L1125-L1158)).
Thus #177 package/native adapters cannot receive `rowAudioSpans` through the
current product compiler. #178/#249 source-audio endpoint results do not prove
independent spanning music.

The #307 domain tests previously encoded the old behavior: an interrupted
supported endpoint move shortened to the start row, while partial/intersecting,
overlapping, cross-section and Stash edits refused
([existing cases](../../packages/contracts/test/row-edits-v2.test.ts#L808-L887),
[reversed/cross-section cases](../../packages/contracts/test/row-edits-v2.test.ts#L986-L1007)).
The new tests replace the superseded within-section move results and retain
the overlap, broken cross-section, Stash and invalid-coverage safety refusals.

## Domain acceptance delta

- Preserve an intact original row run through reorder and exact Undo.
- For original coverage A–B–C–D–E reordered to A–B–C–E–D, retain the
  consecutive original prefix A–B–C, end at C, and preserve the prior endpoint
  and settings in review with “Music shortened by this move”. Do not restart on
  D/E or cover intervening unrelated rows.
- Include the Producer's three-row #125 fixture: moving only the
  paper-signal-frame ending row beyond unrelated rows retains coverage through
  the unchanged chalk-crescent middle row and warns at that endpoint.
- Changed spans shorten only for moves wholly within the original section;
  intact original groups retain the existing move behavior. Overlap, broken
  cross-section, Stash and invalid coverage continue to refuse atomically.
  Runtime source availability and extent checks remain part of the later proof.

The current tests' arbitrary `volume`, `fade`, `ducking`, `loop` settings only
prove payload preservation; they do not prove playback behavior. The domain
result remains a saved intent/review state.

DeepSeek-V4-Pro supplied a bounded draft from public synthetic source. Its
first request exhausted an 18,000-token reasoning allowance without final
content. A smaller non-thinking request returned code and test ideas, but
retained the obsolete endpoint-only guard, dereferenced nullable coverage,
changed the requested warning, and invented test APIs. Codex independently
corrected the implementation and tests; the raw draft is not evidence of
correctness or native capability. No provider or credential integration is
added to the repository.

A Producer-authorized comparison used the smaller request with Thinking on,
low reasoning effort, and a 65,536-token output ceiling. It finished normally:
9,802 reasoning tokens and 2,079 final-answer tokens, priced at $0.02455794.
The unmodified implementation candidate passed 41/51 focused tests in an
isolated source copy. Correcting only its warning literal passed 49/51;
its retained endpoint-only restriction still refused required middle-row and
insertion moves. Its generated tests also used incorrect public APIs. This
proves successful completion under those request conditions, not a controlled
quality comparison: task size, reasoning effort, output budget and JSON format
all differed from the first attempt. Cumulative verified usage across #118
and #326 is $0.24759834, within the unchanged $1 trial cap.

## Local checkpoint verification

The corrected implementation passes all 51 row-edit tests, contracts
typecheck and the two generated-Python contract tests. Generated-currentness,
all lint/type checks and fast TypeScript tests pass (contracts: 663 tests).
Compiler code and goldens are unchanged; existing compiler/media-needs
refusals remain exercised by the fast tests.

`validate:fast` exited 1: Python passed 1,902/1,903 tests, with
`test_actual_capability_bootstrap_returns_and_retains_refusal[loaded]`
in `test_issue208_review_fixes.py` failing on a wall/monotonic clock mismatch
(wall 1.074519 s, monotonic 1.137972 s). That test and clock implementation
are unchanged by #326. The exact failed test passed on one isolated rerun
(2.35 s), without source or assertion changes. This is not a green aggregate
run; retain the original failure when assessing release readiness.

Claude review remains pending the final issue diff. Cloud Validate,
publication and all native/media proof remain pending under the Steward's
holds. This local checkpoint does not close #326 or unblock its consuming
audible promises.

## Smallest later probe and consumer handoff

1. Use one public, generated, hash-bound distinguishable tone file and a saved
   synthetic document. Exercise one word-ended cue and one duration-ended
   variation over two synthetic narration/visual rows, then the five-row
   interruption case. Include intact run reorder and a neighboring duration
   change. Preserve narration row timing and internal cuts.
2. Bridge the saved span through a clearly labeled **probe-only** consumer into
   the smallest versioned audio-only package event/track that #177 can attest,
   deliver and read back. Bind the cue's file hash, source sample range,
   computed record extent, row-span identity and settings. Do not relabel the
   existing visual `source_audio` event as a music cue. #100 remains owner of
   production library, typed cue settings and UI integration.
3. Build only a new disposable project/timeline. Save, close, reopen, verify
   event identity, record/source range and gain/fade settings, then render and
   decode the output to compare cue start/end/trim and unaffected narration
   timing. Record the actual Resolve edition/build and route. Reuse only
   relevant #178/#249 findings; their source-audio cases do not transfer.
4. Exercise one audio-only semantic change as a single unit. The current row
   transaction is atomic in memory; `studio_assembly.py` creates a project and
   can retain a partial target after mutation failure, so it does not provide
   general native all-or-none update semantics
   ([assembly boundary](../../python/vera_timeline_agent/studio_assembly.py#L180-L206)).
   Report the tested unit precisely. Do not claim a reusable selective-plan
   runner; #128's outbound selection/retry mechanism is separately owned by
   #328, and #35 job stages do not supply it.
5. If the route cannot bind saved intent to package, native readback and decoded
   output, or cannot keep a failed audio-only unit from being treated as
   committed, record that as the exact negative limit. Do not substitute a
   manually placed timeline or remove the feature promise.

Consumer handoff: #125 can present the endpoint and review alert from the saved
domain result while this runtime hold remains. #128 can treat one cue add,
remove or move as one semantic selection unit only after its own frozen-plan
proof; this packet does not provide that runner. #100 retains production music
source/library resolution, typed trim/fade/mix semantics, availability/rights
handling, and end-to-end integration.
