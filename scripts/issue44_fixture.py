#!/usr/bin/env python3
"""Generate an opt-in synthetic long master and local proxy review page."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from string import Template

FPS_NUMERATOR = 24_000
FPS_DENOMINATOR = 1_001
DEFAULT_FRAME_COUNT = 14_400

_DIGIT_SEGMENTS = {
    0: "abcdef",
    1: "bc",
    2: "abged",
    3: "abgcd",
    4: "fgbc",
    5: "afgcd",
    6: "afgecd",
    7: "abc",
    8: "abcdefg",
    9: "abfgcd",
}
_SEGMENT_BOXES = {
    "a": (10, 0, 28, 8),
    "b": (40, 8, 8, 31),
    "c": (40, 47, 8, 31),
    "d": (10, 78, 28, 8),
    "e": (0, 47, 8, 31),
    "f": (0, 8, 8, 31),
    "g": (10, 39, 28, 8),
}
_FRAME_GLYPHS = {
    "F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
    "R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
    "A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
    "M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
    "E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
}


def numbered_frame_filter(frame_count: int) -> str:
    """Draw a deterministic FRAME label and changing counter using drawbox only."""
    digit_count = max(5, len(str(frame_count - 1)))
    digit_gap = 12
    digit_width = digit_count * 48 + (digit_count - 1) * digit_gap
    label_width = 5 * 5 * 5 + 4 * 5
    counter_width = max(digit_width, label_width)
    if counter_width + 24 > 1_200:
        raise ValueError("frame count is too large to fit the numbered overlay")

    filters = [
        f"drawbox=x=28:y=26:w={counter_width + 24}:h=172:color=black@0.75:t=fill"
    ]
    label_x = 40
    label_y = 40
    cell_size = 5
    for letter_index, letter in enumerate("FRAME"):
        glyph = _FRAME_GLYPHS[letter]
        for row, bits in enumerate(glyph):
            for column, bit in enumerate(bits):
                if bit == "1":
                    x = label_x + letter_index * 30 + column * cell_size
                    y = label_y + row * cell_size
                    filters.append(
                        f"drawbox=x={x}:y={y}:w={cell_size}:h={cell_size}:color=white:t=fill"
                    )

    first_digit_x = 40
    first_digit_y = 94
    for position in range(digit_count):
        place_value = 10 ** (digit_count - position - 1)
        digit_expression = f"mod(floor(n/{place_value}),10)"
        x_offset = first_digit_x + position * (48 + digit_gap)
        for segment, (x, y, width, height) in _SEGMENT_BOXES.items():
            active_digits = [
                str(digit)
                for digit, segments in _DIGIT_SEGMENTS.items()
                if segment in segments
            ]
            enabled = "+".join(
                f"eq({digit_expression},{digit})" for digit in active_digits
            )
            filters.append(
                f"drawbox=x={x_offset + x}:y={first_digit_y + y}:"
                f"w={width}:h={height}:color=white:t=fill:enable='{enabled}'"
            )
    return ",".join(filters)


def positive_frame_count(value: str) -> int:
    try:
        frame_count = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("frame count must be an integer") from error
    if frame_count < 1:
        raise argparse.ArgumentTypeError("frame count must be positive")
    return frame_count


def empty_temp_target(path: Path) -> Path:
    if not path.is_absolute():
        raise ValueError("output directory must be an absolute path")
    if path.is_symlink():
        raise ValueError("output directory must not be a symbolic link")
    try:
        target = path.resolve(strict=True)
    except FileNotFoundError as error:
        raise ValueError(
            "create the output directory before running this tool"
        ) from error
    temp_root = Path(tempfile.gettempdir()).resolve()
    if target.parent != temp_root:
        raise ValueError(
            "output directory must be a direct child of the system temp directory"
        )
    if not target.is_dir():
        raise ValueError("output path must be a directory")
    if next(target.iterdir(), None) is not None:
        raise ValueError(
            "output directory must be empty; this tool never overwrites files"
        )
    return target


def review_page(frame_count: int) -> str:
    middle_frame = frame_count // 2
    last_frame = frame_count - 1
    return Template("""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="referrer" content="no-referrer">
  <title>Issue 44 local proxy playback check</title>
  <style>
    :root { color-scheme: light dark; font: 16px/1.45 system-ui, sans-serif; }
    body { max-width: 960px; margin: 2rem auto; padding: 0 1rem; }
    video { display: block; width: 100%; max-height: 70vh; background: #111; }
    button, input, select { margin: 0.25rem 0.5rem 0.25rem 0; font: inherit; }
    .note { border-left: 4px solid #c80; padding: 0.5rem 1rem; }
    output { display: block; margin: 0.5rem 0; }
  </style>
</head>
<body>
  <h1>Issue 44 local proxy playback check</h1>
  <p class="note">Playback helper only. It does not verify source-to-proxy
    frame mapping.</p>
  <p>Select the review video and, when supplied, the verified separate audio
    derivative. The browser reads selected files locally; this page does not
    copy or upload them.</p>
  <label for="video-file">Review video</label>
  <input id="video-file" type="file" accept="video/*">
  <output id="video-name">No video selected</output>
  <label for="audio-mode">Audio mode</label>
  <select id="audio-mode">
    <option value="silent" selected>Silence audio (safe default)</option>
    <option value="embedded">Use the video's embedded audio (synthetic master)</option>
    <option value="separate">Use separate verified audio (silent video)</option>
  </select>
  <label for="audio-file">Separate verified audio</label>
  <input id="audio-file" type="file" accept="audio/*,.wav" disabled>
  <output id="audio-name">No separate audio selected</output>
  <label for="audio-volume">Separate audio level</label>
  <input id="audio-volume" type="range" min="0" max="1" step="0.01" value="1" disabled>
  <video id="proxy" controls preload="metadata" playsinline></video>
  <audio id="separate-audio" preload="metadata"></audio>
  <output id="playback">Choose a video to enable playback and seeking.</output>
  <button id="resync" type="button" disabled>Resync audio to video</button>
  <output id="sync-status">Audio is silent by default. Choose a mode above.</output>
  <h2>Master reference seeks</h2>
  <p>Use the video controls to play, pause, and scrub. Reference buttons seek
    to points in the synthetic numbered master; compare the visible frame
    counter manually.</p>
  <button type="button" data-frame="0" disabled>Start: frame 0</button>
  <button type="button" data-frame="$middle_frame" disabled>
    Middle: frame $middle_frame
  </button>
  <button type="button" data-frame="$last_frame" disabled>
    End: frame $last_frame
  </button>
  <output id="sample">No reference seek selected.</output>
  <script>
    "use strict";
    const numerator = $fps_numerator;
    const denominator = $fps_denominator;
    const syncTolerance = 0.12;
    const fileInput = document.getElementById("video-file");
    const audioFileInput = document.getElementById("audio-file");
    const audioMode = document.getElementById("audio-mode");
    const audioVolume = document.getElementById("audio-volume");
    const videoName = document.getElementById("video-name");
    const audioName = document.getElementById("audio-name");
    const video = document.getElementById("proxy");
    const audio = document.getElementById("separate-audio");
    const playback = document.getElementById("playback");
    const syncStatus = document.getElementById("sync-status");
    const resyncButton = document.getElementById("resync");
    const sample = document.getElementById("sample");
    const referenceButtons = document.querySelectorAll("button[data-frame]");
    let videoUrl = null;
    let audioUrl = null;
    let syncMessage = "";

    fileInput.addEventListener("change", () => {
      const file = fileInput.files && fileInput.files[0];
      if (!file) return;
      video.pause();
      audio.pause();
      if (videoUrl) URL.revokeObjectURL(videoUrl);
      videoUrl = URL.createObjectURL(file);
      video.src = videoUrl;
      video.load();
      videoName.textContent = file.name + " (local only)";
      sample.textContent = "Select a start, middle, or end reference seek.";
      referenceButtons.forEach((button) => { button.disabled = false; });
      updatePlayback();
    });

    audioFileInput.addEventListener("change", () => {
      const file = audioFileInput.files && audioFileInput.files[0];
      audio.pause();
      if (audioUrl) URL.revokeObjectURL(audioUrl);
      audioUrl = file ? URL.createObjectURL(file) : null;
      if (audioUrl) {
        audio.src = audioUrl;
        audioName.textContent = file.name + " (local only)";
        audio.load();
      } else {
        audio.removeAttribute("src");
        audio.load();
        audioName.textContent = "No separate audio selected";
      }
      applyAudioMode();
    });

    function usingSeparateAudio() {
      return audioMode.value === "separate";
    }

    function updatePlayback() {
      const current = Number.isFinite(video.currentTime)
        ? video.currentTime.toFixed(3) + " s" : "—";
      const duration = Number.isFinite(video.duration)
        ? video.duration.toFixed(3) + " s" : "—";
      playback.textContent = "Video time: " + current + " / duration: " + duration;
      if (audioMode.value === "silent") {
        syncStatus.textContent = "Audio is muted." +
          (syncMessage ? " " + syncMessage : "");
      } else if (audioMode.value === "embedded") {
        syncStatus.textContent =
          "Using the selected video's embedded audio if present." +
          (syncMessage ? " " + syncMessage : "");
      } else if (!audioUrl) {
        syncStatus.textContent =
          "Video is muted. Select the separately verified audio file.";
      } else if (audio.readyState < 1 || !Number.isFinite(audio.duration)) {
        syncStatus.textContent = "Loading separate audio metadata…";
      } else if (video.currentTime > audio.duration + syncTolerance) {
        syncStatus.textContent =
          "Separate audio ends before this video position; " +
          "report the duration mismatch.";
      } else {
        const drift = audio.currentTime - video.currentTime;
        syncStatus.textContent = "Separate audio drift: " +
          (drift >= 0 ? "+" : "") + drift.toFixed(3) +
          " s (automatic correction above " + syncTolerance + " s)." +
          (syncMessage ? " " + syncMessage : "");
      }
      resyncButton.disabled = !usingSeparateAudio() || !audioUrl || !videoUrl;
    }

    function syncSeparateAudio(force) {
      if (!usingSeparateAudio()) return;
      video.muted = true;
      if (
        !videoUrl || !audioUrl || audio.readyState < 1 ||
        !Number.isFinite(audio.duration)
      ) {
        audio.pause();
        updatePlayback();
        return;
      }
      if (video.currentTime > audio.duration + syncTolerance) {
        audio.pause();
        updatePlayback();
        return;
      }
      const drift = audio.currentTime - video.currentTime;
      if (force || video.seeking || Math.abs(drift) > syncTolerance) {
        audio.currentTime = video.currentTime;
      }
      audio.playbackRate = video.playbackRate;
      if (video.paused || video.ended) {
        audio.pause();
      } else if (audio.paused) {
        audio.play().catch(() => {
          syncMessage =
            "Browser blocked separate audio playback; press Play again " +
            "after selecting both files.";
          updatePlayback();
        });
      }
      updatePlayback();
    }

    function applyAudioMode() {
      const mode = audioMode.value;
      audioFileInput.disabled = mode !== "separate";
      audioVolume.disabled = mode !== "separate";
      video.muted = mode !== "embedded";
      audio.volume = Number(audioVolume.value);
      syncMessage = "";
      if (mode === "separate") {
        syncSeparateAudio(true);
      } else {
        audio.pause();
        updatePlayback();
      }
    }

    audioMode.addEventListener("change", applyAudioMode);
    audioVolume.addEventListener("input", () => {
      audio.volume = Number(audioVolume.value);
    });
    resyncButton.addEventListener("click", () => syncSeparateAudio(true));
    video.addEventListener("loadedmetadata", () => {
      syncSeparateAudio(true);
      updatePlayback();
    });
    video.addEventListener("durationchange", updatePlayback);
    video.addEventListener("timeupdate", () => {
      if (usingSeparateAudio()) syncSeparateAudio(false);
      else updatePlayback();
    });
    video.addEventListener("play", () => syncSeparateAudio(true));
    video.addEventListener("pause", () => {
      if (usingSeparateAudio()) audio.pause();
      updatePlayback();
    });
    video.addEventListener("seeking", () => syncSeparateAudio(true));
    video.addEventListener("seeked", () => syncSeparateAudio(true));
    video.addEventListener("ratechange", () => {
      if (usingSeparateAudio()) audio.playbackRate = video.playbackRate;
    });
    audio.addEventListener("loadedmetadata", () => syncSeparateAudio(true));
    audio.addEventListener("durationchange", updatePlayback);
    audio.addEventListener("seeked", updatePlayback);
    audio.addEventListener("ended", updatePlayback);
    video.addEventListener("error", () => {
      syncMessage = "The selected video could not be decoded by this browser.";
      updatePlayback();
    });
    audio.addEventListener("error", () => {
      syncMessage = "The selected separate audio could not be decoded by this browser.";
      updatePlayback();
    });
    referenceButtons.forEach((button) => {
      button.addEventListener("click", () => {
        if (!videoUrl || !Number.isFinite(video.duration)) return;
        const frame = Number(button.dataset.frame);
        const seconds = (frame + 0.5) * denominator / numerator;
        if (seconds >= video.duration) {
          sample.textContent = "Reference frame " + frame +
            " is beyond the selected video's duration; report a duration mismatch.";
          return;
        }
        sample.textContent = "Master reference frame " + frame +
          " at " + seconds.toFixed(3) +
          " s. Compare the visible FRAME counter manually.";
        video.currentTime = seconds;
      });
    });
    applyAudioMode();
    window.addEventListener("beforeunload", () => {
      if (videoUrl) URL.revokeObjectURL(videoUrl);
      if (audioUrl) URL.revokeObjectURL(audioUrl);
    });
  </script>
</body>
</html>
""").substitute(
        fps_numerator=FPS_NUMERATOR,
        fps_denominator=FPS_DENOMINATOR,
        middle_frame=middle_frame,
        last_frame=last_frame,
    )


def generate(output_dir: Path, frame_count: int) -> None:
    target = empty_temp_target(output_dir)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise ValueError("ffmpeg was not found on PATH")

    duration = f"{frame_count * FPS_DENOMINATOR / FPS_NUMERATOR:.9f}"
    output_path = target / "numbered-master.mov"
    numbered_overlay = numbered_frame_filter(frame_count)
    command = [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-n",
        "-f",
        "lavfi",
        "-i",
        f"testsrc2=size=1280x720:rate={FPS_NUMERATOR}/{FPS_DENOMINATOR}",
        "-f",
        "lavfi",
        "-i",
        "sine=frequency=440:sample_rate=48000",
        "-map",
        "0:v:0",
        "-map",
        "1:a:0",
        "-vf",
        f"setsar=1/1,format=yuv420p,{numbered_overlay}",
        "-frames:v",
        str(frame_count),
        "-t",
        duration,
        "-c:v",
        "libx264",
        "-profile:v",
        "high",
        "-preset",
        "medium",
        "-crf",
        "18",
        "-threads",
        "1",
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-colorspace",
        "bt709",
        "-color_primaries",
        "bt709",
        "-color_trc",
        "bt709",
        "-x264-params",
        "colorprim=bt709:transfer=bt709:colormatrix=bt709",
        "-metadata:s:v:0",
        "color_primaries=bt709",
        "-metadata:s:v:0",
        "color_transfer=bt709",
        "-metadata:s:v:0",
        "colorspace=bt709",
        "-c:a",
        "pcm_s16le",
        "-ar",
        "48000",
        "-ac",
        "1",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    subprocess.run(command, check=True)
    with (target / "review.html").open("x", encoding="utf-8") as page:
        page.write(review_page(frame_count))
    print(f"Synthetic master: {output_path}")
    print(f"Local review page: {target / 'review.html'}")
    print(f"Frames: {frame_count} at {FPS_NUMERATOR}/{FPS_DENOMINATOR} fps")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="existing empty directory directly inside the system temp directory",
    )
    parser.add_argument(
        "--frames",
        type=positive_frame_count,
        default=DEFAULT_FRAME_COUNT,
        help=f"number of numbered frames (default: {DEFAULT_FRAME_COUNT})",
    )
    args = parser.parse_args()
    try:
        generate(args.output_dir, args.frames)
    except (OSError, subprocess.CalledProcessError, ValueError) as error:
        print(f"issue44_fixture: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
