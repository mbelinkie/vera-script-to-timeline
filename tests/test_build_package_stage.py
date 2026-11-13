"""Compose the actual immutable #177 package and independent attestation."""

import hashlib
import json
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from issue177_package_fixture import PackageCase, make_package_case
from vera_timeline_agent import v2_package, workflow_v2
from vera_timeline_agent.build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    SnapshotRepository,
)
from vera_timeline_agent.build_jobs import (
    BuildJobError,
    StageContext,
    publish_immutable_output,
)
from vera_timeline_agent.build_package_stage import (
    PackageStagePort,
    VerifyPackageStagePort,
    package_root,
)
from vera_timeline_agent.v2_package import V2PackageError, verify_v2_package
from vera_timeline_agent.workflow_package import sha256

PreparedCase = tuple[
    PackageCase, FrozenBuildSnapshot, Callable[[str], StageContext], dict[str, Path]
]


@pytest.fixture
def prepared_case(tmp_path: Path) -> PreparedCase:
    fixture = make_package_case(tmp_path / "fixture")
    dependencies = json.loads(fixture.dependencies_path.read_bytes())
    project_id = dependencies["document"]["projectId"]
    build_id = dependencies["build"]["buildId"]
    head = dependencies["document"]
    sources = {f"media:{key}": path for key, path in fixture.media_paths.items()}
    roots = (
        fixture.document_path.parent,
        *(p.parent for p in fixture.media_paths.values()),
    )
    repo = SnapshotRepository(
        tmp_path / "snapshots",
        read_roots=roots,
        write_root=tmp_path / "outputs",
        live_head=lambda _: (
            head["liveHeadSequence"],
            head["contentHash"].removeprefix("sha256:"),
            "rev-1",
        ),
        live_settings=lambda _: "f" * 64,
    )
    snap = repo.freeze(
        project_id=project_id,
        mode="free",
        build_id=build_id,
        build_class="preview",
        settings_hash="f" * 64,
        inputs={
            "document": fixture.document_path,
            "dependencies": fixture.dependencies_path,
            **sources,
        },
        adapter_versions={
            "v2-package": "v2-package/v1",
            "v2-attestation": "vera-injected-delivery-attestation/v2",
        },
    )
    job_id = "job-157"

    def ctx(stage: str) -> StageContext:
        return StageContext(
            project_id,
            job_id,
            snap.snapshot_id,
            stage,
            hashlib.sha256(f"{project_id}\0{job_id}\0{stage}".encode()).hexdigest(),
            tmp_path / "stage-receipts" / stage / "output",
            1,
            1,
            lambda _: None,
            lambda: None,
        )

    output = snap.write_root / job_id
    (output / "compiling").mkdir(parents=True)
    (output / "resolving_media").mkdir()
    shutil.copyfile(
        fixture.manifest_path, output / "compiling" / "timeline-manifest.json"
    )
    shutil.copyfile(fixture.report_path, output / "compiling" / "build-report.json")
    shutil.copyfile(
        fixture.dependencies_path,
        output / "resolving_media" / "compiler-dependencies.json",
    )
    new_prep: dict[str, str] = {}
    for key, path in fixture.preparation_paths.items():
        new_path = output / "resolving_media" / path.name
        shutil.copyfile(path, new_path)
        new_prep[key] = str(new_path)
    publish_immutable_output(
        output / "resolving_media" / "preparation-paths.json",
        (json.dumps(new_prep, sort_keys=True, separators=(",", ":")) + "\n").encode(),
    )
    return fixture, snap, ctx, sources


def test_package_writer_reuses_exact_verified_bytes_and_attests(
    prepared_case: PreparedCase,
) -> None:
    _fixture, snapshot, ctx, sources = prepared_case
    port = PackageStagePort(
        extra_media={key.removeprefix("media:"): key for key in sources}
    )
    writing = ctx("writing_interchange")
    assert port.inspect(writing, snapshot).state == EffectState.ABSENT
    port.execute(writing, snapshot)
    assert port.inspect(writing, snapshot).state == EffectState.VERIFIED
    root = package_root(writing, snapshot)
    assert verify_v2_package(root).build_id == snapshot.build_id
    # Idempotent package writer compares complete inventory and bytes.
    port.execute(writing, snapshot)
    assert port.inspect(writing, snapshot).state == EffectState.VERIFIED
    import_port = VerifyPackageStagePort()
    imported = ctx("verifying_import_package")
    assert import_port.inspect(imported, snapshot).state == EffectState.ABSENT
    import_port.execute(imported, snapshot)
    assert import_port.inspect(imported, snapshot).state == EffectState.VERIFIED
    with pytest.raises(Exception, match="existing attestation"):
        import_port.execute(imported, snapshot)


def test_stage_port_is_still_explicitly_uncached(
    prepared_case: PreparedCase, monkeypatch: pytest.MonkeyPatch
) -> None:
    _fixture, snapshot, ctx, sources = prepared_case

    def prohibited_cache(_root: Path) -> None:
        pytest.fail("alternate package stage must not implicitly enable the cache")

    monkeypatch.setattr(v2_package, "PackageCache", prohibited_cache)
    port = PackageStagePort(
        extra_media={key.removeprefix("media:"): key for key in sources}
    )
    port.execute(ctx("writing_interchange"), snapshot)
    assert (
        port.inspect(ctx("writing_interchange"), snapshot).state == EffectState.VERIFIED
    )


def test_package_attestation_detects_retained_media_tamper(
    prepared_case: PreparedCase,
) -> None:
    _fixture, snap, ctx, sources = prepared_case
    writer = PackageStagePort(
        extra_media={key.removeprefix("media:"): key for key in sources}
    )
    writing = ctx("writing_interchange")
    writer.execute(writing, snap)
    verify = VerifyPackageStagePort()
    imported = ctx("verifying_import_package")
    verify.execute(imported, snap)
    root = package_root(writing, snap)
    media = next((root / "Media").rglob("*.mov"))
    media.write_bytes(b"tampered bytes")
    with pytest.raises((V2PackageError, ValueError, BuildJobError)):
        verify.inspect(imported, snap)


def test_issue336_stages_attest_original_otio_without_rewriting_prior_output(
    prepared_case: PreparedCase,
) -> None:
    """The Studio native route consumes the stage's exact immutable OTIO file."""
    _fixture, snapshot, ctx, sources = prepared_case
    writer = PackageStagePort(
        extra_media={key.removeprefix("media:"): key for key in sources}
    )
    writing = ctx("writing_interchange")
    writer.execute(writing, snapshot)
    root = package_root(writing, snapshot)
    before = {
        path.relative_to(root).as_posix(): sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    verify = VerifyPackageStagePort()
    imported = ctx("verifying_import_package")
    verify.execute(imported, snapshot)
    attestation = verify.attestation(imported, snapshot)
    loaded = workflow_v2.load_verified_package_v2(attestation, sha256(attestation))
    native_otio = workflow_v2._verify_native_otio_plan(loaded)
    assert loaded.root == root
    assert native_otio == root / "Builds" / snapshot.build_id / "timeline.otio"
    assert not workflow_v2._requires_native_otio(loaded.view)
    assert before == {
        path.relative_to(root).as_posix(): sha256(path)
        for path in root.rglob("*")
        if path.is_file()
    }
    # A second attestation is never an invitation to mutate or replay a build.
    with pytest.raises(Exception, match="existing attestation"):
        verify.execute(imported, snapshot)
    assert verify_v2_package(root).build_id == snapshot.build_id
