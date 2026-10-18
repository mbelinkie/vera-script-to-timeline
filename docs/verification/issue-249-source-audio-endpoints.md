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

Studio acceptance is pending. Each endpoint case has its own issue-owned
synthetic media, immutable package and fresh disposable target. A successful
native result must include all seven installed stages, saved/reopened geometry,
fixed same-MOV comparison, measured cadence/gain/sync/drift, and terminal silence.
