"""Authorized/cache-first narration v2 stage, with no speculative paid retries."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from .build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from .build_jobs import (
    BuildJobError,
    NeedsAction,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)
from .build_stage_receipt import canonical_json
from .generated.contracts.compiler_dependencies_v2_schema import (
    NarrationTokenTimingMapV2,
)
from .generated.contracts.script_document_v2_schema import NarrationBlockV2
from .narration.cache import CacheError
from .narration.compiler_dependencies_v2 import narration_v2_dependency_from_asset
from .narration.models import NarrationAudioAsset, sha256_bytes
from .narration.service import NarrationService


@dataclass(frozen=True)
class NarrationAuthorization:
    """Local synthetic or explicit one-job provider consent; default is cache-only."""

    allow_uncached_provider: bool = False
    authorized_project: str | None = None
    authorized_snapshot: str | None = None
    max_estimated_usd: float = 0.0


class NarrationStagePort:
    def __init__(
        self,
        service: NarrationService,
        authorization: NarrationAuthorization | None = None,
    ) -> None:
        self.service = service
        self.authorization = authorization or NarrationAuthorization()

    @staticmethod
    def _block_rows(snapshot: FrozenBuildSnapshot) -> list[dict[str, Any]]:
        try:
            document = json.loads(snapshot.file("document").read_bytes())
            blocks = document["activeDraft"]["blocks"]
        except (ValueError, KeyError, TypeError) as error:
            raise BuildJobError("frozen script lacks v2 narration blocks") from error
        if not isinstance(blocks, list):
            raise BuildJobError("invalid frozen narration block list")
        selected = [
            b
            for b in blocks
            if isinstance(b, dict)
            and b.get("type") == "narration"
            and b.get("state") == "active"
        ]
        selected.sort(key=lambda b: (str(b.get("orderKey", "")), str(b.get("id", ""))))
        return selected

    @staticmethod
    def _paths(
        context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> tuple[Path, Path, Path]:
        directory = snapshot.write_root / context.job_id / context.stage
        return (
            directory / "intent.json",
            directory / "assets.json",
            directory / "timing-maps.json",
        )

    def _check_assets(
        self, context: StageContext, snapshot: FrozenBuildSnapshot, raw: bytes
    ) -> list[NarrationTokenTimingMapV2]:
        try:
            data = json.loads(raw)
            if (
                set(data) != {"schemaVersion", "stageKey", "snapshotSha256", "assets"}
                or data["schemaVersion"] != "vera-build-narration/v1"
            ):
                raise ValueError("unknown narration evidence")
            if (
                data["stageKey"] != context.stage_key
                or data["snapshotSha256"] != snapshot.sha256
            ):
                raise ValueError("narration effect identity changed")
            assets = data["assets"]
            blocks = self._block_rows(snapshot)
            if not isinstance(assets, list) or len(assets) != len(blocks):
                raise ValueError("missing narration blocks")
            maps: list[NarrationTokenTimingMapV2] = []
            for row, block in zip(assets, blocks, strict=True):
                if not isinstance(row, dict) or set(row) != {
                    "blockId",
                    "requestHash",
                    "assetId",
                }:
                    raise ValueError("unexpected narration asset pin")
                if row["blockId"] != block["id"]:
                    raise ValueError("frozen narration block differs")
                plan = self.service.plan_block(block)
                if plan.request_hash != row["requestHash"]:
                    raise ValueError("voice/text request changed")
                cached = self.service.cache.read(
                    "assets", f"{row['blockId']}/{row['assetId']}", "asset.json"
                )
                if (
                    cached is None
                    or "timing.json" not in cached.files
                    or "narration.wav" not in cached.files
                ):
                    raise ValueError("narration asset cache is incomplete")
                saved = cached.metadata.get("asset")
                if (
                    not isinstance(saved, dict)
                    or saved.get("status") != "ready"
                    or saved.get("request_hash") != plan.request_hash
                ):
                    raise ValueError(
                        "failed/placeholder audio cannot satisfy speech stage"
                    )
                asset = NarrationAudioAsset(**saved)
                maps.append(
                    narration_v2_dependency_from_asset(
                        asset,
                        cached.files["timing.json"],
                        cast(NarrationBlockV2, block),
                    )
                )
            return maps
        except (CacheError, KeyError, TypeError, ValueError) as error:
            raise UncertainResult(
                f"narration cache/effect needs inspection: {error}"
            ) from error

    def _recover_ready_cache(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> tuple[bytes, bytes] | None:
        """Rebuild only lost *local* proofs from independently ready cache assets.

        No provider or normalizer is invoked here.  An unfinished/ambiguous
        provider effect remains uncertain and is never retried automatically.
        """
        rows: list[dict[str, Any]] = []
        maps: list[NarrationTokenTimingMapV2] = []
        for block in self._block_rows(snapshot):
            plan = self.service.plan_block(block)
            directory = self.service.cache.root / "assets" / block["id"]
            if not directory.exists():
                return None
            if directory.is_symlink() or not directory.is_dir():
                raise UncertainResult("narration cache asset directory is unsafe")
            matches: list[tuple[dict[str, Any], NarrationTokenTimingMapV2]] = []
            for candidate in directory.iterdir():
                if candidate.name.startswith("."):
                    # An interrupted cache publication is not a completed asset.
                    continue
                if candidate.is_symlink() or not re.fullmatch(
                    r"[0-9a-f]{64}", candidate.name
                ):
                    raise UncertainResult("untrusted narration cache entry")
                try:
                    cached = self.service.cache.read(
                        "assets", f"{block['id']}/{candidate.name}", "asset.json"
                    )
                    if cached is None:
                        continue
                    saved = cached.metadata.get("asset")
                    if not isinstance(saved, dict) or saved.get("status") != "ready":
                        continue
                    asset = NarrationAudioAsset(**saved)
                    if (
                        asset.request_hash != plan.request_hash
                        or asset.block_id != block["id"]
                        or asset.block_revision
                        != self.service._request(block).block_revision
                        or asset.normalization_profile
                        != self.service.normalizer.profile_id
                        or asset.tool_fingerprint
                        != self.service.normalizer.tool_fingerprint
                    ):
                        continue
                    if (
                        sha256_bytes(cached.files["narration.wav"])
                        != asset.normalized_audio_hash
                        or sha256_bytes(cached.files["timing.json"])
                        != asset.raw_timing_hash
                    ):
                        raise UncertainResult("ready narration cache hashes disagree")
                    mapping = narration_v2_dependency_from_asset(
                        asset,
                        cached.files["timing.json"],
                        cast(NarrationBlockV2, block),
                    )
                except (CacheError, KeyError, TypeError, ValueError) as error:
                    raise UncertainResult(
                        f"narration cache cannot independently confirm ready: {error}"
                    ) from error
                matches.append(
                    (
                        {
                            "blockId": asset.block_id,
                            "requestHash": plan.request_hash,
                            "assetId": asset.asset_id,
                        },
                        mapping,
                    )
                )
            if len(matches) != 1:
                return None
            row, mapping = matches[0]
            rows.append(row)
            maps.append(mapping)
        return (
            canonical_json(
                {
                    "schemaVersion": "vera-build-narration/v1",
                    "stageKey": context.stage_key,
                    "snapshotSha256": snapshot.sha256,
                    "assets": rows,
                }
            ),
            canonical_json(maps),
        )

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "generating_speech":
            raise BuildJobError("wrong narration stage")
        intent, record, maps_file = self._paths(context, snapshot)
        if intent.exists():
            expected_intent = canonical_json(
                {
                    "schemaVersion": "vera-build-narration-intent/v1",
                    "stageKey": context.stage_key,
                    "snapshotSha256": snapshot.sha256,
                    "requests": [
                        self.service.plan_block(block).request_hash
                        for block in self._block_rows(snapshot)
                    ],
                }
            )
            if not intent.is_file() or intent.read_bytes() != expected_intent:
                raise BuildJobError("narration intent differs from frozen requests")
            if not record.exists() or not maps_file.exists():
                # This may be a lost response after the provider completed and
                # cached its ready output. Never initiate provider work here.
                recovered = self._recover_ready_cache(context, snapshot)
                if recovered is not None:
                    context.renew_lease()
                    published_record, published_maps = recovered
                    if record.exists() and record.read_bytes() != published_record:
                        raise UncertainResult(
                            "partial narration record conflicts with cache"
                        )
                    if maps_file.exists() and maps_file.read_bytes() != published_maps:
                        raise UncertainResult(
                            "partial narration timing conflicts with cache"
                        )
                    publish_immutable_output(maps_file, published_maps)
                    publish_immutable_output(record, published_record)
        if record.exists() or maps_file.exists():
            if not record.is_file() or not maps_file.is_file():
                return Inspection(
                    EffectState.UNCERTAIN, reason="partial narration artifact"
                )
            rows = self._check_assets(context, snapshot, record.read_bytes())
            if maps_file.read_bytes() != canonical_json(rows):
                return Inspection(
                    EffectState.UNCERTAIN,
                    reason="narration token timing differs from cache",
                )
            return Inspection(
                EffectState.VERIFIED,
                StageEvidence(
                    adapter_id="narration-v2",
                    adapter_version=self.service.provider.adapter_version,
                    inputs={"document": snapshot.file("document")},
                    outputs={"assets": record, "timingMaps": maps_file},
                ),
            )
        if intent.exists():
            return Inspection(
                EffectState.UNCERTAIN,
                reason="narration request started without complete proof",
            )
        return Inspection(EffectState.ABSENT)

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        intent, record, maps_file = self._paths(context, snapshot)
        blocks = self._block_rows(snapshot)
        plans = [self.service.plan_block(block) for block in blocks]
        cost = sum(plan.estimated_cost_usd for plan in plans if not plan.cached)
        if any(not plan.cached for plan in plans):
            permit = self.authorization
            if (
                not permit.allow_uncached_provider
                or permit.authorized_project != snapshot.project_id
                or permit.authorized_snapshot != snapshot.snapshot_id
                or not self.service.config.data_policy_attestation
                or cost > permit.max_estimated_usd
            ):
                raise NeedsAction(
                    "uncached narration needs explicit project/snapshot provider, "
                    "data and cost authorization"
                )
        context.renew_lease()
        publish_immutable_output(
            intent,
            canonical_json(
                {
                    "schemaVersion": "vera-build-narration-intent/v1",
                    "stageKey": context.stage_key,
                    "snapshotSha256": snapshot.sha256,
                    "requests": [plan.request_hash for plan in plans],
                }
            ),
        )
        assets: list[dict[str, Any]] = []
        maps: list[NarrationTokenTimingMapV2] = []
        for block, plan in zip(blocks, plans, strict=True):
            context.renew_lease()
            asset = self.service.process_block(block)
            if asset.status != "ready" or asset.request_hash != plan.request_hash:
                raise NeedsAction(
                    f"narration {block['id']} failed; "
                    "placeholder cannot satisfy a real build"
                )
            cached = self.service.cache.read(
                "assets", f"{asset.block_id}/{asset.asset_id}", "asset.json"
            )
            if cached is None or "timing.json" not in cached.files:
                raise UncertainResult(
                    "provider completed but narration cache lacks timing"
                )
            maps.append(
                narration_v2_dependency_from_asset(
                    asset,
                    cached.files["timing.json"],
                    cast(NarrationBlockV2, block),
                )
            )
            assets.append(
                {
                    "blockId": asset.block_id,
                    "requestHash": plan.request_hash,
                    "assetId": asset.asset_id,
                }
            )
        publish_immutable_output(maps_file, canonical_json(maps))
        publish_immutable_output(
            record,
            canonical_json(
                {
                    "schemaVersion": "vera-build-narration/v1",
                    "stageKey": context.stage_key,
                    "snapshotSha256": snapshot.sha256,
                    "assets": assets,
                }
            ),
        )
