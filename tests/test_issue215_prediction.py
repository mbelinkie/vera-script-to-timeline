"""Edited holds keep their source identity without an advancing source clock."""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any

import pytest
from test_issue214_prediction import case, change_items, refresh_package_inputs
from vera_timeline_agent import qualification_output_v2 as output
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
    _hash,
)


@pytest.mark.parametrize("phase", ["pristine", "edited", "rebuild"])
@pytest.mark.parametrize("source_start", [0, 1])
def test_extended_held_picture_only_changes_edited_hold_duration(
    phase: str, source_start: int
) -> None:
    c = case(phase=phase)
    snapshot = json.loads(c.inputs.geometry)
    geometry = snapshot["geometry"]
    track = {
        **c.binding["tracks"][0],
        "trackId": "video-1",
        "kind": "video",
        "name": "Held picture",
    }
    c.binding["tracks"].append(track)
    geometry["tracks"] = c.binding["tracks"]
    source_hash = _hash(b"single held picture")
    c.binding["nativeSources"].append(
        {"sourceId": "picture", "nativeSourceSha256": source_hash}
    )
    c.binding["nativeSources"].sort(key=lambda row: row["sourceId"])
    c.binding["delivery"].append(
        {
            "eventId": "picture",
            "kind": "placeholder",
            "recordRange": {"startFrame": 0, "durationFrames": 2},
            "sourceRange": {"startFrame": 0, "durationFrames": 2},
        }
    )
    manifest = json.loads(c.inputs.blobs["manifestSha256"])
    manifest["events"].append(
        {
            "eventId": "picture",
            "kind": "placeholder",
            "trackId": "video-1",
            "recordRange": {"startFrame": 0, "endFrame": 2},
            "provenance": {},
            "pictureTreatment": {"kind": "slate", "text": "Held picture"},
        }
    )
    c.inputs = replace(
        c.inputs,
        geometry=_canonical(snapshot),
        blobs={**c.inputs.blobs, "manifestSha256": _canonical(manifest)},
    )
    refresh_package_inputs(c)
    picture: dict[str, Any] = {
        **geometry["items"][0],
        "itemUid": "picture-item",
        "eventId": "picture",
        "sourceId": "picture",
        "mediaUid": "picture-media",
        "kind": "video",
        "trackId": "video-1",
        "recordDuration": 4,
        "sourceDuration": 4,
        "sourceStart": source_start,
        "sourceMappingSha256": source_hash,
    }
    change_items(
        c, sorted([*geometry["items"], picture], key=lambda row: row["itemUid"])
    )
    if phase == "edited" and source_start == 0:
        predicted = output.create_prediction(c.inputs, trust=c.trust, ledger=[])
        assert predicted.pcm
    else:
        with pytest.raises(OutputConsistencyError, match="outside authenticated event"):
            output.create_prediction(c.inputs, trust=c.trust, ledger=[])
