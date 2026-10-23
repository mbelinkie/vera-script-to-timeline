from __future__ import annotations

import base64
import json

import pytest
import vera_timeline_agent.narration.fish_stream as fish_stream
from vera_timeline_agent.narration.fish_stream import (
    FishStreamError,
    parse_timestamp_stream,
)

_DEFAULT_ALIGNMENT = object()


def message(
    audio: bytes = b"audio",
    *,
    seq: int = 0,
    content: str = "Hello",
    offset: float = 0.0,
    alignment: object = _DEFAULT_ALIGNMENT,
) -> dict[str, object]:
    return {
        "audio_base64": base64.b64encode(audio).decode("ascii"),
        "content": content,
        "chunk_seq": seq,
        "chunk_audio_offset_sec": offset,
        "alignment": {"revision": 1} if alignment is _DEFAULT_ALIGNMENT else alignment,
    }


def frame(event: dict[str, object], *, ending: bytes = b"\n\n") -> bytes:
    return b"data: " + json.dumps(event, ensure_ascii=False).encode("utf-8") + ending


def test_fragmented_crlf_multiline_data_and_utf8_parse_as_one_message() -> None:
    event = message(content="café 🌍", alignment={"segments": []})
    pretty_json = json.dumps(event, ensure_ascii=False, indent=2).splitlines()
    wire = b": keepalive\r\n"
    wire += b"".join(b"data: " + line.encode("utf-8") + b"\r\n" for line in pretty_json)
    wire += b"\r\n"

    audio, snapshots = parse_timestamp_stream(bytes([byte]) for byte in wire)

    assert audio == b"audio"
    assert snapshots == (
        {"seq": 0, "content": "café 🌍", "offset": 0.0, "alignment": {"segments": []}},
    )


def test_audio_keeps_arrival_order_and_latest_nonnull_snapshots_keep_offsets() -> None:
    wire = b"".join(
        frame(event)
        for event in (
            message(
                b"first",
                seq=1,
                content="older",
                offset=16.24,
                alignment={"revision": 1},
            ),
            message(
                b"second", seq=0, content="zero", offset=0.0, alignment={"revision": 1}
            ),
            message(
                b"third",
                seq=1,
                content="newer",
                offset=16.24,
                alignment={"revision": 2},
            ),
            message(
                b"fourth", seq=1, content="ignored null", offset=999.0, alignment=None
            ),
            message(
                b"fifth", seq=0, content="ignored null", offset=999.0, alignment=None
            ),
        )
    )

    audio, snapshots = parse_timestamp_stream((wire,))

    assert audio == b"firstsecondthirdfourthfifth"
    assert snapshots == (
        {"seq": 0, "content": "zero", "offset": 0.0, "alignment": {"revision": 1}},
        {"seq": 1, "content": "newer", "offset": 16.24, "alignment": {"revision": 2}},
    )


@pytest.mark.parametrize(
    "wire",
    [
        b"data: {not json}\n\n",
        frame({**message(), "audio_base64": "%%%"}),
        frame({**message(), "audio_base64": 5}),
        frame({**message(), "content": 5}),
        frame({**message(), "chunk_seq": -1}),
        frame({**message(), "chunk_seq": True}),
        frame({**message(), "chunk_audio_offset_sec": -0.1}),
        b'data: {"audio_base64":"YQ==","content":"x","chunk_seq":0,'
        b'"chunk_audio_offset_sec":1e999,"alignment":{}}\n\n',
        frame({**message(), "alignment": []}),
        frame({key: value for key, value in message().items() if key != "alignment"}),
        frame({**message(), "error": "provider failure"}),
        b"event: unexpected\n" + frame(message()),
        frame(message(alignment=None)),
        frame(message(audio=b"")),
        frame(message())[:-1],
        frame(message())[:-2] + b"data: ",
        (
            b'data: {"audio_base64":"YQ==","content":"\xff",'
            b'"chunk_seq":0,"chunk_audio_offset_sec":0,"alignment":{}}\n\n'
        ),
    ],
)
def test_malformed_or_incomplete_streams_are_refused(wire: bytes) -> None:
    with pytest.raises(FishStreamError):
        parse_timestamp_stream((wire,))


def test_done_marker_rejects_later_audio() -> None:
    wire = frame(message()) + b"data: [DONE]\n\n" + frame(message())

    with pytest.raises(FishStreamError, match="after completion"):
        parse_timestamp_stream((wire,))


def test_done_marker_can_end_a_complete_stream() -> None:
    audio, snapshots = parse_timestamp_stream(
        (frame(message()) + b"data: [DONE]\r\n\r\n",)
    )

    assert audio == b"audio"
    assert len(snapshots) == 1


def test_event_and_total_audio_limits_are_enforced(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(fish_stream, "_MAX_EVENT_BYTES", 64)
    with pytest.raises(FishStreamError, match="event exceeds"):
        parse_timestamp_stream((frame(message()),))

    monkeypatch.setattr(fish_stream, "_MAX_EVENT_BYTES", 1024)
    monkeypatch.setattr(fish_stream, "_MAX_AUDIO_BYTES", 2)
    with pytest.raises(FishStreamError, match="audio exceeds"):
        parse_timestamp_stream((frame(message(audio=b"123")),))


def test_event_count_limit_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(fish_stream, "_MAX_EVENTS", 1)
    wire = frame(message()) + frame(message())

    with pytest.raises(FishStreamError, match="too many events"):
        parse_timestamp_stream((wire,))
