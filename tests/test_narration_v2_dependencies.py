from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import cast

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from vera_timeline_agent.generated.contracts.script_document_v2_schema import (
    NarrationBlockV2,
    NarrationToken,
)
from vera_timeline_agent.narration.compiler_dependencies import (
    NarrationDependencyError,
)
from vera_timeline_agent.narration.compiler_dependencies_v2 import (
    narration_v2_dependency_from_asset,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    canonical_json_bytes,
    sha256_bytes,
)

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
ASSET_ID = "a" * 64
AUDIO_HASH = "sha256:" + "c" * 64
TEXT = "go, can't e\u0301lan 🌍 go?"
TOKENS: list[NarrationToken] = [
    {
        "id": "20000000-0000-4000-8000-000000000001",
        "value": "go",
        "startOffset": 0,
        "endOffset": 2,
    },
    {
        "id": "20000000-0000-4000-8000-000000000002",
        "value": "can't",
        "startOffset": 4,
        "endOffset": 9,
    },
    {
        "id": "20000000-0000-4000-8000-000000000003",
        "value": "e\u0301lan",
        "startOffset": 10,
        "endOffset": 15,
    },
    {
        "id": "20000000-0000-4000-8000-000000000004",
        "value": "🌍",
        "startOffset": 16,
        "endOffset": 18,
    },
    {
        "id": "20000000-0000-4000-8000-000000000005",
        "value": "go",
        "startOffset": 19,
        "endOffset": 21,
    },
]


def timing_json(*, sentence_only: bool = False, last_time_ms: int = 1450) -> bytes:
    if sentence_only:
        marks = [
            {
                "kind": "sentence",
                "time_ms": 0,
                "start_utf16": 0,
                "end_utf16": 22,
                "value": TEXT,
            }
        ]
        precision = "sentence_start"
    else:
        marks = [
            {
                "kind": "word",
                "time_ms": time_ms,
                "start_utf16": start,
                "end_utf16": end,
                # Provider aliases are not the authored token quote.
                "value": f"provider-mark-{index}",
            }
            for index, (time_ms, start, end) in enumerate(
                [
                    (0, 0, 2),
                    (300, 4, 9),
                    (725, 10, 15),
                    (1100, 16, 18),
                    (last_time_ms, 19, 21),
                ]
            )
        ]
        precision = "word_start_with_derived_end"
    return canonical_json_bytes(
        {"recordVersion": "provider-timing/v1", "precision": precision, "marks": marks}
    )


def asset(timing: bytes, *, sentence_only: bool = False) -> NarrationAudioAsset:
    return NarrationAudioAsset(
        record_version="narration-audio-asset/v1",
        asset_id=ASSET_ID,
        block_id=BLOCK_ID,
        block_revision=2,
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
        timing_precision=(
            "sentence_start" if sentence_only else "word_start_with_derived_end"
        ),
        normalization_profile="test-profile",
        normalization_hash="sha256:" + "3" * 64,
        tool_fingerprint="sha256:" + "4" * 64,
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
        generated_at="2026-10-09T00:00:00+00:00",
    )


def block() -> NarrationBlockV2:
    return {
        "type": "narration",
        "id": BLOCK_ID,
        "orderKey": "a0",
        "text": TEXT,
        "tokens": [cast(NarrationToken, dict(token)) for token in TOKENS],
        "overlayEvents": [],
        "timingPolicy": "narration_spine",
        "state": "active",
        "notes": [],
        "version": 2,
    }


