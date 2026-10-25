"""Durable parent for the normal guarded Studio request (macOS/Linux)."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
import os
import runpy
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _read(path: Path) -> dict[str, Any]:
    if any(p.is_symlink() for p in (path, *path.absolute().parents)):
        raise ValueError("symbolic link in parent input")
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError("parent input must be an object")
    return value


def _write(path: Path, value: dict[str, Any]) -> None:
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.flush()
        os.fsync(stream.fileno())
    path.chmod(0o400)


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _request(path: Path, expected: str) -> dict[str, Any]:
    value = _read(path)
    if _digest(path) != expected:
        raise ValueError("parent request changed")
    if value.get("schemaVersion") != "vera-injected-delivery-request/v2":
        raise ValueError("parent supports only the normal v2 delivery request")
    return value


def start(request_path: Path, expected: str, python: Path) -> dict[str, Any]:
    """Dispatch once. Repeated calls only read the original operation."""
    from .workflow_v2_cli import LAUNCHER_NAME, _no_symlinks, _verify_release

    request_path = request_path.absolute()
    request = _request(request_path, expected)
    if request.get("externalScripting") != "Local":
        raise ValueError("parent dispatch requires explicit Local scripting authority")
    release = request_path.parent.parent
    if request_path != release / "vera-delivery-v2/request.json":
        raise ValueError("parent requires the installed request slot")
    manifest = _verify_release(release)
    if _digest(manifest) != request["releaseSha256"]:
        raise ValueError("parent release differs from request")
    evidence = Path(request["evidenceDir"])
    _no_symlinks(evidence)
    protected = [release, Path(request["packageDir"]), Path(request["attestationPath"])]
    if not evidence.is_absolute() or any(
        evidence.resolve().is_relative_to(p.resolve())
        or p.resolve().is_relative_to(evidence.resolve())
        for p in protected
    ):
        raise ValueError("parent evidence overlaps protected input")
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    session = evidence / "parent.json"
    with (evidence / "parent.lock").open("a+") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return status(request_path, expected)
        if session.exists():
            return status(request_path, expected, locked=True)
        if any(evidence.glob("started-*.json")) or any(evidence.glob("result-*.json")):
            raise ValueError(
                "prior operation evidence retained; inspect it, never replay"
            )
        record = {
            "schemaVersion": "vera-delivery-parent/v1",
            "requestPath": str(request_path),
            "requestSha256": expected,
            "startedAt": datetime.now(UTC).isoformat(),
            "monotonicStarted": time.monotonic(),
            "invocationId": uuid.uuid4().hex,
        }
        _write(session, record)
        try:
            with (evidence / "parent-console.log").open("x") as console:
                subprocess.Popen(
                    [
                        str(python),
                        str(Path(__file__).absolute()),
                        "_worker",
                        str(session),
                        str(lock.fileno()),
                        str(release / LAUNCHER_NAME),
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=console,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                    pass_fds=(lock.fileno(),),
                )
        except OSError:
            _write(
                evidence / "parent-exit.json",
                {
                    "returncode": 1,
                    "monotonicFinished": time.monotonic(),
                    "requestSha256": expected,
                },
            )
            raise
    return status(request_path, expected)


def status(
    request_path: Path, expected: str, *, locked: bool = False
) -> dict[str, Any]:
    """Read only; missing/corrupt evidence can never authorize another dispatch."""
    response: dict[str, Any] = {"state": "unknown", "verified": False}
    try:
        request_path = request_path.absolute()
        request = _request(request_path, expected)
        evidence = Path(request["evidenceDir"])
        session = _read(evidence / "parent.json")
        if (
            session["requestPath"] != str(request_path)
            or session["requestSha256"] != expected
        ):
            raise ValueError("parent session/request mismatch")
        begin = session["monotonicStarted"]
        if type(begin) not in (int, float) or not math.isfinite(begin) or begin < 0:
            raise ValueError("invalid parent clock")
        # flock proves worker ownership without mistaking a reused PID for liveness.
        if not locked:
            with (evidence / "parent.lock").open("r") as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    return {
                        **response,
                        "state": "live",
                        "elapsedSeconds": time.monotonic() - begin,
                    }
        exit_record = _read(evidence / "parent-exit.json")
        if exit_record["requestSha256"] != expected:
            raise ValueError("parent exit/request mismatch")
        end = exit_record["monotonicFinished"]
        if type(end) not in (int, float) or not math.isfinite(end) or end < begin:
            raise ValueError("invalid parent completion clock")
        response.update(state="failed", elapsedSeconds=end - begin)
        report_path = evidence / f"result-{expected}.json"
        hashes = _read(evidence / f"hashes-{expected}.json")
        report = _read(report_path)
        started = _read(evidence / f"started-{expected}.json")
        context = {
            "requestSha256": expected,
            "releaseSha256": request["releaseSha256"],
            "attestationSha256": request["attestationSha256"],
            "requestedProjectName": request["projectName"],
            "requestedTimelineName": request["timelineName"],
            "parentInvocationId": session["invocationId"],
        }
        if any(
            any(v.get(k) != value for k, value in context.items())
            for v in (started, report, hashes)
        ):
            raise ValueError("final evidence/request mismatch")
        if hashes["resultPath"] != str(report_path) or hashes[
            "resultSha256"
        ] != _digest(report_path):
            raise ValueError("final evidence hash mismatch")
        if report.get(
            "schemaVersion"
        ) != "vera-injected-delivery-result/v2" or report.get("status") not in {
            "verified",
            "preflight_passed",
            "verification_failed",
            "mutation_failed",
            "stopped_safely",
        }:
            raise ValueError("invalid final workflow result")
        if exit_record["returncode"] != 0:
            raise ValueError("parent worker failed")
        verified = (
            report["status"] == "verified"
            and report.get("verified") is True
            and report.get("discrepancies") == []
        )
        response.update(state="terminal", verified=verified, result=report)
    except (OSError, ValueError, KeyError, TypeError) as error:
        response["detail"] = str(error)
    return response


def wait(request_path: Path, expected: str, seconds: float) -> dict[str, Any]:
    """Bounded reattachment; expiration never kills or restarts the worker."""
    if not math.isfinite(seconds) or not 0 <= seconds <= 50:
        raise ValueError("wait must be between 0 and 50 seconds")
    deadline = time.monotonic() + seconds
    while True:
        report = status(request_path, expected)
        if report["state"] != "live" or time.monotonic() >= deadline:
            return report
        time.sleep(min(0.25, max(0, deadline - time.monotonic())))


def _worker(session_path: Path, lock_fd: int, launcher: Path) -> None:
    # File execution keeps the bootstrap's clean-runtime guard intact.
    record = _read(session_path)
    code = 1
    try:
        import DaVinciResolveScript as dvr  # type: ignore[import-not-found]

        resolve = dvr.scriptapp("Resolve")
        if not resolve:
            raise RuntimeError("Resolve is not reachable")
        if _digest(Path(record["requestPath"])) != record["requestSha256"]:
            raise ValueError("request changed before worker launch")
        os.environ["VERA_DELIVERY_PARENT_ID"] = record["invocationId"]
        runpy.run_path(
            str(launcher), run_name="__main__", init_globals={"resolve": resolve}
        )
        code = 0
    finally:
        _write(
            session_path.parent / "parent-exit.json",
            {
                "returncode": code,
                "requestSha256": record["requestSha256"],
                "monotonicFinished": time.monotonic(),
            },
        )
        os.close(lock_fd)


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_worker":
        _worker(Path(sys.argv[2]), int(sys.argv[3]), Path(sys.argv[4]))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("start", "status", "resume"))
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--request-sha256", required=True)
    parser.add_argument(
        "--python", type=Path, help="Resolve's bundled Python executable (start only)"
    )
    parser.add_argument("--wait-seconds", type=float, default=0)
    args = parser.parse_args()
    try:
        if args.action == "start":
            if args.python is None:
                raise ValueError("start requires --python")
            report = start(args.request, args.request_sha256, args.python)
        else:
            report = wait(args.request, args.request_sha256, args.wait_seconds)
        print(json.dumps(report, indent=2, sort_keys=True))
        return 0
    except (OSError, ValueError) as error:
        print(json.dumps({"state": "unknown", "verified": False, "detail": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
