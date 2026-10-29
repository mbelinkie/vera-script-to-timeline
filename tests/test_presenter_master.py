from __future__ import annotations

import copy
import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.presenter_framing import ValidatedSourceTimeInterval
from vera_timeline_agent.presenter_master import (
    PresenterMasterError,
    ResolvedPresenterMedia,
    prepare_presenter_master,
)

_FIXTURES = (
    Path(__file__).parents[1] / "packages/contracts/test/fixtures/presenter-framing"
)
_MEDIA_HASH = f"sha256:{'a' * 64}"
_DIALOGUE_HASH = f"sha256:{'b' * 64}"
_COLOR_HASH = f"sha256:{'c' * 64}"
_REVIEW_HASH = f"sha256:{'d' * 64}"
_PROCESS_HASH = f"sha256:{'e' * 64}"
_SYNC_HASH = f"sha256:{'f' * 64}"
_PROBE_HASH = f"sha256:{'1' * 64}"
_GENERATION = "2" * 64


def _js_numbers(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _js_numbers(nested) for key, nested in value.items()}
    if isinstance(value, list):
        return [_js_numbers(nested) for nested in value]
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return value


def _ts_canonical(value: Any) -> str:
    return (
        json.dumps(_js_numbers(value), indent=2, sort_keys=True, ensure_ascii=False)
        + "\n"
    )


class FakeMedia:
    def __init__(
        self, media_id: str, path: str, unique_id: str, rate: tuple[int, int]
    ) -> None:
        self.media_id, self.path, self.unique_id, self.rate = (
            media_id,
            path,
            unique_id,
            rate,
        )

    def GetMediaId(self) -> str:
        return self.media_id

    def GetUniqueId(self) -> str:
        return self.unique_id

    def GetClipProperty(self, name: str) -> str:
        if name == "File Path":
            return self.path
        if name == "FPS":
            return str(Fraction(*self.rate))
        raise AssertionError(name)


class FakeTimelineItem:
    def __init__(self, media: FakeMedia, info: dict[str, Any], uid: str) -> None:
        self.media, self.info, self.uid = media, info, uid

    def GetType(self) -> str:
        return "video" if self.info["mediaType"] == 1 else "audio"

    def GetMediaPoolItem(self) -> FakeMedia:
        return self.media

    def GetUniqueId(self) -> str:
        return self.uid

    def GetStart(self, _subframe: bool = False) -> int:
        value: int = self.info["recordFrame"]
        return value

    def GetDuration(self, _subframe: bool = False) -> int:
        value: int = self.info["endFrame"] - self.info["startFrame"]
        return value

    def GetSourceStartFrame(self) -> int:
        value: int = self.info["startFrame"]
        return value

    def GetSourceEndFrame(self) -> int:
        value: int = self.info["endFrame"] - 1
        return value


class FakeTimeline:
    def __init__(
        self,
        project: FakeProject,
        uid: str,
        name: str,
        context: dict[str, Any],
        events: list[str],
    ) -> None:
        self.project, self.uid, self.name, self.context, self.events = (
            project,
            uid,
            name,
            context,
            events,
        )
        self.tracks: dict[str, list[list[FakeTimelineItem]]] = {
            "video": [[], []],
            "audio": [[], []],
        }
        self.locks: dict[tuple[str, int], bool] = {}

    def GetName(self) -> str:
        return self.name

    def GetUniqueId(self) -> str:
        return self.uid

    def SetStartTimecode(self, _timecode: str) -> bool:
        self.events.append("mutate:start-timecode")
        return True

    def GetStartFrame(self) -> int:
        return 0

    def GetTrackCount(self, kind: str) -> int:
        return len(self.tracks[kind])

    def AddTrack(self, kind: str) -> bool:
        self.events.append("mutate:add-track")
        self.tracks[kind].append([])
        return True

    def GetItemListInTrack(self, kind: str, index: int) -> list[FakeTimelineItem]:
        return list(self.tracks[kind][index - 1])

    def SetTrackLock(self, kind: str, index: int, locked: bool) -> bool:
        self.events.append("mutate:lock-track")
        self.locks[kind, index] = locked
        return True

    def GetIsTrackLocked(self, kind: str, index: int) -> bool:
        return self.locks.get((kind, index), False)


