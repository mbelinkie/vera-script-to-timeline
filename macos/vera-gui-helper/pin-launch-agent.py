#!/usr/bin/env python3
"""Install a source-frozen, self-attested Aqua GUI helper LaunchAgent.

Never interacts with Resolve, edits a target, or reuses any native one-use
case. This helper's only runtime action is a signed no-edit actor-pin probe.
"""

from __future__ import annotations

import hashlib
import json
import os
import plistlib
import re
import stat
import subprocess
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from vera_timeline_agent import resolve_gui_helper_protocol as protocol
from vera_timeline_agent import resolve_test_bench_carrier as carrier
from vera_timeline_agent import resolve_test_bench_full_loop as full
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent.resolve_gui_helper_build_guard import active_conductor_cases
from vera_timeline_agent.resolve_native_owner import native_owner

LABEL = "org.vera.resolve-test-bench.gui"
BASE = Path.home() / "Library/Application Support/VERA/GUI Helper"
EXE = BASE / "VERA GUI Helper.app/Contents/MacOS/VERAGUIHelper"
SPOOL = BASE / "spool"
PLIST = Path.home() / "Library/LaunchAgents" / (LABEL + ".plist")
TEMPLATE = Path(__file__).resolve().with_name("LaunchAgent.plist.in")


