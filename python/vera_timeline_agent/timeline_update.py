"""Plan and record an update of only the changed rows of a finished timeline.

Pure and SDK-free. The route rules are the measured #327 result for Resolve
Studio 21.1.1 build 10: a same-length picture swap through the take selector
keeps the clip, its neighbours and a boundary dissolve; anything that would
move, trim or recreate a clip is refused, because that version has no scripted
in-place move or trim and recreating a clip loses its hand finishing.

The plan and attempt records use the #328 selective-outbound shape, with the
same canonical hash, so the TypeScript contract can load them unchanged.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

ROUTE_REPLACE = "replace_in_place"
ROUTE_RETIME = "retime"
ROUTE_TRANSITION = "transition"
LENGTH_CHANGE = "timeline-length-change"
PICTURE_KINDS = frozenset({"primary_visual", "overlay_visual"})

# #102 reports this against where clips are now; on a retime they move too.
_RIDES_ALONG = frozenset(
    {"An unassigned editor clip overlaps row clips or a linked transition/music span."}
)
_NO_MOVE = (
    "Resolve 21.1.1 cannot move or trim existing clips from a script. "
    "Doing this would mean deleting and recreating clips and losing the "
    "finishing on them. Make this change by hand on a copy, or upgrade Resolve."
)
_EVENT_IDENTITY_FIELDS = frozenset(
    {
        "eventId",
        "provenance",
        "sourceRange",
        "preparationBindingHash",
        "sourceTimeMapping",
    }
)
_VIEW_IDENTITY_FIELDS = frozenset({"id", "sourceId", "sourceRange", "v2Event"})
_TRANSITION_IDENTITY_FIELDS = frozenset(
    {"outgoingEventId", "incomingEventId", "reason"}
)


class UpdatePlanError(ValueError):
    """The update cannot be planned or recorded safely."""


def canonical(value: Any) -> str:
    """Canonical JSON identical to the #328 TypeScript implementation.

    Only strings, integers, booleans, null, arrays and string-keyed objects are
    accepted, because a float is not spelled the same way in both languages.
    """

    def check(item: Any) -> None:
        if item is None or isinstance(item, (str, bool)):
            return
        if type(item) is int:
            if abs(item) > 2**53 - 1:
                raise UpdatePlanError("integer outside the safe JSON range")
            return
        if isinstance(item, Mapping):
            for key, child in item.items():
                if not isinstance(key, str):
                    raise UpdatePlanError("record keys must be strings")
                check(child)
            return
        if isinstance(item, (list, tuple)):
            for child in item:
                check(child)
            return
        raise UpdatePlanError("record holds a value JSON cannot spell exactly")

    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def outbound_hash(value: Any) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def _row_events(view: Mapping[str, Any], row_id: str) -> dict[tuple[Any, ...], Any]:
    """A row's delivered clips, keyed by where they sit rather than by ID."""
    result: dict[tuple[Any, ...], Any] = {}
    for event in view["events"]:
        original = event["v2Event"]
        if original["provenance"].get("blockId") != row_id:
            continue
        record = event["recordRange"]
        key = (
            event["trackId"],
            record["startFrame"],
            record["durationFrames"],
            original["kind"],
        )
        if key in result:
            raise UpdatePlanError(f"two clips of one row share a position: {row_id}")
        result[key] = event
    return result


def _strip(value: Mapping[str, Any], fields: frozenset[str]) -> dict[str, Any]:
    return {key: item for key, item in value.items() if key not in fields}


def _plain_speed(event: Mapping[str, Any]) -> bool:
    source = event.get("sourceRange")
    return (
        isinstance(source, Mapping)
        and source.get("durationFrames") == event["recordRange"]["durationFrames"]
    )


def _transitions(manifest: Mapping[str, Any], row_id: str) -> dict[str, Any]:
    return {
        plan["id"]: _strip(plan, _TRANSITION_IDENTITY_FIELDS)
        for plan in manifest.get("transitions", [])
        if row_id in (plan.get("fromRowId"), plan["toRowId"])
    }


