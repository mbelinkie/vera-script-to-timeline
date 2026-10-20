from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from issue182_fixture import TOKEN_IDS, build_cache, frozen_block
from vera_timeline_agent.narration.measure import load_asset, measure_asset
from vera_timeline_agent.narration.omission_envelope import (
    FRAME_SAMPLES,
    EnvelopeRefused,
    omission_envelope,
    omission_envelope_report,
)

ONSET_UNC = 480  # 10 ms
END_UNC = 240  # 5 ms


def rat(samples: int) -> dict[str, int]:
    from fractions import Fraction

    value = Fraction(samples, 48_000)
    return {"numerator": value.numerator, "denominator": value.denominator}


def evidence(tokens: list[dict[str, Any]], duration: int = 480_000) -> dict[str, Any]:
    rows = []
    for index, token in enumerate(tokens):
        row: dict[str, Any] = {
            "tokenId": f"t{index}",
            "quotedText": f"w{index}",
            "onset": rat(token["onset"]),
        }
        if "end" in token:
            row["audibleEnd"] = rat(token["end"])
        rows.append(row)
    return {
        "audio": {"sampleRate": 48_000, "durationSamples": duration},
        "tokens": rows,
        "verification": {
            "method": "measured_audio_boundaries/v1",
            "onsetUncertainty": rat(ONSET_UNC),
            "audibleEndUncertainty": rat(END_UNC),
        },
    }


def test_measured_row_yields_unique_safe_first_and_last_targets(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    measured = measure_asset(
        load_asset(cache, key), frozen_block(), artifact_locator="m.json"
    ).evidence
    first = omission_envelope(measured, TOKEN_IDS[0])
    assert first["uniquelySafe"] is True
    assert first["leftNeighbour"] is None and first["rightNeighbour"] == "beta"
    assert first["cutStart"]["frameCount"] >= 1
    assert first["cutEnd"]["frameCount"] >= 1
    # Row-final word with a measured tail.
    last = omission_envelope(measured, TOKEN_IDS[3])
    assert last["rightNeighbour"] is None and last["cutEnd"]["highBasis"] == "row_end"
    # Boundaries are real 23.976 frame boundaries inside the (shrunk) envelope.
    env = first["cutEnd"]
    assert env["firstBoundarySamples"] % FRAME_SAMPLES == 0
    assert env["firstBoundarySamples"] >= env["rawLowSamples"] + END_UNC


def test_connected_speech_neighbour_is_refused(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    measured = measure_asset(
        load_asset(cache, key), frozen_block(), artifact_locator="m.json"
    ).evidence
    # gamma: left neighbour beta has no audible end (runs into gamma).
    report = omission_envelope_report(measured, TOKEN_IDS[2])
    assert report["uniquelySafe"] is False
    assert any("connected speech" in r for r in report["refusalReasons"])
    # beta: it has no audible end of its own.
    with pytest.raises(EnvelopeRefused, match="no measured audible end"):
        omission_envelope(measured, TOKEN_IDS[1])


def test_envelope_collapsed_by_uncertainty_is_refused() -> None:
    # Gap between left end and selected onset is 700 samples < 480 + 240.
    data = evidence(
        [
            {"onset": 1000, "end": 20_000},
            {"onset": 20_700, "end": 40_000},
            {"onset": 60_000, "end": 70_000},
        ]
    )
    report = omission_envelope_report(data, "t1")
    assert report["uniquelySafe"] is False
    assert any("collapses" in r for r in report["refusalReasons"])


def test_envelope_without_a_frame_boundary_is_refused() -> None:
    low = FRAME_SAMPLES * 10 + 1  # envelope [low, low + 1680] holds no boundary
    left_end = low - END_UNC
    onset = low + 1680 + ONSET_UNC
    data = evidence(
        [
            {"onset": 1000, "end": left_end},
            {"onset": onset, "end": onset + 30_000},
            {"onset": onset + 80_000, "end": onset + 90_000},
        ]
    )
    report = omission_envelope_report(data, "t1")
    assert report["uniquelySafe"] is False
    assert any("no 23.976 frame boundary" in r for r in report["refusalReasons"])
    # Move the same envelope so a boundary falls inside it: now safe.
    low = FRAME_SAMPLES * 10 - 100
    onset = low + 1680 + ONSET_UNC
    safe = evidence(
        [
            {"onset": 1000, "end": low - END_UNC},
            {"onset": onset, "end": onset + 30_000},
            {"onset": onset + 80_000, "end": onset + 90_000},
        ]
    )
    report = omission_envelope_report(safe, "t1")
    assert report["uniquelySafe"] is True
    assert report["cutStart"]["firstBoundarySamples"] == FRAME_SAMPLES * 10


def test_non_measured_evidence_is_never_relabelled() -> None:
    data = evidence([{"onset": 1000, "end": 5000}])
    data["verification"]["method"] = "reviewed_audio_boundaries/v1"
    with pytest.raises(EnvelopeRefused, match="measured evidence"):
        omission_envelope(data, "t0")
