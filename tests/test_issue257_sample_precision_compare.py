"""Issue 257 zero-lag PCM comparison stays bound to the reviewed source."""

from __future__ import annotations

import hashlib
import io
import json
import struct
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import sample_precision_compare_v2 as compare_module
from vera_timeline_agent.sample_precision_compare_v2 import (
    GAP_END,
    GAP_START,
    MAX_PROGRAMME_RMS,
    MAX_ROLLING_RMS,
    SAMPLE_COUNT,
    SamplePrecisionCompareError,
    compare_pcm,
)


def _source_wav(samples: list[int]) -> tuple[bytes, bytes]:
    pcm = b"".join(sample.to_bytes(3, "little", signed=True) for sample in samples)
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(3)
        stream.setframerate(48_000)
        stream.writeframes(pcm)
    return buffer.getvalue(), pcm


def _native_pcm(
    samples: list[int], *, bad: dict[tuple[int, int], int] | None = None
) -> bytes:
    bad = bad or {}
    output = bytearray()
    for frame, source in enumerate(samples):
        left = 0 if GAP_START <= frame < GAP_END else source
        right = left
        left = bad.get((frame, 0), left)
        right = bad.get((frame, 1), right)
        output.extend(struct.pack("<ii", left, right))
    return bytes(output)


def _compare(source: bytes, pcm: bytes, native: bytes) -> dict[str, Any]:
    return compare_pcm(
        source,
        native,
        source_wav_sha256=hashlib.sha256(source).hexdigest(),
        source_pcm_sha256=hashlib.sha256(pcm).hexdigest(),
        native_pcm_sha256=hashlib.sha256(native).hexdigest(),
        native_sample_format="s24-s32le",
    )


def test_exact_stereo_lift_keeps_neighbors_and_only_mutes_reviewed_gap() -> None:
    samples = [((index % 31) - 15) * 700 for index in range(SAMPLE_COUNT)]
    samples[GAP_START - 1] = (1 << 23) - 1
    samples[GAP_END] = -(1 << 23)
    source, pcm = _source_wav(samples)
    native = _native_pcm(samples)

    result = _compare(source, pcm, native)

    assert result["status"] == "pass"
    assert result["gap"] == {"startSample": GAP_START, "endSample": GAP_END}
    assert all(channel["gapExactlyZero"] for channel in result["channels"])
    assert all(channel["programmeRms"] == 0.0 for channel in result["channels"])
    before_gap = _native_pcm(samples, bad={(GAP_START - 1, 0): 0})
    after_gap = _native_pcm(samples, bad={(GAP_END, 1): 0})
    assert _compare(source, pcm, before_gap)["status"] == "fail"
    assert _compare(source, pcm, after_gap)["status"] == "fail"


def test_sample_shift_is_not_aligned_away() -> None:
    samples = [0] * SAMPLE_COUNT
    samples[GAP_END] = (1 << 23) - 1
    shifted = samples.copy()
    shifted[GAP_END] = 0
    shifted[GAP_END + 1] = samples[GAP_END]
    source, pcm = _source_wav(samples)

    result = _compare(source, pcm, _native_pcm(shifted))

    assert result["status"] == "fail"
    assert all(
        channel["programmeRms"] > MAX_PROGRAMME_RMS for channel in result["channels"]
    )


def test_sliding_window_catches_a_short_channel_specific_error() -> None:
    samples = [0] * SAMPLE_COUNT
    source, pcm = _source_wav(samples)
    native = _native_pcm(samples, bad={(10, 1): 1 << 21})

    result = _compare(source, pcm, native)

    left, right = result["channels"]
    assert left["pass"] is True
    assert right["programmeRms"] <= MAX_PROGRAMME_RMS
    assert right["maxSliding960Rms"] > MAX_ROLLING_RMS
    assert right["pass"] is False
    assert result["status"] == "fail"


