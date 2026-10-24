from __future__ import annotations

import base64
import io
import json
import math
import subprocess
import wave
from dataclasses import replace
from email.message import Message
from pathlib import Path
from types import SimpleNamespace
from urllib.error import HTTPError, URLError
from urllib.request import Request

import pytest
from vera_timeline_agent.narration import inworld
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.campaign import Ledger
from vera_timeline_agent.narration.configuration import (
    DEFAULT_PROFILE_ID,
    INWORLD_PROFILE_ID,
    default_profile,
    pricing_for,
    provider_for,
    voice_profile,
)
from vera_timeline_agent.narration.inworld import InworldError, InworldProvider
from vera_timeline_agent.narration.models import (
    PronunciationEntry,
    SynthesisRequest,
    SynthesisSettings,
    TextControl,
    VoiceProfile,
)
from vera_timeline_agent.narration.normalize import NormalizationResult
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig
from vera_timeline_agent.roundtrip_v2_narration import guard_service

BLOCK = {"id": "block-1", "version": 1, "text": "hello"}
CONSENT = "inworld_terms_accepted"
SAMPLE_RATE = 48_000
PCM = b"\x01\x00" * SAMPLE_RATE


def _wav(
    pcm: bytes = PCM, *, sample_rate: int = SAMPLE_RATE, channels: int = 1
) -> bytes:
    output = io.BytesIO()
    with wave.open(output, "wb") as audio:
        audio.setnchannels(channels)
        audio.setsampwidth(2)
        audio.setframerate(sample_rate)
        audio.writeframes(pcm)
    return output.getvalue()


def _truncated_pcm_wav() -> bytes:
    value = bytearray(_wav())
    value[40:44] = (SAMPLE_RATE * 2 + 2).to_bytes(4, "little")
    return bytes(value)


def _request(
    *,
    profile: VoiceProfile | None = None,
    settings: SynthesisSettings | None = None,
    text: str = "hello",
    attestation: str | None = CONSENT,
    max_cost_usd: float = 1.0,
) -> SynthesisRequest:
    selected = profile or voice_profile(INWORLD_PROFILE_ID)
    return ServiceConfig(
        profile=selected,
        settings=settings if settings is not None else SynthesisSettings(),
        data_policy_attestation=attestation,
        max_cost_usd=max_cost_usd,
    ).request_for({**BLOCK, "text": text})


def _response(
    request: SynthesisRequest,
    *,
    audio: bytes | None = None,
    words: list[str] | None = None,
    starts: list[float] | None = None,
    ends: list[float] | None = None,
) -> bytes:
    value = {
        "audioContent": base64.b64encode(_wav() if audio is None else audio).decode(
            "ascii"
        ),
        "timestampInfo": {
            "wordAlignment": {
                "words": words if words is not None else [request.text],
                "wordStartTimeSeconds": starts if starts is not None else [0.1],
                "wordEndTimeSeconds": ends if ends is not None else [0.8],
            }
        },
        "usage": {
            "modelId": request.profile.engine,
            "processedCharactersCount": len(request.text.encode("utf-16-le")) // 2,
        },
    }
    return json.dumps(value).encode("utf-8")


class _JSONResponse:
    def __init__(self, payload: bytes) -> None:
        self.headers = Message()
        self.headers["Content-Type"] = "application/json"
        self.payload = payload

    def __enter__(self) -> _JSONResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _limit: int = -1) -> bytes:
        return self.payload


class _CheapNormalizer:
    profile_id = "test-normalizer/v1"
    tool_fingerprint = "sha256:" + "0" * 64

    def normalize_pcm(
        self, audio: bytes, *, sample_rate: int, channels: int
    ) -> NormalizationResult:
        samples = len(audio) // 2
        return NormalizationResult(
            wav_bytes=b"normalized test audio",
            profile_id=self.profile_id,
            normalizer_version="test-normalizer/v1",
            tool_fingerprint=self.tool_fingerprint,
            sample_rate=sample_rate,
            channels=channels,
            sample_format="s16",
            duration_samples=samples,
            duration_ms=round(samples * 1000 / sample_rate),
            padding_samples=0,
            integrated_lufs=-16.0,
            true_peak_dbtp=-1.0,
            loudness_range_lu=1.0,
        )

    def placeholder(self, _block_id: str) -> NormalizationResult:
        raise AssertionError("valid synthetic responses should not need a placeholder")