class FakeProject:
    def __init__(
        self, context: dict[str, Any], events: list[str], *, auto_select: bool = False
    ) -> None:
        self.context, self.events, self.auto_select = context, events, auto_select
        self.uid = "resolve-project-uid"
        self.timelines: list[FakeTimeline] = []
        self.current: FakeTimeline | None = None
        original = FakeTimeline(self, "original-timeline", "Existing", context, events)
        self.timelines.append(original)
        self.current = original

    def GetUniqueId(self) -> str:
        return self.uid

    def GetCurrentTimeline(self) -> FakeTimeline | None:
        return self.current

    def GetTimelineCount(self) -> int:
        return len(self.timelines)

    def GetTimelineByIndex(self, index: int) -> FakeTimeline:
        return self.timelines[index - 1]

    def SetCurrentTimeline(self, timeline: FakeTimeline) -> bool:
        self.events.append("mutate:select-timeline")
        self.current = timeline
        return True


class FakeMediaPool:
    def __init__(
        self, project: FakeProject, events: list[str], *, auto_select: bool = False
    ) -> None:
        self.project, self.events, self.auto_select = project, events, auto_select
        self.appends: list[list[dict[str, Any]]] = []
        self.serial = 0

    def CreateEmptyTimeline(self, name: str) -> FakeTimeline:
        self.events.append("mutate:create-timeline")
        timeline = FakeTimeline(
            self.project,
            f"timeline-{len(self.project.timelines)}",
            name,
            self.project.context,
            self.events,
        )
        self.project.timelines.append(timeline)
        if self.auto_select:
            self.project.current = timeline
        return timeline

    def AppendToTimeline(self, infos: list[dict[str, Any]]) -> list[FakeTimelineItem]:
        self.events.append("mutate:append")
        self.appends.append(
            copy.deepcopy(
                [
                    {
                        key: value
                        for key, value in info.items()
                        if key != "mediaPoolItem"
                    }
                    for info in infos
                ]
            )
        )
        timeline = self.project.current
        assert timeline is not None
        result = []
        for info in infos:
            self.serial += 1
            item = FakeTimelineItem(info["mediaPoolItem"], info, f"item-{self.serial}")
            timeline.tracks["video" if info["mediaType"] == 1 else "audio"][
                info["trackIndex"] - 1
            ].append(item)
            result.append(item)
        return result


def _request(*, context: dict[str, Any], single_wide: bool = False) -> dict[str, Any]:
    profile = json.loads((_FIXTURES / "profile.json").read_text())
    profile_content = (_FIXTURES / "profile-content.json").read_text()
    picture_intervals = [
        {
            "eventId": "wide-event",
            "framingKey": "wide",
            "recordStart": 0,
            "recordEnd": 40,
            "sourceStart": 1000,
            "sourceEnd": 1040,
            "visible": True,
            "name": "OC WIDE wide-event",
            "color": "Blue",
        },
        {
            "eventId": "covered-event",
            "framingKey": "wide",
            "recordStart": 40,
            "recordEnd": 60,
            "sourceStart": 1040,
            "sourceEnd": 1060,
            "visible": False,
            "name": "OC WIDE covered-event",
            "color": "Blue",
        },
        {
            "eventId": "tight-event",
            "framingKey": "tight",
            "recordStart": 60,
            "recordEnd": 100,
            "sourceStart": 1060,
            "sourceEnd": 1100,
            "visible": True,
            "name": "OC TIGHT tight-event",
            "color": "Orange",
        },
    ]
    if single_wide:
        picture_intervals = [
            {
                "eventId": "wide-only-event",
                "framingKey": "wide",
                "recordStart": 0,
                "recordEnd": 100,
                "sourceStart": 1000,
                "sourceEnd": 1100,
                "visible": True,
                "name": "OC WIDE wide-only-event",
                "color": "Blue",
            }
        ]
    mapping = [
        {
            "method": "frame-index-identity/v1",
            "projectId": "registered-project",
            "sourceId": "registered-presenter",
            "sourceContentHash": _MEDIA_HASH,
            "sourceProbeHash": _PROBE_HASH,
            "videoSource": "master",
            "mappingHash": None,
            "generationIdentity": _GENERATION,
            "frameRange": {
                "startInclusive": row["sourceStart"],
                "endExclusive": row["sourceEnd"],
            },
        }
        for row in picture_intervals
    ]
    payload = {
        "schemaVersion": "presenter-framing-request/v1",
        "status": "requested",
        "masterPolicy": "create_new_protected_master",
        "projectId": "registered-project",
        "sessionId": "session",
        "sourceId": "registered-presenter",
        "sourceHash": _MEDIA_HASH,
        "mappingEvidence": mapping,
        "mappingEvidenceHash": f"sha256:{'9' * 64}",
        "reviewedColor": {
            "profileHash": _COLOR_HASH,
            "reviewEvidenceHash": _REVIEW_HASH,
        },
        "profile": profile,
        "profileContentJson": profile_content,
        "intervals": picture_intervals,
        "dialogue": {
            "eventId": "dialogue-event",
            "mediaHash": _DIALOGUE_HASH,
            "processingProfileHash": _PROCESS_HASH,
            "synchronizationEvidenceHash": _SYNC_HASH,
            "recordStart": 0,
            "recordEnd": 100,
            "sourceStartSample": 19200,
            "sourceEndSample": 211200,
            "sampleRate": 48000,
        },
    }
    content = _ts_canonical(payload)
    assert context == profile["context"]
    return {
        **payload,
        "requestContentJson": content,
        "requestHash": sha256_bytes(content.encode()),
    }


