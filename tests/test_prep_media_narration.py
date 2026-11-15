from __future__ import annotations

import io
import json
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
)
from vera_timeline_agent.narration.normalize import NormalizationResult, Normalizer
from vera_timeline_agent.narration.service import BlockPlan, NarrationService
from vera_timeline_agent.prep_media_narration import (
    narration_service_config,
    prepare_v2_narration_inputs,
)

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
TOKEN_ID = "20000000-0000-4000-8000-000000000001"
POLICY = "inworld_terms_accepted"


class LocalProvider:
    adapter_version = "local-prep-test/v1"

    def __init__(self) -> None:
        self.calls = 0

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return request.text.encode("utf-8")

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        text_bytes = request.text.encode("utf-8")
        return ProviderResult(
            audio_bytes=b"\x00\x00" * 16000,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    kind="word",
                    time_ms=0,
                    start_byte=0,
                    end_byte=len(text_bytes),
                    start_utf16=0,
                    end_utf16=len(request.text.encode("utf-16-le")) // 2,
                    value=request.text,
                ),
            ),
            provenance={
                "provider": "local",
                "engine": "fixture",
                "voiceVersion": "v1",
            },
            request_ids=("local-test",),
        )


class LocalNormalizer:
    profile_id = "local-prep-normalize/v1"
    tool_fingerprint = "sha256:" + "a" * 64

    @staticmethod
    def _wav() -> bytes:
        target = io.BytesIO()
        with wave.open(target, "wb") as writer:
            writer.setnchannels(1)
            writer.setsampwidth(3)
            writer.setframerate(48000)
            writer.writeframes(b"\x00\x00\x00" * 48000)
        return target.getvalue()

    def normalize_pcm(self, *_args: Any, **_kwargs: Any) -> NormalizationResult:
        return NormalizationResult(
            wav_bytes=self._wav(),
            profile_id=self.profile_id,
            normalizer_version="local-prep-test/v1",
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=48000,
            channels=1,
            sample_format="pcm_s24le",
            duration_samples=48000,
            duration_ms=1000,
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.0,
            loudness_range_lu=0.0,
        )

    def placeholder(self, _block_id: str) -> NormalizationResult:
        return self.normalize_pcm()


def _script(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schemaVersion": "script-document/v2",
                "activeDraft": {
                    "blocks": [
                        {
                            "id": BLOCK_ID,
                            "type": "narration",
                            "state": "active",
                            "orderKey": "a",
                            "version": 1,
                            "text": "Hello",
                            "tokens": [
                                {
                                    "id": TOKEN_ID,
                                    "value": "Hello",
                                    "startOffset": 0,
                                    "endOffset": 5,
                                }
                            ],
                        }
                    ]
                },
            }
        )
    )
    return path


def _service(
    tmp_path: Path, provider: LocalProvider, *, cap: float = 0.1
) -> NarrationService:
    return NarrationService(
        cache=NarrationCache(tmp_path / "project-narration-cache"),
        provider=provider,
        normalizer=cast(Normalizer, LocalNormalizer()),
        config=narration_service_config(
            data_policy_attestation=POLICY,
            max_cost_usd=cap,
        ),
    )


def test_cli_config_defaults_without_building_provider() -> None:
    config = narration_service_config(data_policy_attestation=POLICY)
    assert config.profile.profile_id == "inworld-arthur-tts-2-en-us-v1"
    assert config.settings.rate == "100%"
    assert config.max_cost_usd == 0.0
    assert config.data_policy_attestation == POLICY