def test_float_native_pcm_uses_normalized_full_scale() -> None:
    samples = [((index % 17) - 8) * 257 for index in range(SAMPLE_COUNT)]
    source, pcm = _source_wav(samples)
    native = bytearray()
    for frame, sample in enumerate(samples):
        value = 0.0 if GAP_START <= frame < GAP_END else sample / (1 << 23)
        native.extend(struct.pack("<ff", value, value))
    native_bytes = bytes(native)

    result = compare_pcm(
        source,
        native_bytes,
        source_wav_sha256=hashlib.sha256(source).hexdigest(),
        source_pcm_sha256=hashlib.sha256(pcm).hexdigest(),
        native_pcm_sha256=hashlib.sha256(native_bytes).hexdigest(),
        native_sample_format="f32le",
    )

    assert result["status"] == "pass"
    assert all(channel["programmeRms"] == 0.0 for channel in result["channels"])


@pytest.mark.parametrize(
    ("source_hash", "pcm_hash", "native_suffix"),
    [
        ("0" * 64, None, b""),
        (None, "0" * 64, b""),
        (None, None, b"\0\0\0\0"),
    ],
)
def test_rejects_hash_mismatch_and_nonintegral_native_extent(
    source_hash: str | None,
    pcm_hash: str | None,
    native_suffix: bytes,
) -> None:
    samples = [0] * SAMPLE_COUNT
    source, pcm = _source_wav(samples)
    native = _native_pcm(samples) + native_suffix
    with pytest.raises(SamplePrecisionCompareError):
        compare_pcm(
            source,
            native,
            source_wav_sha256=source_hash or hashlib.sha256(source).hexdigest(),
            source_pcm_sha256=pcm_hash or hashlib.sha256(pcm).hexdigest(),
            native_pcm_sha256=hashlib.sha256(native).hexdigest(),
            native_sample_format="s24-s32le",
        )


def test_rejects_source_pcm_hash_mismatch_and_wrong_gap() -> None:
    samples = [0] * SAMPLE_COUNT
    source, pcm = _source_wav(samples)
    native = _native_pcm(samples)
    with pytest.raises(SamplePrecisionCompareError, match="source PCM hash"):
        compare_pcm(
            source,
            native,
            source_wav_sha256=hashlib.sha256(source).hexdigest(),
            source_pcm_sha256="0" * 64,
            native_pcm_sha256=hashlib.sha256(native).hexdigest(),
            native_sample_format="s24-s32le",
        )
    with pytest.raises(SamplePrecisionCompareError, match="omission extent"):
        compare_pcm(
            source,
            native,
            source_wav_sha256=hashlib.sha256(source).hexdigest(),
            source_pcm_sha256=hashlib.sha256(pcm).hexdigest(),
            native_pcm_sha256=hashlib.sha256(native).hexdigest(),
            native_sample_format="s24-s32le",
            gap_end=GAP_END + 1,
        )


def _getter(value: int | float, arguments: list[object]) -> dict[str, object]:
    return {
        "status": "supported",
        "pythonType": type(value).__name__,
        "value": value,
        "arguments": arguments,
    }


def _geometry_observations(
    timeline_end_endpoint: str = "inclusive",
    *,
    baseline_frames: int = 100,
    source_end_endpoint: str = "exclusive",
) -> list[dict[str, Any]]:
    ranges = {
        "baseline": [(0, baseline_frames * 2002)],
        "baseline_after_reopen": [(0, baseline_frames * 2002)],
        "sample_lift": [(0, GAP_START), (GAP_END, SAMPLE_COUNT)],
        "sample_lift_after_reopen": [(0, GAP_START), (GAP_END, SAMPLE_COUNT)],
    }
    observations: list[dict[str, Any]] = []
    for stage, expected_ranges in ranges.items():
        items: list[dict[str, Any]] = []
        for index, (start, end) in enumerate(expected_ranges):
            timeline_uid = (
                "baseline-item" if stage.startswith("baseline") else f"survivor-{index}"
            )
            record_start = start / 2002
            record_end = end / 2002 - (timeline_end_endpoint == "inclusive")
            source_end_adjustment = {
                "exclusive": 0,
                "inclusive_sample": 1,
                "inclusive_frame": 2002,
            }[source_end_endpoint]
            getters = {
                "GetStart(True)": _getter(record_start, [True]),
                "GetEnd(True)": _getter(record_end, [True]),
                "GetDuration(True)": _getter((end - start) / 2002, [True]),
                "GetSourceStartTime": _getter(start / 48_000, []),
                "GetSourceEndTime": _getter((end - source_end_adjustment) / 48_000, []),
            }
            items.append(
                {
                    "timelineItemUid": timeline_uid,
                    "sourceUID": "source-uid",
                    "mediaUID": "media-uid",
                    "rawGetters": getters,
                }
            )
        observations.append({"stage": stage, "items": items})
    return observations


