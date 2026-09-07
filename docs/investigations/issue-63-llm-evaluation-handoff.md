# Issue 63 testing protocol and results — external LLM handoff

## Purpose

This document is a self-contained technical handoff for evaluating VERA Issue
#63, “Test CTC disagreement for disfluency recovery and boundary rejection.” It
describes the implemented experiment exactly enough to critique the method and
propose a better bounded follow-up. It is not a production design or an approval
to integrate another model.

The accepted outcome is **no adequate selection**. Unprompted English CTC added
useful evidence that Parakeet missed some speech, including one marked repeated-
word event, but neither the greedy CTC word spans nor the existing Parakeet-text
forced CTC spans could be filtered into a nonempty boundary set satisfying the
timing requirements on independent synthetic calibration evidence.

## Privacy boundary

This handoff intentionally excludes the private audio, transcript text,
per-word timings, event text, detailed model/input/output hashes, screenshots,
and machine-local paths. Those materials and complete cryptographic
fingerprints remain in a local evidence packet. The counts and statistics below
are aggregate results and are safe to share.

This means another LLM can audit the experimental logic and recommend next
approaches, but cannot independently reproduce the numerical result from this
document alone.

## Question and decision criteria

The experiment asked whether unprompted CTC evidence could complement retained
Parakeet recognition in two ways:

1. Keep editing-relevant disfluencies visible instead of silently losing them.
2. Supply or validate word boundaries while explicitly rejecting unsafe ones.

A selection could be called adequate only if all of the following held on the
frozen real-footage evaluation after independent rule calibration:

| Gate | Required value |
| --- | ---: |
| Marked events | Every event preserved or explicitly reported missing |
| Maximum accepted boundary error | No onset or offset above 120 ms |
| Median accepted onset error | At most 40 ms |
| Median accepted offset error | At most 40 ms |
| p95 accepted onset error | At most 120 ms |
| p95 accepted offset error | At most 120 ms |
| Rejected or unaligned recognized words | At most 5% |
| Calibration leakage | No real-footage scoring evidence used for selection |
| Reference handling | No recognition prompting or hypothesis repair |

The evaluator was deliberately fail-closed: an empty accepted set does not
pass timing gates by vacuity. Its timing statistics remain null, not zero.

## Inputs and evidence separation

The experiment reused only previously retained local assets:

- Parakeet TDT 0.6B v3 int8 ONNX output for the full real source.
- TorchAudio `WAV2VEC2_ASR_BASE_960H` as the unprompted English CTC model.
- The frozen Issue #42 synthetic corpus and its machine-readable word truth for
  calibration.
- Producer-frozen Issue #51 real-footage evidence: an 80-word human-timed
  scoring subset and 14 editing-relevant disfluency annotations.
- Existing Parakeet-text forced CTC spans, tested as an alternative boundary
  source rather than regenerated or treated as truth.

The synthetic calibration target was the frozen Issue #42 target text carried
through the existing alignment artifact. It was **not** produced by a fresh
Parakeet recognition pass over the synthetic audio. Consequently, calibration
tests CTC boundary filtering when target text is known, not the joint error
distribution of two independently run recognizers. This is an important
external-validity limitation.

The real Producer reference was loaded only after the calibration search had
selected—or failed to select—a rule. It was never passed to either recognizer,
used to repair either hypothesis, or used to tune thresholds.

## Execution environment and model profiles

All new inference ran locally under an operating-system sandbox with network
access denied. Writes were restricted to the private evidence packet. Audio was
16 kHz, mono, signed 16-bit PCM. Full model-file and parameter fingerprints were
retained privately.

| Component | Exact tested profile |
| --- | --- |
| Baseline recognizer | Parakeet TDT 0.6B v3 int8 ONNX |
| Baseline runner | `onnx-asr 0.12.0`; ONNX Runtime 1.23.2 |
| Baseline execution | CPUExecutionProvider; 8 threads |
| Baseline VAD | Silero; minimum silence 500 ms; maximum speech 30 s; speech padding 30 ms; minimum speech 250 ms |
| CTC recognizer | TorchAudio `WAV2VEC2_ASR_BASE_960H` |
| CTC runtime | Python 3.12.13; Torch 2.2.2; TorchAudio 2.2.2 |
| CTC execution | x86_64 CPU; 1 Torch compute thread; 1 interop thread |
| CTC segmentation | The unchanged retained Parakeet/VAD segment anchors |
| CTC decoding | Framewise argmax; collapse contiguous repeated IDs; remove blank; pipe token is word delimiter |
| Reference prompt | None |
| Interpolation | Disabled and never allowed to authorize an edit boundary |

