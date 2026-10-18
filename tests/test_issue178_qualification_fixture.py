"""The issue #178 qualification fixture traverses real P5 and v2 admission."""

from __future__ import annotations

import platform
import subprocess
import wave
from pathlib import Path

import pytest
from issue174_media_fixture import decode_frame_ordinals
from issue178_qualification_fixture import (
    _COMPILER_CLI,
    _NODE,
    prepare_qualification_case,
)
from vera_timeline_agent import qualification_output_package_v2 as admission
from vera_timeline_agent.media_preparation import MediaTools, _qualified_tools
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.qualification_output_package_v2 import (
    MATRIX_PROFILE,
    SYNTHETIC_PROFILE,
    QualificationPackageError,
    admit_qualification_package_v2,
)

pytestmark = pytest.mark.slow


def _read_first_channel_int24(path: Path) -> tuple[int, ...]:
    with wave.open(str(path), "rb") as source:
        assert source.getnchannels() == 2
        assert source.getsampwidth() == 3
        assert source.getframerate() == 48000
        channels = source.getnchannels()
        raw = source.readframes(source.getnframes())
    samples: list[int] = []
    for offset in range(0, len(raw), channels * 3):
        value = int.from_bytes(raw[offset : offset + 3], "little", signed=False)
        samples.append(value - (1 << 24) if value & (1 << 23) else value)
    return tuple(samples)


def _require_qualified_host() -> None:
    """Skip before generation unless all physical qualification pins exist."""
    if platform.system() != "Darwin":
        pytest.skip("real issue #178 qualification requires the qualified macOS host")
    if (
        not _NODE.is_file()
        or _NODE.is_symlink()
        or not _COMPILER_CLI.is_file()
        or not admission._FFMPEG.is_file()
        or not admission._FFPROBE.is_file()
    ):
        pytest.skip("pinned Node, compiler, or admission ffmpeg tools are unavailable")
    try:
        version = subprocess.run(
            [str(_NODE), "--version"],
            capture_output=True,
            timeout=5,
            check=False,
            env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
        )
        if (
            version.returncode != 0
            or version.stdout.strip() != b"v24.19.0"
            or version.stderr
        ):
            pytest.skip("pinned Node 24.19.0 runtime is not qualified")
        if (
            admission._hash_file(admission._FFMPEG) != admission._FFMPEG_SHA256
            or admission._hash_file(admission._FFPROBE) != admission._FFPROBE_SHA256
        ):
            pytest.skip("pinned admission ffmpeg tools do not match the qualification")
        _qualified_tools(identity_hash(MediaTools().fingerprint()))
    except Exception as error:
        pytest.skip(f"real issue #178 qualification tools are not qualified: {error}")


def test_mixed_25_and_30_sources_compile_and_admit_with_real_p5(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_qualified_host()
    monkeypatch.setattr(admission, "MATRIX_PREPARATION_ROOT", tmp_path)
    case = prepare_qualification_case(tmp_path / "mixed25_30", "mixed25_30")

    assert case.admission.profile == MATRIX_PROFILE
    assert case.build.project_root == case.package_root
    assert case.manifest["timeline"]["frameRate"] == {
        "numerator": 24000,
        "denominator": 1001,
    }
    assert len(case.preparations) == 2
    assert len(case.manifest["events"]) == 3
    assert case.manifest["timeline"]["durationFrames"] == 1032
    assert case.expected_record_frames == {
        "clip-1-25fps": 960,
        "clip-2-30fps": 72,
    }
    assert case.audio_policies == {
        "clip-1-25fps": "full",
        "clip-2-30fps": "mute",
    }
    assert (
        sum(event["kind"] == "source_audio" for event in case.manifest["events"]) == 1
    )
    for label, prepared in case.preparations.items():
        assert prepared.reused is False
        assert prepared.binding["mode"] == "derived_cfr"
        assert prepared.binding["targetRate"] == {
            "numerator": 24000,
            "denominator": 1001,
        }
        observed_ordinals = decode_frame_ordinals(prepared.video_path)
        assert observed_ordinals == case.expected_frame_ordinals[label]
        assert prepared.audio_path is not None
        samples = _read_first_channel_int24(prepared.audio_path)
        assert len(case.expected_audio_samples[label]) == 3
        assert all(
            abs(samples[index]) >= 1_000_000
            for index in case.expected_audio_samples[label]
        )
    with pytest.raises(
        QualificationPackageError,
        match="first smoke profile requires one actual picture/source-audio pair",
    ):
        admit_qualification_package_v2(
            tmp_path / "old-smoke-profile",
            profile=SYNTHETIC_PROFILE,
            package_root=case.package_root,
        )
