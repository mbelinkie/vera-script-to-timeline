"""Prepare cached narration timing and media-path inputs for a v2 build."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from time import monotonic
from typing import Any, cast

from .build_jobs import BuildJobError, NeedsAction
from .generated.contracts.compiler_dependencies_v2_schema import (
    NarrationTokenTimingMapV2,
)
from .generated.contracts.script_document_v2_schema import NarrationBlockV2
from .narration.cache import CacheError
from .narration.compiler_dependencies_v2 import narration_v2_dependency_from_asset
from .narration.configuration import (
    DEFAULT_PROFILE_ID,
    pricing_for,
    voice_profile,
)
from .narration.models import SynthesisSettings
from .narration.normalize import MediaToolError
from .narration.provider import SpeechProviderError
from .narration.service import BlockPlan, NarrationService, ServiceConfig
from .narration.stage_directions import is_direction_only

_DATA_POLICIES = {
    "aws_polly": {"opt_out_confirmed", "provider_terms_accepted"},
    "fish_audio": {"fish_terms_accepted"},
    "inworld": {"inworld_terms_accepted"},
}


@dataclass(frozen=True)
class PreparedNarrationInputs:
    """New temporary narration inputs; existing dependency evidence is untouched."""

    narration_timing_maps: list[NarrationTokenTimingMapV2]
    media_paths: dict[str, str]


def narration_service_config(
    profile_id: str = DEFAULT_PROFILE_ID,
    *,
    model: str | None = None,
    voice_id: str | None = None,
    voice_version: str | None = None,
    rate: str = "100%",
    data_policy_attestation: str | None = None,
    max_cost_usd: float = 0.0,
) -> ServiceConfig:
    """Build CLI-equivalent service settings without constructing a provider."""

    if not math.isfinite(max_cost_usd) or max_cost_usd < 0:
        raise ValueError("cost ceiling must be finite and nonnegative")
    profile = voice_profile(profile_id)
    profile = replace(
        profile,
        engine=model if model is not None else profile.engine,
        voice_id=voice_id if voice_id is not None else profile.voice_id,
        voice_version=(
            voice_version if voice_version is not None else profile.voice_version
        ),
    )
    pricing = pricing_for(profile)
    if data_policy_attestation not in _DATA_POLICIES.get(profile.provider, set()):
        raise ValueError("provider data policy does not match selected profile")
    return ServiceConfig(
        profile=profile,
        settings=SynthesisSettings(rate=rate),
        data_policy_attestation=data_policy_attestation,
        max_cost_usd=max_cost_usd,
        pricing_policy=pricing,
    )


def _read_blocks(script_path: Path) -> list[dict[str, Any]]:
    if script_path.is_symlink() or not script_path.is_file():
        raise BuildJobError("v2 narration script must be a regular local file")
    try:
        document = json.loads(script_path.read_bytes())
        if (
            not isinstance(document, dict)
            or document.get("schemaVersion") != "script-document/v2"
        ):
            raise ValueError("script must be script-document/v2")
        blocks = document["activeDraft"]["blocks"]
        if not isinstance(blocks, list):
            raise ValueError("active narration blocks must be a list")
    except (
        OSError,
        UnicodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        raise BuildJobError(f"could not read v2 narration script: {error}") from error

    selected: list[dict[str, Any]] = []
    try:
        for block in blocks:
            if (
                not isinstance(block, dict)
                or block.get("type") != "narration"
                or block.get("state") != "active"
                or is_direction_only(block)
            ):
                continue
            if (
                not isinstance(block.get("id"), str)
                or not block["id"]
                or not isinstance(block.get("version"), int)
                or not isinstance(block.get("text"), str)
            ):
                raise ValueError("active narration block identity is incomplete")
            selected.append(block)
    except ValueError as error:
        raise BuildJobError(f"invalid active narration block: {error}") from error
    selected.sort(key=lambda block: (str(block.get("orderKey", "")), block["id"]))
    identifiers = [block["id"] for block in selected]
    if len(identifiers) != len(set(identifiers)):
        raise BuildJobError("active narration block IDs must be unique")
    return selected


def _check_policy(service: NarrationService, attestation: str | None) -> None:
    configured = service.config.data_policy_attestation
    expected = _DATA_POLICIES.get(service.config.profile.provider)
    if expected is None or configured not in expected:
        raise NeedsAction("narration service needs its matching provider data policy")
    if attestation is not None and attestation != configured:
        raise NeedsAction("requested narration data policy differs from service config")


def _authorized_for_provider(
    service: NarrationService,
    *,
    plans: list[BlockPlan],
    confirm_provider_call: bool,
    data_policy_attestation: str | None,
    max_cost_usd: float,
) -> None:
    missing = [plan for plan in plans if not plan.cached]
    if not missing:
        return
    if not confirm_provider_call:
        raise NeedsAction("uncached narration requires explicit provider confirmation")
    _check_policy(service, data_policy_attestation)
    estimate = sum(plan.estimated_cost_usd for plan in missing)
    if not math.isfinite(estimate) or estimate < 0 or estimate > max_cost_usd:
        raise NeedsAction("estimated narration charge exceeds the cost ceiling")
    if service.config.max_cost_usd > max_cost_usd:
        raise NeedsAction(
            "narration per-request ceiling exceeds the confirmed total cost ceiling"
        )
    if any(plan.estimated_cost_usd > service.config.max_cost_usd for plan in missing):
        raise NeedsAction("a narration request exceeds the service per-request ceiling")


def prepare_v2_narration_inputs(
    script_path: Path,
    service: NarrationService,
    *,
    confirm_provider_call: bool = False,
    data_policy_attestation: str | None = None,
    max_cost_usd: float = 0.0,
    skip_block_ids: Iterable[str] = (),
    report: Callable[[str], None] = print,
) -> PreparedNarrationInputs:
    """Build v2 timing maps and package paths from ready cache assets.

    Recorded-boundary evidence is supplied by the caller as skipped block IDs;
    this function returns only temporary maps and never edits the script or
    existing compiler dependencies/media paths.
    """

    if not math.isfinite(max_cost_usd) or max_cost_usd < 0:
        raise BuildJobError("cost ceiling must be finite and nonnegative")
    _check_policy(service, data_policy_attestation)
    blocks = _read_blocks(script_path)
    skipped = set(skip_block_ids)
    if any(not isinstance(block_id, str) or not block_id for block_id in skipped):
        raise BuildJobError("skipped narration block IDs must be nonempty strings")
    active_ids = {block["id"] for block in blocks}
    if not skipped <= active_ids:
        raise BuildJobError("skipped boundary block is not active spoken narration")

    work = [block for block in blocks if block["id"] not in skipped]
    for block_id in sorted(skipped):
        report(f"Narration {block_id}: skipped (recorded boundary evidence)")

    plans: list[BlockPlan] = []
    plan_seconds: list[float] = []
    for block in work:
        started = monotonic()
        try:
            plans.append(service.plan_block(block))
        except (CacheError, MediaToolError, SpeechProviderError, ValueError) as error:
            elapsed = max(0.0, monotonic() - started)
            report(f"Narration {block['id']}: planning failed, {elapsed:.2f}s")
            raise BuildJobError(
                f"could not plan narration block {block['id']}: {error}"
            ) from error
        plan_seconds.append(max(0.0, monotonic() - started))

    _authorized_for_provider(
        service,
        plans=plans,
        confirm_provider_call=confirm_provider_call,
        data_policy_attestation=data_policy_attestation,
        max_cost_usd=max_cost_usd,
    )

    maps: list[NarrationTokenTimingMapV2] = []
    media_paths: dict[str, str] = {}
    for block, plan, planning_seconds in zip(work, plans, plan_seconds, strict=True):
        started = monotonic()
        try:
            asset = service.process_block(block)
            if asset.status != "ready" or asset.request_hash != plan.request_hash:
                raise NeedsAction(
                    f"narration {block['id']} failed or changed; placeholder audio "
                    "is not buildable"
                )
            cached = service.cache.read(
                "assets", f"{asset.block_id}/{asset.asset_id}", "asset.json"
            )
            if cached is None or not {"narration.wav", "timing.json"} <= set(
                cached.files
            ):
                raise NeedsAction("ready narration cache lacks audio or timing")
            timing_map = narration_v2_dependency_from_asset(
                asset,
                cached.files["timing.json"],
                cast(NarrationBlockV2, block),
            )
            narration_asset_id = timing_map["narrationAssetId"]
            media_key = f"source:{narration_asset_id}"
            audio_path = cached.path / "narration.wav"
            if not audio_path.is_file() or audio_path.is_symlink():
                raise NeedsAction("ready narration cache audio path is unsafe")
            if media_key in media_paths:
                raise BuildJobError("duplicate narration source asset ID")
            maps.append(timing_map)
            media_paths[media_key] = str(audio_path)
            elapsed = planning_seconds + max(0.0, monotonic() - started)
            report(
                f"Narration {block['id']}: {asset.synthesis_disposition}, "
                f"{asset.normalization_disposition}, {elapsed:.2f}s"
            )
        except NeedsAction:
            elapsed = planning_seconds + max(0.0, monotonic() - started)
            report(f"Narration {block['id']}: needs action, {elapsed:.2f}s")
            raise
        except (CacheError, MediaToolError, SpeechProviderError, ValueError) as error:
            elapsed = planning_seconds + max(0.0, monotonic() - started)
            report(f"Narration {block['id']}: failed, {elapsed:.2f}s")
            raise BuildJobError(
                f"narration block {block['id']} failed: {error}"
            ) from error

    return PreparedNarrationInputs(maps, media_paths)
