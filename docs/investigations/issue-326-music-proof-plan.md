# #326 — cross-row music proof packet

Status as of 2026-10-28: this issue branch implements the first-interruption
domain correction; local verification is recorded below. This packet records
the bounded proof seam and consumer limits. Host preparation and native
placement/readback have passed for the word-end case. Native decoded-output
proof is still pending; publication remains held in the shared CI queue. #326
remains open until the original external criteria and merged delivery are
satisfied.

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
all differed from the first attempt.

A later bounded automatic repair trial used one DeepSeek worker with deterministic
edit/test/failure feedback, frozen tests and type checks, high Thinking and a
65,536-token output ceiling. Its first repair passed 49/51 tests; feeding the
two remaining failures back produced 51/51 plus typecheck on the second repair.
Codex did not edit the candidate or tests between those rounds. The two repairs
cost $0.08604288 and took 521 seconds. This is evidence for the bounded repair
process, not general correctness: the candidate was not substituted for the
smaller independently corrected implementation, and a legacy-alert edge remains
outside that frozen test set. Seven fully accounted requests across #118/#326
total $0.33364122. The Producer subsequently authorized a $10 cumulative cap,
including historical usage; no extra requests were made to use that allowance.
The private reusable controller and its 23 offline tests add no provider or
credential integration to this repository.

## Local checkpoint verification

The corrected implementation passes all 51 row-edit tests, contracts
typecheck and the two generated-Python contract tests. Generated-currentness,
all lint/type checks and fast TypeScript tests pass (contracts: 663 tests).
Compiler code and goldens are unchanged; existing compiler/media-needs
refusals remain exercised by the fast tests.

The focused slow host-preparation integration test passed once (142 seconds).
It verifies the production compiler refusal, span-free real compile/package
verification and the derived OTIO source/record ranges. The four focused audio
checker tests also passed, including rejection of a one-second trim error and
a six-frame-short cue; those synthetic checks qualify the checker, not Resolve.

`validate:fast` exited 1: Python passed 1,902/1,903 tests, with
`test_actual_capability_bootstrap_returns_and_retains_refusal[loaded]`
in `test_issue208_review_fixes.py` failing on a wall/monotonic clock mismatch
(wall 1.074519 s, monotonic 1.137972 s). That test and clock implementation
are unchanged by #326. The exact failed test passed on one isolated rerun
(2.35 s), without source or assertion changes. This is not a green aggregate
run; retain the original failure when assessing release readiness.

Claude review remains pending the final issue diff. Cloud Validate and
publication remain queued; native decoded-output proof is still pending. A
read-only injected Workflow Integration check reached the new empty issue-owned
project on Studio 21.1.1 build 10 with injected Python 3.14.7. The external
connector remained unreachable, and its scripting preference was not inferred
or changed. This checkpoint does not close #326 or unblock its consuming
audible promises.

## Bounded probe and current evidence

The host preparer binds a saved synthetic authoring snapshot, raw snapshot hash,
live content hash, active row span, compiler inputs, package manifest, build
ID and source hashes in `music-probe.json`. It first confirms that the
production compiler refuses active `rowAudioSpans` with
`ROW_AUDIO_RUNTIME_UNAVAILABLE`. It then compiles a refreshed, span-free
probe-only copy through the real compile CLI and unchanged v2 package builder
and verifier. The span remains in the evidence snapshot; the music event is
added only to a derived OTIO track after base-package verification. It does not
claim that production compilation or `source_audio` supports music.

The six defined probe cases use 24 fps, 48 kHz mono PCM and five narration
rows. Each narration row has a distinct 220–440 Hz tone at 0.12 peak; the
12-second music source has 24 successive half-second tones (620–1540 Hz) at
0.4 peak, begins at source sample 48,000, is requested at −12 dB, and has
six-frame fades at both ends.

| Case | Edit or endpoint | Expected music record range | Source sample range |
| --- | --- | --- | --- |
| `word-end-b` | Word-end endpoint in B | 0–84 frames | 48,000–216,000 |
| `duration-end-b` | Duration endpoint in B | 0–96 frames | 48,000–240,000 |
| `neighbor-duration-change` | A grows to 72 frames before B | 0–120 frames | 48,000–288,000 |
| `intact-reorder` | Move intact A–B after C | 48–144 frames | 48,000–240,000 |
| `abc-ed-first-interruption` | Move E between C and D; retain A–B–C | 0–144 frames | 48,000–336,000 |
| `issue125-ending-row-moved` | Move the ending row past unrelated rows; retain the chalk-crescent middle row | 0–96 frames | 48,000–240,000 |

For the first native word-end case, Studio 21.1.1.10 with injected Python
3.14.7 imported 11 expected events (10 base events plus one music event).
Their source hashes, paths and record ranges matched the sidecar; the music
was on audio track 2 at record frames 0–84 and source frames 24–108. The five
narration clips remained unchanged. Single-frame PNG visuals held as expected.
The requested −12 dB level and six-frame fades read back. An invalid
`SetProperties` key returned false without changing the timeline. Saving,
closing and reopening preserved the same project and timeline identity.

This native evidence establishes placement, readback and reopen behavior only.
Rendering and decode have not yet established audible cue start, end, trim,
gain, fades or narration equivalence. The declared fade curve is linear, but
Resolve's actual default fade curve remains unqualified until decoded output is
compared.

### Run guide

Prepare one case or all six in an absolute disposable output directory:

```sh
uv run python scripts/issue326_prepare_music_probe.py \
  --out <absolute-disposable-directory> --case word-end-b
```

Repeat `--case` to choose multiple cases; omit it to prepare all six. The host
preparer requires the pinned Node 24.19.0 runtime. The native entry point is
`scripts/issue326_workflow_launcher.py`, run through the injected Resolve
Workflow Integration route with a hash-pinned request. It dispatches the
probe-only `inspect`, `import`, `diagnose`, `readback`, `save_reopen`,
`configure` and `render` operations; it is not a production delivery adapter.
Pair a narration-only baseline render with the music render for each case and
check them with:

```sh
uv run python scripts/issue326_check_music_audio.py \
  --probe <case-directory>/music-probe.json \
  --baseline-wav <baseline.wav> --mixed-wav <mixed.wav>
```

The decoder checks source-time tones, cue bounds, sustained gain, six-frame
fade envelopes and narration against baseline. Its tone schedule detects
replacement and source shifts of 50 ms or more; short-lived level changes may
be averaged. Fade-curve error is diagnostic because Resolve may apply another
curve. Synthetic tones do not qualify arbitrary music or ducking behavior.

### Remaining evidence and consumer handoff

The actual native baseline/mixed renders and decoded comparison remain the
next gate. Until they pass, there is no audible proof. Report any failed
mutation at the tested unit; the in-memory row transaction is atomic, while
`studio_assembly.py` can retain a partial project after mutation failure
([assembly boundary](../../python/vera_timeline_agent/studio_assembly.py#L180-L206)).
This probe does not establish general native all-or-none update semantics or a
reusable selective-plan runner; #128's outbound selection/retry mechanism is
separately owned by #328, and #35 job stages do not supply it.

Consumer handoff: #125 can present the endpoint and review alert from the saved
domain result while this runtime hold remains. #128 can treat one cue add,
remove or move as one semantic selection unit only after its own frozen-plan
proof; this packet does not provide that runner. #100 retains production music
source/library resolution, typed trim/fade/mix semantics, availability/rights
handling, and end-to-end integration.
