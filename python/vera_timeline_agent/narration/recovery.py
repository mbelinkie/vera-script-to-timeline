"""Pure admission of a local MFA timing candidate against reviewed onsets."""

from __future__ import annotations

import array
import copy
import io
import math
import re
import sys
import uuid
import wave
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from fractions import Fraction
from typing import Any, cast

from vera_word_timing.artifacts import content_hash

from vera_timeline_agent.generated.contracts.script_document_v2_schema import (
    NarrationToken,
)
from vera_timeline_agent.narration.compiler_dependencies import (
    NarrationDependencyError,
)
from vera_timeline_agent.narration.compiler_dependencies_v2 import _validated_tokens
from vera_timeline_agent.narration.measure import parameters_hash, rational
from vera_timeline_agent.narration.models import canonical_json_bytes, sha256_bytes

_SAMPLE_RATE = 48_000
_PREPARED_RATE = 16_000
_MAX_SAFE = 2**53 - 1
_HASH = re.compile(r"^sha256:[0-9a-f]{64}$")
_BARE_HASH = re.compile(r"^[0-9a-f]{64}$")
_BLOCK_ID_PREFIX = "vera:narration-cache-asset:"
_CANDIDATE_SCHEMA = "synthetic-acoustic-candidate/v1"
_REFERENCE_SCHEMA = "independent-acoustic-reference/v1"
_REFERENCE_METHOD = "independent_acoustic_review/v1"
_ALGORITHM_ID = "vera-local-acoustic-recovery"
_TOKENIZATION_VERSION = "script-document/v2-frozen-tokens"


class RecoveryError(ValueError):
    """The supplied audio or timing evidence is not admissible."""


@dataclass(frozen=True)
class PreparedRecoveryAudio:
    wav_bytes: bytes
    sample_rate: int
    duration_samples: int
    source_hash: str
    prepared_hash: str
    discarded_trailing_samples: int


@dataclass(frozen=True)
class RecoverySource:
    block: Mapping[str, Any]
    failed_asset_id: str
    request_hash: str
    response_hash: str
    raw_audio_bytes: bytes
    raw_audio_format: str
    normalized_wav_bytes: bytes
    prepared_wav_bytes: bytes
    sample_rate: int
    duration_samples: int
    normalization_provenance: Mapping[str, Any]


@dataclass(frozen=True)
class RecoveryResult:
    artifact: dict[str, Any]
    artifact_bytes: bytes
    evidence: dict[str, Any]


def prepare_recovery_audio(normalized_wav_bytes: bytes) -> PreparedRecoveryAudio:
    """Make the supported zero-origin 48 kHz mono to 16 kHz boxcar transform."""

    samples, rate = _read_wav(normalized_wav_bytes)
    if rate != _SAMPLE_RATE:
        raise RecoveryError("recovery preparation requires 48 kHz normalized audio")
    discarded = len(samples) % 3
    kept = len(samples) - discarded
    output_samples = array.array(
        "h",
        (
            (samples[index] + samples[index + 1] + samples[index + 2]) // 3
            for index in range(0, kept, 3)
        ),
    )
    if output_samples.itemsize != 2:
        raise RecoveryError("platform does not support PCM-16 recovery output")
    if sys.byteorder == "big":  # pragma: no cover - platform guard
        output_samples.byteswap()
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(_PREPARED_RATE)
        wav.writeframes(output_samples.tobytes())
    prepared_bytes = output.getvalue()
    return PreparedRecoveryAudio(
        wav_bytes=prepared_bytes,
        sample_rate=_PREPARED_RATE,
        duration_samples=len(output_samples),
        source_hash=sha256_bytes(normalized_wav_bytes),
        prepared_hash=sha256_bytes(prepared_bytes),
        discarded_trailing_samples=discarded,
    )


