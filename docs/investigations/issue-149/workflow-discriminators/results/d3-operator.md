# Issue #149 D3-operator W3 mapping-mute result

Task ID: `/root/discriminator_output_verify`

## Challenged claim and classification

This case tests whether a Workflow Integration mapping mute silences A2 after an operator opens the Fairlight page, with no playback or other Fairlight control change, and a render is then started through Workflow Integration. The classification is **adverse**: the Workflow Integration getter reported A2 `mute: true`, but the render retained the A2 pilot and all eight number words.

The first render dispatch was stopped before Resolve rendering because the harness rejected a relative target directory as outside the owned output. That is a harness/configuration failure and produced no native render result. The corrected dispatch used the same pinned fixture and an absolute owned target directory; it ran once and produced the native evidence below.

## Run identity and fixture

The disposable project was `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`. The target timeline was `D3-operator-av-20261003`, UID `f88a069b-af68-40d2-8556-3a7c97c234ec`. Its V1 item was `56cb18fd-a417-45a8-87c1-80fc70a882a3`, linked A1 was `db2502e5-4e44-4b73-9bc6-191e3d259ecd`, independent A2 was `11c37e49-d9f2-4480-b0a1-9ba09b81b4d2`, and independent A3 was `80bdb064-0b4a-404d-8b40-b5640630592e`.

The timeline was 1920×1080, 25 fps, 48 kHz, with native record/source getter bounds 0–399, native timeline end 399, and rendered frame indices 0–398 (399 frames). A1 carried the 1000 Hz NATO control, A2 the 1500 Hz number-word control, and A3 the 2000 Hz bed control. The source fixture hashes were `a1_alpha.wav` `4bc4b8cfa118dab9f75ec2072f79af0c856f41566d7e2da60fca5268f7d81253`, `a2_numbers.wav` `d9aeccc2d50cb96d81341167450eeb1b2c43fecf0f02b9291b4cd65afa92f9ba`, `a3_bed.wav` `022e3dd779808e5b38ff870cd541d8e25fb940836443262aaa95ce8768817e2b`, and `base.mov` `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036`.

The operator step was separately captured as a page-only transition: the user opened Fairlight and did not play, seek, render, or change a Fairlight control. The capture read `page: fairlight`, target timeline UID `f88a069b-af68-40d2-8556-3a7c97c234ec`, and queue count 9 before the mute render.

## Mapping state and render execution

Workflow Integration changed only A2 `track_mapping.1.mute` from `false` to `true`; A1 and A3 remained `false`. The muted readback was:

```json
{"embedded_audio_channels":1,"linked_audio":{},"track_mapping":{"1":{"channel_idx":[1],"mute":true,"type":"mono"}}}
```

The corrected Workflow Integration render used the pinned synthetic AV fixture, External Scripting `None`, and the existing H.264 QuickTime settings: 640×360, 25 fps, 48 kHz 16-bit LPCM, `RenderAll: true`. The job was `6ee16fa3-8391-49d7-9b98-054dee2a2d65`; its terminal poll reached `Complete` at 100%. The first relative-target refusal is retained under `result-render-stage-d3-operator-fairlight-20261003-kit-02.json`; the corrected render result is `result-render-stage-d3-operator-fairlight-corrected-20261003-kit-02.json`.

## Muted-output measurements

The output is `renders/d3-operator-av-fairlight-20261003/D3-operator-av-fairlight-20261003.mov`, SHA-256 `c1376261243f61f6fc68b708e98adce79369df789ea1f8551ecab7253a6e69af`. It contained 766080 mono samples.

| Control | Measured level | Requirement | Result |
| --- | ---: | ---: | --- |
| A1, 1000 Hz | 0.02828 | retained | present |
| A2, 1500 Hz | 0.01986 | ≤ 0.001 | **failed silence gate** |
| A3, 2000 Hz | 0.02003 | retained | present |

