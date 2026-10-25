"""Fake whole-row/cache/sparse/compiler handoff; no service/network/native calls."""

from __future__ import annotations

import copy
import html
import io
import json
import math
import struct
import uuid
import wave
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.narration.cache import NarrationCache
from vera_timeline_agent.narration.configuration import (
    MATTHEW_PROFILE_ID,
    pricing_for,
    voice_profile,
)
from vera_timeline_agent.narration.models import (
    ProviderResult,
    ProviderTimingMark,
    SynthesisRequest,
    VoiceProfile,
    identity_hash,
    sha256_bytes,
)
from vera_timeline_agent.narration.normalize import (
    NORMALIZER_VERSION,
    NormalizationResult,
    Normalizer,
)
from vera_timeline_agent.narration.service import NarrationService, ServiceConfig
from vera_timeline_agent.roundtrip_build import ROOT, ProofBuildError, _parse
from vera_timeline_agent.roundtrip_v2_narration import (
    _binding,
    _bridge,
    _sources,
    _verified_asset,
    finalize_replacement_row_v2,
    prepare_replacement_row_v2,
)

# Repeated external Node compiler/validator integration runs serially in the full gate.
pytestmark = pytest.mark.slow


def test_generation_pins_cover_executed_frozen_helpers_and_generated_types() -> None:
    pins = _sources()
    paths = [
        "python/vera_timeline_agent/roundtrip_audio.py",
        "python/vera_timeline_agent/roundtrip_build.py",
        "python/vera_timeline_agent/roundtrip_proof.py",
        "packages/contracts/src/generated/contracts.ts",
        "packages/contracts/src/generated/contracts-v2.ts",
    ]
    assert all(pins[path] == sha256_bytes((ROOT / path).read_bytes()) for path in paths)


class FakeProvider:
    adapter_version = "issue-191-fake-provider/v1"

    def __init__(self, *, fail: bool = False) -> None:
        self.calls = 0
        self.fail = fail

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return f"<speak>{html.escape(request.text)}</speak>".encode()

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        self.calls += 1
        if self.fail:
            raise RuntimeError("uncertain fake provider response")
        raw = b"".join(
            struct.pack("<h", round(1600 * math.sin(i * 0.06)))
            for i in range(8000 + len(request.text) * 20)
        )
        return ProviderResult(
            audio_bytes=raw,
            audio_format="pcm_s16le",
            sample_rate=16000,
            channels=1,
            provider_input=self.prepare_input(request),
            timing_marks=(
                ProviderTimingMark(
                    "sentence",
                    0,
                    0,
                    len(request.text.encode()),
                    0,
                    len(request.text.encode("utf-16-le")) // 2,
                    request.text,
                ),
            ),
            provenance={
                "provider": "issue191_fake",
                "region": "local-test",
                "engine": "fake",
                "voiceId": "fake",
                "voiceVersion": "1",
                "adapterVersion": self.adapter_version,
            },
            request_ids=(f"fake-{self.calls}",),
        )


class FakeNormalizer(Normalizer):
    def __init__(self) -> None:
        super().__init__(profile_id="issue191-fake-normalization")
        self._fingerprint = sha256_bytes(b"issue191-fake-normalizer")

    def result(self, samples: bytes) -> NormalizationResult:
        count = len(samples) // 3
        output = io.BytesIO()
        with wave.open(output, "wb") as stream:
            stream.setparams((1, 3, 48000, count, "NONE", "not compressed"))
            stream.writeframes(samples)
        return NormalizationResult(
            output.getvalue(),
            self.profile_id,
            NORMALIZER_VERSION,
            self.tool_fingerprint,
            48000,
            1,
            "s32 (24 bit)",
            count,
            round(count / 48),
            0,
            -16.0,
            -6.0,
            1.0,
        )

    def normalize_pcm(
        self,
        audio_bytes: bytes,
        *,
        sample_rate: int,
        channels: int,
        audit_clock: bool = False,
    ) -> NormalizationResult:
        assert sample_rate == 16000 and channels == 1
        samples = b"".join(
            (value * 256).to_bytes(3, "little", signed=True) * 3
            for (value,) in struct.iter_unpack("<h", audio_bytes)
        )
        return self.result(samples)

    def placeholder(self, block_id: str) -> NormalizationResult:
        return self.result(bytes(48000 * 3))


def id_for(index: int) -> str:
    return str(uuid.UUID(f"00000000-0000-4000-8000-{index:012x}"))


