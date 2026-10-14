"""Synthetic read-only boundaries; no installed Studio or qualification evidence."""

from __future__ import annotations

import json
import os
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
    main,
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
            if not name.startswith("Get"):
                self.calls.append(f"FORBIDDEN:{name}")
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
            "GetSourceAudioChannelMapping": (
                '{"track_mapping":{"1":{"channel_idx":[1,2],'
                '"mute":false,"type":"Stereo"}}}'
            ),
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
            "GetAudioRenderFormats": {"WAV": "wav"},
            "GetAudioRenderCodecs": {"PCM": "lpcm"},
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


@pytest.mark.parametrize("failure", ["missing", "overflow"])
def test_partial_audio_inventory_cannot_claim_supported_controls(
    tmp_path: Path, failure: str
) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, timeline, item, calls = native()
    timeline.values["GetTrackCount"] = lambda kind: 2 if kind == "audio" else 0
    timeline.values["GetItemListInTrack"] = lambda _kind, index: (
        [item] if index == 1 else None if failure == "missing" else [item] * 501
    )
    result = run(request, resolve)
    gaps = {row["field"]: row for row in result["gaps"]}
    for field in ["clip.enabled", "clip.gainDb", "clip.channelMap"]:
        assert gaps[field]["status"] == "ambiguous"
        assert "track:audio:2.GetItemListInTrack" in gaps[field]["sources"]
    assert all(name.startswith("Get") for name in calls)


@pytest.mark.parametrize("failure", ["codec", "formats"])
def test_resolution_visibility_requires_complete_parent_enumeration(
    tmp_path: Path, failure: str
) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, _item, calls = native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    if failure == "codec":
        project.values["GetRenderCodecs"] = lambda ext: (
            None if ext == "mov" else {"PCM": "lpcm"}
        )
    else:
        del project.values["GetRenderFormats"]
    result = run(request, resolve)
    row = next(
        r
        for r in result["gaps"]
        if r["field"] == "render.candidates.GetRenderResolutions"
    )
    assert row["status"] == "ambiguous"
    assert "project.GetRenderFormats" in row["sources"]
    assert all(name.startswith("Get") for name in calls)


def launcher(release: Path, request: Path) -> subprocess.CompletedProcess[str]:
    shutil.copyfile(request, release / RELEASE_NAME / "request.json")
    return subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        capture_output=True,
        text=True,
        check=True,
    )


def test_bootstrap_records_exact_preimport_provenance_before_no_resolve_refusal(
    tmp_path: Path,
) -> None:
    request, _authority, release = inputs(tmp_path)
    value = read_object(request)
    launcher(release, request)
    evidence = tmp_path / "evidence"
    started = list(evidence.glob("bootstrap-started-*.json"))
    assert len(started) == 1
    record = read_object(started[0])
    assert record["requestSha256"] == sha256(request)
    assert record["authoritySha256"] == value["authoritySha256"]
    assert record["target"] == TARGET
    assert record["repositorySourcePins"] == value["binding"]["repositorySourcePins"]
    assert started[0].stat().st_mode & 0o222 == 0
    reports = list(evidence.glob("result-*.json"))
    assert len(reports) == 1
    assert read_object(reports[0])["status"] == "stopped_safely"
    assert read_object(reports[0])["qualified"] is False


@pytest.mark.parametrize(
    "attack",
    [
        "authority-bytes",
        "authority-binding",
        "approval",
        "repository-overlap",
        "release-overlap",
        "extra-key",
        "wrong-action",
    ],
)
def test_bootstrap_authority_refusals_precede_import_and_preserve_safe_evidence(
    tmp_path: Path, attack: str
) -> None:
    request, authority, release = inputs(tmp_path)
    value = read_object(request)
    if attack == "authority-bytes":
        authority.chmod(0o600)
        authority.write_text("changed authority bytes")
    elif attack == "authority-binding":
        value["binding"]["target"]["projectUid"] = "different-request"
    elif attack == "approval":
        Path(value["binding"]["approvalPath"]).write_text("changed approval bytes")
    elif attack == "repository-overlap":
        value["binding"]["evidenceDir"] = (
            value["binding"]["repositoryRoot"] + "/private-output"
        )
    elif attack == "release-overlap":
        value["binding"]["evidenceDir"] = str(release / "private-output")
    elif attack == "extra-key":
        value["qualified"] = True
    else:
        value["action"] = "qualify_build"
    request.chmod(0o600)
    request.write_text(json.dumps(value))
    result = launcher(release, request)
    evidence = tmp_path / "evidence"
    assert "workflow_v2_launcher_failed" in result.stdout
    assert len(list(evidence.glob("bootstrap-refusal-*.json"))) == 1
    assert not list(evidence.glob("bootstrap-started-*.json"))
    assert not list(evidence.glob("started-*.json"))
    assert not list(evidence.glob("result-*.json"))


def test_cli_operator_authority_and_request_are_separate_and_missing_flags_refuse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _request, authority, release = inputs(tmp_path)
    binding = read_object(authority)["binding"]
    monkeypatch.setattr(
        preflight, "source_pins", lambda _repo: binding["repositorySourcePins"]
    )
    # Bind the CLI's real repository; its source bytes are the same synthetic pins.
    output = tmp_path / "cli-authority.json"
    args = [
        "capability-authorize",
        "--release",
        str(release),
        "--approval",
        binding["approvalPath"],
        "--operator",
        "Synthetic operator",
        "--project-uid",
        TARGET["projectUid"],
        "--timeline-uid",
        TARGET["timelineUid"],
        "--project-name",
        TARGET["projectName"],
        "--timeline-name",
        TARGET["timelineName"],
        "--evidence-dir",
        str(tmp_path / "cli-evidence"),
        "--output",
        str(output),
    ]
    assert main(args) == 2
    assert not output.exists()
    assert (
        main(
            [
                *args,
                "--confirm-read-only",
                "--confirm-saved-disposable-nonproduction",
                "--external-scripting-none",
            ]
        )
        == 0
    )
    cli_request = tmp_path / "cli-request.json"
    assert main(["capability-request", str(output), "--output", str(cli_request)]) == 0
    assert read_object(cli_request)["authoritySha256"] == sha256(output)


