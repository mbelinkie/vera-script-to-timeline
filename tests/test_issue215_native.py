"""Bounded native observations for the qualification-output edited route."""

from __future__ import annotations

import copy
import hashlib
from pathlib import Path
from typing import Any

import pytest
import test_issue209_native as fixtures
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_records_v2 import (
    AUTHORITY_REFERENCE_FIELDS,
    OutputConsistencyError,
    _canonical,
    _json_hash,
)


def _edited_context(context: dict[str, Any]) -> dict[str, Any]:
    edited = copy.deepcopy(context)
    edited["phase"] = "edited"
    projection = {
        key: value
        for key, value in edited.items()
        if key not in AUTHORITY_REFERENCE_FIELDS | {"invocationId"}
    }
    projection["binding"] = {"kind": "baseline"}
    edited["binding"]["bindingSha256"] = _json_hash(projection)
    return edited


def _set_item(
    item: Any,
    *,
    uid: str,
    stamp: str,
    start: int,
    duration: int,
    source_start: int,
    source_end: int,
    linked: list[Any] | None = None,
) -> Any:
    item.GetUniqueId = lambda: uid
    item.GetMarkerCustomData = lambda _frame: stamp
    item.GetStart = lambda _in_frames: start
    item.GetDuration = lambda _in_frames: duration
    item.GetEnd = lambda _in_frames: start + duration
    item.GetSourceStartFrame = lambda: source_start
    item.GetSourceEndFrame = lambda: source_end
    item.GetLinkedItems = lambda: linked or []
    return item


def _set_inventory(timeline: Any, items: list[Any], end: int) -> None:
    timeline.GetItemListInTrack = lambda _kind, _index: items
    timeline.GetEndFrame = lambda: end


def _held_picture_boundary_case(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], Any, Any, Any]:
    resolve, request, admitted, left, timeline = fixtures._geometry_case(tmp_path)
    request["profile"] = native.MATRIX_PROFILE
    admitted["view"]["sources"][0]["kind"] = "still"
    left_event = admitted["view"]["events"][0]
    left_event["recordRange"] = {"startFrame": 0, "durationFrames": 4}
    left_event["sourceRange"] = {"startFrame": 0, "durationFrames": 4}
    left_event["v2Event"] = {"id": "left-picture", "description": "left hold"}
    right_event = copy.deepcopy(left_event)
    right_event.update(
        {
            "id": "event-two",
            "recordRange": {"startFrame": 4, "durationFrames": 6},
            "sourceRange": {"startFrame": 0, "durationFrames": 6},
            "v2Event": {"id": "right-picture", "description": "right hold"},
        }
    )
    admitted["view"]["events"].append(right_event)
    left = _set_item(
        left,
        uid="held-left",
        stamp=native._event_stamp(left_event),
        start=0,
        duration=6,
        source_start=0,
        source_end=0,
    )
    right = _set_item(
        fixtures._Item(left.media, native._event_stamp(right_event)),
        uid="held-right",
        stamp=native._event_stamp(right_event),
        start=6,
        duration=4,
        source_start=0,
        source_end=0,
    )
    left.media.frame_count = 1
    _set_inventory(timeline, [left, right], 10)
    return request, admitted, resolve, timeline, (left, right)


