"""Focused decoder-profile, lineage and signed-24-domain refusals."""

from __future__ import annotations

import hashlib
import struct
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import qualification_output_decode_v2 as d
from vera_timeline_agent import qualification_output_records_v2 as r

Json = dict[str, Any]


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def lineage(context: Json, output_sha256: str) -> Json:
    return {
        "schemaVersion": "qualification-output-lineage/v1",
        "lane": r.LANE,
        "context": context,
        "commitmentRawSha256": digest(b"commitment"),
        "reservationRawSha256": digest(b"reservation"),
        "renderIntentSha256": digest(b"render intent"),
        "effectReceiptSha256": digest(b"effect"),
        "startReceiptSha256": digest(b"start"),
        "completionReceiptSha256": digest(b"completion"),
        "jobId": "native-job-1",
        "sourceOutputRawSha256": output_sha256,
    }


def probe(*, codec: str = "prores", width: int = 1920) -> Json:
    return {
        "streams": [
            {
                "index": 0,
                "start_pts": 0,
                "start_time": "0.000000",
                "codec_type": "video",
                "codec_name": codec,
                "codec_tag_string": "apcn",
                "profile": "Standard",
                "width": width,
                "height": 1080,
                "r_frame_rate": "24000/1001",
                "avg_frame_rate": "24000/1001",
                "nb_read_frames": "1",
                "disposition": {"attached_pic": 0},
            },
            {
                "index": 1,
                "start_pts": 0,
                "start_time": "0.000000",
                "codec_type": "audio",
                "codec_name": "pcm_s24le",
                "codec_tag_string": "lpcm",
                "bits_per_raw_sample": "24",
                "bits_per_sample": 24,
                "sample_rate": "48000",
                "channels": 2,
                "channel_layout": "stereo",
                "sample_fmt": "s32",
                "time_base": "1/48000",
                "duration_ts": "2002",
            },
        ],
        "format": {
            "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
            "format_long_name": "QuickTime / MOV",
            "start_time": "0.000000",
            "tags": {"major_brand": "qt  "},
        },
    }


def _fake_toolchain() -> d._Toolchain:
    state = d._FileState(1, 2, 3, 4, 5)
    return d._Toolchain(
        d._ToolIdentity(str(d.FFMPEG_PATH), d.FFMPEG_VERSION, d.FFMPEG_SHA256, state),
        d._ToolIdentity(
            str(d.FFPROBE_PATH), d.FFPROBE_VERSION, d.FFPROBE_SHA256, state
        ),
    )


def test_signed24_domain_preserves_stereo_interleave_and_sign() -> None:
    values = [-(1 << 23), 123, -1, 456, 0, -456, (1 << 23) - 1, -100]
    raw = b"".join(struct.pack("<i", value << 8) for value in values)

    decoded = d._signed24_domain(raw, sample_count=4)

    assert list(struct.unpack("<8i", decoded)) == values


def test_signed24_domain_rejects_non_24_bit_aligned_s32() -> None:
    raw = struct.pack("<ii", 1, 0)

    with pytest.raises(r.OutputConsistencyError, match="left-aligned"):
        d._signed24_domain(raw, sample_count=1)


def test_decoder_refuses_tool_hash_drift_before_execution(tmp_path: Path) -> None:
    executable = tmp_path / "ffmpeg"
    executable.write_bytes(b"changed executable")
    executable.chmod(0o755)
    pin = d._ToolPin(executable, "ffmpeg version 8.1.2", "0" * 64)

    with pytest.raises(r.OutputConsistencyError, match="binary hash drifted"):
        d._verify_tool(pin, "ffmpeg")


def test_decoder_refuses_unexpected_video_profile() -> None:
    with pytest.raises(r.OutputConsistencyError, match="video profile"):
        d._validate_profile(
            probe(codec="h264"), extent_frames=1, width=1920, height=1080
        )


def test_decoder_refuses_unexpected_stream() -> None:
    unexpected = probe()
    unexpected["streams"].append({"index": 2, "codec_type": "subtitle"})

    with pytest.raises(
        r.OutputConsistencyError, match="exactly one video and one audio"
    ):
        d._validate_profile(unexpected, extent_frames=1, width=1920, height=1080)


def test_decoder_refuses_unproven_pcm24_mov_tag() -> None:
    unproven_tag = probe()
    unproven_tag["streams"][1]["codec_tag_string"] = "in24"

    with pytest.raises(
        r.OutputConsistencyError, match="audio profile or exact sample extent"
    ):
        d._validate_profile(unproven_tag, extent_frames=1, width=1920, height=1080)


