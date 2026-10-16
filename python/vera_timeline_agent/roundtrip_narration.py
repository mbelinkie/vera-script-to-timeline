"""Synthetic injected whole-row handoff; not an omission decision or cloud CLI."""

from __future__ import annotations

import copy
import subprocess
import wave
from collections.abc import Callable
from pathlib import Path

from vera_timeline_agent.narration.cache import CacheError
from vera_timeline_agent.narration.compiler_dependencies import (
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.polly import PollyProvider
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    JsonObject,
    PreparedBuild,
    ProofBuildError,
    _digest,
    _file_hash,
    _operator_bytes,
    _parse,
)

VALIDATOR = ROOT / "packages/contracts/src/script-validator-cli.ts"


def replace_row_narration(
    prior: PreparedBuild,
    revised_path: Path,
    service: NarrationService,
    *,
    proof_root: Path | None = None,
    before_process: Callable[[], None] | None = None,
) -> JsonObject:
    """Replace at most one row dependency using the accepted synthesis service.

    The caller must separately establish and accept the semantic edit. This
    function never treats a revised file as evidence of audible absence. Its
    returned dependency values still need actual canonical serialization,
    compilation, fresh materialization and verified build before promotion.
    """
    if prior.request["evidenceLevel"] != "synthetic_injected" or (
        service.config.profile.provider != "issue144_synthetic"
        or service.config.profile.region != "local-test"
        or isinstance(service.provider, PollyProvider)
    ):
        raise ProofBuildError("only explicitly injected synthetic narration is allowed")
    owner = (proof_root or prior.root).absolute()
    cache_root = service.cache.root
    if (
        not prior.root.is_relative_to(owner)
        or not cache_root.is_relative_to(owner)
        or any(
            component.is_symlink()
            for target in (owner, prior.root, cache_root)
            for component in (target, *target.parents)
        )
    ):
        raise ProofBuildError(
            "narration cache must be inside the local proof directory"
        )
    # Accepted cache payload reads protect their own paths. Its lock opener
    # follows existing links, so guard this small isolated proof cache too.
    for path in cache_root.rglob("*"):
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            raise ProofBuildError("independent narration cache files required")
    prior._assert_current()
    prior._verify_speech()
    raw = _operator_bytes(revised_path)
    document = _parse(raw)
    revised_hash = _digest(raw)
    prior._check_runtime()
    validation = subprocess.run(
        [prior.node, str(VALIDATOR), str(revised_path)],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if validation.returncode == 1:
        raise ProofBuildError("actual script validator refused the revised document")
    if validation.returncode:
        raise ProofBuildError(
            f"script validator execution fault (exit {validation.returncode})"
        )
    ignored = {"activeDraft", "liveHeadSequence", "liveStateVector", "liveContentHash"}
    if {key: value for key, value in document.items() if key not in ignored} != {
        key: value for key, value in prior.document.items() if key not in ignored
    }:
        raise ProofBuildError("project/document identity or metadata changed")
    old_blocks = prior.document["activeDraft"]["blocks"]
    blocks = document["activeDraft"]["blocks"]
    if [(row["id"], row["type"], row["orderKey"]) for row in blocks] != [
        (row["id"], row["type"], row["orderKey"]) for row in old_blocks
    ]:
        raise ProofBuildError("row identity/order/inventory changed")
    changed = []
    for old, row in zip(old_blocks, blocks, strict=True):
        if row["type"] != "narration":
            if row != old:
                raise ProofBuildError("non-narration row changed")
            continue
        if row["state"] != old["state"] or row["timingPolicy"] != old["timingPolicy"]:
            raise ProofBuildError("row state or timing policy changed")
        if row["text"] == old["text"]:
            if row["version"] != old["version"] or row["tokens"] != old["tokens"]:
                raise ProofBuildError(
                    "unchanged wording has altered revision or tokens"
                )
        elif row["version"] != old["version"] + 1 or row["state"] != "active":
            raise ProofBuildError("wording edit requires a new active row revision")
        else:
            changed.append(row)
    if len(changed) > 1:
        raise ProofBuildError("this bounded handoff accepts at most one changed row")
    dependencies = copy.deepcopy(prior.dependencies)
    replacements = []
    for row in changed:
        index = next(
            index
            for index, dep in enumerate(dependencies["narration"])
            if dep["blockId"] == row["id"]
        )
        old_dep = dependencies["narration"][index]
        try:
            if before_process is not None:
                before_process()
            asset = service.process_block(row)
            entry = service.cache.read(
                "assets", f"{row['id']}/{asset.asset_id}", "asset.json"
            )
            synthesis = service.cache.read(
                "synthesis", asset.request_hash[7:], "synthesis.json"
            )
        except CacheError as error:
            raise ProofBuildError("narration cache verification failed") from error
        if (
            asset.status != "ready"
            or entry is None
            or (
                asset.provider != "issue144_synthetic"
                or asset.region != "local-test"
                or asset.block_id != row["id"]
                or asset.block_revision != row["version"]
                or asset.text_hash != _digest(row["text"].encode("utf-8"))
                or asset.normalized_audio_hash == old_dep["audioHash"]
                or asset.timing_precision != "word_start_with_derived_end"
                or not asset.request_ids
            )
        ):
            raise ProofBuildError(
                "new complete row audio/provenance/word timing required"
            )
        if (
            synthesis is None
            or synthesis.metadata.get("provenance", {}).get("provider")
            != "issue144_synthetic"
            or (
                synthesis.metadata.get("provenance", {}).get("region") != "local-test"
                or _digest(synthesis.files["provider-audio.pcm"])
                != asset.raw_audio_hash
                or _digest(synthesis.files["provider-input.ssml"])
                != asset.provider_input_hash
                or synthesis.files["provider-timing.json"] != entry.files["timing.json"]
            )
        ):
            raise ProofBuildError("verified synthetic synthesis provenance required")
        dependency = narration_dependency_from_asset(asset, entry.files["timing.json"])
        # The accepted cache locator describes its own storage. Import packages
        # require a separate Media/ destination; the materialization origin stays
        # bound to the cache bytes below, never to this delivery locator.
        dependency["audio"]["locator"] = f"Media/Narration/{asset.asset_id}.wav"
        words = [
            mark for mark in dependency["timing"]["marks"] if mark["kind"] == "word"
        ]
        if len(words) != len(row["tokens"]) or any(
            (mark["startUtf16"], mark["endUtf16"], mark["value"])
            != (token["startOffset"], token["endOffset"], token["value"])
            for mark, token in zip(words, row["tokens"], strict=True)
        ):
            raise ProofBuildError("replacement word marks do not match revised tokens")
        if any(
            mark["timeMs"] * asset.sample_rate >= asset.duration_samples * 1000
            or (index > 0 and mark["timeMs"] <= words[index - 1]["timeMs"])
            for index, mark in enumerate(words)
        ):
            raise ProofBuildError(
                "replacement word timing is outside the new recording"
            )
        origin = entry.path / "narration.wav"
        if _file_hash(origin) != asset.normalized_audio_hash:
            raise ProofBuildError("generated narration audio hash differs")
        with wave.open(str(origin), "rb") as stream:
            actual = (
                stream.getnchannels(),
                stream.getsampwidth(),
                stream.getframerate(),
                stream.getnframes(),
            )
        if actual != (1, 3, 48000, asset.duration_samples):
            raise ProofBuildError("generated narration must be matching PCM24 mono 48k")
        stored = entry.metadata["asset"]
        for key in (
            "asset_id",
            "block_id",
            "block_revision",
            "text_hash",
            "request_hash",
            "normalized_audio_hash",
            "raw_timing_hash",
            "provider",
            "region",
            "status",
            "timing_precision",
        ):
            if stored.get(key) != asset.as_json()[key]:
                raise ProofBuildError("cached asset record binding differs")
        dependencies["narration"][index] = dependency
        replacements.append(
            {
                "blockId": row["id"],
                "assetId": asset.asset_id,
                "origin": str(origin),
                "audioHash": asset.normalized_audio_hash,
                "assetRecordPath": str(entry.path / "asset.json"),
                "assetRecordHash": _file_hash(entry.path / "asset.json"),
                "timingPath": str(entry.path / "timing.json"),
                "timingHash": _file_hash(entry.path / "timing.json"),
                "requestHash": asset.request_hash,
                "providerAdapter": service.provider.adapter_version,
            }
        )
    prior._assert_current()
    prior._verify_speech()
    if _file_hash(revised_path) != revised_hash:
        raise ProofBuildError("revised document changed during generation")
    return {
        "schemaVersion": "issue-144-row-narration/v1",
        "evidenceLevel": "synthetic_injected",
        "baselineSnapshotId": prior.snapshot_id,
        "revisedDocumentHash": revised_hash,
        "sources": prior.source_hashes,
        "dependencies": dependencies,
        "replacements": replacements,
    }