def _matrix_av_trim_case(
    tmp_path: Path,
) -> tuple[dict[str, Any], dict[str, Any], Any]:
    resolve, request, admitted, video_first, timeline = fixtures._geometry_case(
        tmp_path
    )
    request["profile"] = native.MATRIX_PROFILE
    video_source = admitted["view"]["sources"][0]
    audio_path = admitted["sourceRoot"] / "media/narration.wav"
    audio_path.write_bytes(b"verified narration source bytes")
    audio_hash = hashlib.sha256(audio_path.read_bytes()).hexdigest()
    audio_source = {
        **video_source,
        "id": "audio-one",
        "kind": "audio",
        "path": "media/narration.wav",
        "contentHash": audio_hash,
    }
    admitted["view"]["sources"].append(audio_source)
    admitted["view"]["tracks"] = [
        {"id": "video-main", "kind": "video", "index": 1, "name": "V1"},
        {"id": "audio-main", "kind": "audio", "index": 1, "name": "A1"},
    ]

    def event(
        event_id: str,
        kind: str,
        source_id: str,
        track_id: str,
        record_start: int,
        record_duration: int,
        source_start: int,
        source_duration: int,
    ) -> dict[str, Any]:
        row: dict[str, Any] = {
            "id": event_id,
            "kind": kind,
            "trackId": track_id,
            "trackKind": "audio" if track_id == "audio-main" else "video",
            "sourceId": source_id,
            "recordRange": {
                "startFrame": record_start,
                "durationFrames": record_duration,
            },
            "sourceRange": {
                "startFrame": source_start,
                "durationFrames": source_duration,
            },
            "v2Event": {"id": event_id, "description": "linked AV trim"},
        }
        if kind == "source_audio":
            row["gainDb"] = -6.0
        return row

    audio = event("audio", "source_audio", "audio-one", "audio-main", 0, 6, 10, 6)
    picture = event(
        "picture", "primary_visual", "picture-one", "video-main", 0, 6, 20, 6
    )
    downstream_audio = event(
        "downstream-audio", "source_audio", "audio-one", "audio-main", 6, 4, 16, 4
    )
    downstream_picture = event(
        "downstream-picture",
        "primary_visual",
        "picture-one",
        "video-main",
        6,
        4,
        26,
        4,
    )
    events = [audio, picture, downstream_audio, downstream_picture]
    admitted["view"]["events"] = events

    video_media = video_first.media
    audio_media: Any = fixtures._Media(audio_path)
    audio_media.GetUniqueId = lambda: "media-audio"
    video_first = _set_item(
        video_first,
        uid="video-first",
        stamp=native._event_stamp(picture),
        start=0,
        duration=4,
        source_start=20,
        source_end=24,
    )
    audio_first = _set_item(
        fixtures._Item(audio_media, native._event_stamp(audio)),
        uid="audio-first",
        stamp=native._event_stamp(audio),
        start=0,
        duration=4,
        source_start=10,
        source_end=14,
    )
    video_downstream = _set_item(
        fixtures._Item(video_media, native._event_stamp(downstream_picture)),
        uid="video-downstream",
        stamp=native._event_stamp(downstream_picture),
        start=4,
        duration=4,
        source_start=26,
        source_end=30,
    )
    audio_downstream = _set_item(
        fixtures._Item(audio_media, native._event_stamp(downstream_audio)),
        uid="audio-downstream",
        stamp=native._event_stamp(downstream_audio),
        start=4,
        duration=4,
        source_start=16,
        source_end=20,
    )
    video_first.GetLinkedItems = lambda: [audio_first]
    audio_first.GetLinkedItems = lambda: [video_first]
    video_downstream.GetLinkedItems = lambda: [audio_downstream]
    audio_downstream.GetLinkedItems = lambda: [video_downstream]

    frame_seconds = 1001 / 24000
    for item, start, end in (
        (audio_first, 10, 14),
        (audio_downstream, 16, 20),
    ):
        item.GetSourceStartTime = lambda start=start: start * frame_seconds
        item.GetSourceEndTime = lambda end=end: end * frame_seconds

    timeline_items = {
        "video": [video_first, video_downstream],
        "audio": [audio_first, audio_downstream],
    }
    timeline_any: Any = timeline
    timeline_any.GetTrackCount = lambda kind: 1 if kind in timeline_items else 0
    timeline_any.GetTrackName = lambda kind, _index: "V1" if kind == "video" else "A1"
    timeline_any.GetIsTrackEnabled = lambda _kind, _index: True
    timeline_any.GetIsTrackLocked = lambda _kind, _index: False
    timeline_any.GetItemListInTrack = lambda kind, _index: timeline_items[kind]
    timeline_any.GetEndFrame = lambda: 8
    request["context"] = _edited_context(request["context"])
    return request, admitted, resolve


