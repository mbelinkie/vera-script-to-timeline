"""One-use Conductor -> dedicated M4 runner handoff.

The immutable launch envelope is *not* a native-effect authority.  A full
launch must separately deliver the existing case-bound authorization and pass
the original full-loop admission.  A focus rehearsal can only call the signed
helper's focus endpoint; it cannot enter the native M4 stage machine.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from . import resolve_gui_helper_protocol as helper
from . import resolve_gui_roll as gui
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_full_loop as full_loop
from . import resolve_test_bench_helper_transport as transport
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4

SCHEMA = "vera.conductor-m4-one-start/v1"
RESULT_SCHEMA = "vera.conductor-m4-one-start-result/v1"
_FIELDS = {
    "schema",
    "requestId",
    "mode",
    "frozenCommit",
    "sourceGraphSha256",
    "config",
    "authority",
    "actorPin",
    "resolvePid",
    "windowName",
    "issuedAt",
    "expiresAt",
}
_RESULT_FIELDS = {
    "schema",
    "requestId",
    "requestSha256",
    "mode",
    "sourceGraphSha256",
    "frozenCommit",
    "authoritySha256",
    "runnerPid",
    "state",
    "jobId",
    "observation",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[a-zA-Z0-9_-]{8,100}\Z")
_MODES = {"focus-only", "complete-m4"}


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise queue.QueueError("Conductor one-start refused: " + message)


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _ref(value: object, label: str) -> tuple[Path, str]:
    _require(
        type(value) is dict
        and set(value) == {"path", "sha256"}
        and type(value["path"]) is str
        and type(value["sha256"]) is str
        and _SHA.fullmatch(value["sha256"]) is not None,
        label + " requires a fixed file/digest",
    )
    assert isinstance(value, dict)
    path = Path(value["path"])
    _require(path.is_absolute() and ".." not in path.parts, label + " unsafe path")
    return path, value["sha256"]


def _load_request(
    path: Path, *, for_start: bool
) -> tuple[dict[str, Any], bytes, bytes | None, bytes | None]:
    _require(
        path.name == "launch-request.json", "fixed launch request filename required"
    )
    carrier._private(path.parent)
    raw = carrier._read(path, 16384)
    try:
        request = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as error:
        raise queue.QueueError("Conductor request is not JSON") from error
    _require(
        type(request) is dict
        and set(request) == _FIELDS
        and raw == queue.canonical(request)
        and request["schema"] == SCHEMA
        and type(request["requestId"]) is str
        and _ID.fullmatch(request["requestId"]) is not None
        and request["mode"] in _MODES
        and type(request["frozenCommit"]) is str
        and re.fullmatch(r"[0-9a-f]{40}", request["frozenCommit"]) is not None
        and type(request["sourceGraphSha256"]) is str
        and _SHA.fullmatch(request["sourceGraphSha256"]) is not None,
        "closed canonical request, mode and source pins required",
    )
    # Parsing a retained audit must not require still-live consent, an
    # installed helper, or the source checkout that existed on launch day.
    # Freshness and installed identity are START-only gates.
    try:
        issued, expires = queue.dt(request["issuedAt"]), queue.dt(request["expiresAt"])
    except (ValueError, TypeError, OverflowError) as error:
        raise queue.QueueError("Conductor launch clock invalid") from error
    _require(
        timedelta(0) < expires - issued <= timedelta(minutes=5),
        "unbounded or inverted Conductor launch window",
    )
    _require(
        type(request["actorPin"]) is dict
        and set(request["actorPin"]) == helper.ACTOR_KEYS
        and request["actorPin"].get("schema") == helper.ACTOR_SCHEMA
        and type(request["actorPin"].get("sourceManifestSha256")) is str
        and _SHA.fullmatch(request["actorPin"]["sourceManifestSha256"]) is not None,
        "closed helper actor identity required",
    )
    helper.validate_binary_pin(request["actorPin"]["binary"])
    if for_start:
        now = datetime.now(UTC)
        _require(
            issued <= now < expires and now - issued <= timedelta(minutes=5),
            "short one-start launch authorization expired or future-dated",
        )
        helper.validate_actor_pin(request["actorPin"], installed=True)
        _require(
            request["actorPin"]["sourceManifestSha256"]
            == helper.source_manifest_sha256(),
            "helper actor source differs",
        )
    config_raw: bytes | None = None
    authority_raw: bytes | None = None
    if request["mode"] == "focus-only":
        _require(
            request["config"] is None
            and request["authority"] is None
            and type(request["resolvePid"]) is int
            and request["resolvePid"] > 0
            and type(request["windowName"]) is str
            and bool(request["windowName"].strip())
            and gui._safe_name(request["windowName"]),
            "focus rehearsal cannot carry native authority or missing target",
        )
    else:
        _require(
            request["resolvePid"] is None and request["windowName"] is None,
            "native target must come from signed M4 admission, not launch caller",
        )
        config_path, config_sha = _ref(request["config"], "config")
        authority_path, authority_sha = _ref(request["authority"], "authority")
        config_raw = carrier._read(config_path, 16384)
        authority_raw = carrier._read(authority_path, 32768)
        _require(
            _digest(config_raw) == config_sha
            and _digest(authority_raw) == authority_sha,
            "immutable Conductor config or authority changed",
        )
        from . import resolve_test_bench_m4_runner as runner

        config = runner.validate_config(json.loads(config_raw))
        case_root = runner._absolute(config["root"], "root")
        carrier._private(case_root)
        _require(
            config_path == case_root / "config.json"
            and authority_path == case_root / "producer-approval.json"
            and path.parent == case_root,
            "Conductor request/config/authority require one exact private case root",
        )
        try:
            authority = json.loads(authority_raw)
        except (ValueError, UnicodeDecodeError) as error:
            raise queue.QueueError("Conductor authority invalid JSON") from error
        _require(
            type(authority) is dict
            and authority.get("actorPin") == request["actorPin"]
            and authority.get("frozenCommit") == request["frozenCommit"]
            and authority.get("sourceGraphSha256") == request["sourceGraphSha256"],
            "Conductor delivered mismatched authority and helper actor",
        )
    return request, raw, config_raw, authority_raw


def _result(
    request: dict[str, Any],
    raw: bytes,
    state: str,
    *,
    job_id: str | None = None,
    observation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema": RESULT_SCHEMA,
        "requestId": request["requestId"],
        "requestSha256": _digest(raw),
        "mode": request["mode"],
        "sourceGraphSha256": request["sourceGraphSha256"],
        "frozenCommit": request["frozenCommit"],
        "authoritySha256": request["authority"]["sha256"]
        if request["authority"]
        else None,
        "runnerPid": os.getpid(),
        "state": state,
        "jobId": job_id,
        "observation": observation,
    }


def _focus_observation_matches(value: object, *, pid: int, window: str) -> bool:
    """A helper reply is a readiness observation, never a native edit receipt."""
    return (
        type(value) is dict
        and set(value)
        == {
            "resolvePid",
            "bundleIdentifier",
            "windowName",
            "mainWindow",
            "foreground",
            "noModalOrSheet",
            "rollEnabled",
        }
        and type(value["resolvePid"]) is int
        and value["resolvePid"] == pid
        and value["bundleIdentifier"] == gui.RESOLVE_BUNDLE_ID
        and value["windowName"] == window
        and all(
            value[key] is True
            for key in ("mainWindow", "foreground", "noModalOrSheet", "rollEnabled")
        )
    )


def dispatch(request_path: Path) -> dict[str, Any]:
    """Conductor hands one immutable request to a detached macOS user job.

    A single Aqua LaunchAgent is explicitly NON-RESTARTING. No launchd submit
    or KeepAlive fallback is allowed; the dispatcher never implies a PASS.
    """
    _require(sys.platform == "darwin", "detached Aqua launch requires macOS")
    request, raw, _, _ = _load_request(request_path, for_start=True)
    _require(
        full_loop._frozen_source(request["frozenCommit"])
        == request["sourceGraphSha256"],
        "Conductor may dispatch only the exact frozen checkout",
    )
    root = request_path.parent
    control = root / ".conductor-launch"
    repo = Path(__file__).resolve().parents[2]
    label = "org.vera.testbench." + request["requestId"]
    plist = {
        "Label": label,
        "ProgramArguments": [
            sys.executable,
            "-m",
            "vera_timeline_agent.resolve_test_bench_conductor_launch",
            "start",
            "--request",
            str(request_path),
        ],
        "WorkingDirectory": str(repo),
        "EnvironmentVariables": {
            "PYTHONPATH": str(repo / "python"),
            "PATH": str(Path(sys.executable).parent) + ":/usr/bin:/bin:/usr/sbin:/sbin",
            "PYTHONDONTWRITEBYTECODE": "1",
        },
        "LimitLoadToSessionType": "Aqua",
        "RunAtLoad": True,
        "KeepAlive": False,
        "StandardOutPath": str(root / "runner.stdout.log"),
        "StandardErrorPath": str(root / "runner.stderr.log"),
    }
    uid = os.getuid()
    domain = f"gui/{uid}"
    # Probe the actual logged-in Aqua domain, rather than current SSH/CLI
    # process context. No native effect or case claim at this point.
    try:
        check = subprocess.run(
            ["/bin/launchctl", "print", domain],
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise queue.QueueError("Aqua launchd domain unavailable") from error
    _require(check.returncode == 0, "Aqua launchd domain is not active")
    carrier._private(control, create=True)
    with carrier._lock(control):
        _, now_raw, _, _ = _load_request(request_path, for_start=True)
        _require(now_raw == raw, "Conductor launch changed before handoff")
        _require(
            not (root / "launch-submit-intent.json").exists()
            and not (root / "launch-intent.json").exists(),
            "Conductor launch already submitted or claimed",
        )
        carrier._once(root / "runner.launchagent.plist", plistlib.dumps(plist))
        carrier._once(
            root / "launch-submit-intent.json",
            queue.canonical(
                {
                    "schema": SCHEMA,
                    "requestSha256": _digest(raw),
                    "runnerExecutable": str(Path(sys.executable)),
                }
            ),
        )
    command = [
        "/bin/launchctl",
        "bootstrap",
        domain,
        str(root / "runner.launchagent.plist"),
    ]
    try:
        submitted = subprocess.run(
            command, capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.TimeoutExpired):
        return {"state": "unknown-dispatch", "requestSha256": _digest(raw)}
    if submitted.returncode != 0:
        return {"state": "unknown-dispatch", "requestSha256": _digest(raw)}
    return {
        "state": "submitted-not-verified",
        "requestSha256": _digest(raw),
        "label": label,
    }


def start(request_path: Path) -> dict[str, Any]:
    """Consume one launch claim before any possible effect; never retry UNKNOWN."""
    request, raw, config_raw, authority_raw = _load_request(
        request_path, for_start=True
    )
    _require(
        full_loop._frozen_source(request["frozenCommit"])
        == request["sourceGraphSha256"],
        "frozen source graph not current",
    )
    root = request_path.parent
    # Do not share carrier.lock with the native runner when both request and
    # immutable config naturally live in the same case directory.
    launch_lock_root = root / ".conductor-launch"
    carrier._private(launch_lock_root, create=True)
    with carrier._lock(launch_lock_root):
        request_again, raw_again, config_again, authority_again = _load_request(
            request_path, for_start=True
        )
        _require(
            request_again == request
            and raw_again == raw
            and config_again == config_raw
            and authority_again == authority_raw,
            "launch request or case source drifted before claim",
        )
        _require(
            not (root / "launch-intent.json").exists()
            and not (root / "launch-intent.json").is_symlink()
            and not (root / "launch-result.json").exists()
            and not (root / "launch-result.json").is_symlink(),
            "launch already claimed or completed, no replay",
        )
        carrier._once(
            root / "launch-intent.json",
            queue.canonical({"schema": SCHEMA, "requestSha256": _digest(raw)}),
        )
        try:
            if request["mode"] == "focus-only":
                observation = transport.SignedHelperDesktop(request["actorPin"]).focus(
                    request["requestId"],
                    "no-edit-rehearsal",
                    request["resolvePid"],
                    request["windowName"],
                )
                _require(
                    _focus_observation_matches(
                        observation,
                        pid=request["resolvePid"],
                        window=request["windowName"],
                    ),
                    "signed helper returned wrong-window or incomplete focus",
                )
                result = _result(request, raw, "focus-ready", observation=observation)
            else:
                config_path, config_sha = _ref(request["config"], "config")
                authority_path, authority_sha = _ref(request["authority"], "authority")
                outcome = full_loop.start(
                    config_path,
                    authority_path,
                    frozen_commit=request["frozenCommit"],
                    expected_config_sha256=config_sha,
                    expected_authority_sha256=authority_sha,
                )
                job_id = outcome.get("jobId")
                _require(
                    outcome.get("state") == "original_M4_four_stages_verified"
                    and type(job_id) is str
                    and m4.ID_RE.fullmatch(job_id) is not None,
                    "native four-stage host did not complete",
                )
                from . import resolve_test_bench_m4_runner as runner

                assert config_raw is not None and isinstance(job_id, str)
                config = runner.validate_config(json.loads(config_raw))
                report = m4.publish(queue.Store(Path(config["queueRoot"])), job_id)
                _require(
                    report["state"] == "completed_verified"
                    and report["readyFor312Phase2"] is True
                    and [row["state"] for row in report["stages"]] == ["verified"] * 4,
                    "authenticated original M4 handoff incomplete",
                )
                result = _result(request, raw, "four-stages-verified", job_id=job_id)
        except BaseException:
            # The claim has already been fsynced.  We cannot know whether an
            # external effect happened; never turn this into a retryable error.
            result = _result(request, raw, "unknown-after-claim")
        carrier._once(root / "launch-result.json", queue.canonical(result))
        return result


def _runner_lock_held(root: Path) -> bool:
    """Read-only liveness probe, not an attempt to acquire a second owner."""
    lock_path = root / ".conductor-launch" / "carrier.lock"
    if not lock_path.is_file() or lock_path.is_symlink():
        return False
    descriptor = os.open(lock_path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        try:
            fcntl.flock(descriptor, fcntl.LOCK_SH | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(descriptor, fcntl.LOCK_UN)
        return False
    finally:
        os.close(descriptor)


def verify(request_path: Path) -> dict[str, Any]:
    """Conductor read-only verification; never repair or redispatch a claim."""
    request, raw, config_raw, _ = _load_request(request_path, for_start=False)
    root = request_path.parent
    try:
        intent_raw = carrier._read(root / "launch-intent.json", 4096)
    except FileNotFoundError:
        submitted = root / "launch-submit-intent.json"
        if submitted.is_file():
            dispatch_intent = json.loads(carrier._read(submitted, 4096))
            _require(
                dispatch_intent.get("schema") == SCHEMA
                and dispatch_intent.get("requestSha256") == _digest(raw),
                "Conductor detached submission is for another request",
            )
            return {
                "state": "submitted-unclaimed",
                "verified": False,
                "requestSha256": _digest(raw),
                "detail": "runner not yet claimed; never submit this request again",
            }
        raise
    expected_intent = queue.canonical({"schema": SCHEMA, "requestSha256": _digest(raw)})
    _require(intent_raw == expected_intent, "immutable Conductor launch claim differs")
    try:
        result_raw = carrier._read(root / "launch-result.json", 4096)
    except FileNotFoundError:
        # The dispatcher/runner may have crashed or been killed after its
        # durable claim.  This is UNKNOWN, never a pre-effect refusal/retry.
        live = _runner_lock_held(root)
        return {
            "state": "in-progress" if live else "unknown-after-claim",
            "verified": False,
            "requestSha256": _digest(raw),
            "detail": "runner holds one-use lock"
            if live
            else "claimed run has no result; inspect, never replay",
        }
    result = json.loads(result_raw)
    _require(
        type(result) is dict
        and set(result) == _RESULT_FIELDS
        and result_raw == queue.canonical(result)
        and result["schema"] == RESULT_SCHEMA
        and result["requestId"] == request["requestId"]
        and result["requestSha256"] == _digest(raw)
        and result["mode"] == request["mode"]
        and result["sourceGraphSha256"] == request["sourceGraphSha256"]
        and result["frozenCommit"] == request["frozenCommit"]
        and result["authoritySha256"]
        == (request["authority"]["sha256"] if request["authority"] else None)
        and type(result["runnerPid"]) is int
        and result["runnerPid"] > 0,
        "result not bound to claimed immutable Conductor request",
    )
    if request["mode"] == "focus-only":
        _require(
            result["state"] in {"focus-ready", "unknown-after-claim"}
            and result["jobId"] is None
            and (
                result["state"] != "focus-ready"
                or _focus_observation_matches(
                    result["observation"],
                    pid=request["resolvePid"],
                    window=request["windowName"],
                )
            ),
            "no-edit focus observation not authenticated",
        )
    else:
        _require(
            result["state"] in {"four-stages-verified", "unknown-after-claim"}
            and result["observation"] is None,
            "Conductor result state or observation invalid",
        )
        if result["state"] == "four-stages-verified":
            from . import resolve_test_bench_m4_runner as runner

            assert config_raw is not None
            config = runner.validate_config(json.loads(config_raw))
            _require(
                type(result["jobId"]) is str
                and m4.ID_RE.fullmatch(result["jobId"]) is not None,
                "bad signed M4 job identity",
            )
            config_path, config_sha = _ref(request["config"], "config")
            authority_path, authority_sha = _ref(request["authority"], "authority")
            case_root = runner._absolute(config["root"], "root")
            complete_raw = carrier._read(case_root / "complete-loop-intent.json", 16384)
            _require(
                complete_raw
                == queue.canonical(
                    {
                        "schema": full_loop.INTENT_SCHEMA,
                        "config": {"path": str(config_path), "sha256": config_sha},
                        "authority": {
                            "path": str(authority_path),
                            "sha256": authority_sha,
                        },
                        "frozenCommit": request["frozenCommit"],
                        "sourceGraphSha256": request["sourceGraphSha256"],
                    }
                ),
                "original M4 launch intent differs from Conductor authority",
            )
            inspected = full_loop.inspect(config_path)
            _require(
                inspected.get("jobId") == result["jobId"]
                and inspected.get("verified") is True
                and inspected.get("state") == "completed_verified",
                "Conductor result names a foreign, unverified or old original M4 job",
            )
            report = m4.publish(queue.Store(Path(config["queueRoot"])), result["jobId"])
            _require(
                report["state"] == "completed_verified"
                and report["readyFor312Phase2"] is True
                and [row["state"] for row in report["stages"]] == ["verified"] * 4,
                "signed original M4 results missing or altered",
            )
    if result["state"] == "unknown-after-claim":
        _require(
            result["jobId"] is None and result["observation"] is None,
            "unknown result must not claim a native job or helper observation",
        )
    return dict(result)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("dispatch", "start", "verify"))
    parser.add_argument("--request", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.action == "dispatch":
            result = dispatch(args.request)
        elif args.action == "start":
            result = start(args.request)
        else:
            result = verify(args.request)
        print(json.dumps(result, sort_keys=True))
        return (
            0
            if result["state"]
            in {"focus-ready", "four-stages-verified", "submitted-not-verified"}
            else 2
        )
    except (OSError, ValueError, TypeError, RuntimeError, KeyError) as error:
        claimed = False
        submitted = False
        with suppress(OSError, ValueError, RuntimeError):
            claimed = bool(
                carrier._read(args.request.parent / "launch-intent.json", 4096)
            )
        with suppress(OSError, ValueError, RuntimeError):
            submitted = bool(
                carrier._read(args.request.parent / "launch-submit-intent.json", 4096)
            )
        if args.action == "verify":
            status = "audit-invalid"
        elif args.action == "dispatch":
            status = "already-submitted" if submitted else "refused"
        elif claimed:
            status = (
                "already-claimed"
                if "already claimed" in str(error)
                else "unknown-after-claim"
            )
        else:
            status = "refused"
        print(
            json.dumps(
                {
                    "state": status,
                    "verified": False,
                    "detail": str(error),
                }
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
