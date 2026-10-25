"""Verified v2 package delivery through the injected Resolve scripting API.

This module deliberately uses only the standard library plus the already accepted
v1 Studio adapter.  The package's OpenTimelineIO file is hash-bound, never loaded.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import platform
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from fractions import Fraction
from itertools import pairwise
from pathlib import Path, PurePosixPath
from typing import Any, TypeGuard, cast

from .studio_spike import _project_settings, _still_source_frame_duration
from .workflow_delivery import (
    SUPPORTED_IDENTITIES,
)
from .workflow_delivery import (
    PublicResolveAdapter as AcceptedDeliveryAdapter,
)
from .workflow_package import SOURCE_PINS

ATTESTATION_SCHEMA_V2 = "vera-injected-delivery-attestation/v2"
VIEW_SCHEMA_V2 = "resolve-native-view/v2"
RECEIPT_SCHEMA_V2 = "v2-package-verification/v1"
DELIVERY_VERSION = "2"
BUILD_FILE_NAMES = (
    "timeline-manifest.json",
    "build-report.json",
    "script-document.json",
    "compiler-dependencies.json",
    "delivery-view.json",
    "timeline.otio",
    "package-verification.json",
)
ATTESTATION_KEYS = {
    "schemaVersion",
    "status",
    "sourcePins",
    "packageDir",
    "buildId",
    "projectName",
    "timelineName",
    "verifiedAt",
    "verifier",
    "verification",
    "packageFiles",
    "files",
}
RECEIPT_KEYS = {
    "schemaVersion",
    "status",
    "buildId",
    "manifestId",
    "reportId",
    "documentId",
    "eventCount",
    "manifestEventCount",
    "markerCount",
    "mediaCount",
    "fileHashes",
    "sourceHashes",
    "preparations",
}
PREPARATION_RECEIPT_KEYS = {
    "path",
    "receiptHash",
    "bindingHash",
    "mappingHash",
    "profileHash",
    "toolHash",
    "originalHash",
    "deliveredHash",
    "originalProbeHash",
    "deliveredProbeHash",
}
_RAW_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CONTENT_HASH = re.compile(r"sha256:[0-9a-f]{64}\Z")
_UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")
_TARGET_SUFFIX = re.compile(r"[0-9a-f]{12}\Z")
_SUPPORTED_INTEGER_RATES = {(24, 1), (25, 1), (30, 1)}
_QUALIFIED_FRACTIONAL_RATE = (24000, 1001)
_SUPPORTED_PACKAGE_RATES = {*_SUPPORTED_INTEGER_RATES, _QUALIFIED_FRACTIONAL_RATE}
_MARKER_COLORS = {
    "BLUE": "Blue",
    "CYAN": "Cyan",
    "GREEN": "Green",
    "ORANGE": "Orange",
    "PINK": "Pink",
    "PURPLE": "Purple",
    "RED": "Red",
    "YELLOW": "Yellow",
}


class WorkflowV2Error(ValueError):
    """The pinned v2 handoff is invalid or cannot be delivered safely."""


@dataclass(frozen=True)
class VerifiedPackageV2:
    root: Path
    manifest: dict[str, Any]
    view: dict[str, Any]
    attestation: dict[str, Any]


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _strict_object(payload: bytes, label: str) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            if key in result:
                raise WorkflowV2Error(f"{label} contains duplicate JSON keys")
            result[key] = value
        return result

    def invalid_constant(_value: str) -> None:
        raise WorkflowV2Error(f"{label} contains a non-finite JSON number")

    def finite_float(value: str) -> float:
        parsed = float(value)
        if not math.isfinite(parsed):
            raise WorkflowV2Error(f"{label} contains a non-finite JSON number")
        return parsed

    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=invalid_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise WorkflowV2Error(f"{label} is not valid UTF-8 JSON") from error
    if not isinstance(value, dict):
        raise WorkflowV2Error(f"{label} must be one JSON object")
    return cast(dict[str, Any], value)


def _regular_absolute(path: Path, label: str, *, directory: bool) -> Path:
    absolute = Path(os.path.abspath(os.fspath(path)))
    for candidate in (absolute, *absolute.parents):
        try:
            info = candidate.lstat()
        except OSError as error:
            raise WorkflowV2Error(f"{label} path is unavailable") from error
        if stat.S_ISLNK(info.st_mode):
            raise WorkflowV2Error(f"{label} path contains a symbolic link")
    try:
        info = absolute.lstat()
    except OSError as error:
        raise WorkflowV2Error(f"{label} path is unavailable") from error
    wanted = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if not wanted:
        raise WorkflowV2Error(
            f"{label} must be a regular {'directory' if directory else 'file'}"
        )
    return absolute


def _read_regular(path: Path, label: str, *, max_bytes: int | None = None) -> bytes:
    _regular_absolute(path, label, directory=False)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise WorkflowV2Error(f"{label} could not be opened safely") from error
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise WorkflowV2Error(f"{label} is not a regular file")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if max_bytes is not None and total > max_bytes:
                raise WorkflowV2Error(f"{label} exceeds the supported size")
            chunks.append(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ) or total != before.st_size:
            raise WorkflowV2Error(f"{label} changed while it was read")
        return b"".join(chunks)
    finally:
        os.close(descriptor)


def _hash_regular(path: Path, label: str) -> tuple[str, int]:
    _regular_absolute(path, label, directory=False)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(path, flags)
    except OSError as error:
        raise WorkflowV2Error(f"{label} could not be opened safely") from error
    digest = hashlib.sha256()
    total = 0
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise WorkflowV2Error(f"{label} is not a regular file")
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
            total += len(chunk)
        after = os.fstat(descriptor)
        if (before.st_dev, before.st_ino, before.st_size) != (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ) or total != before.st_size:
            raise WorkflowV2Error(f"{label} changed while it was hashed")
        return digest.hexdigest(), total
    finally:
        os.close(descriptor)


def _inventory(root: Path) -> list[dict[str, Any]]:
    _regular_absolute(root, "package", directory=True)
    entries: list[dict[str, Any]] = []
    try:
        paths = sorted(
            root.rglob("*"), key=lambda item: item.relative_to(root).as_posix()
        )
    except OSError as error:
        raise WorkflowV2Error("package inventory could not be read") from error
    for path in paths:
        try:
            info = path.lstat()
        except OSError as error:
            raise WorkflowV2Error("package changed during inventory") from error
        if stat.S_ISLNK(info.st_mode):
            raise WorkflowV2Error("package contains a symbolic link")
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode):
            raise WorkflowV2Error("package contains a non-regular entry")
        digest, size = _hash_regular(path, "package entry")
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": digest,
                "sizeBytes": size,
            }
        )
    if not entries:
        raise WorkflowV2Error("package is empty")
    return entries


def _safe_relative(value: object, label: str) -> str:
    if not isinstance(value, str) or not value or "\\" in value:
        raise WorkflowV2Error(f"{label} must be a package-relative POSIX path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise WorkflowV2Error(f"{label} must stay inside the package")
    return path.as_posix()


def _package_path(root: Path, relative: object, label: str) -> Path:
    safe = _safe_relative(relative, label)
    path = root.joinpath(*PurePosixPath(safe).parts)
    _regular_absolute(path, label, directory=False)
    return path


def _read_package_json(root: Path, relative: str) -> dict[str, Any]:
    return _strict_object(
        _read_regular(
            _package_path(root, relative, "package file"),
            "package JSON",
            max_bytes=128 * 1024 * 1024,
        ),
        "package JSON",
    )


def _closed(value: object, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        raise WorkflowV2Error(f"{label} has unsupported fields")
    return cast(dict[str, Any], value)


def _raw_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _RAW_HASH.fullmatch(value) is None:
        raise WorkflowV2Error(f"{label} is not a raw SHA-256 digest")
    return value


def _content_hash(value: object, label: str) -> str:
    if not isinstance(value, str) or _CONTENT_HASH.fullmatch(value) is None:
        raise WorkflowV2Error(f"{label} is not a sha256 content hash")
    return value


def _positive_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _nonnegative_int(value: object) -> TypeGuard[int]:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _frame_range(value: object, label: str) -> tuple[int, int]:
    if not isinstance(value, Mapping):
        raise WorkflowV2Error(f"{label} is missing")
    start = value.get("startFrame")
    duration = value.get("durationFrames")
    if not _nonnegative_int(start) or not _positive_int(duration):
        raise WorkflowV2Error(f"{label} is not a positive frame range")
    return start, duration


def _manifest_range(value: object, label: str) -> tuple[int, int]:
    if value is None:
        raise WorkflowV2Error(f"{label} is absent")
    if not isinstance(value, Mapping):
        raise WorkflowV2Error(f"{label} is malformed")
    start = value.get("startFrame")
    end = value.get("endFrame")
    if not _nonnegative_int(start) or not _positive_int(end):
        raise WorkflowV2Error(f"{label} is malformed")
    if end <= start:
        raise WorkflowV2Error(f"{label} is malformed")
    return start, end - start


def _frame_rate(timeline: Mapping[str, Any]) -> tuple[int, int]:
    value = timeline.get("frameRate")
    if not isinstance(value, Mapping):
        raise WorkflowV2Error("timeline frame rate is missing")
    numerator, denominator = value.get("numerator"), value.get("denominator")
    if not _positive_int(numerator) or not _positive_int(denominator):
        raise WorkflowV2Error("timeline frame rate is malformed")
    return numerator, denominator


def _parse_timestamp(value: object) -> None:
    from datetime import datetime

    if not isinstance(value, str):
        raise WorkflowV2Error("attestation timestamp is missing")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as error:
        raise WorkflowV2Error("attestation timestamp is invalid") from error
    if parsed.utcoffset() is None:
        raise WorkflowV2Error("attestation timestamp must include a timezone")


def _load_attestation(path: Path, expected_sha256: str) -> tuple[dict[str, Any], Path]:
    if (
        not isinstance(expected_sha256, str)
        or _RAW_HASH.fullmatch(expected_sha256) is None
    ):
        raise WorkflowV2Error("expected attestation digest is malformed")
    absolute = _regular_absolute(path, "attestation", directory=False)
    payload = _read_regular(absolute, "attestation", max_bytes=16 * 1024 * 1024)
    if _digest(payload) != expected_sha256:
        raise WorkflowV2Error("attestation digest mismatch")
    value = _strict_object(payload, "attestation")
    _closed(value, ATTESTATION_KEYS, "attestation")
    if (
        value["schemaVersion"] != ATTESTATION_SCHEMA_V2
        or value["status"] != "ready_to_import"
        or value["sourcePins"] != SOURCE_PINS
    ):
        raise WorkflowV2Error("attestation is not an accepted v2 handoff")
    root_value = value["packageDir"]
    if not isinstance(root_value, str) or not os.path.isabs(root_value):
        raise WorkflowV2Error("attestation packageDir must be absolute")
    root = _regular_absolute(Path(root_value), "package", directory=True)
    if str(root) != root_value or root == Path(root.anchor):
        raise WorkflowV2Error("attestation packageDir must be canonical and non-root")
    if absolute.is_relative_to(root):
        raise WorkflowV2Error("attestation must be outside the package")
    _parse_timestamp(value["verifiedAt"])
    verifier = _closed(
        value["verifier"],
        {"implementation", "pythonVersion", "sourceHashes"},
        "verifier",
    )
    if (
        verifier["implementation"] != "CPython"
        or verifier["pythonVersion"] != "3.12.14"
    ):
        raise WorkflowV2Error("attestation verifier is not the pinned runtime")
    source_hashes = verifier["sourceHashes"]
    if not isinstance(source_hashes, dict) or not source_hashes:
        raise WorkflowV2Error("attestation source hashes are missing")
    for source_path, digest in source_hashes.items():
        _safe_relative(source_path, "verifier source path")
        _raw_hash(digest, "verifier source hash")
    build_id = value["buildId"]
    if not isinstance(build_id, str) or _UUID.fullmatch(build_id) is None:
        raise WorkflowV2Error("attestation build identity is invalid")
    name = value["projectName"]
    if not isinstance(name, str) or not name.startswith(f"VERA Delivery {build_id} "):
        raise WorkflowV2Error("attestation target name is invalid")
    suffix = name.removeprefix(f"VERA Delivery {build_id} ")
    if _TARGET_SUFFIX.fullmatch(suffix) is None or value["timelineName"] != name:
        raise WorkflowV2Error("attestation target names do not match")
    return value, root


def load_verified_package_v2(path: Path, expected_sha256: str) -> VerifiedPackageV2:
    """Load a closed v2 handoff after independently rehashing all package bytes."""
    attestation_path = Path(path)
    attestation, root = _load_attestation(attestation_path, expected_sha256)
    build_id = cast(str, attestation["buildId"])
    build_relative = f"Builds/{build_id}"
    expected_file_map = attestation["files"]
    if not isinstance(expected_file_map, dict) or set(expected_file_map) != set(
        BUILD_FILE_NAMES
    ):
        raise WorkflowV2Error("attestation file digest map is incomplete")
    for digest in expected_file_map.values():
        _raw_hash(digest, "attested package file hash")

    inventory = _inventory(root)
    if attestation["packageFiles"] != inventory:
        raise WorkflowV2Error("package inventory changed after verification")
    inventory_by_path = {entry["path"]: entry for entry in inventory}
    receipt_rel = f"{build_relative}/package-verification.json"
    for filename in BUILD_FILE_NAMES:
        relative = f"{build_relative}/{filename}"
        entry = inventory_by_path.get(relative)
        if entry is None or entry["sha256"] != expected_file_map[filename]:
            raise WorkflowV2Error("attested package file bytes do not match")

    manifest = _read_package_json(root, f"{build_relative}/timeline-manifest.json")
    report = _read_package_json(root, f"{build_relative}/build-report.json")
    document = _read_package_json(root, f"{build_relative}/script-document.json")
    dependencies = _read_package_json(
        root, f"{build_relative}/compiler-dependencies.json"
    )
    view = _read_package_json(root, f"{build_relative}/delivery-view.json")
    receipt = _read_package_json(root, receipt_rel)
    _closed(receipt, RECEIPT_KEYS, "package receipt")
    if (
        manifest.get("schemaVersion") != "timeline-manifest/v2"
        or report.get("schemaVersion") != "build-report/v2"
        or report.get("status") != "ready"
        or manifest.get("buildId") != build_id
        or receipt.get("schemaVersion") != RECEIPT_SCHEMA_V2
        or receipt.get("status") != "ready_to_import"
        or receipt.get("buildId") != build_id
        or receipt.get("manifestId") != manifest.get("id")
        or receipt.get("reportId") != report.get("id")
        or receipt.get("documentId") != manifest.get("document", {}).get("documentId")
        or report.get("buildId") != build_id
        or report.get("document", {}).get("documentId") != receipt.get("documentId")
        or document.get("schemaVersion") != "script-document/v2"
        or document.get("id") != receipt.get("documentId")
        or dependencies.get("schemaVersion") != "compiler-dependencies/v2"
        or not isinstance(dependencies.get("build"), Mapping)
        or dependencies.get("build", {}).get("buildId") != build_id
        or dependencies.get("build", {}).get("manifestId") != manifest.get("id")
        or dependencies.get("build", {}).get("reportId") != report.get("id")
    ):
        raise WorkflowV2Error(
            "manifest, report, document and receipt identities differ"
        )

    if (
        view.get("schemaVersion") != VIEW_SCHEMA_V2
        or set(view)
        != {
            "schemaVersion",
            "timeline",
            "tracks",
            "sources",
            "events",
            "markers",
            "composition",
        }
        or view.get("timeline") != manifest.get("timeline")
        or view.get("tracks") != manifest.get("tracks")
        or view.get("composition") != manifest.get("composition")
    ):
        raise WorkflowV2Error(
            "delivery view does not preserve manifest settings and topology"
        )
    _validate_view(view, manifest, root, inventory_by_path)
    _validate_receipt(receipt, manifest, view, inventory_by_path, receipt_rel)

    outer_counts = attestation["verification"]
    expected_outer = {
        "eventCount": len(view["events"]),
        "markerCount": len(view["markers"]),
        "mediaCount": len(view["sources"]),
    }
    if outer_counts != expected_outer:
        raise WorkflowV2Error("attestation counts do not match the native view")
    _validate_semantics(manifest, view)

    if _inventory(root) != inventory:
        raise WorkflowV2Error("package changed while it was being loaded")
    return VerifiedPackageV2(root, manifest, view, attestation)


def _validate_receipt(
    receipt: Mapping[str, Any],
    manifest: Mapping[str, Any],
    view: Mapping[str, Any],
    inventory_by_path: Mapping[str, Mapping[str, Any]],
    receipt_path: str,
) -> None:
    file_hashes = receipt.get("fileHashes")
    expected_file_hashes = {
        path: "sha256:" + cast(str, entry["sha256"])
        for path, entry in inventory_by_path.items()
        if path != receipt_path
    }
    if file_hashes != expected_file_hashes:
        raise WorkflowV2Error("package receipt file hashes do not match the inventory")
    source_hashes = receipt.get("sourceHashes")
    sources = cast(list[Mapping[str, Any]], view["sources"])
    expected_source_hashes = {
        cast(str, source["id"]): cast(str, source["contentHash"]) for source in sources
    }
    if source_hashes != expected_source_hashes:
        raise WorkflowV2Error("package receipt source hashes do not match the view")
    preparations = receipt.get("preparations")
    if not isinstance(preparations, dict):
        raise WorkflowV2Error("package receipt preparation map is malformed")
    for requirement_key, preparation in preparations.items():
        if not isinstance(requirement_key, str) or not requirement_key:
            raise WorkflowV2Error("package receipt preparation key is malformed")
        record = _closed(preparation, PREPARATION_RECEIPT_KEYS, "preparation receipt")
        path = _safe_relative(record["path"], "preparation receipt path")
        if path not in inventory_by_path:
            raise WorkflowV2Error("preparation receipt file is absent from the package")
        for key in PREPARATION_RECEIPT_KEYS - {"path"}:
            _content_hash(record[key], "preparation receipt digest")
    manifest_bindings = manifest.get("preparationBindings")
    if not isinstance(manifest_bindings, list):
        raise WorkflowV2Error("manifest preparation bindings are malformed")
    manifest_keys = {
        binding.get("requirementKey")
        for binding in manifest_bindings
        if isinstance(binding, Mapping)
    }
    if manifest_keys != set(preparations):
        raise WorkflowV2Error("preparation receipts do not match manifest bindings")
    script_events = cast(list[Mapping[str, Any]], manifest["events"])
    counts = {
        "eventCount": len(view["events"]),
        "manifestEventCount": len(script_events),
        "markerCount": len(view["markers"]),
        "mediaCount": len(sources),
    }
    if any(receipt.get(key) != expected for key, expected in counts.items()):
        raise WorkflowV2Error("package receipt counts do not match the package")


def _validate_view(
    view: Mapping[str, Any],
    manifest: Mapping[str, Any],
    root: Path,
    inventory_by_path: Mapping[str, Mapping[str, Any]],
) -> None:
    sources_value = view.get("sources")
    events_value = view.get("events")
    markers_value = view.get("markers")
    manifest_events_value = manifest.get("events")
    manifest_sources_value = manifest.get("sources")
    tracks_value = view.get("tracks")
    if not all(
        isinstance(value, list)
        for value in (
            sources_value,
            events_value,
            markers_value,
            manifest_events_value,
            manifest_sources_value,
            tracks_value,
        )
    ):
        raise WorkflowV2Error("delivery view arrays are malformed")

    source_by_id: dict[str, Mapping[str, Any]] = {}
    for source_value in cast(list[Any], sources_value):
        source = _closed(
            source_value, {"id", "kind", "path", "contentHash"}, "delivery source"
        )
        source_id = source["id"]
        if not isinstance(source_id, str) or not source_id or source_id in source_by_id:
            raise WorkflowV2Error("delivery source identities are invalid or repeated")
        kind = source["kind"]
        if kind not in {"video", "audio", "still"}:
            raise WorkflowV2Error("delivery source kind is unsupported")
        relative = _safe_relative(source["path"], "delivery source path")
        parts = PurePosixPath(relative).parts
        expected_area = "Narration" if kind == "audio" else "Resolved"
        if (
            len(parts) != 3
            or parts[0] != "Media"
            or parts[1] != expected_area
            or not PurePosixPath(parts[2]).name.startswith(source_id + ".")
        ):
            raise WorkflowV2Error(
                "delivery source path is outside its pinned media folder"
            )
        item = inventory_by_path.get(relative)
        content_hash = _content_hash(source["contentHash"], "delivery source hash")
        if item is None or content_hash != "sha256:" + cast(str, item["sha256"]):
            raise WorkflowV2Error("delivery source bytes do not match the inventory")
        source_by_id[source_id] = source

    manifest_sources = cast(list[Mapping[str, Any]], manifest_sources_value)
    manifest_source_ids = {
        source.get("id") for source in manifest_sources if isinstance(source, Mapping)
    }
    tracks = cast(list[Mapping[str, Any]], tracks_value)
    track_by_id: dict[str, Mapping[str, Any]] = {}
    slots: set[tuple[str, int]] = set()
    for track_value in tracks:
        if not isinstance(track_value, Mapping):
            raise WorkflowV2Error("delivery track record is malformed")
        if set(track_value) != {"id", "kind", "index", "name"}:
            raise WorkflowV2Error("delivery track has unsupported fields")
        track_id, kind, index, name = (
            track_value.get("id"),
            track_value.get("kind"),
            track_value.get("index"),
            track_value.get("name"),
        )
        if (
            not isinstance(track_id, str)
            or not track_id
            or track_id in track_by_id
            or kind not in {"video", "audio", "subtitle"}
            or not _positive_int(index)
            or not isinstance(name, str)
            or not name
            or (kind, index) in slots
        ):
            raise WorkflowV2Error("delivery track identity or slot is invalid")
        track_by_id[track_id] = track_value
        slots.add((cast(str, kind), index))

    manifest_events = cast(list[Mapping[str, Any]], manifest_events_value)
    manifest_by_id: dict[str, Mapping[str, Any]] = {}
    for event in manifest_events:
        event_id = event.get("eventId") if isinstance(event, Mapping) else None
        if not isinstance(event_id, str) or not event_id or event_id in manifest_by_id:
            raise WorkflowV2Error("manifest event identities are invalid or repeated")
        manifest_by_id[event_id] = event
    expected_media_events = {
        event_id: event
        for event_id, event in manifest_by_id.items()
        if event.get("kind") != "script_marker"
    }
    actual_event_ids: set[str] = set()
    occupied: dict[str, list[tuple[int, int]]] = {}
    manifest_timeline = cast(Mapping[str, Any], manifest["timeline"])
    timeline_start = manifest_timeline.get("startFrame")
    timeline_duration = manifest_timeline.get("durationFrames")
    if timeline_start != 0 or not _positive_int(timeline_duration):
        raise WorkflowV2Error(
            "delivery requires a frame-zero timeline with positive duration"
        )

    for event_value in cast(list[Any], events_value):
        event = _closed(
            event_value,
            {
                "id",
                "kind",
                "sourceId",
                "trackId",
                "trackKind",
                "recordRange",
                "sourceRange",
                "v2Event",
                "gainDb",
                "pictureTreatment",
            },
            "delivery event",
        )
        event_id = event["id"]
        if not isinstance(event_id, str) or event_id in actual_event_ids:
            raise WorkflowV2Error("delivery event identities are invalid or repeated")
        actual_event_ids.add(event_id)
        original = manifest_by_id.get(event_id)
        if (
            original is None
            or original.get("kind") == "script_marker"
            or event["v2Event"] != original
        ):
            raise WorkflowV2Error("delivery event no longer matches the v2 manifest")
        if event["kind"] != original.get("kind"):
            raise WorkflowV2Error("delivery event kind differs from its v2 source")
        track_id = event["trackId"]
        track_kind = event["trackKind"]
        track = track_by_id.get(track_id) if isinstance(track_id, str) else None
        if (
            track is None
            or track.get("kind") != track_kind
            or track_kind not in {"video", "audio"}
        ):
            raise WorkflowV2Error("delivery event points to an unsupported track")
        record_start, record_duration = _frame_range(
            event["recordRange"], "delivery record range"
        )
        if record_start + record_duration > timeline_duration:
            raise WorkflowV2Error("delivery event exceeds timeline bounds")
        original_record = _manifest_range(
            original.get("recordRange"), "manifest record range"
        )
        if (record_start, record_duration) != original_record:
            raise WorkflowV2Error("delivery record range differs from the v2 event")
        source_id = event["sourceId"]
        delivery_source = (
            source_by_id.get(source_id) if isinstance(source_id, str) else None
        )
        if delivery_source is None:
            raise WorkflowV2Error("delivery event refers to a missing source")
        event_kind = event["kind"]
        picture = original.get("pictureTreatment")
        if event["pictureTreatment"] != picture:
            raise WorkflowV2Error(
                "delivery picture treatment differs from the v2 event"
            )
        if event_kind == "source_audio":
            if track_kind != "audio" or delivery_source.get("kind") != "audio":
                raise WorkflowV2Error(
                    "source audio is not isolated to an audio-only track"
                )
            audio = original.get("audio")
            gain = audio.get("gainDb") if isinstance(audio, Mapping) else None
            policy = audio.get("audioPolicy") if isinstance(audio, Mapping) else None
            if (
                gain not in {-18, -0.1, 0}
                or event["gainDb"] != gain
                or (policy, gain) not in {("quiet", -18), ("full", -0.1), ("full", 0)}
            ):
                raise WorkflowV2Error("source audio gain policy is unsupported")
            if source_id != event_id:
                raise WorkflowV2Error("source audio identity is not event-scoped")
        else:
            if event["gainDb"] is not None:
                raise WorkflowV2Error("non-source-audio event declares an audio gain")
            if track_kind != ("audio" if event_kind == "narration" else "video"):
                raise WorkflowV2Error("delivery event uses the wrong native media type")
            provenance = original.get("provenance")
            provenance_source = (
                provenance.get("sourceId") if isinstance(provenance, Mapping) else None
            )
            if event_kind == "placeholder":
                if source_id != event_id or delivery_source.get("kind") != "still":
                    raise WorkflowV2Error("slate identity is not event-scoped")
                if isinstance(picture, Mapping) and picture.get("kind") == "still":
                    reference = picture.get("reference")
                    reference_hash = (
                        reference.get("contentHash")
                        if isinstance(reference, Mapping)
                        else None
                    )
                    if _content_hash(
                        reference_hash, "placeholder reference hash"
                    ) != delivery_source.get("contentHash"):
                        raise WorkflowV2Error(
                            "placeholder bytes differ from the authored reference"
                        )
            elif provenance_source is not None:
                if (
                    source_id != provenance_source
                    or source_id not in manifest_source_ids
                ):
                    raise WorkflowV2Error(
                        "delivery source identity differs from the manifest"
                    )
                manifest_source_record = next(
                    source
                    for source in manifest_sources
                    if isinstance(source, Mapping) and source.get("id") == source_id
                )
                expected_hash = manifest_source_record.get("deliveredHash")
                if expected_hash is None:
                    narration = manifest_source_record.get("narrationAudio")
                    expected_hash = (
                        narration.get("audioHash")
                        if isinstance(narration, Mapping)
                        else None
                    )
                if (
                    expected_hash is not None
                    and delivery_source.get("contentHash") != expected_hash
                ):
                    raise WorkflowV2Error(
                        "delivery source bytes differ from the manifest binding"
                    )
            elif event_kind != "narration":
                raise WorkflowV2Error("visual event has no manifest source binding")
            elif source_id not in manifest_source_ids:
                raise WorkflowV2Error(
                    "narration source identity differs from the manifest"
                )

        if not _picture_supported(
            event_kind, picture, cast(str, delivery_source["kind"])
        ):
            raise WorkflowV2Error("delivery picture treatment is not supported safely")

        source_range = event["sourceRange"]
        if source_range is not None:
            source_start, source_duration = _frame_range(
                source_range, "delivery source range"
            )
            if source_start + source_duration <= source_start:
                raise WorkflowV2Error("delivery source range is invalid")
            if event_kind == "source_audio":
                # Native source-audio ranges use the timeline-frame projection;
                # sample counts remain only in the preserved v2 event metadata.
                if (
                    source_start + source_duration > 9_007_199_254_740_991
                    or source_duration != record_duration
                ):
                    raise WorkflowV2Error(
                        "source audio range differs from safe timeline counters"
                    )
            elif isinstance(picture, Mapping) and picture.get("kind") == "still_frame":
                if source_duration != record_duration:
                    raise WorkflowV2Error(
                        "still-frame hold range differs from its record duration"
                    )
            elif original.get("sourceRange") is not None and (
                (source_start, source_duration)
                != _manifest_range(original["sourceRange"], "manifest source range")
            ):
                raise WorkflowV2Error("delivery source range differs from the v2 event")
        elif event_kind in {"source_audio", "placeholder"}:
            raise WorkflowV2Error("delivery event has no native source range")

        occupied.setdefault(cast(str, track_id), []).append(
            (record_start, record_start + record_duration)
        )

    if actual_event_ids != set(expected_media_events):
        raise WorkflowV2Error("delivery events do not cover the manifest placements")
    used_sources = {
        cast(str, event["sourceId"])
        for event in cast(list[Mapping[str, Any]], events_value)
    }
    if used_sources != set(source_by_id):
        raise WorkflowV2Error(
            "delivery source inventory does not match event references"
        )

    for intervals in occupied.values():
        intervals.sort()
        if any(current[0] < previous[1] for previous, current in pairwise(intervals)):
            raise WorkflowV2Error("delivery events collide on a native track")

    marker_values = cast(list[Any], markers_value)
    marker_ids: set[str] = set()
    marker_frames: set[int] = set()
    expected_markers = {
        event_id: event
        for event_id, event in manifest_by_id.items()
        if event.get("kind") == "script_marker"
    }
    for marker_value in marker_values:
        marker = _closed(
            marker_value,
            {"id", "frame", "color", "name", "note", "provenance"},
            "delivery marker",
        )
        marker_id, frame = marker["id"], marker["frame"]
        original = (
            expected_markers.get(marker_id) if isinstance(marker_id, str) else None
        )
        if (
            not isinstance(marker_id, str)
            or marker_id in marker_ids
            or original is None
            or marker["provenance"] != original
            or not _nonnegative_int(frame)
            or frame >= timeline_duration
            or frame in marker_frames
            or marker["color"] not in _MARKER_COLORS
            or not isinstance(marker["name"], str)
            or not marker["name"]
            or not isinstance(marker["note"], str)
        ):
            raise WorkflowV2Error("delivery marker is invalid or collides")
        record_start, _ = _manifest_range(
            original.get("recordRange"), "script marker range"
        )
        if frame != record_start:
            raise WorkflowV2Error("delivery marker frame differs from its v2 event")
        marker_ids.add(marker_id)
        marker_frames.add(frame)
    if marker_ids != set(expected_markers):
        raise WorkflowV2Error("delivery markers do not cover script-marker events")

    _validate_composition(manifest, view, track_by_id)


def _picture_supported(event_kind: object, picture: object, source_kind: str) -> bool:
    if picture is None:
        return event_kind != "placeholder" and source_kind in {"video", "audio"}
    if not isinstance(picture, Mapping):
        return False
    kind = picture.get("kind")
    if kind == "still_frame":
        return source_kind == "still" and picture.get("framingPolicy") in {
            "contain",
            "cover",
            "native",
        }
    if kind == "still":
        composition = picture.get("composition")
        return (
            source_kind in {"video", "still"}
            and isinstance(composition, Mapping)
            and composition.get("framingPolicy") == "contain"
            and composition.get("horizontalAlignment") == "center"
            and composition.get("verticalAlignment") == "center"
            and composition.get("backgroundColor") == "#000000"
            and composition.get("motionPreset") == "none"
        )
    if kind == "slate":
        return (
            source_kind in {"still", "video"}
            and picture.get("purpose") in {"intentional", "undefined", "unresolved"}
            and isinstance(picture.get("text"), str)
        )
    return False


def _native_treatment_supported(
    event: Mapping[str, Any], source: Mapping[str, Any]
) -> bool:
    """Whether the current Resolve writer can realize this treatment."""
    picture = event.get("pictureTreatment")
    if not isinstance(picture, Mapping):
        return True
    kind = picture.get("kind")
    if kind == "slate":
        # The package binds a deterministic slate PNG. Its native placement and
        # reopened picture treatment still require the external Studio gate.
        return False
    if kind == "still_frame":
        # Resolve currently maps contain only; cover/native need separately
        # verified property mappings before creation.
        return picture.get("framingPolicy") == "contain"
    if kind == "still":
        return source.get("kind") in {"video", "still"}
    return False


def _fractional_multiframe_still(
    event: Mapping[str, Any], manifest_source: object
) -> bool:
    picture = event.get("pictureTreatment")
    source_frame_map = (
        manifest_source.get("sourceFrameMap")
        if isinstance(manifest_source, Mapping)
        else None
    )
    decoded_frame_count = (
        source_frame_map.get("decodedPackageFrameCount")
        if isinstance(source_frame_map, Mapping)
        else None
    )
    return (
        isinstance(picture, Mapping)
        and picture.get("kind") in {"still", "still_frame"}
        and type(decoded_frame_count) is int
        and decoded_frame_count > 1
    )


def _uses_still_composition(event: Mapping[str, Any], source_kind: str) -> bool:
    picture = event.get("pictureTreatment")
    return source_kind == "still" or (
        isinstance(picture, Mapping) and picture.get("kind") in {"still", "still_frame"}
    )


def _validate_composition(
    manifest: Mapping[str, Any],
    view: Mapping[str, Any],
    track_by_id: Mapping[str, Mapping[str, Any]],
) -> None:
    composition = manifest.get("composition")
    if (
        not isinstance(composition, Mapping)
        or composition.get("topology") != "primary_root_child_overlay"
    ):
        raise WorkflowV2Error("manifest composition topology is unsupported")
    if composition.get("rootContinuous") is not True:
        raise WorkflowV2Error("primary root track is not continuous")
    root_id = composition.get("primaryRootTrackId")
    root = track_by_id.get(root_id) if isinstance(root_id, str) else None
    if root is None or root.get("kind") != "video":
        raise WorkflowV2Error("primary root track is unavailable")
    roles: list[str] = [cast(str, root_id)]
    for key in ("childTrackIds", "overlayTrackIds"):
        track_ids = composition.get(key)
        if not isinstance(track_ids, list):
            raise WorkflowV2Error("composition track groups are malformed")
        for track_id in track_ids:
            track = track_by_id.get(track_id) if isinstance(track_id, str) else None
            if track is None or track.get("kind") != "video":
                raise WorkflowV2Error("composition track is not a video track")
            roles.append(cast(str, track_id))
    if len(roles) != len(set(roles)):
        raise WorkflowV2Error("composition track roles overlap")

    child_indices = [
        cast(int, track_by_id[track_id]["index"])
        for track_id in cast(list[str], composition["childTrackIds"])
    ]
    overlay_indices = [
        cast(int, track_by_id[track_id]["index"])
        for track_id in cast(list[str], composition["overlayTrackIds"])
    ]
    root_index = cast(int, root["index"])
    if child_indices and min(child_indices) <= root_index:
        raise WorkflowV2Error("child tracks must follow the primary root track")
    last_primary_index = max([root_index, *child_indices])
    if overlay_indices and min(overlay_indices) <= last_primary_index:
        raise WorkflowV2Error("overlay tracks must follow root and child tracks")
    timeline = cast(Mapping[str, Any], manifest["timeline"])
    duration = cast(int, timeline["durationFrames"])
    root_intervals = sorted(
        (
            event["recordRange"]["startFrame"],
            event["recordRange"]["startFrame"] + event["recordRange"]["durationFrames"],
        )
        for event in cast(list[Mapping[str, Any]], view["events"])
        if event["trackId"] == root_id
    )
    cursor = 0
    for start, end in root_intervals:
        if start != cursor:
            raise WorkflowV2Error("primary root track has a gap or overlap")
        cursor = end
    if cursor != duration:
        raise WorkflowV2Error("primary root track does not span the timeline")
    events_by_id = {
        cast(str, event["id"]): event
        for event in cast(list[Mapping[str, Any]], view["events"])
    }
    returns = composition.get("returns")
    if not isinstance(returns, list):
        raise WorkflowV2Error("composition return records are malformed")
    for item in returns:
        if (
            not isinstance(item, Mapping)
            or item.get("emitsNewSourceEvent") is not False
        ):
            raise WorkflowV2Error("composition return must reuse its root event")
        returned_event_id = item.get("rootEventId")
        event = (
            events_by_id.get(returned_event_id)
            if isinstance(returned_event_id, str)
            else None
        )
        record_frame = item.get("recordFrame")
        if event is not None:
            root_start, root_duration = _frame_range(
                event.get("recordRange"), "primary root event range"
            )
        else:
            root_start, root_duration = 0, 0
        if (
            event is None
            or event.get("trackId") != root_id
            or not _nonnegative_int(record_frame)
            or not root_start < record_frame < root_start + root_duration
        ):
            raise WorkflowV2Error(
                "composition return is not interior to its continuous root event"
            )


def _validate_semantics(manifest: Mapping[str, Any], view: Mapping[str, Any]) -> None:
    timeline = manifest.get("timeline")
    if not isinstance(timeline, Mapping) or timeline.get("startFrame") != 0:
        raise WorkflowV2Error("delivery requires a frame-zero timeline")
    rate = _frame_rate(timeline)
    if not _positive_int(timeline.get("width")) or not _positive_int(
        timeline.get("height")
    ):
        raise WorkflowV2Error("timeline dimensions are invalid")
    if not _positive_int(timeline.get("audioSampleRate")):
        raise WorkflowV2Error("timeline sample rate is invalid")
    # Keep the exact fractional rate available for read-only preflight even when
    # this caller has not qualified native creation for it.
    if rate not in _SUPPORTED_PACKAGE_RATES:
        raise WorkflowV2Error(
            "native delivery does not support this rational frame rate"
        )
    if view.get("timeline") != timeline:
        raise WorkflowV2Error("native view timeline differs from the manifest")


def _native_rate_supported(
    timeline: Mapping[str, Any], *, allow_fractional_native: bool = False
) -> bool:
    rate = _frame_rate(timeline)
    return rate in _SUPPORTED_INTEGER_RATES or (
        allow_fractional_native is True and rate == _QUALIFIED_FRACTIONAL_RATE
    )


def _native_settings(
    timeline: Mapping[str, Any],
    *,
    preflight: bool,
    allow_fractional_native: bool = False,
) -> dict[str, str]:
    settings = _project_settings(timeline)
    if preflight and not _native_rate_supported(
        timeline, allow_fractional_native=allow_fractional_native
    ):
        settings.pop("timelineFrameRate", None)
    return settings


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _stamp(event: Mapping[str, Any]) -> str:
    original = event["v2Event"]
    digest = _digest(_canonical_json(original).encode("utf-8"))
    return _canonical_json({"v2EventId": event["id"], "v2EventSha256": digest})


def _marker_stamp(marker: Mapping[str, Any]) -> str:
    digest = _digest(_canonical_json(marker["provenance"]).encode("utf-8"))
    return _canonical_json({"v2EventId": marker["id"], "v2EventSha256": digest})


class PublicResolveAdapter(AcceptedDeliveryAdapter):
    """The accepted #109 target guard with v2-only placement and readback."""

    _require_existing_timeline = False

    def __init__(self, resolve: Any) -> None:
        super().__init__(resolve)
        self._v2_root: Path = Path(".")
        self._v2_timeline: Mapping[str, Any] = {}
        self._v2_tracks: tuple[dict[str, Any], ...] = ()
        self._v2_sources: dict[str, Mapping[str, Any]] = {}
        self._v2_manifest_sources: dict[str, Mapping[str, Any]] = {}
        self._v2_preparation_bindings: dict[str, Mapping[str, Any]] = {}
        self.expected_events: dict[str, Mapping[str, Any]] = {}
        self.expected_stamps: dict[str, str] = {}
        self.expected_properties: dict[str, dict[str, Any]] = {}
        self.expected_source_ranges: dict[str, tuple[int, int]] = {}
        self.timeline_marker_stamps: dict[int, str] = {}
        self.expected_markers: dict[int, dict[str, Any]] = {}

    def place_event(self, event: Mapping[str, Any]) -> None:
        self.assert_current_target()
        source_id = cast(str, event["sourceId"])
        media = self.media_by_source.get(source_id)
        if media is None:
            raise WorkflowV2Error("delivery event source was not imported")
        source_range = event.get("sourceRange")
        record_range = cast(Mapping[str, int], event["recordRange"])
        if source_range is None:
            source_start, source_duration = 0, record_range["durationFrames"]
        else:
            source_start, source_duration = _frame_range(
                source_range, "delivery source range"
            )
        source_record = getattr(self, "_v2_sources", {}).get(source_id)
        source_kind = (
            cast(str, source_record["kind"])
            if isinstance(source_record, Mapping)
            else ""
        )
        still_media = source_kind == "still"
        compose_as_still = isinstance(
            source_record, Mapping
        ) and _uses_still_composition(event, source_kind)
        marked = False
        try:
            if still_media:
                source_duration = _still_source_frame_duration(
                    source_duration,
                    media.GetClipProperty("FPS"),
                    self._v2_timeline["frameRate"],
                )
                if not media.SetMarkInOut(
                    source_start, source_start + source_duration, "video"
                ):
                    raise WorkflowV2Error(
                        "still media refused its authored frame range"
                    )
                marked = True
            track = next(
                value for value in self._v2_tracks if value["id"] == event["trackId"]
            )
            media_type = 2 if event["trackKind"] == "audio" else 1
            infos = [
                {
                    "mediaPoolItem": media,
                    "startFrame": source_start,
                    "endFrame": source_start
                    + source_duration
                    + (self._still_end_frame_compensation() if still_media else 0),
                    "mediaType": media_type,
                    "trackIndex": track["index"],
                    "recordFrame": record_range["startFrame"],
                }
            ]
            placed = self.pool.AppendToTimeline(infos)
        finally:
            if marked and not media.ClearMarkInOut("video"):
                raise WorkflowV2Error("still media mark range could not be cleared")
        if not isinstance(placed, (list, tuple)) or len(placed) != 1:
            raise WorkflowV2Error("Resolve did not append exactly one v2 event")
        item = placed[0]
        custom_data = _stamp(event)
        if not item.AddMarker(
            0, "Cyan", "VERA v2 event", cast(str, event["id"]), 1, custom_data
        ):
            raise WorkflowV2Error("Resolve could not stamp the v2 event")
        expected_properties: dict[str, Any] = {}
        if event["kind"] == "source_audio":
            gain = cast(float, event["gainDb"])
            expected_properties = {"AudioVolumeEnabled": True, "AudioVolume": gain}
        elif compose_as_still:
            scale_fit = getattr(self.resolve, "SCALE_FIT", None)
            composite_normal = getattr(self.resolve, "COMPOSITE_NORMAL", None)
            if scale_fit is None or composite_normal is None:
                raise WorkflowV2Error(
                    "Resolve does not expose required still-composition constants"
                )
            expected_properties = {
                "Scaling": scale_fit,
                "CompositeEnabled": True,
                "CompositeMode": composite_normal,
                "TransformEnabled": True,
                "DynamicZoomEnabled": False,
                "Pan": 0.0,
                "Tilt": 0.0,
                "ZoomX": 1.0,
                "ZoomY": 1.0,
                "RotationAngle": 0.0,
                # Resolve expresses the neutral anchor as an offset from centre.
                "AnchorPointX": 0.0,
                "AnchorPointY": 0.0,
                "FlipX": False,
                "FlipY": False,
            }
        if expected_properties:
            if "Scaling" in expected_properties:
                self.assert_current_target()
                if not item.SetProperties({"Scaling": expected_properties["Scaling"]}):
                    raise WorkflowV2Error("Resolve rejected v2 event scaling")
                remaining_properties = {
                    key: value
                    for key, value in expected_properties.items()
                    if key != "Scaling"
                }
                if remaining_properties:
                    self.assert_current_target()
                    if not item.SetProperties(remaining_properties):
                        raise WorkflowV2Error("Resolve rejected v2 event properties")
            else:
                self.assert_current_target()
                if not item.SetProperties(expected_properties):
                    raise WorkflowV2Error("Resolve rejected v2 event properties")
            actual = item.GetProperties()
            if not isinstance(actual, Mapping) or any(
                not _property_equal(actual.get(key), value)
                for key, value in expected_properties.items()
            ):
                raise WorkflowV2Error("Resolve did not retain v2 event properties")
        event_id = cast(str, event["id"])
        self.expected_events[event_id] = event
        self.expected_stamps[event_id] = custom_data
        self.expected_properties[event_id] = expected_properties
        self.expected_source_ranges[event_id] = (
            source_start,
            source_start + source_duration - 1,
        )

    def add_v2_marker(self, marker: Mapping[str, Any]) -> None:
        self.assert_current_target()
        custom = _marker_stamp(marker)
        if not self.timeline.AddMarker(
            marker["frame"],
            _MARKER_COLORS[marker["color"]],
            marker["name"],
            marker["note"],
            1,
            custom,
        ):
            raise WorkflowV2Error("Resolve could not add a script marker")
        frame = cast(int, marker["frame"])
        self.timeline_marker_stamps[frame] = custom
        self.expected_markers[frame] = {
            "color": _MARKER_COLORS[cast(str, marker["color"])],
            "name": marker["name"],
            "note": marker["note"],
            "duration": 1,
        }

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        self._v2_tracks = tuple(dict(track) for track in tracks)
        super().configure_tracks(tracks)

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        super().import_media(sources)

    def verify(self, view: Mapping[str, Any]) -> tuple[str, ...]:
        discrepancies: list[str] = []
        try:
            if self.project.GetName() != self.expected_project_name:
                discrepancies.append("project-name")
            if self.timeline.GetName() != self.expected_timeline_name:
                discrepancies.append("timeline-name")
            for key, expected_value in self.expected_settings.items():
                actual = str(self.project.GetSetting(key))
                if not _setting_matches(key, expected_value, actual):
                    discrepancies.append("project-settings")
                    break
            timeline = cast(Mapping[str, Any], view["timeline"])
            if self.timeline.GetStartFrame() != timeline["startFrame"]:
                discrepancies.append("timeline-start")
            if (
                self.timeline.GetEndFrame()
                != timeline["startFrame"] + timeline["durationFrames"]
            ):
                discrepancies.append("timeline-end")
            expected_tracks = cast(list[Mapping[str, Any]], view["tracks"])
            actual_track_counts: dict[str, int] = {}
            for kind in ("video", "audio", "subtitle"):
                expected_count = max(
                    (
                        track["index"]
                        for track in expected_tracks
                        if track["kind"] == kind
                    ),
                    default=0,
                )
                actual_count = self.timeline.GetTrackCount(kind)
                actual_track_counts[kind] = actual_count
                if actual_count != expected_count:
                    discrepancies.append("track-count")
            for track in expected_tracks:
                if (
                    self.timeline.GetTrackName(track["kind"], track["index"])
                    != track["name"]
                ):
                    discrepancies.append("track-name")
            by_track: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
            for event in cast(list[Mapping[str, Any]], view["events"]):
                track = next(
                    value
                    for value in expected_tracks
                    if value["id"] == event["trackId"]
                )
                by_track.setdefault((track["kind"], track["index"]), []).append(event)
            for kind, track_count in actual_track_counts.items():
                for index in range(1, track_count + 1):
                    expected = by_track.get((kind, index), [])
                    actual_items = list(self.timeline.GetItemListInTrack(kind, index))
                    expected_sorted = sorted(
                        expected, key=lambda item: item["recordRange"]["startFrame"]
                    )
                    actual_sorted = sorted(
                        actual_items, key=lambda item: item.GetStart(False)
                    )
                    if len(expected_sorted) != len(actual_sorted):
                        discrepancies.append("event-count")
                        continue
                    for event, item in zip(expected_sorted, actual_sorted, strict=True):
                        event_id = cast(str, event["id"])
                        record = event["recordRange"]
                        if (
                            item.GetStart(False) != record["startFrame"]
                            or item.GetDuration(False) != record["durationFrames"]
                        ):
                            discrepancies.append("event-record-range")
                        source_range = event.get("sourceRange")
                        source_record = self._v2_sources.get(
                            cast(str, event["sourceId"]), {}
                        )
                        try:
                            is_qualified_fractional = (
                                _frame_rate(timeline) == _QUALIFIED_FRACTIONAL_RATE
                            )
                        except WorkflowV2Error:
                            is_qualified_fractional = False
                        fractional_source_clock = (
                            is_qualified_fractional
                            and isinstance(source_record, Mapping)
                            and (
                                source_record.get("kind") in {"video", "still"}
                                or (
                                    source_record.get("kind") == "audio"
                                    and event.get("kind") == "narration"
                                    and isinstance(event.get("v2Event"), Mapping)
                                    and event["v2Event"].get("sourceRange") is None
                                )
                            )
                        )
                        if fractional_source_clock:
                            media_item = item.GetMediaPoolItem()
                            manifest_source = self._v2_manifest_sources.get(
                                cast(str, event["sourceId"]), {}
                            )
                            if media_item is None:
                                discrepancies.append("event-source-range")
                            else:
                                source_times = {
                                    method_name: getattr(item, method_name)()
                                    for method_name in (
                                        "GetSourceStartTime",
                                        "GetSourceEndTime",
                                    )
                                    if callable(getattr(item, method_name, None))
                                }
                                speed_method = getattr(item, "GetSpeed", None)
                                properties_method = getattr(
                                    media_item, "GetClipProperty", None
                                )
                                source_range_matches = (
                                    callable(speed_method)
                                    and callable(properties_method)
                                    and _fractional_source_range_matches(
                                        event=event,
                                        source=source_record,
                                        manifest_source=manifest_source,
                                        preparation_bindings=self._v2_preparation_bindings,
                                        timeline=timeline,
                                        actual_start=item.GetSourceStartFrame(),
                                        actual_end=item.GetSourceEndFrame(),
                                        source_times=source_times,
                                        speed=speed_method(),
                                        media_properties=properties_method(),
                                        record_duration=cast(
                                            int, record["durationFrames"]
                                        ),
                                    )
                                )
                                if not source_range_matches:
                                    discrepancies.append("event-source-range")
                        else:
                            if source_range is not None:
                                expected_source_range = self.expected_source_ranges.get(
                                    event_id,
                                    (
                                        source_range["startFrame"],
                                        source_range["startFrame"]
                                        + source_range["durationFrames"]
                                        - 1,
                                    ),
                                )
                                if (
                                    item.GetSourceStartFrame()
                                    != expected_source_range[0]
                                ):
                                    discrepancies.append("event-source-start")
                                if item.GetSourceEndFrame() != expected_source_range[1]:
                                    discrepancies.append("event-source-end")
                            media_item = item.GetMediaPoolItem()
                        actual_media_id = (
                            media_item.GetMediaId() if media_item is not None else None
                        )
                        if actual_media_id != self.media_id_by_source.get(
                            cast(str, event["sourceId"])
                        ):
                            discrepancies.append("event-media-identity")
                        if item.GetMarkerCustomData(0) != self.expected_stamps.get(
                            event_id
                        ):
                            discrepancies.append("event-custom-data")
                        expected_properties = self.expected_properties.get(event_id, {})
                        if expected_properties:
                            actual_properties = item.GetProperties()
                            if not isinstance(actual_properties, Mapping) or any(
                                not _property_equal(actual_properties.get(key), value)
                                for key, value in expected_properties.items()
                            ):
                                discrepancies.append("event-properties")
            actual_markers = self.timeline.GetMarkers()
            expected_marker_frames = set(self.timeline_marker_stamps)
            if (
                not isinstance(actual_markers, Mapping)
                or set(actual_markers) != expected_marker_frames
            ):
                discrepancies.append("marker-inventory")
            else:
                for frame, custom in self.timeline_marker_stamps.items():
                    marker_properties = actual_markers[frame]
                    expected_marker_properties = self.expected_markers.get(frame)
                    if (
                        not isinstance(marker_properties, Mapping)
                        or expected_marker_properties is None
                        or any(
                            marker_properties.get(key) != value
                            for key, value in expected_marker_properties.items()
                        )
                    ):
                        discrepancies.append("marker-properties")
                    if self.timeline.GetMarkerCustomData(frame) != custom:
                        discrepancies.append("marker-custom-data")
            self._verify_bins(discrepancies)
            self._verify_media_inventory(view, discrepancies)
        except (AttributeError, KeyError, TypeError, ValueError):
            discrepancies.append("readback-api")
        return tuple(dict.fromkeys(discrepancies))

    def _verify_media_inventory(
        self, view: Mapping[str, Any], discrepancies: list[str]
    ) -> None:
        folder = self.pool.GetRootFolder()
        for name in self.created_bins:
            folder = next(
                (
                    child
                    for child in folder.GetSubFolderList()
                    if child.GetName() == name
                ),
                None,
            )
            if folder is None:
                discrepancies.append("media-bin")
                return
        timeline_item = self.timeline.GetMediaPoolItem()
        timeline_media_id = timeline_item.GetMediaId() if timeline_item else None
        media = [
            item
            for item in folder.GetClipList()
            if item.GetMediaId() != timeline_media_id
        ]
        sources = cast(list[Mapping[str, Any]], view["sources"])
        if len(media) != len(sources):
            discrepancies.append("media-count")
        actual_by_id = {
            item.GetMediaId(): item.GetClipProperty("File Path") for item in media
        }
        for source in sources:
            media_id = self.media_id_by_source.get(cast(str, source["id"]))
            actual_path = actual_by_id.get(media_id)
            expected_path = (self._v2_root / cast(str, source["path"])).resolve()
            if (
                not isinstance(actual_path, str)
                or Path(actual_path).resolve() != expected_path
            ):
                discrepancies.append("media-path")
        pending = [self.pool.GetRootFolder()]
        while pending:
            current = pending.pop()
            if current.GetUniqueId() != folder.GetUniqueId() and any(
                item.GetMediaId() != timeline_media_id for item in current.GetClipList()
            ):
                discrepancies.append("unexpected-media")
            pending.extend(current.GetSubFolderList())