def _build(
    *,
    context_override: dict[str, Any] | None = None,
    auto_select: bool = False,
    single_wide: bool = False,
) -> tuple[Any, ...]:
    profile = json.loads((_FIXTURES / "profile.json").read_text())
    context = context_override if context_override is not None else profile["context"]
    events: list[str] = []
    project = FakeProject(context, events, auto_select=auto_select)
    pool = FakeMediaPool(project, events, auto_select=auto_select)
    picture = ResolvedPresenterMedia(
        "registered-project",
        "registered-presenter",
        _MEDIA_HASH,
        "/synthetic/presenter.mov",
        "media-picture",
        (25, 1),
        "video",
        FakeMedia("media-picture", "/synthetic/presenter.mov", "picture-uid", (25, 1)),
    )
    dialogue = ResolvedPresenterMedia(
        "registered-project",
        "registered-dialogue",
        _DIALOGUE_HASH,
        "/synthetic/dialogue.wav",
        "media-dialogue",
        (25, 1),
        "audio",
        FakeMedia("media-dialogue", "/synthetic/dialogue.wav", "dialogue-uid", (25, 1)),
    )

    def guard(expected_uid: str | None) -> None:
        actual = project.current.GetUniqueId() if project.current else None
        assert actual == expected_uid
        events.append("guard")

    def context_reader(_timeline: Any) -> dict[str, Any]:
        return context

    request = _request(context=profile["context"], single_wide=single_wide)
    result = prepare_presenter_master(
        project,
        pool,
        request,
        registered_project_id="registered-project",
        picture_media=picture,
        dialogue_media=dialogue,
        upstream_color_operation="identity_synthetic_reviewed",
        current_target_guard=guard,
        context_reader=context_reader,
    )
    return result, project, pool, events, picture, dialogue, request


def test_builds_locked_continuous_master_and_separate_framing_target() -> None:
    result, project, pool, events, _picture, _dialogue, _request_value = _build()
    assert result.master_timeline.GetName().startswith("VERA Presenter Master ")
    assert result.generated_timeline.GetName().startswith("VERA Presenter Framing ")
    assert result.master_timeline_uid != result.generated_timeline_uid
    assert result.protected_master_tracks == (
        ("video", 1),
        ("video", 2),
        ("audio", 1),
        ("audio", 2),
    )
    assert all(
        result.master_timeline.GetIsTrackLocked(*track)
        for track in result.protected_master_tracks
    )
    assert not result.generated_timeline.GetIsTrackLocked("video", 1)
    assert len(result.master_timeline.GetItemListInTrack("video", 1)) == 1
    assert len(result.master_timeline.GetItemListInTrack("audio", 1)) == 1
    assert len(result.generated_timeline.GetItemListInTrack("video", 1)) == 3
    assert len(result.generated_timeline.GetItemListInTrack("audio", 1)) == 1
    assert [target.record_interval for target in result.presenter_targets] == [
        ValidatedSourceTimeInterval(0, 40),
        ValidatedSourceTimeInterval(40, 60),
        ValidatedSourceTimeInterval(60, 100),
    ]
    assert [target.source_interval for target in result.presenter_targets] == [
        ValidatedSourceTimeInterval(1000, 1040),
        ValidatedSourceTimeInterval(1040, 1060),
        ValidatedSourceTimeInterval(1060, 1100),
    ]
    assert result.presenter_targets[1].event_id == "covered-event"
    assert result.presenter_targets[1].key == "wide"
    assert [info["mediaType"] for batch in pool.appends for info in batch] == [
        1,
        2,
        1,
        1,
        1,
        2,
    ]
    assert pool.appends[0][0]["endFrame"] == 1100
    assert pool.appends[1][0]["startFrame"] == 10
    assert pool.appends[1][0]["endFrame"] == 110
    assert result.reviewed_color["operation"] == "identity_synthetic_reviewed"
    assert "no color operation" in result.reviewed_color["application"]
    assert "no audio operation" in result.processed_dialogue["processing"]
    assert len(project.timelines) == 3
    assert all(event == "guard" or event.startswith("mutate:") for event in events)
    for index, event in enumerate(events):
        if event.startswith("mutate:"):
            assert events[index - 1] == "guard"


