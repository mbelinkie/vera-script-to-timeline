"""Never invoke the real Resolve application from carrier unit tests."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_queue as queue


def _host(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, action: str = "construct"
) -> tuple[
    Path,
    Path,
    str,
    Path,
    list[Any],
    Callable[..., None],
    list[Any],
    Callable[..., None],
]:
    from vera_timeline_agent import resolve_native_owner as owner

    root = tmp_path / "run"
    installed = tmp_path / "installed"
    (installed / "vera-delivery-v2").mkdir(parents=True)
    source = tmp_path / "pinned-native.json"
    source.write_bytes(b"verified host request")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    target = {"projectUid": "project-1", "timelineUid": "timeline-1"}
    request = {
        "action": action,
        "target": target,
        "context": {"target": target},
        "operationId": "op-once",
        "sequence": 0,
    }
    monkeypatch.setattr(carrier, "_checked_request", lambda *a: request)
    monkeypatch.setattr(
        owner, "acquire_native_owner", lambda: os.open(os.devnull, os.O_RDONLY)
    )
    selected: list[Any] = []

    def check(t: Any, *, require_empty: bool) -> None:
        selected.append((t, require_empty))

    spawned: list[Any] = []

    def spawn(*args: Any, **kwargs: Any) -> None:
        spawned.append((args, kwargs))

    return root, source, digest, installed, selected, check, spawned, spawn


def test_exactly_once_installs_pinned_request_and_preserves_previous(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source, digest, installed, selected, check, spawned, spawn = _host(
        tmp_path, monkeypatch
    )
    slot = installed / "vera-delivery-v2/request.json"
    slot.write_bytes(b"historical partial - do not erase")
    result = carrier.start(
        root, source, digest, installed, spawn=spawn, preflight=check
    )
    assert result == {"state": "dispatched_once", "operationId": "op-once"}
    assert selected == [
        ({"projectUid": "project-1", "timelineUid": "timeline-1"}, True)
    ]
    assert slot.read_bytes() == source.read_bytes()
    assert (
        root / "previous-installed-request.json"
    ).read_bytes() == b"historical partial - do not erase"
    assert json.loads((root / "intent.json").read_bytes())["requestSha256"] == digest
    assert len(spawned) == 1
    assert spawned[0][1]["pass_fds"]
    with pytest.raises(queue.QueueError, match="already spent"):
        carrier.start(root, source, digest, installed, spawn=spawn, preflight=check)
    assert len(spawned) == 1


def test_failure_after_intent_is_unknown_and_never_retries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source, digest, installed, _, check, _, _ = _host(tmp_path, monkeypatch)

    def crash(*args: Any, **kwargs: Any) -> None:
        raise OSError("spawn failed; its effect may be uncertain")

    with pytest.raises(OSError, match="spawn failed"):
        carrier.start(root, source, digest, installed, spawn=crash, preflight=check)
    assert (root / "intent.json").exists()
    with pytest.raises(queue.QueueError, match="already spent"):
        carrier.start(root, source, digest, installed, spawn=crash, preflight=check)


def test_preflight_refusal_never_writes_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source, digest, installed, _, _, _, spawn = _host(tmp_path, monkeypatch)

    def refuse(*args: Any, **kwargs: Any) -> None:
        raise ValueError("wrong target UID")

    with pytest.raises(ValueError, match="wrong target"):
        carrier.start(root, source, digest, installed, spawn=spawn, preflight=refuse)
    assert not (root / "intent.json").exists()
    assert not (installed / "vera-delivery-v2/request.json").exists()


@pytest.mark.parametrize("error", ["bad", "partial", "wrong-target", "wrong-operation"])
def test_read_only_status_never_accepts_unverified_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, error: str
) -> None:
    root, source, digest, installed, _, check, _, spawn = _host(tmp_path, monkeypatch)
    carrier.start(root, source, digest, installed, spawn=spawn, preflight=check)
    from vera_timeline_agent import qualification_output_native_v2 as native

    native_path = tmp_path / "native.json"
    native_path.write_text('{"real":true}')
    monkeypatch.setattr(native, "native_request_paths", lambda c, s: (native_path,))
    if error == "bad":
        monkeypatch.setattr(
            native,
            "verify_native_result",
            lambda *args: (_ for _ in ()).throw(ValueError("unverified")),
        )
    else:
        monkeypatch.setattr(
            native,
            "verify_native_result",
            lambda *args: {
                "status": "partial" if error == "partial" else "complete",
                "operationId": "other" if error == "wrong-operation" else "op-once",
                "action": "construct",
                "target": {"projectUid": "other"}
                if error == "wrong-target"
                else {"projectUid": "project-1", "timelineUid": "timeline-1"},
            },
        )
    assert carrier.status(root)["state"] == "unknown"
    assert not carrier.status(root)["verified"]


def test_status_accepts_only_independently_verified_native_result(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source, digest, installed, _, check, _, spawn = _host(tmp_path, monkeypatch)
    carrier.start(root, source, digest, installed, spawn=spawn, preflight=check)
    from vera_timeline_agent import qualification_output_native_v2 as native

    path = tmp_path / "signed-native.json"
    path.write_bytes(b"authentic-native-evidence")
    monkeypatch.setattr(native, "native_request_paths", lambda c, s: (path,))
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda *args: {
            "operationId": "op-once",
            "action": "construct",
            "status": "complete",
            "target": {"projectUid": "project-1", "timelineUid": "timeline-1"},
        },
    )
    result = carrier.status(root)
    assert result["state"] == "native_result_verified"
    assert result["result"]["sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()


def test_symlinked_private_run_directory_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, source, digest, installed, _, check, _, spawn = _host(tmp_path, monkeypatch)
    other = tmp_path / "actual"
    other.mkdir()
    root.symlink_to(other, target_is_directory=True)
    with pytest.raises(queue.QueueError, match="unsafe carrier directory"):
        carrier.start(root, source, digest, installed, spawn=spawn, preflight=check)


def test_clean_worker_invokes_only_fixed_launcher_with_local_sdk(
    tmp_path: Path,
) -> None:
    """The reviewed bootstrap rejects any preloaded VERA package runtime."""
    root = tmp_path / "run"
    root.mkdir()
    release = tmp_path / "release"
    (release / "vera-delivery-v2").mkdir(parents=True)
    (release / "vera-delivery-v2/request.json").write_bytes(b"request")
    (release / "VERA Delivery v2.py").write_text(
        "import pathlib, sys\n"
        "assert not any("
        "x == 'vera_timeline_agent' or "
        "x.startswith('vera_timeline_agent.') "
        "for x in sys.modules)\n"
        "assert resolve.GetVersion() == [21, 1, 0]\n"
        f"pathlib.Path({str(tmp_path / 'called.txt')!r})"
        ".write_text('native entry received')\n"
    )
    (tmp_path / "DaVinciResolveScript.py").write_text(
        "class Resolve:\n"
        "    def GetVersion(self): return [21, 1, 0]\n"
        "def scriptapp(name):\n"
        "    assert name == 'Resolve'\n"
        "    return Resolve()\n"
    )
    (root / "intent.json").write_bytes(
        queue.canonical(
            {
                "schema": carrier.SCHEMA,
                "installedRoot": str(release),
                "requestSha256": hashlib.sha256(b"request").hexdigest(),
            }
        )
    )
    env = os.environ.copy()
    env["PYTHONPATH"] = str(tmp_path)
    worker = (
        Path(__file__).resolve().parents[1] / "python/vera_test_bench_native_worker.py"
    )
    result = subprocess.run(
        [sys.executable, str(worker), str(root), "3"],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "called.txt").read_text() == "native entry received"


def test_clean_worker_rejects_modified_request_before_sdk(
    tmp_path: Path,
) -> None:
    root = tmp_path / "run"
    root.mkdir()
    release = tmp_path / "release"
    (release / "vera-delivery-v2").mkdir(parents=True)
    (release / "vera-delivery-v2/request.json").write_bytes(b"unexpected")
    (root / "intent.json").write_bytes(
        queue.canonical(
            {
                "schema": carrier.SCHEMA,
                "installedRoot": str(release),
                "requestSha256": "a" * 64,
            }
        )
    )
    worker = (
        Path(__file__).resolve().parents[1] / "python/vera_test_bench_native_worker.py"
    )
    result = subprocess.run(
        [sys.executable, str(worker), str(root), "3"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "installed request SHA differs" in result.stderr


def test_active_worker_requires_inherited_kernel_flock(tmp_path: Path) -> None:
    root = tmp_path / "run"
    root.mkdir(mode=0o700)
    lock = root / "carrier.lock"
    assert not carrier._active_worker(root)
    with lock.open("x+b") as file:
        lock.chmod(0o600)
        fcntl.flock(file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert carrier._active_worker(root) is True
    assert carrier._active_worker(root) is False
