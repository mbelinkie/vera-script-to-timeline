"""#473 original M4 edited host: consumed F1 -> independent SDK/MOV/PCM proof.

This is deliberately not a GUI executor or an alternative native engine. The
one-use GUI journal says only that an effect *might* have happened. The existing
official-SDK v2 host must observe, save/close/reopen, render and authenticate
the original edited target before this module issues one original M4 receipt.

Never use this on the source-sealed historical campaign after changing code.
Only a newly authorized, source-frozen sacrificial campaign may call ``start``.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from . import resolve_gui_roll as gui
from . import resolve_test_bench_campaign as campaign
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_m4_runner as runner
from . import resolve_test_bench_output as output
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from .qualification_output_native_v2 import verify_native_result
from .resolve_test_queue_reverse import verify_supported_boundary


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise queue.QueueError("original M4 edited host refused: " + message)


def _deadline(
    store: queue.Store, job_id: str, plan: dict[str, Any]
) -> tuple[float, str]:
    with store.connect() as db:
        parent = db.execute(
            "SELECT state,started_at,deadline_at FROM reverse_jobs WHERE id=?",
            (job_id,),
        ).fetchone()
        stages = [
            dict(row)
            for row in db.execute(
                "SELECT ordinal,name,state,operation_id,intent_at,receipt_sha "
                "FROM reverse_stages WHERE job_id=? ORDER BY ordinal",
                (job_id,),
            )
        ]
    _require(
        parent is not None
        and parent["state"] == "awaiting_operator"
        and parent["started_at"] is not None
        and parent["deadline_at"] == queue.dt(plan["deadlineAt"]).timestamp()
        and len(stages) == 4
        and [row["name"] for row in stages] == list(m4.STAGES)
        and stages[0]["state"] == "verified"
        and stages[0]["receipt_sha"] is not None
        and stages[1]["state"] == "awaiting_operator"
        and stages[1]["receipt_sha"] is None
        and stages[1]["intent_at"] is not None
        and all(row["state"] == "pending" for row in stages[2:]),
        "original M4 is not awaiting exactly one edited operation",
    )
    assert parent is not None
    absolute = min(
        queue.dt(plan["deadlineAt"]).timestamp(),
        queue.dt(plan["runAt"]).timestamp() + plan["maxElapsedSeconds"],
        queue.dt(parent["started_at"]).timestamp() + plan["maxElapsedSeconds"],
    )
    _require(
        math.isfinite(absolute) and time.time() + 60 < absolute,
        "original cumulative deadline expired or lacks 60-second headroom",
    )
    return absolute, str(stages[1]["operation_id"])


def _job_actor_pin(store: queue.Store, job_id: str) -> dict[str, object]:
    from . import resolve_test_bench_gui_stage as stage

    return stage.helper_actor_pin_from_authority(store, job_id)


def _consumed_gui(
    store: queue.Store, job_id: str, plan: dict[str, Any], operation: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Authenticate the *canonical* previously spent intent and pristine UID pin.

    No caller-provided success flag, alternate intent path, or replayed M4
    operation is accepted. This is read-only, not a claim of GUI success.
    """
    pristine = m4._stage_receipt(store, job_id, 0)
    _require(pristine["session"] == plan["baselineSession"], "baseline changed")
    path = m4._jobdir(store, job_id) / "f1-gui-edit" / "gui-intent.json"
    intent = json.loads(carrier._read(path, 32768))
    _require(
        isinstance(intent, dict)
        and set(intent)
        == {
            "schema",
            "jobId",
            "operationId",
            "actuatorClass",
            "target",
            "actorPin",
            "captureSha256",
            "itemUids",
            "expiresAt",
            "m4DeadlineAt",
            "m4PlanSha256",
        }
        and carrier._read(path, 32768) == queue.canonical(intent)
        and intent["schema"] == "vera.issue473-one-use-f1-gui/v2"
        and intent["jobId"] == job_id
        and intent["operationId"] == operation
        and intent["actuatorClass"] == gui.ACTUATOR_CLASS
        and intent["target"] == plan["initialTarget"]
        and gui._valid_actor_pin(intent["actorPin"])
        and intent["actorPin"] == _job_actor_pin(store, job_id)
        and intent["captureSha256"] == pristine["capture"]["sha256"]
        and intent["m4PlanSha256"] == hashlib.sha256(queue.canonical(plan)).hexdigest()
        and isinstance(intent["itemUids"], list)
        and len(intent["itemUids"]) == gui.NATIVE_ITEM_COUNT
        and len(set(intent["itemUids"])) == gui.NATIVE_ITEM_COUNT,
        "original GUI journal/source/operation or UID pins differ",
    )
    _require(
        queue.dt(intent["expiresAt"]) <= queue.dt(intent["m4DeadlineAt"])
        and queue.dt(intent["m4DeadlineAt"]) <= queue.dt(plan["deadlineAt"]),
        "GUI intent extends original M4 authority",
    )
    original = verify_native_result(
        Path(pristine["capture"]["path"]), pristine["capture"]["sha256"]
    )
    geometry = original.get("nativeGeometry")
    _require(
        original.get("status") == "complete"
        and original.get("action") == "capture_post"
        and original.get("target") == plan["initialTarget"]
        and isinstance(geometry, dict)
        and geometry.get("extentFrames") == gui.EXTENT_FRAMES
        and geometry.get("rate") == {"numerator": 24000, "denominator": 1001}
        and isinstance(geometry.get("tracks"), list)
        and len(geometry["tracks"]) == gui.NATIVE_TRACK_COUNT
        and isinstance(geometry.get("items"), list)
        and len(geometry["items"]) == gui.NATIVE_ITEM_COUNT
        and {row.get("itemUid") for row in geometry["items"] if isinstance(row, dict)}
        == set(intent["itemUids"]),
        "signed original pristine native geometry/UID set differs",
    )
    return pristine, original


