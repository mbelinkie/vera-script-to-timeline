# Workflow Integration W6 discriminators — independently verified

Both producer-requested atomic replacement cases reproduced on Resolve Studio **21.1.1.10**, External Scripting **None**, injected Workflow Integration object, in the new disposable synthetic project `VERA Issue 149 WI Discriminators 20261003-kit-02`. The protected #141 project and `semi1b.mp4` were excluded.

- Kept modified time: rendered original source ID **1** after replacement and `RelinkClips=True`.
- Changed modified time by +1 second: rendered replacement source ID **2** after `RelinkClips=True`.
- Both cases restored original source hash/time, relinked once, verified restored source ID 1 and retained equal save pairs.

This explains the prior W6 discrepancy for these tested setups and supports the requested bounded #141 design input: **detect replacement by content hash; force reload with changed modified time → `RelinkClips` → render verification**. Online/Date Modified/relink success remain insufficient. No universal codec/cache guarantee is claimed.

W3 discriminators are still in progress. #149 remains open for producer review. Complete #141 new-result fields and retained evidence references follow. References under `out/` are local retained artifacts, not public downloads.




## Issue #149 D6-kept W6 discriminating result


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

## Issue #149 D6-changed W6 discriminating result


## Challenged claim and classification

This case tests the second W6 discriminator: atomically replace a linked source file and set a new modified time, call `RelinkClips`, and render. The expected result is that Resolve reloads the replacement bytes and the render decodes as source ID 2. The case is **reproduced**.

Together with D6-kept, this supports the bounded reload design input. The two results are still scoped to this synthetic media layout and this Resolve/Workflow Integration run; they do not establish a universal cache implementation or make a successful native return sufficient evidence of a source switch.

## Run identity and preconditions

The run used Resolve Studio `21.1.1.10`, CPython `3.14.7`, x86_64 macOS 15.1, External Scripting `None`, and Resolve's injected object through the registered Workflow Integration. The disposable project was `VERA Issue 149 WI Discriminators 20261003-kit-02`, UID `0591bb41-d645-4af7-a2ee-ff75f8f43162`.

The target timeline was `D6-changed-r2-20261003`, UID `eea50181-c786-4698-9318-bb1100d12576`. Its V1/A1 linked source was MediaPoolItem `0b89e658-4617-408d-bd5d-03291c1f889a` (`swap.mov`): V1 item UID `6acc3e2c-3262-45f5-ae17-89755de39191` and A1 item UID `74ba68da-6afb-45c2-8a73-68b0892c1b85`. The same 640×360/25 fps/mono 48 kHz PCM layout used for the kept case was retained. The same full-timeline render settings were used: 640×360 H.264 QuickTime, 25 fps, 48 kHz 16-bit LPCM, mark-out 398.

## Exact replacement and render operations

The original `swap.mov` bytes had SHA-256 `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036`, inode `548023084`, and mtimeNs `1790976491428416718`. The native atomic replacement used `relink_alt.mov`, SHA-256 `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579`, and set the target mtimeNs to `1790976492428416718`. The resulting inode was `548130899`; both `mtimeChanged` and `hashChanged` were true.

The replacement retained the same video and audio stream geometry, including a mono 48 kHz PCM audio stream. The MediaPool display remained online at the same path and its displayed Date Modified did not provide the content identity used for this test. After the external replacement guard, the exact injected API operation was `project.GetMediaPool().RelinkClips([swapMediaPoolItem], relinkFolder)`, where `swapMediaPoolItem` was object handle `0b89e658-4617-408d-bd5d-03291c1f889a` and `relinkFolder` was the kit `media/` directory; the native return was `True`. The replacement receipt records `os.replace`-style atomic replacement from `relink_alt.mov` followed by `os.utime` to requested mtimeNs `1790976492428416718`.

The baseline render reached terminal completion on job `b71e75a7-efe0-46e0-9e85-a5cc57482024`. After replacement, `RelinkClips` returned native `True`; the relink render was staged once as job `3b4c4481-b1da-48b5-a2ed-b448f507f6e4`, and its matching poll reached `JobStatus=Complete` at 100% without replay.

Outputs:

| Render | Output | SHA-256 | Decoded source |
| --- | --- | --- | --- |
| Baseline | `D6-changed-r2-baseline.mov` | `bafd8560c17b0f0793bf4abe267ee281b516167ff09c6c8cb252c26ee444f951` | ID 1 |
| After new-mtime replacement + relink | `D6-changed-r2-relinked.mov` | `203e81dde9adae06b684074a1862fd5f3ad1a6a37541722392a958ebea784ef` | ID 2 |