def admit_local_acoustic_recovery(
    source: RecoverySource,
    candidate: Mapping[str, Any],
    reference: Mapping[str, Any],
) -> RecoveryResult:
    """Admit one exact-script MFA candidate after an independent onset review."""

    block_id, revision, tokens, text_hash = _frozen_block(source.block)
    audio_hash, raw_hash, normalization_hash, prepared, normalization = _checked_source(
        source
    )
    duration = Fraction(source.duration_samples, _SAMPLE_RATE)
    prepared_duration = Fraction(prepared.duration_samples, _PREPARED_RATE)
    candidate_doc = _checked_document(
        candidate,
        {
            "schemaVersion",
            "audioHash",
            "preparedAudioHash",
            "textHash",
            "blockId",
            "blockRevision",
            "engine",
            "words",
            "artifactId",
        },
        "candidate",
    )
    if not _positive_safe_integer(candidate_doc["blockRevision"]):
        raise RecoveryError("candidate block revision is invalid")
    if (
        candidate_doc["schemaVersion"] != _CANDIDATE_SCHEMA
        or candidate_doc["audioHash"] != audio_hash
        or candidate_doc["preparedAudioHash"] != prepared.prepared_hash
        or candidate_doc["textHash"] != text_hash
        or candidate_doc["blockId"] != block_id
        or candidate_doc["blockRevision"] != revision
    ):
        raise RecoveryError("candidate binds different source audio, text, or block")
    engine = candidate_doc["engine"]
    if (
        not isinstance(engine, Mapping)
        or set(engine) != {"id", "provenance"}
        or engine.get("id") != "A-MFA"
        or not isinstance(engine.get("provenance"), Mapping)
    ):
        raise RecoveryError(
            "candidate must bind raw provenance from the supported MFA engine"
        )
    _canonical(engine["provenance"], "candidate engine provenance")

    candidate_rows = _candidate_rows(candidate_doc["words"], tokens, prepared_duration)
    reference_doc = _checked_document(
        reference,
        {
            "schemaVersion",
            "audioHash",
            "textHash",
            "method",
            "reviewerReference",
            "independentOfCandidate",
            "tokens",
            "artifactId",
        },
        "reference",
    )
    if (
        reference_doc["schemaVersion"] != _REFERENCE_SCHEMA
        or reference_doc["method"] != _REFERENCE_METHOD
        or reference_doc["audioHash"] != audio_hash
        or reference_doc["textHash"] != text_hash
        or reference_doc["independentOfCandidate"] is not True
        or not isinstance(reference_doc["reviewerReference"], str)
        or not reference_doc["reviewerReference"].strip()
    ):
        raise RecoveryError(
            "reference is not an independent review of this audio and text"
        )
    reference_rows = _reference_rows(reference_doc["tokens"], tokens, duration)

    measured_tokens: list[dict[str, Any]] = []
    evidence_tokens: list[dict[str, Any]] = []
    uncertainty_ms: list[Fraction] = []
    for token, candidate_row, reference_row in zip(
        tokens, candidate_rows, reference_rows, strict=True
    ):
        start_ms, end_ms = candidate_row
        onset_ms, review_uncertainty_ms = reference_row
        error_ms = abs(start_ms - onset_ms)
        if error_ms > review_uncertainty_ms:
            raise RecoveryError(
                "MFA onset exceeds the independently reviewed uncertainty"
            )
        effective_ms = error_ms + review_uncertainty_ms
        uncertainty_ms.append(effective_ms)
        onset = _seconds_rational(start_ms)
        evidence_token = {
            "tokenId": token["id"],
            "startOffset": token["startOffset"],
            "endOffset": token["endOffset"],
            "quotedText": token["value"],
            "onset": onset,
        }
        evidence_tokens.append(evidence_token)
        measured_tokens.append(
            {
                **evidence_token,
                "candidateSupport": {
                    "start": _seconds_rational(start_ms),
                    "end": _seconds_rational(end_ms),
                },
                "referenceOnset": _seconds_rational(onset_ms),
                "referenceUncertainty": _seconds_rational(review_uncertainty_ms),
                "candidateError": _seconds_rational(error_ms),
                "onsetUncertainty": _seconds_rational(effective_ms),
                "referenceReviewed": True,
            }
        )

    p95_uncertainty = _nearest_rank(uncertainty_ms, 95)
    maximum_uncertainty = max(uncertainty_ms)
    if maximum_uncertainty > 200 or p95_uncertainty > 150:
        raise RecoveryError(
            "admitted onset uncertainty exceeds the p95 or maximum limit"
        )

    candidate_id = candidate_doc["artifactId"]
    reference_id = reference_doc["artifactId"]
    preparation = {
        "method": "boxcar-48k-to-16k-pcm16/v1",
        "sourceAudioHash": audio_hash,
        "preparedAudioHash": prepared.prepared_hash,
        "sourceSampleRate": _SAMPLE_RATE,
        "sourceDurationSamples": source.duration_samples,
        "preparedSampleRate": _PREPARED_RATE,
        "preparedDurationSamples": prepared.duration_samples,
        "discardedTrailingSourceSamples": prepared.discarded_trailing_samples,
        "sourceFirstSample": 0,
        "preparedFirstSample": 0,
        "sourceSamplesPerPreparedSample": 3,
    }
    identity = {
        "recordVersion": "narration-local-recovery-cache-key/v1",
        "blockId": block_id,
        "blockRevision": revision,
        "textHash": text_hash,
        "failedAssetId": source.failed_asset_id,
        "requestHash": source.request_hash,
        "responseHash": source.response_hash,
        "rawAudioHash": raw_hash,
        "normalizedAudioHash": audio_hash,
        "preparedAudioHash": prepared.prepared_hash,
        "normalizationHash": normalization_hash,
        "candidateArtifactId": candidate_id,
        "referenceArtifactId": reference_id,
    }
    cache_id = sha256_bytes(canonical_json_bytes(identity)).removeprefix("sha256:")
    narration_id = str(uuid.uuid5(uuid.NAMESPACE_URL, _BLOCK_ID_PREFIX + cache_id))
    timing_hash = sha256_bytes(
        canonical_json_bytes(
            {
                "recordVersion": "local-acoustic-timing/v1",
                "audioHash": audio_hash,
                "candidateArtifactId": candidate_id,
                "referenceArtifactId": reference_id,
                "tokens": evidence_tokens,
            }
        )
    )
    parameters = {
        "referenceMethod": _REFERENCE_METHOD,
        "p95UncertaintyMaxMs": 150,
        "maximumUncertaintyMs": 200,
        "audibleEndsEmitted": False,
        "preparationMethod": "boxcar-48k-to-16k-pcm16/v1",
        "discardedTrailingSourceSamplesMax": 2,
    }
    algorithm = {
        "id": _ALGORITHM_ID,
        "version": "1",
        "parametersHash": parameters_hash(parameters),
        "parameters": parameters,
    }
    artifact = {
        "schemaVersion": "narration-measurement/v1",
        "algorithm": algorithm,
        "asset": {
            "cacheAssetId": cache_id,
            "narrationAssetId": narration_id,
            "blockId": block_id,
            "blockRevision": revision,
            "textHash": text_hash,
            "audioHash": audio_hash,
            "rawAudioHash": raw_hash,
            "preparedAudioHash": prepared.prepared_hash,
            "timingHash": timing_hash,
            "requestHash": source.request_hash,
            "failedAssetId": source.failed_asset_id,
            "durationSamples": source.duration_samples,
            "sampleRate": source.sample_rate,
            "channels": 1,
        },
        "source": {
            "rawAudioFormat": source.raw_audio_format,
            "responseHash": source.response_hash,
            "normalizationHash": normalization_hash,
            "normalization": normalization,
            "preparation": preparation,
        },
        "analysis": {
            "candidateArtifactId": candidate_id,
            "candidateEngineId": "A-MFA",
            "referenceArtifactId": reference_id,
            "referenceMethod": _REFERENCE_METHOD,
            "onsetUncertaintyP95": _seconds_rational(p95_uncertainty),
            "onsetUncertaintyMaximum": _seconds_rational(maximum_uncertainty),
        },
        "tokens": measured_tokens,
        "refusals": [],
    }
    artifact_bytes = canonical_json_bytes(artifact)
    evidence = {
        "schemaVersion": "narration-boundary-evidence/v1",
        "blockId": block_id,
        "blockRevision": revision,
        "textHash": text_hash,
        "tokenizationVersion": _TOKENIZATION_VERSION,
        "narrationAssetId": narration_id,
        "audioHash": audio_hash,
        "timingHash": timing_hash,
        "alignmentVersion": "local-acoustic-recovery/v1",
        "audio": {
            "narrationAssetId": narration_id,
            "audioHash": audio_hash,
            "timingHash": timing_hash,
            "cacheAssetId": cache_id,
            "locator": f"v1/assets/{block_id}/{cache_id}/narration.wav",
            "durationSamples": source.duration_samples,
            "sampleRate": source.sample_rate,
            "channels": 1,
        },
        "tokens": evidence_tokens,
        "verification": {
            "method": "measured_audio_boundaries/v1",
            "algorithm": algorithm,
            "measurementArtifactLocator": f"v1/narration-measurements/{cache_id}.json",
            "measurementArtifactHash": sha256_bytes(artifact_bytes),
            "onsetBasis": "local_acoustic_alignment",
            "onsetUncertainty": _seconds_rational(maximum_uncertainty),
            "audibleEndUncertainty": {"numerator": 0, "denominator": 1},
        },
    }
    return RecoveryResult(artifact, artifact_bytes, evidence)


