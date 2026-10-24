# #289 revised Sweden comparison checkpoint

Status, 2026-10-24: resumed under the revised live issue; awaiting direct TTS
access for ElevenLabs and Inworld. No new provider requests have been made.

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
| ElevenLabs direct TTS | Key unavailable in this chat's environment/launchd or documented VERA configuration | Pending access, unrun |
| Inworld TTS | Key unavailable in this chat's environment/launchd or documented VERA configuration | Pending access, unrun |
| Fish | Existing credential resolves locally; no provider request sent | Control unrun |
| Polly | Existing AWS credential resolves locally; no provider request sent | Control unrun |

The existing ElevenLabs integration is Scribe recognition through OpenRouter;
it is not direct ElevenLabs TTS access. An OpenRouter key cannot be substituted.

- New approved allowance: **$5 additional API usage total** across newly paid
  calls and any authorized retries. Committed/actual new usage: **$0**.
- Original Polly cap: **$1 cumulative**, including the retained **$0.098688**
  reservation for nine prior takes. The old records do not establish the actual
  billed amount; keep that reservation committed. Conservative balance:
  **$0.901312**. The $5 allowance does not expand this cap.
- Fish cap remains **$0**, with no paid fallback.
- Do not create a new subscription, assume account credits, or pay a minimum
  beyond the authorized cap. Account/access requirements are prerequisites.

Only the selected text is authorized for these TTS services. Existing private
audio/media remain local; no hosted aligner, reviewer, GitHub or CI upload.
Calls remain disabled until both first-stage access prerequisites are resolved.
Parent serializes spend; helpers perform no provider calls.

## Candidate endpoint plan (documentation only)

Inworld's synchronous `/tts/v1/voice` endpoint documents explicit
`modelId: inworld-tts-2` and `timestampType: WORD`, with native word start/end
metadata. Use an account-accessible English narration voice and lossless WAV/
LINEAR16 if the account supports it. The 2,000 UTF-16-unit row limit fits both
selected rows. Final voice availability and account credit remain unverified.
[Inworld synthesis](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech),
[Inworld authentication](https://docs.inworld.ai/api-reference/introduction).

ElevenLabs' `/v1/text-to-speech/{voice_id}/with-timestamps` returns original and
normalized character alignment, requiring exact source mapping before grouping
into words. `eleven_v4` is a provisional narration candidate; validate its actual
account/endpoint compatibility and available voices before relying on it. Keep
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

Provider access, pinned candidate configuration, fresh generation, independent
acoustic/fidelity checks, finalist repeats, admission/compiler proof and the blind
audition are outstanding. Preserve the original fail-closed paths and all earlier
failures. #275 remains blocked; no Resolve run, benchmark restart or default switch.
