"""Phase-21 helper protocol: fully simulated, never invoke the Mac or Resolve."""

from __future__ import annotations

import copy
import hashlib
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from _actor_pin import actor_pin
from vera_timeline_agent import resolve_gui_helper_protocol as helper
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent.roundtrip_v2_records import ROOT as PROJECT_ROOT

NOW = datetime.now(UTC)


def request() -> dict[str, Any]:
    return {
        "schema": helper.REQUEST_SCHEMA,
        "requestId": "request-trial-001",
        "deadlineAt": (NOW + timedelta(seconds=60)).isoformat().replace("+00:00", "Z"),
        "operation": helper.OPERATION,
        "jobId": "resolve-reverse-original-1234",
        "stageOperationId": "m4-edited-original-1234",
        "fixtureId": "synthetic-312",
        "trialId": "fresh-trial-123456",
        "resolvePid": 1234,
        "windowName": "VERA Delivery 123e4567-e89b-12d3-a456-426614174000 012345abcdef",
        "projectUid": "brand-new-project-1234",
        "timelineUid": "brand-new-timeline-1234",
        "sourceGraphSha256": "a" * 64,
        "actorPin": actor_pin(),
        "pristineCaptureSha256": "b" * 64,
        "oneUseIntentSha256": "c" * 64,
        "authoritySha256": "d" * 64,
    }


def expected(value: dict[str, Any]) -> dict[str, Any]:
    return {name: value[name] for name in helper.OWNER_KEYS}


def reply_for(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema": helper.REPLY_SCHEMA,
        "requestId": value["requestId"],
        "requestSha256": hashlib.sha256(queue.canonical(value)).hexdigest(),
        "actorPin": value["actorPin"],
        "helperPid": 2345,
        "status": "dispatched-unknown",
        "detail": "OS action attempted; native result unknown",
    }


def test_closed_source_manifest_pins_all_helper_assets() -> None:
    manifest = helper.source_manifest()
    assert set(helper.SOURCE_FILES) <= set(manifest["files"])
    assert all(value.startswith("sha256:") for value in manifest["files"].values())
    assert not any("manifest.json" in name for name in manifest["files"])
    helper.verify_source_manifest(helper.source_manifest_sha256(), manifest)
    with pytest.raises(helper.HelperProtocolError, match="claimed helper source"):
        helper.verify_source_manifest(
            helper.source_manifest_sha256(), {**manifest, "files": {}}
        )


@pytest.mark.parametrize(
    "change",
    [
        "schema",
        "requestId",
        "deadlineAt",
        "operation",
        "jobId",
        "stageOperationId",
        "fixtureId",
        "trialId",
        "resolvePid",
        "windowName",
        "projectUid",
        "timelineUid",
        "sourceGraphSha256",
        "actorPin",
        "pristineCaptureSha256",
        "oneUseIntentSha256",
        "authoritySha256",
        "extra",
        "missing",
    ],
)
def test_request_rejects_tamper_and_unknown_fields(change: str) -> None:
    value = request()
    if change == "extra":
        value["runShell"] = "echo bad"
    elif change == "missing":
        del value["jobId"]
    elif change == "resolvePid":
        value[change] = True
    elif change == "deadlineAt":
        value[change] = (NOW - timedelta(seconds=1)).isoformat().replace("+00:00", "Z")
    elif change == "actorPin":
        value[change] = {"schema": "old-apple-script-pin", "scriptSha256": "a" * 64}
    elif change in {"requestId", "jobId", "stageOperationId", "trialId"}:
        value[change] = "invalid/id"
    elif change in {"windowName", "projectUid", "timelineUid"}:
        value[change] = "bad\nname"
    else:
        value[change] = "untrusted"
    with pytest.raises(helper.HelperProtocolError):
        helper.validate_request(queue.canonical(value), now=NOW)


@pytest.mark.parametrize(
    "text",
    [
        b'{"schema":"vera.gui-helper-request/v1","schema":"vera.gui-helper-request/v1"}',
        b'{"unknown":NaN}',
        b'{"unknown":1}',
        b"not JSON",
        b"\xff",
        b"x" * 32769,
    ],
)
def test_bad_noncanonical_duplicate_or_oversize_record(text: bytes) -> None:
    with pytest.raises(helper.HelperProtocolError):
        helper.validate_request(text, now=NOW)


