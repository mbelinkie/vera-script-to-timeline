"""Offline guard and receipt tests for the #328 Resolve bridge."""

from __future__ import annotations

import hashlib
import stat
from pathlib import Path
from typing import Any

import pytest

from scripts import issue328_native_bridge as bridge


class Media:
    def __init__(self, media_id: str, path: Path) -> None:
        self.media_id = media_id
        self.uid = f"media-{media_id}"
        self.props = {
            "File Path": str(path),
            "FPS": "24",
            "Resolution": "640 x 360",
            "Duration": "00:00:01:00",
        }

    def GetMediaId(self) -> str:
        return self.media_id

    def GetUniqueId(self) -> str:
        return self.uid

    def GetClipProperty(self, key: str | None = None) -> Any:
        return self.props.get(key) if key is not None else dict(self.props)


class Item:
    def __init__(
        self, uid: str, media: Media, start: int, duration: int, source_start: int = 0
    ) -> None:
        self.uid = uid
        self.media = media
        self.start = start
        self.duration = duration
        self.source_start = source_start

    def GetUniqueId(self) -> str:
        return self.uid

    def GetMediaPoolItem(self) -> Media:
        return self.media

    def GetStart(self, _absolute: bool = False) -> float:
        return float(self.start)

    def GetEnd(self, _absolute: bool = False) -> float:
        return float(self.start + self.duration)

    def GetDuration(self, _absolute: bool = False) -> float:
        return float(self.duration)

    def GetSourceStartFrame(self) -> int:
        return self.source_start

    def GetSourceEndFrame(self) -> int:
        return self.source_start + self.duration - 1

    def GetLeftOffset(self) -> float:
        return float(self.source_start)


class Timeline:
    def __init__(self, state: State, name: str, uid: str) -> None:
        self.state = state
        self.name = name
        self.uid = uid
        self.video: list[Item] = []
        self.audio: list[Item] = []

    def GetName(self) -> str:
        return self.name

    def SetName(self, name: str) -> bool:
        self.name = name
        return True

    def GetUniqueId(self) -> str:
        return self.uid

    def GetMediaPoolItem(self) -> TimelineMedia:
        return TimelineMedia(self.uid)

    def GetStartFrame(self) -> int:
        return 0

    def SetStartTimecode(self, timecode: str) -> bool:
        return timecode == "00:00:00:00"

    def DuplicateTimeline(self) -> Timeline:
        return self.state.project.pool.DuplicateTimeline(self)

    def GetTrackCount(self, kind: str) -> int:
        return 1 if kind in {"video", "audio"} else 0

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item] | None:
        if index != 1:
            return None
        if kind == "video":
            return list(self.video)
        if kind == "audio":
            return list(self.audio)
        return None


class TimelineMedia:
    def __init__(self, timeline_uid: str) -> None:
        self.uid = f"pool-{timeline_uid}"

    def GetUniqueId(self) -> str:
        return self.uid

    def GetClipProperty(self, _key: str | None = None) -> dict[str, str]:
        return {"Type": "Timeline"}


class Folder:
    def __init__(self, state: State) -> None:
        self.state = state

    def GetClipList(self) -> list[Any]:
        timeline_items = [
            timeline.GetMediaPoolItem() for timeline in self.state.project.timelines
        ]
        return [*self.state.media, *timeline_items]


