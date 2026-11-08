"""Private, operator-invoked #381 development harness (no service or pairing).

The operator controls a separate 0600 policy that pins exactly one grant and
the filesystem roots. The untrusted request cannot nominate or approve roots.
This is NOT an authenticated browser/companion endpoint; do not invoke it with
request-supplied command-line arguments on behalf of remote clients.
"""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from collections.abc import Sequence
from contextlib import ExitStack
from pathlib import Path
from typing import Any, Never, cast

from .local_media_import import (
    Clone,
    Decoder,
    FFmpegDecoder,
    import_local_media,
    reverify_materialized_source,
)
from .local_media_import_model import (
    ClipUse,
    ImportModelError,
    LocalImportApproval,
    MediaKind,
)

_MAX_JSON_BYTES = 65_536
_REQUEST_FIELDS = {
    "schemaVersion",
    "projectId",
    "importId",
    "assetId",
    "mediaReferenceId",
    "sourceRootId",
    "sourceSegments",
    "expectedContentHash",
    "expectedSizeBytes",
    "maxSizeBytes",
    "minimumFreeBytes",
    "kind",
    "requestedMode",
}
_CLIP_FIELDS = {
    "startFrame",
    "endFrame",
    "handleBeforeFrames",
    "handleAfterFrames",
}
_POLICY_FIELDS = {
    "schemaVersion",
    "sourceRootId",
    "sourceRoot",
    "projectRoot",
    "stateRoot",
    "operatorApproved",
    "grant",
}


class _SafeParser(argparse.ArgumentParser):
    def error(self, message: str) -> Never:
        # argparse's default interpolates supplied, possibly private path text.
        raise ImportModelError("invalid_approval")


def _absolute(value: object) -> Path:
    if not isinstance(value, str):
        raise ImportModelError("invalid_approval")
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts:
        raise ImportModelError("invalid_approval")
    return path


def _object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ImportModelError("invalid_approval")
        result[key] = value
    return result


def _bad_number(_: str) -> None:
    raise ImportModelError("invalid_approval")


def _file_identity(value: os.stat_result) -> tuple[int, int, int, int, int]:
    return (
        value.st_dev,
        value.st_ino,
        value.st_size,
        value.st_mtime_ns,
        value.st_ctime_ns,
    )


def _load_private_json(value: object) -> dict[str, Any]:
    path = _absolute(value)
    # Walk each parent component using no-follow directory descriptors.
    with ExitStack() as stack:
        fd = os.open("/", os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, fd)
        for component in path.parts[1:-1]:
            fd = os.open(
                component,
                os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC,
                dir_fd=fd,
            )
            stack.callback(os.close, fd)
        file_fd = os.open(
            path.name,
            os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK,
            dir_fd=fd,
        )
        stack.callback(os.close, file_fd)
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or before.st_uid != os.getuid()
            or before.st_mode & 0o077
            or not 0 < before.st_size <= _MAX_JSON_BYTES
        ):
            raise ImportModelError("permission_denied")
        chunks: list[bytes] = []
        remaining = before.st_size
        while remaining:
            chunk = os.read(file_fd, remaining)
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        after = os.fstat(file_fd)
        if len(content) != before.st_size or _file_identity(after) != _file_identity(
            before
        ):
            raise ImportModelError("invalid_approval")
    try:
        parsed: object = json.loads(
            content.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_bad_number,
        )
    except (UnicodeError, ValueError, TypeError, RecursionError) as error:
        raise ImportModelError("invalid_approval") from error
    if not isinstance(parsed, dict):
        raise ImportModelError("invalid_approval")
    return parsed


