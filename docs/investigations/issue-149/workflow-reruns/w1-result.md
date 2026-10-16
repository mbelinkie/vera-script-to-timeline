# Task ID #149 — W1 subtitle/render result

## Challenged claim

The three W1 subtitle timelines preserve the configured linked-cut, picture-only-cut, and disabled-A1 cases, and the completed renders contain the corresponding speech. Raw subtitle tokens remain verbatim in the native snapshots; the audio gate separately recognizes the fixture speech words.

## Classification

**Measured W1 gates pass.** All three subtitle requests reached a read-only `JobStatus=Complete` poll, each render reached `JobStatus=Complete` at 100%, and each output matched its configured speech case. The generic full-sequence decoder check is valid for the disabled-A1 full-source timeline, but is the wrong assertion for the two intentional cut timelines: their native snapshots produce a 1-frame black gap and black tail around the source cut. The retained checker failures for linked/picture therefore record a checker-shape mismatch, not a Resolve or subtitle capability failure.

## Run identity and native binding

Injected Workflow Integration run: DaVinci Resolve Studio `21.1.1.10`; CPython `3.14.7`; x86_64 macOS `15.1`; External Scripting `None`; source hashes are action-specific: `0810d527f006a805e81fda9e73671c31871daaa9a13a74342f1dd96b89ff049d` for linked-cut, `be467c29fad0f7c8da474eadc9f51ec4a6e7b13f64ee479bebd7eaeceda0cc93` for picture-only and disabled-A1 (the earlier baseline build used `25d3bf…e003c3`). Project `VERA Issue 149 Workflow Reruns 20261002-kit-01`, project UID `1a05ff3a-8b04-43e3-95ab-c970b93b6415`.

| Case | Native subtitle timeline UID | Subtitle item UIDs and exact text/range | Render job / completion | MOV SHA-256 | Analysis JSON / check-record SHA-256 |
|---|---|---|---|---|---|
| `W1-linked-cut-01` | `a481d34a-69e6-4256-9797-634f93c42b8b` | `6c8769c9-e93f-43d0-b19e-16aea378303e`: `Alpha 1 Bravo 2 Delta 3 Echo` [13,174]; `0a8dc045-2f10-416a-b5bd-533c738bdc9d`: `4 Foxtrot 5 Golf 6 Hotel 7 8` [174,393] | `7c9cfef7-08f3-42cb-8a67-fd893e72a8b4`, Complete 100% | `71e48f25ef0592ec14d63d2fe6fada6205854ab45c60581db5d4e64f9e390012` | analysis `b46ba28860d4210e08b8eef99ab1ac4417c17fc0f14ace897ae2eea8d4419900`; check `79b53ad49e346522a4a62169bbb2757e2f4b68bc527b38f45b2c24e0cd5bf367` |
| `W1-picture-only-cut-01` | `e99194cf-8afe-4bb8-be1a-0fa6130807e3` | `9e891ae6-24b9-485f-98ae-ee943bac409a`: `Alpha 1 Bravo 2 Charlie 3 Delta 4 Echo 5` [13,247]; `f4c9db35-bbdb-4762-a775-905e00518436`: `Foxtrot 6 Golf` [263,322]; `429af495-5fb3-4d02-9066-f069474ed76a`: `7 Hotel 8` [336,393] | `d9117d8c-f6cf-42cf-b07b-d8decd0ae72b`, Complete 100% | `56614e21ad79a09a167e312e16156eebbcdaaa3e0c544c23f38d88ff213245ac` | analysis `76b153711d0c801b049096d467fdb35406698aaf530be1b9a10c8f1f65def2ea`; check `9963250c43dab708612e7ee3d4b6dab369455f40fef9dc874cdb839bbd206a9d` |
| `W1-disabled-A1-01` | `4affc46e-42ef-45c6-b59d-db9cd4678551` | `3330a02d-86ea-4b9a-927c-01ea3cddc49a`: `1, 2, 3, 4, 5, 6, 7, 8` [38,392] | `68644dd7-adbe-4b20-91d1-13915acd96e0`, Complete 100% | `de28ca47ec67218417384792b8befb55185b7c916ef9cc70e4e52fe6a8a6f307` | analysis `d0aaba68b8850fd854323feeb08741056c8c957a8bb0e956ad65088e40e4ab6c`; check `df712c7332c35bfd6be697d4fe80459bd50a20280d0c129846e4e40d9468a1f2` |

