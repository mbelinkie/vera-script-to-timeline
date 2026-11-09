"""Strict non-GUI 327→351 edit-route admission for Test Bench.

The Resolve 21.1.1 SDK has no supported in-place roll edit; 21.1.2's
SetLeftOffset/SetRightOffset edit *source handles*, not the adjacent edit
boundary, and at least one Studio report found destructive results despite
a True return.  ImportTimelineFromFile creates a new timeline and cannot
preserve the existing timeline/item UIDs.  None satisfies M4's same-target
requirement.  A menu/AppleScript/keyboard/console workaround is not an SDK
adapter.  Do not auto-promote a read-only capability probe into authority
to modify an existing clip.

This guard deliberately cannot issue an editing command. A future independent
single-use sacrificial Studio trial and reviewed UID-preserving native adapter
must be added *separately* before a real M4 stage can use that route.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from . import resolve_test_queue as queue


def assess(probe: Mapping[str, Any]) -> dict[str, Any]:
    """Classify verified read-only capability; never infer a roll setter."""
    version = probe.get("resolveVersion")
    if (
        not isinstance(version, list)
        or not (
            (3 <= len(version) <= 4 and all(type(part) is int for part in version))
            or (
                len(version) == 5
                and all(type(part) is int for part in version[:4])
                and type(version[4]) is str
                and len(version[4]) <= 128
            )
        )
        or not all(0 <= part < 100000 for part in version[: min(4, len(version))])
    ):
        raise queue.QueueError("Test Bench: authenticated Resolve version required")
    observed = probe.get("methodPresent")
    if observed is not None and (
        not isinstance(observed, dict)
        or not all(
            isinstance(name, str) and type(v) is bool for name, v in observed.items()
        )
    ):
        raise queue.QueueError("Test Bench: malformed native method inventory")
    if probe.get("disposition") not in (None, "read_only_no_edit_authorized"):
        raise queue.QueueError("Test Bench: unexpected native edit-probe disposition")
    if version[:3] < [21, 1, 2]:
        reason = "Studio SDK version has no documented in-place edit-boundary API"
    else:
        reason = (
            "offset setters are source-handle edits, not a qualified UID-preserving "
            "two-clip roll; imported timelines replace native UIDs"
        )
    return {
        "state": "blocked_no_qualified_non_gui_roll",
        "canRunEditedM4": False,
        "resolveVersion": list(version),
        "reason": reason,
        "requires": (
            "independent disposable same-version native-only trial; exact "
            "saved/reopened item/media/audio UID and boundary readback; "
            "reviewed source/approval pins and one-use intent"
        ),
    }


def require_qualified_adapter(probe: Mapping[str, Any]) -> None:
    """A read-only probe, a successful GUI edit, or import is NEVER an adapter."""
    decision = assess(probe)
    raise queue.QueueError("Test Bench: " + str(decision["reason"]))
