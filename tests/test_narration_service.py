from __future__ import annotations

import copy
import html
import json
import math
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, cast

import pytest
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.configuration import (
    FISH_PROFILE_ID,
    INWORLD_PROFILE_ID,
)
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import Normalizer
from vera_timeline_agent.narration.service import (
    JOANNA_PROFILE_ID,
    MATTHEW_PROFILE_ID,
    NarrationService,
    ServiceConfig,
    default_profile,
    voice_profile,
)

ROOT = Path(__file__).resolve().parents[1]
MINIMAL = ROOT / "tests/data/slice_1_1/minimal.script-document.json"
TORTURE = ROOT / "tests/data/slice_1_1/torture.script-document.json"


def pcm_for_text(text: str) -> bytes:
    sample_count = 8000 + len(text) * 20
    return b"".join(
        struct.pack("<h", round(7000 * math.sin(2 * math.pi * 330 * i / 16000)))
        for i in range(sample_count)
    )


class FakeProvider:
    adapter_version = "fake-provider/v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.requests: list[SynthesisRequest] = []
        self.fail = fail

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{html.escape(request.text)}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("deliberate provider outage")
        raw = request.text.encode()
        return ProviderResult(
            audio_bytes=pcm_for_text(request.text),
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    kind="sentence",
                    time_ms=0,
                    start_byte=0,
                    end_byte=len(raw),
                    start_utf16=0,
                    end_utf16=len(request.text.encode("utf-16-le")) // 2,
                    value=request.text,
                ),
            ),
            provenance={
                "provider": "fake",
                "region": "local-test",
                "engine": "test",
                "voiceId": "test",
                "voiceVersion": "v1",
                "adapterVersion": self.adapter_version,
            },
            request_ids=("fake-request",),
        )


def document(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))


def service(tmp_path: Path, provider: FakeProvider) -> NarrationService:
    return NarrationService(
        cache=NarrationCache(tmp_path / "cache"),
        provider=provider,
        normalizer=Normalizer(),
        config=ServiceConfig(data_policy_attestation="inworld_terms_accepted"),
    )


def test_paragraph_linefeeds_keep_provider_input_but_not_source_identity() -> None:
    baseline: dict[str, Any] = {
        "id": "00000000-0000-4000-8000-000000000581",
        "version": 1,
        "text": "Keep the light on ",
        "tokens": [
            {"id": "t1", "value": "Keep", "startOffset": 0, "endOffset": 4},
            {"id": "t2", "value": "the", "startOffset": 5, "endOffset": 8},
            {"id": "t3", "value": "light", "startOffset": 9, "endOffset": 14},
            {"id": "t4", "value": "on", "startOffset": 15, "endOffset": 17},
        ],
    }
    paragraph = {**baseline, "text": "Keep the\nlight on\n"}
    config = ServiceConfig()
    provider = FakeProvider()

    ordinary = config.request_for(baseline)
    laid_out = config.request_for(paragraph)

    assert ordinary.text == laid_out.text == baseline["text"]
    assert provider.prepare_input(ordinary) == provider.prepare_input(laid_out)
    assert ordinary.source_text_hash is None
    assert laid_out.source_text_hash == sha256_bytes(paragraph["text"].encode("utf-8"))
    assert ordinary.identity(
        provider.prepare_input(ordinary), provider.adapter_version
    ) != laid_out.identity(provider.prepare_input(laid_out), provider.adapter_version)
    # Both variants are frozen against equal-width source separators.
    assert baseline["tokens"] == paragraph["tokens"]
    assert len(ordinary.text.encode("utf-16-le")) == len(
        paragraph["text"].encode("utf-16-le")
    )


@pytest.mark.parametrize(
    ("source", "single_line", "word_offsets"),
    [
        ("🌍\nhello\n", "🌍 hello ", (3, 8)),
        ("🌍\r\nhello\r\n", "🌍  hello  ", (4, 9)),
        ("hello\rworld", "hello world", (6, 11)),
    ],
)
def test_provider_projection_replaces_each_cr_lf_utf16_unit(
    source: str, single_line: str, word_offsets: tuple[int, int]
) -> None:
    # Emoji occupy two UTF-16 units, CRLF two; neither is allowed to shift
    # subsequent frozen word offsets in the provider's timing coordinates.
    start, end = word_offsets
    word = source.encode("utf-16-le")[start * 2 : end * 2].decode("utf-16-le")
    block = {
        "id": "00000000-0000-4000-8000-000000000582",
        "version": 1,
        "text": source,
        "tokens": [
            {"id": "frozen-word", "value": word, "startOffset": start, "endOffset": end}
        ],
    }
    request = ServiceConfig().request_for(block)
    comparator = ServiceConfig().request_for({**block, "text": single_line})
    provider = FakeProvider()

    assert request.text == comparator.text == single_line
    assert provider.prepare_input(request) == provider.prepare_input(comparator)
    assert request.source_text_hash == sha256_bytes(source.encode("utf-8"))
    assert comparator.source_text_hash is None
    assert len(request.text.encode("utf-16-le")) == len(source.encode("utf-16-le"))
    assert len(request.text.encode("utf-16-le")) == len(
        comparator.text.encode("utf-16-le")
    )
    assert (
        request.text.encode("utf-16-le")[start * 2 : end * 2].decode("utf-16-le")
        == word
    )