def test_inworld_profile_default_and_model_pricing_are_configured() -> None:
    profile = voice_profile(INWORLD_PROFILE_ID)
    flash = replace(profile, engine="inworld-tts-2-flash")

    assert DEFAULT_PROFILE_ID == INWORLD_PROFILE_ID
    assert default_profile() == profile
    assert profile.provider == "inworld"
    assert (profile.engine, profile.voice_id) == ("inworld-tts-2", "Arthur")
    assert pricing_for(profile).unit == "utf16_units"
    assert pricing_for(profile).units("é🙂") == 3
    assert pricing_for(flash).version
    assert isinstance(provider_for(profile), InworldProvider)
    with pytest.raises(ValueError, match="unsupported provider/model pricing"):
        pricing_for(replace(profile, engine="unknown-model"))


def test_flash_request_uses_the_selected_voice_model_and_rate() -> None:
    profile = replace(
        voice_profile(INWORLD_PROFILE_ID),
        engine="inworld-tts-2-flash",
        voice_id="SyntheticAltVoice",
    )
    request = _request(profile=profile, settings=SynthesisSettings(rate="115%"))
    payload = json.loads(
        InworldProvider(transport=lambda _payload: b"").prepare_input(request)
    )

    assert payload == {
        "text": "hello",
        "voiceId": "SyntheticAltVoice",
        "modelId": "inworld-tts-2-flash",
        "timestampType": "WORD",
        "language": profile.language,
        "temperature": 1.0,
        "audioConfig": {
            "audioEncoding": "LINEAR16",
            "sampleRateHertz": SAMPLE_RATE,
            "speakingRate": 1.15,
        },
    }
    assert "deliveryMode" not in payload
    assert payload["temperature"] == 1.0


def test_complete_portal_base64_key_is_sent_as_basic_without_reencoding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    portal_key = "YWJjOnNlY3JldA=="
    requests: list[Request] = []
    monkeypatch.setenv("INWORLD_API_KEY", portal_key)

    def open_request(request: Request, *, timeout: int) -> _JSONResponse:
        assert timeout == 90
        requests.append(request)
        return _JSONResponse(b"{}")

    monkeypatch.setattr(inworld, "urlopen", open_request)

    assert InworldProvider._send(b"{}") == b"{}"
    assert len(requests) == 1
    assert requests[0].get_header("Authorization") == "Basic " + portal_key


def test_keychain_output_is_not_in_errors_or_subprocess_arguments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "private-keychain-value"
    calls: list[list[str]] = []
    monkeypatch.delenv("INWORLD_API_KEY", raising=False)
    monkeypatch.setattr(inworld, "sys", SimpleNamespace(platform="darwin"))

    def keychain_run(args: list[str], **_kwargs: object) -> SimpleNamespace:
        calls.append(args)
        return SimpleNamespace(returncode=1, stdout=secret, stderr=secret)

    monkeypatch.setattr(subprocess, "run", keychain_run)

    with pytest.raises(InworldError) as error:
        inworld._api_key()

    assert secret not in str(error.value)
    assert error.value.request_rejected
    assert calls == [
        [
            "/usr/bin/security",
            "find-generic-password",
            "-s",
            "com.vera.script-to-timeline",
            "-a",
            "inworld_api_key",
            "-w",
        ]
    ]
    assert all(secret not in argument for argument in calls[0])


def test_live_opener_refuses_redirects() -> None:
    opener = inworld.urlopen.__self__  # type: ignore[attr-defined]
    redirect_handler = next(
        handler
        for handler in opener.handlers
        if isinstance(handler, inworld._NoRedirect)
    )

    assert (
        redirect_handler.redirect_request(  # type: ignore[func-returns-value]
            Request(inworld.ENDPOINT),
            None,
            302,
            "Found",
            Message(),
            "https://other.example",
        )
        is None
    )


