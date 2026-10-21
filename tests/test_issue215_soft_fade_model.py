"""Pinned Studio 21.1.1 PCM edge model and sample-exact EOF padding."""

from __future__ import annotations

import json
import struct
from array import array
from hashlib import sha256
from typing import Any, cast

import pytest
from test_issue214_prediction import case
from vera_timeline_agent import qualification_output_v2 as output
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
)


def _left(pcm: bytes, sample: int) -> float:
    return float(struct.unpack_from("<d", pcm, sample * 16)[0])


def test_commitment_pins_renderer_model_without_attesting_control_state() -> None:
    c = case()

    intent = output.validate_prediction_intent(c.inputs, trust=c.trust)
    commitment = output.create_prediction(c.inputs, trust=c.trust, ledger=[])
    renderer = cast(dict[str, Any], output.ALGORITHM["renderer"])

    assert output.ALGORITHM["version"] == "qualification-output-fixed-pcm/v2"
    canonical_algorithm = json.dumps(
        output.ALGORITHM,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    assert sha256(canonical_algorithm).hexdigest() == output.ALGORITHM_SHA256
    assert renderer["product"] == "DaVinci Resolve Studio"
    assert renderer["version"] == [21, 1, 1, 10, ""]
    assert renderer["softFades"]["controlState"] == "not_attested"
    assert intent["sources"][0]["segments"][0]["edgeFadeModel"] == (
        output.SOFT_FADE_MODEL
    )
    assert json.loads(commitment.payload.decode("utf-8"))["algorithmSha256"] == (
        output.ALGORITHM_SHA256
    )


def test_linear_72_sample_fades_cover_programme_and_adjacent_clip_edges() -> None:
    frame = output.FRAME
    source = {"one": [array("d", [0.5]) * (2 * frame)]}
    intent = [
        {
            "sourceId": "one",
            "gainDb": 0,
            "segments": [
                {
                    "recordStart": 0,
                    "sampleStart": 0,
                    "sampleCount": frame,
                },
                {
                    "recordStart": 1,
                    "sampleStart": frame,
                    "sampleCount": frame,
                },
            ],
        }
    ]

    predicted = output._mix(intent, source, extent=3)

    assert _left(predicted, 0) == 0
    assert _left(predicted, 36) == pytest.approx(0.25)
    assert _left(predicted, 72) == 0.5
    assert _left(predicted, frame - 72) == 0.5
    assert _left(predicted, frame - 36) == pytest.approx(0.25)
    assert _left(predicted, frame - 1) == pytest.approx(0.5 / 72)
    assert _left(predicted, frame) == 0
    assert _left(predicted, frame + 36) == pytest.approx(0.25)
    assert _left(predicted, frame + 72) == 0.5
    assert _left(predicted, 2 * frame - 1) == pytest.approx(0.5 / 72)
    assert _left(predicted, 2 * frame) == 0


def test_fade_out_ends_at_active_source_eof_before_frame_ceiled_silence() -> None:
    frame = output.FRAME
    active_samples = frame + 17
    source = {"narration": [array("d", [0.5]) * (2 * frame)]}
    intent = [
        {
            "sourceId": "narration",
            "gainDb": 0,
            "segments": [
                {
                    "recordStart": 0,
                    "sampleStart": 0,
                    "sampleCount": active_samples,
                }
            ],
        }
    ]

    predicted = output._mix(intent, source, extent=2)

    assert _left(predicted, active_samples - 72) == 0.5
    assert _left(predicted, active_samples - 36) == pytest.approx(0.25)
    assert _left(predicted, active_samples - 1) == pytest.approx(0.5 / 72)
    assert _left(predicted, active_samples) == 0
    assert _left(predicted, 2 * frame - 1) == 0


def test_pair_edge_mask_uses_fractional_narration_active_eof() -> None:
    frame = output.FRAME
    active_samples = 6 * frame - 17
    c = case(count=active_samples)
    binding = json.loads(c.inputs.input_binding)
    assert binding["sourceEntries"][0]["durationSamples"] == active_samples

    mask = output._clip_edge_exclusion_mask([c.inputs], 6 * frame)

    assert all(mask[:72])
    assert all(mask[active_samples - 72 : active_samples])
    assert not any(mask[active_samples : 6 * frame])


def test_unqualified_overlapping_edge_ramps_refuse_short_clips() -> None:
    intent = [
        {
            "sourceId": "one",
            "gainDb": 0,
            "segments": [{"recordStart": 0, "sampleStart": 0, "sampleCount": 143}],
        }
    ]
    source = {"one": [array("d", [0.5]) * output.FRAME]}

    with pytest.raises(OutputConsistencyError, match="overlapping clip-edge ramps"):
        output._mix(intent, source, extent=1)
