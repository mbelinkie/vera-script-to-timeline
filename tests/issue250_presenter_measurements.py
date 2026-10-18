"""Small decoded-pixel checks for the retained Issue 250 Presenter render."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast
from urllib.parse import unquote, urlsplit

from issue178_render_measurements import (
    MeasurementCase,
    _PreparedInput,
    _require,
    authenticate_render,
    expected_prepared_ordinals,
)
from vera_timeline_agent.media_preparation import MediaTools
from vera_timeline_agent.qualification_output_package_v2 import PRESENTER_PROFILE

Json = dict[str, Any]
_PRESENTER_SLOT = "8ef61d23-9625-5b03-a046-e3f1051bbd75"
_PRESENTER_FRAMES = (144, 150, 180, 240, 270, 281, 305, 306)
_ROOT_FRAMES = (144, 150, 180, 240, 306)
_OVERLAY_FRAMES = (270, 281, 305)
_MARKER_SIZE = 64
_MARKER_FRAME_BYTES = _MARKER_SIZE * _MARKER_SIZE * 3
_COLOR_SIZE = 480
_COLOR_FRAME_BYTES = _COLOR_SIZE * _COLOR_SIZE * 3
# In the 64px center crop, x=24 and x=39 land inside the PNG's transparent
# left/right margins; those cells reveal the advancing root under Presenter.
_TRANSPARENT_MARKER_BITS = tuple(
    row * 4 + column for row in range(3) for column in (1, 2)
)
_TRANSPARENT_MARKER_MASK = sum(1 << bit for bit in _TRANSPARENT_MARKER_BITS)
_PRESENTER_BOUNDS = {
    "red": (187, 67, 293, 413),
    "green": (213, 13, 267, 67),
}
_BOUNDS_TOLERANCE = 4


def _manifest_range(event: Json, name: str, expected: tuple[int, int]) -> None:
    _require(
        event.get(name) == {"startFrame": expected[0], "endFrame": expected[1]},
        f"Presenter {name} differs from its fixed fixture range",
    )


def _presenter_events(manifest: Json) -> tuple[Json, Json, Json]:
    timeline = manifest.get("timeline")
    _require(
        isinstance(timeline, dict)
        and timeline.get("width") == 1920
        and timeline.get("height") == 1080
        and timeline.get("durationFrames") == 641
        and timeline.get("frameRate") == {"numerator": 24000, "denominator": 1001},
        "Presenter measurement requires the retained 1920x1080 fixture timeline",
    )
    events = manifest.get("events")
    _require(isinstance(events, list), "Presenter manifest events are required")
    assert isinstance(events, list)
    roots = [row for row in events if row.get("kind") == "primary_visual"]
    overlays = [row for row in events if row.get("kind") == "overlay_visual"]
    presenters = [
        row
        for row in events
        if row.get("kind") == "placeholder"
        and row.get("provenance", {}).get("slotId") == _PRESENTER_SLOT
    ]
    _require(
        len(roots) == len(overlays) == len(presenters) == 1,
        "Presenter fixture must have one root, placeholder, and overlay",
    )
    root, presenter, overlay = roots[0], presenters[0], overlays[0]
    _manifest_range(root, "recordRange", (0, 641))
    _manifest_range(root, "sourceRange", (0, 641))
    _manifest_range(presenter, "recordRange", (145, 281))
    _manifest_range(overlay, "recordRange", (258, 306))
    _manifest_range(overlay, "sourceRange", (0, 48))
    _require(
        presenter.get("pictureTreatment", {})
        .get("composition", {})
        .get("framingPolicy")
        == "contain",
        "Presenter image must use contain framing",
    )
    return root, presenter, overlay


def _binding_path(locator: object) -> Path:
    _require(isinstance(locator, str), "prepared picture locator is required")
    parsed = urlsplit(cast(str, locator))
    _require(
        parsed.scheme == "file" and parsed.netloc in {"", "localhost"},
        "Presenter measurement requires a local prepared picture",
    )
    path = Path(unquote(parsed.path))
    _require(path.is_absolute(), "prepared picture path must be absolute")
    try:
        resolved = path.resolve(strict=True)
    except OSError as error:
        raise AssertionError("Presenter prepared picture is missing") from error
    _require(
        resolved == path and resolved.is_file(),
        "prepared picture must be a real local file without symlinks",
    )
    return resolved


def load_presenter_case(manifest: Json) -> MeasurementCase:
    """Use the current admission's manifest and its exact preparation bindings."""
    root, _presenter, overlay = _presenter_events(manifest)
    raw_bindings = manifest.get("preparationBindings")
    raw_sources = manifest.get("sources")
    _require(
        isinstance(raw_bindings, list) and len(raw_bindings) == 2,
        "Presenter root and overlay preparations are required",
    )
    _require(isinstance(raw_sources, list), "Presenter manifest sources are required")
    assert isinstance(raw_sources, list) and isinstance(raw_bindings, list)
    source_by_id = {row.get("id"): row for row in raw_sources if isinstance(row, dict)}
    bindings = {
        row.get("requirementKey"): row for row in raw_bindings if isinstance(row, dict)
    }
    _require(len(bindings) == 2, "Presenter preparation keys must be unique")
    preparations: dict[str, _PreparedInput] = {}
    for binding in raw_bindings:
        requirement_key = binding["requirementKey"]
        video_path = _binding_path(binding.get("artifactLocator"))
        receipt_path = video_path.parent / "receipt.json"
        audio_path = video_path.parent / "audio.wav"
        _require(
            receipt_path.is_file() and not receipt_path.is_symlink(),
            "Presenter preparation receipt is missing",
        )
        preparations[requirement_key] = _PreparedInput(
            video_path=video_path,
            audio_path=audio_path if audio_path.is_file() else None,
            receipt_path=receipt_path,
            binding=binding,
        )

    for event in (root, overlay):
        source_id = event.get("provenance", {}).get("sourceId")
        source = source_by_id.get(source_id)
        _require(isinstance(source, dict), "Presenter picture source is missing")
        assert isinstance(source, dict)
        _require(
            source.get("preparationRequirementKey") in bindings,
            "Presenter picture has no admitted preparation binding",
        )
    return MeasurementCase(
        case_name="presenter-alpha-01",
        manifest=manifest,
        preparations=preparations,
        expected_frame_ordinals={},
        expected_audio_samples={},
        audio_policies={},
        expected_audio_gain_db={},
    )


