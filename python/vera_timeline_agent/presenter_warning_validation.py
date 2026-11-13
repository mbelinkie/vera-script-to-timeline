"""Pure product checks for canonical temporary-presenter report warnings.

Extracted intact from the archived qualification output records so packaging
can continue to refuse malformed warnings after proof-code retirement.
"""

from __future__ import annotations

import hashlib
import unicodedata
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

Json = dict[str, Any]
P = ParamSpec("P")
T = TypeVar("T")


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


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise OutputConsistencyError(message)


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