The supplied `evidence/scripts/analyze_audio.py`, called by the retained local analyzer, measures known-fixture word correlation rather than a new ASR transcription. All eight A2 number words—`one`, `two`, `three`, `four`, `five`, `six`, `seven`, `eight`—were present. The output decoded 399 frames, all source ID 1, with zero frame-code mismatches. The offline analysis is `analysis/d3-operator-w3.json`, SHA-256 `12c561bbe49b0c1fbb5a6dfd5d1e185508104cc563a9bb5c9fb31638176e4d16`.

## Restoration and checkpoint

The owned Workflow Integration restore returned true and restored A2 semantically to the original `mute: false` mapping. The restore comparison allowed only the A2 mapping field and reported no unexpected differences. The restored render was job `c810d2ee-4b28-4ec7-bd9f-55a411096463`, reached terminal `Complete`, and produced `renders/d3-operator-av-restored-20261003/D3-operator-av-restored-20261003.mov`, SHA-256 `8a8b433afdd6d0665e0cc372954eb939384263f22f0c11dc3c71c4f570ae9043`. It measured the same pilots (`0.02828`, `0.01986`, `0.02003`), retained all eight number words, and decoded 399 source-ID-1 frames with zero frame-code mismatches. As with the other restored renders, this verifies restored state; it does not show that the mute operation should have silenced the program output.

The final owned-project save checkpoint called `SaveProject` exactly once and returned true. Its pre/post snapshot pair is byte-identical at SHA-256 `c0f8757df49d537d96ec00cbbbba0a80330fbf32a2c3f9dbe1862ae527a99a82`; the checkpoint had queue count 12, rendering false, Deliver page, and the operator timeline's A2 mapping false. The save result is `result-save-final-owned-project-checkpoint-20261003-kit-02.json`, SHA-256 `a1cf6eb30f590e3bac3df139607993bdf94d3ce49ecd8854781d73a9c25b70c7`.

## VERA consequence

The Fairlight-page operator variant also failed the rendered-output gate. Across the direct Workflow Integration, Console, and Fairlight-page variants, a readable A2 mapping flag did not establish program silence in this fixture. VERA must not infer that A2-derived speech has been removed from the rendered program from this mapping flag alone. It needs render/output verification or a separately validated control and should retain the result as an audio-reconciliation limitation. This case did not reproduce a failure of the core script-to-timeline authoring path.

## Pinned evidence

- Muted render poll: `vera-issue-149-workflow-discriminators-result-render-poll-d3-operator-fairlight-20261003-kit-02.json`, SHA-256 `07a6e35b13f6b23f9d48906d977e8683b04cb7d968089d5a48379743bef4ff87`.
- Mapping restore: `vera-issue-149-workflow-discriminators-result-w3-mapping-restore-d3-operator-fairlight-20261003-kit-02.json`, SHA-256 `77184f8c40d3b8035b117752f84f9e0e4922a3c400ae95b92fd5cd9506a6e088`.
- Restored render poll: `vera-issue-149-workflow-discriminators-result-render-poll-d3-operator-restored-20261003-kit-02.json`, SHA-256 `983be64f32550b209a601bbccd3bab54331073e895708de6cbbaea749c1c26b1`.
- Complete `pre.json`/`post.json` pairs are retained in `evidence/w3-mapping-mute-d3-operator-fairlight-20261003-kit-02/`, `evidence/render-stage-d3-operator-fairlight-corrected-20261003-kit-02/`, `evidence/render-poll-d3-operator-fairlight-20261003-kit-02/`, `evidence/w3-mapping-restore-d3-operator-fairlight-20261003-kit-02/`, `evidence/render-poll-d3-operator-restored-20261003-kit-02/`, and `evidence/save-final-owned-project-checkpoint-20261003-kit-02/` under the generated kit. The original pre-mute→final comparison retains and attributes queue/page/getter-context differences; the final save pair itself is identical.
- Workflow Integration harness SHA-256: `ef859db33d1e53136c41431a4189c053a4629d64d309b891cabffe6d9fd16438`.

Issue #149 producer acceptance remains pending.
