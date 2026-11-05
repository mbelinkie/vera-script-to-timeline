"""One host-wide flock for native Resolve work across VERA routes."""

from __future__ import annotations

import contextvars
import fcntl
import hashlib
import importlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_STATE_ROOT = Path.home() / ".local/state/vera/resolve-delivery"
OWNER_LOCK_PATH = _STATE_ROOT / "native-owner.lock"
PARENT_ACTIVE_PATH = _STATE_ROOT / "active.json"
ISSUE328_ACTIVE_PATH = _STATE_ROOT / "issue328-native.active.json"
OUTPUT_ATTEMPTS_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-host/v1/attempts"
)
OUTPUT_TARGETS_ROOT = (
    Path.home()
    / "Library/Application Support/VERA/qualification-output-native/v1/targets"
)
OWNER_FD_ENV = "VERA_NATIVE_OWNER_FD"
_MAX_RECORD_BYTES = 8 * 1024 * 1024
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TERMINAL_RENDER_STATES = frozenset({"Complete", "Failed", "Cancelled"})
_HELD_OWNER_FD: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "vera_native_owner_fd", default=None
)


class NativeOwnerError(ValueError):
    """A known owner or unresolved native operation prevents a new effect."""

    def __init__(self, reason: str, private_detail: str) -> None:
        self.reason = reason
        self.private_detail = private_detail
        super().__init__("Resolve is owned by another VERA operation or is unresolved")


def _blocked(reason: str, detail: str) -> NativeOwnerError:
    return NativeOwnerError(reason, detail)


def _lock_file(path: Path, *, create: bool) -> tuple[int, os.stat_result]:
    if path.is_symlink() or path.parent.is_symlink():
        raise _blocked("unsafe_owner_lock", str(path))
    if create:
        path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    if create:
        flags |= os.O_CREAT
    try:
        descriptor = os.open(path, flags, 0o600)
    except OSError as error:
        raise _blocked("owner_lock_unavailable", f"{path}: {error}") from error
    metadata = os.fstat(descriptor)
    if (
        not stat.S_ISREG(metadata.st_mode)
        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
        or stat.S_IMODE(metadata.st_mode) & 0o077
    ):
        os.close(descriptor)
        raise _blocked("unsafe_owner_lock", str(path))
    return descriptor, metadata


def acquire_native_owner() -> int:
    """Acquire the shared host lock without waiting or changing a retained marker."""
    descriptor, _ = _lock_file(OWNER_LOCK_PATH, create=True)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as error:
        os.close(descriptor)
        raise _blocked("owner_busy", "the shared native owner lock is held") from error
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def release_native_owner(descriptor: int) -> None:
    """Close this reference; inherited duplicates keep the same flock alive."""
    os.close(descriptor)


def _validate_inherited_owner(descriptor: int) -> None:
    try:
        metadata = os.fstat(descriptor)
        path_metadata = OWNER_LOCK_PATH.stat(follow_symlinks=False)
    except OSError as error:
        raise _blocked("invalid_inherited_owner", str(error)) from error
    if (
        not stat.S_ISREG(metadata.st_mode)
        or not stat.S_ISREG(path_metadata.st_mode)
        or metadata.st_dev != path_metadata.st_dev
        or metadata.st_ino != path_metadata.st_ino
        or (hasattr(os, "getuid") and metadata.st_uid != os.getuid())
    ):
        raise _blocked("invalid_inherited_owner", str(OWNER_LOCK_PATH))
    try:
        # Re-locking the inherited open-file description is idempotent. A forged
        # or stale descriptor for this inode cannot pass while another owner holds it.
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except (BlockingIOError, OSError) as error:
        raise _blocked("invalid_inherited_owner", str(OWNER_LOCK_PATH)) from error


