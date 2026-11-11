"""No-Resolve fault tests of the source-pinned, separately adopted #499 hooks.

Only pure fixture files and simulated carrier/controller results are used.
The patch is deliberately NOT applied to the live #499 shared worktree.
"""

from __future__ import annotations

import contextlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest
import vera_timeline_agent as package
from vera_timeline_agent import resolve_test_bench_diagnostic_journal as diagnostics

REPO = Path(__file__).resolve().parents[1]
FROZEN = "91e260291ed279a3789e1022afc2e0250c2d5b0a"
PATCH = REPO / "docs/verification/issue-512-phase2-499-hooks.patch"
MODULES = ("conductor_launch", "campaign", "output")


def _canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _one_use(path: Path, raw: bytes) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())


@pytest.fixture
def patched_sources(tmp_path: Path) -> dict[str, str]:
    if (
        subprocess.run(
            ["git", "cat-file", "-e", FROZEN + "^{commit}"],
            cwd=REPO,
            capture_output=True,
            check=False,
        ).returncode
        != 0
    ):
        pytest.skip("original #499 pinned commit not available in shallow checkout")
    result = {}
    for name in MODULES:
        path = f"python/vera_timeline_agent/resolve_test_bench_{name}.py"
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(
            subprocess.check_output(["git", "show", f"{FROZEN}:{path}"], cwd=REPO)
        )
    subprocess.run(["git", "apply", "--check", str(PATCH)], cwd=tmp_path, check=True)
    subprocess.run(["git", "apply", str(PATCH)], cwd=tmp_path, check=True)
    for name in MODULES:
        patched_path = (
            tmp_path / f"python/vera_timeline_agent/resolve_test_bench_{name}.py"
        )
        result[name] = patched_path.read_text()
        compile(result[name], str(patched_path), "exec")
    return result


def _module(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    source: str,
    stubs: dict[str, ModuleType],
) -> ModuleType:
    for subname, stub in stubs.items():
        qualified = f"vera_timeline_agent.{subname}"
        monkeypatch.setitem(sys.modules, qualified, stub)
        monkeypatch.setattr(package, subname, stub, raising=False)
    result = ModuleType(f"vera_timeline_agent.resolve_test_bench_{name}")
    result.__package__ = "vera_timeline_agent"
    exec(compile(source, f"resolve_test_bench_{name}.py", "exec"), result.__dict__)
    return result


def _stub(**attributes: Any) -> ModuleType:
    result = ModuleType("testbench_stub")
    for key, value in attributes.items():
        setattr(result, key, value)
    return result


def _records(root: Path) -> list[dict[str, Any]]:
    return [
        json.loads(p.read_text())
        for p in sorted((root / "diagnostics-v1" / "records").glob("record-*.json"))
    ]