@pytest.mark.parametrize(
    ("status", "category"),
    [(401, "authentication"), (402, "funding/quota"), (429, "rate/quota")],
)
def test_http_auth_quota_and_rate_errors_are_sanitized_and_one_shot(
    monkeypatch: pytest.MonkeyPatch, status: int, category: str
) -> None:
    secret = "private provider response"
    calls = 0
    monkeypatch.setenv("INWORLD_API_KEY", "YWJjOnNlY3JldA==")

    def fail_once(_request: Request, *, timeout: int) -> None:
        nonlocal calls
        calls += 1
        raise HTTPError(
            inworld.ENDPOINT,
            status,
            "error",
            Message(),
            io.BytesIO(secret.encode()),
        )

    monkeypatch.setattr(inworld, "urlopen", fail_once)

    with pytest.raises(InworldError, match=category) as error:
        InworldProvider._send(b"{}")

    assert calls == 1
    assert secret not in str(error.value)
    assert error.value.request_rejected


def test_network_failure_is_sanitized_and_one_shot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "private transport detail"
    calls = 0
    monkeypatch.setenv("INWORLD_API_KEY", "YWJjOnNlY3JldA==")

    def fail_once(_request: Request, *, timeout: int) -> None:
        nonlocal calls
        calls += 1
        raise URLError(secret)

    monkeypatch.setattr(inworld, "urlopen", fail_once)

    with pytest.raises(InworldError, match="charge uncertain") as error:
        InworldProvider._send(b"{}")

    assert calls == 1
    assert secret not in str(error.value)


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        (b"not-json", "malformed or truncated"),
        (_response(_request(), audio=_wav()[:-1]), "WAV container is incomplete"),
    ],
    ids=["malformed-json", "truncated-wav"],
)
def test_malformed_or_truncated_response_fails_after_one_transport_call(
    raw: bytes,
    message: str,
) -> None:
    calls: list[bytes] = []
    request = _request()

    def transport(payload: bytes) -> bytes:
        calls.append(payload)
        return raw

    provider = InworldProvider(transport=transport)

    with pytest.raises(InworldError, match=message):
        provider.synthesize(request)

    assert len(calls) == 1


def test_response_returns_exact_mono_pcm48_samples_and_native_word_marks() -> None:
    text = "Måns says go."
    request = _request(text=text)
    result = InworldProvider().decode_response(
        request,
        _response(
            request,
            words=["Måns", " ", "says", " ", "go", "."],
            starts=[0.10003, 0.2, 0.30003, 0.45, 0.55003, 0.8],
            ends=[0.19, 0.25, 0.44, 0.5, 0.79, 0.82],
        ),
    )

    assert result.audio_bytes == PCM
    assert len(result.audio_bytes) // 2 == SAMPLE_RATE
    assert (result.audio_format, result.sample_rate, result.channels) == (
        "pcm_s16le",
        SAMPLE_RATE,
        1,
    )
    assert [mark.value for mark in result.timing_marks] == ["Måns", "says", "go"]
    assert [mark.start_utf16 for mark in result.timing_marks] == [0, 5, 10]
    assert [mark.end_utf16 for mark in result.timing_marks] == [4, 9, 12]
    assert [mark.start_byte for mark in result.timing_marks] == [0, 6, 11]
    assert [mark.time_sample for mark in result.timing_marks] == [4801, 14401, 26401]
    assert [mark.time_ms for mark in result.timing_marks] == [100, 300, 550]
    assert all(mark.sample_rate == SAMPLE_RATE for mark in result.timing_marks)


@pytest.mark.parametrize(
    ("audio", "message"),
    [
        (_wav(sample_rate=44_100), "mono 48 kHz"),
        (_wav(channels=2), "mono 48 kHz"),
        (b"NOPE" + _wav()[4:], "WAV container is incomplete"),
        (_truncated_pcm_wav(), "PCM is empty or truncated"),
    ],
    ids=["wrong-rate", "wrong-channels", "bad-riff-header", "short-pcm-data"],
)
def test_response_rejects_wrong_wav_format_or_truncated_pcm(
    audio: bytes, message: str
) -> None:
    request = _request()

    with pytest.raises(InworldError, match=message):
        InworldProvider().decode_response(request, _response(request, audio=audio))