def _checked_source(
    source: RecoverySource,
) -> tuple[str, str, str, PreparedRecoveryAudio, dict[str, Any]]:
    if (
        not isinstance(source.raw_audio_bytes, bytes)
        or not source.raw_audio_bytes
        or not isinstance(source.raw_audio_format, str)
        or not source.raw_audio_format.strip()
    ):
        raise RecoveryError("retained raw audio bytes and format are required")
    if not isinstance(source.failed_asset_id, str) or not _BARE_HASH.fullmatch(
        source.failed_asset_id
    ):
        raise RecoveryError("failed asset id must be a bare cache hash")
    _hash(source.request_hash, "request hash")
    _hash(source.response_hash, "response hash")
    if source.sample_rate != _SAMPLE_RATE or not _positive_safe_integer(
        source.duration_samples
    ):
        raise RecoveryError("normalized source must bind a positive 48 kHz timeline")
    if not isinstance(source.normalized_wav_bytes, bytes):
        raise RecoveryError("normalized audio must be WAV bytes")
    if not isinstance(source.prepared_wav_bytes, bytes):
        raise RecoveryError("prepared audio must be WAV bytes")
    samples, rate = _read_wav(source.normalized_wav_bytes)
    if rate != source.sample_rate or len(samples) != source.duration_samples:
        raise RecoveryError("normalized WAV differs from its source binding")
    raw_hash = sha256_bytes(source.raw_audio_bytes)
    audio_hash = sha256_bytes(source.normalized_wav_bytes)
    provenance = source.normalization_provenance
    if not isinstance(provenance, Mapping) or (
        provenance.get("sourceAudioHash") != raw_hash
        or provenance.get("normalizedAudioHash") != audio_hash
    ):
        raise RecoveryError("normalization provenance does not bind supplied audio")
    normalization = copy.deepcopy(dict(provenance))
    normalization_hash = sha256_bytes(
        _canonical(normalization, "normalization provenance")
    )
    prepared = prepare_recovery_audio(source.normalized_wav_bytes)
    if source.prepared_wav_bytes != prepared.wav_bytes:
        raise RecoveryError(
            "supplied prepared audio differs from deterministic transform"
        )
    return audio_hash, raw_hash, normalization_hash, prepared, normalization


