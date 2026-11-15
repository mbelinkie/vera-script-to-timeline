"""Compose the existing compiler and media preparation for bound Research cuts."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Mapping
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .build_compiler_bridge import invoke_bridge
from .build_stage_receipt import canonical_json
from .generated.contracts.compiler_dependencies_v2_schema import (
    OccurrenceMediaResolutionV2,
)
from .media_preparation import (
    MediaTools,
    PreparationAuthorization,
    identity_hash,
    prepare_media,
)

Json = dict[str, Any]


def prepare_cut_inputs(
    script: Path,
    dependencies: Json,
    cut_sources: Mapping[str, Path],
    preparation_paths: dict[str, str],
    media_root: Path,
    *,
    tools: MediaTools,
    report: Callable[[str], None] = print,
) -> None:
    """Append real prepared bindings; source selection always comes from compiler needs."""
    if not cut_sources:
        return
    descriptors = {
        item["payloadId"]: item for item in dependencies["occurrenceResolutions"]
    }
    with tempfile.TemporaryDirectory(prefix=".needs-", dir=media_root) as attempt:
        plan_input = Path(attempt) / "compiler-dependencies.json"
        plan_input.write_bytes(canonical_json(dependencies))
        result = invoke_bridge("needs", script, plan_input).needs
    root = media_root / "Prepared Clips"
    authorization = PreparationAuthorization(
        "prep-media-project-local",
        (media_root,),
        root,
        identity_hash(tools.fingerprint()),
    )
    prepared = {item["requirementKey"]: item for item in dependencies["preparedMedia"]}
    pending = set(cut_sources)
    for need in result["requirements"]:
        payload_id = need["payloadId"]
        if payload_id not in cut_sources:
            continue
        if need["sourceSufficiency"] != "sufficient" or payload_id not in pending:
            raise ValueError("Research placement has no unique sufficient source range")
        pending.remove(payload_id)
        descriptor = descriptors[payload_id]
        started = monotonic()
        result = prepare_media(
            cut_sources[payload_id],
            cast(OccurrenceMediaResolutionV2, descriptor),
            need["requestedRange"],
            dependencies["timeline"]["frameRate"],
            authorization=authorization,
            video_stream_index=0,
            audio_stream_index=1,
            tools=tools,
        )
        binding = result.binding
        key = binding["requirementKey"]
        descriptor["preparedMediaRequirementKey"] = key
        prepared[key] = binding
        preparation_paths[key] = str(result.receipt_path)
        disposition = "reused" if result.reused else "prepared"
        report(
            f"Research media {descriptor['sourceSnapshot']['snapshotId']}: {disposition} in {monotonic() - started:.2f}s"
        )
    if pending:
        raise ValueError("Compiler did not plan every Research cut")
    dependencies["preparedMedia"] = list(prepared.values())


def read_json_object(path: Path) -> Json:
    from .build_stage_receipt import hash_file

    hash_file(path)
    value = json.loads(path.read_bytes())
    if not isinstance(value, dict):
        raise ValueError(f"{path.name} must contain a JSON object")
    return value
