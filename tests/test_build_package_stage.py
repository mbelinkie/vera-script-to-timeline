"""Compose the actual immutable #177 package and independent attestation."""

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent.build_composition import EffectState, SnapshotRepository
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


@pytest.fixture
def prepared_case(tmp_path: Path):
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


def test_package_writer_reuses_exact_verified_bytes_and_attests(prepared_case) -> None:
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


def test_package_attestation_detects_retained_media_tamper(prepared_case) -> None:
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
