"""#473 original M4 accepted A revision and distinct source-sealed native rebuild.

This is a continuation of the *same* four-stage M4 job, not a second queue or
an alternative Resolve adapter. Only the unambiguous, measured picture-only A
policy is eligible for unattended acceptance. Unresolved semantic decisions,
source drift, spent slots and UNKNOWN native effects are hard stops.

The public starts here are for the separately authorized *new* campaign only.
They must never be pointed at an expired, previously source-sealed run.
"""

from __future__ import annotations

import hashlib
import json
import math
import time
from pathlib import Path
from typing import Any

from . import resolve_test_bench_campaign as campaign
from . import resolve_test_bench_carrier as carrier
from . import resolve_test_bench_m4_runner as runner
from . import resolve_test_bench_output as output
from . import resolve_test_queue as queue
from . import resolve_test_queue_m4 as m4
from .resolve_test_queue_reverse import (
    verify_reverse_receipts,
    verify_supported_boundary,
)


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise queue.QueueError("original M4 revision/rebuild refused: " + reason)


def _stage(
    store: queue.Store, job_id: str, plan: dict[str, Any], ordinal: int
) -> tuple[float, str]:
    """CAS-like readback of the only open original operation and lifetime."""
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
        and all(
            row["state"] == "verified" and row["receipt_sha"] is not None
            for row in stages[:ordinal]
        )
        and stages[ordinal]["state"] == "awaiting_operator"
        and stages[ordinal]["intent_at"] is not None
        and stages[ordinal]["receipt_sha"] is None
        and all(row["state"] == "pending" for row in stages[ordinal + 1 :]),
        "one exact original M4 stage and preceding signed receipts required",
    )
    assert parent is not None
    deadline = min(
        queue.dt(plan["deadlineAt"]).timestamp(),
        queue.dt(plan["runAt"]).timestamp() + plan["maxElapsedSeconds"],
        queue.dt(parent["started_at"]).timestamp() + plan["maxElapsedSeconds"],
    )
    _require(
        math.isfinite(deadline) and time.time() + 60 < deadline,
        "original cumulative deadline expired or lacks 60 seconds",
    )
    return deadline, str(stages[ordinal]["operation_id"])


def _inputs(
    store: queue.Store, job_id: str, value: dict[str, Any]
) -> tuple[dict[str, Any], Path]:
    plan = m4._load_plan(store, job_id)
    root = runner._absolute(value["root"], "root")
    _require(
        value["caseId"] == plan["caseId"] == "synthetic-312"
        and Path(value["queueRoot"]) == store.root
        and value["maxDiskBytes"] == plan["maxDiskBytes"]
        and value["maxElapsedSeconds"] == plan["maxElapsedSeconds"]
        and value["name"] == plan["name"]
        and plan["initialTarget"] != plan["freshTarget"]
        and carrier._read(root / "m4-plan.json") == queue.canonical(plan),
        "original case, immutable plan, source roots or fresh target differ",
    )
    return plan, root


def _policy_decision(proposal_hash: str) -> dict[str, str]:
    """Closed synthetic A authority; never choose a creative/omission branch."""
    _require(
        isinstance(proposal_hash, str)
        and proposal_hash.startswith("sha256:")
        and len(proposal_hash) == 71
        and all(c in "0123456789abcdef" for c in proposal_hash[7:]),
        "authenticated canonical proposal identity required",
    )
    return {
        "schemaVersion": "qualification-output-decision/v1",
        "proposalHash": proposal_hash,
        "historyHash": "sha256:" + hashlib.sha256(b"[]\n").hexdigest(),
        "outcome": "accept",
    }


