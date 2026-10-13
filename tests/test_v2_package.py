from __future__ import annotations

import copy
import hashlib
import json
from fractions import Fraction
from pathlib import Path
from typing import Any

import opentimelineio as otio  # type: ignore[import-untyped]
import pytest
from issue177_package_fixture import make_package_case
from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.v2_package import (
    BUILD_DIRECTORY,
    OTIO_FILENAME,
    VERIFICATION_FILENAME,
    V2PackageError,
    V2PackageVerification,
    _build_otio,
    _delivery_view,
    _InputArtifact,
    _Preparation,
    _source_audio_range,
    _validate_manifest_semantics,
    _verify_otio,
    verify_v2_package,
)


def test_build_verify_and_exact_retry(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)

    created = case.build()

    assert created.project_root == case.project_root
    assert created.reused is False
    expected_files = {
        "Builds/00000000-0000-4000-8000-000000000003/timeline-manifest.json",
        "Builds/00000000-0000-4000-8000-000000000003/build-report.json",
        "Builds/00000000-0000-4000-8000-000000000003/script-document.json",
        "Builds/00000000-0000-4000-8000-000000000003/compiler-dependencies.json",
        "Builds/00000000-0000-4000-8000-000000000003/delivery-view.json",
        "Builds/00000000-0000-4000-8000-000000000003/timeline.otio",
        "Builds/00000000-0000-4000-8000-000000000003/package-verification.json",
        "Builds/00000000-0000-4000-8000-000000000003/Preparation/receipts/"
        "a8ba8b26cd56f0f2cbb282a939a4326d1434e4ef74ab84df83599a6ec174cc47/receipt.json",
        "Builds/00000000-0000-4000-8000-000000000003/Preparation/original/"
        "876593d6-707a-5bff-8a09-353943515a51.mov",
        "Media/Resolved/876593d6-707a-5bff-8a09-353943515a51.mov",
    }
    verification = verify_v2_package(case.project_root)
    assert verification == V2PackageVerification(
        build_id="00000000-0000-4000-8000-000000000003",
        event_count=1,
        marker_count=0,
        media_count=1,
    )
    package_root = case.project_root / "Builds" / verification.build_id
    receipt = json.loads((package_root / "package-verification.json").read_text())
    assert receipt["schemaVersion"] == "v2-package-verification/v1"
    assert receipt["status"] == "ready_to_import"
    assert set(receipt["fileHashes"]) == expected_files - {
        "Builds/00000000-0000-4000-8000-000000000003/package-verification.json"
    }
    assert len(receipt["sourceHashes"]) == 1
    assert set(receipt["preparations"]) == {"prep:occurrence-1"}

    retried = case.build()

    assert retried.reused is True
    assert verify_v2_package(case.project_root) == verification


