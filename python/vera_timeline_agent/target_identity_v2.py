"""CN-207-ID1 finite identity capture. Local operator provenance, not authentication."""

from __future__ import annotations

# BEGIN IDENTITY PROVENANCE
# This stdlib-only block is also checked into the WI bootstrap. A test compares
# its AST so the bootstrap validates independently before importing VERA code.
import getpass
import hashlib
import json
import math
import os
import platform
import re
import stat
import sys
import time
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

TI_MAX_BYTES = 2 * 1024 * 1024
TI_NOTE_HASH = "e02da9eacd54fb90b7ca4ba63f1c3f72f37b997e426828ad8237d0bd1adc6006"
TI_QUOTE = f"Approve CN-207-ID1 SHA256 {TI_NOTE_HASH}, design only"
TI_AUTHORITY = "vera-native-target-identity-authority/v1"
TI_REQUEST = "vera-native-target-identity-request/v1"
TI_RESULT = "vera-native-target-identity-result/v1"
TI_RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
    "workflow_v2.py",
    "workflow_v2_launcher.py",
    "native_qualification_v2.py",
    "target_identity_v2.py",
)
TI_SOURCE_FILES = (
    *(f"python/vera_timeline_agent/{name}" for name in TI_RUNTIME_FILES),
    "python/vera_timeline_agent/workflow_v2_cli.py",
    "python/vera_timeline_agent/workflow_delivery_cli.py",
    "integrations/resolve/VERA Delivery v2.py",
    "docs/plans/issue-178-native-qualification-change-note.md",
    "docs/plans/issue-207-target-identity-handoff.md",
)
TI_NAMED = {"projectName", "timelineName"}
TI_OBSERVED = TI_NAMED | {"projectUid", "timelineUid"}
TI_BINDING = {
    "repositoryRoot",
    "repositorySourcePins",
    "releaseRoot",
    "releaseSha256",
    "installedRoot",
    "evidenceDir",
    "approvalPath",
    "approvalSha256",
    "target",
}
TI_AUTHORITY_KEYS = {
    "schemaVersion",
    "issueNumber",
    "action",
    "operator",
    "issuedAt",
    "expiresAt",
    "invocationId",
    "issuer",
    "binding",
    "confirmations",
}
TI_REQUEST_KEYS = {
    "schemaVersion",
    "issueNumber",
    "action",
    "binding",
    "authorityPath",
    "authoritySha256",
    "invocationId",
}
TI_CONFIRM = {
    "readOnly": True,
    "savedDisposableNonproduction": True,
    "externalScripting": "None",
}


def ti_require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def ti_closed(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    ti_require(type(value) is dict and set(value) == keys, f"invalid {label} fields")
    return cast(dict[str, Any], value)


def ti_text(value: Any) -> str:
    ti_require(
        type(value) is str
        and bool(value.strip())
        and len(value) <= 512
        and not any(ord(c) < 32 or 127 <= ord(c) <= 159 for c in value),
        "invalid bounded string",
    )
    return cast(str, value)


def ti_hash(value: Any) -> str:
    ti_require(
        type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "invalid SHA256",
    )
    return cast(str, value)


def ti_id(value: Any) -> str:
    value = ti_text(value)
    ti_require(str(uuid.UUID(value)) == value, "noncanonical invocation UUID")
    return cast(str, value)


def ti_time(value: Any) -> datetime:
    parsed = datetime.fromisoformat(ti_text(value))
    ti_require(parsed.utcoffset() == timedelta(0), "time must be timezone-aware UTC")
    return parsed


def ti_window(issued: str, expires: str, now: datetime) -> None:
    start, end = ti_time(issued), ti_time(expires)
    ti_require(end - start == timedelta(seconds=1800), "invalid 30-minute window")
    ti_require(start <= now < end, "future or expired authority")


class TIClock:
    def __init__(self, wall: datetime, monotonic: float) -> None:
        ti_require(
            type(monotonic) is float and math.isfinite(monotonic) and monotonic >= 0,
            "invalid monotonic clock provenance",
        )
        self.wall = wall
        self.monotonic = monotonic

    def check(
        self, wall: datetime, monotonic: float, upper: float | None = None
    ) -> None:
        ti_require(monotonic >= self.monotonic and wall >= self.wall, "clock rollback")
        # XNU MAXFREQ=500000 ns/s: allow up to 500 ppm calendar rate skew.
        # The 2 us floor covers two datetime samples, not a step tolerance.
        # Larger slews (including adjtime's 5000 ppm mode) are clock uncertainty.
        # Strict negative elapsed intervals refuse; smaller between-sample steps
        # can be indistinguishable from supported rate/sampling uncertainty.
        elapsed = monotonic - self.monotonic
        wall_elapsed = (wall - self.wall).total_seconds()
        ti_require(
            wall_elapsed + 0.000002 + elapsed * 0.0005 >= elapsed,
            f"wall/monotonic clock rollback (wall={wall_elapsed}, mono={elapsed})",
        )
        self.wall, self.monotonic = wall, monotonic if upper is None else upper


def ti_clock_check(clock: TIClock) -> None:
    # Bracket the wall sample to compare a lower bound on elapsed monotonic time.
    # Scheduler pauses between different clock calls cannot mimic a rollback.
    before = time.monotonic()
    wall = datetime.now(UTC)
    after = time.monotonic()
    clock.check(wall, before, after)


def ti_loaded_runtime() -> bool:
    return any(
        n == "vera_timeline_agent" or n.startswith("vera_timeline_agent.")
        for n in sys.modules
    )


def ti_issuer(pins: dict[str, str]) -> dict[str, str]:
    return {
        "implementation": platform.python_implementation(),
        "pythonVersion": platform.python_version(),
        "hostUser": getpass.getuser(),
        "toolSha256": pins["python/vera_timeline_agent/workflow_v2_cli.py"],
    }


def ti_object(payload: bytes) -> dict[str, Any]:
    ti_require(len(payload) <= TI_MAX_BYTES, "record exceeds bound")

    def pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in entries:
            ti_require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON scalar: {value}")

    try:
        value = json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)
        ti_require(type(value) is dict, "record must be an object")
        json.dumps(value, allow_nan=False)
        return cast(dict[str, Any], value)
    except (UnicodeError, RecursionError, OverflowError) as error:
        raise ValueError("invalid bounded JSON") from error


