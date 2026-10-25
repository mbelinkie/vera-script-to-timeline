"""The output proof must retain the same qualified converted clock checks."""

import hashlib
from pathlib import Path
from typing import Any

import pytest
from test_issue209_native import _geometry_case
from test_issue312_cfr_readback import converted_readback
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError


def converted_output_case(tmp_path: Path) -> tuple[Any, Any, Any, Any]:
    resolve, request, admitted, item, timeline = _geometry_case(tmp_path)
    value = converted_readback()
    event, source = value["event"], value["source"]
    event.update(
        id="event-one", sourceId="picture-one", trackId="video-main", trackKind="video"
    )
    source.update(
        id="picture-one",
        path="media/shot.mov",
        contentHash="sha256:"
        + hashlib.sha256(item.media.path.read_bytes()).hexdigest(),
    )
    manifest_source = value["manifest_source"]
    manifest_source.update(id=source["id"], deliveredHash=source["contentHash"])
    event["v2Event"]["eventId"] = event["id"]
    event["v2Event"]["provenance"]["sourceId"] = source["id"]
    binding = value["preparation_bindings"]["video-prep"]
    binding["verification"]["deliveredHash"] = source["contentHash"]
    binding["derivation"]["outputHash"] = source["contentHash"]
    admitted["view"]["events"] = [event]
    admitted["view"]["sources"] = [source]
    admitted["manifest"]["events"] = [event["v2Event"]]
    admitted["manifest"]["sources"] = [manifest_source]
    admitted["manifest"]["preparationBindings"] = [binding]
    admitted["manifest"]["timeline"]["durationFrames"] = 214
    item.stamp = native._event_stamp(event)
    item.source_start_frame, item.source_end_frame = 0, 212
    item.media.frame_count = 214
    item.GetSourceStartTime = lambda: 0.0
    item.GetSourceEndTime = lambda: 214 * 1001 / 24000
    item.GetDuration = lambda _: 214
    item.GetEnd = lambda _: 214
    timeline.GetEndFrame = lambda: 214
    request["profile"] = native.MATRIX_PROFILE
    return resolve, request, admitted, item


@pytest.mark.parametrize("observed", [False, True])
def test_output_proof_accepts_authenticated_converted_eof(
    tmp_path: Path, observed: bool
) -> None:
    resolve, request, admitted, item = converted_output_case(tmp_path)
    request["context"]["phase"] = "edited" if observed else "pristine"
    capture = (
        native._capture_observed_geometry if observed else native._capture_geometry
    )
    geometry = capture(resolve, request, admitted, None)
    assert item.GetSourceEndFrame() == 212
    assert geometry["items"][0]["sourceDuration"] == 214


@pytest.mark.parametrize(
    "drift", ["time", "frames", "derivation", "mapping", "early_end"]
)
def test_output_proof_refuses_unbound_converted_eof(tmp_path: Path, drift: str) -> None:
    resolve, request, admitted, item = converted_output_case(tmp_path)
    binding = admitted["manifest"]["preparationBindings"][0]
    if drift == "time":
        item.GetSourceEndTime = lambda: 214 * 1001 / 24000 + 2 / 48000
    elif drift == "frames":
        item.media.frame_count = 215
    elif drift == "derivation":
        binding["derivation"]["sourceHash"] = "sha256:" + "f" * 64
    elif drift == "mapping":
        binding["timeMapping"]["mappingHash"] = "sha256:" + "f" * 64
        item.stamp = native._event_stamp(admitted["view"]["events"][0])
    else:
        item.source_end_frame = 211
    with pytest.raises(OutputConsistencyError, match="native source range differs"):
        native._capture_geometry(resolve, request, admitted, None)
