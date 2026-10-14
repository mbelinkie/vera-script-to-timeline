"""Synthetic read-only boundaries; no installed Studio or qualification evidence."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import native_qualification_v2 as preflight
from vera_timeline_agent.workflow_package import read_object, sha256
from vera_timeline_agent.workflow_v2_cli import (
    LAUNCHER_NAME,
    RELEASE_NAME,
    build_release_v2,
)
from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

TARGET = {
    "projectUid": "project-204",
    "timelineUid": "timeline-204",
    "projectName": "VERA disposable preflight 204",
    "timelineName": "Saved synthetic timeline",
}


class GettersOnly:
    def __init__(self, calls: list[str], values: dict[str, Any]) -> None:
        self.calls = calls
        self.values = values

    def __getattr__(self, name: str) -> Any:
        if name not in self.values:
            if name.startswith(("Set", "Create", "Add", "Start", "Save", "Export")):
                raise AssertionError(f"native effect attempted: {name}")
            raise AttributeError(name)

        def getter(*args: Any) -> Any:
            self.calls.append(name)
            value = self.values[name]
            return value(*args) if callable(value) else value

        return getter


def native() -> tuple[GettersOnly, GettersOnly, GettersOnly, list[str]]:
    calls: list[str] = []
    item = GettersOnly(
        calls,
        {
            "GetUniqueId": "item-204",
            "GetClipEnabled": True,
            "GetProperties": {"AudioVolumeEnabled": True, "AudioVolume": -18},
            "GetSpeed": {
                "Percentage": 100,
                "PitchCorrection": True,
                "StretchKeyframesToFit": False,
                "RippleTimeline": False,
            },
            "GetSourceAudioChannelMapping": '{"track_mapping": []}',
        },
    )
    timeline = GettersOnly(
        calls,
        {
            "GetUniqueId": TARGET["timelineUid"],
            "GetName": TARGET["timelineName"],
            "GetSettings": {"timelineFrameRate": "23.976"},
            "GetTrackCount": lambda kind: 1 if kind == "audio" else 0,
            "GetTrackName": "Source",
            "GetIsTrackEnabled": True,
            "GetIsTrackLocked": False,
            "GetTrackSubType": "stereo",
            "GetItemListInTrack": [item],
        },
    )
    project = GettersOnly(
        calls,
        {
            "GetUniqueId": TARGET["projectUid"],
            "GetName": TARGET["projectName"],
            "GetCurrentTimeline": timeline,
            "GetSettings": {"timelineSampleRate": "48000"},
            "GetRenderFormats": {"WAV": "wav", "QuickTime": "mov"},
            "GetRenderCodecs": {"PCM": "lpcm"},
            "GetRenderResolutions": [{"Width": 1920, "Height": 1080}],
            "GetCurrentRenderFormatAndCodec": {"format": "mov", "codec": "x"},
            "GetRenderJobList": [],
        },
    )
    manager = GettersOnly(calls, {"GetCurrentProject": project})
    resolve = GettersOnly(
        calls,
        {
            "GetProductName": "DaVinci Resolve Studio",
            "GetVersion": [21, 1, 1, 10, ""],
            "GetProjectManager": manager,
        },
    )
    return resolve, timeline, item, calls


def inputs(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo = tmp_path / "repository"
    real = Path(__file__).resolve().parents[1]
    for relative in preflight.SOURCE_FILES:
        out = repo / relative
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real / relative, out)
    release = tmp_path / "release"
    build_release_v2(release)
    approval = tmp_path / "producer-approval.json"
    approval.write_text(
        json.dumps(
            {
                "changeNote": "CN-178-Q1",
                "producerQuote": "Approve staged CN-178-Q1",
                "noteSha256": preflight.APPROVED_NOTE_HASH,
                "scope": preflight.APPROVED_SCOPE,
                "recordedAt": "2026-10-14T03:34:24+00:00",
                "ordinaryGuardsRetained": True,
            }
        )
    )
    authority = preflight.create_capability_authority(
        tmp_path / "authority.json",
        release_root=release,
        repository_root=repo,
        target=TARGET,
        evidence_dir=tmp_path / "evidence",
        approval_path=approval,
        operator="Test operator (synthetic)",
        confirm_saved_disposable=True,
        confirm_read_only=True,
        external_scripting_none=True,
    )
    request = preflight.prepare_capability_request(
        tmp_path / "request.json", authority_path=authority
    )
    return request, authority, release


def run(request: Path, resolve: Any) -> dict[str, Any]:
    result = preflight.run_capability_preflight(
        resolve, request, expected_request_sha256=sha256(request)
    )
    return read_object(result)


def test_complete_getters_report_real_gaps_without_native_effects(
    tmp_path: Path,
) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, _item, calls = native()
    result = run(request, resolve)
    assert result["status"] == "capability_gaps_observed"
    assert result["qualified"] is result["verified"] is False
    assert result["target"] == TARGET
    assert calls and all(name.startswith("Get") for name in calls)
    gaps = {row["field"]: row for row in result["gaps"]}
    assert gaps["master.effects"]["status"] == "unsupported"
    assert gaps["bus.automation"]["status"] == "unsupported"
    assert gaps["render.actualOutputCadence"]["status"] == "unsupported"
    assert gaps["render.queue.AudioCodec"]["status"] == "ambiguous"
    assert result["futureEffectsAuthorized"] is False


@pytest.mark.parametrize(
    "attack",
    ["authority-missing", "authority-binding", "action", "extra", "source", "release"],
)
def test_bad_handoff_refuses_before_any_native_getter(
    tmp_path: Path, attack: str
) -> None:
    request, authority, _release = inputs(tmp_path)
    value = read_object(request)
    if attack == "authority-missing":
        authority.unlink()
    elif attack == "authority-binding":
        value["binding"]["target"]["projectUid"] = "unapproved-project"
    elif attack == "action":
        value["action"] = "qualify_build"
    elif attack == "extra":
        value["qualified"] = True
    elif attack == "source":
        source = Path(value["binding"]["repositoryRoot"]) / preflight.SOURCE_FILES[0]
        source.write_text("changed after independent authority")
    else:
        manifest = Path(value["binding"]["releaseRoot"]) / RELEASE_NAME / "release.json"
        manifest.chmod(0o600)
        manifest.write_text("changed release bytes")
    request.chmod(0o600)
    request.write_text(json.dumps(value))
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError):
        run(request, resolve)
    assert calls == []


def test_exact_request_hash_drift_refuses_before_native(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError, match="request drift"):
        preflight.run_capability_preflight(
            resolve, request, expected_request_sha256="0" * 64
        )
    assert calls == []


def test_request_cannot_issue_or_invent_missing_authority(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        preflight.prepare_capability_request(
            tmp_path / "request.json", authority_path=tmp_path / "absent.json"
        )
    assert not (tmp_path / "request.json").exists()


@pytest.mark.parametrize("confirmation", ["saved", "read-only", "none"])
def test_authority_requires_separate_explicit_operator_confirmations(
    tmp_path: Path, confirmation: str
) -> None:
    _request, authority, release = inputs(tmp_path)
    binding = read_object(authority)["binding"]
    with pytest.raises(ValueError):
        preflight.create_capability_authority(
            tmp_path / "second.json",
            release_root=release,
            repository_root=Path(binding["repositoryRoot"]),
            target=TARGET,
            evidence_dir=tmp_path / "other-evidence",
            approval_path=Path(binding["approvalPath"]),
            operator="Test operator",
            confirm_saved_disposable=confirmation != "saved",
            confirm_read_only=confirmation != "read-only",
            external_scripting_none=confirmation != "none",
        )
    assert not (tmp_path / "second.json").exists()


def test_symlink_and_duplicate_json_refuse_before_native(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    alias = tmp_path / "alias.json"
    alias.symlink_to(request)
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError):
        run(alias, resolve)
    request.chmod(0o600)
    request.write_text('{"action":"capability_preflight","action":"qualify_build"}')
    with pytest.raises(ValueError, match="duplicate"):
        run(request, resolve)
    assert calls == []


@pytest.mark.parametrize("attack", ["target", "version", "drift"])
def test_native_identity_failure_retains_unqualified_refusal(
    tmp_path: Path, attack: str
) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, timeline, _item, calls = native()
    if attack == "target":
        timeline.values["GetUniqueId"] = "other"
    elif attack == "version":
        resolve.values["GetVersion"] = [21, 1, 1, 999, ""]
    else:
        count = 0

        def uid() -> str:
            nonlocal count
            count += 1
            return TARGET["timelineUid"] if count == 1 else "drift"

        timeline.values["GetUniqueId"] = uid
    result = run(request, resolve)
    assert result["status"] == "stopped_safely"
    assert result["qualified"] is False
    assert all(name.startswith("Get") for name in calls)


def test_missing_getters_and_nonboolean_states_are_not_defaults(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, timeline, item, _calls = native()
    del item.values["GetProperties"]
    timeline.values["GetIsTrackEnabled"] = "true"
    result = run(request, resolve)
    raw = result["observations"]
    missing = [row for row in raw if row["source"].endswith("GetProperties")]
    assert missing and missing[0]["status"] == "unsupported"
    invalid = [row for row in raw if row["source"].endswith("GetIsTrackEnabled")]
    assert invalid[0]["status"] == "ambiguous"
    assert invalid[0]["value"] == "true"


def test_installed_dispatch_and_evidence_are_immutable(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, _item, _calls = native()
    first = run_installed_request_v2(
        resolve, request, expected_request_sha256=sha256(request)
    )
    old_bytes = first.read_bytes()
    second = run_installed_request_v2(
        resolve, request, expected_request_sha256=sha256(request)
    )
    assert second != first and first.read_bytes() == old_bytes
    hashes = list(first.parent.glob("hashes-*.json"))
    assert len(hashes) == 2
    assert {read_object(path)["resultSha256"] for path in hashes} == {
        sha256(first),
        sha256(second),
    }


@pytest.mark.parametrize("attack", ["undeclared", "loaded"])
def test_installed_bootstrap_refuses_untrusted_runtime(
    tmp_path: Path, attack: str
) -> None:
    request, _authority, release = inputs(tmp_path)
    installed = release / RELEASE_NAME / "request.json"
    shutil.copyfile(request, installed)
    if attack == "undeclared":
        (release / RELEASE_NAME / "extra.py").write_text("raise AssertionError()")
        command = [sys.executable, "-S", str(release / LAUNCHER_NAME)]
    else:
        command = [
            sys.executable,
            "-S",
            "-c",
            "import runpy,sys,types; "
            "n='vera_timeline_agent'; sys.modules[n]=types.ModuleType(n); "
            f"runpy.run_path({str(release / LAUNCHER_NAME)!r})",
        ]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    assert "workflow_v2_launcher_failed" in result.stdout
    assert not list((tmp_path / "evidence").glob("result-*.json"))