def ti_path(value: Any) -> Path:
    path = Path(ti_text(value))
    ti_require(
        path.is_absolute() and str(path) == os.path.abspath(path),
        "path must be canonical absolute",
    )
    ti_require(
        not any(p.is_symlink() for p in (path, *path.parents)), "symbolic link ancestry"
    )
    return path


def ti_ancestry(path: Path) -> list[tuple[str, int, int]]:
    ti_path(str(path))
    return [
        (str(p), p.lstat().st_dev, p.lstat().st_ino)
        for p in (path, *path.parents)
        if p.exists()
    ]


def ti_read(path: Path) -> bytes:
    ancestry = ti_ancestry(path)
    try:
        before = path.lstat()
        fd = os.open(
            path,
            os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0),
        )
        try:
            opened = os.fstat(fd)
            ti_require(
                stat.S_ISREG(opened.st_mode)
                and opened.st_nlink == 1
                and opened.st_size <= TI_MAX_BYTES
                and (before.st_dev, before.st_ino) == (opened.st_dev, opened.st_ino),
                "not a bounded single-link regular input",
            )
            chunks, total = [], 0
            while chunk := os.read(fd, 65536):
                total += len(chunk)
                ti_require(total <= TI_MAX_BYTES, "input grew beyond bound")
                chunks.append(chunk)
            after = os.fstat(fd)
            ti_require(
                (
                    opened.st_dev,
                    opened.st_ino,
                    opened.st_size,
                    opened.st_mtime_ns,
                    opened.st_ctime_ns,
                )
                == (
                    after.st_dev,
                    after.st_ino,
                    after.st_size,
                    after.st_mtime_ns,
                    after.st_ctime_ns,
                )
                and total == opened.st_size
                and ti_ancestry(path) == ancestry,
                "input changed during read",
            )
            return b"".join(chunks)
        finally:
            os.close(fd)
    except OSError as error:
        raise ValueError("input unavailable") from error


def ti_digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def ti_within(path: Path, root: Path) -> bool:
    if path.is_relative_to(root):
        return True
    if not root.exists():
        return False
    identity = (root.stat().st_dev, root.stat().st_ino)
    return any((dev, ino) == identity for _, dev, ino in ti_ancestry(path))


def ti_separate(output: Path, protected: list[Path]) -> None:
    ti_path(str(output))
    for item in protected:
        ti_path(str(item))
        ti_require(
            not ti_within(output, item) and not ti_within(item, output),
            "output overlaps protected input",
        )


def ti_private(root: Path) -> None:
    ti_path(str(root))
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    ti_require(
        stat.S_ISDIR(info.st_mode)
        and stat.S_IMODE(info.st_mode) == 0o700
        and info.st_uid == os.getuid(),
        "root must be private 0700",
    )


