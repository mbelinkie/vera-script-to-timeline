# #289 Sweden narration comparison: Inworld selected

Decision, 2026-10-24: **select Inworld TTS-2 with Arthur**. The Producer reviewed
Arthur's complete first passage and accepted the final long repeat as sounding
great. No further listening is required for this bounded provider decision.
Ashley and Arthur each have three independently generated full passages; all
twelve Inworld assets pass shared narration admission/projection and the v2
compiler through a capture-replay provider. Repeat word boundaries are not all
human-verified, and this sample does not establish a production failure rate.

The Producer now explicitly requests making Inworld the product default, with
the voice selected through configuration rather than hardcoded, then restarting
#275 using that supported path. That is a separate implementation ticket for
the steward to create/dispatch. The live Inworld product/CLI adapter is not
implemented here; #275 remains blocked until that integration lands.

| Candidate/configuration | Timing and speech conclusion | First passage generation / audio | First passage reservation |
| --- | --- | --- | --- |
| Inworld TTS-2 / Arthur | Selected. Human-reviewed 102 starts: median correction 0 ms, p95 68 ms, worst 128 ms; 87 unchanged. Three passages have valid native structure; final repeat sound accepted. | 7.00 s / 37.26 s | $0.014550 |
| Inworld TTS-2 / Ashley | Usable baseline; better voice than Polly per Producer. Human-reviewed 102 starts: median 0 ms, p95 96 ms, worst 129 ms. Three structurally valid passages; checked repeat omission flags were false alarms. | 7.00 s / 35.14 s | $0.014550 |
| ElevenLabs v4 / Matilda | Reject tested configuration. Short clip acceptable; long review stopped after 35 words due to excluded syllables/heavy range corrections. No further repeats. | 10.27 s / 39.52 s | $0.046560 |
| Fish S2.1 Pro Free / existing voice | Reject native timing for this use: long row has four tied starts/five collapsed intervals; response and audio retained. No new repeats. | 19.03 s / 35.16 s | $0 |
| Polly neural / Joanna | Explicit supported fallback; both native rows structurally valid, new passage not human-timed. Existing voice judged less good than Inworld. No automatic fallback. | 1.08 s / 33.83 s | $0.018624 including marks |

Actual billed cost is **unconfirmed for every paid entrant**; these are
conservative reservations, not billing receipts. Wall times include transport
and decoding and are single-passage observations, not throughput guarantees.
Native Inworld timing needs no separate aligner in the tested path. Diagnostic
local MFA batches took 104.97 s for Arthur's first passage and 149.67 s for its
two repeats; those latencies do not belong in native synthesis runtime.
Word starts support anchors/highlighting; audible word ends remain unverified.
Producer listening was unblinded, with direct voice selection and final
acceptance; no blind preference result is claimed.

The finish line is reliable, compiler-usable word timing first, natural speech
and pronunciation second. Fish recovery is optional. Keep the existing owner,
branch, PR #290 and first-phase artifacts; do not rerun the old public corpus.

## Prepared input and staged execution

The private selection was checked against the authored source and local handoff:
two narration rows, in original order, 582 characters and 102 frozen tokens.
The requested opening, diacritics, punctuation and inclusive ending are preserved.
The canonical row selection, readable passage, plan and spend ledger are retained
privately outside Git. Neither the script nor its private locator belongs here.

1. One fresh complete passage per candidate: ElevenLabs, Inworld, Fish and Polly;
   preserve the two row boundaries. Verify each exact model/voice/timestamp
   endpoint and account price before enabling calls.
2. Only timing and wording passers advance to two further independent runs.
   Preserve every attempted take and rejection; do not retry until valid.
3. Verify at least one proposed usable result through supported narration
   admission/projection and the v2 compiler. Any missing production integration
   must be explicit; a throwaway comparison script is not an adapter.
4. Present a short sound/pronunciation audition only for timing passers. The
   initial blind-comparison plan was superseded by the Producer's direct
   selection of Arthur and explicit final acceptance. Producer acceptance
   applies to sound, not technical approval.