def test_decoder_rejects_bad_job_and_output_lineage_before_tools(
    tmp_path: Path,
) -> None:
    mov = tmp_path.resolve() / "delivered.mov"
    mov.write_bytes(b"same delivered MOV")
    context = {
        "projectUid": "project",
        "timelineUid": "timeline",
        "caseId": "case",
        "phase": "pristine",
    }
    output_sha256 = digest(mov.read_bytes())
    invalid = lineage(context, output_sha256)
    invalid["jobId"] = ""

    with pytest.raises(r.OutputConsistencyError, match="native job identity"):
        d.decode_delivered_mov(
            mov,
            context=context,
            expected_output_sha256=output_sha256,
            expected_extent_frames=1,
            expected_width=1920,
            expected_height=1080,
            render_lineage=d.VerifiedRenderLineage(invalid),
        )

    invalid = lineage(context, digest(b"another output"))
    with pytest.raises(r.OutputConsistencyError, match="does not identify"):
        d.decode_delivered_mov(
            mov,
            context=context,
            expected_output_sha256=output_sha256,
            expected_extent_frames=1,
            expected_width=1920,
            expected_height=1080,
            render_lineage=d.VerifiedRenderLineage(invalid),
        )


@pytest.mark.parametrize(
    ("section", "field", "value", "message"),
    [
        ("video", "start_pts", 1, "video timestamp origin"),
        ("video", "start_time", "0.000042", "video timestamp origin"),
        ("audio", "start_pts", 1, "audio timestamp origin"),
        ("audio", "start_time", "0.000021", "audio timestamp origin"),
        ("format", "start_time", "0.000021", "container timestamp origin"),
    ],
)
def test_decoder_rejects_nonzero_stream_or_container_origin(
    section: str,
    field: str,
    value: Any,
    message: str,
) -> None:
    data = probe()
    if section == "format":
        data["format"][field] = value
    else:
        stream = next(item for item in data["streams"] if item["codec_type"] == section)
        stream[field] = value

    with pytest.raises(r.OutputConsistencyError, match=message):
        d._validate_profile(data, extent_frames=1, width=1920, height=1080)


def test_probe_and_decode_pin_the_same_advanced_edit_list_policy() -> None:
    input_ref = "/dev/fd/7"
    for command in (d._probe_command(input_ref), d._decode_command(input_ref)):
        input_index = command.index("-i")
        ignore_index = command.index("-ignore_editlist")
        advanced_index = command.index("-advanced_editlist")
        assert ignore_index < advanced_index < input_index
        assert command[ignore_index + 1] == "0"
        assert command[advanced_index + 1] == "1"
        assert advanced_index + 1 < input_index
        assert command[input_index + 1] == input_ref


def test_decoder_rejects_delivered_file_hash_drift_before_tools(tmp_path: Path) -> None:
    mov = tmp_path.resolve() / "delivered.mov"
    mov.write_bytes(b"changed delivered MOV")
    context = {
        "projectUid": "project",
        "timelineUid": "timeline",
        "caseId": "case",
        "phase": "pristine",
    }
    authenticated_output_hash = digest(b"original delivered MOV")

    with pytest.raises(r.OutputConsistencyError, match="hash differs"):
        d.decode_delivered_mov(
            mov,
            context=context,
            expected_output_sha256=authenticated_output_hash,
            expected_extent_frames=1,
            expected_width=1920,
            expected_height=1080,
            render_lineage=d.VerifiedRenderLineage(
                lineage(context, authenticated_output_hash)
            ),
        )


def test_decoder_binds_profile_pcm_hash_and_render_job_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mov = tmp_path.resolve() / "delivered.mov"
    mov.write_bytes(b"same delivered MOV")
    context = {
        "projectUid": "project",
        "timelineUid": "timeline",
        "caseId": "case",
        "phase": "pristine",
    }
    output_sha256 = digest(mov.read_bytes())
    zero_pcm = bytes(2002 * 2 * 4)
    monkeypatch.setattr(d, "_verify_toolchain", _fake_toolchain)
    monkeypatch.setattr(d, "_assert_toolchain_current", lambda _: None)
    monkeypatch.setattr(d, "_probe_mov", lambda _fd, _ref: probe())
    monkeypatch.setattr(d, "_decode_mov", lambda _fd, _ref, _count: zero_pcm)

    decoded = d.decode_delivered_mov(
        mov,
        context=context,
        expected_output_sha256=output_sha256,
        expected_extent_frames=1,
        expected_width=1920,
        expected_height=1080,
        render_lineage=d.VerifiedRenderLineage(lineage(context, output_sha256)),
    )

    assert decoded.record["sourceOutputRawSha256"] == output_sha256
    assert decoded.record["sampleCount"] == 2002
    assert decoded.record["decodedSamplesSha256"] == digest(decoded.decoded_samples)
    assert decoded.record["decoderCommandSha256"] != digest(b"different command")
    assert len(decoded.decoded_samples) == 2002 * 2 * 4
