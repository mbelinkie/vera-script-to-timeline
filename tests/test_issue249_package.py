"""Real preparation, current compiler and package admission for source endpoints."""

from __future__ import annotations

import hashlib
import io
import wave
from pathlib import Path
from typing import Literal

import pytest
from issue249_qualification_fixture import prepare_endpoint_case
from test_issue178_qualification_fixture import _require_qualified_host
from vera_timeline_agent import qualification_output_package_v2 as admission
from vera_timeline_agent.v2_package import verify_v2_package


def _pcm(raw: bytes) -> tuple[int, bytes]:
    with wave.open(io.BytesIO(raw), "rb") as stream:
        assert stream.getframerate() == 48000
        assert stream.getsampwidth() == 3
        return stream.getnframes(), stream.readframes(stream.getnframes())


@pytest.mark.slow
def test_complete_source_endpoints_prepare_package_and_reload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _require_qualified_host()
    monkeypatch.setattr(admission, "MATRIX_PREPARATION_ROOT", tmp_path)
    policies: tuple[Literal["full", "quiet"], ...] = ("full", "quiet")
    for seconds in (3, 10):
        for policy in policies:
            case = prepare_endpoint_case(
                tmp_path / f"{seconds}s-{policy}", seconds, policy
            )
            assert case.manifest["timeline"]["durationFrames"] == seconds * 24
            assert verify_v2_package(case.package_root).build_id == case.build.build_id
            loaded = admission.load_qualification_package_v2(
                case.admission.admission_path,
                hashlib.sha256(case.admission.admission_path.read_bytes()).hexdigest(),
            )
            payload_id = case.payload_ids[f"endpoint-{seconds}s-{policy}"]
            event = next(
                row
                for row in case.admission.view["events"]
                if row["kind"] == "source_audio"
                and row["v2Event"]["provenance"]["payloadId"] == payload_id
            )
            sid = event["sourceId"]
            assert event["sourceRange"] == {
                "startFrame": 0,
                "durationFrames": seconds * 24,
            }
            original = case.admission.source_wavs[sid]
            native = case.admission.source_paths[sid].read_bytes()
            original_count, original_pcm = _pcm(original)
            native_count, native_pcm = _pcm(native)
            assert original_count == seconds * 48000
            assert native_count == seconds * 24 * 2002
            assert native_pcm[: len(original_pcm)] == original_pcm
            assert native_pcm[len(original_pcm) :] == bytes(
                (native_count - original_count) * 6
            )
            entry = next(
                row for row in case.admission.source_entries if row["sourceId"] == sid
            )
            assert entry["pcmFileSha256"] == hashlib.sha256(original).hexdigest()
            assert entry["nativeSourceSha256"] == hashlib.sha256(native).hexdigest()
            assert loaded.source_wavs[sid] == original
            assert loaded.source_paths[sid].read_bytes() == native
