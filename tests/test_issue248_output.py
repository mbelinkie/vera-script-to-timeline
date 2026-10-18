"""One bounded output retry follows only a verified failed render result."""

from __future__ import annotations

import copy
import json
from typing import Any

import pytest
from test_issue214_prediction import Case, case
from test_issue214_records import digest
from vera_timeline_agent import qualification_output_records_v2 as r
from vera_timeline_agent import qualification_output_v2 as q


def _event(
    context: dict[str, Any],
    state: str,
    prediction_hash: str,
    **changes: Any,
) -> dict[str, Any]:
    return {
        "context": context,
        "state": state,
        "commitmentRawSha256": digest(b"commitment"),
        "commitmentPayloadSha256": digest(b"commitment payload"),
        "predictionBytesSha256": prediction_hash,
        "reservationRawSha256": None,
        "resultRawSha256": None,
        **changes,
    }


def _reserved_then_terminal(
    c: Case, terminal: str
) -> tuple[q.Prediction, dict[str, Any], list[dict[str, Any]]]:
    inputs = c.inputs
    trust = c.trust
    prediction = q.create_prediction(inputs, trust=trust, ledger=[])
    context = json.loads(inputs.input_binding)["context"]
    prediction_hash = digest(prediction.pcm)
    ledger = r._append_ledger(
        [], _event(context, "committed", prediction_hash), r.EMPTY_HEAD
    )
    reservation_hash = digest(b"render reservation")
    ledger = r._append_ledger(
        ledger,
        _event(
            context,
            "reserved_by_render_intent",
            prediction_hash,
            reservationRawSha256=reservation_hash,
        ),
        r._ledger_head(ledger),
    )
    result_hash = digest(b"authenticated native failed poll result")
    result_hash = result_hash if terminal == "render_failed" else None
    ledger = r._append_ledger(
        ledger,
        _event(
            context,
            terminal,
            prediction_hash,
            reservationRawSha256=reservation_hash,
            resultRawSha256=result_hash,
        ),
        r._ledger_head(ledger),
    )
    return prediction, context, ledger


def test_verified_render_failure_allows_one_same_context_prediction_retry() -> None:
    c = case()
    prediction, context, ledger = _reserved_then_terminal(c, "render_failed")

    retry = q.create_prediction(c.inputs, trust=c.trust, ledger=ledger)

    assert retry.pcm == prediction.pcm
    changed_context = copy.deepcopy(context)
    changed_context["invocationId"] = "another invocation"
    with pytest.raises(r.OutputConsistencyError, match="retry context/prediction"):
        r._append_ledger(
            ledger,
            _event(
                changed_context,
                "committed",
                digest(prediction.pcm),
            ),
            r._ledger_head(ledger),
        )
    with pytest.raises(r.OutputConsistencyError, match="retry context/prediction"):
        r._append_ledger(
            ledger,
            _event(context, "committed", digest(b"changed prediction")),
            r._ledger_head(ledger),
        )


def test_render_failure_after_the_retry_does_not_allow_another_retry() -> None:
    c = case()
    prediction, context, ledger = _reserved_then_terminal(c, "render_failed")
    retry = q.create_prediction(c.inputs, trust=c.trust, ledger=ledger)
    prediction_hash = digest(prediction.pcm)

    retry_commit = r._append_ledger(
        ledger,
        _event(context, "committed", prediction_hash),
        r._ledger_head(ledger),
    )
    reservation_hash = digest(b"retry reservation")
    retry_reserved = r._append_ledger(
        retry_commit,
        _event(
            context,
            "reserved_by_render_intent",
            prediction_hash,
            reservationRawSha256=reservation_hash,
        ),
        r._ledger_head(retry_commit),
    )
    failed_again = r._append_ledger(
        retry_reserved,
        _event(
            context,
            "render_failed",
            prediction_hash,
            reservationRawSha256=reservation_hash,
            resultRawSha256=digest(b"second authenticated native failed poll result"),
        ),
        r._ledger_head(retry_reserved),
    )

    with pytest.raises(r.OutputConsistencyError, match="binding already"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=failed_again)
    with pytest.raises(r.OutputConsistencyError, match="binding already attempted"):
        r._append_ledger(
            failed_again,
            _event(context, "committed", prediction_hash),
            r._ledger_head(failed_again),
        )


def test_uncertain_render_result_never_allows_prediction_retry() -> None:
    c = case()
    _, _, ledger = _reserved_then_terminal(c, "uncertain")

    with pytest.raises(r.OutputConsistencyError, match="binding already"):
        q.create_prediction(c.inputs, trust=c.trust, ledger=ledger)
    with pytest.raises(r.OutputConsistencyError, match="binding already attempted"):
        r._append_ledger(
            ledger,
            _event(
                json.loads(c.inputs.input_binding)["context"],
                "committed",
                ledger[-1]["predictionBytesSha256"],
            ),
            r._ledger_head(ledger),
        )
