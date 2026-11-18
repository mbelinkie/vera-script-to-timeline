"""Readback refuses substituted stills and missing native motion."""

import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import build_studio_readback as readback
from vera_timeline_agent.build_jobs import NeedsAction


def test_connected_still_readback_checks_source_and_motion(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "still.png"
    source.write_bytes(b"synthetic")
    target = {"buildId": "build", "projectName": "project", "timelineName": "timeline"}
    event = {
        "id": "event",
        "sourceId": "source",
        "trackId": "track",
        "pictureTreatment": {
            "imageMotion": {"mode": "native_dynamic_zoom"},
            "framingPolicy": "fill",
        },
        "recordRange": {"durationFrames": 72},
    }
    package = SimpleNamespace(
        root=tmp_path,
        attestation=target,
        view={
            "timeline": {},
            "sources": [{"id": "source", "kind": "still", "path": "still.png"}],
            "tracks": [{"id": "track", "kind": "video", "index": 1}],
            "events": [event],
        },
        manifest={"sources": [{"id": "source"}], "preparationBindings": []},
    )
    saved = {"resolveProjectId": "project-uid", "timelineId": "timeline-uid"}
    result = {
        **target,
        "status": "verified",
        "verified": True,
        "discrepancies": [],
        "attestationSha256": "digest",
        "rowTimelineMap": saved,
    }
    monkeypatch.setattr(
        readback,
        "status",
        lambda *_: {"state": "terminal", "verified": True, "result": result},
    )
    monkeypatch.setattr(readback, "load_verified_package_v2", lambda *_: package)
    monkeypatch.setattr(readback, "_frame_rate", lambda _: (24000, 1001))
    monkeypatch.setattr(readback, "exclusive_resolve_build", nullcontext)
    monkeypatch.setattr(
        readback,
        "observe_current_timeline_v2",
        lambda *_a, **_k: {
            "projectName": "project",
            "timelineName": "timeline",
            "resolveProjectId": "project-uid",
            "timelineId": "timeline-uid",
            "observed": [],
        },
    )
    monkeypatch.setattr(
        readback, "compare_reopened_row_map", lambda *_a, **_k: "saved-uid-match"
    )
    monkeypatch.setattr(readback, "_assert_readback_target", lambda *_: None)
    monkeypatch.setattr(readback, "_stamp", lambda _: "stamp")
    monkeypatch.setattr(readback, "_native_otio_scaling", lambda _: 3)
    monkeypatch.setattr(readback, "_fractional_source_range_matches", lambda **_: True)
    monkeypatch.setattr(readback, "_exported_motion_matches", lambda *_: None)
    media = SimpleNamespace(
        GetClipProperty=lambda key=None: str(source) if key else {"Frames": "1"}
    )
    props: dict[str, Any] = {"DynamicZoomEnabled": True, "Scaling": 3}
    item = SimpleNamespace(
        GetMarkerCustomData=lambda _: "stamp",
        GetMediaPoolItem=lambda: media,
        GetProperties=lambda: props,
        GetSourceStartFrame=lambda: 0,
        GetSourceEndFrame=lambda: 0,
        GetSpeed=lambda: 100,
    )
    timeline = SimpleNamespace(GetItemListInTrack=lambda *_: [item])
    monkeypatch.setattr(
        readback,
        "_current_readback_target",
        lambda *_a, **_k: (object(), timeline, "project-uid", "timeline-uid"),
    )
    checker = readback.ConnectedStillReadback(
        tmp_path / "request.json", "request-digest", "request", resolve_factory=object
    )
    assert (
        checker(tmp_path / "attestation.json", "digest", "request")["verified"] is True
    )
    props["DynamicZoomEnabled"] = False
    with pytest.raises(NeedsAction, match="zoom or framing"):
        checker(tmp_path / "attestation.json", "digest", "request")
    props["DynamicZoomEnabled"] = True
    media.GetClipProperty = lambda key=None: (
        str(tmp_path / "other.png") if key else {"Frames": "1"}
    )
    with pytest.raises(NeedsAction, match="source differs"):
        checker(tmp_path / "attestation.json", "digest", "request")
    with pytest.raises(NeedsAction, match="request identity"):
        checker(tmp_path / "attestation.json", "digest", "wrong")


def test_exported_native_zoom_endpoints_match_signed_opaque_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "still.png"
    source.write_bytes(b"synthetic")

    def clip(keys: tuple[str, str], scales: tuple[float, float]) -> dict[str, Any]:
        return {
            "OTIO_SCHEMA": "Clip.2",
            "metadata": {"vera": {"event_id": "event"}},
            "media_references": {"DEFAULT_MEDIA": {"target_url": str(source)}},
            "active_media_reference_key": "DEFAULT_MEDIA",
            "effects": [
                {
                    "metadata": {
                        "Resolve_OTIO": {
                            "Type": 59,
                            "Enabled": True,
                            "Parameters": [
                                {
                                    "Parameter ID": "dynamicZoomCenter",
                                    "Key Frames": {
                                        keys[0]: {"Value": [0.0, 0.0]},
                                        keys[1]: {"Value": [0.0, 0.0]},
                                    },
                                },
                                {
                                    "Parameter ID": "dynamicZoomScale",
                                    "Key Frames": {
                                        keys[0]: {"Value": scales[0]},
                                        keys[1]: {"Value": scales[1]},
                                    },
                                },
                            ],
                        }
                    }
                }
            ],
        }

    def document(value: dict[str, Any]) -> dict[str, Any]:
        return {"tracks": {"children": [{"children": [value]}]}}

    signed = tmp_path / "signed.otio"
    signed.write_text(json.dumps(document(clip(("-86400", "-85400"), (0.8, 1.0)))))
    monkeypatch.setattr(readback, "_verify_native_otio_plan", lambda _: signed)
    exported = document(clip(("0", "1000"), (0.8, 1.0)))

    def export(path: str, *_: object) -> bool:
        Path(path).write_text(json.dumps(exported))
        return True

    resolve = SimpleNamespace(EXPORT_OTIO=1, EXPORT_NONE=0)
    timeline = SimpleNamespace(Export=export)
    readback._exported_motion_matches(resolve, timeline, object(), "event", source)
    exported["tracks"]["children"][0]["children"][0]["effects"][0]["metadata"][
        "Resolve_OTIO"
    ]["Parameters"][1]["Key Frames"]["1000"]["Value"] = 1.2
    with pytest.raises(NeedsAction, match="endpoints differ"):
        readback._exported_motion_matches(resolve, timeline, object(), "event", source)
