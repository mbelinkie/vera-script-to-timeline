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