def setup_case(
    tmp_path: Path, *, fail: bool = False
) -> tuple[dict[str, Any], FakeProvider]:
    fixture = _parse(
        (
            ROOT
            / "tests/data/authoring_v2/issue_180"
            / "before-gamma-24000-1001.input.golden.json"
        ).read_bytes()
    )
    document = fixture["document"]
    row = document["activeDraft"]["blocks"][0]
    row["text"] = "steady left remove these right tail"
    row["tokens"] = []
    offset = 0
    for i, word in enumerate(row["text"].split()):
        row["tokens"].append(
            {
                "id": id_for(100 + i),
                "value": word,
                "startOffset": offset,
                "endOffset": offset + len(word),
            }
        )
        offset += len(word) + 1
    slots = row["primaryVisualSequence"]["slots"]
    row["primaryVisualSequence"]["slots"] = [
        slots[0],
        {
            **slots[1],
            "relation": {"kind": "sequential"},
            "boundaryBefore": {
                "kind": "spoken_word",
                "anchor": {
                    "blockId": row["id"],
                    "tokenId": row["tokens"][4]["id"],
                    "quotedWord": "right",
                    "affinity": "before",
                    "anchorVersion": 1,
                },
            },
        },
    ]
    other = copy.deepcopy(row)
    other["id"] = id_for(200)
    other["orderKey"] = "a1"
    other["text"] = "unchanged other row"
    other["primaryVisualSequence"] = {
        "id": id_for(201),
        "version": 1,
        "slots": [{**slots[0], "id": id_for(202)}],
    }
    other["tokens"] = [
        {
            "id": id_for(210 + i),
            "value": word,
            "startOffset": start,
            "endOffset": start + len(word),
        }
        for i, (word, start) in enumerate(
            (("unchanged", 0), ("other", 10), ("row", 16))
        )
    ]
    document["activeDraft"]["blocks"].append(other)
    provider = FakeProvider()
    service = NarrationService(
        cache=NarrationCache(tmp_path / "cache"),
        provider=provider,
        normalizer=FakeNormalizer(),
        config=ServiceConfig(
            pricing_policy=pricing_for(voice_profile(MATTHEW_PROFILE_ID)),
            profile=VoiceProfile(
                "fake", "issue191_fake", "local-test", "fake", "fake", "1", "en-US"
            ),
            data_policy_attestation="fake-authorized",
            max_cost_usd=0.01,
        ),
    )
    prior = fixture["dependencies"]
    template = copy.deepcopy(prior["narrationBoundaryEvidence"][0])
    prior["narrationBoundaryEvidence"] = []
    for block in (row, other):
        asset = service.process_block(block)
        audio_id = str(
            uuid.uuid5(
                uuid.NAMESPACE_URL, "vera:narration-cache-asset:" + asset.asset_id
            )
        )
        evidence = {
            **template,
            "blockId": block["id"],
            "blockRevision": 1,
            "textHash": sha256_bytes(block["text"].encode()),
            "narrationAssetId": audio_id,
            "audioHash": asset.normalized_audio_hash,
            "timingHash": asset.raw_timing_hash,
            "audio": {
                "narrationAssetId": audio_id,
                "cacheAssetId": asset.asset_id,
                "audioHash": asset.normalized_audio_hash,
                "timingHash": asset.raw_timing_hash,
                "locator": f"Media/Narration/{asset.asset_id}.wav",
                "durationSamples": asset.duration_samples,
                "sampleRate": 48000,
                "channels": 1,
            },
            "tokens": [],
        }
        prior["narrationBoundaryEvidence"].append(evidence)
    old_pins = {
        str(p.relative_to(service.cache.root)): sha256_bytes(p.read_bytes())
        for p in service.cache.root.rglob("*")
        if p.is_file()
    }
    edit = {
        "schemaVersion": "issue-189-v2-accepted-omission/v1",
        "expectedDocumentHash": _bridge(
            "inspect", {"document": document, "prior": prior}
        )["documentHash"],
        "blockId": row["id"],
        "blockRevision": 1,
        "tokenIds": [id_for(102), id_for(103)],
        "evidenceHash": sha256_bytes(b"fake-selected-proof"),
        "decisionHash": sha256_bytes(b"fake-explicit-decision"),
    }
    revised = _bridge("omit", {"document": document, "edit": edit})
    authorized = b"issue191-fake-exact-authorization"
    original_hash = _bridge("inspect", {"document": document, "prior": prior})[
        "priorDependenciesHash"
    ]
    pins: dict[str, str] = {}

    def auth(kind: str, raw: bytes, binding: dict[str, Any]) -> None:
        if kind == "synthesis_authorization":
            assert raw == authorized
            assert binding["request"] == revised["regeneration"]
            assert binding["priorDependenciesHash"] == original_hash
            if not pins:
                pins["service"] = identity_hash(binding["service"])
            if pins["service"] != identity_hash(binding["service"]):
                raise ProofBuildError("authorization differs")
        else:
            assert kind == "replacement_boundaries"
            assert raw == b"issue191-fake-fresh-review"
            assert binding["request"] == revised["regeneration"]

    if fail:
        provider.fail = True
    return {
        "request": revised["regeneration"],
        "document": revised["document"],
        "prior_dependencies": prior,
        "service": service,
        "authorization": authorized,
        "authenticate": auth,
        "oldPins": old_pins,
    }, provider