def test_accepts_a_single_profile_treatment() -> None:
    result, *_ = _build(single_wide=True)
    assert len(result.presenter_targets) == 1
    assert result.presenter_targets[0].key == "wide"


@pytest.mark.parametrize(
    "failure",
    [
        "context",
        "request",
        "non_boolean_visibility",
        "fractional_audio",
        "audio_fps",
        "embedded_audio",
    ],
)
def test_refuses_bad_context_evidence_or_ranges_before_timeline_creation(
    failure: str,
) -> None:
    profile = json.loads((_FIXTURES / "profile.json").read_text())
    context = copy.deepcopy(profile["context"])
    if failure == "context":
        context["timelineRaster"]["width"] = 1280
    events: list[str] = []
    project, pool = FakeProject(context, events), None
    pool = FakeMediaPool(project, events)
    picture = ResolvedPresenterMedia(
        "registered-project",
        "registered-presenter",
        _MEDIA_HASH,
        "/synthetic/presenter.mov",
        "media-picture",
        (25, 1),
        "video",
        FakeMedia("media-picture", "/synthetic/presenter.mov", "picture-uid", (25, 1)),
    )
    dialogue = ResolvedPresenterMedia(
        "registered-project",
        "registered-dialogue",
        _DIALOGUE_HASH,
        "/synthetic/dialogue.wav",
        "media-dialogue",
        (25, 1),
        "audio",
        FakeMedia("media-dialogue", "/synthetic/dialogue.wav", "dialogue-uid", (25, 1)),
    )
    request = _request(context=profile["context"])
    if failure == "request":
        request["intervals"][1]["sourceStart"] = 1051
        payload = {
            key: value
            for key, value in request.items()
            if key not in {"requestHash", "requestContentJson"}
        }
        request["requestContentJson"] = _ts_canonical(payload)
        request["requestHash"] = sha256_bytes(request["requestContentJson"].encode())
    elif failure == "non_boolean_visibility":
        request["intervals"][1]["visible"] = "false"
        payload = {
            key: value
            for key, value in request.items()
            if key not in {"requestHash", "requestContentJson"}
        }
        request["requestContentJson"] = _ts_canonical(payload)
        request["requestHash"] = sha256_bytes(request["requestContentJson"].encode())
    elif failure == "fractional_audio":
        request["dialogue"]["sourceStartSample"] = 1
        request["dialogue"]["sourceEndSample"] = 192001
        payload = {
            key: value
            for key, value in request.items()
            if key not in {"requestHash", "requestContentJson"}
        }
        request["requestContentJson"] = _ts_canonical(payload)
        request["requestHash"] = sha256_bytes(request["requestContentJson"].encode())
    elif failure == "embedded_audio":
        dialogue = replace(dialogue, media_hash=picture.media_hash)
        request["dialogue"]["mediaHash"] = picture.media_hash
        payload = {
            key: value
            for key, value in request.items()
            if key not in {"requestHash", "requestContentJson"}
        }
        request["requestContentJson"] = _ts_canonical(payload)
        request["requestHash"] = sha256_bytes(request["requestContentJson"].encode())
    elif failure == "audio_fps":
        dialogue = ResolvedPresenterMedia(
            "registered-project",
            "registered-dialogue",
            _DIALOGUE_HASH,
            "/synthetic/dialogue.wav",
            "media-dialogue",
            (24, 1),
            "audio",
            FakeMedia(
                "media-dialogue", "/synthetic/dialogue.wav", "dialogue-uid", (24, 1)
            ),
        )

    def guard(expected_uid: str | None) -> None:
        assert (
            project.current.GetUniqueId() if project.current else None
        ) == expected_uid

    with pytest.raises(PresenterMasterError):
        prepare_presenter_master(
            project,
            pool,
            request,
            registered_project_id="registered-project",
            picture_media=picture,
            dialogue_media=dialogue,
            upstream_color_operation="identity_synthetic_reviewed",
            current_target_guard=guard,
            context_reader=lambda _timeline: context,
        )
    assert len(project.timelines) == 1
    assert not pool.appends
    assert not any(event.startswith("mutate:") for event in events)


def test_selects_new_targets_when_resolve_does_not_auto_select() -> None:
    result, _project, _pool, events, *_ = _build(auto_select=False)
    assert result.master_timeline_uid != result.generated_timeline_uid
    assert "mutate:select-timeline" in events
