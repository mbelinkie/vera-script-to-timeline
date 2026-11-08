"""Mock-only reusable stage controller; never contacts native Resolve."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NoReturn
from uuid import uuid4

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_test_bench_campaign as campaign
from vera_timeline_agent import resolve_test_bench_output as output
from vera_timeline_agent import resolve_test_queue as queue
from vera_timeline_agent import workflow_v2_cli as workflow


def _fixture(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, case_id: str = "synthetic-312"
) -> tuple[dict[str, Any], list[str]]:
    name = f"VERA Delivery {uuid4()} {uuid4().hex[:12]}"
    target = {
        "projectUid": "new-disposable-project",
        "projectName": name,
        "timelineUid": "new-disposable-timeline",
        "timelineName": name,
    }
    session = tmp_path / "signed-session.json"
    session.write_bytes(b"test-only-signed-session")
    manifest = tmp_path / "verified-release.json"
    manifest.write_bytes(b"synthetic pinned installed release")
    capture = tmp_path / "signed-native-result.json"
    capture.write_bytes(b"fake native result: cannot satisfy external M4")
    installed = tmp_path / "original-installed-release"
    installed.mkdir()
    events: list[str] = []
    controller = SimpleNamespace(
        context={"caseId": case_id, "phase": "rebuild", "target": target},
        release_root=installed,
    )
    monkeypatch.setattr(workflow, "_verify_output_release", lambda path: manifest)
    monkeypatch.setattr(
        "vera_timeline_agent.resolve_test_bench_campaign.time.time",
        lambda: 2999999000.0,
    )
    monkeypatch.setattr(output, "_session", lambda *args: controller)
    monkeypatch.setattr(output, "_terminal", lambda host: True)
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda path, sha: {
            "status": "complete",
            "action": "capture_post",
            "target": target,
            "context": controller.context,
        },
    )

    def drive(root: Path, **kwargs: Any) -> dict[str, Any]:
        events.append("reviewed-host-drive-" + case_id)
        assert kwargs["hard_deadline"] == plan["deadlineUnix"]
        return {
            "state": "terminal_native_verified",
            "capture": {
                "path": str(capture),
                "sha256": hashlib.sha256(capture.read_bytes()).hexdigest(),
            },
        }

    monkeypatch.setattr(output, "drive", drive)
    plan = {
        "schema": campaign.SCHEMA,
        "root": str(tmp_path / "stage"),
        "session": {
            "path": str(session),
            "sha256": hashlib.sha256(session.read_bytes()).hexdigest(),
        },
        "installed": str(installed),
        "releaseManifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "caseId": case_id,
        "phase": "rebuild",
        "target": target,
        "deadlineUnix": 3000000000.0,
        "maxDiskBytes": 1024 * 1024,
        "consentReference": "Original actual Producer instruction reference",
        "consentInstruction": "Approved synthetic one-start native-only dry-run case",
    }
    return plan, events


@pytest.mark.parametrize("case_id", ["synthetic-312", "synthetic-313"])
def test_reuses_exact_native_host_contract_without_gui_or_second_dispatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, case_id: str
) -> None:
    plan, events = _fixture(tmp_path, monkeypatch, case_id=case_id)
    assert campaign.inspect(plan)["state"] == "not_started"
    assert campaign.start(plan)["verified"] is True
    assert campaign.inspect(plan)["state"] == "terminal_native_verified"
    with pytest.raises(queue.QueueError, match="one-use stage spent"):
        campaign.start(plan)
    assert events == ["reviewed-host-drive-" + case_id]


def test_crash_after_durable_intent_cannot_dispatch_again(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, events = _fixture(tmp_path, monkeypatch)

    def crash(root: Path, **kwargs: Any) -> NoReturn:
        events.append("one native attempt; outcome UNKNOWN")
        raise RuntimeError("crash after spawn / unknown partial native effects")

    monkeypatch.setattr(output, "drive", crash)
    monkeypatch.setattr(output, "_terminal", lambda host: False)
    with pytest.raises(RuntimeError, match="crash after spawn"):
        campaign.start(plan)
    assert campaign.inspect(plan) == {"state": "unknown_or_running", "verified": False}
    with pytest.raises(queue.QueueError, match="never replay"):
        campaign.start(plan)
    assert events == ["one native attempt; outcome UNKNOWN"]


def test_crash_after_host_terminal_but_before_completion_has_no_second_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, events = _fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(
        native,
        "verify_native_result",
        lambda path, sha: (_ for _ in ()).throw(
            RuntimeError("unexpected signed result")
        ),
    )
    with pytest.raises(RuntimeError, match="signed result"):
        campaign.start(plan)
    assert campaign.inspect(plan) == {
        "state": "terminal_host_verified",
        "verified": True,
    }
    with pytest.raises(queue.QueueError, match="never replay"):
        campaign.start(plan)
    assert events == ["reviewed-host-drive-synthetic-312"]


@pytest.mark.parametrize(
    ("field", "replacement", "message"),
    [
        ("caseId", "synthetic-313", "host session/target/case"),
        ("phase", "edited", "host session/target/case"),
        ("releaseManifestSha256", "0" * 64, "installed release manifest differs"),
        ("deadlineUnix", 42, "cumulative authority has less"),
    ],
)
def test_wrong_host_or_unsafe_budget_refused_before_dispatch(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    replacement: Any,
    message: str,
) -> None:
    plan, events = _fixture(tmp_path, monkeypatch)
    plan[field] = replacement
    with pytest.raises(queue.QueueError, match=message):
        campaign.start(plan)
    assert events == []
    assert not (Path(plan["root"]) / "stage-intent.json").exists()


def test_source_pin_changes_are_rejected_before_any_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, events = _fixture(tmp_path, monkeypatch)
    session = Path(plan["session"]["path"])
    session.write_bytes(b"changed source bytes")

    # The verified v2 session loader rejects this SHA in production. Stub a
    # strict loader here rather than treating the synthetic fixture as trusted.
    def read_session(path: Path, sha: str) -> Any:
        if hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError("session source digest differs")
        return SimpleNamespace()

    monkeypatch.setattr(output, "_session", read_session)
    with pytest.raises(ValueError, match="source digest differs"):
        campaign.start(plan)
    assert events == []


def test_inspect_refuses_changed_completed_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _ = _fixture(tmp_path, monkeypatch)
    campaign.start(plan)
    receipt = Path(plan["root"]) / "terminal.json"
    record = json.loads(receipt.read_bytes())
    record["session"]["sha256"] = "f" * 64
    receipt.write_text(json.dumps(record))
    with pytest.raises(queue.QueueError, match="terminal identity differs"):
        campaign.inspect(plan)


def test_invalid_plan_and_symlink_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    plan, _ = _fixture(tmp_path, monkeypatch)
    with pytest.raises(queue.QueueError, match="closed plan"):
        campaign.validate({**plan, "guiFallback": "osascript"})
    release = Path(plan["installed"])
    plan["root"] = str(release)
    with pytest.raises(queue.QueueError, match="independent"):
        campaign.validate(plan)
