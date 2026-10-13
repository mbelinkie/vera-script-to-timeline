"""Synthetic, hash-consistent input case for the v2 package boundary tests."""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
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
_FIXTURE_DIRECTORY = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"


def _raw_hash(value: bytes) -> str:
    return "sha256:" + hashlib.sha256(value).hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_bytes(value))


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


def make_package_case(tmp_path: Path, *, rate: str = "25fps") -> PackageCase:
    """Make a fully synthetic package input without running media tools."""
    try:
        fixture_name = _FIXTURES[rate]
    except KeyError as error:
        raise ValueError(f"unsupported fixture rate {rate!r}") from error
    fixture = _FIXTURE_DIRECTORY / fixture_name
    input_data = json.loads(Path(f"{fixture}.input.golden.json").read_text())
    manifest = json.loads(Path(f"{fixture}.manifest.golden.json").read_text())
    report = json.loads(Path(f"{fixture}.report.golden.json").read_text())
    document = copy.deepcopy(input_data["document"])
    dependencies = copy.deepcopy(input_data["dependencies"])

    original_bytes = b"synthetic original visual source for issue 177\n"
    delivered_bytes = b"synthetic prepared still source for issue 177\n"
    original_hash = _raw_hash(original_bytes)
    delivered_hash = _raw_hash(delivered_bytes)
    source_probe: Json = {
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
        "frames": [{"pts": 0, "best_effort_timestamp": 0}],
    }
    delivered_probe: Json = copy.deepcopy(source_probe)
    original_probe_hash = identity_hash(source_probe)
    delivered_probe_hash = identity_hash(delivered_probe)

    binding = copy.deepcopy(manifest["preparationBindings"][0])
    requirement_key = binding["requirementKey"]
    profile = {
        "profileVersion": "synthetic-issue177-profile/v1",
        "video": {"codec": "synthetic", "pixelFormat": "synthetic"},
    }
    policy = {
        "policyVersion": "synthetic-issue177-policy/v1",
        "audio": "not_applicable",
    }
    tools = {
        "ffmpeg": {"path": "synthetic-fixture", "version": "not-executed"},
        "ffprobe": {"path": "synthetic-fixture", "version": "not-executed"},
    }
    profile_hash = identity_hash(profile)
    policy_hash = identity_hash(policy)
    tool_hash = identity_hash(tools)
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

    occurrence = dependencies["occurrenceResolutions"][0]
    occurrence["sourceSnapshot"]["contentHash"] = original_hash
    occurrence["sourceSnapshot"]["probeHash"] = original_probe_hash
    source_frame_map = copy.deepcopy(binding["timeMapping"]["sourceFrameMap"])
    source_frame_map["probeHash"] = original_probe_hash
    source_frame_map["descriptorHash"] = identity_hash(
        {"snapshot": occurrence["sourceSnapshot"], "probe": source_probe}
    )
    binding["timeMapping"]["sourceFrameMap"] = source_frame_map
    mapping = binding["timeMapping"]
    mapping["mappingHash"] = identity_hash(
        {key: value for key, value in mapping.items() if key != "mappingHash"}
    )
    occurrence["sourceFrameMap"] = copy.deepcopy(source_frame_map)

    commands = [["synthetic-fixture", "prepare", requirement_key]]
    binding["derivation"].update(
        {
            "sourceHash": original_hash,
            "outputHash": delivered_hash,
            "profileHash": profile_hash,
            "toolHash": tool_hash,
            "commandHash": identity_hash(commands),
        }
    )
    dependencies["preparedMedia"][0] = copy.deepcopy(binding)
    manifest["preparationBindings"][0] = copy.deepcopy(binding)
    dependencies["timeline"] = copy.deepcopy(manifest["timeline"])

    source = manifest["sources"][0]
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
    event = manifest["events"][0]
    event["preparationBindingHash"] = identity_hash(binding)
    event["sourceTimeMapping"] = copy.deepcopy(mapping)
    event["provenance"]["originalSourceHash"] = original_hash
    event["provenance"]["deliveredSourceHash"] = delivered_hash
    result = report["mediaPreparation"]["requirements"][0]
    result.update(
        {
            "bindingHash": identity_hash(binding),
            "originalHash": original_hash,
            "deliveredHash": delivered_hash,
        }
    )
    report["dependenciesHash"] = identity_hash(dependencies)
    report["manifest"]["contentHash"] = identity_hash(manifest)

    occurrence_input = dependencies["occurrenceResolutions"][0]
    geometry = {
        "packageStart": {"numerator": 0, "denominator": 1},
        "packageEnd": {"numerator": 1, "denominator": 25},
        "requiredExclusiveLogicalFrame": 1,
        "sourceCoverSurplus": {"numerator": 0, "denominator": 1},
        "terminalQuantization": {"numerator": 0, "denominator": 1},
        "selectedPackageFrames": [0],
    }
    preparation = {
        "recordVersion": "authoring-media-preparation/v1",
        "requirementKey": requirement_key,
        "inputs": {
            "mediaReferenceId": occurrence_input["mediaReferenceId"],
            "sourceSnapshot": copy.deepcopy(occurrence_input["sourceSnapshot"]),
            "sourceFrameMap": copy.deepcopy(occurrence_input["sourceFrameMap"]),
            "requestedRange": copy.deepcopy(binding["requestedRange"]),
            "targetRate": copy.deepcopy(binding["targetRate"]),
            "profile": copy.deepcopy(binding["profile"]),
            "videoStreamIndex": 0,
            "audioStreamIndex": None,
        },
        "binding": copy.deepcopy(binding),
        "sourceProbe": source_probe,
        "deliveredProbe": delivered_probe,
        "tools": tools,
        "profile": profile,
        "policy": policy,
        "commands": commands,
        "audio": None,
        "geometry": geometry,
    }

    root = tmp_path / "v2-project"
    inputs = tmp_path / "inputs"
    media = tmp_path / "media"
    preparation_path = inputs / "preparation" / "receipt.json"
    original_path = media / "original.mov"
    delivered_path = media / "prepared.mov"
    original_path.parent.mkdir(parents=True, exist_ok=True)
    original_path.write_bytes(original_bytes)
    delivered_path.write_bytes(delivered_bytes)
    _write_json(preparation_path, preparation)
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
        media_paths={
            f"source:{source['id']}": delivered_path,
            f"original:{source['id']}": original_path,
        },
        preparation_paths={requirement_key: preparation_path},
        project_root=root,
    )