def test_edited_phase_selects_static_observation_route_and_strict_phase_stays_strict(
    tmp_path: Path,
) -> None:
    request, raw = fixtures._native_request(tmp_path, native.SYNTHETIC_PROFILE)
    assert (
        native.action_plan_for_context(request["context"])
        == native.APPROVAL_ACTION_PLAN
    )
    assert native.action_plan_for_context(_edited_context(request["context"])) == (
        native.OBSERVED_ACTION_PLAN
    )

    request["context"] = _edited_context(request["context"])
    request["action"] = "observe_edited"
    raw = _canonical(request)
    checked = native.verify_native_request(
        raw,
        expected_request_sha256=hashlib.sha256(raw).hexdigest(),
        current=False,
    )
    assert native.native_action(checked["context"], 0) == "observe_edited"
    assert [
        native.native_action(checked["context"], sequence)
        for sequence in range(len(native.OBSERVED_ACTION_PLAN))
    ] == list(native.OBSERVED_ACTION_PLAN)
    with pytest.raises(OutputConsistencyError, match="native action plan is exhausted"):
        native.native_action(checked["context"], len(native.OBSERVED_ACTION_PLAN))

    request["action"] = "construct"
    raw = _canonical(request)
    with pytest.raises(OutputConsistencyError, match="native action order differs"):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=False,
        )

    request["sequence"] = len(native.OBSERVED_ACTION_PLAN)
    request["action"] = "retry_capture"
    raw = _canonical(request)
    with pytest.raises(OutputConsistencyError, match="native action order differs"):
        native.verify_native_request(
            raw,
            expected_request_sha256=hashlib.sha256(raw).hexdigest(),
            current=False,
        )