def _prove_edited(
    store: queue.Store,
    job_id: str,
    plan: dict[str, Any],
    pristine: dict[str, Any],
    original: dict[str, Any],
    session: dict[str, str],
    capture: dict[str, str],
) -> None:
    """Full signed host/decoder verifier, before creating an M4 receipt.

    ``_verified_output`` reauthenticates the native *first* observe_edited,
    save_reopen, capture_pre, render queue/start/poll/post, and genuine MOV/PCM
    comparison. It also ensures the first effect follows the M4 stage intent.
    """
    from .resolve_test_queue_reverse import _items

    before = m4._verified_output(
        pristine,
        "pristine",
        plan["initialTarget"],
        plan["caseId"],
        m4._intent(store, job_id, 0),
    )[1]
    _require(
        before["nativeGeometry"] == original["nativeGeometry"],
        "pristine host capture changed during continuation",
    )
    after = m4._verified_output(
        {"session": session, "capture": capture},
        "edited",
        plan["initialTarget"],
        plan["caseId"],
        m4._intent(store, job_id, 1),
    )[1]
    geometry = after["nativeGeometry"]
    verify_supported_boundary(before["nativeGeometry"], geometry)
    # Explicitly retain every original UID and track; the boundary verifier
    # also rejects changed source mappings, links, audio and source-in.
    _require(
        _items(before["nativeGeometry"]).keys() == _items(geometry).keys()
        and before["nativeGeometry"]["tracks"] == geometry["tracks"],
        "edited host substituted native item IDs or track inventory",
    )


_SESSION_CONTEXT_FIELDS = frozenset(
    {
        "binding",
        "caseId",
        "executionDependenciesSha256",
        "executionDocumentSha256",
        "hostSourceGraphSha256",
        "installedReleaseSha256",
        "invocationId",
        "lane",
        "manifestSha256",
        "nativeSourceGraphSha256",
        "originalDependenciesSha256",
        "originalDocumentSha256",
        "packageSha256",
        "phase",
        "preflightSha256",
        "preparationSha256",
        "profileSha256",
        "reportSha256",
        "runtimeSha256",
        "target",
    }
)


