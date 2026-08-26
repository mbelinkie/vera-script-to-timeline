from __future__ import annotations

import html
import json
import math
import re
from dataclasses import dataclass
from typing import Any, BinaryIO, cast

from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
)

ADAPTER_VERSION = "aws-polly-adapter/v1"
PRICE_USD_PER_MILLION_CHARACTERS = 32.0
ALLOWED_ATTESTATIONS = {"opt_out_confirmed", "provider_terms_accepted"}
_RATE = re.compile(r"(?:x-(?:slow|fast)|slow|medium|fast|x-fast|[+-]?\d+%)\Z")
_PITCH = re.compile(r"(?:x-(?:low|high)|low|medium|high|x-high|[+-]?\d+(?:\.\d+)?%)\Z")
_VOLUME = re.compile(
    r"(?:silent|x-soft|soft|medium|loud|x-loud|[+-]?\d+(?:\.\d+)?dB)\Z"
)
_PAUSE = re.compile(
    r"(?:\d+(?:\.\d+)?(?:ms|s)|none|x-small|small|medium|large|x-large)\Z"
)


class PollyError(RuntimeError):
    pass


@dataclass(frozen=True)
class PollySourceMap:
    plain_text: str
    provider_input: bytes
    authored_spans: tuple[tuple[int, int, int, int], ...]

    def translate_provider_range(self, start: int, end: int) -> tuple[int, int] | None:
        if start < 0 or end < start or end > len(self.provider_input):
            raise PollyError("timing mark byte range is out of bounds")
        overlaps = [
            span for span in self.authored_spans if span[0] < end and start < span[1]
        ]
        if not overlaps:
            return None
        plain_start = min(span[2] for span in overlaps)
        plain_end = max(span[3] for span in overlaps)
        return (
            _utf16_length(self.plain_text[:plain_start]),
            _utf16_length(self.plain_text[:plain_end]),
        )


def _utf16_length(value: str) -> int:
    return len(value.encode("utf-16-le")) // 2


def _utf16_offset_to_index(text: str, offset: int, label: str) -> int:
    if offset < 0:
        raise PollyError(f"{label} bounds are outside authored text")
    current = 0
    for index, character in enumerate(text):
        if current == offset:
            return index
        current += _utf16_length(character)
        if current > offset:
            raise PollyError(f"{label} bounds split a UTF-16 surrogate pair")
    if current == offset:
        return len(text)
    raise PollyError(f"{label} bounds are outside authored text")


def utf8_range_to_utf16(text: str, start: int, end: int) -> tuple[int, int]:
    raw = text.encode("utf-8")
    if start < 0 or end < start or end > len(raw):
        raise PollyError("timing mark byte range is out of bounds")
    try:
        prefix = raw[:start].decode("utf-8")
        selected = raw[start:end].decode("utf-8")
    except UnicodeDecodeError as error:
        raise PollyError("timing mark byte range splits a UTF-8 character") from error
    return _utf16_length(prefix), _utf16_length(prefix + selected)


def _validate_range(start: int, end: int, length: int, label: str) -> None:
    if start < 0 or end < start or end > length:
        raise PollyError(f"{label} bounds are outside authored text")


