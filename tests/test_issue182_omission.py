from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from issue182_fixture import TOKEN_IDS, build_cache, frozen_block
from vera_timeline_agent.narration.measure import (
    load_asset,
    measure_asset,
    parameters_hash,
)
from vera_timeline_agent.narration.models import sha256_bytes
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
    text = ""
    for index, token in enumerate(tokens):
        word = f"w{index}"
        start = len(text)
        text += word + " "
        row: dict[str, Any] = {
            "tokenId": f"t{index}",
            "startOffset": start,
            "endOffset": start + len(word),
            "quotedText": word,
            "onset": rat(token["onset"]),
        }
        if "end" in token:
            row["audibleEnd"] = rat(token["end"])
        rows.append(row)
    parameters = {"endQuietDbfs": -50}
    return {
        "blockId": "b1",
        "blockRevision": 1,
        "textHash": sha256_bytes(text.encode()),
        "audio": {"sampleRate": 48_000, "durationSamples": duration},
        "tokens": rows,
        "verification": {
            "method": "measured_audio_boundaries/v1",
            "algorithm": {
                "id": "vera-polly-marks-energy-ends",
                "version": "1",
                "parameters": parameters,
                "parametersHash": parameters_hash(parameters),
            },
            "onsetUncertainty": rat(ONSET_UNC),
            "audibleEndUncertainty": rat(END_UNC),
        },
    }


def block_of(data: dict[str, Any]) -> dict[str, Any]:
    tokens = data["tokens"]
    text = "".join(f"{token['quotedText']} " for token in tokens)
    return {
        "type": "narration",
        "id": data["blockId"],
        "version": data["blockRevision"],
        "text": text,
        "tokens": [
            {
                "id": token["tokenId"],
                "value": token["quotedText"],
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
            }
            for token in tokens
        ],
    }


def envelope(data: dict[str, Any], token: str) -> dict[str, Any]:
    return omission_envelope_report(data, token, block_of(data))


def test_measured_row_yields_unique_safe_first_and_last_targets(tmp_path: Path) -> None:
    cache, _asset, key = build_cache(tmp_path / "cache")
    measured = measure_asset(
        load_asset(cache, key), frozen_block(), artifact_locator="m.json"
    ).evidence
    first = omission_envelope(measured, TOKEN_IDS[0], frozen_block())
    assert first["uniquelySafe"] is True
    assert first["leftNeighbour"] is None and first["rightNeighbour"] == "beta"
    assert first["cutStart"]["frameCount"] >= 1
    assert first["cutEnd"]["frameCount"] >= 1
    # Row-final word with a measured tail.
    last = omission_envelope(measured, TOKEN_IDS[3], frozen_block())
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
    report = omission_envelope_report(measured, TOKEN_IDS[2], frozen_block())
    assert report["uniquelySafe"] is False
    assert any("connected speech" in r for r in report["refusalReasons"])
    # beta: it has no audible end of its own.
    with pytest.raises(EnvelopeRefused, match="no measured audible end"):
        omission_envelope(measured, TOKEN_IDS[1], frozen_block())


def test_envelope_collapsed_by_uncertainty_is_refused() -> None:
    # Gap between left end and selected onset is 700 samples < 480 + 240.
    data = evidence(
        [
            {"onset": 1000, "end": 20_000},
            {"onset": 20_700, "end": 40_000},
            {"onset": 60_000, "end": 70_000},
        ]
    )
    report = envelope(data, "t1")
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
    report = envelope(data, "t1")
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
    report = envelope(safe, "t1")
    assert report["uniquelySafe"] is True
    assert report["cutStart"]["firstBoundarySamples"] == FRAME_SAMPLES * 10


def test_non_measured_evidence_is_never_relabelled() -> None:
    data = evidence([{"onset": 1000, "end": 5000}])
    data["verification"]["method"] = "reviewed_audio_boundaries/v1"
    with pytest.raises(EnvelopeRefused, match="measured evidence"):
        omission_envelope(data, "t0", block_of(data))


def _three() -> dict[str, Any]:
    return evidence(
        [
            {"onset": 1000, "end": 20_000},
            {"onset": 60_000, "end": 80_000},
            {"onset": 120_000, "end": 140_000},
        ]
    )


def test_evidence_with_a_missing_middle_token_is_refused() -> None:
    # Reproduces the reviewer's case: dropping the intervening token would make
    # t0's right neighbour t2 and yield a "uniquely safe" cut across t1.
    data = _three()
    block = block_of(data)
    del data["tokens"][1]
    with pytest.raises(EnvelopeRefused, match="no gap"):
        omission_envelope_report(data, "t0", block)


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d, b: d.update(blockId="other"), "block id/revision"),
        (lambda d, b: d.update(blockRevision=2), "block id/revision"),
        (lambda d, b: d.update(textHash="sha256:" + "0" * 64), "textHash"),
        (lambda d, b: d["tokens"][1].update(tokenId="tX"), "not the block's token"),
        (lambda d, b: d["tokens"][1].update(startOffset=4), "not the block's token"),
        (lambda d, b: d["tokens"].reverse(), "not the block's token"),
        (lambda d, b: b["tokens"].pop(), "no gap"),
    ],
)
def test_evidence_must_match_the_frozen_block(mutate: Any, message: str) -> None:
    data = _three()
    block = block_of(data)
    mutate(data, block)
    with pytest.raises(EnvelopeRefused, match=message):
        omission_envelope_report(data, "t0", block)


def test_parameters_hash_must_be_the_canonical_hash() -> None:
    data = _three()
    data["verification"]["algorithm"]["parametersHash"] = "sha256:" + "f" * 64
    with pytest.raises(EnvelopeRefused, match="parametersHash"):
        omission_envelope_report(data, "t0", block_of(data))
    data = _three()
    data["verification"]["algorithm"]["parameters"]["endQuietDbfs"] = -40
    with pytest.raises(EnvelopeRefused, match="parametersHash"):
        omission_envelope_report(data, "t0", block_of(data))


def test_reviewed_only_consumers_refuse_measured_evidence_explicitly() -> None:
    from vera_timeline_agent.qualification_output_records_v2 import (
        OutputConsistencyError,
    )
    from vera_timeline_agent.qualification_output_v2 import _reviewed_artifact_hash
    from vera_timeline_agent.roundtrip_build import ProofBuildError
    from vera_timeline_agent.roundtrip_v2_audio import reviewed_artifact_hash

    reviewed = {
        "verification": {
            "method": "reviewed_audio_boundaries/v1",
            "reviewArtifactHash": "sha256:" + "a" * 64,
        }
    }
    assert reviewed_artifact_hash(reviewed) == "sha256:" + "a" * 64
    assert _reviewed_artifact_hash(reviewed) == "sha256:" + "a" * 64
    measured = _three()  # measured evidence has no reviewArtifactHash
    with pytest.raises(ProofBuildError, match="reviewed-only"):
        reviewed_artifact_hash(measured)
    with pytest.raises(OutputConsistencyError, match="reviewed-only"):
        _reviewed_artifact_hash(measured)
