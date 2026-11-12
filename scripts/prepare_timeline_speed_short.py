"""Prepare the retained short sample as an offline, runnable 24 fps input bundle.

This copies the retained v2 document/timing evidence, makes fresh 24 fps source
media, and validates the result through the pure compiler and package builder.
It never connects to Resolve or changes its source package.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import shutil
import subprocess
import uuid
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from time import perf_counter
from typing import Any, Literal, cast

from vera_timeline_agent.build_compiler_bridge import BridgeOutput
from vera_timeline_agent.build_stage_receipt import hash_file
from vera_timeline_agent.build_timeline_once import BuildOptions, compile_prepared
from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    FrameRangeV2,
    NonNegativeRationalTime,
    OccurrenceMediaResolutionV2,
    RationalRate,
    SourceFrameMapV1,
)
from vera_timeline_agent.media_preparation import (
    MediaInspection,
    MediaTools,
    PreparationAuthorization,
    _qualified_tools,
    inspect_media,
    prepare_media,
    wire,
)
from vera_timeline_agent.media_preparation import (
    file_hash as media_file_hash,
)
from vera_timeline_agent.narration.models import identity_hash, sha256_bytes
from vera_timeline_agent.v2_package import _compiler_hash, build_v2_package

Json = dict[str, Any]
RATE = Fraction(24, 1)
RATE_WIRE: RationalRate = {"numerator": 24, "denominator": 1}
ROOT = Path(__file__).resolve().parents[1]
NODE_DEFAULT = (
    Path.home() / ".local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"
)
MAX_OUTPUT_RESERVE = 512 * 1024**2
REQUIRED_VIDEO_PROFILE = {
    "pix_fmt": "yuv420p",
    "color_range": "tv",
    "color_space": "bt709",
    "color_primaries": "bt709",
    "color_transfer": "bt709",
}


def _regular(path: Path) -> Path:
    path = path.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError(f"symlink path refused: {path.name}")
    if not path.is_file():
        raise ValueError(f"required input file is missing: {path.name}")
    return path.resolve()


def _json(path: Path) -> Json:
    value = json.loads(_regular(path).read_text())
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path.name}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    )


def _physical_under(path: Path, root: Path) -> Path:
    physical = _regular(path)
    if not physical.is_relative_to(root.resolve()):
        raise ValueError("retained media path escapes the supplied read root")
    return physical


def _nearest_frame(index: int, old_rate: Fraction, origin: int) -> int:
    position = Fraction(index - origin, 1) * RATE / old_rate
    return math.floor(position + Fraction(1, 2))


def _mapped_range(value: FrameRangeV2, old_rate: Fraction, origin: int) -> FrameRangeV2:
    start, end = value.get("startFrame"), value.get("endFrame")
    if type(start) is not int or type(end) is not int or end <= start:
        raise ValueError("retained source range is invalid")
    new_start = _nearest_frame(start, old_rate, origin)
    new_length = math.ceil(Fraction(end - start, 1) * RATE / old_rate)
    return {"startFrame": new_start, "endFrame": new_start + new_length}


def _rate(value: Mapping[str, object]) -> Fraction:
    numerator, denominator = value.get("numerator"), value.get("denominator")
    if type(numerator) is not int or type(denominator) is not int or denominator <= 0:
        raise ValueError("retained source frame rate is invalid")
    return Fraction(numerator, denominator)


def _evidence_hash(value: list[Json]) -> str:
    def frame_fields(item: Any) -> list[str]:
        if isinstance(item, dict):
            found = [key for key in item if "frame" in key.lower()]
            return found + [
                name for child in item.values() for name in frame_fields(child)
            ]
        if isinstance(item, list):
            return [name for child in item for name in frame_fields(child)]
        return []

    if len(value) != 2 or frame_fields(value):
        raise ValueError(
            "narration evidence is not sample/time-based or has changed shape"
        )
    for row in value:
        if (
            row.get("verification", {}).get("method") != "measured_audio_boundaries/v1"
            or row.get("audio", {}).get("sampleRate") != 48000
            or type(row.get("audio", {}).get("durationSamples")) is not int
        ):
            raise ValueError("measured 48 kHz narration evidence is required")
        for token in row.get("tokens", []):
            for field in ("onset", "audibleEnd"):
                mark = token.get(field)
                if mark is not None and (
                    not isinstance(mark, dict)
                    or type(mark.get("numerator")) is not int
                    or type(mark.get("denominator")) is not int
                    or mark["denominator"] <= 0
                ):
                    raise ValueError(
                        "narration evidence must retain rational audio times"
                    )
    return identity_hash(value)


def _hash(path: Path) -> str:
    return media_file_hash(path)


def _transcode(
    source: Path,
    output: Path,
    *,
    stream_index: int,
    tools: MediaTools,
) -> None:
    tools.run(
        [
            tools.ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-n",
            "-i",
            str(source),
            "-map",
            f"0:{stream_index}",
            "-an",
            "-vf",
            "fps=fps=24:round=near:eof_action=round,format=yuv420p",
            "-fps_mode",
            "cfr",
            "-r",
            "24",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-threads",
            "1",
            "-pix_fmt",
            "yuv420p",
            "-color_range",
            "tv",
            "-colorspace",
            "bt709",
            "-color_primaries",
            "bt709",
            "-color_trc",
            "bt709",
            "-movflags",
            "+faststart",
            str(output),
        ],
        timeout=1800,
    )


def _new_descriptor(
    old: OccurrenceMediaResolutionV2,
    inspection: MediaInspection,
    package_id: str,
) -> OccurrenceMediaResolutionV2:
    content_hash = inspection.content_hash
    probe_hash = inspection.probe_hash
    media_reference_id = old["mediaReferenceId"]
    snapshot_id = str(
        uuid.uuid5(uuid.UUID(package_id), f"{media_reference_id}:{content_hash}")
    )
    frame_count = len(inspection.video_frames)
    frame_map: SourceFrameMapV1 = {
        "decodedPackageFrameCount": frame_count,
        "decodedPackageFrameRate": RATE_WIRE,
        "descriptorHash": probe_hash,
        "loggedTimeAtPackageFrameZero": {"numerator": 0, "denominator": 1},
        "packageFrameZeroLogicalFrame": 0,
        "packageVideoPtsOrigin": cast(
            NonNegativeRationalTime, wire(inspection.pts_origin)
        ),
        "packageVideoTimeBase": cast(RationalRate, wire(inspection.time_base)),
        "probeHash": probe_hash,
        "sourceAudioStreamMappings": [],
    }
    result = copy.deepcopy(old)
    result["sourceSnapshot"] = {
        "system": "local_import",
        "snapshotId": snapshot_id,
        "version": 1,
        "packageId": package_id,
        "contentHash": content_hash,
        "probeHash": probe_hash,
    }
    result["logicalSourceBounds"] = {
        "startFrame": 0,
        "endFrame": frame_count,
        "frameRate": RATE_WIRE,
    }
    result["sourceFrameMap"] = frame_map
    result["occurrenceSourceInFrame"] = 0
    result["preparedMediaRequirementKey"] = None
    result["selectedSourceRange"] = None
    return result


def _update_document(
    document: Json, old_descriptors: list[OccurrenceMediaResolutionV2]
) -> None:
    by_payload = {row["payloadId"]: row for row in old_descriptors}
    by_ref = {row["mediaReferenceId"]: row for row in old_descriptors}
    for block in document["activeDraft"]["blocks"]:
        if block.get("type") == "visual_only":
            payload = block.get("payload", {})
            source = payload.get("source", {})
            descriptor = by_payload.get(payload.get("payloadId"))
            if descriptor and source.get("kind") == "media_reference":
                old_rate = _rate(descriptor["logicalSourceBounds"]["frameRate"])
                old_origin = descriptor["sourceFrameMap"][
                    "packageFrameZeroLogicalFrame"
                ]
                selected = block.get("visualOnlyTiming", {}).get("selectedSourceRange")
                if selected:
                    mapped = _mapped_range(
                        {
                            "startFrame": selected["startFrame"],
                            "endFrame": selected["startFrame"]
                            + selected["durationFrames"],
                        },
                        old_rate,
                        old_origin,
                    )
                    block["visualOnlyTiming"]["selectedSourceRange"] = {
                        "startFrame": mapped["startFrame"],
                        "durationFrames": mapped["endFrame"] - mapped["startFrame"],
                    }

        def visit(value: Any) -> None:
            if isinstance(value, dict):
                payload = value.get("payload")
                if isinstance(payload, dict):
                    source = payload.get("source")
                    usage = payload.get("sourceUsage")
                    if (
                        isinstance(source, dict)
                        and source.get("kind") == "media_reference"
                        and isinstance(usage, dict)
                        and type(usage.get("sourceInFrame")) is int
                    ):
                        ref = source["mediaReferenceId"]
                        old = by_ref[ref]
                        usage["sourceInFrame"] = _nearest_frame(
                            usage["sourceInFrame"],
                            _rate(old["logicalSourceBounds"]["frameRate"]),
                            old["sourceFrameMap"]["packageFrameZeroLogicalFrame"],
                        )
                for child in value.values():
                    visit(child)
            elif isinstance(value, list):
                for child in value:
                    visit(child)

        visit(block)


def _pinned_bridge(
    kind: Literal["needs", "compile"],
    document: Path,
    dependencies: Path,
    node: Path,
) -> BridgeOutput:
    script = ROOT / (
        "packages/contracts/src/build-media-needs-cli.ts"
        if kind == "needs"
        else "packages/contracts/src/issue-190-compile-cli.ts"
    )
    version = subprocess.run(
        [str(node), "--version"], capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()
    if version != "v24.19.0":
        raise ValueError(f"pinned Node v24.19.0 required, found {version}")
    run = subprocess.run(
        [str(node), str(script), str(document), str(dependencies)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    if run.returncode:
        raise ValueError(f"offline {kind} failed: {run.stderr.strip()[:500]}")
    data = json.loads(run.stdout)
    return BridgeOutput(kind, hash_file(document), hash_file(dependencies), data)


def prepare(source_root: Path, read_root: Path, output: Path, node: Path) -> None:
    started = perf_counter()
    source_root = source_root.resolve(strict=True)
    read_root = read_root.resolve(strict=True)
    if not source_root.is_relative_to(read_root):
        raise ValueError("source package must be under the supplied read root")
    if output.exists():
        raise ValueError("output directory must be new; choose a fresh path")
    if any(
        part.is_symlink() for part in (output.absolute(), *output.absolute().parents)
    ):
        raise ValueError("output path contains a symlink")
    output.parent.mkdir(parents=True, exist_ok=True)
    node = _regular(node)
    source_document_path = _regular(source_root / "document.json")
    source_dependencies_path = _regular(source_root / "dependencies.json")
    source_view_path = next(
        (source_root / "package/Builds").glob("*/delivery-view.json"), None
    )
    if source_view_path is None:
        raise ValueError("retained delivery view is missing")
    source_view = _json(source_view_path)
    document = _json(source_document_path)
    dependencies = _json(source_dependencies_path)
    if document.get("schemaVersion") != "script-document/v2":
        raise ValueError("retained document is not script-document/v2")
    if dependencies.get("schemaVersion") != "compiler-dependencies/v2":
        raise ValueError("retained dependencies are not compiler-dependencies/v2")
    descriptors: list[OccurrenceMediaResolutionV2] = dependencies.get(
        "occurrenceResolutions", []
    )
    evidence_hash = _evidence_hash(dependencies.get("narrationBoundaryEvidence", []))
    original_text_hash = dependencies["document"]["textHash"]
    if len(descriptors) != 6:
        raise ValueError(
            "retained short sample no longer matches its six-source/two-narration shape"
        )

    prepared_by_ref = {
        row["originalSource"]["mediaReferenceId"]: row
        for row in dependencies.get("preparedMedia", [])
    }
    if set(prepared_by_ref) != {row["mediaReferenceId"] for row in descriptors}:
        raise ValueError("retained prepared-media bindings do not match occurrences")

    package_root = source_root / "package"
    pictures_by_hash = {
        item["contentHash"]: item["path"] for item in source_view["sources"]
    }
    tools = MediaTools()
    tool_hash = identity_hash(tools.fingerprint())
    _qualified_tools(tool_hash)
    source_bytes = 0
    source_paths: dict[str, Path] = {}
    old_inspections: dict[str, MediaInspection] = {}
    for descriptor in descriptors:
        ref = descriptor["mediaReferenceId"]
        snapshot_hash = descriptor["sourceSnapshot"]["contentHash"]
        relative_path = pictures_by_hash.get(snapshot_hash)
        if relative_path is None:
            raise ValueError("retained package lacks the exact picture source")
        path = _physical_under(package_root / relative_path, package_root)
        inspection = inspect_media(
            path, video_stream_index=0, audio_stream_index=None, tools=tools
        )
        if (
            inspection.content_hash != descriptor["sourceSnapshot"]["contentHash"]
            or inspection.probe_hash != descriptor["sourceSnapshot"]["probeHash"]
            or inspection.rate != _rate(descriptor["logicalSourceBounds"]["frameRate"])
            or inspection.audio is not None
        ):
            raise ValueError(
                "retained source bytes/probe do not match their descriptor"
            )
        if any(inspection.video.get(k) != v for k, v in REQUIRED_VIDEO_PROFILE.items()):
            raise ValueError(
                "retained source is outside the qualified SDR H.264 profile"
            )
        source_paths[ref] = path
        old_inspections[ref] = inspection
        source_bytes += path.stat().st_size

    estimate = source_bytes * 4 + MAX_OUTPUT_RESERVE
    if shutil.disk_usage(output.parent).free < estimate:
        raise ValueError(
            f"insufficient free space for estimated {estimate} byte output"
        )
    print(f"Input video bytes: {source_bytes}; reserved output budget: {estimate}")

    output.mkdir(parents=True)
    inputs = output / "inputs"
    media_root = output / "media/24fps"
    prep_root = output / "preparation"
    inputs.mkdir()
    media_root.mkdir(parents=True)
    prep_root.mkdir()
    script_path = inputs / "script-document.json"
    dependencies_path = inputs / "compiler-dependencies.json"

    package_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"vera:520:{document['id']}:24fps"))
    new_descriptors: list[OccurrenceMediaResolutionV2] = []
    converted_paths: dict[str, Path] = {}
    new_inspections: dict[str, MediaInspection] = {}
    for old in descriptors:
        ref = old["mediaReferenceId"]
        old_path = source_paths[ref]
        target = media_root / f"{ref}.mov"
        _transcode(
            old_path,
            target,
            stream_index=int(old_inspections[ref].video["index"]),
            tools=tools,
        )
        if _hash(old_path) != old_inspections[ref].content_hash:
            raise ValueError("retained source changed during preparation")
        inspection = inspect_media(
            target, video_stream_index=0, audio_stream_index=None, tools=tools
        )
        if (
            inspection.rate != RATE
            or inspection.audio is not None
            or not inspection.video_frames
        ):
            raise ValueError(
                "transcoded source did not decode as 24 fps video-only media"
            )
        if any(inspection.video.get(k) != v for k, v in REQUIRED_VIDEO_PROFILE.items()):
            raise ValueError("transcoded source failed its qualified SDR profile check")
        converted_paths[ref] = target.resolve()
        new_inspections[ref] = inspection
        new = _new_descriptor(old, inspection, package_id)
        old_rate = _rate(old["logicalSourceBounds"]["frameRate"])
        origin = old["sourceFrameMap"]["packageFrameZeroLogicalFrame"]
        new["occurrenceSourceInFrame"] = _nearest_frame(
            old["occurrenceSourceInFrame"], old_rate, origin
        )
        old_range = old.get("selectedSourceRange")
        if old_range is not None:
            new["selectedSourceRange"] = _mapped_range(old_range, old_rate, origin)
        if new["occurrenceSourceInFrame"] >= len(inspection.video_frames):
            raise ValueError("mapped source inpoint exceeds transcoded source")
        new_range = new.get("selectedSourceRange")
        if new_range is not None and new_range["endFrame"] > len(
            inspection.video_frames
        ):
            raise ValueError("mapped selected range exceeds transcoded source")
        new_descriptors.append(new)

    _update_document(document, descriptors)
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    dependencies["document"]["contentHash"] = document["liveContentHash"]
    dependencies["document"]["textHash"] = sha256_bytes(
        "\n".join(
            block["text"]
            for block in document["activeDraft"]["blocks"]
            if block.get("type") == "narration"
        ).encode()
    )
    dependencies["timeline"]["frameRate"] = RATE_WIRE
    dependencies["occurrenceResolutions"] = new_descriptors
    dependencies["preparedMedia"] = []
    if (
        _evidence_hash(dependencies["narrationBoundaryEvidence"]) != evidence_hash
        or dependencies["document"]["textHash"] != original_text_hash
    ):
        raise ValueError("narration evidence or text changed during picture conversion")
    _write_json(script_path, document)
    _write_json(dependencies_path, dependencies)

    needs = _pinned_bridge("needs", script_path, dependencies_path, node).needs
    dependencies["timeline"]["durationFrames"] = needs["durationFrames"]
    prepared: dict[str, Any] = {}
    preparation_paths: dict[str, Path] = {}
    descriptors_by_payload = {row["payloadId"]: row for row in new_descriptors}
    authorization = PreparationAuthorization(
        reference="issue-520-short-24fps-from-retained-local-assets",
        read_roots=(media_root.resolve(),),
        write_root=prep_root.resolve(),
        tool_hash=tool_hash,
    )
    for requirement in needs["requirements"]:
        descriptor = descriptors_by_payload[requirement["payloadId"]]
        result = prepare_media(
            converted_paths[requirement["mediaReferenceId"]],
            descriptor,
            requirement["requestedRange"],
            RATE_WIRE,
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=None,
            tools=tools,
        )
        descriptor["preparedMediaRequirementKey"] = result.binding["requirementKey"]
        prepared[result.binding["requirementKey"]] = result
        preparation_paths[result.binding["requirementKey"]] = (
            result.receipt_path.resolve()
        )

    dependencies["preparedMedia"] = [prepared[key].binding for key in sorted(prepared)]
    needs_dependencies = copy.deepcopy(dependencies)
    needs_dependencies["preparedMedia"] = []
    needs_dependencies_path = inputs / "media-needs.dependencies.json"
    _write_json(needs_dependencies_path, needs_dependencies)
    _write_json(dependencies_path, dependencies)
    final_needs = _pinned_bridge("needs", script_path, dependencies_path, node).needs

    def plan_without_keys(value: Json) -> Json:
        result = copy.deepcopy(value)
        for row in result.get("requirements", []):
            row.pop("requirementKey", None)
        return result

    if plan_without_keys(needs) != plan_without_keys(final_needs):
        raise ValueError("media needs changed while preparing the 24 fps sources")
    dependencies["timeline"]["durationFrames"] = final_needs["durationFrames"]
    _write_json(dependencies_path, dependencies)
    _write_json(inputs / "media-needs.json", final_needs)
    _write_json(
        inputs / "preparation-paths.json",
        {k: str(v) for k, v in preparation_paths.items()},
    )

    narration_paths: dict[str, Path] = {}
    for item in source_view["sources"]:
        if item.get("kind") == "audio":
            path = source_root / "package/Media/Narration" / Path(item["path"]).name
            narration_paths[_hash(path)] = _regular(path)
    media_paths: dict[str, Path] = {}
    manifest_bridge = _pinned_bridge("compile", script_path, dependencies_path, node)
    compiled_manifest = manifest_bridge.result["manifest"]
    if len(compiled_manifest.get("events", [])) != 11:
        raise ValueError("24 fps compilation changed the retained 11-event structure")
    for source in compiled_manifest["sources"]:
        source_id = source["id"]
        if isinstance(source.get("narrationAudio"), dict):
            digest = source["narrationAudio"]["audioHash"]
            narration_path = narration_paths.get(digest)
            if narration_path is None:
                raise ValueError(
                    "retained narration WAV does not match measured audio hash"
                )
            media_paths[f"source:{source_id}"] = narration_path
            continue
        ref = source["mediaReferenceId"]
        requirement_key = source["preparationRequirementKey"]
        media_paths[f"source:{source_id}"] = prepared[
            requirement_key
        ].video_path.resolve()
        media_paths[f"original:{source_id}"] = converted_paths[ref]

    placeholder_paths: dict[str, Path] = {}
    resolved_root = source_root / "package/Media/Resolved"
    for path in resolved_root.iterdir():
        if path.is_file() and not path.is_symlink():
            placeholder_paths.setdefault(_hash(path), path.resolve())
    for event in compiled_manifest["events"]:
        if event["kind"] == "placeholder":
            reference = event.get("pictureTreatment", {}).get("reference", {})
            digest = reference.get("contentHash")
            placeholder_path = placeholder_paths.get(digest)
            if placeholder_path is None:
                raise ValueError(
                    "retained placeholder still does not match compiled event"
                )
            media_paths[f"event:{event['eventId']}"] = placeholder_path
        elif event["kind"] == "source_audio":
            raise ValueError(
                "the retained short sample unexpectedly requires source audio"
            )

    _write_json(
        inputs / "media-paths.json", {k: str(v) for k, v in media_paths.items()}
    )
    prep_map = {key: _regular(value) for key, value in preparation_paths.items()}
    print(f"Preparation: {perf_counter() - started:.2f}s", flush=True)
    # This is the same pure compile/package path used by the product command;
    # it performs no Resolve calls.
    cli_check = compile_prepared(
        BuildOptions(
            script=script_path,
            inputs=inputs,
            output=output / "cli-compile-check",
        ),
        bridge=lambda kind, doc, deps: _pinned_bridge(kind, doc, deps, node),
    )
    build_v2_package(
        cli_check.manifest,
        cli_check.report,
        script_path,
        dependencies_path,
        output / "package-validation",
        media_paths=media_paths,
        preparation_paths=prep_map,
    )
    _write_json(
        output / "provenance.json",
        {
            "schemaVersion": "issue-520-short-24fps-preparation/v1",
            "timelineRate": RATE_WIRE,
            "narrationBoundaryEvidenceHash": evidence_hash,
            "narrationTimingBasis": (
                "unchanged measured 48 kHz audio evidence; no frame coordinates"
            ),
            "pictureConversion": {
                "method": (
                    "ffmpeg fps=24 CFR resampling from retained prepared picture media"
                ),
                "sourceInpoint": (
                    "nearest 24 fps frame to the retained source-frame time"
                ),
                "visualOnlyEnd": "rounded up to cover the retained source interval",
            },
            "sourceRateConversions": [
                {
                    "mediaReferenceId": ref,
                    "inputHash": old_inspections[ref].content_hash,
                    "inputRate": wire(old_inspections[ref].rate),
                    "outputHash": new_inspections[ref].content_hash,
                    "outputRate": wire(new_inspections[ref].rate),
                    "outputFrameCount": len(new_inspections[ref].video_frames),
                }
                for ref in sorted(converted_paths)
            ],
        },
    )
    print(f"Prepared short sample: {final_needs['durationFrames']} frames at 24 fps")
    print(f"Script: {script_path.resolve()}")
    print(f"Inputs: {inputs.resolve()}")
    print(f"Offline package validation: {output / 'package-validation'}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--read-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--node", type=Path, default=NODE_DEFAULT)
    args = parser.parse_args()
    try:
        prepare(args.source_root, args.read_root, args.output, args.node)
    except Exception as error:
        parser.exit(2, f"short preparation failed: {error}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