def build_polly_ssml(request: SynthesisRequest) -> tuple[bytes, PollySourceMap]:
    text = request.text
    if not _RATE.fullmatch(request.settings.rate):
        raise PollyError("invalid prosody rate")
    if not _PITCH.fullmatch(request.settings.pitch):
        raise PollyError("invalid prosody pitch")
    if not _VOLUME.fullmatch(request.settings.volume):
        raise PollyError("invalid prosody volume")
    if request.profile.engine == "neural" and request.settings.pitch != "0%":
        raise PollyError("pitch is not supported by Polly Neural voices")

    spans: list[tuple[int, int, str, str, str | None]] = []
    pauses: dict[int, str] = {}
    for item in request.pronunciations:
        start = _utf16_offset_to_index(text, item.start, "pronunciation")
        end = _utf16_offset_to_index(text, item.end, "pronunciation")
        _validate_range(start, end, len(text), "pronunciation")
        if start == end:
            raise PollyError("pronunciation must cover text")
        if text[start:end] != item.text:
            raise PollyError("pronunciation text does not match authored range")
        if item.kind == "phoneme" and item.alphabet not in {"ipa", "x-sampa"}:
            raise PollyError("phoneme pronunciation requires ipa or x-sampa alphabet")
        spans.append((start, end, item.kind, item.value, item.alphabet))
    for control in request.controls:
        start = _utf16_offset_to_index(text, control.start, "control")
        end = _utf16_offset_to_index(text, control.end, "control")
        _validate_range(start, end, len(text), "control")
        if control.kind == "pause":
            if start != end:
                raise PollyError("pause control must be zero-width")
            if not _PAUSE.fullmatch(control.value):
                raise PollyError("invalid pause duration")
            if start in pauses:
                raise PollyError("pause controls overlap")
            pauses[start] = control.value
        else:
            if start == end:
                raise PollyError("emphasis must cover text")
            if control.value not in {"strong", "moderate", "reduced"}:
                raise PollyError("invalid emphasis level")
            spans.append((start, end, control.kind, control.value, None))

    spans.sort(key=lambda item: (item[0], item[1]))
    previous_end = 0
    for start, end, _kind, _value, _alphabet in spans:
        if start < previous_end:
            raise PollyError("pronunciation and SSML controls overlap")
        if any(start < offset < end for offset in pauses):
            raise PollyError("pronunciation and SSML controls overlap")
        previous_end = end

    pieces: list[str] = []
    authored_spans: list[tuple[int, int, int, int]] = []
    byte_offset = 0

    def emit_tag(value: str) -> None:
        nonlocal byte_offset
        pieces.append(value)
        byte_offset += len(value.encode("utf-8"))

    def emit_authored_character(offset: int) -> None:
        nonlocal byte_offset
        value = html.escape(text[offset], quote=False)
        start_byte = byte_offset
        pieces.append(value)
        byte_offset += len(value.encode("utf-8"))
        authored_spans.append((start_byte, byte_offset, offset, offset + 1))

    prosody_attributes = [
        f'rate="{html.escape(request.settings.rate, quote=True)}"',
        f'volume="{html.escape(request.settings.volume, quote=True)}"',
    ]
    if request.profile.engine != "neural":
        prosody_attributes.append(
            f'pitch="{html.escape(request.settings.pitch, quote=True)}"'
        )
    emit_tag("<speak><prosody " + " ".join(prosody_attributes) + ">")
    cursor = 0

    def append_plain(start: int, end: int) -> None:
        for offset in range(start, end + 1):
            if offset in pauses:
                emit_tag(f'<break time="{html.escape(pauses[offset], quote=True)}"/>')
            if offset < end:
                emit_authored_character(offset)

    for start, end, kind, value, alphabet in spans:
        append_plain(cursor, start)
        escaped_value = html.escape(value, quote=True)
        if kind == "alias":
            emit_tag(f'<sub alias="{escaped_value}">')
        elif kind == "phoneme":
            emit_tag(f'<phoneme alphabet="{alphabet}" ph="{escaped_value}">')
        else:
            emit_tag(f'<emphasis level="{escaped_value}">')
        for offset in range(start, end):
            emit_authored_character(offset)
        emit_tag(
            "</sub>"
            if kind == "alias"
            else "</phoneme>"
            if kind == "phoneme"
            else "</emphasis>"
        )
        cursor = end
    append_plain(cursor, len(text))
    emit_tag("</prosody></speak>")
    ssml = "".join(pieces).encode("utf-8")
    return ssml, PollySourceMap(
        plain_text=text,
        provider_input=ssml,
        authored_spans=tuple(authored_spans),
    )


def _read_stream(response: dict[str, Any]) -> bytes:
    stream = response.get("AudioStream")
    if stream is None or not hasattr(stream, "read"):
        raise PollyError("Polly response did not contain an audio stream")
    body = cast(BinaryIO, stream)
    try:
        return body.read()
    finally:
        body.close()


def _request_id(response: dict[str, Any]) -> str:
    metadata = response.get("ResponseMetadata")
    if not isinstance(metadata, dict):
        return "provider_not_supplied"
    value = metadata.get("RequestId")
    return value if isinstance(value, str) else "provider_not_supplied"


