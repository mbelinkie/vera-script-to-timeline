# Issue #149 D6-changed W6 discriminating result

Task ID: #149 / `/root/discriminator_output_verify`

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
