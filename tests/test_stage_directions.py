from __future__ import annotations

import io
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.generated.contracts.script_document_v2_schema import (
    NarrationBlockV2,
)
from vera_timeline_agent.narration import cli
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.compiler_dependencies_v2 import (
    narration_v2_dependency_from_asset,
)
from vera_timeline_agent.narration.configuration import INWORLD_PROFILE_ID, pricing_for
from vera_timeline_agent.narration.measure import (
    MeasurementError,
    _frozen_tokens,
    _self_check,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    canonical_json_bytes,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import NormalizationResult, Normalizer
from vera_timeline_agent.narration.service import (
    NarrationService,
    ServiceConfig,
    voice_profile,
)
from vera_timeline_agent.narration.stage_directions import masked_text, spoken_tokens

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
TEXT = "The 🌍 [softly] waits"


def mixed_block() -> NarrationBlockV2:
    return {
        "type": "narration",
        "id": BLOCK_ID,
        "version": 1,
        "orderKey": "a0",
        "text": TEXT,
        "tokens": [
            {
                "id": "20000000-0000-4000-8000-000000000001",
                "value": "The",
                "startOffset": 0,
                "endOffset": 3,
            },
            {
                "id": "20000000-0000-4000-8000-000000000002",
                "value": "🌍",
                "startOffset": 4,
                "endOffset": 6,
            },
            {
                "id": "20000000-0000-4000-8000-000000000003",
                "value": "softly",
                "startOffset": 8,
                "endOffset": 14,
                "spoken": False,
            },
            {
                "id": "20000000-0000-4000-8000-000000000004",
                "value": "waits",
                "startOffset": 16,
                "endOffset": 21,
            },
        ],
        "overlayEvents": [],
        "timingPolicy": "narration_spine",
        "state": "active",
        "notes": [],
    }


def direction_only_block() -> NarrationBlockV2:
    return {
        "type": "narration",
        "id": "10000000-0000-4000-8000-000000000002",
        "version": 1,
        "orderKey": "a0",
        "text": "[hold skyline]",
        "tokens": [
            {
                "id": "20000000-0000-4000-8000-000000000005",
                "value": "hold skyline",
                "startOffset": 1,
                "endOffset": 13,
                "spoken": False,
            }
        ],
        "overlayEvents": [],
        "timingPolicy": "narration_spine",
        "state": "active",
        "notes": [],
    }


class _FakeProvider:
    adapter_version = "stage-directions-test/v1"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []
        self.prepared_requests: list[SynthesisRequest] = []

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        self.prepared_requests.append(request)
        return request.text.encode("utf-8")

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.requests.append(request)
        return ProviderResult(
            audio_bytes=b"test-pcm",
            audio_format="pcm_s16le",
            sample_rate=48_000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    kind="sentence",
                    time_ms=0,
                    start_byte=0,
                    end_byte=len(request.text.encode("utf-8")),
                    start_utf16=0,
                    end_utf16=len(request.text.encode("utf-16-le")) // 2,
                    value=request.text,
                ),
            ),
            provenance={},
        )


class _FakeNormalizer(Normalizer):
    @property
    def tool_fingerprint(self) -> str:
        return "sha256:" + "4" * 64

    def normalize_pcm(
        self,
        audio: bytes,
        *,
        sample_rate: int,
        channels: int,
        audit_clock: bool = False,
    ) -> NormalizationResult:
        del audio, sample_rate, audit_clock
        return NormalizationResult(
            wav_bytes=b"test-wav",
            profile_id=self.profile_id,
            normalizer_version="stage-directions-test/v1",
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=48_000,
            channels=channels,
            sample_format="s24",
            duration_samples=48_000,
            duration_ms=1_000,
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.5,
            loudness_range_lu=7.0,
        )


def timing_record() -> bytes:
    return canonical_json_bytes(
        {
            "recordVersion": "provider-timing/v1",
            "precision": "word_start_with_derived_end",
            "marks": [
                {
                    "kind": "word",
                    "time_ms": time_ms,
                    "start_utf16": start,
                    "end_utf16": end,
                    "value": value,
                }
                for time_ms, start, end, value in (
                    (0, 0, 3, "The"),
                    (150, 4, 6, "🌍"),
                    (300, 16, 21, "waits"),
                )
            ],
        }
    )


def ready_asset(timing: bytes) -> NarrationAudioAsset:
    return NarrationAudioAsset(
        record_version="narration-audio-asset/v1",
        asset_id="a" * 64,
        block_id=BLOCK_ID,
        block_revision=1,
        kind="temp_synthetic",
        status="ready",
        text_hash=sha256_bytes(TEXT.encode("utf-8")),
        provider_input_hash="sha256:" + "d" * 64,
        profile_hash="sha256:" + "e" * 64,
        settings_hash="sha256:" + "f" * 64,
        pronunciation_hash="sha256:" + "0" * 64,
        request_hash="sha256:" + "1" * 64,
        provider="test",
        region="test-region",
        model="test-model",
        voice_id="Test",
        voice_version="v1",
        raw_audio_hash="sha256:" + "2" * 64,
        raw_timing_hash=sha256_bytes(timing),
        timing_precision="word_start_with_derived_end",
        normalization_profile="test-profile",
        normalization_hash="sha256:" + "3" * 64,
        tool_fingerprint="sha256:" + "4" * 64,
        normalized_audio_hash="sha256:" + "c" * 64,
        duration_samples=48_000,
        duration_ms=1_000,
        sample_rate=48_000,
        channels=1,
        sample_format="s24",
        synthesis_disposition="generated",
        normalization_disposition="generated",
        locators={
            "audio": "build-assets/narration/clip.wav",
            "timing": "cache/timing.json",
            "record": "cache/asset.json",
        },
        generated_at="2026-10-27T00:00:00+00:00",
    )


