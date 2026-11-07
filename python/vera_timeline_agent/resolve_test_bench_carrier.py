"""One-use, installed-source-verified external carrier for M4 native requests.

This is *not* a second Resolve engine.  The only native entry point is the
reviewed, hash-verified VERA Delivery v2 launcher, connected through the
supported local DaVinciResolveScript API.  Lost replies are UNKNOWN; this
module never redispatches a request whose intent has been recorded.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import stat
import subprocess
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from . import resolve_test_queue as queue

SCHEMA = "vera.test-bench-native-carrier/v1"
MAX_BYTES = 8 * 1024 * 1024


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _private(root: Path, *, create: bool = False) -> None:
    if (
        not root.is_absolute()
        or ".." in root.parts
        or any(part.is_symlink() for part in (root, *root.parents))
    ):
        raise queue.QueueError("unsafe carrier directory")
    if create:
        root.mkdir(parents=True, mode=0o700, exist_ok=True)
    info = root.stat()
    if (
        not stat.S_ISDIR(info.st_mode)
        or info.st_uid != os.getuid()
        or info.st_mode & 0o077
    ):
        raise queue.QueueError("carrier directory must be private and owned")


def _read(path: Path, maximum: int = MAX_BYTES) -> bytes:
    if not path.is_absolute() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise queue.QueueError("carrier input has unsafe path")
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_nlink != 1
            or info.st_size > maximum
        ):
            raise queue.QueueError("carrier input is not a bounded single-link file")
        raw = os.read(fd, maximum + 1)
        if len(raw) > maximum or os.read(fd, 1):
            raise queue.QueueError("carrier input exceeds bound")
        return raw
    finally:
        os.close(fd)


def _once(path: Path, raw: bytes) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "wb") as file:
        file.write(raw)
        file.flush()
        os.fsync(file.fileno())
    queue.sync_directory(path.parent)


@contextmanager
def _lock(root: Path) -> Iterator[int]:
    _private(root)
    file = root / "carrier.lock"
    if file.is_symlink():
        raise queue.QueueError("carrier lock is a symlink")
    fd = os.open(file, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise queue.QueueError("unsafe carrier lock ownership")
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise queue.QueueError("carrier is already running") from error
        yield fd
    finally:
        os.close(fd)


def _checked_request(source: Path, digest: str, installed: Path) -> dict[str, Any]:
    from .qualification_output_native_v2 import (
        REQUEST_SCHEMA,
        verify_native_request,
    )
    from .workflow_v2_cli import _verify_output_release

    raw = _read(source)
    if _digest(raw) != digest:
        raise queue.QueueError("source native request changed")
    request = json.loads(raw)
    if not isinstance(request, dict) or request.get("schemaVersion") != REQUEST_SCHEMA:
        raise queue.QueueError("only closed native output requests are supported")
    verify_native_request(raw, expected_request_sha256=digest)
    manifest = _verify_output_release(installed)
    if request["releaseManifestSha256"] != _digest(_read(manifest)):
        raise queue.QueueError("host authority is not for the installed release")
    if request["release"]["sha256"] != request["context"]["installedReleaseSha256"]:
        raise queue.QueueError("installed native source snapshot differs")
    if request["action"] not in {
        "construct",
        "save_reopen",
        "capture_pre",
        "observe_edited",
        "queue_render",
        "start_render",
        "poll_render",
        "capture_post",
    }:
        raise queue.QueueError("unsupported native action; no automatic retry")
    return request


def start(
    root: Path,
    source: Path,
    digest: str,
    installed: Path,
    *,
    python: Path = Path(sys.executable),
    spawn: Any = subprocess.Popen,
    preflight: Any = None,
) -> dict[str, Any]:
    """Reserve, install and spawn once; NEVER resume by calling start again."""
    from .resolve_native_owner import (
        native_owner,
        preflight_selected_disposable,
    )

    _private(root, create=True)
    with _lock(root) as lock_fd:
        if (root / "intent.json").exists() or (root / "intent.json").is_symlink():
            raise queue.QueueError(
                "carrier intent already spent; inspect, never replay"
            )
        request = _checked_request(source, digest, installed)
        target = request["target"]
        if request["context"]["target"] != target:
            raise queue.QueueError("source request target does not match context")
        slot = installed / "vera-delivery-v2/request.json"
        if source == slot:
            raise queue.QueueError(
                "request source must be independent of mutable installed slot"
            )
        # uv/venv Python normally is a symlink into the versioned interpreter.
        # Resolve its target once before spawning, unlike untrusted input files.
        if not python.is_absolute() or not python.resolve(strict=True).is_file():
            raise queue.QueueError("fixed local Python executable required")
        # preflight_selected_disposable directly acquires the shared owner
        # lock itself (it does NOT consult native_owner's contextvar). It must
        # run BEFORE our longer-lived owner scope, or it would self-deadlock.
        # The installed native engine independently rechecks exact UIDs and
        # retained history while holding the inherited owner before effects.
        (preflight or preflight_selected_disposable)(
            target, require_empty=request["action"] == "construct"
        )
        with native_owner(output_lane=True) as owner_fd:
            # Preserve the exact previous installed request, including failed
            # historical one-use requests; never erase its source evidence.
            if slot.exists() or slot.is_symlink():
                previous = _read(slot)
                _once(root / "previous-installed-request.json", previous)
            intent = {
                "schema": SCHEMA,
                "requestPath": str(source),
                "requestSha256": digest,
                "installedRoot": str(installed),
                "operationId": request["operationId"],
                "sequence": request["sequence"],
                "action": request["action"],
                "target": target,
                "invocationId": str(uuid.uuid4()),
            }
            _once(root / "intent.json", queue.canonical(intent))
            # Installed request is intentionally the only mutable release slot.
            # The review-pinned runtime/launcher files remain untouched.
            temporary = installed / f".test-bench-request-{uuid.uuid4().hex}"
            try:
                _once(temporary, _read(source))
                os.chmod(temporary, 0o400)
                os.replace(temporary, slot)
                queue.sync_directory(slot.parent)
                if _digest(_read(slot)) != digest:
                    raise queue.QueueError("installed request copy differs")
                with (root / "carrier-console.log").open("x") as console:
                    spawn(
                        [
                            str(python),
                            str(
                                Path(__file__).resolve().parents[1]
                                / "vera_test_bench_native_worker.py"
                            ),
                            str(root),
                            str(owner_fd),
                        ],
                        stdin=subprocess.DEVNULL,
                        stdout=console,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                        pass_fds=(lock_fd, owner_fd),
                    )
            finally:
                if temporary.exists():
                    # Only our unique, never-published staging path is deleted.
                    temporary.unlink()
    return {"state": "dispatched_once", "operationId": request["operationId"]}


def status(root: Path) -> dict[str, Any]:
    """Inspect the exact original native result; no effects or retries."""
    from .qualification_output_native_v2 import (
        native_request_paths,
        verify_native_result,
    )

    _private(root)
    if not (root / "intent.json").exists():
        return {"state": "not_started", "verified": False}
    intent = json.loads(_read(root / "intent.json"))
    if (
        set(intent)
        != {
            "schema",
            "requestPath",
            "requestSha256",
            "installedRoot",
            "operationId",
            "sequence",
            "action",
            "target",
            "invocationId",
        }
        or intent["schema"] != SCHEMA
    ):
        raise queue.QueueError("carrier intent fields differ")
    source = Path(intent["requestPath"])
    request = _checked_request(
        source, intent["requestSha256"], Path(intent["installedRoot"])
    )
    if any(
        request[k] != intent[k] for k in ("operationId", "sequence", "action", "target")
    ):
        raise queue.QueueError("carrier intent and host operation disagree")
    result_path = native_request_paths(request["context"], request["sequence"])[0]
    try:
        raw = _read(result_path)
        verified = verify_native_result(result_path, _digest(raw))
    except (OSError, ValueError, KeyError, TypeError):
        if not result_path.exists() and _active_worker(root):
            return {
                "state": "live",
                "verified": False,
                "operationId": intent["operationId"],
            }
        return {
            "state": "unknown",
            "verified": False,
            "operationId": intent["operationId"],
        }
    if (
        verified.get("operationId") != intent["operationId"]
        or verified.get("action") != intent["action"]
        or verified.get("target") != intent["target"]
        or verified.get("status") != "complete"
    ):
        return {
            "state": "unknown",
            "verified": False,
            "operationId": intent["operationId"],
        }
    return {
        "state": "native_result_verified",
        "verified": True,
        "operationId": intent["operationId"],
        "result": {"path": str(result_path), "sha256": _digest(raw)},
    }


def _active_worker(root: Path) -> bool:
    """An inherited flock, not an untrusted PID, proves liveness."""
    lock = root / "carrier.lock"
    if lock.is_symlink() or not lock.is_file():
        return False
    fd = os.open(lock, os.O_RDWR | os.O_NOFOLLOW)
    try:
        info = os.fstat(fd)
        if (
            not stat.S_ISREG(info.st_mode)
            or info.st_uid != os.getuid()
            or info.st_mode & 0o077
        ):
            raise queue.QueueError("unsafe active carrier lock")
        try:
            fcntl.flock(fd, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        return False
    finally:
        os.close(fd)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--request", type=Path)
    parser.add_argument("--request-sha256")
    parser.add_argument("--installed", type=Path)
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    args = parser.parse_args()
    try:
        if args.action == "start":
            if (
                args.request is None
                or args.request_sha256 is None
                or args.installed is None
            ):
                raise queue.QueueError(
                    "start requires exact request, SHA and installed root"
                )
            outcome = start(
                args.root,
                args.request,
                args.request_sha256,
                args.installed,
                python=args.python,
            )
        else:
            outcome = status(args.root)
        print(json.dumps(outcome, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print(json.dumps({"state": "unknown", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
