from __future__ import annotations

import copy
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.presenter_framing import (
    PresenterFramingAdapter,
    PresenterFramingError,
    PresenterFramingIntent,
    PresenterPictureTarget,
    ValidatedSourceTimeInterval,
    free_manual_handoff,
    validate_profile_snapshot,
)

FIXTURES = (
    Path(__file__).parents[1] / "packages/contracts/test/fixtures/presenter-framing"
)


def _fixture() -> tuple[dict[str, Any], dict[str, Any], bytes, dict[str, Any]]:
    profile_bytes = (FIXTURES / "profile.json").read_bytes()
    content_bytes = (FIXTURES / "profile-content.json").read_bytes()
    profile = json.loads(profile_bytes)
    content = json.loads(content_bytes)
    pin = {
        "id": profile["id"],
        "version": profile["version"],
        "profileHash": profile["profileHash"],
    }
    return profile, content, content_bytes, pin


class MockTimelineItem:
    def __init__(
        self,
        *,
        event_id: str,
        key: str,
        interval: ValidatedSourceTimeInterval,
        color: str | None,
        guard_count: Any,
        media_id: str,
        properties: Mapping[str, Any] | None = None,
        color_supported: bool = True,
        name_write_success: bool = True,
        name_retained: bool = True,
    ) -> None:
        self.markers = {
            0: {
                "name": f"OC {key.upper()} {event_id}",
                "color": color,
            }
        }
        self.name = f"Generated presenter {event_id}"
        self.clip_color = color
        self.color_supported = color_supported
        self.name_write_success = name_write_success
        self.name_retained = name_retained
        self.source_start = interval.start_frame
        self.source_end = interval.end_frame - 1
        self.uid = f"timeline-{event_id}"
        self.media = MockMediaItem(media_id)
        self.properties = dict(properties or {})
        self.set_calls: list[dict[str, Any]] = []
        self.guard_counts: list[int] = []
        self._guard_count = guard_count

    def GetMarkers(self) -> dict[int, dict[str, Any]]:
        return copy.deepcopy(self.markers)

    def GetName(self) -> str:
        return self.name

    def SetName(self, name: str) -> bool:
        self.guard_counts.append(self._guard_count())
        if self.name_write_success and self.name_retained:
            self.name = name
        return self.name_write_success

    def GetClipColor(self) -> str | None:
        return self.clip_color

    def SetClipColor(self, color: str) -> bool:
        self.guard_counts.append(self._guard_count())
        if self.color_supported:
            self.clip_color = color
        return self.color_supported

    def GetUniqueId(self) -> str:
        return self.uid

    def GetType(self) -> str:
        return "video"

    def GetMediaPoolItem(self) -> MockMediaItem:
        return self.media

    def GetSourceStartFrame(self) -> int:
        return self.source_start

    def GetSourceEndFrame(self) -> int:
        return self.source_end

    def SetProperties(self, properties: dict[str, Any]) -> bool:
        self.set_calls.append(copy.deepcopy(properties))
        self.guard_counts.append(self._guard_count())
        self.properties.update(properties)
        return True

    def GetProperties(self) -> dict[str, Any]:
        return copy.deepcopy(self.properties)

    def reopened(self) -> MockTimelineItem:
        clone = copy.copy(self)
        clone.markers = copy.deepcopy(self.markers)
        clone.name = self.name
        clone.clip_color = self.clip_color
        clone.properties = copy.deepcopy(self.properties)
        clone.guard_counts = []
        clone.set_calls = []
        clone.guard_counts = []
        return clone


class MockMediaItem:
    def __init__(self, media_id: str) -> None:
        self.media_id = media_id

    def GetMediaId(self) -> str:
        return self.media_id


def _target(
    event_id: str,
    key: str,
    interval: ValidatedSourceTimeInterval,
    guard_count: Any,
    *,
    color: str | None = None,
    color_supported: bool = True,
    name_write_success: bool = True,
    name_retained: bool = True,
    media_id_override: str | None = None,
    properties: Mapping[str, Any] | None = None,
) -> PresenterPictureTarget:
    media_id = (
        media_id_override if media_id_override is not None else f"media-{event_id}"
    )
    return PresenterPictureTarget(
        event_id,
        key,  # type: ignore[arg-type]
        interval,
        f"timeline-{event_id}",
        media_id,
        MockTimelineItem(
            event_id=event_id,
            key=key,
            interval=interval,
            color=color,
            guard_count=guard_count,
            media_id=media_id,
            color_supported=color_supported,
            name_write_success=name_write_success,
            name_retained=name_retained,
            properties=properties,
        ),
    )


