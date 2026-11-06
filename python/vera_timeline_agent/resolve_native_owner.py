"""One host-wide flock for native Resolve work across VERA routes."""

from __future__ import annotations

import argparse
import contextvars
import fcntl
import hashlib
import hmac
import importlib
import json
import os
import re
import stat
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

_STATE_ROOT = Path.home() / ".local/state/vera/resolve-delivery"
OWNER_LOCK_PATH = _STATE_ROOT / "native-owner.lock"
PAUSED_OUTPUT_ROOT = _STATE_ROOT / "paused-output-v1"
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
_PAUSE_OBSERVATION_LIFETIME = timedelta(hours=12)
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
def native_owner(*, output_lane: bool = False) -> Iterator[int]:
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
        # Installed Resolve delivery bundles contain only the small host owner
        # guard and the journal reader, not the full qualification-output
        # verifier. Keep this entry point self-contained. The external parent
        # performs full historical validation before any new native dispatch.
        _check_parent_operation()
        _check_issue328_marker()
        if not output_lane:
            active = _active_output_host_chains(None)
            if any(not _locally_attested_paused_queue(key) for key in active):
                raise _blocked("output_render_unresolved", str(OUTPUT_ATTEMPTS_ROOT))
        yield descriptor
    finally:
        _HELD_OWNER_FD.reset(token)
        release_native_owner(descriptor)


def preflight_native_owner() -> None:
    """Read retained VERA ownership evidence; never edits, unlocks, or resumes it."""
    _check_parent_operation()
    _check_issue328_marker()
    try:
        native = importlib.import_module(".qualification_output_native_v2", __package__)
    except Exception as error:
        raise _blocked("output_guard_unavailable", str(error)) from error
    _check_output_histories(native)


