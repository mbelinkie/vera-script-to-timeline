"""New fake seam inputs; #190 helpers and frozen data are read-only sources.

Fresh delivery tests isolate the orchestration seam with a clearly synthetic
accepted-result double. TS tests separately exercise actual A/B/C inference/core.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from issue177_package_fixture import _refresh_document_closure
from issue190_case import make_proof_case, pin, write
from issue190_native_fixture import FakeResolve, fake_controls
from test_workflow_v2 import _FakeAdapter
from vera_timeline_agent.roundtrip_v2_build import PreparedProofBuildV2
from vera_timeline_agent.roundtrip_v2_native import NativeProofBoundaryV2
from vera_timeline_agent.roundtrip_v2_records import proof_source_hashes_v2
from vera_timeline_agent.workflow_v2 import load_verified_package_v2


def boundary_case(
    root: Path,
    evidence: Path,
    *,
    revision: bool = False,
    rate: str = "25fps",
) -> tuple[PreparedProofBuildV2, NativeProofBoundaryV2, FakeResolve, _FakeAdapter]:
    root.mkdir(parents=True)
    request, probe = make_proof_case(root, rate=rate)
    if revision:
        document_path = Path(request["executionInputs"]["document"]["path"])
        dependencies_path = Path(request["executionInputs"]["dependencies"]["path"])
        document = json.loads(document_path.read_bytes())
        dependencies = json.loads(dependencies_path.read_bytes())
        document["title"] += " synthetic revised seam"
        document["liveHeadSequence"] += 1
        document["liveStateVector"] = ""
        dependencies["document"]["revision"] += 1
        for index, key in enumerate(("buildId", "manifestId", "reportId")):
            dependencies["build"][key] = f"00000000-0000-4000-8000-{9000 + index:012x}"
        # Only this new temporary synthetic case is changed, never frozen inputs.
        inputs = document_path.parent
        _refresh_document_closure(
            document,
            dependencies,
            json.loads((inputs / "timeline-manifest.json").read_bytes()),
            json.loads((inputs / "build-report.json").read_bytes()),
        )
        write(document_path, document)
        write(dependencies_path, dependencies)
        request["executionInputs"] = {
            "document": pin(document_path),
            "dependencies": pin(dependencies_path),
        }
        request["originalFiles"] = request["executionInputs"].copy()
        request["originalInputs"] = {
            key: p["sha256"] for key, p in request["executionInputs"].items()
        }
        write(root / "proof-request-v2.json", request)
    build = PreparedProofBuildV2(root, authenticate=lambda *_: None, read_probe=probe)
    build.prepare_package()
    package = load_verified_package_v2(
        build.attestation_path, pin(build.attestation_path)["sha256"][7:]
    )
    resolve = FakeResolve(package)
    # Unique disposable fake identities for the fresh target.
    resolve.project.uid += ":" + root.name
    resolve.project.timeline.uid += ":" + root.name
    adapter = _FakeAdapter()
    boundary = NativeProofBoundaryV2(
        resolve,
        attestation_path=build.attestation_path,
        attestation_hash=pin(build.attestation_path)["sha256"],
        proof_package_path=build.execution / "proof-package.json",
        proof_package_hash=pin(build.execution / "proof-package.json")["sha256"],
        evidence_root=evidence,
        authenticate=lambda *_: None,
        authority=b"synthetic fake authority only",
        code_hashes=proof_source_hashes_v2(),
        read_controls=fake_controls,
        adapter_factory=lambda _: adapter,
    )
    return build, boundary, resolve, adapter


def target(resolve: FakeResolve) -> dict[str, Any]:
    return {
        "projectUid": resolve.project.uid,
        "timelineUid": resolve.project.timeline.uid,
    }
