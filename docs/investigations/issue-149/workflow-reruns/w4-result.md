# Task ID #149 — W4 retime and click result

## Challenged claim

At 37.5% speed with pitch correction disabled, Resolve exposes an exact OTIO retime and the rendered click impulses land at `source_sample / 0.375`. The embedded AV case and separately sourced A1 case are recorded independently.

## Classification

**Measured retime gates pass for the embedded case.** OTIO contains exact scalar `0.375`; the five rendered impulses visible before the 399-frame export endpoint are all within one audio sample of the source-vector predictions. The generic frame-identity assertion is inapplicable after retime: 399 output frames decode source frames 0–149 with repeated frames, while the machine-readable source ID remains 1.

The separate case records a concrete context difference: the configured W4 action targeted only the V1 `base_picture.mov` item. Its linked A1 `a1_alpha_separate.wav` remained at 100%/pitch correction true in both snapshots, and the separate OTIO has no scalar on A1. The target V1 read back 37.5% but `PitchCorrection: true` despite the false request. This is measured target scope/API behavior; it does not establish a Resolve-version cause.

## Run identity and native binding

Injected Workflow Integration run: DaVinci Resolve Studio `21.1.1.10`; CPython `3.14.7`; x86_64 macOS `15.1`; External Scripting `None`; frozen harness `be467c29fad0f7c8da474eadc9f51ec4a6e7b13f64ee479bebd7eaeceda0cc93`. Project UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`.

| Case | Timeline / target | Getter evidence | OTIO |
|---|---|---|---|
| Embedded `W4-embedded-37p5-01` | Timeline `624aeb81-b32b-4f90-aee4-8360ee9abb11`; V1 `base.mov` UID `6724ba9f-48f1-4ac6-aa2f-7500be267ea0`; A2 `clicks.wav` UID `2d713e82-df4d-4e35-98e6-db7cbad00c51` | Both `GetSpeed` values: 100%/true before; setter returned true and read back 37.5%/false | `exports/W4-embedded-37p5-01.otio`, SHA `322c9bb92597877ecb4dc93ce0880cd5e80d196808bf1aebb89902ae11d52de7`; V1, linked A1, and A2 each have scalar 0.375 |
| Separate `W4-separate-37p5-01` | Timeline `a72f31e0-0ff5-41ff-91d3-bc2372c25d7b`; configured target V1 `base_picture.mov` UID `392fdb06-29f8-40e9-ace8-005399998b29`; linked A1 `a1_alpha_separate.wav` UID `6d2c4353-fe61-4b4c-9cc2-335bc7c28518` | Target V1: 100%/true before; setter returned true, read back 37.5%/true. A1 snapshot: 100%/true before and after | `exports/W4-separate-37p5-01.otio`, SHA `b9642e815dcf1eb8335aa86a8606c43558fcad35f25b5b2fed6853f1a50ad1b6`; only V1 has scalar 0.375; linked A1 has none |

Native action result SHAs: embedded `d96a3718e7c8fcbb5887b49c4651d2c71c3f307f7bad65646fd58f6c3a31f92c`; separate `1fb3a7e0c71c3ab9859e4fd2aea0002404914d1507c2287dea6fe6d2dfee3f5d`. The whole project remained at 13 timelines; no extra build or native mutation was performed during analysis.

### Raw action and terminal-render bindings

| Action | Evidence SHA-256 bindings |
|---|---|
| Embedded speed | `journal.jsonl` `113f01968b79f3a110f98b28b1a7539e88ed74f1ff13297cc191e673abb4ac06`; `pre.json` `50ca2db509e744938c554bcfdb9025eb121b0df7aa0efcbca56a47add33f8237`; `post.json` `9f7fb77132c2ddeea382a5d4e0b96089bf20e0a02a60823e6e2136f94424d269`; result `d96a3718e7c8fcbb5887b49c4651d2c71c3f307f7bad65646fd58f6c3a31f92c`. |
| Separate speed | `journal.jsonl` `fd6a2bc44392d3f9a7dd75e2ca42adb9302a514e52c9ec46162cfce84950467a`; `pre.json` `86a611c682d3248437d77d4deb375755a82ac947e0fa8bc9ff06a26932a4cca1`; `post.json` `06cdd2fdf6000004d06e2c9418afdf35960dd69bb006a2920b10bbacba26e64a`; result `1fb3a7e0c71c3ab9859e4fd2aea0002404914d1507c2287dea6fe6d2dfee3f5d`. |
| Embedded render poll | `journal.jsonl` `de6b876eb30bbad4839e9b2ce8c6277d6408d9d620d6d18287d941ebe48426c5`; `pre.json`/`post.json` `cce03b780204183bd865095a08348297fef749c535bb51744bfdf19349a9ce33`; terminal result `1ce2d786be45bcbece234e8935c5e2a177a7c1d4ac6405f9c300e14f1f0d3c83`. |

## Render and click measurements

Embedded render job `0db7e0c0-e2ef-49e2-a58f-9adad5a6841c` completed at 100% in 1818 ms. MOV `renders/W4-embedded-37p5-01.mov` SHA-256 `291a850e390f40efdc4a97a419c335965b77a8eaa276c5987d61af42decd5595`; ffprobe confirms H.264 640x360, 25/1 fps, 399 frames, 15.96 s, signed 16-bit stereo PCM at 48 kHz.

The clicks fixture manifest SHA is `49fe1898a6905b8e57a84e62c1f7c920e88946d43725774bc4ce84f3b3160db6`. The first five source impulses visible within the render are `[48001, 96777, 144959, 193919, 240001]` samples. At 0.375 they predicted `[128002.67, 258072.00, 386557.33, 517117.33, 640002.67]`; measured positions were `[128003, 258072, 386557, 517117, 640003]`, with differences `[+0.33, 0, -0.33, -0.33, +0.33]` samples. All 5 matched within ±1 sample.

The retained aggregate analysis is `out/issue149-workflow-reruns-20261002-kit-01/w4-analysis.json`; its SHA is recorded in `w4-analysis-check.json` (SHA `3ea5a93438a20d7f06bb10e64eb0e8a5f826eb06f11811e6dc347ac30647b275`). The focused semantic check passed exact scalars for both OTIO files and all five click timings. The embedded decode output is retained for source-ID/retime interpretation, without applying an unretimed frame-index assertion.

## Exact linked-item readback

- embedded pre video1 occurrence `6724ba9f-48f1-4ac6-aa2f-7500be267ea0`; MPI `a25cfcec-f490-4151-a608-6088dae3c5ec`; speed `{'status': 'ok', 'value': {'Percentage': 100.0, 'PitchCorrection': True}}`.
- embedded pre audio1 occurrence `d9a715f6-bf3b-482f-b69b-ca15a8ba7ed7`; MPI `a25cfcec-f490-4151-a608-6088dae3c5ec`; speed `{'status': 'ok', 'value': {'Percentage': 100.0, 'PitchCorrection': True}}`.
- embedded post video1 occurrence `6724ba9f-48f1-4ac6-aa2f-7500be267ea0`; MPI `a25cfcec-f490-4151-a608-6088dae3c5ec`; speed `{'status': 'ok', 'value': {'Percentage': 37.5, 'PitchCorrection': False}}`.
- embedded post audio1 occurrence `d9a715f6-bf3b-482f-b69b-ca15a8ba7ed7`; MPI `a25cfcec-f490-4151-a608-6088dae3c5ec`; speed `{'status': 'ok', 'value': {'Percentage': 37.5, 'PitchCorrection': False}}`.
- separate pre video1 occurrence `392fdb06-29f8-40e9-ace8-005399998b29`; MPI `b5b757fe-43a6-47d2-850c-2294da50c136`; speed `{'status': 'ok', 'value': {'Percentage': 100.0, 'PitchCorrection': True}}`.
- separate pre audio1 occurrence `6d2c4353-fe61-4b4c-9cc2-335bc7c28518`; MPI `903130dc-ad69-4dde-aa94-a8b40eb1090d`; speed `{'status': 'ok', 'value': {'Percentage': 100.0, 'PitchCorrection': True}}`.
- separate post video1 occurrence `392fdb06-29f8-40e9-ace8-005399998b29`; MPI `b5b757fe-43a6-47d2-850c-2294da50c136`; speed `{'status': 'ok', 'value': {'Percentage': 37.5, 'PitchCorrection': True}}`.
- separate post audio1 occurrence `6d2c4353-fe61-4b4c-9cc2-335bc7c28518`; MPI `903130dc-ad69-4dde-aa94-a8b40eb1090d`; speed `{'status': 'ok', 'value': {'Percentage': 100.0, 'PitchCorrection': True}}`.

Retimed test timelines are intentionally retained in their measured state. General variable-speed, other frame rates, and word-edge timing are untested. The named constant-rate output supports bounded time-map reconciliation; separate-source linked audio must be explicitly handled and verified.