class PinInstallRefused(RuntimeError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise PinInstallRefused("signed GUI helper launch gate: " + detail)


def sh(*cmd: str, timeout: int = 18) -> subprocess.CompletedProcess[str]:
    done = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    require(done.returncode == 0, "command refused: " + Path(cmd[0]).name)
    return done


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def private_file(path: Path, *, maximum: int = 65536) -> bytes:
    require(
        not path.is_symlink() and path.is_file(),
        "required regular file absent or alias",
    )
    st = path.stat(follow_symlinks=False)
    require(
        stat.S_ISREG(st.st_mode)
        and st.st_uid == os.getuid()
        and st.st_nlink == 1
        and not st.st_mode & 0o077
        and st.st_size <= maximum,
        "unsafe helper plist permissions/size",
    )
    return carrier._read(path, maximum)


def owner_directory(path: Path) -> None:
    require(
        not path.is_symlink() and path.is_dir(), "LaunchAgent directory alias/absence"
    )
    st = path.stat(follow_symlinks=False)
    require(
        st.st_uid == os.getuid()
        and stat.S_ISDIR(st.st_mode)
        and not st.st_mode & 0o022,
        "LaunchAgent directory owner or write permissions unsafe",
    )


def verified_build_provenance(
    commit: str, graph: str, manifest: str, binary: str
) -> None:
    """Bind exact signed bytes to the trusted clean source at build time."""
    evidence = BASE / ("built-source-pins-" + binary + ".json")
    raw = private_file(evidence, maximum=4096)
    try:
        record = json.loads(raw)
    except (UnicodeError, ValueError) as exc:
        raise PinInstallRefused("signed build provenance unreadable") from exc
    expected = {
        "schema": "vera.gui-helper-signed-build-source/v1",
        "binarySha256": binary,
        "frozenCommit": commit,
        "sourceGraphSha256": graph,
        "sourceManifestSha256": manifest,
    }
    require(
        record == expected and queue.canonical(expected) == raw,
        "signed binary not proved built from this exact frozen source",
    )


def signed_actor(commit: str, graph: str) -> dict[str, object]:
    # Never accept caller-supplied digest or signing fields.
    require(
        EXE.is_file() and not EXE.is_symlink(), "installed signed helper not regular"
    )
    info = sh("/usr/bin/codesign", "-dv", "--verbose=4", str(EXE))
    details = info.stdout + info.stderr
    req = sh("/usr/bin/codesign", "-dr", "-", str(EXE))
    requirement = req.stdout + req.stderr
    team = re.search(r"(?m)^TeamIdentifier=([A-Z0-9]{10})$", details)
    cdhash = re.search(r"(?m)^CDHash=([0-9a-f]{40})$", details)
    designated = re.search(r"(?m)^designated => (.+)$", requirement)
    require(
        bool(team and cdhash and designated),
        "installed signed helper identity unreadable",
    )
    blob = EXE.read_bytes()
    binary = {
        "executablePath": str(EXE),
        "sha256": sha(blob),
        "codeDirectoryHash": cdhash.group(1),
        "designatedRequirement": designated.group(1),
        "teamIdentifier": team.group(1),
        "bundleIdentifier": protocol.BUNDLE_ID,
    }
    actor: dict[str, object] = {
        "schema": protocol.ACTOR_SCHEMA,
        "sourceManifestSha256": protocol.source_manifest_sha256(),
        "binary": binary,
    }
    protocol.validate_actor_pin(actor, installed=True)
    verified_build_provenance(
        commit, graph, actor["sourceManifestSha256"], binary["sha256"]
    )
    return actor


def source_graph() -> tuple[str, str]:
    root = Path(__file__).resolve().parents[2]
    commit = sh("git", "-C", str(root), "rev-parse", "HEAD").stdout.strip()
    return commit, full._frozen_source(commit)


def legacy_exact(plist_bytes: bytes, expected_exec: str, expected_spool: str) -> bool:
    """Closed legacy migration ONLY for the prior pinned helper's exact layout."""
    source = plistlib.loads(TEMPLATE.read_bytes())
    source["ProgramArguments"] = [expected_exec]
    source["EnvironmentVariables"] = {"VERA_GUI_HELPER_SPOOL": expected_spool}
    # Old template had exactly these keys and no extra shell, UI or triggers.
    return plist_bytes == plistlib.dumps(source, sort_keys=True)


def render(actor: dict[str, object], graph: str) -> bytes:
    value = plistlib.loads(TEMPLATE.read_bytes())
    require(
        value.get("Label") == LABEL
        and value.get("ProgramArguments") == ["@VERA_GUI_HELPER_EXECUTABLE@"]
        and value.get("KeepAlive") is True
        and value.get("RunAtLoad") is True
        and value.get("LimitLoadToSessionType") == "Aqua",
        "template lifecycle differs",
    )
    require(
        value.get("EnvironmentVariables")
        == {
            "VERA_GUI_HELPER_SPOOL": "@VERA_GUI_HELPER_SPOOL@",
            "VERA_GUI_HELPER_ACTOR_PIN_SHA256": "@VERA_GUI_HELPER_ACTOR_PIN_SHA256@",
            "VERA_GUI_HELPER_SOURCE_GRAPH_SHA256": (
                "@VERA_GUI_HELPER_SOURCE_GRAPH_SHA256@"
            ),
        },
        "template closed pin fields differ",
    )
    value["ProgramArguments"] = [str(EXE)]
    value["EnvironmentVariables"] = {
        "VERA_GUI_HELPER_SPOOL": str(SPOOL),
        "VERA_GUI_HELPER_ACTOR_PIN_SHA256": sha(queue.canonical(actor)),
        "VERA_GUI_HELPER_SOURCE_GRAPH_SHA256": graph,
    }
    raw = plistlib.dumps(value, sort_keys=True)
    require(plistlib.loads(raw) == value, "roundtrip helper plist failed")
    return raw


def safe_replace(path: Path, raw: bytes) -> None:
    owner_directory(path.parent)
    name = ".vera-pinned-" + uuid.uuid4().hex
    fd = os.open(
        path.parent / name, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
    )
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(path.parent / name, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    except BaseException:
        (path.parent / name).unlink(missing_ok=True)
        raise
    require(private_file(path) == raw, "written LaunchAgent plist changed")


def launch_ctl(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["/bin/launchctl", *args],
        capture_output=True,
        text=True,
        check=False,
        timeout=20,
    )


def current_service(label: str) -> subprocess.CompletedProcess[str]:
    return launch_ctl("print", label)


def verify_pin_probe(
    actor: dict[str, object],
    graph: str,
    *,
    timeout: int = 15,
    previous_pid: int | None = None,
) -> dict[str, object]:
    # Use a distinct private spool namespace that NEVER passes an AX object or
    # changes a Resolve process. The real Swift binary calls NativeRollPins.
    from vera_timeline_agent.resolve_test_bench_helper_transport import (
        SignedHelperDesktop,
    )

    desktop = SignedHelperDesktop(actor)
    # Wait for the new service's own self-status. Do NOT submit multiple probes
    # just because launchd's process is still starting up.
    ready_deadline = time.monotonic() + timeout
    pid = None
    while time.monotonic() < ready_deadline:
        try:
            observed_pid = desktop.readiness()
            if observed_pid == previous_pid:
                time.sleep(0.2)
                continue
            pid = observed_pid
            break
        except (FileNotFoundError, OSError, ValueError, RuntimeError):
            time.sleep(0.2)
    require(
        pid is not None, "new Aqua helper did not authenticate Accessibility readiness"
    )
    probe_id = "pinprobe-" + uuid.uuid4().hex
    expires = datetime.now(UTC) + timedelta(seconds=65)
    request = {
        "schema": protocol.REQUEST_SCHEMA,
        "requestId": probe_id,
        "deadlineAt": expires.isoformat(timespec="seconds").replace("+00:00", "Z"),
        "operation": "M4.edited.verify-actor-no-edit",
        "jobId": "no-edit-gate-" + uuid.uuid4().hex,
        "stageOperationId": "no-edit-pin-check-" + uuid.uuid4().hex,
        "fixtureId": protocol.FIXTURE,
        "trialId": "no-edit-trial-" + uuid.uuid4().hex,
        "resolvePid": 1,
        "windowName": "VERA no-edit helper pin verification",
        "projectUid": "no-edit-project",
        "timelineUid": "no-edit-timeline",
        "sourceGraphSha256": graph,
        "actorPin": actor,
        "pristineCaptureSha256": "0" * 64,
        "oneUseIntentSha256": uuid.uuid4().hex * 2,
        "authoritySha256": "0" * 64,
    }
    payload = queue.canonical(request)
    carrier._once(SPOOL / (probe_id + ".pin-probe-request.json"), payload)
    reply_path = SPOOL / (probe_id + ".pin-probe-reply.json")
    due = time.monotonic() + timeout
    while time.monotonic() < due:
        try:
            reply_raw = carrier._read(reply_path, 4096)
        except FileNotFoundError:
            time.sleep(0.15)
            continue
        reply = json.loads(reply_raw)
        require(
            queue.canonical(reply) == reply_raw
            and set(reply)
            == {"schema", "requestId", "requestSha256", "helperPid", "status", "detail"}
            and reply["schema"] == "vera.gui-helper-pin-probe-reply/v1"
            and reply["requestId"] == probe_id
            and reply["requestSha256"] == sha(payload)
            and reply["helperPid"] == pid
            and reply["status"] == "pin-verified",
            "running helper rejected actual Swift signed actor/source pin gate",
        )
        return {
            "requestId": probe_id,
            "requestSha256": sha(payload),
            "replySha256": sha(reply_raw),
            "helperPid": pid,
        }
    raise PinInstallRefused(
        "no-edit Swift pin probe timed out; do not create native case"
    )


def install() -> dict[str, object]:
    # The installed binary, source commit and loaded job are separately pinned.
    require(sys.version_info[:3] == (3, 12, 14), "CPython 3.12.14 required")
    require(
        SPOOL.is_dir() and SPOOL.stat().st_mode & 0o077 == 0 and not SPOOL.is_symlink(),
        "private helper spool must already exist; no implicit cleanup",
    )
    owner_directory(PLIST.parent)
    commit, graph = source_graph()
    actor = signed_actor(commit, graph)
    destination = render(actor, graph)
    old = private_file(PLIST) if PLIST.exists() or PLIST.is_symlink() else b""
    require(
        not old or old == destination or legacy_exact(old, str(EXE), str(SPOOL)),
        "existing LaunchAgent differs from exact legacy or current pinned template",
    )
    old_self = SPOOL / "self-status.json"
    old_pid: int | None = None
    try:
        old_status = json.loads(carrier._read(old_self, 4096))
        if type(old_status.get("helperPid")) is int:
            old_pid = old_status["helperPid"]
    except (FileNotFoundError, ValueError, OSError):
        pass
    domain = "gui/" + str(os.getuid())
    label = domain + "/" + LABEL
    # Install while holding the same global owner flock as the native worker.
    # No case or immutable request is rewritten, replayed, cancelled, or moved.
    with native_owner(output_lane=True):
        # Refuse helper restart while any long-lived Conductor M4 run owns its
        # carrier, including periods when it releases the SDK native lock.
        active = active_conductor_cases(Path.home() / ".local/state/vera")
        require(not active, "native campaign owns Conductor carrier lock")
        old_running = current_service(label).returncode == 0
        if old and old != destination:
            # Preserve old exact LaunchAgent bytes for offline audit first.
            backup = BASE / ("launchagent-before-pin-" + sha(old) + ".plist")
            if not backup.exists():
                fd = os.open(
                    backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600
                )
                with os.fdopen(fd, "wb") as f:
                    f.write(old)
                    f.flush()
                    os.fsync(f.fileno())
            else:
                require(private_file(backup) == old, "legacy plist evidence changed")
        safe_replace(PLIST, destination)
        if old_running:
            stop = launch_ctl("bootout", label)
            require(stop.returncode == 0, "old Aqua helper bootout failed")
            for _ in range(50):
                if current_service(label).returncode != 0:
                    break
                time.sleep(0.2)
            require(
                current_service(label).returncode != 0, "old Aqua helper still active"
            )
        start = launch_ctl("bootstrap", domain, str(PLIST))
        require(start.returncode == 0, "pinned GUI helper bootstrap failed")
        inspected = current_service(label)
        require(
            inspected.returncode == 0
            and all(
                v in inspected.stdout
                for v in [graph, sha(queue.canonical(actor)), str(SPOOL)]
            ),
            "launchctl loaded pins differ",
        )
        # Fresh process must publish its own Accessibility status; no Terminal
        # trust may substitute for this LaunchAgent's identity.
        passed = verify_pin_probe(actor, graph, timeout=25, previous_pid=old_pid)
    end_commit, end_graph = source_graph()
    require(
        (end_commit, end_graph) == (commit, graph), "source drifted while installing"
    )
    return {
        "schema": "vera.gui-helper-pinned-install/v1",
        "state": "pinned-aqua-pin-probe-pass",
        "frozenCommit": commit,
        "sourceGraphSha256": graph,
        "sourceManifestSha256": actor["sourceManifestSha256"],
        "actorPinSha256": sha(queue.canonical(actor)),
        "plistSha256": sha(destination),
        "binarySha256": actor["binary"]["sha256"],
        "probe": passed,
    }


if __name__ == "__main__":
    try:
        receipt = install()
        print(json.dumps(receipt, sort_keys=True))
    except (OSError, subprocess.SubprocessError, ValueError, RuntimeError) as exc:
        print("BLOCK:", type(exc).__name__, str(exc), file=sys.stderr)
        raise SystemExit(78) from exc
