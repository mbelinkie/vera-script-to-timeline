"""Provider selection and pricing; narration consumers use the shared protocol."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from vera_timeline_agent.narration.models import VoiceProfile
from vera_timeline_agent.narration.provider import SpeechSynthesisProvider

MATTHEW_PROFILE_ID = "aws-polly-matthew-neural-en-us-v1"
JOANNA_PROFILE_ID = "aws-polly-joanna-neural-en-us-v1"
FISH_PROFILE_ID = "fish-mw1-s2.1-pro-free-en-us-v1"
MW1_REFERENCE_ID = "f051ceb7fd8d47f09f63944298f589fc"


def _polly_profile(profile_id: str, voice_id: str) -> VoiceProfile:
    return VoiceProfile(
        profile_id=profile_id,
        provider="aws_polly",
        region="us-east-1",
        engine="neural",
        voice_id=voice_id,
        voice_version="provider_not_supplied",
        language="en-US",
    )


VOICE_PROFILES = {
    MATTHEW_PROFILE_ID: _polly_profile(MATTHEW_PROFILE_ID, "Matthew"),
    JOANNA_PROFILE_ID: _polly_profile(JOANNA_PROFILE_ID, "Joanna"),
    FISH_PROFILE_ID: VoiceProfile(
        profile_id=FISH_PROFILE_ID,
        provider="fish_audio",
        region="provider_not_supplied",
        engine="s2.1-pro-free",
        voice_id=MW1_REFERENCE_ID,
        voice_version="provider_not_supplied",
        language="en-US",
    ),
}


def voice_profile(profile_id: str) -> VoiceProfile:
    try:
        return VOICE_PROFILES[profile_id]
    except KeyError as error:
        choices = ", ".join(sorted(VOICE_PROFILES))
        raise ValueError(
            f"unknown voice profile {profile_id!r}; choose one of: {choices}"
        ) from error


def default_profile() -> VoiceProfile:
    return voice_profile(MATTHEW_PROFILE_ID)


@dataclass(frozen=True)
class PricingPolicy:
    version: str
    unit: Literal["characters", "utf8_bytes"]
    usd_per_million: float

    def units(self, text: str) -> int:
        return len(text.encode("utf-8")) if self.unit == "utf8_bytes" else len(text)

    def estimate(self, text: str) -> float:
        return self.units(text) * self.usd_per_million / 1_000_000


_PRICING = {
    ("aws_polly", "neural"): PricingPolicy(
        "aws-polly-neural-2026-08-25", "characters", 32.0
    ),
    ("fish_audio", "s2.1-pro-free"): PricingPolicy(
        "fish-s2.1-pro-free-2026-10-23", "utf8_bytes", 0.0
    ),
    ("fish_audio", "s2.1-pro"): PricingPolicy(
        "fish-s2.1-pro-2026-10-23", "utf8_bytes", 15.0
    ),
}


def pricing_for(profile: VoiceProfile) -> PricingPolicy:
    try:
        return _PRICING[(profile.provider, profile.engine)]
    except KeyError as error:
        raise ValueError("unsupported provider/model pricing") from error


def provider_for(profile: VoiceProfile) -> SpeechSynthesisProvider:
    # Keep vendor construction at configuration, away from consumers.
    if profile.provider == "aws_polly":
        from vera_timeline_agent.narration.polly import PollyProvider

        return PollyProvider()
    if profile.provider == "fish_audio":
        from vera_timeline_agent.narration.fish import FishProvider

        return FishProvider()
    raise ValueError("unsupported speech provider")
