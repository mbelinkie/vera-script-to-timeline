"""Closed sibling records for bounded output consistency, never native authority.

All digests here are raw lowercase SHA256. Canonical identities use Python JSON
bytes, including codepoint key order; the future TS consumer must use those bytes.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from functools import wraps
from typing import Any, ParamSpec, Protocol, TypeVar, cast

Json = dict[str, Any]
P = ParamSpec("P")
T = TypeVar("T")
LANE = "bounded_output_residual_consistency"
PREFIX = "qualification-output-"
MAX_JSON = 8 * 1024 * 1024
SAFE = 2**53 - 1
EMPTY_HEAD = "0" * 64
CONTEXT_HASH_FIELDS = frozenset(
    [
        "originalDocumentSha256",
        "originalDependenciesSha256",
        "executionDocumentSha256",
        "executionDependenciesSha256",
        "packageSha256",
        "preflightSha256",
        "manifestSha256",
        "reportSha256",
        "preparationSha256",
        "hostSourceGraphSha256",
        "nativeSourceGraphSha256",
        "installedReleaseSha256",
        "runtimeSha256",
        "profileSha256",
    ]
)
# Raw authority envelopes can change on renewal; their content identities are
# still mandatory in the other closed context hash fields.
AUTHORITY_REFERENCE_FIELDS = frozenset({"preflightSha256", "preparationSha256"})
TRACK_FIELDS = frozenset(["trackId", "kind", "index", "name", "enabled", "locked"])
ITEM_FIELDS = frozenset(
    [
        "itemUid",
        "eventId",
        "sourceId",
        "mediaUid",
        "kind",
        "trackId",
        "recordStart",
        "recordDuration",
        "sourceStart",
        "sourceDuration",
        "linkedItemUids",
        "online",
        "enabled",
        "speed",
        "sourceMappingSha256",
    ]
)
SOURCE_FIELDS = frozenset(
    [
        "sourceId",
        "nativeSourceSha256",
        "pcmMode",
        "provenanceReceiptSha256",
        "provenancePinsSha256",
        "deliveryDerivationSha256",
        "pcmFileSha256",
        "decodedSamplesSha256",
        "originalBitDepth",
        "channels",
        "durationSamples",
        "sampleRate",
        "pcmMappingSha256",
        "nativeFrameOrigin",
        "pcmSampleOrigin",
    ]
)
COMMITMENT_FIELDS = (
    "schemaVersion lane context geometrySha256 geometryCaptureRawSha256 "
    "geometryReceiptSha256 derivedIntentSha256 sourceEntries algorithmSha256 "
    "predictionEncoding predictionBytesSha256 predictionByteLength extentFrames "
    "sampleRate channels createdAt expiresAt commitmentReceiptSha256"
)
RESERVATION_FIELDS = (
    "schemaVersion lane context commitmentRawSha256 commitmentPayloadSha256 "
    "renderIntentSha256 reservationId reservedAt reservationReceiptSha256"
)
DECODE_FIELDS = (
    "schemaVersion lane context sourceOutputRawSha256 container videoCodec audioCodec "
    "audioBitDepth audioSampleRate audioChannels sampleCount decodedSamplesSha256 "
    "decoderIdentitySha256 decoderSourceGraphSha256 "
    "decoderCommandSha256 decodeReceiptSha256"
)


class OutputConsistencyError(ValueError):
    """Refusal; the controller must retain the attempt, including partial effects."""


TEMPORARY_PRESENTER_MESSAGE = "On Camera uses the effective temporary presenter still."
TEMPORARY_PRESENTER_COMPLETION_MESSAGE = (
    "Replace the temporary presenter still when an accepted presenter source "
    "is available."
)
TEMPORARY_PRESENTER_RECOVERY_INSTRUCTION = (
    "Replace the temporary still with an accepted presenter source when available."
)


def _refusal[**P, T](function: Callable[P, T]) -> Callable[P, T]:
    @wraps(function)
    def guarded(*args: P.args, **kwargs: P.kwargs) -> T:
        try:
            return function(*args, **kwargs)
        except (
            KeyError,
            TypeError,
            IndexError,
            AttributeError,
            StopIteration,
            OverflowError,
        ) as error:
            raise OutputConsistencyError("malformed qualification input") from error

    return guarded


class OutputTrust(Protocol):
    """Statically wired trusted product port. Never obtained from request data.

    authenticate must time-invariantly verify seal authenticity and provenance
    of the exact expected payload, including source graphs and native lineage.
    Live native/input/target currentness is checked at receipt issuance and by
    #209 before reservation, never when authenticating historical evidence.
    Only #214 applies expiry via checked_now. Hash equality alone is not
    authentication. No permissive default is supplied.
    """

    def authenticate(self, kind: str, receipt: bytes, expected: Json) -> None: ...

    def checked_now(self) -> datetime: ...


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OutputConsistencyError(message)


def _shape(value: Any, fields: str | frozenset[str], label: str) -> Json:
    keys = frozenset(fields.split()) if isinstance(fields, str) else fields
    _require(type(value) is dict and value.keys() == keys, f"closed {label} shape")
    return value  # type: ignore[no-any-return]


def _integer(value: Any, minimum: int = 0, maximum: int = SAFE) -> int:
    _require(
        type(value) is int and minimum <= value <= maximum,
        "bounded exact integer required",
    )
    return value  # type: ignore[no-any-return]


def _identity(value: Any) -> str:
    _require(type(value) is str and 0 < len(value) <= 512, "bounded identity required")
    _require(
        all(unicodedata.category(c) not in {"Cc", "Cf", "Cs"} for c in value),
        "unsupported Unicode control",
    )
    return value  # type: ignore[no-any-return]


def _stable_compiler_id(label: str) -> str:
    hex_id = hashlib.sha256(label.encode("utf-8")).hexdigest()[:32]
    return (
        f"{hex_id[:8]}-{hex_id[8:12]}-5{hex_id[13:16]}-8{hex_id[17:20]}-{hex_id[20:]}"
    )


@_refusal
def validate_temporary_presenter_report(
    document: Any, manifest: Any, report: Any
) -> set[str]:
    """Validate the sole renderable v2 warning against active slots and events.

    This stdlib-only check is shared by host packaging, cached admission replay,
    and the installed native boundary. It accepts only compiler-shaped temporary
    presenter still warnings, their concrete still events, and matching recovery
    and manual-completion rows.
    """
    _require(
        type(document) is dict and type(manifest) is dict and type(report) is dict,
        "temporary presenter validation requires document, manifest, and report "
        "objects",
    )
    active_draft = document.get("activeDraft")
    _require(type(active_draft) is dict, "active narration draft required")
    blocks_value = active_draft.get("blocks")
    _require(type(blocks_value) is list, "active narration blocks required")
    blocks = cast(list[Any], blocks_value)

    events_raw = manifest.get("events")
    _require(type(events_raw) is list, "manifest events are required")
    events: dict[str, Json] = {}
    for event in events_raw:
        _require(type(event) is dict, "manifest event must be an object")
        event_id = _identity(event.get("eventId"))
        _require(event_id not in events, "duplicate manifest event identity")
        events[event_id] = event

    authored_slots: dict[str, tuple[str, str]] = {}
    for block in blocks:
        _require(type(block) is dict, "narration block must be an object")
        if block.get("type") != "narration" or block.get("state") != "active":
            continue
        sequence = block.get("primaryVisualSequence")
        if type(sequence) is not dict:
            continue
        sequence_id = _identity(sequence.get("id"))
        block_id = _identity(block.get("id"))
        slots_value = sequence.get("slots")
        _require(type(slots_value) is list, "primary visual slots are required")
        slots = cast(list[Any], slots_value)
        for slot in slots:
            _require(type(slot) is dict, "primary visual slot must be an object")
            payload = slot.get("payload")
            if (
                type(payload) is dict
                and payload.get("kind") == "on_camera"
                and payload.get("presenterChoiceId") is None
            ):
                slot_id = _identity(slot.get("id"))
                _require(
                    slot_id not in authored_slots,
                    "temporary presenter slot identity is duplicated",
                )
                authored_slots[slot_id] = (block_id, sequence_id)

    events_by_temporary_slot: dict[str, set[str]] = {}
    for event_id, event in events.items():
        provenance = event.get("provenance")
        if type(provenance) is not dict:
            continue
        event_slot_id = provenance.get("slotId")
        if type(event_slot_id) is not str:
            continue
        authored_identity = authored_slots.get(event_slot_id)
        if authored_identity is None:
            continue
        block_id, sequence_id = authored_identity
        treatment = event.get("pictureTreatment")
        _require(
            provenance.get("blockId") == block_id
            and provenance.get("sequenceId") == sequence_id
            and event.get("kind") == "placeholder"
            and type(treatment) is dict
            and treatment.get("kind") == "still",
            "authored temporary presenter has no matching concrete still event",
        )
        events_by_temporary_slot.setdefault(event_slot_id, set()).add(event_id)

    _require(
        set(events_by_temporary_slot) == set(authored_slots),
        "authored temporary presenter slots have no concrete still events",
    )

    diagnostic_values = report.get("diagnostics")
    _require(
        type(diagnostic_values) is list, "build report diagnostics are not an array"
    )
    if not diagnostic_values:
        _require(
            not events_by_temporary_slot,
            "temporary presenter event is missing its canonical warning",
        )
        _require(
            report.get("recoveryActions") == [],
            "build report has recovery actions without diagnostics",
        )
        return set()

    expected_slots = set(events_by_temporary_slot)
    warnings: list[Json] = []
    seen_slots: set[str] = set()
    for diagnostic in diagnostic_values:
        _require(
            type(diagnostic) is dict, "build report contains an unsupported diagnostic"
        )
        entity = diagnostic.get("entity")
        _require(
            type(entity) is dict, "build report contains an unsupported diagnostic"
        )
        slot_id = _identity(entity.get("id"))
        _require(
            diagnostic.get("code") == "TEMPORARY_PRESENTER_STILL"
            and diagnostic.get("severity") == "warning"
            and diagnostic.get("message") == TEMPORARY_PRESENTER_MESSAGE
            and entity == {"id": slot_id, "kind": "slot", "path": "presenterStill"}
            and slot_id not in seen_slots
            and diagnostic.get("evidence")
            == {"kind": "details", "message": TEMPORARY_PRESENTER_MESSAGE}
            and diagnostic.get("recoveryActionKinds") == ["REPLACE_TEMPORARY_PRESENTER"]
            and diagnostic.get("id")
            == _stable_compiler_id(
                f"TEMPORARY_PRESENTER_STILL:slot:{slot_id}:presenterStill:"
                f"{TEMPORARY_PRESENTER_MESSAGE}"
            ),
            "build report contains a non-canonical presenter warning",
        )
        seen_slots.add(slot_id)
        warnings.append(diagnostic)

    warnings.sort(
        key=lambda row: (
            row["code"],
            row["entity"]["id"],
            row["id"],
        )
    )
    _require(
        diagnostic_values == warnings and seen_slots == expected_slots,
        "presenter warnings do not exactly cover concrete temporary still events",
    )

    manifest_document = manifest.get("document")
    _require(type(manifest_document) is dict, "manifest document identity is required")
    document_id = _identity(manifest_document.get("documentId"))
    first_slot = warnings[0]["entity"]["id"]
    expected_recoveries = [
        {
            "documentId": document_id,
            "instruction": TEMPORARY_PRESENTER_RECOVERY_INSTRUCTION,
            "kind": "REPLACE_TEMPORARY_PRESENTER",
            "slotId": first_slot,
        }
    ]
    _require(
        report.get("recoveryActions") == expected_recoveries,
        "presenter warning recovery action is not canonical",
    )

    expected_completions = [
        {
            "entity": row["entity"],
            "id": _stable_compiler_id(
                f"manual-completion:{document_id}:{row['entity']['id']}"
            ),
            "kind": "placeholder",
            "message": TEMPORARY_PRESENTER_COMPLETION_MESSAGE,
        }
        for row in warnings
    ]
    _require(
        report.get("manualCompletionItems") == expected_completions,
        "presenter manual completion items are not canonical",
    )
    return {
        event_id
        for slot_events in events_by_temporary_slot.values()
        for event_id in slot_events
    }


def _digest(value: Any) -> str:
    _require(
        type(value) is str and re.fullmatch("[0-9a-f]{64}", value) is not None,
        "raw lowercase SHA256 required",
    )
    return value  # type: ignore[no-any-return]


def _legacy_digest(value: Any) -> str:
    _require(type(value) is str, "hash string required")
    return _digest(value.removeprefix("sha256:"))


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _tree(value: Any, depth: int = 0) -> None:
    _require(depth <= 64, "JSON nesting exceeds bound")
    if type(value) is dict:
        for key, child in value.items():
            _require(type(key) is str, "JSON string key required")
            _tree(key, depth + 1)
            _tree(child, depth + 1)
    elif type(value) is list:
        for child in value:
            _tree(child, depth + 1)
    elif type(value) is str:
        # Foreign compiler/ffprobe/receipt text is not an identity. Enforce
        # identity bounds only at the specific closed-record identity fields.
        _require(
            len(value) <= MAX_JSON
            and all(unicodedata.category(c) != "Cs" for c in value),
            "unsupported JSON string",
        )
    elif type(value) is int:
        _require(-SAFE <= value <= SAFE, "unsafe JSON integer")
    elif type(value) is float:
        _require(math.isfinite(value), "nonfinite JSON number")
    else:
        _require(value is None or type(value) is bool, "unsupported JSON value")


def _canonical(value: Any) -> bytes:
    _tree(value)
    try:
        raw = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as error:
        raise OutputConsistencyError("invalid canonical JSON") from error
    _require(len(raw) <= MAX_JSON, "JSON exceeds 8 MiB")
    return raw


def _json_hash(value: Any) -> str:
    return _hash(_canonical(value))


def _parse(raw: bytes) -> Json:
    _require(type(raw) is bytes and len(raw) <= MAX_JSON, "bounded JSON bytes required")

    def pairs(rows: list[tuple[str, Any]]) -> Json:
        result: Json = {}
        for key, value in rows:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    try:
        value = json.loads(raw.decode("utf-8"), object_pairs_hook=pairs)
        _tree(value)
    except (ValueError, UnicodeError, RecursionError) as error:
        raise OutputConsistencyError("invalid JSON record") from error
    _require(type(value) is dict, "JSON object required")
    return value  # type: ignore[no-any-return]


def _list(value: Any, maximum: int, minimum: int = 0) -> list[Any]:
    _require(
        type(value) is list and minimum <= len(value) <= maximum,
        "bounded inventory required",
    )
    return value  # type: ignore[no-any-return]


def _ordered(rows: list[Any], field: str) -> None:
    keys = [_identity(row[field]) for row in rows]
    _require(
        keys == sorted(set(keys)),
        f"unique codepoint-ordered {field} inventory required",
    )


def _timestamp(value: Any) -> datetime:
    _identity(value)
    _require(
        re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,6})?Z", value)
        is not None,
        "UTC timestamp required",
    )
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise OutputConsistencyError("invalid UTC timestamp") from error


def _now(trust: OutputTrust) -> datetime:
    value = trust.checked_now()
    _require(
        isinstance(value, datetime) and value.utcoffset() == UTC.utcoffset(value),
        "trusted UTC clock required",
    )
    return value


def _target(value: Any) -> Json:
    target = _shape(value, "projectName projectUid timelineName timelineUid", "target")
    for item in target.values():
        _identity(item)
    return target


@_refusal
def _context(value: Any) -> Json:
    result = _shape(
        value,
        CONTEXT_HASH_FIELDS
        | frozenset(["lane", "invocationId", "caseId", "phase", "target", "binding"]),
        "context",
    )
    _require(
        result["lane"] == LANE and result["phase"] in {"pristine", "edited", "rebuild"},
        "wrong lane/phase",
    )
    _identity(result["invocationId"])
    _identity(result["caseId"])
    _target(result["target"])
    for key in CONTEXT_HASH_FIELDS:
        _digest(result[key])
    binding = result["binding"]
    _require(type(binding) is dict, "binding required")
    if binding.get("kind") == "baseline":
        _shape(binding, "kind bindingSha256", "baseline binding")
        _require(result["phase"] != "rebuild", "rebuild requires revised binding")
    else:
        _shape(
            binding,
            (
                "kind bindingSha256 acceptedDecisionReceiptSha256 "
                "revisionLedgerSha256 proposalEvidenceSha256 "
                "revisedDocumentSha256 revisedDependenciesSha256 "
                "revisedManifestSha256"
            ),
            "revised binding",
        )
        _require(
            binding["kind"] == "revised" and result["phase"] == "rebuild",
            "wrong revised binding phase",
        )
        for key in binding.keys() - {"kind"}:
            _digest(binding[key])
        _require(
            all(
                result[key] == binding[revised]
                for key, revised in (
                    ("executionDocumentSha256", "revisedDocumentSha256"),
                    ("executionDependenciesSha256", "revisedDependenciesSha256"),
                    ("manifestSha256", "revisedManifestSha256"),
                )
            ),
            "revised input identities differ",
        )
    projection = {
        key: child
        for key, child in result.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {
        key: child for key, child in binding.items() if key != "bindingSha256"
    }
    _require(
        _digest(binding["bindingSha256"]) == _json_hash(projection),
        "stable input binding differs",
    )
    return result


def _record(raw: bytes, name: str, fields: str) -> Json:
    result = _shape(_parse(raw), fields, name)
    _require(
        result["schemaVersion"] == f"{PREFIX}{name}/v1" and result["lane"] == LANE,
        "wrong sibling version/lane",
    )
    if "context" in result:
        _context(result["context"])
    return result


def _projection(record: Json, receipt_field: str) -> Json:
    # Acyclic receipt-payload projection excludes exactly one receipt reference.
    _require(receipt_field in record, "missing receipt reference")
    return {key: value for key, value in record.items() if key != receipt_field}


def _authenticate(
    trust: OutputTrust,
    kind: str,
    record: Json,
    field: str,
    receipt: bytes,
    **additional: Any,
) -> None:
    _require(
        type(receipt) is bytes and 0 < len(receipt) <= MAX_JSON,
        "bounded receipt required",
    )
    _require(_digest(record[field]) == _hash(receipt), "receipt raw bytes differ")
    payload = _projection(record, field)
    # Copies prevent trusted adapters from accidentally mutating consumed inputs.
    expected = _parse(_canonical({**payload, **additional}))
    trust.authenticate(kind, receipt, expected)


@_refusal
def _sources(value: Any) -> list[Json]:
    rows = _list(value, 16)
    raw_hashes: set[str] = set()
    cells = 0
    for source in rows:
        _shape(source, SOURCE_FIELDS, "source entry")
        _identity(source["sourceId"])
        for key in SOURCE_FIELDS:
            if key.endswith("Sha256"):
                _digest(source[key])
        _require(
            source["pcmMode"] in {"wav-direct", "prepared-audio"},
            "unsupported PCM mode",
        )
        _require(
            _integer(source["originalBitDepth"]) in {16, 24}, "unsupported bit depth"
        )
        channels = _integer(source["channels"], 1, 2)
        count = _integer(source["durationSamples"], 960, 16_000_000)
        _require(_integer(source["sampleRate"]) == 48000, "source rate differs")
        _integer(source["nativeFrameOrigin"])
        _integer(source["pcmSampleOrigin"], 0, count)
        _require(source["nativeSourceSha256"] not in raw_hashes, "raw-source alias")
        raw_hashes.add(source["nativeSourceSha256"])
        cells += channels * count
    _require(cells <= 32_000_000, "aggregate source sample cells exceed bound")
    _ordered(rows, "sourceId")
    return rows


def _ledger_key(context: Json) -> tuple[str, str, str, str]:
    ctx = _context(context)
    return (
        ctx["binding"]["bindingSha256"],
        _json_hash({key: ctx["target"][key] for key in ("projectUid", "timelineUid")}),
        ctx["caseId"],
        ctx["phase"],
    )


@_refusal
def _ledger_head(ledger: list[Json]) -> str:
    _list(ledger, 4096)
    head = EMPTY_HEAD
    previous: dict[tuple[str, str, str, str], Json] = {}
    retry_used: set[tuple[str, str, str, str]] = set()
    chain: tuple[str, str, str] | None = None
    for sequence, entry in enumerate(ledger):
        _shape(
            entry,
            (
                "schemaVersion lane context sequence priorHeadSha256 state "
                "commitmentRawSha256 commitmentPayloadSha256 "
                "predictionBytesSha256 reservationRawSha256 resultRawSha256"
                " entrySha256"
            ),
            "ledger entry",
        )
        _require(
            entry["schemaVersion"] == f"{PREFIX}attempt/v1" and entry["lane"] == LANE,
            "wrong ledger version/lane",
        )
        key = _ledger_key(entry["context"])
        if chain is None:
            chain = key[1:]
        _require(chain == key[1:], "mixed target/case/phase ledger")
        _require(
            _integer(entry["sequence"]) == sequence
            and entry["priorHeadSha256"] == head,
            "incomplete/reordered ledger chain",
        )
        _require(
            _digest(entry["entrySha256"])
            == _json_hash(_projection(entry, "entrySha256")),
            "ledger tampering",
        )
        for field in (
            "commitmentRawSha256",
            "commitmentPayloadSha256",
            "predictionBytesSha256",
        ):
            _digest(entry[field])
        prior = previous.get(key)
        state = entry["state"]
        _identity(state)
        if state == "committed":
            _require(
                prior is None
                or prior["state"] == "expired_unused"
                or (prior["state"] == "render_failed" and key not in retry_used),
                "binding already attempted",
            )
            if prior is not None and prior["state"] == "render_failed":
                _require(
                    entry["context"] == prior["context"]
                    and entry["predictionBytesSha256"]
                    == prior["predictionBytesSha256"],
                    "render retry context/prediction changed",
                )
                retry_used.add(key)
            elif prior is not None:
                _require(
                    entry["predictionBytesSha256"] == prior["predictionBytesSha256"],
                    "expired prediction changed",
                )
                _require(key not in retry_used, "render retry already used")
            _require(
                entry["reservationRawSha256"] is None
                and entry["resultRawSha256"] is None,
                "future commitment references",
            )
        else:
            _require(prior is not None, "attempt lacks commitment")
            assert prior is not None
            for field in (
                "commitmentRawSha256",
                "commitmentPayloadSha256",
                "predictionBytesSha256",
                "context",
            ):
                _require(entry[field] == prior[field], "attempt lineage changed")
            if state == "expired_unused":
                _require(
                    prior["state"] == "committed"
                    and entry["reservationRawSha256"] is None
                    and entry["resultRawSha256"] is None,
                    "only unused commitments expire",
                )
            elif state == "reserved_by_render_intent":
                _require(
                    prior["state"] == "committed" and entry["resultRawSha256"] is None,
                    "exclusive reservation already used",
                )
                _digest(entry["reservationRawSha256"])
            else:
                _require(
                    state
                    in {
                        "uncertain",
                        "render_failed",
                        "compared_consistent",
                        "compared_refused",
                    }
                    and prior["state"] == "reserved_by_render_intent",
                    "terminal/uncertain attempt cannot restart",
                )
                _require(
                    entry["reservationRawSha256"] == prior["reservationRawSha256"],
                    "reservation changed",
                )
                if state == "uncertain":
                    _require(entry["resultRawSha256"] is None, "uncertain result")
                else:
                    _digest(entry["resultRawSha256"])
        previous[key] = entry
        head = entry["entrySha256"]
    return head


@_refusal
def _append_ledger(ledger: list[Json], event: Json, expected_head: str) -> list[Json]:
    _require(
        _ledger_head(ledger) == _digest(expected_head),
        "prior-terminal-head CAS refused",
    )
    _shape(
        event,
        (
            "context state commitmentRawSha256 commitmentPayloadSha256 "
            "predictionBytesSha256 reservationRawSha256 resultRawSha256"
        ),
        "ledger event",
    )
    entry = {
        "schemaVersion": f"{PREFIX}attempt/v1",
        "lane": LANE,
        **event,
        "sequence": len(ledger),
        "priorHeadSha256": expected_head,
    }
    entry["entrySha256"] = _json_hash(entry)
    result = [*ledger, entry]
    _ledger_head(result)
    # This is a pure CAS projection. #209 must persist with real exclusion/fsync.
    return json.loads(_canonical(result))  # type: ignore[no-any-return]


def _attempt(ledger: list[Json], context: Json) -> Json | None:
    _ledger_head(ledger)
    key = _ledger_key(context)
    return next(
        (row for row in reversed(ledger) if _ledger_key(row["context"]) == key), None
    )


def _render_retry_used(ledger: list[Json], context: Json) -> bool:
    _ledger_head(ledger)
    key = _ledger_key(context)
    prior_state: str | None = None
    for row in ledger:
        if _ledger_key(row["context"]) == key:
            if row["state"] == "committed" and prior_state == "render_failed":
                return True
            prior_state = row["state"]
    return False


def _blobs(blobs: Mapping[str, bytes], context: Json) -> None:
    _require(
        blobs.keys() == CONTEXT_HASH_FIELDS,
        "complete independently pinned input bytes required",
    )
    for key, raw in blobs.items():
        _require(
            type(raw) is bytes and len(raw) <= MAX_JSON and _hash(raw) == context[key],
            f"current {key} bytes differ",
        )
