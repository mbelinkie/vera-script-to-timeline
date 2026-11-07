#!/usr/bin/env python3
"""One-use, owner-locked Resolve Studio EOF readback trial for issue #472.

Only a freshly named, synthetic disposable project may be changed. Never
re-enroll an existing ID, mutate the historical #312 project, or retry an
unknown effect. A durable private append-only ledger precedes each SDK effect.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from vera_timeline_agent.resolve_native_owner import (
    _local_resolve_connection,
    native_owner,
    preflight_independent_disposable,
)

EXPECTED_HASH = "803b9a7375d1da5aa52ecac6a9c02071891d8bcb59fddde22410e37f514ce023"
SOURCE = (
    Path.home() / "Library/Application Support/VERA/private-preparation/"
    "issue-312-m4-acceptance/compiler-refresh-01/admitted-final-01/"
    "package/PublicPackage/Media/Resolved/"
    "42b82702-d6df-59b0-8b9b-201fb3518c64.mp4"
)
PROOF_ROOT = Path.home() / (
    "Library/Application Support/VERA/private-preparation/issue-472-studio-eof-proof"
)
FRAME_COUNT = 214
RECORD_START = 715
END_SECONDS = 214 * 1001 / 24000


def require(ok: bool, message: str) -> None:
    if not ok:
        raise RuntimeError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        while chunk := file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def readback(item: Any) -> dict[str, Any]:
    media = item.GetMediaPoolItem()
    require(media is not None, "clip missing MediaPoolItem")
    props = media.GetClipProperty()
    require(isinstance(props, dict), "clip property inventory unavailable")
    return {
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
        "mediaPath": props.get("File Path"),
        "speed": item.GetSpeed(),
    }


def verified_readback(row: dict[str, Any], expected_uid: str) -> bool:
    try:
        fps = Decimal(str(row["mediaFPS"]))
        pct = row["speed"]["Percentage"]
        measured_path = Path(str(row["mediaPath"])).resolve(strict=True)
        return (
            row["itemUid"] == expected_uid
            and row["recordStart"] == RECORD_START
            and row["recordDuration"] == FRAME_COUNT
            and row["recordEnd"] == RECORD_START + FRAME_COUNT
            and row["sourceStartFrame"] == 0
            and row["sourceEndFrame"] == 212
            and row["sourceStartTime"] == 0
            and abs(row["sourceEndTime"] - END_SECONDS) <= 1 / 48000
            and str(row["mediaFrames"]) == str(FRAME_COUNT)
            and fps == Decimal("23.976")
            and type(pct) in (int, float)
            and pct == 100
            and measured_path == SOURCE.resolve(strict=True)
            and sha256(measured_path) == EXPECTED_HASH
        )
    except (OSError, ValueError, TypeError, KeyError, InvalidOperation):
        return False


def run(run_id: str) -> int:
    token = str(uuid.UUID(run_id))
    require(token == run_id, "run ID must be a canonical UUID")
    project_name = (
        f"VERA Delivery {token} "
        + hashlib.sha256((token + ":472").encode()).hexdigest()[:12]
    )
    root = PROOF_ROOT / token
    PROOF_ROOT.mkdir(mode=0o700, parents=True, exist_ok=True)
    root.mkdir(mode=0o700)  # A second invocation fails before SDK work.
    ledger_path = root / "events.jsonl"
    ledger_fd = os.open(
        ledger_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_APPEND, 0o600
    )
    project_uid: str | None = None
    timeline_uid: str | None = None

    def ledger(action: str, value: Any) -> None:
        raw = json.dumps({"action": action, "value": value}, sort_keys=True).encode()
        os.write(ledger_fd, raw + b"\n")
        os.fsync(ledger_fd)

    def effect(label: str, fn: Any) -> Any:
        ledger("effect_intent", label)
        value = fn()
        ledger(
            "effect_return",
            {"label": label, "ok": value is not None and value is not False},
        )
        return value

    try:
        ledger(
            "start",
            {
                "runId": token,
                "targetName": project_name,
                "expectedSha256": EXPECTED_HASH,
            },
        )
        require(
            SOURCE.is_file() and not SOURCE.is_symlink(),
            "admitted source file unavailable or symlink",
        )
        require(
            sha256(SOURCE) == EXPECTED_HASH,
            "delivered media bytes differ from admission",
        )
        ledger("source_auth", {"sha256": EXPECTED_HASH, "path": str(SOURCE)})

        with native_owner(output_lane=True):
            preflight_independent_disposable(project_name)
            ledger("preflight", "independent disposable and shared owner verified")
            resolve = _local_resolve_connection()
            require(resolve is not None, "installed Resolve scripting unavailable")
            ledger(
                "studio",
                {
                    "product": resolve.GetProductName(),
                    "version": resolve.GetVersionString(),
                },
            )
            require(
                resolve.GetProductName() == "DaVinci Resolve Studio",
                "not a Studio instance",
            )
            manager = resolve.GetProjectManager()
            require(manager is not None, "project manager unavailable")

            project = effect(
                "CreateProject", lambda: manager.CreateProject(project_name)
            )
            require(
                project is not None and project.GetName() == project_name,
                "CreateProject refused",
            )
            project_uid = project.GetUniqueId()
            require(
                type(project_uid) is str and project_uid, "new project UID unreadable"
            )
            require(
                manager.GetCurrentProject() is not None
                and manager.GetCurrentProject().GetUniqueId() == project_uid,
                "new project not selected",
            )
            ledger(
                "created_project",
                {"projectUid": project_uid, "projectName": project_name},
            )
            require(
                effect(
                    "SetSetting 23.976",
                    lambda: project.SetSetting("timelineFrameRate", "23.976"),
                )
                is True,
                "timeline rate setting refused",
            )
            require(
                str(project.GetSetting("timelineFrameRate")) == "23.976",
                "wrong project rate",
            )
            pool = project.GetMediaPool()
            require(pool is not None, "new project media pool missing")
            timeline = effect(
                "CreateEmptyTimeline", lambda: pool.CreateEmptyTimeline(project_name)
            )
            require(
                timeline is not None and timeline.GetName() == project_name,
                "new timeline missing",
            )
            require(
                effect(
                    "SetCurrentTimeline", lambda: project.SetCurrentTimeline(timeline)
                )
                is True,
                "new timeline not selected",
            )
            timeline_uid = timeline.GetUniqueId()
            require(
                type(timeline_uid) is str and timeline_uid,
                "new timeline UID unreadable",
            )
            ledger("created_timeline", {"timelineUid": timeline_uid})
            for track_kind in ("video", "audio", "subtitle"):
                for index in range(1, timeline.GetTrackCount(track_kind) + 1):
                    clips = timeline.GetItemListInTrack(track_kind, index)
                    require(
                        type(clips) in (list, tuple) and len(clips) == 0,
                        "disposable timeline is not empty",
                    )

            imported = effect("ImportMedia", lambda: pool.ImportMedia([str(SOURCE)]))
            require(
                type(imported) in (list, tuple) and len(imported) == 1,
                "expected exactly one authenticated imported media item",
            )
            media = imported[0]
            props = media.GetClipProperty()
            require(type(props) is dict, "imported clip properties unavailable")
            require(
                str(props.get("Frames")) == str(FRAME_COUNT),
                "imported media frame count differs",
            )
            require(
                Decimal(str(props.get("FPS"))) == Decimal("23.976"),
                "imported media FPS differs",
            )
            require(
                Path(str(props.get("File Path"))).resolve(strict=True)
                == SOURCE.resolve(strict=True),
                "imported media path differs",
            )
            ledger(
                "import_verified",
                {"Frames": props.get("Frames"), "FPS": props.get("FPS")},
            )

            info = {
                "mediaPoolItem": media,
                "startFrame": 0,
                "endFrame": FRAME_COUNT,
                "mediaType": 1,
                "trackIndex": 1,
                "recordFrame": RECORD_START,
            }
            placed = effect("AppendToTimeline", lambda: pool.AppendToTimeline([info]))
            require(
                type(placed) in (list, tuple) and len(placed) == 1,
                "AppendToTimeline refused",
            )
            item = placed[0]
            uid = item.GetUniqueId()
            require(type(uid) is str and uid, "new clip UID unavailable")
            before = readback(item)
            ledger("readback_before_save", before)
            require(
                manager.GetCurrentProject().GetUniqueId() == project_uid
                and project.GetCurrentTimeline().GetUniqueId() == timeline_uid,
                "project/timeline selection changed before save",
            )
            require(
                project.IsRenderingInProgress() is False
                and project.GetRenderJobList() == [],
                "disposable target has active render or job",
            )
            require(
                effect("SaveProject", lambda: manager.SaveProject()) is True,
                "SaveProject refused",
            )
            ledger(
                "saved_project",
                {"projectUid": project_uid, "timelineUid": timeline_uid},
            )
            require(
                manager.GetCurrentProject().GetUniqueId() == project_uid,
                "project selection changed before close",
            )
            require(
                effect("CloseProject", lambda: manager.CloseProject(project)) is True,
                "CloseProject refused",
            )
            reopened = effect("LoadProject", lambda: manager.LoadProject(project_name))
            require(reopened is not None, "LoadProject refused")
            require(
                reopened.GetUniqueId() == project_uid
                and manager.GetCurrentProject().GetUniqueId() == project_uid,
                "reopened project UID differs",
            )
            replay = reopened.GetCurrentTimeline()
            require(
                replay is not None and replay.GetUniqueId() == timeline_uid,
                "reopened timeline UID differs",
            )
            items = replay.GetItemListInTrack("video", 1)
            require(type(items) in (list, tuple), "reopened track unreadable")
            matches = [row for row in items if row.GetUniqueId() == uid]
            require(len(matches) == 1, "reopened clip UID missing or duplicated")
            after = readback(matches[0])
            ledger("readback_after_reopen", after)
            verified = (
                verified_readback(before, uid)
                and verified_readback(after, uid)
                and before == after
            )
            report = {
                "schema": "VERA-472-native-studio-proof-v1",
                "runId": token,
                "projectName": project_name,
                "projectUid": project_uid,
                "timelineUid": timeline_uid,
                "sourceSha256": EXPECTED_HASH,
                "beforeSave": before,
                "afterReopen": after,
                "sameUid": before["itemUid"] == after["itemUid"] == uid,
                "verifiedFull214FrameEofUndercount": verified,
                "physicalStudioTestOnly": True,
                "not312M4Acceptance": True,
            }
            ledger("conclusion", report)
            # The event ledger is durable evidence; report is additionally
            # created once and synced, never replacing a prior outcome.
            report_fd = os.open(
                root / "report.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600
            )
            try:
                os.write(
                    report_fd,
                    json.dumps(report, sort_keys=True, indent=2).encode() + b"\n",
                )
                os.fsync(report_fd)
            finally:
                os.close(report_fd)
            print(json.dumps(report, sort_keys=True), flush=True)
            return 0 if verified else 3
    except BaseException as error:
        ledger(
            "failed_closed",
            {
                "errorType": type(error).__name__,
                "error": str(error),
                "projectUid": project_uid,
                "timelineUid": timeline_uid,
                "retryAllowed": False,
            },
        )
        raise
    finally:
        os.close(ledger_fd)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("usage: issue-472-studio-eof-proof.py <fresh-canonical-uuid>")
    raise SystemExit(run(sys.argv[1]))