@pytest.mark.parametrize(
    ("usage", "message"),
    [
        (None, "model/usage missing"),
        ({"modelId": "wrong-model", "processedCharactersCount": 5}, "model/usage"),
        (
            {"modelId": "inworld-tts-2", "processedCharactersCount": True},
            "count differs",
        ),
        (
            {"modelId": "inworld-tts-2", "processedCharactersCount": math.nan},
            "count differs",
        ),
    ],
    ids=["missing-usage", "wrong-model", "boolean-count", "nonfinite-count"],
)
def test_response_requires_matching_model_and_finite_integer_usage(
    usage: dict[str, object] | None, message: str
) -> None:
    request = _request()
    response = json.loads(_response(request))
    response["usage"] = usage

    with pytest.raises(InworldError, match=message):
        InworldProvider().decode_response(request, json.dumps(response).encode())


def test_oversize_response_is_rejected_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = _request()
    monkeypatch.setattr(inworld, "MAX_RESPONSE_BYTES", 32)

    with pytest.raises(InworldError, match="malformed or truncated"):
        InworldProvider().decode_response(request, b"x" * 33)


def test_oversize_transport_response_is_rejected_without_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = 0
    monkeypatch.setenv("INWORLD_API_KEY", "YWJjOnNlY3JldA==")
    monkeypatch.setattr(inworld, "MAX_RESPONSE_BYTES", 8)

    def oversized(_request: Request, *, timeout: int) -> _JSONResponse:
        nonlocal calls
        calls += 1
        return _JSONResponse(b"123456789")

    monkeypatch.setattr(inworld, "urlopen", oversized)

    with pytest.raises(InworldError, match="exceeds retention limit"):
        InworldProvider._send(b"{}")

    assert calls == 1


def test_malformed_native_word_mapping_fails_after_one_transport_call() -> None:
    request = _request()
    response = json.loads(_response(request))
    response["timestampInfo"]["wordAlignment"]["words"] = ["different"]
    raw = json.dumps(response).encode()
    calls: list[bytes] = []

    def transport(payload: bytes) -> bytes:
        calls.append(payload)
        return raw

    provider = InworldProvider(transport=transport)

    with pytest.raises(InworldError):
        provider.synthesize(request)

    assert len(calls) == 1


def test_inworld_input_rejects_unsupported_controls_and_utf16_overflow() -> None:
    request = _request()
    provider = InworldProvider()
    invalid = (
        (
            replace(request, profile=replace(request.profile, engine="unknown")),
            "provider/model",
        ),
        (replace(request, settings=SynthesisSettings(pitch="+5%")), "pitch/volume"),
        (replace(request, settings=SynthesisSettings(volume="+3dB")), "pitch/volume"),
        (
            replace(
                request,
                pronunciations=(PronunciationEntry("hello", "alias", "hullo", 0, 5),),
            ),
            "controls unsupported",
        ),
        (
            replace(request, controls=(TextControl("pause", 0, 0, "250ms"),)),
            "controls unsupported",
        ),
        (replace(request, text="🙂" * 1001), "2000 UTF-16 units"),
    )
    for unsupported, message in invalid:
        with pytest.raises(InworldError, match=message):
            provider.prepare_input(unsupported)

    boundary = replace(request, text="🙂" * 1000)
    assert json.loads(provider.prepare_input(boundary))["text"] == boundary.text


def test_preflight_requires_matching_pricing_consent_and_cost_ceiling() -> None:
    request = _request()
    provider = InworldProvider(transport=lambda _payload: b"")

    with pytest.raises(InworldError, match="pricing policy"):
        provider.preflight(replace(request, pricing_policy_version="stale"))
    with pytest.raises(InworldError, match="consent"):
        provider.preflight(replace(request, data_policy_attestation=None))
    with pytest.raises(InworldError, match="cost ceiling"):
        provider.preflight(replace(request, max_cost_usd=0.0))
    provider.preflight(request)


