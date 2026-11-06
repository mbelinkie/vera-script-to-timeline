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
from vera_timeline_agent.v2_package import (
    V2PackageError,
    _compiler_hash,
    verify_v2_package,
)

from scripts.issue336_studio_qualify import png

NATIVE = {
    "mode": "native_dynamic_zoom",
    "start": {"focusX": 0.5, "focusY": 0.5, "scale": 1.25},
    "end": {"focusX": 0.53, "focusY": 0.52, "scale": 1.2},
    "easing": "linear",
}


def _authored_png_case(
    root: Path, *, frames: int, motion: dict[str, Any], framing: str
) -> Any:
    case = make_package_case(root, rate="25fps")
    document = json.loads(case.document_path.read_text())
    dependencies = json.loads(case.dependencies_path.read_text())
    manifest = json.loads(case.manifest_path.read_text())
    report = json.loads(case.report_path.read_text())
    receipt_path = next(iter(case.preparation_paths.values()))
    receipt = json.loads(receipt_path.read_text())

    source_path = root / "public-1600x900.png"
    png(source_path, 1600, 900)
    source_hash = "sha256:" + hashlib.sha256(source_path.read_bytes()).hexdigest()
    source_id = manifest["sources"][0]["id"]
    case.media_paths[f"source:{source_id}"] = source_path
    case.media_paths[f"original:{source_id}"] = source_path

    rate = {"numerator": 24, "denominator": 1}
    for record in (dependencies, manifest, report):
        record["timeline"]["frameRate"] = copy.deepcopy(rate)
        record["timeline"]["durationFrames"] = frames
    for record in (dependencies, manifest):
        record["authoringDefaults"]["visualOnlyStillDurationMs"] = frames * 1000 // 24
    document["activeDraft"]["blocks"][0]["payload"]["imageMotion"] = motion
    document["activeDraft"]["blocks"][0]["payload"]["framingPolicy"] = framing
    event = manifest["events"][0]
    event["pictureTreatment"]["imageMotion"] = motion
    event["pictureTreatment"]["framingPolicy"] = framing
    event["recordRange"]["endFrame"] = frames
    report["eventResults"][0]["recordRange"]["endFrame"] = frames

    prep_binding = receipt["binding"]
    prep_binding["mode"] = "verified_reuse"
    prep_binding.pop("derivation")
    prep_binding["artifactLocator"] = "prepared/still.png"
    prep_binding["targetRate"] = copy.deepcopy(rate)
    prep_binding["requestedRange"]["duration"] = {"numerator": 1, "denominator": 24}
    prep_binding["verification"]["decodedFrameCount"] = 1
    prep_binding["verification"]["decodedFrameRate"] = copy.deepcopy(rate)
    prep_binding["verification"]["videoTimeBase"] = {
        "numerator": 1,
        "denominator": 24,
    }

    stream_probe = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "png",
                "width": 1600,
                "height": 900,
                "avg_frame_rate": "24/1",
                "time_base": "1/24",
            }
        ],
        "frames": [{"pts": 0, "best_effort_timestamp": 0, "duration": 1}],
    }
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
    frame_map["packageVideoTimeBase"] = {"numerator": 1, "denominator": 24}
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
    case = _authored_png_case(tmp_path, frames=frames, motion=NATIVE, framing="cover")
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
    # Installed Studio 21.1.1.10 interprets a still UUID ending in decimal
    # digits as a numbered image sequence (observed "[51-74].png"). Both the
    # delivered still and retained original must have distinct nonnumeric
    # suffixes while preserving the independently hashed source bytes.
    assert resolved.stem.endswith("-still")
    assert not resolved.stem[-1].isdigit()
    assert original.name == f"{resolved.stem.removesuffix('-still')}.original.png"
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


def test_real_package_static_none_keeps_contain_without_motion(
    tmp_path: Path,
) -> None:
    case = _authored_png_case(
        tmp_path, frames=48, motion={"mode": "none"}, framing="contain"
    )
    built = case.build()
    assert verify_v2_package(case.project_root).build_id == built.build_id


def test_real_package_refuses_native_contain_before_publish(tmp_path: Path) -> None:
    case = _authored_png_case(tmp_path, frames=48, motion=NATIVE, framing="contain")
    with pytest.raises(V2PackageError, match="no qualified output"):
        case.build()
    assert not case.project_root.exists()
