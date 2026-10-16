"""Installed output-native boundary checks; no Resolve or operator effects."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pwd
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    CONTEXT_HASH_FIELDS,
    EMPTY_HEAD,
    LANE,
    OutputConsistencyError,
    _canonical,
    _json_hash,
    _parse,
)


def _context() -> dict[str, Any]:
    value: dict[str, Any] = {key: "a" * 64 for key in CONTEXT_HASH_FIELDS}
    value.update(
        {
            "lane": LANE,
            "invocationId": "invocation-one",
            "caseId": "case-one",
            "phase": "pristine",
            "target": {
                "projectUid": "project-one",
                "timelineUid": "timeline-one",
                "projectName": "disposable-project",
                "timelineName": "disposable-timeline",
            },
            "binding": {"kind": "baseline"},
        }
    )
    projection = {
        key: child
        for key, child in value.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {"kind": "baseline"}
    value["binding"]["bindingSha256"] = _json_hash(projection)
    return value


def _native_request(tmp_path: Path, profile: str) -> tuple[dict[str, Any], bytes]:
    root = tmp_path.resolve() / "wrapper" / "package"
    operation = tmp_path.resolve() / "native" / "operations" / "00000000"
    operation.mkdir(parents=True)
    context = _context()
    request = {
        "schemaVersion": native.REQUEST_SCHEMA,
        "lane": LANE,
        "profile": profile,
        "action": "construct",
        "operationId": "operation-one",
        "sequence": 0,
        "priorResultSha256": EMPTY_HEAD,
        "context": context,
        "target": context["target"],
        "package": {
            "profile": profile,
            "packageRoot": str(root),
            "attestationPath": str(root.parent / "attestation.json"),
            "attestationSha256": "b" * 64,
            "admissionPath": str(
                root.parent / "qualification-output-package-admission.json"
            ),
            "admissionSha256": "c" * 64,
        },
        "inputs": {
            "originalDocumentPath": str(root / "Original/script-document-v2.json"),
            "originalDependenciesPath": str(
                root / "Original/compiler-dependencies-v2.json"
            ),
            "executionDocumentPath": str(root / "Execution/script-document-v2.json"),
            "executionDependenciesPath": str(
                root / "Execution/compiler-dependencies-v2.json"
            ),
        },
        "sourceGraph": {
            "path": str(tmp_path.resolve() / "source-graph.json"),
            "sha256": context["nativeSourceGraphSha256"],
        },
        "release": {
            "path": str(tmp_path.resolve() / "release.json"),
            "sha256": context["installedReleaseSha256"],
        },
        "releaseManifestSha256": "e" * 64,
        "renderIntent": None,
        "authority": {
            "path": str(tmp_path.resolve() / "authority.json"),
            "sha256": "f" * 64,
        },
        "intent": {"path": str(tmp_path.resolve() / "intent.json"), "sha256": "1" * 64},
        "reservation": None,
        "payload": {},
        "resultPath": str(operation / "result.json"),
    }
    return request, _canonical(request)


@pytest.mark.parametrize("profile", [native.SYNTHETIC_PROFILE, native.R16_PROFILE])
def test_closed_native_request_accepts_only_static_qualification_profiles(
    tmp_path: Path, profile: str
) -> None:
    _request, raw = _native_request(tmp_path, profile)
    checked = native.verify_native_request(
        raw, expected_request_sha256=hashlib.sha256(raw).hexdigest(), current=False
    )
    assert checked["profile"] == profile


def test_closed_native_request_refuses_a_caller_invented_profile(
    tmp_path: Path,
) -> None:
    request, _ = _native_request(tmp_path, native.R16_PROFILE)
    request["profile"] = request["package"]["profile"] = "unreviewed-profile/v1"
    raw = _canonical(request)
    with pytest.raises(
        OutputConsistencyError, match="unsupported native package profile"
    ):
        native.verify_native_request(
            raw, expected_request_sha256=hashlib.sha256(raw).hexdigest(), current=False
        )


def test_closed_native_request_refuses_unimplemented_recover_action(
    tmp_path: Path,
) -> None:
    request, _ = _native_request(tmp_path, native.R16_PROFILE)
    request["action"] = "recover"
    raw = _canonical(request)

    with pytest.raises(OutputConsistencyError, match="unsupported native action"):
        native.verify_native_request(
            raw, expected_request_sha256=hashlib.sha256(raw).hexdigest(), current=False
        )


def test_admitted_extent_is_bounded_before_native_effects() -> None:
    with pytest.raises(OutputConsistencyError):
        native._verify_admitted_extent(
            {"timeline": {"durationFrames": native.MAX_NATIVE_EXTENT_FRAMES + 1}}
        )


def test_r16_parent_manifest_report_and_compile_pins_are_exact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path.resolve() / "package"
    compiler = root / "Compiler"
    compiler.mkdir(parents=True)
    payloads = {
        "timeline-manifest-v2.json": b"manifest",
        "build-report-v2.json": b"report",
        "compile-1.json": b"compile-one",
        "compile-2.json": b"compile-two",
    }
    for name, raw in payloads.items():
        (compiler / name).write_bytes(raw)
    pins = {name: hashlib.sha256(raw).hexdigest() for name, raw in payloads.items()}
    monkeypatch.setattr(native, "_R16_PARENT_PINS", pins)
    admission = {
        "profile": native.R16_PROFILE,
        "manifestSha256": pins["timeline-manifest-v2.json"],
        "reportSha256": pins["build-report-v2.json"],
    }

    native._verify_r16_parent_pins(root, admission)
    (compiler / "compile-2.json").write_bytes(b"changed")
    with pytest.raises(OutputConsistencyError, match=r"compile-2\.json pin differs"):
        native._verify_r16_parent_pins(root, admission)


def _output_launcher_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    from vera_timeline_agent.workflow_v2_cli import (
        RELEASE_NAME,
        build_output_release_v2,
    )

    install = tmp_path / "output-release"
    manifest = build_output_release_v2(install)
    request = install / RELEASE_NAME / "request.json"
    request.write_bytes(
        _canonical(
            {
                "schemaVersion": native.REQUEST_SCHEMA,
                "releaseManifestSha256": hashlib.sha256(
                    manifest.read_bytes()
                ).hexdigest(),
            }
        )
    )
    request.chmod(0o400)
    return (
        install,
        install / "VERA Delivery v2.py",
        install / RELEASE_NAME / "python",
    )


def _run_output_launcher(
    launcher: Path, runtime: Path, *, setup: str
) -> subprocess.CompletedProcess[str]:
    code = (
        "import runpy,sys\n"
        "sys.dont_write_bytecode = True\n"
        "sys.pycache_prefix = None\n"
        f"sys.path.insert(0, {str(runtime)!r})\n"
        f"{setup}\n"
        f"runpy.run_path({str(launcher)!r}, init_globals={{'resolve': None}})\n"
    )
    return subprocess.run(
        [sys.executable, "-S", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )


def _run_output_launcher_twice(
    launcher: Path, runtime: Path, *, between: str = ""
) -> subprocess.CompletedProcess[str]:
    code = (
        "import runpy,sys\n"
        "sys.dont_write_bytecode = True\n"
        "sys.pycache_prefix = None\n"
        f"sys.path.insert(0, {str(runtime)!r})\n"
        f"runpy.run_path({str(launcher)!r}, init_globals={{'resolve': None}})\n"
        f"{between}\n"
        f"runpy.run_path({str(launcher)!r}, init_globals={{'resolve': None}})\n"
    )
    return subprocess.run(
        [sys.executable, "-S", "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )


def test_output_launcher_reentry_accepts_only_exact_installed_modules(
    tmp_path: Path,
) -> None:
    _install, launcher, runtime = _output_launcher_fixture(tmp_path)
    completed = _run_output_launcher_twice(launcher, runtime)

    assert "already loaded" not in completed.stdout
    assert "foreign VERA runtime" not in completed.stdout
    assert "source provenance is missing" not in completed.stdout


def test_output_launcher_reentry_rejects_unstamped_exact_modules(
    tmp_path: Path,
) -> None:
    _install, launcher, runtime = _output_launcher_fixture(tmp_path)
    completed = _run_output_launcher(
        launcher,
        runtime,
        setup="import vera_timeline_agent.qualification_output_native_v2",
    )

    assert "source provenance is missing or drifted" in completed.stdout


@pytest.mark.parametrize(
    "setup",
    [
        "import types; sys.modules['vera_timeline_agent'] = "
        "types.ModuleType('vera_timeline_agent')",
        "import types; sys.modules['vera_timeline_agent.foreign'] = "
        "types.ModuleType('vera_timeline_agent.foreign')",
    ],
)
def test_output_launcher_reentry_rejects_foreign_or_unknown_modules(
    tmp_path: Path, setup: str
) -> None:
    _install, launcher, runtime = _output_launcher_fixture(tmp_path)
    completed = _run_output_launcher(launcher, runtime, setup=setup)

    assert "foreign VERA runtime" in completed.stdout


def test_output_launcher_reentry_rejects_installed_runtime_drift(
    tmp_path: Path,
) -> None:
    _install, launcher, runtime = _output_launcher_fixture(tmp_path)
    module = runtime / "vera_timeline_agent/qualification_output_native_v2.py"
    completed = _run_output_launcher_twice(
        launcher,
        runtime,
        between=(
            f"path = {str(module)!r}\n"
            "from pathlib import Path\n"
            "Path(path).write_bytes(Path(path).read_bytes() + b'\\n# drift\\n')"
        ),
    )

    assert "installed source differs from the versioned release" in completed.stdout


def test_output_launcher_reentry_rejects_loaded_code_after_release_replacement(
    tmp_path: Path,
) -> None:
    _install, launcher, runtime = _output_launcher_fixture(tmp_path)
    module = runtime / "vera_timeline_agent/qualification_output_native_v2.py"
    release = runtime.parent / "release.json"
    request = runtime.parent / "request.json"
    between = f"""
from pathlib import Path
import hashlib
import json
module = Path({str(module)!r})
module.write_bytes(module.read_bytes() + b"\\n# replacement release\\n")
release = Path({str(release)!r})
value = json.loads(release.read_bytes())
for row in value["files"]:
    if row["path"] == (
        "vera-delivery-v2/python/vera_timeline_agent/qualification_output_native_v2.py"
    ):
        raw = module.read_bytes()
        row["sha256"] = hashlib.sha256(raw).hexdigest()
        row["sizeBytes"] = len(raw)
