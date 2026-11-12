"""SDK-free current-target readback and saved/mapless comparison tests."""

from __future__ import annotations

import hashlib
import json
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from vera_timeline_agent import readback_timeline_cli as cli
from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.row_timeline_map import make_row_timeline_map
from vera_timeline_agent.workflow_v2 import _marker_stamp, _stamp


class FakeItem:
    def __init__(self, event: dict[str, Any], uid: str) -> None:
        self.stamp = _stamp(event)
        self.uid = uid
        self.start = event["recordRange"]["startFrame"]
        self.duration = event["recordRange"]["durationFrames"]

    def GetMarkerCustomData(self, frame: int) -> str:
        assert frame == 0
        return self.stamp

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStart(self, _relative: bool) -> int:
        return cast(int, self.start)

    def GetDuration(self, _relative: bool) -> int:
        return cast(int, self.duration)


class FakeTimeline:
    def __init__(
        self, view: dict[str, Any], *, name: str = "T", uid: str = "t-uid"
    ) -> None:
        self.name = name
        self.uid = uid
        self.view = view
        self.items: dict[tuple[str, int], list[FakeItem]] = {
            (track["kind"], track["index"]): [] for track in view["tracks"]
        }
        tracks = {track["id"]: track for track in view["tracks"]}
        for event in view["events"]:
            track = tracks[event["trackId"]]
            self.items[(track["kind"], track["index"])].append(
                FakeItem(event, "native-" + event["id"])
            )
        self.markers = {
            marker["frame"]: {
                "color": "Yellow",
                "name": marker["name"],
                "note": marker["note"],
                "duration": 1,
            }
            for marker in view["markers"]
        }
        self.marker_stamps = {
            marker["frame"]: _marker_stamp(marker) for marker in view["markers"]
        }

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStartFrame(self) -> int:
        return cast(int, self.view["timeline"]["startFrame"])

    def GetEndFrame(self) -> int:
        return cast(
            int,
            (
                self.view["timeline"]["startFrame"]
                + self.view["timeline"]["durationFrames"]
            ),
        )

    def GetTrackCount(self, kind: str) -> int:
        return max((index for k, index in self.items if kind == k), default=0)

    def GetTrackName(self, kind: str, index: int) -> str | None:
        return next(
            (
                track["name"]
                for track in self.view["tracks"]
                if (track["kind"], track["index"]) == (kind, index)
            ),
            None,
        )

    def GetItemListInTrack(self, kind: str, index: int) -> list[FakeItem]:
        return self.items.get((kind, index), [])

    def GetMarkers(self) -> dict[int, dict[str, Any]]:
        return self.markers

    def GetMarkerCustomData(self, frame: int) -> str:
        return self.marker_stamps[frame]


class FakeProject:
    def __init__(self, timeline: FakeTimeline, *, name: str = "P") -> None:
        self.name = name
        self.uid = "p-uid"
        self.timeline = timeline

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetCurrentTimeline(self) -> FakeTimeline:
        return self.timeline


class FakeResolve:
    def __init__(self, project: FakeProject | None) -> None:
        self.project = project

    def GetProjectManager(self) -> FakeResolve:
        return self

    def GetCurrentProject(self) -> FakeProject | None:
        return self.project