def test_geometry_requires_unique_units_exact_edges_and_reopen_identity() -> None:
    observations = _geometry_observations()

    result = compare_module._geometry(observations)

    assert result["status"] == "pass"
    assert result["sourceTimeCalibration"]["unit"] == "seconds"
    assert result["sourceTimeCalibration"]["endEndpoint"] == "exclusive"
    assert result["timelineEndEndpoint"] == "inclusive"
    assert result["baselineGetterPrecision"]["status"] == "pass"
    assert result["baselineControlFrames"] == 100
    assert len(result["timelineChecks"]) == 6

    shifted = _geometry_observations()
    shifted[-1]["items"][0]["rawGetters"]["GetStart(True)"]["value"] += 0.001
    with pytest.raises(SamplePrecisionCompareError, match="sample edges"):
        compare_module._geometry(shifted)

    reloaded = _geometry_observations()
    reloaded[-1]["items"][1]["timelineItemUid"] = "replaced-survivor"
    with pytest.raises(SamplePrecisionCompareError, match="UID changed after reopen"):
        compare_module._geometry(reloaded)

    exclusive = compare_module._geometry(_geometry_observations("exclusive"))
    assert exclusive["timelineEndEndpoint"] == "exclusive"

    inconsistent = _geometry_observations()
    inconsistent[-1]["items"][1]["rawGetters"]["GetEnd(True)"]["value"] += 1
    with pytest.raises(SamplePrecisionCompareError, match="endpoint semantics"):
        compare_module._geometry(inconsistent)


@pytest.mark.parametrize(
    ("baseline_frames", "source_endpoint", "append_adjustment"),
    [
        (100, "exclusive", 0),
        (100, "inclusive_sample", 0),
        (101, "inclusive_frame", -1),
    ],
)
def test_geometry_calibrates_baseline_control_and_source_end_semantics(
    baseline_frames: int, source_endpoint: str, append_adjustment: int
) -> None:
    observations = _geometry_observations(
        baseline_frames=baseline_frames,
        source_end_endpoint=source_endpoint,
    )

    result = compare_module._geometry(observations)

    assert result["status"] == "pass"
    assert result["baselineControlFrames"] == baseline_frames
    assert result["sourceTimeCalibration"]["endEndpoint"] == source_endpoint
    assert append_adjustment == (0 if baseline_frames == 100 else -1)


