"""Code-only, injected original-M4 revision and fresh SDK rebuild regressions."""

from __future__ import annotations

import copy
import json
import uuid
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_proof_v2 as proof_module
from vera_timeline_agent import resolve_test_bench_campaign as campaign
from vera_timeline_agent import resolve_test_bench_m4_runner as runner
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_bench_revision_stage as revision
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent import v2_package, workflow_v2_cli


def target() -> dict[str, str]:
    name = f"VERA Delivery {uuid.uuid4()} {uuid.uuid4().hex[:12]}"
    return {
        "projectUid": str(uuid.uuid4()),
        "timelineUid": str(uuid.uuid4()),
        "projectName": name,
        "timelineName": name,
    }


def geometry(phase: str, selected: dict[str, str]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for index in range(11):
        rows.append(
            {
                "itemUid": f"native-{index}",
                "kind": "video" if index < 5 else "audio",
                "trackId": "V1" if index < 2 else f"other-{index % 6}",
                "eventId": f"event-{index}",
                "mediaUid": f"media-{index}",
                "sourceId": f"source-{index}",
                "sourceStart": 0,
                "sourceDuration": 327 if index == 0 else 151 if index == 1 else 100,
                "recordStart": 0
                if index == 0
                else 327
                if index == 1
                else 600 + index * 20,
                "recordDuration": 327 if index == 0 else 151 if index == 1 else 100,
                "linkedItemUids": [],
            }
        )
    if phase == "edited":
        rows[0]["recordDuration"] += 24
        rows[0]["sourceDuration"] += 24
        rows[1]["recordStart"] += 24
        rows[1]["recordDuration"] -= 24
        rows[1]["sourceDuration"] -= 24
    return {
        "context": {"target": selected, "phase": phase},
        "rate": {"numerator": 24000, "denominator": 1001},
        "extentFrames": 1407,
        "tracks": [{"trackId": f"track-{i}"} for i in range(6)],
        "sourceMappings": [{"sourceId": f"source-{i}"} for i in range(11)],
        "items": rows,
    }


class FakeProof:
    regeneration: Any = None
    accepted: str = "accept"

    def __init__(self, _path: Path, _digest: str, original: dict[str, Any]):
        self.inference: dict[str, Any] = {
            "caseKinds": ["A"],
            "boundaryConflicts": [],
            "omission": None,
            "commands": {"boundary": {"kind": "move_word_boundary"}, "trim": None},
            "inferenceHash": "sha256:" + "1" * 64,
        }
        self.session = {
            "baselineSession": original["baselineSession"],
            "editedSession": original["editedSession"],
        }
        self.baseline = SimpleNamespace(context={"target": original["initialTarget"]})
        self.edited = SimpleNamespace(context={"target": original["initialTarget"]})
        self.root = _path.parent
        self.decisions: list[dict[str, Any]] = []

    def observe(self, case: str) -> None:
        assert case == "synthetic-312"

    def infer(self) -> dict[str, Any]:
        return copy.deepcopy(self.inference)

    def decide_inference(self, decision: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(decision)
        return {"outcome": "accept", "regeneration": self.regeneration}

    def proposal(self) -> dict[str, Any]:
        return {
            "inferenceDecision": {"outcome": "accept"},
            "inferenceHistory": [],
            "request": {"handoff": None, "preparedMedia": []},
            "proposalHash": "sha256:" + "2" * 64,
        }

    def decide(self, decision: dict[str, Any]) -> dict[str, Any]:
        self.decisions.append(decision)
        return {"outcome": self.accepted}

    def accepted_revision(self) -> tuple[dict[str, Any], dict[str, Any]]:
        return {"outcome": self.accepted}, {}

    def prepare_revised_preflight(self) -> Path:
        path = self.root / "revised-preflight.json"
        path.write_bytes(b"signed-mock-preflight")
        return path


@pytest.fixture
def campaign_fixture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    from vera_timeline_agent import qualification_output_controller_v2 as ctl
    from vera_timeline_agent import qualification_output_native_v2 as native

    root = tmp_path / "new-campaign"
    root.mkdir(mode=0o700)
    store = queue.Store(root / "queue")
    initial, fresh = target(), target()
    baseline = {"path": str(root / "pristine/session.json"), "sha256": "a" * 64}
    edited = {"path": str(root / "edited/session.json"), "sha256": "b" * 64}
    config = {
        "schema": runner.SCHEMA,
        "root": str(root),
        "queueRoot": str(store.root),
        "packageRoot": str(tmp_path / "public-package"),
        "narrationEvidenceRoot": str(tmp_path / "private-narration"),
        "name": "synthetic-new-m4",
        "caseId": "synthetic-312",
        "profile": "qualification-output-studio-matrix/v1",
        "maxElapsedSeconds": 7200,
        "maxDiskBytes": 1024 * 1024,
        "consentReference": "new-specific-authorization",
        "consentInstruction": "Producer approved this new sacrificial exact roll",
        "merged472Commit": "a" * 40,
    }
    now = queue.now_utc()
    plan = m4.validate_plan(
        {
            "schema": m4.SCHEMA,
            "name": "synthetic-new-m4",
            "caseId": "synthetic-312",
            "baselineSession": baseline,
            "initialTarget": initial,
            "freshTarget": fresh,
            "maxElapsedSeconds": 7200,
            "maxDiskBytes": 1024 * 1024,
            "runAt": queue.iso(now - timedelta(seconds=1)),
            "deadlineAt": queue.iso(now + timedelta(hours=3)),
        }
    )
    (root / "m4-plan.json").write_bytes(queue.canonical(plan))
    monkeypatch.setattr(
        ctl,
        "load_output_session",
        lambda *_: SimpleNamespace(
            context={"phase": "pristine", "caseId": "synthetic-312", "target": initial}
        ),
    )
    monkeypatch.setattr(native, "native_request_paths", lambda *_: (root / "none",) * 4)
    monkeypatch.setattr(m4, "preflight_selected_disposable", lambda *_a, **_k: None)
    # Inject only the external signed native-result verifier; leave the REAL
    # M4 durable enqueue/CAS, operation IDs, receipts, worker and handoff active.
    monkeypatch.setattr(m4, "_verify_stage", lambda *_: None)
    job = m4.enqueue(store, root / "m4-plan.json")
    assert m4.worker_tick(store) is True
    runner._submit_original(
        store,
        job,
        "pristine",
        {
            "session": baseline,
            "capture": {"path": "/mock/pristine", "sha256": "c" * 64},
        },
    )
    assert m4.worker_tick(store) is True
    runner._submit_original(
        store,
        job,
        "edited",
        {"session": edited, "capture": {"path": "/mock/edited", "sha256": "d" * 64}},
    )
    assert m4.publish(store, job)["state"] == "queued"
    assert m4.worker_tick(store) is True
    monkeypatch.setattr(
        m4,
        "_verified_output",
        lambda _receipt, phase, *_: (
            None,
            {"nativeGeometry": geometry(phase, initial)},
        ),
    )
    original = {
        "initialTarget": initial,
        "freshTarget": fresh,
        "baselineSession": baseline,
        "editedSession": edited,
    }
    last_proof: list[FakeProof] = []

    def new_proof(path: Path, digest: str) -> FakeProof:
        result = FakeProof(path, digest, original)
        last_proof.append(result)
        return result

    def prepare(proof_root: Path, **kwargs: Any) -> Path:
        assert kwargs["baseline_sha256"] == baseline["sha256"]
        assert kwargs["edited_sha256"] == edited["sha256"]
        proof_root.mkdir(mode=0o700)
        path = proof_root / "session.json"
        path.write_bytes(b"mock-signed-proof")
        return path

    monkeypatch.setattr(proof_module, "QualificationOutputProofV2", new_proof)
    monkeypatch.setattr(proof_module, "prepare_output_proof_v2", prepare)
    monkeypatch.setattr(
        proof_module, "verify_revised_preflight_v2", lambda *_: {"status": "verified"}
    )
    return {
        "root": root,
        "store": store,
        "job": job,
        "config": config,
        "plan": plan,
        "proofs": last_proof,
        "original": original,
    }


def test_original_revision_signed_receipt_and_unique_operation(
    campaign_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = campaign_fixture
    operation = revision._stage(fixture["store"], fixture["job"], fixture["plan"], 2)[1]
    accepted = revision.revision(fixture["store"], fixture["job"], fixture["config"])
    assert accepted["operationId"] == operation
    assert accepted["state"] == "original_M4_revision_verified"
    receipt = m4._stage_receipt(fixture["store"], fixture["job"], 2)
    assert receipt["operationId"] == operation
    assert set(receipt) == {"schema", "stage", "operationId", "proof"}
    decisions = fixture["proofs"][-1].decisions
    assert len(decisions) == 2
    assert [d["proposalHash"] for d in decisions] == [
        "sha256:" + "1" * 64,
        "sha256:" + "2" * 64,
    ]
    with pytest.raises(queue.QueueError, match="one exact original M4 stage"):
        revision.revision(fixture["store"], fixture["job"], fixture["config"])


@pytest.mark.parametrize(
    "defect",
    [
        "wrong_case",
        "conflict",
        "omission",
        "changed_audio",
        "missing_boundary",
        "needs_regeneration",
        "rejected",
        "bad_hash",
    ],
)
def test_policy_refuses_unapproved_or_ambiguous_inference(
    tmp_path: Path,
    defect: str,
) -> None:
    source: dict[str, Any] = {
        "baselineSession": {},
        "editedSession": {},
        "initialTarget": {},
    }
    fake = FakeProof(tmp_path / "session.json", "a" * 64, source)
    if defect == "wrong_case":
        fake.inference["caseKinds"] = ["B"]
    elif defect == "conflict":
        fake.inference["boundaryConflicts"] = [{"choices": ["invented"]}]
    elif defect == "omission":
        fake.inference["omission"] = {"tokenIds": ["other"]}
    elif defect == "changed_audio":
        fake.inference["commands"]["trim"] = {"kind": "trim_audio"}
    elif defect == "missing_boundary":
        fake.inference["commands"]["boundary"] = None
    elif defect == "needs_regeneration":
        fake.regeneration = {"provider": "not-approved"}
    elif defect == "rejected":
        fake.accepted = "reject"
    elif defect == "bad_hash":
        fake.inference["inferenceHash"] = "not-hash"
    with pytest.raises(queue.QueueError, match=r"policy|revision|canonical|accepted"):
        revision._accept_synthetic_a(fake)


@pytest.mark.parametrize(
    "change",
    [
        "expired",
        "parent_unknown",
        "wrong_operation",
        "prior_unknown",
        "next_started",
    ],
)
def test_revision_stage_rejects_unknown_or_stale_cas_before_proof(
    campaign_fixture: dict[str, Any],
    change: str,
) -> None:
    fixture = campaign_fixture
    with fixture["store"].connect() as db:
        if change == "expired":
            db.execute(
                "UPDATE reverse_jobs SET started_at=? WHERE id=?",
                (queue.iso(queue.now_utc() - timedelta(hours=3)), fixture["job"]),
            )
        elif change == "parent_unknown":
            db.execute(
                "UPDATE reverse_jobs SET state='unknown' WHERE id=?", (fixture["job"],)
            )
        elif change == "wrong_operation":
            db.execute(
                "UPDATE reverse_stages SET state='unknown' "
                "WHERE job_id=? AND ordinal=2",
                (fixture["job"],),
            )
        elif change == "prior_unknown":
            db.execute(
                "UPDATE reverse_stages SET state='unknown' "
                "WHERE job_id=? AND ordinal=1",
                (fixture["job"],),
            )
        elif change == "next_started":
            db.execute(
                "UPDATE reverse_stages SET state='awaiting_operator' "
                "WHERE job_id=? AND ordinal=3",
                (fixture["job"],),
            )
    with pytest.raises(queue.QueueError, match=r"stage|deadline"):
        revision.revision(fixture["store"], fixture["job"], fixture["config"])
    assert not (fixture["root"] / "revision").exists()


def test_edited_host_mutation_refuses_before_revision_decision(
    campaign_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = campaign_fixture
    monkeypatch.setattr(
        m4,
        "_verified_output",
        lambda _receipt, phase, *_: (
            None,
            {"nativeGeometry": geometry("pristine", fixture["plan"]["initialTarget"])},
        ),
    )
    with pytest.raises(ValueError, match="two boundary picture items"):
        revision.revision(fixture["store"], fixture["job"], fixture["config"])
    assert not (fixture["root"] / "revision").exists()


@pytest.mark.parametrize("field", ["maxElapsedSeconds", "name", "maxDiskBytes"])
def test_revised_chain_cannot_change_original_queue_bounds(
    campaign_fixture: dict[str, Any],
    field: str,
) -> None:
    fixture = campaign_fixture
    config = copy.deepcopy(fixture["config"])
    config[field] = (
        config[field] + 1 if isinstance(config[field], int) else "altered-name"
    )
    with pytest.raises(queue.QueueError, match=r"original|bounds|case|configuration"):
        revision.revision(fixture["store"], fixture["job"], config)
    assert not (fixture["root"] / "revision").exists()


def _prepare_rebuild(
    fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    *,
    outcome: str = "terminal_native_verified",
    verdict: str = "verified",
    change_target: bool = False,
) -> list[dict[str, Any]]:
    revision.revision(fixture["store"], fixture["job"], fixture["config"])
    assert m4.worker_tick(fixture["store"]) is True
    root = fixture["root"]
    fresh = fixture["plan"]["freshTarget"]
    calls: list[dict[str, Any]] = []
    revision_build_id = "2ae6c5ae-03f4-4f28-8012-04ea7ded20d5"
    (root / "revision/revision-manifest.json").write_text(
        json.dumps({"buildId": revision_build_id}), encoding="utf-8"
    )

    def materialize(
        proof_path: Path,
        proof_sha256: str,
        output_root: Path,
        *,
        media_paths: dict[str, Path],
        preparation_paths: dict[str, Path],
    ) -> Path:
        calls.append(
            {
                "kind": "materialize",
                "proof_path": proof_path,
                "proof_sha256": proof_sha256,
                "output_root": output_root,
                "media_paths": media_paths,
                "preparation_paths": preparation_paths,
            }
        )
        output_root.mkdir(mode=0o700)
        return output_root

    def prepare(path: Path, **kwargs: Any) -> Path:
        # This regression fails against the old original-package path, even
        # though the real package admission host itself is injected here.
        assert calls and calls[0]["kind"] == "materialize"
        assert kwargs["package_root"] == calls[0]["output_root"]
        assert kwargs["package_root"] != Path(fixture["config"]["packageRoot"])
        assert kwargs["package_root"].is_dir()
        calls.append({"kind": "revised_admission", **kwargs})
        path.mkdir(mode=0o700)
        saved = path / "session.json"
        saved.write_bytes(b"mock-revised-signed-session")
        return saved

    monkeypatch.setattr(proof_module, "prepare_revised_output_session", prepare)
    monkeypatch.setattr(proof_module, "build_output_revision_package", materialize)
    monkeypatch.setattr(
        revision,
        "_revised_media_paths",
        lambda *_a, **_k: {"source:verified": root / "verified-source.mov"},
    )
    monkeypatch.setattr(
        v2_package,
        "verify_v2_package",
        lambda *_a, **_k: v2_package.V2PackageVerification(
            revision_build_id, 11, 0, 11
        ),
    )
    monkeypatch.setattr(runner, "_matrix_preparation_paths", lambda *_a, **_k: {})
    monkeypatch.setattr(runner, "_matrix_narration_paths", lambda *_a, **_k: {})
    installed = root / "reviewed-release"
    installed.mkdir(mode=0o700)
    manifest = installed / "manifest.json"
    manifest.write_bytes(b"mock-review-release")
    monkeypatch.setattr(workflow_v2_cli, "_verify_output_release", lambda *_: manifest)
    monkeypatch.setattr(
        output,
        "_session",
        lambda *_: SimpleNamespace(
            context={
                "phase": "rebuild",
                "target": fixture["plan"]["initialTarget"] if change_target else fresh,
            },
            release_root=installed,
            revised_preflight=(root / "revision/revised-preflight.json", "e" * 64),
        ),
    )

    def start_native(plan: dict[str, Any]) -> dict[str, Any]:
        calls.append(plan)
        return {
            "state": outcome,
            "verified": outcome == "terminal_native_verified",
            "session": plan["session"],
            "capture": {"path": "/mock/new-authenticated-rebuild", "sha256": "e" * 64},
        }

    monkeypatch.setattr(campaign, "start", start_native)
    monkeypatch.setattr(
        revision,
        "verify_reverse_receipts",
        lambda **_: {"status": verdict, "provenance": "host_authenticated_no_replay"},
    )
    return calls


def test_distinct_rebuild_and_original_four_receipts_end_to_end_fake_host(
    campaign_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = campaign_fixture
    calls = _prepare_rebuild(fixture, monkeypatch)
    result = revision.rebuild(fixture["store"], fixture["job"], fixture["config"])
    assert result["state"] == "original_M4_four_stages_verified"
    assert calls[0]["output_root"] == fixture["root"] / "rebuild-package"
    assert calls[1]["package_root"] == fixture["root"] / "rebuild-package"
    assert calls[1]["target"] == fixture["plan"]["freshTarget"]
    assert calls[2]["target"] == fixture["plan"]["freshTarget"]
    assert calls[2]["phase"] == "rebuild"
    assert calls[2]["deadlineUnix"] > 0
    report = m4.publish(fixture["store"], fixture["job"])
    assert report["readyFor312Phase2"] is True
    assert [item["state"] for item in report["stages"]] == ["verified"] * 4
    handoff = json.loads(
        (fixture["store"].root / fixture["job"] / "handoff-private.json").read_bytes()
    )
    assert [step["stage"] for step in handoff["stages"]] == list(m4.STAGES)
    assert len(set(item["operation_id"] for item in report["stages"])) == 4
    with pytest.raises(queue.QueueError, match="one exact original M4 stage"):
        revision.rebuild(fixture["store"], fixture["job"], fixture["config"])


def test_rebuild_rejects_wrong_materialized_build_before_native_or_fourth_receipt(
    campaign_fixture: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    fixture = campaign_fixture
    calls = _prepare_rebuild(fixture, monkeypatch)
    monkeypatch.setattr(
        v2_package,
        "verify_v2_package",
        lambda *_a, **_k: v2_package.V2PackageVerification(
            "wrong-unaccepted-build", 11, 0, 11
        ),
    )
    with pytest.raises(queue.QueueError, match="materialized revised public package"):
        revision.rebuild(fixture["store"], fixture["job"], fixture["config"])
    assert [call["kind"] for call in calls] == ["materialize"]
    assert not (fixture["root"] / "rebuild").exists()
    assert (
        m4.publish(fixture["store"], fixture["job"])["stages"][3]["state"]
        == "awaiting_operator"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "unknown_host",
        "bad_verdict",
        "swapped_target",
        "expired",
        "spent_root",
        "spent_package_root",
    ],
)
def test_rebuild_fail_stop_no_fourth_receipt(
    campaign_fixture: dict[str, Any],
    monkeypatch: pytest.MonkeyPatch,
    fault: str,
) -> None:
    fixture = campaign_fixture
    _prepare_rebuild(
        fixture,
        monkeypatch,
        outcome="UNKNOWN" if fault == "unknown_host" else "terminal_native_verified",
        verdict="rejected" if fault == "bad_verdict" else "verified",
        change_target=fault == "swapped_target",
    )
    if fault == "expired":
        with fixture["store"].connect() as db:
            db.execute(
                "UPDATE reverse_jobs SET started_at=? WHERE id=?",
                (queue.iso(queue.now_utc() - timedelta(hours=3)), fixture["job"]),
            )
    if fault == "spent_root":
        (fixture["root"] / "rebuild").mkdir()
    if fault == "spent_package_root":
        (fixture["root"] / "rebuild-package").mkdir()
    with pytest.raises(
        queue.QueueError, match=r"deadline|reserved|host|verifier|already|prior"
    ):
        revision.rebuild(fixture["store"], fixture["job"], fixture["config"])
    assert (
        m4.publish(fixture["store"], fixture["job"])["stages"][3]["state"]
        == "awaiting_operator"
    )
    assert not (
        fixture["store"].root / fixture["job"] / "receipt-rebuild.json"
    ).exists()
