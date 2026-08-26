from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Literal

from vera_timeline_agent.narration.cache import CacheError, NarrationCache
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    PronunciationEntry,
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    SynthesisSettings,
    TextControl,
    VoiceProfile,
    canonical_json_bytes,
    identity_hash,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import (
    NORMALIZER_VERSION,
    MediaToolError,
    NormalizationResult,
    Normalizer,
)
from vera_timeline_agent.narration.polly import PRICE_USD_PER_MILLION_CHARACTERS
from vera_timeline_agent.narration.provider import SpeechSynthesisProvider

MATTHEW_PROFILE_ID = "aws-polly-matthew-neural-en-us-v1"
JOANNA_PROFILE_ID = "aws-polly-joanna-neural-en-us-v1"


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
class ServiceConfig:
    profile: VoiceProfile = field(default_factory=default_profile)
    settings: SynthesisSettings = field(default_factory=SynthesisSettings)
    pronunciations: tuple[PronunciationEntry, ...] = ()
    controls: tuple[TextControl, ...] = ()
    data_policy_attestation: str | None = None
    max_cost_usd: float = 1.0


def _bare_hash(value: str) -> str:
    return value.removeprefix("sha256:")


def _timing_json(result: ProviderResult) -> bytes:
    return canonical_json_bytes(
        {
            "recordVersion": "provider-timing/v1",
            "precision": (
                "word_start_with_derived_end"
                if any(mark.kind == "word" for mark in result.timing_marks)
                else "sentence_start"
            ),
            "marks": [asdict(mark) for mark in result.timing_marks],
        }
    )