def _setting_matches(key: str, expected: str, actual: str) -> bool:
    if key != "timelineFrameRate":
        return actual == expected
    try:
        from decimal import Decimal, InvalidOperation

        return Decimal(actual) == Decimal(expected)
    except (InvalidOperation, ValueError):
        return False


def _property_equal(actual: object, expected: object) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        return (
            isinstance(actual, (int, float))
            and not isinstance(actual, bool)
            and abs(float(actual) - float(expected)) <= 1e-6
        )
    return actual == expected


def _source_time_error_samples(
    value: object, expected_seconds: Fraction, sample_rate: int = 48_000
) -> Fraction | None:
    if type(value) is int:
        seconds = Fraction(value)
    elif type(value) is float and math.isfinite(value):
        seconds = Fraction(str(value))
    else:
        return None
    return (seconds - expected_seconds) * sample_rate


def _native_speed_matches(speed: object, expected_percent: int) -> bool:
    allowed = {
        "Percentage",
        "PitchCorrection",
        "StretchKeyframesToFit",
        "RippleTimeline",
    }
    return (
        type(speed) is dict
        and "Percentage" in speed
        and speed.keys() <= allowed
        and type(speed["Percentage"]) in {int, float}
        and math.isfinite(speed["Percentage"])
        and speed["Percentage"] == expected_percent
        and ("PitchCorrection" not in speed or type(speed["PitchCorrection"]) is bool)
        and all(
            option not in speed
            or (type(speed[option]) is bool and speed[option] is False)
            for option in ("StretchKeyframesToFit", "RippleTimeline")
        )
    )


