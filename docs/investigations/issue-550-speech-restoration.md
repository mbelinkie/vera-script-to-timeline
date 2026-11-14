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

The Resemble CPU lock resolves using both the PyTorch CPU and PyPI indexes with
`--index-strategy unsafe-best-match` and hashes. The pinned source imports
`ptflops` only in profiling helpers; it is omitted from the inference
environment after the 0.7.2 source package failed to build. The legacy Docker
builder silently skipped heredoc Python bodies in the first recipe. Replacing
them with copied scripts produced an image of 1,250,444,217 bytes, verified
checkpoint SHA-256 `f9d035f318de3e6d919bc70cf7ad7d32b4fe92ec5cbe0b30029a27f5db07d9d6`,
and loaded the model on CPU. The initial offline 40-second trial used the
upstream 30-second chunk, midpoint solver, 64 evaluations, lambda 1 and tau
0.5. Docker reported an out-of-memory kill after 964 seconds with a 6 GiB
container limit; no output was produced. A five-second chunk / one-second
overlap retry reached four of ten chunks after 24m51s and was stopped after
30 minutes without output, to preserve the investigation budget. Its observed
peak was 3,984,650,240 bytes, with other builds sharing the six CPUs. A linear
estimate from the first four chunks is about 62 minutes for the 40-second
excerpt and 6.3 hours for Presenter 1; this is not a completed benchmark and
contention makes it indicative only. No sound-quality, seam or timing judgment
was made from that interrupted attempt. On a later offline run with the same
five-second chunks, the 40-second excerpt finished in 3,585.61 seconds under
shared CPU load. Its 44.1 kHz output resampled to exactly 1,920,000 samples at
48 kHz, but four ten-second waveform-correlation windows measured +323, +12,
-75 and -680 samples. Nine shorter windows likewise varied, with modest
correlation (0.185–0.453). This fails the issue's 1 ms timing-evidence gate;
the result does not determine whether the voice sounds good or prove that a
different processing strategy could not retain sync. It is excluded from the
blind set, and its rejected container image was removed; the output and recipe
remain local.

ClearerVoice MossFormer2 SE 48K passed a one-second synthetic offline CPU
smoke check. Its image is 1,276,629,232 bytes by `docker image inspect`; the
221,552,019-byte checkpoint SHA-256 is
`03692b9f773bbd6bb43b9c5a41f96b1e28affd66e13796b7bec66ad3d8b227c6`.
An offline 40-second Presenter 1 passage finished in 450 seconds under shared
CPU load, at 48 kHz mono with exactly 1,920,000 samples. Four ten-second
waveform correlations measured zero lag; FFmpeg reported -0.6 dBTP. This
first exploratory output is PCM16. The subsequent PCM24 four-passage batch
finished with exactly 1,920,000 samples in each output, no full-scale samples,
and zero-sample lag in four ten-second windows per passage. True peaks were
-0.6 and -0.9 dBTP for Presenter 1, -6.2 and -10.0 dBTP for Presenter 2.
The full Presenter 1 output kept all 11,723,712 samples and measured zero lag
at 10, 60, 120, 180 and 225 seconds. The full run took 2,183 seconds under
shared CPU load, implying roughly 3.7 hours for Presenter 2; no full Presenter
2 run was made. No subjective quality judgment has been made.

The first-party SGMSE EARS-Reverb checkpoint was downloaded locally and its
1,295,848,436 bytes verified as SHA-256
`9be62a3df0401398e5626a1c4dc65039220499d506941ecf110b52cccb7309b2`.
Candidate quality, completed runtimes, finalists and listening packages
remain outstanding. The first SGMSE image build installed its dependencies
but was interrupted when the 40 GiB Docker VM filled. A second build succeeded
and its image reports 575,663,960 bytes. The offline 60-second screen was killed
after 196 seconds at the 5 GiB container limit. A five-second retry also hit
that limit; disabling gradient tracking did not make five seconds fit. A
one-second test with gradients disabled completed in 761.6 seconds including
model load (709 seconds in the processing loop), producing 48,000 samples.
Its waveform correlation estimated -55 samples (-1.15 ms), with correlation
0.689; this very short window is weak evidence of timing and not a meaningful
audition. Its SHA-256 is
`be6529f9377f05b9fa48140732bb8b05432edb9dca1c71e224bb62a6ff2e35f4`.
At this rate, 160 seconds across both presenters would take about 32 hours,
before accounting for chunk joins. No longer output was produced. The
checkpoint loaded with a warning that it was produced by a newer Lightning
version.

Four-way provisional listening packages are held locally at
`out/issue550-private/listening-v2/presenter-1` and `presenter-2`. Each has
four randomized 80-second files assembled from the matched passages; the
answer key and SHA-256/loudness manifest are separate local files. The
listening copies each measure -32.0 LUFS integrated, without limiting, and
remain below -8 dBTP. This lower target avoids clipping when matching the
quiet Presenter 2 originals. Loudness is integrated over the excerpt rather
than a separately hand-labelled speech-only region. Passage coverage and any
missing or altered syllables remain listening questions, not automated claims.