def test_inworld_is_default_and_fish_and_polly_profiles_remain_selectable() -> None:
    default = default_profile()
    assert default.profile_id == INWORLD_PROFILE_ID
    assert default.provider == "inworld"
    assert default.engine == "inworld-tts-2"
    assert default.voice_id == "Arthur"
    fish = voice_profile(FISH_PROFILE_ID)
    assert (fish.provider, fish.voice_id) == (
        "fish_audio",
        "f051ceb7fd8d47f09f63944298f589fc",
    )
    assert voice_profile(MATTHEW_PROFILE_ID).voice_id == "Matthew"
    assert voice_profile(JOANNA_PROFILE_ID).voice_id == "Joanna"


@pytest.mark.slow
def test_voice_profile_change_misses_synthesis_while_normalization_is_content_addressed(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    cache = NarrationCache(tmp_path / "cache")
    matthew = NarrationService(
        cache=cache,
        provider=provider,
        normalizer=Normalizer(),
        config=ServiceConfig(
            profile=voice_profile(MATTHEW_PROFILE_ID),
            data_policy_attestation="provider_terms_accepted",
        ),
    )
    joanna = NarrationService(
        cache=cache,
        provider=provider,
        normalizer=Normalizer(),
        config=ServiceConfig(
            profile=voice_profile(JOANNA_PROFILE_ID),
            data_policy_attestation="provider_terms_accepted",
        ),
    )

    matthew_asset = matthew.process_document(document(MINIMAL))[0]
    joanna_asset = joanna.process_document(document(MINIMAL))[0]

    assert len(provider.requests) == 2
    assert [request.profile.voice_id for request in provider.requests] == [
        "Matthew",
        "Joanna",
    ]
    assert joanna_asset.synthesis_disposition == "generated"
    # The fake provider deliberately returns identical PCM for both voices, so
    # the raw-content-addressed normalization layer is safely reused.
    assert joanna_asset.normalization_disposition == "reused"
    assert matthew_asset.request_hash != joanna_asset.request_hash
    assert matthew_asset.asset_id != joanna_asset.asset_id


@pytest.mark.slow
def test_unchanged_document_reuses_every_layer_and_excluded_is_never_sent(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    subject = service(tmp_path, provider)

    first = subject.process_document(document(TORTURE))
    second = subject.process_document(document(TORTURE))

    assert len(first) == 1
    assert len(provider.requests) == 1
    assert provider.requests[0].text == "Meet me here, then look beyond."
    assert first[0].status == "ready"
    assert first[0].synthesis_disposition == "generated"
    assert first[0].normalization_disposition == "generated"
    assert second[0].synthesis_disposition == "reused"
    assert second[0].normalization_disposition == "reused"
    assert "Unused alternative." not in {item.text for item in provider.requests}


@pytest.mark.slow
def test_one_edited_block_regenerates_exactly_one_and_reuses_other_blocks(
    tmp_path: Path,
) -> None:
    original = document(MINIMAL)
    second_block = copy.deepcopy(original["activeDraft"]["blocks"][1])
    second_block["id"] = "21000000-0000-4000-8000-000000000004"
    second_block["text"] = "Second block."
    second_block["version"] = 1
    original["activeDraft"]["blocks"].append(second_block)
    provider = FakeProvider()
    subject = service(tmp_path, provider)

    first = subject.process_document(original)
    edited = copy.deepcopy(original)
    edited["activeDraft"]["blocks"][1]["text"] = "Hello changed world."
    edited["activeDraft"]["blocks"][1]["version"] = 2
    second = subject.process_document(edited)

    assert len(first) == len(second) == 2
    assert len(provider.requests) == 3
    by_block = {asset.block_id: asset for asset in second}
    assert by_block[second_block["id"]].synthesis_disposition == "reused"
    assert (
        by_block[original["activeDraft"]["blocks"][1]["id"]].synthesis_disposition
        == "generated"
    )


@pytest.mark.slow
def test_normalization_profile_change_reuses_raw_provider_result(
    tmp_path: Path,
) -> None:
    provider = FakeProvider()
    cache = NarrationCache(tmp_path / "cache")
    first = NarrationService(
        cache=cache,
        provider=provider,
        normalizer=Normalizer(profile_id="profile-one"),
        config=ServiceConfig(data_policy_attestation="inworld_terms_accepted"),
    )
    second = NarrationService(
        cache=cache,
        provider=provider,
        normalizer=Normalizer(profile_id="profile-two"),
        config=ServiceConfig(data_policy_attestation="inworld_terms_accepted"),
    )

    first.process_document(document(MINIMAL))
    result = second.process_document(document(MINIMAL))

    assert len(provider.requests) == 1
    assert result[0].synthesis_disposition == "reused"
    assert result[0].normalization_disposition == "generated"


@pytest.mark.slow
def test_provider_failure_publishes_audible_failed_placeholder(tmp_path: Path) -> None:
    result = service(tmp_path, FakeProvider(fail=True)).process_document(
        document(MINIMAL)
    )

    assert len(result) == 1
    asset = result[0]
    assert asset.status == "failed"
    assert asset.failure_reason == "provider: deliberate provider outage"
    assert asset.duration_samples == 48000
    assert asset.normalized_audio_hash.startswith("sha256:")
    audio = tmp_path / "cache" / asset.locators["audio"]
    assert audio.exists()
    assert audio.stat().st_size > 1000


@pytest.mark.slow
def test_concurrent_same_block_calls_provider_once(tmp_path: Path) -> None:
    provider = FakeProvider()
    subject = service(tmp_path, provider)
    value = document(MINIMAL)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(
            executor.map(lambda _: subject.process_document(value), range(2))
        )

    assert len(provider.requests) == 1
    assert {result[0].synthesis_disposition for result in results} == {
        "generated",
        "reused",
    }
    assert results[0][0].asset_id == results[1][0].asset_id
