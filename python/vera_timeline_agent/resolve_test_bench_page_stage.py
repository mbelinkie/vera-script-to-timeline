"""One bounded SDK Edit-page preparation for an already-authorized NEW M4.

Only the original one-start caller may supply its authenticated case authority.
The page change is not a GUI roll or a native media edit. An uncertain SDK
return permanently stops that one-start; old targets are never reselected.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import monotonic
from typing import Any

from . import resolve_gui_roll as roll
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from . import resolve_test_queue_m4_provision as provision
from .qualification_output_controller_v2 import load_output_session
from .qualification_output_native_v2 import verify_native_result
from .qualification_output_proof_v2 import _load_terminal_output_with_comparison
from .resolve_test_bench_edit_probe import inspect_selected


def _require(value: bool, detail: str) -> None:
    if not value:
        raise queue.QueueError("original M4 owned SDK Edit-page refused: " + detail)


def open_owned_edit_page(
    store: queue.Store,
    job_id: str,
    resolve: Any,
    *,
    case_root: Path,
    authority: Mapping[str, Any],
) -> None:
    """Navigate ONLY the authenticated one-start's already-selected new UID.

    No LoadProject, media edits, menu events, TCC changes, owner acquisition,
    journal consumption, or second page attempt. The original start() has
    already authenticated the exact Producer instruction and source graph;
    this second gate rebinds its durable one-start record and provision UIDs.
    """
    roll._require_owner_lock()
    from .resolve_test_bench_full_loop import AUTHORITY_SCHEMA, INTENT_SCHEMA

    record = json.loads(carrier._read(case_root / "complete-loop-intent.json", 32768))
    _require(
        isinstance(record, dict)
        and record.get("schema") == INTENT_SCHEMA
        and isinstance(record.get("authority"), dict)
        and isinstance(record.get("config"), dict)
        and record["authority"].get("sha256")
        == hashlib.sha256(queue.canonical(dict(authority))).hexdigest()
        and record["config"].get("sha256") == authority.get("configSha256")
        and record.get("frozenCommit") == authority.get("frozenCommit")
        and record.get("sourceGraphSha256") == authority.get("sourceGraphSha256")
        and authority.get("schema") == AUTHORITY_SCHEMA
        and authority.get("caseId") == "synthetic-312"
        and authority.get("operation") == "M4.edited.one-use-gui-roll"
        and authority.get("fromFrame") == 327
        and authority.get("toFrame") == 351
        and roll._valid_actor_pin(authority.get("actorPin")),
        "fresh one-start case authority and source binding missing",
    )
    targets = provision.completed(case_root / "provision")
    plan = m4._load_plan(store, job_id)
    _require(
        plan["caseId"] == "synthetic-312"
        and plan["initialTarget"] == authority["initialTarget"] == targets["initial"]
        and plan["freshTarget"] == authority["freshTarget"] == targets["fresh"]
        and targets["initial"] != targets["fresh"],
        "historical, producer or unapproved disposable target",
    )
    gui_root = m4._jobdir(store, job_id) / "f1-gui-edit"
    gui_intent = gui_root / "gui-intent.json"
    _require(
        not gui_root.is_symlink()
        and not gui_intent.exists()
        and not gui_intent.is_symlink(),
        "prior GUI intent or uncertain edit may not be replayed",
    )
    receipt = m4._stage_receipt(store, job_id, 0)
    _require(
        receipt["session"] == plan["baselineSession"],
        "verified pristine session pin differs",
    )
    with store.connect() as db:
        parent = db.execute(
            "SELECT state,started_at,deadline_at FROM reverse_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        rows = [
            dict(row)
            for row in db.execute(
                "SELECT ordinal,name,state,operation_id,receipt_sha,intent_at "
                "FROM reverse_stages WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            )
        ]
    _require(
        parent is not None
        and parent["state"] == "awaiting_operator"
        and parent["started_at"] is not None
        and parent["deadline_at"] == queue.dt(plan["deadlineAt"]).timestamp()
        and len(rows) == 4
        and [row["name"] for row in rows]
        == ["pristine", "edited", "revision", "rebuild"]
        and rows[0]["state"] == "verified"
        and rows[0]["receipt_sha"] is not None
        and rows[1]["state"] == "awaiting_operator"
        and type(rows[1]["operation_id"]) is str
        and bool(rows[1]["operation_id"])
        and rows[1]["receipt_sha"] is None
        and type(rows[1]["intent_at"]) is str
        and all(
            row["state"] == "pending" and row["intent_at"] is None for row in rows[2:]
        ),
        "one freshly enrolled edited operation, never UNKNOWN, required",
    )
    now = datetime.now(UTC)
    started = queue.dt(parent["started_at"])
    intent_time = queue.dt(rows[1]["intent_at"])
    deadline = min(
        queue.dt(plan["deadlineAt"]),
        queue.dt(plan["runAt"]) + timedelta(seconds=plan["maxElapsedSeconds"]),
        started + timedelta(seconds=plan["maxElapsedSeconds"]),
    )

    def check_time() -> None:
        _require(
            started <= intent_time <= datetime.now(UTC)
            and datetime.now(UTC) + timedelta(seconds=60) < deadline,
            "edited intent or original cumulative deadline stale",
        )

    _require(started <= intent_time <= now, "edited operation intent is not current")
    check_time()

    session = load_output_session(
        Path(receipt["session"]["path"]), receipt["session"]["sha256"]
    )
    _require(
        session.context.get("phase") == "pristine"
        and session.context.get("caseId") == "synthetic-312"
        and session.context.get("target") == plan["initialTarget"],
        "original signed session belongs to another native target",
    )
    _load_terminal_output_with_comparison(session)
    signed = verify_native_result(
        Path(receipt["capture"]["path"]), receipt["capture"]["sha256"]
    )
    geometry = signed.get("nativeGeometry")
    _require(
        signed.get("status") == "complete"
        and signed.get("action") == "capture_post"
        and signed.get("context") == session.context
        and signed.get("target") == plan["initialTarget"]
        and isinstance(geometry, dict),
        "original signed eleven-item/six-track capture missing",
    )
    assert isinstance(geometry, dict)
    before = inspect_selected(resolve, plan["initialTarget"], geometry)
    _require(
        before.get("disposition") == "read_only_no_edit_authorized"
        and before.get("resolveVersion") == [21, 1, 1, 10, ""]
        and before.get("target") == plan["initialTarget"],
        "selected native SDK target, inventory or Studio version differs",
    )
    # inspect_selected reads exact project/timeline UIDs, all eleven media/clip
    # UIDs, links, six track states and idle rendering, not window names alone.
    check_time()
    current_page = resolve.GetCurrentPage()
    _require(type(current_page) is str and bool(current_page), "SDK page unknown")
    started_call = monotonic()
    if current_page != "edit":
        _require(
            resolve.OpenPage("edit") is True,
            "one bounded SDK Edit page request failed or refused",
        )
    _require(
        0 <= monotonic() - started_call <= 5,
        "SDK page request exceeded five-second bound; no retry",
    )
    # A partial page result is not success. Never select a project as fallback.
    _require(resolve.GetCurrentPage() == "edit", "SDK did not confirm Edit page")
    after = inspect_selected(resolve, plan["initialTarget"], geometry)
    _require(after == before, "selected SDK UID/inventory drifted during page setup")
    check_time()


def verify_pre_roll_source_origins(
    store: queue.Store,
    job_id: str,
    resolve: Any,
    *,
    session: Mapping[str, str],
) -> None:
    """Read-only original-media path gate BEFORE spending the GUI Roll intent.

    Resolve retains media references to the imported pristine package. The
    edited package is a distinct SHA-equivalent verification copy, never a
    command to relink the timeline. Prove this while the SDK owner is held,
    before the one-use F1 GUI request or any further effect is claimed.
    """
    from .qualification_output_controller_v2 import load_output_session
    from .qualification_output_native_v2 import (
        MATRIX_PROFILE,
        _admitted_media_path,
        _hash_file,
        _m4_edited_original_source_admission,
        _path,
        _source_hash,
    )

    roll._require_owner_lock()
    plan = m4._load_plan(store, job_id)
    ref = m4._ref(dict(session), "edited pre-Roll session")
    controller = load_output_session(Path(ref["path"]), ref["sha256"])
    _require(
        controller.context.get("phase") == "edited"
        and controller.context.get("caseId") == "synthetic-312"
        and controller.context.get("target") == plan["initialTarget"]
        and controller.admission.profile == MATRIX_PROFILE,
        "edited M4 source preflight context differs",
    )
    original = _m4_edited_original_source_admission(
        {
            "context": controller.context,
            "target": plan["initialTarget"],
            "profile": controller.admission.profile,
        },
        {
            "sourceRoot": controller.admission.package_root / "PublicPackage",
            "manifest": controller.admission.manifest,
            "view": controller.admission.view,
            "admission": controller.admission.admission,
        },
    )
    paths = {
        str(_admitted_media_path(original, row)): row
        for row in original["view"]["sources"]
    }
    project = resolve.GetProjectManager().GetCurrentProject()
    _require(project is not None, "pre-Roll project is unavailable")
    timeline = project.GetCurrentTimeline()
    _require(
        timeline is not None
        and project.GetUniqueId() == plan["initialTarget"]["projectUid"]
        and timeline.GetUniqueId() == plan["initialTarget"]["timelineUid"],
        "pre-Roll exact disposable UID selection differs",
    )
    seen = 0
    for kind in ("video", "audio"):
        count = timeline.GetTrackCount(kind)
        _require(type(count) is int and 0 <= count <= 6, "unsupported M4 track count")
        for index in range(1, count + 1):
            items = timeline.GetItemListInTrack(kind, index)
            _require(
                type(items) in (list, tuple) and len(items) <= 24,
                "pre-Roll item inventory unavailable",
            )
            for item in items:
                media = item.GetMediaPoolItem()
                _require(media is not None, "pre-Roll media pool item missing")
                props = media.GetClipProperty()
                value = props.get("File Path") if type(props) is dict else None
                _require(type(value) is str, "pre-Roll native File Path unreadable")
                assert isinstance(value, str)
                _path(value, "pre-Roll original imported media")
                _require(
                    os.path.normpath(value) == value,
                    "pre-Roll native media path is aliased",
                )
                source = paths.get(value)
                _require(
                    source is not None,
                    "pre-Roll media is not from signed pristine package",
                )
                assert source is not None
                _require(
                    _hash_file(Path(value))[0] == _source_hash(source["contentHash"]),
                    "pre-Roll original imported source bytes changed",
                )
                seen += 1
    _require(seen == 11, "pre-Roll native 11-item source inventory incomplete")
