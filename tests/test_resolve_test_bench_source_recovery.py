"""Interrupted source admission recovery is static-only and exactly once."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_package_v2 as admission
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_source_recovery as recovery
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4_provision as provision


@pytest.fixture
def environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Path, dict[str, Any], list[str]]:
    root = tmp_path / "fresh"
    root.mkdir(mode=0o700)
    primary = root / "source-preflight"
    primary.mkdir(mode=0o700)
    (primary / "attestation.json").write_bytes(b"preserved incomplete static proof")
    (root / "provision").mkdir(mode=0o700)
    config = {
        "schema": runner.SCHEMA,
        "root": str(root),
        "queueRoot": str(root / "queue"),
        "packageRoot": str(tmp_path / "source-package"),
        "narrationEvidenceRoot": str(tmp_path / "measured-narration"),
        "name": "fresh-test",
        "caseId": "synthetic-312",
        "profile": admission.MATRIX_PROFILE,
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": 1048576,
        "consentReference": "new consent reference",
        "consentInstruction": "Do the native tests. Keep going.",
        "merged472Commit": "a" * 40,
    }
    (root / "config.json").write_bytes(queue.canonical(config))
    events: list[str] = []
    targets = {
        "initial": {
            "projectUid": "new-initial",
            "timelineUid": "new-initial-timeline",
        },
        "fresh": {"projectUid": "new-fresh", "timelineUid": "new-fresh-timeline"},
    }
    monkeypatch.setattr(provision, "completed", lambda _root: targets)
    monkeypatch.setattr(runner, "_merged_472", lambda _commit: None)
    monkeypatch.setattr(runner, "_require_pinned_node", lambda: None)
    monkeypatch.setattr(runner, "_matrix_preparation_paths", lambda *_args, **_k: {})
    monkeypatch.setattr(runner, "_matrix_narration_paths", lambda *_args, **_k: {})

    def fake_admit(path: Path, **kwargs: Any) -> SimpleNamespace:
        events.append("new-static-admission")
        assert kwargs["profile"] == admission.MATRIX_PROFILE
        assert kwargs["package_root"] == Path(str(config["packageRoot"]))
        path.mkdir()
        (path / "package").mkdir()
        raw = b"fixed-and-sealed-static-package"
        receipt = path / "qualification-output-package-admission.json"
        receipt.write_bytes(raw)
        return SimpleNamespace(
            profile=admission.MATRIX_PROFILE,
            package_root=path / "package",
            assert_current=lambda: events.append("assert-current"),
            serialize_native_admission=lambda: (
                receipt,
                hashlib.sha256(raw).hexdigest(),
            ),
        )

    def fake_load(path: Path, sha256: str) -> SimpleNamespace:
        events.append("reopened-static-admission")
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
            raise ValueError("admission digest mismatch")
        return SimpleNamespace(
            profile=admission.MATRIX_PROFILE,
            package_root=root / recovery.RECOVERY / "package",
            assert_current=lambda: events.append("reopened-assert-current"),
        )

    monkeypatch.setattr(admission, "admit_qualification_package_v2", fake_admit)
    monkeypatch.setattr(admission, "load_qualification_package_v2", fake_load)
    return root, config, events


def test_static_interrupted_attempt_recovers_exactly_once_with_no_native_enroll(
    environment: tuple[Path, dict[str, Any], list[str]],
) -> None:
    root, config, events = environment
    original = (root / "source-preflight/attestation.json").read_bytes()
    result = recovery.recover(root / "config.json")
    assert result["state"] == "authenticated_static_recovery_no_native_effect"
    assert result["nativeEffects"] is False
    assert (root / "source-preflight/attestation.json").read_bytes() == original
    assert not (root / "queue").exists()
    assert not (root / "m4-plan.json").exists()
    assert not (root / "pristine").exists()
    assert events.count("new-static-admission") == 1
    recovery.verify(root, config)
    runner._preflight_before_native(config)
    assert events.count("new-static-admission") == 1
    with pytest.raises(queue.QueueError, match="already attempted"):
        recovery.recover(root / "config.json")
    assert events.count("new-static-admission") == 1


def test_refuses_foreign_target_or_mutated_receipt(
    environment: tuple[Path, dict[str, Any], list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, config, events = environment
    recovery.recover(root / "config.json")
    target = {
        "initial": {"projectUid": "FOREIGN"},
        "fresh": {"projectUid": "new-fresh"},
    }
    monkeypatch.setattr(provision, "completed", lambda _root: target)
    with pytest.raises(queue.QueueError, match="target differs"):
        recovery.verify(root, config)
    with pytest.raises(queue.QueueError, match="target differs"):
        runner._preflight_before_native(config)
    assert events.count("new-static-admission") == 1


def test_refuses_native_state_and_completed_primary(
    environment: tuple[Path, dict[str, Any], list[str]],
) -> None:
    root, _config, events = environment
    (root / "queue").mkdir()
    with pytest.raises(queue.QueueError, match="native state already enrolled"):
        recovery.recover(root / "config.json")
    (root / "queue").rmdir()
    (root / "source-preflight/qualification-output-package-admission.json").write_text(
        "previously accepted or unknown"
    )
    with pytest.raises(queue.QueueError, match="primary admission exists"):
        recovery.recover(root / "config.json")
    assert events == []


def test_failure_after_durable_recovery_intent_never_replays(
    environment: tuple[Path, dict[str, Any], list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _config, events = environment
    original = admission.admit_qualification_package_v2

    def crash_after_intent(*args: Any, **kwargs: Any) -> Any:
        raise OSError("simulated crash after source recovery intent")

    monkeypatch.setattr(admission, "admit_qualification_package_v2", crash_after_intent)
    with pytest.raises(OSError, match="simulated crash"):
        recovery.recover(root / "config.json")
    assert (root / recovery.INTENT).exists()
    assert not (root / recovery.RECEIPT).exists()
    assert (root / "source-preflight/attestation.json").exists()
    monkeypatch.setattr(admission, "admit_qualification_package_v2", original)
    with pytest.raises(queue.QueueError, match="already attempted"):
        recovery.recover(root / "config.json")
    assert events == []


def test_config_drift_refuses_reopening_recovered_static_proof(
    environment: tuple[Path, dict[str, Any], list[str]],
) -> None:
    root, config, events = environment
    recovery.recover(root / "config.json")
    altered = {**config, "consentInstruction": "different authority"}
    with pytest.raises(queue.QueueError, match="intent or provision target differs"):
        recovery.verify(root, altered)
    receipt = root / recovery.RECEIPT
    tampered = json.loads(carrier._read(receipt))
    tampered["admissionSha256"] = "b" * 64
    receipt.write_bytes(queue.canonical(tampered))
    with pytest.raises(ValueError, match="admission digest mismatch"):
        recovery.verify(root, config)
    assert events.count("new-static-admission") == 1
