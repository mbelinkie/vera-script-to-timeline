"""Offline guard and receipt tests for the #328 Resolve bridge."""

from __future__ import annotations

import fcntl
import hashlib
import os
import stat
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts import issue328_native_bridge as bridge


@pytest.fixture(autouse=True)
def _private_native_lock(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(bridge, "NATIVE_LOCK_PATH", tmp_path / "native.lock")


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
        self.enabled = True

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

    def GetClipEnabled(self) -> bool:
        return self.enabled


class Timeline:
    def __init__(self, state: State, name: str, uid: str) -> None:
        self.state = state
        self.name = name
        self.uid = uid
        self.video: list[Item] = []
        self.audio: list[Item] = []
        self.video_track_count = 1
        self.audio_track_count = 1
        self.subtitle_track_count = 0
        self.enabled_tracks: dict[tuple[str, int], bool] = {}

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

    def DuplicateTimeline(self, name: str) -> Timeline:
        duplicate = self.state.project.pool.DuplicateTimeline(self)
        duplicate.name = name
        return duplicate

    def GetTrackCount(self, kind: str) -> int:
        return {
            "video": self.video_track_count,
            "audio": self.audio_track_count,
            "subtitle": self.subtitle_track_count,
        }.get(kind, 0)

    def GetIsTrackEnabled(self, kind: str, index: int) -> bool:
        return self.enabled_tracks.get((kind, index), True)

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
    def __init__(self, project: Project) -> None:
        self.project = project

    def GetClipList(self) -> list[Any]:
        timeline_items = [
            timeline.GetMediaPoolItem() for timeline in self.project.timelines
        ]
        return [*self.project.media_items, *timeline_items]

    def GetSubFolderList(self) -> list[Any]:
        return list(self.project.subfolders)


class GalleryAlbum:
    def __init__(self, stills: list[Any] | None = None) -> None:
        self.stills = [] if stills is None else stills

    def GetStills(self) -> list[Any]:
        return list(self.stills)


class Gallery:
    def __init__(self, state: State) -> None:
        self.state = state

    def GetGalleryStillAlbums(self) -> list[GalleryAlbum]:
        return list(self.state.gallery_still_albums)


class Pool:
    def __init__(self, state: State, project: Project) -> None:
        self.state = state
        self.project = project

    def GetRootFolder(self) -> Folder:
        return Folder(self.project)

    def ImportMedia(self, paths: list[str]) -> list[Media]:
        by_path = {
            str(Path(path).resolve()): item
            for item in self.state.media
            for path in [item.props["File Path"]]
        }
        imported = [by_path[str(Path(path).resolve())] for path in paths]
        self.project.media_items = imported
        return imported

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
        duration = spec["endFrame"] - spec["startFrame"]
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
        self.settings: dict[str, Any] = {}
        self.media_items: list[Media] = []
        self.subfolders: list[Any] = []
        self.render_jobs: list[Any] = []
        self.color_groups: list[Any] = []
        self.pool = Pool(state, self)

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def IsRenderingInProgress(self) -> bool:
        return self.state.rendering

    def GetRenderJobList(self) -> list[Any]:
        return list(self.render_jobs)

    def SetSetting(self, key: str, value: str) -> bool:
        self.settings[key] = value
        return True

    def GetSetting(self, key: str | None = None) -> Any:
        return self.settings.get(key) if key is not None else dict(self.settings)

    def GetColorGroupsList(self) -> list[Any]:
        return list(self.color_groups)

    def GetMediaPool(self) -> Pool:
        return self.pool

    def GetGallery(self) -> Gallery:
        return Gallery(self.state)

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
        if not self.state.save_project_ok:
            return False
        self.state.saved_project = self.current
        self.state.save_count += 1
        return self.current is not None

    def CloseProject(self, project: Project) -> bool:
        if project is not self.current:
            return False
        self.current = None
        if self.state.spawn_empty_project_on_close:
            self.current = Project(
                self.state,
                bridge.EMPTY_PROJECT_NAME,
                self.state.empty_project_uid,
            )
            self.current.render_jobs = list(self.state.empty_project_render_jobs)
        return True

    def LoadProject(self, name: str) -> Project | None:
        if self.state.saved_project is None or name != self.state.saved_project.name:
            return None
        self.current = self.state.saved_project
        self.state.project = self.current
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
        self.gallery_still_albums: list[GalleryAlbum] = []
        self.audio_on_empty = False
        self.bad_append_readback = False
        self.drop_append_result = False
        self.change_ids_on_load = False
        self.rendering = False
        self.spawn_empty_project_on_close = False
        self.empty_project_uid = "untitled-project"
        self.empty_project_render_jobs: list[Any] = []
        self.save_project_ok = True
        self.save_count = 0
        self._timeline_id = 0
        self._item_id = 0

    def next_timeline_uid(self) -> str:
        self._timeline_id += 1
        return f"timeline-{self._timeline_id}"

    def next_item_uid(self) -> str:
        self._item_id += 1
        return f"item-{self._item_id}"


def _setup_inputs(
    tmp_path: Path,
) -> tuple[Resolve, dict[str, Any], dict[str, str], State]:
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
    return resolve, request, hashes, state


def _case(tmp_path: Path) -> tuple[Resolve, dict[str, Any], dict[str, str], State]:
    resolve, request, hashes, state = _setup_inputs(tmp_path)
    setup = bridge.handle_command(request, resolve)
    return resolve, setup, hashes, state


def _empty_project_setup_inputs(
    tmp_path: Path, uid: str = "opted-in-empty-project"
) -> tuple[Resolve, dict[str, Any], State, Project]:
    resolve, request, _hashes, state = _setup_inputs(tmp_path)
    project = Project(state, bridge.EMPTY_PROJECT_NAME, uid)
    project.settings = {
        **bridge.SETTINGS,
        "timelineFrameRate": 24.0,
        "timelineColorSpace": "Rec.709",
    }
    state.project = project
    resolve.manager.current = project
    resolve.manager.names.append(bridge.EMPTY_PROJECT_NAME)
    request["expectedEmptyProjectUid"] = uid
    snapshot_settings = dict(project.settings)
    snapshot_settings["timelineFrameRate"] = 24
    request["expectedEmptyProjectSettings"] = snapshot_settings
    return resolve, request, state, project


def _command(action: str, session: dict[str, Any], **fields: Any) -> dict[str, Any]:
    return {
        "schemaVersion": bridge.SCHEMA,
        "action": action,
        "session": session,
        **fields,
    }


def test_host_lock_covers_setup_and_refuses_nested_commands() -> None:
    resolve = Resolve(State({}))
    setup_request = {"schemaVersion": bridge.SCHEMA, "action": "setup"}
    with bridge._native_lock():
        pass
    descriptor = os.open(bridge.NATIVE_LOCK_PATH, os.O_RDWR)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(ValueError, match="another #328 native bridge command"):
            bridge.handle_command(setup_request, resolve)
    finally:
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        os.close(descriptor)
    with (
        bridge._native_lock(),
        pytest.raises(ValueError, match="another #328 native bridge command"),
    ):
        bridge.handle_command(setup_request, resolve)
    assert resolve.manager.GetCurrentProject() is None
    assert resolve.manager.names == []


def test_setup_admits_only_the_opted_in_empty_untitled_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, _state, project = _empty_project_setup_inputs(tmp_path)
    observations = 0
    get_current_project = resolve.manager.GetCurrentProject
    create_project = resolve.manager.CreateProject

    def observe_current() -> Project | None:
        nonlocal observations
        observations += 1
        return get_current_project()

    def create_after_two_observations(name: str) -> Project | None:
        assert observations == 2
        return create_project(name)

    monkeypatch.setattr(resolve.manager, "GetCurrentProject", observe_current)
    monkeypatch.setattr(resolve.manager, "CreateProject", create_after_two_observations)
    result = bridge.handle_command(request, resolve)

    assert result["session"]["projectUid"] == "project-1"
    assert project.GetName() == bridge.EMPTY_PROJECT_NAME


@pytest.mark.parametrize(
    ("hazard", "message"),
    [
        ("clip", "empty project has root media clips"),
        ("folder", "empty project has root subfolders"),
        ("wrong-uid", "empty project identity differs from opt-in"),
        ("settings", "empty project settings differ from snapshot"),
        ("render-job", "empty project has render jobs"),
        ("rendering", "empty project is rendering"),
        ("gallery-still", "empty project has gallery stills"),
        ("color-group", "empty project has color groups"),
    ],
)
def test_setup_refuses_unsafe_opted_in_untitled_project(
    tmp_path: Path, hazard: str, message: str
) -> None:
    resolve, request, state, project = _empty_project_setup_inputs(tmp_path)
    if hazard == "clip":
        project.media_items.append(state.media[0])
    elif hazard == "folder":
        project.subfolders.append(object())
    elif hazard == "wrong-uid":
        project.uid = "another-empty-project"
    elif hazard == "settings":
        project.settings["timelineColorSpace"] = "Rec.2020"
    elif hazard == "render-job":
        project.render_jobs.append({"JobId": "queued"})
    elif hazard == "rendering":
        state.rendering = True
    elif hazard == "color-group":
        project.color_groups.append(object())
    else:
        state.gallery_still_albums.append(GalleryAlbum([object()]))

    with pytest.raises(ValueError, match=message):
        bridge.handle_command(request, resolve)
    assert resolve.manager.GetCurrentProject() is project
    assert "VERA_328_deadbeef" not in resolve.manager.names


def test_setup_refuses_untitled_project_without_uid_opt_in(tmp_path: Path) -> None:
    resolve, request, _state, _project = _empty_project_setup_inputs(tmp_path)
    del request["expectedEmptyProjectUid"]
    del request["expectedEmptyProjectSettings"]

    with pytest.raises(ValueError, match="explicit empty-project identity opt-in"):
        bridge.handle_command(request, resolve)
    assert "VERA_328_deadbeef" not in resolve.manager.names


def test_setup_rechecks_empty_project_immediately_before_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, _state, project = _empty_project_setup_inputs(tmp_path)
    observations = 0
    get_current_project = resolve.manager.GetCurrentProject

    def change_on_second_observation() -> Project | None:
        nonlocal observations
        observations += 1
        if observations == 2:
            project.name = "Changed Project"
        return get_current_project()

    monkeypatch.setattr(
        resolve.manager, "GetCurrentProject", change_on_second_observation
    )
    with pytest.raises(ValueError, match="not the exact empty Untitled Project"):
        bridge.handle_command(request, resolve)
    assert observations == 2
    assert "VERA_328_deadbeef" not in resolve.manager.names


def test_setup_rejects_settings_change_between_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, request, _state, project = _empty_project_setup_inputs(tmp_path)
    get_setting = project.GetSetting
    observations = 0

    def change_settings_on_second_observation(
        key: str | None = None,
    ) -> Any:
        nonlocal observations
        if key is None:
            observations += 1
            if observations == 2:
                project.settings["timelineColorSpace"] = "Rec.2020"
        return get_setting(key)

    monkeypatch.setattr(project, "GetSetting", change_settings_on_second_observation)
    with pytest.raises(ValueError, match="settings differ from snapshot"):
        bridge.handle_command(request, resolve)
    assert observations == 2
    assert "VERA_328_deadbeef" not in resolve.manager.names


def test_abrupt_process_exit_leaves_marker_and_blocks_before_connect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child_code = (
        "import os, sys\n"
        "from pathlib import Path\n"
        "from scripts import issue328_native_bridge as bridge\n"
        "bridge.NATIVE_LOCK_PATH = Path(sys.argv[1])\n"
        "with bridge._native_lock():\n"
        "    os._exit(23)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", child_code, str(bridge.NATIVE_LOCK_PATH)],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        check=False,
        timeout=10,
    )
    assert result.returncode == 23
    marker_path = bridge.NATIVE_LOCK_PATH.with_suffix(".active.json")
    assert marker_path.is_file()
    connect_called = False

    def unexpected_connect() -> Any:
        nonlocal connect_called
        connect_called = True
        raise AssertionError("Resolve must not be contacted while marker exists")

    monkeypatch.setattr(bridge, "_connect", unexpected_connect)
    with pytest.raises(ValueError, match="unresolved native bridge operation marker"):
        bridge.handle_command({"schemaVersion": bridge.SCHEMA, "action": "observe"})
    assert not connect_called
    assert marker_path.is_file()


