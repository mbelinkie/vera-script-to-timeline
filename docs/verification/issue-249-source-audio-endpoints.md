# Complete source sound at fractional picture endpoints

Issue #249 preserves the original prepared PCM interval when a complete clip's
picture rounds to a later 24000/1001 frame. Package projection creates a separate
PCM24 WAV containing the selected samples unchanged, followed only by the
terminal frame remainder. The original #174 WAV is retained in the package.

| 25 fps selection | Picture | Original PCM at 48 kHz | Terminal silence |
| --- | --- | --- | --- |
| 75 frames / 3 seconds | 72 frames / 3.003 seconds | 144,000 samples | 144 samples / 3 ms |
| 250 frames / 10 seconds | 240 frames / 10.01 seconds | 480,000 samples | 480 samples / 10 ms |

The conversion requires a complete prepared interval, an exact native start,
the authored rounded duration, and less than half a frame of terminal silence.
Other fractional source ranges retain their refusal. No policy still emits no
source-audio event. Full remains 0 dB; Quiet remains −18 dB.

Qualification prediction authenticates and decodes the original sidecar,
independently reproduces the native WAV hash, and predicts the exact samples
plus terminal zeros before rendering. It does not infer source sound from the
rounded picture duration. The fixed zero-lag, unity-gain limits remain programme
RMS ≤0.0004 and maximum sliding 960-sample RMS ≤0.006 per channel.

Local verification: 121 focused package/prediction/comparison checks passed;
the final four-case real preparation/current-compiler/package/cache reload test
passed; `validate:fast` passed with 1,151 non-slow Python tests and unchanged
compiler goldens. The required read-only Claude CLI review found no blocking
bugs. The older retained R16 slow fixture separately refuses its stale compiler
source pin; it is not endpoint acceptance.

Studio acceptance passed on 2026-10-18 through the installed qualification flow
in Studio 21.1.1 build 10. All four fresh disposable targets completed seven
native stages, save/reopen, pre/post geometry and fixed same-MOV comparison.
Every rendered numbered frame matched its admitted cadence. Prepared PCM edges
matched within one sample; every measured click offset and drift was zero.

| Case | Endpoint picture | Measured gain | Exact source samples | Terminal silent samples |
| --- | --- | --- | --- | --- |
| 3-second Full | 72 frames | 0 dB | 144,000 | 144 |
| 3-second Quiet | 72 frames | −18.0000064 dB | 144,000 | 144 |
| 10-second Full | 240 frames | 0 dB | 480,000 | 480 |
| 10-second Quiet | 240 frames | −18.0000064 dB | 480,000 | 480 |

All terminal intervals had decoded peak zero. Full fixed-comparison residuals
were zero in both channels. The largest Quiet residuals were programme RMS
5.29×10⁻¹⁰ and sliding 960-sample RMS 3.75×10⁻⁹, below the unchanged limits.

The first sparse ten-second Quiet fixture correctly refused non-vacuity before
render queueing. Its target and attempt are retained. The fresh passing case
places a separate 72-frame Full reference after the 240-frame Quiet endpoint;
its total render is 312 frames. The Quiet interval remains enabled and is
independently measured at −18 dB, including its 480-sample silent remainder.
No comparison threshold changed. Only `bounded_output_residual_consistency`
is claimed; internal controls, continuous stability and causal exclusivity
remain unverified.

Issue-owned cases, native runs, MOVs and measurements remain in the private
qualification preparation/output roots. Resolve ownership was released after
the fourth completed native chain; all disposable projects remain saved.