def _event_source_provenance_matches(
    event: Mapping[str, Any],
    source: Mapping[str, Any],
    manifest_source: Mapping[str, Any],
    *,
    require_hash_binding: bool = True,
) -> bool:
    source_id = event.get("sourceId")
    content_hash = source.get("contentHash")
    manifest_event = event.get("v2Event")
    if (
        not isinstance(source_id, str)
        or source.get("id") != source_id
        or not isinstance(content_hash, str)
        or _CONTENT_HASH.fullmatch(content_hash) is None
        or not isinstance(manifest_event, Mapping)
        or manifest_event.get("eventId") != event.get("id")
    ):
        return False
    if event.get("kind") == "placeholder":
        treatment = manifest_event.get("pictureTreatment")
        provenance = manifest_event.get("provenance")
        if (
            source_id != event.get("id")
            or source.get("kind") != "still"
            or not isinstance(provenance, Mapping)
            or provenance.get("sourceId") is not None
            or not isinstance(treatment, Mapping)
            or treatment.get("kind") not in {"still", "slate"}
        ):
            return False
        if treatment.get("kind") == "still":
            reference = treatment.get("reference")
            return (
                isinstance(reference, Mapping)
                and reference.get("contentHash") == content_hash
            )
        # The verified package binds generated slate bytes to the authored text.
        return True
    if manifest_source.get("id") != source_id:
        return False
    if require_hash_binding and manifest_source.get("deliveredHash") != content_hash:
        return False
    direct_source_id = manifest_event.get("sourceId")
    if direct_source_id is not None and direct_source_id != source_id:
        return False
    provenance = manifest_event.get("provenance")
    if provenance is not None:
        return (
            isinstance(provenance, Mapping) and provenance.get("sourceId") == source_id
        )
    return direct_source_id == source_id


