"""Read-only native edit probe; no Studio mutations are permitted in tests."""

from __future__ import annotations

from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest
from vera_timeline_agent import resolve_test_bench_edit_probe as probe


def _fixture() -> tuple[Any, dict[str, str], dict[str, Any], dict[str, Any]]:
    name = f"VERA Delivery {uuid4()} {uuid4().hex[:12]}"
    target = {
        "projectName": name,
        "timelineName": name,
        "projectUid": "real-new-project",
        "timelineUid": "real-new-timeline",
    }
    tracks: list[dict[str, Any]] = [
        {
            "kind": "video" if index == 0 else "audio",
            "index": 1 if index == 0 else index,
            "trackId": f"track-{index}",
            "name": f"track-{index}",
            "enabled": True,
            "locked": False,
        }
        for index in range(6)
    ]
    rows: list[dict[str, Any]] = []
    placement: dict[tuple[str, int], list[Any]] = {
        (str(spec["kind"]), int(spec["index"])): [] for spec in tracks
    }
    native_by_uid: dict[str, Any] = {}
    for index in range(11):
        kind = "video" if index < 2 else "audio"
        slot_index = 0 if kind == "video" else 1 + (index - 2) % 5
        track = tracks[slot_index]
        uid = f"native-item-{index}"
        start = 0 if index != 1 else 327
        duration = 327 if index == 0 else 1080 if index == 1 else 100
        row: dict[str, Any] = {
            "itemUid": uid,
            "eventId": f"event-{index}",
            "kind": kind,
            "trackId": track["trackId"],
            "recordStart": start,
            "recordDuration": duration,
            "sourceStart": 0,
            "sourceDuration": duration,
            "mediaUid": f"source-{index}",
            "linkedItemUids": [],
        }
        rows.append(row)

        def forbidden_setter(*args: Any, **kwargs: Any) -> None:
            raise AssertionError("capability probe must never mutate Resolve")

        item = SimpleNamespace(
            GetUniqueId=lambda row=row: row["itemUid"],
            GetStart=lambda subframe=False, row=row: row["recordStart"],
            GetDuration=lambda subframe=False, row=row: row["recordDuration"],
            GetMediaPoolItem=lambda row=row: SimpleNamespace(
                GetUniqueId=lambda: row["mediaUid"]
            ),
            GetLinkedItems=lambda: [],
            SetLeftOffset=forbidden_setter,
            SetRightOffset=forbidden_setter,
            SetPosition=forbidden_setter,
        )
        placement[(kind, int(track["index"]))].append(item)
        native_by_uid[uid] = item

    def track_spec(kind: str, index: int) -> dict[str, Any]:
        return next(
            spec for spec in tracks if spec["kind"] == kind and spec["index"] == index
        )

    timeline = SimpleNamespace(
        GetUniqueId=lambda: target["timelineUid"],
        GetName=lambda: target["timelineName"],
        GetTrackCount=lambda kind: max(
            (spec["index"] for spec in tracks if spec["kind"] == kind),
            default=0,
        ),
        GetTrackName=lambda kind, index: track_spec(kind, index)["name"],
        GetIsTrackEnabled=lambda kind, index: track_spec(kind, index)["enabled"],
        GetIsTrackLocked=lambda kind, index: track_spec(kind, index)["locked"],
        GetItemListInTrack=lambda kind, index: placement[(kind, index)],
    )
    project = SimpleNamespace(
        GetUniqueId=lambda: target["projectUid"],
        GetName=lambda: target["projectName"],
        GetCurrentTimeline=lambda: timeline,
        IsRenderingInProgress=lambda: False,
    )
    resolve = SimpleNamespace(
        GetProjectManager=lambda: SimpleNamespace(GetCurrentProject=lambda: project),
        GetVersion=lambda: [21, 1, 2, 10],
    )
    geometry = {
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "context": {"target": target},
        "tracks": tracks,
        "items": rows,
    }
    return resolve, target, geometry, native_by_uid


