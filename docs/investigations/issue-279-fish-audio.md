# Fish Audio evaluation (#279)

Checked 2026-10-23. Fish works as an opt-in provider through the existing
`SpeechSynthesisProvider`/`NarrationService` boundary. Polly remains the default.
Sound quality and suitability for Matthew's workflow require Producer judgment;
this report does not claim a preferred voice or verified audible word ends.

## Actual service checks

All Fish calls used the existing MW1 reference
`f051ceb7fd8d47f09f63944298f589fc`, the exact `s2.1-pro-free` model header and
`POST /v1/tts/stream/with-timestamp`. No recordings, private scripts or voice
training were transmitted. The key was read locally without logging it.

The first probe preceded integration validation: HTTP 200, SSE, 44,100 Hz
16-bit mono PCM, `prosody.speed=1.1`, `normalize=false`, balanced latency.
It used this 64-byte synthetic text:

> This is a short narration test. The quick brown fox jumps twice.

The #112 63-character source/audio was not identified in the current checkout;
its historical issue comments supply the earlier Polly price comparison only.

| Probe | UTF-8 bytes | Audio duration | First transport | Complete transport | Native timing |
| --- | ---: | ---: | ---: | ---: | --- |
| Fish short, requested 1.1x | 64 | 4.408526 s | 3.138 s | 5.715 s | 7 events; 1 text chunk; 12 source words |
| Fish same text, requested 1.0x | 64 | 4.272479 s | 1.327 s | 2.856 s | 6 events; 1 text chunk |
| Fish longer paragraph, requested 1.1x | 448 | 27.811020 s | 0.560 s | 12.584 s | 20 events; 2 text chunks; 84 source words, 11 sentences |
| Polly Matthew Neural, 110% | 64 characters | 3.566000 s | not measured separately | 9.033 s including normalization | word/sentence speech marks |

The longer text exercises repeated words, a newline, contractions, `Dr.`,
`3.5 p.m.`, `café`, and `$12`. Its second text chunk starts at
17.96061224489796 seconds. Latest cumulative snapshots replaced previous
snapshots; every audio packet was appended in arrival order. The offset was
added once. Complete source coverage, monotonicity and final PCM bounds passed.

Fish accepted the native speed field but did not return an effective-speed
measurement. The independent 1.0x generation was shorter than the 1.1x one;
these stochastic takes do **not** establish a controlled 10% speed change.
Listen to the requested pacing; do not describe effective 1.1x as independently
verified. There was no local speed change or forced-alignment substitution.

The short 1.1x take contains one zero-length native segment; the long take has
two. Starts mostly fall on an approximately 80 ms grid. Those starts can drive
the existing next-word highlighting contract, but native ends are not reliable
audible-cut evidence. The adapter retains them as machine candidates and never
promotes them into verified audible ends. Quality/word tracking is pending the
listening review.

## Integration and cache behavior

The adapter requests PCM explicitly, so there is no codec-delay guess. It maps
Fish labels back to original source offsets, joins subsegments of contractions,
decimals and abbreviations, and preserves source punctuation in sentence spans.
Unmapped words, phrase-only timing, missing snapshots, overlapping/out-of-bounds
timing and incomplete streams refuse rather than publishing ready synthesis.
Sentence splitting covers the tested English abbreviations; it is not a general
multilingual sentence segmenter.

Native timing is stored as samples at 44,100 Hz. The v2 projection preserves
exact rational starts through the existing provider-neutral contract; the v1
projection retains its integer-millisecond representation. Normalization produces
48 kHz mono PCM-24 and changes loudness/sample format, not speed. A live probe
exposed an old duration-check rounding bug for 44.1 kHz input: FFmpeg emits the
final partial interval as a sample. The check now uses that actual rounding;
16 kHz Polly output and historical normalization identities remain unchanged.

Retained responses were reprocessed locally after fixing source mapping and
the duration check, without extra provider calls. Both Fish assets became
ready. A final fresh request through the default Fish transport also became
ready at requested 1.1x: 10.437 seconds generation-to-normalized-audio, with
4.197458 seconds of output. Its warm pass took 0.200 seconds, reused both
layers and worked after the process credential was removed. Existing
Polly request identity, SSML/timing bytes and cache filenames remain compatible.
Fish input is stored as JSON; provider/model/voice/version/rate and generation
settings remain part of immutable synthesis identity.