def test_normal_exception_cleans_marker_but_interrupt_retains_it() -> None:
    request = {"schemaVersion": bridge.SCHEMA, "action": "observe"}
    with pytest.raises(ValueError, match="session is missing"):
        bridge.handle_command(request, Resolve(State({})))
    marker_path = bridge.NATIVE_LOCK_PATH.with_suffix(".active.json")
    assert not marker_path.exists()
    with pytest.raises(KeyboardInterrupt), bridge._native_lock():
        raise KeyboardInterrupt
    assert marker_path.is_file()


def test_active_render_refuses_an_append_without_starting_it(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    state.rendering = True
    with pytest.raises(ValueError, match="render"):
        bridge.handle_command(
            _command(
                "apply",
                setup["session"],
                planSha256="a" * 64,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    assert not list(Path(setup["session"]["operationDir"]).glob("*.started.json"))


@pytest.mark.parametrize(
    ("changed_state", "message"),
    [
        ("project", "current project identity changed before append"),
        ("timeline", "current timeline identity changed before append"),
    ],
)
def test_apply_rechecks_active_identity_immediately_before_append(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    changed_state: str,
    message: str,
) -> None:
    resolve, setup, _hashes, _state = _case(tmp_path)
    project = _current_project(resolve)
    original, target = project.timelines
    append = project.pool.AppendToTimeline
    append_count = 0

    def count_append(values: list[dict[str, Any]]) -> list[Item]:
        nonlocal append_count
        append_count += 1
        return append(values)

    monkeypatch.setattr(project.pool, "AppendToTimeline", count_append)
    assert_active = bridge._assert_active

    def change_identity_then_check(
        manager: ProjectManager,
        project_uid: str,
        project_name: str,
        timeline_uid: str,
        timeline_name: str,
    ) -> None:
        if changed_state == "project":
            project.uid = "changed-project-id"
        else:
            project.current = original
        assert_active(manager, project_uid, project_name, timeline_uid, timeline_name)

    monkeypatch.setattr(bridge, "_assert_active", change_identity_then_check)
    session = setup["session"]
    with pytest.raises(ValueError, match=message):
        bridge.handle_command(
            _command(
                "apply",
                session,
                planSha256="9" * 64,
                change=dict(bridge.CHANGES[0]),
                currentTargetFingerprint=setup["observation"]["fingerprint"],
            ),
            resolve,
        )
    assert append_count == 0
    assert len(original.video) == 1
    assert len(target.video) == 1
    assert _current_timeline(project).GetUniqueId() == session["originalUid"]


def test_setup_and_two_appends_bind_receipts_and_survive_reopen(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    assert state.save_count == 1
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
    assert state.save_count == 2
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
    assert state.save_count == 3
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
    assert state.save_count == 4
    assert reopened == {
        "verified": True,
        "observation": {**setup["observation"], "fingerprint": red["after"]},
        "originalUnchanged": True,
        "originalCurrent": True,
    }


@pytest.mark.parametrize(
    ("uid_matches_closed", "render_jobs", "message"),
    [
        (False, [], None),
        (True, [], "reused the closed project identity"),
        (False, [{"JobId": "queued"}], "has render jobs"),
    ],
)
def test_reopen_checks_default_empty_project_before_loading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    uid_matches_closed: bool,
    render_jobs: list[Any],
    message: str | None,
) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    state.spawn_empty_project_on_close = True
    state.empty_project_uid = (
        session["projectUid"] if uid_matches_closed else "new-empty-project"
    )
    state.empty_project_render_jobs = render_jobs
    load_calls = 0
    load_project = resolve.manager.LoadProject

    def record_load(name: str) -> Project | None:
        nonlocal load_calls
        load_calls += 1
        return load_project(name)

    monkeypatch.setattr(resolve.manager, "LoadProject", record_load)
    command = _command("reopen", session, planSha256="c" * 64)
    if message is None:
        result = bridge.handle_command(command, resolve)
        assert result["verified"] is True
        assert load_calls == 1
    else:
        with pytest.raises(ValueError, match=message):
            bridge.handle_command(command, resolve)
        assert load_calls == 0


def test_reopen_refuses_empty_project_identity_change_between_observations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    state.spawn_empty_project_on_close = True
    get_current_project = resolve.manager.GetCurrentProject
    load_project = resolve.manager.LoadProject
    load_calls = 0
    observed_uids: list[str] = []

    def change_uid_on_second_empty_observation() -> Project | None:
        project = get_current_project()
        if project is not None and project.GetName() == bridge.EMPTY_PROJECT_NAME:
            if len(observed_uids) == 1:
                project.uid = "changed-empty-project"
            observed_uids.append(project.uid)
        return project

    def count_load(name: str) -> Project | None:
        nonlocal load_calls
        load_calls += 1
        return load_project(name)

    monkeypatch.setattr(
        resolve.manager, "GetCurrentProject", change_uid_on_second_empty_observation
    )
    monkeypatch.setattr(resolve.manager, "LoadProject", count_load)
    with pytest.raises(
        ValueError, match="identity or settings changed between observations"
    ):
        bridge.handle_command(_command("reopen", session, planSha256="d" * 64), resolve)
    assert observed_uids[:2] == ["untitled-project", "changed-empty-project"]
    assert load_calls == 0


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


def test_save_failure_leaves_started_only_unknown_attempt(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    session = setup["session"]
    plan = "8" * 64
    state.save_project_ok = False
    request = _command(
        "apply",
        session,
        planSha256=plan,
        change=dict(bridge.CHANGES[0]),
        currentTargetFingerprint=setup["observation"]["fingerprint"],
    )
    with pytest.raises(ValueError, match="SaveProject failed"):
        bridge.handle_command(request, resolve)
    started = Path(session["operationDir"]) / f"{plan}-append-blue.started.json"
    finished = Path(session["operationDir"]) / f"{plan}-append-blue.finished.json"
    assert started.is_file()
    assert not finished.exists()
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
        bridge.handle_command(request, resolve)


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

    prior_state = State(paths)
    prior_resolve = Resolve(prior_state)
    prior_project = Project(prior_state, "already-open", "prior-project")
    prior_resolve.manager.current = prior_project
    prior_resolve.manager.names.append("already-open")
    with pytest.raises(ValueError, match="not the exact empty Untitled Project"):
        bridge.handle_command(request, prior_resolve)
    assert prior_resolve.manager.GetCurrentProject() is prior_project
    assert prior_resolve.manager.names == ["already-open"]
    assert prior_state.saved_project is None

    audio_state = State(paths)
    audio_state.audio_on_empty = True
    with pytest.raises(ValueError, match="one exact 24-frame red video occurrence"):
        bridge.handle_command(request, Resolve(audio_state))


@pytest.mark.parametrize(
    ("profile", "message"),
    [
        ("disabled-clip", "disabled clip"),
        ("disabled-track", "video track 1 is disabled"),
        ("subtitle-track", "subtitle tracks are unsupported"),
        ("extra-video-track", "exactly one video track"),
        ("extra-audio-track", "unsupported audio track count"),
        ("audio-clip", "target contains unexpected geometry"),
    ],
)
def test_observe_refuses_outside_the_cut_only_track_profile(
    tmp_path: Path, profile: str, message: str
) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    target = _current_project(resolve).timelines[1]
    if profile == "disabled-clip":
        target.video[0].enabled = False
    elif profile == "disabled-track":
        target.enabled_tracks[("video", 1)] = False
    elif profile == "subtitle-track":
        target.subtitle_track_count = 1
    elif profile == "extra-video-track":
        target.video_track_count = 2
    elif profile == "extra-audio-track":
        target.audio_track_count = 2
    else:
        target.audio.append(Item(state.next_item_uid(), state.media[0], 24, 24))
    with pytest.raises(ValueError, match=message):
        bridge.handle_command(_command("observe", setup["session"]), resolve)


def test_empty_audio_track_profile_allows_zero_tracks(tmp_path: Path) -> None:
    resolve, setup, _hashes, _state = _case(tmp_path)
    for timeline in _current_project(resolve).timelines:
        timeline.audio_track_count = 0
    assert (
        bridge.handle_command(_command("observe", setup["session"]), resolve)[
            "observation"
        ]
        == setup["observation"]
    )


def test_reopen_rejects_changed_timeline_identity(tmp_path: Path) -> None:
    resolve, setup, _hashes, state = _case(tmp_path)
    state.change_ids_on_load = True
    with pytest.raises(ValueError, match="reopened timeline identities changed"):
        bridge.handle_command(
            _command("reopen", setup["session"], planSha256="e" * 64), resolve
        )


def test_project_settings_accepts_native_numeric_fps_without_relaxing_rate() -> None:
    class NativeSettings:
        def __init__(self, fps: float) -> None:
            self.fps = fps

        def GetSetting(self, key: str) -> Any:
            return self.fps if key == "timelineFrameRate" else bridge.SETTINGS[key]

    bridge._project_settings(NativeSettings(24.0))
    with pytest.raises(ValueError):
        bridge._project_settings(NativeSettings(23.976))