def _adapter(
    profile: Mapping[str, Any],
    *,
    edition: str = "studio",
    guard_calls: list[str] | None = None,
) -> tuple[PresenterFramingAdapter, list[int]]:
    guard_count = [0]
    checks = guard_calls if guard_calls is not None else []

    def check_target() -> None:
        guard_count[0] += 1
        checks.append("current_target")

    adapter = PresenterFramingAdapter(
        current_target_check=check_target,
        context_reader=lambda: profile["context"],
        edition=edition,  # type: ignore[arg-type]
    )
    return adapter, guard_count


def _reopened_lookup(
    targets: tuple[PresenterPictureTarget, ...],
    *,
    mismatch: str | None = None,
    identity_mismatch: str | None = None,
    name_mismatch: str | None = None,
) -> Any:
    def lookup(event_ids: tuple[str, ...]) -> dict[str, MockTimelineItem]:
        assert event_ids == tuple(target.event_id for target in targets)
        result = {target.event_id: target.item.reopened() for target in targets}
        if mismatch is not None:
            result[mismatch].properties["ZoomX"] += 0.00000001
        if identity_mismatch is not None:
            result[identity_mismatch].media.media_id = "wrong-media-id"
        if name_mismatch is not None:
            result[name_mismatch].name = "unrelated clip name"
        return result

    return lookup


def _canonical_profile_content(content: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(content, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    ).encode("utf-8")


def test_profile_hash_uses_ts_bytes_and_returns_deep_copy() -> None:
    profile, _, content_bytes, pin = _fixture()
    original_file_bytes = (FIXTURES / "profile-content.json").read_bytes()

    verified = validate_profile_snapshot(
        profile,
        canonical_content_json=content_bytes.decode("utf-8"),
        expected_pin=pin,
    )
    verified["context"]["sourceRaster"]["width"] = 1

    assert profile["context"]["sourceRaster"]["width"] == 1920
    assert (FIXTURES / "profile-content.json").read_bytes() == original_file_bytes
    assert sha256_bytes(content_bytes) == pin["profileHash"]


def test_profile_hash_pin_context_and_decimal_values_block_before_mutation() -> None:
    profile, _, content_bytes, pin = _fixture()
    interval = ValidatedSourceTimeInterval(100, 125)
    adapter, _ = _adapter(profile)
    item = _target("wide-1", "wide", interval, lambda: 0)

    bad_hash = copy.deepcopy(profile)
    bad_hash["profileHash"] = "sha256:" + "0" * 64
    bad_pin = {**pin, "profileHash": bad_hash["profileHash"]}
    hash_result = adapter.apply(
        profile=bad_hash,
        canonical_content_json=content_bytes,
        expected_pin=bad_pin,
        targets=[item],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((item,)),
    )
    assert hash_result.status == "blocked"
    assert not item.item.set_calls

    wrong_context = copy.deepcopy(profile)
    wrong_context["context"]["timelineRaster"]["width"] += 1
    context_adapter, _ = _adapter(wrong_context)
    context_result = context_adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[item],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((item,)),
    )
    assert context_result.status == "blocked"
    assert not item.item.set_calls

    bad_number = copy.deepcopy(profile)
    bad_number["wide"]["Pan"] = float("inf")
    with pytest.raises(PresenterFramingError, match="finite"):
        validate_profile_snapshot(
            bad_number,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )
    assert not item.item.set_calls


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("context", "sourceRaster", "orientation"), "  "),
        (("context", "sourceRaster", "orientation"), " UNKNOWN "),
        (("context", "resolve", "apiContext"), "unspecified"),
        (("context", "adapter", "sourceIdentity"), "GuEsSeD"),
        (("context", "resolve", "version"), "N/A"),
    ],
)
def test_profile_rejects_blank_or_placeholder_context_strings(
    path: tuple[str, ...], value: str
) -> None:
    profile, _, content_bytes, pin = _fixture()
    node: Any = profile
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    with pytest.raises(PresenterFramingError, match=r"nonblank|placeholder"):
        validate_profile_snapshot(
            profile,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )


def test_profile_integers_use_safe_json_bounds_and_uuid_version_variant() -> None:
    profile, _, content_bytes, pin = _fixture()
    profile["context"]["sourceRaster"]["width"] = 9_007_199_254_740_992
    with pytest.raises(PresenterFramingError, match="positive integer"):
        validate_profile_snapshot(
            profile,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )
    with pytest.raises(PresenterFramingError, match="source-time interval"):
        ValidatedSourceTimeInterval(0, 9_007_199_254_740_992)

    profile, _, content_bytes, pin = _fixture()
    profile["version"] = 9_007_199_254_740_992
    pin["version"] = profile["version"]
    with pytest.raises(PresenterFramingError, match="positive integer"):
        validate_profile_snapshot(
            profile,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )

    for invalid_id in (
        "f646c9c0-5f84-6e78-b6cc-1ec11d47a946",
        "f646c9c0-5f84-4e78-06cc-1ec11d47a946",
    ):
        profile, _, content_bytes, pin = _fixture()
        profile["id"] = invalid_id
        with pytest.raises(PresenterFramingError, match="UUID"):
            validate_profile_snapshot(
                profile,
                canonical_content_json=content_bytes,
                expected_pin=pin,
            )

    profile, _, content_bytes, pin = _fixture()
    profile["id"] = profile["id"].upper()
    pin["id"] = profile["id"]
    assert (
        validate_profile_snapshot(
            profile,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )["id"]
        == profile["id"]
    )


def test_integral_json_floats_match_typescript_number_semantics() -> None:
    profile, _, content_bytes, pin = _fixture()
    profile["version"] = 3.0
    profile["context"]["sourceRaster"]["width"] = 1920.0
    profile["context"]["sourceRaster"]["pixelAspect"]["numerator"] = 1.0
    profile["invariants"]["RotationAngle"] = 0.0
    pin["version"] = 3

    assert (
        validate_profile_snapshot(
            profile,
            canonical_content_json=content_bytes,
            expected_pin=pin,
        )["version"]
        == 3.0
    )


def test_apply_is_target_only_exact_and_reports_missing_color_limitations() -> None:
    profile, _, content_bytes, pin = _fixture()
    guard_calls: list[str] = []
    adapter, guard_count = _adapter(profile, guard_calls=guard_calls)
    wide_interval = ValidatedSourceTimeInterval(100, 125)
    tight_interval = ValidatedSourceTimeInterval(125, 150)
    wide = _target("presenter-a", "wide", wide_interval, lambda: guard_count[0])
    tight = _target(
        "presenter-b",
        "tight",
        tight_interval,
        lambda: guard_count[0],
        color_supported=False,
    )
    broll = _target("broll-1", "wide", wide_interval, lambda: guard_count[0])
    dialogue = _target("dialogue-1", "wide", wide_interval, lambda: guard_count[0])
    targets = (wide, tight)
    saves: list[tuple[str, int]] = []

    result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=targets,
        save_close_reopen=lambda: saves.append(("save-reopen", guard_count[0])),
        lookup_reopened=_reopened_lookup(targets),
    )

    assert result.status == "applied_verified"
    assert result.event_ids == ("presenter-a", "presenter-b")
    assert result.color_limitations == (
        "presenter-b: tight clip color was not retained",
    )
    assert result.profile_pin == pin
    assert result.profile_pin is not pin
    assert saves == [("save-reopen", 8)]
    assert len(wide.item.set_calls) == len(tight.item.set_calls) == 1
    assert wide.item.name == "OC WIDE presenter-a"
    assert tight.item.name == "OC TIGHT presenter-b"
    assert wide.item.clip_color == "Blue"
    assert tight.item.clip_color is None
    assert wide.item.set_calls[0]["ZoomX"] == 1
    assert wide.item.set_calls[0]["Pan"] == 0.125
    assert wide.item.set_calls[0]["TransformEnabled"] is True
    assert tight.item.set_calls[0]["ZoomX"] == 1.35
    assert wide.item.guard_counts == [2, 3, 4]
    assert tight.item.guard_counts == [5, 6, 7]
    assert broll.item.set_calls == []
    assert dialogue.item.set_calls == []
    assert broll.item.name.startswith("Generated presenter")
    assert dialogue.item.name.startswith("Generated presenter")
    assert guard_calls.count("current_target") == 9

    result.profile_pin["version"] = 99
    assert pin["version"] == 3
    assert (FIXTURES / "profile-content.json").read_bytes() == content_bytes


