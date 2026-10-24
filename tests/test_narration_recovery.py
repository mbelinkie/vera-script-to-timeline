from __future__ import annotations

import array
import copy
import io
import wave
from collections.abc import Callable
from dataclasses import replace
from typing import Any

import pytest
from vera_timeline_agent.narration.models import sha256_bytes
from vera_timeline_agent.narration.recovery import (
    RecoveryError,
    RecoveryResult,
    RecoverySource,
    admit_local_acoustic_recovery,
    prepare_recovery_audio,
)
from vera_word_timing.artifacts import content_hash

_RATE = 48_000
_BLOCK_ID = "00000000-0000-4000-8000-000000000001"
_TOKEN_IDS = (
    "00000000-0000-4000-8000-000000000011",
    "00000000-0000-4000-8000-000000000012",
)


def _wav(samples: list[int] | None = None, *, width: int = 2) -> bytes:
    samples = [0] * 4_802 if samples is None else samples
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(width)
        wav.setframerate(_RATE)
        if width == 2:
            pcm = array.array("h", samples)
            if pcm.itemsize != 2:
                raise AssertionError("test host does not have 16-bit shorts")
            wav.writeframes(pcm.tobytes())
        else:
            wav.writeframes(
                b"".join(
                    (sample & 0xFFFFFF).to_bytes(3, "little") for sample in samples
                )
            )
    return output.getvalue()


def _block(text: str = "same same") -> dict[str, Any]:
    tokens: list[dict[str, Any]] = []
    cursor = 0
    words = text.split()
    for token_id, word in zip(_TOKEN_IDS, words, strict=True):
        start = text.index(word, cursor)
        end = start + len(word.encode("utf-16-le")) // 2
        tokens.append(
            {"id": token_id, "value": word, "startOffset": start, "endOffset": end}
        )
        cursor = end
    return {
        "type": "narration",
        "id": _BLOCK_ID,
        "version": 7,
        "text": text,
        "tokens": tokens,
    }


def _source(
    block: dict[str, Any] | None = None, *, wav_bytes: bytes | None = None
) -> RecoverySource:
    raw = b"synthetic-only retained audio"
    normalized = _wav() if wav_bytes is None else wav_bytes
    prepared = prepare_recovery_audio(normalized)
    return RecoverySource(
        block=_block() if block is None else block,
        failed_asset_id=sha256_bytes(b"failed asset").removeprefix("sha256:"),
        request_hash=sha256_bytes(b"request"),
        response_hash=sha256_bytes(b"response"),
        raw_audio_bytes=raw,
        raw_audio_format="audio/wav",
        normalized_wav_bytes=normalized,
        prepared_wav_bytes=prepared.wav_bytes,
        sample_rate=_RATE,
        duration_samples=4_802,
        normalization_provenance={
            "recordVersion": "synthetic-normalization/v1",
            "sourceAudioHash": sha256_bytes(raw),
            "normalizedAudioHash": sha256_bytes(normalized),
        },
    )


def _sealed(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "artifactId": content_hash(body)}


def _candidate(
    source: RecoverySource,
    *,
    words: list[dict[str, Any]] | None = None,
    **changes: Any,
) -> dict[str, Any]:
    prepared = prepare_recovery_audio(source.normalized_wav_bytes)
    body: dict[str, Any] = {
        "schemaVersion": "synthetic-acoustic-candidate/v1",
        "audioHash": sha256_bytes(source.normalized_wav_bytes),
        "preparedAudioHash": prepared.prepared_hash,
        "textHash": sha256_bytes(source.block["text"].encode("utf-8")),
        "blockId": source.block["id"],
        "blockRevision": source.block["version"],
        "engine": {
            "id": "A-MFA",
            "provenance": {"binary": "synthetic-mfa", "version": "1"},
        },
        "words": words
        or [
            {"tokenId": _TOKEN_IDS[0], "startMs": 10, "endMs": 25},
            {"tokenId": _TOKEN_IDS[1], "startMs": 40, "endMs": 55},
        ],
    }
    body.update(changes)
    return _sealed(body)


