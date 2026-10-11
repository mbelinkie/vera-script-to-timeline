"""#191 immutable whole-row service/replay and fresh sparse boundary handoff."""

from __future__ import annotations

import copy
import shutil
import subprocess
import uuid
import wave
from dataclasses import asdict
from pathlib import Path

from vera_timeline_agent.narration.compiler_dependencies import (
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.models import NarrationAudioAsset, identity_hash
from vera_timeline_agent.narration.normalize import NORMALIZER_VERSION
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_audio import _pcm
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    JsonObject,
    ProofBuildError,
    _file_hash,
    _operator_bytes,
    _parse,
)
from vera_timeline_agent.roundtrip_proof import _destination, publish_immutable_output
from vera_timeline_agent.roundtrip_v2_audio import ReceiptVerifier, fact, shape

BRIDGE = ROOT / "packages/contracts/src/issue-191-proof-cli.ts"


def _sources() -> JsonObject:
    paths = [
        *sorted((ROOT / "packages/contracts/src").glob("*.ts")),
        *sorted((ROOT / "contracts").glob("*.json")),
        ROOT / "package-lock.json",
        Path(__file__),
        ROOT / "python/vera_timeline_agent/roundtrip_v2_audio.py",
        *sorted((ROOT / "python/vera_timeline_agent/narration").glob("*.py")),
    ]
    return {str(p.relative_to(ROOT)): _file_hash(p) for p in paths}


def _bridge(action: str, value: JsonObject) -> JsonObject:
    result = subprocess.run(
        [shutil.which("node") or "node", str(BRIDGE), action],
        input=_bytes(value),
        capture_output=True,
        timeout=120,
        check=False,
    )
    fact(
        result.returncode == 0,
        f"v2 pure bridge refused: {result.stderr.decode(errors='replace')}",
    )
    return _parse(result.stdout)


def _bytes(value: JsonObject) -> bytes:
    from vera_timeline_agent.narration.models import canonical_json_bytes

    return canonical_json_bytes(value)


def _cache_safety(service: NarrationService) -> None:
    root = service.cache.root
    _destination(root / ".issue191-check")
    for path in root.rglob("*"):
        fact(
            not path.is_symlink() and (not path.is_file() or path.stat().st_nlink == 1),
            "independent narration cache required",
        )


def _prior_row(prior: JsonObject, row_id: str) -> JsonObject:
    rows = [
        r
        for r in [
            *prior["narrationTimingMaps"],
            *prior.get("narrationBoundaryEvidence", []),
        ]
        if r["blockId"] == row_id
    ]
    fact(len(rows) == 1, "one prior narration dependency required")
    return rows[0]  # type: ignore[no-any-return]


def _binding(
    request: JsonObject,
    document: JsonObject,
    prior: JsonObject,
    service: NarrationService,
    authorization: bytes,
) -> tuple[JsonObject, JsonObject]:
    shape(
        request,
        "schemaVersion policy blockId blockRevision text textHash "
        "revisedDocumentHash evidenceHash decisionHash",
        "row request",
    )
    validated = _bridge(
        "validate", {"document": document, "request": request, "prior": prior}
    )
    row = next(
        r for r in document["activeDraft"]["blocks"] if r["id"] == request["blockId"]
    )
    old = _prior_row(prior, row["id"])
    fact(
        row["version"] == old["blockRevision"] + 1
        and request["textHash"] != old["textHash"],
        "fresh whole-row wording/revision required",
    )
    _cache_safety(service)
    synth = service._request(row)
    provider_input = service.provider.prepare_input(synth)
    fact(
        bool(service.config.data_policy_attestation)
        and service.config.max_cost_usd > 0,
        "explicit data policy and cost authority required",
    )
    binding = {
        "schemaVersion": "issue-189-v2-generation-inputs/v1",
        "request": request,
        "priorDependenciesHash": validated["priorDependenciesHash"],
        "sourceHashes": _sources(),
        "authorizationHash": _hash(authorization),
        "service": {
            "requestIdentity": synth.identity(
                provider_input, service.provider.adapter_version
            ),
            "config": asdict(service.config),
            "cacheRoot": str(service.cache.root),
            "normalizer": {
                "profileId": service.normalizer.profile_id,
                "toolFingerprint": service.normalizer.tool_fingerprint,
                "version": NORMALIZER_VERSION,
            },
        },
    }
    return row, binding


