"""Synthetic, hash-consistent input case for the v2 package boundary tests."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import TYPE_CHECKING, Any

from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash

if TYPE_CHECKING:
    from vera_timeline_agent.v2_package import V2PackageResult

Json = dict[str, Any]
_FIXTURES = {
    "25fps": "visual-only-graphic-still-25fps-default",
    "ntsc": "visual-only-graphic-still-ntsc-default",
}
_SCENARIOS = {
    "root-child-overlay-return": "root-child-overlay-return",
    "intentional-slate": "visual-only-default-25fps",
    "source-audio-quiet": "selected-clip-ntsc",
    "source-audio-full": "selected-clip-ntsc",
    "source-audio-no": "selected-clip-ntsc",
    "source-audio-overlap": "selected-clip-ntsc",
}
_FIXTURE_DIRECTORY = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


def _compiler_hash(value: object) -> str:
    from vera_timeline_agent.v2_package import _compiler_hash as compiler_hash

    return compiler_hash(value)


def _refresh_document_closure(
    document: Json, dependencies: Json, manifest: Json, report: Json
) -> None:
    narration = [
        block["text"]
        for block in document["activeDraft"]["blocks"]
        if block["type"] == "narration"
    ]
    text_hash = _raw_hash("\n".join(narration).encode("utf-8"))
    document["liveContentHash"] = _compiler_hash(
        {key: value for key, value in document.items() if key != "liveContentHash"}
    )
    identity_values = {
        "documentId": document["id"],
        "projectId": document["projectId"],
        "liveHeadSequence": document["liveHeadSequence"],
        "contentHash": document["liveContentHash"],
        "textHash": text_hash,
        "settingsHash": dependencies["authoringDefaults"]["settingsHash"],
    }
    for identity in (
        dependencies["document"],
        manifest["document"],
        report["document"],
    ):
        identity.update(identity_values)
    report["dependenciesHash"] = _compiler_hash(dependencies)
    report["manifest"]["contentHash"] = _compiler_hash(manifest)


def _report_event(event: Json) -> Json:
    return {
        "disposition": "placed",
        "eventId": event["eventId"],
        "kind": event["kind"],
        "message": "Compiled from frozen source bindings.",
        "recordRange": copy.deepcopy(event["recordRange"]),
        "sourceId": event["provenance"]["sourceId"],
        "trackId": event["trackId"],
    }


def _append_report_event(manifest: Json, report: Json, event: Json) -> None:
    manifest["events"].append(event)
    report["eventResults"].append(_report_event(event))
    report["summary"]["eventCount"] = len(manifest["events"])
    report["summary"]["placedCount"] = len(report["eventResults"])
    report["summary"]["placeholderCount"] = sum(
        item["kind"] == "placeholder" for item in manifest["events"]
    )


def _make_child_visual_ready(document: Json, manifest: Json, report: Json) -> None:
    """Make the frozen cutaway slot a source-backed child visual for packaging."""
    child_event = next(
        event
        for event in manifest["events"]
        if event["kind"] == "placeholder" and event["trackRole"] == "child"
    )
    root_event = next(
        event
        for event in manifest["events"]
        if event["kind"] == "primary_visual" and event["trackRole"] == "primary_root"
    )
    root_source_id = root_event["provenance"]["sourceId"]
    root_source = next(
        source for source in manifest["sources"] if source["id"] == root_source_id
    )
    slot_id = child_event["provenance"]["slotId"]
    block = next(
        block
        for block in document["activeDraft"]["blocks"]
        if block["id"] == child_event["provenance"]["blockId"]
    )
    sequence = block["primaryVisualSequence"]
    slot = next(slot for slot in sequence["slots"] if slot["id"] == slot_id)
    payload_id = "00000000-0000-4000-8000-000000000020"
    slot["payload"] = {
        "kind": "visual",
        "payloadId": payload_id,
        "pictureKind": "clip",
        "source": {
            "kind": "media_reference",
            "mediaReferenceId": root_source["mediaReferenceId"],
        },
        "sourceUsage": {"sourceInFrame": 0},
        "audioPolicy": "mute",
        "framingPolicy": "contain",
    }
    record = child_event["recordRange"]
    child_event["kind"] = "primary_visual"
    child_event.pop("pictureTreatment", None)
    child_event["sourceRange"] = {
        "startFrame": 0,
        "endFrame": record["endFrame"] - record["startFrame"],
    }
    child_event["preparationBindingHash"] = root_event["preparationBindingHash"]
    child_event["sourceTimeMapping"] = copy.deepcopy(root_event["sourceTimeMapping"])
    child_event["provenance"].update(
        {
            "payloadId": payload_id,
            "sequenceId": sequence["id"],
            "sourceId": root_source_id,
            "originalSourceHash": root_source["originalHash"],
            "deliveredSourceHash": root_source["deliveredHash"],
        }
    )
    result = next(
        item
        for item in report["eventResults"]
        if item["eventId"] == child_event["eventId"]
    )
    result.update(
        {
            "disposition": "placed",
            "kind": "primary_visual",
            "sourceId": root_source_id,
        }
    )
    report["diagnostics"] = []
    report["manualCompletionItems"] = []
    report["recoveryActions"] = []
    report["summary"].update(
        {
            "diagnosticCount": 0,
            "eventCount": len(manifest["events"]),
            "manualCompletionCount": 0,
            "placedCount": len(manifest["events"]),
            "placeholderCount": 0,
            "recoveryActionCount": 0,
        }
    )


def _configure_source_audio(
    document: Json, dependencies: Json, manifest: Json, report: Json, scenario: str
) -> None:
    policy = (
        "mute"
        if scenario == "source-audio-no"
        else "full"
        if scenario == "source-audio-overlap"
        else scenario.removeprefix("source-audio-")
    )
    document["activeDraft"]["blocks"][0]["payload"]["audioPolicy"] = policy
    audio_events = [
        event for event in manifest["events"] if event["kind"] == "source_audio"
    ]
    if policy == "mute":
        removed_ids = {event["eventId"] for event in audio_events}
        manifest["events"] = [
            event for event in manifest["events"] if event["eventId"] not in removed_ids
        ]
        report["eventResults"] = [
            result
            for result in report["eventResults"]
            if result["eventId"] not in removed_ids
        ]
        report["summary"]["eventCount"] = len(manifest["events"])
        report["summary"]["placedCount"] = len(report["eventResults"])
        return

    gain = -18 if policy == "quiet" else 0
    for event in audio_events:
        event["audio"]["audioPolicy"] = policy
        event["audio"]["gainDb"] = gain
    if scenario == "source-audio-overlap":
        if not audio_events:
            raise ValueError(
                "source-audio-overlap requires an enabled source audio event"
            )
        track_id = "source-audio-duplicate"
        track = {
            "id": track_id,
            "kind": "audio",
            "index": 3,
            "name": "Duplicate source audio",
        }
        dependencies["tracks"].append(track)
        dependencies["roles"]["sourceAudioTrackIds"].append(track_id)
        duplicate = copy.deepcopy(audio_events[0])
        duplicate["eventId"] = "00000000-0000-4000-8000-000000000202"
        duplicate["trackId"] = track_id
        _append_report_event(manifest, report, duplicate)


@dataclass
class PackageCase:
    """Files and explicit byte maps consumed by ``build_v2_package``."""

    manifest_path: Path
    report_path: Path
    document_path: Path
    dependencies_path: Path
    media_paths: dict[str, Path]
    preparation_paths: dict[str, Path]
    project_root: Path

    def build(self) -> V2PackageResult:
        from vera_timeline_agent.v2_package import build_v2_package

        return build_v2_package(
            self.manifest_path,
            self.report_path,
            self.document_path,
            self.dependencies_path,
            self.project_root,
            media_paths=self.media_paths,
            preparation_paths=self.preparation_paths,
        )


def make_package_case(
    tmp_path: Path, *, rate: str = "25fps", scenario: str = "default"
) -> PackageCase:
    """Make a fully synthetic package input without running media tools."""
    audio_scenarios = {
        "source-audio-quiet",
        "source-audio-full",
        "source-audio-no",
        "source-audio-overlap",
    }
    fixture_name = _SCENARIOS.get(scenario)
    if fixture_name is None:
        try:
            fixture_name = _FIXTURES[rate] if scenario == "default" else None
        except KeyError as error:
            raise ValueError(f"unsupported fixture rate {rate!r}") from error
    if fixture_name is None:
        raise ValueError(f"unsupported package scenario {scenario!r}")
    fixture = _FIXTURE_DIRECTORY / fixture_name
    input_data = json.loads(Path(f"{fixture}.input.golden.json").read_text())
    manifest = json.loads(Path(f"{fixture}.manifest.golden.json").read_text())
    report = json.loads(Path(f"{fixture}.report.golden.json").read_text())
    document = copy.deepcopy(input_data["document"])
    dependencies = copy.deepcopy(input_data["dependencies"])
    media_dir = tmp_path / "media"
    media_dir.mkdir(parents=True, exist_ok=True)

    if scenario == "root-child-overlay-return":
        _make_child_visual_ready(document, manifest, report)
    if scenario in audio_scenarios:
        _configure_source_audio(document, dependencies, manifest, report, scenario)

    original_bytes = b"synthetic original media source for issue 177\n"
    original_hash = _raw_hash(original_bytes)
    original_probe: Json = {
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "synthetic",
                "width": 1920,
                "height": 1080,
                "avg_frame_rate": "25/1",
                "time_base": "1/25",
            }
        ],
        "frames": [
            {"pts": frame, "best_effort_timestamp": frame} for frame in range(400)
        ],
    }
    audio_bytes = b"synthetic original 44.1 kHz source audio for issue 177\n"
    audio_hash = _raw_hash(audio_bytes)
    if scenario in audio_scenarios:
        original_probe["streams"].append(
            {
                "codec_type": "audio",
                "codec_name": "synthetic-pcm",
                "sample_rate": "44100",
                "channels": 1,
                "time_base": "1/44100",
            }
        )

    profile = {
        "profileVersion": "synthetic-issue177-profile/v1",
        "video": {"codec": "synthetic", "pixelFormat": "synthetic"},
    }
    policy_record = {
        "policyVersion": "synthetic-issue177-policy/v1",
        "audio": "aligned" if scenario in audio_scenarios else "not_applicable",
    }
    tools = {
        "ffmpeg": {"path": "synthetic-fixture", "version": "not-executed"},
        "ffprobe": {"path": "synthetic-fixture", "version": "not-executed"},
    }
    profile_hash = identity_hash(profile)
    policy_hash = identity_hash(policy_record)
    tool_hash = identity_hash(tools)
    commands: list[list[str]]
    bindings = {
        item["requirementKey"]: item for item in manifest["preparationBindings"]
    }
    dependency_bindings = {
        item["requirementKey"]: item for item in dependencies["preparedMedia"]
    }
    occurrences = {
        item["preparedMediaRequirementKey"]: item
        for item in dependencies["occurrenceResolutions"]
        if item.get("preparedMediaRequirementKey") is not None
    }
    sources_by_requirement = {
        item["preparationRequirementKey"]: item
        for item in manifest["sources"]
        if item.get("preparationRequirementKey") is not None
    }
    preparations: dict[str, Json] = {}
    preparation_paths: dict[str, Path] = {}
    media_paths: dict[str, Path] = {}

    if scenario in audio_scenarios:
        manifest["timeline"]["frameRate"] = {"numerator": 24, "denominator": 1}
        dependencies["timeline"] = copy.deepcopy(manifest["timeline"])
        report["timeline"] = copy.deepcopy(manifest["timeline"])
        for binding in bindings.values():
            binding["targetRate"] = {"numerator": 24, "denominator": 1}
            binding["timeMapping"]["deliveredRate"] = copy.deepcopy(
                binding["targetRate"]
            )
            binding["verification"]["decodedFrameRate"] = copy.deepcopy(
                binding["targetRate"]
            )
            binding["verification"]["videoTimeBase"] = {
                "numerator": 1,
                "denominator": 24,
            }

    for requirement_key, binding in bindings.items():
        source = sources_by_requirement[requirement_key]
        occurrence = occurrences[requirement_key]
        delivered_bytes = f"synthetic prepared media for {source['id']}\n".encode()
        delivered_hash = _raw_hash(delivered_bytes)
        source_probe = copy.deepcopy(original_probe)
        source_frame_map = copy.deepcopy(binding["timeMapping"]["sourceFrameMap"])
        source_rate = source_frame_map["decodedPackageFrameRate"]
        source_probe["streams"][0]["avg_frame_rate"] = (
            f"{source_rate['numerator']}/{source_rate['denominator']}"
        )
        source_probe["streams"][0]["time_base"] = (
            f"{source_rate['denominator']}/{source_rate['numerator']}"
        )
        source_probe["frames"] = [
            {"pts": frame, "best_effort_timestamp": frame}
            for frame in range(source_frame_map["decodedPackageFrameCount"])
        ]
        original_probe_hash = identity_hash(source_probe)
        delivered_rate = binding["targetRate"]
        rate_text = f"{delivered_rate['numerator']}/{delivered_rate['denominator']}"
        decoded_count = binding["verification"]["decodedFrameCount"]
        delivered_probe: Json = {
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "synthetic",
                    "width": 1920,
                    "height": 1080,
                    "avg_frame_rate": rate_text,
                    "time_base": (
                        f"{delivered_rate['denominator']}/{delivered_rate['numerator']}"
                    ),
                }
            ],
            "frames": [
                {"pts": frame, "best_effort_timestamp": frame}
                for frame in range(decoded_count)
            ],
        }
        delivered_probe_hash = identity_hash(delivered_probe)
        binding["originalSource"]["contentHash"] = original_hash
        binding["originalSource"]["probeHash"] = original_probe_hash
        binding["verification"]["deliveredHash"] = delivered_hash
        binding["verification"]["probeHash"] = delivered_probe_hash
        binding["profile"] = {
            "policyHash": policy_hash,
            "profileHash": profile_hash,
            "toolHash": tool_hash,
            "profileVersion": profile["profileVersion"],
        }
        occurrence["sourceSnapshot"]["contentHash"] = original_hash
        occurrence["sourceSnapshot"]["probeHash"] = original_probe_hash
        source_frame_map["probeHash"] = original_probe_hash
        if scenario in audio_scenarios:
            source_frame_map["sourceAudioStreamMappings"] = [
                {
                    "streamIndex": 1,
                    "sampleRate": 44100,
                    "packagePtsOrigin": {"numerator": 0, "denominator": 1},
                    "loggedTimeAtPackageOrigin": {
                        "numerator": 0,
                        "denominator": 1,
                    },
                    "audioHash": audio_hash,
                    "probeHash": original_probe_hash,
                }
            ]
        source_frame_map["descriptorHash"] = identity_hash(
            {"snapshot": occurrence["sourceSnapshot"], "probe": source_probe}
        )
        binding["timeMapping"]["sourceFrameMap"] = copy.deepcopy(source_frame_map)
        mapping = binding["timeMapping"]
        mapping["mappingHash"] = identity_hash(
            {key: value for key, value in mapping.items() if key != "mappingHash"}
        )
        occurrence["sourceFrameMap"] = copy.deepcopy(source_frame_map)
        if scenario in audio_scenarios:
            binding["verification"]["sourceAudio"] = {
                "maxDrift": {"numerator": 0, "denominator": 1},
                "offset": {"numerator": 0, "denominator": 1},
                "sampleRate": 44100,
                "status": "aligned",
            }
        binding["derivation"].update(
            {
                "sourceHash": original_hash,
                "outputHash": delivered_hash,
                "profileHash": profile_hash,
                "toolHash": tool_hash,
                "commandHash": identity_hash(
                    [["synthetic-fixture", "prepare", requirement_key]]
                ),
            }
        )
        source.update(
            {
                "originalHash": original_hash,
                "deliveredHash": delivered_hash,
                "originalProbeHash": original_probe_hash,
                "deliveredProbeHash": delivered_probe_hash,
                "sourceFrameMap": copy.deepcopy(source_frame_map),
                "sourceTimeMapping": copy.deepcopy(mapping),
            }
        )
        for event in manifest["events"]:
            if event["provenance"].get("sourceId") == source["id"]:
                event["preparationBindingHash"] = _compiler_hash(binding)
                event["sourceTimeMapping"] = copy.deepcopy(mapping)
                event["provenance"]["originalSourceHash"] = original_hash
                event["provenance"]["deliveredSourceHash"] = delivered_hash
                if event.get("kind") == "source_audio" and scenario in audio_scenarios:
                    event["audio"]["audioHash"] = audio_hash
                    event["audio"]["sampleRange"] = {
                        "startFrame": 0,
                        "endFrame": 441000,
                    }
                    event["audio"]["streamIndex"] = 1
                    event["provenance"]["originalSourceHash"] = audio_hash
        requirement_result = next(
            item
            for item in report["mediaPreparation"]["requirements"]
            if item["requirementKey"] == requirement_key
        )
        requirement_result.update(
            {
                "bindingHash": _compiler_hash(binding),
                "originalHash": original_hash,
                "deliveredHash": delivered_hash,
            }
        )
        dependency_bindings[requirement_key].clear()
        dependency_bindings[requirement_key].update(copy.deepcopy(binding))

        commands = [["synthetic-fixture", "prepare", requirement_key]]
        source_rate = binding["timeMapping"]["sourceRate"]
        package_start = binding["timeMapping"]["sourceOrigin"]
        package_end = {
            "numerator": (
                package_start["numerator"]
                * binding["requestedRange"]["duration"]["denominator"]
                + binding["requestedRange"]["duration"]["numerator"]
                * package_start["denominator"]
            ),
            "denominator": package_start["denominator"]
            * binding["requestedRange"]["duration"]["denominator"],
        }
        package_start_fraction = Fraction(
            package_start["numerator"], package_start["denominator"]
        )
        package_end_fraction = Fraction(
            package_end["numerator"], package_end["denominator"]
        )
        package_end = {
            "numerator": package_end_fraction.numerator,
            "denominator": package_end_fraction.denominator,
        }
        source_rate_fraction = Fraction(
            source_rate["numerator"], source_rate["denominator"]
        )
        first_source_frame = package_start_fraction * source_rate_fraction
        last_source_frame = package_end_fraction * source_rate_fraction
        first_frame = first_source_frame.numerator // first_source_frame.denominator
        exclusive_frame = -(
            -last_source_frame.numerator // last_source_frame.denominator
        )
        geometry = {
            "packageStart": {
                "numerator": package_start_fraction.numerator,
                "denominator": package_start_fraction.denominator,
            },
            "packageEnd": package_end,
            "requiredExclusiveLogicalFrame": exclusive_frame,
            "sourceCoverSurplus": {"numerator": 0, "denominator": 1},
            "terminalQuantization": {"numerator": 0, "denominator": 1},
            "selectedPackageFrames": list(range(first_frame, exclusive_frame)),
        }
        audio_record: Json | None = None
        if scenario in audio_scenarios:
            audio_probe = {
                "streams": [
                    {
                        "codec_name": "pcm_s24le",
                        "sample_rate": "48000",
                        "channels": 1,
                    }
                ]
            }
            audio_record = {
                "sourceAudioHash": audio_hash,
                "contentHash": _raw_hash(b"synthetic prepared source audio 48000Hz\n"),
                "probe": audio_probe,
                "probeHash": identity_hash(audio_probe),
                "channels": 1,
                "sourcePtsOrigin": {"numerator": 0, "denominator": 1},
                "deliveredTimeAtFirstSample": {"numerator": 0, "denominator": 1},
                "boundaryOffset": {"numerator": 0, "denominator": 1},
                "endpointError": {"numerator": 0, "denominator": 1},
                "decodedSourceTimestampResidual": {"numerator": 0, "denominator": 1},
                "decodedSourceTimestampDrift": {"numerator": 0, "denominator": 1},
                "sourceFirstSample": 0,
                "sourceExclusiveSample": 441000,
                "resampledFirstSample": 0,
                "resampledExclusiveSample": 480000,
                "decodedSamples": 480000,
            }
            binding["verification"]["sourceAudio"] = {
                "maxDrift": {"numerator": 0, "denominator": 1},
                "offset": {"numerator": 0, "denominator": 1},
                "sampleRate": 44100,
                "status": "aligned",
            }
            binding["timeMapping"]["mappingHash"] = identity_hash(
                {
                    key: value
                    for key, value in binding["timeMapping"].items()
                    if key != "mappingHash"
                }
            )

        record = {
            "recordVersion": "authoring-media-preparation/v1",
            "requirementKey": requirement_key,
            "inputs": {
                "mediaReferenceId": occurrence["mediaReferenceId"],
                "sourceSnapshot": copy.deepcopy(occurrence["sourceSnapshot"]),
                "sourceFrameMap": copy.deepcopy(occurrence["sourceFrameMap"]),
                "requestedRange": copy.deepcopy(binding["requestedRange"]),
                "targetRate": copy.deepcopy(binding["targetRate"]),
                "profile": copy.deepcopy(binding["profile"]),
                "videoStreamIndex": 0,
                "audioStreamIndex": 1 if scenario in audio_scenarios else None,
            },
            "binding": copy.deepcopy(binding),
            "sourceProbe": source_probe,
            "deliveredProbe": delivered_probe,
            "tools": tools,
            "profile": profile,
            "policy": policy_record,
            "commands": commands,
            "audio": audio_record,
            "geometry": geometry,
        }
        preparations[requirement_key] = record
        dependencies_binding = dependency_bindings[requirement_key]
        dependencies_binding.clear()
        dependencies_binding.update(copy.deepcopy(binding))
        preparation_path = (
            tmp_path
            / "inputs"
            / "preparation"
            / f"{requirement_key.replace(':', '-')}.json"
        )
        _write_json(preparation_path, record)
        preparation_paths[requirement_key] = preparation_path

        original_path = media_dir / "original.mov"
        if not original_path.exists():
            original_path.write_bytes(original_bytes)
        delivered_path = media_dir / f"prepared-{source['id']}.mov"
        delivered_path.write_bytes(delivered_bytes)
        media_paths[f"source:{source['id']}"] = delivered_path
        media_paths[f"original:{source['id']}"] = original_path

    if scenario in audio_scenarios:
        wav_path = media_dir / "source-audio.wav"
        wav_path.write_bytes(b"synthetic prepared source audio 48000Hz\n")
        audio_event = next(
            (event for event in manifest["events"] if event["kind"] == "source_audio"),
            None,
        )
        if audio_event is not None:
            media_paths[f"event:{audio_event['eventId']}"] = wav_path

    for source in manifest["sources"]:
        narration = source.get("narrationAudio")
        if isinstance(narration, dict):
            narration_bytes = b"synthetic narration audio for issue 177\n"
            narration_hash = _raw_hash(narration_bytes)
            narration["audioHash"] = narration_hash
            narration_path = media_dir / f"narration-{source['id']}.wav"
            narration_path.write_bytes(narration_bytes)
            media_paths[f"source:{source['id']}"] = narration_path
            for event in manifest["events"]:
                if event["provenance"].get("sourceId") == source["id"]:
                    event["provenance"]["originalSourceHash"] = narration_hash
                    event["provenance"]["deliveredSourceHash"] = narration_hash

    if scenario == "intentional-slate":
        from vera_timeline_agent.placeholder_slate import render_placeholder_slate

        placeholder_event = next(
            event for event in manifest["events"] if event["kind"] == "placeholder"
        )
        treatment = placeholder_event["pictureTreatment"]
        slate_path = media_dir / f"slate-{placeholder_event['eventId']}.png"
        slate_path.write_bytes(
            render_placeholder_slate(
                treatment["text"],
                manifest["timeline"]["width"],
                manifest["timeline"]["height"],
            )
        )
        media_paths[f"event:{placeholder_event['eventId']}"] = slate_path

    manifest["tracks"] = copy.deepcopy(dependencies["tracks"])
    manifest["roles"] = copy.deepcopy(dependencies["roles"])
    manifest["authoringDefaults"] = copy.deepcopy(dependencies["authoringDefaults"])
    dependencies["timeline"] = copy.deepcopy(manifest["timeline"])
    report["timeline"] = copy.deepcopy(manifest["timeline"])
    report["dependenciesHash"] = _compiler_hash(dependencies)
    report["manifest"]["contentHash"] = _compiler_hash(manifest)
    _refresh_document_closure(document, dependencies, manifest, report)

    inputs = tmp_path / "inputs"
    document_path = inputs / "script-document.json"
    dependencies_path = inputs / "compiler-dependencies.json"
    manifest_path = inputs / "timeline-manifest.json"
    report_path = inputs / "build-report.json"
    _write_json(document_path, document)
    _write_json(dependencies_path, dependencies)
    _write_json(manifest_path, manifest)
    _write_json(report_path, report)
    return PackageCase(
        manifest_path=manifest_path,
        report_path=report_path,
        document_path=document_path,
        dependencies_path=dependencies_path,
        media_paths=media_paths,
        preparation_paths=preparation_paths,
        project_root=tmp_path / "v2-project",
    )
