from __future__ import annotations

import base64
import json
from dataclasses import replace
from email.message import Message
from pathlib import Path
from typing import Any
from urllib.error import HTTPError

import pytest
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.configuration import FISH_PROFILE_ID, voice_profile
from vera_timeline_agent.narration.fish import (
    SAMPLE_RATE,
    FishError,
    FishProvider,
    timing_marks,
)
from vera_timeline_agent.narration.models import SynthesisRequest, SynthesisSettings
from vera_timeline_agent.narration.normalize import Normalizer
from vera_timeline_agent.narration.provider import SpeechProviderError
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig


def config() -> ServiceConfig:
    return ServiceConfig(
        profile=voice_profile(FISH_PROFILE_ID),
        settings=SynthesisSettings(rate="110%"),
        data_policy_attestation="fish_terms_accepted",
        max_cost_usd=0,
    )


def request(text: str = "Hello, world!") -> SynthesisRequest:
    return config().request_for({"id": "row", "version": 1, "text": text})


def snapshot(
    content: str,
    segments: list[tuple[str, float, float]],
    *,
    seq: int = 0,
    offset: float = 0,
    duration: float = 1,
) -> dict[str, Any]:
    return {
        "seq": seq,
        "content": content,
        "offset": offset,
        "alignment": {
            "audio_duration": duration,
            "segments": [
                {"text": text, "start": start, "end": end}
                for text, start, end in segments
            ],
        },
    }


def stream(value: dict[str, Any], *, samples: int = SAMPLE_RATE) -> bytes:
    event = {
        "content": value["content"],
        "chunk_seq": value["seq"],
        "chunk_audio_offset_sec": value["offset"],
        "alignment": value["alignment"],
        "audio_base64": base64.b64encode(b"\x01\x00" * samples).decode(),
    }
    return b"data: " + json.dumps(event, ensure_ascii=False).encode() + b"\n\n"


def test_adapter_returns_native_source_bound_samples_and_json_input() -> None:
    raw = stream(snapshot("Hello, world!", [("Hello", 0.08, 0.4), ("world", 0.5, 0.9)]))
    sent: list[tuple[bytes, str]] = []

    def transport(payload: bytes, model: str) -> list[bytes]:
        sent.append((payload, model))
        return [raw[:13], raw[13:]]

    result = FishProvider(transport=transport).synthesize(request())
    assert sent[0][1] == "s2.1-pro-free"
    assert json.loads(sent[0][0])["prosody"]["speed"] == 1.1
    assert result.audio_format == "pcm_s16le"
    assert result.provider_input_format == "json"
    words = [mark for mark in result.timing_marks if mark.kind == "word"]
    assert [(mark.value, mark.start_utf16, mark.end_utf16) for mark in words] == [
        ("Hello", 0, 5),
        ("world", 7, 12),
    ]
    assert words[0].time_sample == 3528
    assert words[0].end_sample == 17640
    assert result.provenance["effectiveSpeed"] == "provider_not_reported"


