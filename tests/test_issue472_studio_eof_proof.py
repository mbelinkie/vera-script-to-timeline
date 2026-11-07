"""Offline fake-SDK rehearsal of the one-use #472 physical proof runner."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import uuid
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest


def _load() -> Any:
    path = Path(__file__).resolve().parents[1] / "scripts/issue-472-studio-eof-proof.py"
    spec = importlib.util.spec_from_file_location("issue472_studio_proof", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Clip:
    def __init__(self, media: Any, source_end: int) -> None:
        self.media = media
        self.source_end = source_end

    def GetMediaPoolItem(self) -> Any:
        return self.media

    def GetUniqueId(self) -> str:
        return "new-disposable-item-uid"

    def GetStart(self, frames: bool) -> int:
        assert frames is False
        return 715

    def GetDuration(self, frames: bool) -> int:
        assert frames is False
        return 214

    def GetEnd(self, frames: bool) -> int:
        assert frames is False
        return 929

    def GetSourceStartFrame(self) -> int:
        return 0

    def GetSourceEndFrame(self) -> int:
        return self.source_end

    def GetSourceStartTime(self) -> float:
        return 0.0

    def GetSourceEndTime(self) -> float:
        return 214 * 1001 / 24000

    def GetSpeed(self) -> dict[str, float]:
        return {"Percentage": 100.0}


class Media:
    def __init__(self, path: Path) -> None:
        self.path = path

    def GetClipProperty(self) -> dict[str, Any]:
        return {"Frames": "214", "FPS": 23.976, "File Path": str(self.path)}


class Timeline:
    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[Clip] = []

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return "new-disposable-timeline-uid"

    def GetTrackCount(self, kind: str) -> int:
        return 1 if kind == "video" else 0

    def GetItemListInTrack(self, kind: str, index: int) -> list[Clip]:
        assert kind == "video" and index == 1
        return list(self.items)


class Pool:
    def __init__(self, project: Any, path: Path, source_end: int) -> None:
        self.project = project
        self.media = Media(path)
        self.source_end = source_end

    def CreateEmptyTimeline(self, name: str) -> Timeline:
        assert self.project.timeline is None
        self.project.timeline = Timeline(name)
        return self.project.timeline

    def ImportMedia(self, paths: list[str]) -> list[Media]:
        assert paths == [str(self.media.path)]
        return [self.media]

    def AppendToTimeline(self, rows: list[dict[str, Any]]) -> list[Clip]:
        row = rows[0]
        assert row["mediaPoolItem"] is self.media
        assert row["startFrame"] == 0
        assert row["endFrame"] == 214
        assert row["recordFrame"] == 715
        assert row["trackIndex"] == 1
        clip = Clip(self.media, self.source_end)
        self.project.timeline.items.append(clip)
        return [clip]


class Project:
    def __init__(self, name: str, path: Path, source_end: int) -> None:
        self.name = name
        self.timeline: Timeline | None = None
        self.pool = Pool(self, path, source_end)

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return "new-disposable-project-uid"

    def SetSetting(self, setting: str, value: str) -> bool:
        assert (setting, value) == ("timelineFrameRate", "23.976")
        return True

    def GetSetting(self, name: str) -> str:
        return "23.976"

    def GetMediaPool(self) -> Pool:
        return self.pool

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        return timeline is self.timeline

    def GetCurrentTimeline(self) -> Timeline | None:
        return self.timeline

    def IsRenderingInProgress(self) -> bool:
        return False

    def GetRenderJobList(self) -> list[Any]:
        return []


class Manager:
    def __init__(self, path: Path, source_end: int) -> None:
        self.path = path
        self.source_end = source_end
        self.current: Project | None = None
        self.created = 0
        self.saved = 0

    def GetCurrentProject(self) -> Project | None:
        return self.current

    def CreateProject(self, name: str) -> Project:
        self.created += 1
        self.current = Project(name, self.path, self.source_end)
        return self.current

    def SaveProject(self) -> bool:
        assert self.current is not None
        assert self.current.name.startswith("VERA Delivery ")
        self.saved += 1
        return True

    def CloseProject(self, project: Project) -> bool:
        assert self.current is project
        self.current = None
        return True

    def LoadProject(self, name: str) -> Project:
        assert self.current is None
        assert name
        # The recorded project is returned, preserving native clip identities.
        self.current = self.saved_project
        assert self.current.GetName() == name
        return self.current

    @property
    def saved_project(self) -> Project:
        return self._saved_project

    @saved_project.setter
    def saved_project(self, value: Project) -> None:
        self._saved_project = value


def test_472_physical_runner_mocked_success_and_no_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    proof = _load()
    source = tmp_path / "delivered.mp4"
    source.write_bytes(b"new-authenticated-214-frame-test-clip")
    monkeypatch.setattr(proof, "SOURCE", source)
    monkeypatch.setattr(
        proof, "EXPECTED_HASH", hashlib.sha256(source.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(proof, "PROOF_ROOT", tmp_path / "private-proofs")
    monkeypatch.setattr(proof, "native_owner", lambda *, output_lane: nullcontext())
    monkeypatch.setattr(proof, "preflight_independent_disposable", lambda name: None)
    mgr = Manager(source, 212)
    real_create = mgr.CreateProject

    def create(name: str) -> Project:
        project = real_create(name)
        mgr.saved_project = project
        return project

    mgr.CreateProject = create  # type: ignore[method-assign]

    class Resolve:
        def GetProductName(self) -> str:
            return "DaVinci Resolve Studio"

        def GetVersionString(self) -> str:
            return "21.1.1.10"

        def GetProjectManager(self) -> Manager:
            return mgr

    monkeypatch.setattr(proof, "_local_resolve_connection", lambda: Resolve())
    token = str(uuid.uuid4())
    assert proof.run(token) == 0
    report = json.loads(
        (tmp_path / "private-proofs" / token / "report.json").read_text()
    )
    assert report["verifiedFull214FrameEofUndercount"] is True
    assert report["beforeSave"] == report["afterReopen"]
    assert (mgr.created, mgr.saved) == (1, 1)
    with pytest.raises(FileExistsError):
        proof.run(token)
    assert mgr.created == 1


@pytest.mark.parametrize("source_end", [211, 213, 214])
def test_472_physical_runner_refuses_other_readbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source_end: int
) -> None:
    proof = _load()
    source = tmp_path / "delivered.mp4"
    source.write_bytes(b"new-test-clip")
    monkeypatch.setattr(proof, "SOURCE", source)
    monkeypatch.setattr(
        proof, "EXPECTED_HASH", hashlib.sha256(source.read_bytes()).hexdigest()
    )
    monkeypatch.setattr(proof, "PROOF_ROOT", tmp_path / "private-proofs")
    monkeypatch.setattr(proof, "native_owner", lambda *, output_lane: nullcontext())
    monkeypatch.setattr(proof, "preflight_independent_disposable", lambda name: None)
    mgr = Manager(source, source_end)
    original = mgr.CreateProject

    def create(name: str) -> Project:
        project = original(name)
        mgr.saved_project = project
        return project

    mgr.CreateProject = create  # type: ignore[method-assign]

    class Resolve:
        def GetProductName(self) -> str:
            return "DaVinci Resolve Studio"

        def GetVersionString(self) -> str:
            return "21.1.1.10"

        def GetProjectManager(self) -> Manager:
            return mgr

    monkeypatch.setattr(proof, "_local_resolve_connection", lambda: Resolve())
    token = str(uuid.uuid4())
    assert proof.run(token) == 3
    report = json.loads(
        (tmp_path / "private-proofs" / token / "report.json").read_text()
    )
    assert report["verifiedFull214FrameEofUndercount"] is False