def _fractional_source_range_matches(
    *,
    event: Mapping[str, Any],
    source: Mapping[str, Any],
    manifest_source: Mapping[str, Any],
    preparation_bindings: Mapping[str, Any],
    timeline: Mapping[str, Any],
    actual_start: object,
    actual_end: object,
    source_times: Mapping[str, Any],
    speed: object,
    media_properties: object,
    record_duration: int,
) -> bool:
    """Accept only the already qualified 23.976 Resolve source-clock shapes."""
    try:
        rate = _frame_rate(timeline)
        if rate != _QUALIFIED_FRACTIONAL_RATE:
            return False
        rate_seconds = Fraction(rate[1], rate[0])
        source_id = event.get("sourceId")
        manifest_event = event.get("v2Event")
        if (
            not isinstance(source_id, str)
            or not isinstance(manifest_event, Mapping)
            or not _event_source_provenance_matches(
                event,
                source,
                manifest_source,
                require_hash_binding=not (
                    source.get("kind") == "audio" and event.get("kind") == "narration"
                ),
            )
            or not _positive_int(record_duration)
            or type(actual_start) is not int
            or type(actual_end) is not int
            or not isinstance(source_times, Mapping)
        ):
            return False

        if source.get("kind") == "still":
            try:
                source_start, _source_duration = _frame_range(
                    event.get("sourceRange"), "still event source range"
                )
                if event.get("kind") == "placeholder":
                    manifest_start = 0
                    manifest_duration = record_duration
                    if manifest_event.get("sourceRange") is not None:
                        return False
                else:
                    manifest_start, manifest_duration = _manifest_range(
                        manifest_event.get("sourceRange"),
                        "still manifest source range",
                    )
            except WorkflowV2Error:
                return False
            if (
                event.get("kind")
                not in {"primary_visual", "overlay_visual", "placeholder"}
                or source_start != 0
                or manifest_start != 0
                or manifest_duration <= 0
                or actual_start < 0
                or actual_start != actual_end
                or not isinstance(media_properties, Mapping)
                or media_properties.get("Frames") != "1"
                or not (
                    _native_speed_matches(speed, 0) or _native_speed_matches(speed, 100)
                )
            ):
                return False
            imported_fps = media_properties.get("FPS")
            if type(imported_fps) not in {str, int, float}:
                return False
            if type(imported_fps) is float and not math.isfinite(imported_fps):
                return False
            try:
                fps = Fraction(str(imported_fps))
                if fps <= 0:
                    return False
            except (ValueError, ZeroDivisionError):
                return False
            start_error = _source_time_error_samples(
                source_times.get("GetSourceStartTime"), Fraction(0)
            )
            end_time = source_times.get("GetSourceEndTime")
            end_errors = (
                _source_time_error_samples(end_time, Fraction(1, 1) / fps),
                _source_time_error_samples(end_time, rate_seconds),
            )
            return (
                start_error is not None
                and abs(start_error) <= 1
                and any(error is not None and abs(error) <= 1 for error in end_errors)
            )

        if source.get("kind") == "audio" and event.get("kind") == "narration":
            narration_audio = manifest_source.get("narrationAudio")
            try:
                view_source_start, view_source_duration = _frame_range(
                    event.get("sourceRange"), "narration view source range"
                )
            except WorkflowV2Error:
                return False
            record_start, authored_duration = _frame_range(
                event.get("recordRange"), "narration record range"
            )
            if (
                manifest_event.get("sourceRange", "missing") is not None
                or view_source_start != 0
                or view_source_duration != record_duration
                or record_start < 0
                or not isinstance(narration_audio, Mapping)
                or narration_audio.get("audioHash") != source.get("contentHash")
                or narration_audio.get("sampleRate") != timeline.get("audioSampleRate")
                or narration_audio.get("sampleRate") != 48_000
                or not _positive_int(narration_audio.get("durationSamples"))
                or not _native_speed_matches(speed, 100)
            ):
                return False
            sample_count = cast(int, narration_audio["durationSamples"])
            sample_rate = cast(int, narration_audio["sampleRate"])
            exact_frames = Fraction(sample_count * rate[0], sample_rate * rate[1])
            expected_duration = math.ceil(exact_frames)
            if (
                authored_duration != record_duration
                or expected_duration < record_duration
                or actual_start != 0
            ):
                return False
            start_error = _source_time_error_samples(
                source_times.get("GetSourceStartTime"), Fraction(0), sample_rate
            )
            eof_error = _source_time_error_samples(
                source_times.get("GetSourceEndTime"),
                Fraction(sample_count, sample_rate),
                sample_rate,
            )
            record_end_error = _source_time_error_samples(
                source_times.get("GetSourceEndTime"),
                record_duration * rate_seconds,
                sample_rate,
            )
            return (
                start_error is not None
                and abs(start_error) <= 1
                and (
                    (
                        exact_frames.denominator != 1
                        and expected_duration == record_duration
                        and actual_end == record_duration - 2
                        and eof_error is not None
                        and abs(eof_error) <= 1
                    )
                    or (
                        actual_end == record_duration - 1
                        and record_end_error is not None
                        and abs(record_end_error) <= 1
                    )
                )
            )

        if source.get("kind") != "video" or event.get("kind") not in {
            "primary_visual",
            "overlay_visual",
        }:
            return False
        try:
            expected_start, expected_duration = _frame_range(
                event.get("sourceRange"), "video event source range"
            )
            manifest_start, manifest_duration = _manifest_range(
                manifest_event.get("sourceRange"), "video manifest source range"
            )
        except WorkflowV2Error:
            return False
        expected_end = expected_start + expected_duration
        manifest_end = manifest_start + manifest_duration
        expected_rate = {"numerator": rate[0], "denominator": rate[1]}
        expected_range = {"startFrame": expected_start, "endFrame": expected_end}
        source_frame_map = manifest_source.get("sourceFrameMap")
        source_mapping = manifest_source.get("sourceTimeMapping")
        event_mapping = manifest_event.get("sourceTimeMapping")
        source_requirement = manifest_source.get("preparationRequirementKey")
        binding = (
            preparation_bindings.get(source_requirement)
            if isinstance(source_requirement, str)
            else None
        )
        verification = (
            binding.get("verification") if isinstance(binding, Mapping) else None
        )
        provenance = manifest_event.get("provenance")
        if (
            manifest_start != expected_start
            or manifest_end != expected_end
            or manifest_event.get("sourceRange") != expected_range
            or not isinstance(source_frame_map, Mapping)
            or not isinstance(source_mapping, Mapping)
            or not isinstance(event_mapping, Mapping)
            or not isinstance(binding, Mapping)
            or binding.get("requirementKey") != source_requirement
            or binding.get("timeMapping") != source_mapping
            or event_mapping != source_mapping
            or event_mapping.get("sourceFrameMap") != source_frame_map
            or event_mapping.get("sourceOrigin") != {"numerator": 0, "denominator": 1}
            or event_mapping.get("deliveredOrigin")
            != {"numerator": 0, "denominator": 1}
            or event_mapping.get("sourceRate") != expected_rate
            or event_mapping.get("deliveredRate") != expected_rate
            or not isinstance(verification, Mapping)
            or not isinstance(provenance, Mapping)
            or provenance.get("sourceId") != source_id
            or manifest_source.get("deliveredHash") != source.get("contentHash")
            or verification.get("deliveredHash") != source.get("contentHash")
            or verification.get("decodedFrameRate") != expected_rate
            or source_frame_map.get("decodedPackageFrameRate") != expected_rate
            or type(verification.get("decodedFrameCount")) is not int
            or verification.get("decodedFrameCount")
            != source_frame_map.get("decodedPackageFrameCount")
            or type(verification.get("probeHash")) is not str
            or verification.get("probeHash") != source_frame_map.get("probeHash")
            or verification.get("probeHash") != source_frame_map.get("descriptorHash")
            or verification.get("probeHash")
            != manifest_source.get("deliveredProbeHash")
            or not isinstance(media_properties, Mapping)
            or media_properties.get("Frames")
            != str(verification.get("decodedFrameCount"))
            or not _positive_int(verification.get("decodedFrameCount"))
            or expected_start < 0
            or expected_start >= verification["decodedFrameCount"]
            or expected_end > verification["decodedFrameCount"]
            or source_frame_map.get("packageFrameZeroLogicalFrame") != 0
            or source_frame_map.get("packageVideoPtsOrigin")
            != {"numerator": 0, "denominator": 1}
            or source_frame_map.get("loggedTimeAtPackageFrameZero")
            != {"numerator": 0, "denominator": 1}
            or actual_start not in {expected_start, expected_start - 1}
            or actual_start < 0
            or actual_end not in {expected_end, expected_end - 1}
            or not _native_speed_matches(speed, 100)
        ):
            return False
        start_error = _source_time_error_samples(
            source_times.get("GetSourceStartTime"), expected_start * rate_seconds
        )
        end_error = _source_time_error_samples(
            source_times.get("GetSourceEndTime"), expected_end * rate_seconds
        )
        return (
            start_error is not None
            and abs(start_error) <= 1
            and end_error is not None
            and abs(end_error) <= 1
        )
    except (KeyError, TypeError, ValueError, OverflowError, WorkflowV2Error):
        return False