def test_masks_direction_at_equal_utf16_width_and_service_uses_masked_text() -> None:
    block = mixed_block()
    expected = "The 🌍 " + " " * 8 + " waits"

    masked = masked_text(block)
    request = ServiceConfig().request_for(block)

    assert masked == expected
    assert len(masked.encode("utf-16-le")) == len(TEXT.encode("utf-16-le"))
    assert request.text == expected
    assert request.source_text_hash == sha256_bytes(TEXT.encode("utf-8"))
    assert [token["value"] for token in spoken_tokens(block)] == [
        "The",
        "🌍",
        "waits",
    ]


def test_timing_and_measurement_projections_drop_direction_tokens() -> None:
    block = mixed_block()
    timing = timing_record()

    dependency = narration_v2_dependency_from_asset(ready_asset(timing), timing, block)
    reasons: list[str] = []
    measured_tokens = _frozen_tokens(block, reasons)

    assert [token["quotedText"] for token in dependency["tokens"]] == [
        "The",
        "🌍",
        "waits",
    ]
    assert [token["value"] for token in measured_tokens] == [
        "The",
        "🌍",
        "waits",
    ]
    assert reasons == []


def test_direction_only_block_is_rejected_before_synthesis_request() -> None:
    block = mixed_block()
    block["tokens"] = [
        {
            "id": "20000000-0000-4000-8000-000000000003",
            "value": "softly",
            "startOffset": 8,
            "endOffset": 14,
            "spoken": False,
        }
    ]

    with pytest.raises(ValueError, match="direction-only narration"):
        ServiceConfig().request_for(block)

    with pytest.raises(ValueError, match="direction-only narration"):
        narration_v2_dependency_from_asset(
            ready_asset(timing_record()), timing_record(), block
        )

    reasons: list[str] = []
    assert _frozen_tokens(block, reasons) == []
    assert "direction-only narration" in reasons[0]
    with pytest.raises(MeasurementError, match="at least one spoken token"):
        _self_check(
            {"audio": {"durationSamples": 48_000, "sampleRate": 48_000}, "tokens": []}
        )


def test_process_document_skips_direction_only_row_and_synthesizes_spoken_row(
    tmp_path: Path,
) -> None:
    spoken = mixed_block()
    spoken["orderKey"] = "b0"
    provider = _FakeProvider()
    service = NarrationService(
        cache=NarrationCache(tmp_path / "cache"),
        provider=provider,
        normalizer=_FakeNormalizer(),
        config=ServiceConfig(data_policy_attestation="inworld_terms_accepted"),
    )

    assets = service.process_document(
        {"activeDraft": {"blocks": [direction_only_block(), spoken]}}
    )

    assert [asset.block_id for asset in assets] == [BLOCK_ID]
    assert [request.block_id for request in provider.requests] == [BLOCK_ID]
    assert provider.requests[0].text == masked_text(spoken)
    assert assets[0].status == "ready"


def test_cli_preflight_excludes_direction_only_row_from_cost_and_requests(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = tmp_path / "script.json"
    script.write_text("{}", encoding="utf-8")
    spoken = mixed_block()
    spoken["orderKey"] = "b0"
    document: dict[str, Any] = {
        "activeDraft": {"blocks": [direction_only_block(), spoken]}
    }
    monkeypatch.setattr(
        cli, "_validate_script", lambda _path: (document, "test validator passed")
    )
    provider = _FakeProvider()
    stdout, stderr = io.StringIO(), io.StringIO()
    pricing = pricing_for(voice_profile(INWORLD_PROFILE_ID))

    result = cli.run_cli(
        [
            str(script),
            "--cache",
            str(tmp_path / "cache"),
            "--voice-profile",
            INWORLD_PROFILE_ID,
            "--data-policy",
            "inworld_terms_accepted",
            "--preflight-only",
        ],
        stdout=stdout,
        stderr=stderr,
        provider=provider,
    )

    assert result == cli.CliExit.OK
    assert stderr.getvalue() == ""
    assert "active narration blocks: 1" in stdout.getvalue()
    assert (
        f"estimated maximum charge: ${pricing.estimate(spoken['text']):.6f}"
        in stdout.getvalue()
    )
    assert [request.block_id for request in provider.prepared_requests] == [BLOCK_ID]
    assert provider.requests == []
    assert not (tmp_path / "cache").exists()
