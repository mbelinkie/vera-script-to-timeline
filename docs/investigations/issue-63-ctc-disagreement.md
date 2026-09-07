# Issue 63 — recognizer-side CTC disagreement

Status: **Accepted by the Producer.** The bounded result is **no adequate
selection**.

For the exact protocol, corrected rule-grid results, limitations, and a prompt
for external evaluation, see
[the Issue 63 LLM evaluation handoff](issue-63-llm-evaluation-handoff.md).

## Scope and evidence boundary

This investigation reused the retained full-source Parakeet TDT 0.6B v3 int8
recognition, the retained English TorchAudio wav2vec2 CTC model, the frozen
Issue #42 synthetic corpus, and the Producer-frozen Issue #51 real-footage
annotations. It added a private experimental comparison that retains Parakeet
words, unprompted greedy CTC tokens and acoustic spans, substitutions,
Parakeet-only words, CTC-only spans, scores, and uncertainty as separate
evidence. The Producer transcript entered only the final evaluation pass; it
did not prompt recognition, repair either hypothesis, choose thresholds, or
generate timing truth.

No new model, dependency, product code, contract, fixture, golden, generated
type, application data, or Research data was acquired or changed. No hosted
inference ran. Production ports/adapters/jobs/persistence/UI, take selection,
edit handles, audio treatment, keeper approval, and Apple Silicon claims remain
excluded. Detailed words, media, timings, hashes, paths, screenshots, and full
fingerprints remain only in the private Run A packet.

## Method

The experiment decoded argmax English CTC emissions inside the unchanged
retained Parakeet/VAD segment anchors. Consecutive token IDs were collapsed,
blank IDs removed, and the model's word delimiter converted token spans into
word spans. The output retained every lexical disagreement; interpretation
hints such as `partial_word_candidate` are explicitly not truth claims.

Calibration used only the frozen Issue #42 synthetic corpus. It exhaustively
tested the observed greedy-posterior thresholds, existing forced-path score
thresholds, and forced-versus-greedy boundary-difference thresholds. It tested
both greedy spans and existing Parakeet-text forced-CTC spans as the accepted
boundary source, with exact lexical agreement both required and optional. A
rule was eligible only if it had a nonempty accepted set, no boundary error
above 120 ms, median onset and offset errors at most 40 ms, p95 onset and
offset errors at most 120 ms, and at most 5% rejection. Only after this search
was frozen did the evaluator read the real-footage scoring set.

## Aggregate result

The 43-word synthetic calibration input produced 37 exact lexical agreements,
6 substitutions, and 2 CTC-only insertions. No nonempty rule met the timing
gates, even before imposing the 5% rejection ceiling. The retained fail-closed
rule therefore accepts no boundary: exact agreement is required, posterior
thresholds are set above the model range (`1.1`), maximum boundary disagreement
is `0 ms`, and interpolation never authorizes editing.

On the full source, Parakeet contained 439 recognized words and unprompted CTC
contained 467. The explicit comparison retained 370 equal operations, 69
substitutions, and 28 CTC-only spans. Of the CTC-only spans, 2 are labeled only
as partial-word candidates and 26 as unmatched audio; none is silently folded
into Parakeet text.

The frozen 80-word scoring set contained 54 words where the Producer reference,
Parakeet, and unprompted CTC agreed lexically. Before rejection, both tested CTC
span interpretations had median onset/offset error of 36/37 ms, p95 onset/
offset error of 124/175 ms, and 7 boundaries with onset or offset error above
120 ms. Because calibration found no eligible nonempty rule, the final artifact
accepts 0 of 439 recognized words and explicitly rejects or leaves unaligned
439 of 439 (100%). Empty accepted sets retain null timing metrics; they are not
reported as zero-error success.

All 14 Producer-marked editing-relevant events are explicit in the private
ledger. Four abandoned-phrase events remain preserved by Parakeet and nine are
explicitly missing or ambiguous. The previously omitted three-token repeated-
speech occurrence remains absent from Parakeet but is preserved as a timed CTC
disagreement with its lexical difference intact. It is not repaired from the
reference.

The result passes the honesty, independence, and event-visibility requirements,
but fails the boundary and coverage gates: there is no accepted timing set on
which to claim the 40/120 ms statistics, and rejection is 100%, not at most 5%.
Unprompted English CTC is useful as a recognizer-side recall alarm for missed
speech, but this bounded combination is not safe boundary authority.

## Fingerprints, parameters, and performance

- Parakeet baseline: Parakeet TDT 0.6B v3 int8 ONNX; `onnx-asr 0.12.0`;
  ONNX Runtime 1.23.2; CPUExecutionProvider; 8 threads; Silero VAD with 500 ms
  minimum silence, 30 s maximum speech, 30 ms speech padding, and 250 ms
  minimum speech. Initialization was 3.657 s, VAD 1.895 s, recognition
  19.485 s, and peak resident memory 1,013,415,936 bytes.
- CTC disagreement profile: TorchAudio `WAV2VEC2_ASR_BASE_960H`; Python
  3.12.13; Torch/TorchAudio 2.2.2; one CPU thread; 16 kHz mono input; argmax
  CTC collapse with blank removal and pipe delimiter; retained Parakeet
  anchors; first-to-last nonblank character-frame boundary; no interpolation
  and no reference input. In the final corrected rerun, initialization was
  1.391 s, emission inference 49.323 s, total processing 54.178 s, and peak
  resident memory 941,883,392
  bytes on the tested x86_64 host.

Exact model-file, input, adapter, parameter, output, and rule fingerprints are
retained privately. These Intel measurements make no Apple Silicon performance
claim.

## Automated checks

- Thirteen private pure-function tests pass for CTC collapse, repeated-token
  preservation, deterministic alignment, explicit non-truth hints, empty-set
  semantics, independent rule selection, both boundary sources, optional
  lexical disagreement, and timed repeat adjudication.
- Both final offline inference runs reproduce every comparable Issue #51 greedy
  CTC string; zero parity failures were observed.
- The final evaluator verifies the frozen annotation identity and complete
  human timing/disfluency review before scoring.
- The private packet retains immutable failed attempts, final outputs, full
  fingerprints, and integrity evidence; repository validation and frozen-
  boundary audits are recorded in the review handoff.

Post-acceptance verification corrected two evaluator bookkeeping defects: CTC-
only insertion hints now use local edit-alignment neighbors, and the exact-
agreement rule now rejects substitutions. The first changes only the non-truth
hint split from 1/27 to 2/26; the second restores the intended rule-grid branch.
Fresh immutable offline runs and evaluation retained the same no-adequate-
selection result, word/disagreement counts, boundary metrics, event outcomes,
and fail-closed decision.

## Proposed follow-up (not started)

If the Producer wants another investigation, create a separate bounded issue
to evaluate a boundary-first acoustic estimator on independently human-timed
natural-speech calibration material while keeping CTC disagreement as a recall
alarm. Any additional model must first justify license, size, runtime, and
packaging. This issue does not acquire that model or broaden into production.
