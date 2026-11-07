"""Offline exact-UID provisioning tests; no real Resolve or media access."""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path

import pytest
import vera_timeline_agent.resolve_test_queue as queue
import vera_timeline_agent.resolve_test_queue_m4_provision as provision


class Timeline:
    def __init__(self, name: str, *, wrong_rate: bool = False) -> None:
        self.name = name
        self.uid = f"timeline-{name}"
        self.wrong_rate = wrong_rate
        self.items: list[str] = []

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def GetSetting(self, key: str) -> str:
        assert key == "timelineFrameRate"
        return "24" if self.wrong_rate else "23.976"

    def GetTrackCount(self, kind: str) -> int:
        return 1 if kind == "video" else 0

    def GetItemListInTrack(self, kind: str, index: int) -> list[str]:
        assert kind == "video" and index == 1
        return self.items


class Project:
    def __init__(self, name: str, *, broken: str = "") -> None:
        self.name = name
        self.uid = f"project-{name}"
        self.broken = broken
        self.rate = "24"
        self.timeline: Timeline | None = None

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def SetSetting(self, key: str, value: str) -> bool:
        assert key == "timelineFrameRate" and value == "23.976"
        if self.broken == "rate_set":
            return False
        self.rate = value
        return True

    def GetSetting(self, key: str) -> str:
        assert key == "timelineFrameRate"
        return self.rate

    def GetMediaPool(self) -> Project:
        return self

    def CreateEmptyTimeline(self, name: str) -> Timeline | None:
        if self.broken == "timeline":
            return None
        self.timeline = Timeline(name, wrong_rate=self.broken == "rate_readback")
        if self.broken == "not_empty":
            self.timeline.items.append("existing item")
        return self.timeline

    def SetCurrentTimeline(self, timeline: Timeline) -> bool:
        return self.broken != "select"

    def GetCurrentTimeline(self) -> Timeline | None:
        return self.timeline

    def IsRenderingInProgress(self) -> bool:
        return False

    def GetRenderJobList(self) -> list[dict[str, str]]:
        return []

    def GetRenderJobStatus(self, job_id: str) -> dict[str, str]:
        return {"JobStatus": "Complete"}


class Manager:
    def __init__(self) -> None:
        self.projects: dict[str, Project] = {}
        self.existing = Project("Producer project")
        self.current = self.existing
        self.created: list[str] = []
        self.saved: list[str] = []
        self.broken = ""

    def GetProjectListInCurrentFolder(self) -> list[str]:
        return list(self.projects)

    def GetCurrentProject(self) -> Project:
        return self.current

    def CreateProject(self, name: str) -> Project | None:
        assert name not in self.projects
        self.created.append(name)
        if self.broken == "create":
            return None
        project = Project(name, broken=self.broken)
        self.projects[name] = project
        self.current = project
        return project

    def SaveProject(self) -> bool:
        if self.broken == "save":
            return False
        self.saved.append(self.current.GetName())
        return True

    def LoadProject(self, name: str) -> Project | None:
        self.current = self.projects[name]
        return self.current


@pytest.fixture
def host(monkeypatch: pytest.MonkeyPatch) -> tuple[Manager, list[str]]:
    manager = Manager()
    calls: list[str] = []
    monkeypatch.setattr(
        provision,
        "_local_resolve_connection",
        lambda: type("Resolve", (), {"GetProjectManager": lambda self: manager})(),
    )
    def fake_owner(*, output_lane: bool) -> nullcontext[None]:
        assert output_lane is True
        calls.append("native-owner")
        return nullcontext()

    monkeypatch.setattr(provision, "native_owner", fake_owner)

    def preflight(name: str) -> None:
        calls.append(f"preflight:{name}")
        if name in manager.projects:
            raise provision.ProvisionError("project name collision")

    monkeypatch.setattr(provision, "preflight_independent_disposable", preflight)
    return manager, calls


