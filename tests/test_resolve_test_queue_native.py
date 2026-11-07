from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_queue_native as native_module
from vera_timeline_agent.resolve_test_queue_native import (
    NATIVE_ADAPTER,
    NATIVE_SCHEMA,
    NativeVerdict,
    classify_parent_status,
    expected_for_package,
    is_native,
    preflight,
    validate_native_plan,
)

BUILD_ID = "01234567-89ab-cdef-0123-456789abcdef"
PROJECT = f"VERA Delivery {BUILD_ID} synthetic-test"
REQUEST_SHA = "a" * 64
RELEASE_SHA = "b" * 64
ATTESTATION_SHA = "c" * 64


def package_fixture(root: Path) -> SimpleNamespace:
    view = {
        "schemaVersion": "resolve-native-view/v2",
        "timeline": {"startFrame": 0, "durationFrames": 24, "frameRate": "24"},
        "tracks": [{"id": "track-1", "kind": "video", "index": 1, "name": "V1"}],
        "sources": [{"id": "source-1", "path": "Media/clip.mov"}],
        "events": [
            {
                "id": "event-1",
                "sourceId": "source-1",
                "trackId": "track-1",
                "recordRange": {"startFrame": 0, "durationFrames": 24},
            }
        ],
        "markers": [],
        "composition": {"kind": "timeline"},
    }
    return SimpleNamespace(
        root=root,
        view=view,
        manifest={"timeline": view["timeline"]},
        attestation={
            "buildId": BUILD_ID,
            "projectName": PROJECT,
            "timelineName": PROJECT,
        },
    )


def request_payload(
    *,
    release_sha256: str = RELEASE_SHA,
    attestation_sha256: str = ATTESTATION_SHA,
    action: str = "build",
    external_scripting: str = "Local",
    authorize: bool = True,
    project_name: str = PROJECT,
    timeline_name: str = PROJECT,
    package_dir: str,
    attestation_path: str,
    evidence_dir: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "vera-injected-delivery-request/v2",
        "releaseSha256": release_sha256,
        "attestationPath": attestation_path,
        "attestationSha256": attestation_sha256,
        "packageDir": package_dir,
        "projectName": project_name,
        "timelineName": timeline_name,
        "action": action,
        "authorizeNewNonproduction": authorize,
        "externalScripting": external_scripting,
        "evidenceDir": evidence_dir,
    }


def write_request(path: Path, request: dict[str, Any]) -> str:
    payload = json.dumps(request, sort_keys=True, separators=(",", ":")).encode()
    if path.exists():
        path.chmod(0o600)
    path.write_bytes(payload)
    path.chmod(0o400)
    return hashlib.sha256(payload).hexdigest()


