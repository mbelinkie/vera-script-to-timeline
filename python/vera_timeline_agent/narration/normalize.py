from __future__ import annotations

import json
import math
import re
import struct
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent.narration.models import identity_hash

NORMALIZER_VERSION = "ffmpeg-dialogue-loudnorm-normalizer/v2"
DEFAULT_PROFILE_ID = "vera-temporary-narration-v1"
OUTPUT_SAMPLE_RATE = 48000
MINIMUM_DURATION_SAMPLES = 19200


class MediaToolError(RuntimeError):
    pass


@dataclass(frozen=True)
class NormalizationResult:
    wav_bytes: bytes
    profile_id: str
    normalizer_version: str
    tool_fingerprint: str
    sample_rate: int
    channels: int
    sample_format: str
    duration_samples: int
    duration_ms: int
    padding_samples: int
    integrated_lufs: float
    true_peak_dbtp: float
    loudness_range_lu: float


class Normalizer:
    def __init__(
        self,
        *,
        ffmpeg: str = "ffmpeg",
        ffprobe: str = "ffprobe",
        profile_id: str = DEFAULT_PROFILE_ID,
    ) -> None:
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.profile_id = profile_id
        self._fingerprint: str | None = None

    @property
    def tool_fingerprint(self) -> str:
        if self._fingerprint is None:
            outputs: list[str] = []
            for command in (
                [self.ffmpeg, "-version"],
                [self.ffprobe, "-version"],
                [self.ffmpeg, "-hide_banner", "-filters"],
                [self.ffmpeg, "-hide_banner", "-encoders"],
            ):
                result = self._run(command)
                outputs.append(result.stdout + result.stderr)
            needed = ("acompressor", "loudnorm", "aresample", "pcm_s24le")
            combined = "\n".join(outputs)
            missing = [name for name in needed if name not in combined]
            if missing:
                raise MediaToolError(
                    "FFmpeg lacks required capabilities: " + ", ".join(missing)
                )
            self._fingerprint = identity_hash(
                {
                    "recordVersion": "ffmpeg-capabilities/v1",
                    "outputs": outputs,
                }
            )
        return self._fingerprint

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        try:
            return subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            )
        except FileNotFoundError as error:
            raise MediaToolError(
                f"required media tool is unavailable: {command[0]}"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise MediaToolError(f"media tool timed out: {command[0]}") from error
        except subprocess.CalledProcessError as error:
            detail = (error.stderr or error.stdout or "unknown error").strip()
            raise MediaToolError(f"media tool failed: {detail}") from error

    @staticmethod
    def _loudnorm_json(stderr: str) -> dict[str, Any]:
        for candidate in reversed(re.findall(r"\{[^{}]+\}", stderr, flags=re.DOTALL)):
            try:
                value = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and "input_i" in value:
                return cast(dict[str, Any], value)
        raise MediaToolError("FFmpeg loudnorm did not return measurement JSON")

    @staticmethod
    def _finite_number(value: object, label: str) -> float:
        try:
            result = float(cast(str | int | float, value))
        except (TypeError, ValueError) as error:
            raise MediaToolError(f"invalid loudness measurement: {label}") from error
        if not math.isfinite(result):
            raise MediaToolError(f"non-finite loudness measurement: {label}")
        return result

    def _analyze(self, input_path: Path) -> tuple[float, float, float]:
        result = self._run(
            [
                self.ffmpeg,
                "-hide_banner",
                "-nostdin",
                "-i",
                str(input_path),
                "-af",
                "loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json",
                "-f",
                "null",
                "-",
            ]
        )
        measured = self._loudnorm_json(result.stderr)
        return (
            self._finite_number(measured.get("input_i"), "integrated loudness"),
            self._finite_number(measured.get("input_tp"), "true peak"),
            self._finite_number(measured.get("input_lra"), "loudness range"),
        )

    def normalize_pcm(
        self, audio: bytes, *, sample_rate: int, channels: int
    ) -> NormalizationResult:
        if sample_rate <= 0:
            raise MediaToolError("provider sample rate must be positive")
        if channels != 1:
            raise MediaToolError("provider PCM must be mono")
        if not audio or len(audio) % 2:
            raise MediaToolError("provider PCM must contain complete 16-bit samples")
        samples = struct.unpack(f"<{len(audio) // 2}h", audio)
        if max(abs(sample) for sample in samples) == 0:
            raise MediaToolError("provider PCM is silent")
        source_samples = len(samples)
        resampled_samples = round(source_samples * OUTPUT_SAMPLE_RATE / sample_rate)
        padding_samples = max(0, MINIMUM_DURATION_SAMPLES - resampled_samples)
        with tempfile.TemporaryDirectory(
            prefix="vera-narration-normalize-"
        ) as directory:
            root = Path(directory)
            source = root / "provider.pcm"
            output = root / "narration.wav"
            source.write_bytes(audio)
            base_filter = (
                f"aresample={OUTPUT_SAMPLE_RATE}:first_pts=0,"
                "acompressor=threshold=0.125:ratio=4:attack=1:release=50:makeup=1"
            )
            if padding_samples:
                base_filter += ",apad=whole_dur=0.4"
            first = self._run(
                [
                    self.ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-f",
                    "s16le",
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    "1",
                    "-i",
                    str(source),
                    "-af",
                    base_filter + ",loudnorm=I=-16:TP=-1.5:LRA=7:print_format=json",
                    "-f",
                    "null",
                    "-",
                ]
            )
            measured = self._loudnorm_json(first.stderr)
            measurement_names = {
                "measured_I": "input_i",
                "measured_TP": "input_tp",
                "measured_LRA": "input_lra",
                "measured_thresh": "input_thresh",
                "offset": "target_offset",
            }
            measurement_parts = []
            for option, source_name in measurement_names.items():
                number = self._finite_number(measured.get(source_name), source_name)
                measurement_parts.append(f"{option}={number}")
            loudnorm = (
                "loudnorm=I=-16:TP=-1.5:LRA=7:linear=true:print_format=json:"
                + ":".join(measurement_parts)
            )
            self._run(
                [
                    self.ffmpeg,
                    "-hide_banner",
                    "-nostdin",
                    "-f",
                    "s16le",
                    "-ar",
                    str(sample_rate),
                    "-ac",
                    "1",
                    "-i",
                    str(source),
                    "-af",
                    base_filter + "," + loudnorm,
                    "-map_metadata",
                    "-1",
                    "-map_chapters",
                    "-1",
                    "-fflags",
                    "+bitexact",
                    "-flags:a",
                    "+bitexact",
                    "-c:a",
                    "pcm_s24le",
                    "-ar",
                    str(OUTPUT_SAMPLE_RATE),
                    "-ac",
                    "1",
                    "-rf64",
                    "never",
                    str(output),
                ]
            )
            verified = self.verify_wav(output, analyze=False)
            integrated, true_peak, loudness_range = self._analyze(output)
            expected_samples = max(resampled_samples, MINIMUM_DURATION_SAMPLES)
            if verified.duration_samples != expected_samples:
                raise MediaToolError(
                    "normalization changed duration: "
                    f"expected {expected_samples} samples, got "
                    f"{verified.duration_samples}"
                )
            if abs(integrated - (-16.0)) > 0.6 or true_peak > -1.4:
                raise MediaToolError(
                    "normalized loudness is outside tolerance: "
                    f"{integrated} LUFS, {true_peak} dBTP"
                )
            return NormalizationResult(
                wav_bytes=output.read_bytes(),
                profile_id=self.profile_id,
                normalizer_version=NORMALIZER_VERSION,
                tool_fingerprint=self.tool_fingerprint,
                sample_rate=verified.sample_rate,
                channels=verified.channels,
                sample_format=verified.sample_format,
                duration_samples=verified.duration_samples,
                duration_ms=round(
                    verified.duration_samples * 1000 / OUTPUT_SAMPLE_RATE
                ),
                padding_samples=padding_samples,
                integrated_lufs=integrated,
                true_peak_dbtp=true_peak,
                loudness_range_lu=loudness_range,
            )

    def verify_wav(self, path: Path, *, analyze: bool = True) -> NormalizationResult:
        result = self._run(
            [
                self.ffprobe,
                "-v",
                "error",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ]
        )
        try:
            probe = json.loads(result.stdout)
            streams = probe["streams"]
            if not isinstance(streams, list) or len(streams) != 1:
                raise MediaToolError("normalized WAV must contain exactly one stream")
            stream = streams[0]
            if stream.get("codec_name") != "pcm_s24le":
                raise MediaToolError("normalized WAV is not PCM-24")
            sample_rate = int(stream["sample_rate"])
            channels = int(stream["channels"])
            duration_samples = int(stream["duration_ts"])
            bits = int(stream.get("bits_per_raw_sample") or 24)
            sample_fmt = str(stream["sample_fmt"])
            tags = probe.get("format", {}).get("tags", {})
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            raise MediaToolError(
                "FFprobe returned invalid normalized media metadata"
            ) from error
        if sample_rate != OUTPUT_SAMPLE_RATE or channels != 1 or bits != 24:
            raise MediaToolError("normalized WAV has the wrong audio format")
        if tags:
            raise MediaToolError("normalized WAV contains metadata")
        integrated, true_peak, loudness_range = (
            self._analyze(path) if analyze else (0.0, 0.0, 0.0)
        )
        return NormalizationResult(
            wav_bytes=path.read_bytes(),
            profile_id=self.profile_id,
            normalizer_version=NORMALIZER_VERSION,
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=sample_rate,
            channels=channels,
            sample_format=f"{sample_fmt} ({bits} bit)",
            duration_samples=duration_samples,
            duration_ms=round(duration_samples * 1000 / sample_rate),
            padding_samples=0,
            integrated_lufs=integrated,
            true_peak_dbtp=true_peak,
            loudness_range_lu=loudness_range,
        )

    def placeholder(self, block_id: str) -> NormalizationResult:
        # Two alternating tones make a missing line unmistakable without speech.
        phase = sum(block_id.encode("utf-8")) % 40
        samples = []
        for index in range(16000):
            frequency = 660 if (index // 2000) % 2 == 0 else 440
            envelope = 1.0 if index % 2000 < 1600 else 0.0
            value = round(
                7000
                * envelope
                * math.sin(2 * math.pi * frequency * (index + phase) / 16000)
            )
            samples.append(struct.pack("<h", value))
        return self.normalize_pcm(b"".join(samples), sample_rate=16000, channels=1)