def _frozen_block(
    block: Mapping[str, Any],
) -> tuple[str, int, list[dict[str, Any]], str]:
    block_id, revision, text, raw_tokens = (
        block.get("id"),
        block.get("version"),
        block.get("text"),
        block.get("tokens"),
    )
    if block.get("type") != "narration" or not isinstance(block_id, str):
        raise RecoveryError("frozen narration block identity is invalid")
    try:
        if str(uuid.UUID(block_id)) != block_id:
            raise ValueError
    except ValueError as error:
        raise RecoveryError("frozen narration block identity is invalid") from error
    if not _positive_safe_integer(revision) or not isinstance(text, str) or not text:
        raise RecoveryError("frozen narration revision and text are required")
    if not isinstance(raw_tokens, list) or not raw_tokens:
        raise RecoveryError("frozen narration tokens are required")
    try:
        utf16 = text.encode("utf-16-le")
        tokens = _validated_tokens(utf16, cast(list[NarrationToken], raw_tokens))
    except (UnicodeEncodeError, NarrationDependencyError) as error:
        raise RecoveryError("frozen narration tokens do not match text") from error
    return (
        block_id,
        cast(int, revision),
        cast(list[dict[str, Any]], tokens),
        sha256_bytes(text.encode("utf-8")),
    )