class Pool:
    def __init__(self, state: State) -> None:
        self.state = state

    def GetRootFolder(self) -> Folder:
        return Folder(self.state)

    def ImportMedia(self, paths: list[str]) -> list[Media]:
        by_path = {
            str(Path(path).resolve()): item
            for item in self.state.media
            for path in [item.props["File Path"]]
        }
        return [by_path[str(Path(path).resolve())] for path in paths]

    def CreateEmptyTimeline(self, name: str) -> Timeline:
        timeline = Timeline(self.state, name, self.state.next_timeline_uid())
        self.state.project.timelines.append(timeline)
        self.state.project.current = timeline
        if self.state.audio_on_empty:
            timeline.audio.append(
                Item(self.state.next_item_uid(), self.state.media[0], 0, 24)
            )
        return timeline

    def DuplicateTimeline(self, source: Timeline) -> Timeline:
        duplicate = Timeline(
            self.state, source.name + " Copy", self.state.next_timeline_uid()
        )
        duplicate.video = [
            Item(
                self.state.next_item_uid(),
                item.media,
                item.start,
                item.duration,
                item.source_start,
            )
            for item in source.video
        ]
        duplicate.audio = [
            Item(
                self.state.next_item_uid(),
                item.media,
                item.start,
                item.duration,
                item.source_start,
            )
            for item in source.audio
        ]
        self.state.project.timelines.append(duplicate)
        return duplicate

    def AppendToTimeline(self, values: list[dict[str, Any]]) -> list[Item]:
        if len(values) != 1:
            return []
        spec = values[0]
        if spec["trackIndex"] != 1 or spec["mediaType"] not in {1, 2}:
            return []
        duration = spec["endFrame"] - spec["startFrame"] + 1
        start = spec["startFrame"]
        if self.state.bad_append_readback:
            start += 1
        item = Item(
            self.state.next_item_uid(),
            spec["mediaPoolItem"],
            spec["recordFrame"],
            duration,
            start,
        )
        current = self.state.project.current
        if current is None:
            raise ValueError("no timeline is selected")
        (current.video if spec["mediaType"] == 1 else current.audio).append(item)
        if self.state.drop_append_result:
            return []
        return [item]


class Project:
    def __init__(self, state: State, name: str, uid: str) -> None:
        self.state = state
        self.name = name
        self.uid = uid
        self.timelines: list[Timeline] = []
        self.current: Timeline | None = None
        self.settings: dict[str, str] = {}
        self.pool = Pool(state)

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def SetSetting(self, key: str, value: str) -> bool:
        self.settings[key] = value
        return True

    def GetSetting(self, key: str) -> str | None:
        return self.settings.get(key)

    def GetMediaPool(self) -> Pool:
        return self.pool

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> Timeline | None:
        return self.timelines[index - 1] if 1 <= index <= len(self.timelines) else None

    def GetCurrentTimeline(self) -> Timeline | None:
        return self.current

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        if timeline not in self.timelines:
            return False
        self.current = timeline
        return True


class ProjectManager:
    def __init__(self, state: State) -> None:
        self.state = state
        self.current: Project | None = None
        self.names: list[str] = []

    def GetCurrentProject(self) -> Project | None:
        return self.current

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return list(self.names)

    def CreateProject(self, name: str) -> Project | None:
        if name in self.names:
            return None
        self.names.append(name)
        self.current = Project(self.state, name, "project-1")
        self.state.project = self.current
        return self.current

    def SaveProject(self) -> bool:
        self.state.saved_project = self.current
        return self.current is not None

    def CloseProject(self, project: Project) -> bool:
        if project is not self.current:
            return False
        self.current = None
        return True

    def LoadProject(self, name: str) -> Project | None:
        if self.state.saved_project is None or name != self.state.saved_project.name:
            return None
        self.current = self.state.saved_project
        if self.state.change_ids_on_load:
            self.current.timelines[1].uid = "changed-target-id"
        return self.current


class Resolve:
    def __init__(self, state: State) -> None:
        self.manager = ProjectManager(state)

    def GetProjectManager(self) -> ProjectManager:
        return self.manager


def _current_project(resolve: Resolve) -> Project:
    project = resolve.manager.GetCurrentProject()
    assert project is not None
    return project


def _current_timeline(project: Project) -> Timeline:
    timeline = project.GetCurrentTimeline()
    assert timeline is not None
    return timeline