@pytest.mark.parametrize(("baseline_frames", "adjustment"), [(100, 0), (101, -1)])
def test_construction_uses_calibrated_baseline_append_endpoint(
    baseline_frames: int, adjustment: int
) -> None:
    observations = _geometry_observations(baseline_frames=baseline_frames)
    infos = [
        {
            "startFrame": 0.0,
            "endFrame": GAP_START / 2002 + adjustment,
            "recordFrame": 0.0,
            "trackIndex": 1,
            "mediaType": 2,
            "mediaPoolItem": "media-uid",
        },
        {
            "startFrame": GAP_END / 2002,
            "endFrame": SAMPLE_COUNT / 2002 + adjustment,
            "recordFrame": GAP_END / 2002,
            "trackIndex": 1,
            "mediaType": 2,
            "mediaPoolItem": "media-uid",
        },
    ]
    calibration = {
        "inputEndFrame": 100,
        "observedDurationFrames": float(baseline_frames),
        "appendEndFrameAdjustment": adjustment,
    }
    result = {
        "observations": observations,
        "calibration": calibration,
        "construction": {
            "status": "constructed_fractional_arguments",
            "calibration": calibration,
            "baseline": {
                "startFrame": 0.0,
                "endFrame": 100.0,
                "recordFrame": 0.0,
                "trackIndex": 1,
                "mediaType": 2,
            },
            "delete": {"timelineItemUid": "baseline-item", "rippleDelete": False},
            "survivors": {
                "sourceSampleRanges": [
                    {"startSample": 0, "endSampleExclusive": GAP_START},
                    {"startSample": GAP_END, "endSampleExclusive": SAMPLE_COUNT},
                ],
                "infos": infos,
            },
        },
    }

    compare_module._verify_construction(result)


def test_baseline_getter_support_is_reported_separately_from_pcm() -> None:
    observations = _geometry_observations()
    observations[0]["items"][0]["rawGetters"]["GetSourceEndTime"]["status"] = (
        "unsupported"
    )

    result = compare_module._geometry_report(observations)

    assert result["status"] == "unsupported"
    assert result["baselineGetterPrecision"]["status"] == "unsupported"
    assert result["baselineGetterPrecision"]["reason"]