def map_schema_validator() -> Draft202012Validator:
    root = Path(__file__).parent.parent
    dependency_schema = json.loads(
        (root / "contracts" / "compiler-dependencies-v2.schema.json").read_text()
    )
    document_schema = json.loads(
        (root / "contracts" / "script-document-v2.schema.json").read_text()
    )
    dependency_id = dependency_schema["$id"]
    registry = Registry().with_resources(
        [
            (dependency_id, Resource.from_contents(dependency_schema)),
            (document_schema["$id"], Resource.from_contents(document_schema)),
        ]
    )
    wrapper = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://vera.test/narration-map-wrapper.schema.json",
        "$ref": f"{dependency_id}#/$defs/NarrationTokenTimingMapV2",
    }
    return Draft202012Validator(
        wrapper,
        registry=registry,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def test_projects_exact_frozen_tokens_to_schema_valid_v2_timing_golden() -> None:
    timing = timing_json()
    result = narration_v2_dependency_from_asset(asset(timing), timing, block())
    golden = (
        Path(__file__).parent
        / "data"
        / "authoring_v2"
        / "issue_173"
        / "python"
        / "narration-timing-map-v2.json"
    )

    assert result == json.loads(golden.read_text(encoding="utf-8"))
    assert list(map_schema_validator().iter_errors(result)) == []
    assert [token["tokenId"] for token in result["tokens"]] == [
        token["id"] for token in TOKENS
    ]
    assert [token["quotedText"] for token in result["tokens"]] == [
        token["value"] for token in TOKENS
    ]
    assert result["tokens"][-1]["endBasis"] == "unknown"
    assert all("audibleEnd" not in token for token in result["tokens"])


def test_rejects_stale_timing_hash_revision_text_and_token_snapshot() -> None:
    timing = timing_json()
    narration_asset = asset(timing)
    with pytest.raises(NarrationDependencyError, match="hash differs"):
        narration_v2_dependency_from_asset(narration_asset, timing + b" ", block())

    stale_revision = block()
    stale_revision["version"] = 3
    with pytest.raises(NarrationDependencyError, match="revision differs"):
        narration_v2_dependency_from_asset(narration_asset, timing, stale_revision)

    stale_text = block()
    stale_text["text"] = "Changed narration"
    with pytest.raises(NarrationDependencyError, match="text hash differs"):
        narration_v2_dependency_from_asset(narration_asset, timing, stale_text)

    stale_token = block()
    stale_token["tokens"][2]["value"] = "elan"
    with pytest.raises(NarrationDependencyError, match="token text differs"):
        narration_v2_dependency_from_asset(narration_asset, timing, stale_token)


def test_rejects_unsafe_audio_and_sentence_only_timing() -> None:
    timing = timing_json()
    unsafe_audio = replace(
        asset(timing),
        locators={"audio": "../outside.wav", "timing": "t", "record": "r"},
    )
    with pytest.raises(NarrationDependencyError, match="project-relative"):
        narration_v2_dependency_from_asset(unsafe_audio, timing, block())

    linebreak_audio = replace(
        asset(timing),
        locators={
            "audio": "build-assets/narration/\nclip.wav",
            "timing": "t",
            "record": "r",
        },
    )
    with pytest.raises(NarrationDependencyError, match="project-relative"):
        narration_v2_dependency_from_asset(linebreak_audio, timing, block())

    sentence_timing = timing_json(sentence_only=True)
    with pytest.raises(NarrationDependencyError, match="word_timing_required"):
        narration_v2_dependency_from_asset(
            asset(sentence_timing, sentence_only=True), sentence_timing, block()
        )


def test_rejects_invalid_token_ids_unpaired_surrogates_and_out_of_audio_starts() -> (
    None
):
    timing = timing_json()
    narration_asset = asset(timing)

    invalid_id = block()
    invalid_id["tokens"][0]["id"] = "not-a-uuid"
    with pytest.raises(NarrationDependencyError, match="token ID is invalid"):
        narration_v2_dependency_from_asset(narration_asset, timing, invalid_id)

    invalid_block_id = block()
    invalid_block_id["id"] = "not-a-uuid"
    with pytest.raises(NarrationDependencyError, match="block ID is invalid"):
        narration_v2_dependency_from_asset(narration_asset, timing, invalid_block_id)

    unpaired_surrogate = block()
    unpaired_surrogate["text"] = "invalid \ud800 text"
    with pytest.raises(NarrationDependencyError, match="unpaired surrogate"):
        narration_v2_dependency_from_asset(narration_asset, timing, unpaired_surrogate)

    out_of_audio_timing = timing_json(last_time_ms=2000)
    with pytest.raises(NarrationDependencyError, match="audio duration"):
        narration_v2_dependency_from_asset(
            asset(out_of_audio_timing), out_of_audio_timing, block()
        )
