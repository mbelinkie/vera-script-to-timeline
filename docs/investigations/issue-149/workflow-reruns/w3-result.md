# Task ID #149 — W3 mapping mute/restore result

## Challenged claim

`SetSourceAudioChannelMapping` with `track_mapping.1.mute=true` should silence the A2 `a2_numbers.wav` track in the W3 render and restore the original mapping afterward.

## Classification

**Adverse.** Native mutation and readback succeeded, but the mute render retained all eight number words and the 1500 Hz pilot at the baseline level. Baseline, mute, and restored decoded video sequences are 399 frames of `src_id=1`, frames 0–398; restored mapping and PCM are equal to baseline.

## Measured media

| Render | Full MOV SHA-256 | PCM SHA-256 | Words/pilots |
|---|---|---|---|
| `baseline` `out/issue149-workflow-reruns-20261002-kit-01/renders/W3-baseline-01.mov` | `735abfeaf301d74985b48e7b950891bd03aabccea0dd16f4cb0c9e481ee72feb` | `f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96` | words `alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel, one, two, three, four, five, six, seven, eight`; pilots `1000=0.02828, 1500=0.01986, 2000=0.02003` |
| `mute` `out/issue149-workflow-reruns-20261002-kit-01/renders/W3-mapping-mute-01.mov` | `04130e2a23a7277ec2c5930fb1f1f6821d3cfcc2c1fdf39e13b966ccd2847a75` | `f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96` | words `alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel, one, two, three, four, five, six, seven, eight`; pilots `1000=0.02828, 1500=0.01986, 2000=0.02003` |
| `restored` `out/issue149-workflow-reruns-20261002-kit-01/renders/W3-restored-01.mov` | `fa0b87fec339e61d37a5a7d007ab0e3d1422ddf786b0dc0cc53b79509cde19fe` | `f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96` | words `alpha, bravo, charlie, delta, echo, foxtrot, golf, hotel, one, two, three, four, five, six, seven, eight`; pilots `1000=0.02828, 1500=0.01986, 2000=0.02003` |

`ffprobe` for all three renders: H.264 640×360, 25/1 fps, 399 frames, 15.96 s; PCM signed 16-bit stereo, 48 kHz, 766080 samples. `w3-analysis.json` frame decode reports zero mismatches for all three.

Mute gate result: expected absence of `one`–`eight` failed with: `'W3-mute' contains forbidden words: eight, five, four, one, seven, six, three, two`. The restored all-16-word/check-and-comparison gate passed.

## Native mapping and state evidence

Mute target-only delta: `{'changedPaths': ['track_mapping.1.mute'], 'onlyTarget': True, 'path': 'track_mapping.1.mute'}`. Restore semantic equality: `True`; restore snapshot unexpected paths: `[]`.

Baseline→restored complete post-state diff used the harness recursive diff, with only these concrete allowances: explicit queue additions at `project.GetRenderJobList.value[1]` and `[2]`. Unexpected remaining difference: `project.timelines[0].getters.GetCurrentTimecode.value` (baseline playhead `00:00:15:23`, restored `00:00:00:00`).

## Retained native journals/pairs and SHA-256

