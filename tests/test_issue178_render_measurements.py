"""Pure measurement checks for Issue 178 native-render assertions."""

from __future__ import annotations

import array
import json
import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from issue178_render_measurements import (
    _check_audio_topology,
    _click_template,
    _measure_click,
    _verify_ordinals,
    authenticate_render,
    load_measurement_case,
    verify_composite_ordinals,
)


def test_composite_frames_keep_root_advancing_under_child_and_overlay() -> None:
    manifest = {
        "timeline": {"durationFrames": 8},
        "tracks": [
            {"id": name, "index": index}
            for index, name in enumerate(("root", "child", "overlay"), 1)
        ],
        "events": [
            {
                "eventId": "root",
                "kind": "primary_visual",
                "trackId": "root",
                "recordRange": {"startFrame": 0, "endFrame": 8},
                "sourceRange": {"startFrame": 0},
                "provenance": {"sourceId": "r"},
            },
            {
                "eventId": "child",
                "kind": "primary_visual",
                "trackId": "child",
                "recordRange": {"startFrame": 2, "endFrame": 5},
                "sourceRange": {"startFrame": 0},
                "provenance": {"sourceId": "c"},
            },
            {
                "eventId": "overlay",
                "kind": "overlay_visual",
                "trackId": "overlay",
                "recordRange": {"startFrame": 4, "endFrame": 6},
                "sourceRange": {"startFrame": 0},
                "provenance": {"sourceId": "o"},
            },
        ],
    }
    sources = {"r": tuple(range(8)), "c": (20, 21, 22), "o": (40, 41)}
    rendered = (0, 1, 20, 21, 40, 41, 6, 7)
    result = verify_composite_ordinals(manifest, sources, rendered)
    assert result["root"]["visibleFrames"] == 4
    with pytest.raises(AssertionError, match="frame 6"):
        verify_composite_ordinals(manifest, sources, (*rendered[:6], 0, 1))


@pytest.mark.parametrize("wrong_output", [False, True])
def test_measurements_require_the_completed_native_movie(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, wrong_output: bool
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent.media_preparation import file_hash

    movie = tmp_path / "native.mov"
    movie.write_bytes(b"actual native movie")
    admission_path = tmp_path / "admission.json"
    admission_path.write_text("{}")
    manifest: dict[str, Any] = {"preparationBindings": []}
    case: Any = SimpleNamespace(manifest=manifest, preparations={})
    admission = SimpleNamespace(
        assert_current=lambda: None,
        manifest=manifest,
        admission_path=admission_path,
        admission={"manifestSha256": "manifest-hash"},
    )
    completed = {
        "status": "complete",
        "outputPath": str(movie),
        "sourceOutputRawSha256": (
            "wrong" if wrong_output else file_hash(movie).removeprefix("sha256:")
        ),
    }
    native = SimpleNamespace(
        admission=admission,
        _latest_attempt=lambda: {"state": "compared_consistent"},
        _native_result=lambda sequence: (
            tmp_path / "result.json",
            "result-hash",
            completed,
        ),
    )
    monkeypatch.setattr(controller, "load_output_session", lambda *_args: native)

    if wrong_output:
        with pytest.raises(AssertionError, match="MOV bytes differ"):
            authenticate_render(case, movie, tmp_path / "session.json", "session-hash")
    else:
        result = authenticate_render(
            case, movie, tmp_path / "session.json", "session-hash"
        )
        assert result["completionResultSha256"] == "result-hash"


def _pcm24(value: int) -> bytes:
    return value.to_bytes(3, "little", signed=True)


def test_click_measurement_finds_offset_and_quiet_gain() -> None:
    reference_samples = [0] * 80
    reference_samples[30:34] = [0x500000, -0x500000, 0x500000, -0x500000]
    raw = b"".join(
        _pcm24(value) for sample in reference_samples for value in (sample, sample)
    )
    template = _click_template(raw, 2, 30)

    rendered = array.array("f", [0.0] * (400 * 2))
    scale = 10 ** (-18 / 20)
    actual_start = 100 + 23
    for index, (left, right) in enumerate(template):
        rendered[(actual_start + index) * 2] = left * scale
        rendered[(actual_start + index) * 2 + 1] = right * scale

    lag, correlation, gain, _dot = _measure_click(rendered, template, 100)

    assert lag == 23
    assert correlation == pytest.approx(1.0)
    assert 20 * math.log10(gain) == pytest.approx(-18.0, abs=0.001)


def test_rendered_ordinal_check_uses_manifest_cuts_and_source_ranges() -> None:
    case: Any = SimpleNamespace(expected_frame_ordinals={"clip": (9, 10, 11, 12)})
    events = [
        {
            "recordRange": {"startFrame": 0, "endFrame": 2},
            "sourceRange": {"startFrame": 1, "endFrame": 3},
            "provenance": {"sourceId": "source-1"},
        },
        {
            "recordRange": {"startFrame": 2, "endFrame": 4},
            "sourceRange": {"startFrame": 0, "endFrame": 2},
            "provenance": {"sourceId": "source-1"},
        },
    ]

    cuts = _verify_ordinals(case, events, {"source-1": "clip"}, (10, 11, 9, 10), 4)

    assert [cut["sampledFrames"] for cut in cuts] == [2, 2]
    assert [cut["preparedStartFrame"] for cut in cuts] == [1, 0]


def test_rendered_ordinal_check_rejects_a_cut_gap() -> None:
    case: Any = SimpleNamespace(expected_frame_ordinals={"clip": (9, 10, 11, 12)})
    events = [
        {
            "recordRange": {"startFrame": 0, "endFrame": 2},
            "sourceRange": {"startFrame": 0, "endFrame": 2},
            "provenance": {"sourceId": "source-1"},
        },
        {
            "recordRange": {"startFrame": 3, "endFrame": 4},
            "sourceRange": {"startFrame": 2, "endFrame": 3},
            "provenance": {"sourceId": "source-1"},
        },
    ]

    with pytest.raises(AssertionError, match="gap or overlap"):
        _verify_ordinals(case, events, {"source-1": "clip"}, (9, 10, 12, 0), 4)


def test_compiled_audio_sample_boundaries_match_preparation_within_one_sample(
    tmp_path: Path,
) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "audio": {
                    "sourceFirstSample": 1000,
                    "sourceExclusiveSample": 2000,
                }
            }
        ),
        encoding="utf-8",
    )
    case: Any = SimpleNamespace(
        preparations={"clip": SimpleNamespace(receipt_path=receipt_path)},
        audio_policies={"clip": "full"},
        expected_audio_gain_db={"clip": 0.0},
    )
    record_range = {"startFrame": 0, "endFrame": 10}
    visual_events = [
        {
            "recordRange": record_range,
            "provenance": {"sourceId": "source-1"},
        }
    ]
    audio_events: list[dict[str, Any]] = [
        {
            "recordRange": record_range,
            "provenance": {"sourceId": "source-1"},
            "audio": {
                "audioPolicy": "full",
                "gainDb": 0.0,
                "sampleRange": {"startFrame": 1001, "endFrame": 1999},
            },
        }
    ]

    _check_audio_topology(case, {"source-1": "clip"}, visual_events, audio_events)

    audio_events[0]["audio"]["sampleRange"]["endFrame"] = 1998
    with pytest.raises(AssertionError, match="end differs from preparation"):
        _check_audio_topology(case, {"source-1": "clip"}, visual_events, audio_events)


