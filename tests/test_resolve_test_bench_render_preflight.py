"""Read-only injected SDK tests; NEVER open Resolve or replay M4 effects."""

from __future__ import annotations

import json
from contextlib import nullcontext
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_native_owner as owner
from vera_timeline_agent import resolve_test_bench_render_preflight as preflight
from vera_timeline_agent import resolve_test_queue as queue

NAME = "VERA Delivery 12345678-1234-1234-1234-123456789abc abcdef123456"
TARGET = {
    "projectUid": "project-new-473",
    "timelineUid": "timeline-new-473",
    "projectName": NAME,
    "timelineName": NAME,
}


def _env(
    monkeypatch: pytest.MonkeyPatch,
    *,
    action: str,
    state: str = "reserved_by_render_intent",
    job_status: str | None = None,
    other_project: str = "different-project",
    render_active: bool = False,
    selected: str = "project-new-473",
) -> dict[str, Any]:
    class Timeline:
        def GetUniqueId(self) -> str:
            return TARGET["timelineUid"]

        def GetName(self) -> str:
            return NAME

    class Project:
        def GetUniqueId(self) -> str:
            return selected

        def GetName(self) -> str:
            return NAME

        def GetCurrentTimeline(self) -> Timeline:
            return Timeline()

        def IsRenderingInProgress(self) -> bool:
            return render_active

        def GetRenderJobList(self) -> list[dict[str, str]]:
            return [{"JobId": "signed-job"}] if job_status is not None else []

        def GetRenderJobStatus(self, job_id: str) -> dict[str, str]:
            assert job_id == "signed-job"
            assert job_status is not None
            return {"JobStatus": job_status}

    project = Project()
    manager = SimpleNamespace(
        GetCurrentProject=lambda: project,
        GetProjectListInCurrentFolder=lambda: [NAME],
    )
    monkeypatch.setattr(owner, "native_owner", lambda **kwargs: nullcontext(5))
    monkeypatch.setattr(
        owner,
        "_local_resolve_connection",
        lambda: SimpleNamespace(GetProjectManager=lambda: manager),
    )
    monkeypatch.setattr(native, "_chain_key", lambda _: "own-key")
    monkeypatch.setattr(
        owner,
        "_active_output_host_chains",
        lambda _: {"own-key": state, "foreign-key": "uncertain"},
    )
    monkeypatch.setattr(
        owner,
        "_read",
        lambda path: json.dumps({"projectUid": other_project}).encode(),
    )
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda request, predecessor: ({"jobId": "signed-job"}, "sha", Path("/receipt")),
    )
    return {
        "action": action,
        "target": dict(TARGET),
        "context": {
            "target": dict(TARGET),
            "phase": "pristine",
            "caseId": "synthetic-312",
        },
        "renderIntent": {"path": "/original", "sha256": "a" * 64},
        "reservation": {"path": "/original", "sha256": "b" * 64},
        "payload": {"jobId": "signed-job"},
    }


@pytest.mark.parametrize(
    ("action", "job", "render_active"),
    [
        ("queue_render", None, False),
        ("start_render", "Ready", False),
        ("poll_render", "Rendering", True),
        ("poll_render", "Complete", False),
        ("capture_post", "Complete", False),
    ],
)
def test_exact_own_reservation_only_is_read_only_eligible(
    monkeypatch: pytest.MonkeyPatch, action: str, job: str | None, render_active: bool
) -> None:
    request = _env(
        monkeypatch, action=action, job_status=job, render_active=render_active
    )
    preflight.preflight_owned_render(request)


@pytest.mark.parametrize(
    ("difference", "kwargs"),
    [
        ("uncertain-own-chain", {"state": "uncertain"}),
        ("foreign-active-chain", {"other_project": TARGET["projectUid"]}),
        ("different-selected-target", {"selected": "foreign-project"}),
        ("foreign-active-job", {"job_status": "Rendering"}),
        ("unobserved-rendering", {"render_active": True}),
    ],
)
def test_render_preflight_never_adopts_foreign_or_unknown(
    monkeypatch: pytest.MonkeyPatch, difference: str, kwargs: dict[str, Any]
) -> None:
    request = _env(monkeypatch, action="queue_render", **kwargs)
    with pytest.raises((queue.QueueError, ValueError)):
        preflight.preflight_owned_render(request)


def test_cannot_substitute_unsigned_job_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _env(monkeypatch, action="start_render", job_status="Ready")
    request["payload"]["jobId"] = "foreign-job"
    with pytest.raises(queue.QueueError, match="requested job ID differs"):
        preflight.preflight_owned_render(request)


def test_no_render_intent_or_reservation_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _env(monkeypatch, action="queue_render")
    request["renderIntent"] = None
    with pytest.raises(queue.QueueError, match="reservation and render intent"):
        preflight.preflight_owned_render(request)
