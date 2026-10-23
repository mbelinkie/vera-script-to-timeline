from __future__ import annotations

import base64
import binascii
import json
import math
from collections.abc import Iterable
from typing import Any

_MAX_EVENT_BYTES = 8 * 1024 * 1024
_MAX_AUDIO_BYTES = 128 * 1024 * 1024
_MAX_STREAM_BYTES = 256 * 1024 * 1024
_MAX_EVENTS = 100_000


class FishStreamError(RuntimeError):
    """The Fish timestamp stream is malformed or incomplete."""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"invalid JSON constant {value}")


def parse_timestamp_stream(
    chunks: Iterable[bytes],
) -> tuple[bytes, tuple[dict[str, Any], ...]]:
    """Parse Fish Audio SSE bytes into arrival-ordered audio and final snapshots.

    Complete SSE frames followed by a clean EOF indicate completion; the endpoint
    does not document a separate completion event. The conventional ``[DONE]``
    data sentinel is also accepted when it is the final data frame.
    """
    line = bytearray()
    frame_data: list[str] = []
    frame_event: str | None = None
    frame_pending = False
    frame_bytes = 0
    after_cr = False
    done = False
    event_count = 0
    stream_size = 0
    audio_parts: list[bytes] = []
    audio_size = 0
    seen_sequences: set[int] = set()
    snapshots: dict[int, dict[str, Any]] = {}

    def finish_frame() -> None:
        nonlocal frame_data, frame_event, frame_pending, frame_bytes
        nonlocal done, event_count, audio_size

        if not frame_data:
            frame_event = None
            frame_pending = False
            frame_bytes = 0
            return

        event_type = frame_event or "message"
        if event_type not in ("", "message"):
            raise FishStreamError("Fish stream contains an unsupported event type")

        data = "\n".join(frame_data)
        frame_data = []
        frame_event = None
        frame_pending = False
        frame_bytes = 0

        if data == "[DONE]":
            if done:
                raise FishStreamError("duplicate Fish stream completion marker")
            done = True
            return
        if done:
            raise FishStreamError("Fish stream contains data after completion")

        try:
            event = json.loads(data, parse_constant=_reject_json_constant)
        except (json.JSONDecodeError, ValueError) as exc:
            raise FishStreamError("Fish stream contains malformed event JSON") from exc
        if not isinstance(event, dict):
            raise FishStreamError("Fish stream event must be a JSON object")
        if "error" in event:
            raise FishStreamError("Fish stream returned an error event")

        required = {
            "audio_base64",
            "content",
            "chunk_seq",
            "chunk_audio_offset_sec",
            "alignment",
        }
        missing = required.difference(event)
        if missing:
            raise FishStreamError(
                f"Fish stream event is missing fields: {', '.join(sorted(missing))}"
            )

        encoded_audio = event["audio_base64"]
        if not isinstance(encoded_audio, str):
            raise FishStreamError("Fish stream audio_base64 must be a string")
        try:
            audio = base64.b64decode(encoded_audio, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise FishStreamError("Fish stream audio_base64 is invalid") from exc
        if audio_size + len(audio) > _MAX_AUDIO_BYTES:
            raise FishStreamError("Fish stream audio exceeds the size limit")

        content = event["content"]
        if not isinstance(content, str):
            raise FishStreamError("Fish stream content must be a string")
        sequence = event["chunk_seq"]
        if type(sequence) is not int or sequence < 0:
            raise FishStreamError("Fish stream chunk_seq must be a nonnegative integer")
        offset = event["chunk_audio_offset_sec"]
        if type(offset) not in (int, float) or offset < 0:
            raise FishStreamError(
                "Fish stream chunk_audio_offset_sec must be finite and nonnegative"
            )
        if isinstance(offset, float) and not math.isfinite(offset):
            raise FishStreamError(
                "Fish stream chunk_audio_offset_sec must be finite and nonnegative"
            )
        alignment = event["alignment"]
        if alignment is not None and not isinstance(alignment, dict):
            raise FishStreamError("Fish stream alignment must be an object or null")

        if event_count >= _MAX_EVENTS:
            raise FishStreamError("Fish stream contains too many events")
        event_count += 1
        audio_parts.append(audio)
        audio_size += len(audio)
        seen_sequences.add(sequence)
        if alignment is not None:
            snapshots[sequence] = {
                "seq": sequence,
                "content": content,
                "offset": offset,
                "alignment": alignment,
            }

    def finish_line() -> None:
        nonlocal frame_event, frame_pending, frame_bytes

        raw_line = bytes(line)
        line.clear()
        frame_bytes += len(raw_line) + 1
        if frame_bytes > _MAX_EVENT_BYTES:
            raise FishStreamError("Fish stream event exceeds the size limit")
        try:
            text = raw_line.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise FishStreamError("Fish stream contains invalid UTF-8") from exc

        if not raw_line:
            finish_frame()
            return
        if text.startswith(":"):
            return

        field, separator, value = text.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        frame_pending = True
        if field == "data":
            frame_data.append(value)
        elif field == "event":
            frame_event = value
            if value not in ("", "message"):
                raise FishStreamError("Fish stream contains an unsupported event type")
        # Standard SSE fields such as id/retry and unknown fields are ignored.

    for chunk in chunks:
        if not isinstance(chunk, bytes):
            raise FishStreamError("Fish stream chunks must be bytes")
        stream_size += len(chunk)
        if stream_size > _MAX_STREAM_BYTES:
            raise FishStreamError("Fish stream exceeds the total transport size limit")
        position = 0
        while position < len(chunk):
            if after_cr:
                after_cr = False
                if chunk[position] == 0x0A:
                    position += 1
                    continue

            cr = chunk.find(b"\r", position)
            lf = chunk.find(b"\n", position)
            if cr < 0:
                terminator = lf
            elif lf < 0:
                terminator = cr
            else:
                terminator = min(cr, lf)
            if terminator < 0:
                line.extend(chunk[position:])
                if len(line) > _MAX_EVENT_BYTES:
                    raise FishStreamError("Fish stream event exceeds the size limit")
                break

            line.extend(chunk[position:terminator])
            if len(line) > _MAX_EVENT_BYTES:
                raise FishStreamError("Fish stream event exceeds the size limit")
            finish_line()
            after_cr = chunk[terminator] == 0x0D
            position = terminator + 1

    if line or frame_pending:
        raise FishStreamError("Fish stream ends with an incomplete SSE frame")
    if not audio_size:
        raise FishStreamError("Fish stream contains no audio")
    missing_sequences = seen_sequences.difference(snapshots)
    if missing_sequences:
        missing = ", ".join(str(sequence) for sequence in sorted(missing_sequences))
        raise FishStreamError(
            f"Fish stream has no alignment snapshot for chunk(s): {missing}"
        )

    return b"".join(audio_parts), tuple(snapshots[seq] for seq in sorted(snapshots))
