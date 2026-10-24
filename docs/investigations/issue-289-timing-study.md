# Fish/Polly timing study and retained-take recovery (#289)

Status: in progress. No recovery or provider ranking is established.

## Frozen protocol (before acoustic scoring)

Run local recovery first on the retained failed take, without synthesis. Preserve
the source audio, native response, failed assets and prior cache. Use a new output
identity; never call acoustic starts provider marks. Public model acquisition is
separate from network-denied private inference. Private inputs and per-word output
stay outside Git; only safe aliases and aggregates belong here.

Require 100% exact authored-token coverage, strictly increasing starts, positive
acoustic support within unchanged audio, and unambiguous occurrence mapping.
Omissions, additions, repeats with ambiguous correspondence, nonfinite or collapsed
intervals, out-of-bounds results and missing acoustic support refuse admission.
Recognizer and aligner scores are not calibrated confidence probabilities.

Use MFA as the recovery candidate and a structurally independent local aligner as
an error detector. Predeclare a 70 ms agreement threshold (the shared package's
existing threshold); disagreement abstains, rather than silently choosing an edge.
Agreement alone is not acoustic truth. Independently check acoustic boundaries,
including every formerly tied word, every disagreement and a systematic sample of
the remaining words. Report the checked denominator and unresolved cases. Require
checked onset p95 <= 150 ms (the existing narration evaluation gate), max <= 200 ms,
and zero admitted boundaries outside declared uncertainty. Any required boundary
without independent checked evidence remains refused. Report median/p95/max,
false-confident count, abstentions, coverage, wall time and reference limitations.
Do not call an unreviewed machine prefill human verified.

Public comparison: three original synthetic English texts, 10–20, 40–60 and
90–120 words; three independent generations per provider and text (18 takes).
Before any live request, Matthew expanded the Fish sample to ten distinct clips.
Add seven Fish-only texts with one generation each: 16 Fish takes across ten texts
and nine Polly takes across three texts (25 total). Keep paired and supplemental
denominators separate. The frozen corpus is `scripts/word-timing/issue289_corpus.json`.
Include contractions, repeats, punctuation, numerals and real Fish chunking.
Freeze texts and settings before calls. No retry-until-valid selection. Keep native,
normalized and recovered outcomes separate, and distinguish Fish audio ends from
Polly text byte offsets. Words in one take are correlated; this is exploratory,
not an estimate of production failure rates.

Polly total authorization is $1 for public text only. Preflight current official
audio-plus-marks pricing; reserve the conservative entire call cost before each
request, including uncertain failures. Parent serializes calls. Fish has a hard
$0 cap with no paid fallback. No private provider calls, Resolve or #275 benchmark
execution is part of this issue.

## Initial code-path audit

Both providers supply native starts to the shared synthesis/cache, normalization,
measurement and compiler paths. Production synthesis does not run MFA for either.
The shared `MfaAligner` refuses `reference-text` artifacts by design; the old
`scripts/word-timing/mfa_reference.py` is explicitly evaluation-only. Recovery
must use a supported explicit admission path with acoustic provenance, rather
than relabeling that evaluation bypass as production success.

## Results

### Public native-timing study, 2026-10-24

All 25 planned takes ran once. Original synthetic public texts are in the frozen
corpus; no private narration was synthesized. There was no retry-until-valid loop.
The Fish adapter made one POST per take. Polly used separate audio and speech-mark
requests with SDK `total_max_attempts: 1`; saved response IDs distinguish those two
calls, but the saved records do not include AWS's `RetryAttempts` field.

| Paired text | Whitespace words | Fish accepted / takes | Polly accepted / takes | Fish call time median [range], s | Polly call time median [range], s |
| --- | ---: | ---: | ---: | --- | --- |
| Short | 14 | 3/3 | 3/3 | 4.10 [4.02–5.37] | 0.67 [0.62–1.75] |
| Medium | 60 | 1/3 | 3/3 | 13.53 [12.57–14.79] | 1.31 [1.10–1.72] |
| Long | 109 | 0/3 | 3/3 | 17.30 [16.79–18.99] | 1.40 [1.21–1.94] |

Times surround `provider.synthesize`, including adapter processing. They are not
pure network RTT, normalization time, or end-to-end build time.
"Accepted" here means adapter-accepted native timing, not independent acoustic
verification or a completed compiler/package build.

Seven supplemental Fish texts had 3 accepted and 4 refused takes. Overall, Fish
accepted 7/16 and refused 9/16; six of ten distinct Fish texts had a refused take.
Polly accepted all 9/9 takes across its three paired texts. Every Fish refusal was
`Fish word alignment has non-increasing word starts`. Offline decoding of every
retained SSE reproduced the corresponding result. Coverage was complete even in
the refused rows: this was neither a missing-text nor an incomplete-stream failure.