No Apple Silicon performance conclusion is supported by this run.

## Exact comparison protocol

### 1. Normalize lexical tokens

Text was case-folded. A Unicode word matcher retained letters/digits and allowed
an internal straight or curly apostrophe. Curly apostrophes were normalized to
straight apostrophes. Punctuation outside that form was not part of a word.

For real footage, the comparison target was the ordered list of retained
Parakeet display tokens. Where an existing forced span existed at the same
display index, its start, end, forced-path score, and score kind were attached
without changing the token.

### 2. Run unprompted CTC inside retained segment anchors

For each retained segment, audio samples were cut using its existing start and
end anchors. The entire segment was passed to the CTC model. No transcript or
lexical constraint entered model inference.

For each emission frame, the highest-log-probability token ID was selected. A
contiguous run of the same ID became one token span. Blank runs were discarded;
the same nonblank ID separated by a blank therefore remained two tokens.

The frame duration was calculated independently for every segment:

```text
frame_ms = segment_sample_count / emission_frame_count / sample_rate * 1000
```

For a retained nonblank token run from frame `a` through exclusive frame `b`:

```text
token_start_ms = segment_anchor_start_ms + a * frame_ms
token_end_ms   = segment_anchor_start_ms + b * frame_ms
token_score    = mean(argmax posterior over frames [a, b))
```

Word boundaries were pipe delimiters. A word began at its first nonblank
character frame and ended after its last nonblank character frame; surrounding
blank and delimiter frames were excluded. Millisecond boundaries were rounded
to the nearest integer.

If token spans `i` in a word have duration `d_i` frames and token posterior
`p_i`, its descriptive score was:

```text
greedy_word_score = sum(p_i * d_i) / sum(d_i)
```

This is a duration-weighted argmax-token posterior, not a calibrated probability
that the word or boundary is correct.

### 3. Align target words and greedy CTC words

Each segment used unit-cost Levenshtein alignment. Equal and substituted pairs
were diagonal operations; target-only words were deletions; CTC-only words were
insertions. Dynamic-programming ties were resolved in this order:

```text
equal, substitution, deletion, insertion
```

The output retained every equal, substitution, deletion, and insertion
operation. It did not merge a CTC-only span into Parakeet text.

For a paired target/CTC word with both spans present, boundary disagreement was:

```text
boundary_delta_ms = max(
  abs(forced_start_ms - greedy_start_ms),
  abs(forced_end_ms   - greedy_end_ms)
)
```

### 4. Label CTC-only spans without claiming truth

An insertion's local target boundary was the next alignment operation with a
target index; if none existed, it was one position after the previous target
index; if neither existed, it was zero. Up to two target words before and three
at/after that boundary formed the local context.

The insertion hint was assigned as follows:

```text
repetition_candidate   if inserted word exactly equals a local target word
partial_word_candidate if length >= 2 and inserted word is a proper prefix
                         of a local target word
unmatched_audio_span   otherwise
```

These labels are triage hints only. They are not human truth, and they did not
authorize text replacement or boundary acceptance.

### 5. Build synthetic calibration rows

The frozen synthetic truth words were sorted by start and end time, then
unit-cost aligned to the 43 calibration target words. Only equal lexical pairs
received truth timings. Each target row carried, where available:

- whether target and greedy CTC agreed exactly;
- the CTC edit operation;
- greedy word score;
- existing forced-path score;
- greedy-versus-forced boundary disagreement;
- greedy onset and offset error against synthetic truth; and
- forced-span onset and offset error against synthetic truth.

Errors were absolute:

```text
onset_error_ms  = abs(candidate_start_ms - truth_start_ms)
offset_error_ms = abs(candidate_end_ms   - truth_end_ms)
```

### 6. Exhaustively search the rule grid

The calibration grid crossed:

- exact lexical agreement required: `true` or `false`;
- accepted boundary source: greedy CTC span or existing Parakeet-text forced
  CTC span;
- minimum greedy score: no threshold plus every unique observed score;
- minimum forced score: no threshold plus every unique observed score; and
- maximum boundary disagreement: no threshold plus every unique observed
  disagreement.

There were 43 unique greedy scores, 43 unique forced scores, and 3 unique
boundary-disagreement values, so the corrected search evaluated exactly:

```text
2 * 2 * 44 * 44 * 4 = 30,976 rules
```

When exact agreement was required, substitutions were rejected. When it was
optional, substitutions could supply paired spans but remained explicit
disagreements. Rows missing a required score or boundary disagreement were
rejected by the rule. If any accepted row lacked onset or offset truth, the
entire candidate failed the fully-scored requirement and was not timing-safe.