An attempt marker is persisted before transport. Definite rejections such as
authentication/rate-limit errors release it, allowing a later explicit retry;
there is no retry inside a call. A definite rejection stops new calls for the
rest of that document while retaining failed placeholders and reusable cache hits. An uncertain attempt without a verified raw
cache entry cannot be automatically resent after a restart. Fish responses that
fail validation are retained with their prepared input in the immutable
`quarantine` cache. `FishProvider.decode_response` can validate retained SSE
offline after a parser/mapping fix. Reconcile this response before authorizing
any new call; never erase an uncertain marker automatically. Existing cached
audio remains reusable without credentials or another billable call. The
historical AWS campaign stays AWS-only, preserving #145's inputs and consent.

## Configuration

Set `FISH_AUDIO_API_KEY` in the local process environment using the existing
secure configuration method. Never place it in an argument, source file or log.
Keep the key separate from the script and output directories.

```sh
uv run --frozen python -m vera_timeline_agent.narration script.json \
  --cache /path/to/narration-cache \
  --voice-profile fish-mw1-s2.1-pro-free-en-us-v1 \
  --rate 110% --data-policy fish_terms_accepted \
  --max-cost-usd 0 --preflight-only
```

Use `--confirm-provider-call` in place of `--preflight-only` only for authorized
input. Fish consent is separate from `--aws-data-policy`. Private scripts still
require specific Fish transmission consent. `--model`, `--voice-id` and
`--voice-version` override configuration explicitly; they never create a voice.
Polly's existing arguments still work. Unknown models refuse before transport
because Fish documents a paid-model fallback for unknown/missing headers.

Fish currently refuses authored pronunciation overrides, lexicons, pause,
emphasis, pitch, volume changes and inline voice-control tags. It supports
explicit percentage speed from 50% through 200%. Unsupported settings are not
dropped. Authentication, rate limits, service errors and timeouts are explicit;
there is no automatic retry or provider/model fallback.

To add another provider, implement the existing protocol, return validated PCM
and source-bound timing, then register its constructor/profile/pricing in
`narration/configuration.py` with tests. Service, compiler, cache and narration
consumers need no vendor branch. There is no new frontend or provider framework.

## Cost and terms

Fish's [pricing page](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits)
lists $0 per million UTF-8 bytes for `s2.1-pro-free` and $15 for `s2.1-pro`.
These are bytes, so Unicode input is not billed like Polly character counts.
At the listed paid rate, the 64-byte sample is $0.000960 and the 448-byte sample
is $0.006720; 100,000 UTF-8 bytes is $1.50. Native timing has no separately
listed charge; account billing was not independently audited. Local processing
adds no provider fee. Retries would add usage, so none were automatic.

The four Fish requests cost $0 at the documented promotion rate. One Polly
audio-plus-marks generation was authorized under a $0.01 total cap and estimated
at $0.002048. AWS SDK retries were disabled for that comparison. The retained
Polly rate is $32 per million source characters (audio plus separately billed
marks), supported by the historical [#112 cost correction](https://github.com/mbelinkie/vera-script-to-timeline/issues/112#issuecomment-5624255388).
No paid Fish request was made.

Fish's [free announcement](https://fish.audio/blog/s2-1-pro-free-api/) currently
extends the promotion through November 30, 2026, under fair use, without latency
or uptime guarantees. It says requests may improve models and flags commercial
restrictions. The adapter refuses new free calls after that window until terms
are reverified; it does not switch to paid service. Existing cached results work.

The linked [Terms of Use](https://fish.audio/terms/) (effective August 18, 2024)
state non-commercial use generally and grant commercial use to paid users. That
older general wording and the newer free announcement do not settle every free
commercial scenario. The [Privacy Policy](https://fish.audio/privacy/)
(effective August 28, 2024) describes retention for service/business purposes;
no fixed API-request deletion period was established. Do not infer private-data
or commercial production authorization from this synthetic evaluation.

The [timestamp protocol](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech-stream-with-timestamps)
defines cumulative snapshots, offsets and framing. The [TTS format reference](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech)
defines PCM as 16-bit mono and documents the native prosody field. All linked
Fish sources were retrieved on 2026-10-23; documentation alone did not establish
the tested combination's feasibility.

## Recommendation and acceptance

Retain Fish as a configuration-selectable evaluation option. Keep Polly as
default pending Producer judgment. Native starts support preview/highlighting;
work requiring verified audible edges still uses the accepted timing-review
workflow. Effective speed, naturalness, MW1 consistency and pronunciation remain
listening judgments, not automated assertions.

Local paired playable WAVs and a word-highlighting review page accompany the
handoff; media is kept outside Git and was not published. Play both short takes,
then the long Fish take. Check voice/naturalness, pacing, pronunciation and word
tracking. Reply `Accept #279 Fish evaluation` or `Revise #279: ...`; state any
default-provider choice separately. The issue stays In review until acceptance,
and cannot be Done before the PR merges with green CI.