def _accept_synthetic_a(proof: Any) -> None:
    """Apply ONLY the already approved deterministic 327→351 picture policy.

    For other case kinds, conflicts, narration replacement or unconstrained
    inference, the Producer must authorize a different workflow; no fallback
    to an invented decision, inferred timestamp or external provider call.
    """
    proof.observe("synthetic-312")
    inference = proof.infer()
    commands = inference.get("commands")
    _require(
        inference.get("caseKinds") == ["A"]
        and inference.get("boundaryConflicts") == []
        and inference.get("omission") is None
        and isinstance(commands, dict)
        and isinstance(commands.get("boundary"), dict)
        and commands.get("trim") is None,
        "policy does not authorize creative, ambiguous or audio edits",
    )
    stage = proof.decide_inference(_policy_decision(inference["inferenceHash"]))
    _require(
        stage.get("outcome") == "accept" and stage.get("regeneration") is None,
        "revision would need narration replacement or external regeneration",
    )
    candidate = proof.proposal()
    _require(
        candidate.get("inferenceDecision", {}).get("outcome") == "accept"
        and candidate.get("inferenceHistory") == []
        and candidate.get("request", {}).get("handoff") is None
        and candidate.get("request", {}).get("preparedMedia") == [],
        "not an unambiguous zero-provider accepted A proposal",
    )
    accepted = proof.decide(_policy_decision(candidate["proposalHash"]))
    _require(accepted.get("outcome") == "accept", "revised package not accepted")


def _revised_media_paths(
    source_package: Path, revised_manifest_path: Path, *, case_id: str
) -> dict[str, Path]:
    """Bind an accepted A revision to the original *verified* 11-event media.

    This closed source-matrix policy forbids synthesizing a missing asset,
    selecting an arbitrary same-basename file or changing a media/source hash.
    The accepted A revision moves one existing cut; it cannot replace media.
    """
    from . import v2_package

    _require(case_id == "synthetic-312", "unapproved revised media matrix")
    verified = v2_package.verify_v2_package(source_package)
    original_build = source_package / "Builds" / verified.build_id
    original = json.loads((original_build / v2_package.MANIFEST_FILENAME).read_bytes())
    revised = json.loads(revised_manifest_path.read_bytes())
    _require(
        original.get("sources") == revised.get("sources")
        and isinstance(revised.get("events"), list)
        and len(original.get("events", [])) == len(revised["events"]) == 11,
        "accepted A revision changed immutable source/media inventory",
    )
    original_events = {row["eventId"]: row for row in original["events"]}
    revised_events = {row["eventId"]: row for row in revised["events"]}
    _require(
        len(original_events) == len(revised_events) == 11
        and set(original_events) == set(revised_events),
        "accepted A revision changed event identities",
    )

    def require_media(directory: Path, identifier: str, expected: str) -> Path:
        _require(
            isinstance(identifier, str)
            and bool(identifier)
            and "/" not in identifier
            and ".." not in identifier
            and isinstance(expected, str)
            and expected.startswith("sha256:")
            and len(expected) == 71,
            "invalid revised media identifier or hash",
        )
        matches = list(directory.glob(identifier + ".*"))
        _require(
            len(matches) == 1 and matches[0].is_file() and not matches[0].is_symlink(),
            "ambiguous or absent verified revised source media",
        )
        path = matches[0]
        v2_package._require_path_components_no_symlink(path, "source media")
        _require(
            "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest() == expected,
            "original verified source/media hash differs from accepted revision",
        )
        return path

    paths: dict[str, Path] = {}
    for source in revised["sources"]:
        identifier = source["id"]
        narration = source.get("narrationAudio")
        if isinstance(narration, dict):
            paths["source:" + identifier] = require_media(
                source_package / "Media/Narration", identifier, narration["audioHash"]
            )
        else:
            paths["source:" + identifier] = require_media(
                source_package / "Media/Resolved", identifier, source["deliveredHash"]
            )
            paths["original:" + identifier] = require_media(
                original_build / "Preparation/original",
                identifier,
                source["originalHash"],
            )
    for identifier, event in revised_events.items():
        prior = original_events[identifier]
        _require(
            event.get("kind") == prior.get("kind"),
            "accepted A revision changed event kind",
        )
        if event["kind"] == "placeholder":
            _require(
                event.get("pictureTreatment") == prior.get("pictureTreatment"),
                "accepted A revision changed placeholder media",
            )
            # The original public package has already independently verified
            # the exact generated PNG. The new revision retains its treatment.
            from .v2_package import _hash_bytes, _render_slate

            treatment = event["pictureTreatment"]
            if treatment["kind"] == "slate":
                timeline = revised["timeline"]
                expected = _hash_bytes(
                    _render_slate(
                        treatment["text"], timeline["width"], timeline["height"]
                    )
                )
            else:
                expected = treatment["reference"]["contentHash"]
            paths["event:" + identifier] = require_media(
                source_package / "Media/Resolved", identifier, expected
            )
        _require(
            event["kind"] != "source_audio",
            "no unqualified source-audio sidecar fallback in revised A matrix",
        )
    return paths


