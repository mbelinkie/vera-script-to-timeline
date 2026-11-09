#!/usr/bin/env python3
"""#499 Phase 14: exact-case, no-effect SDK observer for a *spent* calibration.

This is not an M4 host, an edit actor, or a way to resume the one-use Roll.
The only live entry point requires --execute-readonly and a pinned script digest.
It never selects, loads, saves, edits, activates or launches a Resolve project.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
from collections.abc import Callable, Mapping
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent import resolve_native_owner as owner
from vera_timeline_agent.resolve_test_bench_full_loop import _source_hash

CASE_NAME = "VERA Delivery 75ba39c0-4c56-4d85-ac88-58f0092163a8 c191e694fc19"
ROOT = Path.home() / ".local/state/vera/issue-499-one-roll-75ba39c0-v2"
AUTH = ROOT.with_name(ROOT.name + "-authority.json")
SOURCE_GRAPH = "54ffaaeef7d5f21a631f9aa478a98c431e0cd3e0a9831f454306b170b5821ba1"
BASE_COMMIT = "bbe5c64be58e0c841a985ea6a5aed41b3372a873"
CALIBRATION_COMMIT = "b613cab5b960ce0d750fd33ef9e598fb4f67ae05"
SCRIPT_HASHES = {  # 64-character cryptographic source pins
    "issue-499-direct-roll-calibration.py": (
        "4ea491efbdc6f182ba7f5b9fc8e2e53ddbc1ebfc154dd93ab28b9565e41e3f21"
    ),
    "issue-499-direct-roll-setup.applescript": (
        "09b7db76c40ef97e6c6bbe084b23c2611e058d92dea203023aa0290a095aa2c2"
    ),
    "issue-499-direct-roll-once.applescript": (
        "606923e3b61c7e760ff05795b79dce61e490799f5878bdb372a3e2c41af747f5"
    ),
}
# Physical Mac v2 case evidence hashed independently in Phase 12. Not generic input.
EVIDENCE_HASHES = {
    "authority": "90f940db0a68a45a6bc87cdb13b35538ec5fdf9e237da55ca159573ee349887e",
    "pristine.json": "5bf0c3cdebaf00842d931fb2df42fe927c8696141f9bdcd976ce1c90d94f5b13",
    "post-roll-observation.json": (
        "43b71e07a80d72267d6eaafedb5f72a5aed11d0f9f47ac3781918a34207b692f"
    ),
    "reopened.json": "6cf4f362a3a967f031de2c3608300966f48a3d81edfdd6d59d8cd44d253603a8",
    "roll-intent.json": (
        "4bd3147be80af2858a1f2c4897a354c231b839dd02a7f6aa4328eeec70b15fba"
    ),
    "saved.json": "170b1afde5eac64a80d0694751b8f8d5f6ce4173d4d855678371e65336031c26",
    "closed.json": "8333c0de38ce68737cddaa47ec8099d649b9f3b82b832cec85351dd5aee0ab43",
}
ASSET_HASHES = {
    "root.mp4": "d6034a9089ac8b38a011d418fe09472c49fb5133fc2da0ce6ad0ad538cfc1f3f",
    "overlay.mp4": "913b4c2369c7108ab883549a4d07f265b4bb769939df3fdbbba1775a2a8a3581",
    "audio.wav": "e6174f86733a988dc3680989b503db2a34173e55326eb79490c2a95deeabad15",
}
EXPECTED_TRACKS = (
    ("video", 1, "Root"),
    ("video", 2, "Overlay"),
    ("video", 3, "Presenter"),
    ("video", 4, "Placeholder"),
    ("video", 5, "Markers"),
    ("audio", 1, "Narration"),
)
HEX = re.compile(r"[0-9a-f]{64}\Z")


class Refusal(ValueError):
    """Unknown or mismatched evidence, source, owner, SDK or active project."""


def need(condition: bool, reason: str) -> None:
    if not condition:
        raise Refusal(reason)


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
    ).encode()


def private_file(path: Path, expected: str) -> dict[str, Any]:
    need(path.is_file() and not path.is_symlink(), "missing/unsafe pinned evidence")
    meta = path.stat()
    need(
        meta.st_uid == os.getuid() and stat.S_IMODE(meta.st_mode) == 0o600,
        "pinned evidence not private",
    )
    raw = path.read_bytes()
    need(len(raw) <= 40000 and sha(raw) == expected, "pinned evidence bytes differ")
    obj = json.loads(raw)
    need(type(obj) is dict and canonical(obj) == raw, "pinned evidence not canonical")
    return cast(dict[str, Any], obj)


def case_evidence(root: Path = ROOT, authority: Path = AUTH) -> dict[str, Any]:
    """Offline-only validation; performs no SDK lookup or side effect."""
    need(root.is_dir() and not root.is_symlink(), "v2 private case unavailable")
    meta = root.stat()
    need(
        meta.st_uid == os.getuid() and stat.S_IMODE(meta.st_mode) == 0o700,
        "v2 case root not private",
    )
    auth = private_file(authority, EVIDENCE_HASHES["authority"])
    need(
        auth
        == {
            "schema": "vera.issue499.direct-roll-calibration.authority/v1",
            "projectName": CASE_NAME,
            "baseCommit": BASE_COMMIT,
            "checkoutCommit": CALIBRATION_COMMIT,
            "sourceGraphSha256": SOURCE_GRAPH,
            "pythonSha256": SCRIPT_HASHES["issue-499-direct-roll-calibration.py"],
            "setupSha256": SCRIPT_HASHES["issue-499-direct-roll-setup.applescript"],
            "rollSha256": SCRIPT_HASHES["issue-499-direct-roll-once.applescript"],
            "authorized": (
                "one_new_disposable_project_and_at_most_one_roll_start_to_playhead"
            ),
        },
        "authority is not the original one-case v2 authority",
    )
    evidence = {
        key: private_file(root / key, digest)
        for key, digest in EVIDENCE_HASHES.items()
        if key != "authority"
    }
    before = evidence["pristine.json"]
    post = evidence["post-roll-observation.json"]
    reopened = evidence["reopened.json"]
    target = before.get("target")
    need(
        type(target) is dict
        and set(target) == {"projectUid", "timelineUid", "folder"}
        and all(type(target[k]) is str for k in target)
        and target["projectUid"]
        and target["timelineUid"]
        and target["projectUid"] != target["timelineUid"],
        "target UID invalid",
    )
    need(
        before.get("sourceCommit") == BASE_COMMIT
        and before.get("graph") == SOURCE_GRAPH
        and before.get("assets") == ASSET_HASHES
        and post.get("target") == target
        and reopened.get("target") == target
        and post.get("before") == before.get("native")
        and post.get("after") == reopened.get("native")
        and post.get("readError") is None
        and evidence["saved.json"] == {"target": target, "saved": True}
        and evidence["closed.json"] == {"target": target, "closed": True},
        "original one-use snapshots / saved identity differ",
    )
    intent = evidence["roll-intent.json"]
    need(
        intent.get("target") == target
        and intent.get("from") == 327
        and intent.get("to") == 351
        and intent.get("scriptSha256")
        == SCRIPT_HASHES["issue-499-direct-roll-once.applescript"]
        and intent.get("baselineSha256") == EVIDENCE_HASHES["pristine.json"],
        "one-use Roll intent not authentically consumed",
    )
    return {
        "target": target,
        "before": before["native"],
        "reopened": reopened["native"],
    }


def script_and_source_attested(source_hash: Callable[[], str] = _source_hash) -> None:
    need(
        source_hash() == SOURCE_GRAPH, "current verified 245-file source graph differs"
    )
    for name, expected in SCRIPT_HASHES.items():
        path = Path(__file__).resolve().parent / name
        need(
            path.is_file()
            and not path.is_symlink()
            and sha(path.read_bytes()) == expected,
            "original one-use actor/calibration source changed",
        )


def selected(resolve: Any, target: Mapping[str, str]) -> tuple[Any, Any]:
    need(resolve.GetVersion() == [21, 1, 1, 10, ""], "Studio build changed")
    manager = resolve.GetProjectManager()
    need(manager is not None, "SDK project manager unavailable")
    project = manager.GetCurrentProject()
    need(project is not None, "v2 calibration is not already selected; do not load it")
    timeline = project.GetCurrentTimeline()
    need(
        timeline is not None
        and project.GetName() == CASE_NAME
        and timeline.GetName() == CASE_NAME
        and project.GetUniqueId() == target["projectUid"]
        and timeline.GetUniqueId() == target["timelineUid"]
        and manager.GetCurrentFolder() == target["folder"]
        and project.IsRenderingInProgress() is False,
        "current project/timeline/folder/render state is not the saved v2 case",
    )
    return project, timeline


def snapshot(timeline: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Read the same 11-item geometry as the original calibration, no SDK setters."""
    need(
        all(
            type(timeline.GetTrackCount(kind)) is int
            and timeline.GetTrackCount(kind) == count
            for kind, count in (("video", 5), ("audio", 1), ("subtitle", 0))
        ),
        "six-track count differs",
    )
    tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    bound: dict[str, Any] = {}
    for kind, index, name in EXPECTED_TRACKS:
        locked = timeline.GetIsTrackLocked(kind, index)
        need(
            type(locked) is bool
            and locked is ((kind, index) != ("video", 1))
            and timeline.GetTrackName(kind, index) == name,
            "track lock/name differs",
        )
        tracks.append({"kind": kind, "index": index, "name": name, "locked": locked})
        clips = timeline.GetItemListInTrack(kind, index)
        need(
            type(clips) in {tuple, list} and len(clips) <= 11,
            "clip inventory unreadable",
        )
        for item in clips:
            media = item.GetMediaPoolItem()
            links = item.GetLinkedItems()
            need(
                media is not None and type(links) in {list, tuple},
                "media/links unreadable",
            )
            uid = item.GetUniqueId()
            row = {
                "uid": uid,
                "mediaUid": media.GetUniqueId(),
                "kind": kind,
                "track": index,
                "recordStart": item.GetStart(False),
                "recordDuration": item.GetDuration(False),
                "sourceStart": item.GetSourceStartFrame(),
                "sourceEnd": item.GetSourceEndFrame(),
                "links": sorted(peer.GetUniqueId() for peer in links),
            }
            need(
                type(uid) is str
                and uid not in bound
                and type(row["mediaUid"]) is str
                and bool(row["mediaUid"])
                and all(
                    type(row[key]) is int
                    for key in (
                        "recordStart",
                        "recordDuration",
                        "sourceStart",
                        "sourceEnd",
                    )
                ),
                "clip identity or range unreadable",
            )
            bound[uid] = item
            items.append(row)
    items.sort(
        key=lambda row: (row["kind"], row["track"], row["recordStart"], row["uid"])
    )
    need(len(items) == len(bound) == 11, "exact 11-UID inventory missing")
    return {"tracks": tracks, "items": items}, bound


