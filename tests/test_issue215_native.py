"""Bounded native observations for the qualification-output edited route."""

from __future__ import annotations

import copy
import hashlib
from fractions import Fraction
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
) -> tuple[dict[str, Any], dict[str, Any], Any, Any, Any]:
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
    return request, admitted, resolve, audio_first, audio_downstream


def _constructor_av_view() -> dict[str, Any]:
    sources: list[dict[str, Any]] = []
    events = []
    for block, start, duration in (("a", 0, 91), ("b", 91, 48)):
        authored_source_id = f"video-source-{block}"
        delivered_hash = f"sha256:{block * 64}"
        source_ids = {"source_audio": f"audio-source-{block}"}
        source_ids["primary_visual"] = f"video-source-{block}"
        sources.extend(
            [
                {
                    "id": source_ids["source_audio"],
                    "contentHash": f"sha256:{('c' if block == 'a' else 'd') * 64}",
                },
                {
                    "id": source_ids["primary_visual"],
                    "contentHash": delivered_hash,
                },
            ]
        )
        for kind, suffix in (("source_audio", "audio"), ("primary_visual", "visual")):
            event_id = f"{block}-{suffix}"
            events.append(
                {
                    "id": event_id,
                    "kind": kind,
                    "sourceId": source_ids[kind],
                    "recordRange": {
                        "startFrame": start,
                        "durationFrames": duration,
                    },
                    "v2Event": {
                        "id": event_id,
                        "provenance": {
                            "documentId": "document-one",
                            "blockId": f"block-{block}",
                            "payloadId": f"payload-{block}",
                            "sourceId": authored_source_id,
                            "deliveredSourceHash": delivered_hash,
                            "sequenceId": None,
                            "slotId": None,
                            "overlayEventId": None,
                        },
                    },
                }
            )
    return {"sources": sources, "events": events}


def test_constructor_pairs_only_same_authored_av_occurrences_and_admitted_sources(
    tmp_path: Path,
) -> None:
    view = _constructor_av_view()

    assert set(native._constructor_av_link_pairs(view, native.MATRIX_PROFILE)) == {
        ("a-visual", "a-audio"),
        ("b-visual", "b-audio"),
    }
    assert native._constructor_av_link_pairs(view, native.SYNTHETIC_PROFILE) == []
    assert native._constructor_av_link_pairs(view, native.R16_PROFILE) == []
    state, request = fixtures._effect_state(tmp_path)
    request.update(action="construct", profile=native.SYNTHETIC_PROFILE)
    with pytest.raises(OutputConsistencyError, match="limited to MATRIX/PRESENTER"):
        native._private_effect(state, "Timeline.SetClipsLinked", {})
    assert state["effects"] == []

    unrelated = copy.deepcopy(view)
    unrelated["events"][1]["v2Event"]["provenance"]["blockId"] = "other-block"
    assert native._constructor_av_link_pairs(unrelated, native.MATRIX_PROFILE) == [
        ("b-visual", "b-audio")
    ]

    missing_source = copy.deepcopy(view)
    missing_source["sources"] = [
        source
        for source in missing_source["sources"]
        if source["id"] != "audio-source-a"
    ]
    assert native._constructor_av_link_pairs(missing_source, native.MATRIX_PROFILE) == [
        ("b-visual", "b-audio")
    ]

    changed_authored_source = copy.deepcopy(view)
    changed_authored_source["events"][0]["v2Event"]["provenance"]["sourceId"] = (
        "other-authored-source"
    )
    assert native._constructor_av_link_pairs(
        changed_authored_source, native.MATRIX_PROFILE
    ) == [("b-visual", "b-audio")]

    changed_delivered_hash = copy.deepcopy(view)
    changed_delivered_hash["events"][0]["v2Event"]["provenance"][
        "deliveredSourceHash"
    ] = "sha256:" + "e" * 64
    assert native._constructor_av_link_pairs(
        changed_delivered_hash, native.MATRIX_PROFILE
    ) == [("b-visual", "b-audio")]

    changed_geometry = copy.deepcopy(view)
    changed_geometry["events"][0]["recordRange"]["durationFrames"] = 90
    assert native._constructor_av_link_pairs(
        changed_geometry, native.MATRIX_PROFILE
    ) == [("b-visual", "b-audio")]