@contextmanager
def native_owner() -> Iterator[int]:
    """Own Resolve during one call; nested or inherited calls reuse its descriptor."""
    held = _HELD_OWNER_FD.get()
    if held is not None:
        _validate_inherited_owner(held)
        yield held
        return

    inherited = os.environ.get(OWNER_FD_ENV)
    if inherited is not None:
        try:
            descriptor = int(inherited)
            if descriptor < 0:
                raise ValueError("negative file descriptor")
        except ValueError as error:
            raise _blocked("invalid_inherited_owner", OWNER_FD_ENV) from error
        _validate_inherited_owner(descriptor)
        token = _HELD_OWNER_FD.set(descriptor)
        try:
            yield descriptor
        finally:
            _HELD_OWNER_FD.reset(token)
        return

    descriptor = acquire_native_owner()
    token = _HELD_OWNER_FD.set(descriptor)
    try:
        _check_parent_operation()
        _check_issue328_marker()
        yield descriptor
    finally:
        _HELD_OWNER_FD.reset(token)
        release_native_owner(descriptor)


def preflight_native_owner() -> None:
    """Read retained VERA ownership evidence; never edits, unlocks, or resumes it."""
    _check_parent_operation()
    _check_issue328_marker()
    if not any(
        path.exists() or path.is_symlink()
        for path in (OUTPUT_ATTEMPTS_ROOT, OUTPUT_TARGETS_ROOT)
    ):
        return
    try:
        native = importlib.import_module(".qualification_output_native_v2", __package__)
    except Exception as error:
        raise _blocked("output_guard_unavailable", str(error)) from error
    active_host = _active_output_host_chains(native)
    seen: set[str] = set()
    if OUTPUT_TARGETS_ROOT.exists() or OUTPUT_TARGETS_ROOT.is_symlink():
        if OUTPUT_TARGETS_ROOT.is_symlink() or not OUTPUT_TARGETS_ROOT.is_dir():
            raise _blocked("output_state_unreadable", str(OUTPUT_TARGETS_ROOT))
        for target in sorted(OUTPUT_TARGETS_ROOT.iterdir()):
            if (
                target.is_symlink()
                or not target.is_dir()
                or not _HEX64.fullmatch(target.name)
            ):
                raise _blocked("output_state_unreadable", str(target))
            seen.add(target.name)
            operations = target / "operations"
            if not operations.exists():
                if target.name in active_host:
                    raise _blocked("output_operation_unresolved", str(target))
                continue
            _check_native_chain(native, operations, active_host.get(target.name))

    for chain_key, state in active_host.items():
        if chain_key not in seen:
            raise _blocked(
                "output_operation_unresolved",
                f"{OUTPUT_ATTEMPTS_ROOT}/{_short_key(chain_key)} state={state}",
            )


def _check_parent_operation() -> None:
    if not PARENT_ACTIVE_PATH.exists() and not PARENT_ACTIVE_PATH.is_symlink():
        return
    try:
        value = json.loads(_read(PARENT_ACTIVE_PATH, "active parent"))
        if set(value) != {"requestPath", "requestSha256"} or any(
            not isinstance(item, str) or not item for item in value.values()
        ):
            raise ValueError("invalid active parent identity")
        from . import workflow_v2_parent

        status = workflow_v2_parent.status(
            Path(value["requestPath"]), value["requestSha256"]
        )
    except Exception as error:
        raise _blocked("parent_unresolved", f"{PARENT_ACTIVE_PATH}: {error}") from error
    if status.get("state") not in {"terminal", "not_started"}:
        raise _blocked(
            "parent_unresolved",
            f"{PARENT_ACTIVE_PATH} -> {value['requestPath']} "
            f"state={status.get('state')}",
        )


def _check_issue328_marker() -> None:
    if ISSUE328_ACTIVE_PATH.exists() or ISSUE328_ACTIVE_PATH.is_symlink():
        raise _blocked("issue328_unresolved", str(ISSUE328_ACTIVE_PATH))


