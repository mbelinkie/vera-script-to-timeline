#!/usr/bin/env python3
"""Read-only, UID-pinned Studio getter proof for the genuine #472 M4 trial.

Uses the independently authenticated original construct result as the target
identity. One readback before and one after native save_reopen; no SDK edits,
imports, saves, or project navigation. Evidence is write-once and private.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from vera_timeline_agent.qualification_output_controller_v2 import load_output_session
from vera_timeline_agent.qualification_output_native_v2 import (
    native_request_paths,
    verify_native_result,
)
from vera_timeline_agent.resolve_native_owner import (
    _local_resolve_connection,
    native_owner,
)

ROOT = Path.home() / ".local/state/vera/issue-472-guarded-m4-05"
EVENT = "f5871317-bdb5-558b-8c05-6ed0fe4b6889"
DELIVERED_SHA = "803b9a7375d1da5aa52ecac6a9c02071891d8bcb59fddde22410e37f514ce023"


def require(condition: bool, reason: str) -> None:
    if not condition:
        raise RuntimeError(reason)


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while block := f.read(1024 * 1024):
            sha.update(block)
    return sha.hexdigest()


def authenticated_result(context: dict[str, Any], sequence: int) -> dict[str, Any]:
    path, _, _, _ = native_request_paths(context, sequence)
    require(
        path.is_file() and not path.is_symlink(), "signed native result unavailable"
    )
    verified = verify_native_result(path, digest(path))
    require(
        verified.get("status") == "complete"
        and verified.get("sequence") == sequence
        and verified.get("context") == context,
        "native result does not authenticate the current target and sequence",
    )
    return verified


def main(stage: str) -> int:
    require(stage in {"before", "after"}, "only before/after readback stages")
    output = ROOT / f"verified-live-readback-{stage}.json"
    require(
        not output.exists() and not output.is_symlink(), "readback already recorded"
    )
    pin_path = ROOT / "setup-pin.json"
    require(pin_path.is_file() and not pin_path.is_symlink(), "session pin absent")
    pin = json.loads(pin_path.read_bytes())
    context_controller = load_output_session(
        Path(pin["session"]["path"]), pin["session"]["sha256"]
    )
    context = context_controller.context
    target = context["target"]
    require(target == pin["target"], "session target differs from provision receipt")
    construct = authenticated_result(context, 0)
    wanted = next(
        (
            item
            for item in construct["nativeGeometry"]["items"]
            if item["eventId"] == EVENT
        ),
        None,
    )
    require(isinstance(wanted, dict), "signed native event missing")
    require(
        wanted["recordStart"] == 715
        and wanted["recordDuration"] == 214
        and wanted["sourceStart"] == 0
        and wanted["sourceDuration"] == 214,
        "authenticated expected video source bounds differ",
    )
    if stage == "after":
        reopened = authenticated_result(context, 1)
        require(
            reopened.get("action") == "save_reopen"
            and reopened.get("nativeGeometry") == construct["nativeGeometry"],
            "the actual M4 save/reopen verifier did not retain native geometry",
        )
    with native_owner(output_lane=True):
        resolve = _local_resolve_connection()
        require(resolve is not None, "installed Resolve SDK unavailable")
        require(
            resolve.GetProductName() == "DaVinci Resolve Studio",
            "Studio identity changed",
        )
        manager = resolve.GetProjectManager()
        project = manager.GetCurrentProject()
        require(
            project is not None
            and project.GetUniqueId() == target["projectUid"]
            and project.GetName() == target["projectName"],
            "the currently selected project is not the exact new disposable target",
        )
        timeline = project.GetCurrentTimeline()
        require(
            timeline is not None
            and timeline.GetUniqueId() == target["timelineUid"]
            and timeline.GetName() == target["timelineName"],
            "the selected timeline UID differs from admission",
        )
        items = timeline.GetItemListInTrack("video", 1)
        require(isinstance(items, (list, tuple)), "native video track unreadable")
        matches = [item for item in items if item.GetUniqueId() == wanted["itemUid"]]
        require(len(matches) == 1, "the exact event clip is absent or duplicated")
        item = matches[0]
        media = item.GetMediaPoolItem()
        require(media is not None, "native media pool item disappeared")
        props = media.GetClipProperty()
        require(isinstance(props, dict), "native media properties unavailable")
        path = Path(str(props.get("File Path")))
        require(
            path.is_file() and not path.is_symlink() and digest(path) == DELIVERED_SHA,
            "media content differs from the admitted decoded MP4 hash",
        )
        row = {
            "stage": stage,
            "eventId": EVENT,
            "itemUid": item.GetUniqueId(),
            "recordStart": item.GetStart(False),
            "recordDuration": item.GetDuration(False),
            "recordEnd": item.GetEnd(False),
            "sourceStartFrame": item.GetSourceStartFrame(),
            "sourceEndFrame": item.GetSourceEndFrame(),
            "sourceStartTime": item.GetSourceStartTime(),
            "sourceEndTime": item.GetSourceEndTime(),
            "mediaFrames": props.get("Frames"),
            "mediaFPS": props.get("FPS"),
            "mediaSha256": DELIVERED_SHA,
            "speed": item.GetSpeed(),
            "projectUid": project.GetUniqueId(),
            "timelineUid": timeline.GetUniqueId(),
            "constructSha256": digest(native_request_paths(context, 0)[0]),
            "nativeEffects": False,
        }
    require(
        row["itemUid"] == wanted["itemUid"]
        and row["recordStart"] == 715
        and row["recordDuration"] == 214
        and row["recordEnd"] == 929
        and row["sourceStartFrame"] == 0
        and row["sourceEndFrame"] == 212
        and row["sourceStartTime"] == 0
        and abs(row["sourceEndTime"] - 214 * 1001 / 24000) <= 1 / 48000
        and str(row["mediaFrames"]) == "214"
        and abs(float(row["mediaFPS"]) - 23.976) < 0.00001
        and isinstance(row["speed"], dict)
        and row["speed"].get("Percentage") == 100.0,
        "physical supported EOF/record/decoded-media equivalence not established",
    )
    data = json.dumps(row, sort_keys=True).encode() + b"\n"
    fd = os.open(output, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    print(data.decode().strip())
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: issue-472-verified-live-readback.py before|after")
    raise SystemExit(main(sys.argv[1]))