def redacted(value: str, authority_sha: str) -> str:
    return sha((authority_sha + ":" + value).encode())


def source_time(item: Any, method_name: str) -> dict[str, Any]:
    getter = getattr(item, method_name, None)
    if not callable(getter):
        return {"available": False, "raw": None}
    raw = getter()
    if type(raw) is float:
        need(math.isfinite(raw), "source time getter nonfinite")
    need(
        raw is None
        or type(raw) in {int, float}
        or (
            type(raw) is str
            and len(raw) <= 48
            and bool(re.fullmatch(r"[-+0-9.eE]+", raw))
        ),
        "source time getter unsupported (not normalized)",
    )
    return {"available": True, "raw": raw}


def detail(
    item: Any, expected: Mapping[str, Any], root: Path, authority_sha: str
) -> dict[str, Any]:
    media = item.GetMediaPoolItem()
    need(
        media is not None and media.GetUniqueId() == expected["mediaUid"],
        "V1 media UID changed during detailed read",
    )
    props = media.GetClipProperty()
    need(type(props) is dict, "clip properties unreadable")
    path, frames, fps = props.get("File Path"), props.get("Frames"), props.get("FPS")
    sdk_type = props.get("Type")
    assets_dir = root / "assets"
    expected_path = assets_dir / "root.mp4"
    need(
        type(path) is str
        and bool(path)
        and Path(path) == expected_path
        and assets_dir.is_dir()
        and not assets_dir.is_symlink()
        and stat.S_IMODE(assets_dir.stat().st_mode) == 0o700
        and not expected_path.is_symlink()
        and expected_path.is_file()
        and sha(expected_path.read_bytes()) == ASSET_HASHES["root.mp4"],
        "V1 media file does not match pinned internal H.264 source",
    )
    try:
        measured_fps = Decimal(str(fps))
    except InvalidOperation as error:
        raise Refusal("media FPS unavailable") from error
    need(
        type(frames) is str
        and frames.isdecimal()
        and int(frames) == 720
        and type(fps) in {str, int, float}
        and measured_fps.is_finite()
        and abs(measured_fps - Decimal(24000) / Decimal(1001)) < Decimal("0.01")
        and (sdk_type is None or sdk_type in {"Video", "Video + Audio", "Video Only"})
        and type(props.get("Online Status")) is str
        and props["Online Status"] == "Online",
        "media frames/FPS/online status differs",
    )
    row = {
        "GetStartFalse": item.GetStart(False),
        "GetDurationFalse": item.GetDuration(False),
        "GetEndFalse": item.GetEnd(False),
        "GetStartTrue": item.GetStart(True),
        "GetDurationTrue": item.GetDuration(True),
        "GetEndTrue": item.GetEnd(True),
        "GetSourceStartFrame": item.GetSourceStartFrame(),
        "GetSourceEndFrame": item.GetSourceEndFrame(),
    }
    need(
        all(type(v) is int for v in row.values()),
        "record/source frame getter unavailable",
    )
    need(
        row["GetStartFalse"] == expected["recordStart"]
        and row["GetDurationFalse"] == expected["recordDuration"]
        and row["GetEndFalse"] - row["GetStartFalse"]
        in {row["GetDurationFalse"], row["GetDurationFalse"] - 1}
        and row["GetSourceStartFrame"] == expected["sourceStart"]
        and row["GetSourceEndFrame"] == expected["sourceEnd"]
        and row["GetSourceEndFrame"] > row["GetSourceStartFrame"],
        "V1 raw SDK readback does not match saved reopened case",
    )
    start_time = source_time(item, "GetSourceStartTime")
    end_time = source_time(item, "GetSourceEndTime")
    # This is the exact ordinary VIDEO branch at native_v2:4360: sourceStart
    # equals the raw frame getter, sourceDuration = rawEnd - rawStart, absent
    # source EOF special cases. The case has a 720-frame source, not an EOF.
    normalized = {
        "branch": "moving_video_raw_frame_range_non_eof",
        "sourceStart": row["GetSourceStartFrame"],
        "sourceDuration": row["GetSourceEndFrame"] - row["GetSourceStartFrame"],
        "recordDuration": row["GetDurationFalse"],
        "heldStillTimeNormalizationApplied": False,
        "nativeHostAcceptanceClaimed": False,
    }
    need(
        normalized["sourceDuration"] == normalized["recordDuration"]
        and row["GetSourceEndFrame"] < 720,
        "video non-EOF normalization branch not proven",
    )
    return {
        "itemUidSha256": redacted(expected["uid"], authority_sha),
        "mediaUidSha256": redacted(expected["mediaUid"], authority_sha),
        "filePathSha256": redacted(path, authority_sha),
        "filePath": "[REDACTED: exact pinned internal asset]",
        "sourceKind": "video_h264_verified_by_sha256_not_still",
        "sdkClipPropertyType": sdk_type,
        "Frames": frames,
        "FPS": str(fps),
        "sourceBytesSha256": ASSET_HASHES["root.mp4"],
        "raw": row,
        "GetSourceStartTime": start_time,
        "GetSourceEndTime": end_time,
        "hostNormalizationInterpretation": normalized,
    }


