"""Offline Node-to-Python package coverage for authored quote boxes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent import quote_box_inputs
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.native_image_motion import native_still_stem
from vera_timeline_agent.placeholder_slate import transparent_graphic_carrier
from vera_timeline_agent.v2_package import (
    BUILD_DIRECTORY,
    DELIVERY_VIEW_FILENAME,
    OTIO_FILENAME,
    verify_v2_package,
)
from vera_timeline_agent.workflow_v2_cli import attest_package_v2

QUOTE_BOX_SHA256 = (
    "sha256:b089282e6ccab68426eb5f0b39168cb11c051e6798cbe08230b41bf640ff3754"
)


@pytest.fixture
def quote_case(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Use the pinned template revision without requiring Resolve on CI."""
    monkeypatch.setattr(
        quote_box_inputs,
        "verify_installed_quote_box_setting",
        lambda path=None: tmp_path / "EV24 Quote Box.setting",
    )
    return make_package_case(tmp_path / "fixture", scenario="quote-background")


def _compile_case(case: Any) -> dict[str, Any]:
    previous_manifest = json.loads(case.manifest_path.read_text())
    compiled = invoke_bridge("compile", case.document_path, case.dependencies_path)
    result = compiled.result
    assert result["report"]["status"] == "ready"
    previous_sources = {
        event["eventId"]: event["provenance"].get("sourceId")
        for event in previous_manifest["events"]
    }
    for event in result["manifest"]["events"]:
        old_source_id = previous_sources.get(event["eventId"])
        new_source_id = event["provenance"].get("sourceId")
        if not old_source_id or not new_source_id or old_source_id == new_source_id:
            continue
        for prefix in ("source:", "original:"):
            old_key = f"{prefix}{old_source_id}"
            if old_key in case.media_paths:
                case.media_paths[f"{prefix}{new_source_id}"] = case.media_paths.pop(
                    old_key
                )
    case.manifest_path.write_bytes(result["manifestJson"].encode("utf-8"))
    case.report_path.write_bytes(result["reportJson"].encode("utf-8"))
    return result


def test_quote_boxes_compile_package_roundtrip_and_attest(quote_case: Any) -> None:
    case = quote_case
    compiled = _compile_case(case)
    manifest = compiled["manifest"]
    assert (
        manifest["document"]["contentHash"]
        == json.loads(case.document_path.read_text())["liveContentHash"]
    )
    assert case.dependencies_path.read_text()

    quote_events = [
        event for event in manifest["events"] if event["kind"] == "quote_box"
    ]
    assert len(quote_events) == 3
    assert [event["recordRange"] for event in quote_events] == [
        {"startFrame": 0, "endFrame": 24},
        {"startFrame": 24, "endFrame": 48},
        {"startFrame": 48, "endFrame": 72},
    ]
    quote_track = next(
        track for track in manifest["tracks"] if track["id"] == "quote-graphics"
    )
    base_event = next(
        event for event in manifest["events"] if event["kind"] == "primary_visual"
    )
    assert quote_track["index"] == 4
    assert quote_track["index"] > next(
        track["index"]
        for track in manifest["tracks"]
        if track["id"] == base_event["trackId"]
    )
    assert all(event["trackId"] == "quote-graphics" for event in quote_events)
    assert all(
        event["sourceRange"] is None
        and event["sourceTimeMapping"] is None
        and event["preparationBindingHash"] is None
        and event["pictureTreatment"] is None
        and event["audio"] is None
        for event in quote_events
    )
    assert all(
        event["quoteBox"]["templateRevision"] == QUOTE_BOX_SHA256
        for event in quote_events
    )

    built = case.build()
    verified = verify_v2_package(built.project_root)
    assert verified.event_count == len(manifest["events"])
    build_root = built.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / DELIVERY_VIEW_FILENAME).read_text())
    quote_view = [event for event in view["events"] if event["kind"] == "quote_box"]
    assert [event["recordRange"] for event in quote_view] == [
        {"startFrame": 0, "durationFrames": 24},
        {"startFrame": 24, "durationFrames": 24},
        {"startFrame": 48, "durationFrames": 24},
    ]

    source_by_id = {source["id"]: source for source in view["sources"]}
    for event in quote_view:
        source = source_by_id[event["sourceId"]]
        carrier = build_root.parent.parent / source["path"]
        assert source["id"] == event["id"]
        assert source["kind"] == "still"
        assert source["path"] == f"Media/Resolved/{native_still_stem(event['id'])}.png"
        assert carrier.read_bytes() == transparent_graphic_carrier(
            manifest["timeline"]["width"], manifest["timeline"]["height"]
        )

    timeline = otio.adapters.read_from_file(str(build_root / OTIO_FILENAME))
    quote_otio_track = next(
        track
        for track in timeline.tracks
        if track.metadata["vera"]["track_id"] == "quote-graphics"
    )
    assert quote_otio_track.metadata["vera"]["track_index"] == 4
    quote_clips = [
        child for child in quote_otio_track if isinstance(child, otio.schema.Clip)
    ]
    assert [clip.metadata["vera"]["event_kind"] for clip in quote_clips] == [
        "quote_box",
        "quote_box",
        "quote_box",
    ]
    assert [clip.metadata["vera"]["record_range"] for clip in quote_clips] == [
        {"startFrame": 0, "durationFrames": 24},
        {"startFrame": 24, "durationFrames": 24},
        {"startFrame": 48, "durationFrames": 24},
    ]
    assert all(clip.source_range.start_time.to_frames() == 0 for clip in quote_clips)
    assert all(clip.source_range.duration.to_frames() == 24 for clip in quote_clips)

    attestation = attest_package_v2(
        built.project_root, case.project_root.parent / "quote-box-attestation.json"
    )
    attested = json.loads(attestation.read_text())
    assert attested["status"] == "ready_to_import"
    assert attested["verification"] == {
        "eventCount": verified.event_count,
        "markerCount": verified.marker_count,
        "mediaCount": verified.media_count,
    }
