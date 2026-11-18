"""Synthetic delivered audio exercises the quiet-gap detector without a provider."""

import hashlib
import io
import struct
import wave
from typing import Any

import pytest
from vera_timeline_agent.narration.speech_gaps import SpeechGapError, detect_speech_gaps


def _inputs(levels: list[tuple[int, int]]) -> tuple[dict[str, Any], bytes]:
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setparams((1, 2, 48_000, 0, "NONE", "not compressed"))
        wav.writeframes(
            b"".join(struct.pack("<h", level) * (ms * 48) for level, ms in levels)
        )
    audio = output.getvalue()
    audio_hash = "sha256:" + hashlib.sha256(audio).hexdigest()
    return {
        "blockId": "sample",
        "audioHash": audio_hash,
        "timingHash": "sha256:" + "0" * 64,
        "audio": {
            "audioHash": audio_hash,
            "sampleRate": 48_000,
            "channels": 1,
            "durationSamples": sum(ms * 48 for _, ms in levels),
        },
        "tokens": [
            {"tokenId": "a", "startTime": {"numerator": 0, "denominator": 1}},
            {"tokenId": "b", "startTime": {"numerator": 1, "denominator": 2}},
        ],
    }, audio


@pytest.mark.parametrize(
    ("levels", "status", "reason"),
    [
        ([(9000, 200), (0, 300), (9000, 100)], "detected", "unique_terminal_quiet_run"),
        ([(9000, 600)], "absent", "no_qualifying_quiet_run"),
        ([(9000, 100), (0, 100), (9000, 400)], "absent", "nonterminal_quiet_run"),
        (
            [(9000, 100), (0, 100), (9000, 100), (0, 200), (9000, 100)],
            "ambiguous",
            "multiple_qualifying_quiet_runs",
        ),
    ],
)
def test_only_unique_terminal_quiet_runs_can_support_a_cut(
    levels: list[tuple[int, int]], status: str, reason: str
) -> None:
    timing, audio = _inputs(levels)
    observed = detect_speech_gaps(timing, audio)
    assert observed["audioHash"] == timing["audioHash"]
    pair = observed["tokenPairs"][0]
    assert (pair["status"], pair["reason"]) == (status, reason)
    if status == "detected":
        assert pair["quietWindow"] == {
            "startSample": 9_600,
            "endSample": 24_000,
            "durationSamples": 14_400,
        }
    else:
        assert pair["quietWindow"] is None


def test_audio_hash_is_required_even_for_a_single_word() -> None:
    timing, audio = _inputs([(9000, 600)])
    timing["tokens"].pop()
    assert detect_speech_gaps(timing, audio)["tokenPairs"] == []
    with pytest.raises(SpeechGapError, match="hash differs"):
        detect_speech_gaps(timing, audio + b"changed")