def test_multichunk_offsets_unicode_repetition_and_sentence_source_spans() -> None:
    text = "Dr. Zoë can't go.\n🌍 go, go!"
    first = snapshot(
        "Dr. Zoë can't go.",
        [
            ("Dr", 0.08, 0.2),
            ("Zoë", 0.2, 0.4),
            ("can", 0.4, 0.5),
            ("'t", 0.5, 0.6),
            ("go", 0.7, 0.9),
        ],
    )
    second = snapshot(
        "🌍 go, go!",
        [("🌍", 0.1, 0.3), ("go", 0.3, 0.5), ("go", 0.6, 0.9)],
        seq=1,
        offset=1.25,
        duration=1,
    )
    marks = timing_marks(text, (first, second), SAMPLE_RATE * 9 // 4)
    words = [mark for mark in marks if mark.kind == "word"]
    assert [mark.value for mark in words] == [
        "Dr",
        "Zoë",
        "can't",
        "go",
        "🌍",
        "go",
        "go",
    ]
    assert words[4].time_sample == 59535
    assert (
        words[5].start_utf16
        == len(text[: text.index("go, go")].encode("utf-16-le")) // 2
    )
    sentences = [mark.value for mark in marks if mark.kind == "sentence"]
    assert sentences == ["Dr. Zoë can't go.", "🌍 go, go!"]


def test_numbers_abbreviations_currency_combining_marks_and_zero_width_native_end() -> (
    None
):
    text = "At 3.5 p.m., e\u0301lan costs $12. Go, go!"
    values = [
        ("At", 0.0, 0.1),
        ("3", 0.1, 0.15),
        ("5", 0.15, 0.2),
        ("p", 0.2, 0.25),
        ("m", 0.25, 0.3),
        ("e\u0301lan", 0.3, 0.4),
        ("costs", 0.4, 0.5),
        ("12", 0.5, 0.6),
        ("Go", 0.7, 0.7),
        ("go", 0.8, 0.9),
    ]
    marks = timing_marks(text, (snapshot(text, values),), SAMPLE_RATE)
    assert [mark.value for mark in marks if mark.kind == "word"] == [
        "At",
        "3.5",
        "p.m",
        "e\u0301lan",
        "costs",
        "$12",
        "Go",
        "go",
    ]
    assert [mark.value for mark in marks if mark.kind == "sentence"] == [
        "At 3.5 p.m., e\u0301lan costs $12.",
        "Go, go!",
    ]


@pytest.mark.parametrize(
    "segments,match",
    [
        ([("Hello world", 0.0, 0.8)], "differs|phrase"),
        ([("Hello", 0.0, 0.8)], "incomplete"),
        ([("Hello", 0.4, 0.2), ("world", 0.5, 0.9)], "bounds"),
        ([("Hello", 0.0, 0.6), ("world", 0.5, 0.9)], "overlaps"),
        ([("Hello", 0.0, 0.4), ("world", 0.5, 1.1)], "bounds"),
        ([("Hello", float("nan"), 0.4), ("world", 0.5, 0.9)], "invalid"),
        ([("Hello", True, 0.4), ("world", 0.5, 0.9)], "invalid"),
    ],
)
def test_unusable_alignment_refuses(
    segments: list[tuple[str, float, float]], match: str
) -> None:
    with pytest.raises(FishError, match=match):
        timing_marks("Hello world", (snapshot("Hello world", segments),), SAMPLE_RATE)


def test_audio_duration_and_missing_chunk_refuse() -> None:
    value = snapshot("Hello", [("Hello", 0.0, 0.2)])
    with pytest.raises(FishError, match="duration"):
        timing_marks("Hello", (value,), SAMPLE_RATE * 2)
    with pytest.raises(FishError, match="sequence"):
        timing_marks("Hello", ({**value, "seq": 1},), SAMPLE_RATE)
    with pytest.raises(FishError, match="authored"):
        timing_marks("twenty", (snapshot("twenty", [("20", 0.0, 0.2)]),), SAMPLE_RATE)


def test_partial_call_is_not_published_or_reissued_after_restart(
    tmp_path: Path,
) -> None:
    calls: list[bytes] = []

    def transport(payload: bytes, model: str) -> list[bytes]:
        calls.append(payload)
        return [b'data: {"audio_base64":']

    cache = NarrationCache(tmp_path)
    for _attempt in range(2):
        service = NarrationService(
            cache=cache,
            provider=FishProvider(transport=transport),
            normalizer=Normalizer(),
            config=config(),
        )
        plan = service.plan_block({"id": "row", "version": 1, "text": "Hello"})
        with pytest.raises(SpeechProviderError, match=r"incomplete|reconciliation"):
            service._raw_result(request("Hello"), plan.request_hash[7:])
        assert not plan.cached
    assert len(calls) == 1
    assert not list((cache.root / "synthesis").iterdir())


def test_authentication_and_pricing_fail_before_transport() -> None:
    provider = FishProvider(
        transport=lambda payload, model: pytest.fail("transport called")
    )
    with pytest.raises(FishError, match="consent"):
        provider.synthesize(
            replace(request(), data_policy_attestation="provider_terms_accepted")
        )
    with pytest.raises(FishError, match="pricing"):
        provider.synthesize(
            replace(request(), pricing_policy_version="aws-polly-neural-2026-08-25")
        )


@pytest.mark.parametrize("status", [400, 401, 402, 403, 422, 429, 503])
def test_remote_errors_are_sanitized_and_never_retried(
    monkeypatch: pytest.MonkeyPatch, status: int
) -> None:
    from vera_timeline_agent.narration import fish

    calls: list[int] = []

    def fail(*args: object, **kwargs: object) -> None:
        calls.append(status)
        raise HTTPError("https://api.fish.audio", status, "private text", Message(), None)

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-only-key")
    monkeypatch.setattr(fish, "urlopen", fail)
    with pytest.raises(FishError, match=f"HTTP {status}") as error:
        list(FishProvider._stream(b"{}", "s2.1-pro-free"))
    assert "private text" not in str(error.value)
    assert len(calls) == 1


def test_transport_timeout_is_explicitly_uncertain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent.narration import fish

    def timeout(*args: object, **kwargs: object) -> None:
        raise TimeoutError("private text")

    monkeypatch.setenv("FISH_AUDIO_API_KEY", "test-only-key")
    monkeypatch.setattr(fish, "urlopen", timeout)
    with pytest.raises(FishError, match="uncertain"):
        list(FishProvider._stream(b"{}", "s2.1-pro-free"))


def test_invalid_credentials_are_not_echoed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FISH_AUDIO_API_KEY", "private\ncredential")
    with pytest.raises(FishError, match="missing or invalid") as error:
        FishProvider().preflight(request())
    assert "private" not in str(error.value)