def _parse_marks(
    raw: bytes, source_map: PollySourceMap
) -> tuple[ProviderTimingMark, ...]:
    marks: list[ProviderTimingMark] = []
    previous_time = -1
    previous_start = -1
    for line_number, line in enumerate(raw.splitlines(), start=1):
        try:
            value = json.loads(line)
            kind = value["type"]
            time_ms = value["time"]
            start = value["start"]
            end = value["end"]
            spoken = value["value"]
            if not (
                isinstance(kind, str)
                and isinstance(time_ms, int)
                and isinstance(start, int)
                and isinstance(end, int)
                and isinstance(spoken, str)
            ):
                raise TypeError
            translated = source_map.translate_provider_range(start, end)
        except (json.JSONDecodeError, KeyError, TypeError, PollyError) as error:
            raise PollyError(f"invalid timing mark on line {line_number}") from error
        if time_ms < previous_time or start < previous_start:
            raise PollyError("timing marks are nonmonotonic")
        previous_time = time_ms
        previous_start = start
        if translated is None:
            # Polly reports SSML-only elements such as <break> as word marks.
            # They carry useful audio timing but no accepted ScriptDocument range.
            continue
        start_utf16, end_utf16 = translated
        marks.append(
            ProviderTimingMark(
                kind=kind,
                time_ms=time_ms,
                start_byte=start,
                end_byte=end,
                start_utf16=start_utf16,
                end_utf16=end_utf16,
                value=spoken,
            )
        )
    if not marks:
        raise PollyError("Polly returned no timing marks")
    return tuple(marks)


class PollyProvider:
    def __init__(
        self,
        *,
        client: Any | None = None,
        adapter_version: str = ADAPTER_VERSION,
    ) -> None:
        self._client = client
        self.adapter_version = adapter_version

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return build_polly_ssml(request)[0]

    def _validate_preflight(self, request: SynthesisRequest) -> None:
        if len(request.text) > 3000:
            raise PollyError(
                "Polly synchronous input exceeds the 3,000 billed-character limit"
            )
        if request.data_policy_attestation not in ALLOWED_ATTESTATIONS:
            raise PollyError("an explicit AWS data-policy attestation is required")
        if not math.isfinite(request.max_cost_usd) or request.max_cost_usd < 0:
            raise PollyError("cost ceiling must be a finite nonnegative number")
        estimated = len(request.text) * PRICE_USD_PER_MILLION_CHARACTERS / 1_000_000
        if estimated > request.max_cost_usd:
            raise PollyError(
                f"estimated ${estimated:.6f} exceeds the "
                f"${request.max_cost_usd:.6f} cost ceiling"
            )

    def _get_client(self, region: str) -> Any:
        if self._client is not None:
            return self._client
        try:
            import boto3  # type: ignore[import-untyped]

            session = boto3.Session(region_name=region)
            credentials = session.get_credentials()
            if credentials is None:
                raise PollyError("AWS credentials are unavailable")
            return session.client("polly", region_name=region)
        except PollyError:
            raise
        except Exception as error:
            raise PollyError(f"could not initialize AWS Polly: {error}") from error

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self._validate_preflight(request)
        ssml, source_map = build_polly_ssml(request)
        if len(ssml.decode("utf-8")) > 6000:
            raise PollyError(
                "Polly synchronous input exceeds the 6,000-character limit"
            )
        client = self._get_client(request.profile.region)
        common: dict[str, Any] = {
            "Engine": request.profile.engine,
            "LanguageCode": request.profile.language,
            "Text": ssml.decode("utf-8"),
            "TextType": "ssml",
            "VoiceId": request.profile.voice_id,
        }
        if request.profile.lexicons:
            common["LexiconNames"] = [
                name for name, _content_hash in request.profile.lexicons
            ]
        try:
            audio_response = client.synthesize_speech(
                **common,
                OutputFormat="pcm",
                SampleRate="16000",
            )
            timing_response = client.synthesize_speech(
                **common,
                OutputFormat="json",
                SpeechMarkTypes=list(request.timing_kinds),
            )
            audio = _read_stream(audio_response)
            marks = _parse_marks(_read_stream(timing_response), source_map)
        except PollyError:
            raise
        except Exception as error:
            raise PollyError(f"Polly synthesis failed: {error}") from error
        if not audio or len(audio) % 2:
            raise PollyError("Polly returned invalid 16-bit PCM audio")
        request_ids = (_request_id(audio_response), _request_id(timing_response))
        return ProviderResult(
            audio_bytes=audio,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=ssml,
            timing_marks=marks,
            provenance={
                "provider": "aws_polly",
                "region": request.profile.region,
                "engine": request.profile.engine,
                "voiceId": request.profile.voice_id,
                "voiceVersion": request.profile.voice_version,
                "language": request.profile.language,
                "adapterVersion": self.adapter_version,
                "requestIds": list(request_ids),
            },
            request_ids=request_ids,
        )