Across Fish's 30 final logical chunk snapshots, 970 raw segments included 24
zero-duration intervals and 20 adjacent tied starts, with no decreasing starts.
All 20 ties mapped to adjacent authored words in the nine refused rows. The seven
accepted rows had no zero intervals or ties. Every stream had contiguous chunk
sequence numbers, continuous offsets, and final alignment duration matching its
PCM. Short rows used one logical chunk; medium two; long three. The harness's
`fishChunks` counters count SSE updates, not final logical chunks.

Raw segment counts are not source-word counts: `555-0142` and `B-14` split into
subsegments which the adapter aggregates. Polly's `8:30` is one source range.
All nine Polly word-mark sequences strictly increased and their UTF-16 ranges
matched the authored source. Polly supplies starts and text byte ranges; those
byte ranges are not audio end times.

The same Fish profile/settings were used throughout: `s2.1-pro-free`, the existing
MW1 reference, English, 100% speed, mono PCM at 44,100 Hz, `balanced` latency,
chunk length 300, `normalize:false`, temperature 0.7, top-p 0.7. Polly used Joanna,
Neural, en-US/us-east-1, 100% speed, mono PCM at 16,000 Hz and a separate word/
sentence speech-mark request. Provider model/voice revisions are not exposed;
the saved per-take provider input, profile and provenance record the actual controls.
These are different voices and performances, not time-locked recordings.

Polly's conservative audio-plus-marks reservation was **$0.098688**, below the
authorized $1 total. Actual billed cost remains unknown, not asserted equal to the
reservation. Fish's model is listed at $0; no paid Fish call or fallback was made.
[AWS pricing](https://aws.amazon.com/polly/pricing/),
[Fish pricing](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits).

### Retained-take recovery, still unaccepted

The exact failed native take was found and its refusal reproduced locally: 81
frozen words, three tied adjacent starts. Original evidence remains unchanged.
The local recognizer differed around three proper-name spans, so the ordinary
ASR/exact-match route could not certify the transcript. No invented recognition
artifact was substituted.

A full-row exact-script **evaluation candidate**, using the existing shared MFA
engine, placed all 81 words with positive, strictly ordered intervals. Independent
Qwen placed the same 81 words. Their onset differences had median 20 ms, nearest-
rank p95 40 ms, maximum 50 ms, and 0/81 above the predeclared 70 ms disagreement
threshold. MFA took 103.57 s; Qwen 94.41 s, excluding one-off runtime setup.
This is engine agreement, **not independent acoustic truth or calibrated confidence**.
Qwen returned two collapsed word intervals despite its close onset agreement;
those supports are flagged for review and are not admitted as audible word ends.
The unchanged raw PCM was wrapped for review; engine copies were resampled with
zero trim/origin shift. Network was denied for private host inference and disabled
for the Qwen container. No private provider request occurred.

At Matthew's request, prepare Audition review markers showing native, MFA and Qwen
alternatives. The retained take has 10 flagged onsets, including both words of
each tied pair. Machine ranges are prefilled candidates; their ends are not
claimed as audible-end evidence. Unchanged prefilled markers are never treated as
reviewed. Acoustic error/false-confidence/abstention counts require the independent
listening review; they are not populated from either aligner's own output.

The default provider remains unchanged. Native tied starts remain refused. The
observed corpus favors Polly's **structural timing usability** under these tested
conditions; it does not establish general acoustic superiority or a production
failure rate. #289 and #275 remain incomplete until reviewed accuracy, supported
admission/compiler proof and the tested consumer handoff are delivered.

### Paid-model side question

Fish lists paid S2.1 Pro, S2 Pro and Drama 3. It says free/paid S2.1 Pro weights are
identical; Drama 3 advertises delivery, pronunciation and pause controls. No
documented timestamp-accuracy improvement was found for a paid model, and no paid
Fish model was tested.
[Fish inference explanation](https://fish.audio/ko/blog/tts-inference-optimization-s2-pro-free/?articleLocale=en),
[Drama 3](https://docs.fish.audio/features/text-to-speech/drama-3).

### Runtime/model notices

Existing local MFA 3.4.3 (MIT), English US ARPA acoustic/dictionary 3.0.0 and G2P
2.0.0 (CC BY 4.0) were reused. Qwen3-ForcedAligner-0.6B at
`c7cbfc2048c462b0d63a45797104fc9db3ad62b7` is Apache-2.0. Model attribution belongs
with any distributed integration; no model weights are included in this PR.
[MFA model policy](https://montreal-forced-aligner.readthedocs.io/en/stable/user_guide/models/model_versions.html),
[English US ARPA model](https://mfa-models.readthedocs.io/en/latest/acoustic/English/English%20(US)%20ARPA%20acoustic%20model%20v3_0_0.html),
[Qwen model](https://huggingface.co/Qwen/Qwen3-ForcedAligner-0.6B/tree/c7cbfc2048c462b0d63a45797104fc9db3ad62b7).
