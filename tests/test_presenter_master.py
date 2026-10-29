from __future__ import annotations

import copy
import json
import math
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
    _audio_duration_frame_count,
    _identity,
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
        self,
        media_id: str,
        path: str,
        unique_id: str,
        rate: tuple[int, int],
        source_frame_count: int,
        fps_label: str | None = None,
    ) -> None:
        self.media_id, self.path, self.unique_id, self.rate = (
            media_id,
            path,
            unique_id,
            rate,
        )
        self.source_frame_count = source_frame_count
        self.fps_label = fps_label

    def GetMediaId(self) -> str:
        return self.media_id

    def GetUniqueId(self) -> str:
        return self.unique_id

    def GetClipProperty(self, name: str) -> str:
        if name == "File Path":
            return self.path
        if name == "FPS":
            return self.fps_label or str(Fraction(*self.rate))
        if name == "Frames":
            return str(self.source_frame_count)
        if name == "Duration":
            rate = Fraction(*self.rate)
            seconds, frames = divmod(self.source_frame_count, math.ceil(rate))
            hours, seconds = divmod(seconds, 3600)
            minutes, seconds = divmod(seconds, 60)
            return f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
        if name == "Sample Rate":
            return "48000"
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
        end: int = self.info["endFrame"]
        return min(end, self.media.source_frame_count - 1)


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
        if self.project.current_only_lock_getter and self.project.current is not self:
            return False
        return self.locks.get((kind, index), False)


