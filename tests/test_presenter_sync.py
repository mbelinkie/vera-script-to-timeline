"""Lining up separately recorded sound with camera sound (#45)."""

from __future__ import annotations

import numpy as np
import pytest
from vera_timeline_agent.presenter_sync import Samples, SyncRefused, find_offset

RATE = 16000


def _performance(seconds: float, seed: int = 1) -> Samples:
    """Noise in bursts, like speech with pauses; never periodic."""
    rng = np.random.default_rng(seed)
    sound = rng.standard_normal(round(seconds * RATE))
    envelope = np.repeat(rng.random(round(seconds * 4)) > 0.4, RATE // 4)
    return (sound * envelope[: len(sound)] * 0.2).astype(np.float32)


def _heard(sound: Samples, seed: int) -> Samples:
    """The same performance through another microphone: own level and noise."""
    rng = np.random.default_rng(seed)
    noise = rng.standard_normal(len(sound)) * 0.05
    return (sound * 0.7 + noise).astype(np.float32)


def test_separate_audio_that_started_first_is_found_to_the_sample() -> None:
    performance = _performance(36)
    start = round(7.3125 * RATE)
    camera = _heard(performance[start : start + 25 * RATE], 2)
    result = find_offset(camera, _heard(performance, 3), RATE)
    assert abs(result.offset_s - 7.3125) < 2 / RATE
    assert result.spread_s < 0.001
    assert len(result.windows) >= 5


def test_separate_audio_that_started_late_has_a_negative_offset() -> None:
    performance = _performance(36)
    start = round(4.5 * RATE)
    separate = _heard(performance[start : start + 28 * RATE], 2)
    result = find_offset(_heard(performance, 3), separate, RATE)
    assert abs(result.offset_s + 4.5) < 2 / RATE


def test_unrelated_sound_is_refused_not_guessed() -> None:
    with pytest.raises(SyncRefused, match="does not clearly match"):
        find_offset(_performance(20, seed=1), _performance(24, seed=9), RATE)


def test_recordings_that_drift_apart_are_refused() -> None:
    performance = _performance(40)
    # The second recorder runs 0.3% fast: 120 ms of drift across the recording.
    positions = np.arange(0, len(performance) - 1, 1.003)
    drifting = np.interp(positions, np.arange(len(performance)), performance)
    with pytest.raises(SyncRefused):
        find_offset(_heard(performance, 2), drifting.astype(np.float32), RATE)


def test_silence_and_very_short_recordings_are_refused() -> None:
    silent = np.zeros(20 * RATE, dtype=np.float32)
    with pytest.raises(SyncRefused, match="silent"):
        find_offset(silent, _performance(20), RATE)
    with pytest.raises(SyncRefused, match="at least"):
        find_offset(_performance(2), _performance(20), RATE)


def test_a_short_clip_late_in_a_long_recording_is_found() -> None:
    performance = _performance(120)
    start = 90 * RATE
    camera = _heard(performance[start : start + 20 * RATE], 2)
    result = find_offset(camera, _heard(performance, 3), RATE)
    assert abs(result.offset_s - 90) < 2 / RATE


def test_a_microphone_wired_the_other_way_round_still_matches() -> None:
    performance = _performance(36)
    start = 3 * RATE
    camera = _heard(performance[start : start + 25 * RATE], 2)
    result = find_offset(camera, -_heard(performance, 3), RATE)
    assert abs(result.offset_s - 3) < 2 / RATE