def native_plan(
    request_path: Path,
    *,
    request_sha256: str = REQUEST_SHA,
    release_sha256: str = RELEASE_SHA,
    attestation_sha256: str = ATTESTATION_SHA,
    expected: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if expected is None:
        expected = expected_for_package(package_fixture(Path("/unused")))
    return {
        "schema": NATIVE_SCHEMA,
        "name": "guarded-native",
        "fixtureId": f"synthetic-{BUILD_ID}",
        "fixtureSha256": attestation_sha256,
        "targetId": f"disposable-{BUILD_ID}",
        "targetPolicy": "new_disposable_native",
        "category": "native-build",
        "maxElapsedSeconds": 120,
        "maxDiskBytes": 1_048_576,
        "cases": [
            {
                "id": "one-build",
                "adapter": NATIVE_ADAPTER,
                "iterations": 1,
                "delayMs": 0,
            }
        ],
        "native": {
            "requestPath": str(request_path),
            "requestSha256": request_sha256,
            "releaseSha256": release_sha256,
            "attestationSha256": attestation_sha256,
            "projectName": PROJECT,
            "timelineName": PROJECT,
            "expected": expected,
        },
    }


def prepared_native_inputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[dict[str, Any], dict[str, Any], SimpleNamespace, Path]:
    release_root = tmp_path / "release"
    request_dir = release_root / "vera-delivery-v2"
    request_dir.mkdir(parents=True)
    request_path = request_dir / "request.json"
    manifest = request_dir / "release.json"
    manifest.write_bytes(b"release manifest")
    release_sha = hashlib.sha256(manifest.read_bytes()).hexdigest()
    package_root = tmp_path / "package"
    package_root.mkdir()
    attestation_path = tmp_path / "attestation.json"
    attestation_path.write_bytes(b"attestation")
    evidence_dir = tmp_path / "evidence"
    package = package_fixture(package_root)
    attestation_sha = hashlib.sha256(attestation_path.read_bytes()).hexdigest()
    request = request_payload(
        release_sha256=release_sha,
        attestation_sha256=attestation_sha,
        package_dir=str(package_root),
        attestation_path=str(attestation_path),
        evidence_dir=str(evidence_dir),
    )
    request_sha = write_request(request_path, request)
    plan = native_plan(
        request_path,
        request_sha256=request_sha,
        release_sha256=release_sha,
        attestation_sha256=attestation_sha,
        expected=expected_for_package(package),
    )
    monkeypatch.setattr(native_module, "_verify_release", lambda root: manifest)
    monkeypatch.setattr(
        native_module,
        "_load_verified_package",
        lambda path, expected_sha256: package,
    )
    return plan, request, package, request_path


def test_is_native_accepts_mapping_schema() -> None:
    assert is_native({"schema": NATIVE_SCHEMA})
    assert not is_native({"schema": "vera.resolve-test-plan/v1"})
    assert not is_native(None)


def test_expected_for_package_binds_events_settings_media_and_whole_view() -> None:
    expected = expected_for_package(package_fixture(Path("/unused")))
    assert set(expected) == {
        "viewSha256",
        "eventsSha256",
        "settingsSha256",
        "mediaSha256",
        "eventCount",
        "markerCount",
        "mediaCount",
    }
    assert expected["eventCount"] == 1
    assert expected["markerCount"] == 0
    assert expected["mediaCount"] == 1


@pytest.mark.parametrize("version", [None, "resolve-native-view/v1", "unknown"])
def test_expected_for_package_rejects_missing_or_wrong_view_schema(
    version: str | None,
) -> None:
    package = package_fixture(Path("/unused"))
    if version is None:
        del package.view["schemaVersion"]
    else:
        package.view["schemaVersion"] = version
    with pytest.raises(ValueError, match="unsupported fields"):
        expected_for_package(package)


def test_validate_native_plan_reuses_common_v1_limits_and_normalizes_schedule(
    tmp_path: Path,
) -> None:
    plan = native_plan(tmp_path / "release" / "vera-delivery-v2" / "request.json")
    plan["maxElapsedSeconds"] = 0
    with pytest.raises(ValueError, match="maxElapsedSeconds"):
        validate_native_plan(plan)
    plan["maxElapsedSeconds"] = 120
    normalized = validate_native_plan(plan, at="2026-11-04T12:00:00+00:00")
    assert normalized["schema"] == NATIVE_SCHEMA
    assert normalized["targetPolicy"] == "new_disposable_native"
    assert normalized["cases"][0]["adapter"] == NATIVE_ADAPTER
    assert normalized["runAt"] == "2026-11-04T12:00:00+00:00"
    assert normalized["deadlineAt"] > normalized["runAt"]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda plan: plan["native"].update(extra=True), "native must contain exactly"),
        (lambda plan: plan["cases"].append(dict(plan["cases"][0])), "exactly one case"),
        (lambda plan: plan["cases"][0].update(adapter="shell"), "one guarded build"),
        (lambda plan: plan["cases"][0].update(iterations=2), "one guarded build"),
        (lambda plan: plan["cases"][0].update(delayMs=1), "one guarded build"),
        (
            lambda plan: plan.update(targetPolicy="synthetic_only"),
            "new_disposable_native",
        ),
        (
            lambda plan: plan.update(untrustedCommand="python"),
            "unsupported native plan keys",
        ),
    ],
)
def test_native_plan_is_closed_and_single_trial(
    tmp_path: Path, change: Any, message: str
) -> None:
    plan = native_plan(tmp_path / "release" / "vera-delivery-v2" / "request.json")
    change(plan)
    with pytest.raises(ValueError, match=message):
        validate_native_plan(plan)


def test_preflight_validates_immutable_request_release_package_and_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, request, package, request_path = prepared_native_inputs(tmp_path, monkeypatch)
    result = preflight(plan)
    assert result == request
    assert result["evidenceDir"] == str(tmp_path / "evidence")
    assert package.root == Path(request["packageDir"])
    assert request_path.stat().st_mode & 0o222 == 0


@pytest.mark.parametrize(
    ("key", "value", "message"),
    [
        ("action", "preflight", "Local build authority"),
        ("externalScripting", "None", "Local build authority"),
        ("authorizeNewNonproduction", False, "Local build authority"),
        ("projectName", "other target", "identity differs"),
    ],
)
def test_preflight_refuses_wrong_request_authority_or_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    key: str,
    value: Any,
    message: str,
) -> None:
    plan, request, _, request_path = prepared_native_inputs(tmp_path, monkeypatch)
    request[key] = value
    plan["native"]["requestSha256"] = write_request(request_path, request)
    with pytest.raises(ValueError, match=message):
        preflight(plan)


