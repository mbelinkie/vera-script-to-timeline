"""Narrow #88 picture-transition contract and guarded direct Studio delivery.

The manifest is an *intent*, never authority to choose a different installed
effect. Portable OTIO remains cut-only; this path is exclusively post-placement
native AddTransition on the one verified disposable timeline.
"""

from __future__ import annotations

from collections.abc import Mapping
from fractions import Fraction
from typing import Any, TypeGuard, cast


class TransitionRefusal(ValueError):
    """No native write is permitted for this transition declaration."""


QUALIFIED_EFFECT: dict[str, str] = {
    "category": "simple",
    "name": "Cross Dissolve",
    "sourceIdentity": "resolve/native/simple/Cross Dissolve",
    "fingerprint": "issue-292/studio-21.1.1.10/native-simple-cross-dissolve",
    "resolveBuild": "21.1.1.10",
    "route": "direct_add_transition",
}


def _need(ok: object, reason: str) -> None:
    if not ok:
        raise TransitionRefusal(reason)


def _frame(value: object) -> TypeGuard[int]:
    return type(value) is int and 0 <= value <= 2**53 - 1


def _fraction(value: object) -> Fraction:
    _need(isinstance(value, Mapping), "transition duration or rate is unknown")
    assert isinstance(value, Mapping)
    n, d = value.get("numerator"), value.get("denominator")
    _need(_frame(n) and _frame(d) and n > 0 and d > 0, "transition rational is invalid")
    assert isinstance(n, int) and isinstance(d, int)
    return Fraction(n, d)


def _authored_duration(settings: Mapping[str, Any], rate: Mapping[str, Any]) -> int:
    frames = settings.get("durationFrames")
    seconds = settings.get("durationSeconds")
    _need(
        (frames is None) != (seconds is None), "transition needs exactly one duration"
    )
    if frames is None:
        exact = _fraction(seconds) * _fraction(rate)
        _need(exact.denominator == 1, "transition seconds are not whole frames")
        frames = exact.numerator
    _need(
        _frame(frames) and frames > 0 and frames % 2 == 0,
        "transition duration must be positive even frames",
    )
    return frames


def _required_sides(frames: int, alignment: str) -> tuple[int, int]:
    _need(
        alignment in {"left", "center", "right"}, "transition alignment is unsupported"
    )
    left = (
        frames if alignment == "left" else frames // 2 if alignment == "center" else 0
    )
    return left, frames - left


