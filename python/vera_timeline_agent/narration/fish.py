"""Fish timestamped PCM adapter. No paid fallback, retries or voice uploads."""

from __future__ import annotations

import math
import os
import re
import subprocess
import sys
import unicodedata
from collections.abc import Callable, Iterable
from datetime import UTC, datetime
from fractions import Fraction
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from vera_timeline_agent.narration.configuration import pricing_for
from vera_timeline_agent.narration.fish_stream import (
    FishStreamError,
    parse_timestamp_stream,
)
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    canonical_json_bytes,
)
from vera_timeline_agent.narration.provider import SpeechProviderError

ADAPTER_VERSION = "fish-timestamp-pcm-adapter/v2"
ENDPOINT = "https://api.fish.audio/v1/tts/stream/with-timestamp"
SAMPLE_RATE = 44100
FREE_UNTIL = datetime(2026, 12, 1, tzinfo=UTC)
KEYCHAIN_SERVICE = "com.vera.script-to-timeline"
KEYCHAIN_ACCOUNT = "fish_audio_api_key"


class FishError(SpeechProviderError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        # The API key is authorized for this exact endpoint only.
        return None


urlopen = build_opener(_NoRedirect()).open


def _api_key() -> str:
    key = os.environ.get("FISH_AUDIO_API_KEY", "").strip()
    if not key and sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-s",
                    KEYCHAIN_SERVICE,
                    "-a",
                    KEYCHAIN_ACCOUNT,
                    "-w",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError):
            result = None
        if result is not None and result.returncode == 0:
            key = result.stdout.strip()
    if not key or len(key) > 4096 or any(not 33 <= ord(char) <= 126 for char in key):
        raise FishError("FISH_AUDIO_API_KEY is missing or invalid")
    return key


def _ignorable(text: str) -> bool:
    return all(
        char.isspace()
        or unicodedata.category(char).startswith("P")
        or unicodedata.category(char) == "Sc"
        for char in text
    )