def _same_source_distinct_edited_admission(controller: Any, baseline: Any) -> bool:
    """Authenticate byte-identical source across *distinct* sealed admissions.

    `prepare_output_session` copies the same source into a fresh output root for
    each phase, so the two verified admission.package_root absolute paths MUST
    differ. Checking absolute path equality rejects all legitimate fresh M4
    edited sessions. Compare the complete closed set of source/manifest/runtime
    hashes instead, after the independent loader authenticated each admission.
    """
    edited_context = controller.context
    pristine_context = baseline.context
    if (
        not isinstance(edited_context, dict)
        or not isinstance(pristine_context, dict)
        or set(edited_context) != _SESSION_CONTEXT_FIELDS
        or set(pristine_context) != _SESSION_CONTEXT_FIELDS
        or edited_context.get("phase") != "edited"
        or pristine_context.get("phase") != "pristine"
        or edited_context.get("invocationId") == pristine_context.get("invocationId")
        or edited_context.get("binding", {}).get("kind") != "baseline"
        or pristine_context.get("binding", {}).get("kind") != "baseline"
        or controller.admission.package_root == baseline.admission.package_root
        or controller.admission.admission_path == baseline.admission.admission_path
        or controller.release_root == baseline.release_root
        or controller.admission.profile != baseline.admission.profile
    ):
        return False
    excluded = {"phase", "invocationId", "binding"}
    return {k: v for k, v in edited_context.items() if k not in excluded} == {
        k: v for k, v in pristine_context.items() if k not in excluded
    }


def continue_from_session(
    store: queue.Store,
    job_id: str,
    *,
    session: dict[str, str],
    stage_root: Path,
    consent_reference: str,
    consent_instruction: str,
) -> dict[str, Any]:
    """One native host start after F1, never another GUI attempt.

    Run AFTER the F1 dispatcher has released its owner lock. The carrier's
    preflight_selected_disposable acquires that lock independently BEFORE the
    child native worker inherits it; holding the GUI lock here would deadlock.
    The official v2 host owns all native effects and refuses replay/UNKNOWN.
    """
    from .resolve_native_owner import _HELD_OWNER_FD, OWNER_FD_ENV, native_owner
    from .workflow_v2_cli import _verify_output_release

    _require(
        _HELD_OWNER_FD.get() is None and OWNER_FD_ENV not in os.environ,
        "GUI owner must be released before independent SDK carrier preflight",
    )
    plan = m4._load_plan(store, job_id)
    _require(plan["caseId"] == "synthetic-312", "unsupported original M4 case")
    # Short, read-only original owner checkpoint. Never keep this descriptor
    # across campaign.start: carrier.start's independent preflight also locks.
    with native_owner(output_lane=True):
        deadline, operation = _deadline(store, job_id, plan)
        pristine, original = _consumed_gui(store, job_id, plan, operation)
        ref = m4._ref(session, "edited output session")
        controller = output._session(Path(ref["path"]), ref["sha256"])
        baseline_controller = output._session(
            Path(pristine["session"]["path"]), pristine["session"]["sha256"]
        )
        _require(
            _same_source_distinct_edited_admission(controller, baseline_controller)
            and controller.context.get("caseId") == plan["caseId"]
            and controller.context.get("target") == plan["initialTarget"],
            "edited session is not a fresh admission of the original source/target",
        )
    manifest = _verify_output_release(controller.release_root)
    outcome = campaign.start(
        {
            "schema": campaign.SCHEMA,
            "root": str(stage_root),
            "session": ref,
            "installed": str(controller.release_root),
            "releaseManifestSha256": hashlib.sha256(
                carrier._read(manifest)
            ).hexdigest(),
            "caseId": plan["caseId"],
            "phase": "edited",
            "target": plan["initialTarget"],
            "deadlineUnix": deadline,
            "maxDiskBytes": plan["maxDiskBytes"],
            "consentReference": consent_reference,
            "consentInstruction": consent_instruction,
        }
    )
    _require(
        outcome.get("state") == "terminal_native_verified"
        and outcome.get("verified") is True
        and outcome.get("session") == ref,
        "native SDK host did not complete the independent edited chain",
    )
    capture = m4._ref(outcome.get("capture"), "edited host capture")
    _prove_edited(store, job_id, plan, pristine, original, ref, capture)
    # Recheck the same operation and deadline immediately before any receipt.
    latest_deadline, latest_operation = _deadline(store, job_id, plan)
    _require(
        latest_operation == operation and latest_deadline == deadline,
        "edited M4 stage/authority changed during native proof",
    )
    runner._submit_original(
        store, job_id, "edited", {"session": ref, "capture": capture}
    )
    report = m4.publish(store, job_id)
    _require(
        any(
            row["name"] == "edited" and row["state"] == "verified"
            for row in report["stages"]
        ),
        "original edited M4 receipt was not independently verified",
    )
    return {
        "state": "original_M4_edited_verified",
        "operationId": operation,
        "session": ref,
        "capture": capture,
    }


