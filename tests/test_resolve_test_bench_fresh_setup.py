"""#473 fresh M4 setup may only prepare distinct immutable source-pinned config."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_fresh_setup as setup
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent import resolve_test_queue_m4_provision as provision


def _target(name: str, uid: str) -> dict[str, str]:
    return {
        "projectName": name,
        "timelineName": name,
        "projectUid": uid,
        "timelineUid": uid + "-timeline",
    }


@pytest.fixture
def roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
    old = tmp_path / "old" / "run"
    new = tmp_path / "new"
    old.mkdir(mode=0o700, parents=True)
    new.mkdir(mode=0o700)
    original = {
        "schema": runner.SCHEMA,
        "root": str(old),
        "queueRoot": str(old / "queue"),
        "name": "historical",
        "caseId": "synthetic-312",
        "packageRoot": str(tmp_path / "package"),
        "narrationEvidenceRoot": str(tmp_path / "narration"),
        "profile": "qualification-output-studio-matrix/v1",
        "maxElapsedSeconds": 3600,
        "maxDiskBytes": 1048576,
        "consentReference": "old reference",
        "consentInstruction": "old instruction",
        "merged472Commit": "a" * 40,
    }
    (old.parent / "config.json").write_bytes(queue.canonical(original))
    old_target = _target(
        "VERA Delivery 00000000-0000-4000-8000-000000000001 111111111111",
        "old-uid",
    )
    old_fresh = _target(
        "VERA Delivery 00000000-0000-4000-8000-000000000002 222222222222",
        "old-fresh-uid",
    )
    old_plan = m4.validate_plan(
        {
            "schema": m4.SCHEMA,
            "name": "historical",
            "caseId": "synthetic-312",
            "baselineSession": {
                "path": str(tmp_path / "old.session"),
                "sha256": "a" * 64,
            },
            "initialTarget": old_target,
            "freshTarget": old_fresh,
            "maxElapsedSeconds": 3600,
            "maxDiskBytes": 1048576,
        }
    )
    (old / "m4-plan.json").write_bytes(queue.canonical(old_plan))
    monkeypatch.setattr(carrier, "_private", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        provision,
        "completed",
        lambda _root: {
            "initial": _target(
                "VERA Delivery 00000000-0000-4000-8000-000000000003 333333333333",
                "new-uid",
            ),
            "fresh": _target(
                "VERA Delivery 00000000-0000-4000-8000-000000000004 444444444444",
                "new-fresh-uid",
            ),
        },
    )
    return old, new


def _create(old: Path, new: Path) -> dict[str, object]:
    return setup.prepare(
        old.parent / "config.json",
        new,
        name="test-bench-fresh",
        consent_reference="2026-11-08 producer test approval",
        consent_instruction="Do the native tests. Keep going.",
    )


def test_fresh_config_retains_exact_source_but_replaces_old_authority(
    roots: tuple[Path, Path],
) -> None:
    old, new = roots
    result = _create(old, new)
    assert result["nativeEffects"] is False
    assert result["oldTargetsReused"] is False
    config = json.loads((new / "config.json").read_bytes())
    original = json.loads((old.parent / "config.json").read_bytes())
    for field in (
        "packageRoot",
        "narrationEvidenceRoot",
        "caseId",
        "profile",
        "merged472Commit",
        "maxDiskBytes",
        "maxElapsedSeconds",
    ):
        assert config[field] == original[field]
    assert config["root"] == str(new)
    assert config["queueRoot"] == str(new / "queue")
    assert config["consentInstruction"] != original["consentInstruction"]
    assert not (new / "queue").exists()
    assert not (new / "m4-plan.json").exists()
    with pytest.raises(queue.QueueError, match="already exist"):
        _create(old, new)


def test_rejects_historical_identity_and_existing_attempt(
    roots: tuple[Path, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    old, new = roots
    original_plan = m4.validate_plan(json.loads((old / "m4-plan.json").read_bytes()))
    monkeypatch.setattr(
        provision,
        "completed",
        lambda _root: {
            "initial": original_plan["initialTarget"],
            "fresh": _target(
                "VERA Delivery 00000000-0000-4000-8000-000000000004 444444444444",
                "new-fresh-uid",
            ),
        },
    )
    with pytest.raises(queue.QueueError, match="historical M4 identity"):
        _create(old, new)
    assert not (new / "config.json").exists()
    monkeypatch.setattr(
        provision,
        "completed",
        lambda _root: {
            "initial": _target(
                "VERA Delivery 00000000-0000-4000-8000-000000000003 333333333333",
                "new-uid",
            ),
            "fresh": _target(
                "VERA Delivery 00000000-0000-4000-8000-000000000004 444444444444",
                "new-fresh-uid",
            ),
        },
    )
    (new / "m4-plan.json").write_text("spent")
    with pytest.raises(queue.QueueError, match="already exist"):
        _create(old, new)
    assert not (new / "config.json").exists()


def test_rejects_stale_consent_and_old_root(roots: tuple[Path, Path]) -> None:
    old, new = roots
    with pytest.raises(queue.QueueError, match="historical authority"):
        setup.prepare(
            old.parent / "config.json",
            new,
            name="test-bench-fresh",
            consent_reference="old reference",
            consent_instruction="old instruction",
        )
    with pytest.raises(queue.QueueError, match="distinct"):
        setup.prepare(
            old.parent / "config.json",
            old,
            name="test-bench-fresh",
            consent_reference="new",
            consent_instruction="new",
        )
    assert not (new / "config.json").exists()
