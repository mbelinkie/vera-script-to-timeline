"""Hash-closed authored still packages exercising real image-motion admission.

No monkeypatched qualification or Resolve mock in these package-level tests.
Installed Studio raster acceptance is a separate, mandatory external check.
"""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from issue177_package_fixture import (
    _preparation_geometry,
    _refresh_document_closure,
    make_package_case,
)
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.native_image_motion import native_still_stem
from vera_timeline_agent.v2_package import (
    V2PackageError,
    _compiler_hash,
    verify_v2_package,
)

from scripts.issue336_studio_qualify import png

NATIVE = {
    "mode": "native_dynamic_zoom",
    "start": {"focusX": 0.5, "focusY": 0.5, "scale": 1.05},
    "end": {"focusX": 0.5, "focusY": 0.5, "scale": 1.2},
    "easing": "linear",
}


def _authored_png_case(
    root: Path,
    *,
    frames: int,
    motion: dict[str, Any],
    framing: str,
    hide_bars: bool = False,
    size: tuple[int, int] = (1600, 900),
    frame_rate: tuple[int, int] = (24, 1),
    prepared_image: bool = False,
) -> Any:
    case = make_package_case(root, rate="25fps")
    document = json.loads(case.document_path.read_text())
    dependencies = json.loads(case.dependencies_path.read_text())
    manifest = json.loads(case.manifest_path.read_text())
    report = json.loads(case.report_path.read_text())
    receipt_path = next(iter(case.preparation_paths.values()))
    receipt = json.loads(receipt_path.read_text())

    source_path = root / f"public-{size[0]}x{size[1]}.png"
    png(source_path, *size)
    source_hash = "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
    source_id = manifest["sources"][0]["id"]
    case.media_paths[f"source:{source_id}"] = source_path
    case.media_paths[f"original:{source_id}"] = source_path

    rate = {"numerator": frame_rate[0], "denominator": frame_rate[1]}
    for record in (dependencies, manifest, report):
        record["timeline"]["frameRate"] = copy.deepcopy(rate)
        record["timeline"]["durationFrames"] = frames
    for record in (dependencies, manifest):
        record["authoringDefaults"]["visualOnlyStillDurationMs"] = (
            max(1, round(frames * 1000 * frame_rate[1] / frame_rate[0]))
            if prepared_image
            else frames * 1000 // 24
        )
    document["activeDraft"]["blocks"][0]["payload"]["imageMotion"] = motion
    document["activeDraft"]["blocks"][0]["payload"]["framingPolicy"] = framing
    event = manifest["events"][0]
    if hide_bars:
        for record in (dependencies, manifest):
            record["authoringDefaults"]["hideEncodedBars"] = True
        event["encodedBars"] = {"mode": "keep", "reason": "explicit_framing"}
    event["pictureTreatment"]["imageMotion"] = motion
    event["pictureTreatment"]["framingPolicy"] = framing
    event["recordRange"]["endFrame"] = frames
    report["eventResults"][0]["recordRange"]["endFrame"] = frames

    prep_binding = receipt["binding"]
    prep_binding["mode"] = "verified_reuse"
    prep_binding.pop("derivation")
    prep_binding["artifactLocator"] = "prepared/still.png"
    prep_binding["targetRate"] = copy.deepcopy(rate)
    prep_binding["requestedRange"]["duration"] = {
        "numerator": frame_rate[1],
        "denominator": frame_rate[0],
    }
    prep_binding["verification"]["decodedFrameCount"] = 1
    prep_binding["verification"]["decodedFrameRate"] = copy.deepcopy(rate)
    prep_binding["verification"]["videoTimeBase"] = {
        "numerator": frame_rate[1],
        "denominator": frame_rate[0],
    }

    stream_probe = (
        {
            "kind": "image",
            "demuxer": "image2pipe",
            "codec": "png",
            "width": size[0],
            "height": size[1],
            "frames": 1,
        }
        if prepared_image
        else {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "png",
                    "width": size[0],
                    "height": size[1],
                    "avg_frame_rate": f"{frame_rate[0]}/{frame_rate[1]}",
                    "time_base": f"{frame_rate[1]}/{frame_rate[0]}",
                }
            ],
            "frames": [{"pts": 0, "best_effort_timestamp": 0, "duration": 1}],
        }
    )
    probe_hash = identity_hash(stream_probe)
    prep_binding["originalSource"]["contentHash"] = source_hash
    prep_binding["originalSource"]["probeHash"] = probe_hash
    prep_binding["verification"]["deliveredHash"] = source_hash
    prep_binding["verification"]["probeHash"] = probe_hash
    mapping = prep_binding["timeMapping"]
    mapping["sourceRate"] = copy.deepcopy(rate)
    mapping["deliveredRate"] = copy.deepcopy(rate)

    occurrence = dependencies["occurrenceResolutions"][0]
    occurrence["logicalSourceBounds"]["frameRate"] = copy.deepcopy(rate)
    snapshot = occurrence["sourceSnapshot"]
    snapshot["contentHash"] = source_hash
    snapshot["probeHash"] = probe_hash
    frame_map = mapping["sourceFrameMap"]
    frame_map["decodedPackageFrameRate"] = copy.deepcopy(rate)
    frame_map["packageVideoTimeBase"] = {
        "numerator": frame_rate[1],
        "denominator": frame_rate[0],
    }
    frame_map["probeHash"] = probe_hash
    frame_map["descriptorHash"] = identity_hash(
        {"snapshot": snapshot, "probe": stream_probe}
    )
    mapping["mappingHash"] = identity_hash(
        {key: value for key, value in mapping.items() if key != "mappingHash"}
    )
    occurrence["sourceFrameMap"] = copy.deepcopy(frame_map)

    manifest["preparationBindings"][0] = copy.deepcopy(prep_binding)
    dependencies["preparedMedia"][0] = copy.deepcopy(prep_binding)
    source = manifest["sources"][0]
    source["originalHash"] = source_hash
    source["deliveredHash"] = source_hash
    source["originalProbeHash"] = probe_hash
    source["deliveredProbeHash"] = probe_hash
    source["sourceFrameMap"] = copy.deepcopy(frame_map)
    source["sourceTimeMapping"] = copy.deepcopy(mapping)
    event["preparationBindingHash"] = _compiler_hash(prep_binding)
    event["sourceTimeMapping"] = copy.deepcopy(mapping)
    event["provenance"]["originalSourceHash"] = source_hash
    event["provenance"]["deliveredSourceHash"] = source_hash

    receipt["inputs"]["sourceSnapshot"] = copy.deepcopy(snapshot)
    receipt["inputs"]["sourceFrameMap"] = copy.deepcopy(frame_map)
    receipt["inputs"]["requestedRange"] = copy.deepcopy(prep_binding["requestedRange"])
    receipt["inputs"]["targetRate"] = copy.deepcopy(rate)
    receipt["sourceProbe"] = copy.deepcopy(stream_probe)
    receipt["deliveredProbe"] = copy.deepcopy(stream_probe)
    if prepared_image:
        receipt["inputs"]["stillInterpretation"] = (
            "one_png_frame_held_at_timeline_rate/v1"
        )
        receipt["stillEvidence"] = {
            "version": "one_png_frame_held_at_timeline_rate/v1",
            "sourceProbeHash": probe_hash,
            "strictPng": {
                "sourceHash": source_hash,
                "width": size[0],
                "height": size[1],
                "decodedFrameCount": 1,
            },
        }
    receipt["commands"] = []
    receipt["geometry"] = _preparation_geometry(prep_binding, occurrence)

    report_requirement = report["mediaPreparation"]["requirements"][0]
    report_requirement["status"] = "reused"
    report_requirement["bindingHash"] = event["preparationBindingHash"]
    report_requirement["originalHash"] = source_hash
    report_requirement["deliveredHash"] = source_hash
    _refresh_document_closure(document, dependencies, manifest, report)
    for path, value in (
        (case.document_path, document),
        (case.dependencies_path, dependencies),
        (case.manifest_path, manifest),
        (case.report_path, report),
        (receipt_path, receipt),
    ):
        path.write_bytes(canonical_json_bytes(value))
    return case