def _check_output_histories(native: Any) -> None:
    # Each historical result recursively authenticates its predecessors. Share
    # the native verifier's strictly invocation-local traversal so checking
    # multiple operations of one old chain does not repeatedly authenticate
    # the same immutable evidence. A later preflight starts a new traversal.
    with native._verification_scope():
        active_host = _active_output_host_chains(native)
        if OUTPUT_TARGETS_ROOT.is_symlink() or (
            OUTPUT_TARGETS_ROOT.exists() and not OUTPUT_TARGETS_ROOT.is_dir()
        ):
            raise _blocked("output_state_unreadable", str(OUTPUT_TARGETS_ROOT))

        # An unresolved active host chain is a hard stop regardless of the
        # condition of unrelated, inactive historical targets. Check it first:
        # the old target/source verifier is expensive, and repeatedly scanning
        # hundreds of inactive records before refusing a known live owner can
        # make a single scheduled worker pass take minutes. A *passing* check
        # still verifies every historical target below; no evidence is skipped.
        for chain_key, state in sorted(active_host.items()):
            target = OUTPUT_TARGETS_ROOT / chain_key
            if target.is_symlink() or not target.is_dir():
                raise _blocked(
                    "output_operation_unresolved",
                    f"{OUTPUT_ATTEMPTS_ROOT}/{_short_key(chain_key)} state={state}",
                )
            operations = target / "operations"
            if not operations.exists() and not operations.is_symlink():
                raise _blocked("output_operation_unresolved", str(target))
            _check_native_chain(native, operations, state)

        if OUTPUT_TARGETS_ROOT.exists():
            for target in sorted(OUTPUT_TARGETS_ROOT.iterdir()):
                if (
                    target.is_symlink()
                    or not target.is_dir()
                    or not _HEX64.fullmatch(target.name)
                ):
                    raise _blocked("output_state_unreadable", str(target))
                if target.name in active_host:
                    continue  # Already authenticated in this invocation.
                operations = target / "operations"
                if operations.exists() or operations.is_symlink():
                    _check_native_chain(native, operations, None)


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
    from . import qualification_output_records_v2 as records

    active: dict[str, str] = {}
    for directory in sorted(OUTPUT_ATTEMPTS_ROOT.iterdir()):
        if (
            directory.is_symlink()
            or not directory.is_dir()
            or not _HEX64.fullmatch(directory.name)
        ):
            raise _blocked("output_state_unreadable", str(directory))
        try:
            chain = records._parse(_read(directory / "chain.json"))
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
                raw = _read(entry)
                if raw != _read(pending_path):
                    raise ValueError("partial output attempt publication")
                row = records._parse(raw)
                if records._parse(_read(head)) != {
                    "sequence": sequence,
                    "entrySha256": row.get("entrySha256"),
                }:
                    raise ValueError("output attempt head differs")
                rows.append(row)
            if rows:
                expected_chain = records._chain(rows[0]["context"])
                if chain != expected_chain or directory.name != records._json_hash(
                    chain
                ):
                    raise ValueError("output attempt chain identity differs")
                records._validated_history(rows, chain)
                latest = {records._binding(row["context"]): row for row in rows}
                states = {row["state"] for row in latest.values()}
                if "uncertain" in states:
                    active[directory.name] = "uncertain"
                elif "reserved_by_render_intent" in states:
                    active[directory.name] = "reserved_by_render_intent"
            else:
                if (
                    set(chain) != {"projectUid", "timelineUid", "caseId", "phase"}
                    or any(
                        not isinstance(value, str) or not value
                        for value in chain.values()
                    )
                    or directory.name != records._json_hash(chain)
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
    render_started = False
    found_result = False
    paused_queued_result = False
    last_render_result: tuple[Path, dict[str, Any]] | None = None
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
            if status == "uncertain" and action in {"queue_render", "start_render"}:
                if (
                    action == "queue_render"
                    and sequence == len(directories) - 1
                    and not render_started
                    and _has_attested_paused_queue(operations, result_path, verified)
                ):
                    paused_queued_result = True
                else:
                    raise _blocked(
                        "output_operation_unresolved",
                        f"{result_path} contains an uncertain native effect",
                    )
            # Authenticated synchronous returns retain uncertain target contents,
            # but cannot leave a renderer running without a render action.
            if action in {"queue_render", "start_render"}:
                if status != "refused":
                    render_pending = True
                    render_started = render_started or action == "start_render"
                    last_render_result = (result_path, verified)
            elif action == "poll_render":
                job_status = (verified.get("renderStatus") or {}).get("JobStatus")
                if status in {"complete", "partial"} and job_status in (
                    _TERMINAL_RENDER_STATES
                ):
                    render_pending = False
                    render_started = False
                    last_render_result = None
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
            if request["action"] == "start_render" and not render_started:
                # Preserve the queued job; its one-use start expired before effects.
                render_pending = False
            # Native start records are written before the first Resolve effect.
            continue

        if children:
            raise _blocked("output_operation_unresolved", str(directory))

    if host_state is not None and not found_result and not directories:
        raise _blocked(
            "output_operation_unresolved",
            f"{operations} has host state={host_state} without native evidence",
        )
    quiescent_render = last_render_result is not None and _has_attested_terminal_render(
        operations, last_render_result[0], last_render_result[1]
    )
    if render_pending and not (
        (paused_queued_result and not render_started) or quiescent_render
    ):
        raise _blocked(
            "output_render_unresolved",
            f"{operations} has a queued or started render without terminal polling",
        )


def _output_host_history_sha256(target_key: str) -> str:
    """Bind an operator's read-only observation to the exact host journal."""
    directory = OUTPUT_ATTEMPTS_ROOT / target_key
    if directory.is_symlink() or not directory.is_dir():
        raise ValueError("paused output host journal is unavailable")
    names = sorted(
        path
        for path in directory.iterdir()
        if path.name == "chain.json"
        or path.name.startswith(("entry-", "pending-", "head-"))
    )
    if not names or names[0].name != "chain.json":
        raise ValueError("paused output host journal is incomplete")
    digest = hashlib.sha256()
    for path in names:
        if path.is_symlink() or not path.is_file():
            raise ValueError("paused output host journal contains unsafe files")
        digest.update(path.name.encode("utf-8") + b"\0")
        digest.update(hashlib.sha256(_read(path)).digest())
    return digest.hexdigest()


def _has_attested_paused_queue(
    operations: Path, result_path: Path, result: dict[str, Any]
) -> bool:
    """Accept only an exact, independently observed *idle* historical queue.

    This does NOT resolve the uncertain AddRenderJob result or permit replay.
    Future operations or host-journal changes invalidate the attestation.
    """
    try:
        key = operations.parent.name
        result_sha = hashlib.sha256(_read(result_path)).hexdigest()
        host_sha = _output_host_history_sha256(key)
        base = _paused_observation_path(key, result_sha, host_sha)
        return any(
            _valid_paused_queue_observation(path, key, result_sha, host_sha, result)
            for path in _observation_candidates(base)
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _valid_paused_queue_observation(
    path: Path, key: str, result_sha: str, host_sha: str, result: dict[str, Any]
) -> bool:
    try:
        if PAUSED_OUTPUT_ROOT.is_symlink() or path.is_symlink():
            return False
        record = json.loads(_read(path, "paused native output observation"))
        if not isinstance(record, dict) or set(record) != {
            "schemaVersion",
            "targetKey",
            "sequence",
            "operationId",
            "resultSha256",
            "hostHistorySha256",
            "projectUid",
            "timelineUid",
            "observedAt",
            "observedStatuses",
            "matchingJobCount",
            "mac",
        }:
            return False
        signature = record.pop("mac")
        if not isinstance(signature, str) or not hmac.compare_digest(
            signature,
            hmac.digest(
                _paused_observation_key(key), _canonical(record), "sha256"
            ).hex(),
        ):
            return False
        if (
            record["schemaVersion"] != "vera.paused-output-observation/v1"
            or record["targetKey"] != key
            or record["sequence"] != result["sequence"]
            or record["operationId"] != result["operationId"]
            or record["resultSha256"] != result_sha
            or record["hostHistorySha256"] != host_sha
            or record["projectUid"] != result["target"]["projectUid"]
            or record["timelineUid"] != result["target"]["timelineUid"]
            or type(record["matchingJobCount"]) is not int
            or record["matchingJobCount"] != 0
            or not isinstance(record["observedAt"], str)
            or not isinstance(record["observedStatuses"], list)
            or any(
                item not in _TERMINAL_RENDER_STATES
                for item in record["observedStatuses"]
            )
        ):
            return False
        timestamp = datetime.fromisoformat(record["observedAt"])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return False
        age = datetime.now(UTC) - timestamp.astimezone(UTC)
        if age < -timedelta(seconds=30) or age >= _PAUSE_OBSERVATION_LIFETIME:
            return False
        # Unknown AddRenderJob is a queued-only effect. A started render, or
        # any additional stage after the observed tail, is never excused.
        effects = result.get("effectLedger")
        return (
            isinstance(effects, list)
            and bool(effects)
            and effects[-1].get("method") == "Project.AddRenderJob"
            and effects[-1].get("outcome") == "unknown"
            and all(row.get("method") != "Project.StartRendering" for row in effects)
        )
    except (OSError, ValueError, KeyError, TypeError):
        return False


def _terminal_observation_path(key: str, result_sha: str, host_sha: str) -> Path:
    base = _paused_observation_path(key, result_sha, host_sha)
    return base.with_name(f"{base.stem}-terminal.json")


def _new_observation_path(base: Path) -> Path:
    """Give each observation its own immutable record; never overwrite an old one."""
    return base.with_name(f"{base.stem}-obs-{os.urandom(12).hex()}.json")


def _observation_candidates(base: Path) -> list[Path]:
    """Include legacy digest-only records and independently signed renewals."""
    if PAUSED_OUTPUT_ROOT.is_symlink() or not PAUSED_OUTPUT_ROOT.is_dir():
        return []
    matches = sorted(PAUSED_OUTPUT_ROOT.glob(f"{base.stem}-obs-*.json"), reverse=True)
    if len(matches) > 4096:
        raise ValueError("paused output observations exceed safe inspection bound")
    if base.exists() or base.is_symlink():
        matches.append(base)
    return matches


def _has_attested_terminal_render(
    operations: Path, result_path: Path, result: dict[str, Any]
) -> bool:
    """Recognize an independently observed terminal *job*, not a terminal operation.

    Original queue/start history remains unchanged and its missing native poll
    is not invented. Only a signed, short-lived inspection of the exact
    historical project and job can isolate this old reservation.
    """
    if (
        result.get("action") not in {"queue_render", "start_render"}
        or result.get("status") != "complete"
        or not isinstance(result.get("jobId"), str)
        or not result["jobId"]
    ):
        return False
    try:
        directories = sorted(operations.iterdir())
        if result_path.parent not in directories:
            return False
        position = directories.index(result_path.parent)
        # Empty reserved future stages can exist, but no subsequent native
        # request, start, effect or result can have been recorded.
        if any(list(directory.iterdir()) for directory in directories[position + 1 :]):
            return False
        key = operations.parent.name
        result_sha = hashlib.sha256(_read(result_path)).hexdigest()
        host_sha = _output_host_history_sha256(key)
        base = _terminal_observation_path(key, result_sha, host_sha)
        return any(
            _valid_terminal_observation(path, key, result_sha, host_sha, result)
            for path in _observation_candidates(base)
        )
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return False


def _valid_terminal_observation(
    path: Path, key: str, result_sha: str, host_sha: str, result: dict[str, Any]
) -> bool:
    try:
        if PAUSED_OUTPUT_ROOT.is_symlink() or path.is_symlink():
            return False
        record = json.loads(_read(path, "terminal native output observation"))
        if not isinstance(record, dict) or set(record) != {
            "schemaVersion",
            "targetKey",
            "sequence",
            "operationId",
            "resultSha256",
            "hostHistorySha256",
            "projectUid",
            "timelineUid",
            "observedAt",
            "observedStatuses",
            "renderJobId",
            "renderJobStatus",
            "matchingJobCount",
            "mac",
        }:
            return False
        signature = record.pop("mac")
        if not isinstance(signature, str) or not hmac.compare_digest(
            signature,
            hmac.digest(
                _paused_observation_key(key), _canonical(record), "sha256"
            ).hex(),
        ):
            return False
        target = result["target"]
        if (
            record["schemaVersion"] != "vera.paused-terminal-render/v1"
            or record["targetKey"] != key
            or record["sequence"] != result["sequence"]
            or record["operationId"] != result["operationId"]
            or record["resultSha256"] != result_sha
            or record["hostHistorySha256"] != host_sha
            or record["projectUid"] != target["projectUid"]
            or record["timelineUid"] != target["timelineUid"]
            or record["renderJobId"] != result["jobId"]
            or record["renderJobStatus"] not in _TERMINAL_RENDER_STATES
            or type(record["matchingJobCount"]) is not int
            or record["matchingJobCount"] != 1
            or not isinstance(record["observedAt"], str)
            or not isinstance(record["observedStatuses"], list)
            or record["renderJobStatus"] not in record["observedStatuses"]
            or any(
                state not in _TERMINAL_RENDER_STATES
                for state in record["observedStatuses"]
            )
        ):
            return False
        timestamp = datetime.fromisoformat(record["observedAt"])
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            return False
        age = datetime.now(UTC) - timestamp.astimezone(UTC)
        return -timedelta(seconds=30) <= age < _PAUSE_OBSERVATION_LIFETIME
    except (OSError, ValueError, KeyError, TypeError, IndexError):
        return False


def _canonical(value: dict[str, Any]) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _paused_observation_key(target_key: str) -> bytes:
    """Reuse the private host receipt key, never include it in observations."""
    path = OUTPUT_ATTEMPTS_ROOT / target_key / "receipts" / "key"
    metadata = path.stat(follow_symlinks=False)
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) & 0o077:
        raise ValueError("paused output signing key is not private")
    key = _read(path, "paused observation signing key")
    if len(key) != 32:
        raise ValueError("paused output signing key has wrong length")
    return key


def _paused_observation_path(key: str, result_sha: str, host_sha: str) -> Path:
    if not all(_HEX64.fullmatch(value) for value in (key, result_sha, host_sha)):
        raise ValueError("paused observation identity is malformed")
    return PAUSED_OUTPUT_ROOT / f"{key}-{result_sha}-{host_sha}.json"


def _locally_attested_paused_queue(key: str) -> bool:
    """Small installed-runtime guard for a *previously* authenticated pause.

    The full verifier is host-only and unavailable in older installed bundles.
    Walk the exact local result/request digest chain and validate its separate
    read-only observation; never substitute this for host preflight before a
    new dispatch. No external source or historical render is opened here.
    """
    if not _HEX64.fullmatch(key):
        return False
    operations = OUTPUT_TARGETS_ROOT / key / "operations"
    try:
        if operations.is_symlink() or not operations.is_dir():
            return False
        directories = sorted(operations.iterdir())
        if not directories:
            return False
        prior_sha: str | None = None
        last: dict[str, Any] | None = None
        last_path: Path | None = None
        trailing_empty = False
        for sequence, directory in enumerate(directories):
            if (
                directory.is_symlink()
                or not directory.is_dir()
                or directory.name != f"{sequence:08d}"
            ):
                return False
            result_path = directory / "result.json"
            if not result_path.exists() and not result_path.is_symlink():
                if (
                    not last
                    or not result_path.parent.is_dir()
                    or any(directory.iterdir())
                ):
                    return False
                trailing_empty = True
                continue
            if trailing_empty:
                return False
            raw = _read(result_path, "paused output result")
            result = json.loads(raw)
            if (
                not isinstance(result, dict)
                or result.get("sequence") != sequence
                or (sequence and result.get("priorResultSha256") != prior_sha)
                or (last is not None and last.get("status") != "complete")
                or (
                    last is not None
                    and last.get("action") in {"queue_render", "start_render"}
                    and not (
                        last.get("action") == "queue_render"
                        and result.get("action") == "start_render"
                        and last.get("jobId") == result.get("jobId")
                    )
                )
            ):
                return False
            request_raw = _read(directory / "request.json", "paused output request")
            if hashlib.sha256(request_raw).hexdigest() != result.get("requestSha256"):
                return False
            start = json.loads(
                _read(directory / "native-start.json", "paused output start")
            )
            if (
                not isinstance(start, dict)
                or start.get("requestSha256") != result.get("requestSha256")
                or start.get("operationId") != result.get("operationId")
            ):
                return False
            prior_sha = hashlib.sha256(raw).hexdigest()
            last = result
            last_path = result_path
        if last is None or last_path is None:
            return False
        if last.get("action") == "queue_render" and last.get("status") == "uncertain":
            return not trailing_empty and _has_attested_paused_queue(
                operations, last_path, last
            )
        if last.get("action") in {"queue_render", "start_render"}:
            return _has_attested_terminal_render(operations, last_path, last)
        return False
    except (OSError, ValueError, KeyError, TypeError):
        return False


def observe_paused_queue(result_path: Path) -> Path:
    """Attest an exact, quiescent historical queue without resuming its work.

    Intended for a producer-authorized recovery after an agent was stopped.
    Observes the existing Resolve project and render jobs, never creates,
    starts, deletes, saves, or claims completion of an old operation. Only a
    queued-only UNKNOWN with no current nonterminal jobs can be isolated.
    """
    import DaVinciResolveScript as dvr  # type: ignore[import-not-found]

    result_path = result_path.absolute()
    if result_path.name != "result.json":
        raise ValueError("expected an existing native result")
    operation = result_path.parent
    operations = operation.parent
    key = operations.parent.name
    if (
        operations.name != "operations"
        or operations.parent.parent != OUTPUT_TARGETS_ROOT
        or not _HEX64.fullmatch(key)
        or result_path.is_symlink()
        or operation.is_symlink()
        or operations.is_symlink()
        or operations.parent.is_symlink()
    ):
        raise ValueError("native result is not in the exact private target store")
    with native_owner(output_lane=True):
        native = importlib.import_module(".qualification_output_native_v2", __package__)
        raw = _read(result_path)
        result_sha = hashlib.sha256(raw).hexdigest()
        result = native.verify_native_result(result_path, result_sha)
        if (
            result.get("status") != "uncertain"
            or result.get("action") != "queue_render"
            or result.get("sequence") != int(operation.name)
            or result.get("operationId") is None
        ):
            raise ValueError("only an uncertain queued-only operation may be observed")
        directories = sorted(operations.iterdir())
        if (
            not directories
            or directories[-1] != operation
            or len(directories) != result["sequence"] + 1
        ):
            raise ValueError("native operation tail changed")
        for sequence, directory in enumerate(directories[:-1]):
            if directory.name != f"{sequence:08d}":
                raise ValueError("native history sequence changed")
            prior_path = directory / "result.json"
            prior = _read(prior_path)
            verified_prior = native.verify_native_result(
                prior_path, hashlib.sha256(prior).hexdigest()
            )
            if verified_prior.get("status") != "complete":
                raise ValueError("an earlier native stage is unresolved")
        effects = result.get("effectLedger")
        if (
            not isinstance(effects, list)
            or not effects
            or effects[-1].get("method") != "Project.AddRenderJob"
            or effects[-1].get("outcome") != "unknown"
            or any(item.get("method") == "Project.StartRendering" for item in effects)
        ):
            raise ValueError("old effect is not exclusively a queued-only result")
        resolve = dvr.scriptapp("Resolve")
        if not resolve:
            raise ValueError("local Resolve scripting is unavailable")
        identity = result.get("nativeIdentity", {})
        if resolve.GetProductName() != identity.get("product") or list(
            resolve.GetVersion()
        ) != identity.get("version"):
            raise ValueError("installed Resolve identity differs")
        manager = resolve.GetProjectManager()
        if manager is None:
            raise ValueError("Resolve project manager is unavailable")
        target = result["target"]
        project = manager.GetCurrentProject()
        # Never switch projects: the current project may have unsaved edits or
        # an active render which LoadProject could disturb. The operator must
        # select the exact historical target before this read-only check.
        if (
            project is None
            or project.GetUniqueId() != target["projectUid"]
            or project.GetName() != target["projectName"]
        ):
            raise ValueError("original Resolve project UID was not observed")
        timeline = project.GetCurrentTimeline()
        if (
            timeline is None
            or timeline.GetUniqueId() != target["timelineUid"]
            or timeline.GetName() != target["timelineName"]
        ):
            raise ValueError("original Resolve timeline UID was not observed")
        if project.IsRenderingInProgress() is not False:
            raise ValueError("the original project has an active/unknown render")
        request_path = Path(result["requestPath"])
        request_raw = _read(request_path)
        if hashlib.sha256(request_raw).hexdigest() != result["requestSha256"]:
            raise ValueError("old native request changed")
        request = json.loads(request_raw)
        output = Path(request["payload"]["outputPath"])
        jobs = project.GetRenderJobList()
        if type(jobs) not in {list, tuple}:
            raise ValueError("the render job inventory is unavailable")
        statuses: list[str] = []
        matching = 0
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("JobId"), str):
                raise ValueError("a render job lacks a usable identity")
            observed = project.GetRenderJobStatus(job["JobId"])
            state = observed.get("JobStatus") if isinstance(observed, dict) else None
            if state not in _TERMINAL_RENDER_STATES:
                raise ValueError("an original render job is not terminal")
            statuses.append(state)
            matching += int(
                job.get("TargetDir") == str(output.parent)
                and job.get("OutputFilename") == output.name
            )
        if matching:
            raise ValueError("an ambiguous queued render job still exists")
        if hashlib.sha256(_read(result_path)).hexdigest() != result_sha:
            raise ValueError("native result changed during observation")
        host_sha = _output_host_history_sha256(key)
        record = {
            "schemaVersion": "vera.paused-output-observation/v1",
            "targetKey": key,
            "sequence": result["sequence"],
            "operationId": result["operationId"],
            "resultSha256": result_sha,
            "hostHistorySha256": host_sha,
            "projectUid": target["projectUid"],
            "timelineUid": target["timelineUid"],
            "observedAt": datetime.now(UTC).isoformat(),
            "observedStatuses": statuses,
            "matchingJobCount": matching,
        }
        record["mac"] = hmac.digest(
            _paused_observation_key(key), _canonical(record), "sha256"
        ).hex()
        if PAUSED_OUTPUT_ROOT.is_symlink() or PAUSED_OUTPUT_ROOT.parent.is_symlink():
            raise ValueError("paused-output observation directory is unsafe")
        PAUSED_OUTPUT_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = _new_observation_path(
            _paused_observation_path(key, result_sha, host_sha)
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(PAUSED_OUTPUT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return path


def observe_terminal_render(result_path: Path) -> Path:
    """Read only: isolate a retained queue/start after its *exact* job is terminal.

    A missing poll or prior render intent remains historical UNKNOWN. The
    original project/timeline must already be selected by the operator; this
    function never loads a project or mutates any Resolve state.
    """
    import DaVinciResolveScript as dvr

    result_path = result_path.absolute()
    operation = result_path.parent
    operations = operation.parent
    key = operations.parent.name
    if (
        result_path.name != "result.json"
        or operations.name != "operations"
        or operations.parent.parent != OUTPUT_TARGETS_ROOT
        or not _HEX64.fullmatch(key)
        or any(
            path.is_symlink()
            for path in (result_path, operation, operations, operations.parent)
        )
    ):
        raise ValueError("native result is not in the exact private target store")
    with native_owner(output_lane=True):
        native = importlib.import_module(".qualification_output_native_v2", __package__)
        raw = _read(result_path, "terminal render result")
        result_sha = hashlib.sha256(raw).hexdigest()
        result = native.verify_native_result(result_path, result_sha)
        if (
            result.get("action") not in {"queue_render", "start_render"}
            or result.get("status") != "complete"
            or not isinstance(result.get("jobId"), str)
            or not result["jobId"]
            or type(result.get("sequence")) is not int
            or operation.name != f"{result['sequence']:08d}"
        ):
            raise ValueError(
                "only a completed queue/start with known job ID can be observed"
            )
        directories = sorted(operations.iterdir())
        if operation not in directories:
            raise ValueError("native render operation missing from history")
        previous: dict[str, Any] | None = None
        for index, directory in enumerate(directories):
            if directory.is_symlink() or directory.name != f"{index:08d}":
                raise ValueError("native history sequence changed")
            if index > result["sequence"]:
                if any(directory.iterdir()):
                    raise ValueError(
                        "subsequent native request or effect is unresolved"
                    )
                continue
            record_path = directory / "result.json"
            prior_raw = _read(record_path, "earlier native render result")
            checked = native.verify_native_result(
                record_path, hashlib.sha256(prior_raw).hexdigest()
            )
            if index < result["sequence"] and checked.get("status") != "complete":
                raise ValueError("an earlier native stage is unresolved")
            if index == result["sequence"] - 1:
                previous = checked
            if index < result["sequence"] and checked.get("action") == "start_render":
                raise ValueError("an earlier render start remains unpolled")
        if result["action"] == "start_render" and (
            previous is None
            or previous.get("action") != "queue_render"
            or previous.get("jobId") != result["jobId"]
        ):
            raise ValueError("render start is not bound to its exact queued job")
        ledger = result.get("effectLedger")
        expected_effect = (
            "Project.StartRendering"
            if result["action"] == "start_render"
            else "Project.AddRenderJob"
        )
        if not isinstance(ledger, list) or not any(
            isinstance(item, dict)
            and item.get("method") == expected_effect
            and item.get("outcome") != "unknown"
            for item in ledger
        ):
            raise ValueError("native effect ledger does not prove the known operation")
        resolve = dvr.scriptapp("Resolve")
        if not resolve:
            raise ValueError("local Resolve scripting is unavailable")
        identity = result.get("nativeIdentity", {})
        if resolve.GetProductName() != identity.get("product") or list(
            resolve.GetVersion()
        ) != identity.get("version"):
            raise ValueError("installed Resolve identity differs")
        manager = resolve.GetProjectManager()
        project = manager.GetCurrentProject() if manager is not None else None
        target = result["target"]
        if (
            project is None
            or project.GetUniqueId() != target["projectUid"]
            or project.GetName() != target["projectName"]
        ):
            raise ValueError("original Resolve project UID was not observed")
        timeline = project.GetCurrentTimeline()
        if (
            timeline is None
            or timeline.GetUniqueId() != target["timelineUid"]
            or timeline.GetName() != target["timelineName"]
        ):
            raise ValueError("original Resolve timeline UID was not observed")
        if project.IsRenderingInProgress() is not False:
            raise ValueError("the original project has an active/unknown render")
        jobs = project.GetRenderJobList()
        if type(jobs) not in {list, tuple}:
            raise ValueError("render job inventory unavailable")
        statuses: list[str] = []
        matching = 0
        matching_status = ""
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("JobId"), str):
                raise ValueError("a render job lacks a usable identity")
            current_status = project.GetRenderJobStatus(job["JobId"])
            status = (
                current_status.get("JobStatus")
                if isinstance(current_status, dict)
                else None
            )
            if status not in _TERMINAL_RENDER_STATES:
                raise ValueError("a historical render job is still live/unknown")
            statuses.append(status)
            if job["JobId"] == result["jobId"]:
                matching += 1
                matching_status = status
        if matching != 1:
            raise ValueError("exact prior render job is not terminal and unique")
        if hashlib.sha256(_read(result_path)).hexdigest() != result_sha:
            raise ValueError("native result changed during observation")
        host_sha = _output_host_history_sha256(key)
        record = {
            "schemaVersion": "vera.paused-terminal-render/v1",
            "targetKey": key,
            "sequence": result["sequence"],
            "operationId": result["operationId"],
            "resultSha256": result_sha,
            "hostHistorySha256": host_sha,
            "projectUid": target["projectUid"],
            "timelineUid": target["timelineUid"],
            "observedAt": datetime.now(UTC).isoformat(),
            "observedStatuses": statuses,
            "renderJobId": result["jobId"],
            "renderJobStatus": matching_status,
            "matchingJobCount": matching,
        }
        record["mac"] = hmac.digest(
            _paused_observation_key(key), _canonical(record), "sha256"
        ).hex()
        if PAUSED_OUTPUT_ROOT.is_symlink() or PAUSED_OUTPUT_ROOT.parent.is_symlink():
            raise ValueError("paused-output observation directory is unsafe")
        PAUSED_OUTPUT_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = _new_observation_path(
            _terminal_observation_path(key, result_sha, host_sha)
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write((json.dumps(record, sort_keys=True) + "\n").encode("utf-8"))
            stream.flush()
            os.fsync(stream.fileno())
        directory_fd = os.open(PAUSED_OUTPUT_ROOT, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return path


def _read(path: Path, label: str = "ownership record") -> bytes:
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only host observation of one paused historical output queue"
    )
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--observe-paused-queue", type=Path)
    selector.add_argument("--observe-terminal-render", type=Path)
    args = parser.parse_args()
    if args.observe_paused_queue is not None:
        print(observe_paused_queue(args.observe_paused_queue))
    else:
        print(observe_terminal_render(args.observe_terminal_render))


if __name__ == "__main__":
    main()