def test_operator_approval_accepts_only_the_static_edited_plan(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", tmp_path.resolve() / "native")
    approval, pristine_context = fixtures._approval(
        tmp_path, profile=native.R16_PROFILE
    )
    context = _edited_context(pristine_context)
    approval["context"] = context
    approval["actionPlan"] = list(native.OBSERVED_ACTION_PLAN)
    target_key = {
        "projectUid": context["target"]["projectUid"],
        "timelineUid": context["target"]["timelineUid"],
        "caseId": context["caseId"],
        "phase": context["phase"],
    }
    approval["outputPath"] = str(
        native.NATIVE_STATE_ROOT
        / "renders"
        / native._hash(_canonical(target_key))
        / "approved.mov"
    )

    checked = native.verify_operator_approval(
        _canonical(approval),
        context=context,
        profile=native.R16_PROFILE,
        admission_sha256=approval["admissionSha256"],
        release_manifest_sha256=approval["releaseManifestSha256"],
        require_live=False,
        require_output_absent=False,
    )
    assert checked["actionPlan"] == list(native.OBSERVED_ACTION_PLAN)

    approval["actionPlan"] = list(native.APPROVAL_ACTION_PLAN)
    with pytest.raises(OutputConsistencyError, match="approval action plan differs"):
        native.verify_operator_approval(
            _canonical(approval),
            context=context,
            profile=native.R16_PROFILE,
            admission_sha256=approval["admissionSha256"],
            release_manifest_sha256=approval["releaseManifestSha256"],
            require_live=False,
            require_output_absent=False,
        )


def test_observed_held_picture_boundary_transfer_accepts_and_strict_capture_refuses(
    tmp_path: Path,
) -> None:
    request, admitted, resolve, _timeline, items = _held_picture_boundary_case(tmp_path)
    with pytest.raises(OutputConsistencyError, match="native record range differs"):
        native._capture_geometry(resolve, request, admitted, None)

    request["context"] = _edited_context(request["context"])
    geometry = native._capture_observed_geometry(resolve, request, admitted, None)
    assert geometry["extentFrames"] == 10
    assert [
        (item["recordStart"], item["recordDuration"], item["sourceDuration"])
        for item in geometry["items"]
    ] == [(0, 6, 6), (6, 4, 4)]
    assert [item.GetLinkedItems() for item in items] == [[], []]


def test_observed_held_picture_transfer_normalizes_nonzero_still_counter_by_time(
    tmp_path: Path,
) -> None:
    request, admitted, resolve, _timeline, items = _held_picture_boundary_case(tmp_path)
    for item in items:
        item.GetSourceStartFrame = lambda: 86
        item.GetSourceEndFrame = lambda: 86
        item.GetSourceStartTime = lambda: 0.0
        item.GetSourceEndTime = lambda: 1001 / 24000

    request["context"] = _edited_context(request["context"])
    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    assert [
        (item["sourceStart"], item["sourceDuration"]) for item in geometry["items"]
    ] == [(0, 6), (0, 4)]


def test_observed_held_picture_transfer_rejects_nonadjacent_boundary(
    tmp_path: Path,
) -> None:
    request, admitted, resolve, timeline, items = _held_picture_boundary_case(tmp_path)
    right = items[1]
    right.GetStart = lambda _in_frames: 7
    right.GetDuration = lambda _in_frames: 3
    right.GetEnd = lambda _in_frames: 10
    _set_inventory(timeline, list(items), 10)
    request["context"] = _edited_context(request["context"])
    with pytest.raises(
        OutputConsistencyError,
        match="adjacent hold transfer",
    ):
        native._capture_observed_geometry(resolve, request, admitted, None)


@pytest.mark.parametrize("end_error", [0.0, 0.001])
def test_matrix_observed_narration_split_requires_sample_aligned_audio_edges(
    tmp_path: Path, end_error: float
) -> None:
    resolve, request, admitted, first, timeline = fixtures._geometry_case(
        tmp_path, source_audio=True
    )
    event = admitted["view"]["events"][0]
    event["kind"] = "narration"
    event["v2Event"] = {"id": "narration-one", "description": "split narration"}
    first = _set_item(
        first,
        uid="narration-a",
        stamp=native._event_stamp(event),
        start=0,
        duration=4,
        source_start=12,
        source_end=16,
    )
    second = _set_item(
        fixtures._Item(first.media, native._event_stamp(event)),
        uid="narration-b",
        stamp=native._event_stamp(event),
        start=6,
        duration=4,
        source_start=18,
        source_end=22,
    )
    request["profile"] = native.MATRIX_PROFILE
    frame_seconds = 1001 / 24000
    first.GetSourceStartTime = lambda: 12 * frame_seconds
    first.GetSourceEndTime = lambda: 16 * frame_seconds
    second.GetSourceStartTime = lambda: 18 * frame_seconds
    second.GetSourceEndTime = lambda: 22 * frame_seconds + end_error
    _set_inventory(timeline, [first, second], 10)
    request["context"] = _edited_context(request["context"])

    if end_error:
        with pytest.raises(
            OutputConsistencyError,
            match="edited audio source range lacks sample-accurate edges",
        ):
            native._capture_observed_geometry(resolve, request, admitted, None)
        return

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    assert [
        (
            item["recordStart"],
            item["recordDuration"],
            item["sourceStart"],
            item["sourceDuration"],
        )
        for item in geometry["items"]
    ] == [(0, 4, 12, 4), (6, 4, 18, 4)]


def test_matrix_observed_linked_av_trim_captures_exclusive_audio_ends(
    tmp_path: Path,
) -> None:
    request, admitted, resolve = _matrix_av_trim_case(tmp_path)

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)

    items = {item["eventId"]: item for item in geometry["items"]}
    assert (
        max(item["recordStart"] + item["recordDuration"] for item in geometry["items"])
        == 8
    )
    assert (items["audio"]["recordDuration"], items["audio"]["sourceDuration"]) == (
        4,
        4,
    )
    assert (
        items["downstream-audio"]["recordStart"],
        items["downstream-audio"]["sourceDuration"],
    ) == (4, 4)