def test_build_requires_explicit_media_bytes_to_match_the_manifest(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    delivered = case.media_paths[
        next(key for key in case.media_paths if key.startswith("source:"))
    ]
    delivered.write_bytes(b"different delivered bytes")

    with pytest.raises(V2PackageError, match="media hash mismatch"):
        case.build()

    assert not case.project_root.exists()


def test_verify_refuses_tampered_package_media(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    case.build()
    media = next((case.project_root / "Media" / "Resolved").iterdir())
    media.write_bytes(b"tampered after publication")

    with pytest.raises(V2PackageError, match="file hash mismatch"):
        verify_v2_package(case.project_root)


def test_build_refuses_different_inputs_at_an_existing_build_root(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    case.build()
    case.document_path.write_bytes(case.document_path.read_bytes() + b"\n")

    with pytest.raises(V2PackageError, match="not the same verified package"):
        case.build()


def test_build_rejects_symlinked_supplied_media(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    key = next(key for key in case.media_paths if key.startswith("source:"))
    source = case.media_paths[key]
    link = source.with_name("media-link.mov")
    link.symlink_to(source)
    case.media_paths[key] = link

    with pytest.raises(V2PackageError, match="symbolic link"):
        case.build()


def test_build_round_trips_accepted_24000_over_1001_timeline(tmp_path: Path) -> None:
    case = make_package_case(tmp_path, rate="ntsc")

    created = case.build()
    verified = verify_v2_package(case.project_root)
    package_root = case.project_root / BUILD_DIRECTORY / created.build_id
    view = json.loads((package_root / "delivery-view.json").read_text())

    assert verified.build_id == created.build_id
    assert view["timeline"]["frameRate"] == {"numerator": 24000, "denominator": 1001}


def test_accepted_root_child_overlay_return_otio_round_trip_without_source_audio(
    tmp_path: Path,
) -> None:
    fixture = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
    stem = fixture / "root-child-overlay-return"
    inputs = json.loads(Path(f"{stem}.input.golden.json").read_text())
    manifest = json.loads(Path(f"{stem}.manifest.golden.json").read_text())
    _close_test_mapping_hashes(inputs["dependencies"], manifest)
    event_kinds = {event["kind"] for event in manifest["events"]}

    _validate_manifest_semantics(inputs["document"], inputs["dependencies"], manifest)

    assert manifest["composition"]["topology"] == "primary_root_child_overlay"
    assert manifest["composition"]["returns"]
    assert {"primary_visual", "placeholder", "overlay_visual"} <= event_kinds
    assert "source_audio" not in event_kinds

    prepared = {
        binding["requirementKey"]: _Preparation(
            binding["requirementKey"],
            {"binding": binding, "audio": None},
            b"synthetic preparation receipt",
            "sha256:" + "1" * 64,
            "",
        )
        for binding in manifest["preparationBindings"]
    }
    artifacts = {}
    source_paths = {}
    for source in manifest["sources"]:
        source_id = source["id"]
        if "narrationAudio" in source:
            key = f"source:{source_id}"
            relative = f"Media/Narration/{source_id}.wav"
            source_hash = source["narrationAudio"]["audioHash"]
            media_kind = "audio"
        else:
            key = f"source:{source_id}"
            relative = f"Media/Resolved/{source_id}.mov"
            source_hash = source["deliveredHash"]
            media_kind = "video"
        artifacts[key] = _InputArtifact(
            key, Path("."), relative, source_hash, media_kind
        )
        source_paths[source_id] = relative
    placeholder = next(
        event for event in manifest["events"] if event["kind"] == "placeholder"
    )
    placeholder_id = placeholder["eventId"]
    placeholder_path = f"Media/Resolved/{placeholder_id}.svg"
    placeholder_hash = placeholder["pictureTreatment"]["reference"]["contentHash"]
    artifacts[f"event:{placeholder_id}"] = _InputArtifact(
        f"event:{placeholder_id}",
        Path("."),
        placeholder_path,
        placeholder_hash,
        "still",
    )
    source_paths[placeholder_id] = placeholder_path
    view = _delivery_view(
        manifest,
        inputs["dependencies"],
        prepared,
        artifacts,
        source_paths=source_paths,
        validate=False,
    )
    timeline = _build_otio(view, manifest["id"], manifest["buildId"])
    build_root = tmp_path / "root-child-package" / "Builds" / manifest["buildId"]
    build_root.mkdir(parents=True)
    otio.adapters.write_to_file(timeline, str(build_root / OTIO_FILENAME))

    _verify_otio(build_root, manifest, view)


def test_root_child_overlay_same_track_overlap_is_refused() -> None:
    fixture = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
    stem = fixture / "root-child-overlay-return"
    inputs = json.loads(Path(f"{stem}.input.golden.json").read_text())
    manifest = json.loads(Path(f"{stem}.manifest.golden.json").read_text())
    _close_test_mapping_hashes(inputs["dependencies"], manifest)
    overlay = copy.deepcopy(
        next(event for event in manifest["events"] if event["kind"] == "overlay_visual")
    )
    overlay["eventId"] = "00000000-0000-4000-8000-000000000099"
    manifest["events"].append(overlay)

    with pytest.raises(V2PackageError, match="overlap on video-overlay"):
        _validate_manifest_semantics(
            inputs["document"], inputs["dependencies"], manifest
        )


def test_build_rejects_stale_preparation_inputs(tmp_path: Path) -> None:
    case = make_package_case(tmp_path)
    receipt_path = next(iter(case.preparation_paths.values()))
    receipt = json.loads(receipt_path.read_text())
    receipt["inputs"]["profile"]["profileVersion"] = "stale synthetic profile"
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(V2PackageError, match="input mapping is stale"):
        case.build()

    assert not case.project_root.exists()


@pytest.mark.parametrize(("policy", "gain_db"), [("quiet", -18), ("full", 0)])
def test_delivery_view_maps_44100_source_samples_to_verified_wav(
    policy: str, gain_db: int
) -> None:
    fixture = (
        Path(__file__).parent
        / "data/authoring_v2/issue_173/compiler/selected-clip-ntsc.manifest.golden.json"
    )
    manifest_data = json.loads(fixture.read_text())
    event = copy.deepcopy(
        next(
            event
            for event in manifest_data["events"]
            if event["kind"] == "source_audio"
        )
    )
    event["recordRange"] = {"startFrame": 0, "endFrame": 25}
    event["audio"].update(
        {
            "audioPolicy": policy,
            "gainDb": gain_db,
            "sampleRange": {"startFrame": 44100, "endFrame": 88200},
        }
    )
    event["sourceTimeMapping"]["sourceFrameMap"]["sourceAudioStreamMappings"][0][
        "sampleRate"
    ] = 44100
    binding = {"syntheticBinding": True}
    event["preparationBindingHash"] = identity_hash(binding)
    wav_probe = {
        "streams": [{"codec_name": "pcm_s24le", "sample_rate": "48000", "channels": 1}]
    }
    audio_record = {
        "probe": wav_probe,
        "resampledFirstSample": 48000,
        "decodedSamples": 48000,
    }
    preparation = _Preparation(
        "prep:source-audio", {"binding": binding, "audio": audio_record}, b"", "", ""
    )
    event_id = event["eventId"]
    artifact = _InputArtifact(
        f"event:{event_id}",
        Path("."),
        f"Media/Resolved/{event_id}.wav",
        "sha256:" + "1" * 64,
        "audio",
    )
    manifest = {
        "timeline": {
            "frameRate": {"numerator": 25, "denominator": 1},
            "startFrame": 0,
            "durationFrames": 25,
        },
        "tracks": [
            {
                "id": event["trackId"],
                "index": 1,
                "kind": "audio",
                "name": "Source audio",
            }
        ],
        "sources": [],
        "events": [event],
        "composition": {},
    }

    view = _delivery_view(
        manifest,
        {},
        {preparation.requirement_key: preparation},
        {artifact.key: artifact},
        validate=False,
    )

    assert view["events"][0]["sourceRange"] == {
        "startFrame": 0,
        "durationFrames": 25,
    }
    assert view["events"][0]["gainDb"] == gain_db
    assert view["events"][0]["v2Event"]["audio"]["audioPolicy"] == policy


def test_source_audio_refuses_fractional_timeline_frame_mapping() -> None:
    fixture = (
        Path(__file__).parent
        / "data/authoring_v2/issue_173/compiler/selected-clip-ntsc.manifest.golden.json"
    )
    manifest_data = json.loads(fixture.read_text())
    event = copy.deepcopy(
        next(
            event
            for event in manifest_data["events"]
            if event["kind"] == "source_audio"
        )
    )
    event["recordRange"] = {"startFrame": 0, "endFrame": 24}
    event["audio"]["sampleRange"] = {"startFrame": 44100, "endFrame": 88200}
    event["sourceTimeMapping"]["sourceFrameMap"]["sourceAudioStreamMappings"][0][
        "sampleRate"
    ] = 44100
    preparation = _Preparation(
        "prep:source-audio",
        {
            "audio": {
                "probe": {
                    "streams": [
                        {
                            "codec_name": "pcm_s24le",
                            "sample_rate": "48000",
                            "channels": 1,
                        }
                    ]
                },
                "resampledFirstSample": 48000,
                "decodedSamples": 48000,
            }
        },
        b"",
        "",
        "",
    )

    with pytest.raises(V2PackageError, match="does not map to exact timeline frames"):
        _source_audio_range(event, preparation, Fraction(24000, 1001))


def test_verify_checks_otio_metadata_after_receipt_hash_rebinding(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    created = case.build()
    package_root = case.project_root / BUILD_DIRECTORY / created.build_id
    otio_path = package_root / OTIO_FILENAME
    timeline = otio.adapters.read_from_file(str(otio_path))
    clip = timeline.tracks[0][0]
    clip.metadata["vera"]["v2_event"] = {"tampered": True}
    otio.adapters.write_to_file(timeline, str(otio_path))

    receipt_path = package_root / VERIFICATION_FILENAME
    receipt = json.loads(receipt_path.read_text())
    package_relative_path = (
        Path(BUILD_DIRECTORY) / created.build_id / OTIO_FILENAME
    ).as_posix()
    receipt["fileHashes"][package_relative_path] = (
        "sha256:" + hashlib.sha256(otio_path.read_bytes()).hexdigest()
    )
    receipt_path.write_bytes(canonical_json_bytes(receipt))

    with pytest.raises(
        V2PackageError, match=r"OTIO event .* differs from delivery view"
    ):
        verify_v2_package(case.project_root)


def test_build_rejects_symlinked_output_ancestor_before_creating_files(
    tmp_path: Path,
) -> None:
    case = make_package_case(tmp_path)
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    linked_parent.symlink_to(real_parent, target_is_directory=True)
    case.project_root = linked_parent / "v2-project"

    with pytest.raises(V2PackageError, match="symbolic link"):
        case.build()

    assert list(real_parent.iterdir()) == []


def test_build_preserves_failed_staging_for_inspection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import vera_timeline_agent.v2_package as package_module

    case = make_package_case(tmp_path)

    def fail_after_staging(staging: Path, **kwargs: object) -> None:
        marker = staging / "partial-evidence.txt"
        marker.write_text("synthetic interrupted package build")
        raise V2PackageError("synthetic staging failure")

    monkeypatch.setattr(package_module, "_build_staging", fail_after_staging)

    with pytest.raises(V2PackageError, match="partial package retained at") as error:
        case.build()

    retained = Path(str(error.value).rsplit(" at ", maxsplit=1)[-1])
    assert (retained / "partial-evidence.txt").read_text() == (
        "synthetic interrupted package build"
    )


def _close_test_mapping_hashes(
    dependencies: dict[str, Any], manifest: dict[str, Any]
) -> None:
    """Rebind the accepted topology fixture's historical placeholder hashes."""
    bindings_by_requirement = {}
    for binding in manifest["preparationBindings"]:
        mapping = binding["timeMapping"]
        mapping["mappingHash"] = identity_hash(
            {key: value for key, value in mapping.items() if key != "mappingHash"}
        )
        bindings_by_requirement[binding["requirementKey"]] = binding
    dependencies["preparedMedia"] = copy.deepcopy(manifest["preparationBindings"])

    sources = {source["id"]: source for source in manifest["sources"]}
    for source in sources.values():
        if "narrationAudio" in source:
            continue
        binding = bindings_by_requirement[source["preparationRequirementKey"]]
        source["sourceTimeMapping"] = copy.deepcopy(binding["timeMapping"])
        source["sourceFrameMap"] = copy.deepcopy(
            binding["timeMapping"]["sourceFrameMap"]
        )
    for event in manifest["events"]:
        if event["kind"] not in {"primary_visual", "overlay_visual"}:
            continue
        source = sources[event["provenance"]["sourceId"]]
        binding = bindings_by_requirement[source["preparationRequirementKey"]]
        event["preparationBindingHash"] = identity_hash(binding)
        event["sourceTimeMapping"] = copy.deepcopy(binding["timeMapping"])
