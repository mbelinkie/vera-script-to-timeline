from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import struct
import sys
import wave
from dataclasses import replace
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.compiler_dependencies_v2 import (
    narration_v2_dependency_from_asset,
)
from vera_timeline_agent.narration.models import (
    SynthesisRequest,
    SynthesisSettings,
    VoiceProfile,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import (
    NORMALIZER_VERSION,
    NormalizationResult,
)
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "scripts" / "word-timing"),
)
import issue289_inworld_replay as replay

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
TOKEN_IDS = [
    "20000000-0000-4000-8000-000000000001",
    "20000000-0000-4000-8000-000000000002",
    "20000000-0000-4000-8000-000000000003",
]
TEXT = "Måns says go."
TOKENS: list[dict[str, Any]] = [
    {"id": TOKEN_IDS[0], "value": "Måns", "startOffset": 0, "endOffset": 4},
    {"id": TOKEN_IDS[1], "value": "says", "startOffset": 5, "endOffset": 9},
    {"id": TOKEN_IDS[2], "value": "go", "startOffset": 10, "endOffset": 12},
]
WORDS = ["Måns", " ", "says", " ", "go", "."]
STARTS = [0.10003, 0.2, 0.30003, 0.45, 0.55003, 0.8]
ENDS = [0.19, 0.25, 0.44, 0.5, 0.79, 0.82]


def _wav(pcm: bytes) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(1)
        audio.setsampwidth(2)
        audio.setframerate(replay.SAMPLE_RATE)
        audio.writeframes(pcm)
    return output.getvalue()


def _pcm() -> bytes:
    return b"".join(
        struct.pack(
            "<h", round(5000 * math.sin(2 * math.pi * 440 * i / replay.SAMPLE_RATE))
        )
        for i in range(replay.SAMPLE_RATE)
    )


