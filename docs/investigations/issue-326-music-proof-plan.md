# #326 — cross-row music proof

Status as of 2026-10-28: the first-interruption domain correction is implemented.
All six defined cases passed native placement, save/reopen and paired-WAV
decode. Local fast checks completed in stages: generated-contract currentness,
TypeScript lint/typecheck and fast suites, Ruff, MyPy and Python fast tests all
passed. A prior interrupted run had no terminal diagnostic. Two tests now have
finite 15-second Vitest limits under suite load; their assertions are unchanged.
Python fast tests took 305.50 seconds; existing speed follow-ups #335 and #349
cover the runtime. The probe does not add a production music runtime. #326
remains open until its acceptance evidence is complete and delivery is merged.

## Domain change and product boundary

[RK-42](../RESOLVE_KNOWLEDGE_GUIDE.md#rk-42--saved-row-intent-and-native-probes-are-not-normal-product-delivery)
is authoritative: [#307/#310](../plans/issue-310-sorting-stash.md#consumers-and-retained-limits)
prove row operations, Undo and guarded acceptance; they preserve or flag audio
intent but do not place spanning music. [#173](../plans/issue-173-compiler-v2.md)
and [#177](../plans/issue-177-v2-package-studio.md) provide compiler/package
seams, not independent music delivery.

`rowAudioSpans[]` is saved intent: it has start/end row IDs, an artifact ID and
hash, opaque settings and optional review data, but no typed trim, fade, mix,
playback extent or local byte locator
([schema](../../contracts/script-document-v2.schema.json#L2546-L2623)).
The compiler and media-needs resolver refuse active spans with
`ROW_AUDIO_RUNTIME_UNAVAILABLE`
([guard](../../packages/contracts/src/compiler-core-v2.ts#L201-L207),
[call sites](../../packages/contracts/src/compiler-core-v2.ts#L1365-L1371)).
The v2 `source_audio` event is verified sound from a visual source clip; it
does not accept an independent music cue. The validator checks that span
endpoints exist, not audible duration.

The domain correction retains the consecutive original prefix through its
first interrupted join. For A–B–C–D–E reordered to A–B–C–E–D, the span ends at
C and preserves its previous endpoint/settings in review. Intact original runs
can move together. Overlap, broken cross-section, Stash and invalid-coverage
edits continue to refuse. These are saved intent semantics, not a native
timeline transaction.

Historical model comparison: an 18k high-thinking DeepSeek request ended
without usable content; a later 65,536-token request completed but its raw
candidate passed only 41/51 tests. An automatic high-thinking edit/test-feedback
run improved 49/51 to 51/51 in two calls (521 seconds, $0.086), with no Codex
or test edits between rounds. Seven accounted calls across #118/#326 totaled
$0.334 under the Producer-authorized $10 cap; no provider or credential
integration was added. These experiments are not native-playback evidence;
the smaller independently corrected implementation was kept.

The host preparer confirms the production refusal, then compiles a refreshed
span-free probe copy through the real CLI and unchanged v2 package builder and
verifier. It keeps the original span in the evidence snapshot and adds music
only to a derived OTIO track after base-package verification. This is probe-only;
it does not establish a product route.

## Native case matrix

The six cases use 24 fps, 48 kHz mono narration fixtures and a 12-second
synthetic music source made of half-second tones. Music begins at sample 48,000,
requests −12 dB and has six-frame fades.

| Case | Edit or endpoint | Expected record range | Source samples | Native result |
| --- | --- | --- | --- | --- |
| `word-end-b` | Word-end endpoint in B | 0–84 frames | 48,000–216,000 | Pass: placement, reopen and decoded audio |
| `duration-end-b` | Duration endpoint in B | 0–96 frames | 48,000–240,000 | Pass: placement, reopen and decoded audio |
| `neighbor-duration-change` | A grows to 72 frames before B | 0–120 frames | 48,000–288,000 | Pass: 11-second decoded timeline |
| `intact-reorder` | Move intact A–B after C | 48–144 frames | 48,000–240,000 | Pass: decoded intact move |
| `abc-ed-first-interruption` | Move E between C and D; retain A–B–C | 0–144 frames | 48,000–336,000 | Pass: first interruption at C |
| `issue125-ending-row-moved` | Move ending row past unrelated rows; retain chalk-crescent middle row | 0–96 frames | 48,000–240,000 | Pass: saved middle-row endpoint |

### Word-end case result

Studio 21.1.1.10 with injected Python 3.14.7 imported the 11 expected events
(10 base events plus music). Source paths, hashes and record ranges matched the
sidecar. Music was on audio track 2 at record frames 0–84 and source frames
24–108. Narration clips and still visuals matched expectations. A valid gain
update passed; an invalid `SetProperties` key was refused without changing the
tested property. Saving, closing and reopening retained the same project and
timeline identities.

Paired PCM16/48 kHz, 10-second baseline and mixed WAVs decoded successfully.
The 700–940 Hz sequence was present at the one-second source trim and 84-frame
cue bounds. Measured steady peak was 0.100468 against the 0.100475 target.
Narration projection changed by at most 0.000744 (checker limit 0.012). The
six-frame fade windows were close to linear (RMSE 0.000491 in and 0.005721 out;
diagnostic only).

The `duration-end-b` case also passed. Eleven expected events read back after
import and reopen; music was on A2 at record frames 0–96 and source frames
24–120. Its decoded peak was 0.100468 against the 0.100475 target, the maximum
narration projection delta was 0.000744, and fade RMSE was 0.000491 in and
0.005369 out. An initial baseline request was refused before timeline mutation
because an unrelated job was still Ready; dispatching the exact new operation
ID then succeeded. The dispatcher now retains Ready jobs and starts only the
exact requested operation ID; four focused route tests passed.

`neighbor-duration-change` passed on an 11-second, 528,000-sample export. The
cue read back at 0–120 frames and source samples 48,000–288,000; peak was
0.100467, fade RMSE was 0.000491 in/0.004803 out, and narration projection
delta was 0.000668. `intact-reorder` passed on a 10-second export with music at
record frames 48–144 and source samples 48,000–240,000; peak was 0.100468, fade
RMSE 0.000491 in/0.005369 out, and narration projection delta 0.000744.

`abc-ed-first-interruption` passed with music ending at C (record frames
0–144, source samples 48,000–336,000). `issue125-ending-row-moved` passed with
the saved endpoint at chalk-crescent (record frames 0–96, source samples
48,000–240,000). Both produced verified 48 kHz PCM16 stereo WAVs at the
expected gain; narration projection delta was 0.000744 for each. Across all
six cases, measured music peak was about 0.100468 against the 0.100475 target.

The fixture tone appeared only on channel 1, so stereo routing is unqualified.
Tone checks resolve source shifts of at least 50 ms; brief level changes may
average out. Fade fit does not qualify arbitrary curves. The negative/positive
mutation check covers one `SetProperties` gain unit, not general all-or-none
timeline mutation.

## Preparation and checks

The five remaining inputs were prepared once with the preparer's pinned Node
24.19.0 runtime and frozen Python dependencies:

```sh
uv run --frozen python scripts/issue326_prepare_music_probe.py \
  --out <absolute-disposable-directory> \
  --case duration-end-b --case neighbor-duration-change --case intact-reorder \
  --case abc-ed-first-interruption --case issue125-ending-row-moved
```

Native placement, readback, save/reopen and render use
`scripts/issue326_workflow_launcher.py` through the injected Resolve Workflow
Integration route with a hash-pinned request. The audio comparison command is:

```sh
uv run --frozen python scripts/issue326_check_music_audio.py \
  --probe <case-directory>/music-probe.json \
  --baseline-wav <baseline.wav> --mixed-wav <mixed.wav>
```

The focused host-preparation integration test passed once (142 seconds), as did
the four focused audio-checker tests, four native-probe route tests and the
264-frame boundary test. The row-edit tests (51), contracts typecheck and two
generated-Python contract tests passed. Fast checks completed in stages rather
than one successful `npm run validate:fast` process: the contracts fast suite
passed all 33 files and 663 tests, along with the other TypeScript workspace and
root tests; Ruff, MyPy and the Python fast suite then passed (1,920 tests). The
Python fast suite took 305.50 seconds. Two suite-loaded Vitest tests now have
15-second limits with assertions preserved; existing issues #335 and #349
track validation speed.

## Limits and consumer handoff

Production compilation and media-needs resolution still reject active
`rowAudioSpans`. This probe does not prove production music source/library
resolution, rights or availability, typed trim/fade/mix behavior, arbitrary
music, ducking, stereo routing, general transaction atomicity or end-to-end
delivery. #125 can present the saved endpoint/review alert while this runtime
hold remains. #128 still owns its frozen selective-plan proof; #100 retains
production music integration.
