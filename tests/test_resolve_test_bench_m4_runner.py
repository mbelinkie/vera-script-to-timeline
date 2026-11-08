"""No live Resolve, host authority, or producer project access in these tests."""

from __future__ import annotations

import hashlib
import shutil
import subprocess
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
    monkeypatch.setattr(
        output,
        "_session",
        lambda *args: SimpleNamespace(release_root=tmp_path / "reviewed-release"),
    )

    def drive(*args: Any, **kwargs: Any) -> dict[str, Any]:
        state["commands"].append("host-native-chain")
        assert kwargs["installed"] == tmp_path / "reviewed-release"
        return {
            "state": "terminal_native_verified",
            "session": {
                "path": str(tmp_path / "authentic-baseline.json"),
                "sha256": "b" * 64,
            },
            "capture": {"path": str(tmp_path / "native.json"), "sha256": "c" * 64},
        }

    monkeypatch.setattr(output, "drive", drive)

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