def test_two_unique_projects_without_manual_steps(
    tmp_path: Path, host: tuple[Manager, list[str]]
) -> None:
    manager, calls = host
    root = tmp_path / "new-job"
    plan = provision.reserve(root)
    assert set(plan["targets"]) == {"initial", "fresh"}
    assert len(set(plan["targets"].values())) == 2
    assert manager.created == []
    assert provision.advance(root) == {
        "state": "stage_verified",
        "stage": "initial",
        "created": True,
    }
    assert provision.advance(root) == {
        "state": "stage_verified",
        "stage": "fresh",
        "created": True,
    }
    assert provision.advance(root) == {"state": "targets_provisioned", "created": False}
    targets = provision.completed(root)
    assert set(targets) == {"initial", "fresh"}
    assert (
        len(
            {
                v
                for row in targets.values()
                for v in (row["projectUid"], row["timelineUid"])
            }
        )
        == 4
    )
    assert (
        manager.created
        == manager.saved
        == [plan["targets"]["initial"], plan["targets"]["fresh"]]
    )
    assert manager.existing.GetName() == "Producer project"
    assert calls.count("native-owner") == 2
    for stage in ("initial", "fresh"):
        assert targets[stage]["projectName"] == targets[stage]["timelineName"]
        assert manager.projects[targets[stage]["projectName"]].rate == "23.976"
        assert (root / f"intent-{stage}.json").exists()
        assert (root / f"complete-{stage}.json").stat().st_mode & 0o077 == 0


def test_single_command_provisions_and_selects_initial(
    tmp_path: Path, host: tuple[Manager, list[str]]
) -> None:
    manager, _ = host
    root = tmp_path / "one-command"
    assert provision.provision(root) == {
        "state": "targets_provisioned",
        "created": False,
    }
    initial = provision.completed(root)["initial"]
    assert (
        manager.current.GetName() == provision.completed(root)["fresh"]["projectName"]
    )
    assert provision.select(root, "initial") == {
        "state": "selected_verified",
        "stage": "initial",
    }
    assert manager.current.GetUniqueId() == initial["projectUid"]
    # Rerunning a successful session is read-only; no more native projects.
    before = list(manager.created)
    assert provision.provision(root)["created"] is False
    assert manager.created == before


def test_selection_never_switches_from_producer_project(
    tmp_path: Path, host: tuple[Manager, list[str]]
) -> None:
    manager, _ = host
    root = tmp_path / "job"
    provision.provision(root)
    manager.current = manager.existing
    with pytest.raises(provision.ProvisionError, match="not an idle provisioned"):
        provision.select(root, "initial")
    assert manager.current is manager.existing


