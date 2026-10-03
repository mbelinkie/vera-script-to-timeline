# Issue #149 D6-kept W6 discriminating result

Task ID: #149 / `/root/discriminator_output_verify`

## Challenged claim and classification

This case tests the first of the two new W6 discriminators: atomically replace a linked source file while preserving its original modified time, call `RelinkClips`, and render. The expected result is that Resolve continues rendering the cached original bytes, decoded as source ID 1. The case is **reproduced**.

This result is narrower than the earlier W6 result. It does not claim that every replacement or every `RelinkClips` call behaves this way, and it does not replace the pending changed-modified-time case.

## Run identity and preconditions

The run used Resolve Studio `21.1.1.10`, CPython `3.14.7`, x86_64 macOS 15.1, External Scripting `None`, and Resolve's injected object through the registered Workflow Integration. The project was the new disposable synthetic project `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`.

The target timeline was `D6-kept-r2-20261003`, UID `70aee9bd-5928-4e3b-9f0e-f45897773337`, with V1/A1 linked to the same `base.mov` MediaPoolItem UID `dfdd5a46-c202-4493-84ab-f8e9d83c81b1`. The V1 item UID was `4a2c7322-d973-4526-943f-6b0620c7d4f1`; its linked A1 item UID was `26387e10-02cc-4b8b-952a-bc41277301de`. Both occurrences covered timeline frames 0–398 and source frames 0–399. A2 (`a2_numbers.wav`) and A3 (`a3_bed.wav`) were retained as independent control tracks.

The baseline render used 640×360 H.264 QuickTime, 25 fps, 48 kHz 16-bit LPCM, full timeline. Its terminal job was `fa550bdf-3df3-49cc-89c6-f3a7afdc12a3` and its output was `D6-kept-r2-baseline.mov` with SHA-256 `dbcf1eb576b12c65fa97a7b2109fc7ca160e7c472d59035d82efe46554210d9a`.

## Exact operation and observed result

The original `base.mov` bytes had SHA-256 `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036`, inode `548023074`, and mtimeNs `1790976491073030271`. The owned native swap atomically replaced that path with `relink_alt.mov`, whose SHA-256 was `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579`. The resulting inode was `548129868`, while mtimeNs remained exactly `1790976491073030271`.

The native swap receipt confirmed the expected original and replacement hashes. The replacement was audio-bearing and stream-compatible: 640×360 H.264 video, 25 fps, mono 48 kHz PCM audio, 400 source frames. The MediaPool readback remained `Online`, with the same path, `Date Modified` display (`Fri Oct 2 17:28:11 2026`), frame count, and audio layout.

`RelinkClips` returned native `True`. The relink render was staged once as job `9d3ea484-48c8-4b08-9802-d4bc0191000c`; its matching poll reached `JobStatus=Complete` at 100% without replay. Output:

`out/issue149-workflow-discriminators-20261003-kit-02/renders/d6-kept-r2/D6-kept-r2-relinked.mov`

Output SHA-256: `5b5168f85d70745ce11e0470ba323db27aa2129e5a59f92adf94b126d654f916`.

Independent output analysis decoded 399 rendered frames, all source ID 1, with zero frame-code mismatches. The decoded picture therefore retained the original source markers even though the on-disk content hash had changed and `RelinkClips` returned `True`.

The relinked output audio matched the baseline analysis: 766080 samples; A1 1000 Hz pilot `0.02828`, A2 1500 Hz pilot `0.01986`, A3 2000 Hz pilot `0.02003`; all eight A1 NATO words (`alpha` through `hotel`) and all eight A2 number words (`one` through `eight`) were present. The baseline and relinked MOV container hashes differ, but their decoded source-ID sequence and measured audio matched.

## Restoration and save checkpoint

The owned restore atomically replaced the changed `base.mov` with the original bytes from `swap.mov`. Before restore, the target hash was the replacement hash and inode `548129868`; after restore it was the original hash, size 3443686, inode `548130164`, and mtimeNs `1790976491073030271`. `bytesRestored` and `mtimeRestored` were both `True`.