@pytest.mark.parametrize("frames", [24, 48, 96, 144])
def test_real_package_qualifies_hash_bound_png_motion_and_rebuild(
    tmp_path: Path, frames: int
) -> None:
    case = _authored_png_case(
        tmp_path,
        frames=frames,
        motion=NATIVE,
        framing="cover",
        prepared_image=True,
    )
    built = case.build()
    assert verify_v2_package(case.project_root).build_id == built.build_id
    # The initial installed-Studio test caught real basename collision:
    # Resolve selected Builds/.../Preparation/original/<id>.png rather than
    # Media/Resolved/<id>.png.  Never publish indistinguishable basenames.
    resolved = next((case.project_root / "Media" / "Resolved").glob("*.png"))
    original = next(
        (
            case.project_root / "Builds" / built.build_id / "Preparation" / "original"
        ).glob("*.png")
    )
    # Installed Studio 21.1.1.10 interprets an interior digit run even
    # when the UUID ends in "-still.png" (observed "[51-74]-still.png").
    # The delivered basename must contain NO decimal digits at all.
    source_id = json.loads(case.manifest_path.read_text())["sources"][0]["id"]
    assert resolved.stem == native_still_stem(source_id)
    assert not any(character.isdigit() for character in resolved.stem)
    assert original.name == f"{source_id}.original.png"
    assert original.read_bytes() == resolved.read_bytes()
    timeline = otio.adapters.read_from_file(
        str(case.project_root / "Builds" / built.build_id / "timeline.otio")
    )
    clips = [
        item
        for track in timeline.tracks
        for item in track
        if isinstance(item, otio.schema.Clip)
    ]
    assert len(clips) == 1
    assert len(clips[0].effects) == 2
    assert clips[0].source_range.duration.value == frames
    assert clips[0].metadata["vera"]["motion_qualification"].startswith("sha256:")