def test_probe_reports_new_api_without_calling_any_setter() -> None:
    resolve, target, geometry, _ = _fixture()
    result = probe.inspect_selected(resolve, target, geometry)
    assert result["schema"] == probe.SCHEMA
    assert result["disposition"] == "read_only_no_edit_authorized"
    assert result["leftItemUid"] == "native-item-0"
    assert result["rightItemUid"] == "native-item-1"
    assert result["supportsDocumentedOffsetMethods"] is True
    assert len(result["methodPresent"]) == 6
    assert all(result["methodPresent"].values())


def test_older_api_remains_blocked_without_mutation() -> None:
    resolve, target, geometry, _ = _fixture()
    resolve.GetVersion = lambda: [21, 0, 4, 1]
    report = probe.inspect_selected(resolve, target, geometry)
    assert report["supportsDocumentedOffsetMethods"] is False
    assert report["disposition"] == "read_only_no_edit_authorized"


@pytest.mark.parametrize(
    "change",
    [
        "wrong-target",
        "missing-item",
        "moved-item",
        "wrong-media",
        "duplicate",
        "rendering",
        "wrong-track",
    ],
)
def test_probe_refuses_any_changed_native_identity(change: str) -> None:
    resolve, target, geometry, items = _fixture()
    if change == "wrong-target":
        target = {**target, "timelineUid": "different-target"}
    elif change == "missing-item":
        geometry["items"].pop()
    elif change == "moved-item":
        item = items["native-item-1"]
        item.GetStart = lambda subframe=False: 351
    elif change == "wrong-media":
        item = items["native-item-1"]
        item.GetMediaPoolItem = lambda: SimpleNamespace(GetUniqueId=lambda: "different")
    elif change == "duplicate":
        geometry["items"][1]["itemUid"] = geometry["items"][0]["itemUid"]
    elif change == "rendering":
        project = resolve.GetProjectManager().GetCurrentProject()
        project.IsRenderingInProgress = lambda: True
    elif change == "wrong-track":
        timeline = resolve.GetProjectManager().GetCurrentProject().GetCurrentTimeline()
        timeline.GetTrackName = lambda kind, index: "different"
    with pytest.raises(probe.EditProbeRefusal):
        probe.inspect_selected(resolve, target, geometry)


def test_authenticated_read_only_probe_is_write_once(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent import qualification_output_native_v2 as native
    from vera_timeline_agent import qualification_output_proof_v2 as proof
    from vera_timeline_agent import resolve_native_owner as owner

    resolve, target, geometry, _ = _fixture()
    session = SimpleNamespace(context={"phase": "pristine", "target": target})
    calls: list[str] = []
    monkeypatch.setattr(controller, "load_output_session", lambda *args: session)
    monkeypatch.setattr(
        proof, "_load_terminal_output_with_comparison", lambda *args: None
    )
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda *args: {
            "status": "complete",
            "action": "capture_post",
            "context": session.context,
            "target": target,
            "nativeGeometry": geometry,
        },
    )
    monkeypatch.setattr(
        owner,
        "preflight_selected_disposable",
        lambda *args, **kwargs: calls.append("read-only-preflight"),
    )
    monkeypatch.setattr(owner, "native_owner", lambda **kwargs: nullcontext())
    monkeypatch.setattr(owner, "_local_resolve_connection", lambda: resolve)
    root = tmp_path / "probe"

    def inspect() -> dict[str, Any]:
        return probe.inspect_pristine(
            root,
            session_path=tmp_path / "session.json",
            session_sha256="a" * 64,
            capture_path=tmp_path / "capture.json",
            capture_sha256="b" * 64,
        )

    first = inspect()
    assert (root / "edit-capability-probe.json").exists()
    assert calls == ["read-only-preflight"]
    assert inspect() == first
    assert calls == ["read-only-preflight"]
    with pytest.raises(probe.EditProbeRefusal, match="another source"):
        probe.inspect_pristine(
            root,
            session_path=tmp_path / "different-session.json",
            session_sha256="c" * 64,
            capture_path=tmp_path / "capture.json",
            capture_sha256="b" * 64,
        )
