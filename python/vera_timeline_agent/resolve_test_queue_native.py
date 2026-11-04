"""Closed validator and result classifier for the guarded native queue plan."""

from __future__ import annotations

import hashlib
import json
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, cast

NATIVE_SCHEMA = "vera.resolve-test-plan/v2"
NATIVE_ADAPTER = "native.v2.guarded_build"
REQUEST_SCHEMA = "vera-injected-delivery-request/v2"
RESULT_SCHEMA = "vera-injected-delivery-result/v2"
RELEASE_NAME = "vera-delivery-v2"
_SHA_PATTERN = re.compile(r"[a-f0-9]{64}\Z")
_EXPECTED_KEYS = frozenset(
    {
        "viewSha256",
        "eventsSha256",
        "settingsSha256",
        "mediaSha256",
        "eventCount",
        "markerCount",
        "mediaCount",
    }
)
_NATIVE_KEYS = frozenset(
    {
        "requestPath",
        "requestSha256",
        "releaseSha256",
        "attestationSha256",
        "projectName",
        "timelineName",
        "expected",
    }
)
_REQUEST_KEYS = frozenset(
    {
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
)
_COMMON_REQUIRED = frozenset(
    {
        "schema",
        "name",
        "fixtureId",
        "fixtureSha256",
        "targetId",
        "targetPolicy",
        "category",
        "maxElapsedSeconds",
        "maxDiskBytes",
        "cases",
        "native",
    }
)
_COMMON_OPTIONAL = frozenset({"runAt", "deadlineAt", "sourceCommit"})

Disposition = Literal["live", "verified", "failed", "blocked", "unknown"]


@dataclass(frozen=True)
class NativeVerdict:
    disposition: Disposition
    reason: str
    native_verified: bool


def is_native(plan: object) -> bool:
    """Recognize the opt-in v2 schema without requiring a concrete dict type."""
    return isinstance(plan, Mapping) and plan.get("schema") == NATIVE_SCHEMA


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def expected_for_package(package: object) -> dict[str, Any]:
    """Build the plan's proof binding from a verified v2 package view."""
    view = getattr(package, "view", None)
    if not isinstance(view, Mapping):
        raise ValueError("verified package has no delivery view")
    required = {"timeline", "tracks", "sources", "events", "markers", "composition"}
    if set(view) != required:
        raise ValueError("verified package view has unsupported fields")
    events = view["events"]
    markers = view["markers"]
    sources = view["sources"]
    if not all(isinstance(value, list) for value in (events, markers, sources)):
        raise ValueError("verified package view counts are malformed")
    settings = {
        "timeline": view["timeline"],
        "tracks": view["tracks"],
        "markers": markers,
        "composition": view["composition"],
    }
    return {
        "viewSha256": _digest(_canonical(view)),
        "eventsSha256": _digest(_canonical(events)),
        "settingsSha256": _digest(_canonical(settings)),
        "mediaSha256": _digest(_canonical(sources)),
        "eventCount": len(events),
        "markerCount": len(markers),
        "mediaCount": len(sources),
    }


def _validate_expected(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _EXPECTED_KEYS:
        raise ValueError("native.expected must contain the closed proof binding")
    expected = dict(value)
    for key in ("viewSha256", "eventsSha256", "settingsSha256", "mediaSha256"):
        if (
            not isinstance(expected[key], str)
            or _SHA_PATTERN.fullmatch(expected[key]) is None
        ):
            raise ValueError(f"native.expected.{key} must be lower-case SHA-256")
    for key in ("eventCount", "markerCount", "mediaCount"):
        if type(expected[key]) is not int or not 0 <= expected[key] <= 1_000_000:
            raise ValueError(f"native.expected.{key} must be a bounded integer")
    return expected


def _validate_native_fields(value: object) -> dict[str, Any]:
    if not isinstance(value, Mapping) or set(value) != _NATIVE_KEYS:
        raise ValueError("native must contain exactly the guarded request fields")
    native = dict(value)
    request_path = native["requestPath"]
    if not isinstance(request_path, str) or len(request_path) > 4096:
        raise ValueError("native.requestPath must be an absolute installed path")
    path = Path(request_path)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or str(path) != request_path
        or path.name != "request.json"
        or path.parent.name != RELEASE_NAME
    ):
        raise ValueError("native.requestPath must pin the installed v2 request slot")
    for key in ("requestSha256", "releaseSha256", "attestationSha256"):
        if (
            not isinstance(native[key], str)
            or _SHA_PATTERN.fullmatch(native[key]) is None
        ):
            raise ValueError(f"native.{key} must be lower-case SHA-256")
    for key in ("projectName", "timelineName"):
        item = native[key]
        if (
            not isinstance(item, str)
            or not item
            or len(item) > 256
            or any(ord(character) < 32 for character in item)
        ):
            raise ValueError(f"native.{key} must be a bounded target name")
    if native["projectName"] != native["timelineName"]:
        raise ValueError("native project and timeline names must match")
    native["expected"] = _validate_expected(native["expected"])
    return native


def validate_native_plan(source: object, at: str | None = None) -> dict[str, Any]:
    """Validate the closed single-case native plan and normalize its schedule.

    The shared v1 validator is imported only when called so the queue may import
    this module without a module-initialization cycle.
    """
    if not isinstance(source, Mapping):
        raise ValueError("plan must be a JSON object")
    plan = dict(source)
    if not plan.keys() >= _COMMON_REQUIRED or not plan.keys() <= (
        _COMMON_REQUIRED | _COMMON_OPTIONAL
    ):
        raise ValueError("missing or unsupported native plan keys")
    if (
        plan["schema"] != NATIVE_SCHEMA
        or plan["targetPolicy"] != "new_disposable_native"
    ):
        raise ValueError("native plans require the v2 schema and new_disposable_native")
    native = _validate_native_fields(plan["native"])
    if plan["fixtureSha256"] != native["attestationSha256"]:
        raise ValueError("fixtureSha256 must pin the package attestation")
    if not isinstance(plan["fixtureId"], str) or not plan["fixtureId"].startswith(
        "synthetic-"
    ):
        raise ValueError("native fixtureId must identify a synthetic package")
    if not isinstance(plan["targetId"], str) or not plan["targetId"].startswith(
        "disposable-"
    ):
        raise ValueError("native targetId must identify a disposable target")
    cases = plan["cases"]
    if not isinstance(cases, list) or len(cases) != 1:
        raise ValueError("native plans require exactly one case")
    case = cases[0]
    if not isinstance(case, Mapping) or set(case) != {
        "id",
        "adapter",
        "iterations",
        "delayMs",
    }:
        raise ValueError("native case has unsupported fields")
    if (
        case["adapter"] != NATIVE_ADAPTER
        or case["iterations"] != 1
        or type(case["iterations"]) is not int
        or case["delayMs"] != 0
        or type(case["delayMs"]) is not int
    ):
        raise ValueError("native plans allow one guarded build trial only")

    from .resolve_test_queue import PLAN_SCHEMA, validate_plan

    common = {key: value for key, value in plan.items() if key != "native"}
    common["schema"] = PLAN_SCHEMA
    common["targetPolicy"] = "synthetic_only"
    common["cases"] = [{**dict(case), "adapter": "mock.pass"}]
    normalized = validate_plan(common, at=at)
    normalized["schema"] = NATIVE_SCHEMA
    normalized["targetPolicy"] = "new_disposable_native"
    normalized["cases"] = [dict(case)]
    normalized["native"] = native
    return normalized


def _no_symlinks(path: Path) -> None:
    if any(part.is_symlink() for part in (path, *path.absolute().parents)):
        raise ValueError("symbolic link in native request path")


def _absolute_path(value: object, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"request {label} must be an absolute path")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or str(path) != value:
        raise ValueError(f"request {label} must be a canonical absolute path")
    _no_symlinks(path)
    return path


def _load_verified_package(path: Path, expected_sha256: str) -> object:
    from .workflow_v2 import load_verified_package_v2

    return load_verified_package_v2(path, expected_sha256)


def _verify_release(root: Path) -> Path:
    from .workflow_v2_cli import _verify_release as verify_release

    return verify_release(root)


def preflight(plan: object) -> dict[str, Any]:
    """Revalidate the pinned request, installed release, attestation and package."""
    normalized = validate_native_plan(plan)
    native = cast(dict[str, Any], normalized["native"])
    request_path = Path(native["requestPath"])
    _no_symlinks(request_path)
    try:
        info = request_path.lstat()
    except OSError as error:
        raise ValueError("pinned request is unavailable") from error
    if (
        not stat.S_ISREG(info.st_mode)
        or info.st_nlink != 1
        or info.st_mode & 0o222
        or info.st_size > 64 * 1024
    ):
        raise ValueError("pinned request must be a small immutable regular file")
    payload = request_path.read_bytes()
    if _digest(payload) != native["requestSha256"]:
        raise ValueError("pinned request bytes differ from the plan")
    try:
        request_value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("pinned request is not valid JSON") from error
    if not isinstance(request_value, dict) or set(request_value) != _REQUEST_KEYS:
        raise ValueError("pinned request has unsupported fields")
    request = cast(dict[str, Any], request_value)
    if (
        request["schemaVersion"] != REQUEST_SCHEMA
        or request["action"] != "build"
        or request["authorizeNewNonproduction"] is not True
        or type(request["authorizeNewNonproduction"]) is not bool
        or request["externalScripting"] != "Local"
    ):
        raise ValueError(
            "pinned request lacks exact nonproduction Local build authority"
        )
    if any(
        request[key] != native[native_key]
        for key, native_key in (
            ("releaseSha256", "releaseSha256"),
            ("attestationSha256", "attestationSha256"),
            ("projectName", "projectName"),
            ("timelineName", "timelineName"),
        )
    ):
        raise ValueError("pinned request identity differs from the native plan")

    release_root = request_path.parent.parent
    if request_path != release_root / RELEASE_NAME / "request.json":
        raise ValueError("request is outside the pinned installed release slot")
    _no_symlinks(release_root)
    release_manifest = _verify_release(release_root)
    if _digest(release_manifest.read_bytes()) != native["releaseSha256"]:
        raise ValueError("installed release manifest differs from the plan")

    attestation_path = _absolute_path(request["attestationPath"], "attestationPath")
    package_root = _absolute_path(request["packageDir"], "packageDir")
    evidence_path = _absolute_path(request["evidenceDir"], "evidenceDir")
    protected = [release_root.resolve(), package_root.resolve()]
    if (
        any(
            evidence_path.resolve().is_relative_to(path)
            or path.is_relative_to(evidence_path.resolve())
            for path in protected
        )
        or evidence_path.resolve().is_relative_to(attestation_path.resolve())
        or (attestation_path.resolve().is_relative_to(evidence_path.resolve()))
    ):
        raise ValueError("evidence path overlaps a protected native input")

    package = _load_verified_package(attestation_path, native["attestationSha256"])
    package_attestation = getattr(package, "attestation", None)
    package_root_actual = getattr(package, "root", None)
    if not isinstance(package_attestation, Mapping) or not isinstance(
        package_root_actual, Path
    ):
        raise ValueError("verified package did not return its immutable identity")
    build_id = package_attestation.get("buildId")
    if (
        package_root_actual != package_root
        or request["packageDir"] != str(package_root_actual)
        or package_attestation.get("projectName") != native["projectName"]
        or package_attestation.get("timelineName") != native["timelineName"]
        or normalized["fixtureId"] != f"synthetic-{build_id}"
        or normalized["targetId"] != f"disposable-{build_id}"
        or normalized["fixtureSha256"] != native["attestationSha256"]
    ):
        raise ValueError("verified package identity differs from the native plan")
    if expected_for_package(package) != native["expected"]:
        raise ValueError("verified package readback obligations differ from the plan")
    return request


def classify_parent_status(
    response: Mapping[str, Any],
    *,
    request_sha256: str,
    project_name: str,
    timeline_name: str,
    cancel_requested: bool = False,
    release_sha256: str | None = None,
    attestation_sha256: str | None = None,
    expected: Mapping[str, Any] | None = None,
) -> NativeVerdict:
    """Interpret only the authenticated shape returned by parent.status()."""
    state = response.get("state")
    if state == "live":
        return NativeVerdict(
            "live",
            "cancel_pending_native_reconciliation"
            if cancel_requested
            else "parent_worker_live",
            False,
        )
    if state == "busy":
        return NativeVerdict("blocked", "dispatch_busy_no_reservation", False)
    if state == "not_started":
        return NativeVerdict("blocked", "consumed_request_confirmed_not_started", False)
    if state in {"unknown", "failed"}:
        return NativeVerdict("unknown", f"parent_{state}_retain_evidence", False)
    if state != "terminal":
        return NativeVerdict("unknown", "unrecognized_parent_state", False)

    result = response.get("result")
    if not isinstance(result, Mapping):
        return NativeVerdict("unknown", "missing_final_result", False)
    identity = {
        "requestSha256": request_sha256,
        "requestedProjectName": project_name,
        "requestedTimelineName": timeline_name,
    }
    if release_sha256 is not None:
        identity["releaseSha256"] = release_sha256
    if attestation_sha256 is not None:
        identity["attestationSha256"] = attestation_sha256
    if any(result.get(key) != value for key, value in identity.items()):
        return NativeVerdict("unknown", "terminal_identity_mismatch", False)
    if result.get("schemaVersion") != RESULT_SCHEMA:
        return NativeVerdict("unknown", "wrong_native_result_schema", False)
    status = result.get("status")
    if status in {"mutation_failed", "verification_failed"}:
        return NativeVerdict("failed", "native_delivery_or_readback_failed", False)
    if status in {"stopped_safely", "preflight_passed"}:
        return NativeVerdict("blocked", "no_verified_native_build", False)
    if status != "verified":
        return NativeVerdict("unknown", "suspect_terminal_result", False)
    if (
        response.get("verified") is not True
        or result.get("verified") is not True
        or result.get("discrepancies") != []
        or result.get("action") != "build"
        or result.get("deliveryVersion") != "2"
        or result.get("projectName") != project_name
        or result.get("timelineName") != timeline_name
        or result.get("nativeRateQualified") is not True
    ):
        return NativeVerdict("unknown", "native_readback_proof_incomplete", False)
    verification = result.get("verification")
    if (
        not isinstance(verification, Mapping)
        or set(verification)
        != {
            "eventCount",
            "markerCount",
            "mediaCount",
        }
        or any(
            type(verification[key]) is not int or verification[key] < 0
            for key in ("eventCount", "markerCount", "mediaCount")
        )
    ):
        return NativeVerdict("unknown", "native_readback_counts_missing", False)
    if expected is not None:
        try:
            pinned = _validate_expected(expected)
        except ValueError:
            return NativeVerdict("unknown", "invalid_expected_readback_binding", False)
        if any(
            verification[key] != pinned[key]
            for key in ("eventCount", "markerCount", "mediaCount")
        ):
            return NativeVerdict("unknown", "native_readback_count_mismatch", False)
    return NativeVerdict("verified", "saved_reopened_readback_verified", True)
