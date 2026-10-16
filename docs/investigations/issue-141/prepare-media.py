"""Generate only new issue-141 synthetic media with installed tools; no Resolve."""

import hashlib
import json
import math
import platform
import shutil
import struct
import subprocess
import sys
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "python"))
from vera_timeline_agent.placeholder_slate import render_placeholder_slate  # noqa: E402


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pcm(path, values):
    with wave.open(str(path), "wb") as writer:
        writer.setnchannels(1)
        writer.setsampwidth(2)
        writer.setframerate(48000)
        writer.writeframes(values)


def main():
    output = Path(sys.argv[1])
    if (
        not output.is_absolute()
        or output.parent != ROOT / "out"
        or not output.name.startswith("issue-141-media-")
    ):
        raise ValueError(
            "Use a new absolute repository out/issue-141-media-* directory"
        )
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe or not Path("/usr/bin/say").is_file():
        raise RuntimeError(
            "Installed FFmpeg/FFprobe/macOS say required; do not install substitutes"
        )
    output.mkdir(parents=True, exist_ok=False)
    operations = []

    def execute(command):
        operations.append(
            [str(value).replace(str(output), "<synthetic-media>") for value in command]
        )
        try:
            subprocess.run(command, check=True, capture_output=True)
        except subprocess.CalledProcessError as error:
            (output / "generation-failure.json").write_text(
                json.dumps(
                    {
                        "commands": operations,
                        "exitCode": error.returncode,
                        "stdout": error.stdout.decode(errors="replace"),
                        "stderr": error.stderr.decode(errors="replace"),
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            raise

    execute(
        [
            "/usr/bin/say",
            "-v",
            "Alex",
            "-r",
            "200",
            "-o",
            str(output / "echo.aiff"),
            "echo",
        ]
    )
    execute(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-i",
            str(output / "echo.aiff"),
            "-ar",
            "48000",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(output / "echo.wav"),
        ]
    )
    with wave.open(str(output / "echo.wav"), "rb") as reader:
        assert (
            reader.getnchannels(),
            reader.getsampwidth(),
            reader.getframerate(),
        ) == (1, 2, 48000)
        kernel = reader.readframes(reader.getnframes())
    samples = [value[0] for value in struct.iter_unpack("<h", kernel)]
    nonzero = [index for index, value in enumerate(samples) if value != 0]
    assert nonzero and len(samples) < 72000, "Unexpected single-word synthesis length"
    repeated = bytearray(384000 * 2)
    words = []
    for index in range(4):
        start = 19200 + 96000 * index
        repeated[start * 2 : (start + len(samples)) * 2] = kernel
        words.append(
            {
                "tokenId": f"echo-{index + 1}",
                "text": "echo",
                "sourceSampleStart": start + nonzero[0],
                "sourceSampleEndExclusive": start + nonzero[-1] + 1,
                "kernelSampleStart": start,
                "kernelSampleEndExclusive": start + len(samples),
            }
        )
        assert repeated[start * 2 : (start + len(samples)) * 2] == kernel
    pcm(output / "repeated.wav", repeated)
    bed = b"".join(
        struct.pack("<h", round(500 * math.sin(2 * math.pi * 110 * index / 48000)))
        for index in range(384000)
    )
    pcm(output / "bed.wav", bed)
    for name, label in (
        ("base", "VERA 141 BASE SYNTHETIC"),
        ("cutaway", "VERA 141 CUTAWAY SYNTHETIC"),
    ):
        (output / f"{name}.png").write_bytes(render_placeholder_slate(label, 640, 360))
        execute(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-n",
                "-loop",
                "1",
                "-framerate",
                "25",
                "-i",
                str(output / f"{name}.png"),
                "-i",
                str(output / "repeated.wav"),
                "-t",
                "8",
                "-c:v",
                "libx264",
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "pcm_s16le",
                "-video_track_timescale",
                "12800",
                str(output / f"{name}.mov"),
            ]
        )
    # Alpha is explicit; upper-track position alone cannot establish its visible base.
    execute(
        [
            ffmpeg,
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "color=c=green:s=640x360,format=rgba,colorchannelmixer=aa=0.5",
            "-frames:v",
            "1",
            str(output / "overlay.png"),
        ]
    )
    for folder, source in (("relink", "base.mov"), ("wrong", "cutaway.mov")):
        (output / folder).mkdir()
        shutil.copyfile(output / source, output / folder / "base.mov")
    assert digest(output / "base.mov") == digest(output / "relink/base.mov")
    assert digest(output / "base.mov") != digest(output / "wrong/base.mov")
    files = []
    for path in sorted(output.rglob("*")):
        if path.is_file():
            raw = subprocess.run(
                [
                    ffprobe,
                    "-v",
                    "error",
                    "-show_streams",
                    "-show_format",
                    "-of",
                    "json",
                    str(path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            metadata = json.loads(raw.stdout)
            metadata.get("format", {}).pop("filename", None)
            files.append(
                {
                    "path": path.relative_to(output).as_posix(),
                    "sha256": digest(path),
                    "sizeBytes": path.stat().st_size,
                    "ffprobe": metadata,
                }
            )
    docs = Path(
        "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
        "Developer/Scripting"
    )
    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "sampleRate": 48000,
        "sampleIntervalConvention": (
            "half-open integer PCM sample offsets; nonzero waveform support"
        ),
        "wordBoundaryLimit": (
            "Nonzero support of isolated synthetic word copies, "
            "not transcript-derived alignment or program omission proof."
        ),
        "durationSamples": 384000,
        "timelineRate": "25/1",
        "samplesPerFrame": 1920,
        "words": words,
        "files": files,
        "preparationCommands": operations,
        "tools": {
            "python": platform.python_version(),
            "ffmpeg": subprocess.run(
                [ffmpeg, "-version"], capture_output=True, text=True, check=True
            ).stdout.splitlines()[0],
            "say": "installed macOS Alex at 200 words/minute",
        },
        "installedDocs": {
            name: digest(docs / name)
            for name in ("README.md", "DaVinciResolveScript.pyi")
        },
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "mediaDir": str(output),
                "manifestSha256": digest(output / "manifest.json"),
                "files": len(files),
                "words": words,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