def test_measurement_case_loads_persisted_files_without_rebuilding(
    tmp_path: Path,
) -> None:
    root = tmp_path / "case"
    prep = root / "preparations" / "clip"
    prep.mkdir(parents=True)
    (prep / "picture.mp4").write_bytes(b"prepared picture")
    (prep / "receipt.json").write_text("{}", encoding="utf-8")
    summary = {
        "schemaVersion": "issue178-qualification-case/v1",
        "caseName": "single",
        "manifest": {"events": []},
        "preparations": {
            "clip": {
                "videoPath": "preparations/clip/picture.mp4",
                "audioPath": None,
                "receiptPath": "preparations/clip/receipt.json",
                "binding": {"requirementKey": "prep-1"},
            }
        },
        "expectedFrameOrdinals": {"clip": [1, 2]},
        "expectedAudioSamples": {"clip": []},
        "audioPolicies": {"clip": "mute"},
        "expectedAudioGainDb": {"clip": None},
    }
    (root / "qualification-case.json").write_text(json.dumps(summary), encoding="utf-8")

    case = load_measurement_case(root)

    assert case.case_name == "single"
    assert case.expected_frame_ordinals == {"clip": (1, 2)}
    assert case.preparations["clip"].video_path == prep / "picture.mp4"


def test_measurement_case_rejects_paths_outside_its_root(tmp_path: Path) -> None:
    root = tmp_path / "case"
    root.mkdir()
    (tmp_path / "outside.mov").write_bytes(b"outside")
    summary = {
        "schemaVersion": "issue178-qualification-case/v1",
        "caseName": "single",
        "manifest": {},
        "preparations": {
            "clip": {
                "videoPath": "../outside.mov",
                "audioPath": None,
                "receiptPath": "receipt.json",
                "binding": {},
            }
        },
        "expectedFrameOrdinals": {"clip": []},
        "expectedAudioSamples": {"clip": []},
        "audioPolicies": {"clip": "mute"},
        "expectedAudioGainDb": {"clip": None},
    }
    (root / "qualification-case.json").write_text(json.dumps(summary), encoding="utf-8")

    with pytest.raises(ValueError, match="escapes"):
        load_measurement_case(root)
