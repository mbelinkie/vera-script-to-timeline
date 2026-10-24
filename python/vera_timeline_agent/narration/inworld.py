"""Live synchronous Inworld WORD/48 kHz adapter; one attempt, no fallback."""

from __future__ import annotations

import base64
import binascii
import io
import json
import math
import os
import re
import subprocess
import sys
import wave
from collections.abc import Callable
from http.client import HTTPException
from typing import Any, cast
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from vera_timeline_agent.narration.configuration import pricing_for
from vera_timeline_agent.narration.inworld_timing import (
    SAMPLE_RATE,
    InworldTimingError,
    timing_marks,
)
from vera_timeline_agent.narration.models import (
    ProviderResult,
    SynthesisRequest,
    canonical_json_bytes,
)
from vera_timeline_agent.narration.provider import SpeechProviderError

ENDPOINT = "https://api.inworld.ai/tts/v1/voice"
ADAPTER_VERSION = "inworld-live-word-pcm48/v1"
MAX_RESPONSE_BYTES = 128 * 1024 * 1024


class InworldError(SpeechProviderError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


urlopen = build_opener(_NoRedirect()).open


def _api_key() -> str:
    key = os.environ.get("INWORLD_API_KEY", "").strip()
    if not key and sys.platform == "darwin":
        try:
            result = subprocess.run(
                [
                    "/usr/bin/security",
                    "find-generic-password",
                    "-s",
                    "com.vera.script-to-timeline",
                    "-a",
                    "inworld_api_key",
                    "-w",
                ],
                capture_output=True,
                check=False,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                key = result.stdout.strip()
        except (OSError, subprocess.SubprocessError):
            pass
    if not key or len(key) > 4096 or any(not 33 <= ord(c) <= 126 for c in key):
        raise InworldError(
            "INWORLD_API_KEY missing or invalid in environment/macOS Keychain",
            request_rejected=True,
        )
    # Portal supplies the complete Base64 credential. Never encode it again.
    return key


class InworldProvider:
    adapter_version = ADAPTER_VERSION

    def __init__(self, *, transport: Callable[[bytes], bytes] | None = None) -> None:
        self._transport = transport

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        profile, settings = request.profile, request.settings
        if profile.provider != "inworld" or profile.engine not in {
            "inworld-tts-2",
            "inworld-tts-2-flash",
        }:
            raise InworldError("unsupported Inworld provider/model; no fallback")
        if (
            not profile.voice_id
            or profile.voice_id != profile.voice_id.strip()
            or any(ord(c) < 32 for c in profile.voice_id)
        ):
            raise InworldError("Inworld requires an explicit valid voice ID")
        if request.pronunciations or request.controls or profile.lexicons:
            raise InworldError(
                "Inworld pronunciation/pause/emphasis controls unsupported"
            )
        if settings.pitch != "0%" or settings.volume != "0dB":
            raise InworldError("Inworld pitch/volume controls unsupported")
        if not re.fullmatch(r"\d+(?:\.\d+)?%", settings.rate):
            raise InworldError("Inworld speed must be an explicit percentage")
        speed = float(settings.rate[:-1]) / 100
        if not 0.5 <= speed <= 1.5:
            raise InworldError("Inworld speed must be between 50% and 150%")
        units = len(request.text.encode("utf-16-le")) // 2
        if "\u200d" in request.text:
            raise InworldError("Inworld joined-symbol source spans are unsupported")
        if (
            not request.text.strip()
            or units > 2000
            or re.search(r"\[[^\]]*\]", request.text)
        ):
            raise InworldError(
                "Inworld requires plain text within 2000 UTF-16 units; "
                "inline controls unsupported"
            )
        if request.timing_kinds != ("word", "sentence"):
            raise InworldError("Inworld requires word and sentence timing")
        payload: dict[str, Any] = {
            "text": request.text,
            "voiceId": profile.voice_id,
            "modelId": profile.engine,
            "timestampType": "WORD",
            "language": profile.language,
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": SAMPLE_RATE,
                "speakingRate": speed,
            },
        }
        if profile.engine == "inworld-tts-2":
            payload["deliveryMode"] = "BALANCED"
        else:
            payload["temperature"] = 1.0
        return canonical_json_bytes(payload)

    def preflight(self, request: SynthesisRequest) -> None:
        self.prepare_input(request)
        policy = pricing_for(request.profile)
        if request.pricing_policy_version != policy.version:
            raise InworldError("Inworld pricing policy does not match selected model")
        if request.data_policy_attestation != "inworld_terms_accepted":
            raise InworldError("explicit Inworld data-policy consent required")
        if not math.isfinite(request.max_cost_usd) or request.max_cost_usd < 0:
            raise InworldError("cost ceiling must be finite and nonnegative")
        if policy.estimate(request.text) > request.max_cost_usd:
            raise InworldError("Inworld estimated charge exceeds cost ceiling")
        if self._transport is None:
            _api_key()

    @staticmethod
    def _send(payload: bytes) -> bytes:
        request = Request(
            ENDPOINT,
            data=payload,
            method="POST",
            headers={
                "Authorization": "Basic " + _api_key(),
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urlopen(request, timeout=90) as response:
                if response.headers.get_content_type() != "application/json":
                    raise InworldError(
                        "Inworld response is not JSON; no retry performed"
                    )
                data = response.read(MAX_RESPONSE_BYTES + 1)
                if len(data) > MAX_RESPONSE_BYTES:
                    raise InworldError(
                        "Inworld response exceeds retention limit; no retry performed"
                    )
                return cast(bytes, data)
        except HTTPError as error:
            category = {
                401: "authentication",
                403: "access",
                402: "funding/quota",
                429: "rate/quota",
                400: "request/model",
                422: "request/model",
            }.get(error.code, "service")
            raise InworldError(
                f"Inworld {category} error (HTTP {error.code}); no retry performed",
                request_rejected=error.code in {400, 401, 402, 403, 422, 429},
            ) from None
        except (URLError, TimeoutError, OSError, HTTPException):
            raise InworldError(
                "Inworld transport failed; charge uncertain; no retry performed"
            ) from None

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.preflight(request)
        payload = self.prepare_input(request)
        raw = (self._transport or self._send)(payload)
        try:
            return self.decode_response(request, raw)
        except InworldError as error:
            error.response_files = {
                "provider-input.json": payload,
                "provider-response.json": raw,
            }
            raise

    def decode_response(self, request: SynthesisRequest, raw: bytes) -> ProviderResult:
        """Offline decoder also used by tests; never requests replacement audio."""
        payload = self.prepare_input(request)
        try:
            if len(raw) > MAX_RESPONSE_BYTES:
                raise ValueError()
            response = json.loads(raw)
            if not isinstance(response, dict):
                raise ValueError()
            usage = response.get("usage")
            if (
                not isinstance(usage, dict)
                or usage.get("modelId") != request.profile.engine
            ):
                raise InworldError("Inworld response model/usage missing or mismatched")
            count = usage.get("processedCharactersCount")
            if (
                type(count) is not int
                or count != len(request.text.encode("utf-16-le")) // 2
            ):
                raise InworldError(
                    "Inworld response processed character count differs from source"
                )
            audio = base64.b64decode(response["audioContent"], validate=True)
            if audio[:4] != b"RIFF" or int.from_bytes(audio[4:8], "little") + 8 != len(
                audio
            ):
                raise InworldError("Inworld WAV container is incomplete")
            with wave.open(io.BytesIO(audio), "rb") as wav:
                if (
                    wav.getcomptype(),
                    wav.getsampwidth(),
                    wav.getframerate(),
                    wav.getnchannels(),
                ) != ("NONE", 2, SAMPLE_RATE, 1):
                    raise InworldError("Inworld audio must be mono 48 kHz PCM16 WAV")
                frames = wav.getnframes()
                pcm = wav.readframes(frames)
                if frames <= 0 or len(pcm) != frames * 2:
                    raise InworldError("Inworld PCM is empty or truncated")
            marks = timing_marks(request.text, response, frames)
        except InworldError:
            raise
        except InworldTimingError as error:
            raise InworldError(str(error)) from None
        except (
            ValueError,
            TypeError,
            KeyError,
            binascii.Error,
            wave.Error,
            EOFError,
            OSError,
        ):
            raise InworldError(
                "Inworld response/audio is malformed or truncated; no retry performed"
            ) from None
        return ProviderResult(
            audio_bytes=pcm,
            audio_format="pcm_s16le",
            sample_rate=SAMPLE_RATE,
            channels=1,
            provider_input=payload,
            provider_input_format="json",
            timing_marks=marks,
            provenance={
                "provider": "inworld",
                "engine": request.profile.engine,
                "region": request.profile.region,
                "voiceId": request.profile.voice_id,
                "voiceVersion": request.profile.voice_version,
                "adapterVersion": self.adapter_version,
                "timingSource": "native_word_alignment",
                "timingSampleRate": SAMPLE_RATE,
                "nativeWordEnds": "structural_only_not_verified_audible_support",
            },
        )
