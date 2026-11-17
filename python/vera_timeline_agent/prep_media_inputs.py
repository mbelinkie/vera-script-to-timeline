"""Compose the existing compiler and media preparation for bound Research cuts."""

from __future__ import annotations

import json
import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from fractions import Fraction
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .build_compiler_bridge import invoke_bridge
from .build_jobs import BuildJobError, publish_immutable_output
from .build_stage_receipt import canonical_json, hash_file
from .generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
    PreparedMediaBindingV1,
    RationalRate,
    RequestedPreparationRangeV1,
)
from .local_media_import import FFmpegDecoder
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
    _qualified_tools,
    _reuse,
    _validate,
    file_hash,
    preparation_geometry,
    prepare_media,
    rational,
    wire,
)
from .narration.models import identity_hash
from .native_image_motion import _verified_rgb_png_dimensions

Json = dict[str, Any]


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


def prepare_still_media(
    source_path: Path,
    descriptor: OccurrenceMediaResolutionV2,
    requested_range: RequestedPreparationRangeV1,
    target_rate: RationalRate,
    *,
    authorization: PreparationAuthorization,
    tools: MediaTools | None = None,
) -> PreparedMedia:
    """Prepare one imported PNG without assigning a measured source rate."""
    tools = tools or MediaTools()
    _validate(descriptor, "OccurrenceMediaResolutionV2")
    _validate(requested_range, "RequestedPreparationRangeV1")
    _validate(target_rate, "RationalRate")
    if (
        not isinstance(authorization, PreparationAuthorization)
        or not authorization.reference
        or authorization.profile_hash != PROFILE_HASH
        or authorization.policy_hash != POLICY_HASH
        or type(authorization.allow_conversion) is not bool
        or type(authorization.minimum_free_bytes) is not int
        or authorization.minimum_free_bytes < 0
    ):
        raise MediaPreparationError("invalid_authorization", "invalid still policy")

    source = _assert_under(source_path, authorization.read_roots)
    target = rational(target_rate, positive=True)
    frame_time = Fraction(target.denominator, target.numerator)
    snapshot = descriptor["sourceSnapshot"]
    frame_map = descriptor["sourceFrameMap"]
    bounds = descriptor["logicalSourceBounds"]
    if (
        snapshot["system"] != "local_import"
        or source.suffix.lower() != ".png"
        or bounds["startFrame"] != 0
        or bounds["endFrame"] != 1
        or rational(bounds["frameRate"], positive=True) != target
        or descriptor["occurrenceSourceInFrame"] != 0
        or descriptor["selectedSourceRange"] is not None
        or frame_map["packageFrameZeroLogicalFrame"] != 0
        or rational(frame_map["packageVideoPtsOrigin"]) != 0
        or rational(frame_map["loggedTimeAtPackageFrameZero"]) != 0
        or rational(frame_map["decodedPackageFrameRate"], positive=True) != target
        or frame_map["decodedPackageFrameCount"] != 1
        or rational(frame_map["packageVideoTimeBase"], positive=True) != frame_time
        or frame_map["sourceAudioStreamMappings"]
        or requested_range["sourceInFrame"] != 0
        or rational(requested_range["duration"], positive=True) != frame_time
        or rational(requested_range["preHandle"]) != 0
        or rational(requested_range["postHandle"]) != 0
    ):
        raise MediaPreparationError(
            "invalid_still_mapping", "still must bind exactly one frame at target rate"
        )

    # Keep the qualified preparation profile; no still-specific tool profile is
    # qualified yet, even though its encoder capabilities are broader than needed.
    fingerprint = tools.fingerprint()
    tool_hash = identity_hash(fingerprint)
    if tool_hash != authorization.tool_hash:
        raise MediaPreparationError("invalidated_tools", "tool fingerprint changed")
    _qualified_tools(tool_hash)

    source_hash = file_hash(source)
    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise MediaPreparationError(
                "unsafe_media", "regular singly linked PNG required"
            )
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
        after = os.fstat(fd)
        current = os.stat(source, follow_symlinks=False)

        def identity(item: os.stat_result) -> tuple[int, int, int, int, int]:
            return (
                item.st_dev,
                item.st_ino,
                item.st_size,
                item.st_mtime_ns,
                item.st_ctime_ns,
            )

        if identity(before) != identity(after) or identity(after) != identity(current):
            raise MediaPreparationError(
                "changed_media", "PNG changed during verification"
            )
    except (OSError, ValueError) as error:
        raise MediaPreparationError("invalid_still", "PNG import probe failed") from (
            error
        )
    finally:
        os.close(fd)

    source_probe = {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": "png",
        "width": facts.width,
        "height": facts.height,
        "frames": 1,
    }
    probe_hash = identity_hash(source_probe)
    dimensions = _verified_rgb_png_dimensions(source, source_hash, source_probe)
    if (
        facts.kind != "image"
        or facts.probe_hash != probe_hash
        or snapshot["contentHash"] != source_hash
        or snapshot["probeHash"] != probe_hash
        or frame_map["probeHash"] != probe_hash
        or frame_map["descriptorHash"]
        != identity_hash({"snapshot": snapshot, "probe": source_probe})
        or dimensions != (facts.width, facts.height)
        or file_hash(source) != source_hash
        or identity_hash(tools.fingerprint()) != tool_hash
    ):
        raise MediaPreparationError(
            "source_hash_mismatch", "PNG import facts or strict RGB decode differ"
        )

    profile = {
        "policyHash": POLICY_HASH,
        "profileHash": PROFILE_HASH,
        "toolHash": tool_hash,
        "profileVersion": PROFILE["version"],
    }
    inputs = {
        "mediaReferenceId": descriptor["mediaReferenceId"],
        "sourceSnapshot": snapshot,
        "sourceFrameMap": frame_map,
        "videoStreamIndex": 0,
        "audioStreamIndex": None,
        "requestedRange": requested_range,
        "targetRate": wire(target),
        "profile": profile,
        "stillInterpretation": "one_png_frame_held_at_timeline_rate/v1",
        "authorizationReference": authorization.reference,
    }
    key = identity_hash(inputs)
    geometry = preparation_geometry(
        source_rate=target,
        target_rate=target,
        origin_frame=0,
        lower_frame=0,
        upper_frame=1,
        in_frame=0,
        duration=frame_time,
    )
    mapping: Json = {
        "sourceOrigin": frame_map["loggedTimeAtPackageFrameZero"],
        "deliveredOrigin": wire(Fraction(0)),
        "sourceRate": wire(target),
        "deliveredRate": wire(target),
        "sourceFrameMap": frame_map,
    }
    mapping["mappingHash"] = identity_hash(mapping)
    binding = cast(
        PreparedMediaBindingV1,
        {
            "requirementKey": key,
            "mode": "verified_reuse",
            "originalSource": {
                "mediaReferenceId": descriptor["mediaReferenceId"],
                "contentHash": source_hash,
                "probeHash": probe_hash,
            },
            "targetRate": wire(target),
            "requestedRange": requested_range,
            "profile": profile,
            "timeMapping": mapping,
            "verification": {
                "deliveredHash": source_hash,
                "probeHash": probe_hash,
                "decodedFrameCount": 1,
                "decodedFrameRate": wire(target),
                "videoTimeBase": wire(frame_time),
                "sourceAudio": {
                    "status": "not_applicable",
                    "offset": None,
                    "maxDrift": None,
                    "sampleRate": None,
                },
            },
            "authorizationReference": authorization.reference,
            "artifactLocator": f"still:sha256:{source_hash.removeprefix('sha256:')}",
        },
    )
    _validate(binding, "PreparedMediaBindingV1")
    record: Json = {
        "recordVersion": "authoring-media-preparation/v1",
        "requirementKey": key,
        "inputs": inputs,
        "binding": binding,
        "sourceProbe": source_probe,
        "deliveredProbe": source_probe,
        "tools": fingerprint,
        "profile": PROFILE,
        "policy": POLICY,
        "commands": [],
        "audio": None,
        "geometry": {
            "packageStart": wire(geometry.start),
            "packageEnd": wire(geometry.end),
            "requiredExclusiveLogicalFrame": geometry.required_end_frame,
            "sourceCoverSurplus": wire(geometry.cover_surplus),
            "terminalQuantization": wire(geometry.terminal_quantization),
            "selectedPackageFrames": [geometry.selected_package_frame(0)],
        },
        "stillEvidence": {
            "version": "one_png_frame_held_at_timeline_rate/v1",
            "sourceProbeHash": probe_hash,
            "strictPng": {
                "sourceHash": source_hash,
                "width": facts.width,
                "height": facts.height,
                "decodedFrameCount": 1,
            },
        },
    }
    root = _assert_under(authorization.write_root, (authorization.write_root,))
    root.mkdir(parents=True, exist_ok=True)
    if (
        shutil.disk_usage(root).free
        < len(canonical_json(record)) + authorization.minimum_free_bytes
    ):
        raise MediaPreparationError(
            "insufficient_disk", "still receipt exceeds free-space reserve"
        )
    published_root = root / "published"
    published = published_root / key.removeprefix("sha256:")
    _assert_under(published_root, (root,)).mkdir(exist_ok=True)
    _assert_under(published, (root,)).mkdir(exist_ok=True)
    receipt_path = published / "receipt.json"
    reused = receipt_path.exists()
    try:
        publish_immutable_output(receipt_path, canonical_json(record))
    except BuildJobError as error:
        raise MediaPreparationError(
            "published_conflict", "still receipt differs"
        ) from error
    if read_json_object(receipt_path) != record or file_hash(source) != source_hash:
        raise MediaPreparationError("published_conflict", "still receipt differs")
    return PreparedMedia(binding, receipt_path, source, None, reused)