@pytest.mark.parametrize(
    ("geometry_status", "expected"),
    [
        ("pass", "supported"),
        ("unsupported", "unsupported"),
        ("ambiguous", "ambiguous"),
    ],
)
def test_finalize_status_never_claims_support_without_geometry_and_pcm(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    geometry_status: str,
    expected: str,
) -> None:
    from vera_timeline_agent import sample_precision_probe_v2 as probe

    samples = [0] * SAMPLE_COUNT
    source_wav, pcm = _source_wav(samples)
    source_path = tmp_path / "media" / "source.wav"
    source_path.parent.mkdir()
    source_path.write_bytes(source_wav)
    review_path = tmp_path / "review" / "review.json"
    review_path.parent.mkdir()
    review_path.write_text("{}", encoding="utf-8")
    marker_path = tmp_path / "review" / "markers.csv"
    marker_path.write_text("", encoding="utf-8")
    output_dir = tmp_path / "probe"
    renders = output_dir / "renders"
    renders.mkdir(parents=True)
    request_path = output_dir / "request.json"
    request_path.write_text("{}", encoding="utf-8")
    request_path.chmod(0o400)

    native_mov = renders / "issue257-test.mov"
    native_mov.write_bytes(b"test native mov placeholder")
    mov_sha = hashlib.sha256(native_mov.read_bytes()).hexdigest()
    requested_settings = {"profile": "fixed"}
    request: dict[str, Any] = {
        "requestId": "test",
        "outputDir": str(output_dir),
        "releaseRoot": str(tmp_path / "release"),
        "releaseSha256": "a" * 64,
        "sourcePath": str(source_path),
        "sourceSha256": hashlib.sha256(source_wav).hexdigest(),
        "sourcePcmSha256": hashlib.sha256(pcm).hexdigest(),
        "sampleRate": 48_000,
        "channels": 1,
        "bitDepth": 24,
        "sourceSamples": SAMPLE_COUNT,
        "programmeSamples": SAMPLE_COUNT,
        "frameSamples": 2002,
        "targetGap": {"startSample": GAP_START, "endSample": GAP_END},
        "supports": [],
        "profile": {"fixed": True},
        "target": {
            "projectUid": "project-uid",
            "timelineUid": "timeline-uid",
            "projectName": "Project",
            "timelineName": "Timeline",
        },
        "reviewPath": str(review_path),
        "reviewSha256": hashlib.sha256(review_path.read_bytes()).hexdigest(),
        "markerPath": str(marker_path),
        "markerSha256": hashlib.sha256(marker_path.read_bytes()).hexdigest(),
    }
    result_path = output_dir / "result.json"
    result: dict[str, Any] = {
        "schemaVersion": probe.RESULT_SCHEMA,
        "status": "rendered_for_pcm_verification",
        "requestPath": str(compare_module._INSTALLED_REQUEST_PATH),
        "requestSha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "hostRequestPath": str(request_path),
        "hostRequestSha256": hashlib.sha256(request_path.read_bytes()).hexdigest(),
        "releaseSha256": request["releaseSha256"],
        "target": request["target"],
        "source": {},
        "review": {},
        "programme": {},
        "profile": request["profile"],
        "oneUseIntentPath": "unused-in-this-gate-test",
        "oneUseIntentSha256": "b" * 64,
        "startedAt": "test",
        "finishedAt": "test",
        "preflight": {},
        "effects": [],
        "observations": [],
        "construction": {},
        "calibration": None,
        "render": {
            "status": "rendered_for_pcm_verification",
            "outputPath": str(native_mov),
            "sha256": mov_sha,
            "jobId": "job-id",
            "job": {},
            "settings": {
                "requested": requested_settings,
                "readback": {
                    "status": "unsupported",
                    "method": "Project.GetRenderSettings",
                },
            },
            "formatCodec": {"format": "mov", "codec": "apcn"},
            "jobStatus": {"JobStatus": "Complete"},
        },
        "failure": None,
    }
    result_path.write_text(json.dumps(result), encoding="utf-8")
    result_path.chmod(0o400)
    final_path = tmp_path / "finalization.json"

    monkeypatch.setattr(probe, "_no_symlink_ancestry", lambda _: None)
    monkeypatch.setattr(probe, "load_probe_request", lambda *args, **kwargs: request)
    monkeypatch.setattr(compare_module, "_verify_result_bindings", lambda *args: None)
    monkeypatch.setattr(compare_module, "_current_release", lambda _: None)
    monkeypatch.setattr(
        compare_module, "_source_and_review_current", lambda _: source_wav
    )
    monkeypatch.setattr(compare_module, "_verify_effect_journals", lambda *args: None)
    monkeypatch.setattr(
        compare_module,
        "_geometry_report",
        lambda _: {
            "status": geometry_status,
            "baselineGetterPrecision": {"status": geometry_status},
        },
    )
    monkeypatch.setattr(compare_module, "_verify_construction", lambda _: None)
    monkeypatch.setattr(compare_module, "_verify_post_render_snapshot", lambda _: None)
    monkeypatch.setattr(probe, "_verify_job", lambda *args: None)
    monkeypatch.setattr(probe, "_render_settings", lambda _: requested_settings)
    monkeypatch.setattr(
        compare_module,
        "_decode_probe_mov",
        lambda *args: (_native_pcm(samples), {"decoderIdentitySha256": "c" * 64}),
    )

    finalized = compare_module.finalize_probe(request_path, result_path, final_path)

    report = json.loads(finalized.read_text(encoding="utf-8"))
    assert report["pcm"]["status"] == "pass"
    assert report["status"] == expected


