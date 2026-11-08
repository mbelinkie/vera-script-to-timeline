"""Prove source-handle APIs and a menu roll never authorize native editing."""

from __future__ import annotations

import pytest
from vera_timeline_agent import resolve_test_bench_non_gui_edit as edit
from vera_timeline_agent import resolve_test_queue as queue


@pytest.mark.parametrize("version", [[21, 1, 1, 10], [21, 1, 2, 10], [22, 0, 0]])
def test_no_false_native_roll_qualification(version: list[int]) -> None:
    probe = {
        "resolveVersion": version,
        "supportsDocumentedOffsetMethods": version >= [21, 1, 2],
        "methodPresent": {
            "original-left:SetLeftOffset": True,
            "original-right:SetRightOffset": True,
        },
        "disposition": "read_only_no_edit_authorized",
    }
    result = edit.assess(probe)
    assert result["canRunEditedM4"] is False
    assert result["state"] == "blocked_no_qualified_non_gui_roll"
    with pytest.raises(queue.QueueError):
        edit.require_qualified_adapter(probe)


def test_forged_proof_or_bad_version_never_authorizes_edit() -> None:
    for probe in (
        {"resolveVersion": "latest"},
        {"resolveVersion": [21, True, 2]},
        {"resolveVersion": [21, 1, 2], "methodPresent": {"SetLeftOffset": "yes"}},
        {"resolveVersion": [21, 1, 2], "disposition": "qualified_gui_roll"},
    ):
        with pytest.raises(queue.QueueError):
            edit.assess(probe)
