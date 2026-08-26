from __future__ import annotations

import io
import json

import pytest
from vera_timeline_agent.narration.models import (
    PronunciationEntry,
    SynthesisRequest,
    SynthesisSettings,
    TextControl,
    VoiceProfile,
)
from vera_timeline_agent.narration.polly import (
    PollyError,
    PollyProvider,
    build_polly_ssml,
    utf8_range_to_utf16,
)


def profile() -> VoiceProfile:
    return VoiceProfile(
        profile_id="aws-polly-joanna-neural-en-us-v1",
        provider="aws_polly",
        region="us-east-1",
        engine="neural",
        voice_id="Joanna",
        voice_version="provider_not_supplied",
        language="en-US",
    )


def request(text: str = "VERA says hello.") -> SynthesisRequest:
    return SynthesisRequest(
        block_id="block-1",
        block_revision=1,
        text=text,
        profile=profile(),
        settings=SynthesisSettings(),
        data_policy_attestation="opt_out_confirmed",
    )


def test_utf8_provider_offsets_map_to_utf16_without_normalizing_text() -> None:
    text = "A 🌍 élan"
    raw = text.encode("utf-8")
    start = raw.index("é".encode())
    end = start + len("é".encode())

    assert utf8_range_to_utf16(text, start, end) == (5, 7)


def test_ssml_escapes_authored_text_and_applies_disjoint_controls() -> None:
    req = SynthesisRequest(
        **{
            **request("VERA & team pause here.").__dict__,
            "pronunciations": (
                PronunciationEntry("VERA", "alias", "vair-uh", start=0, end=4),
            ),
            "controls": (
                TextControl("emphasis", 7, 11, "strong"),
                TextControl("pause", 17, 17, "250ms"),
            ),
        }
    )

    ssml, source_map = build_polly_ssml(req)

    assert req.text == "VERA & team pause here."
    assert b"VERA &amp; team" not in ssml
    assert b'<sub alias="vair-uh">VERA</sub>' in ssml
    assert b'&amp; <emphasis level="strong">team</emphasis>' in ssml
    assert b'<break time="250ms"/>' in ssml
    assert source_map.plain_text == req.text
    assert source_map.provider_input == ssml


def test_neural_ssml_omits_the_unsupported_neutral_pitch_attribute() -> None:
    ssml, _source_map = build_polly_ssml(request())

    assert b' rate="100%"' in ssml
    assert b' volume="0dB"' in ssml
    assert b" pitch=" not in ssml


def test_neural_ssml_rejects_non_neutral_pitch_before_provider() -> None:
    req = SynthesisRequest(
        **{
            **request().__dict__,
            "settings": SynthesisSettings(pitch="+10%"),
        }
    )

    with pytest.raises(PollyError, match="pitch is not supported by Polly Neural"):
        build_polly_ssml(req)


@pytest.mark.parametrize(
    ("pronunciations", "controls", "message"),
    [
        (
            (PronunciationEntry("VERA", "alias", "x", start=0, end=4),),
            (TextControl("emphasis", 2, 6, "strong"),),
            "overlap",
        ),
        (
            (PronunciationEntry("wrong", "alias", "x", start=0, end=4),),
            (),
            "does not match",
        ),
        ((), (TextControl("pause", 1, 2, "1s"),), "zero-width"),
        ((), (TextControl("emphasis", -1, 2, "strong"),), "bounds"),
    ],
)
def test_ambiguous_or_invalid_ssml_controls_fail_before_provider(
    pronunciations: tuple[PronunciationEntry, ...],
    controls: tuple[TextControl, ...],
    message: str,
) -> None:
    req = SynthesisRequest(
        **{
            **request().__dict__,
            "pronunciations": pronunciations,
            "controls": controls,
        }
    )
    with pytest.raises(PollyError, match=message):
        build_polly_ssml(req)


class FakePollyClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def synthesize_speech(self, **kwargs: object) -> dict[str, object]:
        self.calls.append(kwargs)
        if kwargs["OutputFormat"] == "pcm":
            return {
                "AudioStream": io.BytesIO(b"\x00\x00" * 8000),
                "ResponseMetadata": {"RequestId": "audio-request"},
            }
        marks = [
            {
                "time": 0,
                "type": "word",
                "start": str(kwargs["Text"]).encode().index(b"VERA"),
                "end": str(kwargs["Text"]).encode().index(b"VERA") + 4,
                "value": "VERA",
            },
            {
                "time": 500,
                "type": "sentence",
                "start": str(kwargs["Text"]).encode().index(b"VERA"),
                "end": str(kwargs["Text"]).encode().index(b"VERA")
                + len(b"VERA says hello."),
                "value": "VERA says hello.",
            },
        ]
        return {
            "AudioStream": io.BytesIO(
                b"".join(json.dumps(mark).encode() + b"\n" for mark in marks)
            ),
            "ResponseMetadata": {"RequestId": "timing-request"},
        }