Generated-row timing supports anchors, highlighting and reconciliation. Do not
add a requirement for splicing individual generated words: edits regenerate the
row. Keep native starts/ends and acoustic-derived observations distinct.
Existing 150 ms p95 onset evaluation and 100% coverage gates remain the starting
point; report independent-reference counts, uncertainty and abstentions rather
than declaring an aligner's own output correct.

## Access and money checkpoint

| Candidate | Local access check | Revised passage status |
| --- | --- | --- |
| ElevenLabs direct TTS | Keychain credential authenticated; free account access verified | Both rows generated with v4 / Matilda |
| Inworld TTS | Keychain credential authenticated; synthesis succeeded without funding | Both rows generated with TTS-2 / Ashley |
| Fish | Existing credential; explicitly free model, no paid fallback | Both rows generated; second row rejected by existing timing adapter; response/audio retained |
| Polly | Existing AWS credential; neural audio and speech marks | Both rows generated with Joanna |

The existing ElevenLabs integration is Scribe recognition through OpenRouter;
it is not direct ElevenLabs TTS access. An OpenRouter key cannot be substituted.

- New approved allowance: **$5 additional API usage total** across newly paid
  calls and any authorized retries. Stage-1 conservative reservation:
  **$0.061110** across ElevenLabs and Inworld; this is an upper-bound reservation,
  not a claim of billed money. No account top-up or subscription was purchased.
- Original Polly cap: **$1 cumulative**, including the retained **$0.098688**
  reservation for nine prior takes, plus **$0.018624** for these two rows. The
  records do not establish actual AWS billing; keep both reservations committed.
  Conservative balance: **$0.882688**. The $5 allowance does not expand this cap.
- Fish cap remains **$0**, with no paid fallback.
- Do not create a new subscription, assume account credits, or pay a minimum
  beyond the authorized cap. Account/access requirements are prerequisites.

Only the selected text is authorized for these TTS services. Existing private
audio/media remain local; no hosted aligner, reviewer, GitHub or CI upload.
First-stage access prerequisites are resolved. Parent serializes spend; helpers
perform no provider calls. Each generation is one planned attempt, without
automatic retries. Only the Producer-selected passage was transmitted.

## Tested endpoint configuration