def test_operator_changes_selected_project_before_save_refuses(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _ = host
    root = tmp_path / "job"
    provision.reserve(root)
    original = Project.SetCurrentTimeline

    def change_selection(self: Project, timeline: Timeline) -> bool:
        answer = original(self, timeline)
        manager.current = manager.existing
        return answer

    monkeypatch.setattr(Project, "SetCurrentTimeline", change_selection)
    with pytest.raises(provision.ProvisionError, match="current selection changed"):
        provision.advance(root)
    assert manager.saved == []
    with pytest.raises(provision.ProvisionError, match="UNKNOWN"):
        provision.advance(root)


def test_auto_selection_refuses_unresolved_current_host_operation(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import vera_timeline_agent.resolve_native_owner as owner

    manager, _ = host
    root = tmp_path / "job"
    provision.provision(root)
    current_uid = manager.current.GetUniqueId()
    timeline = manager.current.GetCurrentTimeline()
    assert timeline is not None
    chain = {
        "projectUid": current_uid,
        "timelineUid": timeline.GetUniqueId(),
        "caseId": "synthetic-test",
        "phase": "edited",
    }
    key = "one-use-active"
    path = owner.OUTPUT_ATTEMPTS_ROOT / key / "chain.json"
    path.parent.mkdir(parents=True)
    path.write_bytes(queue.canonical(chain))
    path.chmod(0o600)
    monkeypatch.setattr(owner, "_active_output_host_chains", lambda _: {key: "unknown"})
    with pytest.raises(provision.ProvisionError, match="unresolved output work"):
        provision.select(root, "initial")
    assert manager.current.GetUniqueId() == current_uid


def test_auto_selection_refuses_active_render_queue(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _ = host
    root = tmp_path / "job"
    provision.provision(root)
    current_uid = manager.current.GetUniqueId()
    monkeypatch.setattr(
        Project,
        "GetRenderJobList",
        lambda self: [{"JobId": "pending"}],
    )
    monkeypatch.setattr(
        Project,
        "GetRenderJobStatus",
        lambda self, job_id: {"JobStatus": "Rendering"},
    )
    with pytest.raises(provision.ProvisionError, match="unresolved render"):
        provision.select(root, "initial")
    assert manager.current.GetUniqueId() == current_uid


@pytest.mark.parametrize(
    "broken",
    ["create", "rate_set", "timeline", "select", "rate_readback", "not_empty", "save"],
)
def test_partial_effect_is_unknown_and_never_replayed(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
    broken: str,
) -> None:
    manager, _calls = host
    root = tmp_path / "new-job"
    provision.reserve(root)
    manager.broken = broken
    with pytest.raises(provision.ProvisionError):
        provision.advance(root)
    assert (root / "intent-initial.json").exists()
    assert not (root / "complete-initial.json").exists()
    created = list(manager.created)
    with pytest.raises(provision.ProvisionError, match="UNKNOWN"):
        provision.advance(root)
    assert manager.created == created


def test_preflight_refusal_does_not_consume_intent(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manager, _ = host
    root = tmp_path / "new-job"
    provision.reserve(root)

    def refuse(_: str) -> None:
        raise provision.ProvisionError("active native owner")

    monkeypatch.setattr(provision, "preflight_independent_disposable", refuse)
    with pytest.raises(provision.ProvisionError, match="active native owner"):
        provision.advance(root)
    assert manager.created == []
    assert not (root / "intent-initial.json").exists()


def test_second_stage_refusal_never_replays_first(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
) -> None:
    manager, _ = host
    root = tmp_path / "new-job"
    provision.reserve(root)
    provision.advance(root)
    manager.broken = "create"
    with pytest.raises(provision.ProvisionError):
        provision.advance(root)
    assert (root / "complete-initial.json").exists()
    assert (root / "intent-fresh.json").exists()
    before = list(manager.created)
    with pytest.raises(provision.ProvisionError, match="UNKNOWN"):
        provision.advance(root)
    assert manager.created == before


def test_duplicate_or_symlinked_root_refused(tmp_path: Path) -> None:
    root = tmp_path / "new-job"
    provision.reserve(root)
    with pytest.raises(FileExistsError):
        provision.reserve(root)
    shortcut = tmp_path / "shortcut"
    shortcut.symlink_to(root)
    with pytest.raises(provision.ProvisionError, match="symlink"):
        provision.advance(shortcut)


def test_tampered_plan_and_proof_cannot_be_reinterpreted(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
) -> None:
    root = tmp_path / "new-job"
    provision.reserve(root)
    plan = json.loads((root / "plan.json").read_bytes())
    plan["targets"]["initial"] = "Producer project"
    (root / "plan.json").write_bytes(queue.canonical(plan))
    with pytest.raises(provision.ProvisionError, match="disposable"):
        provision.advance(root)


def test_no_completion_without_real_project_and_timeline_uids(
    tmp_path: Path,
    host: tuple[Manager, list[str]],
) -> None:
    root = tmp_path / "new-job"
    provision.reserve(root)
    provision.advance(root)
    row = provision._read(root / "complete-initial.json")
    row["timelineUid"] = row["projectUid"]
    (root / "complete-initial.json").write_bytes(queue.canonical(row))
    with pytest.raises(provision.ProvisionError, match="UID"):
        provision.advance(root)
