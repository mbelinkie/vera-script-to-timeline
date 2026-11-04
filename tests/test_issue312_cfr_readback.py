"""Converted picture readback uses its delivered clock, with exact time guards."""

import copy
import hashlib
import json
from typing import Any

import pytest
from test_workflow_v2 import _fractional_video_proof
from vera_timeline_agent.workflow_v2 import _fractional_source_range_matches


def converted_readback() -> dict[str, Any]:
    event, source, original, timeline, observed, bindings = _fractional_video_proof()
    rate = {"numerator": 30000, "denominator": 1001}
    mapping = original["sourceTimeMapping"]
    frame_map = mapping["sourceFrameMap"]
    frame_map.update(decodedPackageFrameRate=rate, decodedPackageFrameCount=900)
    mapping.update(
        sourceRate=rate, sourceOrigin={"numerator": 1001, "denominator": 1250}
    )
    mapping["mappingHash"] = (
        "sha256:"
        + hashlib.sha256(
            json.dumps(
                mapping, sort_keys=True, ensure_ascii=False, separators=(",", ":")
            ).encode()
        ).hexdigest()
    )
    binding = bindings["video-prep"]
    binding.update(
        mode="derived_cfr",
        profile={
            "profileVersion": "authoring-cfr/v1",
            "toolHash": "sha256:" + "d" * 64,
            "profileHash": "sha256:" + "e" * 64,
        },
        originalSource={"contentHash": "sha256:" + "a" * 64, "probeHash": "probe-hash"},
        requestedRange={
            "sourceInFrame": 24,
            "duration": {"numerator": 107107, "denominator": 12000},
            "preHandle": {"numerator": 0, "denominator": 1},
            "postHandle": {"numerator": 0, "denominator": 1},
        },
    )
    binding["derivation"] = {
        "sourceHash": binding["originalSource"]["contentHash"],
        "outputHash": source["contentHash"],
        "toolHash": binding["profile"]["toolHash"],
        "profileHash": binding["profile"]["profileHash"],
    }
    original["originalHash"] = binding["originalSource"]["contentHash"]
    binding["verification"]["decodedFrameCount"] = 214
    event["sourceRange"] = {"startFrame": 0, "durationFrames": 214}
    event["recordRange"] = {"startFrame": 0, "durationFrames": 214}
    event["v2Event"]["sourceRange"] = {"startFrame": 0, "endFrame": 214}
    observed.update(
        actual_start=0,
        actual_end=212,
        record_duration=214,
        media_properties={"Frames": "214", "FPS": 23.976},
        source_times={
            "GetSourceStartTime": 0.0,
            "GetSourceEndTime": 214 * 1001 / 24000,
        },
    )
    return dict(
        event=event,
        source=source,
        manifest_source=original,
        timeline=timeline,
        preparation_bindings=bindings,
        **observed,
    )


def test_converted_eof_requires_exact_delivered_time_and_receipt_clock() -> None:
    assert _fractional_source_range_matches(**converted_readback())


@pytest.mark.parametrize(
    "drift", ["time", "frames", "origin", "derivation", "mapping", "early_end"]
)
def test_converted_readback_rejects_drift(drift: str) -> None:
    value = copy.deepcopy(converted_readback())
    binding = value["preparation_bindings"]["video-prep"]
    if drift == "time":
        value["source_times"]["GetSourceEndTime"] += 2 / 48000
    elif drift == "frames":
        value["media_properties"]["Frames"] = "215"
    elif drift == "origin":
        binding["timeMapping"]["sourceOrigin"] = {"numerator": 0, "denominator": 1}
    elif drift == "derivation":
        binding["derivation"]["sourceHash"] = "sha256:" + "f" * 64
    elif drift == "mapping":
        binding["timeMapping"]["mappingHash"] = "sha256:" + "f" * 64
    else:
        value["actual_end"] = 211
    assert not _fractional_source_range_matches(**value)