def run_workflow_delivery_v2(
    resolve: Any,
    attestation_path: Path,
    attestation_sha256: str,
    *,
    action: str = "preflight",
    authorize_new_nonproduction: bool = False,
    external_scripting: str | None = None,
    adapter_factory: Callable[[Any], Any] | None = None,
    allow_fractional_native: bool = False,
) -> dict[str, Any]:
    """Preflight or create one authorized new nonproduction Resolve project."""
    result: dict[str, Any] = {
        "schemaVersion": "vera-injected-delivery-result/v2",
        "deliveryVersion": DELIVERY_VERSION,
        "sourcePins": SOURCE_PINS,
        "startedAt": datetime.now(UTC).isoformat(),
        "pythonVersion": platform.python_version(),
        "action": action,
        "attestationSha256": attestation_sha256,
        "status": "stopped_safely",
        "verified": False,
        "discrepancies": [],
        "partialTargetRetained": False,
    }
    mutation_started = False
    stage = "package validation"
    try:
        if action not in {"preflight", "build"}:
            raise WorkflowV2Error("action must be preflight or build")
        if action == "build" and (
            authorize_new_nonproduction is not True
            or external_scripting not in {"None", "Local"}
        ):
            raise WorkflowV2Error("build requires both operator authorizations")
        package = load_verified_package_v2(attestation_path, attestation_sha256)
        manifest, view, attestation = (
            package.manifest,
            package.view,
            package.attestation,
        )
        timeline = cast(Mapping[str, Any], manifest["timeline"])
        result.update(
            {
                "buildId": attestation["buildId"],
                "projectName": attestation["projectName"],
                "timelineName": attestation["timelineName"],
                "verification": attestation["verification"],
                "packageVerifiedAt": attestation["verifiedAt"],
                "nativeRateQualified": _native_rate_supported(
                    timeline, allow_fractional_native=allow_fractional_native
                ),
            }
        )
        if not result["nativeRateQualified"] and action == "build":
            raise WorkflowV2Error(
                "fractional-rate native creation awaits separate qualification"
            )
        has_source_audio = any(
            event.get("kind") == "source_audio" for event in view["events"]
        )
        result["sourceAudioNativeQualified"] = False
        if has_source_audio and action == "build":
            raise WorkflowV2Error(
                "native source-audio delivery awaits #178 qualification"
            )
        has_subtitle_tracks = any(
            track.get("kind") == "subtitle" for track in view["tracks"]
        )
        result["nativeSubtitleTracksQualified"] = not has_subtitle_tracks
        if has_subtitle_tracks and action == "build":
            raise WorkflowV2Error(
                "native subtitle-track creation awaits separate qualification"
            )
        manifest_source_by_id = {
            source["id"]: source
            for source in cast(list[Mapping[str, Any]], manifest["sources"])
            if isinstance(source.get("id"), str)
        }
        fractional_rate = _frame_rate(timeline) == _QUALIFIED_FRACTIONAL_RATE
        unsupported_treatments = [
            event
            for event in view["events"]
            if not _native_treatment_supported(
                event,
                next(
                    source
                    for source in view["sources"]
                    if source["id"] == event["sourceId"]
                ),
            )
            or (
                fractional_rate
                and _fractional_multiframe_still(
                    event, manifest_source_by_id.get(event.get("sourceId"))
                )
            )
        ]
        result["nativePictureTreatmentsQualified"] = not unsupported_treatments
        if unsupported_treatments and action == "build":
            raise WorkflowV2Error(
                "a picture treatment lacks a qualified native mapping"
            )
        if resolve is None:
            raise WorkflowV2Error("Resolve did not inject an API object")
        settings = _native_settings(
            timeline,
            preflight=(action == "preflight"),
            allow_fractional_native=allow_fractional_native,
        )
        factory = adapter_factory or PublicResolveAdapter
        stage = "Resolve connection preflight"
        adapter = factory(resolve)
        connected = adapter.connected_facts()
        result["connected"] = (
            asdict(connected)
            if hasattr(connected, "__dataclass_fields__")
            else connected
        )
        if (
            getattr(connected, "edition", None) != "studio"
            or not getattr(connected, "scripting_available", False)
            or getattr(connected, "suffix", "")
            or (getattr(connected, "version", None), getattr(connected, "build", None))
            not in SUPPORTED_IDENTITIES
        ):
            raise WorkflowV2Error("unsupported connected Resolve edition or build")
        result["manualCompletion"] = list(adapter.probe(settings))
        stage = "new target collision check"
        adapter.check_project_name_available(attestation["projectName"])
        if load_verified_package_v2(attestation_path, attestation_sha256) != package:
            raise WorkflowV2Error("package changed during preflight")
        if action == "preflight":
            result["status"] = "preflight_passed"
            result["message"] = "The immutable v2 package passed read-only preflight."
            if not result["nativeRateQualified"]:
                result["nativeRateLimitation"] = "24000/1001 is not natively qualified."
            return result

        cast(Any, adapter)._v2_root = package.root
        cast(Any, adapter)._v2_timeline = timeline
        cast(Any, adapter)._v2_tracks = tuple(dict(track) for track in view["tracks"])
        cast(Any, adapter)._v2_sources = {
            source["id"]: source for source in view["sources"]
        }
        cast(Any, adapter)._v2_manifest_sources = {
            source["id"]: source for source in manifest["sources"]
        }
        cast(Any, adapter)._v2_preparation_bindings = {
            binding["requirementKey"]: binding
            for binding in manifest["preparationBindings"]
        }

        def mutate(method: Callable[..., Any], *arguments: Any, label: str) -> Any:
            nonlocal mutation_started, stage
            stage = label
            current = load_verified_package_v2(attestation_path, attestation_sha256)
            if current != package:
                raise WorkflowV2Error("package changed before a native operation")
            if mutation_started:
                adapter.assert_current_target()
            mutation_started = True
            return method(*arguments)

        mutate(
            adapter.create_project, attestation["projectName"], label="create project"
        )
        mutate(adapter.configure_project, settings, label="configure project")
        mutate(adapter.create_bin, "VERA Studio Assembly", label="create assembly bin")
        mutate(adapter.create_bin, "Package Media", label="create package media bin")
        sources = [
            (
                cast(str, source["id"]),
                _package_path(package.root, source["path"], "delivery source"),
            )
            for source in view["sources"]
        ]
        mutate(adapter.import_media, sources, label="import package media")
        mutate(
            adapter.create_timeline,
            attestation["timelineName"],
            label="create timeline",
        )
        mutate(adapter.configure_tracks, view["tracks"], label="configure tracks")
        for event in view["events"]:
            mutate(adapter.place_event, event, label="place timeline event")
        for marker in view["markers"]:
            mutate(adapter.add_v2_marker, marker, label="add timeline marker")
        mutate(
            adapter.save_close_reopen,
            attestation["projectName"],
            label="save close and reopen",
        )
        if load_verified_package_v2(attestation_path, attestation_sha256) != package:
            raise WorkflowV2Error("package changed after native save and reopen")
        discrepancies = tuple(adapter.verify(view))
        result["discrepancies"] = list(discrepancies)
        result["verified"] = not discrepancies
        result["status"] = "verified" if not discrepancies else "verification_failed"
        result["partialTargetRetained"] = bool(discrepancies)
        result["message"] = (
            "The new project was saved, reopened, and checked against the v2 package."
            if not discrepancies
            else "Resolve readback differed; the partial target was retained."
        )
    except Exception as error:
        result["status"] = "mutation_failed" if mutation_started else "stopped_safely"
        result["partialTargetRetained"] = mutation_started
        result["failureType"] = type(error).__name__
        result["failureStage"] = stage
        result["message"] = (
            "Resolve stopped during delivery; the named partial target was retained."
            if mutation_started
            else "Delivery stopped before changing Resolve."
        )
        result["discrepancies"] = (
            ["native-delivery-failure"] if mutation_started else []
        )
    finally:
        result["finishedAt"] = datetime.now(UTC).isoformat()
    return result