class State:
    def __init__(self, source_paths: dict[str, Path]) -> None:
        self.media = [
            Media(f"media-{name}", path) for name, path in source_paths.items()
        ]
        self.project: Project
        self.saved_project: Project | None = None
        self.audio_on_empty = False
        self.bad_append_readback = False
        self.drop_append_result = False
        self.change_ids_on_load = False
        self._timeline_id = 0
        self._item_id = 0

    def next_timeline_uid(self) -> str:
        self._timeline_id += 1
        return f"timeline-{self._timeline_id}"

    def next_item_uid(self) -> str:
        self._item_id += 1
        return f"item-{self._item_id}"


def _case(tmp_path: Path) -> tuple[Resolve, dict[str, Any], dict[str, str], State]:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    operation_dir = tmp_path / "operation"
    operation_dir.mkdir()
    paths = {name: source_dir / f"{name}.mov" for name in ("red", "blue")}
    hashes = {}
    for name, path in paths.items():
        payload = f"public synthetic {name} video".encode()
        path.write_bytes(payload)
        hashes[name] = hashlib.sha256(payload).hexdigest()
    state = State(paths)
    resolve = Resolve(state)
    request = {
        "schemaVersion": bridge.SCHEMA,
        "action": "setup",
        "operationId": "12345678-1234-1234-1234-123456789abc",
        "operationDir": str(operation_dir),
        "projectName": "VERA_328_deadbeef",
        "sourceRevision": bridge.SOURCE_REVISION,
        "sources": [
            {
                "id": name,
                "path": str(paths[name]),
                "sha256": hashes[name],
                "sourceInFrame": 0,
                "durationFrames": 24,
            }
            for name in ("red", "blue")
        ],
    }
    setup = bridge.handle_command(request, resolve)
    return resolve, setup, hashes, state


def _command(action: str, session: dict[str, Any], **fields: Any) -> dict[str, Any]:
    return {
        "schemaVersion": bridge.SCHEMA,
        "action": action,
        "session": session,
        **fields,
    }


def test_setup_and_two_appends_bind_receipts_and_survive_reopen(tmp_path: Path) -> None:
    resolve, setup, _hashes, _state = _case(tmp_path)
    session = setup["session"]
    baseline = setup["observation"]["fingerprint"]
    assert (
        setup["observation"]["target"]
        == f"{session['projectUid']}:{session['targetUid']}"
    )
    assert setup["observation"]["source"]
    assert len(_current_project(resolve).pool.GetRootFolder().GetClipList()) == 4
    assert (
        _current_timeline(_current_project(resolve)).GetUniqueId()
        == session["originalUid"]
    )
    assert (
        bridge.handle_command(_command("observe", session), resolve)["observation"]
        == setup["observation"]
    )
    plan = "a" * 64
    blue_change = dict(bridge.CHANGES[0])
    assert (
        bridge.handle_command(
            _command(
                "reconcile",
                session,
                planSha256=plan,
                change=blue_change,
                currentTargetFingerprint=baseline,
            ),
            resolve,
        )["reconciliation"]
        == "not-applied"
    )
    blue = bridge.handle_command(
        _command(
            "apply",
            session,
            planSha256=plan,
            change=blue_change,
            currentTargetFingerprint=baseline,
        ),
        resolve,
    )["receipt"]
    assert blue == {
        "plan": plan,
        "change": "append-blue",
        "target": setup["observation"]["target"],
        "before": baseline,
        "after": blue["after"],
    }
    assert bridge.handle_command(
        _command("verify", session, planSha256=plan, change=blue_change, receipt=blue),
        resolve,
    ) == {"verified": True}
    assert (
        bridge.handle_command(
            _command(
                "reconcile",
                session,
                planSha256=plan,
                change=blue_change,
                currentTargetFingerprint=baseline,
            ),
            resolve,
        )["reconciliation"]
        == blue
    )

    red_change = dict(bridge.CHANGES[1])
    red = bridge.handle_command(
        _command(
            "apply",
            session,
            planSha256=plan,
            change=red_change,
            currentTargetFingerprint=blue["after"],
        ),
        resolve,
    )["receipt"]
    assert bridge.handle_command(
        _command("verify", session, planSha256=plan, change=blue_change, receipt=blue),
        resolve,
    ) == {"verified": True}
    assert bridge.handle_command(
        _command("verify", session, planSha256=plan, change=red_change, receipt=red),
        resolve,
    ) == {"verified": True}
    assert (
        bridge.handle_command(
            _command(
                "reconcile",
                session,
                planSha256=plan,
                change=red_change,
                currentTargetFingerprint=blue["after"],
            ),
            resolve,
        )["reconciliation"]
        == red
    )

    finished = Path(session["operationDir"]) / f"{plan}-append-red.finished.json"
    started = Path(session["operationDir"]) / f"{plan}-append-red.started.json"
    assert stat.S_IMODE(finished.stat().st_mode) == 0o600
    assert stat.S_IMODE(started.stat().st_mode) == 0o600
    reopened = bridge.handle_command(
        _command("reopen", session, planSha256=plan), resolve
    )
    assert reopened == {
        "verified": True,
        "observation": {**setup["observation"], "fingerprint": red["after"]},
        "originalUnchanged": True,
        "originalCurrent": True,
    }


