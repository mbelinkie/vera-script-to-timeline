"""Operator-only CLI and read-only downstream identity handoff for #381."""

from __future__ import annotations

import hashlib
import json
import os
import uuid
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.local_media_import_cli import run
from vera_timeline_agent.local_media_import_model import DecodedMediaFacts

CANARY = "PRIVATE_ROOT_POLICY_SECRET_CANARY"
DATA = b"\x89PNG\r\n\x1a\n" + b"synthetic media" * 23


def _id(n: int) -> str:
    return str(uuid.UUID(int=n, version=4))


def _hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


class FakeDecoder:
    def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
        content = os.pread(fd, 10000, 0)
        if kind != "image" or content != DATA:
            raise ValueError(CANARY)
        return DecodedMediaFacts(
            kind="image",
            probe_hash=_hash(content + b"decoded"),
            width=32,
            height=32,
        )


def _private_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value))
    path.chmod(0o600)


@pytest.fixture
def setup(
    tmp_path: Path,
) -> tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path]:
    source_root = tmp_path / CANARY
    source_root.mkdir()
    source = source_root / "synthetic.png"
    source.write_bytes(DATA)
    project = tmp_path / "project"
    project.mkdir()
    state = tmp_path / "private_state"
    state.mkdir(mode=0o700)
    request: dict[str, Any] = {
        "schemaVersion": "vera-local-import-request/v1",
        "projectId": _id(1),
        "importId": _id(2),
        "assetId": _id(3),
        "mediaReferenceId": _id(4),
        "sourceRootId": "local_operator_only",
        "sourceSegments": ["synthetic.png"],
        "expectedContentHash": _hash(DATA),
        "expectedSizeBytes": len(DATA),
        "maxSizeBytes": 100000,
        "minimumFreeBytes": 0,
        "kind": "image",
        "requestedMode": "clone",
    }
    policy: dict[str, Any] = {
        "schemaVersion": "vera-local-import-local-policy/v1",
        "sourceRootId": "local_operator_only",
        "sourceRoot": str(source_root),
        "projectRoot": str(project),
        "stateRoot": str(state),
        "operatorApproved": True,
        "grant": request.copy(),
    }
    policy_path = tmp_path / "private-policy.json"
    request_path = tmp_path / "private-request.json"
    _private_json(policy_path, policy)
    _private_json(request_path, request)
    return policy_path, request_path, policy, request, source, project, state


def _invoke(policy_path: Path, request_path: Path, *, verify: bool = False) -> int:
    arguments = ["--policy", str(policy_path), "--request", str(request_path)]
    if verify:
        arguments.append("--verify-existing")
    return run(arguments, decoder=FakeDecoder(), clone=lambda _src, _dst: False)


def _output(capsys: pytest.CaptureFixture[str]) -> dict[str, Any]:
    captured = capsys.readouterr()
    assert captured.err == ""
    assert CANARY not in captured.out
    assert "/tmp/" not in captured.out
    parsed: object = json.loads(captured.out)
    assert isinstance(parsed, dict)
    return cast(dict[str, Any], parsed)