def test_original_job_stage_target_source_and_authority_must_match() -> None:
    value = request()
    original = expected(value)
    for field in original:
        altered = {**original, field: "other-value"}
        with pytest.raises(helper.HelperProtocolError, match="owning job"):
            helper.validate_request(queue.canonical(value), now=NOW, expected=altered)
    helper.validate_request(queue.canonical(value), now=NOW, expected=original)


@pytest.mark.parametrize("seconds", [-1, 0, 121, 86400])
def test_deadline_is_short_and_unexpired(seconds: int) -> None:
    value = request()
    value["deadlineAt"] = (
        (NOW + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
    )
    with pytest.raises(helper.HelperProtocolError, match="deadline"):
        helper.validate_request(queue.canonical(value), now=NOW)


@pytest.mark.parametrize(
    "field",
    [
        "schema",
        "sourceManifestSha256",
        "binary",
        "extra",
    ],
)
def test_actor_pin_rejects_old_apple_script_or_altered_identity(field: str) -> None:
    value = actor_pin()
    if field == "schema":
        value[field] = "vera.apple-script/v1"
    elif field == "sourceManifestSha256":
        value[field] = "0" * 64
    elif field == "binary":
        value[field] = {
            **cast(dict[str, str], value["binary"]),
            "codeDirectoryHash": "0" * 40,
        }
        # A different code-directory hash is syntactically valid; installed
        # binary verification will reject it, not an arbitrary static pin.
        with pytest.raises(helper.HelperProtocolError, match="installed"):
            helper.validate_actor_pin(
                value, installed=True, observer=lambda _: {"drift": "x"}
            )
        return
    else:
        value["scriptSha256"] = "0" * 64
    with pytest.raises(helper.HelperProtocolError):
        helper.validate_actor_pin(value)


def test_installed_binary_hash_changed_and_signature_unavailable_fail_closed(
    tmp_path: Path,
) -> None:
    exe = tmp_path / "VERA GUI Helper.app" / "Contents" / "MacOS" / "VERAGUIHelper"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"signed-binary-fixture")
    binary = {
        **cast(dict[str, str], actor_pin()["binary"]),
        "executablePath": str(exe),
        "sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
    }
    helper.validate_binary_pin(binary)
    exe.write_bytes(b"replaced-binary-fixture")
    with pytest.raises(
        helper.HelperProtocolError, match="installed executable changed"
    ):
        helper.observe_installed_binary(binary)
    exe.unlink()
    exe.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(helper.HelperProtocolError):
        helper.observe_installed_binary(binary)


def test_source_drift_and_symlink_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for name in helper.SOURCE_FILES:
        source = PROJECT_ROOT / name
        destination = tmp_path / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    monkeypatch.setattr(helper, "ROOT", tmp_path)
    digest = helper.source_manifest_sha256()
    helper.verify_source_manifest(digest)
    swift = tmp_path / "macos/vera-gui-helper/Sources/VERAGUIHelper/main.swift"
    swift.write_text(swift.read_text() + "\n// altered\n")
    with pytest.raises(helper.HelperProtocolError, match="helper source changed"):
        helper.verify_source_manifest(digest)
    swift.unlink()
    swift.symlink_to(tmp_path / "elsewhere")
    with pytest.raises(helper.HelperProtocolError):
        helper.source_manifest()


def test_spool_is_one_use_request_and_reply_is_not_native_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(helper, "observe_installed_binary", lambda pin: pin)
    monkeypatch.setattr(
        helper,
        "observe_helper_pid",
        lambda pid, path: pid == 2345 and path.endswith("VERAGUIHelper"),
    )
    root = tmp_path / "private"
    value = request()
    raw = queue.canonical(value)
    client = helper.HelperClient(root)
    digest = client.publish_once(raw, now=NOW, expected=expected(value))
    assert digest == hashlib.sha256(raw).hexdigest()
    with pytest.raises(FileExistsError):
        client.publish_once(raw, now=NOW, expected=expected(value))
    carrier._once(
        root / (value["requestId"] + ".reply.json"), queue.canonical(reply_for(value))
    )
    response = client.read_reply(
        raw,
        now=NOW,
    )
    assert response["status"] == "dispatched-unknown"
    assert "nativeVerified" not in response
    with pytest.raises(helper.HelperProtocolError, match="actual helper process"):
        monkeypatch.setattr(helper, "observe_helper_pid", lambda *_: False)
        client.read_reply(raw, now=NOW)