A rule was `timingSafe` only when it accepted at least one row, every accepted
row had both timing errors, the maximum onset/offset error was at most 120 ms,
both medians were at most 40 ms, and both p95 values were at most 120 ms. A
timing-safe rule was `feasible` only when rejection was also at most 5%.

For `n > 0`, p95 used the nearest-rank order statistic:

```text
p95_index_zero_based = ceil(0.95 * n) - 1
```

Candidate ordering preferred a feasible rule, then more accepted rows, then the
smaller of the candidates' worst onset/offset p95, then lower rejection. In this
experiment there was no timing-safe candidate to order.

### 7. Freeze the selected rule

Because no nonempty candidate was timing-safe, the evaluator emitted this
deliberately impossible sentinel:

```json
{
  "requiresExactLexicalAgreement": true,
  "minimumGreedyScore": 1.1,
  "minimumForcedScore": 1.1,
  "maximumBoundaryDeltaMs": 0,
  "acceptedBoundarySource": "none",
  "interpolationAuthorizesEditing": false
}
```

Scores are posterior-derived and do not exceed 1, so `1.1` forces rejection.
This sentinel is a representation of “no adequate calibrated rule,” not a
learned threshold recommendation.

### 8. Evaluate frozen real-footage evidence

Only after rule selection did the evaluator open the Producer-frozen real
reference. The reference was aligned separately to Parakeet targets and greedy
CTC words. The frozen 80-word timing subset was scored against accepted
boundaries. A boundary was “false confident” when either onset or offset error
exceeded 120 ms.

The evaluator also reported an unfiltered diagnostic for timing-subset words
where the Producer reference, Parakeet, and CTC all agreed lexically. This raw
diagnostic did not override the calibration result.

### 9. Adjudicate marked disfluency events

Fourteen Producer-marked events were carried into an explicit event ledger. An
event was first checked for exact preservation in the Parakeet/reference lexical
alignment and then in the CTC/reference alignment.

When every event token had frozen human timing, CTC preservation was reassessed
inside a window extending 120 ms before the earliest event start and 120 ms
after the latest event end. Exact contiguous event tokens confirmed a match. For
the marked repeated-word event only, a same-CTC-token run of the marked length
also confirmed occurrence while preserving the lexical disagreement. Nothing
was rewritten to the reference text.

Each event received exactly one status:

- `parakeet_preserved`;
- `ctc_disagreement_preserved`; or
- `explicitly_missing_or_ambiguous`.

The written issue criterion considered explicit missing-event reporting
sufficient for event visibility. The implemented final `adequate` predicate was
stricter: in addition to requiring every gate, it required that no event have
the `explicitly_missing_or_ambiguous` status. This extra condition did not
determine the outcome because the boundary and coverage gates already failed.

## Complete aggregate results

### Synthetic calibration comparison

| Measure | Result |
| --- | ---: |
| Segments | 8 |
| Target words | 43 |
| Greedy CTC words | 45 |
| Equal operations | 37 |
| Substitutions | 6 |
| Deletions | 0 |
| CTC-only insertions | 2 |
| Comparable retained-greedy parity failures | 0 |

The unthresholded baselines were:

| Lexical mode | Boundary source | Accepted / 43 | Onset median / p95 | Offset median / p95 | Boundaries above 120 ms |
| --- | --- | ---: | ---: | ---: | ---: |
| Exact required | Greedy CTC | 37 | 74 / 129 ms | 93 / 135 ms | 7 |
| Exact required | Forced CTC | 37 | 74 / 129 ms | 93 / 135 ms | 7 |
| Disagreement allowed | Greedy CTC | 43 | 74 / 133 ms | 93 / 133 ms | 9 |
| Disagreement allowed | Forced CTC | 43 | 73 / 114 ms | 93 / 133 ms | 7 |

Across all 30,976 threshold/source/agreement combinations, **zero nonempty
rules were timing-safe**. Therefore zero were feasible at the 5% rejection
ceiling. The final sentinel accepted 0, rejected 43 (100%), and retained null
onset/offset statistics.

### Full real-source comparison

| Measure | Result |
| --- | ---: |
| Retained Parakeet words | 439 |
| Greedy CTC words | 467 |
| Equal operations | 370 |
| Substitutions | 69 |
| Deletions | 0 |
| CTC-only insertions | 28 |
| CTC-only partial-word candidates | 2 |
| CTC-only unmatched-audio spans | 26 |
| CTC-only repetition candidates | 0 |
| Retained segments | 32 |
| Comparable retained-greedy parity failures | 0 |

The absence of deletion operations means every Parakeet target was paired as
either an equality or substitution in this minimum-edit alignment; it does not
mean every spoken word was recognized.

