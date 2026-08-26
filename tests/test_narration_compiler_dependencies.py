from __future__ import annotations

import json
from pathlib import Path

import pytest
from vera_timeline_agent.narration.compiler_dependencies import (
    NarrationDependencyError,
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    canonical_json_bytes,
    sha256_bytes,
)

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
ASSET_ID = "a" * 64
TEXT_HASH = "sha256:" + "b" * 64
AUDIO_HASH = "sha256:" + "c" * 64


def timing_json(*, precision: str = "word_start_with_derived_end") -> bytes:
    return canonical_json_bytes(
        {
            "recordVersion": "provider-timing/v1",
            "precision": precision,
            "marks": [
                {
                    "kind": "word",
                    "time_ms": 0,
                    "start_byte": 0,
                    "end_byte": 4,
                    "start_utf16": 0,
                    "end_utf16": 4,
                    # This deliberately differs from the authored source token:
                    # pronunciation aliases are valid provider evidence.
                    "value": "vair-uh",
                },
                {
                    "kind": "sentence",
                    "time_ms": 0,
                    "start_byte": 0,
                    "end_byte": 11,
                    "start_utf16": 0,
                    "end_utf16": 11,
                    "value": "VERA says hi",
                },
            ],
        }
    )


def asset(
    timing: bytes,
    *,
    status: str = "ready",
    failure_reason: str | None = None,
) -> NarrationAudioAsset:
    return NarrationAudioAsset(
        record_version="narration-audio-asset/v1",
        asset_id=ASSET_ID,
        block_id=BLOCK_ID,
        block_revision=2,
        kind="temp_synthetic",
        status=status,  # type: ignore[arg-type]
        text_hash=TEXT_HASH,
        provider_input_hash=None,
        profile_hash="sha256:" + "d" * 64,
        settings_hash="sha256:" + "e" * 64,
        pronunciation_hash="sha256:" + "f" * 64,
        request_hash="sha256:" + "0" * 64,
        provider="test",
        region="test-region",
        model="test-model",
        voice_id="Test",
        voice_version="v1",
        raw_audio_hash=None,
        raw_timing_hash=sha256_bytes(timing) if status == "ready" else None,
        timing_precision=json.loads(timing)["precision"],
        normalization_profile="test-profile",
        normalization_hash="sha256:" + "1" * 64,
        tool_fingerprint="sha256:" + "2" * 64,
        normalized_audio_hash=AUDIO_HASH,
        duration_samples=96_000,
        duration_ms=2_000,
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
        generated_at="2026-08-26T00:00:00+00:00",
        failure_reason=failure_reason,
    )


def test_maps_only_compiler_relevant_verified_narration_facts() -> None:
    timing = timing_json()

    assert narration_dependency_from_asset(asset(timing), timing) == {
        "blockId": BLOCK_ID,
        "blockRevision": 2,
        "assetId": ASSET_ID,
        "status": "ready",
        "textHash": TEXT_HASH,
        "audioHash": AUDIO_HASH,
        "audio": {
            "locator": "build-assets/narration/clip.wav",
            "durationSamples": 96_000,
            "sampleRate": 48_000,
            "channels": 1,
        },
        "timing": {
            "recordVersion": "provider-timing/v1",
            "contentHash": sha256_bytes(timing),
            "alignmentVersion": "provider-timing/v1",
            "precision": "word_start_with_derived_end",
            "marks": [
                {
                    "kind": "word",
                    "timeMs": 0,
                    "startUtf16": 0,
                    "endUtf16": 4,
                    "value": "vair-uh",
                },
                {
                    "kind": "sentence",
                    "timeMs": 0,
                    "startUtf16": 0,
                    "endUtf16": 11,
                    "value": "VERA says hi",
                },
            ],
        },
    }


def test_serialized_dependency_matches_the_typescript_boundary_fixture() -> None:
    timing = timing_json()
    fixture_path = (
        Path(__file__).parent
        / "data"
        / "slice_1_3"
        / "python-adapter.ready-narration-dependency.json"
    )

    assert narration_dependency_from_asset(asset(timing), timing) == json.loads(
        fixture_path.read_text(encoding="utf-8")
    )


def test_failed_asset_preserves_duration_and_reason_with_unavailable_marks() -> None:
    timing = canonical_json_bytes(
        {"recordVersion": "provider-timing/v1", "precision": "none", "marks": []}
    )

    dependency = narration_dependency_from_asset(
        asset(timing, status="failed", failure_reason="provider: unavailable"), timing
    )

    assert dependency["status"] == "failed"
    assert dependency["failureReason"] == "provider: unavailable"
    assert dependency["audio"] == {
        "locator": "build-assets/narration/clip.wav",
        "durationSamples": 96_000,
        "sampleRate": 48_000,
        "channels": 1,
    }
    assert dependency["timing"]["precision"] == "none"
    assert dependency["timing"]["marks"] == []
    assert dependency["timing"]["contentHash"] == sha256_bytes(timing)


def test_rejects_tampered_timing_and_unsafe_audio_locator() -> None:
    timing = timing_json()

    with pytest.raises(NarrationDependencyError, match="hash differs"):
        narration_dependency_from_asset(asset(timing), timing + b" ")

    unsafe = asset(timing)
    object.__setattr__(unsafe, "locators", {**unsafe.locators, "audio": "../audio.wav"})
    with pytest.raises(NarrationDependencyError, match="project-relative"):
        narration_dependency_from_asset(unsafe, timing)


def test_rejects_a_ready_asset_with_a_failure_reason() -> None:
    timing = timing_json()

    with pytest.raises(
        NarrationDependencyError, match="may not carry a failure reason"
    ):
        narration_dependency_from_asset(
            asset(timing, failure_reason="should not be here"), timing
        )
