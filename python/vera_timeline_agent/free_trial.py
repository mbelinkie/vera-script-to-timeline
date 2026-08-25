"""Deterministic OTIO/FCPXML inputs for the producer-run Resolve Free trial."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
import xml.etree.ElementTree as ET
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path, PurePosixPath
from typing import Any, cast

from .otio_package import (
    MANIFEST_FILENAME,
    PackageBuildError,
    build_otio_package,
    validate_timeline_manifest,
    verify_otio_package,
)

FCPXML_FILENAME = "timeline.fcpxml"
OTIO_INPUT_DIRECTORY = "otio-input"
FCPXML_INPUT_DIRECTORY = "fcpxml-input"
TRIAL_README_FILENAME = "TRIAL_README.md"

JsonObject = dict[str, Any]


@dataclass(frozen=True)
class TrialResult:
    """Published dual-input paths and verified manifest counts."""

    output_dir: Path
    otio_input_dir: Path
    fcpxml_input_dir: Path
    event_count: int
    marker_count: int
    media_count: int


def _canonical_json(value: object) -> bytes:
    return (
        json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode()


def _load_manifest(path: Path) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PackageBuildError(
            f"could not read timeline manifest {path}: {error}"
        ) from error
    if not isinstance(value, dict):
        raise PackageBuildError("timeline manifest must contain one JSON object")
    validate_timeline_manifest(value)
    return cast(JsonObject, value)


def _fraction(frames: int, rate: Mapping[str, int]) -> str:
    seconds = Fraction(frames * rate["denominator"], rate["numerator"])
    return f"{seconds.numerator}/{seconds.denominator}s"


def _frames(value: str, rate: Mapping[str, int]) -> int:
    if not value.endswith("s"):
        raise PackageBuildError(f"invalid FCPXML time value: {value}")
    seconds = Fraction(value[:-1])
    frames = seconds * rate["numerator"] / rate["denominator"]
    if frames.denominator != 1:
        raise PackageBuildError(f"FCPXML time is not frame-aligned: {value}")
    return frames.numerator


def _audio_rate(sample_rate: int) -> str:
    kilohertz = Fraction(sample_rate, 1000)
    if kilohertz.denominator == 1:
        return f"{kilohertz.numerator}k"
    return f"{float(kilohertz):g}k"


def _metadata(parent: ET.Element, values: Mapping[str, object]) -> None:
    metadata = ET.SubElement(parent, "metadata")
    for key, value in values.items():
        ET.SubElement(metadata, "md", key=key, value=str(value))


def _build_fcpxml(manifest: JsonObject) -> bytes:
    timeline = cast(JsonObject, manifest["timeline"])
    rate = cast(dict[str, int], timeline["frameRate"])
    root = ET.Element("fcpxml", version="1.10")
    resources = ET.SubElement(root, "resources")
    ET.SubElement(
        resources,
        "format",
        id="format1",
        name=f"VERA {timeline['width']}x{timeline['height']}",
        frameDuration=_fraction(1, rate),
        width=str(timeline["width"]),
        height=str(timeline["height"]),
    )
    source_ref: dict[str, str] = {}
    for index, source in enumerate(cast(list[JsonObject], manifest["sources"]), 1):
        ref = f"asset{index}"
        source_ref[cast(str, source["id"])] = ref
        attributes = {
            "id": ref,
            "name": PurePosixPath(cast(str, source["path"])).name,
            "src": cast(str, source["path"]),
            "start": "0/1s",
        }
        if "durationFrames" in source:
            attributes["duration"] = _fraction(
                cast(int, source["durationFrames"]), rate
            )
        if source["kind"] in {"video", "still"}:
            attributes.update({"hasVideo": "1", "format": "format1"})
        if source["kind"] == "audio":
            attributes.update(
                {
                    "hasAudio": "1",
                    "audioSources": "1",
                    "audioChannels": str(source["channels"]),
                    "audioRate": _audio_rate(cast(int, source["sampleRate"])),
                }
            )
        asset = ET.SubElement(resources, "asset", attributes)
        _metadata(
            asset,
            {
                "vera.sourceId": source["id"],
                "vera.kind": source["kind"],
                "vera.contentHash": source["contentHash"],
            },
        )

    library = ET.SubElement(root, "library")
    event = ET.SubElement(library, "event", name="VERA Slice 0.3 trial")
    project = ET.SubElement(event, "project", name=f"VERA build {manifest['buildId']}")
    sequence = ET.SubElement(
        project,
        "sequence",
        format="format1",
        duration=_fraction(cast(int, timeline["durationFrames"]), rate),
        tcStart=_fraction(cast(int, timeline["startFrame"]), rate),
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate=_audio_rate(cast(int, timeline["audioSampleRate"])),
    )
    sequence_metadata: dict[str, object] = {
        "vera.manifestId": manifest["id"],
        "vera.buildId": manifest["buildId"],
        "vera.frameRate": f"{rate['numerator']}/{rate['denominator']}",
    }
    tracks = cast(list[JsonObject], manifest["tracks"])
    for position, track in enumerate(tracks, 1):
        sequence_metadata[f"vera.track.{position:03d}"] = json.dumps(
            track, sort_keys=True, separators=(",", ":")
        )
    for position, transition in enumerate(
        cast(list[JsonObject], manifest["transitions"]), 1
    ):
        sequence_metadata[f"vera.hardCut.{position:03d}"] = json.dumps(
            transition, sort_keys=True, separators=(",", ":")
        )
    _metadata(sequence, sequence_metadata)
    spine = ET.SubElement(sequence, "spine")
    gap = ET.SubElement(
        spine,
        "gap",
        name="VERA timeline",
        offset=_fraction(cast(int, timeline["startFrame"]), rate),
        start="0/1s",
        duration=_fraction(cast(int, timeline["durationFrames"]), rate),
    )
    track_by_id = {track["id"]: track for track in tracks}
    track_order = {track["id"]: position for position, track in enumerate(tracks)}
    for item in sorted(
        cast(list[JsonObject], manifest["events"]),
        key=lambda value: (
            value["recordRange"]["startFrame"],
            track_order[value["trackId"]],
            value["id"],
        ),
    ):
        record = cast(JsonObject, item["recordRange"])
        source_range = cast(
            JsonObject,
            item.get(
                "sourceRange",
                {"startFrame": 0, "durationFrames": record["durationFrames"]},
            ),
        )
        track = track_by_id[item["trackId"]]
        lane = cast(int, track["index"])
        if track["kind"] == "audio":
            lane = -lane
        clip = ET.SubElement(
            gap,
            "asset-clip",
            name=cast(str, item["id"]),
            ref=source_ref[cast(str, item["sourceId"])],
            offset=_fraction(cast(int, record["startFrame"]), rate),
            start=_fraction(cast(int, source_range["startFrame"]), rate),
            duration=_fraction(cast(int, record["durationFrames"]), rate),
            lane=str(lane),
        )
        _metadata(
            clip,
            {
                "vera.eventId": item["id"],
                "vera.trackId": item["trackId"],
                "vera.trackKind": item["trackKind"],
            },
        )
    for marker in cast(list[JsonObject], manifest["markers"]):
        marker_element = ET.SubElement(
            gap,
            "marker",
            start=_fraction(cast(int, marker["frame"]), rate),
            value=cast(str, marker["name"]),
            note=cast(str, marker["note"]),
            completed="0",
        )
        _metadata(
            marker_element,
            {"vera.markerId": marker["id"], "vera.color": marker["color"]},
        )
    ET.indent(root, space="  ")
    return cast(
        bytes,
        ET.tostring(
            root, encoding="utf-8", xml_declaration=True, short_empty_elements=True
        )
        + b"\n",
    )


def _md(element: ET.Element) -> dict[str, str]:
    metadata_elements = element.findall("./metadata")
    if len(metadata_elements) > 1:
        raise PackageBuildError(f"FCPXML {element.tag} has duplicate metadata blocks")
    result: dict[str, str] = {}
    for item in element.findall("./metadata/md"):
        key = item.get("key")
        value = item.get("value")
        if key is None or value is None:
            raise PackageBuildError(f"FCPXML {element.tag} metadata is incomplete")
        if key in result:
            raise PackageBuildError(
                f"FCPXML {element.tag} has duplicate metadata key {key!r}"
            )
        result[key] = value
    return result


def _require_child_tags(element: ET.Element, expected: list[str], label: str) -> None:
    actual = [child.tag for child in element]
    if actual != expected:
        raise PackageBuildError(
            f"FCPXML {label} children differ: expected {expected}, got {actual}"
        )


def _verify_fcpxml_semantics(path: Path, manifest: JsonObject) -> None:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as error:
        raise PackageBuildError(f"FCPXML is not parseable: {error}") from error
    if root.tag != "fcpxml" or root.get("version") != "1.10":
        raise PackageBuildError("FCPXML root/version differs from the trial format")
    if root.findall(".//transition"):
        raise PackageBuildError(
            "FCPXML contains a transition; the trial manifest requires hard cuts"
        )
    _require_child_tags(root, ["resources", "library"], "root")
    resources = root.find("./resources")
    library = root.find("./library")
    if resources is None or library is None:
        raise PackageBuildError("FCPXML resources/library hierarchy is incomplete")
    assets = resources.findall("./asset")
    _require_child_tags(resources, ["format", *("asset" for _ in assets)], "resources")
    resource_ids = [resource.get("id") for resource in resources]
    if any(value is None or value == "" for value in resource_ids) or len(
        set(resource_ids)
    ) != len(resource_ids):
        raise PackageBuildError("FCPXML resource IDs are missing or duplicate")
    _require_child_tags(library, ["event"], "library")
    event_element = library.find("./event")
    if event_element is None:
        raise PackageBuildError("FCPXML library has no event")
    _require_child_tags(event_element, ["project"], "event")
    project_element = event_element.find("./project")
    if project_element is None:
        raise PackageBuildError("FCPXML event has no project")
    _require_child_tags(project_element, ["sequence"], "project")
    sequence = root.find("./library/event/project/sequence")
    if sequence is None:
        raise PackageBuildError("FCPXML has no sequence")
    _require_child_tags(sequence, ["metadata", "spine"], "sequence")
    timeline = cast(JsonObject, manifest["timeline"])
    rate = cast(dict[str, int], timeline["frameRate"])
    if (
        _frames(cast(str, sequence.get("duration")), rate) != timeline["durationFrames"]
        or _frames(cast(str, sequence.get("tcStart")), rate) != timeline["startFrame"]
    ):
        raise PackageBuildError("FCPXML timeline range differs from manifest")
    if _md(sequence).get("vera.manifestId") != manifest["id"]:
        raise PackageBuildError("FCPXML manifest identity differs from manifest")
    format_element = root.find("./resources/format")
    if format_element is None or (
        _frames(cast(str, format_element.get("frameDuration")), rate) != 1
        or format_element.get("width") != str(timeline["width"])
        or format_element.get("height") != str(timeline["height"])
        or sequence.get("audioRate")
        != _audio_rate(cast(int, timeline["audioSampleRate"]))
    ):
        raise PackageBuildError("FCPXML delivery settings differ from manifest")
    gap = sequence.find("./spine/gap")
    if gap is None or (
        _frames(cast(str, gap.get("offset")), rate) != timeline["startFrame"]
        or _frames(cast(str, gap.get("duration")), rate) != timeline["durationFrames"]
    ):
        raise PackageBuildError("FCPXML primary storyline differs from manifest")
    spine = sequence.find("./spine")
    if spine is None:
        raise PackageBuildError("FCPXML sequence has no spine")
    _require_child_tags(spine, ["gap"], "spine")
    expected_event_count = len(cast(list[JsonObject], manifest["events"]))
    expected_marker_count = len(cast(list[JsonObject], manifest["markers"]))
    _require_child_tags(
        gap,
        [
            *("asset-clip" for _ in range(expected_event_count)),
            *("marker" for _ in range(expected_marker_count)),
        ],
        "primary gap",
    )
    asset_records: list[tuple[ET.Element, dict[str, str]]] = [
        (asset, _md(asset)) for asset in assets
    ]
    source_ids = [metadata.get("vera.sourceId") for _, metadata in asset_records]
    if any(value is None or value == "" for value in source_ids) or len(
        set(source_ids)
    ) != len(source_ids):
        raise PackageBuildError(
            "FCPXML asset/source identities are missing or duplicate"
        )
    actual_sources = {
        cast(str, metadata.get("vera.sourceId")): {
            "path": asset.get("src"),
            "kind": metadata.get("vera.kind"),
            "contentHash": metadata.get("vera.contentHash"),
        }
        for asset, metadata in asset_records
    }
    expected_sources = {
        source["id"]: {
            "path": source["path"],
            "kind": source["kind"],
            "contentHash": source["contentHash"],
        }
        for source in cast(list[JsonObject], manifest["sources"])
    }
    if actual_sources != expected_sources:
        raise PackageBuildError("FCPXML sources differ from manifest")
    source_id_by_ref = {
        cast(str, asset.get("id")): cast(str, metadata.get("vera.sourceId"))
        for asset, metadata in asset_records
    }
    track_by_id = {
        track["id"]: track for track in cast(list[JsonObject], manifest["tracks"])
    }
    clips = root.findall("./library/event/project/sequence/spine/gap/asset-clip")
    actual_events = {}
    for clip in clips:
        metadata = _md(clip)
        event_id = metadata.get("vera.eventId")
        if not event_id or event_id in actual_events:
            raise PackageBuildError("FCPXML event identities are missing or duplicate")
        source_id = source_id_by_ref.get(cast(str, clip.get("ref")))
        if source_id is None:
            raise PackageBuildError("FCPXML event references an unknown asset")
        lane_value = clip.get("lane")
        if lane_value is None:
            raise PackageBuildError("FCPXML event has no lane")
        try:
            lane = int(lane_value)
        except ValueError as error:
            raise PackageBuildError("FCPXML event lane is not an integer") from error
        actual_events[event_id] = {
            "sourceId": source_id,
            "trackId": metadata.get("vera.trackId"),
            "trackKind": metadata.get("vera.trackKind"),
            "lane": lane,
            "recordStart": _frames(cast(str, clip.get("offset")), rate),
            "sourceStart": _frames(cast(str, clip.get("start")), rate),
            "duration": _frames(cast(str, clip.get("duration")), rate),
        }
    expected_events = {}
    for item in cast(list[JsonObject], manifest["events"]):
        record = item["recordRange"]
        source_range = item.get("sourceRange", {"startFrame": 0})
        track = track_by_id[item["trackId"]]
        lane = track["index"] if track["kind"] != "audio" else -track["index"]
        expected_events[item["id"]] = {
            "sourceId": item["sourceId"],
            "trackId": item["trackId"],
            "trackKind": item["trackKind"],
            "lane": lane,
            "recordStart": record["startFrame"],
            "sourceStart": source_range["startFrame"],
            "duration": record["durationFrames"],
        }
    if actual_events != expected_events:
        raise PackageBuildError("FCPXML events differ from manifest")
    sequence_metadata = _md(sequence)
    actual_tracks = [
        json.loads(value)
        for key, value in sorted(sequence_metadata.items())
        if key.startswith("vera.track.")
    ]
    if actual_tracks != manifest["tracks"]:
        raise PackageBuildError("FCPXML track metadata differs from manifest")
    actual_hard_cuts = [
        json.loads(value)
        for key, value in sorted(sequence_metadata.items())
        if key.startswith("vera.hardCut.")
    ]
    if actual_hard_cuts != manifest["transitions"]:
        raise PackageBuildError("FCPXML hard cuts differ from manifest")
    markers = root.findall("./library/event/project/sequence/spine/gap/marker")
    marker_ids = [_md(marker).get("vera.markerId") for marker in markers]
    if any(not marker_id for marker_id in marker_ids) or len(set(marker_ids)) != len(
        marker_ids
    ):
        raise PackageBuildError("FCPXML marker identities are missing or duplicate")
    actual_markers = [
        {
            "id": _md(marker).get("vera.markerId"),
            "frame": _frames(cast(str, marker.get("start")), rate),
            "name": marker.get("value"),
            "note": marker.get("note"),
            "color": _md(marker).get("vera.color"),
        }
        for marker in markers
    ]
    expected_markers = [
        {
            "id": marker["id"],
            "frame": marker["frame"],
            "name": marker["name"],
            "note": marker["note"],
            "color": marker["color"],
        }
        for marker in cast(list[JsonObject], manifest["markers"])
    ]
    if actual_markers != expected_markers:
        raise PackageBuildError("FCPXML markers differ from manifest")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_safe_tree(root: Path, label: str) -> None:
    if not root.is_dir() or root.is_symlink():
        raise PackageBuildError(f"{label} root is not a self-contained directory")
    for path in root.rglob("*"):
        relative = path.relative_to(root).as_posix()
        if path.is_symlink():
            raise PackageBuildError(f"{label} contains a symbolic link: {relative}")
        if not path.is_file() and not path.is_dir():
            raise PackageBuildError(
                f"{label} contains an unsupported filesystem entry: {relative}"
            )


def verify_fcpxml_input(input_dir: Path) -> tuple[int, int, int]:
    """Verify one FCPXML input is semantic and wholly self-contained."""
    _verify_safe_tree(input_dir, "FCPXML input")
    manifest = _load_manifest(input_dir / MANIFEST_FILENAME)
    _verify_fcpxml_semantics(input_dir / FCPXML_FILENAME, manifest)
    expected = {
        MANIFEST_FILENAME,
        FCPXML_FILENAME,
        *(source["path"] for source in manifest["sources"]),
    }
    actual = {
        path.relative_to(input_dir).as_posix()
        for path in input_dir.rglob("*")
        if path.is_file()
    }
    if actual != expected:
        raise PackageBuildError("FCPXML input inventory differs from manifest")
    for source in manifest["sources"]:
        path = input_dir / cast(str, source["path"])
        if path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1:
            raise PackageBuildError(
                f"FCPXML media is not a self-contained regular file: {path}"
            )
        if f"sha256:{_sha256(path)}" != source["contentHash"]:
            raise PackageBuildError(f"FCPXML media hash mismatch: {source['path']}")
    return len(manifest["events"]), len(manifest["markers"]), len(manifest["sources"])


def _trial_readme() -> bytes:
    return (
        b"# Resolve Free dual-input trial\n\n"
        b"These are verified trial inputs, not observed Resolve results. Follow "
        b"`docs/slice-0.3-resolve-free-trial.md`; manually import "
        b"`otio-input/timeline.otio` and `fcpxml-input/timeline.fcpxml` into "
        b"separate fresh timelines. Do not move either interchange file away "
        b"from its sibling `media/` directory.\n"
    )


def build_free_trial(
    manifest_path: Path, media_root: Path, output_dir: Path
) -> TrialResult:
    """Atomically build verified, separate OTIO and FCPXML trial inputs."""
    manifest = _load_manifest(manifest_path)
    parent = output_dir.parent.resolve()
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=f".{output_dir.name}-", dir=parent
    ) as temporary:
        staged = Path(temporary) / output_dir.name
        staged.mkdir()
        otio_dir = staged / OTIO_INPUT_DIRECTORY
        build_otio_package(manifest_path, media_root, otio_dir)
        fcpxml_dir = staged / FCPXML_INPUT_DIRECTORY
        fcpxml_dir.mkdir()
        (fcpxml_dir / MANIFEST_FILENAME).write_bytes(_canonical_json(manifest))
        (fcpxml_dir / FCPXML_FILENAME).write_bytes(_build_fcpxml(manifest))
        for source in manifest["sources"]:
            relative = PurePosixPath(cast(str, source["path"]))
            destination = fcpxml_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(media_root / relative, destination)
        (staged / TRIAL_README_FILENAME).write_bytes(_trial_readme())
        verify_otio_package(otio_dir)
        counts = verify_fcpxml_input(fcpxml_dir)
        if output_dir.exists():
            if not output_dir.is_dir():
                raise PackageBuildError(
                    f"output already exists and is not a directory: {output_dir}"
                )
            try:
                _verify_safe_tree(output_dir, "existing trial output")
                verify_otio_package(output_dir / OTIO_INPUT_DIRECTORY)
                verify_fcpxml_input(output_dir / FCPXML_INPUT_DIRECTORY)
            except PackageBuildError as error:
                raise PackageBuildError(
                    f"output already exists with different contents or an unsafe "
                    f"tree: {output_dir}"
                ) from error
            existing = {
                path.relative_to(output_dir).as_posix(): path.read_bytes()
                for path in output_dir.rglob("*")
                if path.is_file()
            }
            proposed = {
                path.relative_to(staged).as_posix(): path.read_bytes()
                for path in staged.rglob("*")
                if path.is_file()
            }
            if existing != proposed:
                raise PackageBuildError(
                    f"output already exists with different contents: {output_dir}"
                )
        else:
            os.replace(staged, output_dir)
    verify_otio_package(output_dir / OTIO_INPUT_DIRECTORY)
    counts = verify_fcpxml_input(output_dir / FCPXML_INPUT_DIRECTORY)
    return TrialResult(
        output_dir,
        output_dir / OTIO_INPUT_DIRECTORY,
        output_dir / FCPXML_INPUT_DIRECTORY,
        *counts,
    )


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Generate verified OTIO and FCPXML inputs for the manual "
            "Resolve Free trial."
        )
    )
    value.add_argument("manifest", type=Path)
    value.add_argument("--media-root", required=True, type=Path)
    value.add_argument("--output", required=True, type=Path)
    return value


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parser().parse_args(argv)
    try:
        result = build_free_trial(
            arguments.manifest, arguments.media_root, arguments.output
        )
    except PackageBuildError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(f"Ready verified Resolve Free trial inputs: {result.output_dir}")
    print(
        f"Verified both formats against {result.event_count} events, "
        f"{result.marker_count} marker, and {result.media_count} media files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