def test_service_cache_identity_covers_voice_model_rate_and_adapter_and_reuses(
    tmp_path: Path,
) -> None:
    base = voice_profile(INWORLD_PROFILE_ID)
    cases = (
        (base, SynthesisSettings(), "inworld-live-word-pcm48/v1"),
        (
            replace(base, voice_id="SyntheticOtherVoice"),
            SynthesisSettings(),
            "inworld-live-word-pcm48/v1",
        ),
        (
            replace(base, engine="inworld-tts-2-flash"),
            SynthesisSettings(),
            "inworld-live-word-pcm48/v1",
        ),
        (base, SynthesisSettings(rate="110%"), "inworld-live-word-pcm48/v1"),
        (base, SynthesisSettings(), "inworld-live-word-pcm48/v2"),
    )
    cache = NarrationCache(tmp_path / "cache")
    requests: list[bytes] = []
    hashes: list[str] = []

    def transport(payload: bytes) -> bytes:
        requests.append(payload)
        request = _request_from_payload(payload)
        return _response(request)

    for profile, settings, adapter_version in cases:
        provider = InworldProvider(transport=transport)
        provider.adapter_version = adapter_version
        service = NarrationService(
            cache=cache,
            provider=provider,
            normalizer=_CheapNormalizer(),  # type: ignore[arg-type]
            config=ServiceConfig(
                profile=profile,
                settings=settings,
                data_policy_attestation=CONSENT,
            ),
        )

        first = service.process_block(BLOCK)
        hashes.append(first.request_hash)
        assert first.status == "ready"
        assert len(requests) == len(hashes)
        second = service.process_block(BLOCK)
        assert second.synthesis_disposition == "reused"
        assert len(requests) == len(hashes)

    assert len(set(hashes)) == len(cases)


def _request_from_payload(payload: bytes) -> SynthesisRequest:
    value = json.loads(payload)
    return _request(
        profile=replace(
            voice_profile(INWORLD_PROFILE_ID),
            engine=value["modelId"],
            voice_id=value["voiceId"],
        ),
        text=value["text"],
    )


def test_missing_credential_does_not_block_later_authorized_attempt(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("INWORLD_API_KEY", raising=False)
    monkeypatch.setattr(inworld, "sys", SimpleNamespace(platform="linux"))
    cache = NarrationCache(tmp_path / "cache")
    normalizer = _CheapNormalizer()
    monkeypatch.setattr(
        normalizer,
        "placeholder",
        lambda _block_id: normalizer.normalize_pcm(PCM, sample_rate=48000, channels=1),
    )
    service = NarrationService(
        cache=cache,
        provider=InworldProvider(),
        normalizer=normalizer,  # type: ignore[arg-type]
        config=ServiceConfig(data_policy_attestation=CONSENT),
    )
    ledger = Ledger(tmp_path / "ledger.json")
    service = guard_service(service, ledger, confirm_provider_call=True)
    failed = service.process_block(BLOCK)
    assert failed.status == "failed" and failed.extra["requestRejected"]
    assert ledger.rows() == []
    monkeypatch.setenv("INWORLD_API_KEY", "YWJjOnNlY3JldA==")
    monkeypatch.setattr(
        inworld,
        "urlopen",
        lambda *_args, **_kwargs: _JSONResponse(_response(_request())),
    )
    recovered = service.process_block(BLOCK)
    assert recovered.status == "ready"
    assert recovered.synthesis_disposition == "generated"
    assert len(ledger.rows()) == 1


def test_joined_symbols_are_rejected_before_transport() -> None:
    calls: list[bytes] = []

    def transport(payload: bytes) -> bytes:
        calls.append(payload)
        return b""

    with pytest.raises(InworldError, match="joined-symbol"):
        InworldProvider(transport=transport).synthesize(
            _request(text="Meet 👨‍👩‍👧 now")
        )
    assert calls == []
