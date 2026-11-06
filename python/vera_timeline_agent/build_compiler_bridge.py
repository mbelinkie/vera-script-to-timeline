"""Bounded local Node-24 v2 compilation/media-needs bridge with input pins."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from .build_jobs import BuildJobError, NeedsAction
from .build_stage_receipt import hash_file

_ROOT = Path(__file__).resolve().parents[2]
_SCRIPTS = {
    "needs": _ROOT / "packages/contracts/src/build-media-needs-cli.ts",
    "compile": _ROOT / "packages/contracts/src/issue-190-compile-cli.ts",
}
_SCHEMAS = {"needs": "vera-build-media-needs/v1", "compile": "issue-190-v2-compile/v1"}


@dataclass(frozen=True)
class BridgeOutput:
    kind: str
    document_sha256: str
    dependencies_sha256: str
    data: dict[str, Any]

    @property
    def needs(self) -> dict[str, Any]:
        value = self.data["needs"]
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise BuildJobError("media requirements not verified")
        return value

    @property
    def result(self) -> dict[str, Any]:
        value = self.data.get("result")
        if not isinstance(value, dict) or value.get("ok") is not True:
            raise BuildJobError("v2 compiler is blocked")
        return value


def invoke_bridge(
    kind: Literal["needs", "compile"],
    document: Path,
    dependencies: Path,
    *,
    timeout: float = 60.0,
) -> BridgeOutput:
    if kind not in _SCRIPTS:
        raise BuildJobError("unrecognized local compiler operation")
    raw_doc, raw_deps = hash_file(document), hash_file(dependencies)
    script = _SCRIPTS[kind]
    hash_file(script)
    try:
        version = subprocess.run(
            ["node", "--version"],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise NeedsAction("pinned Node compiler runtime is unavailable") from error
    if version.stdout.strip() != "v24.19.0":
        raise NeedsAction("local compiler requires pinned Node v24.19.0")
    try:
        result = subprocess.run(
            ["node", str(script), str(document), str(dependencies)],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.SubprocessError) as error:
        raise NeedsAction(
            "v2 compiler invocation failed or timed out; inspect before retry"
        ) from error
    if result.returncode != 0:
        raise BuildJobError(
            f"v2 {kind} refused: {(result.stderr or result.stdout)[:2000]}"
        )
    if len(result.stdout) > 16_000_000:
        raise BuildJobError("compiler response exceeds maximum")
    try:
        data = json.loads(result.stdout)
    except (UnicodeError, ValueError) as error:
        raise BuildJobError("malformed local compiler output") from error
    if (
        not isinstance(data, dict)
        or data.get("schemaVersion") != _SCHEMAS[kind]
        or data.get("runtime") != "v24.19.0"
    ):
        raise BuildJobError("wrong compiler bridge schema/runtime")
    if data.get("inputs") != [f"sha256:{raw_doc}", f"sha256:{raw_deps}"]:
        raise BuildJobError("compiler bridge input digest differs from frozen bytes")
    if hash_file(document) != raw_doc or hash_file(dependencies) != raw_deps:
        raise BuildJobError("compiler input changed during compilation")
    needs = data.get("needs")
    if not isinstance(needs, dict) or needs.get("ok") is not True:
        raise BuildJobError("compiler media requirements are blocked")
    if kind == "compile":
        compiled = data.get("result")
        if not isinstance(compiled, dict) or compiled.get("ok") is not True:
            raise BuildJobError("compiler produced no successful manifest/report")
        report = compiled.get("report")
        if not isinstance(report, dict) or report.get("status") != "ready":
            raise BuildJobError("compiler report is not ready")
        if not all(
            isinstance(compiled.get(field), str)
            for field in ("manifestJson", "reportJson")
        ):
            raise BuildJobError("compiler response lacks deterministic JSON")
    return BridgeOutput(kind, raw_doc, raw_deps, data)