class FakeProject:
    def __init__(
        self,
        context: dict[str, Any],
        events: list[str],
        *,
        auto_select: bool = False,
        current_only_lock_getter: bool = False,
    ) -> None:
        self.context, self.events, self.auto_select = context, events, auto_select
        self.current_only_lock_getter = current_only_lock_getter
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
            "sourceRate": profile["context"]["sourceRaster"]["frameRate"],
            "frameRange": {
                "startInclusive": row["sourceStart"],
                "endExclusive": row["sourceEnd"],
            },
            "startBoundary": {
                "sourceFrameIndex": row["sourceStart"],
                "reviewFrameIndex": row["sourceStart"],
                "reviewPtsSeconds": {
                    "numerator": row["sourceStart"],
                    "denominator": 25,
                },
                "sourcePtsSeconds": {
                    "numerator": row["sourceStart"],
                    "denominator": 25,
                },
            },
            "endBoundary": {
                "sourceFrameIndex": row["sourceEnd"],
                "reviewFrameIndex": row["sourceEnd"],
                "reviewPtsSeconds": {
                    "numerator": row["sourceEnd"],
                    "denominator": 25,
                },
                "sourcePtsSeconds": {
                    "numerator": row["sourceEnd"],
                    "denominator": 25,
                },
            },
        }
        for row in picture_intervals
    ]
    mapping_content = _ts_canonical(mapping)
    payload = {
        "schemaVersion": "presenter-framing-request/v1",
        "status": "requested",
        "masterPolicy": "create_new_protected_master",
        "projectId": "registered-project",
        "sessionId": "session",
        "sourceId": "registered-presenter",
        "sourceHash": _MEDIA_HASH,
        "mappingEvidence": mapping,
        "mappingEvidenceContentJson": mapping_content,
        "mappingEvidenceHash": sha256_bytes(mapping_content.encode("utf-8")),
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


def _profile_pin() -> dict[str, Any]:
    profile = json.loads((_FIXTURES / "profile.json").read_text())
    return {key: profile[key] for key in ("id", "version", "profileHash")}


def _seal_request(request: dict[str, Any]) -> None:
    payload = {
        key: value
        for key, value in request.items()
        if key not in {"requestHash", "requestContentJson"}
    }
    request["requestContentJson"] = _ts_canonical(payload)
    request["requestHash"] = sha256_bytes(request["requestContentJson"].encode())


def _build(
    *,
    context_override: dict[str, Any] | None = None,
    auto_select: bool = False,
    single_wide: bool = False,
    current_only_lock_getter: bool = False,
) -> tuple[Any, ...]:
    profile = json.loads((_FIXTURES / "profile.json").read_text())
    context = context_override if context_override is not None else profile["context"]
    events: list[str] = []
    project = FakeProject(
        context,
        events,
        auto_select=auto_select,
        current_only_lock_getter=current_only_lock_getter,
    )
    pool = FakeMediaPool(project, events, auto_select=auto_select)
    picture = ResolvedPresenterMedia(
        "registered-project",
        "registered-presenter",
        _MEDIA_HASH,
        "/synthetic/presenter.mov",
        "media-picture",
        (25, 1),
        1100,
        "video",
        FakeMedia(
            "media-picture", "/synthetic/presenter.mov", "picture-uid", (25, 1), 1100
        ),
    )
    dialogue = ResolvedPresenterMedia(
        "registered-project",
        "registered-dialogue",
        _DIALOGUE_HASH,
        "/synthetic/dialogue.wav",
        "media-dialogue",
        (25, 1),
        110,
        "audio",
        FakeMedia(
            "media-dialogue", "/synthetic/dialogue.wav", "dialogue-uid", (25, 1), 110
        ),
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
        expected_profile_pin=_profile_pin(),
        expected_request_hash=request["requestHash"],
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


def test_final_lock_readback_selects_master_and_restores_generated_timeline() -> None:
    result, project, _pool, events, *_rest = _build(current_only_lock_getter=True)

    assert project.GetCurrentTimeline() is result.generated_timeline
    assert all(
        result.master_timeline.locks.get(track) is True
        for track in result.protected_master_tracks
    )
    assert result.master_timeline.GetIsTrackLocked("video", 1) is False
    assert result.generated_timeline.GetIsTrackLocked("video", 1) is False
    selection_indices = [
        index for index, event in enumerate(events) if event == "mutate:select-timeline"
    ]
    assert len(selection_indices) >= 4
    assert all(events[index - 1] == "guard" for index in selection_indices)


def test_accepts_a_single_profile_treatment() -> None:
    result, *_ = _build(single_wide=True)
    assert len(result.presenter_targets) == 1
    assert result.presenter_targets[0].key == "wide"


@pytest.mark.parametrize(
    ("fps_label", "registered_rate"),
    [
        ("23.976", (24_000, 1_001)),
        ("29.97", (30_000, 1_001)),
        ("47.952", (48_000, 1_001)),
        ("59.94", (60_000, 1_001)),
        ("119.88", (120_000, 1_001)),
    ],
)
def test_identity_normalizes_only_known_resolve_ntsc_labels(
    fps_label: str, registered_rate: tuple[int, int]
) -> None:
    media = ResolvedPresenterMedia(
        "project",
        "source",
        _MEDIA_HASH,
        "/synthetic/media.mov",
        "media",
        registered_rate,
        240,
        "video",
        FakeMedia(
            "media", "/synthetic/media.mov", "uid", registered_rate, 240, fps_label
        ),
    )

    assert _identity(media) == ("media", "uid")


@pytest.mark.parametrize("rate", [(24000, 1001), (30000, 1001), (60000, 1001)])
def test_fractional_rate_dialogue_identity_uses_nominal_timecode(
    rate: tuple[int, int],
) -> None:
    media = ResolvedPresenterMedia(
        "project",
        "source",
        _DIALOGUE_HASH,
        "/synthetic/dialogue.wav",
        "media",
        rate,
        240,
        "audio",
        FakeMedia("media", "/synthetic/dialogue.wav", "uid", rate, 240),
    )
    assert _identity(media) == ("media", "uid")


@pytest.mark.parametrize(
    ("label", "rate", "expected"),
    [
        ("00:01:00;02", (30000, 1001), 1800),
        ("00:10:00;00", (30000, 1001), 17982),
        ("01:00:00;00", (30000, 1001), 107892),
        ("00:01:00;04", (60000, 1001), 3600),
        ("00:01:00;08", (120000, 1001), 7200),
    ],
)
def test_audio_duration_drop_frame_counts(
    label: str, rate: tuple[int, int], expected: int
) -> None:
    assert _audio_duration_frame_count(label, Fraction(*rate)) == expected


@pytest.mark.parametrize(
    ("label", "rate"),
    [
        ("00:01:00;00", (30000, 1001)),
        ("00:01:00;03", (60000, 1001)),
        ("00:00:01;00", (24000, 1001)),
        ("00:00:01;00", (30, 1)),
        ("00:00:00:24", (24000, 1001)),
    ],
)
def test_audio_duration_refuses_invalid_timecode(
    label: str, rate: tuple[int, int]
) -> None:
    with pytest.raises(PresenterMasterError):
        _audio_duration_frame_count(label, Fraction(*rate))


def test_identity_refuses_decimal_rate_that_does_not_match_registration() -> None:
    registered_rate = (24_000, 1_001)
    media = ResolvedPresenterMedia(
        "project",
        "source",
        _MEDIA_HASH,
        "/synthetic/media.mov",
        "media",
        registered_rate,
        240,
        "video",
        FakeMedia("media", "/synthetic/media.mov", "uid", registered_rate, 240, "24.0"),
    )

    with pytest.raises(PresenterMasterError, match="frame rate differs"):
        _identity(media)


@pytest.mark.parametrize(
    ("kind", "registered_count", "native_count"),
    [("video", 1101, 1100), ("audio", 111, 110)],
)
def test_identity_requires_native_media_to_match_registered_source_frame_count(
    kind: str, registered_count: int, native_count: int
) -> None:
    rate = (25, 1)
    media = ResolvedPresenterMedia(
        "project",
        "source",
        _MEDIA_HASH,
        "/synthetic/media.mov",
        "media",
        rate,
        registered_count,
        kind,  # type: ignore[arg-type]
        FakeMedia(
            "media",
            "/synthetic/media.mov",
            "uid",
            rate,
            native_count,
        ),
    )

    with pytest.raises(PresenterMasterError, match="source frame count differs"):
        _identity(media)


@pytest.mark.parametrize(
    "failure",
    [
        "context",
        "request",
        "non_boolean_visibility",
        "fractional_audio",
        "audio_fps",
        "embedded_audio",
        "request_hash",
        "profile_pin",
        "mapping_rate",
        "mapping_boundary",
        "mapping_generation",
        "stale_mapping_hash",
        "mapping_proxy_without_hash",
        "mapping_hash_missing",
        "mapping_duplicate_keys",
        "mapping_nonfinite",
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
        1100,
        "video",
        FakeMedia(
            "media-picture", "/synthetic/presenter.mov", "picture-uid", (25, 1), 1100
        ),
    )
    dialogue = ResolvedPresenterMedia(
        "registered-project",
        "registered-dialogue",
        _DIALOGUE_HASH,
        "/synthetic/dialogue.wav",
        "media-dialogue",
        (25, 1),
        110,
        "audio",
        FakeMedia(
            "media-dialogue", "/synthetic/dialogue.wav", "dialogue-uid", (25, 1), 110
        ),
    )
    request = _request(context=profile["context"])
    if failure == "request":
        request["intervals"][1]["sourceStart"] = 1051
    elif failure == "non_boolean_visibility":
        request["intervals"][1]["visible"] = "false"
    elif failure == "fractional_audio":
        request["dialogue"]["sourceStartSample"] = 1
        request["dialogue"]["sourceEndSample"] = 192001
    elif failure == "embedded_audio":
        dialogue = replace(dialogue, media_hash=picture.media_hash)
        request["dialogue"]["mediaHash"] = picture.media_hash
    elif failure == "audio_fps":
        dialogue = ResolvedPresenterMedia(
            "registered-project",
            "registered-dialogue",
            _DIALOGUE_HASH,
            "/synthetic/dialogue.wav",
            "media-dialogue",
            (24, 1),
            110,
            "audio",
            FakeMedia(
                "media-dialogue",
                "/synthetic/dialogue.wav",
                "dialogue-uid",
                (24, 1),
                110,
            ),
        )
    elif failure == "mapping_rate":
        request["mappingEvidence"][0]["sourceRate"] = {
            "numerator": 24,
            "denominator": 1,
        }
        mapping_content = _ts_canonical(request["mappingEvidence"])
        request["mappingEvidenceContentJson"] = mapping_content
        request["mappingEvidenceHash"] = sha256_bytes(mapping_content.encode())
    elif failure == "mapping_boundary":
        request["mappingEvidence"][0]["startBoundary"]["sourceFrameIndex"] += 1
        mapping_content = _ts_canonical(request["mappingEvidence"])
        request["mappingEvidenceContentJson"] = mapping_content
        request["mappingEvidenceHash"] = sha256_bytes(mapping_content.encode())
    elif failure == "mapping_generation":
        request["mappingEvidence"][1]["generationIdentity"] = "3" * 64
        mapping_content = _ts_canonical(request["mappingEvidence"])
        request["mappingEvidenceContentJson"] = mapping_content
        request["mappingEvidenceHash"] = sha256_bytes(mapping_content.encode())
    elif failure == "stale_mapping_hash":
        request["mappingEvidenceContentJson"] += " "
    elif failure == "mapping_proxy_without_hash":
        request["mappingEvidence"][0]["videoSource"] = "proxy"
        mapping_content = _ts_canonical(request["mappingEvidence"])
        request["mappingEvidenceContentJson"] = mapping_content
        request["mappingEvidenceHash"] = sha256_bytes(mapping_content.encode())
    elif failure == "mapping_hash_missing":
        del request["mappingEvidence"][0]["mappingHash"]
        mapping_content = _ts_canonical(request["mappingEvidence"])
        request["mappingEvidenceContentJson"] = mapping_content
        request["mappingEvidenceHash"] = sha256_bytes(mapping_content.encode())
    elif failure == "mapping_duplicate_keys":
        request["mappingEvidenceContentJson"] = '[{"duplicate":1,"duplicate":2}]'
    elif failure == "mapping_nonfinite":
        request["mappingEvidenceContentJson"] = "[NaN]"

    _seal_request(request)

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
            expected_profile_pin=(
                {**_profile_pin(), "profileHash": _PROCESS_HASH}
                if failure == "profile_pin"
                else _profile_pin()
            ),
            expected_request_hash=(
                _DIALOGUE_HASH if failure == "request_hash" else request["requestHash"]
            ),
        )
    assert len(project.timelines) == 1
    assert not pool.appends
    assert not any(event.startswith("mutate:") for event in events)


def test_selects_new_targets_when_resolve_does_not_auto_select() -> None:
    result, _project, _pool, events, *_ = _build(auto_select=False)
    assert result.master_timeline_uid != result.generated_timeline_uid
    assert "mutate:select-timeline" in events
