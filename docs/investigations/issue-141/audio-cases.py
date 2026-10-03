"""Bounded injected audio/timeline observations for Issue 141."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

PINNED_CAPTURE = "capture-20260930T223313.312609Z-saved.json"
PINNED_SHA256 = "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
PINNED_BUILD = [21, 1, 0, 14, ""]
TIMELINE_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
RESIDUAL_ID = "f4e9f649-894a-42f2-9f54-a8321ae7c163"
RETIME_VIDEO_ID = "e64549d6-eee5-49f2-985b-475c31ccb07d"
RETIME_AUDIO_ID = "7808b1fb-3423-4dac-a07b-58f1e1e456cd"
SOURCE_HASHES = {
    "base.mov": "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942",
    "repeated.wav": "832dd31cc46b9f4b4fdb7cbde18b4edc09ec249885634fba43da2a7b87dc768e",
}
TARGETS = {
    RESIDUAL_ID: {
        "track": ("audio", 2),
        "start": 4500,
        "end": 4699,
        "duration": 199,
        "filename": "repeated.wav",
        "mediaUid": "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8",
        "enabled": False,
        "marker": '{"issue": 141, "occurrence": 2, "section": "R2-residual"}',
    },
    RETIME_VIDEO_ID: {
        "track": ("video", 1),
        "start": 5500,
        "end": 5699,
        "duration": 199,
        "filename": "base.mov",
        "mediaUid": "9202163a-8381-43e6-9157-3a60f35c6f79",
        "enabled": True,
        "marker": '{"issue": 141, "occurrence": 0, "section": "R2-retime"}',
    },
    RETIME_AUDIO_ID: {
        "track": ("audio", 1),
        "start": 5500,
        "end": 5699,
        "duration": 199,
        "filename": "repeated.wav",
        "mediaUid": "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8",
        "enabled": True,
        "marker": '{"issue": 141, "occurrence": 1, "section": "R2-retime"}',
    },
}


def run(resolve, config, identity, expected, output, stamp, environment, *, probe):
    if environment.get("version") != PINNED_BUILD:
        raise RuntimeError("Resolve build differs from saved matrix checkpoint")
    checkpoint_path = Path(output) / PINNED_CAPTURE
    if probe.sha256(checkpoint_path) != PINNED_SHA256:
        raise RuntimeError("Pinned saved matrix capture changed or is missing")
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    passes = checkpoint.get("passes", [])
    if (
        checkpoint.get("consistency") != "equal-adjacent-reads"
        or len(passes) != 2
        or passes[0] != passes[1]
        or probe.errors(passes[0])
        or passes[0].get("projectId") != identity.get("projectId")
    ):
        raise RuntimeError("Pinned saved matrix capture is incomplete")
    baseline = passes[0]
    baseline_timeline = probe._pass_timeline(baseline, TIMELINE_ID)
    baseline_items = {
        item["GetUniqueId"]["value"]: item
        for track in baseline_timeline["tracks"]
        for item in track["items"]
    }
    if not set(TARGETS).issubset(baseline_items):
        raise RuntimeError("Pinned audio/retime targets are missing")
    for uid, spec in TARGETS.items():
        item = baseline_items[uid]
        source = item["GetMediaPoolItem"]
        clip = source["GetClipProperty"]["value"]
        source_bytes = source.get("sourceBytes", {})
        marker = item["GetMarkers"]["value"]["0"]["customData"]
        speed = item["GetSpeed"]["value"]
        if (
            item["GetTrackTypeAndIndex"]["value"] != list(spec["track"])
            or item["GetStart"]["value"] != spec["start"]
            or item["GetEnd"]["value"] != spec["end"]
            or item["GetDuration"]["value"] != spec["duration"]
            or item["GetClipEnabled"]["value"] is not spec["enabled"]
            or marker != spec["marker"]
            or source["GetUniqueId"]["value"] != spec["mediaUid"]
            or clip.get("File Name") != spec["filename"]
            or speed != {"Percentage": 100.0, "PitchCorrection": True}
            or source_bytes.get("sha256") != SOURCE_HASHES[spec["filename"]]
            or source_bytes.get("hashMatches") is not True
        ):
            raise RuntimeError(f"Pinned occurrence {uid} differs from plan")
        if expected.get(clip.get("File Path")) != SOURCE_HASHES[spec["filename"]]:
            raise RuntimeError(f"Pinned source hash differs for {spec['filename']}")
    if baseline_items[RETIME_VIDEO_ID].get("GetLinkedItems") != [
        {"value": RETIME_AUDIO_ID}
    ] or baseline_items[RETIME_AUDIO_ID].get("GetLinkedItems") != [
        {"value": RETIME_VIDEO_ID}
    ]:
        raise RuntimeError("Pinned retime occurrences are not the exact linked pair")

    journal = Path(output) / f"audio-cases-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()
    captures = []
    setters = []
    initial_timecode = None
    failure = None
    changed = []

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    def context():
        project = probe.require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if timeline is None or timeline.GetUniqueId() != TIMELINE_ID:
            raise RuntimeError("Pinned matrix is no longer selected")
        return project, timeline

    def live_items(timeline, *, allow_retime_bounds=False):
        found = {}
        for uid, spec in TARGETS.items():
            kind, index = spec["track"]
            items = timeline.GetItemListInTrack(kind, index)
            matches = [item for item in (items or []) if item.GetUniqueId() == uid]
            if len(matches) != 1:
                raise RuntimeError(f"Pinned occurrence {uid} is not unique")
            item = matches[0]
            media = item.GetMediaPoolItem()
            properties = media.GetClipProperty()
            locator = (
                properties.get("File Path") if isinstance(properties, dict) else None
            )
            bounds_may_change = allow_retime_bounds and uid in {
                RETIME_VIDEO_ID,
                RETIME_AUDIO_ID,
            }
            if (
                media.GetUniqueId() != spec["mediaUid"]
                or not isinstance(locator, str)
                or Path(locator).name != spec["filename"]
                or expected.get(locator) != SOURCE_HASHES[spec["filename"]]
                or probe.sha256(locator) != SOURCE_HASHES[spec["filename"]]
                or item.GetTrackTypeAndIndex() != list(spec["track"])
                or item.GetStart() != spec["start"]
                or item.GetSourceStartFrame() != 0
                or (
                    not bounds_may_change
                    and (
                        item.GetEnd() != spec["end"]
                        or item.GetDuration() != spec["duration"]
                        or item.GetSourceEndFrame()
                        != baseline_items[uid]["GetSourceEndFrame"]["value"]
                    )
                )
                or probe._marker_at(item.GetMarkers(), 0).get("customData")
                != spec["marker"]
            ):
                raise RuntimeError(f"Pinned occurrence {uid} identity changed")
            found[uid] = item
        return found

    def occurrence_map(value):
        timeline = probe._pass_timeline(value, TIMELINE_ID)
        return {
            item["GetUniqueId"]["value"]: item
            for track in timeline["tracks"]
            for item in track["items"]
        }

    def compare_capture(label, expected_pass=None, mode="exact"):
        result = probe.capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-" + label,
            environment,
        )
        captures.append(result)
        data = json.loads(Path(result["capturePath"]).read_text(encoding="utf-8"))
        reads = data.get("passes", [])
        if (
            result.get("status") != "equal-adjacent-reads"
            or len(reads) != 2
            or reads[0] != reads[1]
            or probe.errors(reads)
        ):
            raise RuntimeError(f"{label} two-pass capture is inconsistent")
        retain("two-pass content capture", "return", {"label": label, **result})
        if mode == "exact":
            expected_pass = baseline if expected_pass is None else expected_pass
            if reads != [expected_pass, expected_pass]:
                raise RuntimeError(f"{label} content differs from saved checkpoint")
        elif mode == "retime":
            current = reads[0]
            actual = occurrence_map(current)
            allowed = deepcopy(baseline)
            allowed_items = occurrence_map(allowed)
            for uid in (RETIME_VIDEO_ID, RETIME_AUDIO_ID):
                allowed_items[uid].clear()
                allowed_items[uid].update(actual[uid])
            if allowed != current:
                raise RuntimeError(
                    "Retime changed content outside the linked occurrences"
                )
            for uid in (RETIME_VIDEO_ID, RETIME_AUDIO_ID):
                for field in (
                    "GetSpeed",
                    "GetStart",
                    "GetStart(True)",
                    "GetEnd",
                    "GetEnd(True)",
                    "GetDuration",
                    "GetDuration(True)",
                    "GetLeftOffset",
                    "GetLeftOffset(True)",
                    "GetRightOffset",
                    "GetRightOffset(True)",
                    "GetSourceStartFrame",
                    "GetSourceEndFrame",
                    "GetSourceStartTime",
                    "GetSourceEndTime",
                    "GetLinkedItems",
                ):
                    value = actual[uid].get(field)
                    if value is None or probe.errors(value):
                        raise RuntimeError(f"Retime {field} readback is incomplete")
            before = occurrence_map(baseline)
            changed_fields = {}
            for uid in (RETIME_VIDEO_ID, RETIME_AUDIO_ID):
                changed_fields[uid] = {
                    key: {"before": before[uid].get(key), "after": actual[uid].get(key)}
                    for key in set(before[uid]) | set(actual[uid])
                    if before[uid].get(key) != actual[uid].get(key)
                }
            retain("SetSpeed linked occurrence delta", "readback", changed_fields)
        return reads[0]

    def call(method, args, *, target_uid=None, track=None, allow_retime_bounds=False):
        _project, timeline = context()
        items = live_items(timeline, allow_retime_bounds=allow_retime_bounds)
        item = items[target_uid] if target_uid is not None else timeline
        if track is not None:
            kind, index = track
            if index != 2 or kind != "audio" or timeline.GetTrackCount(kind) != 3:
                raise RuntimeError("A2 track layout changed before native call")
        retain(method, "request", list(args))
        try:
            value = getattr(item, method)(*args)
            retain(method, "return", value)
            setters.append({"method": method, "args": list(args), "return": value})
            if value is None or value is False:
                raise RuntimeError(f"{method} refused operation")
            return value
        except Exception as error:
            retain(method, "failure", f"{type(error).__name__}: {error}")
            raise

    def verify_track(enabled):
        _project, timeline = context()
        actual = timeline.GetIsTrackEnabled("audio", 2)
        retain("GetIsTrackEnabled(audio, 2)", "readback", actual)
        if actual is not enabled:
            raise RuntimeError("A2 track enable readback differs")

    def item_pass(value, uid):
        return occurrence_map(value)[uid]

    original_speed = deepcopy(baseline_items[RETIME_VIDEO_ID]["GetSpeed"]["value"])

    try:
        _project, timeline = context()
        live = live_items(timeline)
        if original_speed != {"Percentage": 100.0, "PitchCorrection": True}:
            raise RuntimeError("Original V1 speed state differs from the pinned matrix")
        retain("GetSpeed", "original", original_speed)
        if live[RESIDUAL_ID].GetClipEnabled() is not False:
            raise RuntimeError("Residual occurrence initial state differs")
        if timeline.GetTrackCount("audio") != 3:
            raise RuntimeError("Pinned audio track layout differs")
        if (
            timeline.GetTrackName("audio", 2) != "Audio 2"
            or timeline.GetTrackSubType("audio", 2) != "mono"
            or timeline.GetIsTrackLocked("audio", 2) is not False
            or timeline.GetIsTrackEnabled("audio", 2) is not True
        ):
            raise RuntimeError("Pinned A2 track identity/state differs")
        compare_capture("preflight")
        initial_timecode = timeline.GetCurrentTimecode()
        if not isinstance(initial_timecode, str) or not initial_timecode:
            raise RuntimeError("Initial timecode is unreadable")

        compare_capture("residual-before-enable")
        changed.append(("clip", RESIDUAL_ID))
        call("SetClipEnabled", (True,), target_uid=RESIDUAL_ID)
        if live_items(context()[1])[RESIDUAL_ID].GetClipEnabled() is not True:
            raise RuntimeError("Residual enable readback differs")
        data = deepcopy(baseline)
        item_pass(data, RESIDUAL_ID)["GetClipEnabled"]["value"] = True
        compare_capture("residual-enabled", expected_pass=data)

        compare_capture("residual-before-disable", expected_pass=data)
        changed.append(("clip", RESIDUAL_ID))
        call("SetClipEnabled", (False,), target_uid=RESIDUAL_ID)
        if live_items(context()[1])[RESIDUAL_ID].GetClipEnabled() is not False:
            raise RuntimeError("Residual disable readback differs")
        compare_capture("residual-disabled")

        compare_capture("A2-before-disable")
        changed.append(("track", "audio", 2))
        call("SetTrackEnable", ("audio", 2, False), track=("audio", 2))
        verify_track(False)
        data = deepcopy(baseline)
        next(
            track
            for track in probe._pass_timeline(data, TIMELINE_ID)["tracks"]
            if track["type"] == "audio" and track["index"] == 2
        )["GetIsTrackEnabled"]["value"] = False
        compare_capture("A2-disabled", expected_pass=data)

        compare_capture("A2-before-enable", expected_pass=data)
        changed.append(("track", "audio", 2))
        call("SetTrackEnable", ("audio", 2, True), track=("audio", 2))
        verify_track(True)
        compare_capture("A2-enabled")

        compare_capture("retime-before-50")
        changed.append(("speed", RETIME_VIDEO_ID))
        retain("GetSpeed", "original", original_speed)
        set_speed = {
            **original_speed,
            "Percentage": 50.0,
            "RippleTimeline": False,
        }
        call("SetSpeed", (set_speed,), target_uid=RETIME_VIDEO_ID)
        speed = live_items(context()[1], allow_retime_bounds=True)[
            RETIME_VIDEO_ID
        ].GetSpeed()
        retain("GetSpeed", "readback", speed)
        if not isinstance(speed, dict) or speed.get("Percentage") != 50.0:
            raise RuntimeError("V1 SetSpeed 50% readback differs")
        compare_capture("retime-50", mode="retime")

        compare_capture("retime-before-restore", mode="retime")
        changed.append(("speed", RETIME_VIDEO_ID))
        restore_speed = {**original_speed, "RippleTimeline": False}
        call(
            "SetSpeed",
            (restore_speed,),
            target_uid=RETIME_VIDEO_ID,
            allow_retime_bounds=True,
        )
        restored_speed = live_items(context()[1], allow_retime_bounds=True)[
            RETIME_VIDEO_ID
        ].GetSpeed()
        retain("GetSpeed", "restored-readback", restored_speed)
        if restored_speed != original_speed:
            raise RuntimeError("V1 speed/PitchCorrection restoration differs")
        compare_capture("retime-restored")
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"

    if failure is not None and changed:
        for entry in reversed(changed):
            try:
                _project, timeline = context()
                live = live_items(timeline, allow_retime_bounds=True)
                if entry[0] == "speed":
                    item = live[RETIME_VIDEO_ID]
                    speed = item.GetSpeed()
                    if speed != original_speed:
                        call(
                            "SetSpeed",
                            ({**original_speed, "RippleTimeline": False},),
                            target_uid=RETIME_VIDEO_ID,
                            allow_retime_bounds=True,
                        )
                        if (
                            live_items(context()[1], allow_retime_bounds=True)[
                                RETIME_VIDEO_ID
                            ].GetSpeed()
                            != original_speed
                        ):
                            raise RuntimeError(
                                "Partial speed setter could not be restored"
                            )
                elif entry[0] == "track":
                    enabled = timeline.GetIsTrackEnabled("audio", 2)
                    if enabled is not True:
                        call("SetTrackEnable", ("audio", 2, True), track=("audio", 2))
                        verify_track(True)
                elif entry[0] == "clip":
                    item = live[RESIDUAL_ID]
                    if item.GetClipEnabled() is not False:
                        call("SetClipEnabled", (False,), target_uid=RESIDUAL_ID)
                        if (
                            live_items(context()[1])[RESIDUAL_ID].GetClipEnabled()
                            is not False
                        ):
                            raise RuntimeError(
                                "Partial clip setter could not be restored"
                            )
            except Exception as error:
                retain(
                    "partial setter restoration",
                    "failure",
                    {
                        "target": entry,
                        "error": f"{type(error).__name__}: {error}",
                    },
                )

    try:
        _project, timeline = context()
        live = live_items(timeline)
        if (
            live[RESIDUAL_ID].GetClipEnabled() is not False
            or timeline.GetIsTrackEnabled("audio", 2) is not True
            or live[RETIME_VIDEO_ID].GetSpeed() != original_speed
        ):
            raise RuntimeError("Final target state differs from the checkpoint")
        compare_capture("final")
    except Exception as error:
        retain("final checkpoint", "failure", f"{type(error).__name__}: {error}")
        if failure is None:
            failure = f"{type(error).__name__}: {error}"

    if failure is not None:
        retain("audio-cases", "failure", failure)
    evidence = Path(output) / f"audio-cases-{stamp}.json"
    payload = {
        "kind": "bounded-native-audio-state-and-retime-observation",
        "checkpoint": PINNED_CAPTURE,
        "checkpointSha256": PINNED_SHA256,
        "captures": captures,
        "setterCalls": setters,
        "initialTimecode": initial_timecode,
        "failure": failure,
        "limits": [
            "No external output, mix, routing, or program-audio conclusion follows.",
            "Retime-linked audio changes are limited to the captured linked "
            "occurrence.",
        ],
    }
    with evidence.open("x", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")
    return {
        "status": "candidate-audio-states-retained"
        if failure is None
        else "audio-cases-refused",
        "action": "audio-cases",
        "journal": str(journal),
        "evidence": str(evidence),
        "captures": captures,
        "setterCalls": setters,
        "failure": failure,
    }
