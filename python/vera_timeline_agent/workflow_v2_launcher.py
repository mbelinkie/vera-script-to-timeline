"""Hash-pinned v2 operator request and immutable native attempt reports."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from pathlib import Path
from typing import Any

from .workflow_package import read_object, sha256, write_immutable_json
from .workflow_v2 import load_verified_package_v2, run_workflow_delivery_v2

REQUEST_KEYS = {
    "schemaVersion",
    "releaseSha256",
    "attestationPath",
    "attestationSha256",
    "packageDir",
    "projectName",
    "timelineName",
    "action",
    "authorizeNewNonproduction",
    "externalScripting",
    "evidenceDir",
}


def run_installed_request_v2(
    resolve: Any, request_path: Path, *, expected_request_sha256: str
) -> Path:
    """Consume exactly the operator-authorized package and new target."""
    if any(
        path.is_symlink() for path in (request_path, *request_path.absolute().parents)
    ):
        raise ValueError("symbolic link in operator request path")
    payload = request_path.read_bytes()
    request_sha256 = hashlib.sha256(payload).hexdigest()
    if request_sha256 != expected_request_sha256:
        raise ValueError("operator request changed after release verification")
    request = json.loads(payload)
    if isinstance(request, dict) and request.get("schemaVersion") == (
        "vera-sample-import-probe-request/v1"
    ):
        from .sample_import_probe_v2 import run_sample_import_probe

        return run_sample_import_probe(
            resolve, request_path, expected_request_sha256=expected_request_sha256
        )
    if isinstance(request, dict) and request.get("schemaVersion") == (
        "vera-sample-precision-probe-request/v1"
    ):
        from .sample_precision_probe_v2 import run_sample_precision_probe

        return run_sample_precision_probe(
            resolve, request_path, expected_request_sha256=expected_request_sha256
        )
    if isinstance(request, dict) and request.get("schemaVersion") == (
        "qualification-output-native-request/v1"
    ):
        from .qualification_output_native_v2 import run_qualification_output_request

        return run_qualification_output_request(
            resolve, request_path, expected_request_sha256=expected_request_sha256
        )
    if isinstance(request, dict) and request.get("schemaVersion") == (
        "vera-native-target-identity-request/v1"
    ):
        from .target_identity_v2 import run_target_identity

        return run_target_identity(
            resolve, request_path, expected_request_sha256=expected_request_sha256
        )
    if isinstance(request, dict) and request.get("schemaVersion") in {
        "vera-native-qualification-request/v1",
        "vera-native-qualification-request/v2",
    }:
        from .native_qualification_v2 import run_capability_preflight

        return run_capability_preflight(
            resolve, request_path, expected_request_sha256=expected_request_sha256
        )
    if not isinstance(request, dict) or set(request) != REQUEST_KEYS:
        raise ValueError("unsupported operator request fields")
    if request["schemaVersion"] != "vera-injected-delivery-request/v2":
        raise ValueError("unsupported operator request version")
    strings = REQUEST_KEYS - {"authorizeNewNonproduction", "externalScripting"}
    if any(not isinstance(request[key], str) or not request[key] for key in strings):
        raise ValueError("invalid operator request string field")
    if any(
        re.fullmatch(r"[0-9a-f]{64}", request[key]) is None
        for key in ("releaseSha256", "attestationSha256")
    ) or request["externalScripting"] not in (None, "None"):
        raise ValueError("invalid operator request digest or scripting setting")
    if (
        request["action"] not in {"preflight", "build"}
        or type(request["authorizeNewNonproduction"]) is not bool
    ):
        raise ValueError("invalid action or authorization type")
    attestation = Path(request["attestationPath"])
    evidence = Path(request["evidenceDir"])
    root = Path(request["packageDir"])
    if not all(path.is_absolute() for path in (attestation, evidence, root)):
        raise ValueError("attestation, evidence and package paths must be absolute")
    protected = [root.resolve()]
    if attestation.exists():
        protected.append(Path(read_object(attestation)["packageDir"]).resolve())
    if any(path.is_symlink() for path in (evidence, *evidence.parents)) or any(
        evidence.resolve().is_relative_to(path) for path in protected
    ):
        raise ValueError("evidence must be outside the package with no symbolic links")
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
    try:
        package = load_verified_package_v2(attestation, request["attestationSha256"])
        if (
            package.root != root
            or request["projectName"] != package.attestation["projectName"]
            or request["timelineName"] != package.attestation["timelineName"]
        ):
            raise ValueError(
                "operator-authorized package/target differs from attestation"
            )
        result = run_workflow_delivery_v2(
            resolve,
            attestation,
            request["attestationSha256"],
            action=request["action"],
            authorize_new_nonproduction=request["authorizeNewNonproduction"],
            external_scripting=request["externalScripting"],
            allow_fractional_native=True,
        )
    except Exception as error:
        result = {
            "schemaVersion": "vera-injected-delivery-result/v2",
            "status": "stopped_safely",
            "verified": False,
            "message": str(error),
            "failureType": type(error).__name__,
            "partialTargetRetained": False,
        }
    result.update(context)
    # Console retains the native outcome if evidence storage subsequently fails.
    print(json.dumps(result, indent=2, sort_keys=True))
    report = write_immutable_json(evidence / f"result-{run_id}.json", result)
    write_immutable_json(
        evidence / f"hashes-{run_id}.json",
        {
            "resultPath": str(report),
            "resultSha256": sha256(report),
            **context,
        },
    )
    return report