@pytest.mark.parametrize(
    ("event_kind", "second_start", "second_source_start", "uid"),
    [
        ("source_audio", 6, 18, "narration-b"),
        ("narration", 6, 17, "narration-b"),
        ("narration", 3, 15, "narration-b"),
        ("narration", 6, 18, "narration-a"),
    ],
)
def test_observed_split_rejects_wrong_kind_nonaffine_overlap_and_duplicate_uid(
    tmp_path: Path,
    event_kind: str,
    second_start: int,
    second_source_start: int,
    uid: str,
) -> None:
    resolve, request, admitted, first, timeline = fixtures._geometry_case(
        tmp_path, source_audio=True
    )
    event = admitted["view"]["events"][0]
    event["kind"] = event_kind
    event["v2Event"] = {"id": "narration-one", "description": "split narration"}
    first = _set_item(
        first,
        uid="narration-a",
        stamp=native._event_stamp(event),
        start=0,
        duration=4,
        source_start=12,
        source_end=15,
    )
    second = _set_item(
        fixtures._Item(first.media, native._event_stamp(event)),
        uid=uid,
        stamp=native._event_stamp(event),
        start=second_start,
        duration=4,
        source_start=second_source_start,
        source_end=second_source_start + 3,
    )
    _set_inventory(timeline, [first, second], 10)
    request["context"] = _edited_context(request["context"])

    with pytest.raises(OutputConsistencyError):
        native._capture_observed_geometry(resolve, request, admitted, None)


def test_observed_geometry_rejects_unknown_media_path(tmp_path: Path) -> None:
    resolve, request, admitted, item, _timeline = fixtures._geometry_case(tmp_path)
    outside = tmp_path / "unadmitted.mov"
    outside.write_bytes(b"unadmitted media")
    item.media.path = outside
    request["context"] = _edited_context(request["context"])

    with pytest.raises(OutputConsistencyError, match="outside the admitted package"):
        native._capture_observed_geometry(resolve, request, admitted, None)


def test_observed_linked_av_end_trim_ripples_downstream_by_exact_delta() -> None:
    events = {
        "audio": {
            "id": "audio",
            "kind": "source_audio",
            "sourceId": "audio-source",
            "recordRange": {"startFrame": 0, "durationFrames": 6},
            "sourceRange": {"startFrame": 10, "durationFrames": 6},
        },
        "picture": {
            "id": "picture",
            "kind": "primary_visual",
            "sourceId": "picture-source",
            "recordRange": {"startFrame": 0, "durationFrames": 6},
            "sourceRange": {"startFrame": 20, "durationFrames": 6},
        },
        "downstream-audio": {
            "id": "downstream-audio",
            "kind": "source_audio",
            "sourceId": "audio-source",
            "recordRange": {"startFrame": 6, "durationFrames": 4},
            "sourceRange": {"startFrame": 16, "durationFrames": 4},
        },
        "downstream-picture": {
            "id": "downstream-picture",
            "kind": "primary_visual",
            "sourceId": "picture-source",
            "recordRange": {"startFrame": 6, "durationFrames": 4},
            "sourceRange": {"startFrame": 26, "durationFrames": 4},
        },
    }
    items = [
        {
            "itemUid": "a-audio",
            "eventId": "audio",
            "kind": "audio",
            "recordStart": 0,
            "recordDuration": 4,
            "sourceStart": 10,
            "sourceDuration": 4,
        },
        {
            "itemUid": "v-picture",
            "eventId": "picture",
            "kind": "video",
            "recordStart": 0,
            "recordDuration": 4,
            "sourceStart": 20,
            "sourceDuration": 4,
        },
        {
            "itemUid": "a-downstream",
            "eventId": "downstream-audio",
            "kind": "audio",
            "recordStart": 4,
            "recordDuration": 4,
            "sourceStart": 16,
            "sourceDuration": 4,
        },
        {
            "itemUid": "v-downstream",
            "eventId": "downstream-picture",
            "kind": "video",
            "recordStart": 4,
            "recordDuration": 4,
            "sourceStart": 26,
            "sourceDuration": 4,
        },
    ]
    raw_links = {
        "a-audio": ["v-picture"],
        "v-picture": ["a-audio"],
        "a-downstream": ["v-downstream"],
        "v-downstream": ["a-downstream"],
    }

    native._validate_observed_event_geometry(
        events,
        items,
        {
            "audio-source": {"kind": "audio"},
            "picture-source": {"kind": "video"},
        },
        raw_links,
        timeline_end=8,
        expected_end=10,
    )