Inworld's synchronous `/tts/v1/voice` endpoint documents explicit
`modelId: inworld-tts-2` and `timestampType: WORD`, with native word start/end
metadata. Use an account-accessible English narration voice and lossless WAV/
LINEAR16 if the account supports it. The 2,000 UTF-16-unit row limit fits both
selected rows. Ashley and lossless 48 kHz LINEAR16 synthesis succeeded; the
account's remaining balance is not exposed by the tested endpoint.
[Inworld synthesis](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech),
[Inworld authentication](https://docs.inworld.ai/api-reference/introduction).

ElevenLabs' `/v1/text-to-speech/{voice_id}/with-timestamps` returns original and
normalized character alignment, requiring exact source mapping before grouping
into words. `eleven_v4` successfully returned timestamped audio. The researched Elara voice
was absent from the account catalogue; the available American English educational
narration voice Matilda was pinned before generation. Keep
the selected authored text unchanged. Use an approved row for any charged
compatibility attempt, record the attempt, and stop on incompatibility rather
than silently retrying another model. Avoid assuming premium 44.1 kHz PCM/WAV
access: that output format is tier restricted.
[ElevenLabs timestamp endpoint](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps),
[ElevenLabs authentication](https://elevenlabs.io/docs/api-reference/authentication).

The direct credential names are `ELEVENLABS_API_KEY` and `INWORLD_API_KEY`.
Inworld's server credential is the complete Base64 value supplied by its Portal,
sent as Basic authentication without encoding it a second time. Keys must remain
in secure local storage/environment, not Git or chat. The selected text's TTS
authorization does not require enterprise zero-retention access; do not invent
that additional prerequisite. Do record actual retention/usage terms as an
operational limitation, and keep all acoustic analysis local.

## Consumer handoff

The comparison and requested listening are complete. PR merge remains subject
to green CI. The smallest missing product step is a live Inworld transport
behind the existing narration provider seam, provider/profile/pricing and CLI
configuration, secure credential loading, and configurable voice selection.
Reuse the tested exact source-piece mapping, native 48 kHz samples, strict
interval validation and capture-isolated proof. Keep model/voice/settings in
cache identity; preserve existing explicit Polly/Fish routes and fail-closed
behavior. Arthur is the currently selected configuration value, not a transport
or compiler constant. No additional provider research or custom voices are
required for that work.

Only after the new route/default is merged and green should #275 resume through
its supported fresh/cached/one-row-change workflow with Inworld. Preserve the
earlier Fish failures and original assets; do not call captured replay a fresh
live run. The benchmark owner must carry forward applicable text, spending and
credential authorization. The Producer said he will fund the account; this is
not a verified balance or an unlimited spending authorization. No Resolve run,
benchmark restart or default mutation occurred in this comparison.


## Stage-1 timing observations

Each provider received the same two exact authored rows. This is one passage per
provider, not a reliability-rate estimate. Native-to-source mapping covers all
102 frozen tokens for every provider. Coverage establishes source correspondence,
not that the audio actually speaks every word correctly.

| Candidate | Native structure, first passage | Native/MFA onset comparison, pooled |
| --- | --- | --- |
| ElevenLabs v4 / Matilda | Both rows have finite, increasing, in-bounds lexical word starts | 102/102 compared; median 40 ms, p95 260 ms, worst 590 ms |
| Inworld TTS-2 / Ashley | Both rows have finite, increasing, in-bounds lexical word starts | 102/102 compared; median 10 ms, p95 90 ms, worst 120 ms |
| Fish S2.1 Pro Free / existing voice | Short row passes; long row fails with four tied adjacent starts and five collapsed word intervals | 101/102 compared; median 20 ms, p95 50 ms, worst 320 ms; one local reference abstention |
| Polly neural / Joanna | Both rows have finite, increasing, in-bounds word starts; native word ends unavailable | 102/102 compared; median 40 ms, p95 133 ms, worst 263 ms |

Differences are rounded diagnostic disagreements against **unreviewed MFA**,
not measured errors against human truth. The 150 ms p95 gate cannot establish
actual acoustic accuracy without an independently checked reference. This table
records the initial stage before the human reviews and repeats below.

The local batch used engine-only 16 kHz copies, retained original untrimmed audio,
recorded exact offsets and English numeral expansions, and preserved diacritics.
MFA ran with networking denied and cached English models. It placed 407/408 token
occurrences; the first long-row Fish reference falls 0.3125 ms before original
zero after global millisecond quantization and is retained as an explicit
out-of-bounds abstention. No time was clamped or shifted to obtain coverage.

ElevenLabs' final punctuation interval extends 80 ms past decoded audio on both
rows. Lexical word edges remain within audio. The original MP3s and unchanged
provider timing are retained alongside untrimmed PCM-decoded review WAVs. Inworld's
word arrays include spaces, punctuation and split word pieces; exact character
spans group pieces belonging to one source word without subdividing phrases.

The private Audition pack contains all eight review WAVs, native marker
prefills, separate MFA context ranges, flagged onset alternatives, immutable
hashes and canonical token correspondence. Descriptions say NOT HUMAN VERIFIED.
The recommended first review is Inworld's two rows; clean-looking starts need
manual confirmation as well as flagged disagreements. Native ends are never
claimed to be verified audible ends, and Polly markers remain onset points.


| Candidate | First-passage generation wall time | Audio duration | Conservative reservation |
| --- | --- | --- | --- |
| ElevenLabs | 10.27 s | 39.52 s | $0.046560 |
| Inworld | 7.00 s | 35.14 s | $0.014550 |
| Fish | 19.03 s | 35.16 s | $0 |
| Polly | 1.08 s | 33.83 s | $0.018624, audio plus speech marks |

These are one sequential two-row attempt each, including transport and local
response decoding; they are not throughput benchmarks. Ordinary 1.0x settings
produce different speaking rates across voices. MFA's eight-row batch took
141.79 s, including local execution setup. Actual provider billing remains
unconfirmed; reservations remain committed even where included credits may
cover usage. No production service-level or retention guarantees are inferred.


## Checkpoint verification

All eight review-audio hashes and 32 marker-file hashes/inventories were checked.
The 14 focused study/analyzer tests pass, as do all 1,772 non-slow Python tests,
Python lint/format and mypy. Generated types, TypeScript lint/type checks, the
other workspace tests and all four fast tooling groups pass. The initial
`validate:fast` invocation failed on a 5-second timeout in an unrelated
qualification-output-proposals test; its focused 30-test file passes on rerun.
Remaining fast groups were completed individually. No full-suite Mac run was
performed. Final-diff Claude review, CI/merge and issue completion remain pending;
this is a pushed manual-review checkpoint. The existing #256 tracks fast-suite
runtime. No code-check result establishes acoustic accuracy.


## Producer review and finalist selection

The Producer reviewed both Inworld first-generation rows (102 word starts) and
prefers its voice to Polly. Native onset corrections: 16/102 starts changed,
median absolute correction 0 ms, p95 96 ms, maximum 129 ms; 86 starts were left
unchanged within the reported complete-row reviews. Thirteen starts moved later
and three earlier. The Producer observed phrase starts arriving early in silence,
but judged the original timing usable without adjustment. This is evidence for
these two clips, not a production reliability rate. Reviewed exports and every
start/end delta are retained privately by hash; no audible-end evidence is
inferred. One exported point marker and one 29 ms range overlap remain explicit
range limitations; this study's generated-row evaluation concerns word starts.

The short clip first described as Inworld was corrected by the Producer to
ElevenLabs. Its 21-start review has two onset changes (worst 299 ms). The later
ElevenLabs long-row review stopped at the authored year token, ordinal 35:
24/35 starts changed, p95 155 ms and maximum 237 ms; reviewed ends moved by as
much as 158 ms. The remaining 46 words are unreviewed. The Producer reported
whole syllables outside the native ranges and stopped rather than repairing
all of them. Every displayed original word start/end matches the returned
ElevenLabs character timing to display precision; MFA was not used to make
those native ranges.

Reject the tested **ElevenLabs v4 / Matilda native-timing configuration** from
this comparison and preserve the failure. Do not generalize this to every
ElevenLabs voice/model or start a new voice-search/custom-voice investigation.
Published usage for the tested model is $80/M characters versus Inworld TTS-2's
$25/M at On-Demand rates (3.2x); price reinforces the timing-based decision,
not the other way around. No top-up was needed.
[ElevenLabs pricing](https://elevenlabs.io/pricing/api),
[Inworld pricing](https://inworld.ai/pricing).

Inworld advances to two further independent complete-passage generations, using
the same pinned model, voice, authored rows and ordinary delivery. All four
additional rows generated successfully without retries. Across three complete
passages, native source coverage is 306/306 tokens with finite, increasing,
in-bounds starts and no tied or collapsed word intervals. Local repeat acoustic
and wording checks, the admission/compiler proof and any necessary focused
Producer follow-up are still pending. Conservative new-provider reservation
is now **$0.090210** of the cumulative $5 allowance; actual billing remains
unconfirmed. No additional Fish/Polly calls or default changes were made.


## Repeat acoustic and fidelity checks

The four additional Inworld rows each retain exact native coverage, increasing
starts, positive word intervals and audio bounds. The independent, network-denied
MFA batch placed 204/204 token occurrences in 105.41 s. Native/MFA p95 onset
differences by repeat row are 50, 90, 40 and 90 ms; worst differences are 90,
120, 100 and 110 ms. Pooled repeat p95 is 90 ms, worst 120 ms. These remain
machine disagreements. Against the 102 first-generation human-reviewed starts,
MFA itself has median 10 ms, p95 50 ms and worst 109 ms disagreement; that
calibration is specific to the reviewed first-generation audio.

Audio-only local Parakeet recognition ran with networking denied, without script
text. It flagged proper-name spelling/pronunciation variants and apparently
omitted a short phrase and a linking word in both long repeats. A 12-second
four-excerpt check, bound to original sample offsets, was reviewed by the
Producer: all flagged words are audible and acceptable in both repeats. Record
these recognition omissions as false alarms at the checked spots, not TTS
fidelity failures. This spot check does not imply a complete human review of
every repeat or establish their word-boundary times.

The repeat review pack is separate from stage 1; no reviewed export, original
capture or previous prefill was replaced. The Producer may select another
Inworld library voice; Ashley remains the measured baseline. A new chosen voice
requires fresh synthesis and timing checks, with no automatic transfer of this
voice's qualification. The same TTS-2 model and exact authored passage remain
the comparison basis.


## Captured-output admission/compiler proof and Arthur review

A study-only `InworldCaptureReplayProvider` verifies hashes for retained request,
semantic JSON input, native response and original audio. It checks explicit
model/voice identity and response/audio agreement, maps exact frozen source spans,
rejects unsafe intervals, and preserves native samples through `ProviderResult`.
A capture-specific adapter identity prevents distinct generations sharing a
synthesis cache entry. There is no network transport or live product route.

All three Ashley generations passed the real `NarrationService`, production
FFmpeg normalization/cache, exact v2 token projection, TypeScript compiler and
media-needs checks: six admitted assets, 306 projected tokens. Arthur's first
generation passed the same path: two assets and 102 tokens. These proofs use a
derived two-row document with explicit picture placeholders, preserving exact
source text, token IDs, row IDs and revisions. The original script was not
modified. This is a narration-interface proof, not the #275 full-script benchmark,
a Resolve qualification, live provider adapter or default switch.

Arthur is an available English US system voice. Its first two rows have complete
native mapping and no ties/collapses. Local MFA placed 102/102 tokens; per-row
native/MFA p95 differences are 80 and 90 ms, with worst differences 610 and 130 ms.
The Producer reviewed the short row's unchanged native prefill as accurate,
resolving the 610 ms second-word disagreement in favor of native timing. Record
this as an **MFA outlier**, not a reason to shift or reject the native start.
The long row was also reviewed as having only minor disagreements. Its validated
81-word export changes 15 starts, all later, with p95 absolute correction 82 ms
and worst 128 ms; 66 starts are unchanged. All ranges are positive, ordered,
non-overlapping and within the original audio. The review WAV's PCM matches the
retained capture. Twenty-one ends changed, at most 92 ms; no human-confirmed
audible ends or formal boundary evidence are admitted by this onset study.

Across both human-reviewed Arthur rows, 87/102 native starts are unchanged,
p95 absolute correction is 68 ms and worst 128 ms. On that same reviewed audio,
MFA has median disagreement 10 ms, p95 58 ms and worst 610 ms. Its useful typical
agreement does not make its outlier a reason to override the human review.

Two further Arthur passages were generated once each, with no retries. All four
rows retain complete native coverage, ordered positive intervals and audio
bounds (204/204 token occurrences). Both repeat generations also pass the real
admission, normalization/cache, projection, compiler and media-needs path.
Arthur now has six admitted assets and 306 projected tokens across three
independent generations; the repeat boundaries have not been manually verified.
Local MFA placed all 204 repeat token occurrences in 149.67 s. Pooled native/MFA
p95 disagreement is 80 ms, worst 580 ms; row-wise maxima are 540, 280, 580 and
100 ms. These disagreements remain diagnostic, including the short-row outliers;
the first generation's human finding does not automatically settle new takes.

Network-denied, audio-only local recognition of the repeats flags proper-name
variants and apparent omissions in generation 3's long row. These are listening
flags, not established speech failures; similar earlier Ashley omissions were
disproved by listening. The Producer listened to that complete 28.18-second row
and said it sounds great, accepting the final sound/pronunciation check. The
choice is **Inworld TTS-2 with Arthur**; no further listening, paid provider
exploration or custom-voice work is needed for this bounded comparison. This
sound acceptance does not establish every repeat word boundary.

Arthur's reservation adds $0.014550; the cumulative new-provider reservation is
**$0.133860** of $5 after both Arthur repeats, with actual billing still
unconfirmed. The original separate Polly and Fish caps are unchanged. No top-up,
paid fallback, custom voice or additional ElevenLabs generation was used.

The replay/analysis/projection focused check passes 25 tests; Ruff and the full
Python mypy check pass. All 1,782 non-slow Python tests pass in 226.23 s. The
final fast run again encountered the same unrelated five-second
qualification-output-proposals timeout; its focused 30-test file passed again,
and the remaining Python checks completed separately. The requested code-only
Claude review was
attempted with the playbook's restricted settings but could not execute because
the CLI account hit its session limit. No adversarial findings or completed
review are claimed; the playbook permits documenting unavailability and
continuing without a waiver.
