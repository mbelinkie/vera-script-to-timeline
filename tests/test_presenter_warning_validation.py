"""Pure regression checks for the retained product presenter warning validator."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.presenter_warning_validation import (
    OutputConsistencyError,
    validate_temporary_presenter_report,
)

FIXTURES = Path(__file__).parent / "data" / "authoring_v2"


def _empty_case() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    return (
        {"activeDraft": {"blocks": []}},
        {"events": [], "document": {"documentId": "doc"}},
        {"diagnostics": [], "recoveryActions": []},
    )


def _golden_case(
    suite: str, scenario: str
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = FIXTURES / suite / "compiler" if suite == "issue_173" else FIXTURES / suite

    def load(role: str) -> dict[str, Any]:
        return cast(
            dict[str, Any],
            json.loads((base / f"{scenario}.{role}.golden.json").read_text()),
        )

    document = load("input")["document"]
    return document, load("manifest"), load("report")


def test_no_temporary_presenter_is_valid() -> None:
    assert validate_temporary_presenter_report(*_empty_case()) == set()


@pytest.mark.parametrize(
    ("suite", "scenario", "warning_count"),
    [
        ("issue_173", "presenter-still-fallback", 1),
        ("issue_180", "final-tail-25-1", 2),
    ],
)
def test_real_compiler_goldens_accept_exact_temporary_presenter_events(
    suite: str, scenario: str, warning_count: int
) -> None:
    document, manifest, report = _golden_case(suite, scenario)
    event_ids = validate_temporary_presenter_report(document, manifest, report)
    assert len(report["diagnostics"]) == warning_count
    assert len(event_ids) == warning_count
    assert event_ids <= {event["eventId"] for event in manifest["events"]}


def test_rejects_recovery_without_diagnostics() -> None:
    document, manifest, report = _empty_case()
    report["recoveryActions"] = [{"kind": "REPLACE_TEMPORARY_PRESENTER"}]
    with pytest.raises(
        OutputConsistencyError, match="recovery actions without diagnostics"
    ):
        validate_temporary_presenter_report(document, manifest, report)


def test_rejects_manual_completion_without_diagnostics() -> None:
    document, manifest, report = _empty_case()
    report["manualCompletionItems"] = [{"kind": "unexpected"}]
    with pytest.raises(
        OutputConsistencyError, match="manual completion items without diagnostics"
    ):
        validate_temporary_presenter_report(document, manifest, report)


def test_rejects_malformed_active_blocks() -> None:
    document, manifest, report = _empty_case()
    document["activeDraft"]["blocks"] = "not a list"
    with pytest.raises(OutputConsistencyError, match="active narration blocks"):
        validate_temporary_presenter_report(document, manifest, report)


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("missing_warning", "missing its canonical warning"),
        ("wrong_warning_id", "non-canonical presenter warning"),
        ("wrong_warning_entity", "non-canonical presenter warning"),
        ("wrong_warning_slot", "non-canonical presenter warning"),
        ("wrong_still", "no matching concrete still event"),
        ("wrong_recovery", "recovery action is not canonical"),
        ("missing_completion", "manual completion items are not canonical"),
    ],
)
def test_pure_warning_refuses_mutated_compiler_golden(
    mutation: str, reason: str
) -> None:
    document, manifest, report = deepcopy(
        _golden_case("issue_173", "presenter-still-fallback")
    )
    warning = report["diagnostics"][0]
    if mutation == "missing_warning":
        report["diagnostics"] = []
    elif mutation == "wrong_warning_id":
        warning["id"] = "noncanonical-id"
    elif mutation == "wrong_warning_entity":
        warning["entity"]["kind"] = "event"
    elif mutation == "wrong_warning_slot":
        warning["entity"]["id"] = "other-slot"
    elif mutation == "wrong_still":
        temporary_events = validate_temporary_presenter_report(
            document, manifest, report
        )
        for event in manifest["events"]:
            if event["eventId"] in temporary_events:
                event["pictureTreatment"]["kind"] = "video"
    elif mutation == "wrong_recovery":
        report["recoveryActions"][0]["slotId"] = "other-slot"
    elif mutation == "missing_completion":
        report["manualCompletionItems"] = []
    with pytest.raises(OutputConsistencyError, match=reason):
        validate_temporary_presenter_report(document, manifest, report)


def test_warning_diagnostics_must_be_in_canonical_order() -> None:
    document, manifest, report = _golden_case("issue_180", "final-tail-25-1")
    assert len(report["diagnostics"]) == 2
    report["diagnostics"].reverse()
    with pytest.raises(OutputConsistencyError, match="do not exactly cover"):
        validate_temporary_presenter_report(document, manifest, report)


def test_package_admits_only_canonical_speech_cut_warnings() -> None:
    from vera_timeline_agent.presenter_warning_validation import (
        SPEECH_CUT_WARNING,
        _stable_compiler_id,
    )

    document, manifest, report = _empty_case()
    document["activeDraft"]["blocks"] = [
        {
            "id": "row",
            "type": "narration",
            "state": "active",
            "primaryVisualSequence": {
                "id": "sequence",
                "slots": [
                    {
                        "id": "shot",
                        "kind": "content",
                        "payload": {"kind": "visual"},
                        "relation": {"kind": "sequential"},
                        "boundaryBefore": {"kind": "spoken_word"},
                    }
                ],
            },
        }
    ]
    manifest["compiler"] = {"version": "compiler/v2-speech-cuts"}
    warning = {
        "id": _stable_compiler_id(
            f"WORD_TIMING_REQUIRED:slot:shot:boundaryBefore:{SPEECH_CUT_WARNING}"
        ),
        "code": "WORD_TIMING_REQUIRED",
        "message": SPEECH_CUT_WARNING,
        "entity": {"id": "shot", "kind": "slot", "path": "boundaryBefore"},
        "severity": "warning",
        "evidence": {
            "kind": "anchor_issue",
            "anchorId": "shot",
            "reason": "word_timing_required",
        },
        "recoveryActionKinds": [],
    }
    report["diagnostics"] = [warning]
    assert validate_temporary_presenter_report(document, manifest, report) == set()
    warning["severity"] = "blocking"
    with pytest.raises(
        OutputConsistencyError, match="non-canonical speech cut warning"
    ):
        validate_temporary_presenter_report(document, manifest, report)


def _music_warning_case(
    code: str = "MUSIC_SOURCE_SHORTER",
    *,
    severity: str = "warning",
    recovery: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    from vera_timeline_agent.presenter_warning_validation import _stable_compiler_id

    message = f"Synthetic compiler message for {code}."
    document = {
        "id": "doc",
        "activeDraft": {"blocks": []},
        "rowAudioSpans": [{"id": "span"}],
    }
    diagnostic = {
        "id": _stable_compiler_id(f"{code}:block:span:rowAudioSpans/span:{message}"),
        "severity": severity,
        "code": code,
        "message": message,
        "entity": {"id": "span", "kind": "block", "path": "rowAudioSpans/span"},
        "evidence": {"kind": "details", "message": message},
        "recoveryActionKinds": recovery or ["none"],
    }
    recovery_actions = (
        [{"kind": "none", "instruction": "No repair action is required."}]
        if diagnostic["recoveryActionKinds"] == ["none"]
        else [
            {
                "kind": "manual_review",
                "entity": {"id": "doc", "kind": "document", "path": "document"},
                "instruction": "Review the compiler diagnostic.",
            }
        ]
    )
    return (
        document,
        {"events": [], "document": {"documentId": "doc"}},
        {"diagnostics": [diagnostic], "recoveryActions": recovery_actions},
    )


@pytest.mark.parametrize(
    "code",
    [
        "MUSIC_FILE_MISSING",
        "MUSIC_SOURCE_SHORTER",
        "MUSIC_SPAN_INVALID",
        "MUSIC_SETTINGS_UNSUPPORTED",
    ],
)
def test_package_admits_canonical_compiler_music_warnings(code: str) -> None:
    assert validate_temporary_presenter_report(*_music_warning_case(code)) == set()


def test_package_admits_canonical_invalid_music_timing_for_manual_review() -> None:
    case = _music_warning_case(
        "MUSIC_SPAN_INVALID", severity="blocking", recovery=["manual_review"]
    )
    assert validate_temporary_presenter_report(*case) == set()


@pytest.mark.parametrize(
    ("mutation", "reason"),
    [
        ("wrong_id", "non-canonical music warning"),
        ("wrong_entity", "non-canonical music warning"),
        ("wrong_evidence", "non-canonical music warning"),
        ("wrong_recovery", "severity or recovery action"),
        ("unbound_span", "does not name an authored span"),
        ("unsupported_code", "non-canonical presenter warning"),
    ],
)
def test_package_refuses_noncanonical_music_warning(mutation: str, reason: str) -> None:
    document, manifest, report = _music_warning_case()
    diagnostic = report["diagnostics"][0]
    if mutation == "wrong_id":
        diagnostic["id"] = "not-the-compiler-id"
    elif mutation == "wrong_entity":
        diagnostic["entity"]["path"] = "rowAudioSpans/other"
    elif mutation == "wrong_evidence":
        diagnostic["evidence"]["message"] = "different text"
    elif mutation == "wrong_recovery":
        diagnostic["recoveryActionKinds"] = ["manual_review"]
    elif mutation == "unbound_span":
        diagnostic["entity"]["id"] = "other"
    elif mutation == "unsupported_code":
        diagnostic["code"] = "MUSIC_UNTRUSTED"
    with pytest.raises(OutputConsistencyError, match=reason):
        validate_temporary_presenter_report(document, manifest, report)


def test_music_recovery_action_must_match_canonical_no_op() -> None:
    document, manifest, report = _music_warning_case()
    report["recoveryActions"] = []
    with pytest.raises(
        OutputConsistencyError,
        match="recovery actions are not canonical for music diagnostics",
    ):
        validate_temporary_presenter_report(document, manifest, report)
