# Issue 550 — local speech restoration investigation

Status: in progress. No quality ranking or Producer acceptance yet.

## Corpus and alignment

All audio stays local. The originals, Adobe references and existing #548
DeepFilterNet outputs were hashed on 2026-11-13. The incumbent was produced
from PR #548 at `816ab71f48e4b4524cfef66a2a8b792cb79d4e35`; its later head
`a81b35a319c9e4c789f9e225873bc8fcd16ec5d2` merged main without a subsequent
processing commit. The Adobe filename suffixes suggest settings but do not
establish what those settings were.

| Presenter | Original SHA-256 | Adobe SHA-256 | DeepFilterNet SHA-256 |
| --- | --- | --- | --- |
| 1 | `f21999949f87f7fb697f5ce16bafcde58c6b49aff203fa2d692c4e642a336a59` | `9eebf66ab3c1bdbc2a66204229c7312fbb46d7bfd65db921747487cc8cc4a2a9` | `9eff137ac16edacdc471fc394366c082b3658a2c1729d5b5a414ce276cec0ea1` |
| 2 | `d69bf4d3c4dcc38a9c2ff5a4309e50e73d8c0ece153e5a4ff675b86c25b8949d` | `089809ddd1d8fecfa81fd07b8bce7dc5cbe9342e9bb4f2b5d6106b94a5dfd4f2` | `0ffd6b0c630401c91712805f43cc4aa7411fee70703901bf55b3a6351a674abb` |

FFprobe reports 11,723,712 samples for each Presenter 1 original and Adobe
file, and 70,794,752 for each Presenter 2 original and Adobe file, at 48 kHz.
For each pair, 10-second channel-1 windows were cross-correlated using the
NumPy FFT in `presenter_sync._correlate`, searching ±4,800 samples. Presenter 1
windows starting at 20, 90 and 180 seconds had zero-sample lag; Presenter 2
windows at 60, 600 and 1,300 seconds measured 0, 0 and +1 sample. These are
window measurements, not proof that every sample is aligned.

The Presenter 2 incumbent is video-aligned: it has 69,977,760 samples and its
start is 21.290208333 seconds (1,021,930 samples) into the original. The
existing `presenter_sync.find_offset` measured that offset in ten windows
across the first two minutes, with zero measured spread. Excerpts from that
file must use original time minus this offset. Presenter 1's incumbent has
the same sample count as its original.

Two 40-second provisional passages per presenter were extracted at source
times 30 and 120 seconds for Presenter 1, and 120 and 600 seconds for
Presenter 2. Cross-correlation of a 10-second window within each showed the
DeepFilterNet excerpts at zero lag and Adobe at 0 samples for Presenter 1 and
+1 sample for Presenter 2. Passage suitability still needs listening.

## Environment

The local Linux x86_64 Docker engine reported 6 CPUs and 7.753 GiB memory;
host free disk was 59 GiB. These CPU timings will not predict Apple Silicon or
GPU performance. Inference must use `--network none`, read-only inputs and
a separate output mount; no source media is sent to a service.

## Candidate license screen

Licenses here are the publishers' declarations, not a quality assessment.
Build, checkpoint hash and runtime results remain to be measured.

| Candidate | Pinned source / code license | Pinned model / weight license | Role and caveat |
| --- | --- | --- | --- |
| Resemble Enhance | [`8e978149`](https://github.com/resemble-ai/resemble-enhance/tree/8e978149bfe8abab3eb77d965d579a111afdb0ff), MIT | [Official model](https://huggingface.co/ResembleAI/resemble-enhance), MIT | Denoise and restoration; source last changed December 2024. |
| SGMSE+ EARS-Reverb | [`1961cf44`](https://github.com/sp-uhh/sgmse/tree/1961cf4483e37df1bb92ccf0eb8b28bf6f44cb0e), MIT | [First-party checkpoint](https://huggingface.co/sp-uhh/speech-enhancement-sgmse/blob/89193ea626c85f3ba36c5ca6d604068ebb2e5e58/pretrained_checkpoints/48_khz_models/ears_reverb.ckpt), repository tagged MIT; see caveat below | 48 kHz speech dereverberation. The OUVESDE path supports CPU; a different SBVESDE path hardcodes CUDA. Source updated May 2026. |
| ClearerVoice MossFormer2 SE 48K | [`6b3774dc`](https://github.com/modelscope/ClearerVoice-Studio/tree/6b3774dc79c46ae8bed2a4fa5f706f0ac8c75c61), Apache-2.0 | [Official model](https://huggingface.co/alibabasglab/MossFormer2_SE_48K/tree/eff8c97925c8bec812af707814b3e5d777fd4503), Apache-2.0 | Speech enhancement; whether it meaningfully removes this room reverb is unverified. Source last changed August 2025. |

The SGMSE model repository's MIT tag does not by itself establish commercial
rights for weights trained on EARS-Reverb: the [EARS benchmark](https://github.com/sp-uhh/ears_benchmark)
declares CC BY-NC 4.0. Treat commercial eligibility as unresolved until the
rights holder clarifies it. Check the checkpoint's configured SDE before
assuming the CPU-capable path applies.

The Resemble CPU lock now resolves using both the PyTorch CPU and PyPI
indexes with `--index-strategy unsafe-best-match` and hashes. The pinned source
imports `ptflops` only in profiling helpers; it is omitted from the inference
environment after the 0.7.2 source package failed to build. The container
build and inference still need verification. Candidate quality, checkpoint
hashes, peak memory, runtimes, finalists and listening packages remain
outstanding.
