"""Agent-mediated bounded-run issuance stays within the validated session."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from test_issue209_native import _approval
from test_issue209_seam import _runtime_fixture
from vera_timeline_agent import (
    qualification_output_controller_v2 as controller_module,
)
from vera_timeline_agent import (
    qualification_output_native_v2 as native,
)
from vera_timeline_agent import (
    workflow_v2_cli,
)
from vera_timeline_agent.qualification_output_records_v2 import (
    OutputConsistencyError,
    _canonical,
)

_LOAD_OUTPUT_SESSION = controller_module.load_output_session


CONSENT_REFERENCE = "codex-user-message:issue-276-smoke"
CONSENT_INSTRUCTION = (
    "I authorize this disposable synthetic output run for the displayed target, "
    "including one permitted retry after an authenticated terminal render failure."
)


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[Any, Path, str, Path]:
    native_root = tmp_path.resolve() / "native-state"
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", native_root)
    approval, context = _approval(tmp_path, profile=native.SYNTHETIC_PROFILE)
    package_root = Path(approval["packageRoot"])
    admission_path = package_root.parent / "qualification-output-package-admission.json"
    release_root = tmp_path / "release"
    release_manifest = release_root / "vera-delivery-v2" / "release.json"
    release_manifest.parent.mkdir(parents=True)
    release_manifest.write_bytes(b"reviewed release manifest")
    session_path = tmp_path / "session.json"
    session_path.write_bytes(b"pinned current session")
    session_sha256 = _hash(session_path.read_bytes())

    timeline_manifest = json.loads(
        (package_root / "Compiler/timeline-manifest-v2.json").read_text()
    )
    admission = SimpleNamespace(
        profile=native.SYNTHETIC_PROFILE,
        package_root=package_root,
        admission_path=admission_path,
        manifest=timeline_manifest,
        assert_current=lambda: None,
    )
    target = context["target"]
    chain = {
        "projectUid": target["projectUid"],
        "timelineUid": target["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    controller: Any = object.__new__(controller_module.QualificationOutputController)
    controller.context = context
    controller.admission = admission
    controller.release_root = release_root
    controller.journal = SimpleNamespace(chain=chain)
    controller.trust = SimpleNamespace(checked_now=lambda: datetime.now(UTC))
    controller._environment_current = lambda: None
    controller._latest_attempt = lambda: {
        "state": "render_failed",
        "resultRawSha256": "e" * 64,
    }

    monkeypatch.setattr(
        workflow_v2_cli,
        "_verify_output_release",
        lambda _root: release_manifest,
    )
    monkeypatch.setattr(
        controller_module, "load_output_session", lambda _path, _sha256: controller
    )
    return controller, session_path, session_sha256, release_manifest


def _plan(controller: Any, path: Path, *, retry: bool = False) -> Path:
    if retry:
        return controller.prepare_render_retry_plan(path)
    return controller.prepare_operator_plan(path)


def _write_plan(path: Path, mutate: Any) -> None:
    wrapper = json.loads(path.read_text())
    mutate(wrapper["proposal"])
    path.chmod(0o600)
    path.write_bytes(_canonical(wrapper))
    path.chmod(0o400)


def _issue(
    plan_path: Path,
    output_path: Path,
    session_path: Path,
    session_sha256: str,
    *,
    reference: str = CONSENT_REFERENCE,
    instruction: str = CONSENT_INSTRUCTION,
) -> Path:
    return controller_module.issue_operator_approval(
        plan_path,
        output_path,
        session_path=session_path,
        session_sha256=session_sha256,
        consent_reference=reference,
        consent_instruction=instruction,
    )


def _approval_dir(tmp_path: Path) -> Path:
    path = tmp_path / "private-approvals"
    path.mkdir(mode=0o700)
    path.chmod(0o700)
    return path


def _assert_issued(
    approval_path: Path,
    controller: Any,
    release_manifest: Path,
    plan_path: Path,
    session_path: Path,
    session_sha256: str,
    *,
    expected_plan: list[str],
    consent_reference: str = CONSENT_REFERENCE,
) -> dict[str, Any]:
    raw = approval_path.read_bytes()
    approval = native.verify_operator_approval(
        raw,
        context=controller.context,
        profile=controller.admission.profile,
        admission_sha256=_hash(controller.admission.admission_path.read_bytes()),
        release_manifest_sha256=_hash(release_manifest.read_bytes()),
    )
    assert approval["actionPlan"] == expected_plan
    issued = datetime.fromisoformat(approval["issuedAt"].replace("Z", "+00:00"))
    expires = datetime.fromisoformat(approval["expiresAt"].replace("Z", "+00:00"))
    now = datetime.now(UTC)
    assert issued <= now < expires
    assert (
        timedelta(0)
        < expires - issued
        <= timedelta(seconds=native.MAX_LIFETIME_SECONDS)
    )

    sidecar_path = approval_path.with_name(approval_path.name + ".issuance.json")
    sidecar = json.loads(sidecar_path.read_text())
    assert sidecar == {
        "schemaVersion": "qualification-output-agent-issuance/v1",
        "issuanceMode": "agent_mediated_not_transcript_authenticated",
        "consentReference": consent_reference,
        "consentInstruction": CONSENT_INSTRUCTION,
        "sessionPath": str(session_path),
        "sessionSha256": session_sha256,
        "planSha256": _hash(plan_path.read_bytes()),
        "approvalSha256": _hash(raw),
        "scope": approval,
    }
    assert sidecar["issuanceMode"] == "agent_mediated_not_transcript_authenticated"
    assert sidecar["approvalSha256"] == _hash(raw)
    return approval


@pytest.mark.parametrize("expired_proposal", [False, True])
def test_agent_issuance_revalidates_and_records_the_exact_bounded_plan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    expired_proposal: bool,
) -> None:
    controller, session_path, session_sha256, release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    if expired_proposal:
        old = datetime.now(UTC) - timedelta(hours=2)
        _write_plan(
            plan_path,
            lambda proposal: proposal.update(
                issuedAt=(old - timedelta(minutes=30)).isoformat(),
                expiresAt=old.isoformat(),
            ),
        )

    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "approval.json"
    published: list[Path] = []
    publish = controller_module._publish

    def record_publish(path: Path, raw: bytes) -> None:
        published.append(path)
        publish(path, raw)

    monkeypatch.setattr(controller_module, "_publish", record_publish)
    _issue(
        plan_path,
        approval_path,
        session_path,
        session_sha256,
    )

    sidecar_path = approval_path.with_name(approval_path.name + ".issuance.json")
    assert published == [sidecar_path, approval_path]
    _assert_issued(
        approval_path,
        controller,
        release_manifest,
        plan_path,
        session_path,
        session_sha256,
        expected_plan=list(native.APPROVAL_ACTION_PLAN),
    )


def test_one_explicit_instruction_covers_noninteractive_replan_and_permitted_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, session_path, session_sha256, release_manifest = _case(
        tmp_path, monkeypatch
    )
    output_dir = _approval_dir(tmp_path)

    initial_plan = _plan(controller, tmp_path / "initial-plan.json")
    initial_path = output_dir / "initial-approval.json"
    _issue(initial_plan, initial_path, session_path, session_sha256)
    _assert_issued(
        initial_path,
        controller,
        release_manifest,
        initial_plan,
        session_path,
        session_sha256,
        expected_plan=list(native.APPROVAL_ACTION_PLAN),
    )

    monkeypatch.setattr(
        native,
        "next_native_operation",
        lambda _context, *, retry=False: (6, "head") if retry else (0, "head"),
    )
    monkeypatch.setattr(
        native,
        "verified_render_failure",
        lambda _context: (tmp_path / "failed-result.json", "e" * 64, {}),
    )
    retry_plan = _plan(controller, tmp_path / "retry-plan.json", retry=True)
    retry_path = output_dir / "retry-approval.json"
    _issue(retry_plan, retry_path, session_path, session_sha256)
    retry = _assert_issued(
        retry_path,
        controller,
        release_manifest,
        retry_plan,
        session_path,
        session_sha256,
        expected_plan=list(native.RETRY_ACTION_PLAN),
    )
    assert retry["outputPath"].endswith("-retry-1.mov")


def test_progressed_native_run_can_be_replanned_without_new_terminal_entry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, legacy_approval, installed_root, _context, resolve, manifest = (
        _runtime_fixture(tmp_path, monkeypatch)
    )
    controller.admission.assert_current = lambda: None
    controller.admission.manifest = json.loads(
        (
            controller.admission.package_root / "Compiler/timeline-manifest-v2.json"
        ).read_text()
    )

    request_path = controller.prepare_native_request(
        "construct", {}, approval_path=legacy_approval
    )
    request_raw = request_path.read_bytes()
    native.verify_native_request(
        request_raw, expected_request_sha256=_hash(request_raw), current=True
    )
    installed_root.mkdir(parents=True)
    installed_request = installed_root / "request.json"
    installed_request.write_bytes(request_raw)
    installed_request.chmod(0o400)
    result_path = native.run_qualification_output_request(
        resolve, installed_request, expected_request_sha256=_hash(request_raw)
    )
    result_raw = result_path.read_bytes()
    result = native.verify_native_result(result_path, _hash(result_raw))
    assert result["status"] == "complete"
    controller.ingest_native_result(result_path, _hash(result_raw))

    plan_path = controller.prepare_operator_replan(tmp_path / "replan.json")
    session_path = tmp_path / "session.json"
    session_path.write_bytes(b"current session")
    session_sha256 = _hash(session_path.read_bytes())
    monkeypatch.setattr(
        controller_module, "load_output_session", lambda _path, _sha: controller
    )
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "agent-approval.json"
    _issue(plan_path, approval_path, session_path, session_sha256)
    _assert_issued(
        approval_path,
        controller,
        manifest,
        plan_path,
        session_path,
        session_sha256,
        expected_plan=list(native.APPROVAL_ACTION_PLAN),
    )

    next_path = controller.prepare_next_native_request(approval_path)
    next_raw = next_path.read_bytes()
    next_request = native.verify_native_request(
        next_raw, expected_request_sha256=_hash(next_raw), current=True
    )
    assert next_request["action"] == "save_reopen"
    assert next_request["sequence"] == 1


def test_output_authorize_cli_accepts_agent_consent_and_prints_issued_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    controller, session_path, session_sha256, release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "cli-approval.json"

    assert (
        workflow_v2_cli.main(
            [
                "output-authorize",
                "--plan",
                str(plan_path),
                "--output",
                str(approval_path),
                "--session",
                str(session_path),
                "--session-sha256",
                session_sha256,
                "--agent-consent-reference",
                CONSENT_REFERENCE,
                "--agent-consent-instruction",
                CONSENT_INSTRUCTION,
            ]
        )
        == 0
    )
    printed = capsys.readouterr().out
    assert str(approval_path.absolute()) in printed
    assert f"sha256:{_hash(approval_path.read_bytes())}" in printed
    _assert_issued(
        approval_path,
        controller,
        release_manifest,
        plan_path,
        session_path,
        session_sha256,
        expected_plan=list(native.APPROVAL_ACTION_PLAN),
    )


@pytest.mark.parametrize(
    "mutate",
    [
        lambda proposal: proposal["context"]["target"].update(projectUid="other"),
        lambda proposal: proposal["context"].update(nativeSourceGraphSha256="f" * 64),
        lambda proposal: proposal.update(profile="unsupported-profile"),
        lambda proposal: proposal.update(packageRoot="/tmp/other-package"),
        lambda proposal: proposal.update(packageSha256="f" * 64),
        lambda proposal: proposal.update(admissionSha256="f" * 64),
        lambda proposal: proposal.update(releaseManifestSha256="f" * 64),
        lambda proposal: proposal.update(outputPath="/tmp/other-output.mov"),
    ],
    ids=[
        "wrong-project",
        "changed-inputs",
        "wrong-profile",
        "wrong-package-root",
        "changed-package",
        "changed-admission",
        "changed-release",
        "wrong-output",
    ],
)
def test_agent_issuance_refuses_plans_outside_the_loaded_session_scope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutate: Any
) -> None:
    controller, session_path, session_sha256, _release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    _write_plan(plan_path, mutate)
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "approval.json"

    with pytest.raises(OutputConsistencyError):
        _issue(plan_path, approval_path, session_path, session_sha256)

    assert not approval_path.exists()
    assert not approval_path.with_name(approval_path.name + ".issuance.json").exists()


@pytest.mark.parametrize(
    "missing",
    ["session_path", "session_sha256", "consent_reference", "consent_instruction"],
)
def test_agent_issuance_requires_every_consent_field(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, missing: str
) -> None:
    controller, session_path, session_sha256, _release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "approval.json"
    fields: dict[str, Any] = {
        "session_path": session_path,
        "session_sha256": session_sha256,
        "consent_reference": CONSENT_REFERENCE,
        "consent_instruction": CONSENT_INSTRUCTION,
    }
    fields[missing] = None

    with pytest.raises(OutputConsistencyError, match="agent issuance"):
        controller_module.issue_operator_approval(plan_path, approval_path, **fields)

    assert not approval_path.exists()
    assert not approval_path.with_name(approval_path.name + ".issuance.json").exists()


@pytest.mark.parametrize("field", ["consent_reference", "consent_instruction"])
def test_agent_issuance_rejects_empty_attribution_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    controller, session_path, session_sha256, _release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "approval.json"
    fields = {
        "session_path": session_path,
        "session_sha256": session_sha256,
        "consent_reference": CONSENT_REFERENCE,
        "consent_instruction": CONSENT_INSTRUCTION,
    }
    fields[field] = "  "

    with pytest.raises(OutputConsistencyError, match="agent issuance"):
        controller_module.issue_operator_approval(plan_path, approval_path, **fields)

    assert not approval_path.exists()
    assert not approval_path.with_name(approval_path.name + ".issuance.json").exists()


def test_agent_issuance_refuses_a_session_hash_mismatch_before_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, session_path, _session_sha256, _release_manifest = _case(
        tmp_path, monkeypatch
    )
    plan_path = _plan(controller, tmp_path / "operator-plan.json")
    output_dir = _approval_dir(tmp_path)
    approval_path = output_dir / "approval.json"
    monkeypatch.setattr(
        controller_module,
        "load_output_session",
        _LOAD_OUTPUT_SESSION,
    )

    with pytest.raises(OutputConsistencyError, match="session raw pin differs"):
        _issue(plan_path, approval_path, session_path, "0" * 64)

    assert not approval_path.exists()
    assert not approval_path.with_name(approval_path.name + ".issuance.json").exists()
