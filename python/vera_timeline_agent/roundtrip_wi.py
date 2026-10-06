"""Independently stageable stdlib WI reader. Live qualification belongs to #145.

Every native handle is supplied explicitly. Expected package facts are compared
with getters; they never fill a missing native value. No connection or selection.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import stat
import wave
from collections.abc import Callable
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

Json = dict[str, Any]


def fact(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def regular(path: Path) -> Path:
    path = path.absolute()
    fact(not any(p.is_symlink() for p in (path, *path.parents)), "symlink path refused")
    info = path.stat()
    fact(
        stat.S_ISREG(info.st_mode) and info.st_nlink == 1,
        "independent regular file required",
    )
    return path


def file_hash(path: Path) -> str:
    path = regular(path)
    before = path.stat()
    hashed = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            hashed.update(block)
    after = path.stat()
    fact(
        (before.st_ino, before.st_size, before.st_mtime_ns)
        == (after.st_ino, after.st_size, after.st_mtime_ns),
        "source changed while hashing",
    )
    return "sha256:" + hashed.hexdigest()


def encoded(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False, indent=2)
        + "\n"
    ).encode()


def exclusive(path: Path, raw: bytes) -> None:
    # Same stdlib O_EXCL/O_NOFOLLOW and fsync pattern as the host; no host imports.
    fact(
        not any(p.is_symlink() for p in (path.absolute(), *path.absolute().parents)),
        "symlink output refused",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    descriptor = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def get(handle: Any, method: str, *args: Any) -> Any:
    try:
        return getattr(handle, method)(*args)
    except Exception as error:
        raise RuntimeError(
            f"native getter {method} failed: {type(error).__name__}"
        ) from error


def integer(value: Any, label: str, *, minimum: int = 0) -> int:
    fact(
        type(value) in {int, float}
        and minimum <= value <= 2**53 - 1
        and math.isfinite(value)
        and int(value) == value,
        f"uncertain integer {label}",
    )
    return int(value)


def uid(value: Any) -> str:
    fact(isinstance(value, str) and bool(value), "missing native UID/name")
    return str(value)


def context(
    resolve: Any, *, version: list[Any], project_uid: str, timeline_uid: str
) -> tuple[Any, Any]:
    fact(
        get(resolve, "GetProductName") == "DaVinci Resolve Studio"
        and get(resolve, "GetVersion") == version,
        "Resolve product/build changed",
    )
    manager = get(resolve, "GetProjectManager")
    project = get(manager, "GetCurrentProject")
    fact(
        project is not None and get(project, "GetUniqueId") == project_uid,
        "current project UID differs",
    )
    timeline = get(project, "GetCurrentTimeline")
    fact(
        timeline is not None and get(timeline, "GetUniqueId") == timeline_uid,
        "current timeline UID differs",
    )
    return project, timeline


def read_native(
    resolve: Any,
    manifest: Json,
    *,
    package_root: Path,
    version: list[Any],
    project_uid: str,
    timeline_uid: str,
) -> Json:
    project, timeline = context(
        resolve, version=version, project_uid=project_uid, timeline_uid=timeline_uid
    )
    project_name, timeline_name = (
        uid(get(project, "GetName")),
        uid(get(timeline, "GetName")),
    )
    fact(
        project_name == f"VERA Studio build {manifest['buildId']}"
        and timeline_name == f"VERA build {manifest['buildId']}",
        "fresh managed names differ",
    )
    frame_rate = get(timeline, "GetSetting", "timelineFrameRate")
    fact(type(frame_rate) in {str, int, float}, "native frame rate unreadable")
    rate = Fraction(Decimal(str(frame_rate)))
    start, end = (
        integer(get(timeline, "GetStartFrame"), "timeline start"),
        integer(get(timeline, "GetEndFrame"), "timeline end", minimum=1),
    )
    observed_timeline = {
        "startFrame": start,
        "durationFrames": end - start,
        "frameRate": {"numerator": rate.numerator, "denominator": rate.denominator},
    }
    for key, setting in (
        ("width", "timelineResolutionWidth"),
        ("height", "timelineResolutionHeight"),
        ("audioSampleRate", "timelineSampleRate"),
    ):
        raw = get(timeline, "GetSetting", setting)
        fact(type(raw) in {str, int, float}, "native setting unreadable")
        observed_timeline[key] = integer(float(raw), key, minimum=1)
    fact(
        observed_timeline == manifest["timeline"],
        "native timeline settings/extent differ",
    )
    expected_sources = {}
    for source in manifest["sources"]:
        fact(
            source["kind"] in {"video", "audio"},
            "WI reader currently supports ready audio/video sources only",
        )
        relative = Path(source["path"])
        fact(
            not relative.is_absolute() and ".." not in relative.parts,
            "unsafe package source",
        )
        path = regular(package_root / relative)
        fact(file_hash(path) == source["contentHash"], "package source bytes differ")
        fact(str(path) not in expected_sources, "ambiguous package source locator")
        expected_sources[str(path)] = source["contentHash"]
    items, tracks, empty_slots, seen = [], [], [], set()
    for kind in ("video", "audio", "subtitle"):
        count = integer(get(timeline, "GetTrackCount", kind), "track count")
        expected = sorted(
            (t for t in manifest["tracks"] if t["kind"] == kind),
            key=lambda t: t["index"],
        )
        fact(
            count == max((t["index"] for t in expected), default=0)
            and count <= 1024
            and len({t["index"] for t in expected}) == len(expected),
            "complete native track inventory differs",
        )
        # Accepted assembly creates intermediate slots up to the maximum index.
        # Inspect each gap rather than silently ignoring an unmanaged route.
        for index in range(1, count + 1):
            if any(t["index"] == index for t in expected):
                continue
            name = uid(get(timeline, "GetTrackName", kind, index))
            native_items = get(timeline, "GetItemListInTrack", kind, index)
            fact(
                isinstance(native_items, (list, tuple)) and not native_items,
                "unmanaged intermediate native slot is not empty",
            )
            empty_slots.append({"kind": kind, "index": index, "name": name})
        for track in expected:
            name = get(timeline, "GetTrackName", kind, track["index"])
            fact(name == track["name"], "native track name differs")
            # IDs/roles are managed metadata after actual counts/slots/names agree.
            tracks.append({**track, "name": name})
            native_items = get(timeline, "GetItemListInTrack", kind, track["index"])
            fact(
                isinstance(native_items, (list, tuple)) and len(native_items) <= 1024,
                "bounded complete native item list required",
            )
            for item in native_items:
                item_uid = uid(get(item, "GetUniqueId"))
                fact(item_uid not in seen, "duplicate native item UID")
                seen.add(item_uid)
                record = {}
                for method in ("GetStart", "GetEnd", "GetDuration"):
                    value = integer(get(item, method, False), method)
                    fractional = integer(
                        get(item, method, True), method + " fractional"
                    )
                    fact(value == fractional, "fractional native geometry differs")
                    record[method] = value
                duration = record["GetDuration"]
                fact(
                    duration > 0
                    and record["GetEnd"] - record["GetStart"]
                    in {duration, duration - 1},
                    "native record endpoint convention inconsistent",
                )
                source_start = integer(get(item, "GetSourceStartFrame"), "source start")
                source_end = integer(get(item, "GetSourceEndFrame"), "source end")
                fact(
                    source_end - source_start + 1 == duration,
                    "native source duration differs",
                )
                media = get(item, "GetMediaPoolItem")
                fact(media is not None, "native source handle unavailable")
                properties = get(media, "GetClipProperty")
                fact(
                    isinstance(properties, dict)
                    and properties.get("Online Status") == "Online",
                    "native online status unknown/offline",
                )
                locator = properties.get("File Path")
                fact(locator in expected_sources, "native source locator is unknown")
                source_hash = file_hash(Path(locator))
                fact(
                    source_hash == expected_sources[locator],
                    "native source bytes changed",
                )
                links = get(item, "GetLinkedItems")
                fact(isinstance(links, (list, tuple)), "native links unreadable")
                linked = sorted(uid(get(peer, "GetUniqueId")) for peer in links)
                fact(
                    len(linked) == len(set(linked)) and item_uid not in linked,
                    "duplicate/self native links",
                )
                enabled, speed = get(item, "GetClipEnabled"), get(item, "GetSpeed")
                fact(
                    type(enabled) is bool
                    and type(speed) in {int, float}
                    and math.isfinite(speed),
                    "native controls unknown",
                )
                items.append(
                    {
                        "itemUid": item_uid,
                        "mediaUid": uid(get(media, "GetUniqueId")),
                        "trackKind": kind,
                        "trackIndex": track["index"],
                        "recordRange": {
                            "startFrame": record["GetStart"],
                            "durationFrames": duration,
                        },
                        "sourceRange": {
                            "startFrame": source_start,
                            "durationFrames": source_end - source_start + 1,
                        },
                        "sourcePath": locator,
                        "sourceHash": source_hash,
                        "enabled": enabled,
                        "speed": speed,
                        "linkedUids": linked,
                        "available": True,
                    }
                )
    markers = get(timeline, "GetMarkers")
    fact(isinstance(markers, dict), "native marker inventory unreadable")
    # JSON object keys are strings: normalize actual integer frame keys once so
    # retained before-state comparison does not change type after serialization.
    markers = {
        str(integer(frame, "marker frame")): fields for frame, fields in markers.items()
    }
    context(
        resolve, version=version, project_uid=project_uid, timeline_uid=timeline_uid
    )
    fact(
        all(
            file_hash(Path(path)) == hashed for path, hashed in expected_sources.items()
        ),
        "source changed during read",
    )
    return {
        "schemaVersion": "issue-144-wi-structural-readback/v1",
        "projectUid": project_uid,
        "timelineUid": timeline_uid,
        "projectName": project_name,
        "timelineName": timeline_name,
        "timeline": observed_timeline,
        "tracks": tracks,
        "emptySlots": empty_slots,
        "items": sorted(items, key=lambda item: item["itemUid"]),
        "markers": markers,
    }


def load(path: Path, expected_hash: str | None = None) -> Json:
    def pairs(entries: list[tuple[str, Any]]) -> Json:
        result: Json = {}
        for key, value in entries:
            fact(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def bad_constant(value: str) -> None:
        raise RuntimeError(f"non-finite JSON value: {value}")

    def number(value: str) -> int | float:
        parsed = float(value) if any(c in value for c in ".eE") else int(value)
        fact(-(2**53) + 1 <= parsed <= 2**53 - 1, "unsafe JSON number")
        return parsed

    regular(path)
    fact(path.stat().st_size <= 8 * 1024 * 1024, "bounded JSON required")
    raw = path.read_bytes()
    fact(
        expected_hash is None or digest(raw) == expected_hash, "bound JSON bytes differ"
    )
    value = json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=bad_constant,
        parse_int=number,
        parse_float=number,
    )
    if not isinstance(value, dict):
        raise RuntimeError("one JSON object required")
    return value


def immutable(path: Path, value: Json) -> None:
    raw = encoded(value)
    if path.exists():
        fact(regular(path).read_bytes() == raw, "immutable WI output differs")
    else:
        exclusive(path, raw)


def owned(path: Path, root: Path) -> Path:
    fact(".." not in path.parts and ".." not in root.parts, "parent traversal refused")
    path, root = path.absolute(), root.absolute()
    fact(
        path.is_relative_to(root)
        and path != root
        and not any(p.is_symlink() for p in (path, *path.parents)),
        "path outside owned proof root",
    )
    return path


def _capture(
    resolve: Any,
    request_path: Path,
    *,
    proof_root: Path,
    source_root: Path,
    version: list[Any],
    request_hash: str,
    code_hash: str,
    audio_controls: Callable[[Any, Json], Json] | None = None,
) -> Json:
    request_path = owned(request_path, proof_root)
    request = load(request_path, request_hash)
    fact(
        set(request)
        == {
            "schemaVersion",
            "purpose",
            "binding",
            "snapshotId",
            "evidenceLevel",
            "manifestPath",
            "manifestHash",
            "identityPath",
            "identityHash",
            "expectedIdentity",
            "packageRoot",
            "sources",
            "nonce",
        },
        "capture request shape differs",
    )
    fact(
        request["schemaVersion"]
        in ("issue-144-capture-request/v1", "issue-144-omission-capture-request/v1")
        and request["evidenceLevel"] in ("synthetic_injected", "real_issue145")
        and request_path.name == "request.json"
        and request_path.parent.name == request["nonce"],
        "capture schema/lane/nonce differs",
    )
    manifest_path = owned(Path(request["manifestPath"]), proof_root)
    identity_path = owned(Path(request["identityPath"]), proof_root)
    package = owned(Path(request["packageRoot"]), proof_root)
    manifest, identity = (
        load(manifest_path, request["manifestHash"]),
        load(identity_path, request["identityHash"]),
    )

    def guard() -> None:
        fact(
            file_hash(Path(__file__)) == code_hash
            and file_hash(request_path) == request_hash,
            "WI code/request changed",
        )
        fact(
            file_hash(manifest_path) == request["manifestHash"]
            and file_hash(identity_path) == request["identityHash"]
            and load(identity_path) == request["expectedIdentity"],
            "bound manifest/identity changed",
        )
        fact(
            isinstance(request["sources"], dict) and bool(request["sources"]),
            "complete source/code pins required",
        )
        for name, expected in request["sources"].items():
            relative = Path(name)
            fact(
                not relative.is_absolute() and ".." not in relative.parts,
                "source/code locator outside root",
            )
            fact(
                file_hash(source_root / relative) == expected, "source/code pin changed"
            )
        context(
            resolve,
            version=version,
            project_uid=identity["projectUid"],
            timeline_uid=identity["timelineUid"],
        )

    birth = {
        value["itemUid"]: (event, value["mediaUid"])
        for event, value in identity["occurrences"].items()
    }
    fact(len(birth) == len(identity["occurrences"]), "duplicate native birth UID")
    omitted = request["schemaVersion"] == "issue-144-omission-capture-request/v1"
    observations: list[Json] = []
    raw_reads: list[Json] = []
    for _ in range(2):
        guard()
        raw = read_native(
            resolve,
            manifest,
            package_root=package,
            version=version,
            project_uid=identity["projectUid"],
            timeline_uid=identity["timelineUid"],
        )
        guard()
        immutable(request_path.parent / f"raw-{len(raw_reads)}.json", raw)
        raw_reads.append(raw)
        items = []
        for item in raw["items"]:
            track = next(
                t
                for t in raw["tracks"]
                if t["kind"] == item["trackKind"] and t["index"] == item["trackIndex"]
            )
            facts = {key: value for key, value in item.items() if key != "trackIndex"}
            facts["trackId"] = track["id"]
            facts["sourcePath"] = (
                Path(item["sourcePath"]).relative_to(package).as_posix()
            )
            if not omitted:
                fact(
                    item["itemUid"] in birth
                    and birth[item["itemUid"]][1] == item["mediaUid"],
                    "unknown native birth/source UID",
                )
                facts["eventId"] = birth[item["itemUid"]][0]
            items.append(facts)
        observation = {
            "schemaVersion": "issue-144-omission-observation/v1"
            if omitted
            else "issue-144-observation/v1",
            "evidenceLevel": request["evidenceLevel"],
            "projectUid": raw["projectUid"],
            "timelineUid": raw["timelineUid"],
            "timeline": raw["timeline"],
            "tracks": [
                next(t for t in raw["tracks"] if t["id"] == original["id"])
                for original in manifest["tracks"]
            ],
            "items": items,
        }
        if omitted:
            fact(
                audio_controls is not None, "qualified complete control reader required"
            )
            assert audio_controls is not None
            controls = audio_controls(resolve, raw)
            fact(
                set(controls) == {"programControls", "audioControls"},
                "complete control shape required",
            )
            observation.update(controls)
        guard()
        observations.append(observation)
    fact(
        raw_reads[0] == raw_reads[1] and observations[0] == observations[1],
        "adjacent native reads differ",
    )
    response = {
        "schemaVersion": "issue-144-omission-capture-response/v1"
        if omitted
        else "issue-144-capture-response/v1",
        "nonce": request["nonce"],
        "requestHash": request_hash,
        "observationA": observations[0],
        "observationB": observations[1],
    }
    guard()
    for index, raw in enumerate(raw_reads):
        immutable(request_path.parent / f"raw-{index}.json", raw)
    immutable(request_path.parent / "response.json", response)
    return response


def capture(
    resolve: Any,
    request_path: Path,
    *,
    proof_root: Path,
    source_root: Path,
    version: list[Any],
    request_hash: str,
    code_hash: str,
    audio_controls: Callable[[Any, Json], Json] | None = None,
) -> Json:
    path = owned(request_path, proof_root)
    try:
        return _capture(
            resolve,
            path,
            proof_root=proof_root,
            source_root=source_root,
            version=version,
            request_hash=request_hash,
            code_hash=code_hash,
            audio_controls=audio_controls,
        )
    except (RuntimeError, OSError, ValueError, KeyError, TypeError) as error:
        # No complete response is produced. The host can reserve a new attempt;
        # unknown facts/failure and any completed raw reads remain diagnostic only.
        immutable(
            path.parent / "refused.json",
            {
                "schemaVersion": "issue-144-wi-capture-failure/v1",
                "requestHash": request_hash,
                "codeHash": code_hash,
                "reason": str(error),
            },
        )
        raise


def inspect_native(resolve: Any, manifest: Json, **kwargs: Any) -> Json:
    """Exact existing NativeStages shape, derived from adjacent actual getters."""
    first, second = (
        read_native(resolve, manifest, **kwargs),
        read_native(resolve, manifest, **kwargs),
    )
    fact(first == second, "adjacent native inspections differ")
    observed_markers = []
    expected = {m["id"]: m for m in manifest["markers"]}
    for frame, fields in first["markers"].items():
        fact(isinstance(fields, dict), "native marker fields unavailable")
        custom = json.loads(fields["customData"])
        fact(
            isinstance(custom, dict)
            and set(custom) == {"markerId", "provenance"}
            and custom["markerId"] in expected,
            "unknown native marker identity",
        )
        fact(
            integer(fields["duration"], "marker duration") == 1,
            "marker duration differs",
        )
        marker = expected[custom["markerId"]]
        observed_markers.append(
            {
                **marker,
                "id": custom["markerId"],
                "provenance": custom["provenance"],
                "frame": integer(int(frame), "marker frame"),
                **{k: fields[k] for k in ("name", "note", "color")},
            }
        )
    fact(
        len(observed_markers) == len(expected),
        "complete native marker inventory differs",
    )
    observed_markers.sort(
        key=lambda m: next(
            i for i, old in enumerate(manifest["markers"]) if old["id"] == m["id"]
        )
    )
    return {
        **{k: v for k, v in first.items() if k != "emptySlots"},
        "schemaVersion": "issue-144-native-readback/v1",
        "tracks": [
            next(t for t in first["tracks"] if t["id"] == old["id"])
            for old in manifest["tracks"]
        ],
        "items": [
            {k: v for k, v in item.items() if k not in {"available", "linkedUids"}}
            for item in first["items"]
        ],
        "markers": observed_markers,
    }


RenderBoundary = Callable[[Any, str, Json, Json | None], Json]


def perform(
    resolve: Any,
    request_path: Path,
    *,
    proof_root: Path,
    source_root: Path,
    version: list[Any],
    request_hash: str,
    code_hash: str,
    render_boundary: RenderBoundary | None = None,
    inspect_render: bool = False,
) -> Json:
    """Explicit link or qualified render, with one root-scoped effect reservation.

    An uncertain reservation can only be inspected; no request/nonce grants retry.
    These operations never discover a Resolve connection or select another target.
    """
    request_path = owned(request_path, proof_root)
    request = load(request_path, request_hash)
    fact(
        set(request)
        == {
            "schemaVersion",
            "purpose",
            "binding",
            "snapshotId",
            "evidenceLevel",
            "manifestPath",
            "manifestHash",
            "identityPath",
            "identityHash",
            "expectedIdentity",
            "packageRoot",
            "sources",
            "nonce",
            "action",
            "parameters",
            "expectedObservationHash",
        },
        "WI action request shape differs",
    )
    fact(
        request["schemaVersion"] == "issue-144-wi-action/v1"
        and request["evidenceLevel"] in ("synthetic_injected", "real_issue145")
        and request["action"] in ("link", "render")
        and request_path.name == "request.json"
        and request_path.parent.name == request["nonce"],
        "WI action schema/nonce/lane differs",
    )
    manifest_path = owned(Path(request["manifestPath"]), proof_root)
    identity_path = owned(Path(request["identityPath"]), proof_root)
    package = owned(Path(request["packageRoot"]), proof_root)
    manifest = load(manifest_path, request["manifestHash"])
    identity = load(identity_path, request["identityHash"])

    def guard() -> None:
        fact(
            file_hash(Path(__file__)) == code_hash
            and file_hash(request_path) == request_hash,
            "WI action code/request changed",
        )
        fact(
            file_hash(manifest_path) == request["manifestHash"]
            and file_hash(identity_path) == request["identityHash"]
            and identity == request["expectedIdentity"],
            "WI action authority changed",
        )
        fact(
            isinstance(request["sources"], dict) and bool(request["sources"]),
            "WI action source/code pins required",
        )
        for name, expected_hash in request["sources"].items():
            relative = Path(name)
            fact(
                not relative.is_absolute() and ".." not in relative.parts,
                "unsafe source pin",
            )
            fact(
                file_hash(source_root / relative) == expected_hash,
                "WI action source/code pin changed",
            )
        context(
            resolve,
            version=version,
            project_uid=identity["projectUid"],
            timeline_uid=identity["timelineUid"],
        )

    def observe() -> Json:
        reads = []
        for _ in range(2):
            guard()
            reads.append(
                read_native(
                    resolve,
                    manifest,
                    package_root=package,
                    version=version,
                    project_uid=identity["projectUid"],
                    timeline_uid=identity["timelineUid"],
                )
            )
            guard()
        fact(reads[0] == reads[1], "adjacent action reads differ")
        return reads[0]

    action, parameters = request["action"], request["parameters"]
    fact(isinstance(parameters, dict), "WI parameters required")
    if action == "link":
        fact(
            not inspect_render and set(parameters) == {"pair"}, "link parameters differ"
        )
        pair = parameters["pair"]
        fact(
            isinstance(pair, list)
            and len(pair) == 2
            and all(isinstance(x, str) and x for x in pair)
            and len(set(pair)) == 2,
            "exactly two native UIDs required",
        )
        effect_identity: Any = sorted(pair)
    else:
        fact(render_boundary is not None, "qualified render boundary required")
        fact(set(parameters) == {"outputPath", "settings"}, "render parameters differ")
        output = owned(Path(parameters["outputPath"]), proof_root)
        settings = parameters["settings"]
        fact(
            isinstance(settings, dict)
            and settings
            == {
                "format": "wav",
                "scope": "full-program",
                "sampleRate": 48000,
                "channels": 2,
                "sampleWidth": settings.get("sampleWidth"),
                "startFrame": manifest["timeline"]["startFrame"],
                "durationFrames": manifest["timeline"]["durationFrames"],
            }
            and type(settings["sampleWidth"]) is int
            and all(
                type(settings[k]) is int
                for k in ("sampleRate", "channels", "startFrame", "durationFrames")
            )
            and settings["sampleWidth"] in (2, 3),
            "complete stereo PCM render settings required",
        )
        effect_identity = str(output)
    key = digest(
        encoded(
            [action, identity["projectUid"], identity["timelineUid"], effect_identity]
        )
    )[7:]
    directory = owned(proof_root / "wi-effects" / key, proof_root)
    intent_path, queued_path = directory / "intent.json", directory / "effect.json"
    current = observe()
    reserved_here = not intent_path.exists()
    if not reserved_here:
        intent = load(intent_path)
        fact(
            set(intent)
            == {"schemaVersion", "requestHash", "codeHash", "request", "before"}
            and intent["schemaVersion"] == "issue-144-wi-intent/v1"
            and intent["requestHash"] == request_hash
            and intent["codeHash"] == code_hash
            and intent["request"] == request
            and digest(encoded(intent["before"])) == request["expectedObservationHash"],
            "different request cannot reuse effect ownership",
        )
        before = intent["before"]
    else:
        fact(not inspect_render, "no owned render intent to inspect")
        fact(
            digest(encoded(current)) == request["expectedObservationHash"],
            "stale native observation",
        )
        before = current
        if action == "link":
            selected = [
                next((item for item in current["items"] if item["itemUid"] == x), None)
                for x in pair
            ]
            fact(all(selected), "named link item missing")
            a, b = selected
            fact(
                a is not None
                and b is not None
                and {a["trackKind"], b["trackKind"]} == {"video", "audio"}
                and a["recordRange"] == b["recordRange"]
                and a["sourceRange"] == b["sourceRange"]
                and all(
                    item["enabled"] is True
                    and item["speed"] == 100
                    and item["linkedUids"] == []
                    for item in (a, b)
                ),
                "link geometry/control/pair differs",
            )
        else:
            fact(not output.exists(), "render output already exists")
        intent = {
            "schemaVersion": "issue-144-wi-intent/v1",
            "requestHash": request_hash,
            "codeHash": code_hash,
            "request": request,
            "before": before,
        }
        guard()
        exclusive(intent_path, encoded(intent))
        guard()
        if action == "link":
            _, timeline = context(
                resolve,
                version=version,
                project_uid=identity["projectUid"],
                timeline_uid=identity["timelineUid"],
            )
            handles = {}
            for track in current["tracks"]:
                for item in get(
                    timeline, "GetItemListInTrack", track["kind"], track["index"]
                ):
                    native_uid = uid(get(item, "GetUniqueId"))
                    fact(native_uid not in handles, "ambiguous native link handle")
                    handles[native_uid] = item
            fact(
                set(handles) == {item["itemUid"] for item in current["items"]}
                and observe() == before,
                "native handles changed before link",
            )
            fact(
                timeline.SetClipsLinked([handles[x] for x in pair], True) is True,
                "link result uncertain; preserve intent",
            )
        else:
            assert render_boundary is not None
            queued = render_boundary(resolve, "queue", parameters, None)
            guard()
            _render_job(queued, parameters, identity)
            fact(queued["state"] == "queued", "queued render identity uncertain")
            immutable(queued_path, queued)
        current = observe()

    if action == "link":
        # Derive the sole permitted post-effect change from retained actual facts.
        after = json.loads(encoded(before))
        for item in after["items"]:
            if item["itemUid"] in pair:
                item["linkedUids"] = [x for x in pair if x != item["itemUid"]]
        fact(
            current == after, "link intent uncertain or native state changed; no retry"
        )
        result = {
            "status": "linked",
            "evidenceLevel": request["evidenceLevel"],
            "intentHash": file_hash(intent_path),
            "observationHash": digest(encoded(current)),
        }
        guard()
        immutable(queued_path, result)
        return result

    fact(current == before, "render target changed")
    assert render_boundary is not None
    if not queued_path.exists():
        fact(
            inspect_render,
            "render response lost; read-only reconciliation required, no retry",
        )
        recovered = render_boundary(resolve, "inspect", parameters, None)
        guard()
        _render_job(recovered, parameters, identity)
        immutable(queued_path, recovered)
    job = load(queued_path)
    _render_job(job, parameters, identity)
    # The first returned queue identity is fresh; every later replay inspects it.
    observed = (
        job if reserved_here else render_boundary(resolve, "inspect", parameters, job)
    )
    guard()
    _render_job(observed, parameters, identity)
    fact(
        observed["jobId"] == job["jobId"] and observe() == before,
        "owned render job/target differs",
    )
    if not inspect_render:
        return {
            "status": "queued",
            "evidenceLevel": request["evidenceLevel"],
            "intentHash": file_hash(intent_path),
            "job": job,
        }
    if observed["state"] in ("queued", "rendering"):
        return {
            "status": "needs_action",
            "reason": "owned render is incomplete",
            "job": observed,
        }
    fact(observed["state"] == "complete", "render failed or unknown")
    output_hash = file_hash(output)
    with wave.open(str(output), "rb") as stream:
        rate = manifest["timeline"]["frameRate"]
        count = Fraction(
            settings["durationFrames"] * 48000 * rate["denominator"], rate["numerator"]
        )
        fact(
            count.denominator == 1 and 0 < count <= 3_000_000,
            "frame-aligned bounded full render required",
        )
        samples = int(count)
        fact(
            stream.getnchannels() == 2
            and stream.getframerate() == 48000
            and stream.getsampwidth() == settings["sampleWidth"]
            and stream.getcomptype() == "NONE"
            and stream.getnframes() == samples,
            "complete stereo PCM extent differs",
        )
        fact(
            len(stream.readframes(samples + 1))
            == samples * 2 * settings["sampleWidth"],
            "PCM data truncated",
        )
    fact(
        file_hash(output) == output_hash and observe() == before,
        "render/source changed while inspecting",
    )
    result = {
        "status": "complete",
        "evidenceLevel": request["evidenceLevel"],
        "intentHash": file_hash(intent_path),
        "job": observed,
        "outputHash": output_hash,
        "sampleCount": samples,
    }
    guard()
    immutable(directory / "complete.json", result)
    return result


def _render_job(job: Json, parameters: Json, identity: Json) -> None:
    fact(
        isinstance(job, dict)
        and set(job)
        == {"jobId", "projectUid", "timelineUid", "settings", "outputPath", "state"}
        and isinstance(job["jobId"], str)
        and bool(job["jobId"])
        and job["state"] in ("queued", "rendering", "complete")
        and job["projectUid"] == identity["projectUid"]
        and job["timelineUid"] == identity["timelineUid"]
        and job["settings"] == parameters["settings"]
        and job["outputPath"] == parameters["outputPath"],
        "actual render job/settings/output differ",
    )
