"""External render storage stays pinned to one private native target."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from test_issue209_native import _approval, _context
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent import qualification_output_proof_v2 as proof
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    OutputConsistencyError,
    _canonical,
    _json_hash,
)


def test_external_location_is_private_per_target_and_cannot_be_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", state)
    context = _context()
    default = native.render_parent(context)
    assert default.parent == state / "renders"
    root = tmp_path / "external"
    root.mkdir(mode=0o700)
    native.register_render_root(context, root)
    assert native.render_parent(context) == root / default.name
    location = state / "targets" / default.name / "render-location.json"
    assert location.stat().st_mode & 0o777 == 0o400
    native.register_render_root(context, root)
    other = tmp_path / "other"
    other.mkdir(mode=0o700)
    with pytest.raises(OutputConsistencyError, match="render root differs"):
        native.register_render_root(context, other)
    edited = json.loads(json.dumps(context))
    edited["phase"] = "edited"
    projection = {
        k: v
        for k, v in edited.items()
        if k not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {"kind": "baseline"}
    edited["binding"]["bindingSha256"] = _json_hash(projection)
    assert native.render_parent(edited).parent == state / "renders"
    root.chmod(0o755)
    with pytest.raises(OutputConsistencyError, match="private owned render root"):
        native.render_parent(context)


def test_render_location_refuses_links_and_existing_operations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path / "state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", state)
    context = _context()
    root = tmp_path / "external"
    root.mkdir(mode=0o700)
    alias = tmp_path / "alias"
    alias.symlink_to(root, target_is_directory=True)
    with pytest.raises(OutputConsistencyError, match="symlink"):
        native.register_render_root(context, alias)
    parent = state / "targets" / native.render_parent(context).name
    (parent / "operations").mkdir(parents=True)
    with pytest.raises(OutputConsistencyError, match="operation already exists"):
        native.register_render_root(context, root)


def test_revised_session_checks_inherited_root_before_reservation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    preflight = tmp_path / "preflight.json"
    preflight.write_bytes(b"{}")
    baseline = SimpleNamespace(context={"target": {"timelineUid": "old"}})
    fake_proof = SimpleNamespace(
        prepare_revised_preflight=lambda: preflight, baseline=baseline
    )
    monkeypatch.setattr(proof, "QualificationOutputProofV2", lambda *_: fake_proof)
    monkeypatch.setattr(
        package, "admit_qualification_revision_v2", lambda *_args, **_kwargs: object()
    )

    def unavailable(_context: object) -> Path:
        raise OutputConsistencyError("private owned render root required")

    monkeypatch.setattr(native, "render_parent", unavailable)
    with pytest.raises(OutputConsistencyError, match="private owned render root"):
        proof.prepare_revised_output_session(
            tmp_path / "revised",
            proof_session=tmp_path / "proof",
            proof_sha256="0" * 64,
            package_root=tmp_path / "package",
            preparation_paths={},
            target={"timelineUid": "new"},
        )


def test_approval_pins_selected_volume_and_refuses_location_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = tmp_path.resolve() / "state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", state)
    approval, context = _approval(tmp_path, profile=native.R16_PROFILE)
    root = tmp_path.resolve() / "external"
    root.mkdir(mode=0o700)
    native.register_render_root(context, root)
    approval["outputPath"] = str(native.render_parent(context) / "approved.mov")
    raw = _canonical(approval)

    def verify() -> None:
        native.verify_operator_approval(
            raw,
            context=context,
            profile=native.R16_PROFILE,
            admission_sha256=approval["admissionSha256"],
            release_manifest_sha256=approval["releaseManifestSha256"],
        )

    verify()
    location = (
        state / "targets" / native.render_parent(context).name / "render-location.json"
    )
    other = tmp_path.resolve() / "other"
    other.mkdir(mode=0o700)
    value = json.loads(location.read_bytes())
    value["root"] = str(other)
    location.chmod(0o600)
    location.write_bytes(_canonical(value))
    location.chmod(0o400)
    with pytest.raises(OutputConsistencyError, match="private per-case MOV location"):
        verify()
