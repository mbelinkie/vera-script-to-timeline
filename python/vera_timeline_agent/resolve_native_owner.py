"""One host-wide flock for native Resolve work across VERA routes."""

from __future__ import annotations

import contextvars
import fcntl
import importlib.util
import json
import os
import re
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

_STATE_ROOT = Path.home() / ".local/state/vera/resolve-delivery"
OWNER_LOCK_PATH = _STATE_ROOT / "native-owner.lock"
PARENT_ACTIVE_PATH = _STATE_ROOT / "active.json"
ISSUE328_ACTIVE_PATH = _STATE_ROOT / "issue328-native.active.json"
OWNER_FD_ENV = "VERA_NATIVE_OWNER_FD"
_TERMINAL_RENDER_STATES = frozenset({"Complete", "Failed", "Cancelled"})
_RESOLVE_SCRIPTING_MODULE = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules/DaVinciResolveScript.py"
)
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
    """Only allow a new operation after earlier parent ownership is resolved."""
    _check_parent_operation()
    _check_issue328_marker()


_DISPOSABLE_NAME = re.compile(
    r"VERA Delivery [0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12} [0-9a-f]{12}\Z"
)


def _local_resolve_connection() -> Any:
    """Load the installed public SDK even in a clean launchd Python process."""
    module = sys.modules.get("DaVinciResolveScript")
    if module is None:
        path = _RESOLVE_SCRIPTING_MODULE
        if path.is_symlink() or not path.is_file():
            raise ValueError("installed local Resolve scripting module unavailable")
        spec = importlib.util.spec_from_file_location("DaVinciResolveScript", path)
        if spec is None or spec.loader is None:
            raise ValueError("installed local Resolve scripting module cannot load")
        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get(spec.name)
        sys.modules[spec.name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            if previous is None:
                sys.modules.pop(spec.name, None)
            else:
                sys.modules[spec.name] = previous
            raise
        # The real vendor bootstrap replaces itself in sys.modules with
        # fusionscript after successfully importing the native extension.
        module = sys.modules.get(spec.name, module)
    scriptapp = getattr(module, "scriptapp", None)
    if not callable(scriptapp):
        raise ValueError("installed local Resolve scripting module is invalid")
    return scriptapp("Resolve")


def preflight_independent_disposable(target_name: str) -> None:
    """Read-only live safety check for a *new* independent v2 test target.

    The caller must acquire the shared native owner lock before dispatch. This
    deliberately does not turn old UNKNOWN output results into completion or
    clear their reservation: only the *current* Resolve project can intersect
    with a fresh, uniquely named target. Other projects' historical outcomes
    remain UNKNOWN, without claiming to own the currently idle application.
    The normal strict preflight remains the default for every other route.
    """
    if not isinstance(target_name, str) or not _DISPOSABLE_NAME.fullmatch(target_name):
        raise _blocked("disposable_target_invalid", "new target name is not unique")
    _check_parent_operation()
    _check_issue328_marker()
    try:
        resolve = _local_resolve_connection()
        if not resolve:
            raise ValueError("local Resolve connection unavailable")
        manager = resolve.GetProjectManager()
        if manager is None:
            raise ValueError("project manager unavailable")
        current = manager.GetCurrentProject()
        if current is None:
            raise ValueError("no current project to establish idle state")
        current_uid = current.GetUniqueId()
        if not isinstance(current_uid, str) or not current_uid:
            raise ValueError("current project UID unavailable")
        if current.IsRenderingInProgress() is not False:
            raise ValueError("Resolve is rendering or render state is unknown")
        if current.GetName() == target_name:
            raise ValueError("new target is already selected")
        available = manager.GetProjectListInCurrentFolder()
        if not isinstance(available, (list, tuple)) or any(
            not isinstance(name, str) for name in available
        ):
            raise ValueError("project inventory unavailable")
        if target_name in available:
            raise ValueError("new target already exists")
        jobs = current.GetRenderJobList()
        if not isinstance(jobs, (list, tuple)):
            raise ValueError("render job inventory unavailable")
        for job in jobs:
            if (
                not isinstance(job, dict)
                or not isinstance(job.get("JobId"), str)
                or not job["JobId"]
            ):
                raise ValueError("render job identity unavailable")
            status = current.GetRenderJobStatus(job["JobId"])
            if (
                not isinstance(status, dict)
                or status.get("JobStatus") not in _TERMINAL_RENDER_STATES
            ):
                raise ValueError("a render job is pending, active or unknown")

        # Recheck the dynamic render state after reading historical journals.
        if current.IsRenderingInProgress() is not False:
            raise ValueError("Resolve changed to rendering during preflight")
        selected = manager.GetCurrentProject()
        if selected is None or selected.GetUniqueId() != current_uid:
            raise ValueError("current project changed during preflight")
    except NativeOwnerError:
        raise
    except Exception as error:
        raise _blocked("independent_disposable_not_idle", str(error)) from error


def _check_parent_operation() -> None:
    if not PARENT_ACTIVE_PATH.exists() and not PARENT_ACTIVE_PATH.is_symlink():
        return
    try:
        value = json.loads(PARENT_ACTIVE_PATH.read_bytes())
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
