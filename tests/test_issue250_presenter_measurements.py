"""Pure decoded-pixel tests for the Issue 250 Presenter measurement helper."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue178_render_measurements import MeasurementCase, _PreparedInput
from issue250_presenter_measurements import (
    _COLOR_FRAME_BYTES,
    _COLOR_SIZE,
    _MARKER_FRAME_BYTES,
    _MARKER_SIZE,
    _PRESENTER_BOUNDS,
    _PRESENTER_FRAMES,
    load_presenter_case,
    measure_presenter_render,
)
from vera_timeline_agent import qualification_output_controller_v2 as controller
from vera_timeline_agent.qualification_output_package_v2 import PRESENTER_PROFILE


def _binding(key: str, frame_count: int) -> dict[str, Any]:
    return {
        "requirementKey": key,
        "mode": "verified_reuse",
        "targetRate": {"numerator": 24000, "denominator": 1001},
        "timeMapping": {
            "sourceRate": {"numerator": 24000, "denominator": 1001},
            "sourceFrameMap": {"packageFrameZeroLogicalFrame": 0},
        },
        "verification": {"decodedFrameCount": frame_count},
    }


def _case() -> MeasurementCase:
    root_binding = _binding("root", 641)
    overlay_binding = _binding("overlay", 48)
    manifest: dict[str, Any] = {
        "timeline": {
            "width": 1920,
            "height": 1080,
            "durationFrames": 641,
            "frameRate": {"numerator": 24000, "denominator": 1001},
        },
        "preparationBindings": [root_binding, overlay_binding],
        "sources": [
            {"id": "root-source", "preparationRequirementKey": "root"},
            {"id": "overlay-source", "preparationRequirementKey": "overlay"},
        ],
        "events": [
            {
                "kind": "primary_visual",
                "eventId": "root-event",
                "recordRange": {"startFrame": 0, "endFrame": 641},
                "sourceRange": {"startFrame": 0, "endFrame": 641},
                "provenance": {"sourceId": "root-source"},
            },
            {
                "kind": "placeholder",
                "recordRange": {"startFrame": 145, "endFrame": 281},
                "pictureTreatment": {"composition": {"framingPolicy": "contain"}},
                "provenance": {"slotId": "8ef61d23-9625-5b03-a046-e3f1051bbd75"},
            },
            {
                "kind": "overlay_visual",
                "eventId": "overlay-event",
                "recordRange": {"startFrame": 258, "endFrame": 306},
                "sourceRange": {"startFrame": 0, "endFrame": 48},
                "provenance": {"sourceId": "overlay-source"},
            },
        ],
    }
    return MeasurementCase(
        case_name="presenter-alpha-01",
        manifest=manifest,
        preparations={
            "root": _PreparedInput(
                Path("/root.mp4"), None, Path("/root.json"), root_binding
            ),
            "overlay": _PreparedInput(
                Path("/overlay.mp4"), None, Path("/overlay.json"), overlay_binding
            ),
        },
        expected_frame_ordinals={},
        expected_audio_samples={},
        audio_policies={},
        expected_audio_gain_db={},
    )


def _marker_frame(ordinal: int) -> bytes:
    frame = bytearray(_MARKER_FRAME_BYTES)
    for bit in range(12):
        if ordinal & (1 << bit):
            row, column = divmod(bit, 4)
            x, y = 9 + column * 15, 9 + row * 14
            offset = (y * _MARKER_SIZE + x) * 3
            frame[offset : offset + 3] = b"\xff\xff\xff"
    return bytes(frame)


def _bounds_frame() -> bytes:
    frame = bytearray(_COLOR_FRAME_BYTES)
    red = _PRESENTER_BOUNDS["red"]
    green = _PRESENTER_BOUNDS["green"]
    for color, bounds in ((b"\xe6\x14\x14", red), (b"\x14\xe6\x14", green)):
        left, top, right, bottom = bounds
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                offset = (y * _COLOR_SIZE + x) * 3
                frame[offset : offset + 3] = color
    return bytes(frame)


def _native_session(profile: str = PRESENTER_PROFILE) -> SimpleNamespace:
    return SimpleNamespace(admission=SimpleNamespace(profile=profile))


def test_presenter_case_uses_the_current_admitted_manifest(tmp_path: Path) -> None:
    manifest = _case().manifest
    manifest["compiler"] = {"sourceHash": "sha256:" + "b" * 64}
    for binding in manifest["preparationBindings"]:
        directory = tmp_path / binding["requirementKey"]
        directory.mkdir()
        picture = directory / "picture.mp4"
        picture.write_bytes(b"picture")
        (directory / "receipt.json").write_text("{}")
        binding["artifactLocator"] = picture.as_uri()

    case = load_presenter_case(manifest)

    assert case.manifest == manifest
    assert case.manifest["compiler"]["sourceHash"] == "sha256:" + "b" * 64
    assert len(case.preparations) == 2


def test_presenter_measurement_checks_sparse_composite_pixels_and_contain_bounds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import issue250_presenter_measurements as measurements

    root = tmp_path / "native.mov"
    root.write_bytes(b"authenticated native movie")
    output = tmp_path / "measurements"
    output.mkdir()
    case = _case()
    monkeypatch.setattr(
        controller, "load_output_session", lambda *_args: _native_session()
    )
    monkeypatch.setattr(
        measurements,
        "authenticate_render",
        lambda *_args: {"outputSha256": "bound-output"},
    )

    class FakeMediaTools:
        ffmpeg = "ffmpeg"

        def run(self, command: list[str]) -> bytes:
            if (
                f"scale={_COLOR_SIZE}:{_COLOR_SIZE}"
                in command[command.index("-vf") + 1]
            ):
                return _bounds_frame()
            frames = []
            for record_frame in _PRESENTER_FRAMES:
                ordinal = (
                    record_frame - 258 if 258 <= record_frame < 306 else record_frame
                )
                frames.append(_marker_frame(ordinal))
            return b"".join(frames)

    monkeypatch.setattr(measurements, "MediaTools", FakeMediaTools)
    result = measure_presenter_render(
        case,
        root,
        output,
        session_path=tmp_path / "session.json",
        session_sha256="session-pin",
    )

    assert result["status"] == "passed"
    assert [row["recordFrame"] for row in result["rootSamples"]] == [
        144,
        150,
        180,
        240,
        306,
    ]
    assert [row["recordFrame"] for row in result["overlaySamples"]] == [270, 281, 305]
    assert result["presenterContainBoundsAtFrame180"]["observedBounds"] == {
        color: list(bounds) for color, bounds in _PRESENTER_BOUNDS.items()
    }
    assert json.loads(Path(result["resultPath"]).read_text())["nativeBinding"] == {
        "outputSha256": "bound-output"
    }


def test_presenter_measurement_refuses_unbound_native_output_before_decode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import issue250_presenter_measurements as measurements

    output = tmp_path / "measurements"
    output.mkdir()
    monkeypatch.setattr(
        controller, "load_output_session", lambda *_args: _native_session()
    )

    def reject_authentication(*_args: Any) -> dict[str, Any]:
        raise AssertionError("MOV bytes differ from completed native output")

    monkeypatch.setattr(measurements, "authenticate_render", reject_authentication)

    class NoDecode:
        def __init__(self) -> None:
            pytest.fail("ffmpeg must not run before native output authentication")

    monkeypatch.setattr(measurements, "MediaTools", NoDecode)
    with pytest.raises(AssertionError, match="MOV bytes differ"):
        measure_presenter_render(
            _case(),
            tmp_path / "not-the-native-output.mov",
            output,
            session_path=tmp_path / "session.json",
            session_sha256="session-pin",
        )
