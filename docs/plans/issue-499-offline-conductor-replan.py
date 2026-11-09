#!/usr/bin/env python3
"""Safely install Producer-approved #499 21-phase plan while Conductor is OFF.

Private operator helper, not part of VERA production or native Test Bench.
Replans ONLY the blocked #499 ticket, with backups and byte-atomic writes.
Never launches a Zodex chat, Resolve, a native job, or any other ticket.
Default is dry-run; --apply requires launchctl Conductor unloaded.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

KEY = "vera-script-to-timeline#499"
HOME = Path.home()
REPO = HOME / "Desktop/ONGOING/VERA Script to Timeline"
CONDUCTOR = HOME / "Desktop/ONGOING/vera-conductor"
PLAN = REPO / ".pipeline/499/plan.json"
STATE = CONDUCTOR / "state.json"


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise RuntimeError("499 replan refused: " + reason)


def load(path: Path) -> dict:
    require(path.is_file() and not path.is_symlink(), "missing or linked " + str(path))
    obj = json.loads(path.read_bytes())
    require(type(obj) is dict, "invalid JSON object " + str(path))
    return obj


def write_atomically(path: Path, obj: dict) -> None:
    raw = (json.dumps(obj, indent=2, ensure_ascii=False) + "\n").encode()
    tmp = path.with_name("." + path.name + ".499-replan-tmp-" + str(os.getpid()))
    fd = os.open(tmp, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    os.replace(tmp, path)
    dir_fd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dir_fd)
    finally:
        os.close(dir_fd)


def main() -> None:
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument("--plan", required=True, type=Path)
    args.add_argument("--apply", action="store_true")
    opts = args.parse_args()
    newer, old, state = load(opts.plan), load(PLAN), load(STATE)
    require(len(old.get("phases", [])) == 14 and old.get("current") == 11,
            "old on-disk 14-phase pointer unexpected")
    require(len(newer.get("phases", [])) == 21 and newer.get("current") == 12,
            "new 21-phase pointer unexpected")
    require(newer["phases"][:11] == old["phases"][:11],
            "historical phases 1–11 changed")
    require(type(state.get("tickets")) is dict and KEY in state["tickets"],
            "tracked ticket 499 missing")
    ticket = state["tickets"][KEY]
    require(ticket.get("stage") == "blocked" and ticket.get("phase") == 10
            and ticket.get("phases") == old["phases"],
            "ticket not at the expected blocked phase11 or phase plan mismatch")
    require(not (REPO / ".pipeline/499/handoff.json").exists(),
            "existing handoff must be reconciled first")
    active = [(k, t.get("stage")) for k, t in state["tickets"].items()
              if k != KEY and t.get("stage") in {"building", "fixing", "merging"}]
    require(not active, "other conductor tickets active: " + str(active))
    status = subprocess.run(["launchctl", "list", "com.vera.conductor"],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            timeout=7, check=False)
    if opts.apply:
        require(status.returncode != 0,
                "unload the LaunchAgent before changing live state; no double writer")
    print(json.dumps({
        "mode": "apply" if opts.apply else "dry-run",
        "old": {"stage": ticket["stage"], "phase": 11, "total": 14},
        "new": {"stage": "blocked", "nextPhase": 12, "total": 21},
        "conductorLoaded": status.returncode == 0,
        "otherTicketCount": len(state["tickets"]) - 1,
    }, sort_keys=True))
    if not opts.apply:
        return
    backup = CONDUCTOR / (".replan-499-backup-" + time.strftime("%Y%m%d-%H%M%S"))
    backup.mkdir(mode=0o700, exist_ok=False)
    shutil.copy2(STATE, backup / "state.json")
    shutil.copy2(PLAN, backup / "plan.json")
    os.chmod(backup / "state.json", 0o600)
    os.chmod(backup / "plan.json", 0o600)
    ticket["phase"] = 11  # zero-based: next is #12
    ticket["phases"] = newer["phases"]
    ticket["stage"] = "blocked"  # user/Conductor nudge starts phase12
    ticket["stageSince"] = int(time.time() * 1000)
    ticket["nudges"] = 0
    ticket["blockedReason"] = (
        "Producer-approved #499 replan: Phase 11's Qt deadlock was superseded "
        "by separately authorized one-use calibration (NOT an M4 pass). "
        "Next: Phase 12/21 offline forensic evidence. Use Try again/Nudge; "
        "do not restart phase11 or consume any native effect."
    )
    # Preserve historical lastHandoff, progress and receipts; never invent done.
    write_atomically(PLAN, newer)
    write_atomically(STATE, state)
    final_plan, final_state = load(PLAN), load(STATE)
    require(final_plan == newer and final_state["tickets"][KEY]["phase"] == 11
            and final_state["tickets"][KEY]["phases"] == newer["phases"],
            "post-write verification failed; investigate backups")
    print("REPLAN VERIFIED; private backup " + str(backup))


if __name__ == "__main__":
    main()