def test_constructor_av_link_refuses_ambiguous_authored_pair_before_effects(
    tmp_path: Path,
) -> None:
    view = _constructor_av_view()
    duplicate = copy.deepcopy(view["events"][0])
    duplicate["id"] = duplicate["v2Event"]["id"] = "a-audio-duplicate"
    view["events"].append(duplicate)
    state, _request = fixtures._effect_state(tmp_path)

    with pytest.raises(OutputConsistencyError, match="ambiguous qualification"):
        native._constructor_av_link_pairs(view, native.MATRIX_PROFILE)

    assert state["effects"] == []


def test_constructor_av_link_journals_each_exact_pair_and_reads_back_reciprocal_links(
    tmp_path: Path,
) -> None:
    class Item:
        def __init__(self, uid: str) -> None:
            self.uid = uid
            self.links: list[Item] = []

        def GetUniqueId(self) -> str:
            return self.uid

        def GetLinkedItems(self) -> list[Item]:
            return self.links

    class Timeline:
        def __init__(self) -> None:
            self.calls: list[list[str]] = []

        def SetClipsLinked(self, items: list[Item], linked: bool) -> bool:
            assert linked is True
            self.calls.append([item.uid for item in items])
            items[0].links = [items[1]]
            items[1].links = [items[0]]
            return True

    pairs = native._constructor_av_link_pairs(
        _constructor_av_view(), native.MATRIX_PROFILE
    )
    items = {
        event_id: Item(f"native-{event_id}") for pair in pairs for event_id in pair
    }
    timeline = Timeline()
    state, _request = fixtures._effect_state(tmp_path)
    state["request"].update(action="construct", profile=native.MATRIX_PROFILE)

    native._link_constructed_av_pairs(timeline, pairs, items, state)

    assert timeline.calls == [
        [items[visual].uid, items[audio].uid] for visual, audio in pairs
    ]
    assert [row["method"] for row in state["effects"]] == [
        "Timeline.SetClipsLinked",
        "Timeline.SetClipsLinked",
    ]
    assert all(row["outcome"] == "observed" for row in state["effects"])


