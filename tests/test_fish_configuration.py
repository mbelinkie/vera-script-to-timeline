from __future__ import annotations

import io
import json
from dataclasses import replace
from pathlib import Path

import pytest
from vera_timeline_agent.narration import cli
from vera_timeline_agent.narration.configuration import (
    FISH_PROFILE_ID,
    MATTHEW_PROFILE_ID,
    MW1_REFERENCE_ID,
    default_profile,
    pricing_for,
    voice_profile,
)
from vera_timeline_agent.narration.fish import FishError, FishProvider
from vera_timeline_agent.narration.models import (
    ProviderResult,
    SynthesisRequest,
    SynthesisSettings,
    TextControl,
    identity_hash,
)
from vera_timeline_agent.narration.polly import PollyProvider
from vera_timeline_agent.narration.service import ServiceConfig

BLOCK = {"id": "block-1", "version": 1, "text": "Hello."}
FISH_DOCUMENT = {
    "activeDraft": {
        "blocks": [{"type": "narration", "state": "active", **BLOCK, "text": "é🐟"}]
    }
}


class PreparedOnlyProvider:
    adapter_version = "test-provider/v1"

    def __init__(self) -> None:
        self.requests: list[SynthesisRequest] = []

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        self.requests.append(request)
        return b"test-input"

    def synthesize(self, _request: SynthesisRequest) -> ProviderResult:
        raise AssertionError("preflight must not synthesize")


def test_profiles_and_pricing_keep_provider_billing_units() -> None:
    polly = default_profile()
    fish = voice_profile(FISH_PROFILE_ID)
    text = "é🐟"

    assert (polly.profile_id, polly.provider) == (MATTHEW_PROFILE_ID, "aws_polly")
    assert (fish.provider, fish.voice_id) == ("fish_audio", MW1_REFERENCE_ID)
    polly_pricing, fish_pricing = pricing_for(polly), pricing_for(fish)
    assert (polly_pricing.unit, polly_pricing.units(text)) == ("characters", 2)
    assert (fish_pricing.unit, fish_pricing.units(text)) == ("utf8_bytes", 6)
    paid_fish = pricing_for(replace(fish, engine="s2.1-pro"))
    assert paid_fish.estimate(text) == pytest.approx(6 * 15 / 1_000_000)


def test_fish_input_and_preflight_bind_native_settings_and_terms() -> None:
    profile = voice_profile(FISH_PROFILE_ID)
    request = ServiceConfig(
        profile=profile,
        settings=SynthesisSettings(rate="110%"),
        data_policy_attestation="fish_terms_accepted",
    ).request_for(BLOCK)
    provider = FishProvider(transport=lambda _payload, _model: ())
    payload = json.loads(provider.prepare_input(request))

    assert payload["reference_id"] == MW1_REFERENCE_ID
    assert payload["prosody"]["speed"] == 1.1
    invalid_inputs = (
        (
            replace(request, profile=replace(profile, engine="unsupported")),
            "provider/model",
        ),
        (
            replace(request, profile=replace(profile, voice_id="new voice")),
            "reference ID",
        ),
        (
            replace(request, controls=(TextControl("pause", 0, 0, "1s"),)),
            "controls are unsupported",
        ),
    )
    for invalid, error in invalid_inputs:
        with pytest.raises(FishError, match=error):
            provider.prepare_input(invalid)
    for invalid, error in (
        (replace(request, pricing_policy_version="stale"), "pricing policy"),
        (
            replace(request, data_policy_attestation="provider_terms_accepted"),
            "explicit Fish data-policy consent",
        ),
    ):
        with pytest.raises(FishError, match=error):
            provider.preflight(invalid)


def test_service_cache_identity_tracks_profile_and_rate() -> None:
    polly = default_profile()
    fish = voice_profile(FISH_PROFILE_ID)
    normal = SynthesisSettings()
    cases = (
        (polly, normal),
        (fish, normal),
        (replace(fish, engine="s2.1-pro"), normal),
        (replace(fish, voice_id="a" * 32), normal),
        (replace(fish, voice_version="mw1-reference-v2"), normal),
        (fish, SynthesisSettings(rate="110%")),
    )

    hashes: set[str] = set()
    for profile, settings in cases:
        request = ServiceConfig(profile=profile, settings=settings).request_for(BLOCK)
        hashes.add(identity_hash(request.identity(b"prepared-input", "adapter/v1")))

    assert len(hashes) == len(cases)


def test_base_polly_request_identity_remains_historical() -> None:
    request = ServiceConfig(
        data_policy_attestation="provider_terms_accepted"
    ).request_for(BLOCK)
    provider = PollyProvider()
    provider_input = provider.prepare_input(request)

    assert provider_input == (
        b'<speak><prosody rate="100%" volume="0dB">Hello.</prosody></speak>'
    )
    assert identity_hash(
        request.identity(provider_input, provider.adapter_version)
    ) == ("sha256:664cd3deb0feff80427c14a54353e3c4603e5e09019c7f608dd3ae5b75983df6")


def test_fish_cli_preflight_is_offline_bills_utf8_and_rejects_aws_consent(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    script = tmp_path / "script.json"
    script.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli,
        "_validate_script",
        lambda _path: (FISH_DOCUMENT, "test validator passed"),
    )
    provider = PreparedOnlyProvider()
    cache = tmp_path / "cache"
    command = [
        str(script),
        "--cache",
        str(cache),
        "--voice-profile",
        FISH_PROFILE_ID,
        "--preflight-only",
    ]

    for policy, expected in (
        (["--data-policy", "fish_terms_accepted"], cli.CliExit.OK),
        (
            ["--aws-data-policy", "provider_terms_accepted"],
            cli.CliExit.USAGE,
        ),
    ):
        stdout, stderr = io.StringIO(), io.StringIO()
        result = cli.run_cli(
            [*command, *policy],
            stdout=stdout,
            stderr=stderr,
            provider=provider,
        )
        assert result == expected
        if expected == cli.CliExit.OK:
            assert "billed UTF-8 bytes (audio + timing): 6" in stdout.getvalue()
            assert "estimated maximum charge: $0.000000" in stdout.getvalue()
            assert provider.requests[0].profile.profile_id == FISH_PROFILE_ID
        else:
            assert "data policy does not match selected provider" in stderr.getvalue()
    assert len(provider.requests) == 1
    assert not cache.exists()
