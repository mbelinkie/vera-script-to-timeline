"""Compose the existing compiler and media preparation for bound Research cuts."""

from __future__ import annotations

import fcntl
import json
import os
import tempfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .build_compiler_bridge import invoke_bridge
from .build_stage_receipt import canonical_json, hash_file
from .generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
    PreparedMediaBindingV1,
    RationalRate,
    RequestedPreparationRangeV1,
)
from .media_preparation import (
    POLICY,
    POLICY_HASH,
    PROFILE,
    PROFILE_HASH,
    MediaPreparationError,
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    _assert_under,
    _fsync_directory,
    _qualified_tools,
    _reuse,
    _validate,
    _write_record,
    file_hash,
    preparation_geometry,
    prepare_media,
    rational,
    safe_integer,
    wire,
)
from .narration.models import identity_hash

Json = dict[str, Any]

_MAX_STILL_BYTES = 24 * 1024 * 1024
_MAX_STILL_PIXELS = 16_777_216


@dataclass(frozen=True)
class _StillInspection:
    source_probe: Json
    rate_probe: Json
    width: int
    height: int
    rate: Fraction
    time_base: Fraction
    decoded_frames: int
    decode_command: list[str]


def _inspect_still_png(
    source: Path, target_rate: Fraction, tools: MediaTools
) -> _StillInspection:
    """Verify one RGB PNG as a one-frame source at an explicit logical clock."""
    if source.suffix.lower() != ".png" or source.stat().st_size > _MAX_STILL_BYTES:
        raise MediaPreparationError(
            "unsupported_still", "a bounded PNG still is required"
        )
    try:
        with source.open("rb") as stream:
            if stream.read(8) != b"\x89PNG\r\n\x1a\n":
                raise MediaPreparationError("unsupported_still", "PNG signature differs")
    except OSError as error:
        raise MediaPreparationError("missing_media", "still PNG is unavailable") from error

    rate_text = f"{target_rate.numerator}/{target_rate.denominator}"
    probe_command = [
        tools.ffprobe,
        "-v",
        "error",
        "-protocol_whitelist",
        "file,pipe",
        "-probesize",
        "1048576",
        "-analyzeduration",
        "5000000",
        "-f",
        "image2pipe",
        "-framerate",
        rate_text,
        "-count_frames",
        "-show_streams",
        "-show_frames",
        "-show_entries",
        "stream=codec_type,codec_name,width,height,pix_fmt,nb_read_frames,r_frame_rate,avg_frame_rate,time_base:frame=media_type,stream_index,key_frame,pts,pkt_duration,width,height,pix_fmt",
        "-of",
        "json",
        str(source),
    ]
    try:
        probe = json.loads(tools.run(probe_command, timeout=30).decode())
        streams = probe["streams"]
        frames = probe["frames"]
        if not isinstance(streams, list) or len(streams) != 1:
            raise ValueError("ambiguous still streams")
        stream = streams[0]
        if not isinstance(stream, dict) or not isinstance(frames, list):
            raise ValueError("malformed still probe")
        width, height = stream["width"], stream["height"]
        count = int(stream["nb_read_frames"])
        rate = Fraction(stream["avg_frame_rate"])
        nominal_rate = Fraction(stream["r_frame_rate"])
        time_base = Fraction(stream["time_base"])
        if (
            type(width) is not int
            or type(height) is not int
            or width <= 0
            or height <= 0
            or width * height > _MAX_STILL_PIXELS
            or count != 1
            or len(frames) != 1
            or stream["codec_type"] != "video"
            or stream["codec_name"] != "png"
            or stream["pix_fmt"] != "rgb24"
            or frames[0].get("media_type") != "video"
            or frames[0].get("width") != width
            or frames[0].get("height") != height
            or frames[0].get("pix_fmt") != "rgb24"
            or rate != target_rate
            or nominal_rate != target_rate
            or time_base != 1 / target_rate
        ):
            raise ValueError("still facts differ from the explicit target clock")
    except (
        KeyError,
        TypeError,
        ValueError,
        ZeroDivisionError,
        UnicodeError,
        json.JSONDecodeError,
    ) as error:
        raise MediaPreparationError(
            "invalid_still_probe", "PNG probe did not prove one RGB frame at target rate"
        ) from error

    decode_command = [
        tools.ffmpeg,
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "1",
        "-max_alloc",
        "134217728",
        "-protocol_whitelist",
        "file,pipe",
        "-f",
        "image2pipe",
        "-framerate",
        rate_text,
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-an",
        "-sn",
        "-dn",
        "-frames:v",
        "2",
        "-f",
        "null",
        "-",
        "-progress",
        "pipe:1",
    ]
    try:
        progress = tools.run(decode_command, timeout=30).decode()
        decoded_frames = [
            int(line.split("=", 1)[1])
            for line in progress.splitlines()
            if line.startswith("frame=")
        ]
        if not decoded_frames or decoded_frames[-1] != 1:
            raise ValueError("full decoder did not produce exactly one frame")
    except (UnicodeError, ValueError) as error:
        raise MediaPreparationError(
            "invalid_still_decode", "PNG full decode did not produce one frame"
        ) from error

    source_probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": width,
        "height": height,
        "frames": 1,
    }
    return _StillInspection(
        source_probe=source_probe,
        rate_probe=cast(Json, probe),
        width=width,
        height=height,
        rate=rate,
        time_base=time_base,
        decoded_frames=decoded_frames[-1],
        decode_command=decode_command,
    )


