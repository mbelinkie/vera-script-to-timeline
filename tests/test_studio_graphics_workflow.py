from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import vera_timeline_agent.studio_graphics_workflow as workflow
from test_studio_graphics_adapter import Pool, Seed
from test_workflow_delivery import RecordingAdapter, _native_adapter
from vera_timeline_agent.studio_graphics_runtime import (
    FILE_HASHES,
    TEMPLATE_REL,
    _canonical_json,
    _hash,
    _package_digest,
    transport_artifacts,
)
from vera_timeline_agent.studio_graphics_workflow_cli import (
    LAUNCHER_NAME,
    RELEASE_NAME,
    build_graphics_release,
    prepare_graphic_request,
)
from vera_timeline_agent.studio_spike import ConnectedFacts
from vera_timeline_agent.studio_spike import PublicResolveAdapter as MediaAdapter
from vera_timeline_agent.workflow_package import (
    ATTESTATION_SCHEMA,
    SOURCE_PINS,
    file_inventory,
    read_object,
    sha256,
    write_immutable_json,
)

ROOT = Path(__file__).resolve().parents[1]


def test_graphics_native_boundary_imports_without_site_packages() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-S",
            "-c",
            "import vera_timeline_agent.studio_graphics_workflow",
        ],
        env={**os.environ, "PYTHONPATH": str(ROOT / "python")},
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_graphics_release_is_reproducible_and_has_no_verifier(tmp_path: Path) -> None:
    from vera_timeline_agent.studio_graphics_workflow_cli import build_graphics_release

    one = build_graphics_release(tmp_path / "one")
    two = build_graphics_release(tmp_path / "two")
    assert one.read_bytes() == two.read_bytes()
    files = {entry["path"] for entry in json.loads(one.read_text())["files"]}
    assert any(path.endswith("studio_graphics_workflow.py") for path in files)
    assert not any(path.endswith("/studio_graphics.py") for path in files)
    with pytest.raises(FileExistsError):
        build_graphics_release(tmp_path / "one")


@pytest.fixture
def handoff(tmp_path: Path) -> Path:
    """Synthetic attestation for boundary tests, not verifier/native evidence."""
    root = tmp_path / "package"
    data = ROOT / "tests/data/issue_7"
    manifest = read_object(data / "otis.studio.manifest.golden.json")
    report = read_object(data / "otis.studio.report.golden.json")
    media, media_report = transport_artifacts(manifest, report)
    build_id = manifest["buildId"]
    build = root / "Transport/Builds" / build_id
    build.mkdir(parents=True)
    for source in media["sources"]:
        relative = (
            f"Media/Placeholders/{source['id']}.png"
            if source["kind"] == "placeholder"
            else source["path"]
        )
        artifact = root / "Transport" / relative
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_bytes(b"synthetic unit-test media")
    for directory, values in (
        (root, {"timeline-manifest.json": manifest, "build-report.json": report}),
        (build, {"timeline-manifest.json": media, "build-report.json": media_report}),
    ):
        for name, value in values.items():
            (directory / name).write_bytes(_canonical_json(value))
    template = root / TEMPLATE_REL
    template.mkdir(parents=True)
    for name in FILE_HASHES:
        (template / name).write_bytes(
            (ROOT / "packages/contracts/assets/ev24-lower-third" / name).read_bytes()
        )
    profile = {
        "files": [],
        "compatibility": {"requiredCapabilities": []},
        "rights": {"declarations": [], "allowedProjectIds": []},
    }
    (template / "package-manifest.json").write_bytes(_canonical_json(profile))
    (root / "studio-package.json").write_bytes(
        _canonical_json(
            {
                "manifestHash": _hash(_canonical_json(manifest)),
                "reportHash": _hash(_canonical_json(report)),
                "packageDigest": _package_digest(profile),
            }
        )
    )
    (build / "package-verification.json").write_bytes(
        _canonical_json(
            {
                "status": "ready_to_import",
                "buildId": build_id,
                "manifest": {"contentHash": _hash(_canonical_json(media))},
            }
        )
    )
    transport = write_immutable_json(
        tmp_path / "transport.json",
        {
            "schemaVersion": ATTESTATION_SCHEMA,
            "status": "ready_to_import",
            "sourcePins": SOURCE_PINS,
            "packageDir": str(root / "Transport"),
            "buildId": build_id,
            "projectName": f"VERA Delivery {build_id} 0123456789ab",
            "timelineName": f"VERA Delivery {build_id} 0123456789ab",
            "verifiedAt": "2026-10-15T00:00:00+00:00",
            "verifier": {"implementation": "CPython", "pythonVersion": "3.12.14"},
            "verification": {
                "eventCount": len(media["events"]),
                "markerCount": len(media["markers"]),
                "mediaCount": len(media["sources"]),
            },
            "packageFiles": file_inventory(root / "Transport"),
        },
    )
    value = read_object(transport)
    return write_immutable_json(
        tmp_path / "graphic.json",
        {
            **{
                key: value[key]
                for key in (
                    "buildId",
                    "projectName",
                    "timelineName",
                    "verifier",
                    "verifiedAt",
                )
            },
            "schemaVersion": workflow.GRAPHIC_ATTESTATION,
            "status": "ready_for_studio",
            "sourcePins": workflow.GRAPHIC_PINS,
            "packageDir": str(root),
            "packageFiles": file_inventory(root),
            "transportAttestationPath": str(transport),
            "transportAttestationSha256": sha256(transport),
        },
    )