def _selected_rgb_frames(
    tools: MediaTools, mov_path: Path, frames: Sequence[int], size: int
) -> tuple[bytes, ...]:
    selected = "+".join(f"eq(n,{frame})" for frame in frames)
    raw = tools.run(
        [
            tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(mov_path),
            "-map",
            "0:v:0",
            "-vf",
            f"select='{selected}',crop=ih:ih:(iw-ih)/2:0,"
            f"scale={size}:{size}:flags=neighbor",
            "-an",
            "-fps_mode",
            "passthrough",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "-",
        ]
    )
    frame_size = size * size * 3
    _require(
        len(raw) == len(frames) * frame_size,
        "selected Presenter render frames are missing or partial",
    )
    return tuple(
        raw[start : start + frame_size] for start in range(0, len(raw), frame_size)
    )


def _marker_ordinal(frame: bytes) -> int:
    _require(len(frame) == _MARKER_FRAME_BYTES, "Presenter marker frame size differs")
    value = 0
    for bit in range(12):
        row, column = divmod(bit, 4)
        x = 9 + column * 15
        y = 9 + row * 14
        offset = (y * _MARKER_SIZE + x) * 3
        if sum(frame[offset : offset + 3]) >= 384:
            value |= 1 << bit
    return value


def _source_ordinal(event: Json, record_frame: int, prepared: Sequence[int]) -> int:
    record_start = event["recordRange"]["startFrame"]
    source_start = event["sourceRange"]["startFrame"]
    source_frame = source_start + record_frame - record_start
    _require(
        0 <= source_frame < len(prepared), "Presenter source sample is out of range"
    )
    return prepared[cast(int, source_frame)]


