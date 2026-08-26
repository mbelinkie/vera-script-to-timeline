from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

Hash = str


def canonical_json_bytes(value: object) -> bytes:
    """Serialize identity-bearing JSON in the repository's canonical form."""

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> Hash:
    return f"sha256:{hashlib.sha256(value).hexdigest()}"


def identity_hash(value: object) -> Hash:
    return sha256_bytes(canonical_json_bytes(value))


@dataclass(frozen=True)
class VoiceProfile:
    profile_id: str
    provider: str
    region: str
    engine: str
    voice_id: str
    voice_version: str
    language: str
    lexicons: tuple[tuple[str, Hash], ...] = ()


@dataclass(frozen=True)
class SynthesisSettings:
    rate: str = "100%"
    pitch: str = "0%"
    volume: str = "0dB"


@dataclass(frozen=True)
class PronunciationEntry:
    text: str
    kind: Literal["alias", "phoneme"]
    value: str
    start: int
    end: int
    alphabet: str | None = None


@dataclass(frozen=True)
class TextControl:
    kind: Literal["emphasis", "pause"]
    start: int
    end: int
    value: str


@dataclass(frozen=True)
class SynthesisRequest:
    block_id: str
    block_revision: int
    text: str
    profile: VoiceProfile
    settings: SynthesisSettings
    pronunciations: tuple[PronunciationEntry, ...] = ()
    controls: tuple[TextControl, ...] = ()
    timing_kinds: tuple[str, ...] = ("word", "sentence")
    data_policy_attestation: str | None = None
    pricing_policy_version: str = "aws-polly-neural-2026-08-25"
    max_cost_usd: float = 1.0

    def identity(self, provider_input: bytes, adapter_version: str) -> dict[str, Any]:
        return {
            "recordVersion": "synthesis-key/v1",
            "textHash": sha256_bytes(self.text.encode("utf-8")),
            "providerInputHash": sha256_bytes(provider_input),
            "profile": asdict(self.profile),
            "settings": asdict(self.settings),
            "pronunciations": [asdict(item) for item in self.pronunciations],
            "controls": [asdict(item) for item in self.controls],
            "timingKinds": list(self.timing_kinds),
            "adapterVersion": adapter_version,
            "pricingPolicyVersion": self.pricing_policy_version,
        }


@dataclass(frozen=True)
class ProviderTimingMark:
    kind: str
    time_ms: int
    start_byte: int
    end_byte: int
    start_utf16: int
    end_utf16: int
    value: str


@dataclass(frozen=True)
class ProviderResult:
    audio_bytes: bytes
    audio_format: str
    sample_rate: int
    channels: int
    provider_input: bytes
    timing_marks: tuple[ProviderTimingMark, ...]
    provenance: dict[str, Any]
    request_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class NarrationAudioAsset:
    record_version: str
    asset_id: str
    block_id: str
    block_revision: int
    kind: Literal["temp_synthetic"]
    status: Literal["ready", "failed"]
    text_hash: Hash
    provider_input_hash: Hash | None
    profile_hash: Hash
    settings_hash: Hash
    pronunciation_hash: Hash
    request_hash: Hash
    provider: str
    region: str
    model: str
    voice_id: str
    voice_version: str
    raw_audio_hash: Hash | None
    raw_timing_hash: Hash | None
    timing_precision: str
    normalization_profile: str
    normalization_hash: Hash
    tool_fingerprint: Hash
    normalized_audio_hash: Hash
    duration_samples: int
    duration_ms: int
    sample_rate: int
    channels: int
    sample_format: str
    synthesis_disposition: str
    normalization_disposition: str
    locators: dict[str, str]
    generated_at: str
    request_ids: tuple[str, ...] = ()
    data_policy_attestation: str | None = None
    estimated_cost_usd: float = 0.0
    failure_reason: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def as_json(self) -> dict[str, Any]:
        return asdict(self)