def _checked_document(
    value: Mapping[str, Any], expected_keys: set[str], label: str
) -> dict[str, Any]:
    try:
        document = dict(value)
    except (TypeError, ValueError) as error:
        raise RecoveryError(f"{label} wrapper is invalid") from error
    if set(document) != expected_keys:
        raise RecoveryError(f"{label} wrapper has missing or unsupported fields")
    artifact_id = document.get("artifactId")
    if not _is_hash(artifact_id):
        raise RecoveryError(f"{label} artifact id is invalid")
    body = {key: item for key, item in document.items() if key != "artifactId"}
    try:
        expected_id = content_hash(body)
    except (TypeError, ValueError) as error:
        raise RecoveryError(f"{label} wrapper is not canonical JSON") from error
    if artifact_id != expected_id:
        raise RecoveryError(f"{label} artifact id does not match its content")
    return document


def _candidate_rows(
    value: Any, tokens: list[dict[str, Any]], duration: Fraction
) -> list[tuple[Fraction, Fraction]]:
    if not isinstance(value, list) or len(value) != len(tokens):
        raise RecoveryError("candidate must cover every frozen token exactly once")
    rows: list[tuple[Fraction, Fraction]] = []
    previous_start = Fraction(-1)
    previous_end = Fraction(-1)
    for token, row in zip(tokens, value, strict=True):
        if not isinstance(row, Mapping) or set(row) != {"tokenId", "startMs", "endMs"}:
            raise RecoveryError("candidate word row has an invalid shape")
        if row.get("tokenId") != token["id"]:
            raise RecoveryError("candidate token IDs differ from frozen token order")
        start = _milliseconds(row.get("startMs"), "candidate start", positive=False)
        end = _milliseconds(row.get("endMs"), "candidate end", positive=True)
        if start >= end or end > duration * 1000 or start <= previous_start:
            raise RecoveryError(
                "candidate support is collapsed, unordered, or out of bounds"
            )
        if start < previous_end:
            raise RecoveryError("candidate supports overlap")
        _seconds_rational(start)
        _seconds_rational(end)
        previous_start, previous_end = start, end
        rows.append((start, end))
    return rows