def observe(
    resolve: Any,
    evidence: Mapping[str, Any],
    root: Path = ROOT,
    source_hash: Callable[[], str] = _source_hash,
) -> dict[str, Any]:
    """Must be called under the owner's lock. Injected SDK for negative tests."""
    need(source_hash() == SOURCE_GRAPH, "source graph changed before SDK observer")
    _project, timeline = selected(resolve, evidence["target"])
    first, bound = snapshot(timeline)
    need(first == evidence["reopened"], "saved/reopened 11 UID geometry drifted")
    rows = [
        row for row in first["items"] if row["kind"] == "video" and row["track"] == 1
    ]
    left = [
        row for row in rows if row["recordStart"] == 0 and row["recordDuration"] == 351
    ]
    right = [
        row
        for row in rows
        if row["recordStart"] == 351 and row["recordDuration"] == 127
    ]
    need(
        len(left) == len(right) == 1
        and left[0]["uid"] != right[0]["uid"]
        and left[0]["sourceStart"] == 0
        and left[0]["sourceEnd"] == 351
        and right[0]["sourceStart"] == 24
        and right[0]["sourceEnd"] == 151
        and left[0]["links"] == right[0]["links"] == [],
        "exact saved 327-to-351 V1 boundary unavailable",
    )
    auth_sha = EVIDENCE_HASHES["authority"]
    details = {
        "left": detail(bound[left[0]["uid"]], left[0], root, auth_sha),
        "right": detail(bound[right[0]["uid"]], right[0], root, auth_sha),
    }
    need(
        selected(resolve, evidence["target"])[1].GetUniqueId()
        == timeline.GetUniqueId(),
        "selected target changed during read",
    )
    second, _ = snapshot(timeline)
    need(
        second == first == evidence["reopened"] and source_hash() == SOURCE_GRAPH,
        "host geometry/source drift during read",
    )
    report = {
        "schema": "vera.issue499.calibration.sdk-metadata-readonly/v1",
        "disposition": "saved_video_calibration_only_not_M4",
        "authoritySha256": auth_sha,
        "sourceGraphSha256": SOURCE_GRAPH,
        "reopenedEvidenceSha256": EVIDENCE_HASHES["reopened.json"],
        "projectUidSha256": redacted(evidence["target"]["projectUid"], auth_sha),
        "timelineUidSha256": redacted(evidence["target"]["timelineUid"], auth_sha),
        "geometrySha256": sha(canonical(first)),
        "sdkBuild": [21, 1, 1, 10],
        "itemsVerified": 11,
        "tracksVerified": 6,
        "boundary": details,
        "nativeEditPerformed": False,
        "normalizationScope": (
            "only existing time-based H264 calibration; no held-still conclusion"
        ),
    }
    report["evidenceSha256"] = sha(canonical(report))
    return report


