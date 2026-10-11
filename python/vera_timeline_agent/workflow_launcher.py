"""Audited operator request and unique evidence for the installed script."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from .workflow_delivery import run_workflow_delivery
from .workflow_package import read_object, sha256, write_immutable_json


def run_installed_request(resolve: Any, request_path: Path) -> Path:
    request = read_object(request_path)
    if request.get("schemaVersion") != "vera-injected-delivery-request/v1":
        raise ValueError("unsupported operator request")
    attestation_path = Path(request["attestationPath"])
    evidence = Path(request["evidenceDir"])
    if not attestation_path.is_absolute() or not evidence.is_absolute():
        raise ValueError("attestation/evidence paths must be absolute")
    package_path = Path(request["packageDir"])
    if not package_path.is_absolute():
        raise ValueError("package path must be absolute")
    root = package_path.resolve()
    if attestation_path.exists():
        actual_root = Path(read_object(attestation_path)["packageDir"]).resolve()
        if root != actual_root:
            raise ValueError("request package identity differs from attestation")
    if evidence.resolve().is_relative_to(root):
        raise ValueError("evidence must be outside the ready package")
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    context = {
        "requestSha256": sha256(request_path),
        "releaseSha256": request["releaseSha256"],
        "attestationSha256": request["attestationSha256"],
        "requestedProjectName": request["projectName"],
        "requestedTimelineName": request["timelineName"],
    }
    write_immutable_json(evidence / f"started-{run_id}.json", context)
    result = run_workflow_delivery(
        resolve,
        attestation_path,
        request["attestationSha256"],
        action=request["action"],
        authorize_new_nonproduction=request["authorizeNewNonproduction"],
        external_scripting=request["externalScripting"],
    )
    result.update(context)
    report = write_immutable_json(evidence / f"result-{run_id}.json", result)
    write_immutable_json(
        evidence / f"hashes-{run_id}.json",
        {"resultPath": str(report), "resultSha256": sha256(report), **context},
    )
    return report
