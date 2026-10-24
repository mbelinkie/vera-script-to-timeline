# Speech provider shortlist: timing first (2026-10-24)

Read-only research for Matthew's timing-first narration-provider decision.
No new accounts, provider calls, private uploads, roadmap changes or dispatches.
Vendor docs establish metadata availability, not acoustic accuracy. Prices were
checked on 2026-10-24; promotions, accounts and model availability can change.

## Recommendation

Re-scope paused #289 instead of creating an overlapping study: choose a
provider/model that passes VERA's word-timing requirements and improves on
Polly's naturalness and pronunciation. Recovering Fish is an optional route,
not the required outcome. Preserve and reuse its existing samples and findings.

First test ElevenLabs and Inworld, with Fish and Polly as existing controls;
add Cartesia if those do not produce a clear winner. Keep MiniMax and Qwen as
reserves. Gemini is a quality contender but needs a separate alignment stage,
so it is not the shortest timing-first path. These are research recommendations,
not approval to spend or a claim that any alternative passes VERA's gates.

The [Artificial Analysis provider-voice arena](https://artificialanalysis.ai/text-to-speech/leaderboard/provider-voice)
currently places Eleven v4/Turbo, Qwen 3.1 Plus, Cartesia Sonic 3.6, Gemini 3.8
Flash TTS and Inworld TTS-2 among its leading listener-preference models. Fish
Drama 3 also ranks ahead of Fish S2.1 Pro there. This helps select audition
candidates; it measures neither timing accuracy nor Matthew's preferred voice.

## Comparable API costs

For comparison only, ten minutes means 1,500 English words / **9,000 ASCII
characters**. Actual duration varies with delivery. One million characters
means approximately 18.5 hours at that assumption. UTF-8 byte billing equals
character billing only for ASCII. Amounts below exclude tax, account minimums,
retries, cloning, storage and any separate alignment; use paid list rates unless
a promotion is explicitly identified.

| Provider / model | Published API usage rate | Approx. 10-minute generation | Timing route |
| --- | --- | --- | --- |
| Polly Neural, current VERA baseline | $16/M chars audio + $16/M marks = **$32/M** | **$0.29** | Separate native word-start speech marks; not native word ends. |
| Fish S2.1 Pro / Pro Free | **$15/M UTF-8 bytes / $0** | **$0.14 / $0** | Native streamed word/segment starts and ends; existing VERA failure cases still need resolution. Free announcement runs through Nov 30, 2026. |
| Fish Drama 3 | **$50/M bytes**, launch **$10/M** through Nov 12, 2026 | **$0.45 list / $0.09 promotional** | Do not assume S2 timing compatibility; exact model/endpoint needs a feasibility probe. |
| Eleven v4 Turbo / v4 | **$40 / $80 per M chars** | **$0.36 / $0.72** | Character alignment from timestamp APIs; dialogue timestamp endpoint exists. Verify exact model/endpoint, original/normalized mapping and chunk offsets. |
| Inworld TTS-2 Flash / TTS-2 | On-demand **$15 / $25 per M chars** | **$0.14 / $0.23** | Native word or character start/end alignment. |
| Cartesia Sonic 3.6 | Pro **$5/month / 100K chars**; effectively **$50/M** if fully used | **$0.45 allocated** | Native word and optional phoneme alignment. $5 is the monthly payment, not a $0.45 standalone purchase. |
| MiniMax Speech 2.8 Turbo / HD | **$60 / $100 per M chars** | **$0.54 / $0.90** | Native word-level subtitle timing. |
| Qwen Audio 3.1 TTS Plus | Singapore **$30/M chars** | **$0.27** | Streaming word timestamps; exact English voice/model compatibility must be established before admission. |
| Gemini 3.8 Flash TTS | **$0.50/M input text tokens + $9/M audio tokens** through Dec 31, 2026 | **$0.135 + text input** | Documented TTS output is audio-only; separate alignment required. Jan 1 rates double. |

Cost sources: [AWS](https://aws.amazon.com/polly/pricing/),
[Fish](https://docs.fish.audio/developer-guide/models-pricing/pricing-and-rate-limits),
[Fish free-period announcement](https://fish.audio/blog/s2-1-pro-free-api/),
[ElevenLabs](https://elevenlabs.io/pricing/api),
[Inworld](https://inworld.ai/pricing), [Cartesia](https://www.cartesia.ai/pricing),
[MiniMax](https://platform.minimax.io/docs/pricing/overview),
[Alibaba](https://www.alibabacloud.com/help/en/model-studio/model-pricing),
[Google](https://ai.google.dev/gemini-api/docs/pricing).
Google's 25 audio tokens/second gives 600 × 25 × $9/1M = $0.135.
This reconciles the repo's Polly baseline against current AWS prices: audio
and marks are separately billed, so comparing audio-only $16/M is misleading.

Inworld offers $0/month on-demand access; optional credit subscriptions begin
at $25/month. Cartesia also has 20K free monthly credits; commercial use is
listed on paid Pro. ElevenLabs lists usage prices, but voice/account access and
44.1kHz PCM/WAV tier restrictions must be checked before assuming no subscription
cost. MiniMax uses a funded balance. New account, funding or paid-tier needs
remain explicit budget decisions, not implied by this comparison.

## Proposed bounded test for #289

1. **Cheap eligibility probe:** pin model, voice, endpoint and audio format;
   obtain matching audio plus native timing on public synthetic English text.
   Verify licensing/account requirements before calls. Avoid implementing a
   production adapter for every provider just to compare them.
2. **Timing is the pass/fail gate:** complete authored-text coverage and
   normalization mapping; no invented, reversed or unresolved tied word starts;
   valid bounds against decoded audio; correct chunk offsets and silence.
   Evaluate independently against acoustic boundaries, not the same aligner
   used to produce candidate timing. Report median/p95/worst errors and failure
   counts. Reuse VERA's actual tolerances; don't invent a more lenient pass bar.
3. **Repeat and stress finalists:** reuse #289's short/medium/long strata and
   repeated generations, including numbers, names, acronyms, contractions,
   repeated words, pauses and regeneration. Reject incorrect spoken wording,
   not just malformed metadata. Compare native timing separately from any
   recovery/alignment pipeline; never disguise recovered timing as native.
4. **Audition only timing passers:** Matthew compares naturalness and
   pronunciation blind. Pronunciation dictionaries are useful only if timing
   still maps back to the original authored script. A decimal timestamp is not
   evidence of sub-frame accuracy or a guaranteed safe cutting boundary.
5. **Conclude, don't build a platform:** recommend a winner and fallback,
   actual spend, latency, timing error/failures, pronunciation limitations and
   smallest integration step. An alternative provider may need a separate
   bounded production integration before #275 resumes; do not claim a throwaway
   comparison script is that integration.

Existing #289 authorization is limited to its recorded Polly cap and free Fish
calls. This proposal does not authorize paid alternatives or private uploads.
No issue was edited and no owner was instructed to resume during this research.

Additional timing references: [Fish streaming](https://docs.fish.audio/api-reference/endpoint/openapi-v1/text-to-speech-stream-with-timestamps),
[ElevenLabs TTS timestamps](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps),
[ElevenLabs dialogue timestamps](https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps),
[ElevenLabs forced alignment](https://elevenlabs.io/docs/api-reference/forced-alignment/create),
[Qwen HTTP API](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-http-api),
[Qwen voice compatibility](https://www.alibabacloud.com/help/en/model-studio/qwen-audio-tts-voice-list),
[Gemini audio-only TTS](https://ai.google.dev/gemini-api/docs/speech-generation).

## Three-provider API detail

| Provider / current model IDs | Native timing in the documented API | Public character price and plan model | Pronunciation controls |
| --- | --- | --- | --- |
| **Inworld Realtime TTS-2** — `inworld-tts-2`; cost tier `inworld-tts-2-flash` | `POST /tts/v1/voice` accepts `timestampType: WORD` or `CHARACTER`; response has ordered word/character arrays with start and end times in seconds. TTS-2 adds phonetic details on word alignment. Flash also has timestamp alignment per release notes. Sync endpoint accepts 2,000 UTF-16 code units; streaming accepts 4,000. | On-demand: TTS-2 **$25/M chars**, Flash **$15/M**; includes up to 70 minutes free. Paid plans start at **$25/month**, issued as $25 usage credits: Creator $20/$10 per M; Builder $17.50/$9; Developer $15/$8; Growth $12.50/$7 (TTS-2/Flash). Overage uses the plan rate. Enterprise is custom. Pricing lists timestamps as a feature and no separate timestamp charge. | Inline English IPA pronunciation; TTS-2 also supports bracketed natural-language delivery steering. |
| **Cartesia Sonic 3.6** — `sonic-3.6`; immutable snapshot `sonic-3.6-2026-08-27` | `POST /tts/sse` with `add_timestamps: true` emits word-level timing events; optional `add_phoneme_timestamps: true` emits phoneme timing. WebSocket also returns word start/end arrays in seconds. No character-level alignment documented. API exposes normalized-versus-original timestamp selection. | 1 credit = 1 character; free includes **20K credits/month**. Pro starts at **$5/month** with 100K credits and a commercial-use license; Startup **$49 / 1.25M** and Scale **$299 / 8M**. Published overage rates are Pro **$65/M**, Startup **$45/M**, Scale **$38/M credits**. Pricing does not list an extra timestamp fee. Enterprise custom. | Reusable pronunciation dictionaries map text to pronunciation; TTS request references a dictionary ID. |
| **MiniMax Speech 2.8** — `speech-2.8-hd`, `speech-2.8-turbo` | HTTP `POST /v1/t2a_v2` supports `subtitle_enable` plus `subtitle_type: word` for word-level subtitles on both 2.8 models. `word_streaming` is only for streamed requests; non-streaming returns a subtitle file. No character-level timing is documented. Public API reference does not specify numeric timestamp precision or alignment accuracy. | Pay-as-you-go: HD **$100/M chars**, Turbo **$60/M**; usage draws from a funded API balance. Optional monthly/yearly audio/video resource packs advertise lower unit pricing, but the linked public overview does not state a minimum or pack rate. The public TTS price table lists no timestamp surcharge. | `pronunciation_dict` substitutions, inline IPA/Pinyin/Jyutping, explicit `<#seconds#>` pause markers, and speed/volume/pitch controls. |

### Timing-first order

1. **Inworld** is the strongest docs-only fit for this use: its synchronous JSON API exposes both word and character timing in one response, and Flash is listed with timestamp alignment at $15/M on demand. Its short single-request text cap is a practical caveat for long blocks.
2. **Cartesia** is a good alternative when phoneme boundaries are useful. Its TTS APIs expose word and optional phoneme events, with word-level but no documented character-level mapping. The published paid usage cost is above the existing Polly benchmark at scale.
3. **MiniMax** provides the required native word granularity, but no character timing is documented and its published TTS rates are much higher. Its static subtitle-file output is simpler to batch, while streaming word subtitles are cumulative and need replacement within each segment.

“Precision” here means only the API's representation: Inworld reports times in
seconds, Cartesia reports numeric word/phoneme start/end times in seconds, and
MiniMax specifies word-level subtitle granularity without publishing a numeric
precision in the cited API reference. None of these docs demonstrate that a
returned boundary is accurate against the waveform. A timing bake-off would
need fixed text/audio fixtures and human or forced-alignment adjudication.

The accepted Slice 1.2 plan also used **$32/M characters** for Polly Neural
audio plus speech marks (dated 2026-08-25), consistent with the current check
above. Provider Arena preferences were not treated as timing-accuracy evidence.

## Official sources

- Cartesia: [Sonic 3.6 model and snapshot](https://docs.cartesia.ai/build-with-cartesia/tts-models/latest), [TTS SSE endpoint and timing fields](https://docs.cartesia.ai/api-reference/tts/sse), [TTS WebSocket timing response](https://docs.cartesia.ai/api-reference/tts/websocket), [pronunciation dictionary API](https://docs.cartesia.ai/api-reference/pronunciation-dicts/create), [pricing](https://www.cartesia.ai/pricing).
- Inworld: [TTS model IDs and features](https://docs.inworld.ai/tts/tts-models), [synchronous synthesis API](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech), [TTS-2 Flash release note](https://docs.inworld.ai/release-notes/tts), [custom pronunciation](https://dev.docs.inworld.ai/tts/capabilities/custom-pronunciation), [pricing and credit tiers](https://inworld.ai/pricing).
- MiniMax: [TTS HTTP API](https://platform.minimax.io/docs/api-reference/speech-t2a-http), [TTS WebSocket API](https://platform.minimax.io/docs/api-reference/speech-t2a-websocket), [official pricing overview](https://platform.minimax.io/docs/pricing/overview).
- Existing Polly comparison anchor: [accepted Slice 1.2 plan](../plans/slice-1.2-voice-cache.md).
