"""Build and independently verify immutable, verified v2 OTIO packages.

This is deliberately separate from the v1 ``otio_package`` boundary.  V2
packages preserve the compiler's original inputs and project v2 event intent
into a small Resolve-facing delivery view without rewriting the manifest.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import math
import os
import shutil
import stat
import tempfile
from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any, cast

import jsonschema  # type: ignore[import-untyped]
import opentimelineio as otio  # type: ignore[import-untyped]
from referencing import Registry, Resource

from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.placeholder_slate import render_placeholder_slate

BUILD_DIRECTORY = "Builds"
MEDIA_DIRECTORY = "Media"
MANIFEST_FILENAME = "timeline-manifest.json"
REPORT_FILENAME = "build-report.json"
DOCUMENT_FILENAME = "script-document.json"
DEPENDENCIES_FILENAME = "compiler-dependencies.json"
DELIVERY_VIEW_FILENAME = "delivery-view.json"
OTIO_FILENAME = "timeline.otio"
VERIFICATION_FILENAME = "package-verification.json"
VIEW_SCHEMA_VERSION = "resolve-native-view/v2"
VERIFICATION_SCHEMA_VERSION = "v2-package-verification/v1"
_HASH_PREFIX = "sha256:"
_MAX_SAFE = 2**53 - 1
_REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
_CONTRACTS_DIRECTORY = _REPOSITORY_ROOT / "contracts"
_V2_SCHEMA_FILES = (
    "script-document-v2.schema.json",
    "timeline-manifest-v2.schema.json",
    "build-report-v2.schema.json",
    "compiler-dependencies-v2.schema.json",
)

JsonObject = dict[str, Any]


class V2PackageError(RuntimeError):
    """An actionable failure that prevents v2 package publication or import."""


@dataclass(frozen=True)
class V2PackageResult:
    """Published v2 package identity and whether this was an exact retry."""

    project_root: Path
    build_id: str
    reused: bool


@dataclass(frozen=True)
class V2PackageVerification:
    """Counts independently recovered from the published delivery view."""

    build_id: str
    event_count: int
    marker_count: int
    media_count: int


def _error(message: str) -> V2PackageError:
    return V2PackageError(message)


def _hash_bytes(data: bytes) -> str:
    return _HASH_PREFIX + hashlib.sha256(data).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as error:
        raise _error(f"could not hash file {path}: {error}") from error
    return _HASH_PREFIX + digest.hexdigest()


def _require_hash(value: object, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 71
        or not value.startswith(_HASH_PREFIX)
    ):
        raise _error(f"{label} is not a sha256 content hash")
    try:
        int(value[len(_HASH_PREFIX) :], 16)
    except ValueError as error:
        raise _error(f"{label} is not a lowercase sha256 content hash") from error
    if value != value.lower():
        raise _error(f"{label} is not a lowercase sha256 content hash")
    return value


def _canonical_json(value: object) -> bytes:
    return canonical_json_bytes(value)


def _compiler_hash(value: object) -> str:
    """Match compiler-core.ts canonical JSON for the frozen integer-only schemas."""
    text = (
        json.dumps(
            _compiler_json_values(value),
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
        )
        + "\n"
    )
    # JSON.stringify preserves valid Unicode and escapes lone surrogate units.
    text = "".join(
        f"\\u{ord(char):04x}" if 0xD800 <= ord(char) <= 0xDFFF else char
        for char in text
    )
    return _hash_bytes(text.encode("utf-8"))


def _compiler_json_values(value: object) -> object:
    if isinstance(value, dict):
        return {key: _compiler_json_values(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_compiler_json_values(nested) for nested in value]
    if isinstance(value, float):
        if not math.isfinite(value) or not value.is_integer() or abs(value) > _MAX_SAFE:
            raise _error("compiler hash input is not a schema-supported safe integer")
        return int(value)
    if type(value) is int and abs(value) > _MAX_SAFE:
        raise _error("compiler hash input is not a schema-supported safe integer")
    return value


def _load_json(path: Path, label: str) -> tuple[JsonObject, bytes]:
    _require_path_components_no_symlink(path, label)
    _require_regular(path, label)
    try:
        raw = path.read_bytes()
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_unique_json_keys,
            parse_constant=_invalid_json_number,
            parse_float=_finite_json_float,
        )
    except (OSError, UnicodeError, ValueError) as error:
        raise _error(f"could not read {label} {path}: {error}") from error
    if not isinstance(value, dict):
        raise _error(f"{label} must contain one JSON object: {path}")
    return cast(JsonObject, value), raw


def _unique_json_keys(pairs: list[tuple[str, Any]]) -> JsonObject:
    result: JsonObject = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def _invalid_json_number(value: str) -> Any:
    raise ValueError(f"non-finite JSON number {value}")


def _finite_json_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite JSON number {value}")
    return number


def _require_regular(path: Path, label: str) -> os.stat_result:
    try:
        if path.is_symlink():
            raise _error(f"{label} is a symbolic link: {path}")
        info = path.stat(follow_symlinks=False)
    except OSError as error:
        raise _error(f"could not inspect {label} {path}: {error}") from error
    if not stat.S_ISREG(info.st_mode):
        raise _error(f"{label} must be a regular file: {path}")
    return info


def _require_path_components_no_symlink(path: Path, label: str) -> None:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        try:
            if component.is_symlink():
                raise _error(f"{label} contains a symbolic link: {component}")
        except OSError as error:
            raise _error(f"could not inspect {label} {component}: {error}") from error


def _copy_input_file(
    source: Path, destination: Path, expected_hash: str | None = None
) -> str:
    """Copy bytes with O_NOFOLLOW and detect a source changed during the read."""
    _require_path_components_no_symlink(source, "supplied media path")
    before = _require_regular(source, "supplied media")
    destination.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256()
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        source_fd = os.open(source, flags)
    except OSError as error:
        raise _error(f"could not open supplied media {source}: {error}") from error
    try:
        opened = os.fstat(source_fd)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (
            before.st_dev,
            before.st_ino,
        ):
            raise _error(f"supplied media changed before copying: {source}")
        with (
            os.fdopen(source_fd, "rb", closefd=False) as reader,
            destination.open("xb") as writer,
        ):
            for chunk in iter(lambda: reader.read(1024 * 1024), b""):
                digest.update(chunk)
                writer.write(chunk)
            writer.flush()
            os.fsync(writer.fileno())
        after = os.fstat(source_fd)
    except V2PackageError:
        destination.unlink(missing_ok=True)
        raise
    except OSError as error:
        destination.unlink(missing_ok=True)
        raise _error(f"could not copy supplied media {source}: {error}") from error
    finally:
        os.close(source_fd)
    final = source.stat(follow_symlinks=False)
    if (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns) != (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
    ):
        destination.unlink(missing_ok=True)
        raise _error(f"supplied media changed while copying: {source}")
    actual = _HASH_PREFIX + digest.hexdigest()
    if expected_hash is not None and actual != expected_hash:
        destination.unlink(missing_ok=True)
        raise _error(f"media hash mismatch for {source}: {expected_hash} != {actual}")
    return actual


def _safe_relative(value: object, label: str) -> PurePosixPath:
    if not isinstance(value, str) or not value or "\\" in value:
        raise _error(f"{label} must be a non-empty POSIX relative path")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or path.as_posix() != value
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise _error(f"unsafe {label}: {value}")
    return path


def _schema_registry() -> tuple[dict[str, JsonObject], Registry[Any]]:
    schemas: dict[str, JsonObject] = {}
    resources: list[tuple[str, Resource[Any]]] = []
    for filename in _V2_SCHEMA_FILES:
        path = _CONTRACTS_DIRECTORY / filename
        schema, _ = _load_json(path, "v2 contract schema")
        schema_id = schema.get("$id")
        if not isinstance(schema_id, str):
            raise _error(f"v2 contract schema has no string $id: {path}")
        schemas[schema_id] = schema
        resources.append((schema_id, Resource.from_contents(schema)))
    return schemas, Registry().with_resources(resources)


def _validate_schema(value: object, schema_key: str, label: str) -> None:
    schemas, registry = _schema_registry()
    schema = next(
        (
            candidate
            for schema_id, candidate in schemas.items()
            if schema_key in schema_id
        ),
        None,
    )
    if schema is None:
        raise _error(f"missing accepted schema for {label}")
    errors = sorted(
        jsonschema.Draft202012Validator(
            schema, registry=registry, format_checker=jsonschema.FormatChecker()
        ).iter_errors(value),
        key=lambda item: item.json_path,
    )
    if errors:
        first = errors[0]
        raise _error(
            f"{label} schema validation failed at {first.json_path}: {first.message}"
        )


def _walk_rationals(value: object, path: str = "$") -> None:
    if isinstance(value, dict):
        if set(value) == {"numerator", "denominator"}:
            numerator, denominator = value["numerator"], value["denominator"]
            if (
                type(numerator) is not int
                or type(denominator) is not int
                or abs(numerator) > _MAX_SAFE
                or not 0 < denominator <= _MAX_SAFE
                or math.gcd(abs(numerator), denominator) != 1
            ):
                raise _error(f"rational at {path} is not reduced safe-integer geometry")
        for key, item in value.items():
            _walk_rationals(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _walk_rationals(item, f"{path}[{index}]")


def _fraction(value: object, label: str, *, positive: bool = False) -> Fraction:
    if not isinstance(value, dict) or set(value) != {"numerator", "denominator"}:
        raise _error(f"{label} is not a rational pair")
    numerator, denominator = value["numerator"], value["denominator"]
    if (
        type(numerator) is not int
        or type(denominator) is not int
        or abs(numerator) > _MAX_SAFE
        or not 0 < denominator <= _MAX_SAFE
        or math.gcd(abs(numerator), denominator) != 1
        or (positive and numerator <= 0)
    ):
        raise _error(f"{label} is not a reduced safe rational")
    return Fraction(numerator, denominator)


def _safe_frame(value: object, label: str, *, positive: bool = False) -> int:
    if (
        type(value) is not int
        or not 0 <= value <= _MAX_SAFE
        or (positive and value == 0)
    ):
        raise _error(f"{label} is not a safe nonnegative frame counter")
    return value


def _range(
    value: object, label: str, *, allow_zero_duration: bool = False
) -> tuple[int, int]:
    if not isinstance(value, dict) or set(value) != {"startFrame", "endFrame"}:
        raise _error(f"{label} is not a v2 half-open frame range")
    start = _safe_frame(value["startFrame"], f"{label}.startFrame")
    end = _safe_frame(value["endFrame"], f"{label}.endFrame")
    if end < start or (end == start and not allow_zero_duration):
        raise _error(f"{label} is empty or reversed")
    return start, end


def _unique_by_id(values: object, label: str, key: str = "id") -> dict[str, JsonObject]:
    if not isinstance(values, list):
        raise _error(f"{label} collection is not an array")
    result: dict[str, JsonObject] = {}
    for item in values:
        if not isinstance(item, dict) or not isinstance(item.get(key), str):
            raise _error(f"{label} has a missing or invalid {key}")
        identity = item[key]
        if identity in result:
            raise _error(f"duplicate {label} id {identity}")
        result[identity] = cast(JsonObject, item)
    return result


def _id_component(value: str, label: str) -> str:
    if not value or value in {".", ".."} or any(char in value for char in "/\\\0"):
        raise _error(f"unsafe {label}: {value!r}")
    return value


def _suffix(path: Path) -> str:
    suffix = path.suffix
    if (
        not suffix
        or len(suffix) > 17
        or any(
            character
            not in ".abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
            for character in suffix
        )
    ):
        return ".media"
    return suffix.lower()


def _validate_inputs(
    document: JsonObject,
    dependencies: JsonObject,
    manifest: JsonObject,
    report: JsonObject,
) -> None:
    for value in (document, dependencies, manifest, report):
        _walk_rationals(value)
    _validate_schema(document, "script-document-v2", "script document v2")
    _validate_schema(
        dependencies, "compiler-dependencies-v2", "compiler dependencies v2"
    )
    _validate_schema(manifest, "timeline-manifest-v2", "timeline manifest v2")
    _validate_schema(report, "build-report-v2", "build report v2")

    document_id = document.get("id")
    project_id = document.get("projectId")
    live_hash = _require_hash(
        cast(JsonObject, document.get("liveContentHash")), "document liveContentHash"
    )
    if live_hash != _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    ):
        raise _error("document liveContentHash does not match its actual saved content")
    dep_identity = cast(JsonObject, dependencies.get("document"))
    manifest_identity = cast(JsonObject, manifest.get("document"))
    report_identity = cast(JsonObject, report.get("document"))
    for identity, label in (
        (dep_identity, "dependencies document"),
        (manifest_identity, "manifest document"),
        (report_identity, "report document"),
    ):
        if (
            identity.get("documentId") != document_id
            or identity.get("projectId") != project_id
        ):
            raise _error(f"{label} identity does not match the saved script document")
        if identity.get("contentHash") != live_hash:
            raise _error(f"{label} live content hash does not match the saved document")
    if (
        dep_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
        or manifest_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
        or report_identity.get("liveHeadSequence") != document.get("liveHeadSequence")
    ):
        raise _error("document head sequence differs across frozen package inputs")
    for identity, label in (
        (manifest_identity, "manifest"),
        (report_identity, "report"),
    ):
        if (
            identity.get("revision") != dep_identity.get("revision")
            or identity.get("textHash") != dep_identity.get("textHash")
            or identity.get("settingsHash") != dep_identity.get("settingsHash")
        ):
            raise _error(
                f"{label} document revision/hash identity differs from dependencies"
            )
    narration = [
        block["text"]
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    ]
    try:
        text_hash = _hash_bytes("\n".join(narration).encode("utf-8"))
    except UnicodeError as error:
        raise _error("narration text is not valid scalar Unicode") from error
    if dep_identity.get("textHash") != text_hash:
        raise _error("document textHash does not match the exact saved narration text")
    if (
        dep_identity.get("settingsHash")
        != dependencies["authoringDefaults"]["settingsHash"]
    ):
        raise _error(
            "document settingsHash differs from its accepted authoring defaults"
        )

    build = cast(JsonObject, dependencies.get("build"))
    if (
        manifest.get("buildId") != build.get("buildId")
        or manifest.get("id") != build.get("manifestId")
        or report.get("buildId") != build.get("buildId")
        or report.get("id") != build.get("reportId")
        or cast(JsonObject, report.get("manifest")).get("id") != manifest.get("id")
    ):
        raise _error("manifest, report, and dependencies build identities do not close")
    if manifest.get("buildClass") != build.get("buildClass") or report.get(
        "buildClass"
    ) != build.get("buildClass"):
        raise _error("manifest, report, and dependencies build classes differ")
    if document_id != dep_identity.get("documentId"):
        raise _error(
            "dependencies document identity differs from the supplied document"
        )
    if report.get("dependenciesHash") != _compiler_hash(dependencies):
        raise _error(
            "build report dependenciesHash does not match canonical dependencies"
        )
    manifest_identity_hash = _compiler_hash(manifest)
    if (
        cast(JsonObject, report.get("manifest")).get("contentHash")
        != manifest_identity_hash
    ):
        raise _error(
            "build report manifest hash does not match canonical manifest JSON"
        )

    timeline = manifest.get("timeline")
    if timeline != dependencies.get("timeline") or timeline != report.get("timeline"):
        raise _error(
            "timeline settings differ across manifest, report, and dependencies"
        )
    if manifest.get("tracks") != dependencies.get("tracks"):
        raise _error("manifest tracks differ from compiler dependencies")
    if manifest.get("roles") != dependencies.get("roles"):
        raise _error("manifest roles differ from compiler dependencies")
    if manifest.get("authoringDefaults") != dependencies.get("authoringDefaults"):
        raise _error("manifest authoring defaults differ from compiler dependencies")

    readiness = cast(JsonObject, report.get("readiness"))
    if (
        report.get("status") != "ready"
        or readiness.get("preview") != "ready"
        or readiness.get("release") != "ready"
        or readiness.get("blockingIssueIds") != []
        or report.get("diagnostics") != []
        or report.get("migrationIssues") != []
        or report.get("recoveryActions") != []
    ):
        raise _error("only a fully ready v2 report can be packaged")

    _validate_manifest_semantics(document, dependencies, manifest)
    _validate_report_semantics(manifest, report, dependencies)


def _validate_manifest_semantics(
    document: JsonObject, dependencies: JsonObject, manifest: JsonObject
) -> None:
    timeline = cast(JsonObject, manifest["timeline"])
    rate = _fraction(timeline.get("frameRate"), "timeline frame rate", positive=True)
    start = _safe_frame(timeline.get("startFrame"), "timeline startFrame")
    duration = _safe_frame(
        timeline.get("durationFrames"), "timeline durationFrames", positive=True
    )
    end = start + duration
    if end > _MAX_SAFE:
        raise _error("timeline endpoint exceeds the safe integer range")

    tracks = _unique_by_id(manifest.get("tracks"), "track")
    dependency_tracks = _unique_by_id(dependencies.get("tracks"), "dependency track")
    if tracks != dependency_tracks:
        raise _error("manifest and dependencies track maps differ")
    slots: set[tuple[str, int]] = set()
    for track_record in tracks.values():
        index = _safe_frame(
            track_record.get("index"),
            f"track {track_record['id']} index",
            positive=True,
        )
        slot = (cast(str, track_record.get("kind")), index)
        if slot in slots:
            raise _error(f"duplicate {slot[0]} track index {slot[1]}")
        slots.add(slot)

    roles = cast(JsonObject, dependencies.get("roles"))
    composition = cast(JsonObject, manifest.get("composition"))
    if (
        composition.get("topology") != "primary_root_child_overlay"
        or composition.get("primaryRootTrackId") != roles.get("primaryRootTrackId")
        or composition.get("childTrackIds") != roles.get("childTrackIds")
        or composition.get("overlayTrackIds") != roles.get("overlayTrackIds")
    ):
        raise _error(
            "manifest composition topology differs from configured track roles"
        )
    root_id = cast(str, composition["primaryRootTrackId"])
    child_ids = cast(list[str], roles.get("childTrackIds", []))
    overlay_ids = cast(list[str], roles.get("overlayTrackIds", []))
    root = tracks.get(root_id)
    if root is None or root.get("kind") != "video":
        raise _error("primary root composition track is missing or not video")
    if (
        len(set(child_ids)) != len(child_ids)
        or len(set(overlay_ids)) != len(overlay_ids)
        or root_id in child_ids
        or root_id in overlay_ids
        or set(child_ids) & set(overlay_ids)
    ):
        raise _error("primary root, child, and overlay tracks must be disjoint")
    for role_key, expected_kind in (
        ("narrationTrackId", "audio"),
        ("sourceAudioTrackIds", "audio"),
        ("presenterTrackId", "video"),
        ("placeholderTrackId", "video"),
        ("markerTrackId", "video"),
    ):
        raw = roles.get(role_key)
        ids = raw if isinstance(raw, list) else [raw]
        for track_id in ids:
            if track_id is None:
                continue
            role_track = tracks.get(cast(str, track_id))
            if role_track is None or role_track.get("kind") != expected_kind:
                raise _error(
                    f"configured {role_key} refers to a missing or wrong-kind track"
                )
    for track_id in child_ids:
        if track_id not in tracks or tracks[track_id].get("kind") != "video":
            raise _error(f"configured child track {track_id} is missing or not video")
    for track_id in overlay_ids:
        if track_id not in tracks or tracks[track_id].get("kind") != "video":
            raise _error(f"configured overlay track {track_id} is missing or not video")
    role_indices = {
        track_id: _safe_frame(
            tracks[track_id].get("index"), f"track {track_id} index", positive=True
        )
        for track_id in (root_id, *child_ids, *overlay_ids)
    }
    if (
        child_ids != sorted(child_ids, key=role_indices.__getitem__)
        or overlay_ids != sorted(overlay_ids, key=role_indices.__getitem__)
        or (
            child_ids
            and role_indices[root_id] >= min(role_indices[item] for item in child_ids)
        )
        or (
            overlay_ids
            and role_indices[root_id] >= min(role_indices[item] for item in overlay_ids)
        )
        or (
            child_ids
            and overlay_ids
            and max(role_indices[item] for item in child_ids)
            >= min(role_indices[item] for item in overlay_ids)
        )
    ):
        raise _error(
            "primary root, child, and overlay tracks are not in ascending "
            "composition order"
        )

    events = _unique_by_id(manifest.get("events"), "event", "eventId")
    sources = _unique_by_id(manifest.get("sources"), "source")
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    dependency_bindings = _unique_by_id(
        dependencies.get("preparedMedia"), "prepared media", "requirementKey"
    )
    if bindings != dependency_bindings:
        raise _error("manifest preparation bindings differ from compiler dependencies")
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    root_events: list[JsonObject] = []
    visual_source_ids: set[str] = set()
    for event in events.values():
        event_id = cast(str, event["eventId"])
        event_kind = cast(str, event["kind"])
        track_id = cast(str, event["trackId"])
        event_track = tracks.get(track_id)
        if event_track is None:
            raise _error(f"event {event_id} references missing track {track_id}")
        track_kind = cast(str, event_track["kind"])
        if (event_kind in {"narration", "source_audio"}) != (track_kind == "audio"):
            raise _error(f"event {event_id} kind and track media type disagree")
        record_start, record_end = _range(
            event.get("recordRange"), f"event {event_id} recordRange"
        )
        if record_start < start or record_end > end:
            raise _error(f"event {event_id} falls outside the timeline range")
        role = event.get("trackRole")
        if event_kind == "primary_visual":
            if track_id == root_id and role == "primary_root":
                root_events.append(event)
            elif track_id in child_ids and role == "child":
                pass
            else:
                raise _error(
                    f"primary visual event {event_id} is outside a root or child track"
                )
        elif event_kind == "overlay_visual":
            if track_id not in roles.get("overlayTrackIds", []) or role != "overlay":
                raise _error(
                    f"overlay event {event_id} is outside a configured overlay track"
                )
        elif event_kind == "placeholder":
            allowed = {
                root_id,
                roles.get("placeholderTrackId"),
                roles.get("presenterTrackId"),
                *child_ids,
            }
            valid_placeholder_role = (
                (track_id == root_id and role == "primary_root")
                or (
                    track_id == roles.get("placeholderTrackId")
                    and role == "placeholder"
                )
                or (track_id == roles.get("presenterTrackId") and role == "presenter")
                or (track_id in child_ids and role == "child")
            )
            if track_id not in allowed or not valid_placeholder_role:
                raise _error(
                    f"placeholder event {event_id} is outside a supported picture track"
                )
            treatment = event.get("pictureTreatment")
            if not isinstance(treatment, dict) or treatment.get("kind") not in {
                "still",
                "slate",
            }:
                raise _error(
                    f"placeholder event {event_id} is not a static still or slate"
                )
            if treatment["kind"] == "still":
                reference = treatment.get("reference")
                if (
                    not isinstance(reference, dict)
                    or treatment.get("composition", {}).get("motionPreset") != "none"
                ):
                    raise _error(
                        f"placeholder {event_id} needs a bound still with no motion"
                    )
            elif not isinstance(treatment.get("text"), str):
                raise _error(f"placeholder slate {event_id} has no authored text")
            if track_id == root_id:
                root_events.append(event)
        elif event_kind == "narration":
            if track_id != roles.get("narrationTrackId") or role != "narration":
                raise _error(
                    f"narration event {event_id} is outside the narration track"
                )
        elif event_kind == "source_audio":
            if (
                track_id not in roles.get("sourceAudioTrackIds", [])
                or role != "source_audio"
            ):
                raise _error(f"source audio {event_id} is outside a configured track")
        elif event_kind == "script_marker":
            if track_id != roles.get("markerTrackId") or role != "marker":
                raise _error(f"script marker {event_id} is outside the marker track")
        else:
            raise _error(f"unsupported v2 event kind {event_kind!r}")

        source_id = cast(JsonObject, event.get("provenance"))["sourceId"]
        if event_kind in {
            "primary_visual",
            "overlay_visual",
            "narration",
            "source_audio",
        }:
            if not isinstance(source_id, str) or source_id not in sources:
                raise _error(
                    f"event {event_id} references missing source {source_id!r}"
                )
            if event_kind in {"primary_visual", "overlay_visual"}:
                visual_source_ids.add(source_id)
        elif event_kind == "placeholder" and source_id is not None:
            raise _error(
                f"placeholder event {event_id} must use its explicit event media"
            )

        if event_kind in {"primary_visual", "overlay_visual"}:
            source_range = event.get("sourceRange")
            source_start, source_end = _range(
                source_range, f"event {event_id} sourceRange"
            )
            treatment = event.get("pictureTreatment")
            if isinstance(treatment, dict) and treatment.get("kind") == "still_frame":
                if source_end - source_start != 1:
                    raise _error(
                        f"still event {event_id} must retain its one-frame range"
                    )
            elif source_end - source_start != record_end - record_start:
                raise _error(
                    f"dynamic visual event {event_id} requires unsupported retiming"
                )
            requirement_key = sources[source_id].get("preparationRequirementKey")
            binding = (
                bindings.get(cast(str, requirement_key))
                if requirement_key is not None
                else None
            )
            if binding is None or event.get("preparationBindingHash") != _compiler_hash(
                binding
            ):
                raise _error(
                    f"visual event {event_id} preparation binding is missing or stale"
                )
            if event.get("sourceTimeMapping") != binding.get("timeMapping"):
                raise _error(
                    f"visual event {event_id} mapping differs from preparation"
                )
        elif event_kind == "narration":
            source_record = sources[source_id]
            audio = source_record.get("narrationAudio")
            if not isinstance(audio, dict):
                raise _error(
                    f"narration event {event_id} has no compiler-pinned narration audio"
                )
            _require_hash(audio.get("audioHash"), f"narration {source_id} audioHash")
            sample_rate = _safe_frame(
                audio.get("sampleRate"),
                f"narration {source_id} sampleRate",
                positive=True,
            )
            samples = _safe_frame(
                audio.get("durationSamples"),
                f"narration {source_id} durationSamples",
                positive=True,
            )
            if (
                Fraction(samples, sample_rate)
                < Fraction(record_end - record_start, 1) / rate
            ):
                raise _error(
                    f"narration event {event_id} exceeds its verified audio asset"
                )
        elif event_kind == "source_audio":
            if (
                event.get("preparationBindingHash") is None
                or event.get("sourceTimeMapping") is None
            ):
                raise _error(
                    f"source audio event {event_id} lacks its #174 preparation mapping"
                )
            binding = next(
                (
                    candidate
                    for candidate in bindings.values()
                    if _compiler_hash(candidate) == event["preparationBindingHash"]
                ),
                None,
            )
            if binding is None or event.get("sourceTimeMapping") != binding.get(
                "timeMapping"
            ):
                raise _error(
                    f"source audio event {event_id} preparation mapping is stale"
                )

        events_by_track[track_id].append(event)

    source_audio_events = sorted(
        (
            event
            for event in events.values()
            if event["kind"] == "source_audio" and event.get("audio") is not None
        ),
        key=lambda event: event["recordRange"]["startFrame"],
    )
    furthest_source_audio_end = -1
    for event in source_audio_events:
        begin, finish = _range(
            event["recordRange"], f"source audio event {event['eventId']} recordRange"
        )
        if begin < furthest_source_audio_end:
            raise _error("enabled source-audio events overlap in record time")
        furthest_source_audio_end = max(furthest_source_audio_end, finish)

    for track_id, track_events in events_by_track.items():
        ordered = sorted(
            track_events, key=lambda event: event["recordRange"]["startFrame"]
        )
        previous_end: int | None = None
        previous_id: str | None = None
        for event in ordered:
            if event["kind"] == "script_marker":
                continue
            begin, finish = _range(
                event["recordRange"], f"event {event['eventId']} recordRange"
            )
            if previous_end is not None and begin < previous_end:
                raise _error(
                    f"events {previous_id} and {event['eventId']} overlap on {track_id}"
                )
            previous_end, previous_id = finish, cast(str, event["eventId"])

    if composition.get("rootContinuous"):
        ordered_root = sorted(
            root_events, key=lambda event: event["recordRange"]["startFrame"]
        )
        cursor = start
        if not ordered_root:
            raise _error("continuous primary root contains no visual events")
        for event in ordered_root:
            begin, finish = _range(
                event["recordRange"], f"root event {event['eventId']} range"
            )
            if begin != cursor:
                raise _error(
                    "primary root events do not form continuous timeline coverage"
                )
            cursor = finish
        if cursor != end:
            raise _error("primary root does not reach the exclusive timeline end")

    root_events_by_id = {event["eventId"]: event for event in root_events}
    for returned in composition.get("returns", []):
        root_event = root_events_by_id.get(returned.get("rootEventId"))
        frame = _safe_frame(
            returned.get("recordFrame"), "composition return recordFrame"
        )
        if root_event is None:
            raise _error("composition return references a missing primary-root event")
        root_start, root_end = _range(
            root_event["recordRange"], "return root event range"
        )
        if (
            not root_start < frame < root_end
            or returned.get("emitsNewSourceEvent") is not False
        ):
            raise _error(
                "composition return is outside its root event or emits a source event"
            )

    for source_id, source in sources.items():
        if "narrationAudio" in source:
            continue
        _require_hash(source.get("originalHash"), f"source {source_id} originalHash")
        _require_hash(source.get("deliveredHash"), f"source {source_id} deliveredHash")
        _require_hash(
            source.get("originalProbeHash"), f"source {source_id} originalProbeHash"
        )
        _require_hash(
            source.get("deliveredProbeHash"), f"source {source_id} deliveredProbeHash"
        )
        if source.get("preparationRequirementKey") not in bindings:
            raise _error(
                f"source {source_id} references a missing preparation requirement"
            )
        if source.get("sourceTimeMapping") != bindings[
            source["preparationRequirementKey"]
        ].get("timeMapping"):
            raise _error(
                f"source {source_id} time mapping differs from its preparation"
            )
        if source.get("sourceFrameMap") != source["sourceTimeMapping"].get(
            "sourceFrameMap"
        ):
            raise _error(
                f"source {source_id} source frame map differs from its mapping"
            )

    # Compiler dependencies must describe the exact same primary/child/overlay roles.
    occurrence_by_key: dict[str, JsonObject] = {}
    for item in cast(list[JsonObject], dependencies.get("occurrenceResolutions", [])):
        requirement_key = item.get("preparedMediaRequirementKey")
        if requirement_key is not None:
            occurrence_by_key[cast(str, requirement_key)] = item
    if set(bindings) != set(occurrence_by_key):
        raise _error(
            "preparation requirements do not exactly cover occurrence resolutions"
        )
    del visual_source_ids  # kept explicit above for media-input classification.


def _validate_report_semantics(
    manifest: JsonObject, report: JsonObject, dependencies: JsonObject
) -> None:
    events = _unique_by_id(manifest.get("events"), "manifest event", "eventId")
    results = _unique_by_id(report.get("eventResults"), "report event", "eventId")
    if set(results) != set(events):
        raise _error(
            "build report event results do not cover the exact manifest event set"
        )
    for event_id, event in events.items():
        result = results[event_id]
        provenance = cast(JsonObject, event["provenance"])
        if (
            result.get("kind") != event.get("kind")
            or result.get("trackId") != event.get("trackId")
            or result.get("recordRange") != event.get("recordRange")
            or result.get("sourceId") != provenance.get("sourceId")
            or result.get("disposition") != "placed"
        ):
            raise _error(
                f"build report event result does not exactly cover event {event_id}"
            )

    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "manifest preparation", "requirementKey"
    )
    report_prep = cast(JsonObject, report.get("mediaPreparation"))
    requirements = _unique_by_id(
        report_prep.get("requirements"), "report media requirement", "requirementKey"
    )
    expected_prep_status = "complete" if bindings else "not_required"
    if (
        set(requirements) != set(bindings)
        or report_prep.get("status") != expected_prep_status
    ):
        raise _error(
            "build report media preparation does not cover the exact binding set"
        )
    for key, binding in bindings.items():
        item = requirements[key]
        original = cast(JsonObject, binding["originalSource"])
        verification = cast(JsonObject, binding["verification"])
        if (
            item.get("status") != "prepared"
            or item.get("bindingHash") != _compiler_hash(binding)
            or item.get("originalHash") != original.get("contentHash")
            or item.get("deliveredHash") != verification.get("deliveredHash")
            or item.get("diagnosticIds") != []
        ):
            raise _error(
                f"build report preparation result differs for requirement {key}"
            )

    summary = cast(JsonObject, report.get("summary"))
    if (
        summary.get("eventCount") != len(events)
        or summary.get("placedCount") != len(events)
        or summary.get("blockedCount") != 0
        or summary.get("diagnosticCount") != 0
    ):
        raise _error("build report summary does not describe every event as placed")


@dataclass(frozen=True)
class _InputArtifact:
    key: str
    origin: Path
    relative_path: str
    content_hash: str
    kind: str


@dataclass(frozen=True)
class _Preparation:
    requirement_key: str
    record: JsonObject
    raw: bytes
    content_hash: str
    relative_path: str


def _validate_preparations(
    document: JsonObject,
    dependencies: JsonObject,
    manifest: JsonObject,
    report: JsonObject,
    preparation_paths: Mapping[str, Path],
) -> dict[str, _Preparation]:
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    if set(preparation_paths) != set(bindings):
        missing = sorted(set(bindings) - set(preparation_paths))
        extra = sorted(set(preparation_paths) - set(bindings))
        raise _error(
            f"preparation_paths key mismatch; missing={missing}, extra={extra}"
        )
    occurrences: dict[str, JsonObject] = {}
    for occurrence in cast(
        list[JsonObject], dependencies.get("occurrenceResolutions", [])
    ):
        key = occurrence.get("preparedMediaRequirementKey")
        if key is not None:
            occurrences[cast(str, key)] = occurrence
    prepared: dict[str, _Preparation] = {}
    for requirement_key, binding in bindings.items():
        source_path = preparation_paths[requirement_key]
        if not isinstance(source_path, Path):
            raise _error(
                f"preparation path for {requirement_key} must be a pathlib.Path"
            )
        record, raw = _load_json(
            source_path, f"#174 preparation receipt {requirement_key}"
        )
        digest = _hash_bytes(raw)
        descriptor = occurrences.get(requirement_key)
        if descriptor is None:
            raise _error(
                f"preparation receipt {requirement_key} has no compiler occurrence"
            )
        if record.get("recordVersion") != "authoring-media-preparation/v1":
            raise _error(f"prep {requirement_key} has an unsupported record version")
        if (
            record.get("requirementKey") != requirement_key
            or record.get("binding") != binding
        ):
            raise _error(f"prep {requirement_key} differs from its manifest binding")
        inputs = cast(JsonObject, record.get("inputs"))
        if (
            inputs.get("mediaReferenceId") != descriptor.get("mediaReferenceId")
            or inputs.get("sourceSnapshot") != descriptor.get("sourceSnapshot")
            or inputs.get("sourceFrameMap") != descriptor.get("sourceFrameMap")
            or inputs.get("requestedRange") != binding.get("requestedRange")
            or inputs.get("targetRate") != binding.get("targetRate")
            or inputs.get("profile") != binding.get("profile")
        ):
            raise _error(
                f"preparation receipt {requirement_key} input mapping is stale"
            )
        if (
            type(inputs.get("videoStreamIndex")) is not int
            or inputs["videoStreamIndex"] < 0
        ):
            raise _error(f"prep {requirement_key} has an invalid video stream index")
        audio_stream_index = inputs.get("audioStreamIndex")
        if audio_stream_index is not None and (
            type(audio_stream_index) is not int or audio_stream_index < 0
        ):
            raise _error(f"prep {requirement_key} has an invalid audio stream index")

        source_probe = record.get("sourceProbe")
        delivered_probe = record.get("deliveredProbe")
        tools = record.get("tools")
        profile = record.get("profile")
        policy = record.get("policy")
        commands = record.get("commands")
        geometry = record.get("geometry")
        if (
            not isinstance(source_probe, dict)
            or not isinstance(delivered_probe, dict)
            or not isinstance(tools, dict)
        ):
            raise _error(
                f"preparation receipt {requirement_key} lacks probe/tool evidence"
            )
        if (
            not isinstance(profile, dict)
            or not isinstance(policy, dict)
            or not isinstance(commands, list)
            or not isinstance(geometry, dict)
        ):
            raise _error(
                f"prep {requirement_key} lacks profile/command/geometry evidence"
            )
        original = cast(JsonObject, binding["originalSource"])
        verification = cast(JsonObject, binding["verification"])
        binding_profile = cast(JsonObject, binding["profile"])
        mapping = cast(JsonObject, binding["timeMapping"])
        if (
            identity_hash(source_probe) != original.get("probeHash")
            or identity_hash(delivered_probe) != verification.get("probeHash")
            or identity_hash(profile) != binding_profile.get("profileHash")
            or identity_hash(policy) != binding_profile.get("policyHash")
            or identity_hash(tools) != binding_profile.get("toolHash")
        ):
            raise _error(
                f"prep {requirement_key} probe/profile/tool hashes do not bind"
            )
        if mapping.get("sourceFrameMap") != descriptor.get(
            "sourceFrameMap"
        ) or mapping.get("mappingHash") != identity_hash(
            {key: value for key, value in mapping.items() if key != "mappingHash"}
        ):
            raise _error(
                f"prep {requirement_key} mapping hash or source map is invalid"
            )
        if binding.get("mode") not in {"verified_reuse", "derived_cfr"}:
            raise _error(f"preparation receipt {requirement_key} mode is unsupported")
        if binding.get("mode") == "derived_cfr":
            derivation = binding.get("derivation")
            if not isinstance(derivation, dict) or (
                derivation.get("sourceHash") != original.get("contentHash")
                or derivation.get("outputHash") != verification.get("deliveredHash")
                or derivation.get("profileHash") != binding_profile.get("profileHash")
                or derivation.get("toolHash") != binding_profile.get("toolHash")
                or derivation.get("commandHash") != identity_hash(commands)
            ):
                raise _error(
                    f"prep {requirement_key} derived output evidence is invalid"
                )
        elif (
            original.get("contentHash") != verification.get("deliveredHash")
            or "derivation" in binding
        ):
            raise _error(f"prep {requirement_key} verified-reuse identity is invalid")
        _fraction(
            geometry.get("packageStart"), f"preparation {requirement_key} packageStart"
        )
        package_end = _fraction(
            geometry.get("packageEnd"), f"preparation {requirement_key} packageEnd"
        )
        package_start = _fraction(
            geometry.get("packageStart"), f"preparation {requirement_key} packageStart"
        )
        if package_end <= package_start or not isinstance(
            geometry.get("selectedPackageFrames"), list
        ):
            raise _error(
                f"preparation receipt {requirement_key} geometry is empty or incomplete"
            )
        for index, frame in enumerate(geometry["selectedPackageFrames"]):
            _safe_frame(
                frame, f"preparation {requirement_key} selectedPackageFrames[{index}]"
            )
        for field in ("sourceCoverSurplus", "terminalQuantization"):
            _fraction(geometry.get(field), f"preparation {requirement_key} {field}")
        _safe_frame(
            geometry.get("requiredExclusiveLogicalFrame"),
            f"preparation {requirement_key} requiredExclusiveLogicalFrame",
        )
        expected_mapping_origin = _fraction(
            cast(JsonObject, descriptor["sourceFrameMap"]).get(
                "loggedTimeAtPackageFrameZero"
            ),
            f"preparation {requirement_key} logged package origin",
        )
        if binding["mode"] == "derived_cfr":
            expected_mapping_origin += package_start
        if (
            mapping.get("sourceOrigin")
            != {
                "numerator": expected_mapping_origin.numerator,
                "denominator": expected_mapping_origin.denominator,
            }
            or mapping.get("deliveredOrigin") != {"numerator": 0, "denominator": 1}
            or mapping.get("deliveredRate") != binding.get("targetRate")
        ):
            raise _error(
                f"prep {requirement_key} source/delivered time mapping is invalid"
            )
        audio_record = record.get("audio")
        source_audio_mappings = cast(JsonObject, descriptor["sourceFrameMap"]).get(
            "sourceAudioStreamMappings"
        )
        if audio_record is not None:
            if (
                not isinstance(audio_record, dict)
                or not isinstance(source_audio_mappings, list)
                or len(source_audio_mappings) != 1
            ):
                raise _error(
                    f"preparation receipt {requirement_key} has unbound audio evidence"
                )
            audio_map = cast(JsonObject, source_audio_mappings[0])
            audio_probe = audio_record.get("probe")
            audio_streams = (
                audio_probe.get("streams") if isinstance(audio_probe, dict) else None
            )
            if (
                not isinstance(audio_streams, list)
                or len(audio_streams) != 1
                or not isinstance(audio_streams[0], dict)
            ):
                raise _error(
                    f"prep {requirement_key} has an invalid prepared-audio probe"
                )
            audio_stream = cast(JsonObject, audio_streams[0])
            source_rate = audio_map.get("sampleRate")
            source_first = audio_record.get("sourceFirstSample")
            source_exclusive = audio_record.get("sourceExclusiveSample")
            resampled_first = audio_record.get("resampledFirstSample")
            resampled_exclusive = audio_record.get("resampledExclusiveSample")
            decoded_samples = audio_record.get("decodedSamples")
            if (
                audio_record.get("sourceAudioHash") != audio_map.get("audioHash")
                or type(source_rate) is not int
                or source_rate not in {44100, 48000}
                or type(source_first) is not int
                or type(source_exclusive) is not int
                or type(resampled_first) is not int
                or type(resampled_exclusive) is not int
                or type(decoded_samples) is not int
                or source_first < 0
                or source_exclusive <= source_first
                or resampled_first < 0
                or resampled_exclusive <= resampled_first
                or decoded_samples <= 0
                or abs(decoded_samples - (resampled_exclusive - resampled_first)) > 1
                or audio_stream.get("codec_name") != "pcm_s24le"
                or str(audio_stream.get("sample_rate")) != "48000"
                or audio_stream.get("channels") != audio_record.get("channels")
                or identity_hash(audio_record.get("probe"))
                != audio_record.get("probeHash")
            ):
                raise _error(
                    f"prep {requirement_key} source-audio probe/range is invalid"
                )
            for field in (
                "sourcePtsOrigin",
                "deliveredTimeAtFirstSample",
                "boundaryOffset",
                "endpointError",
                "decodedSourceTimestampResidual",
                "decodedSourceTimestampDrift",
            ):
                _fraction(
                    audio_record.get(field),
                    f"preparation {requirement_key} audio {field}",
                )
            endpoint_error = _fraction(
                audio_record.get("endpointError"),
                f"preparation {requirement_key} audio endpointError",
            )
            video_frame_map = cast(JsonObject, descriptor["sourceFrameMap"])
            audio_pts_origin = _fraction(
                audio_map.get("packagePtsOrigin"),
                f"prep {requirement_key} source-audio PTS origin",
            )
            audio_record_pts_origin = _fraction(
                audio_record.get("sourcePtsOrigin"),
                f"prep {requirement_key} prepared-audio PTS origin",
            )
            audio_logged_origin = _fraction(
                audio_map.get("loggedTimeAtPackageOrigin"),
                f"prep {requirement_key} source-audio logged origin",
            )
            video_pts_origin = _fraction(
                video_frame_map.get("packageVideoPtsOrigin"),
                f"prep {requirement_key} package-video PTS origin",
            )
            video_logged_origin = _fraction(
                video_frame_map.get("loggedTimeAtPackageFrameZero"),
                f"prep {requirement_key} package-video logged origin",
            )
            package_audio_start = video_pts_origin + package_start - audio_pts_origin
            package_audio_end = video_pts_origin + package_end - audio_pts_origin
            expected_audio_logged_origin = (
                video_logged_origin + audio_pts_origin - video_pts_origin
            )
            expected_source_first = _ceil_fraction(package_audio_start * source_rate)
            expected_source_end = _ceil_fraction(package_audio_end * source_rate)
            expected_resampled_first = _ceil_fraction(package_audio_start * 48000)
            expected_resampled_end = _ceil_fraction(package_audio_end * 48000)
            expected_offset = (
                Fraction(expected_resampled_first, 48000) - package_audio_start
            )
            expected_delivered_first = (
                package_start + expected_offset
                if binding["mode"] == "verified_reuse"
                else expected_offset
            )
            actual_offset = _fraction(
                audio_record.get("boundaryOffset"),
                f"prep {requirement_key} source-audio boundary offset",
            )
            actual_delivered_first = _fraction(
                audio_record.get("deliveredTimeAtFirstSample"),
                f"prep {requirement_key} source-audio first-sample time",
            )
            if (
                audio_map.get("probeHash") != original.get("probeHash")
                or audio_map.get("sampleRate") != source_rate
                or audio_record_pts_origin != audio_pts_origin
                or audio_logged_origin != expected_audio_logged_origin
                or source_first != expected_source_first
                or source_exclusive != expected_source_end
                or resampled_first != expected_resampled_first
                or resampled_exclusive != expected_resampled_end
                or actual_offset != expected_offset
                or actual_delivered_first != expected_delivered_first
            ):
                raise _error(
                    f"prep {requirement_key} audio coordinates do not bind to P2"
                )
            if endpoint_error > Fraction(1, 48000):
                raise _error(
                    f"prep {requirement_key} audio endpoint exceeds one sample"
                )
        if (
            record.get("audio") is None
            and binding["verification"]["sourceAudio"].get("status") == "aligned"
        ):
            raise _error(f"prep {requirement_key} omits aligned source-audio bytes")
        rel = (
            f"{BUILD_DIRECTORY}/"
            f"{_id_component(cast(str, manifest['buildId']), 'build id')}"
            f"/Preparation/receipts/{hashlib.sha256(requirement_key.encode('utf-8')).hexdigest()}/receipt.json"
        )
        prepared[requirement_key] = _Preparation(
            requirement_key, record, raw, digest, rel
        )

    del document, report
    return prepared


def _media_artifacts(
    manifest: JsonObject,
    prepared: Mapping[str, _Preparation],
    media_paths: Mapping[str, Path],
) -> dict[str, _InputArtifact]:
    sources = _unique_by_id(manifest.get("sources"), "source")
    events = _unique_by_id(manifest.get("events"), "event", "eventId")
    expected_hashes: dict[str, tuple[str, str, str]] = {}
    source_usage: dict[str, set[str]] = defaultdict(set)
    for event in events.values():
        kind = cast(str, event["kind"])
        source_id = cast(JsonObject, event["provenance"]).get("sourceId")
        if kind in {"primary_visual", "overlay_visual", "narration", "source_audio"}:
            if not isinstance(source_id, str):
                raise _error(f"event {event['eventId']} has no source identity")
            source_usage[source_id].add(kind)
    for source_id, source in sources.items():
        narration = source.get("narrationAudio")
        if isinstance(narration, dict):
            expected = _require_hash(
                narration.get("audioHash"), f"narration {source_id} audio hash"
            )
            kinds = source_usage.get(source_id, set())
            if kinds and kinds != {"narration"}:
                raise _error(
                    f"narration source {source_id} is assigned to a non-narration event"
                )
            expected_hashes[f"source:{source_id}"] = (expected, "Narration", "audio")
            continue
        expected = _require_hash(
            source.get("deliveredHash"), f"source {source_id} delivered hash"
        )
        kinds = source_usage.get(source_id, set())
        if "narration" in kinds or not kinds:
            raise _error(f"prepared source {source_id} has no matching visual event")
        event_treatments = {
            cast(JsonObject, event.get("pictureTreatment") or {}).get("kind")
            for event in events.values()
            if cast(JsonObject, event["provenance"]).get("sourceId") == source_id
            and event["kind"] in {"primary_visual", "overlay_visual"}
        }
        native_kind = "still" if event_treatments == {"still_frame"} else "video"
        expected_hashes[f"source:{source_id}"] = (expected, "Resolved", native_kind)
        original_hash = _require_hash(
            source.get("originalHash"), f"source {source_id} original hash"
        )
        expected_hashes[f"original:{source_id}"] = (
            original_hash,
            "Preparation",
            "original",
        )

    for event in events.values():
        kind = cast(str, event["kind"])
        event_id = cast(str, event["eventId"])
        if kind == "placeholder":
            treatment = cast(JsonObject, event["pictureTreatment"])
            if treatment["kind"] == "slate":
                timeline = cast(JsonObject, manifest["timeline"])
                generated = render_placeholder_slate(
                    cast(str, treatment["text"]),
                    _safe_frame(timeline.get("width"), "timeline width", positive=True),
                    _safe_frame(
                        timeline.get("height"), "timeline height", positive=True
                    ),
                )
                expected = _hash_bytes(generated)
            else:
                reference = cast(JsonObject, treatment["reference"])
                expected = _require_hash(
                    reference.get("contentHash"),
                    f"placeholder {event_id} reference hash",
                )
            expected_hashes[f"event:{event_id}"] = (expected, "Resolved", "still")
        elif kind == "source_audio":
            binding_hash = event.get("preparationBindingHash")
            preparation = next(
                (
                    item
                    for item in prepared.values()
                    if _compiler_hash(item.record.get("binding")) == binding_hash
                ),
                None,
            )
            if preparation is None or not isinstance(
                preparation.record.get("audio"), dict
            ):
                raise _error(
                    f"source audio event {event_id} has no hash-bound #174 WAV"
                )
            audio = cast(JsonObject, preparation.record["audio"])
            expected = _require_hash(
                audio.get("contentHash"), f"source audio event {event_id} contentHash"
            )
            audio_info = cast(JsonObject, event["audio"])
            if audio_info.get("audioHash") != audio.get("sourceAudioHash"):
                raise _error(f"source audio {event_id} is not bound to its #174 stream")
            source_map = cast(
                JsonObject,
                cast(JsonObject, event["sourceTimeMapping"])["sourceFrameMap"],
            )
            audio_maps = source_map.get("sourceAudioStreamMappings")
            if (
                not isinstance(audio_maps, list)
                or len(audio_maps) != 1
                or audio_maps[0].get("audioHash") != audio_info.get("audioHash")
            ):
                raise _error(
                    f"source audio {event_id} is not bound to one verified stream"
                )
            sample_range = cast(JsonObject, audio_info.get("sampleRange"))
            sample_start, sample_end = _range(
                sample_range, f"source audio event {event_id} sampleRange"
            )
            if (
                sample_start < audio["sourceFirstSample"]
                or sample_end > audio["sourceExclusiveSample"]
            ):
                raise _error(
                    f"source audio {event_id} exceeds the prepared sample interval"
                )
            if (
                media_paths.get(f"event:{event_id}") is not None
                and media_paths[f"event:{event_id}"].suffix.lower() != ".wav"
            ):
                raise _error(f"source audio {event_id} must use the #174 WAV sidecar")
            expected_hashes[f"event:{event_id}"] = (expected, "Narration", "audio")

    if set(media_paths) != set(expected_hashes):
        missing = sorted(set(expected_hashes) - set(media_paths))
        extra = sorted(set(media_paths) - set(expected_hashes))
        raise _error(f"media_paths key mismatch; missing={missing}, extra={extra}")
    build_id = _id_component(cast(str, manifest["buildId"]), "build id")
    artifacts: dict[str, _InputArtifact] = {}
    for key, (expected_hash, area, kind) in expected_hashes.items():
        source_path = media_paths[key]
        if not isinstance(source_path, Path):
            raise _error(f"media path for {key} must be a pathlib.Path")
        _require_path_components_no_symlink(source_path, f"media path {key}")
        _require_regular(source_path, f"media path {key}")
        actual = _file_hash(source_path)
        if actual != expected_hash:
            raise _error(f"media hash mismatch for {key}: {expected_hash} != {actual}")
        suffix = _suffix(source_path)
        if key.startswith("source:"):
            identity = _id_component(key.removeprefix("source:"), "source id")
            relative = f"{MEDIA_DIRECTORY}/{area}/{identity}{suffix}"
        elif key.startswith("original:"):
            identity = _id_component(key.removeprefix("original:"), "source id")
            relative = (
                f"{BUILD_DIRECTORY}/{build_id}/Preparation/original/{identity}{suffix}"
            )
        else:
            identity = _id_component(key.removeprefix("event:"), "event id")
            event = events[identity]
            if event["kind"] == "placeholder":
                treatment = cast(JsonObject, event["pictureTreatment"])
                if (
                    treatment.get("kind") == "slate"
                    and source_path.suffix.lower() != ".png"
                ):
                    raise _error(f"placeholder slate {identity} must use PNG bytes")
            relative = f"{MEDIA_DIRECTORY}/{area}/{identity}{suffix}"
        _safe_relative(relative, f"package path for {key}")
        artifacts[key] = _InputArtifact(key, source_path, relative, actual, kind)
    return artifacts


def _ceil_fraction(value: Fraction) -> int:
    return -((-value.numerator) // value.denominator)


def _source_audio_range(
    event: JsonObject,
    preparation: _Preparation,
    timeline_rate: Fraction,
) -> dict[str, int]:
    event_id = cast(str, event["eventId"])
    audio_record = cast(JsonObject, preparation.record["audio"])
    audio = cast(JsonObject, event["audio"])
    mapping = cast(JsonObject, event["sourceTimeMapping"])
    source_frame_map = cast(JsonObject, mapping["sourceFrameMap"])
    stream_mappings = source_frame_map.get("sourceAudioStreamMappings")
    if not isinstance(stream_mappings, list) or len(stream_mappings) != 1:
        raise _error(
            f"source audio event {event_id} has no unique verified source stream"
        )
    stream = cast(JsonObject, stream_mappings[0])
    source_sample_rate = _safe_frame(
        stream.get("sampleRate"), f"source audio {event_id} sampleRate", positive=True
    )
    audio_range = cast(JsonObject, audio["sampleRange"])
    sample_start, sample_end = _range(
        audio_range, f"source audio {event_id} sampleRange"
    )
    audio_probe = cast(JsonObject, audio_record.get("probe"))
    audio_streams = audio_probe.get("streams")
    if (
        not isinstance(audio_streams, list)
        or len(audio_streams) != 1
        or not isinstance(audio_streams[0], dict)
    ):
        raise _error(f"source audio event {event_id} has no unique prepared PCM stream")
    audio_stream = cast(JsonObject, audio_streams[0])
    if (
        audio_stream.get("codec_name") != "pcm_s24le"
        or str(audio_stream.get("sample_rate")) != "48000"
    ):
        raise _error(
            f"source audio event {event_id} is not the verified 48 kHz PCM sidecar"
        )
    # The accepted #174 receipt pins PCM rate in its independently hashed probe;
    # it intentionally has no redundant top-level audio.sampleRate field.
    output_sample_rate = 48000
    resampled_first = _safe_frame(
        audio_record.get("resampledFirstSample"),
        f"source audio {event_id} resampledFirstSample",
    )
    # P2's verified binding maps the original source sample edge to the prepared
    # 48 kHz sidecar by subtracting its absolute first PCM sample. Keeping this
    # in exact rational seconds avoids mixing package PTS and delivered origins.
    local_start = Fraction(sample_start, source_sample_rate) - Fraction(
        resampled_first, output_sample_rate
    )
    local_end = Fraction(sample_end, source_sample_rate) - Fraction(
        resampled_first, output_sample_rate
    )
    if local_end <= local_start:
        raise _error(
            f"source audio event {event_id} maps to an empty or reversed WAV interval"
        )
    start_frames = local_start * timeline_rate
    end_frames = local_end * timeline_rate
    if start_frames.denominator != 1 or end_frames.denominator != 1:
        raise _error(f"source audio {event_id} does not map to exact timeline frames")
    start_counter, end_counter = start_frames.numerator, end_frames.numerator
    record_start, record_end = _range(
        event["recordRange"], f"source audio event {event_id} recordRange"
    )
    if (
        start_counter < 0
        or end_counter <= start_counter
        or end_counter - start_counter != record_end - record_start
    ):
        raise _error(
            f"source audio {event_id} native range differs from record duration"
        )
    first_sample = (
        _ceil_fraction(Fraction(sample_start * output_sample_rate, source_sample_rate))
        - resampled_first
    )
    exclusive_sample = (
        _ceil_fraction(Fraction(sample_end * output_sample_rate, source_sample_rate))
        - resampled_first
    )
    decoded_samples = _safe_frame(
        audio_record.get("decodedSamples"),
        f"source audio {event_id} decodedSamples",
        positive=True,
    )
    if not 0 <= first_sample < exclusive_sample <= decoded_samples:
        raise _error(
            f"source audio event {event_id} maps outside its verified WAV sidecar"
        )
    available_frames = Fraction(decoded_samples, output_sample_rate) * timeline_rate
    if Fraction(end_counter, 1) > available_frames:
        raise _error(f"source audio {event_id} frame range exceeds WAV duration")
    return {"startFrame": start_counter, "durationFrames": end_counter - start_counter}


def _delivery_view(
    manifest: JsonObject,
    dependencies: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    *,
    source_paths: Mapping[str, str] | None = None,
    validate: bool = True,
) -> JsonObject:
    events = cast(list[JsonObject], manifest["events"])
    source_records = _unique_by_id(manifest.get("sources"), "source")
    binding_by_hash = {
        _compiler_hash(item.record["binding"]): item for item in prepared.values()
    }
    timeline_rate = _fraction(
        cast(JsonObject, manifest["timeline"]).get("frameRate"),
        "timeline frame rate",
        positive=True,
    )

    source_specs: dict[str, tuple[str, str, str]] = {}
    event_sources: dict[str, str] = {}
    for event in events:
        kind = cast(str, event["kind"])
        event_id = cast(str, event["eventId"])
        provenance = cast(JsonObject, event["provenance"])
        if kind == "script_marker":
            continue
        if kind == "placeholder":
            source_id = event_id
            key = f"event:{event_id}"
            native_kind = "still"
        elif kind == "source_audio":
            source_id = event_id
            key = f"event:{event_id}"
            native_kind = "audio"
        else:
            source_id = cast(str, provenance["sourceId"])
            key = f"source:{source_id}"
            source = source_records[source_id]
            if isinstance(source.get("narrationAudio"), dict):
                native_kind = "audio"
            else:
                treatment = event.get("pictureTreatment")
                native_kind = (
                    "still"
                    if isinstance(treatment, dict)
                    and treatment.get("kind") == "still_frame"
                    else "video"
                )
        artifact = artifacts.get(key)
        if artifact is None:
            raise _error(
                f"delivery view event {event_id} has no explicit media bytes for {key}"
            )
        expected_kind = artifact.kind
        if expected_kind != native_kind and not (
            expected_kind == "video" and native_kind == "still"
        ):
            raise _error(f"delivery view source {source_id} has conflicting media kind")
        if source_paths is not None:
            package_path = source_paths.get(source_id)
            if package_path is None:
                raise _error(
                    f"delivery view source {source_id} has no verified package path"
                )
        else:
            package_path = artifact.relative_path
        spec = (native_kind, package_path, artifact.content_hash)
        previous = source_specs.get(source_id)
        if previous is not None and previous != spec:
            raise _error(f"delivery source {source_id} has conflicting reuse")
        source_specs[source_id] = spec
        event_sources[event_id] = source_id

    sources_view = [
        {"id": source_id, "kind": kind, "path": path, "contentHash": content_hash}
        for source_id, (kind, path, content_hash) in source_specs.items()
    ]
    tracks = _unique_by_id(manifest.get("tracks"), "track")
    events_view: list[JsonObject] = []
    markers: list[JsonObject] = []
    for event in events:
        event_id = cast(str, event["eventId"])
        kind = cast(str, event["kind"])
        record_start, record_end = _range(
            event["recordRange"], f"event {event_id} recordRange"
        )
        record_range = {
            "startFrame": record_start,
            "durationFrames": record_end - record_start,
        }
        if kind == "script_marker":
            marker = cast(JsonObject, event["marker"])
            markers.append(
                {
                    "id": event_id,
                    "frame": record_start,
                    "color": "YELLOW",
                    "name": marker["text"],
                    "note": marker["text"],
                    "provenance": event,
                }
            )
            continue
        source_range: JsonObject | None
        if kind in {"primary_visual", "overlay_visual"}:
            selected_start, selected_end = _range(
                event.get("sourceRange"), f"event {event_id} sourceRange"
            )
            if (
                isinstance(event.get("pictureTreatment"), dict)
                and event["pictureTreatment"].get("kind") == "still_frame"
            ):
                source_range = {
                    "startFrame": selected_start,
                    "durationFrames": record_end - record_start,
                }
            else:
                source_range = {
                    "startFrame": selected_start,
                    "durationFrames": selected_end - selected_start,
                }
        elif kind == "placeholder" or kind == "narration":
            source_range = {
                "startFrame": 0,
                "durationFrames": record_end - record_start,
            }
        elif kind == "source_audio":
            binding_hash = cast(str, event["preparationBindingHash"])
            prep = binding_by_hash.get(binding_hash)
            if prep is None or prep.record.get("audio") is None:
                raise _error(
                    f"source audio event {event_id} has no validated #174 sidecar"
                )
            source_range = _source_audio_range(event, prep, timeline_rate)
        else:
            raise _error(f"unsupported delivery event kind {kind!r}")
        if source_range is not None:
            _safe_frame(
                source_range.get("startFrame"), f"event {event_id} native source start"
            )
            _safe_frame(
                source_range.get("durationFrames"),
                f"event {event_id} native source duration",
                positive=True,
            )
        track = tracks[cast(str, event["trackId"])]
        events_view.append(
            {
                "id": event_id,
                "kind": kind,
                "sourceId": event_sources[event_id],
                "trackId": event["trackId"],
                "trackKind": track["kind"],
                "recordRange": record_range,
                "sourceRange": source_range,
                "v2Event": event,
                "gainDb": event["audio"]["gainDb"]
                if isinstance(event.get("audio"), dict)
                else None,
                "pictureTreatment": event.get("pictureTreatment"),
            }
        )
    view = {
        "schemaVersion": VIEW_SCHEMA_VERSION,
        "timeline": manifest["timeline"],
        "tracks": manifest["tracks"],
        "sources": sources_view,
        "events": events_view,
        "markers": markers,
        "composition": manifest["composition"],
    }
    if validate:
        _validate_delivery_view(manifest, dependencies, view, prepared, artifacts)
    return view


def _validate_delivery_view(
    manifest: JsonObject,
    dependencies: JsonObject,
    view: JsonObject,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
) -> None:
    if set(view) != {
        "schemaVersion",
        "timeline",
        "tracks",
        "sources",
        "events",
        "markers",
        "composition",
    }:
        raise _error("delivery view has missing or unexpected top-level fields")
    if view.get("schemaVersion") != VIEW_SCHEMA_VERSION:
        raise _error("delivery view is not explicitly resolve-native-view/v2")
    sources = _unique_by_id(view.get("sources"), "delivery source")
    expected_source_ids = {
        event["eventId"]
        if event["kind"] in {"placeholder", "source_audio"}
        else cast(JsonObject, event["provenance"])["sourceId"]
        for event in cast(list[JsonObject], manifest["events"])
        if event["kind"] != "script_marker"
    }
    if set(sources) != expected_source_ids:
        raise _error("delivery view source set differs from its media events")
    source_paths: dict[str, str] = {}
    for source_id, source in sources.items():
        if set(source) != {"id", "kind", "path", "contentHash"}:
            raise _error(f"delivery source {source_id} has unexpected fields")
        relative = _safe_relative(
            source.get("path"), f"delivery source {source_id} path"
        )
        if len(relative.parts) != 3 or relative.parts[0] != MEDIA_DIRECTORY:
            raise _error(
                f"delivery source {source_id} path is outside the package Media tree"
            )
        expected_area = "Narration" if source.get("kind") == "audio" else "Resolved"
        if relative.parts[1] != expected_area or not relative.name.startswith(
            f"{source_id}."
        ):
            raise _error(f"delivery source {source_id} has a mismatched package path")
        if source.get("kind") not in {"video", "audio", "still"}:
            raise _error(f"delivery source {source_id} has unsupported native kind")
        _require_hash(
            source.get("contentHash"), f"delivery source {source_id} contentHash"
        )
        source_paths[source_id] = relative.as_posix()

    artifact_map: dict[str, _InputArtifact] = {}
    manifest_sources = _unique_by_id(manifest.get("sources"), "manifest source")
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            item = cast(JsonObject, source["narrationAudio"])
            content_hash = _require_hash(
                item.get("audioHash"), f"narration {source_id} audioHash"
            )
            view_source_id = source_id
        else:
            content_hash = _require_hash(
                source.get("deliveredHash"), f"source {source_id} deliveredHash"
            )
            view_source_id = source_id
        package_source = sources.get(view_source_id)
        if package_source is None or package_source.get("contentHash") != content_hash:
            raise _error(
                f"delivery source {source_id} content hash differs from the manifest"
            )
        artifact_map[f"source:{source_id}"] = _InputArtifact(
            f"source:{source_id}",
            Path("."),
            package_source["path"],
            content_hash,
            package_source["kind"],
        )
        if "narrationAudio" not in source:
            artifact_map[f"original:{source_id}"] = _InputArtifact(
                f"original:{source_id}",
                Path("."),
                "",
                source["originalHash"],
                "original",
            )

    binding_by_hash = {
        _compiler_hash(item.record["binding"]): item for item in prepared.values()
    }
    for event in cast(list[JsonObject], manifest["events"]):
        event_id = cast(str, event["eventId"])
        if event["kind"] == "placeholder":
            treatment = cast(JsonObject, event["pictureTreatment"])
            if treatment["kind"] == "slate":
                timeline = cast(JsonObject, manifest["timeline"])
                content_hash = _hash_bytes(
                    render_placeholder_slate(
                        cast(str, treatment["text"]),
                        _safe_frame(
                            timeline.get("width"), "timeline width", positive=True
                        ),
                        _safe_frame(
                            timeline.get("height"), "timeline height", positive=True
                        ),
                    )
                )
            else:
                content_hash = _require_hash(
                    cast(JsonObject, treatment["reference"]).get("contentHash"),
                    f"placeholder {event_id} reference hash",
                )
            package_source = sources[event_id]
            if package_source.get("contentHash") != content_hash:
                raise _error(
                    f"placeholder {event_id} does not retain its reference bytes"
                )
            artifact_map[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                Path("."),
                package_source["path"],
                content_hash,
                "still",
            )
        elif event["kind"] == "source_audio":
            binding_hash = cast(str, event["preparationBindingHash"])
            prep = binding_by_hash.get(binding_hash)
            if prep is None or not isinstance(prep.record.get("audio"), dict):
                raise _error(
                    f"source audio event {event_id} has no validated preparation WAV"
                )
            content_hash = _require_hash(
                cast(JsonObject, prep.record["audio"]).get("contentHash"),
                f"source audio {event_id} content hash",
            )
            package_source = sources[event_id]
            if package_source.get("contentHash") != content_hash:
                raise _error(f"source audio {event_id} does not retain its #174 WAV")
            artifact_map[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                Path("."),
                package_source["path"],
                content_hash,
                "audio",
            )

    expected = _delivery_view(
        manifest,
        dependencies,
        prepared,
        artifact_map,
        source_paths=source_paths,
        validate=False,
    )
    if view != expected:
        raise _error("delivery view differs from the exact v2 manifest projection")


def _otio_rate(value: Fraction) -> float:
    return value.numerator / value.denominator


def _otio_time(frames: int, rate: Fraction) -> Any:
    return otio.opentime.RationalTime(frames, _otio_rate(rate))


def _otio_range(start: int, duration: int, rate: Fraction) -> Any:
    return otio.opentime.TimeRange(_otio_time(start, rate), _otio_time(duration, rate))


def _otio_track_kind(kind: str) -> str:
    if kind == "video":
        return cast(str, otio.schema.Track.Kind.Video)
    if kind == "audio":
        return cast(str, otio.schema.Track.Kind.Audio)
    if kind == "subtitle":
        # OTIO accepts custom track-kind labels and round-trips them in its JSON
        # adapter; the accepted v2 contract has subtitle tracks but no subtitle
        # event kind yet.
        return "Subtitle"
    raise _error(f"unsupported OTIO track kind {kind!r}")


def _otio_track_order(tracks: list[JsonObject]) -> list[JsonObject]:
    kind_order = {"video": 0, "audio": 1, "subtitle": 2}
    for track in tracks:
        if track.get("kind") not in kind_order:
            _otio_track_kind(cast(str, track.get("kind")))
    return sorted(
        tracks,
        key=lambda item: (
            kind_order[cast(str, item["kind"])],
            _safe_frame(
                item.get("index"), f"track {item.get('id')} index", positive=True
            ),
        ),
    )


def _plain_otio(value: Any) -> Any:
    if hasattr(value, "items"):
        return {key: _plain_otio(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)) or type(value).__name__ == "AnyVector":
        return [_plain_otio(item) for item in value]
    return value


def _time_frames(value: Any, rate: Fraction, label: str) -> int:
    try:
        frames = value.rescaled_to(_otio_rate(rate)).to_frames()
    except (AttributeError, TypeError, ValueError, RuntimeError) as error:
        raise _error(f"OTIO {label} is not valid frame time: {error}") from error
    rounded = round(frames)
    if not math.isfinite(frames) or abs(frames - rounded) > 1e-6:
        raise _error(f"OTIO {label} does not land on an exact frame boundary")
    return int(rounded)


def _event_source_rate(event: JsonObject, timeline_rate: Fraction) -> Fraction:
    if event.get("kind") in {"primary_visual", "overlay_visual"}:
        treatment = event.get("pictureTreatment")
        if isinstance(treatment, dict) and treatment.get("kind") == "still_frame":
            return timeline_rate
        mapping = cast(JsonObject, event["v2Event"].get("sourceTimeMapping"))
        return _fraction(
            mapping.get("deliveredRate"),
            f"event {event['id']} delivered rate",
            positive=True,
        )
    return timeline_rate


def _build_otio(view: JsonObject, manifest_id: str, build_id: str) -> Any:
    timeline_data = cast(JsonObject, view["timeline"])
    timeline_rate = _fraction(
        timeline_data["frameRate"], "delivery view frame rate", positive=True
    )
    start = _safe_frame(timeline_data["startFrame"], "delivery view start frame")
    end = start + _safe_frame(
        timeline_data["durationFrames"], "delivery view duration", positive=True
    )
    timeline = otio.schema.Timeline(
        name=f"VERA build {build_id}",
        global_start_time=_otio_time(start, timeline_rate),
    )
    timeline.metadata["vera"] = {
        "schema_version": VIEW_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "build_id": build_id,
        "timeline": timeline_data,
        "composition": view["composition"],
    }
    sources = _unique_by_id(view["sources"], "delivery source")
    events_by_track: defaultdict[str, list[JsonObject]] = defaultdict(list)
    for event in cast(list[JsonObject], view["events"]):
        events_by_track[cast(str, event["trackId"])].append(event)

    for track_data in _otio_track_order(cast(list[JsonObject], view["tracks"])):
        track_id = cast(str, track_data["id"])
        track = otio.schema.Track(
            name=cast(str, track_data["name"]),
            kind=_otio_track_kind(cast(str, track_data["kind"])),
            metadata={
                "vera": {
                    "track_id": track_id,
                    "track_kind": track_data["kind"],
                    "track_index": track_data["index"],
                }
            },
        )
        cursor = start
        ordered = sorted(
            events_by_track[track_id],
            key=lambda item: item["recordRange"]["startFrame"],
        )
        for event in ordered:
            record = cast(JsonObject, event["recordRange"])
            record_start = _safe_frame(
                record.get("startFrame"), f"event {event['id']} record start"
            )
            duration = _safe_frame(
                record.get("durationFrames"),
                f"event {event['id']} record duration",
                positive=True,
            )
            if record_start < cursor or record_start + duration > end:
                raise _error(
                    f"delivery event {event['id']} cannot be placed on its OTIO track"
                )
            if record_start > cursor:
                track.append(
                    otio.schema.Gap(
                        source_range=_otio_range(
                            0, record_start - cursor, timeline_rate
                        )
                    )
                )
            source = sources[cast(str, event["sourceId"])]
            source_range = cast(JsonObject, event["sourceRange"])
            source_start = _safe_frame(
                source_range.get("startFrame"), f"event {event['id']} source start"
            )
            source_duration = _safe_frame(
                source_range.get("durationFrames"),
                f"event {event['id']} source duration",
                positive=True,
            )
            source_rate = _event_source_rate(event, timeline_rate)
            if (
                Fraction(source_duration, 1) / source_rate
                != Fraction(duration, 1) / timeline_rate
            ):
                raise _error(
                    f"event {event['id']} source duration differs from record duration"
                )
            source_path = _safe_relative(
                source.get("path"), f"event {event['id']} media path"
            )
            reference = otio.schema.ExternalReference(
                target_url=source_path.as_posix(),
                available_range=_otio_range(
                    0, source_start + source_duration, source_rate
                ),
                metadata={
                    "vera": {
                        "source_id": source["id"],
                        "source_kind": source["kind"],
                        "content_hash": source["contentHash"],
                    }
                },
            )
            clip = otio.schema.Clip(
                name=f"{source['kind']}: {source_path.name}",
                media_reference=reference,
                source_range=_otio_range(source_start, source_duration, source_rate),
                metadata={
                    "vera": {
                        "event_id": event["id"],
                        "event_kind": event["kind"],
                        "source_id": event["sourceId"],
                        "source_kind": source["kind"],
                        "track_id": event["trackId"],
                        "track_kind": event["trackKind"],
                        "record_range": record,
                        "source_range": source_range,
                        "gain_db": event["gainDb"],
                        "picture_treatment": event["pictureTreatment"],
                        "v2_event": event["v2Event"],
                    }
                },
            )
            track.append(clip)
            cursor = record_start + duration
        if cursor < end:
            track.append(
                otio.schema.Gap(
                    source_range=_otio_range(0, end - cursor, timeline_rate)
                )
            )
        timeline.tracks.append(track)

    for marker_data in cast(list[JsonObject], view["markers"]):
        frame = _safe_frame(
            marker_data.get("frame"), f"marker {marker_data['id']} frame"
        )
        timeline.tracks.markers.append(
            otio.schema.Marker(
                name=cast(str, marker_data["name"]),
                marked_range=_otio_range(frame - start, 0, timeline_rate),
                color=cast(
                    Any,
                    getattr(
                        otio.schema.MarkerColor,
                        str(marker_data["color"]).upper(),
                        otio.schema.MarkerColor.RED,
                    ),
                ),
                metadata={"vera": marker_data},
            )
        )
    return timeline


def _verify_otio(package_root: Path, manifest: JsonObject, view: JsonObject) -> None:
    try:
        timeline = otio.adapters.read_from_file(str(package_root / OTIO_FILENAME))
    except (OSError, RuntimeError, ValueError) as error:
        raise _error(f"OTIO could not be parsed: {error}") from error
    if not isinstance(timeline, otio.schema.Timeline):
        raise _error("OTIO root is not a Timeline")
    timeline_data = cast(JsonObject, view["timeline"])
    rate = _fraction(
        timeline_data["frameRate"], "delivery view frame rate", positive=True
    )
    start = _safe_frame(timeline_data["startFrame"], "delivery view start frame")
    end = start + _safe_frame(
        timeline_data["durationFrames"], "delivery view duration", positive=True
    )
    metadata = _plain_otio(timeline.metadata.get("vera", {}))
    if (
        timeline.global_start_time is None
        or _time_frames(timeline.global_start_time, rate, "global start") != start
        or metadata.get("schema_version") != VIEW_SCHEMA_VERSION
        or metadata.get("manifest_id") != manifest.get("id")
        or metadata.get("build_id") != manifest.get("buildId")
        or metadata.get("timeline") != timeline_data
        or metadata.get("composition") != view.get("composition")
    ):
        raise _error(
            "OTIO timeline identity, start, or composition differs from v2 view"
        )
    expected_tracks = _otio_track_order(cast(list[JsonObject], view["tracks"]))
    if len(timeline.tracks) != len(expected_tracks):
        raise _error("OTIO track count differs from delivery view")
    expected_events = _unique_by_id(view["events"], "delivery event")
    actual_ids: set[str] = set()
    for actual_track, expected_track in zip(
        timeline.tracks, expected_tracks, strict=True
    ):
        track_metadata = _plain_otio(actual_track.metadata.get("vera", {}))
        if (
            actual_track.name != expected_track["name"]
            or actual_track.kind != _otio_track_kind(cast(str, expected_track["kind"]))
            or track_metadata.get("track_id") != expected_track["id"]
            or track_metadata.get("track_kind") != expected_track["kind"]
            or track_metadata.get("track_index") != expected_track["index"]
        ):
            raise _error(
                f"OTIO track differs from delivery view track {expected_track['id']}"
            )
        cursor = start
        for child in actual_track:
            duration = _time_frames(child.duration(), rate, "track child duration")
            if isinstance(child, otio.schema.Gap):
                cursor += duration
                continue
            if not isinstance(child, otio.schema.Clip):
                raise _error(
                    f"OTIO contains unsupported track child {type(child).__name__}"
                )
            vera = _plain_otio(child.metadata.get("vera", {}))
            event_id = vera.get("event_id")
            if (
                not isinstance(event_id, str)
                or event_id in actual_ids
                or event_id not in expected_events
            ):
                raise _error(
                    "OTIO event metadata is missing, duplicated, or unexpected"
                )
            expected = expected_events[event_id]
            record = cast(JsonObject, expected["recordRange"])
            source_range = cast(JsonObject, expected["sourceRange"])
            source = next(
                item
                for item in cast(list[JsonObject], view["sources"])
                if item["id"] == expected["sourceId"]
            )
            source_rate = _event_source_rate(expected, rate)
            reference = child.media_reference
            if (
                not isinstance(reference, otio.schema.ExternalReference)
                or child.source_range is None
            ):
                raise _error(
                    f"OTIO event {event_id} has no external media/source range"
                )
            ref_metadata = _plain_otio(reference.metadata.get("vera", {}))
            event_record_start = _safe_frame(
                record["startFrame"], f"event {event_id} record start"
            )
            event_record_duration = _safe_frame(
                record["durationFrames"],
                f"event {event_id} record duration",
                positive=True,
            )
            if cursor != event_record_start or duration != event_record_duration:
                raise _error(
                    f"OTIO event {event_id} record placement differs from delivery view"
                )
            actual_source_start = _time_frames(
                child.source_range.start_time,
                source_rate,
                f"event {event_id} source start",
            )
            actual_source_duration = _time_frames(
                child.source_range.duration,
                source_rate,
                f"event {event_id} source duration",
            )
            actual_source = {
                "startFrame": actual_source_start,
                "durationFrames": actual_source_duration,
            }
            if (
                actual_source != source_range
                or reference.target_url != source["path"]
                or ref_metadata
                != {
                    "source_id": source["id"],
                    "source_kind": source["kind"],
                    "content_hash": source["contentHash"],
                }
                or vera.get("event_kind") != expected["kind"]
                or vera.get("source_id") != expected["sourceId"]
                or vera.get("source_kind") != source["kind"]
                or vera.get("track_id") != expected["trackId"]
                or vera.get("track_kind") != expected["trackKind"]
                or vera.get("record_range") != record
                or vera.get("source_range") != source_range
                or vera.get("gain_db") != expected["gainDb"]
                or vera.get("picture_treatment") != expected["pictureTreatment"]
                or vera.get("v2_event") != expected["v2Event"]
            ):
                raise _error(f"OTIO event {event_id} differs from delivery view")
            actual_ids.add(event_id)
            cursor += duration
        if cursor != end:
            raise _error(f"OTIO duration differs on track {expected_track['id']}")
    if actual_ids != set(expected_events):
        raise _error("OTIO event set differs from delivery view")

    expected_markers = cast(list[JsonObject], view["markers"])
    if len(timeline.tracks.markers) != len(expected_markers):
        raise _error("OTIO marker count differs from delivery view")
    for actual, expected in zip(timeline.tracks.markers, expected_markers, strict=True):
        metadata = _plain_otio(actual.metadata.get("vera", {}))
        frame = (
            _time_frames(
                actual.marked_range.start_time, rate, f"marker {expected['id']} frame"
            )
            + start
        )
        if (
            actual.name != expected["name"]
            or frame != expected["frame"]
            or actual.marked_range.duration.to_frames() != 0
            or metadata != expected
        ):
            raise _error(
                f"OTIO marker differs from delivery view marker {expected['id']}"
            )
    if list(timeline.tracks.find_children(descended_from_type=otio.schema.Transition)):
        raise _error("OTIO contains unintended transition objects")


def _walk_package(root: Path) -> tuple[set[str], set[str]]:
    files: set[str] = set()
    directories: set[str] = set()
    if root.is_symlink() or not root.is_dir():
        raise _error(f"package root is not a real directory: {root}")
    for current, dirnames, filenames in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in tuple(dirnames):
            path = current_path / name
            if path.is_symlink() or not path.is_dir():
                raise _error(
                    f"package contains a symbolic link or non-directory: {path}"
                )
            directories.add(path.relative_to(root).as_posix())
        for name in filenames:
            path = current_path / name
            _require_regular(path, "package file")
            files.add(path.relative_to(root).as_posix())
    return files, directories


def _expected_directories(files: set[str]) -> set[str]:
    result: set[str] = set()
    for value in files:
        path = PurePosixPath(value).parent
        while path != PurePosixPath("."):
            result.add(path.as_posix())
            path = path.parent
    return result


def _receipt_preparations(prepared: Mapping[str, _Preparation]) -> JsonObject:
    result: JsonObject = {}
    for key, item in prepared.items():
        binding = cast(JsonObject, item.record["binding"])
        original = cast(JsonObject, binding["originalSource"])
        verification = cast(JsonObject, binding["verification"])
        profile = cast(JsonObject, binding["profile"])
        result[key] = {
            "path": item.relative_path,
            "receiptHash": item.content_hash,
            "bindingHash": _compiler_hash(binding),
            "mappingHash": cast(JsonObject, binding["timeMapping"])["mappingHash"],
            "profileHash": profile["profileHash"],
            "toolHash": profile["toolHash"],
            "originalHash": original["contentHash"],
            "deliveredHash": verification["deliveredHash"],
            "originalProbeHash": original["probeHash"],
            "deliveredProbeHash": verification["probeHash"],
        }
    return result


def _write_exclusive(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
    except OSError as error:
        raise _error(f"could not write staged package file {path}: {error}") from error


def _copy_artifact(artifact: _InputArtifact, root: Path) -> None:
    _copy_input_file(
        artifact.origin, root / artifact.relative_path, artifact.content_hash
    )


def _build_staging(
    staging: Path,
    *,
    document: JsonObject,
    document_raw: bytes,
    dependencies: JsonObject,
    dependencies_raw: bytes,
    manifest: JsonObject,
    manifest_raw: bytes,
    report: JsonObject,
    report_raw: bytes,
    prepared: Mapping[str, _Preparation],
    artifacts: Mapping[str, _InputArtifact],
    view: JsonObject,
) -> JsonObject:
    build_id = _id_component(cast(str, manifest["buildId"]), "build id")
    build_root = staging / BUILD_DIRECTORY / build_id
    for filename, raw in (
        (MANIFEST_FILENAME, manifest_raw),
        (REPORT_FILENAME, report_raw),
        (DOCUMENT_FILENAME, document_raw),
        (DEPENDENCIES_FILENAME, dependencies_raw),
    ):
        _write_exclusive(build_root / filename, raw)
    _write_exclusive(build_root / DELIVERY_VIEW_FILENAME, _canonical_json(view))
    for item in prepared.values():
        _write_exclusive(staging / item.relative_path, item.raw)
    for artifact in artifacts.values():
        _copy_artifact(artifact, staging)
    timeline = _build_otio(view, cast(str, manifest["id"]), build_id)
    try:
        otio.adapters.write_to_file(
            timeline, str(build_root / OTIO_FILENAME), adapter_name="otio_json"
        )
    except (OSError, RuntimeError, ValueError) as error:
        raise _error(f"could not serialize verified v2 OTIO: {error}") from error

    package_files, _ = _walk_package(staging)
    receipt_path = f"{BUILD_DIRECTORY}/{build_id}/{VERIFICATION_FILENAME}"
    file_hashes = {path: _file_hash(staging / path) for path in sorted(package_files)}
    sources = cast(list[JsonObject], view["sources"])
    dep_build = cast(JsonObject, dependencies["build"])
    receipt = {
        "schemaVersion": VERIFICATION_SCHEMA_VERSION,
        "status": "ready_to_import",
        "buildId": build_id,
        "manifestId": manifest["id"],
        "reportId": report["id"],
        "documentId": document["id"],
        "eventCount": len(cast(list[JsonObject], view["events"])),
        "manifestEventCount": len(cast(list[JsonObject], manifest["events"])),
        "markerCount": len(cast(list[JsonObject], view["markers"])),
        "mediaCount": len(sources),
        "fileHashes": file_hashes,
        "sourceHashes": {source["id"]: source["contentHash"] for source in sources},
        "preparations": _receipt_preparations(prepared),
    }
    if (
        dep_build.get("buildId") != build_id
        or dep_build.get("manifestId") != manifest["id"]
        or dep_build.get("reportId") != report["id"]
    ):
        raise _error("package receipt build identity does not close")
    _write_exclusive(staging / receipt_path, _canonical_json(receipt))
    return receipt


def _safe_package_file(root: Path, relative: object, label: str) -> Path:
    rel = _safe_relative(relative, label)
    path = root.joinpath(*rel.parts)
    _require_path_components_no_symlink(path, label)
    _require_regular(path, label)
    return path


def _receipt_identity(
    receipt: JsonObject, value: JsonObject, key: str, expected: object, label: str
) -> None:
    if receipt.get(key) != expected:
        raise _error(f"package verification {label} differs from its retained {key}")


def _verify_package(project_root: Path) -> tuple[V2PackageVerification, JsonObject]:
    _require_path_components_no_symlink(project_root, "package root")
    if project_root.is_symlink() or not project_root.is_dir():
        raise _error(f"package root is not a real directory: {project_root}")
    try:
        root_names = {item.name for item in project_root.iterdir()}
    except OSError as error:
        raise _error(
            f"could not inspect package root {project_root}: {error}"
        ) from error
    if root_names != {BUILD_DIRECTORY, MEDIA_DIRECTORY}:
        raise _error("package root must contain only Builds and Media")
    builds_root = project_root / BUILD_DIRECTORY
    _require_path_components_no_symlink(builds_root, "package Builds directory")
    if not builds_root.is_dir() or builds_root.is_symlink():
        raise _error("package Builds path is not a real directory")
    build_dirs = [
        item
        for item in builds_root.iterdir()
        if item.is_dir() and not item.is_symlink()
    ]
    if len(build_dirs) != 1 or len(list(builds_root.iterdir())) != 1:
        raise _error("package root must contain exactly one immutable v2 build")
    build_root = build_dirs[0]
    build_id = _id_component(build_root.name, "build id")
    receipt_rel = f"{BUILD_DIRECTORY}/{build_id}/{VERIFICATION_FILENAME}"
    receipt_path = _safe_package_file(
        project_root, receipt_rel, "package verification receipt"
    )
    receipt, receipt_raw = _load_json(receipt_path, "package verification receipt")
    if _canonical_json(receipt) != receipt_raw:
        raise _error("package verification receipt is not canonical JSON")
    receipt_keys = {
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
    if (
        set(receipt) != receipt_keys
        or receipt.get("schemaVersion") != VERIFICATION_SCHEMA_VERSION
        or receipt.get("status") != "ready_to_import"
    ):
        raise _error("package verification receipt has an unsupported shape or status")
    _receipt_identity(receipt, {}, "buildId", build_id, "build id")

    raw_files, actual_directories = _walk_package(project_root)
    files_hashes = receipt.get("fileHashes")
    if not isinstance(files_hashes, dict):
        raise _error("package verification fileHashes is not an object")
    expected_files = set(files_hashes) | {receipt_rel}
    if raw_files != expected_files:
        raise _error("package file inventory differs from the immutable receipt")
    for relative, expected_hash in files_hashes.items():
        _safe_relative(relative, "package inventory path")
        _require_hash(expected_hash, f"package file hash {relative}")
        if _file_hash(project_root / relative) != expected_hash:
            raise _error(f"package file hash mismatch: {relative}")

    manifest_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{MANIFEST_FILENAME}",
        "packaged manifest",
    )
    report_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{REPORT_FILENAME}",
        "packaged report",
    )
    document_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DOCUMENT_FILENAME}",
        "packaged document",
    )
    dependencies_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DEPENDENCIES_FILENAME}",
        "packaged dependencies",
    )
    view_path = _safe_package_file(
        project_root,
        f"{BUILD_DIRECTORY}/{build_id}/{DELIVERY_VIEW_FILENAME}",
        "packaged delivery view",
    )
    manifest, _ = _load_json(manifest_path, "packaged manifest")
    report, _ = _load_json(report_path, "packaged report")
    document, _ = _load_json(document_path, "packaged document")
    dependencies, _ = _load_json(dependencies_path, "packaged dependencies")
    view, view_raw = _load_json(view_path, "packaged delivery view")
    if _canonical_json(view) != view_raw:
        raise _error("delivery view is not canonical JSON")
    _validate_inputs(document, dependencies, manifest, report)
    if (
        manifest.get("buildId") != build_id
        or receipt.get("manifestId") != manifest.get("id")
        or receipt.get("reportId") != report.get("id")
        or receipt.get("documentId") != document.get("id")
    ):
        raise _error("package receipt identity differs from its retained documents")
    preparations_raw = receipt.get("preparations")
    if not isinstance(preparations_raw, dict):
        raise _error("package preparation receipt map is invalid")
    bindings = _unique_by_id(
        manifest.get("preparationBindings"), "preparation binding", "requirementKey"
    )
    if set(preparations_raw) != set(bindings):
        raise _error("package preparation receipt map differs from manifest bindings")
    prep_paths: dict[str, Path] = {}
    for key, info in preparations_raw.items():
        expected_rel = (
            f"{BUILD_DIRECTORY}/{build_id}/Preparation/receipts/"
            f"{hashlib.sha256(key.encode('utf-8')).hexdigest()}/receipt.json"
        )
        if (
            not isinstance(info, dict)
            or set(info)
            != {
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
            or info.get("path") != expected_rel
        ):
            raise _error(
                f"package preparation receipt {key} has an invalid identity record"
            )
        prep_path = _safe_package_file(
            project_root, expected_rel, f"package preparation receipt {key}"
        )
        record, raw = _load_json(prep_path, f"package preparation receipt {key}")
        binding = cast(JsonObject, record.get("binding"))
        original = cast(JsonObject, binding.get("originalSource"))
        verification = cast(JsonObject, binding.get("verification"))
        profile = cast(JsonObject, binding.get("profile"))
        expected_prep = {
            "receiptHash": _hash_bytes(raw),
            "bindingHash": _compiler_hash(binding),
            "mappingHash": cast(JsonObject, binding.get("timeMapping"))["mappingHash"],
            "profileHash": profile["profileHash"],
            "toolHash": profile["toolHash"],
            "originalHash": original["contentHash"],
            "deliveredHash": verification["deliveredHash"],
            "originalProbeHash": original["probeHash"],
            "deliveredProbeHash": verification["probeHash"],
        }
        if any(info.get(field) != value for field, value in expected_prep.items()):
            raise _error(f"package preparation receipt {key} hash/provenance differs")
        prep_paths[key] = prep_path
    prepared = _validate_preparations(
        document, dependencies, manifest, report, prep_paths
    )

    sources = _unique_by_id(view.get("sources"), "delivery source")
    source_hashes = receipt.get("sourceHashes")
    if not isinstance(source_hashes, dict) or set(source_hashes) != set(sources):
        raise _error("package sourceHashes differ from delivery view sources")
    artifacts: dict[str, _InputArtifact] = {}
    for source_id, source in sources.items():
        relative = _safe_relative(
            source.get("path"), f"delivery source {source_id} path"
        ).as_posix()
        _require_hash(
            source.get("contentHash"), f"delivery source {source_id} content hash"
        )
        media_path = _safe_package_file(
            project_root, relative, f"delivery source {source_id}"
        )
        actual = _file_hash(media_path)
        if actual != source["contentHash"] or source_hashes.get(source_id) != actual:
            raise _error(
                f"delivery source {source_id} hash differs from package bytes/receipt"
            )
    manifest_sources = _unique_by_id(manifest.get("sources"), "manifest source")
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            artifact_key = f"source:{source_id}"
            content_hash = cast(JsonObject, source["narrationAudio"])["audioHash"]
        else:
            artifact_key = f"source:{source_id}"
            content_hash = source["deliveredHash"]
        view_source = sources.get(source_id)
        if view_source is None:
            raise _error(f"manifest source {source_id} is absent from delivery view")
        artifacts[artifact_key] = _InputArtifact(
            artifact_key,
            project_root / view_source["path"],
            view_source["path"],
            content_hash,
            view_source["kind"],
        )
        if "narrationAudio" not in source:
            artifacts[f"original:{source_id}"] = _InputArtifact(
                f"original:{source_id}",
                Path("."),
                "",
                source["originalHash"],
                "original",
            )
    for event in cast(list[JsonObject], manifest.get("events", [])):
        event_id = cast(str, event["eventId"])
        if event["kind"] == "placeholder":
            view_source = sources.get(event_id)
            if view_source is None:
                raise _error(
                    f"placeholder event {event_id} is absent from delivery view"
                )
            artifacts[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                project_root / view_source["path"],
                view_source["path"],
                view_source["contentHash"],
                "still",
            )
        elif event["kind"] == "source_audio":
            view_source = sources.get(event_id)
            if view_source is None:
                raise _error(
                    f"source audio event {event_id} is absent from delivery view"
                )
            artifacts[f"event:{event_id}"] = _InputArtifact(
                f"event:{event_id}",
                project_root / view_source["path"],
                view_source["path"],
                view_source["contentHash"],
                "audio",
            )
    _validate_delivery_view(manifest, dependencies, view, prepared, artifacts)

    # Reconstruct the only permitted package inventory from frozen IDs, view
    # sources and preparation receipts; receipt-signed unrelated files are not accepted.
    expected_inventory = {
        f"{BUILD_DIRECTORY}/{build_id}/{name}"
        for name in (
            MANIFEST_FILENAME,
            REPORT_FILENAME,
            DOCUMENT_FILENAME,
            DEPENDENCIES_FILENAME,
            DELIVERY_VIEW_FILENAME,
            OTIO_FILENAME,
            VERIFICATION_FILENAME,
        )
    }
    expected_inventory.update(item.relative_path for item in prepared.values())
    expected_inventory.update(source["path"] for source in sources.values())
    for source_id, source in manifest_sources.items():
        if "narrationAudio" in source:
            continue
        original_matches = [
            path
            for path in files_hashes
            if isinstance(path, str)
            and path.startswith(
                f"{BUILD_DIRECTORY}/{build_id}/Preparation/original/{source_id}."
            )
        ]
        if len(original_matches) != 1:
            raise _error(
                f"package original bytes for {source_id} are missing or duplicated"
            )
        original_path = _safe_package_file(
            project_root, original_matches[0], f"original source {source_id}"
        )
        if _file_hash(original_path) != source["originalHash"]:
            raise _error(
                f"package original bytes for {source_id} differ from manifest hash"
            )
        expected_inventory.add(original_matches[0])
    expected_inventory.discard(receipt_rel)
    if set(files_hashes) != expected_inventory:
        raise _error("package inventory includes missing or unrelated artifacts")
    all_files = expected_inventory | {receipt_rel}
    if actual_directories != _expected_directories(all_files):
        raise _error("package directory inventory includes unexpected or missing paths")

    _verify_otio(build_root, manifest, view)
    expected_counts = {
        "eventCount": len(cast(list[JsonObject], view["events"])),
        "manifestEventCount": len(cast(list[JsonObject], manifest["events"])),
        "markerCount": len(cast(list[JsonObject], view["markers"])),
        "mediaCount": len(cast(list[JsonObject], view["sources"])),
    }
    for key, value in expected_counts.items():
        if receipt.get(key) != value:
            raise _error(
                f"package verification {key} differs from retained v2 artifacts"
            )
    return V2PackageVerification(
        build_id,
        expected_counts["eventCount"],
        expected_counts["markerCount"],
        expected_counts["mediaCount"],
    ), receipt


def verify_v2_package(project_root: Path) -> V2PackageVerification:
    """Independently verify one immutable package and its OTIO projection."""
    if not isinstance(project_root, Path):
        raise V2PackageError("project_root must be a pathlib.Path")
    verification, _ = _verify_package(project_root)
    return verification


def _read_inputs(
    manifest_path: Path,
    report_path: Path,
    document_path: Path,
    dependencies_path: Path,
) -> tuple[JsonObject, bytes, JsonObject, bytes, JsonObject, bytes, JsonObject, bytes]:
    manifest, manifest_raw = _load_json(manifest_path, "v2 manifest")
    report, report_raw = _load_json(report_path, "v2 build report")
    document, document_raw = _load_json(document_path, "v2 script document")
    dependencies, dependencies_raw = _load_json(
        dependencies_path, "v2 compiler dependencies"
    )
    return (
        document,
        document_raw,
        dependencies,
        dependencies_raw,
        manifest,
        manifest_raw,
        report,
        report_raw,
    )


def build_v2_package(
    manifest_path: Path,
    report_path: Path,
    document_path: Path,
    dependencies_path: Path,
    project_root: Path,
    *,
    media_paths: Mapping[str, Path],
    preparation_paths: Mapping[str, Path],
) -> V2PackageResult:
    """Create one immutable verified v2 package under a fresh project root."""
    paths = (manifest_path, report_path, document_path, dependencies_path, project_root)
    if any(not isinstance(path, Path) for path in paths):
        raise V2PackageError(
            "all package input and output paths must be pathlib.Path values"
        )
    if not isinstance(media_paths, Mapping) or not isinstance(
        preparation_paths, Mapping
    ):
        raise V2PackageError(
            "media_paths and preparation_paths must be explicit mappings"
        )
    (
        document,
        document_raw,
        dependencies,
        dependencies_raw,
        manifest,
        manifest_raw,
        report,
        report_raw,
    ) = _read_inputs(manifest_path, report_path, document_path, dependencies_path)
    _validate_inputs(document, dependencies, manifest, report)
    prepared = _validate_preparations(
        document, dependencies, manifest, report, preparation_paths
    )
    artifacts = _media_artifacts(manifest, prepared, media_paths)
    view = _delivery_view(manifest, dependencies, prepared, artifacts)

    root = project_root.absolute()
    if root == root.parent or root.name in {"", ".", ".."}:
        raise V2PackageError("project_root must name a dedicated package directory")
    _require_path_components_no_symlink(root.parent, "package parent directory")
    root.parent.mkdir(parents=True, exist_ok=True)
    _require_path_components_no_symlink(root, "package root")
    lock_path = root.parent / f".{root.name}.v2-package.lock"
    flags = os.O_CREAT | os.O_RDWR | getattr(os, "O_NOFOLLOW", 0)
    try:
        lock_fd = os.open(lock_path, flags, 0o600)
    except OSError as error:
        raise _error(f"could not open package lock {lock_path}: {error}") from error
    staging: Path | None = None
    try:
        fcntl.flock(lock_fd, fcntl.LOCK_EX)
        _require_path_components_no_symlink(root, "package root")
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise _error(
                f"package root already exists and is not a real directory: {root}"
            )
        staging = Path(
            tempfile.mkdtemp(prefix=f".{root.name}.v2-staging-", dir=root.parent)
        )
        _build_staging(
            staging,
            document=document,
            document_raw=document_raw,
            dependencies=dependencies,
            dependencies_raw=dependencies_raw,
            manifest=manifest,
            manifest_raw=manifest_raw,
            report=report,
            report_raw=report_raw,
            prepared=prepared,
            artifacts=artifacts,
            view=view,
        )
        proposed_verification, proposed_receipt = _verify_package(staging)
        if root.exists():
            if any(root.iterdir()):
                try:
                    existing_verification, existing_receipt = _verify_package(root)
                except V2PackageError as error:
                    raise _error(
                        f"project root is not the same verified package: {root}"
                    ) from error
                if (
                    existing_verification != proposed_verification
                    or existing_receipt != proposed_receipt
                ):
                    raise _error(
                        f"project root is not the same verified package: {root}"
                    )
                old_files, _ = _walk_package(root)
                new_files, _ = _walk_package(staging)
                if old_files != new_files or any(
                    (root / item).read_bytes() != (staging / item).read_bytes()
                    for item in old_files
                ):
                    raise _error(
                        f"project root already exists and is not byte-identical: {root}"
                    )
                shutil.rmtree(staging)
                staging = None
                return V2PackageResult(root, proposed_verification.build_id, True)
            root.rmdir()
        if root.exists():
            raise _error(f"project root appeared during package publication: {root}")
        os.rename(staging, root)
        staging = None
        published = verify_v2_package(root)
        if published != proposed_verification:
            raise _error("published package differs from its staged verification")
        return V2PackageResult(root, published.build_id, False)
    except V2PackageError as error:
        if staging is None:
            raise
        retained = staging
        staging = None
        raise _error(f"{error}; partial package retained at {retained}") from error
    except (OSError, RuntimeError, ValueError) as error:
        if staging is None:
            raise _error(
                f"could not publish v2 package under {root}: {error}"
            ) from error
        retained = staging
        staging = None
        raise _error(
            f"could not publish v2 package under {root}: {error}; "
            f"partial package retained at {retained}"
        ) from error
    except Exception as error:
        if staging is None:
            raise _error(
                f"could not publish v2 package under {root}: {error}"
            ) from error
        retained = staging
        staging = None
        raise _error(
            f"could not publish v2 package under {root}: {error}; "
            f"partial package retained at {retained}"
        ) from error
    except BaseException as error:
        if staging is not None:
            retained = staging
            staging = None
            error.add_note(f"partial v2 package retained at {retained}")
        raise
    finally:
        if staging is not None:
            shutil.rmtree(staging, ignore_errors=True)
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
        finally:
            os.close(lock_fd)
