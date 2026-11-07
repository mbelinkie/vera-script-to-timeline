"""Fail-stop automatic disposable Resolve project provisioning for Test Bench.

Provisioning uses the installed Resolve SDK only, never UI scripting. Each
CreateProject has a durable, unique, pre-effect intent. An interrupted intent
is UNKNOWN: inspect it; do not silently recreate or adopt a project.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import uuid
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from . import resolve_native_owner as owner
from . import resolve_test_queue as queue
from .resolve_native_owner import (
    _local_resolve_connection,
    native_owner,
    preflight_independent_disposable,
)

SCHEMA = "vera.resolve-test-provision/v1"
DISPOSABLE = re.compile(
    r"VERA Delivery [0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12} [0-9a-f]{12}\Z"
)
STAGES = ("initial", "fresh")
ROOT = Path.home() / "Library/Application Support/VERA/resolve-test-bench/provision"


class ProvisionError(ValueError):
    """No permission to perform or repeat this native effect."""


def _private(root: Path, *, create: bool) -> None:
    root = root.absolute()
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ProvisionError("private provision root must not be a symlink")
    if create:
        root.mkdir(mode=0o700, parents=True, exist_ok=False)
    if not root.is_dir():
        raise ProvisionError("private provision root is unavailable")
    metadata = root.stat()
    if metadata.st_uid != os.getuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
        raise ProvisionError("private provision directory ownership or mode differs")


def _read(path: Path) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise ProvisionError("pinned provision evidence missing or unsafe")
    meta = path.stat()
    if (
        meta.st_uid != os.getuid()
        or meta.st_nlink != 1
        or stat.S_IMODE(meta.st_mode) & 0o077
        or meta.st_size > 16 * 1024
    ):
        raise ProvisionError("pinned provision evidence ownership or size differs")
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeDecodeError, ValueError) as error:
        raise ProvisionError("pinned provision evidence is not JSON") from error
    if not isinstance(value, dict) or raw != queue.canonical(value):
        raise ProvisionError("pinned provision evidence is not canonical")
    return value


def _once(path: Path, value: dict[str, Any]) -> None:
    """Write-once and sync before a side effect, never overwrite a receipt."""
    if path.exists() or path.is_symlink():
        raise ProvisionError("one-use provision stage already recorded")
    data = queue.canonical(value)
    descriptor = os.open(
        path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0),
        0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    queue.sync_directory(path.parent)


def reserve(root: Path) -> dict[str, Any]:
    """Create two globally unique disposable names, without opening Resolve."""
    _private(root, create=True)
    names = [f"VERA Delivery {uuid.uuid4()} {uuid.uuid4().hex[:12]}" for _ in STAGES]
    plan = {
        "schema": SCHEMA,
        "targets": {stage: names[index] for index, stage in enumerate(STAGES)},
    }
    _once(root / "plan.json", plan)
    return plan


def _plan(root: Path) -> dict[str, Any]:
    _private(root, create=False)
    plan = _read(root / "plan.json")
    if (
        set(plan) != {"schema", "targets"}
        or plan["schema"] != SCHEMA
        or not isinstance(plan["targets"], dict)
        or set(plan["targets"]) != set(STAGES)
        or any(
            not isinstance(name, str) or DISPOSABLE.fullmatch(name) is None
            for name in plan["targets"].values()
        )
        or len(set(plan["targets"].values())) != len(STAGES)
    ):
        raise ProvisionError("closed disposable provision plan differs")
    return plan


def _target(root: Path, stage: str, plan: Mapping[str, Any]) -> dict[str, str]:
    receipt = _read(root / f"complete-{stage}.json")
    if (
        set(receipt) != {"schema", "stage", "name", "projectUid", "timelineUid"}
        or receipt["schema"] != SCHEMA
        or receipt["stage"] != stage
        or receipt["name"] != plan["targets"][stage]
        or not isinstance(receipt["projectUid"], str)
        or not 0 < len(receipt["projectUid"]) <= 256
        or not isinstance(receipt["timelineUid"], str)
        or not 0 < len(receipt["timelineUid"]) <= 256
        or any(
            ord(ch) < 32
            for uid in (receipt["projectUid"], receipt["timelineUid"])
            for ch in uid
        )
        or receipt["projectUid"] == receipt["timelineUid"]
    ):
        raise ProvisionError("completed target UID receipt differs")
    return {
        "projectName": receipt["name"],
        "timelineName": receipt["name"],
        "projectUid": receipt["projectUid"],
        "timelineUid": receipt["timelineUid"],
    }


def completed(root: Path) -> dict[str, dict[str, str]]:
    plan = _plan(root)
    targets = {stage: _target(root, stage, plan) for stage in STAGES}
    identities = [
        uid
        for target in targets.values()
        for uid in (target["projectUid"], target["timelineUid"])
    ]
    if len(set(identities)) != 4:
        raise ProvisionError("initial and rebuild UIDs are not independent")
    return targets


def _new_target(resolve: Any, name: str) -> tuple[str, str]:
    """All changes are confined to the *newly created* named project."""
    manager = resolve.GetProjectManager()
    if not isinstance(manager.GetProjectListInCurrentFolder(), (list, tuple)):
        raise ProvisionError("project inventory is unavailable")
    if name in manager.GetProjectListInCurrentFolder():
        raise ProvisionError("disposable project already exists")
    project = manager.CreateProject(name)
    if project is None or project.GetName() != name:
        raise ProvisionError("new synthetic project creation refused")
    project_uid = project.GetUniqueId()
    if (
        not isinstance(project_uid, str)
        or not project_uid
        or manager.GetCurrentProject() is None
        or manager.GetCurrentProject().GetUniqueId() != project_uid
    ):
        raise ProvisionError("new synthetic project was not selected")
    if project.SetSetting("timelineFrameRate", "23.976") is not True:
        raise ProvisionError("could not set synthetic NTSC timeline rate")
    if str(project.GetSetting("timelineFrameRate")) != "23.976":
        raise ProvisionError("synthetic timeline rate readback differs")
    pool = project.GetMediaPool()
    if pool is None:
        raise ProvisionError("new synthetic project has no media pool")
    timeline = pool.CreateEmptyTimeline(name)
    if timeline is None or timeline.GetName() != name:
        raise ProvisionError("new synthetic timeline creation refused")
    if project.SetCurrentTimeline(timeline) is not True:
        raise ProvisionError("new synthetic timeline selection failed")
    timeline_uid = timeline.GetUniqueId()
    if (
        not isinstance(project_uid, str)
        or not project_uid
        or not isinstance(timeline_uid, str)
        or not timeline_uid
        or project_uid == timeline_uid
        or project.GetCurrentTimeline().GetUniqueId() != timeline_uid
        or str(timeline.GetSetting("timelineFrameRate")) != "23.976"
    ):
        raise ProvisionError("real new native identity or rate readback differs")
    for kind in ("video", "audio", "subtitle"):
        count = timeline.GetTrackCount(kind)
        if type(count) is not int or not 0 <= count <= 64:
            raise ProvisionError("new timeline has unreadable track inventory")
        for index in range(1, count + 1):
            clips = timeline.GetItemListInTrack(kind, index)
            if not isinstance(clips, (list, tuple)) or clips:
                raise ProvisionError("new timeline is not empty")
    # SaveProject writes the *currently selected* project, not the passed
    # object. A Producer click can change this selection independently of our
    # native-owner flock; fail before SaveProject rather than saving their work.
    selected = manager.GetCurrentProject()
    if (
        selected is None
        or selected.GetUniqueId() != project_uid
        or selected.GetName() != name
        or selected.GetCurrentTimeline() is None
        or selected.GetCurrentTimeline().GetUniqueId() != timeline_uid
        or selected.IsRenderingInProgress() is not False
    ):
        raise ProvisionError("current selection changed; do not save another project")
    if manager.SaveProject() is not True:
        raise ProvisionError("new synthetic project save refused")
    if (
        manager.GetCurrentProject().GetUniqueId() != project_uid
        or manager.GetCurrentProject().GetCurrentTimeline().GetUniqueId()
        != timeline_uid
        or name not in manager.GetProjectListInCurrentFolder()
    ):
        raise ProvisionError("saved synthetic project identity changed")
    return project_uid, timeline_uid


def advance(root: Path) -> dict[str, Any]:
    """Perform at most one stage; no rerun after a pre-effect intent."""
    plan = _plan(root)
    for stage in STAGES:
        intent = root / f"intent-{stage}.json"
        complete = root / f"complete-{stage}.json"
        if complete.exists() or complete.is_symlink():
            if not intent.exists() or intent.is_symlink():
                raise ProvisionError("completion without valid pre-effect intent")
            pinned = _read(intent)
            if (
                set(pinned) != {"schema", "stage", "name", "operationId"}
                or pinned["name"] != plan["targets"][stage]
                or pinned["stage"] != stage
                or pinned["schema"] != SCHEMA
            ):
                raise ProvisionError("pre-effect intent differs")
            _target(root, stage, plan)
            continue
        if intent.exists() or intent.is_symlink():
            raise ProvisionError(
                "previous project creation is UNKNOWN; inspect, do not replay"
            )
        name = plan["targets"][stage]
        # Lock acquired before preflight and held until save/readback. This
        # cannot turn an unresolved historical project into a fresh one.
        with native_owner(output_lane=True):
            preflight_independent_disposable(name)
            _once(
                intent,
                {
                    "schema": SCHEMA,
                    "stage": stage,
                    "name": name,
                    "operationId": str(uuid.uuid4()),
                },
            )
            resolve = _local_resolve_connection()
            if not resolve:
                raise ProvisionError("Resolve connection unavailable after intent")
            project_uid, timeline_uid = _new_target(resolve, name)
            _once(
                complete,
                {
                    "schema": SCHEMA,
                    "stage": stage,
                    "name": name,
                    "projectUid": project_uid,
                    "timelineUid": timeline_uid,
                },
            )
        return {"state": "stage_verified", "stage": stage, "created": True}
    completed(root)
    # Provisioning is not a native edit/rebuild verification. Never reuse the
    # M4 terminal state name `completed_verified` in setup-only reporting.
    return {"state": "targets_provisioned", "created": False}


def provision(root: Path) -> dict[str, Any]:
    """One-command two-project setup, preserving per-stage crash semantics."""
    if not root.exists() and not root.is_symlink():
        reserve(root)
    for _ in range(len(STAGES) + 1):
        result = advance(root)
        if result["state"] == "targets_provisioned":
            return result
    raise ProvisionError("both projects were not authenticated")


def select(root: Path, stage: str) -> dict[str, Any]:
    """Select only a provisioned target, never an arbitrary Producer project."""
    targets = completed(root)
    if stage not in targets:
        raise ProvisionError("unknown provisioned target selection")
    target = targets[stage]
    with native_owner(output_lane=True):
        resolve = _local_resolve_connection()
        if not resolve:
            raise ProvisionError("Resolve unavailable for selected-target check")
        manager = resolve.GetProjectManager()
        current = manager.GetCurrentProject()
        if current is None:
            raise ProvisionError("no current Resolve project")
        current_uid = current.GetUniqueId()
        selected = next(
            (row for row in targets.values() if row["projectUid"] == current_uid),
            None,
        )
        if (
            selected is None
            or current.GetName() != selected["projectName"]
            or current.GetCurrentTimeline() is None
            or current.GetCurrentTimeline().GetUniqueId() != selected["timelineUid"]
            or current.IsRenderingInProgress() is not False
        ):
            raise ProvisionError("current project is not an idle provisioned target")
        jobs = current.GetRenderJobList()
        if not isinstance(jobs, (list, tuple)):
            raise ProvisionError("selected target render queue unavailable")
        for job in jobs:
            if not isinstance(job, dict) or not isinstance(job.get("JobId"), str):
                raise ProvisionError("unreadable current target render job")
            status = current.GetRenderJobStatus(job["JobId"])
            if not isinstance(status, dict) or status.get("JobStatus") not in {
                "Complete",
                "Failed",
                "Cancelled",
            }:
                raise ProvisionError("selected target has unresolved render job")
        # Unlike a foreign retained historic UNKNOWN, unresolved work on the
        # actual currently selected synthetic target blocks switching away.
        for key in owner._active_output_host_chains(None):
            path = owner.OUTPUT_ATTEMPTS_ROOT / key / "chain.json"
            chain = json.loads(owner._read(path))
            if chain.get("projectUid") == current_uid:
                raise ProvisionError("current target has unresolved output work")
        if current_uid != target["projectUid"]:
            loaded = manager.LoadProject(target["projectName"])
            if loaded is None:
                raise ProvisionError("provisioned project selection failed")
        active = manager.GetCurrentProject()
        if (
            active is None
            or active.GetUniqueId() != target["projectUid"]
            or active.GetName() != target["projectName"]
            or active.GetCurrentTimeline() is None
            or active.GetCurrentTimeline().GetUniqueId() != target["timelineUid"]
            or active.GetCurrentTimeline().GetName() != target["timelineName"]
        ):
            raise ProvisionError("Resolve selected an incorrect project or timeline")
    return {"state": "selected_verified", "stage": stage}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument(
        "action",
        choices=(
            "run",
            "reserve",
            "advance",
            "select-initial",
            "select-fresh",
            "status",
        ),
    )
    args = parser.parse_args()
    try:
        if args.action == "run":
            result = provision(args.root)
            # Leave Resolve on the initial empty target for M4 pristine.
            select(args.root, "initial")
        elif args.action == "reserve":
            reserve(args.root)
            result = {"state": "reserved", "nativeEffects": False}
        elif args.action == "advance":
            result = advance(args.root)
        elif args.action.startswith("select-"):
            result = select(args.root, args.action.removeprefix("select-"))
        else:
            _plan(args.root)
            result = {
                "state": "targets_provisioned"
                if all(
                    (args.root / f"complete-{stage}.json").exists() for stage in STAGES
                )
                else "pending_or_unknown"
            }
            if result["state"] == "targets_provisioned":
                completed(args.root)
        print(json.dumps(result, sort_keys=True))
    except (ProvisionError, OSError, ValueError) as error:
        parser.exit(2, f"Test Bench refused: {error}\n")


if __name__ == "__main__":
    main()
