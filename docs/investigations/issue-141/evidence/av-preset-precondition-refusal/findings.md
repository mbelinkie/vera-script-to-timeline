# Issue 141 AV preset-precondition refusal

The 2026-10-01 06:20 UTC AV attempt stopped before the render-settings setter. Its exported preset XML has `RecordFormatType=mov`, `RecordFormatSubType=avc1`, `RecordAudioEnabled=true`, and `ExtraInfoMap.aud_codec=lpcm`, but `RecordAudioBitDepth=16`. The candidate requires that field to equal `24`, so it raised `Snapshot XML does not verify MOV/H264 plus lpcm`. The prior audio snapshot from 01:59 UTC has the same MOV/H.264, audio-enabled, `lpcm` fields and `RecordAudioBitDepth=24`. This identifies the mismatch; it does not establish why Resolve saved the 16-bit value.

The journal shows only two successful mutating calls before refusal: `SaveAsNewRenderPreset(VERA141_AV_OUTPUT_20261001T062051.400988Z)` and `ExportRenderPreset` to its owned evidence location. `SetRenderSettings`, `AddRenderJob`, `StartRendering`, `LoadRenderPreset`, `DeleteRenderJob`, and `DeleteRenderPreset` were not called. The owned preset and exported XML remain available. This is a failed candidate precondition, not evidence of a Resolve render/output failure.

All three fresh complete pairs have SHA-256 `35f7132f331a8ecf0f1685dd1167c636add1aea3118bfbf2f2e7896ae348c1c3`, identical to `av-calibration-checkpoint-after-r1-move-20261001T061824.json`. Each pair identifies selected Matrix `29ae8331-b86e-4041-a548-960695cc7b24`, with two equal timeline reads and two equal pool reads. All 11 synthetic manifest entries were rehashed from disk and match their recorded hashes. These observations establish the pinned timeline/pool and inputs were unchanged for this comparison.

Environment recorded by the candidate: DaVinci Resolve Studio `21.1.0.14`, macOS `15.1` x86_64, Python `3.14.7` using Resolve's `fuscript`. No claim is made about hidden render-settings equality. The XML export is evidence of saved preset fields only; the actual MOV/H.264+PCM render remains untested.

## Evidence index

`evidence-index.json` records raw-source and published-derivative hashes. `av-journal-redacted.jsonl`, `full-pair-redacted.json`, `preset-field-comparison.json`, and `final-local-result-redacted.json` redact workspace-specific paths. `continuation-record.json` binds the exact prior refusal artifacts and checkpoint for a single controlled continuation. The full pair content was byte-identical across all three captures and the pin, so one path-redacted pair derivative represents the identical source bytes.
