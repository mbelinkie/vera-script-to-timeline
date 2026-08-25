# Slice 1.2 — Voice adapter and block asset cache plan

## Status and gate

**Authorized for implementation.** Slice 1.1 is accepted and its minimal and
torture `ScriptDocument` inputs are frozen. This plan binds Slice 1.2 before
code changes begin.

The slice remains producer-gated even under D-0008: its done condition requires
the producer to hear generated audio and observe live cache behavior. Agents may
complete implementation, automated verification, provider-independent tests,
and independent review without stopping, but may not claim that listening,
provider authorization, or a billable cloud call occurred.

## Provider evaluation and decision

Current official documentation was reviewed on 2026-08-25.

| Provider | Timing | Pronunciation | Current cost signal | Data/API tradeoff |
| --- | --- | --- | --- | --- |
| AWS Polly | Native word and sentence speech marks with millisecond starts and UTF-8 byte ranges; audio and marks are separate calls | PLS lexicons plus SSML phoneme, alias, prosody, and pauses | Standard $4/M characters or Neural $16/M for each speech or speech-mark request | Mature SDK/IAM path and low cost; no immutable hosted voice revision; AWS terms permit Polly-content improvement use unless the account/organization opts out |
| Google Cloud TTS | Timestamps only for explicit SSML marks, so the adapter must inject and map token marks | SSML phoneme and alias | Standard/WaveNet $4/M, Neural2 $16/M, Chirp 3 HD $30/M | Best documented default posture: Google says Cloud TTS does not log customer text/audio; requires a billing-enabled project and ADC |
| Azure Speech | SDK `WordBoundary` events include audio offset and input character position | SSML phoneme, lexicon, alias, prosody | Region/currency dependent; 0.5M Neural characters/month on F0 | Strong timing but a heavier native SDK/event surface; reviewed public material did not establish a clear TTS-specific retention period |
| ElevenLabs | Audio and original/normalized character start/end alignment in one response | Versioned pronunciation dictionaries and model-specific IPA/alias controls | Approximately $50–$100/M characters for the compared API models | Finest timing and simple REST; materially higher cost, default logging, and account/plan-dependent training and zero-retention controls |

Initial provider: **AWS Polly Neural**, profile
`aws-polly-joanna-neural-en-us-v1`, voice `Joanna`, engine `neural`, language
`en-US`, and default region `us-east-1`. The provider adapter records the exact
region, engine, voice ID, language, SDK/adapter versions, request IDs, input and
output hashes, and an honest `voiceVersion: provider_not_supplied`. It must not
invent immutable vendor identity. Output bytes are cached immutably so later
managed-provider drift cannot rewrite an accepted artifact.

The initial request asks Polly for 16 kHz mono signed PCM and separately asks
for word and sentence speech marks. Both requests are included in the cost
estimate. Polly's synchronous 3,000 billed-character/6,000 total-character
limit is enforced with an actionable error in this slice; chunking long blocks
is a proposed follow-up rather than an unbounded addition.

Official sources:

- [Polly speech marks](https://docs.aws.amazon.com/polly/latest/dg/speechmarks.html)
- [Polly synthesis API](https://docs.aws.amazon.com/polly/latest/APIReference/API_SynthesizeSpeech.html)
- [Polly lexicons](https://docs.aws.amazon.com/polly/latest/dg/managing-lexicons.html)
- [Polly pricing](https://aws.amazon.com/polly/pricing/)
- [Polly limits](https://docs.aws.amazon.com/polly/latest/dg/limits.html)
- [AWS Service Terms](https://aws.amazon.com/service-terms/) (updated 2026-08-20)
- [Google SSML timepoints](https://cloud.google.com/text-to-speech/docs/ssml)
- [Google Cloud TTS data logging](https://cloud.google.com/text-to-speech/docs/data-logging)
- [Azure synthesis events](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/how-to-speech-synthesis)
- [ElevenLabs timestamp API](https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps)

## Data and cost policy

- Exact active narration text may leave the local machine only through the
  producer-run temporary-narration command. Excluded narration is never sent.
- A live Polly call requires one explicit CLI attestation:
  `--aws-data-policy opt_out_confirmed` or
  `--aws-data-policy provider_terms_accepted`. There is no silent default.
  The selected value is recorded as provenance but never as a claim the agent
  independently verified.
- The CLI prints a preflight estimate from a dated, versioned pricing snapshot.
  Neural audio plus speech marks are estimated at $32/M characters as of
  2026-08-25.
- The automatic per-run ceiling is $1.00. A higher estimate fails before any
  provider call unless the producer supplies a higher `--max-cost-usd` value.
- Agents do not perform the first billable call merely because credentials are
  present. The real invocation is part of the audited producer acceptance flow.

## Bounded scope

1. Add a narrow Python `SpeechSynthesisProvider` protocol and AWS Polly adapter.
2. Parse and synthesize every `state: active` narration block independently;
   never synthesize excluded narration.
3. Preserve exact authored `block.text` as normalized plain text for this
   slice. Do not collapse whitespace or Unicode-normalize behind the accepted
   token offsets. Provider-specific SSML remains a separate byte artifact with
   its own hash and source mapping.
4. Support deterministic pronunciation entries (`alias` and `phoneme`), named
   voice/profile, block-level rate/pitch/volume, emphasis spans, and pauses.
   Generate escaped SSML and map provider UTF-8 byte offsets back to accepted
   UTF-16 text offsets. Overlapping or ambiguous controls fail before network
   access.
5. Store raw provider audio/timing and normalized output in separate immutable
   cache layers so a normalization change never incurs a new provider charge.
6. Emit an internal deterministic `NarrationAudioAsset` JSON record per block
   with all domain-model identity hashes and honest timing precision.
7. Normalize through FFmpeg, verify through FFprobe, and publish only complete,
   verified cache directories atomically.
8. Add a CLI that proves first-run generation, unchanged all-reuse, and one
   edited block causing exactly one regeneration.
9. On per-block synthesis failure, publish a clearly failed record and a
   deterministic audible placeholder rather than silently shortening the
   narration spine. Never relabel an older asset as current.

## Explicit exclusions

- Slice 1.3 anchor-to-frame compilation, manifests, build reports, and goldens.
- Resolve placement, package writing, or any Free/Studio workflow.
- Authoring UI, persistence service, collaboration, durable jobs, or editor
  voice controls.
- Recorded/locked host takes, replacement timing previews, and final mixing.
- A local/offline provider.
- Provider-side lexicon creation/deletion or any other remote resource mutation.
  This slice accepts inline SSML controls or references pre-existing lexicons
  with recorded names/content hashes.
- Long-block chunking, automatic linguistic tokenization, fuzzy pronunciation
  matching, or timing repair.
- Any change to `/contracts`, generated shared types, `/fixtures`, accepted
  Slice 1.1 inputs/tests, accepted Phase 0 data/tests, or golden files.

## Internal API and records

The provider protocol receives a frozen `SynthesisRequest` containing exact
plain text, voice/profile settings, pronunciations, SSML controls, and requested
timing kinds. It returns provider audio bytes plus declared format/rate/channels,
provider input bytes, timing marks, and complete provenance. Large audio is
written only inside a bounded staging directory; no provider URL is handed to
FFmpeg.

Timing marks preserve provider millisecond starts and source byte ranges. Word
end times are optional because Polly supplies starts, not exact word ends.
Derived next-word/audio-end boundaries are stored separately and labeled
`word_start_with_derived_end`; Slice 1.3 must consume that precision honestly.

Canonical JSON uses UTF-8, sorted keys, compact separators, no NaN, and a
record/key version. Hashes use `sha256:<lowercase hex>`. Identity excludes wall
clock time, request IDs, credentials, and paths.

### Synthesis key

Hash the exact text and provider input, logical profile, provider/region/engine,
voice and unavailable-version sentinel, language, pronunciation dictionary,
synthesis settings, requested timing kinds, adapter version, and pricing-policy
version. Any material synthesis change misses this layer.

### Normalization key

Hash raw audio and timing hashes, the complete normalization profile, FFmpeg
capability fingerprint, and normalizer version. A profile/tool change reuses
raw synthesis and produces only a new normalized asset.

### `NarrationAudioAsset` internal record

Record version, asset ID, block ID/revision, `kind: temp_synthetic`, status,
text/provider-input/profile/settings/pronunciation/request hashes, provider,
region, model/engine, voice ID/version sentinel, raw audio/timing hashes,
timing precision/artifact, normalization profile/hash/tool fingerprint,
normalized audio hash, exact duration samples and derived milliseconds,
sample rate/channels/sample format, cache dispositions, locators, generation
time, request IDs, data-policy attestation, estimated cost, and failure reason.

This is an internal Python record in Slice 1.2, not a fourth frozen shared
contract. If Slice 1.3 proves a cross-language serialized contract is needed,
work stops for the repository's explicit contract-change note and producer
approval rather than smuggling one into this slice.

## Cache layout and safety

```text
<cache>/v1/
  locks/<synthesis-key>.lock
  synthesis/<synthesis-key>/
    provider-input.ssml
    provider-audio.pcm
    provider-timing.json
    synthesis.json
  normalization/<normalization-key>/
    narration.wav
    normalization.json
  assets/<block-id>/<asset-id>/
    narration.wav
    timing.json
    asset.json
```

Acquire a per-synthesis-key process lock, recheck after locking, stage on the
same filesystem, verify strict inventory and all hashes, then publish a whole
directory with a non-overwriting atomic rename. A verified concurrent winner is
reused. Corrupt or unsafe existing entries fail visibly and are never deleted,
quarantined, overwritten, or silently regenerated.

## Normalization profile

Profile `vera-temporary-narration-v1`:

- measured two-pass FFmpeg `loudnorm`;
- integrated loudness -16.0 LUFS, true peak no higher than -1.5 dBTP, LRA
  target/cap 7 LU;
- explicit mono downmix, then 48 kHz resampling;
- RIFF/WAV, `pcm_s24le`, mono, 48 kHz;
- metadata/chapters stripped; no BEXT/PEAK chunks;
- no trimming, time-stretching, or proportional timing repair;
- exact decoded sample count preserved, with recorded trailing padding only
  for a sub-400 ms block needed for measurable loudness;
- FFmpeg/FFprobe capabilities and versions recorded in normalization identity.

The installed producer pair is FFmpeg/FFprobe 8.1.2. Integration tests require
the needed capabilities and assert semantic output on CI; byte identity is
claimed only for repeated runs under the same tool fingerprint, not across
unrelated FFmpeg builds or CPU architectures.

## Files and dependency justification

Expected implementation boundary:

```text
python/vera_timeline_agent/narration/
  __init__.py
  __main__.py
  models.py
  provider.py
  polly.py
  normalize.py
  cache.py
  service.py
  cli.py
tests/
  test_narration_provider.py
  test_narration_normalize.py
  test_narration_cache.py
  test_narration_service.py
  test_narration_cli.py
docs/slice-1.2-voice-cache-acceptance.md
```

Dependency: add exact-pinned `boto3==1.43.79` and update `uv.lock`. One-line
justification: boto3 supplies supported AWS credential resolution, SigV4
signing, retries, response streaming, and Polly API models without maintaining
security-sensitive signing code. FFmpeg/FFprobe remain external prerequisites.

## Test-first matrix

Provider-independent tests must prove:

- exact text and provider input are separate and fully hashed;
- UTF-8 speech-mark byte offsets map correctly to UTF-16, including astral and
  combining Unicode cases;
- malformed/nonmonotonic/out-of-bounds speech marks fail;
- pronunciation/control overlap, unsafe SSML, provider limits, missing
  credentials, missing data-policy attestation, and cost ceiling fail before a
  provider call;
- each identity input invalidates exactly the intended cache layer;
- unchanged runs make zero fake-provider calls and report every block reused;
- an in-memory or temporary-copy one-block text edit causes one provider call
  pair and leaves every other block reused;
- excluded narration is never sent;
- concurrent same-key requests call the fake provider once;
- cache tampering, symlinks, hard links, unexpected files, partial writes, and
  injected failures never publish or reuse unsafe output;
- FFmpeg output is one mono 48 kHz PCM-24 WAV with exact sample duration,
  stripped metadata, finite loudness within tolerance, and same-tool repeated
  byte identity;
- corrupt/unsupported/multistream/silent provider media fails explicitly;
- placeholder records/audio are obvious and never report ready synthesis;
- deterministic CLI order/output/exit codes cover generated, reused,
  renormalized, failed, usage, validation, provider, and media-tool failures.

No automated test performs a cloud call. Frozen Polly response samples may be
hand-authored under new Slice 1.2 test data; they are not `/fixtures` and do not
contain credentials or production text.

## Automated completion and manual acceptance

Agent completion requires focused tests, root `npm run validate`, clean locked
installs, generated-contract currentness, dependency/lock audit, frozen-boundary
audit, same-tool normalization repetition, and independent no-findings review.

Producer acceptance requires the documented command over a copy/read-only use
of the canonical script inputs with authorized AWS credentials and a chosen
data-policy attestation:

1. inspect the cost/data/tool/profile preflight before network access;
2. generate and listen to every active block as a separate normalized WAV;
3. rerun unchanged and see every block reported reused with no Polly calls;
4. edit exactly one narration block in a temporary copy and see exactly one
   block regenerated;
5. confirm excluded narration produced no asset and no request; and
6. explicitly accept or reject voice quality, pronunciation, normalization,
   timing evidence, and cache behavior.