def test_hardlinked_request_is_refused_before_native(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    alias = tmp_path / "hardlinked-request.json"
    os.link(request, alias)
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError, match="hardlink"):
        run(alias, resolve)
    assert calls == []


@pytest.mark.parametrize("identity", ["case", "firmlink"])
def test_macos_alias_overlap_refuses_before_any_native_read(
    tmp_path: Path, identity: str
) -> None:
    request, authority, _release = inputs(tmp_path)
    value = read_object(authority)
    repo = Path(value["binding"]["repositoryRoot"])
    alias = (
        repo.parent / repo.name.upper()
        if identity == "case"
        else Path("/System/Volumes/Data") / repo.relative_to("/")
    )
    if not alias.exists():
        pytest.skip(f"{identity} alias unavailable on this filesystem")
    assert alias.stat().st_ino == repo.stat().st_ino
    value["binding"]["evidenceDir"] = str(alias / "forbidden-evidence")
    authority.chmod(0o600)
    authority.write_text(json.dumps(value))
    request_value = read_object(request)
    request_value["binding"] = value["binding"]
    request_value["authoritySha256"] = sha256(authority)
    request.chmod(0o600)
    request.write_text(json.dumps(request_value))
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError, match="overlaps"):
        run(request, resolve)
    assert not (repo / "forbidden-evidence").exists()
    assert calls == []


@pytest.mark.parametrize("input_name", ["source", "authority", "approval"])
def test_input_drift_during_getters_invalidates_later_rows(
    tmp_path: Path, input_name: str
) -> None:
    request, authority, _release = inputs(tmp_path)
    value = read_object(request)
    resolve, _timeline, _item, calls = native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    changed = (
        Path(value["binding"]["repositoryRoot"]) / preflight.SOURCE_FILES[0]
        if input_name == "source"
        else authority
        if input_name == "authority"
        else Path(value["binding"]["approvalPath"])
    )

    def drift() -> dict[str, str]:
        changed.chmod(0o600)
        changed.write_text("changed during getter group")
        return {"timelineSampleRate": "48000"}

    project.values["GetSettings"] = drift
    result = run(request, resolve)
    assert result["status"] == "stopped_safely"
    row = next(
        r for r in result["observations"] if r["source"] == "project.GetSettings"
    )
    assert row["contextVerified"] is False
    assert row["status"] == "ambiguous"
    assert all(name.startswith("Get") for name in calls)


@pytest.mark.parametrize("bad_issue", [True, 204.0])
def test_issue_scalar_is_strict_before_getters(tmp_path: Path, bad_issue: Any) -> None:
    request, _authority, _release = inputs(tmp_path)
    value = read_object(request)
    value["issueNumber"] = bad_issue
    request.chmod(0o600)
    request.write_text(json.dumps(value))
    resolve, _timeline, _item, calls = native()
    with pytest.raises(ValueError):
        run(request, resolve)
    assert calls == []


def test_opaque_format_identifiers_and_malformed_neighbors_preserve_queue_observation(
    tmp_path: Path,
) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, _item, calls = native()
    project = resolve.values["GetProjectManager"].values["GetCurrentProject"]
    project.values["GetRenderFormats"] = {"MXF": "mxf_op1a", "Bad": None}
    result = run(request, resolve)
    assert result["status"] == "capability_gaps_observed"
    assert any(
        r["source"] == "project.GetRenderJobList" for r in result["observations"]
    )
    row = next(
        r
        for r in result["gaps"]
        if r["field"] == "render.candidates.GetRenderResolutions"
    )
    assert row["status"] == "ambiguous"
    assert all(name.startswith("Get") for name in calls)


def test_oversized_getter_retains_bounded_partial_report(tmp_path: Path) -> None:
    request, _authority, _release = inputs(tmp_path)
    resolve, _timeline, item, calls = native()
    item.values["GetProperties"] = {"oversized": "x" * (1024 * 1024)}
    result = run(request, resolve)
    row = next(
        r for r in result["observations"] if r["source"].endswith("GetProperties")
    )
    assert row["status"] == "ambiguous"
    assert "budget" in row["reason"]
    assert result["qualified"] is False
    assert list((tmp_path / "evidence").glob("hashes-*.json"))
    assert all(name.startswith("Get") for name in calls)


@pytest.mark.parametrize("attack", ["extra-key", "wrong-action", "scalar"])
def test_bootstrap_closed_authority_refuses_before_import(
    tmp_path: Path, attack: str
) -> None:
    request, authority, release = inputs(tmp_path)
    value = read_object(authority)
    if attack == "extra-key":
        value["selfQualified"] = True
    elif attack == "wrong-action":
        value["action"] = "qualify_build"
    else:
        value["confirmations"]["readOnly"] = 1
    authority.chmod(0o600)
    authority.write_text(json.dumps(value))
    raw = read_object(request)
    raw["authoritySha256"] = sha256(authority)
    request.chmod(0o600)
    request.write_text(json.dumps(raw))
    result = launcher(release, request)
    evidence = tmp_path / "evidence"
    assert "workflow_v2_launcher_failed" in result.stdout
    assert list(evidence.glob("bootstrap-refusal-*.json"))
    assert not list(evidence.glob("bootstrap-started-*.json"))
    assert not list(evidence.glob("started-*.json"))
