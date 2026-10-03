"""One focused stdlib check for the guarded second-duplicate evidence rules."""

import importlib.util
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "second_duplicate", Path(__file__).with_name("second-duplicate.py")
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _timeline(
    uid, name, occurrence_uids, *, media_uids=None, marker_note="same", identical=False
):
    media_uids = media_uids or [f"media-{index % 5}" for index in range(6)]
    track = {
        "type": "video",
        "index": 1,
        "GetTrackName": {"value": "V1"},
        "items": [],
    }
    for index, occurrence_uid in enumerate(occurrence_uids):
        track["items"].append(
            {
                "GetUniqueId": {"value": occurrence_uid},
                "GetName": {"value": "same" if identical else f"clip-{index}"},
                "GetType": {"value": "Video"},
                "GetTrackTypeAndIndex": {"value": ["video", 1]},
                "GetMarkers": {
                    "value": {
                        10: {
                            "name": "section",
                            "note": marker_note,
                            "customData": "bound",
                        }
                    }
                },
                "GetProperties": {"value": {"Opacity": "1.0"}},
                "GetClipEnabled": {"value": True},
                "GetSourceStartFrame": {"value": 0},
                "GetSourceEndFrame": {"value": 199},
                "GetSourceStartTime": {"value": 0.0},
                "GetSourceEndTime": {"value": 7.96},
                "GetStart": {"value": 0 if identical else index * 200},
                "GetEnd": {"value": 199 if identical else index * 200 + 199},
                "GetDuration": {"value": 199},
                "GetStart(True)": {"value": 0 if identical else index * 200},
                "GetEnd(True)": {"value": 199 if identical else index * 200 + 199},
                "GetDuration(True)": {"value": 199},
                "GetLeftOffset": {"value": 0},
                "GetRightOffset": {"value": 0},
                "GetMediaPoolItem": {"GetUniqueId": {"value": media_uids[index]}},
            }
        )
    return {
        "GetUniqueId": {"value": uid},
        "GetName": {"value": name},
        "GetStartFrame": {"value": 0},
        "GetEndFrame": {"value": 1200},
        "GetStartTimecode": {"value": "00:00:00:00"},
        "GetMarkers": {
            "value": {0: {"name": "sequence", "note": "note", "customData": "seq"}}
        },
        "tracks": [track],
    }


def _inventory(timelines, proxy_uids, usage="1"):
    mappings = [
        {
            "timelineUid": {"value": uid},
            "timelineName": {"value": name},
            "poolItemUid": {"value": proxy_uids[uid]},
            "poolItemName": {"value": name},
            "poolItemProperties": {
                "value": {"Usage": usage, "File Name": f"{name}.drt"}
            },
        }
        for uid, name in timelines.items()
    ]
    items = [
        {
            "uid": proxy_uids[uid],
            "name": {"value": name},
            "folderUid": "folder",
            "evidence": {
                "GetClipProperty": {
                    "value": {"Usage": usage, "File Name": f"{name}.drt"}
                }
            },
        }
        for uid, name in timelines.items()
    ]
    for index in range(5):
        items.append(
            {
                "uid": f"media-{index}",
                "name": {"value": f"media-{index}"},
                "folderUid": "folder",
                "evidence": {
                    "GetClipProperty": {
                        "value": {"Usage": usage, "File Path": f"/synthetic/{index}"}
                    }
                },
            }
        )
    return {
        "folders": [{"uid": "folder", "name": "Master"}],
        "timelineMappings": mappings,
        "items": items,
    }


def demo():
    source_ids = [f"old-{index}" for index in range(6)]
    copied_ids = [f"new-{index}" for index in range(6)]
    source = _timeline(
        MODULE.R1_UID, "VERA 141 R1 identity", source_ids, identical=True
    )
    duplicate = _timeline(
        "new-timeline", MODULE.DUPLICATE_NAME, copied_ids, identical=True
    )
    state_before = {"timelines": [source]}
    state_after = {"timelines": [source, duplicate]}
    result = MODULE._validate_copy(
        state_before, state_after, MODULE.R1_UID, "new-timeline"
    )
    assert result["matchingOccurrenceSignatures"] == 6
    assert result["ambiguousSignatureOccurrences"] == 2
    assert not set(result["sourceOccurrenceUids"]) & set(
        result["duplicateOccurrenceUids"]
    )
    assert result["sharedSourceUids"] == [f"media-{index}" for index in range(5)]

    original_timelines = dict(MODULE.TIMELINES)
    after_timelines = {**original_timelines, "new-timeline": MODULE.DUPLICATE_NAME}
    old_proxy = {uid: f"proxy-{uid}" for uid in original_timelines}
    new_proxy = {**old_proxy, "new-timeline": "proxy-new"}
    before_pool = _inventory(original_timelines, old_proxy)
    after_pool = _inventory(after_timelines, new_proxy, usage="2")
    pool_delta = MODULE._validate_additive_pool(
        before_pool, after_pool, "new-timeline", MODULE.DUPLICATE_NAME
    )
    assert pool_delta["addedTimelineProxyUid"] == "proxy-new"

    for broken in (
        _timeline("new-timeline", MODULE.DUPLICATE_NAME, source_ids),
        _timeline(
            "new-timeline", MODULE.DUPLICATE_NAME, copied_ids, marker_note="changed"
        ),
        _timeline(
            "new-timeline", MODULE.DUPLICATE_NAME, copied_ids, media_uids=["wrong"] * 6
        ),
    ):
        try:
            MODULE._validate_copy(
                state_before,
                {"timelines": [source, broken]},
                MODULE.R1_UID,
                "new-timeline",
            )
        except RuntimeError:
            pass
        else:
            raise AssertionError("Invalid duplicate passed copied-content checks")

    changed_timeline_marker = _timeline(
        "new-timeline", MODULE.DUPLICATE_NAME, copied_ids, identical=True
    )
    changed_timeline_marker["GetMarkers"] = {"value": {0: {"customData": "changed"}}}
    try:
        MODULE._validate_copy(
            state_before,
            {"timelines": [source, changed_timeline_marker]},
            MODULE.R1_UID,
            "new-timeline",
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Changed timeline marker data passed")

    extra_proxy = _inventory(after_timelines, new_proxy)
    extra_proxy["items"].append({"uid": "unexpected", "name": {"value": "unexpected"}})
    try:
        MODULE._validate_additive_pool(
            before_pool, extra_proxy, "new-timeline", MODULE.DUPLICATE_NAME
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("Unexpected pool item passed")

    class Probe:
        ROOT = Path(__file__).resolve().parents[3]

        @staticmethod
        def sha256(path):
            raise AssertionError("Pending-pin refusal must happen before file access")

    class Resolve:
        def __getattr__(self, name):
            raise AssertionError(
                f"Pending-pin refusal must precede Resolve calls: {name}"
            )

    try:
        MODULE.run(
            Resolve(),
            {
                "action": "second-native-duplicate",
                "externalScriptingSetting": "None",
                "projectName": "VERA Issue 141 Synthetic Probe 20260930-01a0f318",
            },
            probe=Probe,
        )
    except RuntimeError as error:
        assert "pin is pending" in str(error)
    else:
        raise AssertionError(
            "Missing reviewed R4 pin must refuse before any Resolve call"
        )

    print("Second native duplicate fake checks passed")


if __name__ == "__main__":
    demo()