release.chmod(0o644)
release.write_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
release.chmod(0o444)
request = Path({str(request)!r})
request.chmod(0o644)
request.write_bytes(json.dumps({{
    "schemaVersion": "qualification-output-native-request/v1",
    "releaseManifestSha256": hashlib.sha256(release.read_bytes()).hexdigest(),
}}, sort_keys=True, separators=(",", ":")).encode())
request.chmod(0o400)
"""
    completed = _run_output_launcher_twice(launcher, runtime, between=between)

    assert "source provenance is missing or drifted" in completed.stdout


def _approval(tmp_path: Path, *, profile: str) -> tuple[dict[str, Any], dict[str, Any]]:
    tmp_path = tmp_path.resolve()
    root = tmp_path / "wrapper" / "package"
    (root / "Compiler").mkdir(parents=True)
    timeline = {
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "startFrame": 0,
        "durationFrames": 10,
        "width": 1920,
        "height": 1080,
    }
    (root / "Compiler/timeline-manifest-v2.json").write_bytes(
        _canonical({"timeline": timeline})
    )
    admission_path = root.parent / "qualification-output-package-admission.json"
    admission_raw = _canonical({"qualificationOnly": profile == native.R16_PROFILE})
    admission_path.write_bytes(admission_raw)
    context = _context()
    target_key = {
        "projectUid": context["target"]["projectUid"],
        "timelineUid": context["target"]["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    output_path = (
        native.NATIVE_STATE_ROOT
        / "renders"
        / native._hash(_canonical(target_key))
        / "approved.mov"
    )
    now = datetime.now(UTC)

    def stamp(value: datetime) -> str:
        return value.isoformat().replace("+00:00", "Z")

    approval = {
        "schemaVersion": native.APPROVAL_SCHEMA,
        "lane": LANE,
        "approvalId": "approval-one",
        "operator": pwd.getpwuid(os.getuid()).pw_name,
        "issuedAt": stamp(now - timedelta(seconds=1)),
        "expiresAt": stamp(now + timedelta(minutes=10)),
        "invocationId": context["invocationId"],
        "context": context,
        "target": context["target"],
        "profile": profile,
        "releaseManifestSha256": "2" * 64,
        "installedReleaseSha256": context["installedReleaseSha256"],
        "packageRoot": str(root),
        "packageSha256": context["packageSha256"],
        "admissionSha256": hashlib.sha256(admission_raw).hexdigest(),
        "sourceGraphSha256": context["nativeSourceGraphSha256"],
        "outputPath": str(output_path),
        "settings": native._settings_for_timeline(timeline),
        "actionPlan": list(native.APPROVAL_ACTION_PLAN),
        "maxPolls": native.MAX_POLL_COUNT,
        "confirmations": dict(native.CONFIRMATIONS),
        "oneUse": True,
    }
    return approval, context


def test_r16_operator_approval_binds_profile_context_and_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        native, "NATIVE_STATE_ROOT", tmp_path.resolve() / "native-state"
    )
    approval, context = _approval(tmp_path, profile=native.R16_PROFILE)
    raw = _canonical(approval)
    checked = native.verify_operator_approval(
        raw,
        context=context,
        profile=native.R16_PROFILE,
        admission_sha256=approval["admissionSha256"],
        release_manifest_sha256=approval["releaseManifestSha256"],
    )
    assert checked["profile"] == native.R16_PROFILE
    assert checked["confirmations"] == native.CONFIRMATIONS

    approval["confirmations"] = {**native.CONFIRMATIONS, "connectInjectedOnly": False}
    with pytest.raises(
        OutputConsistencyError, match="explicit one-use nonproduction approval"
    ):
        native.verify_operator_approval(
            _canonical(approval),
            context=context,
            profile=native.R16_PROFILE,
            admission_sha256=approval["admissionSha256"],
            release_manifest_sha256=approval["releaseManifestSha256"],
        )


def _r16_original_fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> dict[str, bytes]:
    private_root = tmp_path.resolve() / "private-preparation"
    candidate_root = (
        private_root / "issue-148/2026-10-11-r16-producer-review/candidate-inputs"
    )
    target_root = (
        private_root
        / "issue-148/2026-10-11-r15-heroes-base-binding/attempt-01/candidate-inputs"
    )
    delta_path = (
        private_root
        / "issue-145/advance-inputs/issue209-r16-preparation-cn209p1-attempt02"
        / "execution-dependency-delta.json"
    )
    candidate_root.mkdir(parents=True)
    target_root.mkdir(parents=True)
    contents = {
        "script-document-v2.json": b"original document bytes",
        "compiler-dependencies-v2.json": b"original dependency bytes",
    }
    original_hashes = {
        name: hashlib.sha256(raw).hexdigest() for name, raw in contents.items()
    }
    regular_files: dict[str, Any] = {}
    for name, raw in contents.items():
        target = target_root / name
        target.write_bytes(raw)
        target.chmod(0o644)
        link = candidate_root / name
        link.symlink_to(target)
        regular_files[str(link)] = {
            "rawSha256": f"sha256:{original_hashes[name]}",
            "identity": {
                "path": str(link),
                "resolvedTarget": str(target),
                "linkText": os.readlink(link),
                "linkIdentity": native._r16_file_identity(link),
                "targetIdentity": native._r16_file_identity(target),
            },
        }
    delta_raw = json.dumps(
        {"finalInputState": {"regularFiles": regular_files}},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    delta_path.parent.mkdir(parents=True)
    delta_path.write_bytes(delta_raw)
    monkeypatch.setattr(native, "_R16_CANDIDATE_ROOT", candidate_root)
    monkeypatch.setattr(native, "_R16_ORIGINAL_TARGET_ROOT", target_root)
    monkeypatch.setattr(native, "_R16_DELTA_PATH", delta_path)
    monkeypatch.setattr(
        native, "_R16_DELTA_SHA256", hashlib.sha256(delta_raw).hexdigest()
    )
    monkeypatch.setattr(native, "_R16_ORIGINALS", original_hashes)
    return contents


def test_r16_original_currentness_matches_pinned_delta_and_target_modes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    contents = _r16_original_fixture(tmp_path, monkeypatch)

    assert native._verify_r16_original_currentness() == contents


def test_r16_original_currentness_refuses_changed_link_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _r16_original_fixture(tmp_path, monkeypatch)
    link = native._R16_CANDIDATE_ROOT / "script-document-v2.json"
    replacement = tmp_path.resolve() / "different-original.json"
    replacement.write_bytes(b"different original")
    replacement.chmod(0o644)
    link.unlink()
    link.symlink_to(replacement)

    with pytest.raises(
        OutputConsistencyError, match="R16 original link target/text changed"
    ):
        native._verify_r16_original_currentness()


def test_r16_original_currentness_refuses_changed_target_mode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _r16_original_fixture(tmp_path, monkeypatch)
    target = native._R16_ORIGINAL_TARGET_ROOT / "compiler-dependencies-v2.json"
    target.chmod(0o600)

    with pytest.raises(
        OutputConsistencyError,
        match="R16 original target mode differs from the pinned currentness mode",
    ):
        native._verify_r16_original_currentness()


def test_r16_admission_accepts_the_retained_recovery_kind_shape(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_root = tmp_path.resolve() / "wrapper/package"
    compiler = package_root / "Compiler"
    compiler.mkdir(parents=True)
    warning_rows = [
        {"code": "TEMPORARY_PRESENTER_STILL", "entity": {"id": f"slot-{i}"}}
        for i in range(3)
    ]
    recovery_rows = [{"kind": "REPLACE_TEMPORARY_PRESENTER", "slotId": "slot-0"}]
    report_raw = _canonical(
        {"diagnostics": warning_rows, "recoveryActions": recovery_rows}
    )
    manifest_raw = _canonical({"timeline": {"durationFrames": 1}})
    report_path = compiler / "build-report-v2.json"
    manifest_path = compiler / "timeline-manifest-v2.json"
    compile_one_path = compiler / "compile-1.json"
    compile_two_path = compiler / "compile-2.json"
    report_path.write_bytes(report_raw)
    manifest_path.write_bytes(manifest_raw)
    compile_one_path.write_bytes(b"compile-one")
    compile_two_path.write_bytes(b"compile-two")
    parent_pins = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in (manifest_path, report_path, compile_one_path, compile_two_path)
    }
    monkeypatch.setattr(native, "_R16_PARENT_PINS", parent_pins)
    inventory_rows: list[dict[str, Any]] = []
    for path in (report_path, manifest_path, compile_one_path, compile_two_path):
        raw = path.read_bytes()
        inventory_rows.append(
            {
                "path": path.relative_to(package_root).as_posix(),
                "sha256": hashlib.sha256(raw).hexdigest(),
                "size": len(raw),
            }
        )
    inventory_rows.sort(key=lambda row: row["path"])
    inventory_raw = _canonical(
        {
            "schemaVersion": native.INVENTORY_SCHEMA,
            "files": inventory_rows,
        }
    )
    (package_root / "package-inventory.json").write_bytes(inventory_raw)

    input_root = tmp_path.resolve() / "inputs"
    input_root.mkdir()
    inputs: dict[str, str] = {}
    input_hashes: dict[str, str] = {}
    for name, raw in {
        "originalDocumentPath": b"original document",
        "originalDependenciesPath": b"original dependencies",
        "executionDocumentPath": b"execution document",
        "executionDependenciesPath": b"execution dependencies",
    }.items():
        path = input_root / name
        path.write_bytes(raw)
        inputs[name] = str(path)
        input_hashes[name.removesuffix("Path") + "Sha256"] = hashlib.sha256(
            raw
        ).hexdigest()

    context = _context()
    context.update(input_hashes)
    context["manifestSha256"] = hashlib.sha256(manifest_raw).hexdigest()
    context["reportSha256"] = hashlib.sha256(report_raw).hexdigest()
    projection = {
        key: value
        for key, value in context.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {"kind": "baseline"}
    context["binding"]["bindingSha256"] = _json_hash(projection)

    admission = {
        "schemaVersion": native.ADMISSION_SCHEMA,
        "profile": native.R16_PROFILE,
        "disposition": "qualification_only",
        "originalDocumentSha256": context["originalDocumentSha256"],
        "originalDependenciesSha256": context["originalDependenciesSha256"],
        "executionDocumentSha256": context["executionDocumentSha256"],
        "executionDependenciesSha256": context["executionDependenciesSha256"],
        "manifestSha256": parent_pins["timeline-manifest-v2.json"],
        "reportSha256": parent_pins["build-report-v2.json"],
        "viewSha256": "2" * 64,
        "packageInventorySha256": hashlib.sha256(inventory_raw).hexdigest(),
        "preflightSha256": "3" * 64,
        "preparationSha256": "4" * 64,
        "sourceProofs": [],
        "diagnostics": warning_rows,
        "recoveryActions": recovery_rows,
        "creativeQualification": "unqualified_temporary_presenter",
    }
    admission_raw = _canonical(admission)
    admission_path = package_root.parent / "qualification-output-package-admission.json"
    admission_path.write_bytes(admission_raw)
    request = {
        "profile": native.R16_PROFILE,
        "context": context,
        "package": {
            "packageRoot": str(package_root),
            "admissionPath": str(admission_path),
            "admissionSha256": hashlib.sha256(admission_raw).hexdigest(),
        },
        "inputs": inputs,
    }

    checked = native._verify_admission(request)

    assert checked["recoveryActions"] == recovery_rows


class _Media:
    def __init__(self, path: Path) -> None:
        self.path = path

    def GetUniqueId(self) -> str:
        return "media-one"

    def GetMediaId(self) -> str:
        return "media-id-one"

    def GetClipProperty(self) -> dict[str, str]:
        return {"Online Status": "Online", "File Path": str(self.path)}


class _Item:
    def __init__(self, media: _Media, stamp: str) -> None:
        self.media = media
        self.stamp = stamp
        self.speed: dict[str, Any] = {
            "Percentage": 100,
            "PitchCorrection": False,
            "StretchKeyframesToFit": False,
            "RippleTimeline": False,
        }
        self.properties: dict[str, Any] = {
            "AudioVolumeEnabled": True,
            "AudioVolume": -6.0,
        }
        self.true_start = 0
        self.source_start_frame = 12
        self.source_end_frame = 22

    def GetUniqueId(self) -> str:
        return "timeline-item-one"

    def GetStart(self, _in_frames: bool) -> int:
        return self.true_start

    def GetDuration(self, _in_frames: bool) -> int:
        return 10

    def GetEnd(self, _in_frames: bool) -> int:
        return self.true_start + 10

    def GetSourceStartFrame(self) -> int:
        return self.source_start_frame

    def GetSourceEndFrame(self) -> int:
        return self.source_end_frame

    def GetLinkedItems(self) -> list[Any]:
        return []

    def GetClipEnabled(self) -> bool:
        return True

    def GetSpeed(self) -> dict[str, Any]:
        return self.speed

    def GetMediaPoolItem(self) -> _Media:
        return self.media

    def GetMarkerCustomData(self, _frame: int) -> str:
        return self.stamp

    def GetProperties(self) -> dict[str, Any]:
        return self.properties


class _Timeline:
    def __init__(
        self,
        item: _Item,
        *,
        track_kind: str,
        track_name: str,
        marker_name: str = "Act I",
        frame_rate: Any = "23.976",
    ) -> None:
        self.item = item
        self.track_kind = track_kind
        self.track_name = track_name
        self.frame_rate = frame_rate
        self.markers = {
            5: {"color": "Cyan", "name": marker_name, "note": "chapter", "duration": 1}
        }
        self.marker_stamp = (
            '{"v2EventId":"marker-one","v2EventSha256":"' + "a" * 64 + '"}'
        )

    def GetUniqueId(self) -> str:
        return "timeline-one"

    def GetName(self) -> str:
        return "disposable-timeline"

    def GetSetting(self, name: str) -> Any:
        return {
            "timelineFrameRate": self.frame_rate,
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }[name]

    def GetStartFrame(self) -> int:
        return 0

    def GetEndFrame(self) -> int:
        return 10

    def GetTrackCount(self, kind: str) -> int:
        return 1 if kind == self.track_kind else 0

    def GetTrackName(self, kind: str, index: int) -> str:
        assert kind == self.track_kind and index == 1
        return self.track_name

    def GetItemListInTrack(self, kind: str, index: int) -> list[_Item]:
        assert kind == self.track_kind and index == 1
        return [self.item]

    def GetIsTrackEnabled(self, kind: str, index: int) -> bool:
        assert kind == self.track_kind and index == 1
        return True

    def GetIsTrackLocked(self, kind: str, index: int) -> bool:
        assert kind == self.track_kind and index == 1
        return False

    def GetMarkers(self) -> dict[int, dict[str, Any]]:
        return self.markers

    def GetMarkerCustomData(self, frame: int) -> str:
        assert frame == 5
        return self.marker_stamp

    def SetStartTimecode(self, _value: str) -> bool:
        return True

    def AddTrack(self, *_args: Any) -> bool:
        return True

    def SetTrackName(self, *_args: Any) -> bool:
        return True

    def AddMarker(self, *_args: Any) -> bool:
        return True


class _EmptyFolder:
    def __init__(self, clips: list[Any] | None = None) -> None:
        self.clips = [] if clips is None else clips

    def GetUniqueId(self) -> str:
        return "empty-folder"

    def GetClipList(self) -> list[Any]:
        return self.clips

    def GetSubFolderList(self) -> list[Any]:
        return []


class _PoolItem:
    def __init__(self, uid: Any) -> None:
        self.uid = uid

    def GetUniqueId(self) -> Any:
        return self.uid


class _EmptyPool:
    def __init__(self, clips: list[Any] | None = None) -> None:
        self.root = _EmptyFolder(clips)

    def ImportMedia(self, _paths: list[str]) -> list[Any]:
        return []

    def GetRootFolder(self) -> _EmptyFolder:
        return self.root


class _EmptyTargetTimeline:
    def __init__(
        self,
        counts: dict[str, int],
        items: dict[tuple[str, int], list[Any]] | None = None,
        pool_item: _PoolItem | None = None,
        start_frame: Any = 0,
        start_timecode_result: Any = True,
        start_timecode_readback: Any = None,
    ) -> None:
        self.counts = counts
        self.items = {} if items is None else items
        self.pool_item = (
            _PoolItem("target-timeline-pool-item") if pool_item is None else pool_item
        )
        self.start_frame = start_frame
        self.start_timecode_result = start_timecode_result
        self.start_timecode_readback = start_timecode_readback
        self.start_timecode_calls: list[str] = []

    def GetStartFrame(self) -> Any:
        return self.start_frame

    def SetStartTimecode(self, timecode: str) -> Any:
        self.start_timecode_calls.append(timecode)
        if self.start_timecode_result is True:
            self.start_frame = (
                0
                if self.start_timecode_readback is None
                else self.start_timecode_readback
            )
        return self.start_timecode_result

    def GetTrackCount(self, kind: str) -> int:
        return self.counts.get(kind, 0)

    def GetItemListInTrack(self, kind: str, index: int) -> list[Any]:
        return self.items.get((kind, index), [])

    def GetMarkers(self) -> dict[int, Any]:
        return {}

    def GetMediaPoolItem(self) -> _PoolItem:
        return self.pool_item


class _EmptyTargetProject:
    def __init__(
        self, timeline: _EmptyTargetTimeline, clips: list[Any] | None = None
    ) -> None:
        self.timeline = timeline
        self.pool = _EmptyPool([timeline.pool_item] if clips is None else clips)
        self.settings: dict[str, Any] = {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        }
        self.set_calls: list[tuple[str, str]] = []

    def GetMediaPool(self) -> _EmptyPool:
        return self.pool

    def GetSetting(self, key: str) -> Any:
        return self.settings[key]

    def SetSetting(self, key: str, value: str) -> bool:
        self.set_calls.append((key, value))
        self.settings[key] = value
        return True


def test_empty_target_accepts_empty_default_video_audio_tracks() -> None:
    timeline = _EmptyTargetTimeline({"video": 1, "audio": 1, "subtitle": 0})
    project = _EmptyTargetProject(timeline)

    assert (
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )
        == 0
    )


def test_empty_target_admits_nonzero_frame_for_later_normalization() -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0}, start_frame=86_400
    )
    project = _EmptyTargetProject(timeline)

    assert (
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )
        == 86_400
    )
    assert timeline.start_timecode_calls == []


@pytest.mark.parametrize("start_frame", [None, -1, True])
def test_empty_target_rejects_unreadable_or_invalid_start_frame(
    start_frame: Any,
) -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0}, start_frame=start_frame
    )
    project = _EmptyTargetProject(timeline)

    with pytest.raises(
        OutputConsistencyError, match="start frame is unreadable or invalid"
    ):
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )
    assert timeline.start_timecode_calls == []


@pytest.mark.parametrize("other_uid", ["imported-media", "another-timeline"])
def test_empty_target_rejects_unrelated_media_pool_items(other_uid: str) -> None:
    timeline = _EmptyTargetTimeline({"video": 1, "audio": 1, "subtitle": 0})
    project = _EmptyTargetProject(timeline, [timeline.pool_item, _PoolItem(other_uid)])

    with pytest.raises(OutputConsistencyError, match="already contains media"):
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )


def test_empty_target_rejects_duplicate_or_unreadable_pool_item_uids() -> None:
    timeline = _EmptyTargetTimeline({"video": 1, "audio": 1, "subtitle": 0})
    duplicate_project = _EmptyTargetProject(
        timeline,
        [timeline.pool_item, _PoolItem("target-timeline-pool-item")],
    )

    with pytest.raises(
        OutputConsistencyError, match="duplicate target media-pool item"
    ):
        native._check_empty_target(
            duplicate_project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )

    unreadable_project = _EmptyTargetProject(
        timeline, [timeline.pool_item, _PoolItem(None)]
    )
    with pytest.raises(OutputConsistencyError, match="identity is unreadable"):
        native._check_empty_target(
            unreadable_project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )


def test_empty_target_rejects_unreadable_target_timeline_pool_item_uid() -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0},
        pool_item=_PoolItem(None),
    )
    project = _EmptyTargetProject(timeline)

    with pytest.raises(OutputConsistencyError, match="identity is unreadable"):
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )


@pytest.mark.parametrize(
    ("counts", "items", "message"),
    [
        ({"video": 2, "audio": 1, "subtitle": 0}, {}, "unexpected or unsupported"),
        ({"video": 1, "audio": 1, "subtitle": 1}, {}, "unexpected or unsupported"),
        (
            {"video": 1, "audio": 1, "subtitle": 0},
            {("video", 1): [object()]},
            "contains items",
        ),
    ],
)
def test_empty_target_rejects_extra_unsupported_or_populated_tracks(
    counts: dict[str, int], items: dict[tuple[str, int], list[Any]], message: str
) -> None:
    timeline = _EmptyTargetTimeline(counts, items)
    project = _EmptyTargetProject(timeline)

    with pytest.raises(OutputConsistencyError, match=message):
        native._check_empty_target(
            project,
            timeline,
            {"video": 1, "audio": 1, "subtitle": 0},
        )


def test_matching_locked_project_settings_are_verified_without_setter(
    tmp_path: Path,
) -> None:
    project = _EmptyTargetProject(_EmptyTargetTimeline({"video": 1, "audio": 1}))
    state, _request = _effect_state(tmp_path)

    native._set_project_settings(
        project,
        {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
            "timelineSampleRate": "48000",
        },
        state,
    )

    assert project.set_calls == []
    assert state["effects"] == []


def test_numeric_timeline_rate_is_a_matching_project_setting(
    tmp_path: Path,
) -> None:
    project = _EmptyTargetProject(_EmptyTargetTimeline({"video": 1, "audio": 1}))
    project.settings["timelineFrameRate"] = 23.976
    state, _request = _effect_state(tmp_path)

    native._set_project_settings(project, {"timelineFrameRate": "23.976"}, state)

    assert project.set_calls == []
    assert state["effects"] == []


def test_mismatched_project_setting_is_set_and_read_back_exactly(
    tmp_path: Path,
) -> None:
    project = _EmptyTargetProject(_EmptyTargetTimeline({"video": 1, "audio": 1}))
    project.settings["timelineResolutionWidth"] = "1280"
    state, _request = _effect_state(tmp_path)

    native._set_project_settings(
        project,
        {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
        },
        state,
    )

    assert project.set_calls == [("timelineResolutionWidth", "1920")]
    assert project.GetSetting("timelineResolutionWidth") == "1920"


@pytest.mark.parametrize("actual", [23.976, "23.976"])
def test_timeline_rate_comparison_accepts_only_exact_documented_match(
    actual: Any,
) -> None:
    assert native._setting_matches("timelineFrameRate", "23.976", actual)


@pytest.mark.parametrize(
    "actual",
    [
        24.0,
        "24",
        23.9760001,
        "23.9760001",
        True,
        float("nan"),
        float("inf"),
        23,
        object(),
    ],
)
def test_timeline_rate_comparison_rejects_wrong_or_unsupported_values(
    actual: Any,
) -> None:
    assert not native._setting_matches("timelineFrameRate", "23.976", actual)


def test_numeric_timeline_rate_readback_is_retained_in_effect_observation(
    tmp_path: Path,
) -> None:
    class NumericRateReadbackProject(_EmptyTargetProject):
        def SetSetting(self, key: str, value: str) -> bool:
            self.set_calls.append((key, value))
            self.settings[key] = 23.976 if key == "timelineFrameRate" else value
            return True

    project = NumericRateReadbackProject(_EmptyTargetTimeline({"video": 1, "audio": 1}))
    project.settings["timelineFrameRate"] = 24.0
    state, _request = _effect_state(tmp_path)

    native._set_project_settings(project, {"timelineFrameRate": "23.976"}, state)

    assert project.set_calls == [("timelineFrameRate", "23.976")]
    assert state["effects"][0]["outcome"] == "observed"
    observed_path = Path(state["effects"][0]["path"]).with_name("0000-observed.json")
    observed = _parse(native._read(observed_path, "test numeric rate observation"))
    assert observed["observation"] == {"return": True, "value": 23.976}


def test_wrong_numeric_timeline_rate_readback_reports_safe_value_and_type(
    tmp_path: Path,
) -> None:
    class WrongRateReadbackProject(_EmptyTargetProject):
        def SetSetting(self, key: str, value: str) -> bool:
            self.set_calls.append((key, value))
            self.settings[key] = 24.0 if key == "timelineFrameRate" else value
            return True

    project = WrongRateReadbackProject(_EmptyTargetTimeline({"video": 1, "audio": 1}))
    project.settings["timelineFrameRate"] = 24.0
    state, _request = _effect_state(tmp_path)

    with pytest.raises(OutputConsistencyError, match=r"actual 24\.0 \(float\)"):
        native._set_project_settings(project, {"timelineFrameRate": "23.976"}, state)

    assert project.set_calls == [("timelineFrameRate", "23.976")]
    assert len(state["effects"]) == 1
    assert state["effects"][0]["outcome"] == "unknown"


def _geometry_case(
    tmp_path: Path,
    *,
    source_audio: bool = False,
    frame_rate: Any = "23.976",
    project_sample_rate: Any = "48000",
) -> tuple[Any, dict[str, Any], dict[str, Any], _Item, _Timeline]:
    tmp_path = tmp_path.resolve()
    source_root = tmp_path / "verified-public-package"
    source_path = source_root / "media/shot.mov"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"verified source bytes")
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    track_id = "audio-main" if source_audio else "video-main"
    track_kind = "audio" if source_audio else "video"
    track_name = "A1" if source_audio else "V1"
    event: dict[str, Any] = {
        "id": "event-one",
        "kind": "source_audio" if source_audio else "primary_visual",
        "trackId": track_id,
        "trackKind": track_kind,
        "sourceId": "picture-one",
        "recordRange": {"startFrame": 0, "durationFrames": 10},
        "sourceRange": {"startFrame": 12, "durationFrames": 10},
        "v2Event": {"id": "event-one", "description": "one frame range"},
    }
    if source_audio:
        event["gainDb"] = -6.0
    marker = {
        "id": "marker-one",
        "frame": 5,
        "color": "CYAN",
        "name": "Act I",
        "note": "chapter",
        "provenance": {"source": "accepted-v2-marker"},
    }
    item = _Item(_Media(source_path), native._event_stamp(event))
    item.source_end_frame = 21 if source_audio else 22
    timeline = _Timeline(
        item, track_kind=track_kind, track_name=track_name, frame_rate=frame_rate
    )
    timeline.marker_stamp = native._marker_stamp(marker)
    project = type(
        "Project",
        (),
        {
            "GetUniqueId": lambda _self: "project-one",
            "GetName": lambda _self: "disposable-project",
            "GetCurrentTimeline": lambda _self: timeline,
            "GetMediaPool": lambda _self: object(),
            "GetSetting": lambda _self, key: (
                project_sample_rate if key == "timelineSampleRate" else "value"
            ),
            "SetSetting": lambda _self, *_args: True,
        },
    )()
    manager = type(
        "ProjectManager",
        (),
        {
            "GetCurrentProject": lambda _self: project,
            "SaveProject": lambda _self: True,
            "CloseProject": lambda _self, _project: True,
            "LoadProject": lambda _self, _name: project,
        },
    )()
    resolve = type("Resolve", (), {"GetProjectManager": lambda _self: manager})()
    context = _context()
    wrapper_root = tmp_path / "qualification-wrapper" / "package"
    request: dict[str, Any] = {
        "target": context["target"],
        "context": context,
        "package": {"packageRoot": str(wrapper_root)},
    }
    timeline_manifest = {
        "startFrame": 0,
        "durationFrames": 10,
        "frameRate": {"numerator": 24000, "denominator": 1001},
        "width": 1920,
        "height": 1080,
        "audioSampleRate": 48000,
    }
    admitted = {
        "sourceRoot": source_root,
        "manifest": {"timeline": timeline_manifest},
        "view": {
            "timeline": timeline_manifest,
            "tracks": [
                {"id": track_id, "kind": track_kind, "index": 1, "name": track_name}
            ],
            "sources": [
                {
                    "id": "picture-one",
                    "kind": "audio" if source_audio else "video",
                    "path": "media/shot.mov",
                    "contentHash": source_hash,
                }
            ],
            "events": [event],
            "markers": [marker],
        },
    }
    return resolve, request, admitted, item, timeline


@pytest.mark.parametrize("source_audio", [False, True])
def test_geometry_uses_verified_source_root_and_checks_exact_native_ranges(
    tmp_path: Path, source_audio: bool
) -> None:
    resolve, request, admitted, _item, _timeline = _geometry_case(
        tmp_path, source_audio=source_audio
    )
    geometry = native._capture_geometry(resolve, request, admitted, None)
    assert geometry["items"][0]["sourceStart"] == 12
    assert geometry["items"][0]["sourceDuration"] == 10
    assert geometry["items"][0]["sourceMappingSha256"] is None
    assert geometry["extentFrames"] == 10


@pytest.mark.parametrize(
    ("source_audio", "source_end_frame"),
    [(False, 21), (False, 23), (True, 20), (True, 22)],
)
def test_geometry_rejects_source_end_one_frame_short_or_long(
    tmp_path: Path, source_audio: bool, source_end_frame: int
) -> None:
    resolve, request, admitted, item, _timeline = _geometry_case(
        tmp_path, source_audio=source_audio
    )
    item.source_end_frame = source_end_frame

    with pytest.raises(
        OutputConsistencyError,
        match=(
            rf"native source range differs .*start=12, end={source_end_frame}, "
            r"expectedStart=12, expectedDuration=10"
        ),
    ):
        native._capture_geometry(resolve, request, admitted, None)


def test_geometry_accepts_numeric_timeline_rate_readback(tmp_path: Path) -> None:
    resolve, request, admitted, _item, _timeline = _geometry_case(
        tmp_path, frame_rate=23.976
    )

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["rate"] == admitted["manifest"]["timeline"]["frameRate"]


def test_geometry_reports_mismatched_numeric_rate_readback(tmp_path: Path) -> None:
    resolve, request, admitted, _item, _timeline = _geometry_case(
        tmp_path, frame_rate=24.0
    )

    with pytest.raises(OutputConsistencyError, match=r"actual 24\.0 \(float\)"):
        native._capture_geometry(resolve, request, admitted, None)


@pytest.mark.parametrize("sample_rate", ["44100", "48000x", None])
def test_geometry_reads_exact_sample_rate_from_project(
    tmp_path: Path, sample_rate: Any
) -> None:
    resolve, request, admitted, _item, _timeline = _geometry_case(
        tmp_path, project_sample_rate=sample_rate
    )

    with pytest.raises(
        OutputConsistencyError,
        match="native project setting timelineSampleRate differs or is unreadable",
    ):
        native._capture_geometry(resolve, request, admitted, None)


def test_geometry_rechecks_source_audio_controls_after_reopen(tmp_path: Path) -> None:
    resolve, request, admitted, item, _timeline = _geometry_case(
        tmp_path, source_audio=True
    )
    native._capture_geometry(resolve, request, admitted, None)
    item.properties["AudioVolume"] = -4.0
    with pytest.raises(
        OutputConsistencyError, match="reopened source-audio controls differ"
    ):
        native._capture_geometry(resolve, request, admitted, None)


@pytest.mark.parametrize(
    ("source_audio", "speed"),
    [
        (False, {"Percentage": 100.0}),
        (True, {"Percentage": 100.0, "PitchCorrection": True}),
    ],
)
def test_geometry_accepts_installed_speed_option_shapes(
    tmp_path: Path, source_audio: bool, speed: dict[str, Any]
) -> None:
    resolve, request, admitted, item, _timeline = _geometry_case(
        tmp_path, source_audio=source_audio
    )
    item.speed = speed

    geometry = native._capture_geometry(resolve, request, admitted, None)

    assert geometry["items"][0]["sourceDuration"] == 10


@pytest.mark.parametrize(
    "speed",
    [
        {},
        {"PitchCorrection": False},
        {"Percentage": True},
        {"Percentage": 99.0},
        {"Percentage": float("nan")},
        {"Percentage": float("inf")},
        {"Percentage": 100.0, "PitchCorrection": "true"},
        {"Percentage": 100.0, "StretchKeyframesToFit": True},
        {"Percentage": 100.0, "RippleTimeline": True},
        {"Percentage": 100.0, "UnreviewedOption": False},
    ],
)
def test_geometry_rejects_malformed_or_unsafe_speed_options(
    tmp_path: Path, speed: dict[str, Any]
) -> None:
    resolve, request, admitted, item, _timeline = _geometry_case(tmp_path)
    item.speed = speed

    with pytest.raises(OutputConsistencyError):
        native._capture_geometry(resolve, request, admitted, None)


@pytest.mark.parametrize(
    "drift", ["speed", "fractional_frame", "source_range", "marker"]
)
def test_geometry_refuses_unqualified_speed_frame_or_marker_drift(
    tmp_path: Path, drift: str
) -> None:
    resolve, request, admitted, item, timeline = _geometry_case(tmp_path)
    if drift == "speed":
        item.speed["StretchKeyframesToFit"] = True
    elif drift == "fractional_frame":
        item.true_start = 1
    elif drift == "source_range":
        item.source_start_frame = 13
    else:
        timeline.markers[5]["name"] = "changed chapter"
    diagnostic = (
        r"native source range differs \(track=video:1, "
        r"itemUid=timeline-item-one, eventId=event-one, "
        r"start=13, end=22, "
        r"expectedStart=12, expectedDuration=10\)"
        if drift == "source_range"
        else None
    )
    with pytest.raises(OutputConsistencyError, match=diagnostic):
        native._capture_geometry(resolve, request, admitted, None)


def _lineage_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[
    dict[str, Any], dict[str, Any], dict[str, Any], str, dict[Path, dict[str, Any]]
]:
    state_root = tmp_path.resolve() / "native-state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", state_root)
    context = _context()
    request: dict[str, Any] = {
        "action": "capture_post",
        "sequence": len(native.APPROVAL_ACTION_PLAN) - 1,
        "context": context,
        "reservation": {"sha256": "3" * 64},
        "renderIntent": {"sha256": "4" * 64},
    }
    queue_path = native.native_request_paths(context, 3)[0]
    start_path = native.native_request_paths(context, 4)[0]
    queue_path.parent.mkdir(parents=True)
    start_path.parent.mkdir(parents=True)
    queue_path.write_bytes(_canonical({"stage": "queue"}))
    start_path.write_bytes(_canonical({"stage": "start"}))
    queue_sha = hashlib.sha256(queue_path.read_bytes()).hexdigest()
    start_sha = hashlib.sha256(start_path.read_bytes()).hexdigest()
    completion_sha = "5" * 64
    common = {
        "context": context,
        "status": "complete",
        "jobId": "job-one",
        "outputPath": str(tmp_path.resolve() / "deliver.mov"),
        "settings": {"container": "mov", "audioCodec": "lpcm"},
        "commitmentRawSha256": "1" * 64,
        "reservationSha256": request["reservation"]["sha256"],
        "renderIntentSha256": request["renderIntent"]["sha256"],
    }
    queue = {**common, "action": "queue_render"}
    start = {**common, "action": "start_render", "queuedResultSha256": queue_sha}
    completion = {
        **common,
        "action": "poll_render",
        "queuedResultSha256": queue_sha,
        "startedResultSha256": start_sha,
        "sourceOutputRawSha256": "6" * 64,
    }
    lineage = {
        "schemaVersion": "qualification-output-lineage/v1",
        "lane": LANE,
        "context": context,
        "commitmentRawSha256": common["commitmentRawSha256"],
        "reservationRawSha256": common["reservationSha256"],
        "renderIntentSha256": common["renderIntentSha256"],
        "effectReceiptSha256": queue_sha,
        "startReceiptSha256": start_sha,
        "completionReceiptSha256": completion_sha,
        "jobId": common["jobId"],
        "sourceOutputRawSha256": completion["sourceOutputRawSha256"],
    }
    results = {queue_path: queue, start_path: start}
    return request, lineage, completion, completion_sha, results


def test_render_lineage_authenticates_fixed_queue_start_and_completion_chain(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, lineage, completion, completion_sha, results = _lineage_case(
        tmp_path, monkeypatch
    )

    def verify(path: Path, expected_sha256: str) -> dict[str, Any]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256
        return results[path]

    monkeypatch.setattr(native, "verify_native_result", verify)
    native._verify_render_lineage(request, lineage, completion, completion_sha)

    lineage["startReceiptSha256"] = "f" * 64
    with pytest.raises(OutputConsistencyError, match="receipt hashes differ"):
        native._verify_render_lineage(request, lineage, completion, completion_sha)


def test_render_lineage_rejects_cross_bound_job_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, lineage, completion, completion_sha, results = _lineage_case(
        tmp_path, monkeypatch
    )
    completion["jobId"] = "different-job"

    def verify(path: Path, expected_sha256: str) -> dict[str, Any]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256
        return results[path]

    monkeypatch.setattr(native, "verify_native_result", verify)
    with pytest.raises(
        OutputConsistencyError, match="native render stage binding differs"
    ):
        native._verify_render_lineage(request, lineage, completion, completion_sha)


def test_render_lineage_rejects_completion_with_a_different_started_hash(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    request, lineage, completion, completion_sha, results = _lineage_case(
        tmp_path, monkeypatch
    )
    completion["startedResultSha256"] = "f" * 64

    def verify(path: Path, expected_sha256: str) -> dict[str, Any]:
        assert hashlib.sha256(path.read_bytes()).hexdigest() == expected_sha256
        return results[path]

    monkeypatch.setattr(native, "verify_native_result", verify)
    with pytest.raises(OutputConsistencyError, match="receipt hashes differ"):
        native._verify_render_lineage(request, lineage, completion, completion_sha)


def test_start_render_uses_dedicated_status_for_exact_queued_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, state, request = _start_render_case(
        tmp_path, monkeypatch, {"JobStatus": "Ready"}
    )

    result = native._start_render(request, object(), state, None)

    assert project.status_calls == ["job-one"]
    assert project.start_calls == [["job-one"]]
    assert result["jobId"] == "job-one"
    assert state["effects"][0]["method"] == "Project.StartRendering"
    assert state["effects"][0]["outcome"] == "observed"


@pytest.mark.parametrize(
    "status_response",
    [
        None,
        {},
        {"JobStatus": 1},
        {"JobStatus": "Rendering"},
        {"JobStatus": "Complete"},
        {"JobStatus": "Failed"},
        {"JobStatus": "Cancelled"},
        {"JobStatus": "Ready for background render"},
        {"JobStatus": "Ready to remotely render"},
        {"JobStatus": "unknown"},
    ],
)
def test_start_render_refuses_any_status_other_than_local_ready(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_response: Any,
) -> None:
    project, state, request = _start_render_case(tmp_path, monkeypatch, status_response)

    with pytest.raises(OutputConsistencyError):
        native._start_render(request, object(), state, None)

    assert project.status_calls == ["job-one"]
    assert project.start_calls == []
    assert state["effects"] == []


def test_start_render_refuses_missing_or_unreadable_status_before_start(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, state, request = _start_render_case(
        tmp_path / "missing-getter",
        monkeypatch,
        RuntimeError("private status detail"),
        include_status_getter=False,
    )

    with pytest.raises(
        OutputConsistencyError, match="render job status unavailable before start"
    ):
        native._start_render(request, object(), state, None)

    assert project.start_calls == []
    assert state["effects"] == []

    project, state, request = _start_render_case(
        tmp_path / "unreadable-getter",
        monkeypatch,
        RuntimeError("private status detail"),
    )

    with pytest.raises(
        OutputConsistencyError, match="render job status unreadable before start"
    ):
        native._start_render(request, object(), state, None)

    assert project.status_calls == ["job-one"]
    assert project.start_calls == []
    assert state["effects"] == []


@pytest.mark.parametrize(
    ("render_status", "expected_status"),
    [("Complete", "complete"), ("Failed", "partial")],
)
def test_poll_result_retains_queue_and_start_hashes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    render_status: str,
    expected_status: str,
) -> None:
    started_path = tmp_path.resolve() / "started-result.json"
    started_path.write_bytes(b"fixed started result")
    output_path = tmp_path.resolve() / "deliver.mov"
    output_path.write_bytes(b"rendered bytes")
    started_sha = hashlib.sha256(started_path.read_bytes()).hexdigest()
    queued_sha = "a" * 64
    previous = {
        "jobId": "job-one",
        "outputPath": str(output_path),
        "settings": {"container": "mov", "audioCodec": "lpcm"},
        "commitmentRawSha256": "1" * 64,
        "reservationSha256": "2" * 64,
        "renderIntentSha256": "3" * 64,
        "queuedResultSha256": queued_sha,
        "startedAt": "2026-10-16T12:00:00Z",
    }
    request = {
        "payload": {
            "startedResultPath": str(started_path),
            "startedResultSha256": started_sha,
            "jobId": "job-one",
        }
    }
    project = type(
        "Project",
        (),
        {"GetRenderJobStatus": lambda _self, _job_id: {"JobStatus": render_status}},
    )()
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda _request, _action: (previous, started_sha, started_path),
    )
    monkeypatch.setattr(
        native,
        "_project_timeline",
        lambda *_args: (None, project, None),
    )

    result = native._poll_render(request, object(), {}, None)

    assert result.get("status", "complete") == expected_status
    assert result["queuedResultSha256"] == queued_sha
    assert result["startedResultSha256"] == started_sha


def test_poll_render_uses_the_full_bounded_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    started_path = tmp_path.resolve() / "started-result.json"
    started_path.write_bytes(b"fixed started result")
    output_path = tmp_path.resolve() / "deliver.mov"
    started_sha = hashlib.sha256(started_path.read_bytes()).hexdigest()
    previous = {
        "jobId": "job-one",
        "outputPath": str(output_path),
        "settings": {"container": "mov", "audioCodec": "lpcm"},
        "commitmentRawSha256": "1" * 64,
        "reservationSha256": "2" * 64,
        "renderIntentSha256": "3" * 64,
        "queuedResultSha256": "4" * 64,
        "startedAt": "2026-10-16T12:00:00Z",
    }
    request = {
        "payload": {
            "startedResultPath": str(started_path),
            "startedResultSha256": started_sha,
            "jobId": "job-one",
        }
    }
    clock = [0.0]
    polls = [0]

    class Project:
        def GetRenderJobStatus(self, _job_id: str) -> dict[str, str]:
            polls[0] += 1
            return {"JobStatus": "Rendering"}

    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda _request, _action: (previous, started_sha, started_path),
    )
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, Project(), None)
    )
    monkeypatch.setattr(time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(
        time,
        "sleep",
        lambda seconds: clock.__setitem__(0, clock[0] + seconds),
    )

    result = native._poll_render(request, object(), {}, None)

    assert result["status"] == "partial"
    assert native.MAX_POLL_COUNT == 721
    assert polls[0] == native.MAX_POLL_COUNT
    assert clock[0] == native.MAX_POLL_SECONDS


@pytest.mark.parametrize(
    ("action", "prior_action"),
    [("poll_render", "start_render"), ("capture_post", "poll_render")],
)
def test_expired_readonly_stages_require_prior_native_lineage(
    monkeypatch: pytest.MonkeyPatch, action: str, prior_action: str
) -> None:
    calls: list[str] = []

    def record(
        _request: dict[str, Any], prior: str
    ) -> tuple[dict[str, Any], str, Path]:
        calls.append(prior)
        return {}, "a" * 64, Path("/tmp/result")

    monkeypatch.setattr(
        native,
        "_previous_result",
        record,
    )

    native._verify_readonly_native_lineage({"action": action})

    assert calls == [prior_action]


@pytest.mark.parametrize(
    ("action", "prior_action"),
    [("poll_render", "start_render"), ("capture_post", "poll_render")],
)
@pytest.mark.parametrize(
    ("stage_error_type", "error_message", "expected_reason"),
    [
        (None, "", ""),
        (
            OutputConsistencyError,
            "target pool identity is unreadable",
            "target pool identity is unreadable",
        ),
        (
            RuntimeError,
            "private path should stay redacted",
            "RuntimeError: native stage stopped; retained effects are not retried",
        ),
    ],
)
def test_dispatcher_uses_historical_auth_only_after_readonly_lineage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
    prior_action: str,
    stage_error_type: type[Exception] | None,
    error_message: str,
    expected_reason: str,
) -> None:
    monkeypatch.setattr(native, "NATIVE_RELEASE_ROOT", tmp_path.resolve())
    request_path = tmp_path.resolve() / "request.json"
    request_raw = b"retained request"
    request_path.write_bytes(request_raw)
    request = {
        "action": action,
        "context": {},
        "sequence": 1,
        "resultPath": str(request_path),
        "priorResultSha256": "a" * 64,
        "package": {"admissionSha256": "b" * 64},
        "authority": {"approvalPath": str(tmp_path / "approval.json")},
        "intent": None,
        "reservation": None,
        "renderIntent": None,
        "payload": {},
        "release": None,
        "sourceGraph": None,
    }
    calls: list[tuple[str, object]] = []

    monkeypatch.setattr(
        native, "verify_native_request", lambda *_args, **_kwargs: request
    )
    monkeypatch.setattr(
        native,
        "native_request_paths",
        lambda *_args: (request_path, "unused", "unused", request_path),
    )
    monkeypatch.setattr(
        native,
        "_admission_profile",
        lambda _request: {"admission": {"packageInventorySha256": "c" * 64}},
    )
    monkeypatch.setattr(
        native,
        "_verify_readonly_native_lineage",
        lambda _request: calls.append(("lineage", prior_action)),
    )

    def reservation(_request: dict[str, Any], *, current: bool) -> None:
        calls.append(("reservation", current))

    def authority(
        _request: dict[str, Any], *, current: bool
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        calls.append(("authority", current))
        return {"approvalPath": str(tmp_path / "approval.json")}, "d" * 64, {}

    monkeypatch.setattr(native, "_verify_reservation", reservation)
    monkeypatch.setattr(native, "_verify_authority", authority)
    monkeypatch.setattr(
        native,
        "_verify_intent",
        lambda *_args: ({}, "e" * 64),
    )
    monkeypatch.setattr(
        native, "_verify_installed_release", lambda *_args, **_kwargs: {}
    )
    monkeypatch.setattr(native, "_claim_prepared_native_operation", lambda *_args: None)
    monkeypatch.setattr(
        native,
        "_base_result",
        lambda *_args: {"approvalPath": None, "settings": None},
    )
    monkeypatch.setattr(native, "_connected", lambda _resolve: {})

    def native_stage(*_args: Any) -> dict[str, Any]:
        if stage_error_type is not None:
            raise stage_error_type(error_message)
        return {
            "status": "complete",
            "inputBindingPath": str(tmp_path / "input-binding.json"),
            "inputBindingSha256": "a" * 64,
            "completionResultSha256": "b" * 64,
            "renderLineageSha256": "c" * 64,
        }

    monkeypatch.setattr(native, "_native_stage", native_stage)
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: ({"settings": {}}, "f" * 64, request_path),
    )
    published: list[dict[str, Any]] = []

    def publish(path: Path, result: dict[str, Any]) -> Path:
        published.append(result)
        return path

    monkeypatch.setattr(native, "_publish", publish)

    result = native.run_qualification_output_request(
        object(),
        request_path,
        expected_request_sha256=hashlib.sha256(request_raw).hexdigest(),
    )

    assert result == request_path
    assert published[0]["reason"] == expected_reason
    if stage_error_type is not None:
        assert published[0]["status"] == "refused"
        assert published[0]["effectLedger"] == []
    assert calls == [
        ("lineage", prior_action),
        ("reservation", False),
        ("authority", False),
    ]


def _effect_state(tmp_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    context = _context()
    request_path = tmp_path.resolve() / "operations/00000000/request.json"
    request_path.parent.mkdir(parents=True)
    request = {
        "context": context,
        "resultPath": str(request_path),
        "operationId": "operation-one",
        "sequence": 0,
    }
    state = {
        "request": request,
        "authoritySha256": "7" * 64,
        "intentSha256": "8" * 64,
        "effects": [],
    }
    return state, request


def _queue_render_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    video_codecs: dict[str, str] | None = None,
    selected_readback: dict[str, str] | None = None,
    job_video_codec: str = "Apple ProRes 422",
    job_audio_codec: str = "Linear PCM",
    job_render_mode: str = "Single clip",
) -> tuple[Any, dict[str, Any], dict[str, Any], list[tuple[str, Any]]]:
    output_path = tmp_path.resolve() / "deliver.mov"
    settings = dict(native.RENDER_SETTINGS)
    request = {
        "payload": {
            "settings": settings,
            "outputPath": str(output_path),
            "outputFilename": output_path.stem,
        },
        "package": {"packageRoot": str(tmp_path.resolve())},
        "profile": native.SYNTHETIC_PROFILE,
        "renderIntent": {},
        "reservation": {"path": str(tmp_path.resolve() / "reservation.json")},
        "context": {},
    }
    state: dict[str, Any] = {"effects": []}
    observations: list[tuple[str, Any]] = []

    class Project:
        def __init__(self) -> None:
            self.selection_calls: list[tuple[str, str]] = []
            self.render_settings: dict[str, Any] | None = None
            self.jobs: list[dict[str, Any]] = []
            self.render_mode = 0
            self.render_mode_calls: list[int] = []
            self.selected_codec = selected_readback or {
                "format": "mov",
                "codec": "ProRes422",
            }

        def GetRenderFormats(self) -> dict[str, str]:
            return {"QuickTime": "mov"}

        def GetRenderCodecs(self, _format: str) -> dict[str, str]:
            return (
                {"Apple ProRes 422": "ProRes422"}
                if video_codecs is None
                else video_codecs
            )

        def GetAudioRenderCodecs(self, _format: str) -> dict[str, str]:
            return {"Linear PCM": "lpcm"}

        def GetRenderJobList(self) -> list[dict[str, Any]]:
            return list(self.jobs)

        def SetCurrentRenderFormatAndCodec(self, fmt: str, codec: str) -> bool:
            self.selection_calls.append((fmt, codec))
            return True

        def GetCurrentRenderFormatAndCodec(self) -> dict[str, str]:
            return self.selected_codec

        def SetCurrentRenderMode(self, mode: int) -> bool:
            self.render_mode_calls.append(mode)
            self.render_mode = mode
            return True

        def GetCurrentRenderMode(self) -> int:
            return self.render_mode

        def SetRenderSettings(self, render_settings: dict[str, Any]) -> bool:
            self.render_settings = render_settings
            return True

        def AddRenderJob(self) -> str:
            assert self.render_settings is not None
            self.jobs.append(
                {
                    "JobId": "job-one",
                    "TargetDir": str(output_path.parent),
                    "OutputFilename": output_path.name,
                    "IsExportVideo": True,
                    "IsExportAudio": True,
                    "AudioCodec": job_audio_codec,
                    "AudioBitDepth": 24,
                    "AudioSampleRate": 48000,
                    "FormatWidth": 1920,
                    "FormatHeight": 1080,
                    "VideoCodec": job_video_codec,
                    "VideoFormat": "QuickTime",
                    "RenderMode": job_render_mode,
                }
            )
            return "job-one"

    project = Project()
    monkeypatch.setattr(native, "_previous_result", lambda *_args: None)
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, project, None)
    )
    monkeypatch.setattr(native, "_expected_settings", lambda *_args: settings)
    monkeypatch.setattr(
        native,
        "_read_ref",
        lambda *_args: (b"render intent", "a" * 64, None),
    )
    monkeypatch.setattr(
        native,
        "_read",
        lambda *_args, **_kwargs: b"reservation",
    )
    monkeypatch.setattr(
        native,
        "_parse",
        lambda _raw: {"commitmentRawSha256": "b" * 64},
    )
    monkeypatch.setattr(
        native,
        "verify_render_intent",
        lambda *_args, **_kwargs: {"outputPath": str(output_path)},
    )

    def private_effect(
        _state: dict[str, Any], method: str, arguments: Any
    ) -> dict[str, Any]:
        row = {"method": method, "arguments": arguments, "outcome": "unknown"}
        state["effects"].append(row)
        return row

    def effect_observed(
        _state: dict[str, Any], row: dict[str, Any], observation: Any
    ) -> None:
        row["outcome"] = "observed"
        observations.append((row["method"], observation))

    monkeypatch.setattr(native, "_private_effect", private_effect)
    monkeypatch.setattr(native, "_effect_observed", effect_observed)
    return project, request, state, observations


def _start_render_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status_response: Any,
    *,
    include_status_getter: bool = True,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    queued_sha = "a" * 64
    queued_path = tmp_path.resolve() / "queued-result.json"
    previous = {
        "jobId": "job-one",
        "outputPath": str(tmp_path.resolve() / "deliver.mov"),
        "settings": {"container": "mov", "audioCodec": "lpcm"},
        "commitmentRawSha256": "1" * 64,
        "renderIntentSha256": "2" * 64,
    }
    state, request = _effect_state(tmp_path)
    request["payload"] = {
        "queuedResultPath": str(queued_path),
        "queuedResultSha256": queued_sha,
        "jobId": "job-one",
    }

    class Project:
        def __init__(self) -> None:
            self.status_calls: list[str] = []
            self.start_calls: list[list[str]] = []

        def GetRenderJobList(self) -> list[dict[str, str]]:
            # The installed RenderJobInfo shape has JobId, but no JobStatus.
            return [{"JobId": "job-one"}]

        def StartRendering(self, job_ids: list[str]) -> bool:
            self.start_calls.append(list(job_ids))
            return True

    project = Project()
    if include_status_getter:

        def get_render_job_status(job_id: str) -> Any:
            project.status_calls.append(job_id)
            if isinstance(status_response, BaseException):
                raise status_response
            return status_response

        monkeypatch.setattr(
            project, "GetRenderJobStatus", get_render_job_status, raising=False
        )
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda _request, action: (
            (previous, queued_sha, queued_path)
            if action == "queue_render"
            else pytest.fail("unexpected predecessor action")
        ),
    )
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, project, None)
    )
    return project, state, request


@pytest.mark.parametrize(
    ("job_video_codec", "job_audio_codec"),
    [
        ("Apple ProRes 422", "Linear PCM"),
        ("ProRes422", "lpcm"),
    ],
)
def test_queue_render_uses_exact_resolve_codec_label_and_token(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_video_codec: str,
    job_audio_codec: str,
) -> None:
    project, request, state, observations = _queue_render_case(
        tmp_path,
        monkeypatch,
        job_video_codec=job_video_codec,
        job_audio_codec=job_audio_codec,
    )

    result = native._queue_render(
        request,
        object(),
        {
            "manifest": {
                "timeline": {
                    "width": 1920,
                    "height": 1080,
                    "frameRate": {"numerator": 24000, "denominator": 1001},
                }
            }
        },
        state,
        None,
    )

    assert result["settings"]["videoCodec"] == "prores422"
    assert project.selection_calls == [("mov", "ProRes422")]
    assert state["effects"][0]["arguments"] == {
        "format": "mov",
        "codec": "ProRes422",
    }
    assert project.render_mode_calls == [1]
    assert project.render_settings is not None
    assert project.render_settings["UseUniqueFilenames"] is False
    assert project.jobs[0]["RenderMode"] == "Single clip"
    assert observations[0] == (
        "Project.SetCurrentRenderFormatAndCodec",
        {"return": True, "formatCodec": {"format": "mov", "codec": "ProRes422"}},
    )
    assert observations[1] == (
        "Project.SetCurrentRenderMode",
        {"return": True, "renderMode": 1},
    )


def test_queue_render_rejects_individual_clips_job_even_after_single_clip_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, request, state, _observations = _queue_render_case(
        tmp_path, monkeypatch, job_render_mode="Individual clips"
    )

    with pytest.raises(
        OutputConsistencyError, match="queued render job is not a single clip"
    ):
        native._queue_render(
            request,
            object(),
            {
                "manifest": {
                    "timeline": {
                        "width": 1920,
                        "height": 1080,
                        "frameRate": {"numerator": 24000, "denominator": 1001},
                    }
                }
            },
            state,
            None,
        )

    assert project.render_mode_calls == [1]
    assert project.GetCurrentRenderMode() == 1
    assert project.jobs[0]["RenderMode"] == "Individual clips"


@pytest.mark.parametrize(
    "video_codecs",
    [
        {},
        {"Apple ProRes 422 HQ": "ProRes422HQ"},
        {"Apple ProRes 422": "prores422"},
        {"Apple ProRes 422": "ProRes422HQ"},
    ],
)
def test_queue_render_rejects_missing_or_different_prores_codec_mapping(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    video_codecs: dict[str, str],
) -> None:
    project, request, state, _observations = _queue_render_case(
        tmp_path, monkeypatch, video_codecs=video_codecs
    )

    with pytest.raises(
        OutputConsistencyError, match="Resolve lacks the exact ProRes 422 codec"
    ):
        native._queue_render(
            request, object(), {"manifest": {"timeline": {}}}, state, None
        )

    assert project.selection_calls == []
    assert state["effects"] == []


def test_queue_render_requires_exact_native_codec_readback_before_queueing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, request, state, _observations = _queue_render_case(
        tmp_path,
        monkeypatch,
        selected_readback={"format": "mov", "codec": "prores422"},
    )

    with pytest.raises(
        OutputConsistencyError, match="MOV/ProRes 422 selection did not read back"
    ):
        native._queue_render(
            request, object(), {"manifest": {"timeline": {}}}, state, None
        )

    assert project.selection_calls == [("mov", "ProRes422")]
    assert project.jobs == []
    assert state["effects"][0]["outcome"] == "unknown"


@pytest.mark.parametrize(
    "job_video_codec", ["ProRes 422 HQ", "ProRes422HQ", "prores422", "unknown"]
)
def test_queue_render_rejects_other_queued_codec_variants(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    job_video_codec: str,
) -> None:
    project, request, state, _observations = _queue_render_case(
        tmp_path, monkeypatch, job_video_codec=job_video_codec
    )

    with pytest.raises(
        OutputConsistencyError, match="queued render job codec/container differ"
    ):
        native._queue_render(
            request,
            object(),
            {
                "manifest": {
                    "timeline": {
                        "width": 1920,
                        "height": 1080,
                        "frameRate": {"numerator": 24000, "denominator": 1001},
                    }
                }
            },
            state,
            None,
        )

    assert project.selection_calls == [("mov", "ProRes422")]
    assert project.jobs[0]["VideoCodec"] == job_video_codec


def test_construct_normalizes_nonzero_empty_target_and_records_readback(
    tmp_path: Path,
) -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0}, start_frame=86_400
    )
    project = _EmptyTargetProject(timeline)
    start_frame = native._check_empty_target(
        project,
        timeline,
        {"video": 1, "audio": 1, "subtitle": 0},
    )
    state, _request = _effect_state(tmp_path)

    native._normalize_target_start_timecode(timeline, start_frame, state)

    assert timeline.start_timecode_calls == ["00:00:00:00"]
    assert timeline.GetStartFrame() == 0
    assert len(state["effects"]) == 1
    row = state["effects"][0]
    assert row["method"] == "Timeline.SetStartTimecode"
    assert row["outcome"] == "observed"
    observed_path = Path(row["path"]).with_name("0000-observed.json")
    observed = _parse(native._read(observed_path, "test start-timecode observation"))
    assert observed["observation"] == {"return": True, "startFrame": 0}


def test_construct_does_not_set_timecode_for_zero_start(tmp_path: Path) -> None:
    timeline = _EmptyTargetTimeline({"video": 1, "audio": 1, "subtitle": 0})
    state, _request = _effect_state(tmp_path)

    native._normalize_target_start_timecode(timeline, 0, state)

    assert timeline.start_timecode_calls == []
    assert state["effects"] == []


@pytest.mark.parametrize(
    ("setter_result", "readback"),
    [(False, None), (True, 86_400)],
)
def test_start_timecode_refusal_or_wrong_readback_stays_uncertain_without_retry(
    tmp_path: Path, setter_result: Any, readback: Any
) -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0},
        start_frame=86_400,
        start_timecode_result=setter_result,
        start_timecode_readback=readback,
    )
    state, _request = _effect_state(tmp_path)

    with pytest.raises(OutputConsistencyError):
        native._normalize_target_start_timecode(timeline, 86_400, state)

    assert timeline.start_timecode_calls == ["00:00:00:00"]
    assert len(state["effects"]) == 1
    assert state["effects"][0]["outcome"] == "unknown"
    assert native._failed_stage_status(state["effects"]) == "uncertain"


def test_construct_refuses_populated_target_before_timecode_setter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    timeline = _EmptyTargetTimeline(
        {"video": 1, "audio": 1, "subtitle": 0},
        items={("video", 1): [object()]},
        start_frame=86_400,
    )
    project = _EmptyTargetProject(timeline)
    state, _request = _effect_state(tmp_path)
    monkeypatch.setattr(native, "_connected", lambda _resolve: {})
    monkeypatch.setattr(
        native, "_project_timeline", lambda *_args: (None, project, timeline)
    )
    monkeypatch.setattr(
        native,
        "_required_track_counts",
        lambda _view: {"video": 1, "audio": 1, "subtitle": 0},
    )

    with pytest.raises(OutputConsistencyError, match="already contains items"):
        native._construct(object(), {}, {"manifest": {}, "view": {}}, state)

    assert timeline.start_timecode_calls == []
    assert state["effects"] == []


def test_effect_ledger_binds_method_arguments_chain_and_observation(
    tmp_path: Path,
) -> None:
    state, request = _effect_state(tmp_path)
    row = native._private_effect(
        state, "Project.SetSetting", {"key": "timelineFrameRate", "value": "23.976"}
    )
    native._effect_observed(state, row, {"return": True, "value": "23.976"})
    result = {
        "effectLedger": state["effects"],
        "status": "complete",
        "requestPath": request["resultPath"],
        "context": request["context"],
        "operationId": request["operationId"],
        "sequence": request["sequence"],
        "authoritySha256": state["authoritySha256"],
        "intentSha256": state["intentSha256"],
    }
    native._verify_effect_ledger(result)

    observed_path = Path(row["path"]).with_name("0000-observed.json")
    observed_raw = native._read(observed_path, "test observation")
    assert observed_path.stat().st_mode & 0o777 == 0o400
    observed = _parse(observed_raw)
    observed["observation"] = {"return": False, "value": "altered"}
    observed_path.chmod(0o600)
    observed_path.write_bytes(_canonical(observed))
    observed_path.chmod(0o400)
    with pytest.raises(
        OutputConsistencyError, match="native effect observation differs"
    ):
        native._verify_effect_ledger(result)
    observed_path.chmod(0o600)
    observed_path.write_bytes(observed_raw)
    observed_path.chmod(0o400)

    path = Path(row["path"])
    effect = _parse(native._read(path, "test effect"))
    effect["effectId"] = "9" * 64
    path.chmod(0o600)
    path.write_bytes(_canonical(effect))
    path.chmod(0o400)
    row["sha256"] = native._hash(_canonical(effect))
    with pytest.raises(OutputConsistencyError, match="native effect identity differs"):
        native._verify_effect_ledger(result)


def test_unknown_effect_has_no_observed_artifact(tmp_path: Path) -> None:
    state, request = _effect_state(tmp_path)
    row = native._private_effect(
        state, "Project.SetSetting", {"key": "timelineFrameRate", "value": "23.976"}
    )
    result = {
        "effectLedger": state["effects"],
        "status": "uncertain",
        "requestPath": request["resultPath"],
        "context": request["context"],
        "operationId": request["operationId"],
        "sequence": request["sequence"],
        "authoritySha256": state["authoritySha256"],
        "intentSha256": state["intentSha256"],
    }
    observed_path = Path(row["path"]).with_name("0000-observed.json")
    assert not observed_path.exists()
    native._verify_effect_ledger(result)

    _write_immutable(observed_path, b"unbound observation")
    with pytest.raises(
        OutputConsistencyError,
        match="unknown native effect has an observation artifact",
    ):
        native._verify_effect_ledger(result)


def test_failed_stage_stays_uncertain_if_any_effect_outcome_is_unknown() -> None:
    assert (
        native._failed_stage_status([{"outcome": "unknown"}, {"outcome": "observed"}])
        == "uncertain"
    )
    assert native._failed_stage_status([{"outcome": "observed"}]) == "partial"
    assert native._failed_stage_status([]) == "refused"


def test_native_runtime_identity_rejects_python_version_drift() -> None:
    previous = {
        "product": "DaVinci Resolve Studio",
        "version": [21, 1, 1, 10, ""],
        "python": "3.11.8",
    }
    current = {
        **previous,
        "python": "3.12.4",
    }

    with pytest.raises(
        OutputConsistencyError,
        match="native runtime identity changed between native stages",
    ):
        native._verify_native_identity_continuity(previous, current)


def test_effect_allowlist_rejects_a_non_native_method_before_intent(
    tmp_path: Path,
) -> None:
    state, _request = _effect_state(tmp_path)
    with pytest.raises(OutputConsistencyError, match="outside the closed method set"):
        native._private_effect(state, "os.remove", {"path": "/tmp/unrelated"})
    assert state["effects"] == []


def test_prepared_native_operation_is_claimed_once_before_effects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", tmp_path.resolve() / "native")
    context = _context()
    result_path, authority_path, intent_path, request_path = (
        native.native_request_paths(context, 0)
    )
    request_path.parent.mkdir(parents=True)
    authority_raw = _canonical({"stage": "authority"})
    intent_raw = _canonical({"stage": "intent"})
    authority_path.write_bytes(authority_raw)
    intent_path.write_bytes(intent_raw)
    authority_path.chmod(0o400)
    intent_path.chmod(0o400)
    request = {
        "context": context,
        "sequence": 0,
        "action": "construct",
        "operationId": "operation-one",
        "priorResultSha256": EMPTY_HEAD,
        "resultPath": str(result_path),
        "authority": {
            "path": str(authority_path),
            "sha256": hashlib.sha256(authority_raw).hexdigest(),
        },
        "intent": {
            "path": str(intent_path),
            "sha256": hashlib.sha256(intent_raw).hexdigest(),
        },
    }
    request_raw = _canonical(request)
    request_path.write_bytes(request_raw)
    request_path.chmod(0o400)
    request_sha = hashlib.sha256(request_raw).hexdigest()
    surprise = request_path.parent / "unexpected.json"
    surprise.write_bytes(b"unowned partial artifact")

    with pytest.raises(OutputConsistencyError, match="unexpected or prior start"):
        native._claim_prepared_native_operation(request, request_raw, request_sha)
    with pytest.raises(OutputConsistencyError, match="read-only recovery required"):
        native.next_native_operation(context)

    surprise.unlink()
    marker_path = native._claim_prepared_native_operation(
        request, request_raw, request_sha
    )
    assert marker_path.is_file()
    assert marker_path.stat().st_mode & 0o777 == 0o400
    assert not result_path.exists()
    assert not (request_path.parent / "effects").exists()
    with pytest.raises(OutputConsistencyError, match="already been claimed"):
        native._claim_prepared_native_operation(request, request_raw, request_sha)
    with pytest.raises(OutputConsistencyError, match="read-only recovery required"):
        native.next_native_operation(context)


def _write_immutable(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == raw
        return
    path.write_bytes(raw)
    path.chmod(0o400)


def _host_receipt(
    vault: Path,
    key: bytes,
    *,
    kind: str,
    payload: dict[str, Any],
    evidence: tuple[bytes, ...],
) -> tuple[Path, bytes]:
    evidence_hashes = []
    for raw in evidence:
        digest = hashlib.sha256(raw).hexdigest()
        _write_immutable(vault / digest, raw)
        evidence_hashes.append(digest)
    value = {
        "schemaVersion": "qualification-output-host-receipt/v1",
        "lane": LANE,
        "kind": kind,
        "payload": payload,
        "evidenceSha256": evidence_hashes,
    }
    value["mac"] = hmac.digest(key, _canonical(value), "sha256").hex()
    raw = _canonical(value)
    path = vault / hashlib.sha256(raw).hexdigest()
    _write_immutable(path, raw)
    return path, raw


def test_reservation_authenticates_the_entire_five_evidence_prediction_bundle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    host_root = tmp_path.resolve() / "host-state"
    monkeypatch.setattr(native, "HOST_STATE_ROOT", host_root)
    context = _context()
    vault = host_root / native._chain_key(context) / "receipts"
    vault.mkdir(parents=True)
    key = b"k" * 32
    _write_immutable(vault / "key", key)

    source_entries: list[dict[str, Any]] = []
    binding = {
        "schemaVersion": "qualification-output-inputs/v1",
        "lane": LANE,
        "context": context,
        "sourceEntries": source_entries,
    }
    binding_raw = _canonical(binding)
    geometry = {
        "context": context,
        "extentFrames": 1,
        "rate": {"numerator": 24, "denominator": 1},
        "tracks": [],
        "items": [],
        "sourceMappings": [],
    }
    geometry_sha = hashlib.sha256(_canonical(geometry)).hexdigest()
    output_path = str(tmp_path.resolve() / "approved.mov")
    settings = {"container": "mov", "videoCodec": "prores422"}
    approval_path = tmp_path.resolve() / "approval.json"
    approval_raw = _canonical({"outputPath": output_path, "settings": settings})
    _write_immutable(approval_path, approval_raw)
    envelope = {
        "schemaVersion": "qualification-output-geometry/v1",
        "lane": LANE,
        "geometry": geometry,
        "inputBindingSha256": hashlib.sha256(binding_raw).hexdigest(),
        "capturePhase": "pre_render",
        "capturedAt": "2026-10-16T12:00:00Z",
        "expiresAt": "2026-10-16T12:10:00Z",
    }
    geometry_receipt_payload = {**envelope, "inputBinding": binding}
    _geometry_receipt_path, geometry_receipt_raw = _host_receipt(
        vault,
        key,
        kind="output_geometry_snapshot",
        payload=geometry_receipt_payload,
        evidence=(b"native geometry result", binding_raw),
    )
    geometry_raw = _canonical(
        {**envelope, "receiptSha256": hashlib.sha256(geometry_receipt_raw).hexdigest()}
    )
    prediction = b"prediction-pcm"
    commit_payload = {
        "schemaVersion": "qualification-output-commitment/v1",
        "lane": LANE,
        "context": context,
        "geometrySha256": geometry_sha,
        "geometryCaptureRawSha256": hashlib.sha256(geometry_raw).hexdigest(),
        "geometryReceiptSha256": hashlib.sha256(geometry_receipt_raw).hexdigest(),
        "derivedIntentSha256": "1" * 64,
        "sourceEntries": source_entries,
        "algorithmSha256": "2" * 64,
        "predictionEncoding": "float64-le-stereo/v1",
        "predictionBytesSha256": hashlib.sha256(prediction).hexdigest(),
        "predictionByteLength": len(prediction),
        "extentFrames": 1,
        "sampleRate": 48000,
        "channels": 2,
        "createdAt": "2026-10-16T12:01:00Z",
        "expiresAt": "2026-10-16T12:10:00Z",
    }
    commitment_payload_raw = _canonical(commit_payload)
    _commitment_receipt_path, commitment_receipt_raw = _host_receipt(
        vault,
        key,
        kind="output_prediction_commitment",
        payload=commit_payload,
        evidence=(
            binding_raw,
            geometry_raw,
            geometry_receipt_raw,
            commitment_payload_raw,
            prediction,
        ),
    )
    commitment = {
        **commit_payload,
        "commitmentReceiptSha256": hashlib.sha256(commitment_receipt_raw).hexdigest(),
    }
    commitment_raw = _canonical(commitment)
    commitment_raw_sha = hashlib.sha256(commitment_raw).hexdigest()
    commitment_payload_sha = hashlib.sha256(commitment_payload_raw).hexdigest()

    render_intent_path = tmp_path.resolve() / "render-intent.json"
    render_intent = {
        "schemaVersion": native.RENDER_INTENT_SCHEMA,
        "lane": LANE,
        "context": context,
        "commitmentRawSha256": commitment_raw_sha,
        "outputPath": output_path,
        "settings": settings,
        "profile": native.SYNTHETIC_PROFILE,
        "authorityPath": str(approval_path),
        "authoritySha256": hashlib.sha256(approval_raw).hexdigest(),
    }
    render_raw = _canonical(render_intent)
    _write_immutable(render_intent_path, render_raw)
    reservation_payload = {
        "schemaVersion": "qualification-output-reservation/v1",
        "lane": LANE,
        "context": context,
        "commitmentRawSha256": commitment_raw_sha,
        "commitmentPayloadSha256": commitment_payload_sha,
        "renderIntentSha256": hashlib.sha256(render_raw).hexdigest(),
        "reservationId": "reservation-one",
        "reservedAt": "2026-10-16T12:02:00Z",
    }
    reservation_receipt_path, reservation_receipt_raw = _host_receipt(
        vault,
        key,
        kind="output_render_reservation",
        payload=reservation_payload,
        evidence=(commitment_raw, commitment_receipt_raw, render_raw),
    )
    reservation = {
        **reservation_payload,
        "reservationReceiptSha256": hashlib.sha256(reservation_receipt_raw).hexdigest(),
    }
    reservation_raw = _canonical(reservation)
    reservation_path = tmp_path.resolve() / "reservation.json"
    _write_immutable(reservation_path, reservation_raw)
    reservation_sha = hashlib.sha256(reservation_raw).hexdigest()
    history_row = {
        "context": context,
        "state": "reserved_by_render_intent",
        "reservationRawSha256": reservation_sha,
        "commitmentRawSha256": commitment_raw_sha,
        "commitmentPayloadSha256": commitment_payload_sha,
    }
    monkeypatch.setattr(native, "_host_attempt_history", lambda _context: [history_row])
    monkeypatch.setattr(
        native,
        "_historical_approval",
        lambda _raw, _request: {"outputPath": output_path, "settings": settings},
    )
    request = {
        "action": "capture_post",
        "context": context,
        "payload": {},
        "reservation": {
            "path": str(reservation_path),
            "sha256": reservation_sha,
            "receiptPath": str(reservation_receipt_path),
            "receiptSha256": hashlib.sha256(reservation_receipt_raw).hexdigest(),
        },
        "renderIntent": {
            "path": str(render_intent_path),
            "sha256": hashlib.sha256(render_raw).hexdigest(),
        },
    }

    checked = native._verify_reservation(request, current=False)

    assert checked == reservation_sha