def test_local_synthetic_copy_duplicate_and_read_only_build_handoff(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, _, request, source, project, state = setup
    source_before = source.read_bytes()
    assert _invoke(policy_path, request_path) == 0
    assert _output(capsys) == {
        "status": "completed",
        "importId": request["importId"],
        "buildQualification": "unqualified",
    }
    target = project / "Media/Local Images" / request["assetId"] / "synthetic.png"
    assert target.read_bytes() == source_before == source.read_bytes()
    assert target.stat().st_ino != source.stat().st_ino
    receipt = state / "receipts" / (request["importId"] + ".json")
    assert receipt.stat().st_mode & 0o077 == 0
    assert _invoke(policy_path, request_path) == 0
    assert _output(capsys)["status"] == "duplicate"
    assert _invoke(policy_path, request_path, verify=True) == 0
    assert _output(capsys)["status"] == "verified-unqualified"
    assert source.read_bytes() == source_before
    # Source originals can disappear after an import: the independently
    # reopened script-owned copy remains recheckable without reading originals.
    source.unlink()
    assert _invoke(policy_path, request_path, verify=True) == 0
    assert _output(capsys)["status"] == "verified-unqualified"


def test_policy_grant_is_not_inferred_from_request(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, _, request, source, project, _ = setup
    for changed in (
        {**request, "sourceRoot": str(source.parent)},
        {**request, "sourceSegments": ["other.png"]},
        {**request, "expectedContentHash": _hash(b"wrong")},
        {**request, "assetId": _id(500)},
        {**request, "requestedMode": "move"},
        {**request, "minimumFreeBytes": 1},
    ):
        _private_json(request_path, changed)
        assert _invoke(policy_path, request_path) == 2
        assert _output(capsys)["status"] == "refused"
    assert list(project.iterdir()) == []
    assert source.read_bytes() == DATA


def test_unapproved_and_insecure_policy_refuse_before_mutation(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    policy_path, request_path, policy, _, source, project, _ = setup
    _private_json(policy_path, {**policy, "operatorApproved": False})
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "approval_required"
    _private_json(policy_path, policy)
    policy_path.chmod(0o644)
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "permission_denied"
    policy_path.chmod(0o600)
    linked = tmp_path / "linked_policy.json"
    linked.symlink_to(policy_path)
    assert _invoke(linked, request_path) == 4
    assert _output(capsys)["code"] == "io_failure"
    assert list(project.iterdir()) == []
    assert source.read_bytes() == DATA


def test_duplicate_json_keys_and_wrong_types_fail_closed(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, policy, request, _, project, _ = setup
    request_path.write_text(json.dumps(request)[:-1] + ',"expectedSizeBytes":1}')
    request_path.chmod(0o600)
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "invalid_approval"
    _private_json(request_path, {**request, "expectedSizeBytes": True})
    policy["grant"] = {**request, "expectedSizeBytes": True}
    _private_json(policy_path, policy)
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "invalid_approval"
    assert list(project.iterdir()) == []


def test_no_reverification_without_receipt_no_mutation(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, _, _, _, project, state = setup
    assert _invoke(policy_path, request_path, verify=True) == 3
    assert _output(capsys)["code"] == "needs_inspection"
    assert list(project.iterdir()) == []
    assert list(state.iterdir()) == []


def test_missing_or_replaced_destination_refused_on_downstream_handoff(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, _, request, source, project, _ = setup
    assert _invoke(policy_path, request_path) == 0
    _output(capsys)
    target = project / "Media/Local Images" / request["assetId"] / "synthetic.png"
    target.rename(target.with_suffix(".previous"))
    target.write_bytes(DATA)
    target.chmod(0o600)
    assert _invoke(policy_path, request_path, verify=True) == 3
    assert _output(capsys)["code"] == "needs_inspection"
    target.unlink()
    assert _invoke(policy_path, request_path, verify=True) == 3
    assert _output(capsys)["code"] == "needs_inspection"
    assert source.read_bytes() == DATA


def test_reverification_detects_target_mutation_during_decoder(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, _, request, source, project, _ = setup
    assert _invoke(policy_path, request_path) == 0
    _output(capsys)
    target = project / "Media/Local Images" / request["assetId"] / "synthetic.png"

    class MutatingDecoder(FakeDecoder):
        def decode(self, fd: int, kind: str) -> DecodedMediaFacts:
            proof = super().decode(fd, kind)
            target.write_bytes(b"changed after the first hash")
            return proof

    assert (
        run(
            [
                "--policy",
                str(policy_path),
                "--request",
                str(request_path),
                "--verify-existing",
            ],
            decoder=MutatingDecoder(),
        )
        == 3
    )
    assert _output(capsys)["code"] == "needs_inspection"
    assert source.read_bytes() == DATA


def test_private_failures_and_argument_parser_never_echo_canaries(
    setup: tuple[Path, Path, dict[str, Any], dict[str, Any], Path, Path, Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    policy_path, request_path, policy, _, source, project, _ = setup
    source.unlink()
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "source_unavailable"
    assert run(["--incorrect", CANARY]) == 2
    assert _output(capsys)["code"] == "invalid_approval"
    # Bad/missing policy root cannot be rescued by the request.
    _private_json(policy_path, {**policy, "projectRoot": CANARY})
    assert _invoke(policy_path, request_path) == 2
    assert _output(capsys)["code"] == "invalid_approval"
    assert {entry.name for entry in project.iterdir()} == {".vera-local-import.lock"}
    assert not (project / "Media").exists()