def execute(expected_probe_sha256: str) -> dict[str, Any]:
    need(
        bool(HEX.fullmatch(expected_probe_sha256))
        and sha(Path(__file__).read_bytes()) == expected_probe_sha256,
        "observer script hash differs from reviewed execute packet",
    )
    script_and_source_attested()
    # No creation, LoadProject, OpenPage, SaveProject, render, GUI or asset edit.
    with owner.native_owner(output_lane=True):
        case = case_evidence()
        script_and_source_attested()
        resolve = owner._local_resolve_connection()  # only attaches to running app
        need(resolve is not None, "Resolve is quit; execution DEFERRED")
        report = observe(resolve, case)
        script_and_source_attested()
        return report


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--execute-readonly", action="store_true")
    p.add_argument("--probe-sha256", default="")
    args = p.parse_args()
    if not args.execute_readonly:
        print(
            json.dumps(
                {
                    "status": "DEFERRED",
                    "reason": "Resolve quit / drive disconnected; "
                    "live SDK call requires exact reviewed hash "
                    "and safe selected v2 case",
                }
            )
        )
        return 0
    try:
        print(canonical(execute(args.probe_sha256)).decode().rstrip("\n"))
        return 0
    except (Refusal, OSError, TypeError, KeyError, RuntimeError, ValueError) as error:
        # No SDK exceptions, private paths, UIDs or raw input ever hit stdout.
        print(
            json.dumps({"status": "REFUSED_NO_EFFECT", "reason": type(error).__name__})
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
