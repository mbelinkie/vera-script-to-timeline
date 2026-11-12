"""#507: accepted bytes and frozen compiler inputs; no native effects."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest
from test_issue382_build_agent import (
    JOB,
    PROJECT,
    SNAPSHOT,
    TARGET,
    FakeInputAuthority,
    FakePort,
    FakeTransport,
    complete_dependencies,
    digest,
    manifest,
    service,
)
from vera_timeline_agent.build_agent_service import (
    AgentTransportRefusal,
    _same_frozen_authority,
    _validated_selected_pins,
)
from vera_timeline_agent.build_submission_inputs import (
    AcceptedSourceFile,
    FrozenInputRefusal,
    checked_compiler_dependencies,
    frozen_source_file,
)

GOLDEN = (
    Path(__file__).parent
    / "data/authoring_v2/issue_173/compiler/selected-clip-ntsc.input.golden.json"
)


def _pin(
    source_id: str = TARGET, raw: bytes = b"public synthetic clip"
) -> dict[str, str]:
    return {
        "sourceId": source_id,
        "revision": "accepted-v1",
        "sha256": "sha256:" + hashlib.sha256(raw).hexdigest(),
    }


def _accepted(
    tmp_path: Path, transport: FakeTransport, raw: bytes = b"public synthetic clip"
) -> tuple[FakeInputAuthority, Path]:
    directory = tmp_path / "accepted"
    directory.mkdir(mode=0o700)
    path = directory / "clip.mov"
    path.write_bytes(raw)
    pin = _pin(raw=raw)
    transport.data["selectedSources"] = [pin]
    authority = FakeInputAuthority(transport)
    authority.accepted[TARGET] = AcceptedSourceFile(
        PROJECT,
        TARGET,
        pin["revision"],
        pin["sha256"],
        path,
    )
    fixture = json.loads(GOLDEN.read_text())["dependencies"]
    deps = complete_dependencies(transport.data)
    occurrence = copy.deepcopy(fixture["occurrenceResolutions"][0])
    occurrence["mediaReferenceId"] = TARGET
    occurrence["sourceSnapshot"]["contentHash"] = pin["sha256"]
    deps["occurrenceResolutions"] = [occurrence]
    authority.dependencies = deps
    return authority, directory


def test_pin_parser_preserves_exact_version_hash() -> None:
    pin = _pin()
    assert _validated_selected_pins([pin]) == {TARGET: (pin["revision"], pin["sha256"])}
    assert _validated_selected_pins([]) == {}


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "extra",
        "duplicate",
        "length",
        "revision_path",
        "revision_space",
        "revision_control",
        "digest",
        "source_id",
        "order",
        "not_list",
        "not_object",
    ],
)
def test_malformed_duplicate_or_noncanonical_source_claim_refused(fault: str) -> None:
    pin = _pin()
    other = _pin(JOB)
    claims: Any = [pin]
    if fault == "missing":
        pin.pop("revision")
    elif fault == "extra":
        pin["localPath"] = "/tmp/escape"
    elif fault == "duplicate":
        claims = [pin, dict(pin)]
    elif fault == "length":
        claims = [pin] * 257
    elif fault == "revision_path":
        pin["revision"] = "../escape"
    elif fault == "revision_space":
        pin["revision"] = " v1 "
    elif fault == "revision_control":
        pin["revision"] = "a\x00b"
    elif fault == "digest":
        pin["sha256"] = "wrong"
    elif fault == "source_id":
        pin["sourceId"] = "../bad"
    elif fault == "order":
        claims = [pin, other]  # bbbb then aaaa, not canonical
    elif fault == "not_list":
        claims = {"selectedSources": []}
    else:
        claims = ["not-a-pin"]
    with pytest.raises(AgentTransportRefusal):
        _validated_selected_pins(claims)


@pytest.mark.parametrize(
    "field",
    [
        "targetId",
        "mode",
        "buildClass",
        "snapshotDigest",
        "settingsRevision",
        "documentRevision",
        "selectedSources",
    ],
)
def test_frozen_authority_detects_substitutions(field: str) -> None:
    before = manifest()
    before["selectedSources"] = [_pin()]
    after = copy.deepcopy(before)
    assert _same_frozen_authority(before, after)
    after[field] = [_pin(JOB)] if field == "selectedSources" else "altered"
    assert not _same_frozen_authority(before, after)


def test_real_issue173_selected_clip_ntsc_schema_and_pins() -> None:
    golden = json.loads(GOLDEN.read_text())
    assert golden["document"]["schemaVersion"] == "script-document/v2"
    original = copy.deepcopy(golden["dependencies"])
    source_id = original["occurrenceResolutions"][0]["mediaReferenceId"]
    source_hash = original["occurrenceResolutions"][0]["sourceSnapshot"]["contentHash"]
    value = manifest()
    value["documentJson"] = json.dumps(golden["document"])
    value["documentDigest"] = digest(value["documentJson"])
    value["documentRevision"] = original["document"]["revision"]
    value["projectId"] = golden["document"]["projectId"]
    value["settingsJson"] = json.dumps({"projectId": value["projectId"]})
    value["settingsDigest"] = digest(value["settingsJson"])
    value["jobId"] = original["build"]["buildId"]
    value["selectedSources"] = [
        {"sourceId": source_id, "revision": "v1", "sha256": source_hash}
    ]
    original["document"]["contentHash"] = value["documentDigest"]
    original["document"]["settingsHash"] = value["settingsDigest"]
    original["authoringDefaults"]["settingsHash"] = value["settingsDigest"]
    original["preparedMedia"] = []  # only verified P5 may publish preparation
    assert json.loads(
        checked_compiler_dependencies(
            original, value, _validated_selected_pins(value["selectedSources"])
        )
    )["timeline"]["frameRate"] == {"numerator": 24000, "denominator": 1001}


@pytest.mark.parametrize(
    "fault", ["missing", "schema", "document", "settings", "source", "prepared"]
)
def test_missing_or_contradictory_compiler_data_fails(fault: str) -> None:
    value = manifest()
    deps = complete_dependencies(value)
    if fault == "missing":
        del deps["timeline"]
    elif fault == "schema":
        deps["schemaVersion"] = "compiler-dependencies/v1"
    elif fault == "document":
        deps["document"]["contentHash"] = digest("wrong")
    elif fault == "settings":
        deps["authoringDefaults"]["settingsHash"] = digest("wrong")
    elif fault == "source":
        deps["occurrenceResolutions"] = json.loads(GOLDEN.read_text())["dependencies"][
            "occurrenceResolutions"
        ]
    else:
        deps["preparedMedia"] = json.loads(GOLDEN.read_text())["dependencies"][
            "preparedMedia"
        ]
    with pytest.raises(FrozenInputRefusal):
        checked_compiler_dependencies(deps, value, {})
    with pytest.raises(FrozenInputRefusal):
        checked_compiler_dependencies(None, value, {})


def test_accepted_source_is_copied_and_pinned_in_local_snapshot(tmp_path: Path) -> None:
    transport, port = FakeTransport(), FakePort()
    authority, directory = _accepted(tmp_path, transport)
    agent = service(
        tmp_path,
        transport,
        port,
        input_authority=authority,
        accepted_source_roots=(directory,),
    )
    assert agent.run_one(JOB) == "queued"
    assert port.calls == 1
    source = agent.root / "inputs" / JOB / f"source-{TARGET}.bin"
    assert source.read_bytes() == b"public synthetic clip"
    snapshot = next((agent.root / "snapshots").glob("*.json"))
    frozen = json.loads(snapshot.read_text())
    assert f"source:{TARGET}" in frozen["inputs"]
    assert "submission" in frozen["inputs"]
    submission = json.loads((source.parent / "submission.json").read_text())
    assert submission["selectedSources"] == transport.data["selectedSources"]
    assert submission["targetId"] == TARGET
    assert submission["snapshotDigest"] == SNAPSHOT
    assert (
        json.loads((source.parent / "dependencies.json").read_text())["schemaVersion"]
        == "compiler-dependencies/v2"
    )


def test_revoked_or_altered_source_fails_before_next_effect(tmp_path: Path) -> None:
    transport, port = FakeTransport(), FakePort()
    authority, directory = _accepted(tmp_path, transport)
    agent = service(
        tmp_path,
        transport,
        port,
        input_authority=authority,
        accepted_source_roots=(directory,),
    )
    assert agent.run_one(JOB) == "queued"
    assert port.calls == 1
    (directory / "clip.mov").write_bytes(b"altered synthetic clip")
    with pytest.raises(AgentTransportRefusal):
        agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
    assert port.calls == 1
    (directory / "clip.mov").write_bytes(b"public synthetic clip")
    authority.accepted.clear()
    with pytest.raises(AgentTransportRefusal):
        agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
    assert port.calls == 1


def test_changed_compiler_metadata_stops_next_stage(tmp_path: Path) -> None:
    transport, port = FakeTransport(), FakePort()
    authority = FakeInputAuthority(transport, complete_dependencies(transport.data))
    agent = service(tmp_path, transport, port, input_authority=authority)
    assert agent.run_one(JOB) == "queued"
    assert port.calls == 1
    assert authority.dependencies is not None
    authority.dependencies["timeline"]["durationFrames"] += 1
    with pytest.raises(AgentTransportRefusal):
        agent.run_one(JOB, resumed_epoch=1, resumed_digest=SNAPSHOT)
    assert port.calls == 1


@pytest.mark.parametrize("field", ["targetId", "mode", "buildClass", "selectedSources"])
def test_manifest_drift_after_claim_prevents_first_effect(
    tmp_path: Path, field: str
) -> None:
    class DriftTransport(FakeTransport):
        def frozen(self, job_id: str, epoch: int) -> dict[str, Any]:
            result = super().frozen(job_id, epoch)
            if self.reads == 2:
                result[field] = (
                    []
                    if field == "selectedSources"
                    else (
                        "release"
                        if field == "buildClass"
                        else "studio"
                        if field == "mode"
                        else JOB
                    )
                )
                if field == "selectedSources":
                    result[field] = [_pin()]
            return result

    transport, port = DriftTransport(), FakePort()
    with pytest.raises(AgentTransportRefusal, match="frozen authority changed"):
        service(tmp_path, transport, port).run_one(JOB)
    assert port.calls == 0


@pytest.mark.parametrize(
    "fault",
    [
        "unaccepted",
        "revision",
        "outside",
        "symlink",
        "root_permissions",
        "copy_changed",
        "path_traversal",
    ],
)
def test_bad_accepted_source_boundaries_refuse_without_stage(
    tmp_path: Path, fault: str
) -> None:
    transport, port = FakeTransport(), FakePort()
    authority, directory = _accepted(tmp_path, transport)
    if fault == "unaccepted":
        authority.accepted.clear()
    elif fault == "revision":
        current = authority.accepted[TARGET]
        authority.accepted[TARGET] = AcceptedSourceFile(
            PROJECT, TARGET, "other", current.sha256, current.path
        )
    elif fault == "outside":
        current = authority.accepted[TARGET]
        outside = tmp_path / "outside.mov"
        outside.write_bytes(current.path.read_bytes())
        authority.accepted[TARGET] = AcceptedSourceFile(
            PROJECT, TARGET, current.revision, current.sha256, outside
        )
    elif fault == "symlink":
        path = directory / "link.mov"
        path.symlink_to(directory / "clip.mov")
        current = authority.accepted[TARGET]
        authority.accepted[TARGET] = AcceptedSourceFile(
            PROJECT, TARGET, current.revision, current.sha256, path
        )
    elif fault == "root_permissions":
        directory.chmod(0o755)
    elif fault == "copy_changed":
        folder = tmp_path / "private" / "inputs" / JOB
        folder.mkdir(parents=True, mode=0o700)
        (folder / f"source-{TARGET}.bin").write_bytes(b"old wrong bytes")
    elif fault == "path_traversal":
        current = authority.accepted[TARGET]
        outside = directory.parent / "outside.mov"
        outside.write_bytes(current.path.read_bytes())
        authority.accepted[TARGET] = AcceptedSourceFile(
            PROJECT,
            TARGET,
            current.revision,
            current.sha256,
            directory / ".." / outside.name,
        )
    with pytest.raises(AgentTransportRefusal):
        service(
            tmp_path,
            transport,
            port,
            input_authority=authority,
            accepted_source_roots=(directory,),
        ).run_one(JOB)
    assert port.calls == 0


def test_direct_byte_resolver_rejects_wrong_digest(tmp_path: Path) -> None:
    transport = FakeTransport()
    authority, root = _accepted(tmp_path, transport)
    with pytest.raises(FrozenInputRefusal):
        frozen_source_file(
            authority,
            PROJECT,
            TARGET,
            "accepted-v1",
            digest("wrong"),
            (root,),
            tmp_path / "published.bin",
        )
    assert not (tmp_path / "published.bin").exists()