def _reference_rows(
    value: Any, tokens: list[dict[str, Any]], duration: Fraction
) -> list[tuple[Fraction, Fraction]]:
    if not isinstance(value, list) or len(value) != len(tokens):
        raise RecoveryError("reference must review every frozen token exactly once")
    rows: list[tuple[Fraction, Fraction]] = []
    previous = Fraction(-1)
    for token, row in zip(tokens, value, strict=True):
        if (
            not isinstance(row, Mapping)
            or set(row) != {"tokenId", "onsetMs", "uncertaintyMs", "reviewed"}
            or row.get("tokenId") != token["id"]
            or row.get("reviewed") is not True
        ):
            raise RecoveryError(
                "reference does not explicitly review frozen token order"
            )
        onset = _milliseconds(row.get("onsetMs"), "reference onset", positive=False)
        uncertainty = _milliseconds(
            row.get("uncertaintyMs"), "reference uncertainty", positive=True
        )
        if onset >= duration * 1000 or onset <= previous:
            raise RecoveryError("reference onsets are unordered or out of bounds")
        _seconds_rational(onset)
        _seconds_rational(uncertainty)
        previous = onset
        rows.append((onset, uncertainty))
    return rows


def _read_wav(payload: bytes) -> tuple[array.array[int], int]:
    if not isinstance(payload, bytes):
        raise RecoveryError("normalized audio must be WAV bytes")
    try:
        with wave.open(io.BytesIO(payload), "rb") as wav:
            width = wav.getsampwidth()
            rate = wav.getframerate()
            frames = wav.getnframes()
            if (
                wav.getnchannels() != 1
                or width not in {2, 3}
                or wav.getcomptype() != "NONE"
            ):
                raise RecoveryError("normalized audio must be mono PCM-16 or PCM-24")
            raw = wav.readframes(frames)
    except (wave.Error, EOFError, OSError) as error:
        raise RecoveryError("normalized audio is not a readable WAV") from error
    if len(raw) != frames * width:
        raise RecoveryError("normalized WAV frame count differs from PCM payload")
    if width == 2:
        samples = array.array("h")
        samples.frombytes(raw)
        if samples.itemsize != 2:
            raise RecoveryError("platform does not support PCM-16 samples")
        if sys.byteorder == "big":  # pragma: no cover - platform guard
            samples.byteswap()
    else:
        samples = array.array(
            "h",
            (
                int.from_bytes(raw[index : index + 3], "little", signed=True) >> 8
                for index in range(0, len(raw), 3)
            ),
        )
    return samples, rate


def _milliseconds(value: Any, label: str, *, positive: bool) -> Fraction:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RecoveryError(f"{label} must be a finite safe number")
    if abs(value) > _MAX_SAFE or not math.isfinite(value):
        raise RecoveryError(f"{label} must be a finite safe number")
    try:
        result = Fraction(Decimal(str(value)))
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise RecoveryError(f"{label} must be a finite safe number") from error
    if result < 0 or (positive and result == 0):
        raise RecoveryError(f"{label} is outside its permitted range")
    return result


def _seconds_rational(milliseconds: Fraction) -> dict[str, int]:
    seconds = milliseconds / 1000
    if abs(seconds.numerator) > _MAX_SAFE or seconds.denominator > _MAX_SAFE:
        raise RecoveryError("time rational exceeds safe contract integers")
    return rational(seconds * _SAMPLE_RATE, _SAMPLE_RATE)


def _nearest_rank(values: list[Fraction], percentile: int) -> Fraction:
    index = (len(values) * percentile + 99) // 100 - 1
    return sorted(values)[index]


def _positive_safe_integer(value: Any) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 0 < value <= _MAX_SAFE
    )


def _is_hash(value: Any) -> bool:
    return isinstance(value, str) and _HASH.fullmatch(value) is not None


def _hash(value: Any, label: str) -> str:
    if not _is_hash(value):
        raise RecoveryError(f"{label} is invalid")
    return cast(str, value)


def _canonical(value: object, label: str) -> bytes:
    try:
        return canonical_json_bytes(value)
    except (TypeError, ValueError) as error:
        raise RecoveryError(f"{label} is not canonical JSON") from error
