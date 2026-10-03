# Task ID #149 — W3 contradiction note

The old #149 T6 result and the W3 rerun use the same mapping contract. Both read the original A2 mapping as

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":false,"type":"mono"}}}
```

and the muted mapping as the same object with `"mute":true`; `SetSourceAudioChannelMapping` returned native `true` in both. See old `evidence/runner/results/p3-001-build-mute-solo.json` lines 27–37 and W3 mute journal lines 568–571. W3 target topology is V1/A1 linked, A2 `a2_numbers.wav`, A3 `a3_bed.wav`, all `[0,400)`, with project/timeline/item/source UIDs recorded in `w3-result.md`.

The contradiction is at the render boundary: old #149 README reports A2 pilot `0.020 → 0.0002` and no number words; W3 readback says `mute:true`, but the mute render has pilot `0.01986`, all eight number words, and PCM byte-equal to baseline. Both manifest files are byte-identical (`111645645106943e675418fa766fe2dfe2a2a05047d0dc8f9e9fc5e845111b39`), while retained old media bytes are unavailable, so fixture identity is strongly supported but not directly proven by old media hashes.

Concrete run-context difference: W3 recorded `GetCurrentPage="deliver"` before mutation; p3 does not record page, cache settings, or render-call order. W3 project cache reads `perfAutoRenderCacheEnable=1`, codec `apch`, empty cache location. This makes page/cache a bounded follow-up variable, not a proven cause. The playhead difference (baseline post `00:00:15:23`, restored post `00:00:00:00`) has no setter call evidence and must not be attributed to mapping.

Interpretation: native mapping mutation/readback is reproduced; output silence is not. VERA cannot infer program silence from the flag and needs render analysis or manual review. This does not establish a core authoring failure. The retained Edit-page/reselected-timeline follow-up also left the pilot, number words and PCM at baseline (see [W3 record](w3-result.md) and its Edit-selected appendix). Page selection in that controlled sequence did not resolve the contradiction. Cache/render/integration-context differences remain unisolated; no build or harness cause is asserted.