def _hash(raw: bytes) -> str:
    from vera_timeline_agent.narration.models import sha256_bytes

    return sha256_bytes(raw)


def _verified_asset(
    service: NarrationService,
    row: JsonObject,
    old: JsonObject,
    binding: JsonObject,
    asset_id: str,
) -> tuple[NarrationAudioAsset, JsonObject]:
    entry = service.cache.read("assets", f"{row['id']}/{asset_id}", "asset.json")
    fact(entry is not None, "verified fresh asset cache required")
    assert entry is not None
    asset = NarrationAudioAsset(**entry.metadata["asset"])
    request_hash = identity_hash(binding["service"]["requestIdentity"])
    synthesis = service.cache.read("synthesis", request_hash[7:], "synthesis.json")
    fact(synthesis is not None, "verified service synthesis cache required")
    assert synthesis is not None
    normalization = service.cache.read(
        "normalization", asset.normalization_hash[7:], "normalization.json"
    )
    fact(normalization is not None, "verified service normalization cache required")
    assert normalization is not None
    fact(
        asset.status == "ready"
        and asset.block_id == row["id"]
        and asset.block_revision == row["version"]
        and asset.text_hash == _hash(row["text"].encode())
        and asset.request_hash == request_hash
        and bool(asset.request_ids)
        and asset.provider == service.config.profile.provider
        and asset.region == service.config.profile.region
        and asset.model == service.config.profile.engine
        and asset.voice_id == service.config.profile.voice_id
        and asset.voice_version == service.config.profile.voice_version
        and asset.data_policy_attestation == service.config.data_policy_attestation
        and asset.profile_hash == identity_hash(asdict(service.config.profile))
        and asset.settings_hash == identity_hash(asdict(service.config.settings))
        and asset.pronunciation_hash
        == identity_hash([asdict(v) for v in service.config.pronunciations])
        and asset.asset_id != old["audio"]["cacheAssetId"]
        and asset.normalized_audio_hash != old["audioHash"]
        and asset.raw_timing_hash != old["timingHash"]
        and asset.asset_id == asset_id,
        "fresh service row/text/audio/timing/provenance differs",
    )
    fact(
        asset.provider_input_hash == _hash(synthesis.files["provider-input.ssml"])
        and asset.raw_audio_hash == _hash(synthesis.files["provider-audio.pcm"])
        and asset.raw_timing_hash == _hash(synthesis.files["provider-timing.json"])
        and entry.files["timing.json"] == synthesis.files["provider-timing.json"]
        and asset.normalized_audio_hash == _hash(entry.files["narration.wav"])
        and entry.files["narration.wav"] == normalization.files["narration.wav"]
        and asset.provider_input_hash
        == binding["service"]["requestIdentity"]["providerInputHash"]
        and synthesis.metadata["requestIds"] == list(asset.request_ids),
        "cache/audio/timing/request receipt differs",
    )
    try:
        _pcm(entry.files["narration.wav"], asset.channels, asset.duration_samples)
    except (wave.Error, EOFError) as error:
        raise ProofBuildError("malformed normalized PCM") from error
    projected = narration_dependency_from_asset(asset, entry.files["timing.json"])
    text_utf16 = row["text"].encode("utf-16-le")
    for mark in projected["timing"]["marks"]:
        fact(
            mark["endUtf16"] <= len(text_utf16) // 2
            and text_utf16[mark["startUtf16"] * 2 : mark["endUtf16"] * 2].decode(
                "utf-16-le"
            )
            == mark["value"]
            and mark["timeMs"] * asset.sample_rate < asset.duration_samples * 1000,
            "provider timing contradicts fresh text/audio",
        )
    fact(
        asset.sample_rate == 48000
        and asset.sample_format == normalization.metadata["sampleFormat"],
        "fresh normalized PCM profile required",
    )
    normalized = normalization.metadata
    fact(
        normalized["profileId"] == service.normalizer.profile_id
        and normalized["toolFingerprint"] == service.normalizer.tool_fingerprint
        and normalized["normalizerVersion"] == NORMALIZER_VERSION,
        "normalizer provenance differs",
    )
    fact(
        asset.normalization_hash
        == identity_hash(
            {
                "recordVersion": "normalization-key/v1",
                "rawAudioHash": asset.raw_audio_hash,
                "rawTimingHash": asset.raw_timing_hash,
                "profileId": service.normalizer.profile_id,
                "toolFingerprint": service.normalizer.tool_fingerprint,
                "normalizerVersion": NORMALIZER_VERSION,
            }
        )
        and all(
            normalized[name] == expected
            for name, expected in (
                ("durationSamples", asset.duration_samples),
                ("sampleRate", asset.sample_rate),
                ("channels", asset.channels),
                ("durationMs", asset.duration_ms),
            )
        ),
        "normalization identity/extent differs",
    )
    receipt = {
        "schemaVersion": "issue-189-v2-row-generation/v1",
        "status": "ready_for_boundary_review",
        "generationInputHash": identity_hash(binding),
        "serviceRequestHash": request_hash,
        "assetId": asset.asset_id,
        "assetRecordHash": _file_hash(entry.path / "asset.json"),
        "audioHash": asset.normalized_audio_hash,
        "providerTimingHash": asset.raw_timing_hash,
        "cacheHashes": {
            "synthesis": _file_hash(synthesis.path / "synthesis.json"),
            "normalization": _file_hash(normalization.path / "normalization.json"),
        },
    }
    return asset, receipt


