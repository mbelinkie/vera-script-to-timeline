"""Repository-owned Workflow Integration v2; Resolve injects `resolve`."""

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

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
# Resolve can exec a script without __file__; retain #107's documented root.
SCRIPT_PATH = Path(globals().get("__file__", str(PLUGIN_ROOT / "VERA Delivery v2.py")))


def within(path: Path, parent: Path) -> bool:
    if path.is_relative_to(parent):
        return True
    if not parent.exists():
        return False
    identity = (parent.stat().st_dev, parent.stat().st_ino)
    return any(
        p.exists() and (p.stat().st_dev, p.stat().st_ino) == identity
        for p in (path, *path.parents)
    )


def provenance_bytes(path: Path) -> bytes:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError("unsafe qualification input")
    before = path.lstat()
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size > 2 * 1024 * 1024
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise RuntimeError("hardlinked/changed/unbounded qualification input")
        payload = source.read(2 * 1024 * 1024 + 1)
        after = os.fstat(source.fileno())
    if len(payload) != opened.st_size or (opened.st_size, opened.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        raise RuntimeError("qualification input changed while reading")
    return payload


def qualification_object(payload: bytes) -> dict[str, Any]:
    def pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in entries:
            if key in value:
                raise RuntimeError("duplicate qualification key")
            value[key] = item
        return value

    parsed = json.loads(payload, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise RuntimeError("qualification record must be an object")
    json.dumps(parsed, allow_nan=False)
    return cast(dict[str, Any], parsed)


def launch(injected_resolve: object) -> None:
    if any(
        path.is_symlink() for path in (SCRIPT_PATH, *SCRIPT_PATH.absolute().parents)
    ):
        raise RuntimeError("symbolic link in installed script path")
    root = SCRIPT_PATH.resolve().parent
    release_root = root / "vera-delivery-v2"
    if release_root.is_symlink():
        raise RuntimeError("symbolic link in installed release root")
    request_path = release_root / "request.json"
    if request_path.is_symlink():
        raise RuntimeError("symbolic link in installed request path")
    # CN-207-ID1: this checked-in stdlib verifier runs before any VERA import.
    candidate = ti_object(ti_read(request_path))
    if candidate.get("schemaVersion") == TI_CAP_REQUEST:
        if ti_loaded_runtime():
            raise ValueError("a VERA runtime is already loaded; restart Resolve")
        digest = ti_digest(ti_read(request_path))
        checked = ti_cap_request(request_path, digest)
        authority, _ = ti_cap_authority(ti_path(checked["authorityPath"]))
        observed, _ = ti_receipt(
            ti_path(authority["identityReceipt"]["resultPath"]),
            authority["identityReceipt"]["resultSha256"],
        )
        ti_require(
            ti_path(observed["binding"]["installedRoot"]) == root
            and SCRIPT_PATH.name == "VERA Delivery v2.py",
            "installed root/script mismatch",
        )
        ti_cap_reserve(request_path, digest)
        sys.dont_write_bytecode = True
        sys.pycache_prefix = None
        sys.path.insert(0, str(release_root / "python"))
        from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

        print(
            run_installed_request_v2(
                injected_resolve, request_path, expected_request_sha256=digest
            )
        )
        return
    if candidate.get("schemaVersion") == TI_REQUEST:
        if any(
            n == "vera_timeline_agent" or n.startswith("vera_timeline_agent.")
            for n in sys.modules
        ):
            raise ValueError("a VERA runtime is already loaded; restart Resolve")
        digest = ti_digest(ti_read(request_path))
        checked = ti_request(request_path, digest)
        ti_require(
            ti_path(checked["binding"]["installedRoot"]) == root
            and SCRIPT_PATH.name == "VERA Delivery v2.py",
            "installed root/script mismatch",
        )
        ti_reserve(request_path, digest)
        sys.dont_write_bytecode = True
        sys.pycache_prefix = None
        sys.path.insert(0, str(release_root / "python"))
        from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

        print(
            run_installed_request_v2(
                injected_resolve, request_path, expected_request_sha256=digest
            )
        )
        return
    request_bytes = request_path.read_bytes()
    request = json.loads(request_bytes)
    qualification = (
        request.get("schemaVersion") == "vera-native-qualification-request/v1"
    )
    if qualification:
        request = qualification_object(request_bytes)
    binding = request["binding"] if qualification else request
    release_path = release_root / "release.json"
    if release_path.is_symlink():
        raise RuntimeError("symbolic link in installed release manifest")
    release_bytes = release_path.read_bytes()
    if hashlib.sha256(release_bytes).hexdigest() != binding["releaseSha256"]:
        raise RuntimeError("installed release hash differs from the operator request")
    release = json.loads(release_bytes)
    if (
        not isinstance(release, dict)
        or set(release) != {"schemaVersion", "deliveryVersion", "sourcePins", "files"}
        or release["schemaVersion"] != "vera-injected-delivery-release/v2"
        or release["deliveryVersion"] != "2"
    ):
        raise RuntimeError("unsupported installed release")
    for entry in release["files"]:
        path = root / entry["path"]
        if (
            not path.resolve().is_relative_to(root)
            or path.is_symlink()
            or path.stat().st_size != entry["sizeBytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise RuntimeError("installed source differs from the versioned release")
    runtime = release_root / "python"
    declared_files = {entry["path"] for entry in release["files"]}
    entries = list(release_root.rglob("*"))
    if any(
        path.is_symlink() or not (path.is_file() or path.is_dir()) for path in entries
    ):
        raise RuntimeError("unsupported entry in installed release")
    installed_files = {
        path.relative_to(root).as_posix()
        for path in entries
        if path.is_file()
        and path not in {release_path, request_path}
        and path.name != ".DS_Store"
    } | {SCRIPT_PATH.name}
    declared_directories = {
        parent.as_posix()
        for name in declared_files
        for parent in Path(name).parents
        if parent != Path(".")
    }
    installed_directories = {release_root.relative_to(root).as_posix()} | {
        path.relative_to(root).as_posix() for path in entries if path.is_dir()
    }
    if (
        installed_files != declared_files
        or installed_directories != declared_directories
    ):
        raise RuntimeError(
            "installed source inventory differs from release; reinstall clean release"
        )
    for name in tuple(sys.modules):
        if name == "vera_timeline_agent" or name.startswith("vera_timeline_agent."):
            raise RuntimeError("a VERA runtime is already loaded; restart Resolve")
    if qualification:
        # Retain exact input provenance before importing the installed controller.
        if (
            set(request)
            != {
                "schemaVersion",
                "issueNumber",
                "action",
                "binding",
                "authorityPath",
                "authoritySha256",
            }
            or type(request["issueNumber"]) is not int
            or request["issueNumber"] != 204
            or request["action"] != "capability_preflight"
        ):
            raise RuntimeError("unsupported read-only qualification request")
        authority_path = Path(request["authorityPath"])
        approval_path = Path(binding["approvalPath"])
        evidence = Path(binding["evidenceDir"])
        inputs = (
            authority_path,
            approval_path,
            evidence,
            Path(binding["repositoryRoot"]),
        )
        if any(
            not path.is_absolute()
            or any(part.is_symlink() for part in (path, *path.parents))
            for path in inputs
        ):
            raise RuntimeError("unsafe qualification provenance paths")
        if provenance_bytes(request_path) != request_bytes:
            raise RuntimeError("qualification request changed before import")
        authority_bytes = provenance_bytes(authority_path)
        authority = qualification_object(authority_bytes)
        if (
            set(authority)
            != {
                "schemaVersion",
                "issueNumber",
                "action",
                "operator",
                "issuedAt",
                "invocationId",
                "issuer",
                "binding",
                "confirmations",
            }
            or authority["schemaVersion"] != "vera-native-qualification-authority/v1"
            or type(authority["issueNumber"]) is not int
            or authority["issueNumber"] != 204
            or authority["action"] != "capability_preflight"
            or authority["confirmations"]
            != {
                "readOnly": True,
                "savedDisposableNonproduction": True,
                "externalScripting": "None",
            }
            or authority["confirmations"]["readOnly"] is not True
            or authority["confirmations"]["savedDisposableNonproduction"] is not True
        ):
            raise RuntimeError("invalid closed read-only operator authority")
        if (
            hashlib.sha256(authority_bytes).hexdigest() != request["authoritySha256"]
            or authority["binding"] != binding
            or hashlib.sha256(provenance_bytes(approval_path)).hexdigest()
            != binding["approvalSha256"]
            or within(evidence, root)
            or within(evidence, Path(binding["repositoryRoot"]))
            or within(evidence, Path(binding["releaseRoot"]))
            or within(root, evidence)
            or within(Path(binding["repositoryRoot"]), evidence)
            or within(Path(binding["releaseRoot"]), evidence)
            or within(authority_path, evidence)
            or within(approval_path, evidence)
        ):
            raise RuntimeError("qualification provenance mismatch/overlap")
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        started = evidence / f"bootstrap-started-{uuid.uuid4().hex}.json"
        with started.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "requestSha256": hashlib.sha256(request_bytes).hexdigest(),
                    "authoritySha256": request["authoritySha256"],
                    "releaseSha256": binding["releaseSha256"],
                    "approvalSha256": binding["approvalSha256"],
                    "repositorySourcePins": binding["repositorySourcePins"],
                    "target": binding["target"],
                    "qualified": False,
                },
                stream,
                indent=2,
                sort_keys=True,
            )
        started.chmod(0o400)
    sys.dont_write_bytecode = True
    sys.pycache_prefix = None
    sys.path.insert(0, str(runtime))
    from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

    report = run_installed_request_v2(
        injected_resolve,
        request_path,
        expected_request_sha256=hashlib.sha256(request_bytes).hexdigest(),
    )
    print(report)


def retain_bootstrap_refusal(failure: dict[str, Any]) -> None:
    # Retain bootstrap failures without importing unverified installed code.
    try:
        config = json.loads(
            (SCRIPT_PATH.resolve().parent / "vera-delivery-v2/request.json").read_text()
        )
        if config.get("schemaVersion") == TI_REQUEST:
            # Refusal output comes only from independently revalidated authority.
            authority, digest = ti_authority(ti_path(config["authorityPath"]))
            ti_require(
                digest == config["authoritySha256"], "refusal authority mismatch"
            )
            binding = authority["binding"]
            evidence = ti_path(binding["evidenceDir"])
            protected = ti_protected(
                binding,
                [
                    ti_path(config["authorityPath"]),
                    SCRIPT_PATH,
                    SCRIPT_PATH.parent / "vera-delivery-v2/request.json",
                ],
            )
            ti_separate(evidence, protected)
            path = ti_publish(
                evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json",
                failure,
                protected,
            )
            failure["reportPath"] = str(path)
            print(json.dumps(failure, sort_keys=True))
            return
        if config.get("schemaVersion") == TI_CAP_REQUEST:
            authority, digest = ti_cap_authority(ti_path(config["authorityPath"]))
            ti_require(
                digest == config["authoritySha256"], "refusal authority mismatch"
            )
            observed, _ = ti_receipt(
                ti_path(authority["identityReceipt"]["resultPath"]),
                authority["identityReceipt"]["resultSha256"],
            )
            protected = ti_protected(
                observed["binding"],
                [
                    SCRIPT_PATH,
                    SCRIPT_PATH.parent / "vera-delivery-v2/request.json",
                    ti_path(config["authorityPath"]),
                    ti_path(authority["binding"]["approvalPath"]),
                ],
            )
            evidence = ti_path(authority["binding"]["evidenceDir"])
            ti_separate(evidence, protected)
            path = ti_publish(
                evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json",
                failure,
                protected,
            )
            failure["reportPath"] = str(path)
            print(json.dumps(failure, sort_keys=True))
            return
        if config.get("schemaVersion") == "vera-native-qualification-request/v1":
            binding = config["binding"]
            # A tampered request's unsafe output cannot replace its bound safe receipt.
            try:
                authority = provenance_bytes(Path(config["authorityPath"]))
                if hashlib.sha256(authority).hexdigest() == config["authoritySha256"]:
                    binding = json.loads(authority)["binding"]
            except Exception:
                pass
            evidence = Path(binding["evidenceDir"])
            protected_roots = [
                SCRIPT_PATH.resolve().parent,
                Path(binding["repositoryRoot"]).resolve(),
                Path(binding["releaseRoot"]).resolve(),
                Path(binding["approvalPath"]).resolve(),
                Path(config["authorityPath"]).resolve(),
            ]
            if any(within(path, evidence) for path in protected_roots):
                raise RuntimeError("qualification evidence contains protected input")
        else:
            evidence = Path(config["evidenceDir"])
            package = Path(config["packageDir"]).resolve()
            protected_roots = [package]
            attestation_path = Path(config["attestationPath"])
            if attestation_path.exists():
                protected_roots.append(
                    Path(
                        json.loads(attestation_path.read_text())["packageDir"]
                    ).resolve()
                )
        if (
            not evidence.is_absolute()
            or any(
                path.is_symlink() for path in (evidence, *evidence.absolute().parents)
            )
            or any(within(evidence, root) for root in protected_roots)
        ):
            raise RuntimeError("unsafe evidence directory")
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(failure, stream, indent=2, sort_keys=True)
        path.chmod(0o400)
        failure["reportPath"] = str(path)
    except Exception:
        failure["reportRetention"] = "unavailable; retain this Console output"
    print(json.dumps(failure, indent=2, sort_keys=True))


try:
    launch(globals().get("resolve"))
except Exception as error:
    retain_bootstrap_refusal(
        {
            "status": "workflow_v2_launcher_failed",
            "verified": False,
            "detail": str(error),
        }
    )