def _color_bounds(frame: bytes, *, color: str) -> tuple[int, int, int, int] | None:
    _require(len(frame) == _COLOR_FRAME_BYTES, "Presenter color frame size differs")
    left, top, right, bottom = _PRESENTER_BOUNDS[color]
    seed = ((left + right) // 2, (top + bottom) // 2)
    pending = [seed]
    visited: set[tuple[int, int]] = set()
    min_x, min_y = _COLOR_SIZE, _COLOR_SIZE
    max_x = max_y = -1
    # The advancing root has its own green sync flash. Measure the connected
    # Presenter component, including its full edges, rather than that flash.
    while pending:
        x, y = pending.pop()
        if (x, y) in visited or not (0 <= x < _COLOR_SIZE and 0 <= y < _COLOR_SIZE):
            continue
        visited.add((x, y))
        offset = (y * _COLOR_SIZE + x) * 3
        red, green, blue = frame[offset : offset + 3]
        match = (
            red >= 120 and red - green >= 80 and red - blue >= 80
            if color == "red"
            else green >= 120 and green - red >= 80 and green - blue >= 80
        )
        if match:
            min_x, min_y = min(min_x, x), min(min_y, y)
            max_x, max_y = max(max_x, x), max(max_y, y)
            pending.extend(((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)))
    return None if max_x < 0 else (min_x, min_y, max_x, max_y)


def _verify_presenter_bounds(frame: bytes) -> Json:
    observed: Json = {}
    for color, expected in _PRESENTER_BOUNDS.items():
        bounds = _color_bounds(frame, color=color)
        _require(bounds is not None, f"Presenter {color} region is missing")
        assert bounds is not None
        _require(
            all(
                abs(actual - target) <= _BOUNDS_TOLERANCE
                for actual, target in zip(bounds, expected, strict=True)
            ),
            f"Presenter {color} bounds differ from contain geometry: {bounds}",
        )
        observed[color] = list(bounds)
    return {
        "decodedSize": [_COLOR_SIZE, _COLOR_SIZE],
        "expectedBounds": {
            color: list(bounds) for color, bounds in _PRESENTER_BOUNDS.items()
        },
        "observedBounds": observed,
        "tolerancePixels": _BOUNDS_TOLERANCE,
    }


def measure_presenter_render(
    case: MeasurementCase,
    mov_path: Path,
    outputdir: Path,
    *,
    session_path: Path,
    session_sha256: str,
) -> Json:
    """Measure sparse decoded frames after authenticating the native result chain."""
    from vera_timeline_agent.qualification_output_controller_v2 import (
        load_output_session,
    )

    _require(case.case_name == "presenter-alpha-01", "Presenter fixture case required")
    root, _presenter, overlay = _presenter_events(case.manifest)
    controller = load_output_session(session_path, session_sha256)
    _require(
        controller.admission.profile == PRESENTER_PROFILE,
        "native output session must use the current Presenter profile",
    )
    native_binding = authenticate_render(case, mov_path, session_path, session_sha256)
    _require(
        mov_path.suffix.lower() == ".mov"
        and mov_path.is_file()
        and not mov_path.is_symlink(),
        "authenticated Presenter output must be a real MOV",
    )
    _require(
        outputdir.is_absolute() and outputdir.is_dir() and not outputdir.is_symlink(),
        "Presenter measurement output directory must be an absolute real directory",
    )

    sources = {
        source["id"]: expected_prepared_ordinals(
            case.preparations[source["preparationRequirementKey"]].binding
        )
        for source in case.manifest["sources"]
        if source.get("preparationRequirementKey") in case.preparations
    }
    source_ids = {
        event["eventId"]: event["provenance"]["sourceId"] for event in (root, overlay)
    }
    root_expected = sources[source_ids[root["eventId"]]]
    overlay_expected = sources[source_ids[overlay["eventId"]]]
    tools = MediaTools()
    marker_frames = _selected_rgb_frames(
        tools, mov_path, _PRESENTER_FRAMES, _MARKER_SIZE
    )
    markers = dict(
        zip(_PRESENTER_FRAMES, map(_marker_ordinal, marker_frames), strict=True)
    )

    root_samples: list[Json] = []
    for frame in _ROOT_FRAMES:
        expected = _source_ordinal(root, frame, root_expected)
        observed = markers[frame]
        mask = 0xFFF if frame in {144, 306} else _TRANSPARENT_MARKER_MASK
        _require(
            observed & mask == expected & mask,
            f"root picture ordinal differs at Presenter sample frame {frame}",
        )
        root_samples.append(
            {
                "recordFrame": frame,
                "expectedOrdinal": expected,
                "observedOrdinal": observed,
                "comparedMask": hex(mask),
            }
        )
    overlay_samples: list[Json] = []
    for frame in _OVERLAY_FRAMES:
        expected = _source_ordinal(overlay, frame, overlay_expected)
        observed = markers[frame]
        _require(
            observed == expected,
            f"overlay is not the topmost picture at overlap sample frame {frame}",
        )
        overlay_samples.append(
            {
                "recordFrame": frame,
                "expectedOrdinal": expected,
                "observedOrdinal": observed,
            }
        )

    color_frame = _selected_rgb_frames(tools, mov_path, (180,), _COLOR_SIZE)[0]
    presenter_bounds = _verify_presenter_bounds(color_frame)
    result: Json = {
        "schemaVersion": "issue250-presenter-measurements/v1",
        "status": "passed",
        "caseName": case.case_name,
        "profile": PRESENTER_PROFILE,
        "movPath": str(mov_path),
        "nativeBinding": native_binding,
        "rootSamples": root_samples,
        "overlaySamples": overlay_samples,
        "presenterContainBoundsAtFrame180": presenter_bounds,
        "transparentPresenterMarkerBits": list(_TRANSPARENT_MARKER_BITS),
        "transparentPresenterMarkerCells64": [
            {
                "bit": bit,
                "x": 9 + (bit % 4) * 15,
                "y": 9 + (bit // 4) * 14,
            }
            for bit in _TRANSPARENT_MARKER_BITS
        ],
    }
    result_path = outputdir / "issue250-presenter-measurements.json"
    result_path.write_text(
        json.dumps(
            result, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True
        )
        + "\n",
        encoding="utf-8",
    )
    result["resultPath"] = str(result_path)
    return result