def _reference(
    source: RecoverySource,
    *,
    onsets: list[float] | None = None,
    uncertainties: list[float] | None = None,
    reviewed: bool = True,
    **changes: Any,
) -> dict[str, Any]:
    block_tokens = source.block["tokens"]
    onsets = [10, 40] if onsets is None else onsets
    uncertainties = [5, 5] if uncertainties is None else uncertainties
    tokens = [
        {
            "tokenId": token["id"],
            "onsetMs": onset,
            "uncertaintyMs": uncertainty,
            "reviewed": reviewed,
        }
        for token, onset, uncertainty in zip(
            block_tokens, onsets, uncertainties, strict=False
        )
    ]
    body: dict[str, Any] = {
        "schemaVersion": "independent-acoustic-reference/v1",
        "audioHash": sha256_bytes(source.normalized_wav_bytes),
        "textHash": sha256_bytes(source.block["text"].encode("utf-8")),
        "method": "independent_acoustic_review/v1",
        "reviewerReference": "synthetic-review-record-1",
        "independentOfCandidate": True,
        "tokens": tokens,
    }
    body.update(changes)
    return _sealed(body)


def _admit(
    source: RecoverySource | None = None,
    *,
    candidate: dict[str, Any] | None = None,
    reference: dict[str, Any] | None = None,
) -> RecoveryResult:
    source = _source() if source is None else source
    return admit_local_acoustic_recovery(
        source,
        _candidate(source) if candidate is None else candidate,
        _reference(source) if reference is None else reference,
    )


def test_admits_exact_reviewed_candidate_and_emits_only_onsets() -> None:
    source = _source()
    candidate = _candidate(source)
    reference = _reference(source)
    before = copy.deepcopy((source, candidate, reference))

    result = admit_local_acoustic_recovery(source, candidate, reference)

    assert result.evidence["verification"]["onsetBasis"] == "local_acoustic_alignment"
    assert result.evidence["tokens"][0]["onset"] == {"numerator": 1, "denominator": 100}
    assert all("audibleEnd" not in row for row in result.evidence["tokens"])
    assert result.evidence["audio"]["audioHash"] == sha256_bytes(
        source.normalized_wav_bytes
    )
    assert result.evidence["verification"]["measurementArtifactHash"] == sha256_bytes(
        result.artifact_bytes
    )
    assert result.artifact["analysis"]["candidateEngineId"] == "A-MFA"
    assert "qwen" not in str(result.artifact).lower()
    assert (source, candidate, reference) == before


def test_recovery_preparation_records_trailing_discard_and_is_deterministic() -> None:
    payload = _wav([1, 2, 3, 4, 5])

    prepared = prepare_recovery_audio(payload)

    assert prepared.discarded_trailing_samples == 2
    assert prepared.sample_rate == 16_000
    assert prepared.duration_samples == 1
    assert prepare_recovery_audio(payload) == prepared


def test_pcm24_source_is_prepared_as_pcm16() -> None:
    prepared = prepare_recovery_audio(_wav([0, 256, 512, -256], width=3))

    with wave.open(io.BytesIO(prepared.wav_bytes), "rb") as wav:
        assert wav.getnchannels() == 1
        assert wav.getframerate() == 16_000
        assert wav.getsampwidth() == 2
        assert wav.getnframes() == 1