class NarrationService:
    def __init__(
        self,
        *,
        cache: NarrationCache,
        provider: SpeechSynthesisProvider,
        normalizer: Normalizer,
        config: ServiceConfig,
    ) -> None:
        self.cache = cache
        self.provider = provider
        self.normalizer = normalizer
        self.config = config

    def process_document(self, document: dict[str, Any]) -> list[NarrationAudioAsset]:
        active_draft = document.get("activeDraft")
        if not isinstance(active_draft, dict) or not isinstance(
            active_draft.get("blocks"), list
        ):
            raise ValueError("ScriptDocument activeDraft.blocks is required")
        blocks = [
            block
            for block in active_draft["blocks"]
            if isinstance(block, dict)
            and block.get("type") == "narration"
            and block.get("state") == "active"
        ]
        blocks.sort(
            key=lambda block: (str(block.get("orderKey", "")), str(block.get("id", "")))
        )
        return [self.process_block(block) for block in blocks]

    def _request(self, block: dict[str, Any]) -> SynthesisRequest:
        block_id = block.get("id")
        revision = block.get("version")
        text = block.get("text")
        if (
            not isinstance(block_id, str)
            or not isinstance(revision, int)
            or not isinstance(text, str)
        ):
            raise ValueError(
                "active narration block requires string id/text and integer version"
            )
        return SynthesisRequest(
            block_id=block_id,
            block_revision=revision,
            text=text,
            profile=self.config.profile,
            settings=self.config.settings,
            pronunciations=self.config.pronunciations,
            controls=self.config.controls,
            data_policy_attestation=self.config.data_policy_attestation,
            max_cost_usd=self.config.max_cost_usd,
        )

    def _raw_result(
        self, request: SynthesisRequest, synthesis_key: str
    ) -> tuple[ProviderResult, str]:
        with self.cache.lock(synthesis_key):
            entry = self.cache.read("synthesis", synthesis_key, "synthesis.json")
            if entry is not None:
                metadata = entry.metadata
                marks_value = json.loads(entry.files["provider-timing.json"])["marks"]
                marks = tuple(ProviderTimingMark(**mark) for mark in marks_value)
                return (
                    ProviderResult(
                        audio_bytes=entry.files["provider-audio.pcm"],
                        audio_format=str(metadata["audioFormat"]),
                        sample_rate=int(metadata["sampleRate"]),
                        channels=int(metadata["channels"]),
                        provider_input=entry.files["provider-input.ssml"],
                        timing_marks=marks,
                        provenance=dict(metadata["provenance"]),
                        request_ids=tuple(metadata["requestIds"]),
                    ),
                    "reused",
                )
            result = self.provider.synthesize(request)
            timing = _timing_json(result)
            disposition = self.cache.publish(
                "synthesis",
                synthesis_key,
                {
                    "provider-input.ssml": result.provider_input,
                    "provider-audio.pcm": result.audio_bytes,
                    "provider-timing.json": timing,
                },
                "synthesis.json",
                {
                    "recordVersion": "synthesis-cache/v1",
                    "audioFormat": result.audio_format,
                    "sampleRate": result.sample_rate,
                    "channels": result.channels,
                    "provenance": result.provenance,
                    "requestIds": list(result.request_ids),
                },
            )
            return result, disposition

    def _normalized(
        self, raw: ProviderResult, normalization_key: str
    ) -> tuple[NormalizationResult, str]:
        with self.cache.lock(normalization_key):
            entry = self.cache.read(
                "normalization", normalization_key, "normalization.json"
            )
            if entry is not None:
                metadata = entry.metadata
                return (
                    NormalizationResult(
                        wav_bytes=entry.files["narration.wav"],
                        profile_id=str(metadata["profileId"]),
                        normalizer_version=str(metadata["normalizerVersion"]),
                        tool_fingerprint=str(metadata["toolFingerprint"]),
                        sample_rate=int(metadata["sampleRate"]),
                        channels=int(metadata["channels"]),
                        sample_format=str(metadata["sampleFormat"]),
                        duration_samples=int(metadata["durationSamples"]),
                        duration_ms=int(metadata["durationMs"]),
                        padding_samples=int(metadata["paddingSamples"]),
                        integrated_lufs=float(metadata["integratedLufs"]),
                        true_peak_dbtp=float(metadata["truePeakDbtp"]),
                        loudness_range_lu=float(metadata["loudnessRangeLu"]),
                    ),
                    "reused",
                )
            normalized = self.normalizer.normalize_pcm(
                raw.audio_bytes,
                sample_rate=raw.sample_rate,
                channels=raw.channels,
            )
            disposition = self.cache.publish(
                "normalization",
                normalization_key,
                {"narration.wav": normalized.wav_bytes},
                "normalization.json",
                {
                    "recordVersion": "normalization-cache/v1",
                    "profileId": normalized.profile_id,
                    "normalizerVersion": normalized.normalizer_version,
                    "toolFingerprint": normalized.tool_fingerprint,
                    "sampleRate": normalized.sample_rate,
                    "channels": normalized.channels,
                    "sampleFormat": normalized.sample_format,
                    "durationSamples": normalized.duration_samples,
                    "durationMs": normalized.duration_ms,
                    "paddingSamples": normalized.padding_samples,
                    "integratedLufs": normalized.integrated_lufs,
                    "truePeakDbtp": normalized.true_peak_dbtp,
                    "loudnessRangeLu": normalized.loudness_range_lu,
                },
            )
            return normalized, disposition

    def process_block(self, block: dict[str, Any]) -> NarrationAudioAsset:
        request = self._request(block)
        provider_input = self.provider.prepare_input(request)
        request_identity = request.identity(
            provider_input, self.provider.adapter_version
        )
        request_hash = identity_hash(request_identity)
        synthesis_key = _bare_hash(request_hash)
        generated_at = datetime.now(UTC).isoformat()
        estimated_cost = (
            len(request.text) * PRICE_USD_PER_MILLION_CHARACTERS / 1_000_000
        )
        try:
            raw, synthesis_disposition = self._raw_result(request, synthesis_key)
            timing = _timing_json(raw)
            normalization_identity = {
                "recordVersion": "normalization-key/v1",
                "rawAudioHash": sha256_bytes(raw.audio_bytes),
                "rawTimingHash": sha256_bytes(timing),
                "profileId": self.normalizer.profile_id,
                "toolFingerprint": self.normalizer.tool_fingerprint,
                "normalizerVersion": NORMALIZER_VERSION,
            }
            normalization_key = _bare_hash(identity_hash(normalization_identity))
            normalized, normalization_disposition = self._normalized(
                raw, normalization_key
            )
            status: Literal["ready", "failed"] = "ready"
            failure_reason = None
        except CacheError:
            raise
        except Exception as error:
            normalized = self.normalizer.placeholder(request.block_id)
            raw = None
            timing = canonical_json_bytes(
                {
                    "recordVersion": "provider-timing/v1",
                    "precision": "none",
                    "marks": [],
                }
            )
            synthesis_disposition = "failed"
            normalization_disposition = "placeholder_generated"
            normalization_key = _bare_hash(
                identity_hash(
                    {
                        "recordVersion": "placeholder-key/v1",
                        "blockId": request.block_id,
                        "requestHash": request_hash,
                        "placeholderAudioHash": sha256_bytes(normalized.wav_bytes),
                    }
                )
            )
            status = "failed"
            category = "media_tool" if isinstance(error, MediaToolError) else "provider"
            failure_reason = f"{category}: {error}"

        asset_id = _bare_hash(
            identity_hash(
                {
                    "recordVersion": "narration-asset-key/v1",
                    "blockId": request.block_id,
                    "blockRevision": request.block_revision,
                    "requestHash": request_hash,
                    "normalizationKey": normalization_key,
                    "status": status,
                    "failureReason": failure_reason,
                }
            )
        )
        asset_key = f"{request.block_id}/{asset_id}"
        asset_locator = f"v1/assets/{asset_key}"
        provenance = raw.provenance if raw is not None else {}
        timing_precision = (
            "word_start_with_derived_end"
            if raw is not None and any(mark.kind == "word" for mark in raw.timing_marks)
            else "sentence_start"
            if raw is not None
            else "none"
        )
        asset = NarrationAudioAsset(
            record_version="narration-audio-asset/v1",
            asset_id=asset_id,
            block_id=request.block_id,
            block_revision=request.block_revision,
            kind="temp_synthetic",
            status=status,
            text_hash=sha256_bytes(request.text.encode("utf-8")),
            provider_input_hash=sha256_bytes(provider_input)
            if raw is not None
            else None,
            profile_hash=identity_hash(asdict(request.profile)),
            settings_hash=identity_hash(asdict(request.settings)),
            pronunciation_hash=identity_hash(
                [asdict(item) for item in request.pronunciations]
            ),
            request_hash=request_hash,
            provider=str(provenance.get("provider", request.profile.provider)),
            region=str(provenance.get("region", request.profile.region)),
            model=str(provenance.get("engine", request.profile.engine)),
            voice_id=str(provenance.get("voiceId", request.profile.voice_id)),
            voice_version=str(
                provenance.get("voiceVersion", request.profile.voice_version)
            ),
            raw_audio_hash=sha256_bytes(raw.audio_bytes) if raw is not None else None,
            raw_timing_hash=sha256_bytes(timing) if raw is not None else None,
            timing_precision=timing_precision,
            normalization_profile=normalized.profile_id,
            normalization_hash=f"sha256:{normalization_key}",
            tool_fingerprint=normalized.tool_fingerprint,
            normalized_audio_hash=sha256_bytes(normalized.wav_bytes),
            duration_samples=normalized.duration_samples,
            duration_ms=normalized.duration_ms,
            sample_rate=normalized.sample_rate,
            channels=normalized.channels,
            sample_format=normalized.sample_format,
            synthesis_disposition=synthesis_disposition,
            normalization_disposition=normalization_disposition,
            locators={
                "audio": f"{asset_locator}/narration.wav",
                "timing": f"{asset_locator}/timing.json",
                "record": f"{asset_locator}/asset.json",
            },
            generated_at=generated_at,
            request_ids=raw.request_ids if raw is not None else (),
            data_policy_attestation=request.data_policy_attestation,
            estimated_cost_usd=estimated_cost
            if synthesis_disposition == "generated"
            else 0.0,
            failure_reason=failure_reason,
            extra={
                "paddingSamples": normalized.padding_samples,
                "integratedLufs": normalized.integrated_lufs,
                "truePeakDbtp": normalized.true_peak_dbtp,
                "loudnessRangeLu": normalized.loudness_range_lu,
            },
        )
        with self.cache.lock(asset_id):
            existing_asset = self.cache.read("assets", asset_key, "asset.json")
            if existing_asset is None:
                self.cache.publish(
                    "assets",
                    asset_key,
                    {"narration.wav": normalized.wav_bytes, "timing.json": timing},
                    "asset.json",
                    {"recordVersion": "asset-cache/v1", "asset": asset.as_json()},
                )
            else:
                stored = existing_asset.metadata.get("asset")
                if isinstance(stored, dict) and isinstance(
                    stored.get("generated_at"), str
                ):
                    asset = replace(asset, generated_at=stored["generated_at"])
        return asset