def prepare_replacement_row_v2(
    root: Path,
    *,
    request: JsonObject,
    document: JsonObject,
    prior_dependencies: JsonObject,
    service: NarrationService,
    authorization: bytes,
    authenticate: ReceiptVerifier,
) -> JsonObject:
    """Generate/replay one row via an already explicitly authorized service.

    No service is constructed/discovered here. Authorization must bind the exact
    request/config/decision and cost/privacy policy through the trusted port.
    A central request intent prevents uncertain retries through a new directory.
    Sparse acoustic review is a later step, after actual fresh bytes exist.
    """
    row, binding = _binding(
        request, document, prior_dependencies, service, authorization
    )
    authenticate("synthesis_authorization", authorization, binding)
    root = root.absolute()
    _destination(root / "generation-inputs.json")
    root.mkdir(parents=True, exist_ok=True)
    request_hash = identity_hash(binding["service"]["requestIdentity"])
    lock_key = identity_hash({"issue191Call": request_hash})[7:]
    with service.cache.lock(lock_key):
        publish_immutable_output(root / "generation-inputs.json", _bytes(binding))
        intent_path = (
            service.cache.root
            / "issue-191-call-intents"
            / request_hash[7:]
            / "intent.json"
        )
        intent = {
            "schemaVersion": "issue-189-v2-call-intent/v1",
            "requestIdentity": binding["service"]["requestIdentity"],
        }
        old_intent = intent_path.exists()
        if old_intent:
            fact(
                _operator_bytes(intent_path) == _bytes(intent),
                "service request intent differs",
            )
            fact(
                service.cache.read("synthesis", request_hash[7:], "synthesis.json")
                is not None,
                "uncertain synthesis: no duplicate call without verified cache",
            )
        else:
            publish_immutable_output(intent_path, _bytes(intent))
        if (root / "generation.json").exists():
            retained = _parse(_operator_bytes(root / "generation.json"))
            asset_id = retained["assetId"]
        else:
            asset_id = service.process_block(row).asset_id
        _cache_safety(service)
        _, receipt = _verified_asset(
            service, row, _prior_row(prior_dependencies, row["id"]), binding, asset_id
        )
        fact(_sources() == binding["sourceHashes"], "generation source code changed")
        publish_immutable_output(root / "generation.json", _bytes(receipt))
        return copy.deepcopy(receipt)


