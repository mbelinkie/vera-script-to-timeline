"""Offline Node-to-Python package coverage for authored quote boxes."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from issue177_package_fixture import _refresh_document_closure, make_package_case
from PIL import Image
from vera_timeline_agent import quote_box_inputs
from vera_timeline_agent.build_compiler_bridge import invoke_bridge
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.native_image_motion import native_still_stem
from vera_timeline_agent.placeholder_slate import transparent_graphic_carrier
from vera_timeline_agent.still_credit import freeze_still_credit_inputs, render_credit
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


def test_adjacent_quote_rows_package_one_continuous_still(quote_case: Any) -> None:
    case = quote_case
    document, deps, manifest, report = [
        json.loads(path.read_text())
        for path in (
            case.document_path,
            case.dependencies_path,
            case.manifest_path,
            case.report_path,
        )
    ]
    rows = document["activeDraft"]["blocks"]
    first = rows[0]
    first_slot = first["primaryVisualSequence"]["slots"][0]
    asset_hash = deps["occurrenceResolutions"][0]["sourceSnapshot"]["contentHash"]
    picture = {
        "researchProjectId": str(uuid4()),
        "ownerKind": "web_capture",
        "ownerId": str(uuid4()),
        "revisionId": str(uuid4()),
        "original": {
            "versionId": "kept-v1",
            "sha256": asset_hash.removeprefix("sha256:"),
            "byteCount": 10,
            "mimeType": "image/png",
            "width": 1920,
            "height": 1080,
        },
    }
    first_slot["payload"]["researchQuotePicture"] = picture
    first["overlayEvents"] = first["overlayEvents"][:1]
    first_box = first["overlayEvents"][0]
    first_box["quoteBox"].update(
        researchProjectId=picture["researchProjectId"],
        researchSourceId=str(uuid4()),
        researchQuoteUseId=str(uuid4()),
        researchQuoteVersion=1,
    )
    last = first["tokens"][-1]
    first_box["timing"].pop("durationMs")
    first_box["timing"]["end"] = {
        "kind": "audible_word_end",
        "anchor": {
            **first_box["timing"]["start"]["anchor"],
            "tokenId": last["id"],
            "quotedWord": last["value"],
            "affinity": "after",
        },
    }

    second = copy.deepcopy(first)
    second.update(id=str(uuid4()), orderKey="b")
    rows.append(second)
    timing = copy.deepcopy(deps["narrationTimingMaps"][0])
    timing["blockId"] = second["id"]
    ids = {token["id"]: str(uuid4()) for token in second["tokens"]}
    for token, observation in zip(second["tokens"], timing["tokens"], strict=True):
        token["id"] = ids[token["id"]]
        observation["tokenId"] = token["id"]
    deps["narrationTimingMaps"].append(timing)
    sequence = second["primaryVisualSequence"]
    sequence["id"] = str(uuid4())
    slot = sequence["slots"][0]
    slot["id"] = str(uuid4())
    payload_id = str(uuid4())
    slot["payload"]["payloadId"] = payload_id
    overlay = second["overlayEvents"][0]
    overlay["id"] = str(uuid4())
    overlay["payload"]["payloadId"] = str(uuid4())
    overlay["quoteBox"].update(
        researchQuoteId=str(uuid4()),
        researchQuoteUseId=str(uuid4()),
        backgroundPayloadId=payload_id,
    )
    for edge in ("start", "end"):
        anchor = overlay["timing"][edge]["anchor"]
        anchor.update(blockId=second["id"], tokenId=ids[anchor["tokenId"]])
    deps["occurrenceResolutions"].append(
        {
            **deps["occurrenceResolutions"][0],
            "payloadId": payload_id,
            "owner": {
                "kind": "primary_slot",
                "sequenceId": sequence["id"],
                "slotId": slot["id"],
            },
        }
    )
    deps["timeline"]["durationFrames"] *= 2
    _refresh_document_closure(document, deps, manifest, report)
    case.document_path.write_text(json.dumps(document))
    case.dependencies_path.write_text(json.dumps(deps))

    compiled = _compile_case(case)["manifest"]
    pictures = [
        event for event in compiled["events"] if event["kind"] == "primary_visual"
    ]
    assert len(pictures) == 1
    assert len(pictures[0]["quoteBackgroundParts"]) == 2
    assert sum(event["kind"] == "quote_box" for event in compiled["events"]) == 2
    assert verify_v2_package(case.build().project_root).event_count == 5


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


def test_still_credit_compiles_packages_and_verifies_real_graphic(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path / "fixture", scenario="still-credit")
    document, deps, manifest, report = [
        json.loads(path.read_text())
        for path in (
            case.document_path,
            case.dependencies_path,
            case.manifest_path,
            case.report_path,
        )
    ]
    row = document["activeDraft"]["blocks"][0]
    payload = row["primaryVisualSequence"]["slots"][0]["payload"]
    asset_hash = deps["occurrenceResolutions"][0]["sourceSnapshot"][
        "contentHash"
    ].removeprefix("sha256:")
    pin = {
        "researchProjectId": str(uuid4()),
        "itemId": str(uuid4()),
        "itemVersion": 1,
        "sourceId": str(uuid4()),
        "title": "Fixture still",
        "credit": "Example Credit",
        "provenance": {
            "kind": "still_crop",
            "sourceUrl": "https://example.com/a.jpg",
            "resolvedUrl": "https://example.com/a.jpg",
            "pageUrl": "https://example.com/",
            "altText": "Fixture",
            "parentItemId": str(uuid4()),
            "crop": {"x": 0, "y": 0, "width": 1, "height": 1},
            "inputSha256": asset_hash,
        },
        "original": {
            "versionId": "kept-v1",
            "sha256": asset_hash,
            "byteCount": 46,
            "mimeType": "image/jpeg",
            "width": 1920,
            "height": 1080,
        },
    }
    payload["researchStill"] = pin
    before = copy.deepcopy(deps)
    assert not freeze_still_credit_inputs(document, deps)
    assert deps == before
    payload["showResearchStillCredit"] = True
    for unusable_credit in ("写真", "\x85"):
        pin["credit"] = unusable_credit
        with pytest.raises(BuildJobError, match="Still credit cannot be displayed"):
            freeze_still_credit_inputs(document, deps)
        assert deps == before
    pin["credit"] = "Example Credit"
    assert freeze_still_credit_inputs(document, deps)
    once = copy.deepcopy(deps)
    assert freeze_still_credit_inputs(document, deps)
    assert deps == once
    _refresh_document_closure(document, deps, manifest, report)
    case.document_path.write_text(json.dumps(document))
    case.dependencies_path.write_text(json.dumps(deps))
    compiled = _compile_case(case)["manifest"]
    credits = [event for event in compiled["events"] if event["kind"] == "still_credit"]
    assert len(credits) == 1
    assert credits[0]["recordRange"] == {"startFrame": 24, "endFrame": 96}
    assert credits[0]["stillCredit"]["text"] == pin["credit"]
    built = case.build()
    assert verify_v2_package(built.project_root).event_count == len(compiled["events"])
    build_root = built.project_root / BUILD_DIRECTORY / built.build_id
    view = json.loads((build_root / DELIVERY_VIEW_FILENAME).read_text())
    event = next(event for event in view["events"] if event["kind"] == "still_credit")
    source = next(
        source for source in view["sources"] if source["id"] == event["sourceId"]
    )
    carrier = built.project_root / source["path"]
    assert carrier.read_bytes() == render_credit(
        pin["credit"], compiled["timeline"]["width"], compiled["timeline"]["height"]
    )
    with Image.open(carrier) as graphic:
        assert graphic.mode == "RGBA"
        assert graphic.getchannel("A").getextrema() == (0, 255)
    assert attest_package_v2(built.project_root, tmp_path / "attestation.json").exists()
