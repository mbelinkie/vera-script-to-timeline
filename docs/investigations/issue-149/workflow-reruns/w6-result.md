# Issue #149 W6 result

Task ID: #149. This is a read-only verification of the generated W6 swap, no-relink, relink, and restore+relink cases. Resolve was not called from analysis.

## Challenged claim

The Phase 10 W6 handoff expects the render after same-layout byte replacement, before relinking, to fail with a decode error. After `RelinkClips([item], folder)`, the render should complete with replacement source ID 2. Restoring the original bytes followed by relink should return source ID 1. These are output-based gates; a native `True` relink return is insufficient.

## Classification

**Adverse/no-switch.** The replacement, native relink calls, render jobs, restoration, and save checkpoint all completed. The expected pre-relink decode failure was not reproduced: that job completed with source ID 1. The relink render also retained source ID 1, failing the source-switch gate even though `RelinkClips` returned `True`. The restored render retained source ID 1 and its PCM matched baseline.

## Native chain

The owned timeline was `W6-swap` (`ef85640d-1bab-451b-a9c7-eb73b14251e8`) in project `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; its four item UIDs are recorded in `out/.../w6-analysis-check.json`. All four render polls were terminal `JobStatus=Complete`, 100%:

| case | render output | job | result evidence SHA-256 |
|---|---|---|---|
| baseline | `W6-baseline-01.mov` | `228fae45-1e2a-4bce-a074-4292c6076a5a` | `cfabfc93cc255d0c5ec09a53d3c4c924f91eb995350894e5e8191c86410b7ae3` |
| after swap/no relink | `W6-no-relink-01.mov` | `2f253e30-8e07-48e3-bbd9-4504a63b8a07` | `9181e4cb2c347e43e2432bcadbe12fa8968c100517318d4fa85711acd1b0ecd0` |
| relink | `W6-relinked-01.mov` | `f635ec8d-4925-4a3f-af41-91cb72f8819e` | `aeefc55413046c651805cad7114a630c783c1dd223834068a6f7ccf961030c01` |
| restored + relink | `W6-restored-01.mov` | `e80367fb-e97f-4dd2-b8ac-d8d9a1689f50` | `2faf996d3fdfe87493fba97c46b08b656c6dede9c799dd830e34f5edcc3d13f6` |

The external swap replaced original SHA `164348e62292c173ac23708244f6350c6a2d6211667930ebadffacc1021a7036` with replacement SHA `2bad2d2457c3d572d2fe3542ef22da915ec38306c8985026bec10d1289f76579` while retaining the original `mtimeNs` exactly (`1790976491428416718`). `restore-01.json` records restoration of the original bytes and the retained backup. The native relink calls returned `True` in both replacement and restored phases.

## Measured output

The analyzer found all 16 expected words and identical pilots (`1000=.02828`, `1500=.01986`, `2000=.02003`) in all four renders. Each decoded 399 frames with zero frame mismatches. Source IDs were `1` for baseline, no-relink, relink, and restored; therefore the relink render is an observed no-switch despite its native `True` return, and is classified by its completed media rather than by the return value.

All four MOVs decode to the same 3,064,320-byte PCM s16le stream (`f0e1d5c4dc4c52e2d68d4a7ea92ba683f2c736b5dad059867e86e82dcf203b96`). Baseline and restored full-container hashes differ because the MOV containers differ (`6ef615c684208e67824b7062215daef1ac675a3f589ccbc3a7146b855ccdf491` versus `8e4c2fed0c9afeb9373e2ee8a75d7ddc0a4c9588685b9ec841189dea0afb8d78`), while PCM content is byte-equal. Full media hashes and analyzer details are in `out/.../w6-analysis.json` and `out/.../w6-analysis-check.json`.

The captured `swap.mov` pool entry stayed `Online` with `Date Modified = Fri Oct  2 17:28:11 2026` and the same path in every W6 pre/post snapshot. This reports the observed API metadata; it does not establish why the native relink did not switch the decoded source marker.

## Run identity and native binding

The W6 injected run used DaVinci Resolve Studio `21.1.1.10`, CPython `3.14.7`, x86_64 macOS `15.1`, and External Scripting `None`. The immutable harness probe is `be467c29fad0f7c8da474eadc9f51ec4a6e7b13f64ee479bebd7eaeceda0cc93`; the launcher SHA is `e4f58381c398bc0ce13130fddb25c956876f7754dc877346fe389dfb826c2450`. Project UID is `1a05ff3a-8b04-43e3-95ab-c970b93b6415`; timeline `W6-swap` UID is `ef85640d-1bab-451b-a9c7-eb73b14251e8`.

The W6 item/MPI bindings were: video item `f7d60eff-cb40-483e-badf-3703d0129820` and linked audio item `72b4dec9-d450-4450-bd3b-47801cfb009b`, both MPI `d307edb5-a0a0-45f1-8547-9472ca1da827` (`swap.mov`); A2 item `7dcd99a9-1dd8-4a64-b56e-68d62b249d85`, MPI `a23c9a6e-1640-4db8-b380-b16870ced30c`; A3 item `642d480d-7cf7-4221-b43b-dbf232851769`, MPI `aa4454ba-ce62-4511-976e-e4d1ff92689d`. The exact owned UIDs and all immutable parameter records are retained in `w6-analysis-check.json`.

The action sequence was `select-timeline-w6-preswap-01-20261002-kit-01`, `w6-before-swap-01-20261002-kit-01`, `render-stage-w6-baseline-01-20261002-kit-01`, `render-poll-w6-baseline-01-20261002-kit-01`, `w6-after-swap-01-20261002-kit-01`, `render-poll-w6-after-swap-01-20261002-kit-01`, `w6-relink-render-01-20261002-kit-01`, `render-poll-w6-relinked-01-20261002-kit-01`, `w6-restore-relink-01-20261002-kit-01`, `render-poll-w6-restored-01-20261002-kit-01`, and `save-checkpoint-w6-restored-01-20261002-kit-01`. The final save receipt is `8625c9785827dedd443c898304f04e73b5d0bb0755a5edd3a009811b58b8217b`, with `calledExactlyOnce=true` and `return=true`.

## Gate and reconciliation consequence

The challenged W6 gates are: pre-relink render fails with the named decode error; relink produces source ID 2 and replacement audio; restore+relink produces source ID 1 and PCM byte-equal to baseline; all jobs reach a recorded terminal status and native calls/pairs are retained. The expected failure was not reproduced, and the relink source-switch gate failed: both outputs completed with source ID 1 and baseline audio. Baseline, terminal observation, and byte/mtime/PCM restoration checks passed. This distinction preserves the original handoff's expectation rather than redefining success around our observed result.

VERA reconciliation cannot treat this relink API return as proof that the timeline now references replacement media. A relink-sensitive automation path needs a rendered source-identity check and a narrow manual review or a narrower, explicitly tested sequence. Cache invalidation, project reopen, alternate selection context, and other relink-context follow-ups were not run here. The result does not demonstrate a core authoring failure: the owned timeline, item bindings, native calls, renders, restoration, and save all completed; only replacement-media observability remained adverse.

## Native action and parameter bindings

Each row names the exact action ID and the SHA-256 of its immutable parameter and result records.

| action ID | params SHA-256 | result SHA-256 |
|---|---|---|
| `select-timeline-w6-preswap-01-20261002-kit-01` | `f01b0b22dfc9666d37d52b06df17b7acb25a20b810e9d4f9e45f77a8e8affbaa` | `0790323c8edea80e33629a31659d32a88f43fb47f4a26b0e89a11c5c6fde6f18` |
| `w6-before-swap-01-20261002-kit-01` | `0de2cf326752612ef33b642b0173a5bea2b2b7eb6d785b524a61089cabe62db5` | `3955dedfe85b88b3d9839c42c5bb4410364e9e70582879f86ae179fa5b8ef90f` |
| `render-stage-w6-baseline-01-20261002-kit-01` | `c6aba7c342d6293eff88f3fa98bc2296ee6f028eef8b2677a57c31b5aae23586` | `58fa17fe2e92e2a29168f53adf71b178456f17fd1e5e6a0aa3a1de43eb1a2293` |
| `render-poll-w6-baseline-01-20261002-kit-01` | `52446f282909bfeaf377984f67a14f0170f43786b69d5234a6c66d596cfbfec6` | `cfabfc93cc255d0c5ec09a53d3c4c924f91eb995350894e5e8191c86410b7ae3` |
| `w6-after-swap-01-20261002-kit-01` | `38b7fe52651c98bbeb325ba611006c32368563179707873c67e4e06cd28db70b` | `2e542d1d8f34b2869946340e679d36231575cda3a8306b770e611f1dbe24a3d5` |
| `render-poll-w6-after-swap-01-20261002-kit-01` | `187588978fe1e2e8691b897d1412e5fd6c99c5f91fd1765a3e2e986585f144a2` | `9181e4cb2c347e43e2432bcadbe12fa8968c100517318d4fa85711acd1b0ecd0` |
| `w6-relink-render-01-20261002-kit-01` | `af2abeef8800c2721b78e53ea3b993bc8e613e2a1e4dd9ed7bf760eb18305279` | `4b8fcda75b4709986e3d4b7d95418a267d40f1677700fc157269926aff1bc06a` |
| `render-poll-w6-relinked-01-20261002-kit-01` | `56c1fd36e92141e7e288bf1db5fb2828288b87aa3d0794a25c9602decd15787f` | `aeefc55413046c651805cad7114a630c783c1dd223834068a6f7ccf961030c01` |
| `w6-restore-relink-01-20261002-kit-01` | `d7dc6807ea09d2f9b6e8f06f4472162baad6834cc6c15bde4b5ca0f4ea6a8660` | `cec8594c1ef91c8d70704bf8029735bf8e29f97f969d3f2abf42295595f73bd2` |
| `render-poll-w6-restored-01-20261002-kit-01` | `67694179e706274604efb7637fb9fe350b34c285aac265800c93c85a9316f670` | `2faf996d3fdfe87493fba97c46b08b656c6dede9c799dd830e34f5edcc3d13f6` |
| `save-checkpoint-w6-restored-01-20261002-kit-01` | `c0ff07962b19542fd8d5e6ba75754863ab850e69d0d69983c436c56d407c1fae` | `8625c9785827dedd443c898304f04e73b5d0bb0755a5edd3a009811b58b8217b` |

## Alternative explanation

The external swap and restoration records prove the original and replacement bytes used here, and the generated media manifest is retained with the analyzer output. The snapshots kept the same path, `Online` state, and `Date Modified`, so this run does not distinguish cache behavior from other Resolve relink-context behavior. The unrun cache/context follow-ups remain bounded open questions; no fixture-version or Resolve-version cause is claimed.

Artifact bindings, evidence-journal hashes, terminal poll records, exact UIDs, full media hashes, and PCM hashes are retained in `out/issue149-workflow-reruns-20261002-kit-01/w6-analysis-check.json` (SHA-256 `46f14464d69f45552992291799024bb38a6a79b5998215714771f2669f95326c`).

## Provenance and fixture interpretation

The fixture gate defines original `base.mov`/source 1 as embedded A1 NATO audio (`alpha`–`hotel`, 1000 Hz), and `relink_alt.mov`/source 2 as `cutaway.mov` plus A2 number audio (`one`–`eight`, 1500 Hz), with identical mono PCM48k and H.264 640x360/25 stream layout. The W6 replacement SHA is therefore an A2-bearing source-2 ground truth, not an inference from its filename.

`swap-01.json` records `atomic os.replace`: the inode changed (`547705168` → `547844691`) while `mtimeNs` stayed `1790976491428416718`; `restore-01.json` records the original bytes restored with the backup retained. The raw replacement procedure is an observed file operation, not an established causal explanation. Swap/relink/restore journal SHA-256 values are respectively `b6eab5f78685a1dc08bb90935fed9304b761ae0fb49cd8e93f04d8bf45b6e9fa`, `8ebc249dcfdbdf49f5eecfddbddc6032c92316d66a56db172443a00e311102c6`, and `c3614555ef10314328c20d685c2e27f43b09494f7371d1dcf44ed5a0444e7b3b`. The immutable installed scripting references were README SHA `5f58c94da8ec3c1f390d77ad9c60675263591dc101159b302e50b5774513830b` and `DaVinciResolveScript.pyi` SHA `2755259ef5f57b5d477786f799892e5b86ed3945db84bf88fb69bf751b36e651`.