def inputs(case: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in case.items() if k != "oldPins"}


def fresh_evidence(case: dict[str, Any], receipt: dict[str, Any]) -> dict[str, Any]:
    asset = case["service"].cache.read(
        "assets", f"{case['request']['blockId']}/{receipt['assetId']}", "asset.json"
    )
    assert asset is not None
    metadata = asset.metadata["asset"]
    audio_id = str(
        uuid.uuid5(
            uuid.NAMESPACE_URL, "vera:narration-cache-asset:" + receipt["assetId"]
        )
    )
    row = case["document"]["activeDraft"]["blocks"][0]
    token = row["tokens"][2]
    return {
        "schemaVersion": "narration-boundary-evidence/v1",
        "blockId": row["id"],
        "blockRevision": row["version"],
        "textHash": case["request"]["textHash"],
        "tokenizationVersion": "script-document/v2-frozen-tokens",
        "narrationAssetId": audio_id,
        "audioHash": receipt["audioHash"],
        "timingHash": receipt["providerTimingHash"],
        "alignmentVersion": "issue191-fresh-sparse-review/v1",
        "audio": {
            "narrationAssetId": audio_id,
            "audioHash": receipt["audioHash"],
            "timingHash": receipt["providerTimingHash"],
            "cacheAssetId": receipt["assetId"],
            "locator": f"Media/Narration/{receipt['assetId']}.wav",
            "durationSamples": metadata["duration_samples"],
            "sampleRate": 48000,
            "channels": 1,
        },
        "tokens": [
            {
                "tokenId": token["id"],
                "startOffset": token["startOffset"],
                "endOffset": token["endOffset"],
                "quotedText": token["value"],
                "onset": {"numerator": 1, "denominator": 5},
            }
        ],
        "verification": {
            "method": "reviewed_audio_boundaries/v1",
            "reviewId": id_for(300),
            "reviewRevision": 1,
            "reviewerReference": "issue191-fake-reviewer",
            "reviewArtifactLocator": "Reviews/issue191-fresh.json",
            "reviewArtifactHash": sha256_bytes(b"issue191-fake-fresh-review"),
        },
    }


def test_generate_replay_fresh_sparse_compilation_and_preservation(
    tmp_path: Path,
) -> None:
    case, provider = setup_case(tmp_path)
    before = copy.deepcopy(case["prior_dependencies"])
    root = tmp_path / "generation"
    receipt = prepare_replacement_row_v2(root, **inputs(case))
    assert provider.calls == 3  # two baselines and exactly one whole-row replacement
    assert prepare_replacement_row_v2(root, **inputs(case)) == receipt
    assert provider.calls == 3
    result = finalize_replacement_row_v2(
        root,
        **inputs(case),
        boundary_evidence=fresh_evidence(case, receipt),
        review_artifact=b"issue191-fake-fresh-review",
    )
    assert result["preview"]["report"]["status"] == "ready"
    assert (
        result["preview"]["dependencies"]["narrationBoundaryEvidence"][1]
        == before["narrationBoundaryEvidence"][1]
    )
    assert case["prior_dependencies"] == before
    assert (
        finalize_replacement_row_v2(
            root,
            **inputs(case),
            boundary_evidence=fresh_evidence(case, receipt),
            review_artifact=b"issue191-fake-fresh-review",
        )
        == result
    )
    for relative, pin in case["oldPins"].items():
        assert sha256_bytes((case["service"].cache.root / relative).read_bytes()) == pin


def test_prior_timing_cannot_supply_fresh_handoff(tmp_path: Path) -> None:
    case, provider = setup_case(tmp_path)
    root = tmp_path / "generation"
    receipt = prepare_replacement_row_v2(root, **inputs(case))
    finalized = finalize_replacement_row_v2(
        root,
        **inputs(case),
        boundary_evidence=fresh_evidence(case, receipt),
        review_artifact=b"issue191-fake-fresh-review",
    )
    prior = copy.deepcopy(case["prior_dependencies"])
    prior["narrationBoundaryEvidence"][0]["timingHash"] = receipt["providerTimingHash"]
    row, binding = _binding(
        case["request"], case["document"], prior, case["service"], case["authorization"]
    )
    with pytest.raises(ProofBuildError, match="fresh service"):
        _verified_asset(
            case["service"],
            row,
            prior["narrationBoundaryEvidence"][0],
            binding,
            receipt["assetId"],
        )
    handoff = copy.deepcopy(finalized["handoff"])
    handoff["priorDependenciesHash"] = binding["priorDependenciesHash"]
    with pytest.raises(ProofBuildError, match="fresh whole-row"):
        _bridge(
            "finalize",
            {"document": case["document"], "prior": prior, "handoff": handoff},
        )
    assert provider.calls == 3


