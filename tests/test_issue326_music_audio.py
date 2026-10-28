from __future__ import annotations

import json
import math
import wave
from pathlib import Path
from typing import Any

import pytest

from scripts.issue326_check_music_audio import check_render

RATE = 48_000
FRAME = 2_000
SEGMENT = 24_000
FREQUENCIES = [620 + 40 * index for index in range(24)]


def probe(*, two_rows: bool = False) -> dict[str, Any]:
    rows = (
        [
            {
                "rowId": "row-a",
                "recordStartFrame": 0,
                "recordEndFrame": 24,
                "frequencyHz": 220,
                "peakAmplitude": 0.12,
            },
            {
                "rowId": "row-b",
                "recordStartFrame": 24,
                "recordEndFrame": 48,
                "frequencyHz": 277,
                "peakAmplitude": 0.12,
            },
        ]
        if two_rows
        else [
            {
                "rowId": "row-a",
                "recordStartFrame": 0,
                "recordEndFrame": 48,
                "frequencyHz": 330,
                "peakAmplitude": 0.12,
            }
        ]
    )
    return {
        "caseId": "decoded-test",
        "sampleRate": RATE,
        "narration": rows,
        "music": {
            "recordStartFrame": 0,
            "recordEndFrame": 48,
            "sourceTrimSamples": RATE,
            "sourceRangeSamples": {"startSample": RATE, "endSample": RATE + 48 * FRAME},
            "segmentSamples": SEGMENT,
            "segmentFrequenciesHz": FREQUENCIES,
            "sourcePeak": 0.4,
            "gainDb": -12,
            "fadeFrames": 6,
        },
    }


def write_wav(path: Path, samples: list[float], *, width: int = 2) -> None:
    maximum = (1 << (width * 8 - 1)) - 1
    raw = bytearray()
    for sample in samples:
        value = round(max(-1.0, min(1.0, sample)) * maximum)
        raw.extend(value.to_bytes(width, "little", signed=True))
    with wave.open(str(path), "wb") as output:
        output.setparams((1, width, RATE, len(samples), "NONE", "not compressed"))
        output.writeframes(raw)


def render(
    metadata: dict[str, Any],
    *,
    with_music: bool,
    source_trim: int = RATE,
    playback_rate: float = 1.0,
    fade_power: float = 1.0,
    changed_rows: list[dict[str, Any]] | None = None,
) -> list[float]:
    total = 48 * FRAME
    rows = changed_rows or metadata["narration"]
    music = metadata["music"]
    start = music["recordStartFrame"] * FRAME
    end = music["recordEndFrame"] * FRAME
    fade = music["fadeFrames"] * FRAME
    gain = 10 ** (music["gainDb"] / 20)
    output: list[float] = []
    for sample in range(total):
        voice = 0.0
        for row in rows:
            row_start = row["recordStartFrame"] * FRAME
            row_end = row["recordEndFrame"] * FRAME
            if row_start <= sample < row_end:
                voice = row["peakAmplitude"] * math.sin(
                    2 * math.pi * row["frequencyHz"] * (sample - row_start) / RATE
                )
                break
        music_value = 0.0
        if with_music and start <= sample < end:
            source_sample = source_trim + round((sample - start) * playback_rate)
            source_index = source_sample // music["segmentSamples"]
            frequency = music["segmentFrequenciesHz"][source_index]
            fade_in = min(1.0, max(0.0, (sample - start) / fade)) ** fade_power
            fade_out = min(1.0, max(0.0, (end - sample) / fade)) ** fade_power
            envelope = min(fade_in, fade_out)
            music_value = (
                music["sourcePeak"]
                * gain
                * envelope
                * math.sin(2 * math.pi * frequency * source_sample / RATE)
            )
        output.append(voice + music_value)
    return output


def save_pair(
    tmp_path: Path,
    *,
    metadata: dict[str, Any] | None = None,
    source_trim: int = RATE,
    playback_rate: float = 1.0,
    fade_power: float = 1.0,
    changed_rows: list[dict[str, Any]] | None = None,
) -> tuple[Path, Path, Path]:
    data = metadata or probe(two_rows=changed_rows is not None)
    probe_path = tmp_path / "music-probe.json"
    baseline_path, mixed_path = tmp_path / "baseline.wav", tmp_path / "mixed.wav"
    probe_path.write_text(json.dumps(data), encoding="utf-8")
    write_wav(baseline_path, render(data, with_music=False))
    write_wav(
        mixed_path,
        render(
            data,
            with_music=True,
            source_trim=source_trim,
            playback_rate=playback_rate,
            fade_power=fade_power,
            changed_rows=changed_rows,
        ),
        width=3,
    )
    return probe_path, baseline_path, mixed_path


def test_decodes_mixed_render_and_reports_fade_curve_without_assuming_linearity(
    tmp_path: Path,
) -> None:
    args = save_pair(tmp_path, fade_power=0.5)
    report = check_render(*args)

    assert report["verified"]
    assert report["decoded"]["baselineBitsPerSample"] == 16
    assert report["decoded"]["mixedBitsPerSample"] == 24
    assert report["music"]["sourceTrimSamples"] == RATE
    assert report["music"]["sourceCodeFrequenciesCheckedHz"][0] == 700
    assert report["music"]["fadeInLinearCurveRmse"] > 0
    assert report["music"]["linearCurveErrorIsDiagnosticOnly"]
    assert report["narration"]["unchangedAgainstBaseline"]


@pytest.mark.parametrize(
    ("source_trim", "playback_rate"),
    [(0, 1.0), (RATE, 0.98)],
)
def test_rejects_wrong_source_trim_or_stretched_source_time(
    tmp_path: Path, source_trim: int, playback_rate: float
) -> None:
    args = save_pair(tmp_path, source_trim=source_trim, playback_rate=playback_rate)

    with pytest.raises(ValueError, match="source tone or -12 dB gain"):
        check_render(*args)


def test_rejects_narration_timing_change_against_baseline(tmp_path: Path) -> None:
    metadata = probe(two_rows=True)
    shifted_rows = [
        {**metadata["narration"][0], "recordEndFrame": 26},
        {**metadata["narration"][1], "recordStartFrame": 26},
    ]
    args = save_pair(tmp_path, metadata=metadata, changed_rows=shifted_rows)

    with pytest.raises(ValueError, match="narration changed"):
        check_render(*args)