def test_polly_adapter_makes_audio_and_timing_calls_with_complete_provenance() -> None:
    client = FakePollyClient()
    provider = PollyProvider(client=client, adapter_version="test-adapter")

    result = provider.synthesize(request())

    assert len(client.calls) == 2
    assert {call["OutputFormat"] for call in client.calls} == {"pcm", "json"}
    assert result.audio_format == "pcm_s16le"
    assert result.sample_rate == 16000
    assert result.channels == 1
    assert result.request_ids == ("audio-request", "timing-request")
    assert result.provenance["voiceVersion"] == "provider_not_supplied"
    assert result.provenance["adapterVersion"] == "test-adapter"
    assert result.timing_marks[0].start_utf16 == 0
    assert result.timing_marks[0].end_utf16 == 4


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda req: SynthesisRequest(**{**req.__dict__, "text": "x" * 3001}), "3,000"),
        (
            lambda req: SynthesisRequest(
                **{**req.__dict__, "data_policy_attestation": None}
            ),
            "data-policy",
        ),
        (
            lambda req: SynthesisRequest(**{**req.__dict__, "max_cost_usd": 0.0}),
            "cost ceiling",
        ),
        (
            lambda req: SynthesisRequest(
                **{**req.__dict__, "max_cost_usd": float("nan")}
            ),
            "finite",
        ),
        (
            lambda req: SynthesisRequest(
                **{
                    **req.__dict__,
                    "pronunciations": (
                        PronunciationEntry("VERA", "alias", "x" * 6000, start=0, end=4),
                    ),
                }
            ),
            "6,000",
        ),
    ],
)
def test_limits_attestation_and_cost_fail_before_any_provider_call(
    mutate: object, message: str
) -> None:
    client = FakePollyClient()
    provider = PollyProvider(client=client)
    req = mutate(request())  # type: ignore[operator]

    with pytest.raises(PollyError, match=message):
        provider.synthesize(req)
    assert client.calls == []


def test_malformed_nonmonotonic_and_out_of_bounds_marks_fail() -> None:
    class BadClient(FakePollyClient):
        def synthesize_speech(self, **kwargs: object) -> dict[str, object]:
            if kwargs["OutputFormat"] == "pcm":
                return super().synthesize_speech(**kwargs)
            return {
                "AudioStream": io.BytesIO(
                    b'{"time":10,"type":"word","start":5,"end":999,"value":"x"}\n'
                    b'{"time":1,"type":"word","start":0,"end":1,"value":"V"}\n'
                ),
                "ResponseMetadata": {"RequestId": "bad"},
            }

    with pytest.raises(PollyError, match="timing mark"):
        PollyProvider(client=BadClient()).synthesize(request())


def test_ssml_source_map_ignores_tags_and_maps_escaped_authored_characters() -> None:
    req = SynthesisRequest(
        **{
            **request("A & B").__dict__,
            "controls": (TextControl("pause", 2, 2, "100ms"),),
        }
    )
    ssml, source_map = build_polly_ssml(req)
    ampersand = ssml.index(b"&amp;")
    pause = ssml.index(b"<break")

    assert source_map.translate_provider_range(ampersand, ampersand + 5) == (2, 3)
    assert (
        source_map.translate_provider_range(pause, ssml.index(b"/>", pause) + 2) is None
    )


def test_ssml_control_ranges_use_accepted_utf16_offsets() -> None:
    req = SynthesisRequest(
        **{
            **request("A 🌍 B").__dict__,
            "pronunciations": (
                PronunciationEntry("🌍", "alias", "world", start=2, end=4),
            ),
        }
    )

    ssml, _source_map = build_polly_ssml(req)

    assert b'<sub alias="world">\xf0\x9f\x8c\x8d</sub>' in ssml
    with pytest.raises(PollyError, match="surrogate pair"):
        build_polly_ssml(
            SynthesisRequest(
                **{
                    **request("A 🌍 B").__dict__,
                    "controls": (TextControl("pause", 3, 3, "1s"),),
                }
            )
        )
