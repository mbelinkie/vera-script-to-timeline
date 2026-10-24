# #289 revised Sweden comparison checkpoint

Status, 2026-10-24: all four providers generated both selected rows in stage 1.
Native inspection and an independent local MFA comparison are complete. The
private eight-clip Audition pack is prepared. No candidate has human-confirmed
acoustic accuracy, confirmed spoken fidelity or sound approval.

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
4. Present a short blind sound/pronunciation audition against Polly only for
   timing passers. Producer acceptance applies to sound, not technical approval.

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

## Remaining delivery

Human timing/fidelity review, finalist repeats,
admission/compiler proof and the blind sound audition are outstanding. Native
arrays matching the source and having increasing times are structural evidence
only. The Producer explicitly requires manual accuracy confirmation even for
apparently clean data. Custom/cloned voices are a separate future investigation.
Preserve the original fail-closed paths and all earlier failures. #275 remains
blocked; no Resolve run, benchmark restart or default switch.


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
| Polly neural / Joanna | Both rows have finite, increasing, in-bounds word starts; native audible ends unavailable | 102/102 compared; median 40 ms, p95 133 ms, worst 263 ms |

Differences are rounded diagnostic disagreements against **unreviewed MFA**,
not measured errors against human truth. The 150 ms p95 gate cannot establish
actual acoustic accuracy without an independently checked reference. Inworld is
the first manual-review candidate; ElevenLabs has the largest disagreements to
inspect. No finalist repeats or sound winner have been selected.

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
