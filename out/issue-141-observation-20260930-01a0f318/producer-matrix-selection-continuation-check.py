"""Offline checks for the protected-six Matrix selection continuation."""

from __future__ import annotations

import hashlib
import importlib.util
import json
from copy import deepcopy
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE_PATH = HERE / "producer-matrix-selection-continuation.py"
SPEC = importlib.util.spec_from_file_location("producer_matrix_selection", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def main():
    source = MODULE_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "SaveProject",
        "SetCurrentTimecode",
        "SetTrackLock",
        "SetClipsLinked",
        "AddMarker",
        "AppendToTimeline",
        "DeleteClips",
        "StartRendering",
        "Transcribe",
    ):
        assert forbidden not in source, forbidden
    assert source.count(".SetCurrentTimeline(") == 1

    probe, reader = MODULE._modules()
    media = MODULE.ROOT / "out/issue-141-media-20260930-01a0f318"
    manifest = media / "manifest.json"
    config = {
        "mediaDir": str(media),
        "manifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "timelineInventory": MODULE.PROTECTED_INVENTORY,
    }
    _, expected = reader._manifest(config, MODULE.ROOT, probe)
    pair = MODULE._pin(
        HERE, MODULE.PRIOR_PAIR, MODULE.PRIOR_PAIR_SHA256, reader, probe
    )
    state, pool = MODULE._pair_content(pair, reader, probe, expected)
    assert len(state["timelines"]) == 6
    assert len(pool["items"]) == 13
    evidence = MODULE._source_evidence(pair, expected)
    assert evidence["protectedSourceStatus"] == "protected-locator-not-accessed"
    assert evidence["protectedSourceEvidenceCount"] == 14
    assert evidence["generatedReachableEvidenceCount"] == 280

    base = {
        "productName": {"state": "value", "value": "DaVinci Resolve Studio"},
        "version": {"state": "value", "value": MODULE.BUILD},
        "project": {
            "GetUniqueId": {"state": "value", "value": MODULE.PROJECT_ID},
            "GetName": {"state": "value", "value": MODULE.PROJECT_NAME},
        },
        "currentTimeline": {
            "getter": {"state": "value", "value": {"repr": "<before>"}},
            "identity": {
                "GetUniqueId": {"state": "value", "value": MODULE.PRIOR_UID},
                "GetName": {"state": "value", "value": MODULE.PRIOR_NAME},
            },
        },
        "playhead": {"state": "value", "value": "01:00:10:05"},
        "currentPage": {"state": "value", "value": "edit"},
        "formatCodec": {
            "state": "value",
            "value": {"format": "mov", "codec": "H264"},
        },
        "jobs": {"state": "value", "value": []},
        "rendering": {"state": "value", "value": False},
    }
    after = deepcopy(base)
    after["currentTimeline"]["getter"]["value"]["repr"] = "<after>"
    after["currentTimeline"]["identity"]["GetUniqueId"]["value"] = MODULE.MATRIX_UID
    after["currentTimeline"]["identity"]["GetName"]["value"] = MODULE.MATRIX_NAME
    after["playhead"]["value"] = "00:01:37:24"
    MODULE._selection_context_is_safe(base, after)
    assert any(
        row["path"] == "/currentTimeline/getter/value/repr"
        for row in MODULE._context_differences(base, after)
    )
    invalid = deepcopy(after)
    invalid["jobs"]["value"] = [{"renderJob": "unexpected"}]
    try:
        MODULE._selection_context_is_safe(base, invalid)
    except RuntimeError:
        pass
    else:
        raise AssertionError("queue drift was accepted")

    r2 = MODULE._result_config(
        {"mediaDir": str(media), "manifestSha256": config["manifestSha256"]},
        HERE,
        {"path": "after-pair.json", "sha256": "after"},
    )
    assert r2["action"] == "editorial-case-prepare"
    assert r2["case"] == "R2-picture"
    assert r2["timelineInventory"] == MODULE.PROTECTED_INVENTORY
    assert r2["priorPair"] == "after-pair.json"
    assert r2["sourceReview"]["probe.py"] == MODULE.PROBE_SHA256
    assert r2["sourceReview"]["r4-range-repair.py"] == MODULE.READER_SHA256

    result = {
        "status": "passed",
        "pinnedPairSha256": MODULE.PRIOR_PAIR_SHA256,
        "protectedTimelineCount": len(state["timelines"]),
        "protectedPoolItemCount": len(pool["items"]),
        "protectedSourceEvidenceCount": evidence["protectedSourceEvidenceCount"],
        "generatedReachableEvidenceCount": evidence["generatedReachableEvidenceCount"],
        "oneSelectionSetter": True,
        "mutationTokensAbsent": True,
        "r2PictureConfigShape": True,
    }
    artifact = HERE / "producer-matrix-selection-continuation-local-check.json"
    artifact.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()

