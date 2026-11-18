"""Pure product checks for canonical renderable build-report warnings.

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


SPEECH_CUT_WARNING = (
    "No measured pause supports an early picture cut. "
    "The cut stays at the incoming word start."
)

SPEECH_CUT_SOURCE_WARNING = (
    "The incoming clip has too few source frames for the full early cut. "
    "The lead was shortened."
)

TEMPORARY_PRESENTER_MESSAGE = "On Camera uses the effective temporary presenter still."
TEMPORARY_PRESENTER_COMPLETION_MESSAGE = (
    "Replace the temporary presenter still when an accepted presenter source "
    "is available."
)
TEMPORARY_PRESENTER_RECOVERY_INSTRUCTION = (
    "Replace the temporary still with an accepted presenter source when available."
)
_MUSIC_WARNING_CODES = frozenset(
    {
        "MUSIC_FILE_MISSING",
        "MUSIC_SOURCE_SHORTER",
        "MUSIC_SPAN_INVALID",
        "MUSIC_SETTINGS_UNSUPPORTED",
    }
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


def _validate_music_diagnostic(
    diagnostic: Any,
    spans: set[str],
) -> None:
    """Accept compiler-shaped music diagnostics for authored spans."""
    _require(
        type(diagnostic) is dict, "build report contains an unsupported diagnostic"
    )
    code = diagnostic.get("code")
    span_id = _identity(diagnostic.get("entity", {}).get("id"))
    _require(span_id in spans, "music warning does not name an authored span")
    message = diagnostic.get("message")
    _require(
        type(message) is str
        and bool(message)
        and len(message) <= 4096
        and all(unicodedata.category(c) not in {"Cc", "Cf", "Cs"} for c in message),
        "music warning message is malformed",
    )
    entity = {"id": span_id, "kind": "block", "path": f"rowAudioSpans/{span_id}"}
    warning = diagnostic.get("severity") == "warning"
    invalid_timing = (
        code == "MUSIC_SPAN_INVALID"
        and diagnostic.get("severity") == "blocking"
        and diagnostic.get("recoveryActionKinds") == ["manual_review"]
    )
    _require(
        (warning and diagnostic.get("recoveryActionKinds") == ["none"])
        or invalid_timing,
        "music warning severity or recovery action is non-canonical",
    )
    _require(
        diagnostic
        == {
            "id": _stable_compiler_id(
                f"{code}:block:{span_id}:rowAudioSpans/{span_id}:{message}"
            ),
            "severity": diagnostic["severity"],
            "code": code,
            "message": message,
            "entity": entity,
            "evidence": {"kind": "details", "message": message},
            "recoveryActionKinds": diagnostic["recoveryActionKinds"],
        },
        "build report contains a non-canonical music warning",
    )


def _music_recovery_actions(diagnostics: list[Json], manifest: Json) -> list[Json]:
    """Derive the small canonical recovery rows supported by music diagnostics."""
    kinds: list[str] = []
    for diagnostic in sorted(
        diagnostics,
        key=lambda row: (
            row["code"],
            row["entity"]["id"],
            row["id"],
        ),
    ):
        for kind in diagnostic["recoveryActionKinds"]:
            if kind not in kinds:
                kinds.append(kind)

    actions: list[Json] = []
    for kind in kinds:
        if kind == "none":
            actions.append(
                {"kind": "none", "instruction": "No repair action is required."}
            )
        elif kind == "manual_review":
            manifest_document = manifest.get("document")
            _require(
                type(manifest_document) is dict,
                "manifest document identity is required",
            )
            document_id = _identity(manifest_document.get("documentId"))
            actions.append(
                {
                    "kind": "manual_review",
                    "entity": {
                        "id": document_id,
                        "kind": "document",
                        "path": "document",
                    },
                    "instruction": "Review the compiler diagnostic.",
                }
            )
    return actions


@_refusal
def validate_temporary_presenter_report(
    document: Any, manifest: Any, report: Any
) -> set[str]:
    """Validate renderable v2 warnings against their authored owners and events.

    This stdlib-only check is shared by host packaging, cached admission replay,
    and the installed native boundary. Music and speech warnings are admitted
    independently; presenter warnings still require concrete still events and
    matching recovery and manual-completion rows.
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

    music_spans: set[str] = set()
    raw_music_spans = document.get("rowAudioSpans", [])
    _require(type(raw_music_spans) is list, "music spans are malformed")
    for span in cast(list[Any], raw_music_spans):
        _require(type(span) is dict, "music span is malformed")
        span_id = _identity(span.get("id"))
        _require(span_id not in music_spans, "duplicate music span identity")
        music_spans.add(span_id)

    authored_slots: dict[str, tuple[str, str]] = {}
    speech_cut_slots: set[str] = set()
    speech_cut_compiler = (
        manifest.get("compiler", {}).get("version") == "compiler/v2-speech-cuts"
    )
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
                speech_cut_compiler
                and slot.get("relation", {}).get("kind") == "sequential"
                and slot.get("boundaryBefore", {}).get("kind") == "spoken_word"
                and type(payload) is dict
                and payload.get("kind") == "visual"
            ):
                speech_cut_slots.add(_identity(slot.get("id")))
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
    presenter_diagnostics = []
    warned_speech_slots: set[str] = set()
    music_diagnostics: list[Json] = []
    for diagnostic in diagnostic_values:
        if (
            type(diagnostic) is dict
            and isinstance(diagnostic.get("code"), str)
            and diagnostic["code"] in _MUSIC_WARNING_CODES
        ):
            _validate_music_diagnostic(
                diagnostic,
                music_spans,
            )
            music_diagnostics.append(diagnostic)
            continue
        if (
            speech_cut_compiler
            and type(diagnostic) is dict
            and diagnostic.get("code") == "WORD_TIMING_REQUIRED"
        ):
            slot_id = _identity(diagnostic.get("entity", {}).get("id"))
            message = diagnostic.get("message")
            _require(
                message in (SPEECH_CUT_WARNING, SPEECH_CUT_SOURCE_WARNING)
                and slot_id in speech_cut_slots
                and slot_id not in warned_speech_slots
                and diagnostic
                == {
                    "id": _stable_compiler_id(
                        f"WORD_TIMING_REQUIRED:slot:{slot_id}:boundaryBefore:{message}"
                    ),
                    "code": "WORD_TIMING_REQUIRED",
                    "message": message,
                    "entity": {"id": slot_id, "kind": "slot", "path": "boundaryBefore"},
                    "severity": "warning",
                    "evidence": {
                        "kind": "anchor_issue",
                        "anchorId": slot_id,
                        "reason": "word_timing_required",
                    },
                    "recoveryActionKinds": [],
                },
                "build report contains a non-canonical speech cut warning",
            )
            warned_speech_slots.add(slot_id)
        else:
            presenter_diagnostics.append(diagnostic)
    diagnostic_values = presenter_diagnostics
    music_recovery_actions = _music_recovery_actions(music_diagnostics, manifest)
    if not diagnostic_values:
        _require(
            not events_by_temporary_slot,
            "temporary presenter event is missing its canonical warning",
        )
        if music_diagnostics:
            _require(
                report.get("recoveryActions") == music_recovery_actions,
                "build report recovery actions are not canonical for music diagnostics",
            )
        else:
            _require(
                report.get("recoveryActions") == [],
                "build report has recovery actions without diagnostics",
            )
        _require(
            report.get("manualCompletionItems") in (None, []),
            "build report has manual completion items without diagnostics",
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
    expected_recoveries = music_recovery_actions + expected_recoveries
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
