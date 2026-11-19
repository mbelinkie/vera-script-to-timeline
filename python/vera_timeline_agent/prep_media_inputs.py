"""Compose the existing compiler and media preparation for bound Research cuts."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import tempfile
from collections.abc import Callable, Mapping
from fractions import Fraction
from io import BytesIO
from pathlib import Path
from time import monotonic
from typing import Any, cast

from PIL import Image, ImageCms, ImageOps
from PIL import __version__ as PILLOW_VERSION

from .build_compiler_bridge import invoke_bridge
from .build_jobs import BuildJobError, publish_immutable_output
from .build_stage_receipt import canonical_json, hash_file
from .generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
    PreparedMediaBindingV1,
    RationalRate,
    RequestedPreparationRangeV1,
)
from .local_media_import import IMAGE_SUFFIXES, FFmpegDecoder
from .local_media_import_model import DecodedMediaFacts
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
from .native_image_motion import (
    MAX_STILL_EDGE,
    MAX_STILL_PIXELS,
    MAX_STILL_PNG_BYTES,
    _verified_rgb_png_dimensions,
)

Json = dict[str, Any]

_LEGACY_STILL_INTERPRETATION = "one_png_frame_held_at_timeline_rate/v1"
_NORMALIZED_STILL_INTERPRETATION = "one_normalized_png_frame_held_at_timeline_rate/v1"


def _still_probe(codec: str, width: int, height: int) -> Json:
    return {
        "kind": "image",
        "demuxer": "image2pipe",
        "codec": codec,
        "width": width,
        "height": height,
        "frames": 1,
    }


def _image_orientation(raw: bytes, facts: DecodedMediaFacts, source_probe: Json) -> int:
    if (
        max(facts.width, facts.height) > MAX_STILL_EDGE
        or facts.width * facts.height > MAX_STILL_PIXELS
    ):
        raise MediaPreparationError(
            "unsupported_dimensions",
            f"stills must fit {MAX_STILL_EDGE} pixels per edge "
            f"and {MAX_STILL_PIXELS} total",
        )
    codec = source_probe["codec"]
    # Pillow reads some 16-bit RGB PNGs into its 8-bit RGB mode.
    if codec == "png" and (len(raw) < 29 or raw[12:16] != b"IHDR" or raw[24] != 8):
        raise MediaPreparationError(
            "unsupported_profile", "PNG must use 8-bit channel precision"
        )

    try:
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG"]) as image:
            expected_format = "PNG" if codec == "png" else "JPEG"
            if image.format != expected_format or image.size != (
                facts.width,
                facts.height,
            ):
                raise MediaPreparationError(
                    "source_hash_mismatch",
                    "still dimensions or format differ from import",
                )
            if getattr(image, "n_frames", 1) != 1:
                raise MediaPreparationError(
                    "unsupported_profile", "animated stills are unsupported"
                )
            if image.mode != "RGB" or "transparency" in image.info:
                raise MediaPreparationError(
                    "unsupported_profile",
                    "still must be opaque RGB (alpha, grayscale, indexed and CMYK)",
                )
            orientation = image.getexif().get(274, 1)
            if type(orientation) is not int or orientation not in range(1, 9):
                raise MediaPreparationError(
                    "unsupported_orientation", "EXIF orientation is outside 1..8"
                )
            if codec == "png" and not {"icc_profile", "srgb"}.intersection(image.info):
                gamma = image.info.get("gamma", 0.45455)
                srgb_chromaticity = (0.3127, 0.329, 0.64, 0.33, 0.30, 0.60, 0.15, 0.06)
                chromaticity = image.info.get("chromaticity", srgb_chromaticity)
                if abs(gamma - 0.45455) > 0.00005 or any(
                    abs(actual - expected) > 0.00005
                    for actual, expected in zip(
                        chromaticity, srgb_chromaticity, strict=True
                    )
                ):
                    raise MediaPreparationError(
                        "unsupported_profile",
                        "non-sRGB PNG color requires an RGB ICC profile",
                    )
    except (OSError, ValueError) as error:
        raise MediaPreparationError(
            "invalid_still", "still metadata cannot be read"
        ) from error
    return orientation


def _normalize_still(raw: bytes, destination: Path) -> None:
    """Apply EXIF orientation and embedded color before encoding RGB PNG."""
    try:
        with Image.open(BytesIO(raw), formats=["PNG", "JPEG"]) as image:
            ImageOps.exif_transpose(image, in_place=True)
            output: Image.Image = image
            icc = image.info.get("icc_profile")
            if icc is not None:
                try:
                    profile = ImageCms.ImageCmsProfile(BytesIO(icc))
                    if profile.profile.xcolor_space != "RGB ":
                        raise MediaPreparationError(
                            "unsupported_profile", "still ICC profile must be RGB"
                        )
                    converted = ImageCms.profileToProfile(
                        image, profile, ImageCms.createProfile("sRGB"), outputMode="RGB"
                    )
                    if converted is None:
                        raise MediaPreparationError(
                            "unsupported_profile",
                            "still ICC profile conversion returned no image",
                        )
                    output = converted
                except (ImageCms.PyCMSError, OSError, TypeError, ValueError) as error:
                    raise MediaPreparationError(
                        "unsupported_profile", "still ICC profile conversion failed"
                    ) from error
            output.info.clear()
            output.save(destination, format="PNG")
    except (OSError, ValueError) as error:
        raise MediaPreparationError(
            "decode_or_tool_failure", "still normalization failed"
        ) from error


def _verify_still_output(
    path: Path, width: int, height: int, tools: MediaTools
) -> tuple[str, Json]:
    output_hash = file_hash(path)
    probe = _still_probe("png", width, height)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC)
    try:
        facts = FFmpegDecoder(ffprobe=tools.ffprobe, ffmpeg=tools.ffmpeg).decode(
            fd, "image"
        )
    except (OSError, ValueError) as error:
        raise MediaPreparationError(
            "output_verification_failed", "normalized still is not a decodable PNG"
        ) from error
    finally:
        os.close(fd)
    if (
        facts.probe_hash != identity_hash(probe)
        or (facts.width, facts.height) != (width, height)
        or _verified_rgb_png_dimensions(path, output_hash, probe) != (width, height)
        or file_hash(path) != output_hash
    ):
        raise MediaPreparationError(
            "output_verification_failed", "normalized still is not strict RGB PNG"
        )
    return output_hash, probe


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
    verify_only: bool = False,
) -> PreparedMedia:
    """Prepare one imported still while keeping the delivered asset strict RGB PNG."""
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
        or source.suffix.lower() not in IMAGE_SUFFIXES
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

    fingerprint = tools.fingerprint()
    tool_hash = identity_hash(fingerprint)
    if tool_hash != authorization.tool_hash:
        raise MediaPreparationError("invalidated_tools", "tool fingerprint changed")
    _qualified_tools(tool_hash)

    fd = os.open(source, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise MediaPreparationError(
                "unsafe_media", "regular singly linked still required"
            )
        if before.st_size > MAX_STILL_PNG_BYTES:
            raise MediaPreparationError(
                "unsupported_dimensions", "still exceeds file limit"
            )
        chunks: list[bytes] = []
        offset = 0
        while offset < before.st_size:
            chunk = os.pread(fd, min(1024 * 1024, before.st_size - offset), offset)
            if not chunk:
                raise MediaPreparationError(
                    "changed_media", "still truncated during verification"
                )
            chunks.append(chunk)
            offset += len(chunk)
        raw = b"".join(chunks)
        source_hash = "sha256:" + hashlib.sha256(raw).hexdigest()
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
                "changed_media", "still changed during verification"
            )
    except (OSError, ValueError) as error:
        raise MediaPreparationError(
            "invalid_still", "still import probe failed"
        ) from error
    finally:
        os.close(fd)

    source_probe: Json | None = None
    for codec in ("png", "mjpeg"):
        candidate = _still_probe(codec, facts.width, facts.height)
        if facts.probe_hash == identity_hash(candidate):
            source_probe = candidate
            break
    if facts.kind != "image" or source_probe is None:
        raise MediaPreparationError(
            "source_hash_mismatch", "image import facts do not match PNG/JPEG source"
        )
    probe_hash = identity_hash(source_probe)
    orientation = _image_orientation(raw, facts, source_probe)
    dimensions_from_probe = (facts.width, facts.height)
    displayed_size = (
        dimensions_from_probe[::-1] if orientation >= 5 else dimensions_from_probe
    )
    dimensions = _verified_rgb_png_dimensions(source, source_hash, source_probe)
    strict_source = orientation == 1 and dimensions == dimensions_from_probe
    if (
        snapshot["contentHash"] != source_hash
        or snapshot["probeHash"] != probe_hash
        or frame_map["probeHash"] != probe_hash
        or frame_map["descriptorHash"]
        != identity_hash({"snapshot": snapshot, "probe": source_probe})
        or file_hash(source) != source_hash
        or identity_hash(tools.fingerprint()) != tool_hash
    ):
        raise MediaPreparationError(
            "source_hash_mismatch", "PNG import facts or source bytes differ"
        )
    if not strict_source and not authorization.allow_conversion:
        raise MediaPreparationError(
            "conversion_needed", "still requires normalization to strict RGB PNG"
        )

    profile = {
        "policyHash": POLICY_HASH,
        "profileHash": PROFILE_HASH,
        "toolHash": tool_hash,
        "profileVersion": PROFILE["version"],
    }
    interpretation = (
        _LEGACY_STILL_INTERPRETATION
        if strict_source
        else _NORMALIZED_STILL_INTERPRETATION
    )
    inputs = {
        "mediaReferenceId": descriptor["mediaReferenceId"],
        "sourceSnapshot": snapshot,
        "sourceFrameMap": frame_map,
        "videoStreamIndex": 0,
        "audioStreamIndex": None,
        "requestedRange": requested_range,
        "targetRate": wire(target),
        "profile": profile,
        "stillInterpretation": interpretation,
        "authorizationReference": authorization.reference,
    }
    if not strict_source:
        inputs["normalizerVersion"] = PILLOW_VERSION
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

    root = _assert_under(authorization.write_root, (authorization.write_root,))
    published_root = root / "published"
    published = published_root / key.removeprefix("sha256:")
    receipt_path = _assert_under(published / "receipt.json", (root,))
    delivered_path = (
        source if strict_source else _assert_under(published / "picture.png", (root,))
    )
    reused = receipt_path.exists()
    if verify_only and not reused:
        raise MediaPreparationError("missing_receipt", "still receipt missing")
    if not reused:
        root.mkdir(parents=True, exist_ok=True)

    output_bytes = None
    if strict_source:
        delivered_hash, delivered_probe = source_hash, source_probe
    elif reused:
        if not delivered_path.is_file():
            raise MediaPreparationError(
                "missing_receipt", "normalized still output missing"
            )
        delivered_hash, delivered_probe = _verify_still_output(
            delivered_path, *displayed_size, tools
        )
    else:
        with tempfile.TemporaryDirectory(prefix=".still-", dir=root) as attempt:
            temporary = Path(attempt) / "picture.png"
            _normalize_still(raw, temporary)
            delivered_hash, delivered_probe = _verify_still_output(
                temporary, *displayed_size, tools
            )
            output_bytes = temporary.read_bytes()

    binding = cast(
        PreparedMediaBindingV1,
        {
            "requirementKey": key,
            "mode": "verified_reuse" if strict_source else "derived_cfr",
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
                "deliveredHash": delivered_hash,
                "probeHash": identity_hash(delivered_probe),
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
            "artifactLocator": (
                f"still:sha256:{source_hash.removeprefix('sha256:')}"
                if strict_source
                else delivered_path.as_uri()
            ),
        },
    )
    commands: list[list[str]] = []
    if not strict_source:
        commands = [
            [
                "Pillow",
                PILLOW_VERSION,
                "EXIF transpose",
                "RGB to sRGB if profiled",
                "RGB PNG",
            ]
        ]
        binding["derivation"] = {
            "method": "cfr_sample/v1",
            "sourceHash": source_hash,
            "outputHash": delivered_hash,
            "toolHash": tool_hash,
            "profileHash": PROFILE_HASH,
            "commandHash": identity_hash(commands),
        }
    _validate(binding, "PreparedMediaBindingV1")
    evidence: Json = {
        "version": interpretation,
        "sourceProbeHash": probe_hash,
        "strictPng": {
            "sourceHash": delivered_hash,
            "width": displayed_size[0],
            "height": displayed_size[1],
            "decodedFrameCount": 1,
        },
    }
    if not strict_source:
        evidence["orientation"] = orientation
    record: Json = {
        "recordVersion": "authoring-media-preparation/v1",
        "requirementKey": key,
        "inputs": inputs,
        "binding": binding,
        "sourceProbe": source_probe,
        "deliveredProbe": delivered_probe,
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
        "stillEvidence": evidence,
    }
    if not reused:
        raw_receipt = canonical_json(record)
        needed = len(raw_receipt) + (
            len(output_bytes) if output_bytes is not None else 0
        )
        if shutil.disk_usage(root).free < needed + authorization.minimum_free_bytes:
            raise MediaPreparationError(
                "insufficient_disk", "still preparation exceeds free-space reserve"
            )
        published_root.mkdir(exist_ok=True)
        published.mkdir(exist_ok=True)
        try:
            if output_bytes is not None:
                publish_immutable_output(delivered_path, output_bytes)
            publish_immutable_output(receipt_path, raw_receipt)
        except BuildJobError as error:
            raise MediaPreparationError(
                "published_conflict", "still preparation publication differs"
            ) from error
    if (
        read_json_object(receipt_path) != record
        or file_hash(delivered_path) != delivered_hash
        or file_hash(source) != source_hash
    ):
        raise MediaPreparationError("published_conflict", "still preparation differs")
    return PreparedMedia(binding, receipt_path, delivered_path, None, reused)


def prepare_cut_inputs(
    script: Path,
    dependencies: Json,
    cut_sources: Mapping[str, Path],
    preparation_paths: dict[str, str],
    media_root: Path,
    *,
    tools: MediaTools,
    needs: Json | None = None,
    report: Callable[[str, bool, float], None] | None = None,
) -> dict[str, tuple[Path, PreparedMedia]]:
    """Prepare bindings for the source ranges selected by the compiler."""
    descriptors = {
        item["payloadId"]: item for item in dependencies["occurrenceResolutions"]
    }
    needs = needs or compiler_media_needs(script, dependencies, media_root)
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


def compiler_media_needs(script: Path, dependencies: Json, media_root: Path) -> Json:
    """Ask the pinned compiler which bound source ranges this script needs."""
    with tempfile.TemporaryDirectory(prefix=".needs-", dir=media_root) as attempt:
        plan_input = Path(attempt) / "compiler-dependencies.json"
        plan_input.write_bytes(canonical_json(dependencies))
        return invoke_bridge("needs", script, plan_input).needs


def prepare_still_inputs(
    needs: Json,
    dependencies: Json,
    media_paths: Json,
    preparation_paths: dict[str, str],
    media_root: Path,
    *,
    tools: MediaTools,
    report: Callable[[str], None] | None = None,
) -> dict[str, tuple[Path, PreparedMedia]]:
    """Bind selected project-local PNG stills using the compiler's exact ranges."""
    descriptors: dict[str, list[Json]] = {}
    for descriptor in dependencies["occurrenceResolutions"]:
        descriptors.setdefault(descriptor["payloadId"], []).append(descriptor)

    authorization: PreparationAuthorization | None = None
    prepared: dict[str, PreparedMediaBindingV1] = {
        item["requirementKey"]: item for item in dependencies["preparedMedia"]
    }
    delivery: dict[str, tuple[Path, PreparedMedia]] = {}
    seen: set[str] = set()
    root = media_root / "Prepared Stills"
    for need in needs["requirements"]:
        payload_id = need["payloadId"]
        matches = descriptors.get(payload_id, [])
        if len(matches) != 1:
            continue
        descriptor = matches[0]
        if (
            descriptor["mediaReferenceId"] != need["mediaReferenceId"]
            or descriptor["sourceSnapshot"]["system"] != "local_import"
        ):
            continue
        locator = media_paths.get(f"source:{descriptor['mediaReferenceId']}")
        if not isinstance(locator, str) or not Path(locator).is_absolute():
            continue
        source = Path(locator)
        if source.suffix.lower() not in IMAGE_SUFFIXES:
            continue
        if payload_id in seen:
            raise ValueError("Compiler planned a local still more than once")
        seen.add(payload_id)
        if need["sourceSufficiency"] != "sufficient":
            raise ValueError(
                "Local still does not cover the compiler's requested range"
            )
        if authorization is None:
            authorization = PreparationAuthorization(
                "prep-media-project-local",
                (media_root,),
                root,
                identity_hash(tools.fingerprint()),
            )
        started = monotonic()
        result = prepare_still_media(
            source,
            cast(OccurrenceMediaResolutionV2, descriptor),
            cast(RequestedPreparationRangeV1, need["requestedRange"]),
            cast(RationalRate, dependencies["timeline"]["frameRate"]),
            authorization=authorization,
            tools=tools,
        )
        binding = result.binding
        if binding != read_json_object(result.receipt_path)["binding"]:
            raise ValueError("Prepared still belongs to a different source binding")
        key = binding["requirementKey"]
        descriptor["preparedMediaRequirementKey"] = key
        prepared[key] = binding
        previous = delivery.get(key)
        if previous is not None and previous[0] != source:
            raise ValueError("Shared still preparation has conflicting source paths")
        delivery[key] = (source, result)
        preparation_paths[key] = str(result.receipt_path)
        if report is not None:
            status = "reused" if result.reused else "prepared"
            report(f"Still {payload_id}: {status} ({monotonic() - started:.2f}s)")

    dependencies["preparedMedia"] = list(prepared.values())
    return delivery


def read_json_object(path: Path) -> Json:
    hash_file(path)
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value