def ti_publish(
    path: Path, value: dict[str, Any], protected: list[Path] | None = None
) -> Path:
    payload = (
        json.dumps(value, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode()
    ti_require(len(payload) <= TI_MAX_BYTES, "output exceeds bound")
    ti_separate(path, protected or [])
    ti_private(path.parent)
    ancestry = ti_ancestry(path.parent)
    fd_dir = os.open(
        path.parent, os.O_RDONLY | os.O_DIRECTORY | getattr(os, "O_NOFOLLOW", 0)
    )
    try:
        opened = os.fstat(fd_dir)
        ti_require(
            (opened.st_dev, opened.st_ino) == (ancestry[0][1], ancestry[0][2])
            and ti_ancestry(path.parent) == ancestry,
            "output ancestry changed",
        )
        ti_separate(path, protected or [])
        try:
            fd = os.open(
                path.name,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
                0o400,
                dir_fd=fd_dir,
            )
        except OSError as error:
            raise ValueError("immutable output collision/unavailable") from error
        try:
            remaining = memoryview(payload)
            while remaining:
                written = os.write(fd, remaining)
                ti_require(written > 0, "uncertain publication")
                remaining = remaining[written:]
            os.fsync(fd)
            os.fchmod(fd, 0o400)
        finally:
            os.close(fd)
        os.fsync(fd_dir)
        ti_require(
            ti_ancestry(path.parent) == ancestry and ti_read(path) == payload,
            "uncertain publication/ancestry",
        )
        ti_separate(path, protected or [])
    finally:
        os.close(fd_dir)
    return path


def ti_names(value: Any, observed: bool = False) -> dict[str, Any]:
    result = ti_closed(value, TI_OBSERVED if observed else TI_NAMED, "target")
    for item in result.values():
        ti_text(item)
    return result


def ti_source_pins(repository: Path) -> dict[str, str]:
    ti_path(str(repository))
    pins = {name: ti_digest(ti_read(repository / name)) for name in TI_SOURCE_FILES}
    ti_require(pins[TI_SOURCE_FILES[-1]] == TI_NOTE_HASH, "identity note drift")
    ti_require(
        pins[TI_SOURCE_FILES[-2]]
        == "c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740",
        "capability note drift",
    )
    return pins


def ti_release(root: Path, binding: dict[str, Any], installed: bool) -> dict[str, str]:
    ti_path(str(root))
    payload = ti_read(root / "vera-delivery-v2/release.json")
    ti_require(ti_digest(payload) == ti_hash(binding["releaseSha256"]), "release drift")
    manifest = ti_closed(
        ti_object(payload),
        {"schemaVersion", "deliveryVersion", "sourcePins", "files"},
        "release",
    )
    ti_require(
        manifest["schemaVersion"] == "vera-injected-delivery-release/v2"
        and manifest["deliveryVersion"] == "2"
        and manifest["sourcePins"]
        == {
            "issue34": "2586dded4d3566e944d7938604b20bded6fc36fb",
            "issue107": "c9614eaf7bf7aa88f4cf33e77180ff5a393377e4",
            "issue147": "75029de57baa594d3dfc7f509a09cfc21943e088",
        },
        "unsupported identity release",
    )
    pins = binding["repositorySourcePins"]
    expected = {
        f"vera-delivery-v2/python/vera_timeline_agent/{n}": pins[
            f"python/vera_timeline_agent/{n}"
        ]
        for n in TI_RUNTIME_FILES
    }
    expected["VERA Delivery v2.py"] = pins["integrations/resolve/VERA Delivery v2.py"]
    entries = manifest["files"]
    ti_require(
        type(entries) is list and len(entries) == len(expected),
        "incomplete release inventory",
    )
    seen: set[str] = set()
    for raw in entries:
        entry = ti_closed(raw, {"path", "sha256", "sizeBytes"}, "release entry")
        name = ti_text(entry["path"])
        ti_require(name in expected and name not in seen, "undeclared/duplicate source")
        data = ti_read(root / name)
        ti_require(
            type(entry["sizeBytes"]) is int
            and len(data) == entry["sizeBytes"]
            and ti_digest(data) == ti_hash(entry["sha256"]) == expected[name],
            "release source drift",
        )
        seen.add(name)
    files = set(expected) | {"vera-delivery-v2/release.json"}
    if installed:
        files.add("vera-delivery-v2/request.json")
    directories = {
        p.as_posix() for name in expected for p in Path(name).parents if p != Path(".")
    }
    # Resolve installs into a shared plugin directory; own only the declared
    # root launcher plus the v2 subtree. Never inspect another plugin's contents.
    inventory_root = root / "vera-delivery-v2" if installed else root
    ti_path(str(inventory_root))
    for item in inventory_root.rglob("*"):
        ti_path(str(item))
        if item.name == ".DS_Store" and item.is_file():
            ti_read(item)  # Finder tolerance applies only to safe regular files.
            continue
        if item.is_file():
            ti_require(
                item.relative_to(root).as_posix() in files, "undeclared release file"
            )
        else:
            ti_require(
                item.is_dir() and item.relative_to(root).as_posix() in directories,
                "undeclared release directory/type",
            )
    return expected


def ti_approval(path: Path, expected: str) -> None:
    payload = ti_read(path)
    ti_require(ti_digest(payload) == ti_hash(expected), "identity approval drift")
    value = ti_closed(
        ti_object(payload),
        {"changeNote", "producerQuote", "noteSha256", "recordedAt"},
        "identity approval",
    )
    ti_require(
        value["changeNote"] == "CN-207-ID1"
        and value["producerQuote"] == TI_QUOTE
        and value["noteSha256"] == TI_NOTE_HASH,
        "exact identity approval required",
    )
    ti_time(value["recordedAt"])


def ti_protected(
    binding: dict[str, Any], extra: list[Path] | None = None
) -> list[Path]:
    return [
        ti_path(binding[k])
        for k in ("repositoryRoot", "releaseRoot", "installedRoot", "approvalPath")
    ] + (extra or [])


def ti_binding(value: Any, *, check_installed: bool = True) -> dict[str, Any]:
    binding = ti_closed(value, TI_BINDING, "identity binding")
    ti_names(binding["target"])
    repository = ti_path(binding["repositoryRoot"])
    ti_require(
        binding["repositorySourcePins"] == ti_source_pins(repository), "source drift"
    )
    ti_approval(ti_path(binding["approvalPath"]), binding["approvalSha256"])
    ti_release(ti_path(binding["releaseRoot"]), binding, False)
    if check_installed:
        ti_release(ti_path(binding["installedRoot"]), binding, True)
    evidence = ti_path(binding["evidenceDir"])
    ti_separate(evidence, ti_protected(binding))
    return binding


def ti_authority(
    path: Path, *, check_installed: bool = True, at: datetime | None = None
) -> tuple[dict[str, Any], str]:
    payload = ti_read(path)
    value = ti_closed(ti_object(payload), TI_AUTHORITY_KEYS, "identity authority")
    ti_require(
        value["schemaVersion"] == TI_AUTHORITY
        and type(value["issueNumber"]) is int
        and value["issueNumber"] == 208
        and value["action"] == "target_identity_handoff",
        "unsupported identity authority",
    )
    ti_closed(value["confirmations"], set(TI_CONFIRM), "confirmations")
    ti_require(
        value["confirmations"] == TI_CONFIRM
        and value["confirmations"]["readOnly"] is True
        and value["confirmations"]["savedDisposableNonproduction"] is True,
        "explicit operator confirmations required",
    )
    ti_text(value["operator"])
    ti_id(value["invocationId"])
    ti_window(
        value["issuedAt"], value["expiresAt"], datetime.now(UTC) if at is None else at
    )
    binding = ti_binding(value["binding"], check_installed=check_installed)
    issuer = ti_closed(
        value["issuer"],
        {"implementation", "pythonVersion", "hostUser", "toolSha256"},
        "issuer",
    )
    ti_require(
        issuer["implementation"] == "CPython"
        and issuer["pythonVersion"] == "3.12.14"
        and issuer["toolSha256"]
        == binding["repositorySourcePins"][
            "python/vera_timeline_agent/workflow_v2_cli.py"
        ],
        "locked issuer required",
    )
    ti_text(issuer["hostUser"])
    ti_separate(path, [*ti_protected(binding), ti_path(binding["evidenceDir"])])
    ti_require(
        stat.S_IMODE(path.stat().st_mode) == 0o400, "authority must be immutable"
    )
    return value, ti_digest(payload)


def ti_request(
    path: Path,
    expected: str,
    *,
    check_installed: bool = True,
    at: datetime | None = None,
) -> dict[str, Any]:
    payload = ti_read(path)
    ti_require(ti_digest(payload) == ti_hash(expected), "identity request drift")
    value = ti_closed(ti_object(payload), TI_REQUEST_KEYS, "identity request")
    ti_require(
        value["schemaVersion"] == TI_REQUEST
        and type(value["issueNumber"]) is int
        and value["issueNumber"] == 208
        and value["action"] == "target_identity_handoff",
        "unsupported identity request",
    )
    authority_path = ti_path(value["authorityPath"])
    authority, digest = ti_authority(
        authority_path, check_installed=check_installed, at=at
    )
    ti_require(
        digest == ti_hash(value["authoritySha256"])
        and value["binding"] == authority["binding"]
        and ti_id(value["invocationId"]) == authority["invocationId"],
        "identity authority/request mismatch",
    )
    binding = value["binding"]
    protected = [*ti_protected(binding), authority_path]
    evidence = ti_path(binding["evidenceDir"])
    ti_separate(evidence, [*protected, path])
    ti_private(evidence)
    installed_slot = ti_path(binding["installedRoot"]) / "vera-delivery-v2/request.json"
    if path != installed_slot:
        ti_separate(path, [*protected, evidence])
    ti_require(stat.S_IMODE(path.stat().st_mode) == 0o400, "request must be immutable")
    prepared = ti_closed(
        ti_object(ti_read(evidence / f"prepared-{value['invocationId']}.json")),
        {"requestPath", "requestSha256", "invocationId"},
        "prepared lineage",
    )
    host = ti_path(prepared["requestPath"])
    ti_separate(host, [*protected, evidence])
    ti_require(
        prepared["invocationId"] == value["invocationId"]
        and prepared["requestSha256"] == expected
        and ti_read(host) == payload,
        "host/installed request lineage mismatch",
    )
    return value


def ti_start_value(request: dict[str, Any], digest: str) -> dict[str, Any]:
    return {
        "schemaVersion": "vera-native-target-identity-bootstrap/v1",
        "invocationId": request["invocationId"],
        "requestSha256": digest,
        "authoritySha256": request["authoritySha256"],
        "binding": request["binding"],
        "startedAt": datetime.now(UTC).isoformat(),
        "monotonicStarted": time.monotonic(),
        "qualified": False,
    }


def ti_reserve(request_path: Path, expected: str) -> Path:
    request = ti_request(request_path, expected)
    binding = request["binding"]
    path = (
        ti_path(binding["evidenceDir"])
        / f"bootstrap-started-{request['invocationId']}.json"
    )
    return ti_publish(
        path,
        ti_start_value(request, expected),
        ti_protected(binding, [request_path, ti_path(request["authorityPath"])]),
    )


def ti_started(request: dict[str, Any], expected: str) -> dict[str, Any]:
    path = (
        ti_path(request["binding"]["evidenceDir"])
        / f"bootstrap-started-{request['invocationId']}.json"
    )
    value = ti_closed(
        ti_object(ti_read(path)),
        {
            "schemaVersion",
            "invocationId",
            "requestSha256",
            "authoritySha256",
            "binding",
            "startedAt",
            "monotonicStarted",
            "qualified",
        },
        "bootstrap lineage",
    )
    comparison = ti_start_value(request, expected)
    comparison["startedAt"] = value["startedAt"]
    comparison["monotonicStarted"] = value["monotonicStarted"]
    ti_require(
        value == comparison and value["qualified"] is False,
        "bootstrap lineage mismatch",
    )
    ti_require(ti_time(value["startedAt"]) <= datetime.now(UTC), "future bootstrap")
    ti_clock_check(TIClock(ti_time(value["startedAt"]), value["monotonicStarted"]))
    return value


TI_RESULT_KEYS = {
    "schemaVersion",
    "issueNumber",
    "action",
    "invocationId",
    "status",
    "qualified",
    "verified",
    "futureEffectsAuthorized",
    "startedAt",
    "finishedAt",
    "requestSha256",
    "authoritySha256",
    "binding",
    "runtime",
    "reads",
    "target",
    "reason",
}
TI_CAP_AUTHORITY = "vera-native-qualification-authority/v2"
TI_CAP_REQUEST = "vera-native-qualification-request/v2"
TI_CAP_BINDING = TI_BINDING - {"installedRoot"}
TI_RECEIPT_KEYS = {
    "resultPath",
    "resultSha256",
    "invocationId",
    "identityApprovalPath",
    "identityApprovalSha256",
    "confirmedAt",
}


def ti_immutable(path: Path) -> bytes:
    payload = ti_read(path)
    ti_require(stat.S_IMODE(path.stat().st_mode) == 0o400, "lineage must be immutable")
    return payload


def ti_receipt(path: Path, expected: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate original private completion lineage; hashes alone are insufficient."""
    payload = ti_immutable(path)
    ti_require(ti_digest(payload) == ti_hash(expected), "identity result hash drift")
    result = ti_closed(ti_object(payload), TI_RESULT_KEYS, "identity result")
    ti_require(
        result["schemaVersion"] == TI_RESULT
        and type(result["issueNumber"]) is int
        and result["issueNumber"] == 208
        and result["action"] == "target_identity_handoff"
        and result["status"] == "identity_observed"
        and result["reason"] is None
        and all(
            result[k] is False
            for k in ("qualified", "verified", "futureEffectsAuthorized")
        ),
        "only successful unqualified identity receipts may be consumed",
    )
    invocation = ti_id(result["invocationId"])
    binding = ti_binding(result["binding"])
    evidence = ti_path(binding["evidenceDir"])
    ti_private(evidence)
    ti_require(
        path == evidence / f"result-{invocation}.json", "copied/foreign result lineage"
    )
    prepared = ti_closed(
        ti_object(ti_immutable(evidence / f"prepared-{invocation}.json")),
        {"requestPath", "requestSha256", "invocationId"},
        "prepared lineage",
    )
    begin, finish = ti_time(result["startedAt"]), ti_time(result["finishedAt"])
    ti_require(begin <= finish <= datetime.now(UTC), "invalid result chronology")
    request = ti_request(
        ti_path(prepared["requestPath"]), result["requestSha256"], at=finish
    )
    ti_require(
        request["invocationId"] == invocation
        and request["binding"] == binding
        and request["authoritySha256"] == result["authoritySha256"],
        "result/request lineage mismatch",
    )
    start_path = evidence / f"bootstrap-started-{invocation}.json"
    started = ti_started(request, result["requestSha256"])
    start_hash = ti_digest(ti_immutable(start_path))
    controller_path = evidence / f"controller-started-{invocation}.json"
    controller = ti_closed(
        ti_object(ti_immutable(controller_path)),
        {"invocationId", "bootstrapSha256"},
        "controller lineage",
    )
    ti_require(
        controller == {"invocationId": invocation, "bootstrapSha256": start_hash},
        "controller lineage mismatch",
    )
    hashes = ti_closed(
        ti_object(ti_immutable(evidence / f"hashes-{invocation}.json")),
        {
            "invocationId",
            "resultPath",
            "resultSha256",
            "bootstrapSha256",
            "controllerSha256",
            "requestSha256",
            "authoritySha256",
        },
        "result hashes",
    )
    ti_require(
        hashes
        == {
            "invocationId": invocation,
            "resultPath": str(path),
            "resultSha256": expected,
            "bootstrapSha256": start_hash,
            "controllerSha256": ti_digest(ti_immutable(controller_path)),
            "requestSha256": result["requestSha256"],
            "authoritySha256": result["authoritySha256"],
        },
        "completion hash lineage mismatch",
    )
    begin, finish = ti_time(result["startedAt"]), ti_time(result["finishedAt"])
    ti_require(
        result["startedAt"] == started["startedAt"]
        and begin <= finish <= datetime.now(UTC)
        and datetime.now(UTC) < finish + timedelta(seconds=1800),
        "stale identity result",
    )
    authority, _ = ti_authority(ti_path(request["authorityPath"]), at=finish)
    ti_require(
        ti_time(authority["issuedAt"]) <= begin
        and finish < ti_time(authority["expiresAt"]),
        "result outside authority window",
    )
    reads = result["reads"]
    ti_require(
        type(reads) is list and len(reads) == 2, "two complete identity reads required"
    )
    previous = begin
    for raw in reads:
        read = ti_closed(raw, {"readAt", "target"}, "complete target read")
        instant = ti_time(read["readAt"])
        ti_require(previous <= instant <= finish, "invalid read chronology")
        previous = instant
        ti_names(read["target"], True)
    target = ti_names(result["target"], True)
    ti_require(
        reads[0]["target"] == reads[1]["target"] == target
        and {k: target[k] for k in TI_NAMED} == binding["target"],
        "identity read pair drift",
    )
    runtime = ti_closed(
        result["runtime"],
        {
            "injectedObjectAvailable",
            "implementation",
            "pythonVersion",
            "platform",
            "product",
            "version",
            "installedRoot",
            "installedSourcePins",
        },
        "runtime",
    )
    version = runtime["version"]
    ti_require(
        runtime["injectedObjectAvailable"] is True
        and runtime["product"] == "DaVinci Resolve Studio"
        and type(version) is list
        and len(version) == 5
        and all(type(n) is int for n in version[:4])
        and version == [21, 1, 1, 10, ""]
        and runtime["installedRoot"] == binding["installedRoot"]
        and runtime["installedSourcePins"]
        == ti_release(ti_path(binding["installedRoot"]), binding, True),
        "runtime lineage drift",
    )
    for key in ("implementation", "pythonVersion", "platform"):
        ti_text(runtime[key])
    return result, request


def ti_cap_approval(path: Path, expected: str) -> None:
    payload = ti_read(path)
    ti_require(ti_digest(payload) == ti_hash(expected), "capability approval drift")
    approved = ti_closed(
        ti_object(payload),
        {
            "changeNote",
            "producerQuote",
            "noteSha256",
            "scope",
            "recordedAt",
            "ordinaryGuardsRetained",
        },
        "capability approval",
    )
    ti_require(
        approved["changeNote"] == "CN-178-Q1"
        and approved["producerQuote"] == "Approve staged CN-178-Q1"
        and approved["noteSha256"]
        == "c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740"
        and approved["scope"]
        == (
            "separateinstalledqualificationroute "
            "STAGEDread-onlycapabilitypreflightfirst; "
            "nocreation/renderinguntilactualcapability/controls/formatreport"
        )
        and approved["ordinaryGuardsRetained"] is True,
        "staged capability approval required",
    )
    ti_time(approved["recordedAt"])


def ti_consumption(authority: dict[str, Any], authority_path: Path) -> dict[str, Any]:
    receipt = authority["identityReceipt"]
    return {
        "schemaVersion": "vera-native-target-identity-consumption/v1",
        "resultPath": receipt["resultPath"],
        "resultSha256": receipt["resultSha256"],
        "identityInvocationId": receipt["invocationId"],
        "capabilityInvocationId": authority["invocationId"],
        "authorityPath": str(authority_path),
        "issuedAt": authority["issuedAt"],
        "expiresAt": authority["expiresAt"],
        "confirmedAt": receipt["confirmedAt"],
    }


def ti_cap_authority(path: Path) -> tuple[dict[str, Any], str]:
    payload = ti_immutable(path)
    value = ti_closed(
        ti_object(payload),
        TI_AUTHORITY_KEYS | {"identityReceipt"},
        "receipt-backed capability authority",
    )
    ti_require(
        value["schemaVersion"] == TI_CAP_AUTHORITY
        and type(value["issueNumber"]) is int
        and value["issueNumber"] == 204
        and value["action"] == "capability_preflight",
        "unsupported receipt-backed authority",
    )
    ti_closed(value["confirmations"], set(TI_CONFIRM), "capability confirmations")
    ti_require(
        value["confirmations"] == TI_CONFIRM
        and value["confirmations"]["readOnly"] is True
        and value["confirmations"]["savedDisposableNonproduction"] is True,
        "fresh capability operator confirmation required",
    )
    ti_text(value["operator"])
    ti_id(value["invocationId"])
    receipt = ti_closed(
        value["identityReceipt"], TI_RECEIPT_KEYS, "identity receipt reference"
    )
    result, request = ti_receipt(
        ti_path(receipt["resultPath"]), receipt["resultSha256"]
    )
    source = result["binding"]
    ti_require(
        receipt["invocationId"] == result["invocationId"]
        and receipt["identityApprovalPath"] == source["approvalPath"]
        and receipt["identityApprovalSha256"] == source["approvalSha256"],
        "identity approval/invocation drift",
    )
    issue, expiry, confirmed = (
        ti_time(value["issuedAt"]),
        ti_time(value["expiresAt"]),
        ti_time(receipt["confirmedAt"]),
    )
    finish = ti_time(result["finishedAt"])
    ti_require(
        finish <= confirmed <= issue <= datetime.now(UTC) < expiry
        and expiry
        == min(issue + timedelta(seconds=1800), finish + timedelta(seconds=1800)),
        "stale receipt-backed authority/confirmation",
    )
    binding = ti_closed(value["binding"], TI_CAP_BINDING, "capability binding")
    ti_names(binding["target"], True)
    ti_require(
        binding["target"] == result["target"]
        and all(
            binding[k] == source[k]
            for k in (
                "repositoryRoot",
                "repositorySourcePins",
                "releaseRoot",
                "releaseSha256",
            )
        ),
        "capability source/release/target drift",
    )
    ti_cap_approval(ti_path(binding["approvalPath"]), binding["approvalSha256"])
    issuer = ti_closed(
        value["issuer"],
        {"implementation", "pythonVersion", "hostUser", "toolSha256"},
        "issuer",
    )
    ti_require(
        issuer["implementation"] == "CPython"
        and issuer["pythonVersion"] == "3.12.14"
        and issuer["toolSha256"]
        == source["repositorySourcePins"][
            "python/vera_timeline_agent/workflow_v2_cli.py"
        ],
        "locked capability issuer required",
    )
    ti_text(issuer["hostUser"])
    protected = ti_protected(
        source, [ti_path(request["authorityPath"]), ti_path(binding["approvalPath"])]
    )
    evidence = ti_path(binding["evidenceDir"])
    ti_separate(evidence, [*protected, path, ti_path(source["evidenceDir"])])
    ti_separate(path, [*protected, evidence, ti_path(source["evidenceDir"])])
    marker = ti_path(source["evidenceDir"]) / f"consumed-{receipt['resultSha256']}.json"
    ti_require(
        ti_object(ti_immutable(marker)) == ti_consumption(value, path),
        "consumption lineage mismatch",
    )
    return value, ti_digest(payload)


def ti_cap_request(path: Path, expected: str) -> dict[str, Any]:
    payload = ti_immutable(path)
    ti_require(ti_digest(payload) == ti_hash(expected), "capability request drift")
    value = ti_closed(
        ti_object(payload), TI_REQUEST_KEYS - {"invocationId"}, "capability request"
    )
    ti_require(
        value["schemaVersion"] == TI_CAP_REQUEST
        and type(value["issueNumber"]) is int
        and value["issueNumber"] == 204
        and value["action"] == "capability_preflight",
        "unsupported capability request v2",
    )
    authority_path = ti_path(value["authorityPath"])
    authority, digest = ti_cap_authority(authority_path)
    ti_require(
        digest == value["authoritySha256"] and value["binding"] == authority["binding"],
        "capability authority/request mismatch",
    )
    result, identity_request = ti_receipt(
        ti_path(authority["identityReceipt"]["resultPath"]),
        authority["identityReceipt"]["resultSha256"],
    )
    source = result["binding"]
    protected = ti_protected(
        source,
        [
            authority_path,
            ti_path(value["binding"]["approvalPath"]),
            ti_path(identity_request["authorityPath"]),
        ],
    )
    evidence = ti_path(value["binding"]["evidenceDir"])
    ti_separate(evidence, [*protected, path, ti_path(source["evidenceDir"])])
    installed = ti_path(source["installedRoot"]) / "vera-delivery-v2/request.json"
    if path != installed:
        ti_separate(path, [*protected, evidence, ti_path(source["evidenceDir"])])
    ti_private(evidence)
    prepared = ti_closed(
        ti_object(
            ti_immutable(evidence / f"prepared-{authority['invocationId']}.json")
        ),
        {"requestPath", "requestSha256", "invocationId"},
        "capability preparation",
    )
    host = ti_path(prepared["requestPath"])
    ti_separate(host, [*protected, evidence, ti_path(source["evidenceDir"])])
    ti_require(
        prepared["requestSha256"] == expected
        and prepared["invocationId"] == authority["invocationId"]
        and ti_immutable(host) == payload,
        "capability prepared/installed lineage drift",
    )
    return value


def ti_cap_start(request: dict[str, Any], digest: str) -> dict[str, Any]:
    authority, _ = ti_cap_authority(ti_path(request["authorityPath"]))
    return {
        "schemaVersion": "vera-native-qualification-bootstrap/v2",
        "invocationId": authority["invocationId"],
        "requestSha256": digest,
        "authoritySha256": request["authoritySha256"],
        "binding": request["binding"],
        "identityReceipt": authority["identityReceipt"],
        "qualified": False,
        "startedAt": datetime.now(UTC).isoformat(),
        "monotonicStarted": time.monotonic(),
    }


def ti_cap_reserve(request_path: Path, expected: str) -> Path:
    request = ti_cap_request(request_path, expected)
    value = ti_cap_start(request, expected)
    authority, _ = ti_cap_authority(ti_path(request["authorityPath"]))
    result, _ = ti_receipt(
        ti_path(authority["identityReceipt"]["resultPath"]),
        authority["identityReceipt"]["resultSha256"],
    )
    evidence = ti_path(request["binding"]["evidenceDir"])
    return ti_publish(
        evidence / f"bootstrap-started-{value['invocationId']}.json",
        value,
        ti_protected(
            result["binding"], [request_path, ti_path(request["authorityPath"])]
        ),
    )


def ti_cap_started(request: dict[str, Any], expected: str) -> dict[str, Any]:
    value = ti_cap_start(request, expected)
    evidence = ti_path(request["binding"]["evidenceDir"])
    marker = evidence / f"bootstrap-started-{value['invocationId']}.json"
    retained = ti_closed(
        ti_object(ti_immutable(marker)), set(value), "capability bootstrap"
    )
    value["startedAt"] = retained["startedAt"]
    value["monotonicStarted"] = retained["monotonicStarted"]
    ti_require(retained == value, "capability bootstrap lineage mismatch")
    ti_clock_check(TIClock(ti_time(value["startedAt"]), value["monotonicStarted"]))
    return retained


# END IDENTITY PROVENANCE


def create_identity_authority(
    output: Path,
    *,
    release_root: Path,
    installed_root: Path,
    repository_root: Path,
    evidence_dir: Path,
    approval_path: Path,
    target: dict[str, Any],
    operator: str,
    confirm_saved_disposable: bool,
    confirm_read_only: bool,
    external_scripting_none: bool,
) -> Path:
    """Only the operator invokes this; preparing a request cannot issue authority."""
    ti_require(
        confirm_saved_disposable is True
        and confirm_read_only is True
        and external_scripting_none is True,
        "all operator confirmations required",
    )
    ti_require(
        platform.python_implementation() == "CPython"
        and platform.python_version() == "3.12.14",
        "locked host required",
    )
    pins = ti_source_pins(repository_root)
    binding = ti_binding(
        {
            "repositoryRoot": str(repository_root),
            "repositorySourcePins": pins,
            "releaseRoot": str(release_root),
            "installedRoot": str(installed_root),
            "releaseSha256": ti_digest(
                ti_read(release_root / "vera-delivery-v2/release.json")
            ),
            "evidenceDir": str(evidence_dir),
            "approvalPath": str(approval_path),
            "approvalSha256": ti_digest(ti_read(approval_path)),
            "target": ti_names(target),
        },
        check_installed=False,
    )
    ti_separate(output, [*ti_protected(binding), evidence_dir])
    issued = datetime.now(UTC)
    value = {
        "schemaVersion": TI_AUTHORITY,
        "issueNumber": 208,
        "action": "target_identity_handoff",
        "operator": ti_text(operator),
        "issuedAt": issued.isoformat(),
        "expiresAt": (issued + timedelta(seconds=1800)).isoformat(),
        "invocationId": str(uuid.uuid4()),
        "binding": binding,
        "confirmations": dict(TI_CONFIRM),
        "issuer": {
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "hostUser": getpass.getuser(),
            "toolSha256": pins["python/vera_timeline_agent/workflow_v2_cli.py"],
        },
    }
    return ti_publish(output, value, [*ti_protected(binding), evidence_dir])


def prepare_identity_request(output: Path, *, authority_path: Path) -> Path:
    authority, digest = ti_authority(authority_path, check_installed=False)
    binding = authority["binding"]
    evidence = ti_path(binding["evidenceDir"])
    protected = ti_protected(binding, [authority_path])
    ti_separate(output, [*protected, evidence])
    ti_separate(evidence, [*protected, output])
    request = {
        "schemaVersion": TI_REQUEST,
        "issueNumber": 208,
        "action": "target_identity_handoff",
        "binding": binding,
        "authorityPath": str(authority_path),
        "authoritySha256": digest,
        "invocationId": authority["invocationId"],
    }
    ti_publish(output, request, [*protected, evidence])
    ti_publish(
        evidence / f"prepared-{authority['invocationId']}.json",
        {
            "requestPath": str(output),
            "requestSha256": ti_digest(ti_read(output)),
            "invocationId": authority["invocationId"],
        },
        [*protected, output],
    )
    return output


def create_capability_authority_from_identity(
    output: Path,
    *,
    result_path: Path,
    result_sha256: str,
    approval_path: Path,
    evidence_dir: Path,
    operator: str,
    acknowledge_result_sha256: str,
    confirm_displayed_target: bool,
    confirm_saved_disposable: bool,
    confirm_read_only: bool,
    external_scripting_none: bool,
) -> Path:
    """Separate attended operator decision using the displayed receipt target."""
    ti_require(
        confirm_displayed_target is True
        and confirm_saved_disposable is True
        and confirm_read_only is True
        and external_scripting_none is True,
        "fresh displayed target/operator confirmations required",
    )
    ti_require(
        platform.python_implementation() == "CPython"
        and platform.python_version() == "3.12.14",
        "locked host required",
    )
    result, request = ti_receipt(result_path, result_sha256)
    ti_require(
        ti_hash(acknowledge_result_sha256) == result_sha256,
        "operator acknowledgement does not match result hash",
    )
    source = result["binding"]
    binding = {
        k: source[k]
        for k in (
            "repositoryRoot",
            "repositorySourcePins",
            "releaseRoot",
            "releaseSha256",
        )
    }
    binding.update(
        target=result["target"],
        approvalPath=str(approval_path),
        approvalSha256=ti_digest(ti_read(approval_path)),
        evidenceDir=str(evidence_dir),
    )
    ti_cap_approval(approval_path, binding["approvalSha256"])
    original = ti_path(source["evidenceDir"])
    protected = ti_protected(source, [ti_path(request["authorityPath"]), approval_path])
    ti_separate(evidence_dir, [*protected, original, output])
    ti_separate(output, [*protected, original, evidence_dir])
    confirmed = datetime.now(UTC)
    issued = datetime.now(UTC)
    expiry = min(
        issued + timedelta(seconds=1800),
        ti_time(result["finishedAt"]) + timedelta(seconds=1800),
    )
    ti_require(issued < expiry, "identity expired before confirmation")
    value = {
        "schemaVersion": TI_CAP_AUTHORITY,
        "issueNumber": 204,
        "action": "capability_preflight",
        "operator": ti_text(operator),
        "issuedAt": issued.isoformat(),
        "expiresAt": expiry.isoformat(),
        "invocationId": str(uuid.uuid4()),
        "issuer": ti_issuer(source["repositorySourcePins"]),
        "binding": binding,
        "confirmations": dict(TI_CONFIRM),
        "identityReceipt": {
            "resultPath": str(result_path),
            "resultSha256": result_sha256,
            "invocationId": result["invocationId"],
            "identityApprovalPath": source["approvalPath"],
            "identityApprovalSha256": source["approvalSha256"],
            "confirmedAt": confirmed.isoformat(),
        },
    }
    # At most one issuance even on crash/uncertain publication. Never reset this marker.
    ti_publish(
        original / f"consumed-{result_sha256}.json",
        ti_consumption(value, output),
        [*protected, output, evidence_dir],
    )
    ti_receipt(result_path, result_sha256)
    ti_publish(output, value, [*protected, original, evidence_dir])
    ti_cap_authority(output)
    return output


def prepare_capability_request_from_identity(
    output: Path, *, authority_path: Path
) -> Path:
    authority, digest = ti_cap_authority(authority_path)
    result, _ = ti_receipt(
        ti_path(authority["identityReceipt"]["resultPath"]),
        authority["identityReceipt"]["resultSha256"],
    )
    evidence = ti_path(authority["binding"]["evidenceDir"])
    protected = ti_protected(
        result["binding"],
        [authority_path, ti_path(authority["binding"]["approvalPath"])],
    )
    ti_separate(
        output, [*protected, evidence, ti_path(result["binding"]["evidenceDir"])]
    )
    request = {
        "schemaVersion": TI_CAP_REQUEST,
        "issueNumber": 204,
        "action": "capability_preflight",
        "binding": authority["binding"],
        "authorityPath": str(authority_path),
        "authoritySha256": digest,
    }
    ti_publish(output, request, [*protected, evidence])
    ti_publish(
        evidence / f"prepared-{authority['invocationId']}.json",
        {
            "requestPath": str(output),
            "requestSha256": ti_digest(ti_read(output)),
            "invocationId": authority["invocationId"],
        },
        [*protected, output],
    )
    return output


class _FiniteReads:
    ALLOWED = frozenset(
        {
            "GetProductName",
            "GetVersion",
            "GetProjectManager",
            "GetCurrentProject",
            "GetCurrentTimeline",
            "GetName",
            "GetUniqueId",
        }
    )

    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []

    def get(
        self, handle: Any, source: str, method: str, *, native: bool = False
    ) -> Any:
        ti_require(method in self.ALLOWED, "native method outside finite allowlist")
        row: dict[str, Any] = {"source": f"{source}.{method}", "status": "attempted"}
        self.rows.append(row)
        try:
            getter = getattr(handle, method, None)
            ti_require(callable(getter), "finite getter unavailable")
            assert callable(getter)
            value = getter()
            if native:
                ti_require(value is not None, "current native handle absent")
                row["value"] = "native-handle"
            else:
                payload = json.dumps(value, allow_nan=False).encode()
                ti_require(len(payload) <= 4096, "getter value exceeds bound")
                row["value"] = value
            row["status"] = "observed"
            return value
        except Exception as error:
            row["reason"] = str(error)[:512]
            raise ValueError(f"{source}.{method}: {str(error)[:512]}") from error

    def target(self, resolve: Any, names: dict[str, Any]) -> dict[str, Any]:
        manager = self.get(resolve, "resolve", "GetProjectManager", native=True)
        project = self.get(manager, "manager", "GetCurrentProject", native=True)
        project_name = ti_text(self.get(project, "project", "GetName"))
        ti_require(
            project_name == names["projectName"], "current project name mismatch"
        )
        project_uid = ti_text(self.get(project, "project", "GetUniqueId"))
        timeline = self.get(project, "project", "GetCurrentTimeline", native=True)
        timeline_name = ti_text(self.get(timeline, "timeline", "GetName"))
        ti_require(
            timeline_name == names["timelineName"], "current timeline name mismatch"
        )
        timeline_uid = ti_text(self.get(timeline, "timeline", "GetUniqueId"))
        return {
            "projectName": project_name,
            "projectUid": project_uid,
            "timelineName": timeline_name,
            "timelineUid": timeline_uid,
        }

    def runtime(self, resolve: Any, runtime: dict[str, Any]) -> None:
        runtime["product"] = self.get(resolve, "resolve", "GetProductName")
        runtime["version"] = self.get(resolve, "resolve", "GetVersion")
        version = runtime["version"]
        ti_require(
            runtime["product"] == "DaVinci Resolve Studio"
            and type(version) is list
            and len(version) == 5
            and all(type(n) is int for n in version[:4])
            and version == [21, 1, 1, 10, ""],
            "unsupported actual Studio product/build",
        )


def run_target_identity(
    resolve: Any,
    request_path: Path,
    *,
    expected_request_sha256: str,
) -> Path:
    request = ti_request(request_path, expected_request_sha256)
    started = ti_started(request, expected_request_sha256)
    binding = request["binding"]
    evidence = ti_path(binding["evidenceDir"])
    invocation = request["invocationId"]
    protected = ti_protected(binding, [request_path, ti_path(request["authorityPath"])])
    # Also reserve controller execution: bootstrap receipt alone cannot replay it.
    ti_publish(
        evidence / f"controller-started-{invocation}.json",
        {
            "invocationId": invocation,
            "bootstrapSha256": ti_digest(
                ti_read(evidence / f"bootstrap-started-{invocation}.json")
            ),
        },
        protected,
    )
    clock = TIClock(ti_time(started["startedAt"]), started["monotonicStarted"])
    seen = _FiniteReads()
    result: dict[str, Any] = {
        "schemaVersion": TI_RESULT,
        "issueNumber": 208,
        "action": "target_identity_handoff",
        "invocationId": invocation,
        "status": "stopped_safely",
        "qualified": False,
        "verified": False,
        "futureEffectsAuthorized": False,
        "startedAt": started["startedAt"],
        "finishedAt": None,
        "requestSha256": expected_request_sha256,
        "authoritySha256": request["authoritySha256"],
        "binding": binding,
        "runtime": {
            "injectedObjectAvailable": resolve is not None,
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
            "product": None,
            "version": None,
            "installedRoot": binding["installedRoot"],
            "installedSourcePins": None,
        },
        "reads": [],
        "target": None,
        "reason": None,
    }

    def guard() -> None:
        ti_clock_check(clock)
        ti_require(
            ti_request(request_path, expected_request_sha256) == request,
            "identity inputs changed",
        )
        ti_require(
            ti_started(request, expected_request_sha256) == started, "bootstrap changed"
        )

    try:
        guard()
        ti_require(resolve is not None, "injected object unavailable")
        result["runtime"]["installedSourcePins"] = ti_release(
            ti_path(binding["installedRoot"]), binding, True
        )
        seen.runtime(resolve, result["runtime"])
        for _ in range(2):
            guard()
            target = seen.target(resolve, binding["target"])
            result["reads"].append(
                {"readAt": datetime.now(UTC).isoformat(), "target": target}
            )
            guard()
            seen.runtime(resolve, result["runtime"])
        ti_require(
            result["reads"][0]["target"] == result["reads"][1]["target"],
            "current target name/UID drift",
        )
        guard()
        result.update(status="identity_observed", target=result["reads"][1]["target"])
    except Exception as error:
        result.update(status="stopped_safely", target=None, reason=str(error)[:512])
        # Preserve the original native outcome even if refusal retention fails.
        print(json.dumps(result, sort_keys=True))
        ti_publish(
            evidence / f"refusal-{invocation}.json",
            {
                "invocationId": invocation,
                "observations": seen.rows,
                "reason": str(error)[:512],
            },
            protected,
        )
    result["finishedAt"] = datetime.now(UTC).isoformat()
    print(json.dumps(result, sort_keys=True))
    if result["status"] == "identity_observed":
        guard()
    report = ti_publish(evidence / f"result-{invocation}.json", result, protected)
    ti_publish(
        evidence / f"hashes-{invocation}.json",
        {
            "invocationId": invocation,
            "resultPath": str(report),
            "resultSha256": ti_digest(ti_read(report)),
            "bootstrapSha256": ti_digest(
                ti_read(evidence / f"bootstrap-started-{invocation}.json")
            ),
            "controllerSha256": ti_digest(
                ti_read(evidence / f"controller-started-{invocation}.json")
            ),
            "requestSha256": expected_request_sha256,
            "authoritySha256": request["authoritySha256"],
        },
        protected,
    )
    return report
