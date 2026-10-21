"""Controller/native byte seams for the bounded #209 review corrections."""

from __future__ import annotations

import hashlib
import os
import pwd
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_records_v2 as records
from vera_timeline_agent import workflow_v2_cli
from vera_timeline_agent.qualification_output_controller_v2 import (
    HostClockRegression,
    OutputAttemptJournal,
    QualificationOutputController,
    _hash,
)
from vera_timeline_agent.qualification_output_records_v2 import _canonical, _parse


def _context() -> dict[str, Any]:
    values: dict[str, str] = {}
    for name in records.CONTEXT_HASH_FIELDS:
        values[name] = hashlib.sha256(name.encode()).hexdigest()
    values.update(
        {
            "originalDocumentSha256": _hash(b"original-document"),
            "originalDependenciesSha256": _hash(b"original-dependencies"),
            "executionDocumentSha256": _hash(b"execution-document"),
            "executionDependenciesSha256": _hash(b"execution-dependencies"),
            "nativeSourceGraphSha256": _hash(b"native-source-graph"),
            "installedReleaseSha256": _hash(b"installed-release"),
        }
    )
    value: dict[str, Any] = {
        **values,
        "lane": records.LANE,
        "invocationId": "invocation-one",
        "caseId": "case-one",
        "phase": "pristine",
        "target": {
            "projectUid": "project-one",
            "timelineUid": "timeline-one",
            "projectName": "disposable-project",
            "timelineName": "disposable-timeline",
        },
        "binding": {"kind": "baseline"},
    }
    projection = {
        key: child
        for key, child in value.items()
        if key not in records.AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    value["binding"]["bindingSha256"] = hashlib.sha256(
        _canonical(projection)
    ).hexdigest()
    return value


class _Admission:
    profile = native.SYNTHETIC_PROFILE

    def __init__(self, root: Path, context: dict[str, Any]) -> None:
        self.package_root = root
        self.admission_path = (
            root.parent / "qualification-output-package-admission.json"
        )
        self.admission_path.write_bytes(b"admission")
        self.admission_path.chmod(0o400)
        timeline = {
            "frameRate": {"numerator": 24000, "denominator": 1001},
            "startFrame": 0,
            "durationFrames": 10,
            "width": 1920,
            "height": 1080,
        }
        (root / "Compiler").mkdir(parents=True)
        (root / "Compiler/timeline-manifest-v2.json").write_bytes(
            _canonical({"timeline": timeline})
        )
        self.original_document_path = root / "Original/script-document-v2.json"
        self.original_dependencies_path = (
            root / "Original/compiler-dependencies-v2.json"
        )
        self.execution_document_path = root / "Execution/script-document-v2.json"
        self.execution_dependencies_path = (
            root / "Execution/compiler-dependencies-v2.json"
        )
        for path, raw in (
            (self.original_document_path, b"original-document"),
            (self.original_dependencies_path, b"original-dependencies"),
            (self.execution_document_path, b"execution-document"),
            (self.execution_dependencies_path, b"execution-dependencies"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
            path.chmod(0o400)

    def native_package_ref(self) -> dict[str, Any]:
        return {
            "profile": self.profile,
            "packageRoot": str(self.package_root),
            "attestationPath": str(self.package_root.parent / "attestation.json"),
            "attestationSha256": "b" * 64,
            "admissionPath": str(self.admission_path),
            "admissionSha256": _hash(self.admission_path.read_bytes()),
        }


class _Journal:
    def __init__(self, root: Path, context: dict[str, Any]) -> None:
        self.directory = root
        self.artifacts = root / "artifacts"
        self.artifacts.mkdir(parents=True)
        self.chain = {
            "projectUid": context["target"]["projectUid"],
            "timelineUid": context["target"]["timelineUid"],
            "caseId": context["caseId"],
            "phase": context["phase"],
        }

    def _retain(self, raw: bytes) -> str:
        digest: str = _hash(raw)
        path = self.artifacts / digest
        if not path.exists():
            path.write_bytes(raw)
            path.chmod(0o400)
        return digest


class _Trust:
    def checked_now(self) -> datetime:
        return datetime.now(UTC)


class _EmptyPoolItem:
    def GetUniqueId(self) -> str:
        return "timeline-pool-item"


class _EmptyRoot:
    def __init__(self, timeline_item: _EmptyPoolItem) -> None:
        self.timeline_item = timeline_item

    def GetUniqueId(self) -> str:
        return "empty-root"

    def GetClipList(self) -> list[Any]:
        return [self.timeline_item]

    def GetSubFolderList(self) -> list[Any]:
        return []


class _EmptyMediaPool:
    def __init__(self, timeline_item: _EmptyPoolItem) -> None:
        self.root = _EmptyRoot(timeline_item)

    def ImportMedia(self, _paths: list[str]) -> list[Any]:
        return []

    def GetRootFolder(self) -> _EmptyRoot:
        return self.root


class _EmptyTimeline:
    def __init__(self, pool_item: _EmptyPoolItem) -> None:
        self.pool_item = pool_item

    def GetUniqueId(self) -> str:
        return "timeline-one"

    def GetName(self) -> str:
        return "disposable-timeline"

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 10

    def GetTrackCount(self, _kind: str) -> int:
        return 0

    def GetTrackName(self, _kind: str, _index: int) -> str:
        return ""

    def GetItemListInTrack(self, _kind: str, _index: int) -> list[Any]:
        return []

    def GetIsTrackEnabled(self, _kind: str, _index: int) -> bool:
        return True

    def GetIsTrackLocked(self, _kind: str, _index: int) -> bool:
        return False

    def GetMarkers(self) -> dict[int, Any]:
        return {}

    def GetMediaPoolItem(self) -> _EmptyPoolItem:
        return self.pool_item

    def GetMarkerCustomData(self, _frame: int) -> str:
        return ""

    def GetSetting(self, name: str) -> str:
        return {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }[name]

    def SetStartTimecode(self, _value: str) -> bool:
        return True

    def AddTrack(self, *_args: Any) -> bool:
        return True

    def SetTrackName(self, *_args: Any) -> bool:
        return True

    def AddMarker(self, *_args: Any) -> bool:
        return True


class _EmptyProject:
    def __init__(self) -> None:
        timeline_item = _EmptyPoolItem()
        self.timeline = _EmptyTimeline(timeline_item)
        self.pool = _EmptyMediaPool(timeline_item)
        self.settings = {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }

    def GetUniqueId(self) -> str:
        return "project-one"

    def GetName(self) -> str:
        return "disposable-project"

    def GetCurrentTimeline(self) -> _EmptyTimeline:
        return self.timeline

    def GetMediaPool(self) -> _EmptyMediaPool:
        return self.pool

    def GetSetting(self, name: str) -> str:
        return self.settings[name]

    def SetSetting(self, name: str, value: str) -> bool:
        self.settings[name] = value
        return True


class _EmptyProjectManager:
    def __init__(self) -> None:
        self.project = _EmptyProject()

    def GetCurrentProject(self) -> _EmptyProject:
        return self.project

    def SaveProject(self) -> bool:
        return True

    def CloseProject(self, _project: _EmptyProject) -> bool:
        return True

    def LoadProject(self, _name: str) -> _EmptyProject:
        return self.project


class _EmptyResolve:
    def __init__(self) -> None:
        self.manager = _EmptyProjectManager()

    def GetProductName(self) -> str:
        return "DaVinci Resolve Studio"

    def GetVersion(self) -> list[Any]:
        return [21, 1, 1, 10, ""]

    def GetProjectManager(self) -> _EmptyProjectManager:
        return self.manager


def _empty_admitted(tmp_path: Path) -> dict[str, Any]:
    timeline = {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "startFrame": 0,
        "durationFrames": 10,
        "width": 1920,
        "height": 1080,
        "audioSampleRate": 48000,
    }
    return {
        "sourceRoot": tmp_path,
        "admission": {"packageInventorySha256": "0" * 64},
        "manifest": {"timeline": timeline},
        "view": {
            "timeline": timeline,
            "tracks": [],
            "sources": [],
            "events": [],
            "markers": [],
        },
    }


def _runtime_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    Any,
    Path,
    Path,
    dict[str, Any],
    _EmptyResolve,
    Path,
]:
    """Build a real host journal and static native slot around an empty target."""
    context = _context()
    native_root = tmp_path / "native-state"
    host_root = tmp_path / "host-state"
    installed_root = tmp_path / "installed-release"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", native_root)
    monkeypatch.setattr(native, "HOST_STATE_ROOT", host_root)
    monkeypatch.setattr(native, "NATIVE_RELEASE_ROOT", installed_root)
    package_root = tmp_path / "package"
    package_root.mkdir()
    admission = _Admission(package_root, context)
    release_root = tmp_path / "release"
    manifest = release_root / "vera-delivery-v2/release.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"reviewed-release-manifest")
    manifest.chmod(0o400)
    release_bytes = b"installed-release"
    context["installedReleaseSha256"] = _hash(release_bytes)
    journal = OutputAttemptJournal(host_root, context)
    journal._retain(b"native-source-graph")
    journal._retain(release_bytes)
    controller: Any = object.__new__(QualificationOutputController)
    controller.revised_preflight = None
    controller.context = context
    controller.admission = admission
    controller.release_root = release_root
    controller.journal = journal
    controller.trust = _Trust()
    monkeypatch.setattr(controller, "_environment_current", lambda: None)
    monkeypatch.setattr(
        workflow_v2_cli, "_verify_output_release", lambda _root: manifest
    )
    monkeypatch.setattr(
        native, "_verify_installed_release", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(
        native, "_admission_profile", lambda _request: _empty_admitted(tmp_path)
    )

    now = datetime.now(UTC)

    def stamp(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    target_key = {
        "projectUid": context["target"]["projectUid"],
        "timelineUid": context["target"]["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    output_path = (
        native_root / "renders" / _hash(_canonical(target_key)) / "approved.mov"
    )
    approval: dict[str, Any] = {
        "schemaVersion": native.APPROVAL_SCHEMA,
        "lane": records.LANE,
        "approvalId": "approval-one",
        "operator": pwd.getpwuid(os.getuid()).pw_name,
        "issuedAt": stamp(now - timedelta(seconds=1)),
        "expiresAt": stamp(now + timedelta(minutes=5)),
        "invocationId": context["invocationId"],
        "context": context,
        "target": context["target"],
        "profile": native.SYNTHETIC_PROFILE,
        "releaseManifestSha256": _hash(manifest.read_bytes()),
        "installedReleaseSha256": context["installedReleaseSha256"],
        "packageRoot": str(package_root),
        "packageSha256": context["packageSha256"],
        "admissionSha256": _hash(admission.admission_path.read_bytes()),
        "sourceGraphSha256": context["nativeSourceGraphSha256"],
        "outputPath": str(output_path),
        "settings": native._settings_for_timeline(
            {
                "frameRate": {"numerator": 24000, "denominator": 1001},
                "startFrame": 0,
                "durationFrames": 10,
                "width": 1920,
                "height": 1080,
            }
        ),
        "actionPlan": list(native.APPROVAL_ACTION_PLAN),
        "maxPolls": native.MAX_POLL_COUNT,
        "confirmations": dict(native.CONFIRMATIONS),
        "oneUse": True,
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(_canonical(approval))
    approval_path.chmod(0o400)
    return controller, approval_path, installed_root, context, _EmptyResolve(), manifest


def test_controller_bytes_pass_actual_request_and_authority_validators(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = _context()
    native_root = tmp_path / "native-state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", native_root)
    package_root = tmp_path / "package"
    package_root.mkdir()
    admission = _Admission(package_root, context)
    release_root = tmp_path / "release"
    manifest = release_root / "vera-delivery-v2/release.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_bytes(b"reviewed-release-manifest")
    manifest.chmod(0o400)
    release_bytes = b"installed-release"
    context["installedReleaseSha256"] = _hash(release_bytes)
    journal = _Journal(tmp_path / "journal", context)
    journal._retain(b"native-source-graph")
    journal._retain(release_bytes)
    controller: Any = object.__new__(QualificationOutputController)
    controller.revised_preflight = None
    controller.context = context
    controller.admission = admission
    controller.release_root = release_root
    controller.journal = journal
    controller.trust = _Trust()
    monkeypatch.setattr(controller, "_environment_current", lambda: None)
    monkeypatch.setattr(
        workflow_v2_cli, "_verify_output_release", lambda _root: manifest
    )

    now = datetime.now(UTC)

    def stamp(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    target_key = {
        "projectUid": context["target"]["projectUid"],
        "timelineUid": context["target"]["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    output_path = (
        native_root / "renders" / _hash(_canonical(target_key)) / "approved.mov"
    )
    approval: dict[str, Any] = {
        "schemaVersion": native.APPROVAL_SCHEMA,
        "lane": records.LANE,
        "approvalId": "approval-one",
        "operator": pwd.getpwuid(os.getuid()).pw_name,
        "issuedAt": stamp(now - timedelta(seconds=1)),
        "expiresAt": stamp(now + timedelta(minutes=5)),
        "invocationId": context["invocationId"],
        "context": context,
        "target": context["target"],
        "profile": native.SYNTHETIC_PROFILE,
        "releaseManifestSha256": _hash(manifest.read_bytes()),
        "installedReleaseSha256": context["installedReleaseSha256"],
        "packageRoot": str(package_root),
        "packageSha256": context["packageSha256"],
        "admissionSha256": _hash(admission.admission_path.read_bytes()),
        "sourceGraphSha256": context["nativeSourceGraphSha256"],
        "outputPath": str(output_path),
        "settings": native._settings_for_timeline(
            {
                "frameRate": {"numerator": 24000, "denominator": 1001},
                "startFrame": 0,
                "durationFrames": 10,
                "width": 1920,
                "height": 1080,
            }
        ),
        "actionPlan": list(native.APPROVAL_ACTION_PLAN),
        "maxPolls": native.MAX_POLL_COUNT,
        "confirmations": dict(native.CONFIRMATIONS),
        "oneUse": True,
    }
    approval_path = tmp_path / "approval.json"
    approval_path.write_bytes(_canonical(approval))
    approval_path.chmod(0o400)

    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=approval_path
    )
    request_raw = request_path.read_bytes()
    request = native.verify_native_request(
        request_raw, expected_request_sha256=_hash(request_raw), current=True
    )
    authority, _, checked_approval = native._verify_authority(request, current=True)
    assert checked_approval["approvalId"] == "approval-one"
    assert authority["issuedAt"] == approval["issuedAt"]


def test_clock_refusal_leaves_no_native_slot_and_can_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        controller,
        approval_path,
        _installed_root,
        context,
        _resolve,
        _manifest,
    ) = _runtime_fixture(tmp_path, monkeypatch)
    result_path, authority_path, intent_path, request_path = (
        native.native_request_paths(context, 0)
    )
    operation_root = request_path.parent
    operations_root = operation_root.parent
    calls = 0

    def fail_first_clock_sample() -> datetime:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HostClockRegression({"classification": "wall_lag", "lagSeconds": 0.1})
        return datetime.now(UTC)

    monkeypatch.setattr(controller.trust, "checked_now", fail_first_clock_sample)
    with pytest.raises(HostClockRegression, match="host clock rollback/uncertainty"):
        controller.prepare_native_request("construct", {}, approval_path=approval_path)

    assert not operation_root.exists()
    assert not any(
        path.exists()
        for path in (result_path, authority_path, intent_path, request_path)
    )

    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=approval_path
    )
    request_raw = request_path.read_bytes()
    request = native.verify_native_request(
        request_raw, expected_request_sha256=_hash(request_raw), current=True
    )
    assert request["action"] == "construct"
    assert calls == 2
    assert [path.name for path in operations_root.iterdir()] == ["00000000"]
    assert {path.name for path in operation_root.iterdir()} == {
        "authority.json",
        "intent.json",
        "request.json",
    }
    assert not result_path.exists()
    assert not (operation_root / "native-start.json").exists()
    assert not (operation_root / "effects").exists()


def test_controller_request_runs_native_result_and_host_ingest_then_next_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (
        controller,
        approval_path,
        installed_root,
        _context_value,
        resolve,
        _manifest,
    ) = _runtime_fixture(tmp_path, monkeypatch)

    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=approval_path
    )
    request_raw = request_path.read_bytes()
    request = native.verify_native_request(
        request_raw, expected_request_sha256=_hash(request_raw), current=True
    )
    authority, _, checked_approval = native._verify_authority(request, current=True)
    assert checked_approval["approvalId"] == "approval-one"
    assert authority["issuedAt"] == checked_approval["issuedAt"]

    installed_root.mkdir(parents=True)
    installed_request = installed_root / "request.json"
    installed_request.write_bytes(request_raw)
    installed_request.chmod(0o400)
    result_path = native.run_qualification_output_request(
        resolve,
        installed_request,
        expected_request_sha256=_hash(request_raw),
    )
    result_raw = result_path.read_bytes()
    result = native.verify_native_result(result_path, _hash(result_raw))
    assert result["action"] == "construct"
    assert result["status"] == "complete"

    ingested = controller.ingest_native_result(result_path, _hash(result_raw))
    assert ingested == {
        "sequence": 0,
        "action": "construct",
        "status": "complete",
        "resultSha256": _hash(result_raw),
        "hostStage": "native_result_authenticated",
    }

    next_path = controller.prepare_next_native_request(approval_path)
    next_raw = next_path.read_bytes()
    next_request = native.verify_native_request(
        next_raw, expected_request_sha256=_hash(next_raw), current=True
    )
    next_authority, _, _ = native._verify_authority(next_request, current=True)
    assert next_request["action"] == "save_reopen"
    assert next_request["sequence"] == 1
    assert next_authority["permissions"] == ["save_reopen"]


@pytest.mark.parametrize(
    ("action", "payload"),
    [
        (
            "poll_render",
            {
                "jobId": "job-one",
                "startedResultPath": "/tmp/native-start.json",
                "startedResultSha256": "a" * 64,
            },
        ),
        (
            "capture_post",
            {
                "inputBindingPath": "/tmp/input-binding.json",
                "inputBindingSha256": "a" * 64,
                "renderLineagePath": "/tmp/render-lineage.json",
                "renderLineageSha256": "b" * 64,
                "completionResultPath": "/tmp/completion-result.json",
                "completionResultSha256": "c" * 64,
            },
        ),
    ],
)
def test_expired_readonly_authority_is_historical_with_existing_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    payload: dict[str, Any],
) -> None:
    (
        controller,
        approval_path,
        _installed_root,
        _context_value,
        _resolve,
        _manifest,
    ) = _runtime_fixture(tmp_path, monkeypatch)
    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=approval_path
    )
    request_raw = request_path.read_bytes()
    request = native.verify_native_request(
        request_raw, expected_request_sha256=_hash(request_raw), current=True
    )
    approval = _parse(approval_path.read_bytes())
    now = datetime.now(UTC)
    approval["issuedAt"] = (
        (now - timedelta(seconds=30)).isoformat().replace("+00:00", "Z")
    )
    approval["expiresAt"] = (
        (now - timedelta(seconds=2)).isoformat().replace("+00:00", "Z")
    )
    approval_raw = _canonical(approval)
    approval_path.chmod(0o600)
    approval_path.write_bytes(approval_raw)
    approval_path.chmod(0o400)
    output_path = Path(approval["outputPath"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"existing output")

    authority = _parse(Path(request["authority"]["path"]).read_bytes())
    authority["action"] = action
    authority["payloadSha256"] = _hash(_canonical(payload))
    authority["permissions"] = [action]
    authority["issuedAt"] = approval["issuedAt"]
    authority["expiresAt"] = approval["expiresAt"]
    authority["approvalSha256"] = _hash(approval_raw)
    authority_path = tmp_path / f"{action}-authority.json"
    authority_raw = _canonical(authority)
    authority_path.write_bytes(authority_raw)
    authority_path.chmod(0o400)
    readonly_request = {
        **request,
        "action": action,
        "payload": payload,
        "authority": {
            "path": str(authority_path),
            "sha256": _hash(authority_raw),
        },
        "renderIntent": {
            "path": str(tmp_path / f"{action}-render-intent.json"),
            "sha256": "d" * 64,
        },
    }

    _authority, _, historical = native._verify_authority(
        readonly_request, current=False
    )
    assert historical["approvalId"] == "approval-one"
    with pytest.raises(
        records.OutputConsistencyError, match="native authority expired"
    ):
        native._verify_authority(readonly_request, current=True)
