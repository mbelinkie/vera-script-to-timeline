"""Synthetic narration row for #182 measurement tests (no ffmpeg, no provider).

Row text "alpha beta gamma delta" (16 kHz raw provider PCM, 48 kHz normalized):

    0-100 ms   silence
    100-400    alpha  (400 Hz)           then 120 ms silence   -> pause
    520-820    beta   (600 Hz)  runs straight into gamma      -> connected
    820-1120   gamma  (800 Hz)           then 150 ms silence   -> pause
    1270-1520  delta  (1000 Hz) row-final, then 150 ms tail   -> row-final
"""

from __future__ import annotations

import io
import math
import struct
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any

from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    ProviderTimingMark,
    canonical_json_bytes,
    sha256_bytes,
)

BLOCK_ID = "10000000-0000-4000-8000-000000000001"
TEXT = "alpha beta gamma delta"
WORDS = ("alpha", "beta", "gamma", "delta")
TOKEN_IDS = tuple(f"20000000-0000-4000-8000-00000000000{n}" for n in range(1, 5))
OFFSETS = ((0, 5), (6, 10), (11, 16), (17, 22))
MARK_MS = (100, 520, 820, 1270)
# (start ms, end ms, frequency Hz) of every voiced burst in the raw row.
BURSTS = ((100, 400, 400), (520, 820, 600), (820, 1120, 800), (1270, 1520, 1000))
RAW_MS = 1670
RAW_RATE = 16_000


