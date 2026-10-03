# Source timing analysis — Issue 141

The manifest-bound generated `repeated.wav` (`832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e`) is mono PCM16, 48 kHz, 384,000 samples. Full decode found 66,896 nonzero samples, all within these half-open support ranges:

| Range | Start at 25 fps | Exclusive end at 25 fps | End to next frame boundary |
|---|---:|---:|---:|
| `[19210, 36258)` | 10.005208333 frames | 18.884375 frames | 222 samples |
| `[115210, 132258)` | 60.005208333 frames | 68.884375 frames | 222 samples |
| `[211210, 228258)` | 110.005208333 frames | 118.884375 frames | 222 samples |
| `[307210, 324258)` | 160.005208333 frames | 168.884375 frames | 222 samples |

At 48 kHz and 25 fps, one frame is 1,920 samples. Each support starts 10 samples after a frame boundary; each half-open end is 1,698 samples into a frame and 222 samples before the next boundary. Successive ranges start 96,000 samples (50 frames) apart. SHA-256 for generated `base.mov` is `c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942`.

The retained selected-Matrix `R2-retime` capture getters show:

| Item/state | Source start/end frames | Source start/end times | `GetEnd(True)` | `GetDuration(True)` | Speed |
|---|---:|---:|---:|---:|---:|
| V1 before | 0 / 199 | 0.0 / 7.96 s | 5699.0 | 199.0 | 100% |
| V1 at 50% | 0 / 99 | 0.0 / 4.0 s | 5699.0 | 199.0 | 50% |
| Linked A1 before | 0 / 199 | 0.0 / 7.96 s | 5699.0 | 199.0 | 100% |
| Linked A1 while V1 is 50% | 0 / 199 | 0.0 / 7.96 s | 5699.0 | 199.0 | 100% |

These clip getters do not directly expose the individual word-support ends. The arithmetic does not establish fractional-unit semantics, sample-exact edited-audio behavior, program routing/output, or word omission. R2-derived-end and the other pending R2 checks remain incomplete. Exact JSON getter records and raw capture/input hashes are in `analysis.json` and `hashes.json`.