def test_uncached_narration_requires_confirmation_policy_and_cost_cap(
    tmp_path: Path,
) -> None:
    script = _script(tmp_path / "script.json")
    provider = LocalProvider()
    service = _service(tmp_path, provider)

    with pytest.raises(NeedsAction, match="explicit provider confirmation"):
        prepare_v2_narration_inputs(script, service)
    with pytest.raises(NeedsAction, match="differs from service config"):
        prepare_v2_narration_inputs(
            script,
            service,
            confirm_provider_call=True,
            data_policy_attestation="fish_terms_accepted",
            max_cost_usd=0.1,
        )
    with pytest.raises(NeedsAction, match="exceeds the cost ceiling"):
        prepare_v2_narration_inputs(
            script,
            service,
            confirm_provider_call=True,
            data_policy_attestation=POLICY,
            max_cost_usd=0.00001,
        )
    assert provider.calls == 0


def test_prepares_timing_and_prefixed_media_path_then_reuses_cache_offline(
    tmp_path: Path,
) -> None:
    script = _script(tmp_path / "script.json")
    provider = LocalProvider()
    service = _service(tmp_path, provider)
    reports: list[str] = []

    prepared = prepare_v2_narration_inputs(
        script,
        service,
        confirm_provider_call=True,
        data_policy_attestation=POLICY,
        max_cost_usd=0.1,
        report=reports.append,
    )

    assert provider.calls == 1
    assert len(prepared.narration_timing_maps) == 1
    timing = prepared.narration_timing_maps[0]
    assert timing["blockId"] == BLOCK_ID
    assert timing["tokens"][0]["tokenId"] == TOKEN_ID
    assert list(prepared.media_paths) == [f"source:{timing['narrationAssetId']}"]
    audio_path = Path(prepared.media_paths[f"source:{timing['narrationAssetId']}"])
    assert audio_path.is_absolute() and audio_path.is_file()
    assert reports[0].startswith(f"Narration {BLOCK_ID}: generated,")

    reused = prepare_v2_narration_inputs(
        script,
        service,
        data_policy_attestation=POLICY,
        report=reports.append,
    )
    assert provider.calls == 1
    assert reused == prepared
    assert reports[1].startswith(f"Narration {BLOCK_ID}: reused,")


def test_cache_missing_after_planning_cannot_call_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    script = _script(tmp_path / "script.json")
    provider = LocalProvider()
    service = _service(tmp_path, provider)
    plan = service.plan_block

    def planned_cached(block: dict[str, Any]) -> BlockPlan:
        return replace(plan(block), cached=True)

    monkeypatch.setattr(service, "plan_block", planned_cached)
    with pytest.raises(NeedsAction, match="failed or changed"):
        prepare_v2_narration_inputs(script, service)
    assert provider.calls == 0


def test_recorded_boundary_block_is_skipped_without_changing_inputs(
    tmp_path: Path,
) -> None:
    script = _script(tmp_path / "script.json")
    dependency_path = tmp_path / "compiler-dependencies.json"
    existing = {
        "narrationBoundaryEvidence": [{"blockId": BLOCK_ID, "evidence": "recorded"}],
        "narrationTimingMaps": [],
    }
    dependency_path.write_text(json.dumps(existing))
    original_script = script.read_bytes()
    original_dependencies = dependency_path.read_bytes()
    provider = LocalProvider()
    service = _service(tmp_path, provider)
    reports: list[str] = []

    prepared = prepare_v2_narration_inputs(
        script,
        service,
        data_policy_attestation=POLICY,
        skip_block_ids=(BLOCK_ID,),
        report=reports.append,
    )

    assert prepared.narration_timing_maps == []
    assert prepared.media_paths == {}
    assert provider.calls == 0
    assert script.read_bytes() == original_script
    assert dependency_path.read_bytes() == original_dependencies
    assert reports == [f"Narration {BLOCK_ID}: skipped (recorded boundary evidence)"]


def test_service_policy_must_match_profile_even_for_cache_only_use(
    tmp_path: Path,
) -> None:
    script = _script(tmp_path / "script.json")
    provider = LocalProvider()
    service = _service(tmp_path, provider)
    service.config = replace(
        service.config,
        data_policy_attestation="fish_terms_accepted",
    )

    with pytest.raises(NeedsAction, match="matching provider data policy"):
        prepare_v2_narration_inputs(script, service)
    assert provider.calls == 0