@pytest.mark.parametrize(
    ("returned", "partial"), [(False, False), (None, False), (True, True)]
)
def test_constructor_av_link_keeps_failed_or_partial_call_uncertain_without_retry(
    tmp_path: Path, returned: Any, partial: bool
) -> None:
    class Item:
        def __init__(self, uid: str) -> None:
            self.uid = uid
            self.links: list[Item] = []

        def GetUniqueId(self) -> str:
            return self.uid

        def GetLinkedItems(self) -> list[Item]:
            return self.links

    class Timeline:
        def __init__(self) -> None:
            self.calls = 0

        def SetClipsLinked(self, items: list[Item], linked: bool) -> Any:
            self.calls += 1
            assert linked is True
            items[0].links = [items[1]]
            if not partial and returned is True:
                items[1].links = [items[0]]
            return returned

    pairs = [("visual", "audio")]
    items = {
        event_id: Item(f"native-{event_id}") for pair in pairs for event_id in pair
    }
    timeline = Timeline()
    state, _request = fixtures._effect_state(tmp_path)
    state["request"].update(action="construct", profile=native.MATRIX_PROFILE)

    with pytest.raises(OutputConsistencyError):
        native._link_constructed_av_pairs(timeline, pairs, items, state)

    assert timeline.calls == 1
    assert len(state["effects"]) == 1
    assert state["effects"][0]["method"] == "Timeline.SetClipsLinked"
    assert state["effects"][0]["outcome"] == "unknown"
    assert native._failed_stage_status(state["effects"]) == "uncertain"
    with pytest.raises(
        OutputConsistencyError, match="outside its fixed constructor scope"
    ):
        native._verify_effect_ledger(
            {
                "effectLedger": state["effects"],
                "profile": native.SYNTHETIC_PROFILE,
                "action": "construct",
            }
        )
    observed = Path(state["effects"][0]["path"]).with_name("0000-observed.json")
    assert observed.exists() is (returned is True and not partial)


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
        ) as refused:
            native._capture_observed_geometry(resolve, request, admitted, None)
        reason = str(refused.value)
        assert "sourceFrames=(18,22)" in reason
        assert "GetSourceStartTime" in reason and "GetSourceEndTime" in reason
        assert "sampleErrors=" in reason and "toleranceSamples=1" in reason
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
    request, admitted, resolve, _audio_first, _audio_downstream = _matrix_av_trim_case(
        tmp_path
    )

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
    ("inclusive_end_sample_error", "refuse"),
    [(Fraction(0), False), (Fraction(1, 48_000), False), (Fraction(24, 48_000), True)],
)
def test_matrix_observed_av_trim_validates_mixed_audio_endpoints_with_sample_tolerance(
    tmp_path: Path, inclusive_end_sample_error: Fraction, refuse: bool
) -> None:
    request, admitted, resolve, audio_first, audio_downstream = _matrix_av_trim_case(
        tmp_path
    )
    # The trimmed clip reports an exclusive end. The shifted downstream WAV
    # ends at its 20-frame EOF, where Resolve reports the final included frame.
    audio_downstream.media.frame_count = 20
    audio_downstream.GetSourceEndFrame = lambda: 19
    end_time = Fraction(20 * 1001, 24_000) + inclusive_end_sample_error
    audio_downstream.GetSourceEndTime = lambda: float(end_time)

    if refuse:
        with pytest.raises(
            OutputConsistencyError,
            match="edited audio source range lacks sample-accurate edges",
        ) as refused:
            native._capture_observed_geometry(resolve, request, admitted, None)
        reason = str(refused.value)
        assert "sourceFrames=(16,19)" in reason
        assert "GetSourceStartTime" in reason and "GetSourceEndTime" in reason
        assert "sampleErrors=" in reason and "toleranceSamples=1" in reason
        return

    geometry = native._capture_observed_geometry(resolve, request, admitted, None)
    items = {item["eventId"]: item for item in geometry["items"]}
    assert (
        items["audio"]["sourceDuration"],
        items["downstream-audio"]["sourceDuration"],
    ) == (4, 4)
    assert audio_first.GetSourceEndFrame() == 14


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

    trim = native._validate_observed_event_geometry(
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
    # #260: the authenticated ripple trim is the only programme shortening.
    assert trim == 2


def _b_linked_av_ripple_case() -> tuple[
    dict[str, dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, Any]],
    dict[str, list[str]],
]:
    events: dict[str, dict[str, Any]] = {}
    items: list[dict[str, Any]] = []
    sources: dict[str, dict[str, Any]] = {}

    def add(
        event_id: str,
        event_kind: str,
        source_id: str,
        source_kind: str,
        track_id: str,
        start: int,
        duration: int,
        source_start: int,
        observed_start: int,
        observed_duration: int | None = None,
    ) -> None:
        observed_duration = duration if observed_duration is None else observed_duration
        events[event_id] = {
            "id": event_id,
            "kind": event_kind,
            "sourceId": source_id,
            "trackId": track_id,
            "recordRange": {"startFrame": start, "durationFrames": duration},
            "sourceRange": {"startFrame": source_start, "durationFrames": duration},
        }
        sources.setdefault(source_id, {"kind": source_kind})
        items.append(
            {
                "itemUid": f"native-{event_id}",
                "eventId": event_id,
                "kind": "audio"
                if event_kind in {"narration", "source_audio"}
                else "video",
                "recordStart": observed_start,
                "recordDuration": observed_duration,
                "sourceStart": source_start,
                "sourceDuration": observed_duration,
            }
        )

    add(
        "9b19fa0d-3bf7-50f5-8a53-3db459c9469d",
        "primary_visual",
        "9ab8485e-0d6f-5e47-8b3d-94ae34eca7f4",
        "video",
        "primary-root",
        143,
        111,
        5809,
        143,
        87,
    )
    add(
        "fbb405b6-c62d-5af7-8f0d-d3ee050379f7",
        "source_audio",
        "9ab8485e-0d6f-5e47-8b3d-94ae34eca7f4",
        "video",
        "source-audio",
        143,
        111,
        0,
        143,
        87,
    )
    add(
        "55752ec4-3554-5df9-8630-de6ab7ba3b04",
        "placeholder",
        "55752ec4-3554-5df9-8630-de6ab7ba3b04",
        "still",
        "primary-root",
        254,
        122,
        0,
        230,
    )
    add(
        "7299c32b-6bb5-51ec-8b91-6d3b84ae4fe6",
        "narration",
        "cdc8267a-6c99-5f69-a204-f894a3e92fbf",
        "audio",
        "narration",
        254,
        610,
        0,
        230,
    )
    add(
        "6bcba16b-aa83-5880-8321-0512a2084a89",
        "placeholder",
        "6bcba16b-aa83-5880-8321-0512a2084a89",
        "still",
        "primary-root",
        517,
        148,
        0,
        493,
    )
    add(
        "f6a3c354-a235-5083-8cd1-9e885b04cf77",
        "placeholder",
        "f6a3c354-a235-5083-8cd1-9e885b04cf77",
        "still",
        "primary-root",
        764,
        100,
        0,
        740,
    )
    raw_links: dict[str, list[str]] = {item["itemUid"]: [] for item in items}
    visual_uid = "native-9b19fa0d-3bf7-50f5-8a53-3db459c9469d"
    audio_uid = "native-fbb405b6-c62d-5af7-8f0d-d3ee050379f7"
    raw_links[visual_uid] = [audio_uid]
    raw_links[audio_uid] = [visual_uid]
    return events, items, sources, raw_links