@pytest.mark.parametrize(
    "mutate",
    [
        lambda rows: rows[:1],
        lambda rows: [rows[1], rows[0]],
        lambda rows: [rows[0], {**rows[1], "tokenId": rows[0]["tokenId"]}],
        lambda rows: [{**rows[0], "endMs": rows[0]["startMs"]}, rows[1]],
        lambda rows: [rows[0], {**rows[1], "startMs": 20}],
        lambda rows: [rows[0], {**rows[1], "endMs": 101}],
        lambda rows: [{**rows[0], "startMs": 40}, rows[1]],
    ],
)
def test_rejects_incomplete_reordered_duplicate_or_invalid_supports(
    mutate: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> None:
    source = _source()
    words = mutate(_candidate(source)["words"])

    with pytest.raises(RecoveryError):
        _admit(source, candidate=_candidate(source, words=words))


@pytest.mark.parametrize(
    "changes",
    [
        {"audioHash": sha256_bytes(b"wrong audio")},
        {"preparedAudioHash": sha256_bytes(b"wrong preparation")},
        {"textHash": sha256_bytes(b"wrong text")},
        {"blockRevision": 8},
        {"humanVerified": True},
    ],
)
def test_rejects_misbound_or_extra_candidate_claims(changes: dict[str, Any]) -> None:
    source = _source()

    with pytest.raises(RecoveryError):
        _admit(source, candidate=_candidate(source, **changes))


def test_rejects_candidate_hash_mutation() -> None:
    source = _source()
    candidate = _candidate(source)
    candidate["words"][0]["startMs"] = 11

    with pytest.raises(RecoveryError, match="artifact id"):
        _admit(source, candidate=candidate)


@pytest.mark.parametrize(
    "changes",
    [
        {"audioHash": sha256_bytes(b"wrong audio")},
        {"textHash": sha256_bytes(b"wrong text")},
        {"independentOfCandidate": False},
        {"reviewerReference": "  "},
        {"qwenHumanReviewed": True},
    ],
)
def test_rejects_misbound_or_self_asserted_reference(changes: dict[str, Any]) -> None:
    source = _source()

    with pytest.raises(RecoveryError):
        _admit(source, reference=_reference(source, **changes))


def test_reference_requires_each_token_to_be_explicitly_reviewed() -> None:
    source = _source()

    with pytest.raises(RecoveryError, match="explicitly review"):
        _admit(source, reference=_reference(source, reviewed=False))


@pytest.mark.parametrize(
    "onsets",
    [[10], [40, 10], [10, 10]],
)
def test_reference_requires_complete_unique_ordered_tokens(onsets: list[float]) -> None:
    source = _source()

    with pytest.raises(RecoveryError):
        _admit(source, reference=_reference(source, onsets=onsets))


def test_candidate_must_fit_review_uncertainty() -> None:
    source = _source()
    reference = _reference(source, onsets=[16, 40], uncertainties=[5, 5])

    with pytest.raises(RecoveryError, match="exceeds"):
        _admit(source, reference=reference)


@pytest.mark.parametrize("uncertainty", [151, 201])
def test_reported_reference_error_plus_uncertainty_is_bounded(uncertainty: int) -> None:
    source = _source()

    with pytest.raises(RecoveryError, match="uncertainty"):
        _admit(
            source,
            reference=_reference(source, uncertainties=[uncertainty, uncertainty]),
        )


def test_source_requires_exact_normalization_and_preparation_bindings() -> None:
    source = _source()
    wrong_normalization = replace(
        source,
        normalization_provenance={
            **source.normalization_provenance,
            "sourceAudioHash": sha256_bytes(b"other"),
        },
    )
    wrong_preparation = replace(source, prepared_wav_bytes=b"not a wav")

    for malformed in (wrong_normalization, wrong_preparation):
        with pytest.raises(RecoveryError):
            _admit(malformed)


def test_reference_changes_produce_new_content_bound_asset_and_timing_ids() -> None:
    source = _source()
    first = _admit(source)
    second = _admit(source, reference=_reference(source, onsets=[11, 40]))

    assert first.evidence["audioHash"] == second.evidence["audioHash"]
    assert (
        first.evidence["audio"]["cacheAssetId"]
        != second.evidence["audio"]["cacheAssetId"]
    )
    assert first.evidence["timingHash"] != second.evidence["timingHash"]
