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
PICTURE_KINDS = frozenset({"primary_visual", "overlay_visual"})

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
        if row_id in (plan["fromRowId"], plan["toRowId"])
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
) -> list[dict[str, Any]]:
    """One entry per row the script change affects, in script order.

    ``comparison`` is the #102 three-way result and ``observation`` the #101
    read-back it was made from. ``takes`` is the take-selector count of each
    managed clip, read from Resolve; ``None`` means it could not be read.
    """
    saved_items = {
        item["eventId"]: item for row in saved_map["rows"] for item in row["items"]
    }
    observed = {
        item["resolveItemId"]: item
        for row in observation["rows"]
        for item in row["items"]
    }
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
        if row["scriptChange"] == "added":
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
        plans.append(
            {
                "rowId": row_id,
                "label": new_labels.get(row_id) or old_labels.get(row_id) or row_id,
                "state": row["state"],
                "conflict": conflict,
                "conflictReason": row["reason"] if conflict else None,
                "hazards": list(row["hazards"]) if conflict else [],
                "refusal": refusal,
                "edits": edits,
                "warnings": warnings,
            }
        )
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
        return [
            plan["rowId"]
            for plan in plans
            if plan["refusal"] is None and not plan["conflict"]
        ]
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
    return chosen


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
    lines: list[str] = []
    if safe:
        lines.append("Safe to update (the picture is swapped in place):")
        for plan in safe:
            lines.append(f"  {plan['label']}")
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
        if plan["refusal"] is not None:
            refused.append({**entry, "reason": plan["refusal"]})
        elif outcome == "verified" and status == "updated":
            updated.append(entry)
        elif outcome in {"uncertain", "failed", "verified"}:
            uncertain.append(entry)
        else:
            reason = (
                "In conflict and not named."
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
            "This update's folder is the new baseline for the whole timeline."
            if report["baselineComplete"]
            else "Some rows are still out of sync, so the earlier baseline "
            "stays in force for them. Only the updated rows have a new baseline."
        )
    return "\n".join(lines)