def test_observed_linked_av_ripple_accepts_b_narration_and_static_pictures() -> None:
    events, items, sources, raw_links = _b_linked_av_ripple_case()

    trim = native._validate_observed_event_geometry(
        events,
        items,
        sources,
        raw_links,
        timeline_end=995,
        expected_end=1019,
    )

    assert trim == 24


@pytest.mark.parametrize(
    ("event_kind", "source_kind", "duration"),
    [("narration", "audio", 610), ("placeholder", "still", 122)],
)
def test_observed_unchanged_earlier_shift_still_requires_linked_av_trim(
    event_kind: str, source_kind: str, duration: int
) -> None:
    event_id = f"shifted-{event_kind}"
    source_id = f"{event_kind}-source"
    events = {
        event_id: {
            "id": event_id,
            "kind": event_kind,
            "sourceId": source_id,
            "recordRange": {"startFrame": 254, "durationFrames": duration},
            "sourceRange": {"startFrame": 0, "durationFrames": duration},
        }
    }
    items = [
        {
            "itemUid": "shifted-item",
            "eventId": event_id,
            "kind": "audio" if event_kind == "narration" else "video",
            "recordStart": 230,
            "recordDuration": duration,
            "sourceStart": 0,
            "sourceDuration": duration,
        }
    ]

    with pytest.raises(
        OutputConsistencyError,
        match="downstream shift is only admitted with a linked AV end trim",
    ):
        native._validate_observed_event_geometry(
            events,
            items,
            {source_id: {"kind": source_kind}},
            {"shifted-item": []},
            timeline_end=995,
            expected_end=1019,
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ("source", "native edited item differs outside the observed edit rules"),
        (
            "duration",
            "observed edit multiplicity is outside the reviewed A/B/split cases",
        ),
        ("delta", "linked AV end trim has an unpaired or nonuniform downstream shift"),
    ],
)
def test_observed_b_ripple_still_refuses_changed_source_duration_or_delta(
    mutation: str, message: str
) -> None:
    events, items, sources, raw_links = _b_linked_av_ripple_case()
    item = next(
        row for row in items if row["eventId"] == "6bcba16b-aa83-5880-8321-0512a2084a89"
    )
    if mutation == "source":
        item["sourceStart"] = 1
    elif mutation == "duration":
        item["recordDuration"] -= 1
        item["sourceDuration"] -= 1
    else:
        narration = next(
            row
            for row in items
            if row["eventId"] == "7299c32b-6bb5-51ec-8b91-6d3b84ae4fe6"
        )
        narration["recordStart"] -= 1

    with pytest.raises(OutputConsistencyError, match=message):
        native._validate_observed_event_geometry(
            events,
            items,
            sources,
            raw_links,
            timeline_end=995,
            expected_end=1019,
        )