@pytest.fixture
def fake_launch(
    tmp_path: Path,
    patched_sources: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> tuple[ModuleType, Path, list[str]]:
    root = tmp_path / "case123456"
    root.mkdir(mode=0o700)
    calls: list[str] = []
    queue = _stub(QueueError=ValueError, canonical=_canonical)
    carrier = _stub(
        _private=lambda p, create=False: (
            p.mkdir(mode=0o700, exist_ok=True) if create else None
        ),
        _lock=lambda _: contextlib.nullcontext(),
        _once=_one_use,
    )

    def fail_original_full_loop(*args: Any, **kwargs: Any) -> None:
        calls.append("full_loop")
        raise RuntimeError("token=SECRET1234")

    full_loop = _stub(
        _frozen_source=lambda _: "a" * 64,
        start=fail_original_full_loop,
    )
    stubs = {
        "resolve_gui_helper_protocol": _stub(),
        "resolve_gui_roll": _stub(),
        "resolve_test_bench_carrier": carrier,
        "resolve_test_bench_full_loop": full_loop,
        "resolve_test_bench_helper_transport": _stub(),
        "resolve_test_queue": queue,
        "resolve_test_queue_m4": _stub(),
    }
    launch = _module(
        monkeypatch, "conductor_launch", patched_sources["conductor_launch"], stubs
    )
    request = {
        "requestId": "request1234",
        "mode": "complete-m4",
        "sourceGraphSha256": "a" * 64,
        "actorPin": {"sourceManifestSha256": "b" * 64},
        "authority": {
            "sha256": "c" * 64,
            "path": str(root / "producer-approval.json"),
        },
        "config": {"path": str(root / "config.json"), "sha256": "a" * 64},
        "frozenCommit": FROZEN,
    }
    monkeypatch.setattr(
        launch,
        "_load_request",
        lambda *args, **kwargs: (
            request,
            _canonical(request),
            b'{"caseId":"synthetic-312"}',
            b"{}",
        ),
    )
    return launch, root / "launch-request.json", calls


def test_after_claim_exception_is_durable_unknown_and_never_replayed(
    fake_launch: tuple[ModuleType, Path, list[str]],
) -> None:
    launch, request_path, calls = fake_launch
    result = launch.start(request_path)
    assert result["state"] == "unknown-after-claim"
    assert calls == ["full_loop"]
    assert (request_path.parent / "launch-intent.json").exists()
    assert (
        json.loads((request_path.parent / "launch-result.json").read_text()) == result
    )
    records = _records(request_path.parent)
    assert [r["event"] for r in records] == ["claim", "claim", "exception"]
    assert records[-1]["kind"] == "exception"
    assert records[-1]["status"] == "unknown"
    assert records[-1]["exception"]["className"] == "RuntimeError"
    assert "SECRET1234" not in records[-1]["exception"]["message"]
    with pytest.raises(ValueError, match="already claimed"):
        launch.start(request_path)
    assert calls == ["full_loop"]


@pytest.mark.parametrize("boundary", ["before_claim", "after_claim"])
def test_failing_diagnostic_refuses_effects_even_after_claim(
    fake_launch: tuple[ModuleType, Path, list[str]],
    monkeypatch: pytest.MonkeyPatch,
    boundary: str,
) -> None:
    launch, request_path, calls = fake_launch
    original = diagnostics.DiagnosticJournal.emit

    def fail(
        self: diagnostics.DiagnosticJournal,
        event: str,
        at: str,
        **kwargs: Any,
    ) -> None:
        if event == "claim" and at == boundary:
            raise OSError("simulated fsync error")
        original(self, event, at, **kwargs)

    monkeypatch.setattr(diagnostics.DiagnosticJournal, "emit", fail)
    if boundary == "before_claim":
        with pytest.raises(OSError, match="fsync"):
            launch.start(request_path)
        assert not (request_path.parent / "launch-intent.json").exists()
    else:
        assert launch.start(request_path)["state"] == "unknown-after-claim"
        assert (request_path.parent / "launch-intent.json").exists()
        assert (
            json.loads((request_path.parent / "launch-result.json").read_text())[
                "state"
            ]
            == "unknown-after-claim"
        )
    assert calls == []


def test_after_start_render_before_poll_render_is_unknown_without_carrier_replay(
    patched_sources: dict[str, str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root = tmp_path / "native-actions"
    root.mkdir(mode=0o700)
    journal = diagnostics.DiagnosticJournal(
        root, case_id="synthetic-312", phase="pristine", stage="pristine"
    )
    journal.emit("claim", "after_claim")
    actions = [
        "construct",
        "save_reopen",
        "capture_pre",
        "queue_render",
        "start_render",
        "poll_render",
    ]
    emitted_native: list[str] = []
    controller = SimpleNamespace(
        context={"caseId": "synthetic-312", "phase": "pristine"}
    )

    def request_paths(context: Any, sequence: int) -> tuple[Path, None, None, Path]:
        return root / f"request-{sequence:02d}.json", None, None, root / "unused"

    def authenticated_result(path: Path, digest: str) -> dict[str, Any]:
        sequence = int(re.search(r"(\d+)\.json\Z", str(path)).group(1))  # type: ignore[union-attr]
        return {"sequence": sequence, "action": actions[sequence], "status": "complete"}

    for sequence, action in enumerate(actions[:5]):
        path, _, _, _ = request_paths(controller.context, sequence)
        path.write_bytes(b"{}")
        step = root / f"native-{sequence:02d}"
        step.mkdir(mode=0o700)
        _one_use(step / "intent.json", b"original-one-use-claim")
        receipt = {
            "path": str(root / f"signed-{sequence:02d}.json"),
            "sha256": "d" * 64,
        }
        ingestion = {
            "schema": "vera.test-bench-host-ingest/v1",
            "session": {"path": str(root / "session.json"), "sha256": "a" * 64},
            "result": receipt,
            "sequence": sequence,
            "action": action,
        }
        _one_use(step / "host-ingest-intent.json", _canonical(ingestion))
        _one_use(
            step / "host-ingested.json",
            _canonical(
                {
                    "sequence": sequence,
                    "action": action,
                    "status": "complete",
                    "resultSha256": "d" * 64,
                }
            ),
        )

    def status(path: Path) -> dict[str, Any]:
        seq = int(path.name.split("-")[-1])
        return {
            "state": "native_result_verified",
            "result": {
                "path": str(root / f"signed-{seq:02d}.json"),
                "sha256": "d" * 64,
            },
        }

    def injected_preparation(_: Path) -> None:
        raise RuntimeError("forced failure immediately before poll_render")

    controller.prepare_operator_plan = injected_preparation
    native = _stub(
        action_plan_for_context=lambda _: actions,
        native_request_paths=request_paths,
        verify_native_result=authenticated_result,
    )
    carrier = _stub(
        _private=lambda p, create=False: (
            p.mkdir(mode=0o700, parents=True, exist_ok=True) if create else None
        ),
        _read=lambda p, maximum=0: p.read_bytes(),
        _once=_one_use,
        _lock=lambda _: contextlib.nullcontext(),
        status=status,
        start=lambda *args, **kwargs: emitted_native.append("native_started"),
    )
    queue = _stub(QueueError=ValueError, canonical=_canonical)
    output = _module(
        monkeypatch,
        "output",
        patched_sources["output"],
        {
            "resolve_test_bench_carrier": carrier,
            "resolve_test_queue": queue,
            "qualification_output_native_v2": native,
            "qualification_output_controller_v2": _stub(
                issue_operator_approval=lambda *a, **k: None
            ),
        },
    )
    monkeypatch.setattr(output, "_session", lambda *args: controller)
    with pytest.raises(RuntimeError, match="before poll_render"):
        output.drive(
            root,
            session_path=root / "session.json",
            session_sha256="a" * 64,
            installed=root,
            consent_reference="producer-consent",
            consent_instruction="approved",
            max_seconds=60,
            minimum_free_bytes=1,
            diagnostic=journal,
        )
    records = _records(root)
    assert records[-1]["event"] == "exception"
    assert records[-1]["status"] == "unknown"
    assert records[-1]["lastVerified"] == {
        "nativeSequence": 4,
        "action": "start_render",
        "resultSha256": "d" * 64,
    }
    assert records[-1]["nextPending"] == {
        "nativeSequence": 5,
        "action": "poll_render",
    }
    assert not (root / "native-05" / "intent.json").exists()
    assert emitted_native == []
