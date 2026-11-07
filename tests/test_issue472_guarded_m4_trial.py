"""Fail-closed orchestration checks for the real Studio #472 trial."""

from __future__ import annotations

import hashlib
import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_output as output


def _entrypoint() -> Any:
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts/issue-472-guarded-m4-acceptance.py"
    )
    spec = importlib.util.spec_from_file_location("vera472_guarded_m4_trial", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_current_admission_uses_manifest_event_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = _entrypoint()
    root = tmp_path / "trial"
    artifact = root / "admitted/qualification-output-package-admission.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"fresh authenticated admission bytes")
    match = {
        "eventId": "f5871317-bdb5-558b-8c05-6ed0fe4b6889",
        "recordRange": {"startFrame": 715, "endFrame": 929},
    }
    fake = SimpleNamespace(
        profile=module.MATRIX_PROFILE,
        admission_path=artifact,
        manifest={
            "timeline": {"durationFrames": 1407},
            "events": [match] + [{"eventId": str(i)} for i in range(10)],
            "tracks": [{} for _ in range(6)],
        },
    )

    def loader(path: Path, digest: str) -> Any:
        assert path == artifact
        assert digest == hashlib.sha256(artifact.read_bytes()).hexdigest()
        return fake

    monkeypatch.setattr(module, "load_qualification_package_v2", loader)
    assert module._admission(root) is fake
    match["recordRange"]["endFrame"] = 928
    with pytest.raises(RuntimeError, match="native target event"):
        module._admission(root)


def test_bounded_host_never_attempts_capture_after_save_reopen(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "private-run"
    root.mkdir(mode=0o700)
    actions = ("construct", "save_reopen", "capture_pre")
    monkeypatch.setattr(native, "action_plan_for_context", lambda _ctx: actions)
    requested: list[int] = []
    rows: dict[int, Path] = {}

    def paths(_context: Any, sequence: int) -> tuple[Path, Path, Path, Path]:
        requested.append(sequence)
        assert sequence in (0, 1), "must not touch capture_pre"
        base = tmp_path / f"native-{sequence:02d}"
        return (
            base / "result.json",
            base / "approval.json",
            base / "intent.json",
            base / "request.json",
        )

    for seq in (0, 1):
        step = root / f"native-{seq:02d}"
        step.mkdir(mode=0o700)
        (step / "intent.json").write_text("independent one-use intent")
        base = tmp_path / f"native-{seq:02d}"
        base.mkdir(mode=0o700)
        result = base / "result.json"
        result.write_text("native signed result bytes")
        rows[seq] = result

    def native_result(path: Path, _digest: str) -> dict[str, Any]:
        sequence = next(i for i, value in rows.items() if value == path)
        return {"action": actions[sequence], "sequence": sequence}

    def carrier_status(step: Path) -> dict[str, Any]:
        seq = int(step.name[-2:])
        path = rows[seq]
        return {
            "state": "native_result_verified",
            "result": {
                "path": str(path),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            },
        }

    monkeypatch.setattr(native, "native_request_paths", paths)
    monkeypatch.setattr(native, "verify_native_result", native_result)
    monkeypatch.setattr(carrier, "status", carrier_status)
    ingested: list[int] = []

    class Controller:
        def __init__(self) -> None:
            self.context: dict[str, Any] = {}

        def ingest_native_result(self, path: Path, digest: str) -> dict[str, Any]:
            seq = next(i for i, value in rows.items() if value == path)
            ingested.append(seq)
            return {
                "sequence": seq,
                "action": actions[seq],
                "status": "complete",
                "resultSha256": digest,
            }

    monkeypatch.setattr(output, "_session", lambda *_args: Controller())
    outcome = output.tick(
        root,
        session_path=tmp_path / "session.json",
        session_sha256="a" * 64,
        installed=tmp_path / "installed",
        consent_reference="Producer 2026-11-07",
        consent_instruction="Test the #472 new disposable Studio project only",
        minimum_free_bytes=1,
        max_native_sequence=1,
    )
    assert outcome == {
        "state": "bounded_native_checkpoint",
        "lastAction": "save_reopen",
        "maxNativeSequence": 1,
    }
    assert requested == [0, 1]
    assert ingested == [0, 1]
    assert not (root / "native-02").exists()
