"""Compose the existing compiler and media preparation for bound Research cuts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .build_compiler_bridge import invoke_bridge
from .build_stage_receipt import canonical_json, hash_file
from .generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
)
from .media_preparation import (
    POLICY_HASH,
    PROFILE,
    PROFILE_HASH,
    MediaTools,
    PreparationAuthorization,
    PreparedMedia,
    _qualified_tools,
    _reuse,
    prepare_media,
)
from .narration.models import identity_hash

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