@pytest.mark.parametrize(
    "change",
    [
        "requestId",
        "requestSha256",
        "actorPin",
        "helperPid",
        "status",
        "detail",
        "extra",
    ],
)
def test_reply_rejects_mismatch_or_forged_success(change: str) -> None:
    request_value = request()
    reply = reply_for(request_value)
    if change == "extra":
        reply["nativeVerified"] = True
    elif change == "helperPid":
        reply[change] = 0
    elif change == "status":
        reply[change] = "success"
    elif change == "actorPin":
        reply[change] = {**reply[change], "sourceManifestSha256": "1" * 64}
    elif change == "detail":
        reply[change] = ""
    else:
        reply[change] = "wrong"
    with pytest.raises(helper.HelperProtocolError):
        helper.validate_reply(
            queue.canonical(reply), queue.canonical(request_value), now=NOW
        )


def test_aliases_and_request_path_symlinks_cannot_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(helper, "observe_installed_binary", lambda pin: pin)
    private = tmp_path / "private"
    client = helper.HelperClient(private)
    value = request()
    raw = queue.canonical(value)
    reply_path = private / (value["requestId"] + ".reply.json")
    reply_path.symlink_to(tmp_path / "outside.json")
    client.publish_once(raw, now=NOW, expected=expected(value))
    with pytest.raises(queue.QueueError):
        client.read_reply(raw, now=NOW)
    aliased = tmp_path / "alias"
    aliased.symlink_to(private, target_is_directory=True)
    with pytest.raises(queue.QueueError):
        helper.HelperClient(aliased)
    assert private.is_dir() and not (tmp_path / "outside.json").exists()


def test_real_codesign_parser_accepts_exact_test_double_and_rejects_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Read-only codesign adapter is tested without invoking /usr/bin/codesign."""
    path = tmp_path / "VERA GUI Helper.app" / "Contents/MacOS/VERAGUIHelper"
    path.parent.mkdir(parents=True)
    path.write_bytes(b"synthetic signed executable original")
    binary = {
        **cast(dict[str, str], actor_pin()["binary"]),
        "executablePath": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    calls: list[list[str]] = []
    broken = [False]

    def codesign(args: list[str], **_kwargs: Any) -> SimpleNamespace:
        calls.append(args)
        if broken[0] and "-dv" in args:
            return SimpleNamespace(returncode=0, stdout="", stderr="Identifier=other")
        if "-dv" in args:
            stderr = (
                f"Identifier={helper.BUNDLE_ID}\nCDHash={binary['codeDirectoryHash']}\n"
                f"TeamIdentifier={binary['teamIdentifier']}\n"
            )
        elif "-dr" in args:
            stderr = "designated => " + binary["designatedRequirement"]
        else:
            stderr = ""
        return SimpleNamespace(returncode=0, stdout="", stderr=stderr)

    monkeypatch.setattr(subprocess, "run", codesign)
    assert helper.observe_installed_binary(binary) == binary
    assert len(calls) == 3 and calls[0][1] == "--verify"
    broken[0] = True
    with pytest.raises(helper.HelperProtocolError, match="signing identity"):
        helper.observe_installed_binary(binary)


def test_helper_client_requires_authorized_actor_and_single_request_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(helper, "observe_installed_binary", lambda pin: pin)
    value = request()
    bound = expected(value)
    client = helper.HelperClient(tmp_path / "private")
    for field, alternative in (
        (
            "actorPin",
            {
                **value["actorPin"],
                "binary": {**value["actorPin"]["binary"], "sha256": "f" * 64},
            },
        ),
        ("requestId", "another-id-1234"),
        (
            "deadlineAt",
            (NOW + timedelta(seconds=90)).isoformat().replace("+00:00", "Z"),
        ),
    ):
        changed = copy.deepcopy(value)
        changed[field] = alternative
        with pytest.raises(helper.HelperProtocolError, match="owning job"):
            client.publish_once(queue.canonical(changed), now=NOW, expected=bound)
    assert list(client.root.iterdir()) == []


def test_read_only_helper_pid_probe_refuses_non_mac_environment() -> None:
    assert (
        helper.observe_helper_pid(
            0, "/Applications/VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
        )
        is False
    )
