# Issue 44 synthetic master and proxy playback check

This opt-in fixture creates a synthetic, numbered-frame master and a local
browser page for reviewing a matching proxy. It does not use production media,
create a proxy, or verify source-to-proxy frame mapping.

## Generate the synthetic master

Requirements: Python 3 and an `ffmpeg` build with the `drawbox` filter and
`libx264`. The numbered counter is drawn with deterministic boxes, so `drawtext`
and a font package are not required. The default master contains 14,400 frames
at exactly `24000/1001` fps (about 600.6 seconds), a visible `FRAME` counter,
and a continuous 440 Hz audio tone. The video is progressive, square-pixel
8-bit `yuv420p` with explicit limited-range BT.709 SDR stream and encoder
metadata, matching the source inspector's accepted profile. `--frames` changes
the frame count while preserving that rate.

Create a new empty directory directly inside the system temporary directory,
then pass its absolute path. The script refuses non-empty directories, paths
outside the temp directory, and symbolic links. It never overwrites or deletes
files.

```sh
set -e
TMP_ROOT="$(python3 -c 'import tempfile; print(tempfile.gettempdir())')"
TARGET_DIR="$TMP_ROOT/vera-issue44-master"
mkdir "$TARGET_DIR"
python3 scripts/issue44_fixture.py --output-dir "$TARGET_DIR" --frames 14400
open "$TARGET_DIR/review.html"
```

The output directory contains `numbered-master.mov` and `review.html`. If
generation fails or is interrupted, partial output is left in place; use a new
empty temporary directory for a later attempt. The tool does not remove a
source, cache, or partial output.

## Run verified local ingest

To exercise the real review-ingest adapter with a quick synthetic sample, make
a separate empty temp target for the 12-frame fixture, then run:

```sh
TMP_ROOT="$(python3 -c 'import tempfile; print(tempfile.gettempdir())')"
SHORT_TARGET_DIR="$(mktemp -d "$TMP_ROOT/vera-issue44-smoke-12.XXXXXX")"
python3 scripts/issue44_fixture.py \
  --output-dir "$SHORT_TARGET_DIR" --frames 12
printf 'Fixture directory: %s\n' "$SHORT_TARGET_DIR"
./.venv/bin/python scripts/issue44_ingest_fixture.py \
  --fixture-dir "$SHORT_TARGET_DIR"
```

The ingest command accepts only an explicit absolute fixture directory directly
inside the system temp directory, with the generated `numbered-master.mov` and
`review.html`. It hashes the master as the fixture's registered source, then
submits and runs the normal proxy, audio, and waveform stages. The pipeline
reads the master without writing to it, and the script checks its content hash
again before printing the handoff. The script does not upload or delete files.

The job database, stage outputs, and review cache persist under
`$SHORT_TARGET_DIR/.issue44-ingest/`. Keep the printed fixture path and rerun
only the ingest command with that same path to reuse the existing job. Running
the whole example again intentionally creates a fresh fixture and state
directory. The CLI passes a stable request key; the adapter scopes it to the
inspected generation. If the source, profile, or tool identity changes while
using the same state directory, the adapter creates a distinct job and
preserves the prior job and its artifacts. If a stage ends in `waiting` or
`failed`, rerun with `--resume` to retry that job for the same generation. If
the process stopped while a stage was active, the JSON failure includes the
lease expiry; rerun after it expires. Long stage calls renew their lease while
running. Success prints one JSON verified handoff to stdout; failures print
JSON status and the visible error to stderr and return a nonzero exit code.

The handoff contains `video_path`, `video_source`, `video_muted`, `frame_map`,
`audio_path`, `audio_source`, `audio_timing`, and verified per-stage paths and
receipt hashes. Rational rates and PTS origins are encoded as
`{"numerator": ..., "denominator": ...}`. Keep this output with the fixture
when reporting a local mismatch.

## Review locally

1. Open `review.html` and select the review video. The browser reads it through
   a local object URL; it does not copy or upload the file.
2. Choose an audio mode. **Silence audio** is the safe default. Choose **Use the
   video's embedded audio** only for the synthetic `numbered-master.mov` (or
   another file whose embedded audio you explicitly intend to hear).
3. For a silent proxy with a separately verified audio derivative, choose
   **Use separate verified audio**, then select the verified WAV. The video is
   muted and its time controls drive both files. The supplied derivative must
   already be aligned to video time zero; this page does not apply an offset.
4. Use the video controls to play, pause, and scrub. The page reports the audio
   drift and corrects it when it exceeds 0.12 seconds. Use **Resync audio to
   video** to align it immediately after a manual seek. Start, Middle, and End
   seek buttons target the synthetic master frame centers:

| Check | Master frame | Reference time |
| --- | ---: | ---: |
| Start | 0 | 0.021 s |
| Middle | 7,200 | 300.321 s |
| End | 14,399 | 600.579 s |

Use those reference buttons only for a proxy made from this fixture's synthetic
master. Compare the visible `FRAME` counter manually and listen for the 440 Hz
tone when using the synthetic master's embedded-audio mode. If a separate
audio file ends before the video or remains out of sync after resync, record
the frame/time and what you observed. Browser seeking, displayed duration, and
manual listening do not prove exact frame or sample mapping.

## Selecting artifacts from a verified handoff

Use the successful CLI output from the preceding section. The handoff's
`video_muted` field is always `true`, and its `audio_source` field chooses the
audio behavior:

- Select the returned `video_path`.
- If `audio_source` is `audio-stage`, choose **Use separate verified audio**
  and select the returned `audio_path`. The pipeline has verified this WAV is
  aligned to the master-video origin, so the page starts it at video time zero.
  Use the returned `audio_timing` evidence when investigating a mismatch.
- If `audio_source` is `absent`, choose **Silence audio**. Do not use an
  embedded track as a substitute for an absent verified audio artifact.

This applies whether `video_source` is `proxy` or `master`; keep the video's
audio muted in the handoff. The page only plays locally selected files. It does
not inspect receipts or independently verify that a selected file matches the
handoff, so select only the paths from the successful verified handoff. The
synthetic master-with-audio option is for this fixture, not a replacement for
the handoff's explicit audio policy.

## Reply

After the playback checks pass, reply exactly:

`Accepted review-proxy playback check.`

If anything differs, do not send the acceptance reply. Instead report:

`Mismatch at master frame <frame> / <time>: <what you observed>.`

## Limits

- The synthetic master cannot establish behavior on production footage.
- The fixture does not generate a proxy or verify source-to-proxy frame
  mapping, decoded frames, or audio samples.
- Browser codec support and manual comparison limit what this check can show.
- The local page is a review aid, not an integration into VERA's ingest
  workflow.
