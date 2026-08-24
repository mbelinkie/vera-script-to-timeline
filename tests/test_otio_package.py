from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from vera_timeline_agent.otio_package import (
    BUILD_REPORT_FILENAME,
    IMPORT_INSTRUCTIONS_FILENAME,
    MANIFEST_FILENAME,
    PackageBuildError,
    build_otio_package,
    validate_build_report,
    validate_timeline_manifest,
    verify_otio_package,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
HANDCRAFTED_MANIFEST = REPOSITORY_ROOT / "tests/data/slice_0_2/timeline-manifest.json"
MEDIA_ROOT = REPOSITORY_ROOT / "fixtures"


def load_handcrafted_manifest() -> dict[str, Any]:
    return cast(
        dict[str, Any], json.loads(HANDCRAFTED_MANIFEST.read_text(encoding="utf-8"))
    )


def write_manifest(path: Path, manifest: dict[str, Any]) -> Path:
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def plain_otio_metadata(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: plain_otio_metadata(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [plain_otio_metadata(item) for item in value]
    return value


def test_handcrafted_manifest_is_schema_valid_and_has_acceptance_shape() -> None:
    manifest = load_handcrafted_manifest()
    validate_timeline_manifest(manifest)

    assert [event["kind"] for event in manifest["events"]] == [
        "video",
        "video",
        "video",
        "still",
        "audio",
    ]
    assert all(
        event["sourceRange"]["startFrame"] > 0 for event in manifest["events"][:3]
    )
    assert len(manifest["markers"]) == 1
    assert {transition["kind"] for transition in manifest["transitions"]} == {
        "hard_cut"
    }
    assert [track["name"].split()[0] for track in manifest["tracks"]] == [
        "V1",
        "V2",
        "V3",
        "V4",
        "V5",
        "A1",
        "A2",
        "A3",
        "A4",
        "A5",
        "S1",
    ]


def test_builds_and_parse_verifies_self_contained_package(tmp_path: Path) -> None:
    manifest = load_handcrafted_manifest()
    output = tmp_path / "resolve-import-package"

    result = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    verification = verify_otio_package(output)

    assert result.output_dir == output
    assert verification.event_count == 5
    assert verification.marker_count == 1
    assert verification.media_count == 5
    assert result.otio_path.suffix == ".otio"

    expected_files = {
        MANIFEST_FILENAME,
        BUILD_REPORT_FILENAME,
        IMPORT_INSTRUCTIONS_FILENAME,
        result.otio_path.name,
        *(source["path"] for source in manifest["sources"]),
    }
    actual_files = {
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert actual_files == expected_files
    assert len(list(output.glob("*.otio"))) == 1

    assert json.loads((output / MANIFEST_FILENAME).read_text()) == manifest
    assert (output / MANIFEST_FILENAME).read_bytes() == (
        json.dumps(manifest, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()
    for source in manifest["sources"]:
        copied = output / source["path"]
        original = MEDIA_ROOT / source["path"]
        assert copied.read_bytes() == original.read_bytes()
        assert f"sha256:{sha256(copied)}" == source["contentHash"]


def test_otio_matches_manifest_event_for_event_without_transitions(
    tmp_path: Path,
) -> None:
    manifest = load_handcrafted_manifest()
    result = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, tmp_path / "package")
    timeline = otio.adapters.read_from_file(str(result.otio_path))
    assert isinstance(timeline, otio.schema.Timeline)

    assert timeline.global_start_time is not None
    assert timeline.global_start_time.to_frames() == manifest["timeline"]["startFrame"]
    assert timeline.metadata["vera"]["manifest_id"] == manifest["id"]
    assert timeline.metadata["vera"]["build_id"] == manifest["buildId"]

    actual_tracks = [
        {
            "id": track.metadata["vera"]["track_id"],
            "kind": track.metadata["vera"]["track_kind"],
            "index": track.metadata["vera"]["track_index"],
            "name": track.name,
        }
        for track in timeline.tracks
    ]
    assert actual_tracks == manifest["tracks"]
    assert [track.kind for track in timeline.tracks] == [
        {"video": "Video", "audio": "Audio", "subtitle": "subtitle"}[track["kind"]]
        for track in manifest["tracks"]
    ]
    timeline_rate = (
        manifest["timeline"]["frameRate"]["numerator"]
        / manifest["timeline"]["frameRate"]["denominator"]
    )
    assert all(
        track.duration().rescaled_to(timeline_rate).to_frames()
        == manifest["timeline"]["durationFrames"]
        for track in timeline.tracks
    )

    source_by_id = {source["id"]: source for source in manifest["sources"]}
    actual_events: dict[str, dict[str, Any]] = {}
    for track in timeline.tracks:
        cursor = manifest["timeline"]["startFrame"]
        for child in track:
            duration = child.duration().to_frames()
            if isinstance(child, otio.schema.Clip):
                event_id = child.metadata["vera"]["event_id"]
                media_reference = child.media_reference
                assert isinstance(media_reference, otio.schema.ExternalReference)
                actual_events[event_id] = {
                    "trackId": track.metadata["vera"]["track_id"],
                    "recordRange": {
                        "startFrame": cursor,
                        "durationFrames": duration,
                    },
                    "sourceRange": {
                        "startFrame": child.source_range.start_time.to_frames(),
                        "durationFrames": child.source_range.duration.to_frames(),
                    },
                    "mediaPath": media_reference.target_url,
                    "sourceKind": child.metadata["vera"]["source_kind"],
                }
            cursor += duration

    assert set(actual_events) == {event["id"] for event in manifest["events"]}
    for event in manifest["events"]:
        source = source_by_id[event["sourceId"]]
        expected_source_range = event.get(
            "sourceRange",
            {"startFrame": 0, "durationFrames": event["recordRange"]["durationFrames"]},
        )
        assert actual_events[event["id"]] == {
            "trackId": event["trackId"],
            "recordRange": event["recordRange"],
            "sourceRange": expected_source_range,
            "mediaPath": source["path"],
            "sourceKind": source["kind"],
        }

    transition_objects = list(
        timeline.tracks.find_children(descended_from_type=otio.schema.Transition)
    )
    assert transition_objects == []
    assert (
        plain_otio_metadata(timeline.tracks.metadata["vera"]["hard_cuts"])
        == manifest["transitions"]
    )


def test_marker_and_build_report_are_complete_and_faithful(tmp_path: Path) -> None:
    manifest = load_handcrafted_manifest()
    output = tmp_path / "package"
    result = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    timeline = otio.adapters.read_from_file(str(result.otio_path))

    assert len(timeline.tracks.markers) == 1
    actual_marker = timeline.tracks.markers[0]
    expected_marker = manifest["markers"][0]
    assert actual_marker.name == expected_marker["name"]
    assert actual_marker.marked_range.start_time.to_frames() == expected_marker["frame"]
    assert actual_marker.marked_range.duration.to_frames() == 0
    assert actual_marker.color == expected_marker["color"].upper()
    assert plain_otio_metadata(actual_marker.metadata["vera"]) == {
        "marker_id": expected_marker["id"],
        "note": expected_marker["note"],
        "original_color": expected_marker["color"],
        "provenance": expected_marker["provenance"],
    }

    report = cast(
        dict[str, Any], json.loads((output / BUILD_REPORT_FILENAME).read_text())
    )
    validate_build_report(report)
    assert report["buildId"] == manifest["buildId"]
    assert report["status"] == "ready_with_warnings"
    assert report["temporaryNarration"] is True
    assert report["summary"] == {
        "sourceCount": 5,
        "eventCount": 5,
        "markerCount": 1,
        "placedCount": 5,
        "placeholderCount": 0,
        "manualCompletionCount": 0,
        "warningCount": 1,
        "errorCount": 0,
    }
    assert [entry["eventId"] for entry in report["eventResults"]] == [
        event["id"] for event in manifest["events"]
    ]
    assert all(entry["disposition"] == "placed" for entry in report["eventResults"])
    assert report["issues"][0]["code"] == "TEMPORARY_NARRATION"
    assert report["manualCompletionItems"] == []
    assert report["manifest"]["contentHash"] == f"sha256:{sha256(result.manifest_path)}"

    instructions = (output / IMPORT_INSTRUCTIONS_FILENAME).read_text()
    assert result.otio_path.name in instructions
    assert "synthetic test narration" in instructions
    assert "DaVinci Resolve" in instructions
    assert "Slice 0.3" in instructions


def test_output_is_byte_deterministic_and_track_map_is_configurable(
    tmp_path: Path,
) -> None:
    first = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, tmp_path / "one")
    second = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, tmp_path / "two")

    first_files = {
        path.relative_to(first.output_dir).as_posix(): path.read_bytes()
        for path in first.output_dir.rglob("*")
        if path.is_file()
    }
    second_files = {
        path.relative_to(second.output_dir).as_posix(): path.read_bytes()
        for path in second.output_dir.rglob("*")
        if path.is_file()
    }
    assert first_files == second_files

    adjusted = load_handcrafted_manifest()
    adjusted["tracks"] = [
        {"id": "picture-custom", "kind": "video", "index": 7, "name": "Pictures"},
        {"id": "voice-custom", "kind": "audio", "index": 4, "name": "Voice"},
    ]
    for event in adjusted["events"]:
        if event["trackKind"] == "video":
            event["trackId"] = "picture-custom"
        else:
            event["trackId"] = "voice-custom"
    adjusted_manifest = write_manifest(tmp_path / "adjusted.json", adjusted)
    adjusted_result = build_otio_package(
        adjusted_manifest, MEDIA_ROOT, tmp_path / "adjusted"
    )
    adjusted_timeline = otio.adapters.read_from_file(str(adjusted_result.otio_path))
    assert [
        (
            track.metadata["vera"]["track_id"],
            track.kind,
            track.metadata["vera"]["track_index"],
            track.name,
        )
        for track in adjusted_timeline.tracks
    ] == [
        ("picture-custom", "Video", 7, "Pictures"),
        ("voice-custom", "Audio", 4, "Voice"),
    ]
    adjusted_instructions = adjusted_result.instructions_path.read_text()
    assert "`Pictures`" in adjusted_instructions
    assert "`Voice`" in adjusted_instructions
    assert "Inspect V3" not in adjusted_instructions
    assert "A1" not in adjusted_instructions


def test_verifier_rejects_a_schema_valid_but_incomplete_report(tmp_path: Path) -> None:
    output = tmp_path / "package"
    build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    report_path = output / BUILD_REPORT_FILENAME
    report = cast(dict[str, Any], json.loads(report_path.read_text()))
    report["eventResults"][0]["sourceId"] = report["eventResults"][1]["sourceId"]
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    validate_build_report(report)

    with pytest.raises(PackageBuildError, match="build report is incomplete"):
        verify_otio_package(output)


ManifestMutation = Callable[[dict[str, Any]], None]


def remove_required_id(manifest: dict[str, Any]) -> None:
    del manifest["id"]


def make_path_unsafe(manifest: dict[str, Any]) -> None:
    manifest["sources"][0]["path"] = "../outside.mp4"


def corrupt_declared_hash(manifest: dict[str, Any]) -> None:
    manifest["sources"][0]["contentHash"] = f"sha256:{'0' * 64}"


def reference_missing_media(manifest: dict[str, Any]) -> None:
    manifest["sources"][0]["path"] = "media/missing.mp4"


def overrun_source_range(manifest: dict[str, Any]) -> None:
    manifest["events"][0]["sourceRange"] = {
        "startFrame": 40,
        "durationFrames": 18,
    }


def require_implicit_retime(manifest: dict[str, Any]) -> None:
    manifest["sources"][0]["frameRate"] = {"numerator": 24, "denominator": 1}


def overlap_record_ranges(manifest: dict[str, Any]) -> None:
    manifest["events"][1]["recordRange"]["startFrame"] = 17


def target_incompatible_track(manifest: dict[str, Any]) -> None:
    manifest["events"][-1]["trackId"] = "video-primary"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (remove_required_id, "schema validation failed"),
        (make_path_unsafe, "schema validation failed"),
        (corrupt_declared_hash, "hash mismatch"),
        (reference_missing_media, "does not exist"),
        (overrun_source_range, "exceeds source duration"),
        (require_implicit_retime, "requires a retime"),
        (overlap_record_ranges, "overlaps"),
        (target_incompatible_track, "does not match target track kind"),
    ],
)
def test_rejects_invalid_schema_media_and_ranges_without_publishing_output(
    tmp_path: Path,
    mutation: ManifestMutation,
    message: str,
) -> None:
    manifest = copy.deepcopy(load_handcrafted_manifest())
    mutation(manifest)
    manifest_path = write_manifest(tmp_path / "invalid.json", manifest)
    output = tmp_path / "must-not-exist"

    with pytest.raises(PackageBuildError, match=message):
        build_otio_package(manifest_path, MEDIA_ROOT, output)
    assert not output.exists()


def test_refuses_to_replace_an_existing_output_directory(tmp_path: Path) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("do not delete", encoding="utf-8")

    with pytest.raises(PackageBuildError, match="already exists"):
        build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    assert sentinel.read_text(encoding="utf-8") == "do not delete"


def test_idempotently_reuses_the_same_verified_output(tmp_path: Path) -> None:
    output = tmp_path / "package"
    first = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    before = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }

    second = build_otio_package(HANDCRAFTED_MANIFEST, MEDIA_ROOT, output)
    after = {
        path.relative_to(output).as_posix(): path.read_bytes()
        for path in output.rglob("*")
        if path.is_file()
    }
    assert second == first
    assert after == before


def test_documented_cli_generates_and_verifies_package(tmp_path: Path) -> None:
    output = tmp_path / "cli-package"
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "vera_timeline_agent.otio_package",
            str(HANDCRAFTED_MANIFEST),
            "--media-root",
            str(MEDIA_ROOT),
            "--output",
            str(output),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    assert "Verified 5 events, 1 marker, and 5 media files" in result.stdout
    assert output.is_dir()
    verify_otio_package(output)

    repeated = subprocess.run(
        [
            sys.executable,
            "-m",
            "vera_timeline_agent.otio_package",
            str(HANDCRAFTED_MANIFEST),
            "--media-root",
            str(MEDIA_ROOT),
            "--output",
            str(output),
        ],
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "Ready verified OTIO import package" in repeated.stdout