def test_preflight_rejects_changed_request_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _, _, request_path = prepared_native_inputs(tmp_path, monkeypatch)
    request_path.chmod(0o600)
    request_path.write_bytes(b"changed")
    request_path.chmod(0o400)
    with pytest.raises(ValueError, match="request bytes differ"):
        preflight(plan)


def test_preflight_rejects_stale_release_and_mismatched_package_proof(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _, _, request_path = prepared_native_inputs(tmp_path, monkeypatch)
    request_path.parent.joinpath("release.json").write_bytes(b"stale release")
    with pytest.raises(ValueError, match="release manifest differs"):
        preflight(plan)

    plan, _, _, _ = prepared_native_inputs(tmp_path / "second", monkeypatch)
    plan["native"]["expected"]["eventsSha256"] = "d" * 64
    with pytest.raises(ValueError, match="readback obligations differ"):
        preflight(plan)


def parent_terminal() -> dict[str, Any]:
    return {
        "state": "terminal",
        "verified": True,
        "result": {
            "schemaVersion": "vera-injected-delivery-result/v2",
            "deliveryVersion": "2",
            "requestSha256": REQUEST_SHA,
            "releaseSha256": RELEASE_SHA,
            "attestationSha256": ATTESTATION_SHA,
            "requestedProjectName": PROJECT,
            "requestedTimelineName": PROJECT,
            "action": "build",
            "projectName": PROJECT,
            "timelineName": PROJECT,
            "nativeRateQualified": True,
            "status": "verified",
            "verified": True,
            "discrepancies": [],
            "verification": {"eventCount": 1, "markerCount": 0, "mediaCount": 1},
        },
    }


def verdict(response: dict[str, Any], **kwargs: Any) -> NativeVerdict:
    return classify_parent_status(
        response,
        request_sha256=REQUEST_SHA,
        project_name=PROJECT,
        timeline_name=PROJECT,
        release_sha256=RELEASE_SHA,
        attestation_sha256=ATTESTATION_SHA,
        expected={
            "eventCount": 1,
            "markerCount": 0,
            "mediaCount": 1,
            "viewSha256": "d" * 64,
            "eventsSha256": "e" * 64,
            "settingsSha256": "f" * 64,
            "mediaSha256": "0" * 64,
        },
        **kwargs,
    )


@pytest.mark.parametrize("state", ["live", "unknown", "failed", "busy", "not_started"])
def test_nonterminal_parent_states_never_verify(state: str) -> None:
    result = verdict({"state": state, "verified": False})
    assert result.native_verified is False


def test_live_cancellation_stays_pending_reconciliation() -> None:
    result = verdict({"state": "live", "verified": False}, cancel_requested=True)
    assert result.disposition == "live"
    assert result.reason == "cancel_pending_native_reconciliation"


def test_exact_authenticated_terminal_shape_verifies() -> None:
    assert verdict(parent_terminal()).native_verified is True


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("requestSha256", "0" * 64, "terminal_identity_mismatch"),
        ("releaseSha256", "0" * 64, "terminal_identity_mismatch"),
        ("attestationSha256", "0" * 64, "terminal_identity_mismatch"),
        ("requestedProjectName", "other", "terminal_identity_mismatch"),
        ("requestedTimelineName", "other", "terminal_identity_mismatch"),
        ("schemaVersion", "other/v1", "wrong_native_result_schema"),
        ("nativeRateQualified", False, "native_readback_proof_incomplete"),
    ],
)
def test_terminal_identity_and_schema_are_exact(
    field: str, value: Any, reason: str
) -> None:
    reply = parent_terminal()
    reply["result"][field] = value
    assert verdict(reply).reason == reason


def test_terminal_verification_requires_exact_readback_counts_and_flags() -> None:
    reply = parent_terminal()
    reply["result"]["verification"]["eventCount"] = 2
    assert verdict(reply).reason == "native_readback_count_mismatch"
    reply = parent_terminal()
    reply["result"]["verified"] = False
    assert verdict(reply).reason == "native_readback_proof_incomplete"
    reply = parent_terminal()
    reply["result"]["discrepancies"] = ["media-count"]
    assert verdict(reply).reason == "native_readback_proof_incomplete"


@pytest.mark.parametrize(
    ("status", "disposition"),
    [
        ("mutation_failed", "failed"),
        ("verification_failed", "failed"),
        ("stopped_safely", "blocked"),
        ("preflight_passed", "blocked"),
    ],
)
def test_terminal_native_failures_are_not_promoted(
    status: str, disposition: str
) -> None:
    reply = parent_terminal()
    reply["result"]["status"] = status
    result = verdict(reply)
    assert result.disposition == disposition
    assert result.native_verified is False