def _case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], FakeResolve]:
    original_video = {
        "eventId": "e1",
        "kind": "primary_visual",
        "recordRange": {"startFrame": 0, "endFrame": 12},
        "provenance": {"blockId": "row-a"},
    }
    original_audio = {
        "eventId": "e2",
        "kind": "narration",
        "recordRange": {"startFrame": 0, "endFrame": 12},
        "provenance": {"blockId": "row-a"},
    }
    view: dict[str, Any] = {
        "timeline": {"startFrame": 0, "durationFrames": 12},
        "tracks": [
            {"id": "v", "kind": "video", "index": 1, "name": "Video"},
            {"id": "a", "kind": "audio", "index": 1, "name": "Audio"},
        ],
        "events": [
            {
                "id": original["eventId"],
                "trackId": track,
                "recordRange": {"startFrame": 0, "durationFrames": 12},
                "v2Event": original,
            }
            for track, original in (("v", original_video), ("a", original_audio))
        ],
        "markers": [
            {
                "id": "note-1",
                "frame": 3,
                "color": "YELLOW",
                "name": "Note",
                "note": "text",
                "provenance": {"blockId": "row-a"},
            }
        ],
    }
    manifest = {
        "buildId": "build-1",
        "id": "manifest-1",
        "document": {"documentId": "doc-1"},
        "events": [deepcopy(original_video), deepcopy(original_audio)],
    }
    output = tmp_path / "result"
    output.mkdir()
    raw_attestation = b"fake attestation for injected verified package"
    (output / "v2-attestation.json").write_bytes(raw_attestation)

    def verified(path: Path, digest: str) -> SimpleNamespace:
        assert path == output / "v2-attestation.json"
        assert digest == hashlib.sha256(raw_attestation).hexdigest()
        return SimpleNamespace(
            manifest=manifest,
            view=view,
            attestation={"projectName": "P", "timelineName": "T"},
        )

    monkeypatch.setattr(cli, "load_verified_package_v2", verified)
    timeline = FakeTimeline(view)
    resolve = FakeResolve(FakeProject(timeline))
    monkeypatch.setattr(cli, "_external_resolve", lambda: resolve)
    observed = [
        {
            "eventId": event["id"],
            "resolveItemId": "native-" + event["id"],
            "trackId": event["trackId"],
            "trackKind": "video" if event["trackId"] == "v" else "audio",
            "trackIndex": 1,
            "startFrame": 0,
            "durationFrames": 12,
        }
        for event in view["events"]
    ]
    saved = make_row_timeline_map(
        manifest,
        view,
        observed,
        project_name="P",
        resolve_project_id="p-uid",
        timeline_name="T",
        timeline_id="t-uid",
    )
    (output / "row-timeline-map.json").write_text(json.dumps(saved))
    return output, saved, resolve


def test_map_present_verifies_current_stamped_items_and_saved_uids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output, _, _ = _case(tmp_path, monkeypatch)
    assert cli.main(["--output", str(output)]) == 0
    assert "saved item UIDs match" in capsys.readouterr().out


def test_mapless_only_checks_structure_and_accepts_new_item_uids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _, resolve = _case(tmp_path, monkeypatch)
    (output / "row-timeline-map.json").unlink()
    assert resolve.project is not None
    resolve.project.timeline.items[("video", 1)][0].uid = "different-uid"
    result = cli.readback_output(output)
    assert "no saved map" in result
    assert "UID continuity not checked" in result


@pytest.mark.parametrize(
    ("change", "diagnostic"),
    [
        (lambda r: setattr(r, "project", None), "current Resolve project"),
        (lambda r: setattr(r.project, "name", "another"), "current Resolve project"),
        (lambda r: setattr(r.project, "uid", "wrong"), "project UID"),
        (
            lambda r: setattr(r.project.timeline, "name", "another"),
            "current Resolve timeline",
        ),
        (lambda r: setattr(r.project.timeline, "uid", "wrong"), "timeline UID"),
        (
            lambda r: setattr(
                r.project.timeline.items[("video", 1)][0], "uid", "wrong"
            ),
            "saved row map differs",
        ),
        (
            lambda r: setattr(r.project.timeline.items[("video", 1)][0], "start", 1),
            "event record range differs",
        ),
        (
            lambda r: setattr(
                r.project.timeline.items[("video", 1)][0], "duration", 11
            ),
            "event record range differs",
        ),
        (
            lambda r: r.project.timeline.items[("video", 1)].clear(),
            "missing TimelineItem",
        ),
        (
            lambda r: r.project.timeline.items[("video", 1)].append(
                FakeItem(r.project.timeline.view["events"][0], "another-uid")
            ),
            "duplicate TimelineItem",
        ),
        (
            lambda r: r.project.timeline.items[("video", 1)].append(
                FakeItem(
                    {
                        "id": "unknown",
                        "v2Event": {"eventId": "unknown"},
                        "recordRange": {"startFrame": 9, "durationFrames": 1},
                    },
                    "extra",
                )
            ),
            "extra or unknown",
        ),
        (
            lambda r: setattr(
                r.project.timeline.items[("audio", 1)][0], "stamp", "not-json"
            ),
            "extra or unstamped",
        ),
        (
            lambda r: setattr(
                r.project.timeline.items[("audio", 1)][0],
                "stamp",
                '{"v2EventId":"e2","v2EventSha256":"bad"}',
            ),
            "event stamp differs",
        ),
        (
            lambda r: r.project.timeline.items[("video", 1)].append(
                r.project.timeline.items[("audio", 1)].pop()
            ),
            "event track differs",
        ),
        (lambda r: r.project.timeline.markers.clear(), "marker inventory differs"),
        (
            lambda r: r.project.timeline.marker_stamps.update({3: "wrong"}),
            "timeline marker differs",
        ),
    ],
)
def test_fails_closed_on_current_target_or_structural_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: Any,
    diagnostic: str,
) -> None:
    output, _, resolve = _case(tmp_path, monkeypatch)
    change(resolve)
    with pytest.raises(ValueError, match=diagnostic):
        cli.readback_output(output)


