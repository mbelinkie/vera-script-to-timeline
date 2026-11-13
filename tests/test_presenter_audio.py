"""Synthetic CLI coverage for cleaned presenter audio (#92)."""

from __future__ import annotations

import hashlib
import os
import shutil
import stat
import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import numpy as np
import pytest
from vera_timeline_agent.presenter_sync import find_offset
from vera_timeline_agent.presenter_takes import RATE, decode_audio

ROOT = Path(__file__).resolve().parents[1]
VIDEO_SECONDS = 12
VIDEO_FPS = 30
OUTPUT_RATE = 48_000
OUTPUT_SAMPLES = VIDEO_SECONDS * OUTPUT_RATE

pytestmark = pytest.mark.slow


@pytest.fixture
def media_tools() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if ffmpeg is None or ffprobe is None:
        pytest.skip("synthetic presenter media tests require ffmpeg and ffprobe")
    return ffmpeg, ffprobe


def _performance(seconds: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    count = seconds * OUTPUT_RATE
    active = np.repeat(rng.random(seconds * 4) > 0.4, OUTPUT_RATE // 4)
    return (rng.standard_normal(count) * active[:count] * 0.2).astype(np.float32)


def _write_wav(path: Path, samples: np.ndarray) -> None:
    pcm = np.round(np.clip(samples, -1.0, 1.0) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(OUTPUT_RATE)
        audio.writeframes(pcm.tobytes())


def _make_video(ffmpeg: str, video: Path, audio: Path) -> None:
    result = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=64x64:r={VIDEO_FPS}:d={VIDEO_SECONDS}",
            "-i",
            str(audio),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "mpeg4",
            "-q:v",
            "5",
            "-c:a",
            "pcm_s16le",
            "-t",
            str(VIDEO_SECONDS),
            "-shortest",
            str(video),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0, result.stderr


def _fake_filter(tmp_path: Path) -> tuple[Path, Path]:
    executable = tmp_path / "fake-deep-filter"
    log = tmp_path / "filter-args.json"
    executable.write_text(
        "#!/usr/bin/env python3\n"
        + textwrap.dedent(
            """
            import json
            import os
            import shutil
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            if args[:3] != ["-a", "30", "-D"] or len(args) != 6 or args[3] != "-o":
                raise SystemExit("unexpected DeepFilterNet arguments: " + repr(args))
            output_dir = Path(args[4])
            source = Path(args[5])
            shutil.copyfile(source, output_dir / "filtered.wav")
            Path(os.environ["VERA_TEST_FILTER_LOG"]).write_text(json.dumps(args))
            """
        ),
        encoding="utf-8",
    )
    executable.chmod(
        executable.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH
    )
    return executable, log


def _run_cli(
    video: Path,
    output: Path,
    filter_executable: Path,
    log: Path,
    separate: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        "-m",
        "vera_timeline_agent.presenter_audio",
        str(video),
        "--out",
        str(output),
    ]
    if separate is not None:
        command.extend(["--audio", str(separate)])
    environment = os.environ.copy()
    environment["VERA_DEEPFILTER_COMMAND"] = str(filter_executable)
    environment["VERA_TEST_FILTER_LOG"] = str(log)
    return subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_clean_wav(path: Path) -> None:
    with wave.open(str(path), "rb") as audio:
        assert audio.getnchannels() == 1
        assert audio.getframerate() == OUTPUT_RATE
        assert audio.getsampwidth() == 3
        assert audio.getcomptype() == "NONE"
        assert audio.getnframes() == OUTPUT_SAMPLES


def _assert_output_aligned(video: Path, output: Path) -> None:
    aligned = find_offset(decode_audio(video), decode_audio(output), RATE)
    assert abs(aligned.offset_s) <= 1 / VIDEO_FPS
    assert aligned.spread_s <= 1 / VIDEO_FPS


def test_camera_only_extracts_and_filters_video_audio_without_changing_source(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    camera_audio = tmp_path / "camera.wav"
    video = tmp_path / "camera-only.avi"
    output = tmp_path / "cleaned-camera.wav"
    filter_executable, log = _fake_filter(tmp_path)
    _write_wav(camera_audio, _performance(VIDEO_SECONDS, seed=4))
    _make_video(ffmpeg, video, camera_audio)
    source_hashes = (_sha256(video), _sha256(camera_audio))

    result = _run_cli(video, output, filter_executable, log)

    assert result.returncode == 0, result.stderr
    assert output.is_file()
    _assert_clean_wav(output)
    assert (_sha256(video), _sha256(camera_audio)) == source_hashes
    assert log.is_file()
    assert '"-a", "30", "-D"' in log.read_text(encoding="utf-8")


def test_separate_recording_is_trimmed_to_video_and_verified_in_sync(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    lead_s = 2
    performance = _performance(VIDEO_SECONDS + lead_s, seed=8)
    camera_audio = tmp_path / "camera.wav"
    separate_audio = tmp_path / "separate.wav"
    video = tmp_path / "camera-with-separate-track.avi"
    output = tmp_path / "cleaned-separate.wav"
    filter_executable, log = _fake_filter(tmp_path)
    _write_wav(camera_audio, performance[lead_s * OUTPUT_RATE :])
    _write_wav(separate_audio, performance)
    _make_video(ffmpeg, video, camera_audio)
    source_hashes = (_sha256(video), _sha256(camera_audio), _sha256(separate_audio))

    result = _run_cli(video, output, filter_executable, log, separate_audio)

    assert result.returncode == 0, result.stderr
    assert "Separate audio offset:" in result.stdout
    _assert_clean_wav(output)
    assert (
        _sha256(video),
        _sha256(camera_audio),
        _sha256(separate_audio),
    ) == source_hashes

    _assert_output_aligned(video, output)


def test_late_separate_recording_is_padded_at_video_start(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    late_by_s = 1
    performance = _performance(VIDEO_SECONDS + late_by_s, seed=27)
    camera_audio = tmp_path / "camera.wav"
    separate_audio = tmp_path / "late-separate.wav"
    video = tmp_path / "camera-with-late-track.avi"
    output = tmp_path / "cleaned-late-separate.wav"
    filter_executable, log = _fake_filter(tmp_path)
    _write_wav(camera_audio, performance[:OUTPUT_SAMPLES])
    _write_wav(separate_audio, performance[late_by_s * OUTPUT_RATE :])
    _make_video(ffmpeg, video, camera_audio)
    source_hashes = (_sha256(video), _sha256(camera_audio), _sha256(separate_audio))

    source_alignment = find_offset(
        decode_audio(video), decode_audio(separate_audio), RATE
    )
    assert abs(source_alignment.offset_s + late_by_s) <= 1 / VIDEO_FPS

    result = _run_cli(video, output, filter_executable, log, separate_audio)

    assert result.returncode == 0, result.stderr
    assert "Separate audio offset: -" in result.stdout
    _assert_clean_wav(output)
    assert (
        _sha256(video),
        _sha256(camera_audio),
        _sha256(separate_audio),
    ) == source_hashes
    cleaned = decode_audio(output)
    assert np.max(np.abs(cleaned[: RATE - 100])) < 1e-5
    _assert_output_aligned(video, output)


def test_one_long_recording_is_cut_to_two_video_segments(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    starts_s = (3, 17)
    performance = _performance(30, seed=54)
    separate_audio = tmp_path / "long-separate.wav"
    _write_wav(separate_audio, performance)
    separate_hash = _sha256(separate_audio)
    filter_executable, log = _fake_filter(tmp_path)
    output_audio: list[np.ndarray] = []

    for index, start_s in enumerate(starts_s):
        camera_audio = tmp_path / f"camera-{index}.wav"
        video = tmp_path / f"camera-{index}.avi"
        output = tmp_path / f"cleaned-{index}.wav"
        start = start_s * OUTPUT_RATE
        _write_wav(camera_audio, performance[start : start + OUTPUT_SAMPLES])
        _make_video(ffmpeg, video, camera_audio)

        result = _run_cli(video, output, filter_executable, log, separate_audio)

        assert result.returncode == 0, result.stderr
        assert "Separate audio offset:" in result.stdout
        _assert_clean_wav(output)
        _assert_output_aligned(video, output)
        output_audio.append(decode_audio(output))
        assert _sha256(separate_audio) == separate_hash

    assert not np.array_equal(output_audio[0], output_audio[1])


def test_unrelated_separate_audio_is_refused_without_writing_output_or_changing_sources(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    camera_audio = tmp_path / "camera.wav"
    unrelated_audio = tmp_path / "unrelated.wav"
    video = tmp_path / "camera-with-unrelated-track.avi"
    output = tmp_path / "must-not-be-written.wav"
    filter_executable, log = _fake_filter(tmp_path)
    _write_wav(camera_audio, _performance(VIDEO_SECONDS, seed=12))
    _write_wav(unrelated_audio, _performance(VIDEO_SECONDS + 2, seed=99))
    _make_video(ffmpeg, video, camera_audio)
    source_hashes = (_sha256(video), _sha256(camera_audio), _sha256(unrelated_audio))

    result = _run_cli(video, output, filter_executable, log, unrelated_audio)

    assert result.returncode != 0
    assert "does not clearly match" in (result.stdout + result.stderr)
    assert not output.exists()
    assert (
        _sha256(video),
        _sha256(camera_audio),
        _sha256(unrelated_audio),
    ) == source_hashes
    assert not log.exists()


def test_refuses_video_starting_after_container(
    tmp_path: Path, media_tools: tuple[str, str]
) -> None:
    ffmpeg, _ = media_tools
    audio = tmp_path / "sound.wav"
    video = tmp_path / "offset.mkv"
    output = tmp_path / "output.wav"
    executable, log = _fake_filter(tmp_path)
    _write_wav(audio, _performance(VIDEO_SECONDS, seed=20))
    subprocess.run(
        [
            ffmpeg,
            "-v",
            "error",
            "-i",
            str(audio),
            "-itsoffset",
            "0.5",
            "-f",
            "lavfi",
            "-i",
            f"color=c=black:s=64x64:r=30:d={VIDEO_SECONDS}",
            "-map",
            "1:v:0",
            "-map",
            "0:a:0",
            "-c:v",
            "mpeg4",
            "-c:a",
            "pcm_s16le",
            str(video),
        ],
        check=True,
        capture_output=True,
    )
    result = _run_cli(video, output, executable, log)
    assert result.returncode != 0
    assert "start at different times" in result.stderr
    assert not output.exists()


def test_output_on_filesystem_without_hardlinks(
    tmp_path: Path, media_tools: tuple[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import errno

    from vera_timeline_agent import presenter_audio

    ffmpeg, _ = media_tools
    audio = tmp_path / "sound.wav"
    video = tmp_path / "camera.avi"
    output = tmp_path / "output.wav"
    executable, log = _fake_filter(tmp_path)
    _write_wav(audio, _performance(VIDEO_SECONDS, seed=21))
    _make_video(ffmpeg, video, audio)
    monkeypatch.setenv("VERA_DEEPFILTER_COMMAND", str(executable))
    monkeypatch.setenv("VERA_TEST_FILTER_LOG", str(log))

    def unsupported(*_args: object) -> None:
        raise OSError(errno.ENOTSUP, "unsupported")

    monkeypatch.setattr(presenter_audio.os, "link", unsupported)
    presenter_audio.clean(video, output)
    _assert_clean_wav(output)

    failed_output = tmp_path / "failed.wav"

    def fail_sync(_fd: int) -> None:
        raise OSError("disk failure")

    monkeypatch.setattr(presenter_audio.os, "fsync", fail_sync)
    with pytest.raises(OSError, match="disk failure"):
        presenter_audio.clean(video, failed_output)
    assert not failed_output.exists()