Both renders decoded 399 frames with zero frame-code mismatches. The relinked render's first, frame 123, and last decoded markers were source ID 2 with the expected frame indexes. The analyzer's `analysis_equal` field compares the audio measurements only; it must not be read as full audio/video equality. The video source-ID change is the decisive result.

Both audio streams measured 766080 samples, pilots A1 1000 Hz `0.02828`, A2 1500 Hz `0.01986`, A3 2000 Hz `0.02003`, and all eight A1 NATO plus all eight A2 number words. The replacement's audio is intentionally equivalent, so audio equality does not weaken the source-ID result.

## Restoration and save checkpoint

The owned restore atomically replaced the changed `swap.mov` with the original bytes from `base.mov`. Before restore, the target had replacement hash, size 4593112, inode `548130899`, and mtimeNs `1790976492428416718`. After restore it had the original hash, size 3443686, inode `548131480`, and mtimeNs `1790976491428416718`. `bytesRestored` and `mtimeRestored` were both `True`.

The restored `RelinkClips` returned `True`. Render job `f0eb2283-5a9e-4c62-80e8-6d565938f226` reached terminal `Complete` at 100%. The restored output was `D6-changed-r2-restored.mov`, SHA-256 `75f7139ed4a0dcda6e4b6da09729ed1739d8f710d8edc1057e6720bd8b08eca8`. It decoded as source ID 1, 399 frames, zero frame-code mismatches, and matched the baseline's audio measurements and words. The retained comparison reports audio `analysis_equal: true`; full MOV container hashes differ.

One `SaveProject()` call after restoration returned `True`. Its complete pre/post capture pair is byte-identical, both SHA-256 `3a003a04cd0b12ae30f5c08486173179f0f858ffbdad0ae4a252a0ca872a1243`.

## State-pair attribution and limitations

The baseline-poll and after-swap pairs are byte-identical. The relink-render pair contains the expected render-context changes: one new render queue row, temporary 640×360 output settings, Deliver-page context, in-progress state, and transient property-read differences while rendering. The relink-poll pair is byte-identical. The restore-render pair has the same render-context pattern, and the restore-poll pair and final save pair are byte-identical.

The final project is on the D6-changed timeline, so comparison with the original pre-case checkpoint also includes the expected current-timeline selection change and six render queue entries from the two W6 cases and their restores, plus Deliver-page/playhead context. These are test progression/context effects. No unexplained source or timeline-content mutation was found within the changed case's complete terminal pair.

## VERA consequence and remaining alternative

This case reproduces source switching only when the replacement has a changed modified time: hash change + changed mtime + `RelinkClips` + render produced decoded source ID 2. D6-kept showed that the same hash change with unchanged mtime left decoded source ID 1. The paired evidence supports the bounded VERA design input:

> Detect replacement by content hash; force reload with a changed modified time → `RelinkClips` → render verification.

The output verification step remains required. `RelinkClips=True`, Online status, and displayed Date Modified alone cannot prove that Resolve rendered replacement bytes. This evidence does not establish behavior for other codecs, cache states, timeline constructions, retimes, or arbitrary file replacement methods.

## Retained evidence

Primary analysis:

- `out/issue149-workflow-discriminators-20261003-kit-02/analysis/d6-changed-r2.json` — SHA-256 `9c420a633184fed4d47bc54fd4c81b31665695a538bbcb1261b2bf63d1f6a0b5`
- `analysis/d6-changed-restore-r2.json` — SHA-256 `8eccb50955b5c9aeb43f1ae0f233a8e6e818c8b8657e54300fd71ae6fe1e3924`

Native replacement and restoration records:

- `native/d6-changed-r2-swap.json` — SHA-256 `adf60bbe23cfe1c0c5967d3101634df2206a108b52b45d8e8f664ff9b505e691`
- `native/d6-changed-r2-restore-operation.json` — SHA-256 `cd3be40a6bb1397dd26100d5e9b1e588638b0a3151d2ddfc1496b6a2fa24feb3`

Terminal native result hashes:

- changed relink poll: `fa0155fd1e3943a828ce8866c41776ac2208904a8e98e58d06ae26f55187a20e`
- changed restore poll: `ba2a82ab3dd3f9022d04a57792b7a9f5314492cb038f56a2adb05f08ca15c21b`
- final save result: `764b4a03b9336bcdc2cd2b9d9dca027704b897f43b986b7cf6525fdbe98a51a6`

Complete before/after pairs and journals are retained under `evidence/w6-changed-*` and `evidence/save-d6-changed-restored-*`. The replacement render-stage result, relink render result, terminal poll result, restore result, and all complete pairs are retained in the same kit.
