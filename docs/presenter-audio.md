# Clean presenter audio

Run DeepFilterNet 0.5.6 locally. Download the official Mac binary from the
[0.5.6 release](https://github.com/Rikorose/DeepFilterNet/releases/tag/v0.5.6),
make it executable, and point `VERA_DEEPFILTER_COMMAND` at it. FFmpeg and
FFprobe must also be on your PATH. The model is not installed as a VERA
checkout dependency.

```sh
export VERA_DEEPFILTER_COMMAND="/path/to/deep-filter-0.5.6"
uv run --frozen python -m vera_timeline_agent.presenter_audio \
  "/path/to/video.mov" --out "/path/to/new-clean.wav"
```

Add `--audio "/path/to/separate.wav"` when the sound was recorded separately.
For one long recording covering several videos, run the command once per video,
using the same `--audio` and a new output filename for each. The existing
presenter sync algorithm finds each video's offset. It stops if the match or
alignment is uncertain; it never guesses. The command prints the measured
offset, the cleaned audio's sync difference, and elapsed time.
Sync verification needs at least about 10 seconds of overlapping sound. If
the separate recording starts late or ends early, the missing portion is
silent and the command reports that gap. Videos whose picture and container
start at different times are refused because their sync cannot be verified.

The first channel is made mono, then DeepFilterNet runs with the accepted
continuous attenuation settings (`-a 30 -D`), with no hard gate. After noise
reduction, two-pass loudness normalization targets −19 LUFS and a −1.5 dBTP
true-peak ceiling. FFmpeg may use dynamic normalization when fixed gain would
exceed that ceiling or the source's loudness range is too wide for the target;
the command reports the measured level and mode. Quiet
recordings may have more audible remaining noise after the level is raised.

The output is 48 kHz mono 24-bit PCM WAV, padded or trimmed to the video
duration. The filter requires a 16-bit intermediate. The original files are
never changed, and an existing output is never overwritten. EQ and the final
mix remain in Resolve.