def _number(value: object, label: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FishError(f"invalid Fish {label}")
    if (isinstance(value, float) and not math.isfinite(value)) or value < 0:
        raise FishError(f"invalid Fish {label}")
    return Fraction(str(value))


def _utf16(text: str) -> int:
    return len(text.encode("utf-16-le")) // 2


def _source_words(text: str) -> list[tuple[int, int]]:
    """Keep Unicode marks, contractions, decimals and internal abbreviation dots."""
    spans: list[tuple[int, int]] = []
    start: int | None = None
    for index, char in enumerate(text):
        lexical = unicodedata.category(char)[0] in {"L", "M", "N", "S"}
        internal = (
            char in "'\u2019-."
            and start is not None
            and index + 1 < len(text)
            and unicodedata.category(text[index + 1])[0] in {"L", "M", "N"}
        )
        if lexical or internal:
            if start is None:
                start = index
        elif start is not None:
            spans.append((start, index))
            start = None
    if start is not None:
        spans.append((start, len(text)))
    return spans


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans: list[tuple[int, int]] = []
    start = 0
    for match in re.finditer(r"""[.!?]+["'\u201d\u2019\)\]]*(?=\s|$)""", text):
        prefix = text[: match.start()]
        last = re.search(r"[\w.]+$", prefix)
        abbreviation = last.group().lower() if last else ""
        if match.group().startswith(".") and (
            abbreviation
            in {
                "mr",
                "mrs",
                "ms",
                "dr",
                "prof",
                "sr",
                "jr",
                "st",
                "vs",
                "etc",
                "e.g",
                "i.e",
            }
            or re.fullmatch(r"(?:[A-Za-z]\.)*[A-Za-z]", abbreviation)
        ):
            continue
        left = start
        while left < match.end() and text[left].isspace():
            left += 1
        if left < match.end():
            spans.append((left, match.end()))
        start = match.end()
    while start < len(text) and text[start].isspace():
        start += 1
    end = len(text.rstrip())
    if start < end:
        spans.append((start, end))
    return spans


def _segment_start(text: str, piece: str, start: int, end: int) -> int:
    left = text.find(piece, start, end)
    if left >= 0:
        return left
    # Fish can return a straight apostrophe for an authored curly apostrophe.
    source = text[start:end].replace("\u2019", "'")
    normalized_piece = piece.replace("\u2019", "'")
    left = source.find(normalized_piece)
    return start + left if left >= 0 else -1


def timing_marks(
    text: str, snapshots: tuple[dict[str, Any], ...], audio_samples: int
) -> tuple[ProviderTimingMark, ...]:
    """Bind complete latest snapshots to authored spans, without guessed word splits."""
    spans = _source_words(text)
    coverage: dict[tuple[int, int], tuple[int, int]] = {}
    source_cursor = 0
    previous_end = 0
    final_duration = Fraction(0)
    for expected_seq, snapshot in enumerate(snapshots):
        if snapshot["seq"] != expected_seq:
            raise FishError("Fish timing chunk sequence is incomplete")
        content = snapshot["content"].strip()
        start = text.find(content, source_cursor) if content else -1
        if start < 0 or text[source_cursor:start].strip():
            raise FishError("Fish chunk text does not cover the authored source")
        content_end = start + len(content)
        alignment = snapshot["alignment"]
        segments = alignment.get("segments")
        if not isinstance(segments, list) or not segments:
            raise FishError("Fish returned missing word alignment")
        offset = _number(snapshot["offset"], "chunk offset")
        duration = _number(alignment.get("audio_duration"), "alignment duration")
        final_duration = offset + duration
        cursor = start
        for segment in segments:
            if not isinstance(segment, dict) or not isinstance(
                segment.get("text"), str
            ):
                raise FishError("invalid Fish segment")
            piece = segment["text"].strip()
            left = _segment_start(text, piece, cursor, content_end) if piece else -1
            if left < 0 or not _ignorable(text[cursor:left]):
                raise FishError("Fish word alignment differs from authored text")
            right = left + len(piece)
            local_start = _number(segment.get("start"), "segment start")
            local_end = _number(segment.get("end"), "segment end")
            if local_end < local_start or local_end > duration:
                raise FishError("Fish segment bounds are invalid")
            first = round((offset + local_start) * SAMPLE_RATE)
            last = round((offset + local_end) * SAMPLE_RATE)
            if first < previous_end or first > last or last > audio_samples:
                raise FishError("Fish timing overlaps or lies outside final audio")
            previous_end = last
            matched = [span for span in spans if span[0] < right and span[1] > left]
            if len(matched) > 1:
                raise FishError(
                    "Fish supplied phrase timing; word timing is unavailable"
                )
            if matched:
                span = matched[0]
                # A contraction split into subsegments still denotes one source word.
                old = coverage.get(span)
                coverage[span] = (old[0] if old else first, last)
            cursor = right
        if not _ignorable(text[cursor:content_end]):
            raise FishError("Fish word alignment is incomplete")
        source_cursor = content_end
    if text[source_cursor:].strip() or set(coverage) != set(spans) or not spans:
        raise FishError("Fish word alignment does not cover all authored words")
    if abs(final_duration - Fraction(audio_samples, SAMPLE_RATE)) > Fraction(1, 20):
        raise FishError("Fish alignment duration differs from final PCM audio")

    def mark(
        kind: str, left: int, right: int, first: int, last: int
    ) -> ProviderTimingMark:
        return ProviderTimingMark(
            kind=kind,
            time_ms=round(Fraction(first * 1000, SAMPLE_RATE)),
            start_byte=len(text[:left].encode("utf-8")),
            end_byte=len(text[:right].encode("utf-8")),
            start_utf16=_utf16(text[:left]),
            end_utf16=_utf16(text[:right]),
            value=text[left:right],
            time_sample=first,
            end_sample=last,
            sample_rate=SAMPLE_RATE,
        )

    marks = [
        mark("word", left, right, *coverage[(left, right)]) for left, right in spans
    ]
    for left, right in _sentence_spans(text):
        words = [coverage[span] for span in spans if left <= span[0] < right]
        if words:
            marks.append(mark("sentence", left, right, words[0][0], words[-1][1]))
    return tuple(
        sorted(marks, key=lambda item: (item.time_sample, item.start_utf16, item.kind))
    )


class FishProvider:
    adapter_version = ADAPTER_VERSION

    def __init__(
        self,
        *,
        transport: Callable[[bytes, str], Iterable[bytes]] | None = None,
    ) -> None:
        self._transport = transport or self._stream

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        if request.profile.provider != "fish_audio" or request.profile.engine not in {
            "s2.1-pro-free",
            "s2.1-pro",
        }:
            raise FishError(
                "unsupported Fish provider/model; paid fallback is disabled"
            )
        if not re.fullmatch(r"[0-9a-f]{32}", request.profile.voice_id):
            raise FishError("Fish requires an existing voice reference ID")
        if request.pronunciations or request.controls or request.profile.lexicons:
            raise FishError(
                "Fish pronunciation, pause and emphasis controls are unsupported"
            )
        if request.settings.pitch != "0%" or request.settings.volume != "0dB":
            raise FishError("Fish pitch and volume controls are unsupported")
        if not re.fullmatch(r"\d+(?:\.\d+)?%", request.settings.rate):
            raise FishError("Fish speed must be an explicit percentage")
        speed = float(request.settings.rate[:-1]) / 100
        if not 0.5 <= speed <= 2.0:
            raise FishError("Fish speed must be between 50% and 200%")
        if (
            not request.text.strip()
            or "<|" in request.text
            or re.search(r"\[[^\]]+\]", request.text)
        ):
            raise FishError(
                "Fish requires nonempty plain text without inline voice controls"
            )
        if set(request.timing_kinds) != {"word", "sentence"}:
            raise FishError("Fish requires word and sentence timing")
        return canonical_json_bytes(
            {
                "text": request.text,
                "reference_id": request.profile.voice_id,
                "format": "pcm",
                "sample_rate": SAMPLE_RATE,
                "prosody": {"speed": speed, "volume": 0, "normalize_loudness": False},
                "normalize": False,
                "language": request.profile.language,
                "latency": "balanced",
                "chunk_length": 300,
                "temperature": 0.7,
                "top_p": 0.7,
            }
        )

    def preflight(self, request: SynthesisRequest) -> None:
        self.prepare_input(request)
        policy = pricing_for(request.profile)
        if request.pricing_policy_version != policy.version:
            raise FishError("Fish pricing policy does not match the selected model")
        if request.data_policy_attestation != "fish_terms_accepted":
            raise FishError("explicit Fish data-policy consent is required")
        if not math.isfinite(request.max_cost_usd) or request.max_cost_usd < 0:
            raise FishError("cost ceiling must be finite and nonnegative")
        if policy.estimate(request.text) > request.max_cost_usd:
            raise FishError("Fish estimated charge exceeds the cost ceiling")
        if (
            request.profile.engine == "s2.1-pro-free"
            and datetime.now(UTC) >= FREE_UNTIL
        ):
            raise FishError(
                "Fish free promotion must be reverified before further calls"
            )
        if self._transport == self._stream:
            _api_key()

    @staticmethod
    def _stream(payload: bytes, model: str) -> Iterable[bytes]:
        request = Request(
            ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Authorization": "Bearer " + _api_key(),
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "model": model,
            },
        )
        try:
            with urlopen(request, timeout=60) as response:
                if response.headers.get_content_type() != "text/event-stream":
                    raise FishError("Fish did not return timestamped SSE audio")
                while chunk := response.read1(65536):
                    yield chunk
        except HTTPError as error:
            # Do not echo remote bodies: they can contain private request text.
            category = {
                401: "authentication",
                403: "voice/access",
                402: "balance",
                429: "rate limit",
                400: "request/model/capability",
                422: "request/model/capability",
            }.get(error.code, "service")
            raise FishError(
                f"Fish {category} error (HTTP {error.code}); no retry performed",
                request_rejected=error.code in {400, 401, 402, 403, 422, 429},
            ) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise FishError(
                "Fish transport failed; result is uncertain; no retry performed"
            ) from None

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.preflight(request)
        payload = self.prepare_input(request)
        captured = bytearray()

        def chunks() -> Iterable[bytes]:
            for chunk in self._transport(payload, request.profile.engine):
                if len(captured) + len(chunk) > 256 * 1024 * 1024:
                    raise FishError("Fish response exceeds the retention limit")
                captured.extend(chunk)
                yield chunk

        try:
            return self.decode_response(request, chunks())
        except SpeechProviderError as error:
            if captured:
                error.response_files = {
                    "provider-input.json": payload,
                    "provider-response.sse": bytes(captured),
                }
                error.request_rejected = False
            raise

    def decode_response(
        self, request: SynthesisRequest, chunks: Iterable[bytes]
    ) -> ProviderResult:
        """Reprocess a retained response offline; never opens a connection."""
        payload = self.prepare_input(request)
        try:
            audio, snapshots = parse_timestamp_stream(chunks)
        except FishStreamError as error:
            raise FishError(str(error)) from error
        if len(audio) % 2:
            raise FishError("Fish returned incomplete 16-bit PCM samples")
        marks = timing_marks(request.text, snapshots, len(audio) // 2)
        return ProviderResult(
            audio_bytes=audio,
            audio_format="pcm_s16le",
            sample_rate=SAMPLE_RATE,
            channels=1,
            provider_input=payload,
            provider_input_format="json",
            timing_marks=marks,
            provenance={
                "provider": "fish_audio",
                "engine": request.profile.engine,
                "region": request.profile.region,
                "voiceId": request.profile.voice_id,
                "voiceVersion": request.profile.voice_version,
                "adapterVersion": self.adapter_version,
                "timingSource": "native_timestamp_endpoint",
                "requestedSpeed": float(request.settings.rate[:-1]) / 100,
                "effectiveSpeed": "provider_not_reported",
                "timingSampleRate": SAMPLE_RATE,
                "alignmentSnapshots": list(snapshots),
                "requestIds": [],
            },
        )
