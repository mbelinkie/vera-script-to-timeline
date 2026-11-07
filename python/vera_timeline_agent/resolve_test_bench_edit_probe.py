"""Read-only, exact-UID Resolve 21 timeline-edit capability probe for #473.

This module NEVER calls timeline setters, imports media, opens a project, or
claims native M4 evidence. It inspects an already selected, provisioned
disposable target against the authenticated pristine v2 host readback.

Resolve 21.1.2 added SetLeftOffset/SetRightOffset, but a published empirical
report describes destructive SetLeftOffset behavior even when it returns True.
Method presence is NOT evidence that either method performs a correct roll.
The target stays edit-blocked until an independent disposable qualification
proves exact UID-preserving before/after geometry and the approved host verifies
the complete edited native capture.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import resolve_test_bench_carrier as carrier
from . import resolve_test_queue as queue
from .resolve_test_queue_reverse import BEFORE_BOUNDARY, EXPECTED_EXTENT, EXPECTED_RATE

SCHEMA = "vera.test-bench-edit-capability/v1"
MIN_OFFSET_VERSION = (21, 1, 2)
MAX_NATIVE_ITEMS = 64


class EditProbeRefusal(ValueError):
    """Untrusted, changed or unsupported read-only edit target."""


def _require(value: bool, message: str) -> None:
    if not value:
        raise EditProbeRefusal(message)


def _item_rows(geometry: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    rows = geometry.get("items")
    _require(
        isinstance(rows, list) and len(rows) == 11,
        "11 authenticated items required",
    )
    assert isinstance(rows, list)
    found: dict[str, dict[str, Any]] = {}
    for row in rows:
        _require(isinstance(row, dict), "unrecognized geometry item")
        assert isinstance(row, dict)
        uid = row.get("itemUid")
        _require(
            isinstance(uid, str) and bool(uid) and uid not in found,
            "duplicate/invalid item UID",
        )
        assert isinstance(uid, str)
        found[uid] = row
    return found


def _boundary(geometry: Mapping[str, Any]) -> tuple[str, str]:
    _require(
        geometry.get("rate") == EXPECTED_RATE
        and type(geometry.get("extentFrames")) is int
        and geometry["extentFrames"] == EXPECTED_EXTENT,
        "not the qualified 1407-frame programme",
    )
    items = _item_rows(geometry)
    lefts = [
        row
        for row in items.values()
        if row.get("kind") == "video"
        and type(row.get("recordStart")) is int
        and type(row.get("recordDuration")) is int
        and row["recordStart"] + row["recordDuration"] == BEFORE_BOUNDARY
    ]
    _require(len(lefts) == 1, "original 327 boundary left item is ambiguous")
    left = lefts[0]
    rights = [
        row
        for row in items.values()
        if row.get("kind") == "video"
        and row.get("recordStart") == BEFORE_BOUNDARY
        and row.get("trackId") == left.get("trackId")
        and row.get("eventId") != left.get("eventId")
        and type(row.get("recordDuration")) is int
        and row["recordDuration"] > 24
    ]
    _require(len(rights) == 1, "original 327 boundary right item is ambiguous")
    right = rights[0]
    _require(
        type(left.get("sourceDuration")) is int
        and type(right.get("sourceDuration")) is int
        and right["sourceDuration"] > 24
        and type(right.get("sourceStart")) is int,
        "qualified source ranges not available",
    )
    return left["itemUid"], right["itemUid"]


def inspect_selected(
    resolve: Any, target: Mapping[str, str], pristine_geometry: Mapping[str, Any]
) -> dict[str, Any]:
    """No mutation; reads an exact already selected disposable native target."""
    from .resolve_test_queue_m4 import _target as validate_target

    target = validate_target(dict(target), "selected probe target")
    left, right = _boundary(pristine_geometry)
    _require(
        pristine_geometry.get("context", {}).get("target") == target,
        "baseline geometry target differs",
    )
    manager = resolve.GetProjectManager()
    _require(manager is not None, "Resolve project manager is unavailable")
    project = manager.GetCurrentProject()
    _require(project is not None, "no selected project")
    timeline = project.GetCurrentTimeline()
    _require(timeline is not None, "no selected timeline")
    _require(
        project.GetUniqueId() == target["projectUid"]
        and project.GetName() == target["projectName"]
        and timeline.GetUniqueId() == target["timelineUid"]
        and timeline.GetName() == target["timelineName"]
        and project.IsRenderingInProgress() is False,
        "selected project/UID/idle state differs",
    )
    version = resolve.GetVersion()
    _require(
        isinstance(version, (tuple, list))
        and len(version) >= 3
        and all(type(value) is int and 0 <= value < 100000 for value in version)
        and version[0] >= 21,
        "Resolve Studio version cannot be authenticated",
    )
    tracks = pristine_geometry.get("tracks")
    _require(
        isinstance(tracks, list) and len(tracks) == 6,
        "six original tracks required",
    )
    assert isinstance(tracks, list)
    expected_slots: dict[tuple[str, int], dict[str, Any]] = {}
    for spec in tracks:
        _require(isinstance(spec, dict), "unrecognized native track")
        assert isinstance(spec, dict)
        kind, index = spec.get("kind"), spec.get("index")
        _require(
            kind in {"video", "audio"}
            and type(index) is int
            and 1 <= index <= 64
            and (kind, index) not in expected_slots,
            "invalid native track identity",
        )
        assert isinstance(kind, str) and isinstance(index, int)
        expected_slots[(kind, index)] = spec
    expected = _item_rows(pristine_geometry)
    observed: dict[str, dict[str, Any]] = {}
    capabilities: dict[str, bool] = {}
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        _require(
            type(count) is int
            and 0 <= count <= 64
            and count
            == max((idx for k, idx in expected_slots if k == kind), default=0),
            "native track inventory differs before any edit",
        )
        for index in range(1, count + 1):
            slot = expected_slots.get((kind, index))
            _require(slot is not None, "unmapped timeline track")
            assert slot is not None
            _require(
                timeline.GetTrackName(kind, index) == slot["name"]
                and timeline.GetIsTrackEnabled(kind, index) == slot["enabled"]
                and timeline.GetIsTrackLocked(kind, index) == slot["locked"],
                "native track state differs before edit",
            )
            items = timeline.GetItemListInTrack(kind, index)
            _require(
                isinstance(items, (tuple, list)) and len(items) <= MAX_NATIVE_ITEMS,
                "native item inventory unreadable/too large",
            )
            for item in items:
                uid = item.GetUniqueId()
                _require(
                    type(uid) is str and uid in expected and uid not in observed,
                    "unexpected or duplicate timeline item UID",
                )
                row = expected[uid]
                media = item.GetMediaPoolItem()
                _require(media is not None, "native media UID unavailable")
                links = item.GetLinkedItems()
                _require(isinstance(links, (tuple, list)), "native links unreadable")
                actual = {
                    "kind": kind,
                    "trackId": slot["trackId"],
                    "recordStart": item.GetStart(False),
                    "recordDuration": item.GetDuration(False),
                    "mediaUid": media.GetUniqueId(),
                    "linkedItemUids": sorted(peer.GetUniqueId() for peer in links),
                }
                _require(
                    actual == {key: row[key] for key in actual}
                    and type(actual["recordStart"]) is int
                    and type(actual["recordDuration"]) is int,
                    "native clip identity/range differs before edit",
                )
                observed[uid] = actual
                if uid in {left, right}:
                    for method in ("SetLeftOffset", "SetRightOffset", "SetPosition"):
                        key = f"{uid}:{method}"
                        capabilities[key] = callable(getattr(item, method, None))
    _require(observed.keys() == expected.keys(), "missing native clip UID")
    return {
        "schema": SCHEMA,
        "disposition": "read_only_no_edit_authorized",
        "target": dict(target),
        "geometrySha256": hashlib.sha256(
            queue.canonical(pristine_geometry)
        ).hexdigest(),
        "resolveVersion": list(version),
        "supportsDocumentedOffsetMethods": tuple(version[:3]) >= MIN_OFFSET_VERSION,
        "leftItemUid": left,
        "rightItemUid": right,
        "methodPresent": capabilities,
        "warning": (
            "SetLeftOffset/SetRightOffset are unqualified and must not be called"
        ),
    }


def inspect_pristine(
    root: Path,
    *,
    session_path: Path,
    session_sha256: str,
    capture_path: Path,
    capture_sha256: str,
) -> dict[str, Any]:
    """Read-only native capability inspection after signed pristine acceptance."""
    from .qualification_output_controller_v2 import load_output_session
    from .qualification_output_native_v2 import verify_native_result
    from .qualification_output_proof_v2 import _load_terminal_output_with_comparison
    from .resolve_native_owner import (
        _local_resolve_connection,
        native_owner,
        preflight_selected_disposable,
    )

    carrier._private(root, create=True)
    previous = root / "edit-capability-probe.json"
    session = load_output_session(session_path, session_sha256)
    _require(session.context.get("phase") == "pristine", "pristine session required")
    _load_terminal_output_with_comparison(session)
    capture = verify_native_result(capture_path, capture_sha256)
    _require(
        capture.get("status") == "complete"
        and capture.get("action") == "capture_post"
        and capture.get("context") == session.context
        and capture.get("target") == session.context.get("target")
        and isinstance(capture.get("nativeGeometry"), dict),
        "authenticated native pristine capture required",
    )
    refs = {
        "session": {"path": str(session_path), "sha256": session_sha256},
        "capture": {"path": str(capture_path), "sha256": capture_sha256},
    }
    if previous.exists() or previous.is_symlink():
        saved = json.loads(carrier._read(previous, 32 * 1024))
        _require(
            isinstance(saved, dict)
            and saved.get("schema") == SCHEMA
            and all(saved.get(key) == ref for key, ref in refs.items())
            and saved.get("geometrySha256")
            == hashlib.sha256(queue.canonical(capture["nativeGeometry"])).hexdigest(),
            "saved probe refers to another source or native identity",
        )
        assert isinstance(saved, dict)
        return saved
    target = session.context["target"]
    # This read-only guard acquires and releases its own owner lock.
    preflight_selected_disposable(target, require_empty=False)
    with native_owner(output_lane=True):
        resolve = _local_resolve_connection()
        _require(resolve is not None, "Resolve Local scripting unavailable")
        report = inspect_selected(resolve, target, capture["nativeGeometry"])
    report.update(refs)
    carrier._once(previous, queue.canonical(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--session", type=Path, required=True)
    parser.add_argument("--session-sha256", required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--capture-sha256", required=True)
    args = parser.parse_args()
    try:
        record = inspect_pristine(
            args.root,
            session_path=args.session,
            session_sha256=args.session_sha256,
            capture_path=args.capture,
            capture_sha256=args.capture_sha256,
        )
        print(json.dumps(record, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print(json.dumps({"state": "blocked", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