def test_native_whole_frame_floats_are_accepted_but_requests_stay_integer(
    tmp_path: Path,
) -> None:
    _resolve, setup, hashes, state = _case(tmp_path)
    assert bridge._integer(24.0, "native frame") == 24
    for invalid in (True, 24.5, float("nan"), float("inf"), float("-inf")):
        with pytest.raises(ValueError, match="whole frame"):
            bridge._integer(invalid, "native frame")
    with pytest.raises(ValueError, match="must be an integer"):
        bridge._change({**bridge.CHANGES[0], "recordFrame": 24.0})
    with pytest.raises(ValueError, match="must be an integer"):
        bridge._source_specs(
            [
                {
                    "id": name,
                    "path": media.GetClipProperty("File Path"),
                    "sha256": hashes[name],
                    "sourceInFrame": 0,
                    "durationFrames": 24.0,
                }
                for name, media in zip(("red", "blue"), state.media, strict=True)
            ]
        )
    assert setup["session"]["originalGeometry"][0]["durationFrames"] == 24


def test_invalid_change_and_duplicate_apply_refuse_without_replay(
    tmp_path: Path,
) -> None:
    resolve, setup, _hashes, _state = _case(tmp_path)
    session = setup["session"]
    plan = "b" * 64
    with pytest.raises(ValueError, match="fixed two-append plan"):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256=plan,
                change={**bridge.CHANGES[0], "recordFrame": 23},
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    first = bridge.handle_command(
        _command(
            "apply",
            session,
            planSha256=plan,
            change=dict(bridge.CHANGES[0]),
            currentTargetFingerprint=setup["observation"]["fingerprint"],
        ),
        resolve,
    )["receipt"]
    with pytest.raises(ValueError, match="known-before"):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    assert first["change"] == "append-blue"
    assert (
        _current_timeline(_current_project(resolve)).GetUniqueId()
        == session["originalUid"]
    )


def test_started_only_after_mutation_is_unknown_and_blocks_retry(
    tmp_path: Path,
) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    plan = "c" * 64
    state.drop_append_result = True
    with pytest.raises(ValueError, match="did not return exactly one"):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    state.drop_append_result = False
    assert (
        bridge.handle_command(
            _command(
                "reconcile",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )["reconciliation"]
        == "unknown"
    )
    with pytest.raises(ValueError, match="known-before"):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )


def test_started_only_at_before_geometry_is_unknown_and_blocks_replay(
    tmp_path: Path,
) -> None:
    resolve, setup, _hashes, _state = _case(tmp_path)
    session = setup["session"]
    plan = "f" * 64
    change = bridge.CHANGES[0]
    record = {
        "schemaVersion": "vera-issue-328-native-attempt/v1",
        "plan": plan,
        "change": change["id"],
        "target": setup["observation"]["target"],
        "before": setup["observation"]["fingerprint"],
        "after": bridge._fingerprint(bridge._expected_geometry(session, 1)),
    }
    started, _finished = bridge._journal_paths(session, plan, change["id"])
    bridge._write_journal(started, record)
    request = _command(
        "reconcile",
        session,
        planSha256=plan,
        change=change,
        currentTargetFingerprint=setup["observation"]["fingerprint"],
    )
    assert bridge.handle_command(request, resolve)["reconciliation"] == "unknown"
    request["action"] = "apply"
    with pytest.raises(ValueError, match="attempt record"):
        bridge.handle_command(request, resolve)


def test_apply_readback_mismatch_keeps_started_record_and_no_receipt(
    tmp_path: Path,
) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    plan = "d" * 64
    state.bad_append_readback = True
    with pytest.raises(ValueError, match="source bounds differ"):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    assert not (
        Path(session["operationDir"]) / f"{plan}-append-blue.finished.json"
    ).exists()
    assert (
        bridge.handle_command(
            _command(
                "reconcile",
                session,
                planSha256=plan,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )["reconciliation"]
        == "unknown"
    )


def test_source_change_and_wrong_project_are_refused(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    state.media[0].props["File Path"] = str(tmp_path / "missing-red.mov")
    with pytest.raises(ValueError, match="unexpected media-pool source"):
        bridge.handle_command(_command("observe", session), resolve)
    state.media[0].props["File Path"] = session["sources"][0]["path"]
    Path(session["sources"][0]["path"]).write_bytes(b"changed red bytes")
    with pytest.raises(ValueError, match="source bytes changed"):
        bridge.handle_command(_command("observe", session), resolve)
    Path(session["sources"][0]["path"]).write_bytes(b"public synthetic red video")
    _current_project(resolve).uid = "wrong-project"
    with pytest.raises(ValueError, match="current project identity changed"):
        bridge.handle_command(_command("observe", session), resolve)


def test_setup_refuses_duplicate_project_and_audio_baseline(tmp_path: Path) -> None:
    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    operation_dir = tmp_path / "operation"
    operation_dir.mkdir()
    paths = {name: source_dir / f"{name}.mov" for name in ("red", "blue")}
    hashes = {}
    for name, path in paths.items():
        data = f"public synthetic {name} video".encode()
        path.write_bytes(data)
        hashes[name] = hashlib.sha256(data).hexdigest()
    request = {
        "schemaVersion": bridge.SCHEMA,
        "action": "setup",
        "operationId": "12345678-1234-1234-1234-123456789abc",
        "operationDir": str(operation_dir),
        "projectName": "VERA_328_deadbeef",
        "sourceRevision": bridge.SOURCE_REVISION,
        "sources": [
            {
                "id": name,
                "path": str(paths[name]),
                "sha256": hashes[name],
                "sourceInFrame": 0,
                "durationFrames": 24,
            }
            for name in ("red", "blue")
        ],
    }
    duplicate_state = State(paths)
    duplicate_resolve = Resolve(duplicate_state)
    duplicate_resolve.manager.names.append("VERA_328_deadbeef")
    with pytest.raises(ValueError, match="already exists"):
        bridge.handle_command(request, duplicate_resolve)

    audio_state = State(paths)
    audio_state.audio_on_empty = True
    with pytest.raises(ValueError, match="one exact 24-frame red video occurrence"):
        bridge.handle_command(request, Resolve(audio_state))


def test_reopen_rejects_changed_timeline_identity(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    state.change_ids_on_load = True
    with pytest.raises(ValueError, match="reopened timeline identities changed"):
        bridge.handle_command(
            _command("reopen", setup["session"], planSha256="e" * 64), resolve
        )