@pytest.mark.parametrize(
    ("size", "frames", "frame_rate"),
    [
        ((4097, 3), 1, (24000, 1001)),
        ((1, 4096), 3, (25, 1)),
        ((8192, 1), 1001, (30, 1)),
        ((1600, 900), 7, (24, 1)),
    ],
)
def test_real_package_admits_prepared_still_hold_extents_and_rates(
    tmp_path: Path,
    size: tuple[int, int],
    frames: int,
    frame_rate: tuple[int, int],
) -> None:
    case = _authored_png_case(
        tmp_path,
        frames=frames,
        motion=NATIVE,
        framing="cover",
        size=size,
        frame_rate=frame_rate,
        prepared_image=True,
    )
    built = case.build()
    manifest = json.loads(case.manifest_path.read_text())
    event = manifest["events"][0]
    source = manifest["sources"][0]
    assert event["recordRange"] == {"startFrame": 0, "endFrame": frames}
    assert event["sourceRange"] == {"startFrame": 0, "endFrame": 1}
    delivered_path = case.media_paths[f"source:{source['id']}"]
    assert source["deliveredHash"] == (
        "sha256:" + hashlib.sha256(delivered_path.read_bytes()).hexdigest()
    )
    assert verify_v2_package(case.project_root).build_id == built.build_id
    timeline = otio.adapters.read_from_file(
        str(case.project_root / "Builds" / built.build_id / "timeline.otio")
    )
    clips = [
        item
        for track in timeline.tracks
        for item in track
        if isinstance(item, otio.schema.Clip)
    ]
    assert len(clips) == 1
    assert clips[0].source_range.start_time.value == 0
    assert clips[0].source_range.duration.value == frames
    assert [effect.metadata["Resolve_OTIO"]["Type"] for effect in clips[0].effects] == [
        59,
        22,
    ]


@pytest.mark.parametrize("hide_bars", [False, True])
def test_real_package_static_none_keeps_contain_without_motion(
    tmp_path: Path,
    hide_bars: bool,
) -> None:
    case = _authored_png_case(
        tmp_path,
        frames=48,
        motion={"mode": "none"},
        framing="contain",
        hide_bars=hide_bars,
        prepared_image=True,
    )
    built = case.build()
    assert verify_v2_package(case.project_root).build_id == built.build_id


def test_real_package_refuses_native_contain_before_publish(tmp_path: Path) -> None:
    case = _authored_png_case(
        tmp_path,
        frames=48,
        motion=NATIVE,
        framing="contain",
        prepared_image=True,
    )
    with pytest.raises(V2PackageError, match="no qualified output"):
        case.build()
    assert not case.project_root.exists()