def finalize_replacement_row_v2(
    root: Path,
    *,
    request: JsonObject,
    document: JsonObject,
    prior_dependencies: JsonObject,
    service: NarrationService,
    authorization: bytes,
    boundary_evidence: JsonObject,
    review_artifact: bytes,
    authenticate: ReceiptVerifier,
) -> JsonObject:
    """Reverify cache and fresh review before replacing exactly one timing row."""
    row, binding = _binding(
        request, document, prior_dependencies, service, authorization
    )
    authenticate("synthesis_authorization", authorization, binding)
    fact(
        _operator_bytes(root / "generation-inputs.json") == _bytes(binding),
        "retained generation inputs differ",
    )
    retained = _parse(_operator_bytes(root / "generation.json"))
    asset, receipt = _verified_asset(
        service,
        row,
        _prior_row(prior_dependencies, row["id"]),
        binding,
        retained["assetId"],
    )
    fact(retained == receipt, "retained generation receipt differs")
    evidence = copy.deepcopy(boundary_evidence)
    audio_id = str(
        uuid.uuid5(uuid.NAMESPACE_URL, "vera:narration-cache-asset:" + asset.asset_id)
    )
    expected_audio = {
        "narrationAssetId": audio_id,
        "cacheAssetId": asset.asset_id,
        "audioHash": asset.normalized_audio_hash,
        "timingHash": asset.raw_timing_hash,
        "durationSamples": asset.duration_samples,
        "sampleRate": asset.sample_rate,
        "channels": asset.channels,
        "locator": f"Media/Narration/{asset.asset_id}.wav",
    }
    fact(
        evidence.get("audio") == expected_audio
        and evidence.get("narrationAssetId") == audio_id
        and evidence.get("audioHash") == asset.normalized_audio_hash
        and evidence.get("timingHash") == asset.raw_timing_hash
        and evidence.get("verification", {}).get("reviewArtifactHash")
        == _hash(review_artifact),
        "fresh boundary/verified cache/review binding differs",
    )
    authenticate(
        "replacement_boundaries",
        review_artifact,
        {
            "request": request,
            "audio": expected_audio,
            "providerTimingHash": asset.raw_timing_hash,
            "boundaryEvidence": evidence,
        },
    )
    handoff = {
        "schemaVersion": "issue-189-v2-row-handoff/v1",
        "request": request,
        "priorDependenciesHash": binding["priorDependenciesHash"],
        "serviceRequestHash": asset.request_hash,
        "generationReceiptHash": identity_hash(receipt),
        "assetRecordHash": receipt["assetRecordHash"],
        "audioHash": asset.normalized_audio_hash,
        "providerTimingHash": asset.raw_timing_hash,
        "reviewArtifactHash": _hash(review_artifact),
        "boundaryEvidence": evidence,
    }
    preview = _bridge(
        "finalize",
        {"document": document, "prior": prior_dependencies, "handoff": handoff},
    )
    _cache_safety(service)
    fact(
        _sources() == binding["sourceHashes"]
        and _parse(_operator_bytes(root / "generation.json")) == receipt,
        "generation sources/receipt changed during finalization",
    )
    publish_immutable_output(root / "row-handoff.json", _bytes(handoff))
    publish_immutable_output(root / "replacement-preview.json", _bytes(preview))
    return {"handoff": handoff, "preview": preview}