def prepare_still_media(
    source_path: Path,
    descriptor: OccurrenceMediaResolutionV2,
    requested_range: RequestedPreparationRangeV1,
    target_rate: RationalRate,
    *,
    authorization: PreparationAuthorization,
    tools: MediaTools | None = None,
) -> PreparedMedia:
    """Bind an unchanged imported PNG as one logical frame at a target rate.

    The PNG remains the delivered source. Its timeline clock is explicit in a
    separate rate probe because still image files have no intrinsic frame rate.
    """
    return _prepare_still_media(
        source_path,
        descriptor,
        requested_range,
        target_rate,
        authorization=authorization,
        tools=tools,
    )


def _prepare_still_media(
    source_path: Path,
    descriptor: OccurrenceMediaResolutionV2,
    requested_range: RequestedPreparationRangeV1,
    target_rate: RationalRate,
    *,
    authorization: PreparationAuthorization,
    tools: MediaTools | None = None,
    qualification_run: bool = False,
) -> PreparedMedia:
    tools = tools or MediaTools()
    _validate(descriptor, "OccurrenceMediaResolutionV2")
    _validate(requested_range, "RequestedPreparationRangeV1")
    _validate(target_rate, "RationalRate")
    if (
        not isinstance(authorization, PreparationAuthorization)
        or not authorization.reference
        or type(authorization.minimum_free_bytes) is not int
        or authorization.minimum_free_bytes < 0
        or authorization.profile_hash != PROFILE_HASH
        or authorization.policy_hash != POLICY_HASH
    ):
        raise MediaPreparationError("invalid_authorization", "invalid still preparation policy")
    source = _assert_under(source_path, authorization.read_roots)
    root = _assert_under(authorization.write_root, (authorization.write_root,))
    fingerprint = tools.fingerprint()
    tool_hash = identity_hash(fingerprint)
    if tool_hash != authorization.tool_hash:
        raise MediaPreparationError("invalidated_tools", "installed tool fingerprint changed")
    if not qualification_run:
        _qualified_tools(tool_hash)

    snapshot = descriptor["sourceSnapshot"]
    frame_map = descriptor["sourceFrameMap"]
    bounds = descriptor["logicalSourceBounds"]
    target = rational(target_rate, positive=True)
    expected_rate_time = Fraction(1, target.numerator) * target.denominator
    if (
        snapshot["system"] != "local_import"
        or source.suffix.lower() != ".png"
        or bounds["startFrame"] != 0
        or bounds["endFrame"] != 1
        or descriptor["occurrenceSourceInFrame"] != 0
        or descriptor["selectedSourceRange"] is not None
        or rational(bounds["frameRate"], positive=True) != target
        or frame_map["packageFrameZeroLogicalFrame"] != 0
        or rational(frame_map["packageVideoPtsOrigin"]) != 0
        or rational(frame_map["decodedPackageFrameRate"], positive=True) != target
        or frame_map["decodedPackageFrameCount"] != 1
        or rational(frame_map["packageVideoTimeBase"], positive=True)
        != expected_rate_time
        or frame_map["sourceAudioStreamMappings"]
        or requested_range["sourceInFrame"] != 0
        or rational(requested_range["duration"], positive=True) != expected_rate_time
        or rational(requested_range["preHandle"]) != 0
        or rational(requested_range["postHandle"]) != 0
    ):
        raise MediaPreparationError(
            "invalid_still_mapping", "still must be one frame at the exact target rate"
        )

    source_hash = file_hash(source)
    inspected = _inspect_still_png(source, target, tools)
    source_probe_hash = identity_hash(inspected.source_probe)
    if (
        source_hash != snapshot["contentHash"]
        or source_probe_hash != snapshot["probeHash"]
        or frame_map["probeHash"] != source_probe_hash
        or frame_map["descriptorHash"]
        != identity_hash({"snapshot": snapshot, "probe": inspected.source_probe})
        or inspected.decoded_frames != 1
        or file_hash(source) != source_hash
    ):
        raise MediaPreparationError(
            "source_hash_mismatch", "PNG bytes or local import probe differs"
        )

    profile = {
        "policyHash": POLICY_HASH,
        "profileHash": PROFILE_HASH,
        "toolHash": tool_hash,
        "profileVersion": PROFILE["version"],
    }
    key_inputs = {
        "mediaReferenceId": descriptor["mediaReferenceId"],
        "sourceSnapshot": snapshot,
        "sourceFrameMap": frame_map,
        "videoStreamIndex": 0,
        "audioStreamIndex": None,
        "requestedRange": requested_range,
        "targetRate": wire(target),
        "profile": profile,
        "stillInterpretation": "one_png_frame_at_target_rate/v1",
    }
    key = identity_hash(key_inputs)
    geometry = preparation_geometry(
        source_rate=target,
        target_rate=target,
        origin_frame=0,
        lower_frame=0,
        upper_frame=1,
        in_frame=0,
        duration=expected_rate_time,
    )
    mapping: Json = {
        "sourceOrigin": frame_map["loggedTimeAtPackageFrameZero"],
        "deliveredOrigin": wire(Fraction(0)),
        "sourceRate": wire(target),
        "deliveredRate": wire(target),
        "sourceFrameMap": frame_map,
    }
    mapping["mappingHash"] = identity_hash(mapping)
    binding: Json = {
        "requirementKey": key,
        "mode": "verified_reuse",
        "originalSource": {
            "mediaReferenceId": descriptor["mediaReferenceId"],
            "contentHash": source_hash,
            "probeHash": source_probe_hash,
        },
        "targetRate": wire(target),
        "requestedRange": requested_range,
        "profile": profile,
        "timeMapping": mapping,
        "verification": {
            "deliveredHash": source_hash,
            "probeHash": source_probe_hash,
            "decodedFrameCount": 1,
            "decodedFrameRate": wire(target),
            "videoTimeBase": wire(inspected.time_base),
            "sourceAudio": {
                "status": "not_applicable",
                "offset": None,
                "maxDrift": None,
                "sampleRate": None,
            },
        },
        "authorizationReference": authorization.reference,
        "artifactLocator": source.as_uri(),
    }
    _validate(binding, "PreparedMediaBindingV1")
    root.mkdir(parents=True, exist_ok=True)
    for name in ("attempts", "published", "locks"):
        _assert_under(root / name, (root,)).mkdir(exist_ok=True)
    _fsync_directory(root)
    published = root / "published" / key.removeprefix("sha256:")
    _assert_under(published, (root,))
    lock = root / "locks" / (key.removeprefix("sha256:") + ".lock")
    lock_fd = os.open(lock, os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    try:
        try:
            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise MediaPreparationError(
                "preparation_busy", "retry after requirement owner releases lease"
            ) from error
        if published.exists():
            return _reuse_still(
                published, source, key_inputs, authorization, tools, reused=True
            )
        attempt = Path(
            tempfile.mkdtemp(prefix=key.removeprefix("sha256:") + "-", dir=root / "attempts")
        )
        _write_record(
            attempt / "request.json",
            {
                "requirementKey": key,
                "inputs": key_inputs,
                "authorizationReference": authorization.reference,
            },
        )
        _fsync_directory(attempt)
        command_start = len(tools.commands) - 2
        commands = tools.commands[command_start:]
        record = {
            "recordVersion": "authoring-media-preparation/v1",
            "requirementKey": key,
            "inputs": key_inputs,
            "binding": binding,
            "sourceProbe": inspected.source_probe,
            "deliveredProbe": inspected.source_probe,
            "tools": fingerprint,
            "profile": PROFILE,
            "policy": POLICY,
            "commands": commands,
            "audio": None,
            "geometry": {
                "packageStart": wire(geometry.start),
                "packageEnd": wire(geometry.end),
                "requiredExclusiveLogicalFrame": geometry.required_end_frame,
                "sourceCoverSurplus": wire(geometry.cover_surplus),
                "terminalQuantization": wire(geometry.terminal_quantization),
                "selectedPackageFrames": [geometry.selected_package_frame(0)],
            },
            "stillRateProbe": inspected.rate_probe,
            "stillRateProbeHash": identity_hash(inspected.rate_probe),
            "stillDecode": {
                "decodedFrameCount": inspected.decoded_frames,
                "commandHash": identity_hash(inspected.decode_command),
            },
        }
        _write_record(attempt / "receipt.json", record)
        for path in attempt.iterdir():
            with path.open("rb") as stream:
                os.fsync(stream.fileno())
        _fsync_directory(attempt)
        _write_record(
            attempt / "receipt-checksum.pending.json",
            {"receiptHash": file_hash(attempt / "receipt.json")},
        )
        os.rename(
            attempt / "receipt-checksum.pending.json", attempt / "receipt-checksum.json"
        )
        _fsync_directory(attempt)
        tools.check_cancel()
        os.rename(attempt, published)
        _fsync_directory(root / "published")
        _fsync_directory(root / "attempts")
        return _reuse_still(
            published, source, key_inputs, authorization, tools, reused=False
        )
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        os.close(lock_fd)


def _reuse_still(
    published: Path,
    source: Path,
    key_inputs: Json,
    authorization: PreparationAuthorization,
    tools: MediaTools,
    *,
    reused: bool,
) -> PreparedMedia:
    try:
        if published.is_symlink():
            raise ValueError("symlink")
        receipt_path = published / "receipt.json"
        checksum = json.loads((published / "receipt-checksum.json").read_bytes())
        if checksum["receiptHash"] != file_hash(receipt_path):
            raise ValueError("receipt checksum conflict")
        record = cast(Json, json.loads(receipt_path.read_bytes()))
        key = identity_hash(key_inputs)
        if (
            record["inputs"] != key_inputs
            or record["requirementKey"] != key
            or published.name != key.removeprefix("sha256:")
        ):
            raise ValueError("requirement conflict")
        binding = cast(PreparedMediaBindingV1, record["binding"])
        _validate(binding, "PreparedMediaBindingV1")
        fingerprint = tools.fingerprint()
        tool_hash = identity_hash(fingerprint)
        if tool_hash != authorization.tool_hash:
            raise ValueError("tool fingerprint conflict")
        inspected = _inspect_still_png(
            source, rational(key_inputs["targetRate"], positive=True), tools
        )
        source_probe_hash = identity_hash(inspected.source_probe)
        still_decode = record["stillDecode"]
        if (
            binding != record["binding"]
            or binding["requirementKey"] != key
            or binding["mode"] != "verified_reuse"
            or record["profile"] != PROFILE
            or record["policy"] != POLICY
            or identity_hash(record["tools"]) != tool_hash
            or record["sourceProbe"] != inspected.source_probe
            or record["deliveredProbe"] != inspected.source_probe
            or identity_hash(inspected.source_probe)
            != binding["verification"]["probeHash"]
            or record["stillRateProbe"] != inspected.rate_probe
            or identity_hash(record["stillRateProbe"])
            != record["stillRateProbeHash"]
            or record["stillDecode"]["decodedFrameCount"] != 1
            or record["stillDecode"]["commandHash"]
            != identity_hash(inspected.decode_command)
            or not any(
                identity_hash(command) == still_decode["commandHash"]
                for command in record["commands"]
            )
            or file_hash(source) != binding["verification"]["deliveredHash"]
            or binding["verification"]["decodedFrameCount"] != 1
            or binding["verification"]["decodedFrameRate"]
            != wire(inspected.rate)
            or binding["verification"]["videoTimeBase"]
            != wire(inspected.time_base)
            or binding["originalSource"]["probeHash"] != source_probe_hash
            or record["stillDecode"]["decodedFrameCount"]
            != inspected.decoded_frames
        ):
            raise ValueError("still receipt verification conflict")
        projected = cast(
            PreparedMediaBindingV1,
            {
                **binding,
                "authorizationReference": authorization.reference,
                "artifactLocator": source.as_uri(),
            },
        )
        return PreparedMedia(projected, receipt_path, source, None, reused)
    except MediaPreparationError as error:
        if error.code in {"cancelled", "tool_timeout"}:
            raise
        raise MediaPreparationError(
            "published_conflict", "preserve still artifact; inspect before repair"
        ) from error
    except (OSError, KeyError, TypeError, ValueError) as error:
        raise MediaPreparationError(
            "published_conflict", "preserve still artifact; inspect before repair"
        ) from error


def _reuse_cut(
    source: Path,
    descriptor: Json,
    requested_range: Json,
    target_rate: Json,
    root: Path,
    tools: MediaTools,
) -> PreparedMedia | None:
    """Reuse a verified derivative without requalifying installed encoders."""
    expected = {
        "mediaReferenceId": descriptor["mediaReferenceId"],
        "sourceSnapshot": descriptor["sourceSnapshot"],
        "sourceFrameMap": descriptor["sourceFrameMap"],
        "videoStreamIndex": 0,
        "audioStreamIndex": 1,
        "requestedRange": requested_range,
        "targetRate": target_rate,
    }
    for path in sorted((root / "published").glob("*/receipt.json")):
        record = read_json_object(path)
        inputs = record["inputs"]
        if any(inputs.get(key) != value for key, value in expected.items()):
            continue
        profile = inputs["profile"]
        tool_hash = profile["toolHash"]
        if profile != {
            "policyHash": POLICY_HASH,
            "profileHash": PROFILE_HASH,
            "toolHash": tool_hash,
            "profileVersion": PROFILE["version"],
        }:
            continue
        if path.parent.name != identity_hash(inputs).removeprefix("sha256:"):
            raise ValueError("Prepared Research media has a different cache key")
        _qualified_tools(tool_hash)
        authorization = PreparationAuthorization(
            "prep-media-project-local", (root.parent,), root, tool_hash
        )
        return _reuse(path.parent, source, inputs, authorization, tools)
    return None


def _prebound_still(
    source: Path,
    descriptor: Json,
    requested_range: Json,
    target_rate: Json,
    prepared: Mapping[str, Json],
    preparation_paths: Mapping[str, str],
) -> PreparedMedia | None:
    """Keep an accepted one-frame binding byte-identical when its rate matches."""
    key = descriptor.get("preparedMediaRequirementKey")
    if not isinstance(key, str):
        return None
    binding = prepared.get(key)
    receipt_locator = preparation_paths.get(key)
    if not isinstance(binding, dict) or not isinstance(receipt_locator, str):
        return None
    verification = binding.get("verification")
    mapping = binding.get("timeMapping")
    original = binding.get("originalSource")
    target = rational(target_rate, positive=True)
    snapshot = descriptor["sourceSnapshot"]
    if (
        binding.get("mode") != "verified_reuse"
        or binding.get("targetRate") != target_rate
        or binding.get("requestedRange") != requested_range
        or not isinstance(verification, dict)
        or not isinstance(mapping, dict)
        or not isinstance(original, dict)
        or original.get("contentHash") != snapshot.get("contentHash")
        or original.get("probeHash") != snapshot.get("probeHash")
        or mapping.get("sourceFrameMap") != descriptor.get("sourceFrameMap")
        or mapping.get("sourceRate") != descriptor["logicalSourceBounds"]["frameRate"]
        or mapping.get("deliveredRate") != target_rate
        or verification.get("deliveredHash") != snapshot.get("contentHash")
        or verification.get("probeHash") != snapshot.get("probeHash")
        or verification.get("decodedFrameCount") != 1
        or rational(verification.get("decodedFrameRate"), positive=True) != target
        or verification.get("videoTimeBase")
        != descriptor["sourceFrameMap"]["packageVideoTimeBase"]
        or file_hash(source) != snapshot.get("contentHash")
    ):
        return None
    receipt_path = Path(receipt_locator)
    record = read_json_object(receipt_path)
    if (
        record.get("recordVersion") != "authoring-media-preparation/v1"
        or record.get("requirementKey") != key
        or record.get("binding") != binding
    ):
        return None
    return PreparedMedia(
        cast(PreparedMediaBindingV1, binding), receipt_path, source, None, True
    )


def prepare_cut_inputs(
    script: Path,
    dependencies: Json,
    cut_sources: Mapping[str, Path],
    preparation_paths: dict[str, str],
    media_root: Path,
    *,
    tools: MediaTools,
    still_sources: Mapping[str, Path] | None = None,
    report: Callable[[str, bool, float], None] | None = None,
) -> dict[str, tuple[Path, PreparedMedia]]:
    """Prepare bindings for the source ranges selected by the compiler."""
    still_sources = still_sources or {}
    descriptors = {
        item["payloadId"]: item for item in dependencies["occurrenceResolutions"]
    }
    with tempfile.TemporaryDirectory(prefix=".needs-", dir=media_root) as attempt:
        plan_input = Path(attempt) / "compiler-dependencies.json"
        plan_input.write_bytes(canonical_json(dependencies))
        needs = invoke_bridge("needs", script, plan_input).needs
    dependencies["timeline"]["durationFrames"] = needs["durationFrames"]
    if not cut_sources and not still_sources:
        return {}
    root = media_root / "Prepared Clips"
    authorization = None
    prepared = {item["requirementKey"]: item for item in dependencies["preparedMedia"]}
    delivery: dict[str, tuple[Path, PreparedMedia]] = {}
    pending = set(cut_sources)
    still_results: dict[str, tuple[Json, PreparedMedia]] = {}
    still_root = media_root / "Prepared Stills"
    still_authorization: PreparationAuthorization | None = None
    for need in needs["requirements"]:
        payload_id = need["payloadId"]
        if payload_id not in cut_sources and payload_id not in still_sources:
            continue
        if need["sourceSufficiency"] != "sufficient":
            raise ValueError("Research placement has no unique sufficient source range")
        descriptor = descriptors[payload_id]
        started = monotonic()
        target = dependencies["timeline"]["frameRate"]
        if payload_id in still_sources:
            source = still_sources[payload_id]
            previous = still_results.get(payload_id)
            if previous is not None:
                if previous[0] != need["requestedRange"]:
                    raise ValueError("One still source has conflicting preparation ranges")
                result = previous[1]
            else:
                result = _prebound_still(
                    source,
                    descriptor,
                    need["requestedRange"],
                    target,
                    prepared,
                    preparation_paths,
                )
                if result is None:
                    if still_authorization is None:
                        still_authorization = PreparationAuthorization(
                            "prep-media-project-local",
                            (media_root,),
                            still_root,
                            identity_hash(tools.fingerprint()),
                        )
                    result = prepare_still_media(
                        source,
                        cast(OccurrenceMediaResolutionV2, descriptor),
                        need["requestedRange"],
                        target,
                        authorization=still_authorization,
                        tools=tools,
                    )
                still_results[payload_id] = (need["requestedRange"], result)
            binding = result.binding
            key = binding["requirementKey"]
            descriptor["preparedMediaRequirementKey"] = key
            prepared[key] = cast(Json, binding)
            delivery[key] = (source, result)
            preparation_paths[key] = str(result.receipt_path)
            if report is not None:
                report(payload_id, result.reused, monotonic() - started)
            continue

        if payload_id not in pending:
            raise ValueError("Research placement has no unique sufficient source range")
        pending.remove(payload_id)
        source = cut_sources[payload_id]
        result = _reuse_cut(
            source, descriptor, need["requestedRange"], target, root, tools
        )
        if result is None:
            authorization = authorization or PreparationAuthorization(
                "prep-media-project-local",
                (media_root,),
                root,
                identity_hash(tools.fingerprint()),
            )
            result = prepare_media(
                source,
                cast(OccurrenceMediaResolutionV2, descriptor),
                need["requestedRange"],
                target,
                authorization=authorization,
                video_stream_index=0,
                audio_stream_index=1,
                tools=tools,
            )
        binding = result.binding
        if binding != read_json_object(result.receipt_path)["binding"]:
            raise ValueError("Prepared Research media belongs to a different locator")
        key = binding["requirementKey"]
        descriptor["preparedMediaRequirementKey"] = key
        prepared[key] = binding
        delivery[key] = (source, result)
        preparation_paths[key] = str(result.receipt_path)
        if report is not None:
            report(payload_id, result.reused, monotonic() - started)
    if pending:
        raise ValueError("Compiler did not plan every Research cut")
    dependencies["preparedMedia"] = list(prepared.values())
    return delivery


def read_json_object(path: Path) -> Json:
    hash_file(path)
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value