def burst_pcm(
    bursts: tuple[tuple[int, ...], ...] = BURSTS,
    total_ms: int = RAW_MS,
    amplitude: float = 8000.0,
) -> list[int]:
    samples = [0] * (total_ms * RAW_RATE // 1000)
    ramp = 5 * RAW_RATE // 1000
    for burst in bursts:
        start_ms, end_ms, hertz = burst[:3]
        level = float(burst[3]) if len(burst) > 3 else amplitude
        first = start_ms * RAW_RATE // 1000
        last = end_ms * RAW_RATE // 1000
        for index in range(first, last):
            fade = min(1.0, (index - first) / ramp, (last - 1 - index) / ramp)
            fade = 0.5 - 0.5 * math.cos(math.pi * max(0.0, fade))
            samples[index] = round(
                level * fade * math.sin(2 * math.pi * hertz * index / RAW_RATE)
            )
    return samples


def pcm_bytes(samples: list[int]) -> bytes:
    return struct.pack(f"<{len(samples)}h", *samples)


def normalize(
    raw: list[int], *, lag_samples: int = 0, gain: float = 0.5, tail_ms: int = 100
) -> list[int]:
    """Upsample 16 -> 48 kHz by holding, delay by ``lag_samples``, gain, pad."""

    wide = [round(sample * gain) for sample in raw for _ in range(3)]
    wide = [0] * lag_samples + wide if lag_samples >= 0 else wide[-lag_samples:]
    return wide + [0] * (tail_ms * 48)


def wav_bytes(samples: list[int], rate: int = 48_000) -> bytes:
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(pcm_bytes(samples))
    return buffer.getvalue()


def frozen_block(text: str = TEXT) -> dict[str, Any]:
    return {
        "type": "narration",
        "id": BLOCK_ID,
        "version": 1,
        "text": text,
        "tokens": [
            {
                "id": TOKEN_IDS[n],
                "value": WORDS[n],
                "startOffset": OFFSETS[n][0],
                "endOffset": OFFSETS[n][1],
            }
            for n in range(4)
        ],
    }


def timing_bytes(mark_ms: tuple[int, ...] = MARK_MS) -> bytes:
    marks = [
        ProviderTimingMark(
            kind="word",
            time_ms=mark_ms[n],
            start_byte=OFFSETS[n][0],
            end_byte=OFFSETS[n][1],
            start_utf16=OFFSETS[n][0],
            end_utf16=OFFSETS[n][1],
            value=WORDS[n],
        )
        for n in range(len(mark_ms))
    ]
    return canonical_json_bytes(
        {
            "recordVersion": "provider-timing/v1",
            "precision": "word_start_with_derived_end",
            "marks": [asdict(mark) for mark in marks],
        }
    )


def build_cache(
    root: Path,
    *,
    lag_samples: int = 0,
    gain: float = 0.5,
    mark_ms: tuple[int, ...] = MARK_MS,
    bursts: tuple[tuple[int, ...], ...] = BURSTS,
) -> tuple[NarrationCache, NarrationAudioAsset, str]:
    """Publish synthesis + asset entries the way NarrationService lays them out."""

    cache = NarrationCache(root)
    raw = burst_pcm(bursts)
    raw_bytes = pcm_bytes(raw)
    wav = wav_bytes(normalize(raw, lag_samples=lag_samples, gain=gain))
    timing = timing_bytes(mark_ms)
    request_hash = sha256_bytes(b"request-" + wav[:64])
    synthesis_key = request_hash.removeprefix("sha256:")
    cache.publish(
        "synthesis",
        synthesis_key,
        {
            "provider-input.ssml": b"<speak>x</speak>",
            "provider-audio.pcm": raw_bytes,
            "provider-timing.json": timing,
        },
        "synthesis.json",
        {
            "recordVersion": "synthesis-cache/v1",
            "audioFormat": "pcm_s16le",
            "sampleRate": RAW_RATE,
            "channels": 1,
            "provenance": {"provider": "fake"},
            "requestIds": ["req-1"],
        },
    )
    asset_id = sha256_bytes(b"asset-" + wav[:64]).removeprefix("sha256:")
    frames = len(wav_samples(wav))
    asset = NarrationAudioAsset(
        record_version="narration-audio-asset/v1",
        asset_id=asset_id,
        block_id=BLOCK_ID,
        block_revision=1,
        kind="temp_synthetic",
        status="ready",
        text_hash=sha256_bytes(TEXT.encode()),
        provider_input_hash=sha256_bytes(b"<speak>x</speak>"),
        profile_hash="sha256:" + "1" * 64,
        settings_hash="sha256:" + "2" * 64,
        pronunciation_hash="sha256:" + "3" * 64,
        request_hash=request_hash,
        provider="fake",
        region="local",
        model="neural",
        voice_id="Matthew",
        voice_version="v1",
        raw_audio_hash=sha256_bytes(raw_bytes),
        raw_timing_hash=sha256_bytes(timing),
        timing_precision="word_start_with_derived_end",
        normalization_profile="test",
        normalization_hash="sha256:" + "4" * 64,
        tool_fingerprint="sha256:" + "5" * 64,
        normalized_audio_hash=sha256_bytes(wav),
        duration_samples=frames,
        duration_ms=frames // 48,
        sample_rate=48_000,
        channels=1,
        sample_format="s16",
        synthesis_disposition="generated",
        normalization_disposition="generated",
        locators={
            "audio": f"v1/assets/{BLOCK_ID}/{asset_id}/narration.wav",
            "timing": f"v1/assets/{BLOCK_ID}/{asset_id}/timing.json",
            "record": f"v1/assets/{BLOCK_ID}/{asset_id}/asset.json",
        },
        generated_at="2026-10-19T00:00:00+00:00",
        request_ids=("req-1",),
    )
    key = f"{BLOCK_ID}/{asset_id}"
    cache.publish(
        "assets",
        key,
        {"narration.wav": wav, "timing.json": timing},
        "asset.json",
        {"recordVersion": "asset-cache/v1", "asset": asset.as_json()},
    )
    return cache, asset, key


def wav_samples(data: bytes) -> list[int]:
    with wave.open(io.BytesIO(data)) as handle:
        raw = handle.readframes(handle.getnframes())
    return list(struct.unpack(f"<{len(raw) // 2}h", raw))