def _edited_queue_render_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *, mark_out: int
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    project, request, state, _observations = fixtures._queue_render_case(
        tmp_path, monkeypatch
    )
    settings = request["payload"]["settings"]
    settings.update({"startFrame": 0, "endFrame": 9})
    request["context"] = {"phase": "edited"}
    request["profile"] = native.MATRIX_PROFILE
    pre_capture = {
        "inputBindingPath": str(tmp_path.resolve() / "input-binding.json"),
        "inputBindingSha256": "b" * 64,
        "nativeGeometry": {"items": []},
    }
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: (pre_capture, "c" * 64, tmp_path.resolve() / "capture.json"),
    )
    monkeypatch.setattr(
        native, "_input_binding", lambda *_args: ({}, None, "b" * 64, None)
    )
    monkeypatch.setattr(
        native,
        "_capture_observed_geometry",
        lambda *_args: pre_capture["nativeGeometry"],
    )
    add_render_job = project.AddRenderJob

    def add_job_with_reported_marks() -> str:
        job_id = add_render_job()
        project.jobs[-1]["MarkIn"] = settings["startFrame"]
        project.jobs[-1]["MarkOut"] = mark_out
        return str(job_id)

    project.AddRenderJob = add_job_with_reported_marks
    return project, request, state


@pytest.mark.parametrize(("mark_out", "accepted"), [(9, True), (8, False)])
def test_edited_queue_checks_reported_render_mark_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mark_out: int,
    accepted: bool,
) -> None:
    project, request, state = _edited_queue_render_case(
        tmp_path, monkeypatch, mark_out=mark_out
    )
    admitted = {
        "manifest": {
            "timeline": {
                "width": 1920,
                "height": 1080,
                "frameRate": {"numerator": 24000, "denominator": 1001},
            }
        }
    }

    if accepted:
        native._queue_render(request, object(), admitted, state, None)
        assert project.jobs[0]["MarkOut"] == request["payload"]["settings"]["endFrame"]
    else:
        with pytest.raises(
            OutputConsistencyError,
            match="queued render job mark range differs from the edited render extent",
        ):
            native._queue_render(request, object(), admitted, state, None)


def _edited_start_render_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    include_marks: bool,
    mark_out: int = 9,
) -> tuple[Any, dict[str, Any], dict[str, Any]]:
    project, state, request = fixtures._start_render_case(
        tmp_path, monkeypatch, {"JobStatus": "Ready"}
    )
    request["context"]["phase"] = "edited"
    previous = {
        "jobId": "job-one",
        "outputPath": str(tmp_path.resolve() / "deliver.mov"),
        "settings": {"startFrame": 0, "endFrame": 9},
        "commitmentRawSha256": "1" * 64,
        "renderIntentSha256": "2" * 64,
    }
    queued_sha = request["payload"]["queuedResultSha256"]
    queued_path = Path(request["payload"]["queuedResultPath"])
    monkeypatch.setattr(
        native,
        "_previous_result",
        lambda *_args: (previous, queued_sha, queued_path),
    )
    job: dict[str, Any] = {"JobId": "job-one"}
    if include_marks:
        job.update({"MarkIn": 0, "MarkOut": mark_out})
    project.GetRenderJobList = lambda: [job]
    return project, state, request


def test_edited_start_refuses_changed_reported_render_mark_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, state, request = _edited_start_render_case(
        tmp_path, monkeypatch, include_marks=True, mark_out=8
    )

    with pytest.raises(
        OutputConsistencyError,
        match="queued render job mark range differs from the edited render extent",
    ):
        native._start_render(request, object(), state, None)

    assert project.status_calls == []
    assert project.start_calls == []


def test_edited_start_keeps_mark_check_optional_when_api_omits_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, state, request = _edited_start_render_case(
        tmp_path, monkeypatch, include_marks=False
    )

    native._start_render(request, object(), state, None)

    assert project.status_calls == ["job-one"]
    assert project.start_calls == [["job-one"]]