@pytest.mark.parametrize(
    "failure", [None, "atlas", "manifest", "extra", "transport", "symlink"]
)
def test_handoff_binds_the_entire_graphic_envelope(
    handoff: Path, failure: str | None
) -> None:
    verified = workflow.load_graphic_handoff(handoff, sha256(handoff))
    root = verified.root
    if failure is None:
        assert verified.manifest["buildId"] == verified.transport.manifest["buildId"]
        return
    if failure == "atlas":
        (root / TEMPLATE_REL / "ev24_badges_atlas.png").write_bytes(b"tampered")
    elif failure == "manifest":
        (root / "timeline-manifest.json").write_bytes(b"{}")
    elif failure == "extra":
        (root / "extra.setting").write_text("not attested")
    elif failure == "transport":
        next((root / "Transport/Builds").glob("*/build-report.json")).write_bytes(b"{}")
    else:
        (root / "link").symlink_to(root / "timeline-manifest.json")
    with pytest.raises(ValueError):
        workflow.load_graphic_handoff(handoff, sha256(handoff))


@pytest.mark.parametrize(
    "failure", [None, "unauthorized", "version", "target", "changed"]
)
def test_injected_runner_preserves_authorization_version_and_stage_guards(
    handoff: Path,
    monkeypatch: pytest.MonkeyPatch,
    failure: str | None,
) -> None:
    package = workflow.load_graphic_handoff(handoff, sha256(handoff))

    def mutate() -> None:
        (package.root / "extra").write_text("stale")

    class GraphicRecordingAdapter(RecordingAdapter):
        def __init__(self, **kwargs: Any) -> None:
            super().__init__(**kwargs)
            self.graphic_observations: list[dict[str, Any]] = []

        def verify(self, manifest: Any) -> tuple[str, ...]:
            self._record("verify", manifest["buildId"])
            return self.discrepancies

    adapter = GraphicRecordingAdapter(
        connected=ConnectedFacts(
            "DaVinci Resolve Studio",
            "studio",
            "21.1.1",
            "11" if failure == "version" else "10",
            True,
        ),
        fail_on="assert_current_target" if failure == "target" else None,
        mutate_after="create_project" if failure == "changed" else None,
        mutate=mutate,
    )
    monkeypatch.setattr(workflow, "InjectedGraphicAdapter", lambda *_: adapter)
    result = workflow.run_graphic_delivery(
        object(),
        handoff,
        sha256(handoff),
        action="build",
        authorize_new_nonproduction=failure != "unauthorized",
        external_scripting="None",
    )
    assert result["verified"] is (failure is None), result.get("message")
    names = [name for name, _ in adapter.calls]
    if failure in {"unauthorized", "version"}:
        assert "create_project" not in names
    elif failure in {"target", "changed"}:
        assert names[-1] == "create_project"
        assert result["partialTargetRetained"] is True
    else:
        assert names[-1] == "verify"