### Frozen real timing subset

| Measure | Result |
| --- | ---: |
| Human-timed reference words | 80 |
| Three-way lexical agreements with comparable raw spans | 54 |
| Raw onset median / p95 | 36 / 124 ms |
| Raw offset median / p95 | 37 / 175 ms |
| Raw boundaries with onset or offset above 120 ms | 7 |
| Final accepted Parakeet words | 0 of 439 |
| Final rejected or unaligned Parakeet words | 439 of 439 (100%) |
| Final accepted timed words | 0 of 80 |
| Final accepted timing statistics | Null; empty set is not success |

On these 54 exact-agreement rows, greedy and existing forced-span diagnostics
were numerically identical. Their medians met the 40 ms target, but p95 onset
and offset exceeded 120 ms and seven boundaries exceeded the hard 120 ms cap.

### Marked event ledger

| Measure | Result |
| --- | ---: |
| Total marked events | 14 |
| Abandoned-phrase events | 13 |
| Repeated-word events | 1 |
| Preserved by Parakeet | 4 |
| Preserved as explicit CTC disagreement | 1 |
| Explicitly missing or ambiguous | 9 |

The one repeated-word event was not preserved by Parakeet. It was confirmed in
the frozen timing window as a three-token CTC repeat with the CTC lexical token
left unchanged. The evaluator did not substitute the reference token.

### Gate outcomes

| Gate | Result | Reason |
| --- | --- | --- |
| Every marked event explicit | Pass | All 14 have a ledger status |
| No accepted boundary above 120 ms | Fail | No nonempty calibrated accepted set |
| Median onset/offset at most 40 ms | Fail | No accepted timing observations |
| p95 onset/offset at most 120 ms | Fail | No accepted timing observations |
| Rejection at most 5% | Fail | 100% rejected or unaligned |
| Calibration independent | Pass | Synthetic-only rule selection |
| No reference-text repair | Pass | Hypotheses and disagreements remain separate |

Final result: **no adequate selection**.

### Runtime and peak memory

| Run | Initialization | Inference stages | Total | Peak resident memory |
| --- | ---: | ---: | ---: | ---: |
| Retained Parakeet real-source baseline | 3.657 s | VAD 1.895 s; recognition 19.485 s | Not recorded as one combined field | 1,013,415,936 bytes |
| Corrected synthetic CTC rerun | 1.826 s | Emissions 6.669 s | 13.645 s | 923,422,720 bytes |
| Corrected real-source CTC rerun | 1.391 s | Emissions 49.323 s | 54.178 s | 941,883,392 bytes |

These are single observed process measurements, not benchmarks with variance or
confidence intervals. Peak-memory semantics are the macOS process maximum
resident set in bytes.

## Verification performed

- Thirteen private unit tests passed. They cover CTC collapse including repeats
  separated by blanks, word-span construction, deterministic repeated-word
  alignment, local insertion context, non-truth hint classification, retained-
  text parity semantics, exact-versus-optional lexical filtering, both boundary
  sources, independent rule selection, empty-metric behavior, hard-boundary
  counting, and timed repeated-event adjudication.
- Both final inference runs ran with network access denied.
- The 8 synthetic and 32 real segments completed.
- Every comparable regenerated greedy CTC string matched the retained Issue #51
  greedy string; there were zero parity failures. A segment with no retained
  greedy field is “not applicable,” not a parity success or failure.
- The evaluator asserted that the real reference was frozen, timing verification
  was complete, and disfluency review was complete before scoring.
- Repository validation passed with 141 contract tests, 1 tooling test, 6
  progress tests, 23 roadmap tests, and 175 Python tests.

## Post-acceptance corrections

The original accepted aggregate conclusion was rechecked while preparing this
handoff. Two private-harness defects were corrected and covered by regression
tests:

1. CTC insertion hints had looked near the start of each segment because an
   insertion has no target index. They now use the insertion's local alignment
   boundary. This changed only the descriptive real CTC-only split from 1
   partial-word candidate plus 27 unmatched spans to 2 plus 26. Total
   insertions, timing, events, and the decision were unchanged.
2. The exact-agreement predicate had mistakenly allowed substitutions. It now
   accepts only rows whose explicit exact-agreement flag is true. The corrected
   30,976-rule search still found zero nonempty timing-safe candidates, so the
   selected fail-closed rule and final conclusion were unchanged.

Fresh immutable synthetic, real, and evaluation outputs were produced after
both corrections. The aggregate results in this document are from those final
corrected outputs.

## Interpretation

