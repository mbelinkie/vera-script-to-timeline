"""Strict read-only native-owner handoff for an owned #473 render chain.

The shared `preflight_selected_disposable` is deliberately *more* restrictive:
it rejects every active output reservation on the selected project. The
qualified VERA Delivery v2 host must first retain its OWN authenticated
`reserved_by_render_intent` entry before queueing any render, so that generic
guard self-blocks the official output host. This helper does not alter that
shared guard. It permits only the original currently signed chain and exact
original job, checks every other selected-project reservation for conflict,
and makes NO Resolve calls with effects. Its result is never native evidence.

Only `resolve_test_bench_carrier.start` may call this helper after
`verify_native_request` has reauthenticated the original immutable host
request, whose own per-stage native bootstrap must independently reverify
authority, reservation, target, sources, effect journal and job lineage.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from typing import Any

from . import resolve_native_owner as owner
from . import resolve_test_queue as queue

RENDER_ACTIONS = frozenset(
    {"queue_render", "start_render", "poll_render", "capture_post"}
)
TERMINAL_RENDER_STATES = frozenset({"Complete", "Failed", "Cancelled"})
ACTIVE_RENDER_STATES = frozenset({"Ready", "Rendering"})


def _require(condition: bool, description: str) -> None:
    if not condition:
        raise queue.QueueError("Test Bench render preflight: " + description)


def _expected_job(request: Mapping[str, Any]) -> str | None:
    """Authenticate exact prior native result (never a caller-supplied job)."""
    from . import qualification_output_native_v2 as native

    action = request["action"]
    predecessor = {
        "start_render": "queue_render",
        "poll_render": "start_render",
        "capture_post": "poll_render",
    }.get(action)
    if predecessor is None:
        return None
    result, _, _ = native._previous_result(dict(request), predecessor)
    job = result.get("jobId")
    _require(isinstance(job, str) and bool(job), "signed prior job is missing")
    if action in {"start_render", "poll_render"}:
        _require(
            request.get("payload", {}).get("jobId") == job,
            "requested job ID differs from authenticated native predecessor",
        )
    return job


def preflight_owned_render(request: Mapping[str, Any]) -> None:
    """Observe signed own render intent and target while owning the host lock.

    Refuses before any native effect. It must never create, change, delete or
    adopt a Resolve project/job, nor clear a foreign or UNKNOWN reservation.
    """
    from . import qualification_output_native_v2 as native
    from .resolve_test_queue_m4 import _target as checked_target

    _require(isinstance(request, Mapping), "signed host request required")
    action = request.get("action")
    _require(action in RENDER_ACTIONS, "only approved render actions supported")
    target = checked_target(request.get("target"), "signed render target")
    context = request.get("context")
    _require(
        isinstance(context, dict)
        and context.get("target") == target
        and context.get("phase") in {"pristine", "edited", "rebuild"}
        and isinstance(context.get("caseId"), str)
        and request.get("renderIntent") is not None
        and request.get("reservation") is not None,
        "closed current host target, reservation and render intent required",
    )
    assert isinstance(context, dict)
    own_key = native._chain_key(context)
    expected_job = _expected_job(request)

    # The same exclusive lock and global parent/issue328 ownership checks as
    # every existing native integration. Unlike the generic non-render guard,
    # this scope explicitly recognizes the exact signed self reservation.
    with owner.native_owner(output_lane=True):
        active = owner._active_output_host_chains(None)
        _require(
            active.get(own_key) == "reserved_by_render_intent",
            "exact own signed render reservation is not active and healthy",
        )
        for key in active:
            if key == own_key:
                continue
            chain = json.loads(
                owner._read(owner.OUTPUT_ATTEMPTS_ROOT / key / "chain.json")
            )
            _require(
                chain.get("projectUid") != target["projectUid"],
                "foreign/uncertain host operation owns selected project",
            )

        resolve = owner._local_resolve_connection()
        _require(resolve is not None, "local Resolve SDK is unavailable")
        manager = resolve.GetProjectManager()
        _require(manager is not None, "native project manager unavailable")
        project = manager.GetCurrentProject()
        _require(project is not None, "no selected native project")
        timeline = project.GetCurrentTimeline()
        _require(timeline is not None, "no selected native timeline")
        _require(
            project.GetUniqueId() == target["projectUid"]
            and timeline.GetUniqueId() == target["timelineUid"]
            and project.GetName() == target["projectName"]
            and timeline.GetName() == target["timelineName"],
            "selected project/timeline name or UID differs",
        )
        available = manager.GetProjectListInCurrentFolder()
        _require(
            isinstance(available, (tuple, list)) and target["projectName"] in available,
            "selected project missing from exact native folder",
        )
        rendering = project.IsRenderingInProgress()
        _require(type(rendering) is bool, "render activity is not readable")
        _require(
            action == "poll_render" or rendering is False,
            "foreign/active render cannot be controlled by this stage",
        )

        jobs = project.GetRenderJobList()
        _require(
            isinstance(jobs, (list, tuple)) and len(jobs) <= 64,
            "bounded native job inventory unavailable",
        )
        statuses: dict[str, str] = {}
        for row in jobs:
            _require(isinstance(row, dict), "unreadable native render job")
            job_id = row.get("JobId")
            _require(
                isinstance(job_id, str) and bool(job_id) and job_id not in statuses,
                "missing/duplicate native render job ID",
            )
            status = project.GetRenderJobStatus(job_id)
            _require(
                isinstance(status, dict)
                and isinstance(status.get("JobStatus"), str)
                and status["JobStatus"]
                in TERMINAL_RENDER_STATES | ACTIVE_RENDER_STATES,
                "unknown native render job status",
            )
            statuses[job_id] = status["JobStatus"]

        for job_id, status in statuses.items():
            _require(
                status in TERMINAL_RENDER_STATES or job_id == expected_job,
                "foreign native render job is active or queued",
            )
        if action == "queue_render":
            _require(
                expected_job is None and not rendering,
                "render queue requires an idle, unclaimed new job",
            )
        elif expected_job is None:
            raise queue.QueueError("authenticated previous native render job required")
        elif action == "start_render":
            _require(
                statuses.get(expected_job) == "Ready" and not rendering,
                "signed queued job is not the unique ready native job",
            )
        elif action == "poll_render":
            _require(
                statuses.get(expected_job)
                in TERMINAL_RENDER_STATES | ACTIVE_RENDER_STATES,
                "signed started render job is unavailable",
            )
        else:
            _require(
                statuses.get(expected_job) == "Complete" and not rendering,
                "post-render capture requires the original completed job",
            )
        selected = manager.GetCurrentProject()
        _require(
            selected is not None
            and selected.GetUniqueId() == target["projectUid"]
            and selected.GetCurrentTimeline() is not None
            and selected.GetCurrentTimeline().GetUniqueId() == target["timelineUid"]
            and (action == "poll_render" or selected.IsRenderingInProgress() is False),
            "native target or render activity changed during owner preflight",
        )