def _utf16_length(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _capture(
    root: Path,
    *,
    words: list[str] | None = None,
    starts: list[float] | None = None,
    ends: list[float] | None = None,
    response_wav: bytes | None = None,
    provider_input_text: str = TEXT,
    voice_id: str = "Ashley",
) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    pcm = _pcm()
    wav = _wav(pcm)
    cursor = 0
    tokens = []
    for source_token in TOKENS:
        token = dict(source_token)
        start_cp = TEXT.index(token["value"], cursor)
        end_cp = start_cp + len(token["value"])
        token["startOffset"] = _utf16_length(TEXT[:start_cp])
        token["endOffset"] = _utf16_length(TEXT[:end_cp])
        cursor = end_cp
        tokens.append(dict(token))
    row = {
        "blockId": BLOCK_ID,
        "blockRevision": 2,
        "text": TEXT,
        "textHash": sha256_bytes(TEXT.encode("utf-8")),
        "tokens": tokens,
    }
    files: dict[str, bytes] = {
        "request.private.json": json.dumps(
            {
                "provider": "inworld",
                "takeId": "synthetic-capture-1",
                "status": "succeeded",
                "config": {"model": "inworld-tts-2", "voiceId": voice_id},
                "row": row,
                "audio": {
                    "sha256": sha256_bytes(wav),
                    "sampleRate": replay.SAMPLE_RATE,
                    "channels": 1,
                    "samples": replay.SAMPLE_RATE,
                    "durationSeconds": 1.0,
                },
            },
            ensure_ascii=False,
        ).encode("utf-8"),
        "provider-input.json": json.dumps(
            {
                "modelId": "inworld-tts-2",
                "voiceId": voice_id,
                "text": provider_input_text,
                "timestampType": "WORD",
                "audioConfig": {
                    "audioEncoding": "LINEAR16",
                    "speakingRate": 1.0,
                },
            },
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8"),
        "response.raw.json": json.dumps(
            {
                "audioContent": base64.b64encode(response_wav or wav).decode("ascii"),
                "timestampInfo": {
                    "wordAlignment": {
                        "words": words if words is not None else WORDS,
                        "wordStartTimeSeconds": starts
                        if starts is not None
                        else STARTS,
                        "wordEndTimeSeconds": ends if ends is not None else ENDS,
                    }
                },
                "usage": {"characters": len(TEXT)},
            }
        ).encode("utf-8"),
        "audio.wav": wav,
    }
    for name, data in files.items():
        (root / name).write_bytes(data)
    return {
        name: f"sha256:{hashlib.sha256(data).hexdigest()}"
        for name, data in files.items()
    }


def _request(
    *, text: str = TEXT, profile: VoiceProfile = replay.INWORLD_STUDY_PROFILE
) -> SynthesisRequest:
    return SynthesisRequest(
        block_id=BLOCK_ID,
        block_revision=2,
        text=text,
        profile=profile,
        settings=SynthesisSettings(),
        max_cost_usd=0.0,
        pricing_policy_version=replay.INWORLD_STUDY_PRICING.version,
    )


def test_replay_maps_exact_frozen_tokens_and_keeps_native_samples(
    tmp_path: Path,
) -> None:
    hashes = _capture(tmp_path)
    provider = replay.InworldCaptureReplayProvider(tmp_path, hashes, voice_id="Ashley")
    result = provider.synthesize(_request())

    assert result.audio_format == "pcm_s16le"
    assert result.sample_rate == replay.SAMPLE_RATE and result.channels == 1
    assert [mark.value for mark in result.timing_marks] == ["Måns", "says", "go"]
    assert [mark.start_utf16 for mark in result.timing_marks] == [0, 5, 10]
    assert [mark.end_utf16 for mark in result.timing_marks] == [4, 9, 12]
    assert [mark.start_byte for mark in result.timing_marks] == [0, 6, 11]
    assert [mark.time_sample for mark in result.timing_marks] == [4801, 14401, 26401]
    assert [mark.time_ms for mark in result.timing_marks] == [100, 300, 550]
    assert all(mark.sample_rate == replay.SAMPLE_RATE for mark in result.timing_marks)
    assert result.provenance["provider"] == "inworld"
    assert result.provenance["engine"] == "inworld-tts-2"
    assert result.provenance["voiceId"] == "Ashley"
    assert result.provenance["captureHashes"] == hashes
    assert json.loads(result.provider_input) == json.loads(
        (tmp_path / "provider-input.json").read_text(encoding="utf-8")
    )


def test_capture_pin_is_part_of_provider_cache_identity(tmp_path: Path) -> None:
    first_hashes = _capture(tmp_path / "first")
    second_hashes = _capture(
        tmp_path / "second", starts=[0.10004, 0.2, 0.30003, 0.45, 0.55003, 0.8]
    )

    first = replay.InworldCaptureReplayProvider(
        tmp_path / "first", first_hashes, voice_id="Ashley"
    )
    second = replay.InworldCaptureReplayProvider(
        tmp_path / "second", second_hashes, voice_id="Ashley"
    )

    assert first.adapter_version != second.adapter_version


def test_explicit_arthur_capture_keeps_its_voice_identity(tmp_path: Path) -> None:
    profile = replay.inworld_study_profile("Arthur")
    hashes = _capture(tmp_path, voice_id="Arthur")
    provider = replay.InworldCaptureReplayProvider(
        tmp_path, hashes, voice_id=profile.voice_id
    )

    result = provider.synthesize(_request(profile=profile))

    assert provider.profile == profile
    assert profile.profile_id != replay.INWORLD_STUDY_PROFILE.profile_id
    assert result.provenance["voiceId"] == "Arthur"
    with pytest.raises(replay.InworldReplayError, match="wrong Inworld model or voice"):
        replay.InworldCaptureReplayProvider(tmp_path, hashes, voice_id="Ashley")


def test_replay_refuses_unpinned_bytes_before_parsing(tmp_path: Path) -> None:
    hashes = _capture(tmp_path)
    with (tmp_path / "response.raw.json").open("ab") as output:
        output.write(b" ")

    with pytest.raises(replay.InworldReplayError, match="hash mismatch"):
        replay.InworldCaptureReplayProvider(tmp_path, hashes, voice_id="Ashley")


@pytest.mark.parametrize(
    ("words", "starts", "ends", "message"),
    [
        (
            ["Måns", " ", "says", " ", "go", "."],
            [0.1, 0.2, 0.1, 0.45, 0.55, 0.8],
            ENDS,
            "tie",
        ),
        (
            ["Måns says", " ", "go", "."],
            [0.1, 0.3, 0.55, 0.8],
            [0.44, 0.5, 0.79, 0.82],
            "cover tokens",
        ),
        (["Måns", " ", "says", " ", "missing", "."], STARTS, ENDS, "exactly cover"),
    ],
)
def test_replay_refuses_ties_phrases_and_missing_source_coverage(
    tmp_path: Path,
    words: list[str],
    starts: list[float],
    ends: list[float],
    message: str,
) -> None:
    hashes = _capture(tmp_path, words=words, starts=starts, ends=ends)

    with pytest.raises(replay.InworldReplayError, match=message):
        replay.InworldCaptureReplayProvider(tmp_path, hashes, voice_id="Ashley")


def test_replay_refuses_text_and_profile_mismatches(tmp_path: Path) -> None:
    hashes = _capture(tmp_path)
    provider = replay.InworldCaptureReplayProvider(tmp_path, hashes, voice_id="Ashley")
    with pytest.raises(replay.InworldReplayError, match="text mismatch"):
        provider.prepare_input(_request(text="changed"))
    other_profile = replace(replay.INWORLD_STUDY_PROFILE, voice_id="Joanna")
    with pytest.raises(replay.InworldReplayError, match="profile mismatch"):
        provider.prepare_input(_request(profile=other_profile))


def test_replay_refuses_provider_input_text_and_response_audio_mismatch(
    tmp_path: Path,
) -> None:
    wrong_input = _capture(tmp_path, provider_input_text="different")
    with pytest.raises(replay.InworldReplayError, match="provider input differs"):
        replay.InworldCaptureReplayProvider(tmp_path, wrong_input, voice_id="Ashley")

    other_root = tmp_path / "other"
    wrong_audio = _wav(b"\x00\x00" * replay.SAMPLE_RATE)
    hashes = _capture(other_root, response_wav=wrong_audio)
    with pytest.raises(replay.InworldReplayError, match="response audio mismatch"):
        replay.InworldCaptureReplayProvider(other_root, hashes, voice_id="Ashley")


class _ReplayNormalizer:
    profile_id = "test-normalizer"
    tool_fingerprint = "test-tool-fingerprint"

    def normalize_pcm(
        self, pcm: bytes, *, sample_rate: int, channels: int
    ) -> NormalizationResult:
        assert sample_rate == replay.SAMPLE_RATE and channels == 1
        return NormalizationResult(
            wav_bytes=_wav(pcm),
            profile_id=self.profile_id,
            normalizer_version=NORMALIZER_VERSION,
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=sample_rate,
            channels=channels,
            sample_format="s16",
            duration_samples=len(pcm) // 2,
            duration_ms=round(len(pcm) * 1000 / (2 * sample_rate)),
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.0,
            loudness_range_lu=1.0,
        )

    def placeholder(self, _block_id: str) -> NormalizationResult:
        raise AssertionError("the captured replay should be admitted")


def test_retained_replay_crosses_real_service_and_v2_projection(tmp_path: Path) -> None:
    hashes = _capture(tmp_path / "take")
    provider = replay.InworldCaptureReplayProvider(
        tmp_path / "take", hashes, voice_id="Ashley"
    )
    block = {
        "type": "narration",
        "id": BLOCK_ID,
        "orderKey": "a0",
        "text": TEXT,
        "tokens": [dict(token) for token in TOKENS],
        "overlayEvents": [],
        "timingPolicy": "narration_spine",
        "state": "active",
        "notes": [],
        "version": 2,
    }
    cache = NarrationCache(tmp_path / "cache")
    service = NarrationService(
        cache=cache,
        provider=provider,
        normalizer=cast(Any, _ReplayNormalizer()),
        config=ServiceConfig(
            profile=provider.profile,
            pricing_policy=replay.INWORLD_STUDY_PRICING,
            max_cost_usd=0.0,
        ),
    )

    asset = service.process_block(block)
    entry = cache.read(
        "synthesis", asset.request_hash.removeprefix("sha256:"), "synthesis.json"
    )
    assert entry is not None
    timing = entry.files["provider-timing.json"]
    projected = narration_v2_dependency_from_asset(asset, timing, cast(Any, block))

    assert asset.status == "ready"
    assert asset.provider == "inworld" and asset.model == "inworld-tts-2"
    assert asset.voice_id == "Ashley"
    assert [token["tokenId"] for token in projected["tokens"]] == TOKEN_IDS
    assert projected["tokens"][0]["startTime"] == {
        "numerator": 4801,
        "denominator": 48000,
    }
    assert projected["tokens"][1]["startTime"] == {
        "numerator": 14401,
        "denominator": 48000,
    }