def _edited_queue_render_case(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    *,
    mark_out: int,
    extent: int = 10,
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
        "nativeGeometry": {"items": [], "extentFrames": extent},
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
    extent: int = 10,
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
    capture = {"action": "capture_pre", "nativeGeometry": {"extentFrames": extent}}
    monkeypatch.setattr(
        native,
        "_native_result_at",
        lambda _context, sequence: (tmp_path / f"{sequence}.json", "d" * 64, capture),
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


def _queue_admitted() -> dict[str, Any]:
    return {
        "manifest": {
            "timeline": {
                "width": 1920,
                "height": 1080,
                "frameRate": {"numerator": 24000, "denominator": 1001},
            }
        }
    }


@pytest.mark.parametrize(("mark_out", "accepted"), [(7, True), (9, False), (6, False)])
def test_shortened_edit_queues_marks_for_authenticated_extent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mark_out: int,
    accepted: bool,
) -> None:
    """#260: a 10-frame admitted interval trimmed by 2 queues 0..7, not 0..9.

    This reproduces the measured 139->115 clamp: Resolve reports the shortened
    MarkOut, which must equal the extent the native capture authenticated.
    """
    project, request, state = _edited_queue_render_case(
        tmp_path, monkeypatch, mark_out=mark_out, extent=8
    )
    if accepted:
        native._queue_render(request, object(), _queue_admitted(), state, None)
        assert (project.jobs[0]["MarkIn"], project.jobs[0]["MarkOut"]) == (0, 7)
    else:
        with pytest.raises(
            OutputConsistencyError,
            match="queued render job mark range differs from the edited render extent",
        ):
            native._queue_render(request, object(), _queue_admitted(), state, None)


def test_edited_extent_beyond_approved_interval_refuses_before_queueing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, request, state = _edited_queue_render_case(
        tmp_path, monkeypatch, mark_out=10, extent=11
    )
    with pytest.raises(
        OutputConsistencyError,
        match="edited render extent is outside the approved interval",
    ):
        native._queue_render(request, object(), _queue_admitted(), state, None)
    assert project.jobs == []


@pytest.mark.parametrize(("include_marks", "mark_out"), [(False, 7), (True, 9)])
def test_shortened_start_requires_its_reported_mark_range(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    include_marks: bool,
    mark_out: int,
) -> None:
    project, state, request = _edited_start_render_case(
        tmp_path, monkeypatch, include_marks=include_marks, mark_out=mark_out, extent=8
    )
    with pytest.raises(OutputConsistencyError, match="mark range"):
        native._start_render(request, object(), state, None)
    assert project.start_calls == []


def test_shortened_start_accepts_its_exact_reported_mark_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, state, request = _edited_start_render_case(
        tmp_path, monkeypatch, include_marks=True, mark_out=7, extent=8
    )
    native._start_render(request, object(), state, None)
    assert project.start_calls == [["job-one"]]


def test_shortened_queue_refuses_when_job_omits_its_mark_range(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project, request, state = _edited_queue_render_case(
        tmp_path, monkeypatch, mark_out=7, extent=8
    )
    add_with_marks = project.AddRenderJob

    def add_without_marks() -> str:
        job_id = add_with_marks()
        del project.jobs[-1]["MarkIn"], project.jobs[-1]["MarkOut"]
        return str(job_id)

    project.AddRenderJob = add_without_marks
    with pytest.raises(
        OutputConsistencyError,
        match="shortened render job does not report its mark range",
    ):
        native._queue_render(request, object(), _queue_admitted(), state, None)