def test_marker_only_name_or_wrong_source_identity_refuses_before_properties() -> None:
    profile, _, content_bytes, pin = _fixture()
    adapter, _ = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    target = _target("presenter-a", "wide", interval, lambda: 0)
    target.item.SetName = None
    target.item.markers = {0: {"name": "OC WIDE presenter-a", "color": "Blue"}}

    label_result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((target,)),
    )
    assert label_result.status == "blocked"
    assert not target.item.set_calls

    target = _target("presenter-a", "wide", interval, lambda: 0)
    target.item.source_end = 123
    interval_result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((target,)),
    )
    assert interval_result.status == "blocked"
    assert not target.item.set_calls

    target.item.source_end = interval.end_frame - 1
    target.item.media.media_id = "wrong-media-id"
    identity_result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((target,)),
    )
    assert identity_result.status == "blocked"
    assert "media identity differs" in identity_result.message
    assert not target.item.set_calls

    target = _target("presenter-a", "wide", interval, lambda: 0)
    target.item.GetType = lambda: "audio"
    type_result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((target,)),
    )
    assert type_result.status == "blocked"
    assert "item or media identity differs" in type_result.message
    assert not target.item.set_calls


def test_item_name_must_read_back_after_setter_and_after_reopen() -> None:
    profile, _, content_bytes, pin = _fixture()
    adapter, guard_count = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    unretained = _target(
        "presenter-a",
        "wide",
        interval,
        lambda: guard_count[0],
        name_retained=False,
    )
    immediate = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[unretained],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((unretained,)),
    )
    assert immediate.status == "pending"
    assert "authoritative item name differs" in immediate.message
    assert not unretained.item.set_calls

    reopened_target = _target("presenter-b", "tight", interval, lambda: guard_count[0])
    after_reopen = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[reopened_target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup(
            (reopened_target,), name_mismatch="presenter-b"
        ),
    )
    assert after_reopen.status == "pending"
    assert "authoritative item name differs" in after_reopen.message


def test_reopen_mismatch_stays_pending_and_never_claims_verified() -> None:
    profile, _, content_bytes, pin = _fixture()
    adapter, guard_count = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    target = _target("presenter-a", "wide", interval, lambda: guard_count[0])
    result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((target,), mismatch="presenter-a"),
    )
    assert result.status == "pending"
    assert "readback differs" in result.message
    assert result.observed_properties is None

    identity_target = _target("presenter-b", "wide", interval, lambda: guard_count[0])
    identity_result = adapter.apply(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        targets=[identity_target],
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup(
            (identity_target,), identity_mismatch="presenter-b"
        ),
    )
    assert identity_result.status == "pending"
    assert "media identity differs" in identity_result.message


def test_calibration_reads_both_raw_tuples_without_rewriting_prior() -> None:
    profile, content, _, _ = _fixture()
    prior_profile_bytes = (FIXTURES / "profile.json").read_bytes()
    prior_content_bytes = (FIXTURES / "profile-content.json").read_bytes()
    adapter, guard_count = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    wide = _target(
        "calibration-wide",
        "wide",
        interval,
        lambda: guard_count[0],
        media_id_override="shared-source",
    )
    tight = _target(
        "calibration-tight",
        "tight",
        interval,
        lambda: guard_count[0],
        media_id_override="shared-source",
    )
    transforms = copy.deepcopy(content)
    transforms["wide"]["Pan"] = 0.25

    calibration = adapter.calibrate_disposable_samples(
        is_disposable_timeline=True,
        samples={"wide": wide, "tight": tight},
        transforms={"wide": transforms["wide"], "tight": transforms["tight"]},
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((wide, tight)),
    )

    assert calibration.status == "sample_readback_complete", calibration.message
    assert calibration.observed_transforms is not None
    assert calibration.observed_transforms["wide"] == transforms["wide"]
    assert calibration.observed_transforms["tight"] == transforms["tight"]
    assert "visual behavior remains unqualified" in calibration.message
    assert wide.item.set_calls[0]["RotationAngle"] == 0
    assert tight.item.set_calls[0]["DynamicZoomEnabled"] is False

    assert (FIXTURES / "profile.json").read_bytes() == prior_profile_bytes
    assert (FIXTURES / "profile-content.json").read_bytes() == prior_content_bytes


