"""Phase 16: no-native negative tests for new M4 isolation and signed receipts."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import resolve_test_queue_m4 as m4
from vera_timeline_agent.qualification_output_records_v2 import OutputConsistencyError

SLOTS = [
    ("video", 1),
    ("video", 2),
    ("video", 3),
    ("video", 4),
    ("video", 5),
    ("audio", 1),
]


def _request(phase: str = "pristine", case: str = "synthetic-312") -> dict[str, Any]:
    return {
        "action": "construct",
        "profile": native.MATRIX_PROFILE,
        "context": {"caseId": case, "phase": phase},
    }


def _view() -> dict[str, Any]:
    return {
        "tracks": [
            {"kind": kind, "index": index, "name": f"{kind}{index}"}
            for kind, index in SLOTS
        ],
        "events": [{} for _ in range(11)],
    }


def _host(monkeypatch: pytest.MonkeyPatch) -> tuple[Any, dict[str, Any]]:
    track_locks: dict[tuple[str, int], bool] = {slot: False for slot in SLOTS}
    events: list[tuple[str, Any]] = []
    selected = {"uid": "new-synthetic-project"}

    class Timeline:
        def GetUniqueId(self) -> str:
            return "new-synthetic-timeline"

        def GetIsTrackLocked(self, kind: str, index: int) -> Any:
            return track_locks[(kind, index)]

        def SetTrackLock(self, kind: str, index: int, lock: bool) -> bool:
            events.append(("sdk-lock", (kind, index, lock)))
            track_locks[(kind, index)] = lock
            return True

    timeline = Timeline()

    def project_timeline(_resolve: Any, _request: Any) -> tuple[Any, Any, Any]:
        if selected["uid"] != "new-synthetic-project":
            raise OutputConsistencyError("actual project UID changed")
        return None, SimpleNamespace(IsRenderingInProgress=lambda: False), timeline

    def durable_intent(
        _state: dict[str, Any], method: str, args: Any
    ) -> dict[str, Any]:
        events.append(("durable-intent", (method, deepcopy(args))))
        return {"method": method}

    def observed(_state: dict[str, Any], row: dict[str, Any], value: Any) -> None:
        events.append(("observed", (row["method"], value)))

    monkeypatch.setattr(native, "_project_timeline", project_timeline)
    monkeypatch.setattr(native, "_private_effect", durable_intent)
    monkeypatch.setattr(native, "_effect_observed", observed)
    return timeline, {"locks": track_locks, "events": events, "selected": selected}


@pytest.mark.parametrize("phase", ["pristine", "rebuild"])
def test_new_m4_lock_setup_is_journaled_and_v1_only(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    timeline, host = _host(monkeypatch)
    native._seal_synthetic_m4_roll_tracks(
        object(), _request(phase), {"view": _view()}, timeline, {}
    )
    assert host["locks"] == {slot: slot != ("video", 1) for slot in SLOTS}
    assert [entry[0] for entry in host["events"]] == [
        part for _ in range(5) for part in ("durable-intent", "sdk-lock", "observed")
    ]
    assert all(
        entry[1][0] == "Timeline.SetTrackLock"
        for entry in host["events"]
        if entry[0] == "durable-intent"
    )


@pytest.mark.parametrize("change", ["profile", "phase", "action", "slots", "events"])
def test_wrong_fresh_case_refuses_before_any_lock(
    monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    timeline, host = _host(monkeypatch)
    request = _request()
    view = _view()
    if change == "profile":
        request["profile"] = "wrong-profile"
    elif change == "phase":
        request["context"]["phase"] = "edited"
    elif change == "action":
        request["action"] = "observe_edited"
    elif change == "slots":
        view["tracks"][-1]["index"] = 2
    else:
        view["events"].pop()
    with pytest.raises(OutputConsistencyError):
        native._seal_synthetic_m4_roll_tracks(
            object(), request, {"view": view}, timeline, {}
        )
    assert host["events"] == []


@pytest.mark.parametrize("slot", SLOTS)
def test_existing_or_unreadable_lock_never_adopts_old_target(
    monkeypatch: pytest.MonkeyPatch, slot: tuple[str, int]
) -> None:
    timeline, host = _host(monkeypatch)
    host["locks"][slot] = True
    with pytest.raises(OutputConsistencyError, match="preexisting locked"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert host["events"] == []


def test_failed_setter_stays_unknown_after_durable_intent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline, host = _host(monkeypatch)
    monkeypatch.setattr(timeline, "SetTrackLock", lambda *_: False)
    with pytest.raises(OutputConsistencyError, match="did not read back"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert [entry[0] for entry in host["events"]] == ["durable-intent"]


def test_successful_setter_without_lock_readback_is_still_unknown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline, host = _host(monkeypatch)
    monkeypatch.setattr(timeline, "SetTrackLock", lambda *_: True)
    with pytest.raises(OutputConsistencyError, match="did not read back"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert [entry[0] for entry in host["events"]] == ["durable-intent"]


def test_partial_native_lock_failure_is_not_rolled_back_or_replayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After one SDK lock, the next failure spends its intent; no undo guess."""
    timeline, host = _host(monkeypatch)
    original_setter = timeline.SetTrackLock
    attempted = 0

    def fail_second(kind: str, index: int, locked: bool) -> bool:
        nonlocal attempted
        attempted += 1
        if attempted == 2:
            return False
        return original_setter(kind, index, locked) is True

    monkeypatch.setattr(timeline, "SetTrackLock", fail_second)
    with pytest.raises(OutputConsistencyError, match="did not read back"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert attempted == 2
    assert sum(value is True for value in host["locks"].values()) == 1
    assert [e[0] for e in host["events"]] == [
        "durable-intent",
        "sdk-lock",
        "observed",
        "durable-intent",
    ]
    # The partial SDK effect persists. Re-entering must refuse before a setter.
    with pytest.raises(OutputConsistencyError, match="preexisting locked"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert attempted == 2


@pytest.mark.parametrize("change", ["case", "phase", "profile", "action"])
def test_native_effect_allowlist_refuses_other_lock_authorities_before_intent(
    change: str,
) -> None:
    request = _request()
    if change == "case":
        request["context"]["caseId"] = "producer-project"
    elif change == "phase":
        request["context"]["phase"] = "edited"
    elif change == "profile":
        request["profile"] = "unknown-profile"
    else:
        request["action"] = "observe_edited"
    with pytest.raises(OutputConsistencyError, match="track locking is limited"):
        native._private_effect(
            {"request": request},
            "Timeline.SetTrackLock",
            {"kind": "video", "index": 2, "locked": True},
        )


@pytest.mark.parametrize(
    "arguments",
    [
        {"kind": "video", "index": 1, "locked": True},
        {"kind": "video", "index": 6, "locked": True},
        {"kind": "audio", "index": 2, "locked": True},
        {"kind": "video", "index": 2, "locked": False},
        {"kind": "video", "index": 2, "locked": 1},
        {"kind": "video", "index": True, "locked": True},
        {"kind": "video", "index": 2, "locked": True, "extra": 1},
        {"kind": ["video"], "index": 2, "locked": True},
    ],
)
def test_native_effect_allowlist_never_mints_wrong_lock_intent(
    arguments: dict[str, Any],
) -> None:
    """Effect allowlist itself, not only the constructor, limits native locks."""
    with pytest.raises(OutputConsistencyError, match="track locking"):
        native._private_effect(
            {"request": _request()}, "Timeline.SetTrackLock", arguments
        )


def test_project_switch_refuses_remaining_lock_operations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline, host = _host(monkeypatch)

    def switched(_state: Any, _row: Any, _value: Any) -> None:
        host["selected"]["uid"] = "someone-elses-project"

    monkeypatch.setattr(native, "_effect_observed", switched)
    with pytest.raises(OutputConsistencyError, match="project UID"):
        native._seal_synthetic_m4_roll_tracks(
            object(), _request(), {"view": _view()}, timeline, {}
        )
    assert len([e for e in host["events"] if e[0] == "sdk-lock"]) == 1


def test_non_m4_constructor_never_changes_any_track(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timeline, host = _host(monkeypatch)
    native._seal_synthetic_m4_roll_tracks(
        object(), _request(case="normal-product-case"), {"view": _view()}, timeline, {}
    )
    assert host["events"] == []


def _geometry() -> dict[str, Any]:
    return {
        "tracks": [
            {
                "kind": kind,
                "index": index,
                "enabled": True,
                "locked": (kind, index) != ("video", 1),
            }
            for kind, index in SLOTS
        ]
    }


@pytest.mark.parametrize(
    "mutation",
    ["v1-locked", "v2-unlocked", "duplicate", "unknown", "disabled", "nonboolean"],
)
def test_signed_pristine_and_rebuild_require_unchanged_v1_only_lock_topology(
    mutation: str,
) -> None:
    value = _geometry()
    if mutation == "v1-locked":
        value["tracks"][0]["locked"] = True
    elif mutation == "v2-unlocked":
        value["tracks"][1]["locked"] = False
    elif mutation == "duplicate":
        value["tracks"][1]["index"] = 1
    elif mutation == "unknown":
        value["tracks"][1]["kind"] = "subtitle"
    elif mutation == "disabled":
        value["tracks"][2]["enabled"] = False
    else:
        value["tracks"][1]["locked"] = 1
    with pytest.raises(Exception, match="signed M4 Roll"):
        m4._assert_roll_isolated_tracks(value)
    m4._assert_roll_isolated_tracks(_geometry())


def test_original_stage_zero_requires_lock_proof_before_verifying_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = {"path": "/not/a/real/session", "sha256": "a" * 64}
    plan = {
        "baselineSession": baseline,
        "initialTarget": {"projectUid": "fresh-initial"},
        "caseId": "synthetic-312",
    }
    seen: list[str] = []
    proof = _geometry()

    def verified(*_args: Any) -> tuple[None, dict[str, Any]]:
        seen.append("signed native capture verified")
        return None, {"nativeGeometry": proof}

    monkeypatch.setattr(m4, "_load_plan", lambda *_: plan)
    monkeypatch.setattr(m4, "_verified_output", verified)
    m4._verify_stage(None, "new-case", 0, {"session": baseline}, "original-intent")  # type: ignore[arg-type]
    assert seen == ["signed native capture verified"]

    proof["tracks"][3]["locked"] = False
    with pytest.raises(Exception, match="signed M4 Roll"):
        m4._verify_stage(None, "new-case", 0, {"session": baseline}, "original-intent")  # type: ignore[arg-type]
    assert seen == ["signed native capture verified"] * 2
