"""Audited operator request and unique evidence for the installed script."""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .workflow_delivery import run_workflow_delivery
from .workflow_package import (
    load_verified_package,
    read_object,
    sha256,
    write_immutable_json,
)


def run_installed_request(
    resolve: Any,
    request_path: Path,
    *,
    expected_request_sha256: str,
    package_loader: Callable[[Path, str], Any] | None = None,
    runner: Callable[..., dict[str, Any]] | None = None,
    request_schema: str = "vera-injected-delivery-request/v1",
) -> Path:
    payload = request_path.read_bytes()
    request_sha256 = hashlib.sha256(payload).hexdigest()
    if request_sha256 != expected_request_sha256:
        raise ValueError("operator request changed after release verification")
    request = json.loads(payload)
    if not isinstance(request, dict):
        raise ValueError("operator request must contain one JSON object")
    if request.get("schemaVersion") != request_schema:
        raise ValueError("unsupported operator request")
    if (
        request.get("action") not in {"preflight", "build"}
        or type(request.get("authorizeNewNonproduction")) is not bool
    ):
        raise ValueError("invalid operator action or authorization type")
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
        "requestSha256": request_sha256,
        "releaseSha256": request["releaseSha256"],
        "attestationSha256": request["attestationSha256"],
        "requestedProjectName": request["projectName"],
        "requestedTimelineName": request["timelineName"],
    }
    write_immutable_json(evidence / f"started-{run_id}.json", context)
    if attestation_path.exists():
        package = (package_loader or load_verified_package)(
            attestation_path, request["attestationSha256"]
        )
        if (
            package.root.resolve() != root
            or request["projectName"] != package.attestation["projectName"]
            or request["timelineName"] != package.attestation["timelineName"]
        ):
            raise ValueError("operator-authorized target differs from attestation")
    result = (runner or run_workflow_delivery)(
        resolve,
        attestation_path,
        request["attestationSha256"],
        action=request["action"],
        authorize_new_nonproduction=request["authorizeNewNonproduction"],
        external_scripting=request["externalScripting"],
    )
    result.update(context)
    # Keep the native outcome available if evidence storage fails after mutation.
    print(json.dumps(result, indent=2, sort_keys=True))
    report = write_immutable_json(evidence / f"result-{run_id}.json", result)
    write_immutable_json(
        evidence / f"hashes-{run_id}.json",
        {"resultPath": str(report), "resultSha256": sha256(report), **context},
    )
    return report
