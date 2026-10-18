"""Matrix authority stays distinct from the earlier smoke and private profiles."""

from pathlib import Path

import pytest
from test_issue209_native import _approval
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent.qualification_output_records_v2 import _canonical


def test_matrix_grant_cannot_be_used_as_smoke_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", tmp_path / "native-state")
    approval, context = _approval(tmp_path, profile=package.MATRIX_PROFILE)
    raw = _canonical(approval)
    native.verify_operator_approval(
        raw,
        context=context,
        profile=package.MATRIX_PROFILE,
        admission_sha256=approval["admissionSha256"],
        release_manifest_sha256=approval["releaseManifestSha256"],
    )
    with pytest.raises(ValueError, match="profile"):
        native.verify_operator_approval(
            raw,
            context=context,
            profile=package.SYNTHETIC_PROFILE,
            admission_sha256=approval["admissionSha256"],
            release_manifest_sha256=approval["releaseManifestSha256"],
        )


def test_matrix_refuses_incomplete_preparation_inventory(tmp_path: Path) -> None:
    with pytest.raises(package.QualificationPackageError, match="path inventory"):
        package._prepared_matrix(
            {},
            {},
            {"preparationBindings": [{"requirementKey": "missing"}]},
            {},
            tmp_path,
            {},
            {},
            {},
        )
    assert list(tmp_path.iterdir()) == []


def test_matrix_refuses_receipts_outside_approved_published_root(
    tmp_path: Path,
) -> None:
    key = "0" * 64
    with pytest.raises(
        package.QualificationPackageError, match="approved published root"
    ):
        package._verify_public_receipt(
            "sha256:" + key,
            tmp_path / "published" / key / "receipt.json",
            {},
            {},
            matrix=True,
        )


def test_prepare_cli_passes_exact_matrix_receipt_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller
    from vera_timeline_agent import workflow_v2_cli as cli

    captured: dict[str, object] = {}

    def prepare(_root: Path, **kwargs: object) -> dict[str, bool]:
        captured.update(kwargs)
        return {"prepared": True}

    monkeypatch.setattr(controller, "prepare_output_session", prepare)
    receipt = tmp_path / "receipt.json"
    assert (
        cli.main(
            [
                "output-prepare",
                "--output",
                str(tmp_path / "session"),
                "--profile",
                package.MATRIX_PROFILE,
                "--package",
                str(tmp_path / "package"),
                "--project-uid",
                "project",
                "--timeline-uid",
                "timeline",
                "--project-name",
                "Disposable",
                "--timeline-name",
                "Qualification",
                "--case-id",
                "mixed",
                "--preparation",
                "key",
                str(receipt),
            ]
        )
        == 0
    )
    assert captured["preparation_paths"] == {"key": receipt}


def test_matrix_refuses_dotdot_escape_from_published_root() -> None:
    key = "0" * 64
    path = (
        package.MATRIX_PREPARATION_ROOT
        / ".."
        / "outside/published"
        / key
        / "receipt.json"
    )
    with pytest.raises(package.QualificationPackageError, match="canonical matrix"):
        package._verify_public_receipt("sha256:" + key, path, {}, {}, matrix=True)


def test_generated_track_layout_can_be_constructed_natively(tmp_path: Path) -> None:
    import json

    from issue178_qualification_fixture import _build_case_inputs

    _, dependencies = _build_case_inputs(tmp_path, ())
    view = json.loads(dependencies.read_bytes())
    assert native._required_track_counts(view) == {
        "video": 4,
        "audio": 3,
        "subtitle": 0,
    }


def test_matrix_authenticates_preparation_without_source_sound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import hashlib
    import json

    from vera_timeline_agent.narration.models import identity_hash

    inputs = {"audioStreamIndex": None}
    key = identity_hash(inputs)
    directory = tmp_path / "published" / key.removeprefix("sha256:")
    directory.mkdir(parents=True)
    binding = {
        "authorizationReference": "test",
        "timeMapping": {"sourceFrameMap": {"sourceAudioStreamMappings": []}},
    }
    record = {
        "recordVersion": "authoring-media-preparation/v1",
        "requirementKey": key,
        "inputs": inputs,
        "binding": binding,
        "audio": None,
    }
    raw = json.dumps(record).encode()
    receipt = directory / "receipt.json"
    receipt.write_bytes(raw)
    (directory / "receipt-checksum.json").write_text(
        json.dumps({"receiptHash": "sha256:" + hashlib.sha256(raw).hexdigest()})
    )
    (directory / "request.json").write_text(
        json.dumps(
            {"authorizationReference": "test", "inputs": inputs, "requirementKey": key}
        )
    )
    monkeypatch.setattr(package, "MATRIX_PREPARATION_ROOT", tmp_path)
    states: dict[Path, tuple[int, int, int, int, int]] = {}
    hashes: dict[Path, str] = {}
    result = package._verify_public_receipt(key, receipt, states, hashes, matrix=True)
    assert result == (record, raw, None, b"", b"")
    assert len(hashes) == 3
    monkeypatch.setattr(package, "_PREPARED_ROOT", tmp_path / "published")
    with pytest.raises(package.QualificationPackageError, match=r"audio\.wav"):
        package._verify_public_receipt(key, receipt, {}, {}, matrix=False)
