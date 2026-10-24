# Inworld temporary narration

New ordinary narration requests use the configured `inworld-arthur-tts-2-en-us-v1`
profile: Inworld TTS-2, Arthur, en-US, 100% speed. This changes the default for
new requests; it does not regenerate existing assets. Explicit Polly and Fish
profiles remain available. The selected voice is profile data in
`narration/configuration.py`; transport and timing code accept configured IDs.

Use the supported narration CLI with a ScriptDocument v1 containing **only the
authorized active narration blocks**:

```sh
uv run --frozen python -m vera_timeline_agent.narration selected-script.json \
  --cache /path/to/private/cache --data-policy inworld_terms_accepted \
  --max-cost-usd 0.02 --preflight-only
```

Replace `--preflight-only` with `--confirm-provider-call` after checking the
selection and allowance. A second identical invocation verifies and reuses
the cached assets without a synthesis request. The CLI requires both explicit
data-policy acceptance and live-call confirmation. Selecting a default profile
alone does not authorize transmitting text or spending money.

Set `INWORLD_API_KEY`, or store the complete Portal Base64 credential in macOS
Keychain generic-password service `com.vera.script-to-timeline`, account
`inworld_api_key`. The adapter captures Keychain output internally and sends the
credential unchanged as Basic authentication. Do not paste it into commands,
logs, configuration files, Git, or reviewer inputs.

Voice/model/speed overrides require no source edits:

```sh
uv run --frozen python -m vera_timeline_agent.narration selected-script.json \
  --cache /path/to/private/cache --data-policy inworld_terms_accepted \
  --voice-id YOUR_EXISTING_VOICE_ID --model inworld-tts-2 --rate 110% \
  --max-cost-usd 0.02 --preflight-only
```

Voice IDs are passed through to the provider; there is no hardcoded catalogue.
The supported models are `inworld-tts-2` and `inworld-tts-2-flash`; only TTS-2 /
Arthur has the accepted live study. Each override changes synthesis identity.
Profile, model, voice/version, language, rate and adapter semantics participate
in immutable cache identity. Historic replay captures have separate identities.
To select an older route, pass `--voice-profile fish-mw1-s2.1-pro-free-en-us-v1`
with `--data-policy fish_terms_accepted`, or a named Polly profile with its
`--aws-data-policy` attestation. There is no automatic fallback or paid retry.

The live adapter requests synchronous WORD timing and mono 48 kHz LINEAR16 WAV.
It accepts 1–2,000 UTF-16 code units per row and speed from 50% to 150%; it
rejects unsupported pitch, volume, pronunciation, inline delivery controls and
pause/emphasis settings. TTS-2 delivery is explicitly BALANCED; Flash uses its
documented default temperature. These fixed wire settings belong to the
adapter version. Longer rows fail clearly rather than silently changing the
text or splitting the synthesis. Native pieces must exactly cover authored
text; token grouping preserves original source spans. Invalid, tied, collapsed,
overlapping or out-of-bounds lexical timing is rejected. Native word ends are
structural metadata, not verified audible support.

Cost reservations use conservative on-demand prices: TTS-2 $25/million UTF-16
units; Flash $15/million. Account credits and actual billing can differ. Funding,
authentication, quota/rate, transport and malformed/partial responses stop the
attempt without substitution or automatic retry. A transport failure may still
have incurred a charge. Private rejected response evidence remains in the local
cache only; remote error bodies are never echoed.

Sources checked 2026-10-24: [synthesis endpoint and limits](https://docs.inworld.ai/api-reference/ttsAPI/texttospeech/synthesize-speech),
[Basic authentication](https://docs.inworld.ai/api-reference/introduction),
[on-demand pricing](https://inworld.ai/pricing).

## #275 handoff

Resume the existing benchmark only after #293 merges green and is Closed/Done.
Use the configured Inworld profile above through `NarrationService` and the v2
projection/compiler path. Keep fresh, verified cached and one-row-change cases
distinct. Carry forward the original selected-text authorization and cumulative
allowance; account funding does not authorize bulk generation. Integration live
evidence and remaining allowance are recorded in the #293 result comment.