def _row_labels(document: Mapping[str, Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    number = 0
    for block in document["activeDraft"]["blocks"]:
        kind = block.get("type")
        if kind == "narration" and block.get("state") != "active":
            continue
        if kind not in {"narration", "visual_only"}:
            continue
        number += 1
        text = " ".join(str(block.get("text") or "").split())
        snippet = f" “{text[:40]}{'…' if len(text) > 40 else ''}”" if text else ""
        labels[block["id"]] = f"Row {number}{snippet}"
    return labels


def _layout(view: Mapping[str, Any], row_id: str) -> list[tuple[Any, ...]]:
    """Where a row's clips sit, relative to the row's first frame."""
    events = _row_events(view, row_id)
    if not events:
        return []
    origin = min(key[1] for key in events)
    return sorted((key[0], key[1] - origin, key[2], key[3]) for key in events)


def _sequence(view: Mapping[str, Any], row_id: str) -> dict[tuple[Any, ...], list[Any]]:
    """A row's clips in time order on each track, for pairing across a retime."""
    result: dict[tuple[Any, ...], list[Any]] = {}
    for key, event in sorted(_row_events(view, row_id).items(), key=lambda i: i[0][1]):
        result.setdefault((key[0], key[3]), []).append(event)
    return result


_RETIME_IDENTITY = _EVENT_IDENTITY_FIELDS | {"recordRange", "music"}
_RETIME_VIEW_IDENTITY = _VIEW_IDENTITY_FIELDS | {"recordRange"}


def _retime_row(
    row: Mapping[str, Any],
    *,
    baseline_manifest: Mapping[str, Any],
    baseline_view: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    current_view: Mapping[str, Any],
    saved_items: Mapping[str, Mapping[str, Any]],
    observed: Mapping[str, Mapping[str, Any]],
    takes: Mapping[str, int | None],
) -> tuple[str | None, list[dict[str, Any]], list[str]]:
    """Per-clip moves, resizes and replacements for one row on 21.2."""
    row_id = row["rowId"]
    if row["scriptChange"] in {"added", "removed"} or row["reordered"]:
        return (
            "Adding, removing or reordering rows is not done in place yet. "
            "Make this change by hand, or build the timeline afresh.",
            [],
            [],
        )
    before, after = _sequence(baseline_view, row_id), _sequence(current_view, row_id)
    if {k: len(v) for k, v in before.items()} != {k: len(v) for k, v in after.items()}:
        return (
            "The change adds or removes clips inside this row. That is not "
            "done in place yet.",
            [],
            [],
        )
    sources = {source["id"]: source for source in current_view["sources"]}
    old_sources = {source["id"]: source for source in baseline_view["sources"]}
    edits: list[dict[str, Any]] = []
    warnings: list[str] = []
    for key in sorted(before, key=str):
        for old, new in zip(before[key], after[key], strict=True):
            if old["v2Event"] == new["v2Event"]:
                continue
            saved = saved_items[old["id"]]
            uid = saved["resolveItemId"]
            seen = observed.get(uid)
            source, old_source = sources[new["sourceId"]], old_sources[old["sourceId"]]
            kind = new["v2Event"]["kind"]
            same_media = source["contentHash"] == old_source["contentHash"] and (
                new.get("sourceRange") or {}
            ).get("startFrame") == (old.get("sourceRange") or {}).get("startFrame")
            if (
                source["kind"] not in {"video", "audio"}
                or old_source["kind"] != (source["kind"])
            ):
                return (
                    "This row holds a still or a placeholder. Moving or "
                    "resizing those in place has not been measured.",
                    [],
                    [],
                )
            if (
                _music_settings(old["v2Event"]) != _music_settings(new["v2Event"])
                or _strip(old["v2Event"], _RETIME_IDENTITY)
                != _strip(new["v2Event"], _RETIME_IDENTITY)
                or _strip(old, _RETIME_VIEW_IDENTITY)
                != _strip(new, _RETIME_VIEW_IDENTITY)
                or not _plain_speed(old)
                or not _plain_speed(new)
            ):
                return (
                    "This row changes how a clip is framed, sped up or "
                    "treated. That needs the clip recreated, which would lose "
                    "its finishing.",
                    [],
                    [],
                )
            if (
                seen is None
                or seen["status"] != ["unchanged"]
                or seen.get("cannotRead")
            ):
                return (
                    "A clip of this row was moved, trimmed, replaced or removed "
                    "by hand in Resolve, so VERA cannot move or resize it "
                    "without losing track of it.",
                    [],
                    [],
                )
            swap = replace = False
            if not same_media:
                if kind in PICTURE_KINDS and source["kind"] == "video":
                    swap = True
                    if takes.get(uid) != 0:
                        return (
                            "A clip of this row already has takes in Resolve's "
                            "take selector, so VERA will not add its own.",
                            [],
                            [],
                        )
                elif kind == "narration" and source["kind"] == "audio":
                    replace = True
                    warnings.append(
                        "The narration is a new recording, so its clip is "
                        "replaced. Level, fades, EQ, audio effects, colour, "
                        "flags and markers are carried over."
                    )
                else:
                    return (
                        "This row changes music or source sound to a different "
                        "file. Only picture and narration are replaced in place.",
                        [],
                        [],
                    )
            edits.append(
                {
                    "route": ROUTE_RETIME,
                    "eventId": new["id"],
                    "previousEventId": old["id"],
                    "resolveItemId": uid,
                    "trackKind": new["trackKind"],
                    "trackId": new["trackId"],
                    "startFrame": new["recordRange"]["startFrame"],
                    "durationFrames": new["recordRange"]["durationFrames"],
                    "previousStartFrame": old["recordRange"]["startFrame"],
                    "previousDurationFrames": old["recordRange"]["durationFrames"],
                    "sourceId": new["sourceId"],
                    "sourceStartFrame": new["sourceRange"]["startFrame"],
                    "swapPicture": swap,
                    "replaceAudio": replace,
                }
            )
    old_ids = {
        plan["id"]
        for plan in baseline_manifest.get("transitions", [])
        if plan["disposition"] == "apply"
    }
    for plan in current_manifest.get("transitions", []):
        if (
            row_id in (plan.get("fromRowId"), plan["toRowId"])
            and plan["disposition"] == "apply"
            and plan["id"] not in old_ids
        ):
            return (
                "The script adds a transition on this row's cut. Adding a "
                "transition in place is not done yet.",
                [],
                [],
            )
    # A transition survives only when both sides of its cut move together.
    by_event = {edit["previousEventId"]: edit for edit in edits}
    new_plans = {plan["id"]: plan for plan in current_manifest.get("transitions", [])}
    for old_plan in baseline_manifest.get("transitions", []):
        if "fromRowId" not in old_plan and old_plan["toRowId"] == row_id:
            if (
                new_plans.get(old_plan["id"]) != old_plan
                or old_plan["incomingEventId"] in by_event
            ):
                return (
                    "The opening fade or its picture changed. Rebuild the timeline to keep the fade.",
                    [],
                    [],
                )
        if old_plan.get("fromRowId") != row_id or old_plan["disposition"] != "apply":
            continue
        new_plan = new_plans.get(old_plan["id"])
        if new_plan is None or _relative(old_plan) != _relative(new_plan):
            return (
                "The transition after this row changes in the script. Changing "
                "a transition in place is not done yet.",
                [],
                [],
            )
        delta = new_plan["boundaryFrame"] - old_plan["boundaryFrame"]
        outgoing = by_event.get(old_plan["outgoingEventId"])
        pure_move = outgoing is None or (
            outgoing["durationFrames"] == outgoing["previousDurationFrames"]
            and not outgoing["swapPicture"]
        )
        start_delta = (
            outgoing["startFrame"] - outgoing["previousStartFrame"] if outgoing else 0
        )
        if pure_move and start_delta == delta:
            continue  # Both clips travel in one move; the dissolve goes along.
        edits.append(
            {
                "route": ROUTE_TRANSITION,
                "transitionId": new_plan["id"],
                "outgoingEventId": new_plan["outgoingEventId"],
                "previousStartFrame": old_plan["startFrame"],
                "previousEndFrame": old_plan["endFrame"],
                "startFrame": new_plan["startFrame"],
                "endFrame": new_plan["endFrame"],
                "durationFrames": new_plan["requestedDurationFrames"],
                "alignment": new_plan["alignment"],
                "effectName": new_plan["effectIdentity"]["name"],
                "effectCategory": new_plan["effectIdentity"]["category"],
            }
        )
        warnings.append(
            "Resolve drops the transition after this row when the cut moves. "
            "VERA puts the script's transition back; any hand adjustment to "
            "it is lost."
        )
    if not edits:
        return (
            "The script change to this row does not alter any clip VERA "
            "placed, so there is nothing to update in Resolve.",
            [],
            [],
        )
    return None, edits, warnings


def _music_settings(event: Mapping[str, Any]) -> Any:
    """A music span's own settings, without the frame it was asked to end on."""
    music = event.get("music")
    if not isinstance(music, Mapping):
        return music
    return {key: value for key, value in music.items() if key != "requestedEndFrame"}


def _relative(plan: Mapping[str, Any]) -> dict[str, Any]:
    """A transition plan without clip IDs or its absolute position."""
    value = _strip(plan, _TRANSITION_IDENTITY_FIELDS)
    boundary = value.pop("boundaryFrame")
    value["startFrame"] -= boundary
    value["endFrame"] -= boundary
    return value


def global_gaps_for_group(comparison: Mapping[str, Any]) -> list[str]:
    unowned = comparison["unownedCompiledEvents"]
    if unowned["baseline"] != unowned["current"]:
        return ["clips that belong to no script row changed"]
    return []


def editor_moves(
    observation: Mapping[str, Any], comparison: Mapping[str, Any]
) -> tuple[dict[str, int], list[str]]:
    """How far each clip he added must travel with the rows it sits over.

    A clip over rows that all move by the same amount moves with them. One
    over rows that move differently has no single right place, so it is
    reported as a problem and nothing is guessed.
    """
    rows = [
        (row["baselineStartFrame"], row["baselineEndFrame"], row["shiftFrames"])
        for row in comparison["rows"]
        if row["baselineStartFrame"] is not None
    ]
    moves: dict[str, int] = {}
    problems: list[str] = []
    for observed_row in observation["rows"]:
        for item in observed_row["items"]:
            if item["status"] != ["added"]:
                continue
            start, duration = item.get("startFrame"), item.get("durationFrames")
            where = f"{item.get('trackKind')} {item.get('trackIndex')}"
            if start is None or duration is None:
                problems.append(f"a clip you added on {where} has unreadable timing")
                continue
            shifts = {
                shift
                for first, last, shift in rows
                if first < start + duration and start < last
            }
            if not shifts:
                earlier = [shift for first, last, shift in rows if last <= start]
                shifts = {earlier[-1] if earlier else 0}
            if len(shifts) != 1:
                problems.append(
                    f"a clip you added on {where} at frame {start} sits over "
                    "rows that move by different amounts"
                )
                continue
            delta = shifts.pop()
            if delta:
                moves[item["resolveItemId"]] = delta
    return moves, problems


def _bind_retime_group(
    plans: list[dict[str, Any]],
    observation: Mapping[str, Any],
    comparison: Mapping[str, Any],
    gaps: Any,
) -> None:
    """A change of length is applied to every changed row together, or not at all."""
    members = [plan for plan in plans if plan["group"] == ROUTE_RETIME]
    if not members:
        return
    blockers = [
        f"{plan['label']} cannot be updated ({plan['refusal']})"
        for plan in plans
        if plan["refusal"] is not None
    ]
    blockers += editor_moves(observation, comparison)[1]
    blockers += gaps(comparison)
    if not blockers:
        for plan in plans:
            plan["group"] = ROUTE_RETIME  # Same-length swaps join the one update.
        return
    for plan in members:
        if plan["refusal"] is None:
            plan["refusal"] = (
                "The timeline's length changes, so every changed row has to be "
                f"updated together, and that is not possible: {blockers[0]}."
            )
            plan["edits"] = []


def plan_rows(
    *,
    baseline_manifest: Mapping[str, Any],
    baseline_view: Mapping[str, Any],
    baseline_document: Mapping[str, Any],
    current_manifest: Mapping[str, Any],
    current_view: Mapping[str, Any],
    current_document: Mapping[str, Any],
    saved_map: Mapping[str, Any],
    comparison: Mapping[str, Any],
    observation: Mapping[str, Any],
    takes: Mapping[str, int | None],
    can_retime: bool = False,
) -> list[dict[str, Any]]:
    """One entry per row the script change affects, in script order.

    ``comparison`` is the #102 three-way result and ``observation`` the #101
    read-back it was made from. ``takes`` is the take-selector count of each
    managed clip, read from Resolve; ``None`` means it could not be read.
    ``can_retime`` is true on a Resolve that moves and trims clips in place
    (measured on Studio 21.2.0 build 6): rows may then change length and
    later rows move, as one group that is applied together.
    """
    saved_items = {
        item["eventId"]: item for row in saved_map["rows"] for item in row["items"]
    }
    observed = {
        item["resolveItemId"]: item
        for row in observation["rows"]
        for item in row["items"]
    }
    observed_rows = {row.get("rowId"): row["items"] for row in observation["rows"]}
    sources = {source["id"]: source for source in current_view["sources"]}
    old_sources = {source["id"]: source for source in baseline_view["sources"]}
    old_labels = _row_labels(baseline_document)
    new_labels = _row_labels(current_document)
    plans: list[dict[str, Any]] = []
    for row in comparison["rows"]:
        row_id = row["rowId"]
        old_transitions = _transitions(baseline_manifest, row_id)
        new_transitions = _transitions(current_manifest, row_id)
        transition_changed = old_transitions != new_transitions
        if (
            row["scriptChange"] == "unchanged"
            and not row["shiftFrames"]
            and not transition_changed
        ):
            continue
        refusal: str | None = None
        edits: list[dict[str, Any]] = []
        warnings: list[str] = []
        old_length = (row["baselineEndFrame"] or 0) - (row["baselineStartFrame"] or 0)
        new_length = (row["currentEndFrame"] or 0) - (row["currentStartFrame"] or 0)
        group: str | None = None
        structural = bool(
            row["scriptChange"] in {"added", "removed"}
            or row["reordered"]
            or row["shiftFrames"]
            or old_length != new_length
            or _layout(baseline_view, row_id) != _layout(current_view, row_id)
        )
        if can_retime and structural:
            group = ROUTE_RETIME
            refusal, edits, warnings = _retime_row(
                row,
                baseline_manifest=baseline_manifest,
                baseline_view=baseline_view,
                current_manifest=current_manifest,
                current_view=current_view,
                saved_items=saved_items,
                observed=observed,
                takes=takes,
            )
        elif row["scriptChange"] == "added":
            refusal = f"This row is new in the script. {_NO_MOVE}"
        elif row["scriptChange"] == "removed":
            refusal = f"This row was removed from the script. {_NO_MOVE}"
        elif row["reordered"]:
            refusal = f"This row changed position in the script. {_NO_MOVE}"
        elif old_length != new_length:
            refusal = (
                f"This row changes length from {old_length} to {new_length} "
                f"frames. {_NO_MOVE}"
            )
        elif row["shiftFrames"]:
            refusal = (
                f"An earlier row changed, so this row would move "
                f"{abs(row['shiftFrames'])} frames. {_NO_MOVE}"
            )
        elif transition_changed:
            refusal = (
                "The transition on this row's cut changes. Resolve 21.1.1 "
                "drops a transition when a neighbouring clip is recreated, so "
                "this is not done automatically."
            )
        else:
            before = _row_events(baseline_view, row_id)
            after = _row_events(current_view, row_id)
            if before.keys() != after.keys():
                refusal = (
                    "The change adds, removes or re-times clips inside this "
                    f"row, not only swaps a picture. {_NO_MOVE}"
                )
            for key in sorted(before.keys() & after.keys(), key=str):
                if refusal is not None:
                    break
                old, new = before[key], after[key]
                if old["v2Event"] == new["v2Event"]:
                    continue
                saved = saved_items[old["id"]]
                seen = observed.get(saved["resolveItemId"])
                source = sources[new["sourceId"]]
                if (
                    new["v2Event"]["kind"] not in PICTURE_KINDS
                    or new.get("trackKind") != "video"
                    or source["kind"] != "video"
                    or old_sources[old["sourceId"]]["kind"] != "video"
                ):
                    refusal = (
                        "This row changes narration, music, a still or a "
                        "placeholder. Only a video picture swap has been shown "
                        "to keep finishing on Resolve 21.1.1."
                    )
                elif (
                    _strip(old["v2Event"], _EVENT_IDENTITY_FIELDS)
                    != _strip(new["v2Event"], _EVENT_IDENTITY_FIELDS)
                    or _strip(old, _VIEW_IDENTITY_FIELDS)
                    != _strip(new, _VIEW_IDENTITY_FIELDS)
                    or not _plain_speed(old)
                    or not _plain_speed(new)
                ):
                    refusal = (
                        "This row changes how a clip is framed, timed or "
                        "treated, not only which picture it shows. That needs "
                        "the clip recreated, which would lose its finishing."
                    )
                elif (
                    seen is None
                    or seen["status"] != ["unchanged"]
                    or seen.get("cannotRead")
                ):
                    refusal = (
                        "The clip for this row was moved, trimmed, replaced or "
                        "removed by hand in Resolve, so it cannot be swapped "
                        "in place."
                    )
                elif takes.get(saved["resolveItemId"]) != 0:
                    refusal = (
                        "The clip for this row already has takes in Resolve's "
                        "take selector (or they could not be read), so VERA "
                        "will not add its own."
                    )
                else:
                    start = new["sourceRange"]["startFrame"]
                    same_media = (
                        source["contentHash"]
                        == old_sources[old["sourceId"]]["contentHash"]
                        and start == old["sourceRange"]["startFrame"]
                    )
                    edits.append(
                        {
                            "route": ROUTE_REPLACE,
                            "eventId": new["id"],
                            "previousEventId": old["id"],
                            "resolveItemId": saved["resolveItemId"],
                            "sourceId": new["sourceId"],
                            "sourceStartFrame": start,
                            "durationFrames": new["recordRange"]["durationFrames"],
                            "swapPicture": not same_media,
                        }
                    )
            if refusal is None and not edits:
                refusal = (
                    "The script change to this row does not alter any clip "
                    "VERA placed, so there is nothing to update in Resolve."
                )
            if refusal is None and any(
                plan["disposition"] == "apply" for plan in new_transitions.values()
            ):
                warnings.append(
                    "A transition sits on this row's cut. It should stay; it "
                    "is checked after the update."
                )
        if refusal is not None:
            edits = []
        conflict = row["state"] == "both_conflict"
        if (
            conflict
            and group == ROUTE_RETIME
            and row["scriptChange"] == "unchanged"
            and set(row["hazards"]) <= _RIDES_ALONG
            and all(
                item["status"] in (["unchanged"], ["added"])
                and not item.get("cannotRead")
                for item in observed_rows.get(row_id, [])
            )
        ):
            # The row only moves, and the only Resolve-side difference is clips
            # he added over or beside it. They travel with the rows they sit
            # over, and the precheck refuses if any two would then collide.
            conflict = False
        plans.append(
            {
                "rowId": row_id,
                "label": new_labels.get(row_id)
                or f"Removed row (was {old_labels.get(row_id, row_id)})",
                "state": row["state"],
                "conflict": conflict,
                "conflictReason": row["reason"] if conflict else None,
                "hazards": list(row["hazards"]) if conflict else [],
                "refusal": refusal,
                "edits": edits,
                "warnings": warnings,
                "group": group,
                "summary": (
                    f"{old_length} to {new_length} frames"
                    if old_length != new_length
                    else f"moves {abs(row['shiftFrames'])} frames "
                    f"{'later' if row['shiftFrames'] > 0 else 'earlier'}"
                    if row["shiftFrames"]
                    else "picture swapped"
                ),
            }
        )
    if can_retime:
        _bind_retime_group(plans, observation, comparison, global_gaps_for_group)
    return plans


def global_gaps(
    baseline_view: Mapping[str, Any],
    current_view: Mapping[str, Any],
    comparison: Mapping[str, Any],
) -> list[str]:
    """Script-side changes that belong to no row and are therefore not applied."""
    gaps: list[str] = []
    unowned = comparison["unownedCompiledEvents"]
    if unowned["baseline"] != unowned["current"]:
        gaps.append("Clips that belong to no script row changed; they are not updated.")
    if baseline_view.get("markers") != current_view.get("markers"):
        gaps.append("Script markers changed; timeline markers are not updated.")
    return gaps


def choose_rows(
    plans: Sequence[Mapping[str, Any]], choice: Sequence[str] | str | None
) -> list[str]:
    """Turn "all safe rows" or named rows into row IDs. Empty means do nothing.

    Named rows may be given as the row number shown in the plan or as the row
    ID. A row in conflict is included only when named. A refused row can never
    be chosen.
    """
    if choice is None:
        return []
    if isinstance(choice, str):
        if choice != "safe":
            raise UpdatePlanError("choose named rows or all safe rows")
        safe = [
            plan["rowId"]
            for plan in plans
            if plan["refusal"] is None and not plan["conflict"]
        ]
        return _whole_group(plans, safe, named=False)
    by_name: dict[str, Mapping[str, Any]] = {}
    for plan in plans:
        by_name[plan["rowId"]] = plan
        by_name[plan["label"].split("“")[0].strip().removeprefix("Row ")] = plan
    chosen: list[str] = []
    for name in choice:
        found = by_name.get(name.strip().removeprefix("Row ").strip())
        if found is None:
            raise UpdatePlanError(f"row {name!r} is not in the update plan")
        if found["refusal"] is not None:
            raise UpdatePlanError(
                f"{found['label']} cannot be updated: {found['refusal']}"
            )
        if found["rowId"] in chosen:
            raise UpdatePlanError(f"{found['label']} was named twice")
        chosen.append(found["rowId"])
    # The #328 record applies rows in plan order, whatever order they were named.
    order = [plan["rowId"] for plan in plans]
    return _whole_group(plans, sorted(chosen, key=order.index), named=True)


def _whole_group(
    plans: Sequence[Mapping[str, Any]], chosen: list[str], *, named: bool
) -> list[str]:
    """Rows that change the timeline's length go together or not at all."""
    group = [
        plan["rowId"]
        for plan in plans
        if plan.get("group") == ROUTE_RETIME and plan["refusal"] is None
    ]
    if not group or not set(chosen) & set(group):
        return chosen
    missing = [plan for plan in plans if plan["rowId"] in set(group) - set(chosen)]
    if not missing:
        return chosen
    if not named:
        # "All safe rows" never includes a row in conflict, so the group waits.
        return [row for row in chosen if row not in group]
    raise UpdatePlanError(
        "this change alters the timeline's length, so every changed row is "
        "updated together. Also name: " + ", ".join(plan["label"] for plan in missing)
    )


def freeze_plan(
    plans: Sequence[Mapping[str, Any]],
    selected: Sequence[str],
    *,
    source: str,
    target: str,
    baseline: str,
) -> dict[str, Any]:
    """The #328 frozen plan: selected, skipped and blocked rows with one hash."""
    if not selected or not all(
        isinstance(value, str) and value for value in (source, target, baseline)
    ):
        raise UpdatePlanError("a selection and its context are required")
    known = {plan["rowId"]: plan for plan in plans}
    if len(set(selected)) != len(selected) or any(
        row not in known or known[row]["refusal"] is not None for row in selected
    ):
        raise UpdatePlanError("unknown, duplicate or refused selection")
    changes = []
    if any(known[row].get("group") == ROUTE_RETIME for row in selected):
        # A length change is one native batch over every row, so it is one
        # change with one receipt; a row of it is never "not yet reached".
        body = {
            "version": 1,
            "source": source,
            "target": target,
            "baseline": baseline,
            "changes": [
                {
                    "change": {
                        "id": LENGTH_CHANGE,
                        "order": 0,
                        "kind": "structural",
                        "edits": [
                            {"rowId": row, **edit}
                            for row in selected
                            for edit in known[row]["edits"]
                        ],
                        "blocked": None,
                    },
                    "disposition": "selected",
                }
            ],
        }
        return {**body, "hash": outbound_hash(body)}
    for order, plan in enumerate(plans):
        change = {
            "id": plan["rowId"],
            "order": order,
            "kind": "cut" if plan["refusal"] is None else "structural",
            "edits": [dict(edit) for edit in plan["edits"]] or [{"route": "none"}],
            "blocked": plan["refusal"],
        }
        disposition = (
            "blocked"
            if plan["refusal"] is not None
            else "selected"
            if plan["rowId"] in selected
            else "skipped"
        )
        changes.append({"change": change, "disposition": disposition})
    body = {
        "version": 1,
        "source": source,
        "target": target,
        "baseline": baseline,
        "changes": changes,
    }
    return {**body, "hash": outbound_hash(body)}


def start_attempt(plan: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "version": 1,
        "plan": dict(plan),
        "outcomes": [
            {
                "change": item["change"]["id"],
                "status": (
                    "unattempted"
                    if item["disposition"] == "selected"
                    else item["disposition"]
                ),
                "receipt": None,
                "error": None,
            }
            for item in plan["changes"]
        ],
        "baseline": plan["baseline"],
        "current": plan["baseline"],
        "completed": False,
    }


def record_outcome(
    attempt: Mapping[str, Any],
    change_id: str,
    status: str,
    *,
    after: str | None = None,
    error: str | None = None,
) -> dict[str, Any]:
    """Return the attempt with one row's outcome set, keeping #328's invariants.

    ``verified`` needs the target fingerprint read back after the change and
    advances ``current``. The baseline advances only when every selected row is
    verified.
    """
    if status not in {"uncertain", "failed", "verified"}:
        raise UpdatePlanError("invalid outcome status")
    plan = attempt["plan"]
    current = attempt["current"]
    receipt = None
    if status == "verified":
        if not after or after == current:
            raise UpdatePlanError("a verified change needs a new target fingerprint")
        receipt = {
            "plan": plan["hash"],
            "change": change_id,
            "target": plan["target"],
            "before": current,
            "after": after,
        }
        current = after
    outcomes = []
    found = False
    for outcome in attempt["outcomes"]:
        if outcome["change"] == change_id:
            if outcome["status"] not in {"unattempted", "uncertain"}:
                raise UpdatePlanError("this row already has a final outcome")
            found = True
            outcome = {
                "change": change_id,
                "status": status,
                "receipt": receipt,
                "error": error,
            }
        outcomes.append(dict(outcome))
    if not found:
        raise UpdatePlanError("outcome is for a row outside the plan")
    completed = all(
        outcome["status"] in {"verified", "skipped", "blocked"} for outcome in outcomes
    )
    return {
        "version": 1,
        "plan": plan,
        "outcomes": outcomes,
        "baseline": current if completed else plan["baseline"],
        "current": current,
        "completed": completed,
    }


def render_plan(plans: Sequence[Mapping[str, Any]], gaps: Sequence[str]) -> str:
    """The plain-language plan shown before anything is changed."""
    if not plans and not gaps:
        return "The script change does not affect any row of this timeline."
    safe = [p for p in plans if p["refusal"] is None and not p["conflict"]]
    conflict = [p for p in plans if p["refusal"] is None and p["conflict"]]
    refused = [p for p in plans if p["refusal"] is not None]
    together = any(p.get("group") == ROUTE_RETIME for p in safe + conflict)
    lines: list[str] = []
    if together:
        lines.append(
            "The timeline's length changes, so these rows are updated together "
            "or not at all. Later rows move in place and keep their finishing."
        )
    if safe:
        lines.append(
            "Safe to update:"
            if together
            else "Safe to update (the picture is swapped in place):"
        )
        for plan in safe:
            detail = f": {plan['summary']}" if together else ""
            lines.append(f"  {plan['label']}{detail}")
            lines.extend(f"    Note: {warning}" for warning in plan["warnings"])
    if conflict:
        lines.append("In conflict (updated only if you name the row):")
        for plan in conflict:
            lines.append(f"  {plan['label']}: {plan['conflictReason']}")
            lines.extend(f"    Hazard: {hazard}" for hazard in plan["hazards"])
    if refused:
        lines.append("Refused (VERA will not change these):")
        lines.extend(f"  {plan['label']}: {plan['refusal']}" for plan in refused)
    lines.extend(f"Not updated: {gap}" for gap in gaps)
    return "\n".join(lines)


def build_report(
    plans: Sequence[Mapping[str, Any]],
    gaps: Sequence[str],
    attempt: Mapping[str, Any] | None,
    *,
    archive_name: str | None,
    kept: Sequence[str],
    not_checked: Sequence[str],
    status: str,
) -> dict[str, Any]:
    """What happened, row by row. ``status`` is unchanged, updated or uncertain."""
    outcomes = (
        {outcome["change"]: outcome["status"] for outcome in attempt["outcomes"]}
        if attempt is not None
        else {}
    )
    updated, out_of_sync, refused, uncertain = [], [], [], []
    for plan in plans:
        entry = {"rowId": plan["rowId"], "label": plan["label"]}
        outcome = outcomes.get(plan["rowId"])
        if outcome is None and plan["refusal"] is None:
            outcome = outcomes.get(LENGTH_CHANGE)
        if plan["refusal"] is not None:
            refused.append({**entry, "reason": plan["refusal"]})
        elif outcome == "verified" and status == "updated":
            updated.append(entry)
        elif outcome in {"uncertain", "failed", "verified"}:
            uncertain.append(entry)
        else:
            reason = (
                "Chosen, but the update stopped before reaching it."
                if outcome == "unattempted"
                else "In conflict and not named."
                if plan["conflict"]
                else "Not chosen for this update."
            )
            out_of_sync.append({**entry, "reason": reason})
    return {
        "schemaVersion": "vera-timeline-update-report/v1",
        "status": status,
        "archiveTimeline": archive_name,
        "rowsUpdated": updated,
        "rowsOutOfSync": out_of_sync,
        "rowsRefused": refused,
        "rowsUncertain": uncertain,
        "notUpdated": list(gaps),
        "handWorkKept": list(kept),
        "handWorkNotChecked": list(not_checked),
        "baselineComplete": status == "updated"
        and not out_of_sync
        and not refused
        and not gaps,
    }


def render_report(report: Mapping[str, Any]) -> str:
    lines: list[str] = []
    if report["status"] == "unchanged":
        lines.append("Nothing was changed in Resolve.")
    elif report["status"] == "uncertain":
        lines.append(
            "STOPPED: a change to Resolve could not be confirmed. Do not run "
            "the update again. The archive copy is the way back."
        )
    if report["archiveTimeline"]:
        lines.append(f"Archive copy kept as: {report['archiveTimeline']}")
    for title, key in (
        ("Updated", "rowsUpdated"),
        ("Could not be confirmed", "rowsUncertain"),
        ("Left out of sync with the script", "rowsOutOfSync"),
        ("Refused", "rowsRefused"),
    ):
        rows = report[key]
        if rows:
            lines.append(f"{title}:")
            for row in rows:
                reason = f": {row['reason']}" if "reason" in row else ""
                lines.append(f"  {row['label']}{reason}")
    lines.extend(f"Not updated: {gap}" for gap in report["notUpdated"])
    if report["handWorkKept"]:
        lines.append("Checked unchanged on every clip VERA did not touch:")
        lines.extend(f"  {item}" for item in report["handWorkKept"])
    if report["handWorkNotChecked"]:
        lines.append("VERA cannot read these, so they were not checked:")
        lines.extend(f"  {item}" for item in report["handWorkNotChecked"])
    if report["status"] == "updated":
        lines.append(
            "Use this update's folder as the baseline next time."
            if report["baselineComplete"]
            else "Some rows are still out of sync with the script. Use this "
            "update's folder as the baseline next time; it remembers them."
        )
    return "\n".join(lines)
