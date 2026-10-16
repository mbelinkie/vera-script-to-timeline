# Issue #149 D3-direct W3 mapping-mute result

Task ID: `/root/discriminator_output_verify`

## Challenged claim and classification

This case tests whether Workflow Integration can mute the independent A2 timeline item through `SetSourceAudioChannelMapping`, and whether that mute reaches the rendered program output on a **never-rendered** timeline. The classification is **adverse**: the native setter/readback reported `mute: true`, but the completed render retained the A2 pilot and all eight number words.

This result is limited to the synthetic AV fixture, Resolve Studio `21.1.1.10`, External Scripting `None`, and this Workflow Integration path. It does not establish that the setter is unusable for every Resolve entry point or every linked/routing topology. It does establish that a successful mapping getter and setter cannot serve as proof of rendered program silence.

## Run identity and fixture

The disposable project was `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`. The target timeline was `D3-direct-av-20261003`, UID `ca636ad2-b6f2-47ed-9ff7-7f0029860a95`. Its four items were V1 `7eee2712-f027-4baf-863a-f0154efc520b`, linked A1 `563c3945-7a0a-458d-a639-50a5a12a4c2b`, independent A2 `4a7677a5-6237-489d-80a1-32cebfde4a5d`, and independent A3 `03fdd84b-a40a-4702-8138-7a332d05943a`. A2 used MediaPoolItem `eda97c9f-08da-4e29-be52-4ebe8dfd7620`.

The timeline was 1920×1080, 25 fps, 48 kHz, with native record/source getter bounds 0–399, native timeline end 399, and rendered frame indices 0–398 (399 frames). This was the first render of this timeline; there was no baseline render before the mute operation. A1 carried the 1000 Hz NATO control, A2 the 1500 Hz number-word control, and A3 the 2000 Hz bed control.

## Native mapping operation and readback

The original A2 mapping was:

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":false,"type":"mono"}}}
```

`a2Item.SetSourceAudioChannelMapping(mutatedMappingJson)` returned native `True`, where `mutatedMappingJson` is the original mapping serialized after changing only `track_mapping.1.mute` to `true`. `GetSourceAudioChannelMapping()` returned:

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}
```

The retained target-only comparison reports exactly `track_mapping.1.mute` as changed. No baseline render, Fairlight action, or Console render intervened before this direct Workflow Integration render.

## Render and offline measurements

The render was started once with the retained 640×360 H.264 QuickTime, 25 fps, 48 kHz 16-bit LPCM settings. Job `a6d08df1-8e8d-4e2e-b654-5bfe86d60540` reached terminal `Complete` at 100%. The output is `D3-direct-av-20261003.mov`, SHA-256 `c26efae392a6db5a73a2988b88472fff395e26b08eae75e50efa5ce9fee1caf1`.

The output contained 766080 audio samples. Pilot levels were:

| Control | Measured level | Requirement | Result |
| --- | ---: | ---: | --- |
| A1, 1000 Hz | 0.02828 | retained | present |
| A2, 1500 Hz | 0.01986 | ≤ 0.001 | **failed silence gate** |
| A3, 2000 Hz | 0.02003 | retained | present |

All eight A2 number words—`one`, `two`, `three`, `four`, `five`, `six`, `seven`, `eight`—were present. The render decoded 399 frames, all source ID 1, with zero frame-code mismatches. The retained `workflow-discriminators/analyze.py` invokes the supplied `evidence/scripts/analyze_audio.py` for pilot levels and correlation against the known synthetic word supports; word presence is measured fixture correlation, not a new speech transcription. `decode_code.py` decodes the picture markers. The full offline analysis is `analysis/d3-direct-w3.json`; its SHA-256 is `9a7f84b5454d69ff3162d0fc8ac5f73c1f5e57febdad5ee95209aafbf11e8aff`.

## Restoration, closeout render, and final checkpoint

The owned restore returned true and restored A2's mapping semantically to the original `mute: false` mapping. The restore comparison found no unexpected differences: the only allowed difference was the A2 mapping field itself. The restore pair was:

- pre SHA-256 `40b8b23839808b8c368c5756a465ec5f1d138ed3a2b7a03366afef8a5bbfc4b0`, with `mute: true`;
- post SHA-256 `fe9dacd24bf32cb54cdc43eeb6905e3d9428e55886913f4d081a583be779c460`, with `mute: false`.

The later bounded closeout rendered the restored direct timeline once as job `de6df76f-a57b-4642-aafd-75fa30955a2d`, which reached terminal `Complete`. The output is `D3-direct-av-restored-closeout-20261003.mov`, SHA-256 `75170940ae0b2b09e48fc298a2dd8ecd438372b36f5382712f52158134453feb`. It contained 766080 samples; pilots were A1 `0.02828`, A2 `0.01986`, and A3 `0.02003`; all eight number words were present; and it decoded 399 frames, all source ID 1, with zero frame-code mismatches. The full closeout analysis is `analysis/d3-direct-restored-closeout.json`, SHA-256 `103d825a4ff86107ccf948aaa0e30e5c68917482ea41cc23bcd30984ce997b88`.

One final `SaveProject()` call then returned true. Its complete pre/post pair is byte-identical at SHA-256 `c0f8757df49d537d96ec00cbbbba0a80330fbf32a2c3f9dbe1862ae527a99a82`. Rendering is false, the final queue contains 12 jobs, the current page is Deliver, and A2 mapping on all three fresh D3 timelines is `mute: false`, matching their original mappings. All 12 jobs have retained terminal completion evidence, including the manually initiated Console job and the direct closeout job. Comparing the original pre-mute capture with the final saved checkpoint shows expected test progression only: Edit→Deliver, added render-queue rows, and `GetCurrentTimecode()` readings changing from `00:00:15:24` to `00:00:00:00` in the captured records; no residual mapping, clip, or source-content drift was found. The exact cause and any inactive timeline stored-playhead changes were not established, so this remains a context observation rather than an atomic-snapshot guarantee.

## VERA consequence

For this never-rendered Workflow Integration case, mapping mute is **not sufficient evidence of program silence**. VERA must verify the rendered output or use a control whose program-output effect is independently established. The failed silence gate affects audio reconciliation: it cannot safely support automatic removal or masking of A2-derived speech based only on the mapping flag. This test did not reproduce a failure of the core script-to-timeline authoring path. The separately documented Console and Fairlight-page variants were also adverse, so the retained evidence covers all three requested entry-point variants for this fixture.

## Retained evidence

- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-w3-mapping-mute-d3-direct-av-20261003-kit-02.json` — SHA-256 `4c496073e2ab3fc0c3fdbfc978bab9df007b588f1f61eee322a25ba1b91b12a9`.
- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-render-poll-w3-direct-av-20261003-kit-02.json` — SHA-256 `277ffd5e310b831fa9c522f42c1d45cebcee0ea491c3f03fbd7c4da6a8903ccc`.
- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-w3-mapping-restore-d3-direct-av-20261003-kit-02.json` — SHA-256 `66c051a81a93cb0ab0836097874238d5e64b4504b23a5616ce55c915904fec2a`.
- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-save-d3-direct-restored-checkpoint-20261003-kit-02.json` — SHA-256 `e24853c08d90685a9d8040d78fdbc857cfec2c6c2fd89378a787c42420a732d1`.
- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-render-poll-d3-direct-restored-closeout-20261003-kit-02.json` — terminal poll for closeout job `de6df76f-a57b-4642-aafd-75fa30955a2d`.
- `out/issue149-workflow-discriminators-20261003-kit-02/vera-issue-149-workflow-discriminators-result-save-final-owned-project-checkpoint-20261003-kit-02.json` — final equal-pair checkpoint.
- `out/issue149-workflow-discriminators-20261003-kit-02/recovery/d3-direct-restored-checkpoint-review.json`.
- Complete before/after pairs and journals are retained under `evidence/w3-mapping-mute-d3-direct-av-20261003-kit-02`, `evidence/render-poll-w3-direct-av-20261003-kit-02`, `evidence/w3-mapping-restore-d3-direct-av-20261003-kit-02`, and `evidence/save-d3-direct-restored-checkpoint-20261003-kit-02`.