def _exact_keys(value: object, expected: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ImportModelError("invalid_approval")
    return value


def _approval(policy: dict[str, Any], request: dict[str, Any]) -> LocalImportApproval:
    _exact_keys(policy, _POLICY_FIELDS)
    if (
        policy["schemaVersion"] != "vera-local-import-local-policy/v1"
        or policy["operatorApproved"] is not True
    ):
        raise ImportModelError("approval_required")
    kind = request.get("kind")
    expected = _REQUEST_FIELDS | ({"clipUse"} if kind == "clip" else set())
    _exact_keys(request, expected)
    if request["schemaVersion"] != "vera-local-import-request/v1":
        raise ImportModelError("invalid_approval")
    # Comparison is encoded rather than Python dict equality: bool != int in
    # JSON, and an untrusted request must match every operator-granted field.
    if json.dumps(policy["grant"], sort_keys=True) != json.dumps(
        request, sort_keys=True
    ):
        raise ImportModelError("permission_denied")
    if request["sourceRootId"] != policy["sourceRootId"]:
        raise ImportModelError("permission_denied")
    segments = request["sourceSegments"]
    if not isinstance(segments, list):
        raise ImportModelError("invalid_locator")
    clip = None
    if kind == "clip":
        fields = _exact_keys(request["clipUse"], _CLIP_FIELDS)
        clip = ClipUse(
            start_frame=fields["startFrame"],
            end_frame=fields["endFrame"],
            handle_before_frames=fields["handleBeforeFrames"],
            handle_after_frames=fields["handleAfterFrames"],
        )
    if kind not in ("image", "clip"):
        raise ImportModelError("unsupported_media")
    return LocalImportApproval(
        project_id=request["projectId"],
        import_id=request["importId"],
        asset_id=request["assetId"],
        media_reference_id=request["mediaReferenceId"],
        source_root_id=request["sourceRootId"],
        source_root=_absolute(policy["sourceRoot"]),
        project_root=_absolute(policy["projectRoot"]),
        source_segments=tuple(segments),
        expected_content_hash=request["expectedContentHash"],
        expected_size_bytes=request["expectedSizeBytes"],
        max_size_bytes=request["maxSizeBytes"],
        minimum_free_bytes=request["minimumFreeBytes"],
        kind=cast(MediaKind, kind),
        clip_use=clip,
        requested_mode=request["requestedMode"],
    )


def run(
    argv: Sequence[str] | None = None,
    *,
    decoder: Decoder | None = None,
    clone: Clone | None = None,
) -> int:
    """Return bounded exit status. Injections are for in-process tests only."""
    try:
        parser = _SafeParser(description="Operator-only synthetic local media import")
        parser.add_argument(
            "--policy", required=True, help="private local operator grant JSON"
        )
        parser.add_argument(
            "--request", required=True, help="private proposed request JSON"
        )
        parser.add_argument(
            "--verify-existing",
            action="store_true",
            help="read-only rehash/reprobe of an already imported project source",
        )
        args = parser.parse_args(argv)
        policy = _load_private_json(args.policy)
        request = _load_private_json(args.request)
        approval = _approval(policy, request)
        state_root = _absolute(policy["stateRoot"])
        # The exact operator-pinned object is the only local grant. This is
        # explicitly NOT a remote actor authentication or generic permission.
        authorize = lambda candidate: candidate == approval  # noqa: E731
        actual_decoder = decoder if decoder is not None else FFmpegDecoder()
        if args.verify_existing:
            result = reverify_materialized_source(
                approval,
                state_root=state_root,
                authorize=authorize,
                decoder=actual_decoder,
            )
            status = "verified-unqualified"
            import_id = result.import_id
        else:
            execution = import_local_media(
                approval,
                state_root=state_root,
                authorize=authorize,
                decoder=actual_decoder,
                clone=clone,
            )
            status = execution.status
            import_id = execution.result.import_id
        print(
            json.dumps(
                {
                    "status": status,
                    "importId": import_id,
                    "buildQualification": "unqualified",
                },
                sort_keys=True,
            )
        )
        return 0
    except ImportModelError as error:
        print(json.dumps({"status": "refused", "code": error.code}, sort_keys=True))
        return 3 if error.code in ("needs_inspection", "incomplete_attempt") else 2
    except (OSError, ValueError, TypeError, OverflowError, RecursionError):
        # No OS exception text, traceback, private paths or raw decoder stderr.
        print('{"code":"io_failure","status":"refused"}')
        return 4


def main() -> None:
    sys.exit(run())


if __name__ == "__main__":
    main()