def revision(store: queue.Store, job_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """One accepted host proof, original revision M4 receipt; zero native effects."""
    from .qualification_output_proof_v2 import (
        QualificationOutputProofV2,
        prepare_output_proof_v2,
        verify_revised_preflight_v2,
    )

    value = runner.validate_config(config)
    plan, root = _inputs(store, job_id, value)
    deadline, operation = _stage(store, job_id, plan, 2)
    pristine = m4._stage_receipt(store, job_id, 0)
    edited = m4._stage_receipt(store, job_id, 1)
    _require(pristine["session"] == plan["baselineSession"], "pristine pin changed")
    first = m4._verified_output(
        pristine,
        "pristine",
        plan["initialTarget"],
        plan["caseId"],
        m4._intent(store, job_id, 0),
    )[1]
    second = m4._verified_output(
        edited,
        "edited",
        plan["initialTarget"],
        plan["caseId"],
        m4._intent(store, job_id, 1),
    )[1]
    boundary = verify_supported_boundary(
        first["nativeGeometry"], second["nativeGeometry"]
    )
    _require(
        boundary.get("fromFrame") == 327 and boundary.get("toFrame") == 351,
        "only original approved F1 movement eligible",
    )
    proof_root = root / "revision"
    _require(
        not proof_root.exists() and not proof_root.is_symlink(),
        "prior revision proof exists; inspect, never replay",
    )
    session_path = prepare_output_proof_v2(
        proof_root,
        baseline_session=Path(pristine["session"]["path"]),
        baseline_sha256=pristine["session"]["sha256"],
        edited_session=Path(edited["session"]["path"]),
        edited_sha256=edited["session"]["sha256"],
    )
    proof_pin = output._pin(session_path)
    proof = QualificationOutputProofV2(session_path, proof_pin["sha256"])
    _accept_synthetic_a(proof)
    preflight_path = proof.prepare_revised_preflight()
    verify_revised_preflight_v2(preflight_path, output._pin(preflight_path)["sha256"])
    _require(
        _stage(store, job_id, plan, 2) == (deadline, operation),
        "original revision CAS/operation/deadline changed during proof",
    )
    runner._submit_original(store, job_id, "revision", {"proof": proof_pin})
    report = m4.publish(store, job_id)
    _require(
        report["state"] == "queued" and report["stages"][2]["state"] == "verified",
        "original revision M4 receipt not authenticated",
    )
    return {
        "state": "original_M4_revision_verified",
        "operationId": operation,
        "proof": proof_pin,
    }


def rebuild(store: queue.Store, job_id: str, config: dict[str, Any]) -> dict[str, Any]:
    """Reserve distinct fresh target, run official SDK host, verify MOV/PCM."""
    from .qualification_output_proof_v2 import (
        QualificationOutputProofV2,
        build_output_revision_package,
        prepare_revised_output_session,
    )
    from .v2_package import verify_v2_package
    from .workflow_v2_cli import _verify_output_release

    value = runner.validate_config(config)
    plan, root = _inputs(store, job_id, value)
    deadline, operation = _stage(store, job_id, plan, 3)
    pristine = m4._stage_receipt(store, job_id, 0)
    edited = m4._stage_receipt(store, job_id, 1)
    revision_receipt = m4._stage_receipt(store, job_id, 2)
    proof_pin = revision_receipt["proof"]
    proof = QualificationOutputProofV2(Path(proof_pin["path"]), proof_pin["sha256"])
    accepted, _candidate = proof.accepted_revision()
    _require(
        accepted.get("outcome") == "accept"
        and proof.session["baselineSession"] == pristine["session"]
        and proof.session["editedSession"] == edited["session"]
        and proof.baseline.context.get("target") == plan["initialTarget"]
        and proof.edited.context.get("target") == plan["initialTarget"],
        "accepted proof does not bind original same-target M4 chain",
    )
    rebuild_root = root / "rebuild"
    revised_package_root = root / "rebuild-package"
    _require(
        not rebuild_root.exists()
        and not rebuild_root.is_symlink()
        and not revised_package_root.exists()
        and not revised_package_root.is_symlink(),
        "prior fresh rebuild or revised package reserved; inspect, never replay",
    )
    source = runner._absolute(value["packageRoot"], "packageRoot")
    preparations = runner._matrix_preparation_paths(source, case_id=value["caseId"])
    narrations = runner._matrix_narration_paths(
        source,
        runner._absolute(value["narrationEvidenceRoot"], "narrationEvidenceRoot"),
        case_id=value["caseId"],
    )
    revised_media = _revised_media_paths(
        source, proof.root / "revision-manifest.json", case_id=value["caseId"]
    )
    build_output_revision_package(
        Path(proof_pin["path"]),
        proof_pin["sha256"],
        revised_package_root,
        media_paths=revised_media,
        preparation_paths=preparations,
    )
    verified_revised = verify_v2_package(revised_package_root)
    _require(
        verified_revised.build_id
        == json.loads((proof.root / "revision-manifest.json").read_bytes())["buildId"],
        "materialized revised public package build differs from accepted revision",
    )
    path = prepare_revised_output_session(
        rebuild_root,
        proof_session=Path(proof_pin["path"]),
        proof_sha256=proof_pin["sha256"],
        package_root=revised_package_root,
        preparation_paths=preparations,
        narration_evidence_paths=narrations,
        target=plan["freshTarget"],
    )
    session = output._pin(path)
    controller = output._session(path, session["sha256"])
    _require(
        controller.context.get("phase") == "rebuild"
        and controller.context.get("target") == plan["freshTarget"]
        and controller.revised_preflight is not None
        and plan["freshTarget"]["projectUid"] != plan["initialTarget"]["projectUid"]
        and plan["freshTarget"]["timelineUid"] != plan["initialTarget"]["timelineUid"],
        "signed revised package not reserved to independent fresh target",
    )
    manifest = _verify_output_release(controller.release_root)
    outcome = campaign.start(
        {
            "schema": campaign.SCHEMA,
            "root": str(root / "rebuild-stage"),
            "session": session,
            "installed": str(controller.release_root),
            "releaseManifestSha256": hashlib.sha256(
                carrier._read(manifest)
            ).hexdigest(),
            "caseId": plan["caseId"],
            "phase": "rebuild",
            "target": plan["freshTarget"],
            "deadlineUnix": deadline,
            "maxDiskBytes": plan["maxDiskBytes"],
            "consentReference": value["consentReference"],
            "consentInstruction": value["consentInstruction"],
        }
    )
    _require(
        outcome.get("state") == "terminal_native_verified"
        and outcome.get("verified") is True
        and outcome.get("session") == session,
        "fresh official SDK host did not finish real MOV/PCM",
    )
    capture = m4._ref(outcome.get("capture"), "fresh signed native capture")
    m4._verified_output(
        {"session": session, "capture": capture},
        "rebuild",
        plan["freshTarget"],
        plan["caseId"],
        m4._intent(store, job_id, 3),
    )
    verdict = verify_reverse_receipts(
        proof_path=Path(proof_pin["path"]),
        proof_sha256=proof_pin["sha256"],
        pristine_result_path=Path(pristine["capture"]["path"]),
        pristine_result_sha256=pristine["capture"]["sha256"],
        edited_result_path=Path(edited["capture"]["path"]),
        edited_result_sha256=edited["capture"]["sha256"],
        fresh_session_path=path,
        fresh_session_sha256=session["sha256"],
        fresh_result_path=Path(capture["path"]),
        fresh_result_sha256=capture["sha256"],
    )
    _require(
        verdict.get("status") == "verified"
        and verdict.get("provenance") == "host_authenticated_no_replay",
        "strict #312 reverse verifier refused signed final MOV/PCM chain",
    )
    _require(
        _stage(store, job_id, plan, 3) == (deadline, operation),
        "original rebuild CAS/operation/deadline changed during host work",
    )
    runner._submit_original(
        store, job_id, "rebuild", {"session": session, "capture": capture}
    )
    report = m4.publish(store, job_id)
    _require(
        report["state"] == "completed_verified"
        and report["readyFor312Phase2"] is True
        and [step["state"] for step in report["stages"]] == ["verified"] * 4
        and (m4._jobdir(store, job_id) / "handoff-private.json").is_file(),
        "original M4 four-stage signed handoff still incomplete",
    )
    return {
        "state": "original_M4_four_stages_verified",
        "operationId": operation,
        "session": session,
        "capture": capture,
    }