def test_calibration_requires_a_disposable_studio_pair() -> None:
    profile, content, _, _ = _fixture()
    adapter, guard_count = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    wide = _target("calibration-wide", "wide", interval, lambda: guard_count[0])
    tight = _target("calibration-tight", "tight", interval, lambda: guard_count[0])
    result = adapter.calibrate_disposable_samples(
        is_disposable_timeline=False,
        samples={"wide": wide, "tight": tight},
        transforms={"wide": content["wide"], "tight": content["tight"]},
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((wide, tight)),
    )
    assert result.status == "blocked"
    assert not wide.item.set_calls
    assert not tight.item.set_calls


def test_calibration_captures_authored_tuples_and_refuses_non_neutral_samples() -> None:
    profile, content, _, _ = _fixture()
    adapter, guard_count = _adapter(profile)
    interval = ValidatedSourceTimeInterval(100, 125)
    wide_values = {**content["wide"], "Pan": 0.375}
    tight_values = dict(content["tight"])
    invariants = {
        "TransformEnabled": True,
        "DynamicZoomEnabled": False,
        "RotationAngle": 0,
        "AnchorPointX": 0,
        "AnchorPointY": 0,
        "FlipX": False,
        "FlipY": False,
    }

    def sample_properties(values: Mapping[str, Any]) -> dict[str, Any]:
        return {**invariants, **values}

    wide = _target(
        "sample-wide",
        "wide",
        interval,
        lambda: guard_count[0],
        media_id_override="same-camera",
        properties=sample_properties(wide_values),
    )
    tight = _target(
        "sample-tight",
        "tight",
        interval,
        lambda: guard_count[0],
        media_id_override="same-camera",
        properties=sample_properties(tight_values),
    )
    result = adapter.calibrate_disposable_samples(
        is_disposable_timeline=True,
        samples={"wide": wide, "tight": tight},
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((wide, tight)),
    )
    assert result.status == "sample_readback_complete"
    assert result.observed_transforms == {
        "wide": wide_values,
        "tight": tight_values,
    }
    assert wide.item.set_calls[0] == sample_properties(wide_values)
    assert tight.item.set_calls[0] == sample_properties(tight_values)

    non_neutral = sample_properties(wide_values)
    non_neutral["RotationAngle"] = 0.01
    bad_wide = _target(
        "sample-wide-2",
        "wide",
        interval,
        lambda: guard_count[0],
        media_id_override="same-camera",
        properties=non_neutral,
    )
    bad_tight = _target(
        "sample-tight-2",
        "tight",
        interval,
        lambda: guard_count[0],
        media_id_override="same-camera",
        properties=sample_properties(tight_values),
    )
    blocked = adapter.calibrate_disposable_samples(
        is_disposable_timeline=True,
        samples={"wide": bad_wide, "tight": bad_tight},
        save_close_reopen=lambda: None,
        lookup_reopened=_reopened_lookup((bad_wide, bad_tight)),
    )
    assert blocked.status == "blocked"
    assert "neutral invariants differ" in blocked.message
    assert not bad_wide.item.set_calls
    assert not bad_tight.item.set_calls
    assert bad_wide.item.name.startswith("Generated presenter")


def test_free_handoff_is_pure_and_blocked_without_qualified_controls() -> None:
    profile, _, content_bytes, pin = _fixture()
    target = PresenterFramingIntent(
        "presenter-free", "tight", "OC TIGHT presenter-free"
    )
    result = free_manual_handoff(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        observed_context=profile["context"],
        targets=[target],
    )
    assert result.status == "blocked"
    assert result.event_ids == ("presenter-free",)
    assert "separately qualified Inspector mapping" in result.message
    assert "supplies controls and values" in result.message

    wrong_context = copy.deepcopy(profile["context"])
    wrong_context["resolve"]["version"] = "21.0"
    mismatch = free_manual_handoff(
        profile=profile,
        canonical_content_json=content_bytes,
        expected_pin=pin,
        observed_context=wrong_context,
        targets=[target],
    )
    assert mismatch.status == "blocked"
    assert "context differs" in mismatch.message
