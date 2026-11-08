"""No live Resolve, host authority, or producer project access in these tests."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn

import pytest
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4


def _config(tmp_path: Path) -> dict[str, Any]:
    return {
        "schema": runner.SCHEMA,
        "root": str(tmp_path / "unattended"),
        "queueRoot": str(tmp_path / "queue"),
        "packageRoot": str(tmp_path / "pinned-package"),
        "narrationEvidenceRoot": str(tmp_path / "original-narration-evidence"),
        "name": "test-bench-312",
        "caseId": "synthetic-312",
        "profile": "qualification-output-studio-matrix/v1",
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": 128 * 1024 * 1024,
        "consentReference": "https://github.com/mbelinkie/vera-script-to-timeline/issues/473",
        "consentInstruction": (
            "Producer authorized unattended disposable Test Bench and "
            "authentic native operations"
        ),
        "merged472Commit": "f" * 40,
    }


@pytest.mark.parametrize(
    "change",
    [
        lambda x: x.update(schema="wrong"),
        lambda x: x.update(unknown="command injection"),
        lambda x: x.update(profile="untrusted-profile"),
        lambda x: x.update(merged472Commit="main"),
        lambda x: x.update(consentInstruction=""),
        lambda x: x.update(root="relative"),
        lambda x: x.update(maxElapsedSeconds=1),
        lambda x: x.update(maxDiskBytes=0),
    ],
)
def test_one_start_closed_configuration(
    tmp_path: Path, change: Callable[[dict[str, Any]], Any]
) -> None:
    config = _config(tmp_path)
    change(config)
    with pytest.raises(queue.QueueError):
        runner.validate_config(config)


def test_matrix_profile_binds_all_six_original_published_receipts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from vera_timeline_agent import qualification_output_package_v2 as package
    from vera_timeline_agent import v2_package

    build_id = "sample-original-build"
    root = tmp_path / "original-package"
    build = root / "Builds" / build_id
    published = tmp_path / "published"
    monkeypatch.setattr(
        v2_package,
        "verify_v2_package",
        lambda path: SimpleNamespace(build_id=build_id),
    )
    monkeypatch.setattr(package, "MATRIX_PREPARATION_ROOT", published)
    bindings = [{"requirementKey": f"sha256:{index:064x}"} for index in range(6)]
    (build / v2_package.MANIFEST_FILENAME).parent.mkdir(parents=True)
    (build / v2_package.MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "events": [{}] * 11,
                "timeline": {"durationFrames": 1407},
                "preparationBindings": bindings,
            }
        )
    )
    for index, binding in enumerate(bindings):
        key = binding["requirementKey"]
        embedded = (
            build
            / "Preparation/receipts"
            / hashlib.sha256(key.encode()).hexdigest()
            / "receipt.json"
        )
        external = (
            published
            / runner._CASE_312_PREPARATION
            / "published"
            / key[7:]
            / "receipt.json"
        )
        embedded.parent.mkdir(parents=True)
        external.parent.mkdir(parents=True)
        original_bytes = f"exact-published-receipt-{index}".encode()
        embedded.write_bytes(original_bytes)
        external.write_bytes(original_bytes)
    resolved = runner._matrix_preparation_paths(root, case_id="synthetic-312")
    assert set(resolved) == {binding["requirementKey"] for binding in bindings}
    assert len(resolved) == 6
    first = resolved[bindings[0]["requirementKey"]]
    first.write_bytes(b"swapped evidence")
    with pytest.raises(queue.QueueError, match="published source receipt differs"):
        runner._matrix_preparation_paths(root, case_id="synthetic-312")
    with pytest.raises(queue.QueueError, match="unsupported unattended"):
        runner._matrix_preparation_paths(root, case_id="not-312")


def test_matrix_narration_uses_original_three_measured_assets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    from vera_timeline_agent import roundtrip_v2_audio, v2_package

    build = tmp_path / "pkg" / "Builds" / "build-one"
    build.mkdir(parents=True)
    evidence_root = tmp_path / "original-narration"
    bound: list[str] = []
    rows: list[dict[str, Any]] = []
    for index in range(3):
        block_id = f"{index:08x}-abcd-4000-8000-000000000000"
        asset_id = f"{index:064x}"
        wav_data = f"original-waveform-{index}".encode()
        audio_locator = f"v1/assets/{block_id}/{asset_id}/narration.wav"
        measure_locator = f"narration-measurements/{asset_id}.measurement.json"
        wav = evidence_root / "cache" / audio_locator
        measure = evidence_root / measure_locator
        wav.parent.mkdir(parents=True)
        measure.parent.mkdir(parents=True, exist_ok=True)
        wav.write_bytes(wav_data)
        (wav.parent / "timing.json").write_bytes(b"timing")
        measure.write_bytes(b"measurement")
        rows.append(
            {
                "blockId": block_id,
                "audio": {
                    "locator": audio_locator,
                    "audioHash": "sha256:" + hashlib.sha256(wav_data).hexdigest(),
                },
                "verification": {
                    "method": "measured_audio_boundaries/v1",
                    "measurementArtifactLocator": measure_locator,
                },
            }
        )
    (build / v2_package.DEPENDENCIES_FILENAME).write_text(
        json.dumps({"narrationBoundaryEvidence": rows})
    )
    monkeypatch.setattr(
        v2_package,
        "verify_v2_package",
        lambda path: SimpleNamespace(build_id="build-one"),
    )
    monkeypatch.setattr(
        roundtrip_v2_audio,
        "verify_measured_narration_evidence",
        lambda row, **kwargs: bound.append(row["blockId"]),
    )
    actual = runner._matrix_narration_paths(
        tmp_path / "pkg", evidence_root, case_id="synthetic-312"
    )
    assert len(actual) == 3
    assert set(bound) == {row["blockId"] for row in rows}
    wav = evidence_root / "cache" / rows[0]["audio"]["locator"]
    wav.write_bytes(b"mutated")
    with pytest.raises(queue.QueueError, match="narration audio differs"):
        runner._matrix_narration_paths(
            tmp_path / "pkg", evidence_root, case_id="synthetic-312"
        )


def test_full_source_admission_refuses_before_any_disposable_creation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_package_v2 as package

    config = _config(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(runner, "_merged_472", lambda commit: None)
    monkeypatch.setattr(
        shutil, "disk_usage", lambda path: SimpleNamespace(free=4 * 1024**3)
    )
    monkeypatch.setattr(runner, "_matrix_preparation_paths", lambda *a, **k: {})
    monkeypatch.setattr(runner, "_matrix_narration_paths", lambda *a, **k: {})

    def refuse_admission(root: Path, **kwargs: Any) -> None:
        calls.append("real-admission-refused")
        raise ValueError("unverified source evidence")

    monkeypatch.setattr(package, "admit_qualification_package_v2", refuse_admission)
    monkeypatch.setattr(
        runner,
        "_one_start_setup",
        lambda config: calls.append("PROJECTS SHOULD NOT BE CREATED"),
    )
    with pytest.raises(ValueError, match="unverified source evidence"):
        runner.start(config)
    assert calls == ["real-admission-refused"]


def test_pinned_node_refuses_launchctl_missing_or_wrong_runtime(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_package_v2 as package

    node = tmp_path / "node"
    node.write_bytes(b"real locked executable fixture")
    monkeypatch.setattr(package, "_NODE", node)
    monkeypatch.setattr(shutil, "which", lambda name: None)
    with pytest.raises(queue.QueueError, match="must expose"):
        runner._require_pinned_node(mac=True)
    different = tmp_path / "foreign-node"
    different.write_bytes(b"wrong")
    monkeypatch.setattr(shutil, "which", lambda name: str(different))
    with pytest.raises(queue.QueueError, match="must expose"):
        runner._require_pinned_node(mac=True)
    monkeypatch.setattr(shutil, "which", lambda name: str(node))
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "v26.5.0\n"),
    )
    with pytest.raises(queue.QueueError, match="version differs"):
        runner._require_pinned_node(mac=True)
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args, 0, "v24.19.0\n"),
    )
    runner._require_pinned_node(mac=True)


def test_mac_preflight_requires_full_host_runtime_before_source_or_resolve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import qualification_output_controller_v2 as controller

    calls: list[str] = []
    config = _config(tmp_path)
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.setattr(runner, "_require_pinned_node", lambda: calls.append("node"))

    def missing_uv() -> NoReturn:
        calls.append("runtime")
        raise ValueError("locked uv unavailable")

    monkeypatch.setattr(controller, "output_runtime_snapshot", missing_uv)
    monkeypatch.setattr(
        runner,
        "_matrix_preparation_paths",
        lambda *a, **k: calls.append("source preflight should not run"),
    )
    with pytest.raises(ValueError, match="locked uv unavailable"):
        runner._preflight_before_native(config)
    assert calls == ["node", "runtime"]


def test_no_setup_or_native_operation_before_472_gate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    called = []

    def block(_commit: str) -> NoReturn:
        called.append("472-refused")
        raise queue.QueueError("#472 not merged")

    monkeypatch.setattr(runner, "_merged_472", block)
    monkeypatch.setattr(
        runner,
        "_one_start_setup",
        lambda config: called.append("PROVISIONED - SHOULD NOT HAPPEN"),
    )
    with pytest.raises(queue.QueueError, match="#472 not merged"):
        runner.start(_config(tmp_path))
    assert called == ["472-refused"]


def test_preflight_refuses_insufficient_disk_before_project_provision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(runner, "_merged_472", lambda commit: None)
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=1024),
    )
    monkeypatch.setattr(
        runner, "_matrix_preparation_paths", lambda *a, **k: calls.append("verified")
    )
    monkeypatch.setattr(
        runner,
        "_one_start_setup",
        lambda config: calls.append("projects-created"),
    )
    with pytest.raises(queue.QueueError, match="free disk"):
        runner.start(config)
    assert calls == []


def test_preflight_refuses_invalid_package_before_project_provision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = _config(tmp_path)
    calls: list[str] = []
    monkeypatch.setattr(runner, "_merged_472", lambda commit: None)
    monkeypatch.setattr(
        shutil,
        "disk_usage",
        lambda path: SimpleNamespace(free=4 * 1024**3),
    )

    def invalid(_path: Path, *, case_id: str) -> None:
        raise ValueError("invalid source hash")

    monkeypatch.setattr(runner, "_matrix_preparation_paths", invalid)
    monkeypatch.setattr(
        runner,
        "_one_start_setup",
        lambda config: calls.append("projects-created"),
    )
    with pytest.raises(ValueError, match="invalid source hash"):
        runner.start(config)
    assert calls == []


def test_merge_gate_refuses_472_only_in_local_branch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commands: list[tuple[str, ...]] = []

    def git(command: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        commands.append(tuple(command))
        return subprocess.CompletedProcess(
            command,
            1
            if command[1:5] == ["merge-base", "--is-ancestor", "f" * 40, "origin/main"]
            else 0,
            stdout="python/vera_timeline_agent/qualification_output_native_v2.py\n",
        )

    monkeypatch.setattr(subprocess, "run", git)
    with pytest.raises(queue.QueueError, match="not merged into origin/main"):
        runner._merged_472("f" * 40)
    assert any("origin/main" in command for command in commands)


def test_single_start_drives_only_verified_pristine_then_blocks_unknown_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    state: dict[str, Any] = {"phase": "queued", "verified": False, "commands": []}
    monkeypatch.setattr(runner, "_merged_472", lambda commit: None)
    monkeypatch.setattr(runner, "_preflight_before_native", lambda config: None)
    capability_calls: list[str] = []

    def capability(
        _store: Any, _job: str, _root: Path, report: dict[str, Any]
    ) -> dict[str, Any]:
        capability_calls.append("inspected-only")
        return {
            "state": "blocked_unattended_native_roll_edit_not_proven",
            "jobId": "resolve-reverse-" + "a" * 32,
            "verifiedStages": [
                row["name"] for row in report["stages"] if row["state"] == "verified"
            ],
            "next": "edited",
        }

    monkeypatch.setattr(runner, "_blocked_after_pristine", capability)
    monkeypatch.setattr(
        runner,
        "_one_start_setup",
        lambda config: (
            SimpleNamespace(root=tmp_path),
            "resolve-reverse-" + "a" * 32,
            {"path": str(tmp_path / "authentic-baseline.json"), "sha256": "b" * 64},
        ),
    )

    def report(store: Any, job_id: str) -> dict[str, Any]:
        stage = "pristine" if state["phase"] == "awaiting_operator" else None
        return {
            "state": state["phase"],
            "stage": stage,
            "stages": [
                {
                    "name": "pristine",
                    "state": "verified" if state["verified"] else "pending",
                }
            ],
        }

    monkeypatch.setattr(m4, "publish", report)

    def worker(_store: Any) -> bool:
        state["commands"].append("queue-intent")
        state["phase"] = "awaiting_operator"
        return True

    monkeypatch.setattr(runner, "_worker_once", worker)

    def drive(*args: Any, **kwargs: Any) -> dict[str, Any]:
        state["commands"].append("host-native-chain")
        assert args[0]["caseId"] == "synthetic-312"
        return {
            "state": "terminal_native_verified",
            "session": {
                "path": str(tmp_path / "authentic-baseline.json"),
                "sha256": "b" * 64,
            },
            "capture": {"path": str(tmp_path / "native.json"), "sha256": "c" * 64},
        }

    monkeypatch.setattr(runner, "_run_pristine", drive)

    def submit(*args: Any) -> None:
        state["commands"].append("verified-M4-submission")
        state["phase"] = "queued"
        state["verified"] = True

    monkeypatch.setattr(runner, "_submit_original", submit)
    outcome = runner.start(_config(tmp_path))
    assert outcome == {
        "state": "blocked_unattended_native_roll_edit_not_proven",
        "jobId": "resolve-reverse-" + "a" * 32,
        "verifiedStages": ["pristine"],
        "next": "edited",
    }
    assert state["commands"] == [
        "queue-intent",
        "host-native-chain",
        "verified-M4-submission",
    ]
    assert capability_calls == ["inspected-only"]
    assert runner.start(_config(tmp_path)) == outcome
    assert capability_calls == ["inspected-only", "inspected-only"]
    assert state["commands"] == [
        "queue-intent",
        "host-native-chain",
        "verified-M4-submission",
    ]


def test_reusable_pristine_controller_uses_original_m4_elapsed_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import resolve_test_bench_campaign as campaign
    from vera_timeline_agent import workflow_v2_cli as workflow

    config = _config(tmp_path)
    pristine = {"path": str(tmp_path / "session.json"), "sha256": "b" * 64}
    installed = tmp_path / "frozen-installed"
    manifest = tmp_path / "release.json"
    manifest.write_bytes(b"fixed original installed manifest")
    original = {
        "baselineSession": pristine,
        "initialTarget": {
            "projectUid": "new-project",
            "timelineUid": "new-timeline",
            "projectName": "exact-new-disposable",
            "timelineName": "exact-new-disposable",
        },
        "caseId": "synthetic-312",
        "runAt": "2026-11-08T00:00:00Z",
        "deadlineAt": "2026-11-08T02:00:00Z",
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": config["maxDiskBytes"],
    }
    monkeypatch.setattr(m4, "_load_plan", lambda store, job: original)
    monkeypatch.setattr(
        output, "_session", lambda *args: SimpleNamespace(release_root=installed)
    )
    monkeypatch.setattr(workflow, "_verify_output_release", lambda path: manifest)
    observed: list[dict[str, Any]] = []

    def fake_start(plan: dict[str, Any]) -> dict[str, Any]:
        observed.append(plan)
        return {"capture": {"path": str(tmp_path / "capture.json"), "sha256": "c" * 64}}

    monkeypatch.setattr(campaign, "start", fake_start)
    result = runner._run_pristine(config, object(), "test-job", pristine)  # type: ignore[arg-type]
    assert result["session"] == pristine
    assert len(observed) == 1
    assert observed[0]["deadlineUnix"] == queue.dt("2026-11-08T01:00:00Z").timestamp()
    assert observed[0]["target"] == original["initialTarget"]
    assert (
        observed[0]["releaseManifestSha256"]
        == hashlib.sha256(manifest.read_bytes()).hexdigest()
    )
    original["maxDiskBytes"] += 1
    with pytest.raises(queue.QueueError, match="M4 and native stage pins differ"):
        runner._run_pristine(config, object(), "test-job", pristine)  # type: ignore[arg-type]
    assert len(observed) == 1


def test_enrolled_receipt_is_written_once_and_verified_by_m4(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = queue.Store(tmp_path / "queue")
    job = "resolve-reverse-" + "a" * 32
    folder = store.root / job
    folder.mkdir(mode=0o700)
    calls: list[str] = []
    report: dict[str, Any] = {
        "stages": [
            {
                "name": "pristine",
                "state": "awaiting_operator",
                "operation_id": "one-use-op",
            }
        ]
    }
    monkeypatch.setattr(m4, "publish", lambda *args: report)

    def submit(_store: Any, _job: str) -> None:
        calls.append("existing M4 verifier")
        report["stages"][0]["state"] = "verified"

    monkeypatch.setattr(m4, "submit", submit)
    receipt = {
        "session": {"path": "/private/host-session.json", "sha256": "a" * 64},
        "capture": {"path": "/private/native.json", "sha256": "b" * 64},
    }
    runner._submit_original(store, job, "pristine", receipt)
    path = folder / "receipt-pristine.json"
    original = path.read_bytes()
    runner._submit_original(store, job, "pristine", receipt)
    assert path.read_bytes() == original
    assert calls == ["existing M4 verifier"]
    modified = {
        **receipt,
        "capture": {"path": "/private/other.json", "sha256": "c" * 64},
    }
    with pytest.raises(queue.QueueError, match="receipt differs"):
        runner._submit_original(store, job, "pristine", modified)


def test_post_pristine_capability_is_read_only_and_never_advances_edit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import resolve_test_bench_edit_probe as probe

    store = queue.Store(tmp_path / "queue")
    job = "resolve-reverse-" + "a" * 32
    receipt = {
        "session": {"path": str(tmp_path / "session.json"), "sha256": "a" * 64},
        "capture": {"path": str(tmp_path / "capture.json"), "sha256": "b" * 64},
    }
    monkeypatch.setattr(m4, "_stage_receipt", lambda *args: receipt)
    calls: list[dict[str, Any]] = []

    def inspection(root: Path, **kwargs: Any) -> dict[str, Any]:
        calls.append({"root": root, **kwargs})
        return {
            "resolveVersion": [21, 1, 2, 10],
            "supportsDocumentedOffsetMethods": True,
            "leftItemUid": "original-left",
            "rightItemUid": "original-right",
        }

    monkeypatch.setattr(probe, "inspect_pristine", inspection)
    report = {
        "stages": [
            {"name": "pristine", "state": "verified"},
            {"name": "edited", "state": "pending"},
        ]
    }
    result = runner._blocked_after_pristine(store, job, tmp_path / "run", report)
    assert result["state"] == "blocked_unattended_native_roll_edit_not_proven"
    assert result["verifiedStages"] == ["pristine"]
    assert result["editCapability"]["unqualified"] is True
    assert calls == [
        {
            "root": tmp_path / "run" / "edit-capability",
            "session_path": tmp_path / "session.json",
            "session_sha256": "a" * 64,
            "capture_path": tmp_path / "capture.json",
            "capture_sha256": "b" * 64,
        }
    ]


def test_no_m4_receipt_for_unenrolled_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = queue.Store(tmp_path / "queue")
    monkeypatch.setattr(
        m4,
        "publish",
        lambda *args: {
            "stages": [
                {"name": "pristine", "state": "pending", "operation_id": "unknown"}
            ]
        },
    )
    with pytest.raises(queue.QueueError, match="not enrolled"):
        runner._submit_original(store, "no-job", "pristine", {})


def test_missing_original_queue_row_stays_unenrolled(tmp_path: Path) -> None:
    store = queue.Store(tmp_path / "queue")
    assert runner._find_job(store, hashlib.sha256(b"unrelated").hexdigest()) is None
