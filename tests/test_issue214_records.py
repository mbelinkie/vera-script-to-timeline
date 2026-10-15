"""Owned closed-shape vectors and synthetic authentication, never native evidence."""

from __future__ import annotations

import ast
import copy
import hashlib
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_records_v2 as r
from vera_timeline_agent.narration.models import canonical_json_bytes

TRACK_FIELDS = "trackId kind index name enabled locked"
ITEM_FIELDS = (
    "itemUid eventId sourceId mediaUid kind trackId recordStart recordDuration "
    "sourceStart sourceDuration linkedItemUids online enabled speed sourceMappingSha256"
)
SOURCE_FIELDS = (
    "sourceId nativeSourceSha256 pcmMode provenanceReceiptSha256 provenancePinsSha256 "
    "deliveryDerivationSha256 pcmFileSha256 decodedSamplesSha256 originalBitDepth "
    "channels durationSamples sampleRate pcmMappingSha256 "
    "nativeFrameOrigin pcmSampleOrigin"
)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def canonical(value: Any) -> bytes:
    return canonical_json_bytes(value)


def context(**changes: Any) -> dict[str, Any]:
    value: dict[str, Any] = {
        "lane": "bounded_output_residual_consistency",
        "invocationId": "invocation-1",
        "caseId": "C",
        "phase": "pristine",
        "target": {
            "projectName": "Synthetic project",
            "projectUid": "project-1",
            "timelineName": "Synthetic timeline",
            "timelineUid": "timeline-1",
        },
        **{key: digest(key.encode()) for key in r.CONTEXT_HASH_FIELDS},
        "binding": {"kind": "baseline", "bindingSha256": "0" * 64},
    }
    value.update(changes)
    projection = copy.deepcopy(value)
    projection.pop("invocationId")
    # Exact raw authority-file references, never content/source/runtime identity.
    projection.pop("preflightSha256")
    projection.pop("preparationSha256")
    projection["binding"].pop("bindingSha256")
    value["binding"]["bindingSha256"] = digest(canonical(projection))
    return value


class SealedTrust:
    """Test oracle: only independently registered exact kind/payload pairs pass."""

    def __init__(self) -> None:
        self.seals: dict[bytes, tuple[str, bytes]] = {}
        self.now = datetime(2026, 10, 15, 1, tzinfo=UTC)
        self.calls: list[str] = []

    def seal(self, kind: str, payload: dict[str, Any]) -> bytes:
        raw = b"synthetic-seal:" + canonical([kind, payload])
        self.seals[raw] = (kind, canonical(payload))
        return raw

    def authenticate(self, kind: str, receipt: bytes, expected: dict[str, Any]) -> None:
        self.calls.append(kind)
        if self.seals.get(receipt) != (kind, canonical(expected)):
            raise r.OutputConsistencyError("independent authentication refused")

    def checked_now(self) -> datetime:
        return self.now


def test_tuple_fields_are_explicit_before_parser() -> None:
    assert frozenset(TRACK_FIELDS.split()) == r.TRACK_FIELDS
    assert frozenset(ITEM_FIELDS.split()) == r.ITEM_FIELDS
    assert frozenset(SOURCE_FIELDS.split()) == r.SOURCE_FIELDS


@pytest.mark.parametrize(
    "value",
    [
        {"z": [1, 0.0, -0.0, 1.25], "ä": "é", "😀": "x", "\ue000": 2**53 - 1},
        {"a": {"b": True}, "c": None},
    ],
)
def test_python_canonical_bytes_match_accepted_oracle(value: Any) -> None:
    assert r._canonical(value) == canonical(value)
    assert r._parse(canonical(value)) == value


@pytest.mark.parametrize(
    "raw",
    [
        b'{"x":1,"x":2}',
        b'{"x":NaN}',
        b'{"x":Infinity}',
        b'{"x":9007199254740992}',
        b'{"x":"\\ud800"}',
        b"[]",
        b"\xef\xbb\xbf{}",
        "{}".encode("utf-16"),
        "{}".encode("utf-32"),
        b"{}" + b" " * (8 * 1024 * 1024),
    ],
    ids=[
        "duplicate",
        "nan",
        "infinity",
        "unsafe-int",
        "surrogate",
        "array",
        "bom",
        "utf16",
        "utf32",
        "oversize",
    ],
)
def test_unsafe_json_refuses(raw: bytes) -> None:
    with pytest.raises(r.OutputConsistencyError):
        r._parse(raw)


def test_binding_derived_from_context_excludes_invocation_and_authority_refs() -> None:
    first, second = context(), context(invocationId="invocation-2")
    assert r._context(first) == first
    assert r._ledger_key(first) == r._ledger_key(second)
    for key in r.CONTEXT_HASH_FIELDS:
        renewed = context(**{key: "a" * 64})
        if key in {"preflightSha256", "preparationSha256"}:
            assert r._ledger_key(first) == r._ledger_key(renewed)
        else:
            assert r._ledger_key(first) != r._ledger_key(renewed)
    wrong = copy.deepcopy(first)
    wrong["binding"]["bindingSha256"] = "b" * 64
    with pytest.raises(r.OutputConsistencyError):
        r._context(wrong)