### `render-stage-w3-baseline-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-render-stage-w3-baseline-01-20261002-kit-01.json` — `f751d34a7f6229ffd9d7f697140ca0f4b8f6c54e5d5d90ca3814d82e1650f749`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-baseline-01-20261002-kit-01/journal.jsonl` — `9a833051dfd116433037edd67f4639dff72ec7334148d8fae07cac6e923e2039`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-baseline-01-20261002-kit-01/pre.json` — `8f1a6c728001ae3639ce75f42d60d375112f4078076c28978e60016679659ddb`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-baseline-01-20261002-kit-01/post.json` — `a25a47526737331017654cca69c1264f06235d1e82b49fba2c0d68a69f59c9af`
### `render-poll-w3-baseline-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-render-poll-w3-baseline-01-20261002-kit-01.json` — `dd63636c8067be93ae91c2a50e990ac4ce06ba026ec77da7d8eef97abf2b0c83`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-baseline-01-20261002-kit-01/journal.jsonl` — `0327c6b91bb6945e816f8c6e8a0b80206186eca44db3426b5b0d2f56387e685d`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-baseline-01-20261002-kit-01/pre.json` — `89063d733da7cee57e9c3c72242083ff0955399a4f931c4cab134aaa9afd4eb1`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-baseline-01-20261002-kit-01/post.json` — `89063d733da7cee57e9c3c72242083ff0955399a4f931c4cab134aaa9afd4eb1`
### `w3-mapping-mute-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-w3-mapping-mute-01-20261002-kit-01.json` — `946fe06211d2d528690b75b67636ec85ed1ebaf3c90df890e47662c36bb433d7`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-mute-01-20261002-kit-01/journal.jsonl` — `7a187e2388997b7f80fb0e7efd47f33970db4a505b26be42ca92a741d0bee2b0`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-mute-01-20261002-kit-01/pre.json` — `89063d733da7cee57e9c3c72242083ff0955399a4f931c4cab134aaa9afd4eb1`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-mute-01-20261002-kit-01/post.json` — `2df05ef49511228b33db3d462f1a71e9c99e3bc237da7d3750f61e41b1054eef`
### `render-poll-w3-mute-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-render-poll-w3-mute-01-20261002-kit-01.json` — `18ecfa5275e05813a34b1bead67c53a816d6746ba69e900bb6bfdabad58fd777`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-mute-01-20261002-kit-01/journal.jsonl` — `3a7acbbef8e2b21e6946cd94c71069d0bcbf1a9b4608d0606b7e1008197948ed`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-mute-01-20261002-kit-01/pre.json` — `e9e31ddb706f96d183b9b91b719b5bcfa016168992fd859e189ec0abef72c2ab`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-mute-01-20261002-kit-01/post.json` — `e9e31ddb706f96d183b9b91b719b5bcfa016168992fd859e189ec0abef72c2ab`
### `w3-mapping-restore-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-w3-mapping-restore-01-20261002-kit-01.json` — `a59ffcbe764cf89df98b05e469a22401f14b9632ac748934499f5ee7037adb43`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-restore-01-20261002-kit-01/journal.jsonl` — `954834a6bb6d12235947735783a8faac4abe0b414df011ffc89f060fcc1c0da6`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-restore-01-20261002-kit-01/pre.json` — `e9e31ddb706f96d183b9b91b719b5bcfa016168992fd859e189ec0abef72c2ab`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/w3-mapping-restore-01-20261002-kit-01/post.json` — `3ed2972404386195100021e5a2139adb17212935921811902eb37d55b21563be`
### `render-stage-w3-restored-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-render-stage-w3-restored-01-20261002-kit-01.json` — `a0afed02970da8774cedc9ea1d3c516fb6c6314cedc13295449481b61568dad6`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-restored-01-20261002-kit-01/journal.jsonl` — `f63f48e6001ed37825f797626d14ea06d366e20ae7c80d8950463b7c8de1b1b3`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-restored-01-20261002-kit-01/pre.json` — `3ed2972404386195100021e5a2139adb17212935921811902eb37d55b21563be`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-stage-w3-restored-01-20261002-kit-01/post.json` — `fa4ada19af9f995b3369776ec8c9a5743801d6c98d19d0c9832f2487d079d234`
### `render-poll-w3-restored-01-20261002-kit-01`
- `out/issue149-workflow-reruns-20261002-kit-01/vera-issue-149-workflow-reruns-result-render-poll-w3-restored-01-20261002-kit-01.json` — `ebf1176af657658627471ad67298f007b8bdce31737af6958e62e7f3e82e35b6`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-restored-01-20261002-kit-01/journal.jsonl` — `33deca803545a5fb6634465a71dc316f02c5a436f00dda9e5265b6c94987f937`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-restored-01-20261002-kit-01/pre.json` — `e76dcbe42224426afae6ac771d6a9bee6c7ae23e0eccb3ff0d5679ba8e826a0e`
- `out/issue149-workflow-reruns-20261002-kit-01/evidence/render-poll-w3-restored-01-20261002-kit-01/post.json` — `e76dcbe42224426afae6ac771d6a9bee6c7ae23e0eccb3ff0d5679ba8e826a0e`

## Alternative explanation

The generated W3 media hashes match the retained #149 fixture manifest byte-for-byte, and the manifest files themselves are identical (`111645645106943e675418fa766fe2dfe2a2a05047d0dc8f9e9fc5e845111b39`). The retained #149 media files are not present in this checkout, so direct old-render/source-file byte equality is unavailable; fixture-version mismatch is therefore reduced by the manifest comparison but not fully excluded. The measured case isolates successful native mapping mutation/readback without an output-audio effect; whether Resolve mapping semantics, page context, or render-side caching explains that result remains unresolved.

## Re-run identity and native target

- Injected Workflow Integration run: DaVinci Resolve Studio `21.1.1.10`, CPython `3.14.7`, x86_64 macOS `15.1`, External Scripting `None`.
- Frozen harness source: `25d3bf713afd2e0036d131c2ef9d9fa3ad0082ebc5183f69ddf3d02f98e003c3/harness.py`.
- Project `VERA Issue 149 Workflow Reruns 20261002-kit-01`, project UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; timeline `W3-mapping-mute`, timeline UID `8c67340f-2428-407c-86f7-ce553152a86c`.
- Target A2 timeline-item UID `ceaf0513-cdc9-4188-b690-b91dbaa01d13`; its `mediaSnapshot`/source UID `a23c9a6e-1640-4db8-b380-b16870ced30c`. The W3 snapshot schema has no literal `mpi_uid` key; these are the corresponding recorded `GetUniqueId` values.

