# Issue #149 D3-console W3 mapping-mute result

Task ID: `/root/discriminator_output_verify`

## Challenged claim and classification

This case tests whether a Workflow Integration mapping mute is reflected by a render started manually from Workspace → Console. The classification is **adverse**: Workflow Integration read back A2 `mute: true`, but the Console render retained the A2 pilot and all eight number words.

The earlier Console attempt failed before helper compilation because the wrapper opened the UTF-8 helper as ASCII. That was a preexecution wrapper failure and produced no Resolve result. The corrected command was run once and produced the native evidence below. This case remains limited to the synthetic AV fixture, Resolve Studio `21.1.1.10`, External Scripting `None`, and the tested Console path.

## Run identity and fixture

The disposable project was `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`. The target timeline was `D3-console-av-20261003`, UID `dc548f02-103c-495a-8e88-c4b767aa10dc`. Its V1 item was `82c25e87-8b15-4388-92e6-d91867d5ce57`, linked A1 was `7d62988b-effd-4646-900b-b5725c02be2f`, independent A2 was `02572600-80b5-43ca-a7bd-6bd74f7b3a89`, and independent A3 was `4ade3d8d-a7d6-413a-a5ae-0466ea27edf7`. A2 used MediaPoolItem `eda97c9f-08da-4e29-be52-4ebe8dfd7620`.

The timeline was 1920×1080, 25 fps, 48 kHz, with all items spanning timeline/source frames 0–399. A1 carried the 1000 Hz NATO control, A2 the 1500 Hz number-word control, and A3 the 2000 Hz bed control.

## Mapping state and Console execution

Workflow Integration changed only A2 `track_mapping.1.mute` from false to true. The full pre/post pair for that setter contains no other difference. The muted readback was:

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}
```

The corrected Console wrapper executed the pinned helper/config exactly once. Its native render job was `bca942f4-c4d6-4a8a-9b64-0831b1587312`, and the terminal poll reached `Complete` at 100%. The render used 640×360 H.264 QuickTime, 25 fps, 48 kHz 16-bit LPCM, with `RenderAll: true`.

## Console output measurements

The output is `D3-console-av-20261003.mov`, SHA-256 `6fb687d847ee6cb5426bae9a5deb35119a0944b441d1d87fb7eb81059ba1376e`. It contained 766080 samples and measured:

| Control | Measured level | Requirement | Result |
| --- | ---: | ---: | --- |
| A1, 1000 Hz | 0.02828 | retained | present |
| A2, 1500 Hz | 0.01986 | ≤ 0.001 | **failed silence gate** |
| A3, 2000 Hz | 0.02003 | retained | present |

All eight A2 number words—`one`, `two`, `three`, `four`, `five`, `six`, `seven`, `eight`—were present. The output decoded 399 frames, all source ID 1, with zero frame-code mismatches. Word presence and pilot levels come from the supplied `evidence/scripts/analyze_audio.py` via the retained local analyzer; picture markers use `decode_code.py`. The full offline analysis is `analysis/d3-console-w3.json`, SHA-256 `56f01483a607e12538ac9d1dc9901b6623abf7a5189d73e41012879b29c69756`.

## Restoration and restored-output verification

The owned Workflow Integration restore returned true and restored A2 semantically to the original `mute: false` mapping. The restore comparison had no unexpected differences; only the A2 mapping field was allowed to change. A restored render was started exactly once as job `461e9071-612f-414d-940b-460c234fbb0b` and reached terminal `Complete`.

The restored output is `D3-console-av-restored-20261003.mov`, SHA-256 `150c010826680103892bc3c4e300aa20bcdc17799b7520c346d8e785de3f0c4c`. It measured the same pilots (`0.02828`, `0.01986`, `0.02003`), retained all eight number words, decoded 399 source-ID-1 frames, and had zero frame-code mismatches. This is a restoration verification of the synthetic mapping state; it does not establish that the original mute operation could silence program output.

The final restore polling pair is byte-identical at SHA-256 `c74ed7e302cc3f1055cc185d43983678e01f3ad5a1767e4c065bf7374f3937b4`, with mapping false, Deliver page, queue count 9, and rendering false. Comparing the original pre-mute capture (`5d9cea30816d31e009c76806f0949804a91d8c01e7ca7c37de3b943b913b4d2d`) with the final restored poll shows only expected context/progression changes: Edit→Deliver, two new render queue rows (Console plus restored output), and `GetCurrentTimecode` readings from `00:00:15:24` to `00:00:00:00` in the captured D6-kept, D3-direct and D3-console records. Those observed getter/context changes do not establish independent stored playhead edits on each inactive timeline; their precise causal event was not isolated. No residual mapping or clip/source-content difference was found.

## VERA consequence

The mapping mute failed the rendered-output gate both for the direct Workflow Integration render and for a manually initiated Console render. VERA must not infer program silence from this mapping flag or automatically reconcile A2-derived speech on that basis. A render/output verification or a separately validated control is required. This affects the tested audio reconciliation control. This test did not reproduce a failure of the core script-to-timeline authoring path. The Fairlight/operator variant remains a separate pending observation.

## Pinned setup and retained evidence

The Console config SHA-256 is `ee05f7d1033c9b64fefaa1cc970a5cf1a9478c598075f82ebc3e89fd0011326c`. The helper SHA-256 is `48f8d3e5499cc4073f5c25fe70dfc3a2d88a04bc459cbe5bbba3783aa6ad90bb`; the harness SHA-256 is `ef859db33d1e53136c41431a4189c053a4629d64d309b891cabffe6d9fd16438`. The source pins remained unchanged: `base.mov` and `swap.mov` SHA-256 `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036`, `a2_numbers.wav` `d9aeccc2d50cb96d81341167450eeb1b2c43fecf0f02b9291b4cd65afa92f9ba`, and `a3_bed.wav` `022e3dd779808e5b38ff870cd541d8e25fb940836443262aaa95ce8768817e2b`.

- `console-render-result-d3-console-render-20261003-kit-02.json` — SHA-256 `0a699e3fa4f618fa4a540b8f1b1be405eaef2f7d5aa5de3da374446765fbb7d8`.
- `vera-issue-149-workflow-discriminators-result-w3-mapping-restore-d3-console-av-20261003-kit-02.json` — SHA-256 `21b5235cedfb6ad714da692853c56da7eaeccc5357044c2be4d3e6518aaeb2ac`.
- `vera-issue-149-workflow-discriminators-result-render-poll-d3-console-restored-20261003-kit-02.json` — SHA-256 `da2c55556abba0c5dd5ec5c0c36eb76bbd29409a32ae32272a68308cdd543723`.
- Restored analysis `analysis/d3-console-w3-restored.json` — SHA-256 `f1a5bdf60291ac3f2e2285bad9308772a7feae5ff8426cc02b67899f31de9d3b`.
- Complete pairs and journals are retained under `evidence/d3-console-render-20261003-kit-02`, `evidence/w3-mapping-restore-d3-console-av-20261003-kit-02`, and `evidence/render-poll-d3-console-restored-20261003-kit-02`.