@pytest.mark.parametrize(
    "failure", [None, "extra", "missing", "wrong-folder", "path", "duplicate-bin"]
)
def test_injected_inventory_checks_regular_and_template_bins(
    handoff: Path,
    failure: str | None,
) -> None:
    package = workflow.load_graphic_handoff(handoff, sha256(handoff))
    adapter = workflow.InjectedGraphicAdapter(None, package, lambda: None)
    graphics = [
        s["id"] for s in package.manifest["sources"] if s["kind"] == "fusion_template"
    ]
    ids = [s["id"] for s in package.transport.manifest["sources"]]
    adapter.created_bins = ["VERA Studio Assembly", "Package Media"]
    adapter.media_id_by_source = {s: s for s in ids}
    adapter.expected_paths = {s: Path("/package") / f"{s}.png" for s in ids}

    def clip(identity: str) -> Any:
        return SimpleNamespace(
            GetMediaId=lambda: identity,
            GetClipProperty=lambda _: str(
                adapter.expected_paths.get(identity, "/extra")
            ),
        )

    def folder(name: str, clips: list[Any], children: list[Any]) -> Any:
        return SimpleNamespace(
            GetName=lambda: name,
            GetUniqueId=lambda: name,
            GetClipList=lambda: clips,
            GetSubFolderList=lambda: children,
        )

    template_clips = [clip(s) for s in graphics]
    regular_clips = [clip(s) for s in ids if s not in graphics]
    templates = folder(adapter.template_bin_name, template_clips, [])
    media = folder("Package Media", regular_clips, [])
    children = [folder("VERA Studio Assembly", [], [media]), templates]
    root_clips: list[Any] = []
    if failure == "extra":
        root_clips.append(clip("extra"))
    elif failure == "missing":
        template_clips.clear()
    elif failure == "wrong-folder":
        regular_clips.extend(template_clips)
        template_clips.clear()
    elif failure == "path":
        template_clips[0].GetClipProperty = lambda _: "/wrong/atlas.png"
    elif failure == "duplicate-bin":
        children.append(folder(adapter.template_bin_name, [], []))
    adapter.pool = SimpleNamespace(
        GetRootFolder=lambda: folder("root", root_clips, children)
    )
    adapter.timeline = SimpleNamespace(GetMediaPoolItem=lambda: None)
    assert bool(adapter._verify_media_inventory(package.transport.manifest)) is (
        failure is not None
    )


def test_installed_graphics_release_is_stdlib_only_and_refuses_tamper(
    handoff: Path,
    tmp_path: Path,
) -> None:
    release = tmp_path / "release"
    build_graphics_release(release)
    prepare_graphic_request(
        handoff, release, release / RELEASE_NAME / "request.json", tmp_path / "evidence"
    )
    first = subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "stopped_safely" in first.stdout
    assert "No module named" not in first.stdout
    runtime = (
        release / RELEASE_NAME / "python/vera_timeline_agent/studio_graphics_runtime.py"
    )
    runtime.write_text(runtime.read_text() + "\n# altered\n")
    second = subprocess.run(
        [sys.executable, "-S", str(release / LAUNCHER_NAME)],
        capture_output=True,
        text=True,
        check=True,
    )
    assert "installed source differs" in second.stdout
    assert len(list((tmp_path / "evidence").glob("result-*.json"))) == 1
    assert len(list((tmp_path / "evidence").glob("bootstrap-refusal-*.json"))) == 1