def test_mapless_drift_still_fails_and_named_existing_project_is_explicit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _, resolve = _case(tmp_path, monkeypatch)
    (output / "row-timeline-map.json").unlink()
    assert resolve.project is not None
    resolve.project.name = "My existing project"
    with pytest.raises(ValueError, match="current Resolve project"):
        cli.readback_output(output)
    assert "no saved map" in cli.readback_output(output, project="My existing project")
    resolve.project.timeline.items[("audio", 1)][0].start = 2
    with pytest.raises(ValueError, match="event record range differs"):
        cli.readback_output(output, project="My existing project")


@pytest.mark.parametrize(
    "alter", ["json", "duplicate", "unknown-key", "uid", "symlink"]
)
def test_invalid_existing_map_never_falls_back_to_mapless(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, alter: str
) -> None:
    output, saved, _ = _case(tmp_path, monkeypatch)
    path = output / "row-timeline-map.json"
    if alter == "json":
        path.write_text("{")
    elif alter == "duplicate":
        path.write_text('{"rows":[],"rows":[]}')
    elif alter == "unknown-key":
        saved["unexpected"] = True
        path.write_text(json.dumps(saved))
    elif alter == "uid":
        saved["rows"][0]["items"][0]["resolveItemId"] = "old-other-uid"
        path.write_text(json.dumps(saved))
    else:
        path.unlink()
        path.symlink_to(output / "v2-attestation.json")
    with pytest.raises((ValueError, OSError)):
        cli.readback_output(output)


def test_cli_nonzero_and_no_sdk_write_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    output, _, resolve = _case(tmp_path, monkeypatch)
    assert resolve.project is not None
    resolve.project.timeline.items[("audio", 1)].clear()
    assert cli.main(["--output", str(output)]) == 2
    assert "MISMATCH" in capsys.readouterr().err
    monkeypatch.setattr(
        cli, "_external_resolve", lambda: (_ for _ in ()).throw(RuntimeError("closed"))
    )
    assert cli.main(["--output", str(output)]) == 2
    assert "readback unavailable" in capsys.readouterr().err


def test_native_lock_refuses_overlapping_resolve_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _, _ = _case(tmp_path, monkeypatch)

    @contextmanager
    def locked() -> Any:
        raise NeedsAction("Resolve is already building a timeline")
        yield

    monkeypatch.setattr(cli, "exclusive_resolve_build", locked)
    with pytest.raises(NeedsAction, match="already building"):
        cli.readback_output(output)


def test_switching_current_timeline_during_readback_is_not_a_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, _, resolve = _case(tmp_path, monkeypatch)
    project = resolve.project
    assert project is not None
    original_view = project.timeline.view

    class ChangingResolve(FakeResolve):
        calls = 0

        def GetCurrentProject(self) -> FakeProject | None:
            self.calls += 1
            if self.calls == 2:
                return FakeProject(FakeTimeline(original_view, uid="new"))
            return self.project

    changing = ChangingResolve(project)
    with pytest.raises(ValueError, match="target changed during readback"):
        cli.readback_output(output, resolve_factory=lambda: changing)