This CTC profile is useful as a recall alarm: it surfaced explicit extra spans
and retained evidence of the one repeated-word event that Parakeet omitted. It
is not safe boundary authority under the tested design. The score thresholds
and agreement checks could not separate a useful nonempty set from boundary
outliers on independent calibration data.

The result rejects this bounded combination, not CTC generally. In particular,
it does not show that another acoustic boundary estimator, a differently
trained recognizer, better calibration data, or richer posterior features would
fail.

## Limitations and threats to validity

1. **Inherited segmentation.** CTC decoded only inside Parakeet/Silero segment
   anchors. Speech omitted outside those anchors was invisible to the test.
2. **Synthetic target is not fresh recognition.** Calibration target text came
   from the frozen corpus/alignment path, not an independent Parakeet run, so
   recognizer-disagreement prevalence is not naturally reproduced.
3. **Synthetic acoustics.** The 43-word corpus is small and may not represent
   conversational boundary shapes, disfluencies, overlap, noise, or speaking
   rate in real productions.
4. **English-only model.** No other language or accent profile was tested.
5. **Single platform and run.** Runtime was observed once on x86_64 CPU; no
   Apple Silicon or variability claim is possible.
6. **Uncalibrated scores.** Greedy token posterior and existing forced-path
   score are model-internal ranking features, not calibrated correctness
   probabilities.
7. **Alignment dependence.** Unit-cost edit alignment and its tie order affect
   which repeated or ambiguous token is paired. Alignment equality is not proof
   of acoustic identity.
8. **Sparse human timing.** Only 80 real reference words had frozen human
   timings; only 54 formed the raw three-way-agreement diagnostic.
9. **Event adjudication differs by evidence.** Fully timed events use a local
   ±120 ms window. Events lacking complete timing rely on global lexical
   alignment, which is weaker evidence of local acoustic occurrence.
10. **Insertion hints are heuristic.** Prefix and local-repeat labels are not
    validated partial-word or repetition truth.
11. **No statistical uncertainty.** Medians, p95 values, and failure counts are
    descriptive. No confidence intervals, resampling, or power analysis was
    performed.
12. **Stricter event predicate than the written gate.** The final adequacy
    predicate disallowed any missing/ambiguous event even though the issue text
    allowed an event to be explicitly reported missing. This did not affect the
    observed decision, but a follow-up should resolve the policy before testing.

## Candidate next approaches for evaluation

An external evaluator should consider these as separate hypotheses, not as
preapproved scope:

1. Build a larger, independently human-timed natural-speech calibration set
   with disfluencies and difficult boundaries. Keep it disjoint from the final
   real evaluation and specify sample-size/power or confidence goals first.
2. Test a boundary-first acoustic estimator rather than treating a recognizer's
   greedy character extent as a word boundary. Require license, model size,
   offline runtime, memory, and packaging evidence before acquisition.
3. Evaluate selective prediction with calibrated risk control, such as
   conformal or held-out coverage/error bounds, rather than choosing thresholds
   from every observed score in a 43-word sample.
4. Add acoustic features that may explain boundary failure: blank-transition
   shape, posterior entropy/margin, local energy, voicing, duration, proximity
   to a VAD edge, and agreement across independently segmented passes.
5. Run a second segmentation path or full-source streaming decoder so recall
   evidence is not limited by inherited Parakeet/VAD anchors.
6. Keep recall and boundary decisions separate: CTC disagreement may trigger a
   review region while a different, calibrated component supplies boundaries.
7. Test a boundary ensemble only if it has explicit abstention and is calibrated
   on independent natural speech; simple agreement between correlated CTC paths
   is not sufficient.
8. Define language/profile-specific acceptance. Do not extrapolate this English
   result or its thresholds to other languages or acoustic domains.

## Requested response from another LLM

Please return:

1. A validity audit separating implementation defects, statistical weaknesses,
   data leakage risks, and external-validity limits.
2. Any conclusion in this document that is not supported by the described
   evidence, with the exact reason.
3. A ranked list of at most three next approaches, scored for expected
   information gain, implementation cost, privacy risk, offline feasibility,
   and probability of meeting both timing and 95% coverage gates.
4. A minimally sufficient next experiment for the top approach: data split,
   ground truth, features/model, calibration method, metrics, stopping rule,
   runtime/memory evidence, and failure-reporting format.
5. Explicit safeguards against reference-text repair, inherited-segmentation
   blindness, empty-set success, threshold overfitting, and unreported omitted
   speech.

Do not assume access to the redacted transcript, media, per-word timing rows, or
private hashes. If those are necessary for a proposed analysis, state the
minimum additional aggregate or blinded evidence required rather than asking
for the private source material.