def prepare_cut_inputs(
    script: Path,
    dependencies: Json,
    cut_sources: Mapping[str, Path],
    preparation_paths: dict[str, str],
    media_root: Path,
    *,
    tools: MediaTools,
    report: Callable[[str, bool, float], None] | None = None,
) -> dict[str, tuple[Path, PreparedMedia]]:
    """Prepare bindings for the source ranges selected by the compiler."""
    descriptors = {
        item["payloadId"]: item for item in dependencies["occurrenceResolutions"]
    }
    with tempfile.TemporaryDirectory(prefix=".needs-", dir=media_root) as attempt:
        plan_input = Path(attempt) / "compiler-dependencies.json"
        plan_input.write_bytes(canonical_json(dependencies))
        needs = invoke_bridge("needs", script, plan_input).needs
    dependencies["timeline"]["durationFrames"] = needs["durationFrames"]
    if not cut_sources:
        return {}
    root = media_root / "Prepared Clips"
    authorization = None
    prepared = {item["requirementKey"]: item for item in dependencies["preparedMedia"]}
    delivery: dict[str, tuple[Path, PreparedMedia]] = {}
    pending = set(cut_sources)
    for need in needs["requirements"]:
        payload_id = need["payloadId"]
        if payload_id not in cut_sources:
            continue
        if need["sourceSufficiency"] != "sufficient" or payload_id not in pending:
            raise ValueError("Research placement has no unique sufficient source range")
        pending.remove(payload_id)
        descriptor = descriptors[payload_id]
        started = monotonic()
        source = cut_sources[payload_id]
        target = dependencies["timeline"]["frameRate"]
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