def _active_output_host_chains(native: Any) -> dict[str, str]:
    if not OUTPUT_ATTEMPTS_ROOT.exists() and not OUTPUT_ATTEMPTS_ROOT.is_symlink():
        return {}
    if OUTPUT_ATTEMPTS_ROOT.is_symlink() or not OUTPUT_ATTEMPTS_ROOT.is_dir():
        raise _blocked("output_state_unreadable", str(OUTPUT_ATTEMPTS_ROOT))
    controller = importlib.import_module(
        ".qualification_output_controller_v2", __package__
    )
    active: dict[str, str] = {}
    for directory in sorted(OUTPUT_ATTEMPTS_ROOT.iterdir()):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not _HEX64.fullmatch(directory.name)
        ):
            raise _blocked("output_state_unreadable", str(directory))
        try:
            chain = controller._parse(controller._read(directory / "chain.json"))
            entries = sorted(directory.glob("entry-*.json"))
            pending = sorted(directory.glob("pending-*.json"))
            heads = sorted(directory.glob("head-*.json"))
            if len(entries) != len(pending) or len(entries) != len(heads):
                raise ValueError("partial output attempt append")
            rows = []
            for sequence, (entry, pending_path, head) in enumerate(
                zip(entries, pending, heads, strict=True)
            ):
                expected = f"{sequence:04d}.json"
                if (
                    entry.name != f"entry-{expected}"
                    or pending_path.name != f"pending-{expected}"
                    or head.name != f"head-{expected}"
                ):
                    raise ValueError("reordered output attempt history")
                raw = controller._read(entry)
                if raw != controller._read(pending_path):
                    raise ValueError("partial output attempt publication")
                row = controller._parse(raw)
                if controller._parse(controller._read(head)) != {
                    "sequence": sequence,
                    "entrySha256": row.get("entrySha256"),
                }:
                    raise ValueError("output attempt head differs")
                rows.append(row)
            if rows:
                expected_chain = controller._chain(rows[0]["context"])
                if chain != expected_chain or directory.name != controller._json_hash(
                    chain
                ):
                    raise ValueError("output attempt chain identity differs")
                controller._validated_history(rows, chain)
                state = rows[-1]["state"]
                if state in {"reserved_by_render_intent", "uncertain"}:
                    chain_key = native._chain_key(rows[-1]["context"])
                    prior = active.get(chain_key)
                    if prior is not None and prior != state:
                        raise ValueError("conflicting host output chain states")
                    active[chain_key] = state
            else:
                if (
                    set(chain) != {"projectUid", "timelineUid", "caseId", "phase"}
                    or any(
                        not isinstance(value, str) or not value
                        for value in chain.values()
                    )
                    or directory.name != controller._json_hash(chain)
                ):
                    raise ValueError("empty output chain identity differs")
                # The controller prepares artifact/receipt vaults before commitment.
                children = list(directory.iterdir())
                if any(path.is_symlink() for path in children) or not {
                    path.name for path in children
                } <= {"chain.json", "lock", "artifacts", "receipts"}:
                    raise ValueError("incomplete empty output attempt chain")
                for name in ("artifacts", "receipts"):
                    vault = directory / name
                    if vault.exists() and not vault.is_dir():
                        raise ValueError("invalid empty output chain vault")
        except Exception as error:
            raise _blocked(
                "output_state_unreadable", f"{directory}: {error}"
            ) from error
    return active


