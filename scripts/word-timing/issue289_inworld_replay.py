"""Replay one hash-pinned Inworld capture through VERA's narration provider seam.

Study-only: this module has no network transport and does not claim to recreate
the provider's original wire bytes. It deterministically serializes the pinned
JSON input with the same semantic payload for ``SpeechSynthesisProvider``.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import math
import wave
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path
from typing import Any, cast

import issue289_native_comparison as native
from vera_timeline_agent.narration.configuration import PricingPolicy
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    SynthesisSettings,
    VoiceProfile,
)

CAPTURE_FILES = (
    "request.private.json",
    "provider-input.json",
    "response.raw.json",
    "audio.wav",
)


def inworld_study_profile(voice_id: str = "Ashley") -> VoiceProfile:
    if not voice_id or voice_id != voice_id.strip():
        raise InworldReplayError("voice ID must be explicit and non-empty")
    suffix = hashlib.sha256(voice_id.encode("utf-8")).hexdigest()[:12]
    return VoiceProfile(
        profile_id=f"issue-289-inworld-tts-2-study-{suffix}",
        provider="inworld",
        region="provider_not_supplied",
        engine="inworld-tts-2",
        voice_id=voice_id,
        voice_version="provider_not_supplied",
        language="en-US",
    )


INWORLD_STUDY_PROFILE = inworld_study_profile()
INWORLD_STUDY_PRICING = PricingPolicy(
    version="issue-289-captured-replay-no-provider-call-v1",
    unit="characters",
    usd_per_million=0.0,
)
SAMPLE_RATE = 48_000


class InworldReplayError(ValueError):
    """A retained capture cannot safely cross the narration seam."""


class InworldCaptureReplayProvider:
    """Read-only replay of a pinned capture; never calls Inworld."""

    adapter_version = "issue-289-inworld-capture-replay/v1"

    def __init__(
        self,
        capture_dir: Path,
        expected_hashes: Mapping[str, str],
        *,
        voice_id: str,
    ) -> None:
        self.profile = inworld_study_profile(voice_id)
        if set(expected_hashes) != set(CAPTURE_FILES):
            raise InworldReplayError("capture hash manifest has the wrong files")
        self.capture_hashes = dict(expected_hashes)
        fingerprint = hashlib.sha256(
            json.dumps(
                sorted(self.capture_hashes.items()), separators=(",", ":")
            ).encode()
        ).hexdigest()[:16]
        self.adapter_version = f"{type(self).adapter_version}+capture-{fingerprint}"
        self._files: dict[str, bytes] = {}
        for name in CAPTURE_FILES:
            path = capture_dir / name
            if path.is_symlink() or not path.is_file():
                raise InworldReplayError(f"capture file is missing or unsafe: {name}")
            data = path.read_bytes()
            digest = f"sha256:{hashlib.sha256(data).hexdigest()}"
            if self.capture_hashes[name] != digest:
                raise InworldReplayError(f"capture hash mismatch: {name}")
            self._files[name] = data

        self._request = self._json("request.private.json")
        self._provider_payload = self._json("provider-input.json")
        self._response = self._json("response.raw.json")
        self._row = _mapping(self._request.get("row"), "capture row")
        self._text = _string(self._row.get("text"), "capture text")
        token_text, self._tokens, valid = native._frozen_tokens(self._row)
        _require(
            valid and token_text == self._text, "capture token snapshot is invalid"
        )
        self._validate_capture_identity()
        self._audio_pcm, self._audio_frames = self._decode_audio()
        self._marks = self._map_marks()

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        self._validate_request(request)
        return json.dumps(self._provider_payload, ensure_ascii=False).encode("utf-8")

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        provider_input = self.prepare_input(request)
        return ProviderResult(
            audio_bytes=self._audio_pcm,
            audio_format="pcm_s16le",
            sample_rate=SAMPLE_RATE,
            channels=1,
            provider_input=provider_input,
            timing_marks=self._marks,
            provenance={
                "provider": "inworld",
                "region": self.profile.region,
                "engine": self.profile.engine,
                "voiceId": self.profile.voice_id,
                "voiceVersion": self.profile.voice_version,
                "adapterVersion": self.adapter_version,
                "captureReplay": True,
                "captureTakeId": self._request.get("takeId"),
                "captureHashes": dict(self.capture_hashes),
                "nativeTimingUnit": "seconds-rounded-to-48khz-samples",
            },
            provider_input_format="json",
        )

    def _json(self, name: str) -> dict[str, Any]:
        try:
            value = json.loads(self._files[name])
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InworldReplayError(f"capture JSON is invalid: {name}") from error
        return _mapping(value, f"capture JSON {name}")

    def _validate_capture_identity(self) -> None:
        _require(self._request.get("provider") == "inworld", "wrong provider")
        config = _mapping(self._request.get("config"), "capture config")
        _require(
            config.get("model") == self.profile.engine
            and config.get("voiceId") == self.profile.voice_id,
            "wrong Inworld model or voice",
        )
        text_hash = hashlib.sha256(self._text.encode("utf-8")).hexdigest()
        _require(
            self._row.get("textHash") in (text_hash, f"sha256:{text_hash}"),
            "text hash mismatch",
        )

        _require(
            self._provider_payload
            == {
                "modelId": self.profile.engine,
                "voiceId": self.profile.voice_id,
                "text": self._text,
                "timestampType": "WORD",
                "audioConfig": {"audioEncoding": "LINEAR16", "speakingRate": 1.0},
            },
            "provider input differs from capture settings",
        )

    def _validate_request(self, request: SynthesisRequest) -> None:
        _require(
            request.profile == self.profile,
            "profile mismatch",
        )
        _require(
            request.block_id == self._row.get("blockId")
            and request.block_revision == self._row.get("blockRevision"),
            "block mismatch",
        )
        _require(request.text == self._text, "text mismatch")
        _require(
            request.settings == SynthesisSettings()
            and not request.pronunciations
            and not request.controls
            and request.timing_kinds == ("word", "sentence")
            and request.max_cost_usd == 0,
            "request settings mismatch",
        )

    def _decode_audio(self) -> tuple[bytes, int]:
        try:
            response_content = base64.b64decode(
                _string(self._response.get("audioContent"), "response audio"),
                validate=True,
            )
            with wave.open(io.BytesIO(self._files["audio.wav"]), "rb") as audio:
                _require(
                    (
                        audio.getcomptype(),
                        audio.getsampwidth(),
                        audio.getframerate(),
                        audio.getnchannels(),
                    )
                    == ("NONE", 2, SAMPLE_RATE, 1),
                    "WAV must be mono 48 kHz PCM16",
                )
                frames = audio.getnframes()
                pcm = audio.readframes(frames)
                _require(len(pcm) == frames * 2, "WAV is truncated")
        except (wave.Error, OSError, EOFError, ValueError) as error:
            if isinstance(error, InworldReplayError):
                raise
            raise InworldReplayError("capture audio is invalid") from error
        _require(
            response_content == self._files["audio.wav"],
            "response audio mismatch",
        )

        metadata = _mapping(self._request.get("audio"), "capture audio metadata")
        expected_audio_hash = self.capture_hashes["audio.wav"]
        _require(
            metadata.get("sha256")
            in (expected_audio_hash, expected_audio_hash.removeprefix("sha256:")),
            "WAV hash mismatch",
        )
        _require(
            (
                metadata.get("sampleRate"),
                metadata.get("channels"),
                metadata.get("samples"),
            )
            == (SAMPLE_RATE, 1, frames),
            "WAV metadata mismatch",
        )
        duration = _finite_fraction(metadata.get("durationSeconds"), "audio duration")
        _require(
            round(duration * SAMPLE_RATE) == frames,
            "WAV duration mismatch",
        )
        return pcm, frames

    def _map_marks(self) -> tuple[ProviderTimingMark, ...]:
        timestamp = _mapping(self._response.get("timestampInfo"), "timestamp info")
        alignment = _mapping(timestamp.get("wordAlignment"), "word alignment")
        words = native._characters(alignment.get("words"))
        if not words or "".join(words) != self._text:
            raise InworldReplayError(
                "native word text does not exactly cover capture text"
            )
        starts = alignment.get("wordStartTimeSeconds")
        ends = alignment.get("wordEndTimeSeconds")
        if not isinstance(starts, list) or not isinstance(ends, list):
            raise InworldReplayError("native word timing arrays are missing")
        _require(
            len(words) == len(starts) == len(ends),
            "native word timing arrays have different lengths",
        )
        for value in (*starts, *ends):
            _finite_fraction(value, "native word time")

        spans, status, _mismatch, valid = native._timed_spans(
            self._text, words, starts, ends
        )
        _require(
            valid and status == "exact",
            "native word alignment does not exactly map to text",
        )
        rows, metrics = native._project_tokens(self._tokens, spans, True, status)
        _require(
            all(row.get("mappingStatus") == "exact" for row in rows),
            "native word alignment does not exactly cover tokens",
        )
        _require(
            not metrics["rawNonFinite"] and not metrics["rawMissing"],
            "native timing contains non-finite values",
        )

        previous_start = Fraction(-1)
        previous_end = Fraction(-1)
        previous_sample_start = -1
        previous_sample_end = -1
        for span in spans:
            if not span.lexical:
                continue
            start, end = (
                _finite_fraction(span.native_start, "lexical start"),
                _finite_fraction(span.native_end, "lexical end"),
            )
            _require(
                start >= 0
                and end > start
                and end <= Fraction(self._audio_frames, SAMPLE_RATE),
                "native lexical interval is collapsed or outside audio",
            )
            _require(
                start > previous_start and start >= previous_end,
                "native lexical intervals tie, decrease, or overlap",
            )
            start_sample, end_sample = (
                round(start * SAMPLE_RATE),
                round(end * SAMPLE_RATE),
            )
            _require(
                start_sample > previous_sample_start
                and start_sample >= previous_sample_end
                and end_sample > start_sample
                and end_sample <= self._audio_frames,
                "native lexical interval collapses on the audio sample grid",
            )
            previous_start, previous_end = start, end
            previous_sample_start, previous_sample_end = start_sample, end_sample

        offsets = native._utf16_boundaries(self._text)
        marks: list[ProviderTimingMark] = []
        previous_token_start = -1
        previous_token_end = -1
        for token, row in zip(self._tokens, rows, strict=True):
            native_start = _finite_fraction(row.get("nativeStart"), "token start")
            native_end = _finite_fraction(row.get("nativeEnd"), "token end")
            start_sample, end_sample = (
                round(native_start * SAMPLE_RATE),
                round(native_end * SAMPLE_RATE),
            )
            _require(
                start_sample > previous_token_start
                and start_sample >= previous_token_end
                and end_sample > start_sample
                and end_sample <= self._audio_frames,
                "mapped token intervals tie, overlap, or exceed audio",
            )
            start_cp, end_cp = offsets[token.start_offset], offsets[token.end_offset]
            _require(
                self._text[start_cp:end_cp] == token.value,
                "mapped token does not round-trip to source text",
            )
            start_byte = len(self._text[:start_cp].encode("utf-8"))
            end_byte = len(self._text[:end_cp].encode("utf-8"))
            _require(
                self._text.encode("utf-8")[start_byte:end_byte].decode("utf-8")
                == token.value,
                "mapped token byte span does not round-trip",
            )
            marks.append(
                ProviderTimingMark(
                    kind="word",
                    time_ms=round(Fraction(start_sample * 1000, SAMPLE_RATE)),
                    start_byte=start_byte,
                    end_byte=end_byte,
                    start_utf16=token.start_offset,
                    end_utf16=token.end_offset,
                    value=token.value,
                    time_sample=start_sample,
                    end_sample=end_sample,
                    sample_rate=SAMPLE_RATE,
                )
            )
            previous_token_start, previous_token_end = start_sample, end_sample
        return tuple(marks)


def _mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise InworldReplayError(f"{name} must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise InworldReplayError(f"{name} must be a string")
    return value


def _finite_fraction(value: Any, name: str) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InworldReplayError(f"{name} must be a finite number")
    if not math.isfinite(float(value)):
        raise InworldReplayError(f"{name} must be a finite number")
    return Fraction(str(value))


def _require(condition: Any, message: str) -> None:
    if not condition:
        raise InworldReplayError(message)