@pytest.mark.parametrize(
    "key,value",
    [
        ("lane", "synthetic_local"),
        ("phase", "unknown"),
        ("invocationId", "bad\nidentity"),
        ("profileSha256", "A" * 64),
    ],
)
def test_context_refuses_bad_identity(key: str, value: Any) -> None:
    bad = context(**{key: value})
    with pytest.raises(r.OutputConsistencyError):
        r._context(bad)


def test_host_production_import_closure() -> None:
    for name in ("qualification_output_records_v2", "qualification_output_v2"):
        path = Path("python/vera_timeline_agent") / f"{name}.py"
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.Import):
                modules = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom):
                modules = [node.module or ""]
            else:
                continue
            for module in modules:
                assert module.split(".")[0] in sys.stdlib_module_names or (
                    name == "qualification_output_v2"
                    and module == "vera_timeline_agent.qualification_output_records_v2"
                ), module


def ledger_event(ctx: dict[str, Any], state: str, **changes: Any) -> dict[str, Any]:
    return {
        "context": ctx,
        "state": state,
        "commitmentRawSha256": "1" * 64,
        "commitmentPayloadSha256": "2" * 64,
        "predictionBytesSha256": "3" * 64,
        "reservationRawSha256": None,
        "resultRawSha256": None,
        **changes,
    }


@pytest.mark.parametrize(
    "state",
    [
        "reserved_by_render_intent",
        "uncertain",
        "compared_consistent",
        "compared_refused",
    ],
)
def test_no_invocation_restart_and_chain_spans_bindings(state: str) -> None:
    first = context()
    ledger = r._append_ledger([], ledger_event(first, "committed"), r.EMPTY_HEAD)
    reservation = ledger_event(
        first, "reserved_by_render_intent", reservationRawSha256="4" * 64
    )
    ledger = r._append_ledger(ledger, reservation, r._ledger_head(ledger))
    if state != "reserved_by_render_intent":
        event = ledger_event(first, state, reservationRawSha256="4" * 64)
        if state.startswith("compared_"):
            event["resultRawSha256"] = "5" * 64
        ledger = r._append_ledger(ledger, event, r._ledger_head(ledger))
    with pytest.raises(r.OutputConsistencyError):
        r._append_ledger(
            ledger,
            ledger_event(context(invocationId="another"), "committed"),
            r._ledger_head(ledger),
        )
    changed = context(packageSha256="6" * 64)
    head = r._ledger_head(ledger)
    appended = r._append_ledger(ledger, ledger_event(changed, "committed"), head)
    assert appended[-1]["priorHeadSha256"] == head
    assert len(appended) == len(ledger) + 1
    assert appended[:-1] == ledger


def test_expired_unused_only_allows_identical_prediction_and_cas() -> None:
    c = context()
    ledger = r._append_ledger([], ledger_event(c, "committed"), r.EMPTY_HEAD)
    head = r._ledger_head(ledger)
    ledger = r._append_ledger(ledger, ledger_event(c, "expired_unused"), head)
    with pytest.raises(r.OutputConsistencyError):
        r._append_ledger(ledger, ledger_event(c, "committed"), head)
    with pytest.raises(r.OutputConsistencyError):
        r._append_ledger(
            ledger,
            ledger_event(c, "committed", predictionBytesSha256="7" * 64),
            r._ledger_head(ledger),
        )
    again = r._append_ledger(
        ledger, ledger_event(c, "committed"), r._ledger_head(ledger)
    )
    tampered = copy.deepcopy(again)
    tampered[0]["predictionBytesSha256"] = "8" * 64
    with pytest.raises(r.OutputConsistencyError):
        r._ledger_head(tampered)


def test_target_rename_discloses_prior_binding_in_same_uid_chain() -> None:
    first = context()
    ledger = r._append_ledger([], ledger_event(first, "committed"), r.EMPTY_HEAD)
    ledger = r._append_ledger(
        ledger,
        ledger_event(first, "reserved_by_render_intent", reservationRawSha256="4" * 64),
        r._ledger_head(ledger),
    )
    ledger = r._append_ledger(
        ledger,
        ledger_event(
            first,
            "compared_refused",
            reservationRawSha256="4" * 64,
            resultRawSha256="5" * 64,
        ),
        r._ledger_head(ledger),
    )
    renamed = context(
        target={
            **first["target"],
            "projectName": "Renamed project",
            "timelineName": "Renamed timeline",
        }
    )
    assert renamed["binding"] != first["binding"]
    assert r._ledger_key(renamed)[1:] == r._ledger_key(first)[1:]
    result = r._append_ledger(
        ledger, ledger_event(renamed, "committed"), r._ledger_head(ledger)
    )
    assert result[:-1] == ledger
    assert result[-1]["priorHeadSha256"] == ledger[-1]["entrySha256"]


@pytest.mark.parametrize("phase", [[], {}, True])
def test_malformed_enums_are_refusals_not_crashes(phase: Any) -> None:
    with pytest.raises(r.OutputConsistencyError):
        r._context(context(phase=phase))