The exact W3 mapping strings were:

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":false,"type":"mono"}}}
{"embedded_audio_channels": 1, "linked_audio": {}, "track_mapping": {"1": {"channel_idx": [1], "mute": true, "type": "mono"}}}
```

`SetSourceAudioChannelMapping` returned native boolean `true` for mute (journal lines 568–571) and restore (restore journal lines 568–571); the immediate getters read the requested `mute:true` and then original `mute:false` strings. Retained #149 `p3-001-build-mute-solo.json` records the same compact original/muted JSON and `true` return at lines 27–37.

## Gate and interpretation

The valid output gate is: A2 1500 Hz pilot `<= 0.001`, no `one`–`eight`, A1 control words `alpha`–`hotel` present at their baseline frame positions, and restored PCM byte-equal to baseline. Video must remain 399 frames, `src_id=1`, with zero decoded frame mismatches. W3 failed only the mute effect gate: pilot `0.01986` and all eight number words remained, despite native mutation/readback; controls stayed at the same frames and restore passed. A mapping flag alone cannot establish program silence in VERA: this effect currently requires render analysis or manual review. The result does not establish a core authoring failure.

## Concrete context difference

W3's mutation snapshot was taken with `GetCurrentPage = "deliver"` and current timecode `00:00:00:00` (mute journal lines 19–20 and 57–58). The retained #149 p3 result does not record `GetCurrentPage`, project cache settings, or render call order; it only records the T6 append/mapping sequence and snapshots. Thus page context is a concrete cross-run difference, but the retained records do not prove it caused the adverse render. The baseline→restored state diff's playhead change (`00:00:15:23` → `00:00:00:00`) is recorded separately and has no evidence tying it to the mapping setter.

## Analysis artifacts

- `out/issue149-workflow-reruns-20261002-kit-01/w3-analysis.json` — `ed495b969265be687a0bfb370a51d455487ff912a20bc11429d637d1253b4660`
- `out/issue149-workflow-reruns-20261002-kit-01/w3-verification.json` — `cfdf6b93f7fa9e8634a5657c124bbc1c9bf0f72ef514f2020f8256f60f9f1ae4`

## Appendix — Edit-selected restore PCM verification

The follow-up explicitly opened and verified the Edit page and reselected the same W3 timeline before setting the same A2 mapping flag. `w3-mapping-mute-edit-02-20261002-kit-01` returned `True` and read back only `track_mapping.1.mute=true`; its result SHA is `6304b8c02bfaea3c9404756219f6fba34d49f8c8e26bfe512466d823bc8c97c2`, journal SHA `5dcc16b6a95a89217f3660b1a8cef94241d8689d2b43c61aa6066e9932e28405`. Render job `583d9dbc-4e04-49fb-b3a0-9e05f105b496` completed at 100%; terminal result SHA `48c5136e92051ac9e5b5029026e474c9213d5a3e5f1cbdeed1e645afea7f7fb1`. `W3-edit-muted-02.mov` SHA `5b3a444b71b6fb1931ac4e41ba9239e1df63112e8e6f47a70da5eaec6770d8c0` retained all 16 words, A2 pilot `0.01986`, and PCM byte-equal to baseline. `w3-edit-analysis-check.json` binds the exact mapping, page, IDs and analysis. Changing page and selection in this sequence did not resolve the contradiction; it does not isolate caching, source mapping semantics or integration context as the cause.

Task ID #149. The Edit-selected follow-up `w3-mapping-restore-edit-02-20261002-kit-01` completed its native restore action and render poll (`JobStatus=Complete`, 100%). The restored render `W3-edit-restored-02.mov` has full SHA-256 `93c08a07aca05f0801e1ac9e672a4e98c34cd046d77b9dbfd0773fd4b512b728`; its decoded PCM s16le is 3,064,320 bytes with SHA-256 `f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96`, byte-equal to W3 baseline PCM. Baseline full MOV SHA is `735abfeaf301d74985b48e7b950891bd03aabccea0dd16f4cb0c9e481ee72feb`; container hashes differ, so this appendix asserts PCM equality only. Native restore result SHA `e02cd802bad0e6175601a1fc79b6453b3fc53f560fe744d9b074d59353ebfa36`, render-stage SHA `e45a86da263eb81f13bfd9b0d4a4f0a295751db6db9f8244e453c594d2f77afa`, and terminal poll SHA `653f785a572d66ec62295b7378c6c7394155105cc86367d0741aa66077806ad` (job `bbde62c9-6f09-4417-bf3d-345ba5e23793`) are retained. This confirms restored audio payload; the existing adverse classification concerns the mute effect and is unchanged.