def _check_native_chain(native: Any, operations: Path, host_state: str | None) -> None:
    if operations.is_symlink() or not operations.is_dir():
        raise _blocked("output_operation_unresolved", str(operations))
    directories = sorted(operations.iterdir())
    render_pending = False
    found_result = False
    for sequence, directory in enumerate(directories):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or directory.name != f"{sequence:08d}"
        ):
            raise _blocked("output_operation_unresolved", str(directory))
        result_path = directory / "result.json"
        request_path = directory / "request.json"
        start_path = directory / "native-start.json"
        effects_path = directory / "effects"
        children = {item.name for item in directory.iterdir()}
        if result_path.exists() or result_path.is_symlink():
            if (
                request_path.is_symlink()
                or not request_path.is_file()
                or start_path.is_symlink()
                or not start_path.is_file()
            ):
                raise _blocked("output_operation_unresolved", str(directory))
            try:
                raw = _read(result_path, "native result")
                result = json.loads(raw)
                if not isinstance(result, dict):
                    raise ValueError("native result is not an object")
                action = result.get("action")
                status = result.get("status")
                if status not in {"complete", "partial", "refused", "uncertain"}:
                    raise ValueError("unsupported native result status")
                relevant = (
                    status == "uncertain"
                    or action
                    in {
                        "queue_render",
                        "start_render",
                        "poll_render",
                        "capture_post",
                    }
                    or host_state is not None
                )
                verified = (
                    native.verify_native_result(
                        result_path, hashlib.sha256(raw).hexdigest()
                    )
                    if relevant
                    else result
                )
            except Exception as error:
                raise _blocked(
                    "output_operation_unresolved", f"{result_path}: {error}"
                ) from error
            found_result = True
            if status == "uncertain":
                raise _blocked(
                    "output_operation_unresolved",
                    f"{result_path} contains an uncertain native effect",
                )
            if action in {"queue_render", "start_render"}:
                if status != "refused":
                    render_pending = True
            elif action == "poll_render":
                job_status = (verified.get("renderStatus") or {}).get("JobStatus")
                if status in {"complete", "partial"} and job_status in (
                    _TERMINAL_RENDER_STATES
                ):
                    render_pending = False
                else:
                    render_pending = True
            elif action == "capture_post" and render_pending:
                raise _blocked(
                    "output_operation_unresolved",
                    f"{result_path} follows a render without terminal polling",
                )
            continue

        if (
            start_path.exists()
            or start_path.is_symlink()
            or effects_path.exists()
            or effects_path.is_symlink()
        ):
            raise _blocked("output_operation_unresolved", str(directory))
        if request_path.exists() or request_path.is_symlink():
            if request_path.is_symlink() or not request_path.is_file():
                raise _blocked("output_operation_unresolved", str(request_path))
            try:
                raw = _read(request_path, "prepared native request")
                digest = hashlib.sha256(raw).hexdigest()
                request = native.verify_native_request(
                    raw, expected_request_sha256=digest, current=False
                )
                authority, authority_sha, _ = native._verify_authority(
                    request, current=False
                )
                reservation_sha = native._verify_reservation(request, current=False)
                native._verify_intent(request, authority_sha, reservation_sha)
                expired = native._time(
                    authority["expiresAt"], "native authority expiry"
                ) <= datetime.now(UTC)
            except Exception as error:
                raise _blocked(
                    "output_operation_unresolved", f"{request_path}: {error}"
                ) from error
            if not expired:
                raise _blocked(
                    "output_operation_unresolved",
                    f"{request_path} is prepared but has not expired",
                )
            # Native start records are written before the first Resolve effect.
            continue

        if children:
            raise _blocked("output_operation_unresolved", str(directory))

    if host_state is not None and not found_result and not directories:
        raise _blocked(
            "output_operation_unresolved",
            f"{operations} has host state={host_state} without native evidence",
        )
    if render_pending:
        raise _blocked(
            "output_render_unresolved",
            f"{operations} has a queued or started render without terminal polling",
        )


def _read(path: Path, label: str) -> bytes:
    if (
        path.is_symlink()
        or path.stat(follow_symlinks=False).st_size > _MAX_RECORD_BYTES
    ):
        raise ValueError(f"invalid {label}")
    descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or (
            hasattr(os, "getuid") and metadata.st_uid != os.getuid()
        ):
            raise ValueError(f"regular current-user-owned {label} required")
        with os.fdopen(descriptor, "rb", closefd=False) as stream:
            raw = stream.read(_MAX_RECORD_BYTES + 1)
        if len(raw) > _MAX_RECORD_BYTES:
            raise ValueError(f"{label} exceeds size bound")
        return raw
    finally:
        os.close(descriptor)


def _short_key(value: str) -> str:
    return value[:12]