@pytest.mark.parametrize("raw", [b"not a wave file", b"RIFF"])
def test_malformed_normalized_pcm_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, raw: bytes
) -> None:
    case, provider = setup_case(tmp_path)
    normalizer = case["service"].normalizer
    original = normalizer.result
    monkeypatch.setattr(
        normalizer, "result", lambda samples: replace(original(samples), wav_bytes=raw)
    )
    root = tmp_path / "generation"
    with pytest.raises(ProofBuildError, match="malformed normalized PCM"):
        prepare_replacement_row_v2(root, **inputs(case))
    assert provider.calls == 3
    assert not (root / "generation.json").exists()


def test_uncertain_call_cannot_retry_from_same_or_new_directory(tmp_path: Path) -> None:
    case, provider = setup_case(tmp_path, fail=True)
    with pytest.raises(ProofBuildError, match="verified service synthesis cache"):
        prepare_replacement_row_v2(tmp_path / "generation", **inputs(case))
    assert provider.calls == 3
    provider.fail = False
    for name in ("generation", "other-directory"):
        with pytest.raises(ProofBuildError, match="uncertain synthesis"):
            prepare_replacement_row_v2(tmp_path / name, **inputs(case))
    assert provider.calls == 3


def test_concurrent_generation_calls_once(tmp_path: Path) -> None:
    case, provider = setup_case(tmp_path)
    with ThreadPoolExecutor(max_workers=2) as executor:
        rows = list(
            executor.map(
                lambda _: prepare_replacement_row_v2(
                    tmp_path / "generation", **inputs(case)
                ),
                range(2),
            )
        )
    assert rows[0] == rows[1]
    assert provider.calls == 3


@pytest.mark.parametrize(
    "fault", ["text", "revision", "document", "config", "authorization"]
)
def test_request_currentness_before_synthesis(tmp_path: Path, fault: str) -> None:
    case, provider = setup_case(tmp_path)
    if fault == "text":
        case["request"]["text"] += " wrong"
    elif fault == "revision":
        case["request"]["blockRevision"] += 1
    elif fault == "document":
        case["document"]["title"] = "stale"
    elif fault == "config":
        prepare_replacement_row_v2(tmp_path / "generation", **inputs(case))
        case["service"].config = replace(case["service"].config, max_cost_usd=0.02)
    else:
        case["authorization"] = b"not-authorized"
    previous_calls = provider.calls
    with pytest.raises((ProofBuildError, AssertionError)):
        prepare_replacement_row_v2(tmp_path / "generation", **inputs(case))
    assert provider.calls == previous_calls


@pytest.mark.parametrize(
    "fault",
    ["audio", "timing", "revision", "quote", "missing", "review", "cache", "handoff"],
)
def test_fresh_boundary_and_cache_refusals(tmp_path: Path, fault: str) -> None:
    case, provider = setup_case(tmp_path)
    root = tmp_path / "generation"
    receipt = prepare_replacement_row_v2(root, **inputs(case))
    evidence = fresh_evidence(case, receipt)
    if fault == "audio":
        evidence["audio"]["audioHash"] = case["prior_dependencies"][
            "narrationBoundaryEvidence"
        ][0]["audioHash"]
    elif fault == "timing":
        evidence["audio"]["timingHash"] = sha256_bytes(b"stale")
    elif fault == "revision":
        evidence["blockRevision"] -= 1
    elif fault == "quote":
        evidence["tokens"][0]["quotedText"] = "wrong"
    elif fault == "missing":
        evidence["tokens"] = []
    elif fault == "review":
        evidence["verification"]["reviewArtifactHash"] = sha256_bytes(b"stale")
    elif fault == "cache":
        asset = case["service"].cache.read(
            "assets", f"{case['request']['blockId']}/{receipt['assetId']}", "asset.json"
        )
        assert asset is not None
        (asset.path / "timing.json").write_bytes(b"{}")
    elif fault == "handoff":
        (root / "generation.json").write_bytes(
            json.dumps({**receipt, "audioHash": sha256_bytes(b"wrong")}).encode()
        )
    with pytest.raises((ProofBuildError, RuntimeError)):
        finalize_replacement_row_v2(
            root,
            **inputs(case),
            boundary_evidence=evidence,
            review_artifact=b"issue191-fake-fresh-review",
        )
    assert provider.calls == 3
    assert not (root / "row-handoff.json").exists()