@pytest.mark.parametrize(
    "authorize,none", [(False, False), (True, False), (False, True)]
)
def test_request_cannot_infer_operator_authorizations(
    handoff: Path, tmp_path: Path, authorize: bool, none: bool
) -> None:
    release = tmp_path / "release"
    build_graphics_release(release)
    with pytest.raises(ValueError, match="both operator"):
        prepare_graphic_request(
            handoff,
            release,
            tmp_path / "request.json",
            tmp_path / "evidence",
            action="build",
            authorize_new_nonproduction=authorize,
            external_scripting_none=none,
        )
    assert not (tmp_path / "request.json").exists()


@pytest.mark.parametrize("switched", [False, True])
def test_graphics_adapter_uses_guarded_uid_preserving_reopen(
    handoff: Path, switched: bool
) -> None:
    package = workflow.load_graphic_handoff(handoff, sha256(handoff))
    adapter = workflow.InjectedGraphicAdapter(None, package, lambda: None)
    native, calls = _native_adapter(
        current_id="other" if switched else "created-project"
    )
    adapter.__dict__.update(native.__dict__)
    if switched:
        with pytest.raises(ValueError, match="current project changed"):
            adapter.save_close_reopen("target")
        assert calls == []
    else:
        adapter.save_close_reopen("target")
        assert calls == ["save", "close", "load"]
        adapter.assert_current_target()
    assert adapter._still_end_frame_compensation() == 0


def test_real_injected_wiring_restores_paths_and_never_imports_external_verifier(
    handoff: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package = workflow.load_graphic_handoff(handoff, sha256(handoff))
    calls: list[str] = []
    adapter = workflow.InjectedGraphicAdapter(
        None, package, lambda: calls.append("guard")
    )
    adapter.pool = Pool()
    source_ids = [source["id"] for source in package.manifest["sources"]]
    sources = [(identity, package.root / f"{identity}.png") for identity in source_ids]

    def import_media(base: Any, entries: Any) -> None:
        base.media_by_source = {identity: Seed(identity) for identity, _ in entries}
        base.media_id_by_source = {identity: identity for identity, _ in entries}
        base.pool.current.seeds.extend(base.media_by_source.values())

    monkeypatch.setattr(MediaAdapter, "import_media", import_media)
    monkeypatch.setitem(sys.modules, "vera_timeline_agent.studio_graphics", None)
    adapter.import_media(sources)
    assert adapter.expected_paths == {
        identity: path.resolve() for identity, path in sources
    }
    assert set(adapter.media_id_by_source) == set(source_ids)
    assert len(adapter.pool.root.children) == 1
    assert adapter.pool.root.children[0].GetName() == adapter.template_bin_name
    adapter.verify_package()
    assert calls == ["guard"]


def test_graphic_attestation_parses_exact_hashed_bytes(
    handoff: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = sha256(handoff)
    original_read = read_object
    original_bytes = Path.read_bytes
    calls: list[Path] = []

    def read_checked(path: Path) -> dict[str, Any]:
        assert path != handoff, (
            "attestation must be parsed from hashed bytes, not reopened"
        )
        return original_read(path)

    def read_bytes(path: Path) -> bytes:
        if path == handoff:
            calls.append(path)
        return original_bytes(path)

    monkeypatch.setattr(workflow, "read_object", read_checked)
    monkeypatch.setattr(Path, "read_bytes", read_bytes)
    workflow.load_graphic_handoff(handoff, expected)
    assert calls == [handoff]


def test_early_graphic_refusal_keeps_result_schema(tmp_path: Path) -> None:
    result = workflow.run_graphic_delivery(None, tmp_path / "missing.json", "0" * 64)
    assert result["schemaVersion"] == "vera-studio-graphic-result/v1"
    assert result["action"] == "preflight"
    assert result["sourcePins"] == workflow.GRAPHIC_PINS
    assert result["discrepancies"] == []
    assert result["verified"] is False


def test_graphic_attestation_refuses_non_object_json(tmp_path: Path) -> None:
    path = tmp_path / "array.json"
    path.write_text("[]")
    with pytest.raises(ValueError, match="one JSON object"):
        workflow.load_graphic_handoff(path, sha256(path))
