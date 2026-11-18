"""Prepare one synthetic frozen Studio submission; never dispatch Resolve.

Run once with a new absolute private directory. The resulting service store and
attested package are inputs to the separately guarded native acceptance step.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

from vera_timeline_agent.build_agent_service import (
    LocalBuildAgentService,
    QualifiedStagePipeline,
)
from vera_timeline_agent.build_media_stage import (
    MediaStageAuthorization,
    MediaStagePort,
)
from vera_timeline_agent.build_narration_stage import NarrationStagePort
from vera_timeline_agent.build_package_stage import PackageStagePort
from vera_timeline_agent.build_studio_parent_driver import ParentStudioDriver
from vera_timeline_agent.build_studio_readback import ConnectedStillReadback
from vera_timeline_agent.build_studio_stage import (
    BuildStudioStagePort,
    NativeAuthorization,
    NativeDriver,
    VerifyStudioStagePort,
)
from vera_timeline_agent.build_submission_inputs import (
    AcceptedSourceFile,
    checked_compiler_dependencies,
)
from vera_timeline_agent.local_media_import import FFmpegDecoder
from vera_timeline_agent.media_preparation import (
    MediaTools,
    PreparationAuthorization,
    wire,
)
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.v2_package import _compiler_hash
from vera_timeline_agent.workflow_package import sha256
from vera_timeline_agent.workflow_v2_cli import build_release_v2
from vera_timeline_agent.workflow_v2_cli import main as delivery_cli

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))
from test_issue603_still_preparation import _descriptor  # noqa: E402

from scripts.issue336_studio_qualify import png  # noqa: E402


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


class Transport:
    def __init__(self, value: dict[str, Any]) -> None:
        self.value = value

    def claim(self, job_id: str) -> tuple[int, str]:
        assert job_id == self.value["jobId"]
        return 1, self.value["snapshotDigest"]

    def frozen(self, job_id: str, epoch: int) -> dict[str, Any]:
        assert (job_id, epoch) == (self.value["jobId"], 1)
        return dict(self.value)

    def progress(self, *args: Any) -> None:
        print("progress", args[2:], flush=True)

    def inspect(self, *args: Any) -> None:
        print("inspected receipt", args[2:], flush=True)


class Authority:
    def __init__(
        self, record: AcceptedSourceFile, dependencies: dict[str, Any]
    ) -> None:
        self.record = record
        self.dependencies = dependencies

    def accepted_source(
        self, project_id: str, source_id: str, revision: str
    ) -> AcceptedSourceFile | None:
        record = self.record
        return (
            record
            if (project_id, source_id, revision)
            == (record.project_id, record.source_id, record.revision)
            else None
        )

    def frozen_dependencies(
        self, project_id: str, job_id: str
    ) -> dict[str, Any] | None:
        return self.dependencies


def main(root: Path) -> None:
    root = root.absolute()
    if any(part.is_symlink() for part in (root, *root.parents)) or root.exists():
        raise ValueError("use a new absolute path without symbolic links")
    root.mkdir(mode=0o700, parents=True)
    accepted = root / "accepted"
    accepted.mkdir(mode=0o700)
    source = accepted / "generated.png"
    png(source, 1600, 900)
    tools = MediaTools()
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    finally:
        os.close(fd)
    fixture = json.loads(
        (
            ROOT
            / "tests/data/authoring_v2/issue_173/compiler"
            / "visual-only-image-still-25fps-default.input.golden.json"
        ).read_bytes()
    )
    document, deps = fixture["document"], fixture["dependencies"]
    block = document["activeDraft"]["blocks"][0]
    block["payload"].pop("framingPolicy")
    document["liveContentHash"] = _compiler_hash(
        {k: v for k, v in document.items() if k != "liveContentHash"}
    )
    descriptor = _descriptor(source, facts, Fraction(24000, 1001))
    old = deps["occurrenceResolutions"][0]
    descriptor.update(
        payloadId=old["payloadId"],
        owner=old["owner"],
        mediaReferenceId=old["mediaReferenceId"],
    )
    # _descriptor includes the source ID in the snapshot and map hash; bind it
    # to the compiler's original selected media reference as well.
    descriptor["sourceSnapshot"]["snapshotId"] = old["mediaReferenceId"]
    probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": facts.width,
        "height": facts.height,
        "frames": 1,
    }
    descriptor["sourceFrameMap"]["descriptorHash"] = identity_hash(
        {"snapshot": descriptor["sourceSnapshot"], "probe": probe}
    )
    deps["timeline"]["frameRate"] = wire(Fraction(24000, 1001))
    deps["timeline"]["durationFrames"] = 72
    deps["occurrenceResolutions"] = [descriptor]
    deps["preparedMedia"] = []
    project = document["projectId"]
    job = deps["build"]["buildId"]
    target = "00000000-0000-4000-8000-000000006039"
    raw_document = json.dumps(document, sort_keys=True, separators=(",", ":"))
    settings = json.dumps({"projectId": project}, sort_keys=True, separators=(",", ":"))
    deps["document"]["contentHash"] = document["liveContentHash"]
    deps["document"]["settingsHash"] = digest(settings.encode())
    deps["authoringDefaults"]["settingsHash"] = digest(settings.encode())
    source_id = descriptor["mediaReferenceId"]
    source_hash = digest(source.read_bytes())
    manifest = {
        "projectId": project,
        "jobId": job,
        "targetId": target,
        "snapshotDigest": "sha256:" + "f" * 64,
        "documentJson": raw_document,
        "documentDigest": digest(raw_document.encode()),
        "documentRevision": deps["document"]["revision"],
        "settingsJson": settings,
        "settingsDigest": digest(settings.encode()),
        "settingsRevision": 1,
        "selectedSources": [
            {"sourceId": source_id, "revision": "generated-v1", "sha256": source_hash}
        ],
        "buildClass": deps["build"]["buildClass"],
        "mode": "studio",
    }
    authority = Authority(
        AcceptedSourceFile(project, source_id, "generated-v1", source_hash, source),
        deps,
    )
    checked_compiler_dependencies(
        deps, manifest, {source_id: ("generated-v1", source_hash)}
    )
    transport = Transport(manifest)
    service = cast(
        NarrationService,
        SimpleNamespace(provider=SimpleNamespace(adapter_version="synthetic-empty/v1")),
    )
    narrator = NarrationStagePort(service)
    write_root = root / "service" / "outputs"

    def make(snapshot: str, enabled: bool) -> LocalBuildAgentService:
        preparation = PreparationAuthorization(
            "issue633-synthetic",
            (root / "service" / "inputs",),
            write_root,
            identity_hash(tools.fingerprint()),
            minimum_free_bytes=0,
        )
        media = MediaStagePort(
            MediaStageAuthorization(project, snapshot, preparation, {}), tools=tools
        )
        auth = NativeAuthorization(
            project,
            snapshot,
            "0" * 64,
            "issue633-one-use",
            enabled,
            route="Local",
            job_id=job,
            target_id=target,
        )
        driver = cast(NativeDriver, object())
        pipeline = QualifiedStagePipeline(
            narrator,
            media,
            PackageStagePort(),
            BuildStudioStagePort(auth, driver),
            VerifyStudioStagePort(auth, driver),
        )
        return LocalBuildAgentService(
            root / "service",
            project,
            transport,
            input_authority=authority,
            accepted_source_roots=(accepted,),
            pipeline=pipeline,
        )

    initial = make("0" * 64, False)
    if initial.run_one(job) != "needs_action":
        raise RuntimeError("expected exact snapshot authorization fence")
    snapshots = list((root / "service" / "snapshots").glob("*.json"))
    if len(snapshots) != 1:
        raise RuntimeError("expected one frozen snapshot")
    snapshot = snapshots[0].stem
    active = make(snapshot, True)
    for _ in range(5):
        status = active.run_one(
            job, resumed_epoch=1, resumed_digest=manifest["snapshotDigest"]
        )
        if status != "queued":
            raise RuntimeError(f"core stage did not complete: {status}")
    print(
        json.dumps(
            {
                "snapshot": snapshot,
                "job": job,
                "project": project,
                "target": target,
                "serviceRoot": str(root / "service"),
                "note": "Core stages only; no native operation was dispatched.",
            },
            indent=2,
        )
    )


def resume(root: Path, phase: str) -> None:
    root = root.absolute()
    if any(p.is_symlink() for p in (root, *root.parents)):
        raise ValueError("unsafe root")
    inputs_root = root / "service" / "inputs"
    jobs = list(inputs_root.iterdir())
    if len(jobs) != 1:
        raise ValueError("expected one frozen job")
    inputs = jobs[0]
    manifest = json.loads((inputs / "submission.json").read_bytes())
    manifest["documentJson"] = (inputs / "document.json").read_text()
    manifest["settingsJson"] = (inputs / "settings.json").read_text()
    deps = json.loads((inputs / "dependencies.json").read_bytes())
    pin = manifest["selectedSources"][0]
    job, project, target = (
        manifest["jobId"],
        manifest["projectId"],
        manifest["targetId"],
    )
    authority = Authority(
        AcceptedSourceFile(
            project,
            pin["sourceId"],
            pin["revision"],
            pin["sha256"],
            root / "accepted" / "generated.png",
        ),
        deps,
    )
    snapshots = list((root / "service" / "snapshots").glob("*.json"))
    if len(snapshots) != 1:
        raise ValueError("expected one snapshot")
    snapshot = snapshots[0].stem
    with sqlite3.connect(root / "service" / "jobs" / "build-jobs.sqlite3") as conn:
        rows = conn.execute("SELECT id, status, active_stage FROM jobs").fetchall()
    expected_status = "waiting" if phase == "reconcile" else "queued"
    if len(rows) != 1 or rows[0][1] != expected_status or rows[0][2] is not None:
        raise ValueError(f"job is not safely queued: {rows}")
    local_job = rows[0][0]
    output = root / "service" / "outputs"
    tools = MediaTools()
    prep = PreparationAuthorization(
        "issue633-synthetic",
        (inputs_root,),
        output,
        identity_hash(tools.fingerprint()),
        minimum_free_bytes=0,
    )
    media = MediaStagePort(
        MediaStageAuthorization(project, snapshot, prep, {}), tools=tools
    )
    narrator = NarrationStagePort(
        cast(
            NarrationService,
            SimpleNamespace(
                provider=SimpleNamespace(adapter_version="synthetic-empty/v1")
            ),
        )
    )
    request_id = "issue633-one-use"
    attestation = output / local_job / "v2-attestation.json"
    if phase in ("native", "reconcile"):
        if not attestation.is_file():
            raise ValueError("verified package attestation missing")
        release = root / "release"
        request = release / "vera-delivery-v2" / "request.json"
        if phase == "native":
            if release.exists():
                raise ValueError(
                    "release already exists; refuse repeated native dispatch"
                )
            build_release_v2(release)
            rc = delivery_cli(
                [
                    "request",
                    str(attestation),
                    "--release",
                    str(release),
                    "--output",
                    str(request),
                    "--evidence-dir",
                    str(root / "native-evidence"),
                    "--action",
                    "build",
                    "--authorize-new-nonproduction",
                    "--external-scripting-local",
                ]
            )
            if rc:
                raise ValueError("request preparation refused")
        request_hash = sha256(request)
        readback = ConnectedStillReadback(request, request_hash, request_id)
        driver: Any = ParentStudioDriver(
            request,
            request_hash,
            request_id,
            Path(
                "/Applications/DaVinci Resolve 21.2/DaVinci Resolve.app"
                "/Contents/Resources/ResolvePython/ResolvePython"
            ),
            reopened_readback=readback,
            wait_seconds=50,
        )
        auth = NativeAuthorization(
            project,
            snapshot,
            sha256(attestation),
            request_id,
            True,
            route="Local",
            job_id=job,
            target_id=target,
            expires_at=time.time() + 3600,
            current_authority=lambda: True,
        )
    elif phase == "core":
        driver = cast(NativeDriver, object())
        auth = NativeAuthorization(
            project,
            snapshot,
            "0" * 64,
            request_id,
            True,
            route="Local",
            job_id=job,
            target_id=target,
        )
    else:
        raise ValueError("phase must be core or native")
    pipeline = QualifiedStagePipeline(
        narrator,
        media,
        PackageStagePort(),
        BuildStudioStagePort(auth, driver),
        VerifyStudioStagePort(auth, driver),
    )
    service = LocalBuildAgentService(
        root / "service",
        project,
        Transport(manifest),
        input_authority=authority,
        accepted_source_roots=(root / "accepted",),
        pipeline=pipeline,
    )
    if phase == "reconcile":
        result = driver.inspect_build(attestation, sha256(attestation), request_id)
        if result.get("status") != "verified" or result.get("verified") is not True:
            raise ValueError("parent is not verified; inspect only, do not retry")
        service.store.resume(project, local_job)
    for _ in range(5 if phase == "core" else 2):
        state = service.store.status(project, local_job)
        remaining = [s["name"] for s in state["stages"] if s["status"] == "requested"]
        if not remaining or (
            phase == "core" and remaining[0] == "building_resolve_timeline"
        ):
            break
        result = service.run_one(
            job, resumed_epoch=1, resumed_digest=manifest["snapshotDigest"]
        )
        print("service result", result, flush=True)
        if result not in ("queued", "complete"):
            raise RuntimeError(f"stop; inspect retained state: {result}")
    print(json.dumps(service.store.status(project, local_job), indent=2))


if __name__ == "__main__":
    if len(sys.argv) == 2:
        main(Path(sys.argv[1]))
    elif len(sys.argv) == 3:
        resume(Path(sys.argv[2]), sys.argv[1])
    else:
        raise SystemExit(
            "usage: issue633_frozen_probe.py NEW_ROOT | core ROOT | native ROOT"
        )