All MOVs independently probe as H.264 640x360, 25/1 fps, 399 frames, 15.96 s, signed 16-bit stereo PCM at 48 kHz with 766080 samples. Render stage settings were fixed at MOV/H.264, 640x360, frame rate 25, `lpcm`, 48 kHz, 16-bit, with `MarkIn=0`, `MarkOut=398`.

## Speech and decode measurements

| Case | Expected / observed speech | Pilots (1000 / 1500 / 2000 Hz) | Decode |
|---|---|---|---|
| linked cut | NATO `alpha bravo delta echo foxtrot golf hotel` (Charlie absent); numbers one–eight | `.02481 / .01991 / .02005` | 399 frames; native cut semantics: source 0–98, black frame 99, source 150–398 at output 100–348, black tail 349–398 |
| picture-only cut | NATO alpha–hotel; numbers one–eight | `.02828 / .01986 / .02003` | Same intentional cut semantics; 300 mismatches only against the generic uncut full-source expectation |
| disabled A1 | numbers one–eight only; NATO alpha–hotel absent | `.00043 / .02004 / .01988` | 399 frames, all source 1 frames 0–398, zero mismatches; semantic checker passed |

The native cut shape is independently visible in the post snapshots: linked-cut clips are timeline `[0,99]`/source `[0,99]` and timeline `[100,349]`/source `[150,399]`, with the remaining output tail black. The analyzer preserves raw caption strings. The disabled caption's numeric `1..8` text is retained verbatim; comparison to spoken `one..eight` is an explicit fixture lexical mapping, not silent ASR text rewriting.

### Physical cut geometry and decode attribution

The build dispatch uses an exclusive-end convention for both cut cases:
`base.mov` source `[0,100)` at record frame `0`, then source `[150,400)` at
record frame `100`. The linked case places those AV ranges on V1/A1; the
picture-only case places those ranges on V1 while its A1 is the independent
full-range audio placement `[0,400)` at record frame `0`. Raw native
record Start/End values are `0/99` and `100/349`; raw source Start/End
values are `0/99` and `150/399`. These are getter values, not an assertion
that every listed endpoint is an occupied frame. Independent frame decoding observes source frames
`0–98`, black output frame `99`, source frames `150–398` at output frames
`100–348`, and black tail `349–398`; this decode occupancy is an output
measurement and does not change the configured exclusive ranges.

## Operation and checkpoint evidence

Each case duplicated one configured source exactly once, polled only after the subtitle job settled, and rendered once. Save checkpoints returned native `True` exactly once for all three. The first linked-cut subtitle request retained a `SaveProject refused the W1 duplicate` harness failure (`b09a0a5c9f1832b59234b889b691caafb166dbffb27226cf2d746af95aff7576`); no subtitle request was repeated. Its later read-only poll completed with the two items above, a fresh save checkpoint returned `True`, and the existing duplicate rendered successfully. This is the known checkpoint ordering bug, not a capability failure.

Retained evidence lives under `out/issue149-workflow-reruns-20261002-kit-01/`: each case has the native request/poll, render-stage/poll, save-checkpoint result, pre/post snapshots, analysis JSON, and the corresponding `*-analysis-check.json`. The initial analysis-check command mistakenly used an uncut source-index expectation for linked/picture and failed only on that structural assertion; audio gates passed. No source bytes, fixtures, contracts, or native state were changed by this analysis.

## Success requirements and VERA effect

The named three cases reproduce #149’s timeline transcript behavior through Workflow Integration. Subtitles and independent rendered word sets distinguish a linked speech cut, a picture-only cut, and disabled A1. This supports bounded spoken-omission reconciliation using a duplicate timeline on the Edit page, waiting for the asynchronous status and subtitle items, and checking transcript quality/coverage. It is phrase-level ASR, not word-exact timing or proof of arbitrary routing; all relevant speech sources still require fresh transcription/alignment coverage. Original source timelines remain intact; three subtitle duplicates are intentionally retained. No core authoring failure is established.

Native request identities and attribution:

- `w1-subtitle-request-linked-cut-01-20261002-kit-01`: source `bf87f303-1a54-4cb4-ae9c-af9cd0949d12`, duplicate `W1-linked-cut-subtitles-01`, request result SHA `b09a0a5c9f1832b59234b889b691caafb166dbffb27226cf2d746af95aff7576`. Its journal/pair directory retains `post-partial.json`; the later settled poll has a complete pair.
- `w1-subtitle-request-picture-only-cut-01-20261002-kit-01`: source `ff88a947-3c4f-4fff-b8c2-fd1f8910be7e`, duplicate `W1-picture-only-cut-subtitles-01`, request result SHA `015261dfa5be3e4393c98e3b587e0833b8ce24a8c0253d0788dd2c97a0d6be1f`. Its request pair is complete (`post.json`); the settled poll also has a complete pair.
- `w1-subtitle-request-disabled-A1-01-20261002-kit-01`: source `2dd077a7-22b8-458f-84d0-9541399b3125`, duplicate `W1-disabled-A1-subtitles-01`, request result SHA `9ab9be3da6caf4463d627980e3390161e4409c832976ec73520f43d0b0a47b26`. Its request pair is complete (`post.json`); the settled poll also has a complete pair.
| Request case | Evidence SHA-256 bindings |
|---|---|
| Linked cut request | `journal.jsonl` `442985ebb784cb439eef06162a1416352dd90185b7f055e6da73c90f1dc9171f`; `pre.json` `301c3000308bbbfb03f2c3bcb9e35687863e676de2304420d87c053862e3f9ef`; `post-partial.json` `618018268f554b4bb3e56bb0e69c89df2ade7babb31edfeec65da2df05c7585f`; result `b09a0a5c9f1832b59234b889b691caafb166dbffb27226cf2d746af95aff7576`. This is the only request with the retained partial checkpoint. |
| Picture-only request | `journal.jsonl` `99fd8b02e2cd2f4fe5c76335bfb1b80119bef32e7b1fb1a7e4a1137f606148a3`; `pre.json` `e854b2b5dd1b45fccc0b2cfaa7b405425394d16595cca96779409582e3829dce`; `post.json` `8c1f10927b6a6452b9219c550f681183128f011b41e9c0681344d480d7252e4d`; result `015261dfa5be3e4393c98e3b587e0833b8ce24a8c0253d0788dd2c97a0d6be1f`. |
| Disabled-A1 request | `journal.jsonl` `ab73f5a7ceda2e424a84c55bd72926b450956b523bd3307b9d26647aa31250fb`; `pre.json` `81e6a63605101f206b4cf7895a765374338ddd6dabaf0ba4c701665380f46372`; `post.json` `1d3867b616844ce4f0866476f789c707fc35aca250508445db9c4aaeee0b7df4`; result `9ab9be3da6caf4463d627980e3390161e4409c832976ec73520f43d0b0a47b26`. |

| Subtitle poll case | Evidence SHA-256 bindings |
|---|---|
| Linked cut poll | `journal.jsonl` `7d4a2a589eb200500e8a3724c5f59f612e396a74f340e118ee8aebf77aa91f72`; `pre.json`/`post.json` `98eb5b64fbb5774109a83d44d74c20f46ab2a541810dcebf13b7f36073103199`; result `eb5401dcd37caf1f84fa1b500ac6770cef343c80496346a9b4514385187e1242`. |
| Picture-only poll | `journal.jsonl` `c71d94f94db8111e7f81acb6f3af7ea751ddfffbc5cd93aac1ed62e4ddd885c9`; `pre.json`/`post.json` `ed40485192702833464a5c64908e936ee3867911121e41f19b4c5e815eb804a6`; result `7bcab352ea4aa64a1863130c8ca4640faf67a53b2262fdd8b85770b0231e1ece`. |
| Disabled-A1 poll | `journal.jsonl` `35e698945109c32ea5051fecc85e329134d4e2e0993da4bfce20dd751d2607bc`; `pre.json`/`post.json` `6a6d1a5bafe061083c36bfb1454c092b8ae4c224181750b82635bc5edb7bac60`; result `694325f412bbd1a1788d9e12623c23b26751709ce04badc2f8e9796d2c5c8a21`. |
