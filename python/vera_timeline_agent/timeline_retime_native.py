"""Change rows' lengths in place on a Resolve that can move and trim clips.

Every call sequence here was measured on Studio 21.2.0 build 6 in #104's
probes (``docs/investigations/issue-104``): later clips move with
``Timeline.MoveItems`` and keep their IDs and finishing, a clip is resized at
its tail with ``SetRightOffset``, a picture is swapped through the take
selector, and a narration clip that becomes a different file is placed anew
with its settings copied across. Nothing is retried.
"""

from __future__ import annotations

import itertools
from collections.abc import Mapping, Sequence
from typing import Any

from .timeline_update_native import (
    NativeUpdateError,
    _hand_markers,
    _require,
    _same_properties,
    live_items,
    restamp,
    swap_picture,
)
from .workflow_v2 import _MARKER_COLORS, _marker_stamp

RETIME_VERSION = [21, 2, 0, 6]


class RetimePrecheckError(ValueError):
    """The timeline is not in a state the change can be applied to. Nothing changed."""


def _transitions(timeline: Any) -> list[tuple[int, Any]]:
    return [
        (index, item)
        for uid, (kind, index, item) in live_items(timeline).items()
        if kind == "video" and item.GetType() == "transition"
    ]


def precheck(
    timeline: Any,
    ops: Sequence[Mapping[str, Any]],
    editor: Mapping[str, int],
    transition_edits: Sequence[Mapping[str, Any]],
    new_markers: Sequence[Mapping[str, Any]] = (),
    old_markers: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Read-only checks before the first write. Returns what to expect after.

    ``expect`` maps each existing item to how it should change: ``delta``
    frames later, a new ``duration``, a picture ``swap``, a new VERA marker
    (``restamp``) or removal (``gone``). ``bonds`` are pairs of clips that
    share a transition and must travel in one move. ``end`` is the last frame
    any clip will reach.
    """
    items = live_items(timeline)
    by_uid = {op["resolveItemId"]: op for op in ops}
    expect: dict[str, dict[str, Any]] = {}
    for uid, op in by_uid.items():
        found = items.get(uid)
        if found is None or found[2].GetType() == "transition":
            raise RetimePrecheckError("a clip the update needs is no longer there")
        item = found[2]
        if (
            item.GetStart(False) != op["previousStartFrame"]
            or item.GetDuration(False) != op["previousDurationFrames"]
        ):
            raise RetimePrecheckError("a clip is not where the baseline says it is")
        grow = op["durationFrames"] - op["previousDurationFrames"]
        if grow > 0 and not op["swapPicture"] and not op["replaceAudio"]:
            handle = item.GetRightOffset()
            if not isinstance(handle, (int, float)) or handle < grow:
                raise RetimePrecheckError(
                    "a clip's source is too short to extend it as the script asks"
                )
        expect[uid] = {
            "delta": op["startFrame"] - op["previousStartFrame"],
            "duration": op["durationFrames"],
            "swap": op["swapPicture"],
            "restamp": True,
            "gone": op["replaceAudio"],
        }
    for uid, delta in editor.items():
        if uid not in items:
            raise RetimePrecheckError("a clip you added is no longer there")
        expect[uid] = {"delta": delta}

    # Where every clip ends up. Nothing may land on top of anything else.
    final: dict[tuple[str, int], list[tuple[int, int]]] = {}
    end = 0
    for uid, (kind, index, item) in items.items():
        if kind == "video" and item.GetType() == "transition":
            continue
        change = expect.get(uid, {})
        start = item.GetStart(False) + change.get("delta", 0)
        stop = start + change.get("duration", item.GetDuration(False))
        final.setdefault((kind, index), []).append((start, stop))
        end = max(end, stop)
    for spans in final.values():
        spans.sort()
        for (_, first_stop), (second_start, _) in itertools.pairwise(spans):
            if second_start < first_stop:
                raise RetimePrecheckError(
                    "after the change two clips would sit on top of each "
                    f"other at frame {second_start}"
                )

    def edge(uid: str, which: str) -> tuple[int, bool]:
        """How far a clip's start or end travels, and whether that edge is safe.

        The end is safe only on a clip that just moves. The start is also
        safe on a clip that is resized at its tail.
        """
        delta = expect.get(uid, {}).get("delta", 0)
        op = by_uid.get(uid)
        if op is None:
            return delta, True
        grow = op["durationFrames"] - op["previousDurationFrames"]
        unreplaced = not op["swapPicture"] and not op["replaceAudio"]
        if which == "end":
            return delta + grow, grow == 0 and unreplaced
        return delta, unreplaced

    planned = {
        (e["previousStartFrame"], e["previousEndFrame"]): e for e in transition_edits
    }
    seen_planned: set[tuple[int, int]] = set()
    bonds: list[tuple[str, str]] = []
    for track, transition in _transitions(timeline):
        start, stop = transition.GetStart(False), transition.GetEnd(False)
        if (start, stop) in planned:
            # Resolve may drop this one; the script's plan puts it back if so.
            edit = planned[(start, stop)]
            seen_planned.add((start, stop))
            expect[transition.GetUniqueId()] = {
                "maybe_gone": True,
                "delta": edit["startFrame"] - start,
            }
            continue
        left = right = None
        for uid, (kind, index, item) in items.items():
            if kind != "video" or index != track or item.GetType() == "transition":
                continue
            clip_start = item.GetStart(False)
            clip_stop = clip_start + item.GetDuration(False)
            if start <= clip_stop <= stop and clip_start < start:
                left = uid
            if start <= clip_start <= stop and clip_stop > stop:
                right = uid
        if left is None and right is None:
            raise RetimePrecheckError(
                f"a transition at frame {start} is not on a cut VERA can find"
            )
        deltas = set()
        safe = True
        for uid, which in ((left, "end"), (right, "start")):
            if uid is not None:
                delta, edge_safe = edge(uid, which)
                deltas.add(delta)
                safe &= edge_safe
        if len(deltas) > 1 or (not safe and deltas != {0}):
            raise RetimePrecheckError(
                f"a transition you made by hand at frame {start} sits on a cut "
                "that has to open, and Resolve would drop it"
            )
        if deltas != {0}:
            expect[transition.GetUniqueId()] = {"delta": deltas.pop()}
            if left is not None and right is not None:
                bonds.append((left, right))
    if seen_planned != set(planned):
        raise RetimePrecheckError(
            "a transition the script wrote is no longer as VERA built it"
        )

    # A script marker must not land on a ruler marker he placed himself.
    live_markers = timeline.GetMarkers()
    if not isinstance(live_markers, Mapping):
        raise RetimePrecheckError("timeline markers are unreadable")
    ours = {marker["frame"]: _marker_stamp(marker) for marker in old_markers}
    for marker in new_markers:
        frame = marker["frame"]
        present = live_markers.get(frame) or live_markers.get(float(frame))
        if isinstance(present, Mapping) and present.get("customData") != ours.get(
            frame
        ):
            raise RetimePrecheckError(
                f"a script marker would land on your own marker at frame {frame}"
            )
    return {"expect": expect, "bonds": bonds, "end": end}


def _runs(
    moving: Sequence[tuple[str, int, int, Any]],
    slots: Mapping[str, tuple[str, int]],
    bonds: Sequence[tuple[str, str]],
) -> list[tuple[int, list[Any], int]]:
    """Group clips that must travel in one call.

    Neighbours on one track that travel equally go together, as do two clips
    that share a transition; a clip on another track never splits them.
    """
    parent = {uid: uid for uid, _, _, _ in moving}

    def root(uid: str) -> str:
        while parent[uid] != uid:
            parent[uid] = parent[parent[uid]]
            uid = parent[uid]
        return uid

    by_track: dict[tuple[str, int], list[tuple[int, int, str]]] = {}
    for uid, start, delta, _ in moving:
        by_track.setdefault(slots[uid], []).append((start, delta, uid))
    for members in by_track.values():
        members.sort()
        for (_, first, one), (_, second, two) in itertools.pairwise(members):
            if first == second:
                parent[root(one)] = root(two)
    for one, two in bonds:
        if one in parent and two in parent:
            parent[root(one)] = root(two)
    groups: dict[str, tuple[int, list[Any], int]] = {}
    for uid, start, delta, item in sorted(moving, key=lambda entry: entry[1]):
        key = root(uid)
        if key not in groups:
            groups[key] = (delta, [], start)
        groups[key][1].append(item)
    return sorted(groups.values(), key=lambda run: run[2])


def apply(
    project: Any,
    timeline: Any,
    ops: Sequence[Mapping[str, Any]],
    editor: Mapping[str, int],
    transition_edits: Sequence[Mapping[str, Any]],
    *,
    media: Mapping[str, Any],
    stamps: Mapping[str, str],
    uid_by_event: Mapping[str, str],
    old_markers: Sequence[Mapping[str, Any]],
    new_markers: Sequence[Mapping[str, Any]],
    bonds: Sequence[tuple[str, str]] = (),
) -> dict[str, Any]:
    """Carry out a prechecked retime. Returns the new clips it had to create."""
    items = {uid: item for uid, (_, _, item) in live_items(timeline).items()}
    slots = {
        uid: (kind, index) for uid, (kind, index, _) in live_items(timeline).items()
    }
    tracks = {uid: index for uid, (_, index) in slots.items()}

    def resize(item: Any, change: int, target: int) -> None:
        handle = item.GetRightOffset()
        _require(isinstance(handle, (int, float)), "a clip's handle is unreadable")
        _require(
            item.SetRightOffset(handle - change) and item.GetDuration(False) == target,
            "Resolve did not resize a clip as asked",
        )

    # 1. Shorten first, so that nothing ever has to overlap.
    for op in ops:
        item = items[op["resolveItemId"]]
        short = min(op["durationFrames"], op["previousDurationFrames"])
        if short < op["previousDurationFrames"]:
            resize(item, short - op["previousDurationFrames"], short)
        if op["swapPicture"]:
            swap_picture(item, media[op["sourceId"]], op["sourceStartFrame"], short)

    # 2. Move. Clips going later are taken from the end of the timeline
    # backwards, clips going earlier from the start forwards.
    moving = [
        (
            op["resolveItemId"],
            op["previousStartFrame"],
            op["startFrame"] - op["previousStartFrame"],
            items[op["resolveItemId"]],
        )
        for op in ops
        if op["startFrame"] != op["previousStartFrame"]
    ]
    moving += [
        (uid, items[uid].GetStart(False), delta, items[uid])
        for uid, delta in editor.items()
    ]
    runs = _runs(moving, slots, bonds)
    ordered = [run for run in reversed(runs) if run[0] > 0]
    ordered += [run for run in runs if run[0] < 0]
    for delta, members, start in ordered:
        before = [member.GetStart(False) for member in members]
        _require(
            timeline.MoveItems(members, {"startFrame": float(start + delta)}, False),
            "Resolve did not move the later clips",
        )
        _require(
            [member.GetStart(False) for member in members]
            == [value + delta for value in before],
            "the later clips did not land where the script puts them",
        )

    # 3. Lengthen into the room the moves made.
    for op in ops:
        grow = op["durationFrames"] - op["previousDurationFrames"]
        if grow > 0 and not op["replaceAudio"]:
            resize(items[op["resolveItemId"]], grow, op["durationFrames"])

    # 4. A narration clip that is a different recording is placed anew, with
    # the old clip's settings copied onto it.
    created: dict[str, str] = {}
    pool = project.GetMediaPool()
    for op in ops:
        if not op["replaceAudio"]:
            continue
        old = items[op["resolveItemId"]]
        _require(timeline.AddTrack("audio"), "could not add a spare audio track")
        spare = timeline.GetTrackCount("audio")
        placed = pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": media[op["sourceId"]],
                    "mediaType": 2,
                    "trackIndex": spare,
                    "recordFrame": op["startFrame"],
                    "startFrame": op["sourceStartFrame"],
                    "endFrame": op["sourceStartFrame"] + op["durationFrames"],
                }
            ]
        )
        _require(
            isinstance(placed, (list, tuple)) and len(placed) == 1,
            "Resolve did not place the new narration",
        )
        new = placed[0]
        _require(
            old.CopyAttributes(
                [new], {"allAudioAttributes": True, "allClipAttributes": True}
            )
            and new.SetFades(old.GetFades()),
            "could not carry the old narration's settings over",
        )
        colour = old.GetClipColor()
        if new.GetClipColor() != colour:
            _require(
                new.SetClipColor(colour) if colour else new.ClearClipColor(),
                "could not restore the narration's clip colour",
            )
        _require(
            timeline.DeleteClips([old], False), "could not remove the old narration"
        )
        _require(
            new.SetPosition(
                {
                    "trackIndex": tracks[op["resolveItemId"]],
                    "startFrame": float(op["startFrame"]),
                }
            )
            and timeline.DeleteTrack("audio", spare),
            "could not put the new narration in place",
        )
        _require(
            new.GetStart(False) == op["startFrame"]
            and new.GetDuration(False) == op["durationFrames"],
            "the new narration is not where the script puts it",
        )
        created[op["resolveItemId"]] = new.GetUniqueId()
        items[op["resolveItemId"]] = new

    # 5. Put back the script's own transitions that Resolve dropped.
    restored: list[str] = []
    for edit in transition_edits:
        if any(
            item.GetStart(False) == edit["startFrame"]
            and item.GetEnd(False) == edit["endFrame"]
            for _, item in _transitions(timeline)
        ):
            continue  # It travelled with its cut after all.
        outgoing = items[uid_by_event[edit["outgoingEventId"]]]
        added = outgoing.AddTransition(
            {
                "type": edit["effectName"],
                "category": edit["effectCategory"],
                "position": "end",
                "alignment": edit["alignment"],
                "duration": edit["durationFrames"],
            }
        )
        _require(
            added is not None
            and added is not False
            and added.GetStart(False) == edit["startFrame"]
            and added.GetEnd(False) == edit["endFrame"],
            "the script's transition did not go back as written",
        )
        restored.append(added.GetUniqueId())

    # 6. Every clip that changed gets the marker of its new script event.
    for op in ops:
        restamp(items[op["resolveItemId"]], op["eventId"], stamps[op["eventId"]])

    # 7. The script's own timeline markers follow their rows.
    live = timeline.GetMarkers()
    _require(isinstance(live, Mapping), "timeline markers are unreadable")
    for marker in old_markers:
        current = live.get(marker["frame"]) or live.get(float(marker["frame"]))
        if isinstance(current, Mapping) and current.get("customData") == _marker_stamp(
            marker
        ):
            _require(
                timeline.DeleteMarkerAtFrame(marker["frame"]),
                "could not remove a script marker",
            )
    for marker in new_markers:
        _require(
            timeline.AddMarker(
                marker["frame"],
                _MARKER_COLORS[marker["color"]],
                marker["name"],
                marker["note"],
                1,
                _marker_stamp(marker),
            ),
            "could not add a script marker",
        )
    return {"created": created, "transitions": restored}


def _vera_free(markers: Any) -> Any:
    return _hand_markers(markers)


def check(
    before: Mapping[str, Any],
    after: Mapping[str, Any],
    expect: Mapping[str, Mapping[str, Any]],
    *,
    created: Mapping[str, str],
    transitions: Sequence[str],
    bounds: Sequence[int],
    required_transitions: Sequence[tuple[int, int]] = (),
) -> list[str]:
    """Differences from the expected result. Empty means hand work was kept."""
    problems: list[str] = []
    spans = {
        (row["start"], row["start"] + row["duration"])
        for row in after["items"]
        if row["type"] == "transition"
    }
    if any(span not in spans for span in required_transitions):
        problems.append("a transition the script writes is missing")
    if list(after["bounds"]) != list(bounds):
        problems.append("the timeline is not the length the script gives it")
    if _vera_free(before["markers"]) != _vera_free(after["markers"]):
        problems.append("your timeline markers changed")
    old = {row["id"]: row for row in before["items"]}
    new = {row["id"]: row for row in after["items"]}
    allowed = set(created.values()) | set(transitions)
    if set(new) - set(old) - allowed:
        problems.append("clips or transitions appeared that the update did not make")
    for uid, row in old.items():
        change = expect.get(uid, {})
        where = f"{row['kind']} {row['track']} at {row['start']}"
        now = new.get(created.get(uid, uid))
        if change.get("maybe_gone") and now is None:
            continue  # Resolve dropped it; the script's plan put one back.
        if change.get("gone") and uid not in created:
            if uid in new:
                problems.append(f"transition on {where} should have been replaced")
            continue
        if now is None:
            problems.append(f"clip on {where} is gone")
            continue
        skip = {"id", "start", "duration", "sourceEnd"}
        if change.get("swap") or uid in created:
            skip |= {"name", "mediaId", "sourceStart", "takes"}
        if change.get("restamp"):
            skip.add("markers")
        changed = sorted(
            key
            for key in row
            if key not in skip
            and (
                not _same_properties(row[key], now.get(key))
                if key == "properties"
                else row[key] != now.get(key)
            )
        )
        if now["start"] != row["start"] + change.get("delta", 0):
            changed.append("position")
        if now["duration"] != change.get("duration", row["duration"]):
            changed.append("length")
        if change.get("restamp") and _hand_markers(row["markers"]) != _hand_markers(
            now.get("markers")
        ):
            changed.append("your markers")
        if changed:
            problems.append(f"clip on {where} changed: {', '.join(changed)}")
    return problems


__all__ = [
    "RETIME_VERSION",
    "NativeUpdateError",
    "RetimePrecheckError",
    "apply",
    "check",
    "precheck",
]