def test_result_binding_uses_host_request_and_does_not_reopen_installed_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from vera_timeline_agent import sample_precision_probe_v2 as probe

    output_dir = tmp_path / "evidence"
    output_dir.mkdir()
    request_path = output_dir / "request.json"
    request_path.write_bytes(b"{}")
    request_path.chmod(0o400)
    request_sha = hashlib.sha256(b"{}").hexdigest()
    target = {
        "projectUid": "project-uid",
        "timelineUid": "timeline-uid",
        "projectName": "Project",
        "timelineName": "Timeline",
    }
    request: dict[str, Any] = {
        "outputDir": str(output_dir),
        "releaseSha256": "a" * 64,
        "target": target,
        "sourcePath": "/review/source.wav",
        "sourceSha256": "b" * 64,
        "sourcePcmSha256": "c" * 64,
        "sampleRate": 48_000,
        "channels": 1,
        "bitDepth": 24,
        "sourceSamples": SAMPLE_COUNT,
        "programmeSamples": SAMPLE_COUNT,
        "frameSamples": 2002,
        "targetGap": {"startSample": GAP_START, "endSample": GAP_END},
        "supports": [],
        "profile": {"profile": "fixed"},
        "reviewPath": "/review/review.json",
        "reviewSha256": "d" * 64,
        "markerPath": "/review/markers.csv",
        "markerSha256": "e" * 64,
    }
    state_root = tmp_path / "probe-state"
    intent_dir = state_root / "intents"
    intent_dir.mkdir(parents=True)
    monkeypatch.setattr(probe, "PROBE_STATE_ROOT", state_root)
    target_key = hashlib.sha256(b"project-uid\0timeline-uid").hexdigest()
    intent_path = intent_dir / f"target-{target_key}.json"
    intent = {
        "schemaVersion": "vera-sample-precision-probe-intent/v1",
        "requestSha256": request_sha,
        "target": target,
        "claimedAt": "test",
    }
    intent_bytes = json.dumps(intent, sort_keys=True, separators=(",", ":")).encode()
    for path in (intent_path, intent_dir / f"request-{request_sha}.json"):
        path.write_bytes(intent_bytes)
        path.chmod(0o400)
    result: dict[str, Any] = {key: None for key in compare_module._RESULT_KEYS}
    result.update(
        schemaVersion=probe.RESULT_SCHEMA,
        status="unsupported",
        requestPath=str(compare_module._INSTALLED_REQUEST_PATH),
        requestSha256=request_sha,
        hostRequestPath=str(request_path),
        hostRequestSha256=request_sha,
        releaseSha256=request["releaseSha256"],
        target=target,
        source={
            "path": request["sourcePath"],
            "sha256": request["sourceSha256"],
            "pcmSha256": request["sourcePcmSha256"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "samples": request["sourceSamples"],
        },
        review={
            "path": request["reviewPath"],
            "sha256": request["reviewSha256"],
            "markerPath": request["markerPath"],
            "markerSha256": request["markerSha256"],
        },
        programme={
            "frameSamples": request["frameSamples"],
            "sampleRate": request["sampleRate"],
            "channels": request["channels"],
            "bitDepth": request["bitDepth"],
            "sourceSamples": request["sourceSamples"],
            "programmeSamples": request["programmeSamples"],
            "targetGap": request["targetGap"],
            "supports": request["supports"],
        },
        profile=request["profile"],
        oneUseIntentPath=str(intent_path),
        oneUseIntentSha256=hashlib.sha256(intent_bytes).hexdigest(),
    )
    result_path = output_dir / "result.json"

    compare_module._verify_result_bindings(request, request_path, result, result_path)

    result["hostRequestSha256"] = "f" * 64
    with pytest.raises(
        SamplePrecisionCompareError, match="does not bind to this request"
    ):
        compare_module._verify_result_bindings(
            request, request_path, result, result_path
        )


@pytest.mark.parametrize(
    ("native_status", "geometry_status", "pcm_status", "expected"),
    [
        ("rendered_for_pcm_verification", "pass", "pass", ("supported", None)),
        (
            "rendered_for_pcm_verification",
            "pass",
            "fail",
            ("unsupported", "measured_pcm_mismatch"),
        ),
        (
            "rendered_for_pcm_verification",
            "unsupported",
            "pass",
            ("unsupported", "required_getter_unavailable"),
        ),
        (
            "rendered_for_pcm_verification",
            "ambiguous",
            "pass",
            ("ambiguous", "geometry_or_mapping_ambiguous"),
        ),
    ],
)
def test_verdict_preserves_measured_mismatch_and_geometry_ambiguity(
    native_status: str,
    geometry_status: str,
    pcm_status: str,
    expected: tuple[str, str | None],
) -> None:
    assert (
        compare_module._verdict(
            native_status, {"status": geometry_status}, {"status": pcm_status}
        )
        == expected
    )