The restored `RelinkClips` returned `True`. Render job `0b197d4f-e0e2-4444-8aad-1531552078ac` reached terminal `Complete` at 100%. The restored output was `D6-kept-r2-restored.mov`, SHA-256 `21ca2ce41ee9e4c4a719176cf4850a7fa0af51a93fae222a9b3ce91aa6bbc76f`. It decoded as 399 frames of source ID 1 with zero frame-code mismatches and had the same pilots, sample count, and 16 detected words as the baseline. The retained analyzer comparison reports `analysis_equal: true`; full MOV hashes differ because container bytes differ.

One `SaveProject()` call after restoration returned `True`. Its complete pre/post pair was byte-identical (both pair SHA-256 `b8a7b82f9585afbd5703a8113fed6f4f9f6d9d7e6debcc260d161fbe13a99422`).

## State-pair attribution and limitations

The before-swap pair and after-swap pair were each byte-identical. The relink-render pair contains expected render-context differences: a render queue entry, temporary 640×360 output settings, Deliver-page context, in-progress state, and transient missing property reads while the render was active. The restored-render pair has the same kind of render-context differences. The post-restore save pair is equal, and the timeline/item identities and content remain the same.

Comparing the original saved checkpoint with the final restored save identifies only three top-level differences: page `edit` → `deliver`, render queue length 0 → 3, and the current timeline playhead `00:00:15:24` → `00:00:00:00`. The three queue entries are attributable to the baseline, relinked, and restored render operations. The page and playhead changes were observed in the render workflow but their precise causal event was not isolated; they are context drift, not evidence of a source or timeline-content change. No unrelated timeline or media identity change was found.

## VERA consequence and remaining alternative

For this exact Workflow Integration case, Resolve's `Online` status and displayed modified date remained unchanged while the source content hash and inode changed. A successful `RelinkClips` return did not establish that the rendered bytes switched. VERA therefore needs content-hash detection and output verification when it must establish source identity. The candidate reload rule to test in the changed-time case is:

> Detect replacement by content hash; force reload with a changed modified time → `RelinkClips` → render verification.

The changed-modified-time case must reproduce source ID 2 before adopting that sequence as a bounded #141 design input. This case does not establish a universal Resolve cache mechanism, a guarantee for fractional or other retimes, or any lineage/identity property beyond the observed decoded source markers.

## Retained evidence

The main output analyses are:

- baseline: `out/issue149-workflow-discriminators-20261003-kit-02/analysis/d6-kept-baseline-r2.json` (SHA-256 `38d0ab443b0c018709a34479b0cc1a9bf43b499255e616920bffc934f009073d`)
- relinked replacement: `analysis/d6-kept-relinked-r2.json` (SHA-256 `0345c77a2c7c721558a30553c5f018c336cd36555d9b77805ce0dc829db7446b`)
- restored independent analysis: `analysis/d6-kept-restore-independent.json` (SHA-256 `e03d3806c88ea83a887730efdb880ce26f95a877b6e983f4f54ceaf2082b58b1`)
- retained restore comparison: `analysis/d6-kept-restore-r2.json` (SHA-256 `9daf93ad3056e6ea15b6e75ccaceefb64f901cfea26f7cd85f9c0ba30f578c88`)

The native swap operation is `native/d6-kept-r2-swap.json` (SHA-256 `9b9bd797fc01cd734c8924c26615ba685320003330fd8074e710e123b04c5a04`); the restore operation is `native/d6-kept-r2-restore-operation.json` (SHA-256 `a273a9ae1f9dd15c2df2bff8067d223d3c1e7134f33af826480308609ad25277`). Complete before/after pairs and journals are retained under `evidence/w6-kept-*` and `evidence/save-d6-kept-restored-*`. The terminal relink result SHA is `09a62a9c0bc66c7218b363342203ef8aefa352c0620ddfacad014723fe85e142`; the terminal restore-poll result SHA is `8f78352c3705853303dbda8400a00eacd4fb30af90b4c45cee64d14f97ddfb71`; the final save result SHA is `56da3147ffc7038ad70251cec23fbe6cb4296d998af6ac2f333d5f777315a502`.