def _events(manifest: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    entries = manifest.get("events", [])
    _need(isinstance(entries, list), "transition event inventory is missing")
    result: dict[str, Mapping[str, Any]] = {}
    for item in entries:
        _need(
            isinstance(item, Mapping) and isinstance(item.get("eventId"), str),
            "transition event identity is malformed",
        )
        assert isinstance(item, Mapping)
        result[cast(str, item["eventId"])] = item
    _need(len(result) == len(entries), "transition event inventory is ambiguous")
    return result


def validate_signed_transitions(
    document: Mapping[str, Any],
    dependencies: Mapping[str, Any],
    manifest: Mapping[str, Any],
    report: Mapping[str, Any] | None = None,
) -> tuple[Mapping[str, Any], ...]:
    """Independently bind authored adjacent rows to exact signed video events.

    Even if an attacker recomputes the manifest/report hashes, a fabricated,
    dropped or changed transition cannot become native write authority.
    """
    raw = manifest.get("transitions", [])
    _need(isinstance(raw, list), "transition plan is not an array")
    all_rows = document.get("activeDraft", {}).get("blocks", [])
    _need(isinstance(all_rows, list), "authored transition rows are unavailable")
    rows = [
        row
        for row in all_rows
        if isinstance(row, Mapping)
        and row.get("state") == "active"
        and row.get("type") in {"visual_only", "narration"}
    ]
    written = document.get("rowTransitions", [])
    _need(isinstance(written, list), "authored transitions are unavailable")
    authored = [
        pair
        for pair in written
        if isinstance(pair, Mapping)
        and pair.get("state") == "active"
        and pair.get("effect") != "cut"
    ]
    _need(
        len(authored) == len(raw),
        "signed transition plan differs from authored active row pairs",
    )
    by_id = {pair.get("id"): pair for pair in authored}
    _need(len(by_id) == len(authored), "authored transition identities are ambiguous")
    _events(manifest)
    tracks = {track.get("id"): track for track in manifest.get("tracks", [])}
    root_track = manifest.get("roles", {}).get("primaryRootTrackId")
    _need(
        not raw or (root_track in tracks and tracks[root_track].get("kind") == "video"),
        "transition root track is missing",
    )
    bindings = {
        b.get("requirementKey"): b for b in dependencies.get("preparedMedia", [])
    }
    by_event = {
        item.get("eventId"): item
        for item in manifest.get("events", [])
        if isinstance(item, Mapping)
    }
    occurrences = {
        item.get("payloadId"): item
        for item in dependencies.get("occurrenceResolutions", [])
    }
    seen_ids: set[str] = set()
    seen_edges: set[tuple[str, int]] = set()
    for plan in raw:
        _need(isinstance(plan, Mapping), "transition plan entry is malformed")
        ident = plan.get("id")
        _need(
            isinstance(ident, str) and ident in by_id and ident not in seen_ids,
            "transition plan identity was forged or repeated",
        )
        seen_ids.add(ident)
        pair = by_id[ident]
        _need(
            plan.get("fromRowId") == pair.get("fromRowId")
            and plan.get("toRowId") == pair.get("toRowId")
            and pair.get("effect") == "Cross Dissolve",
            "transition row pair or effect differs from authoring",
        )
        _need(
            plan.get("effectIdentity") == QUALIFIED_EFFECT,
            "transition category, fingerprint or Studio build is unqualified",
        )
        settings = pair.get("settings")
        _need(isinstance(settings, Mapping), "authored transition settings are missing")
        assert isinstance(settings, Mapping)
        duration = _authored_duration(settings, manifest["timeline"]["frameRate"])
        alignment = settings.get("alignment", "center")
        left, right = _required_sides(duration, alignment)
        from_row, to_row = pair["fromRowId"], pair["toRowId"]
        candidates = [
            index
            for index, row in enumerate(rows[:-1])
            if row.get("id") == from_row and rows[index + 1].get("id") == to_row
        ]
        _need(len(candidates) == 1, "transition authored rows are no longer adjacent")
        outgoing = by_event.get(plan.get("outgoingEventId"))
        incoming = by_event.get(plan.get("incomingEventId"))
        _need(
            isinstance(outgoing, Mapping)
            and isinstance(incoming, Mapping)
            and outgoing is not incoming,
            "transition event identities are unknown",
        )
        assert isinstance(outgoing, Mapping) and isinstance(incoming, Mapping)
        boundary = plan.get("boundaryFrame")
        _need(
            _frame(boundary)
            and boundary >= left
            and _frame(plan.get("startFrame"))
            and _frame(plan.get("endFrame"))
            and plan["startFrame"] == boundary - left
            and plan["endFrame"] == boundary + right
            and plan.get("requestedDurationFrames") == duration
            and plan.get("alignment") == alignment,
            "signed transition duration or boundary span differs from authoring",
        )
        _need(
            (root_track, boundary) not in seen_edges,
            "transition boundary is claimed more than once",
        )
        seen_edges.add((root_track, boundary))
        for event, row_id, end_side in (
            (outgoing, from_row, True),
            (incoming, to_row, False),
        ):
            record = event.get("recordRange", {})
            provenance = event.get("provenance", {})
            _need(
                event.get("kind") == "primary_visual"
                and event.get("trackId") == root_track
                and event.get("trackRole") == "primary_root"
                and provenance.get("blockId") == row_id
                and (record.get("endFrame") if end_side else record.get("startFrame"))
                == boundary
                and isinstance(event.get("sourceRange"), Mapping),
                "signed transition does not identify exact adjacent root video events",
            )
        _need(
            plan.get("trackId") == root_track
            and outgoing["recordRange"]["endFrame"]
            == incoming["recordRange"]["startFrame"]
            and outgoing["recordRange"]["endFrame"] == boundary,
            "transition track or cut geometry changed",
        )
        disposition = plan.get("disposition")
        _need(
            disposition in {"apply", "cut_insufficient_handles"},
            "transition disposition is unsupported",
        )
        if disposition == "apply":
            _need("reason" not in plan, "applicable transition has a cut reason")
            for event, needed, side in (
                (outgoing, right, "postHandle"),
                (incoming, left, "preHandle"),
            ):
                source = event["sourceRange"]
                source_id = event["provenance"].get("sourceId")
                manifest_source = next(
                    (
                        s
                        for s in manifest.get("sources", [])
                        if s.get("id") == source_id
                    ),
                    None,
                )
                _need(
                    isinstance(manifest_source, Mapping),
                    "transition source is not manifest-bound",
                )
                assert isinstance(manifest_source, Mapping)
                key = manifest_source.get("preparationRequirementKey")
                binding = bindings.get(key)
                _need(
                    isinstance(binding, Mapping),
                    "transition source has no verified preparation",
                )
                assert isinstance(binding, Mapping)
                selected = (
                    source.get("startFrame")
                    if side == "preHandle"
                    else source.get("endFrame")
                )
                count = binding.get("verification", {}).get("decodedFrameCount")
                _need(
                    _frame(selected)
                    and _frame(count)
                    and _frame(source.get("startFrame"))
                    and _frame(source.get("endFrame"))
                    and source["endFrame"] <= count
                    and (
                        selected >= needed
                        if side == "preHandle"
                        else count - selected >= needed
                    ),
                    "transition delivered source handles are insufficient",
                )
                need_seconds = Fraction(needed, 1) / _fraction(
                    manifest["timeline"]["frameRate"]
                )
                _need(
                    _fraction(binding.get("requestedRange", {}).get(side))
                    >= need_seconds
                    if needed
                    else True,
                    "transition preparation did not request full source handles",
                )
        else:
            _need(
                isinstance(plan.get("reason"), str)
                and str(ident) in plan["reason"]
                and str(from_row) in plan["reason"]
                and str(to_row) in plan["reason"],
                "named cut lacks exact authored pair warning",
            )
            # A cut is the *known-short* fallback, not a way to hide a valid
            # authored dissolve or a source whose available handles are unknown.
            shortage: list[bool] = []
            for event, needed, outgoing_side in (
                (outgoing, right, True),
                (incoming, left, False),
            ):
                provenance = event["provenance"]
                descriptor = occurrences.get(provenance.get("payloadId"))
                _need(
                    isinstance(descriptor, Mapping),
                    "named cut has no known original source extent",
                )
                assert isinstance(descriptor, Mapping)
                logical = descriptor.get("logicalSourceBounds")
                _need(
                    isinstance(logical, Mapping),
                    "named cut source bounds are unknown",
                )
                assert isinstance(logical, Mapping)
                in_frame = descriptor.get("occurrenceSourceInFrame")
                low, high = logical.get("startFrame"), logical.get("endFrame")
                _need(
                    _frame(in_frame) and _frame(low) and _frame(high),
                    "named cut source frames are unknown",
                )
                assert isinstance(in_frame, int)
                assert isinstance(low, int) and isinstance(high, int)
                rate = _fraction(logical.get("frameRate"))
                timeline_rate = _fraction(manifest["timeline"]["frameRate"])
                extra = (Fraction(needed, 1) * rate / timeline_rate).__ceil__()
                record = event["recordRange"]
                source_duration = (
                    Fraction(record["endFrame"] - record["startFrame"], 1)
                    * rate
                    / timeline_rate
                ).__ceil__()
                shortage.append(
                    in_frame + source_duration + extra > high
                    if outgoing_side
                    else in_frame - extra < low
                )
            record_too_short = any(
                event["recordRange"]["endFrame"] - event["recordRange"]["startFrame"]
                < duration
                for event in (outgoing, incoming)
            )
            _need(
                any(shortage) or record_too_short,
                "named cut has sufficient source handles",
            )
            if report is not None:
                warnings = [
                    d
                    for d in report.get("diagnostics", [])
                    if d.get("code") == "ROW_TRANSITION_CUT_SHORT_HANDLES"
                    and d.get("entity", {}).get("id") == ident
                    and d.get("severity") == "warning"
                    and d.get("message") == plan["reason"]
                ]
                _need(
                    len(warnings) == 1,
                    "named cut lacks its typed compiler report warning",
                )
    _need(
        seen_ids == set(by_id), "signed transition plan omitted an authored transition"
    )
    if report is not None:
        warnings = [
            d
            for d in report.get("diagnostics", [])
            if d.get("code") == "ROW_TRANSITION_CUT_SHORT_HANDLES"
        ]
        _need(
            len(warnings)
            == sum(p["disposition"] == "cut_insufficient_handles" for p in raw),
            "named cut warning inventory does not match signed plans",
        )
    return tuple(raw)


def observe_native_transition(item: Any, plan: Mapping[str, Any]) -> bool:
    """Only real getters, not AddTransition's boolean, prove exact geometry."""
    return (
        item is not None
        and item.GetType() == "transition"
        and item.GetName() == QUALIFIED_EFFECT["name"]
        and item.GetFusionCompCount() == 0
        and item.GetStart() == plan["startFrame"]
        and item.GetEnd() == plan["endFrame"]
        and item.GetDuration() == plan["requestedDurationFrames"]
        and isinstance(item.GetUniqueId(), str)
        and bool(item.GetUniqueId())
    )


def apply_guarded_transition(plan: Mapping[str, Any], locate_boundary: Any) -> str:
    """Precheck live UID/stamp/adjacency/handles; single write; no retry/rollback."""
    _need(plan["disposition"] == "apply", "only exact qualified plans may be applied")
    before = locate_boundary(plan)
    _need(before["transition"] is None, "transition already occupies the boundary")
    out, inc = before["outgoing"], before["incoming"]
    _need(
        before["outgoingId"] == plan["outgoingEventId"]
        and before["incomingId"] == plan["incomingEventId"],
        "live event marker identity changed",
    )
    _need(
        out.GetEnd(False) == inc.GetStart(False) == plan["boundaryFrame"],
        "native boundary is no longer adjacent",
    )
    left = plan["boundaryFrame"] - plan["startFrame"]
    right = plan["endFrame"] - plan["boundaryFrame"]
    _need(
        out.GetRightOffset() >= right
        and inc.GetLeftOffset() >= left
        and min(out.GetDuration(False), inc.GetDuration(False))
        >= plan["requestedDurationFrames"],
        "live transition handles or clip duration are insufficient",
    )
    # No probes or mutation after this point may be retried automatically.
    result = out.AddTransition(
        {
            "type": QUALIFIED_EFFECT["name"],
            "category": QUALIFIED_EFFECT["category"],
            "position": "end",
            "alignment": plan["alignment"],
            "duration": plan["requestedDurationFrames"],
        }
    )
    _need(
        result is not None and result is not False,
        "AddTransition was uncertain; no retry",
    )
    after = locate_boundary(plan)
    _need(
        after["outgoingId"] == before["outgoingId"]
        and after["incomingId"] == before["incomingId"],
        "native boundary changed after transition write",
    )
    actual = after["transition"]
    _need(
        observe_native_transition(actual, plan),
        "native transition did not retain exact geometry or identity",
    )
    return str(actual.GetUniqueId())