def start(store: queue.Store, job_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Prepare a fresh edited admission then invoke exactly one host chain.

    This intentionally refuses a previous incomplete edited session rather
    than re-admitting, replacing or concealing a partially spent effect.
    """
    from .qualification_output_controller_v2 import prepare_output_session

    value = runner.validate_config(config)
    plan = m4._load_plan(store, job_id)
    root = runner._absolute(value["root"], "root")
    _require(
        Path(value["queueRoot"]) == store.root
        and value["caseId"] == plan["caseId"]
        and value["maxDiskBytes"] == plan["maxDiskBytes"]
        and (root / "m4-plan.json").is_file()
        and carrier._read(root / "m4-plan.json") == queue.canonical(plan),
        "configuration does not own the original M4 enrollment",
    )
    _absolute_deadline, operation = _deadline(store, job_id, plan)
    _consumed_gui(store, job_id, plan, operation)
    source = runner._absolute(value["packageRoot"], "packageRoot")
    target = plan["initialTarget"]
    edited_root = root / "edited"
    session_path = prepare_output_session(
        edited_root,
        profile=value["profile"],
        package_root=source,
        preparation_paths=runner._matrix_preparation_paths(
            source, case_id=value["caseId"]
        ),
        narration_evidence_paths=runner._matrix_narration_paths(
            source,
            runner._absolute(value["narrationEvidenceRoot"], "narrationEvidenceRoot"),
            case_id=value["caseId"],
        ),
        target=target,
        case_id=value["caseId"],
        phase="edited",
    )
    return continue_from_session(
        store,
        job_id,
        session=output._pin(session_path),
        stage_root=root / "edited-stage",
        consent_reference=value["consentReference"],
        consent_instruction=value["consentInstruction"],
    )


def prepare_before_gui(
    store: queue.Store, job_id: str, config: dict[str, Any]
) -> dict[str, str]:
    """Prepare/authenticate ONE edited admission before Edit page or Roll.

    This intentionally does not require a consumed GUI journal: that journal
    MUST NOT exist yet. A caller cannot reprepare after a spent/unknown edit.
    """
    from .qualification_output_controller_v2 import prepare_output_session
    from .resolve_test_bench_gui_stage import helper_actor_pin_from_authority

    value = runner.validate_config(config)
    plan = m4._load_plan(store, job_id)
    root = runner._absolute(value["root"], "root")
    _require(
        Path(value["queueRoot"]) == store.root
        and value["caseId"] == plan["caseId"] == "synthetic-312"
        and value["maxDiskBytes"] == plan["maxDiskBytes"]
        and carrier._read(root / "m4-plan.json") == queue.canonical(plan),
        "fresh M4 configuration/source is not enrolled",
    )
    _, operation = _deadline(store, job_id, plan)
    journal_path = m4._jobdir(store, job_id) / "f1-gui-edit" / "gui-intent.json"
    admission_path = root / "edited-session-admission.json"
    _require(
        not journal_path.exists()
        and not journal_path.is_symlink()
        and not admission_path.exists()
        and not admission_path.is_symlink(),
        "prior edit/journal/admission cannot be re-used",
    )
    pristine = m4._stage_receipt(store, job_id, 0)
    _require(pristine["session"] == plan["baselineSession"], "pristine pin changed")
    source = runner._absolute(value["packageRoot"], "packageRoot")
    session_path = prepare_output_session(
        root / "edited",
        profile=value["profile"],
        package_root=source,
        preparation_paths=runner._matrix_preparation_paths(
            source, case_id=value["caseId"]
        ),
        narration_evidence_paths=runner._matrix_narration_paths(
            source,
            runner._absolute(value["narrationEvidenceRoot"], "narrationEvidenceRoot"),
            case_id=value["caseId"],
        ),
        target=plan["initialTarget"],
        case_id=value["caseId"],
        phase="edited",
    )
    ref = output._pin(session_path)
    prepared = output._session(Path(ref["path"]), ref["sha256"])
    baseline = output._session(
        Path(pristine["session"]["path"]), pristine["session"]["sha256"]
    )
    _require(
        _same_source_distinct_edited_admission(prepared, baseline)
        and prepared.context.get("target") == plan["initialTarget"],
        "edited session is not a fresh same-source admission",
    )
    carrier._once(
        admission_path,
        queue.canonical(
            {
                "schema": "vera.test-bench-edited-pre-gui-admission/v1",
                "jobId": job_id,
                "operationId": operation,
                "session": ref,
                "actorPin": helper_actor_pin_from_authority(store, job_id),
                "pristineCaptureSha256": pristine["capture"]["sha256"],
            }
        ),
    )
    return ref


def verify_prepared_identity(
    store: queue.Store,
    job_id: str,
    config: dict[str, Any],
    session: dict[str, str],
) -> None:
    """Read-only same-session/source check before Roll and after it.

    Neither a caller-provided pin nor an alternative path can silently
    substitute a new edited admission for this consumed one-use operation.
    """
    from .resolve_test_bench_gui_stage import helper_actor_pin_from_authority

    value = runner.validate_config(config)
    root = runner._absolute(value["root"], "root")
    plan = m4._load_plan(store, job_id)
    _absolute_deadline, operation = _deadline(store, job_id, plan)
    raw = carrier._read(root / "edited-session-admission.json", 32768)
    admission = json.loads(raw)
    pristine = m4._stage_receipt(store, job_id, 0)
    _require(
        type(admission) is dict
        and queue.canonical(admission) == raw
        and set(admission)
        == {
            "schema",
            "jobId",
            "operationId",
            "session",
            "actorPin",
            "pristineCaptureSha256",
        }
        and admission["schema"] == "vera.test-bench-edited-pre-gui-admission/v1"
        and admission["jobId"] == job_id
        and admission["operationId"] == operation
        and admission["session"] == session
        and admission["actorPin"] == helper_actor_pin_from_authority(store, job_id)
        and admission["pristineCaptureSha256"] == pristine["capture"]["sha256"],
        "pre-Roll edited session, actor or pristine pins changed",
    )
    _require(
        type(session) is dict
        and set(session) == {"path", "sha256"}
        and type(session["path"]) is str
        and Path(session["path"]).is_absolute()
        and not Path(session["path"]).is_symlink(),
        "aliased or invalid edited-session path",
    )
    prepared = output._session(Path(session["path"]), session["sha256"])
    baseline = output._session(
        Path(pristine["session"]["path"]), pristine["session"]["sha256"]
    )
    _require(
        _same_source_distinct_edited_admission(prepared, baseline)
        and prepared.context.get("target") == plan["initialTarget"],
        "same edited session no longer authenticates after Roll",
    )


def continue_prepared_after_gui(
    store: queue.Store,
    job_id: str,
    config: dict[str, Any],
    session: dict[str, str],
) -> dict[str, Any]:
    """Reauthenticate the SAME pre-Roll session, then invoke original host."""
    verify_prepared_identity(store, job_id, config, session)
    value = runner.validate_config(config)
    root = runner._absolute(value["root"], "root")
    return continue_from_session(
        store,
        job_id,
        session=session,
        stage_root=root / "edited-stage",
        consent_reference=value["consentReference"],
        consent_instruction=value["consentInstruction"],
    )
