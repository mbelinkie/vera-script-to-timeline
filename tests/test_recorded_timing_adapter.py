"""#47 timing duration, word anchors, source shortage and audio pins."""

from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
from pathlib import Path

import pytest
from test_recorded_conform import _snapshot, sample
from vera_timeline_agent.recorded_conform import ConformRefused
from vera_timeline_agent.recorded_timing_adapter import (
    derived_dependencies,
    frames_for_audio,
    impact_report,
    impact_text,
    silent_carrier,
    wire,
    write_silent_carrier,
)
from vera_timeline_agent.recorded_word_evidence import canonical_json


def test_approved_source_duration_binds_real_v2_audio_and_moves_spine() -> None:
    data = sample()
    snap = _snapshot(data)
    deps, carriers = derived_dependencies(snap, data["dependencies"])
    assert len(carriers) == 2
    original = data["dependencies"]["narrationTimingMaps"]
    new = deps["narrationTimingMaps"]
    assert new[1] == original[1]  # locked temporary voice stays byte-for-byte
    assert new[0]["audio"]["durationSamples"] == 96000  # 2s, NOT old 4s
    assert new[2]["audio"]["durationSamples"] == 144000
    assert new[0]["audioHash"] == new[0]["audio"]["audioHash"]
    assert new[0]["audio"]["timingHash"] == new[0]["timingHash"]
    for index in (0, 2):
        audio = new[index]["audio"]
        assert new[index]["audioHash"] == "sha256:" + audio["cacheAssetId"]
        assert any(c["sha256"] == audio["cacheAssetId"] for c in carriers)
    assert new[0]["tokens"][0]["startTime"] == {"numerator": 3, "denominator": 10}
    assert new[0]["tokens"][0]["endBasis"] == "evidenced_audible_end"
    impact = impact_report(snap, data["document"], data["dependencies"], deps)
    assert [r["oldDurationFrames"] for r in impact["rows"]] == [96, 96, 96]
    assert [r["newDurationFrames"] for r in impact["rows"]] == [48, 96, 72]
    assert [r["shiftAfterFrames"] for r in impact["rows"]] == [-48, -48, -72]
    assert "old 96f -> new 48f" in impact_text(impact)
    gold = Path(__file__).resolve().parents[1] / "tests/data/recorded_conform"
    assert canonical_json(impact) == (gold / "approved.impact.golden.json").read_bytes()
    assert (
        impact_text(impact).encode()
        == (gold / "approved.impact.golden.txt").read_bytes()
    )


def test_word_anchor_follows_recorded_acoustic_onset_not_scaled_old_position() -> None:
    data = sample()
    snap = _snapshot(data)
    first_block = data["document"]["activeDraft"]["blocks"][0]
    first = first_block["primaryVisualSequence"]["slots"][0]
    first["boundaryBefore"] = {
        "kind": "spoken_word",
        "anchor": {"tokenId": first_block["tokens"][0]["id"], "affinity": "before"},
    }
    deps, _ = derived_dependencies(snap, data["dependencies"])
    impact = impact_report(snap, data["document"], data["dependencies"], deps)
    assert impact["movedPictureAnchors"] == [
        {
            "rowId": "row-1",
            "ownerId": first["id"],
            "kind": "primary_visual_word_anchor",
            "tokenId": first_block["tokens"][0]["id"],
            "oldFrame": 0,
            "newFrame": 8,
            "deltaFrames": 8,
        }
    ]


def test_too_short_source_is_named_and_never_extended() -> None:
    data = sample()
    snap = _snapshot(data)
    data["dependencies"]["occurrenceResolutions"][0]["logicalSourceBounds"][
        "endFrame"
    ] = 40
    deps, _ = derived_dependencies(snap, data["dependencies"])
    impact = impact_report(snap, data["document"], data["dependencies"], deps)
    assert impact["requires_reconciliation"] is True
    assert impact["compilerReady"] is False
    short = impact["shortSources"][0]
    assert short["rowId"] == "row-1"
    assert short["requiredRange"] == {"startFrame": 0, "endFrame": 60}
    assert short["availableRange"] == {"startFrame": 0, "endFrame": 40}
    assert "SHORT SOURCE" in impact_text(impact)


def test_ntsc_source_rate_remains_sample_exact_without_floating_retime(
    tmp_path,
) -> None:
    data = sample()
    snap = _snapshot(data)
    altered = copy.deepcopy(snap)
    row = altered["rows"][0]
    row["sourceRate"] = [30000, 1001]
    row["effectiveCut"] = {"startFrame": 90, "endFrame": 150}
    # The measured word local interval must remain within 60 source frames.
    derived, carriers = derived_dependencies(altered, data["dependencies"])
    binding = derived["narrationTimingMaps"][0]["audio"]
    assert binding["sampleRate"] == 240000
    assert binding["durationSamples"] == 480480
    carrier = next(c for c in carriers if c["sha256"] == binding["cacheAssetId"])
    write_silent_carrier(carrier, tmp_path)
    audio = (tmp_path / carrier["name"]).read_bytes()
    assert len(audio) == 44 + 2 * 480480
    assert hashlib.sha256(audio).hexdigest() == carrier["sha256"]
    assert set(audio[44:]) == {0}


def test_silence_keeps_duration_and_forbids_acoustic_anchor() -> None:
    data = sample()
    snap = _snapshot(data)
    snap["rows"][1]["state"] = "no_spoken_line"
    derived, carriers = derived_dependencies(snap, data["dependencies"])
    assert len(carriers) == 3
    assert frames_for_audio(derived["narrationTimingMaps"][1]["audio"], [24, 1]) == 96
    block = data["document"]["activeDraft"]["blocks"][1]
    block["primaryVisualSequence"]["slots"][0]["boundaryBefore"] = {
        "kind": "spoken_word",
        "anchor": {"tokenId": block["tokens"][0]["id"], "affinity": "before"},
    }
    with pytest.raises(ConformRefused, match="silent passage"):
        impact_report(snap, data["document"], data["dependencies"], derived)


def test_invalid_or_non_reduced_word_time_fails_closed() -> None:
    with pytest.raises(ConformRefused, match="non-reduced"):
        wire({"numerator": 2, "denominator": 4})
    with pytest.raises(ConformRefused, match="non-reduced"):
        wire({"numerator": -1, "denominator": 1})
    assert wire({"numerator": 1001, "denominator": 30000}) == Fraction(1001, 30000)
    with pytest.raises(ConformRefused, match="safe PCM16"):
        silent_carrier(48000, 2**32)


def test_silent_wav_rejects_mismatched_pinned_hash(tmp_path: Path) -> None:
    carrier = silent_carrier(16000, 100)
    carrier["sha256"] = "0" * 64
    with pytest.raises(ConformRefused, match="pinned audio hash"):
        write_silent_carrier(carrier, tmp_path)
