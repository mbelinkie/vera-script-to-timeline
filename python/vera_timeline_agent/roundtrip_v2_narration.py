"""#191 immutable whole-row service/replay and fresh sparse boundary handoff."""

from __future__ import annotations

import copy
import os
import shutil
import subprocess
import uuid
import wave
from dataclasses import asdict
from pathlib import Path

from vera_timeline_agent.narration.campaign import (
    CAP_MICRO_USD,
    STATUS_ATTEMPTED,
    STATUS_CHARGED,
    STATUS_RESERVED,
    CapExceeded,
    Ledger,
    _micro,
    default_ledger_path,
)
from vera_timeline_agent.narration.compiler_dependencies import (
    narration_dependency_from_asset,
)
from vera_timeline_agent.narration.configuration import (
    PricingPolicy,
    pricing_for,
    provider_for,
)
from vera_timeline_agent.narration.measure import (
    METHOD as MEASURED_METHOD,
)
from vera_timeline_agent.narration.measure import (
    MeasurementError,
    load_asset,
    measure_asset,
)
from vera_timeline_agent.narration.models import (
    NarrationAudioAsset,
    ProviderResult,
    SynthesisRequest,
    identity_hash,
)
from vera_timeline_agent.narration.normalize import NORMALIZER_VERSION, Normalizer
from vera_timeline_agent.narration.provider import (
    SpeechProviderError,
    SpeechSynthesisProvider,
)
from vera_timeline_agent.narration.service import (
    MATTHEW_PROFILE_ID,
    BlockPlan,
    NarrationService,
    ServiceConfig,
    voice_profile,
)
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
        *sorted((ROOT / "packages/contracts/src").rglob("*.ts")),
        *sorted((ROOT / "contracts").glob("*.json")),
        ROOT / "package-lock.json",
        Path(__file__),
        ROOT / "python/vera_timeline_agent/roundtrip_v2_audio.py",
        ROOT / "python/vera_timeline_agent/roundtrip_audio.py",
        ROOT / "python/vera_timeline_agent/roundtrip_build.py",
        ROOT / "python/vera_timeline_agent/roundtrip_proof.py",
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
            # The optional injected policy must not rewrite historical defaults.
            "config": {
                key: value
                for key, value in asdict(service.config).items()
                if key != "pricing_policy" or value is not None
            },
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


def _clear_owned_unsent_intent(
    service: NarrationService,
    intent_path: Path,
    intent_raw: bytes,
    request_hash: str,
) -> None:
    """Remove only a new intent with neither a guarded attempt nor cached result."""
    provider = service.provider
    if not isinstance(provider, LedgerGuardedProvider):
        return
    try:
        if any(
            row.get("requestHash") == request_hash for row in provider.ledger.rows()
        ):
            return
        if service.cache.read("synthesis", request_hash[7:], "synthesis.json"):
            return
        if (
            intent_path.is_symlink()
            or not intent_path.is_file()
            or _operator_bytes(intent_path) != intent_raw
        ):
            return
        intent_path.unlink()
    except Exception:
        # Cleanup is best-effort; uncertainty or filesystem trouble keeps intent.
        return


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
        intent_raw = _bytes(intent)
        old_intent = intent_path.exists()
        if old_intent:
            fact(
                _operator_bytes(intent_path) == intent_raw,
                "service request intent differs",
            )
            fact(
                service.cache.read("synthesis", request_hash[7:], "synthesis.json")
                is not None,
                "uncertain synthesis: no duplicate call without verified cache",
            )
        else:
            publish_immutable_output(intent_path, intent_raw)
        try:
            if (root / "generation.json").exists():
                retained = _parse(_operator_bytes(root / "generation.json"))
                asset_id = retained["assetId"]
            else:
                asset_id = service.process_block(row).asset_id
            _cache_safety(service)
            _, receipt = _verified_asset(
                service,
                row,
                _prior_row(prior_dependencies, row["id"]),
                binding,
                asset_id,
            )
        except BaseException:
            if not old_intent:
                _clear_owned_unsent_intent(
                    service, intent_path, intent_raw, request_hash
                )
            raise
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
    verification = evidence.get("verification", {})
    measured = verification.get("method") == MEASURED_METHOD
    if measured:
        # #182 measured evidence keeps the cache-relative locator the measurer
        # recorded and pins its measurement artifact instead of a human review.
        expected_audio["locator"] = asset.locators["audio"]
    artifact_key = "measurementArtifactHash" if measured else "reviewArtifactHash"
    fact(
        evidence.get("audio") == expected_audio
        and evidence.get("narrationAssetId") == audio_id
        and evidence.get("audioHash") == asset.normalized_audio_hash
        and evidence.get("timingHash") == asset.raw_timing_hash
        and verification.get(artifact_key) == _hash(review_artifact),
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


# --------------------------------------------------------------------- #215
# Whole-row regeneration of an accepted omission with automatic timing.


class ProviderCallRefused(ProofBuildError):
    """A real provider call is needed but is not authorized or affordable."""


# Tests only: allow a ledger other than the approved campaign ledger.
TEST_LEDGER_ENV = "VERA_ALLOW_NONCAMPAIGN_LEDGER_FOR_TESTS"


def campaign_ledger(ledger: Ledger | None = None) -> Ledger:
    """The approved campaign ledger; any other path is refused.

    ``None`` selects ``narration.campaign.default_ledger_path()``. Another path
    is accepted only when the test hook environment variable is set, so a real
    run can never spend against (or hide spend from) an unapproved ledger.
    """
    approved = default_ledger_path()
    if ledger is None:
        return Ledger(approved)
    if ledger.path.absolute() != approved.absolute() and (
        os.environ.get(TEST_LEDGER_ENV) != "1"
    ):
        raise ProviderCallRefused(
            "only the approved campaign ledger may be used for provider calls"
        )
    return ledger


def refuse_uncertain_prior_attempt(ledger: Ledger, request_hash: str) -> None:
    """Never resend a request whose earlier attempt has no verified result."""
    for row in ledger.rows():
        if row.get("requestHash") == request_hash and row.get("status") in (
            STATUS_RESERVED,
            STATUS_ATTEMPTED,
        ):
            raise ProviderCallRefused(
                "the campaign ledger records an uncertain earlier attempt "
                f"({row['status']}) for this exact request with no cached "
                "result; it will not be resent automatically"
            )


class LedgerGuardedProvider:
    """Reserve every real call in the campaign ledger before it can reach AWS.

    Wraps the provider a NarrationService calls. Cache hits never reach
    ``synthesize`` so they reserve and charge nothing. The reservation is
    written (under the ledger lock, cap checked) strictly before the inner call
    and is settled ``charged``/``attempted``; nothing is ever refunded.
    """

    def __init__(
        self,
        inner: SpeechSynthesisProvider,
        ledger: Ledger,
        *,
        confirmed: bool,
        cap_micro_usd: int = CAP_MICRO_USD,
        pricing_policy: PricingPolicy | None = None,
    ) -> None:
        self.inner = inner
        self.adapter_version = inner.adapter_version
        self.ledger = ledger
        self.confirmed = confirmed
        self.cap_micro_usd = cap_micro_usd
        self.pricing_policy = pricing_policy

    def prepare_input(self, request: SynthesisRequest) -> bytes:
        return self.inner.prepare_input(request)

    def preflight(self, request: SynthesisRequest) -> None:
        preflight = getattr(self.inner, "preflight", None)
        if callable(preflight):
            preflight(request)

    def synthesize(self, request: SynthesisRequest) -> ProviderResult:
        if not self.confirmed:
            raise ProviderCallRefused("provider call was not confirmed")
        # Local refusals must precede both call intent and spend reservation.
        self.preflight(request)
        request_hash = identity_hash(
            request.identity(
                self.inner.prepare_input(request), self.inner.adapter_version
            )
        )
        policy = self.pricing_policy or pricing_for(request.profile)
        estimated = policy.estimate(request.text)
        with self.ledger.locked():
            refuse_uncertain_prior_attempt(self.ledger, request_hash)
            try:
                reservation = self.ledger.reserve(
                    request_hash=request_hash,
                    block_id=request.block_id,
                    characters=len(request.text),
                    estimated_cost_usd=estimated,
                    cap_micro_usd=self.cap_micro_usd,
                )
            except CapExceeded as error:
                # The reservation refused before transport, so retrying is safe.
                raise SpeechProviderError(str(error), request_rejected=True) from error
            try:
                result = self.inner.synthesize(request)
            except BaseException:
                self.ledger.settle(reservation["reservationId"], STATUS_ATTEMPTED)
                raise
            self.ledger.settle(
                reservation["reservationId"], STATUS_CHARGED, result.request_ids
            )
            return result


def production_narration_service(
    cache_dir: Path,
    *,
    data_policy: str,
    provider: SpeechSynthesisProvider | None = None,
    normalizer: Normalizer | None = None,
    profile_id: str = MATTHEW_PROFILE_ID,
) -> NarrationService:
    """The #182 campaign service: campaign cache, Matthew Neural, attested policy."""
    from vera_timeline_agent.narration.cache import NarrationCache

    return NarrationService(
        cache=NarrationCache(cache_dir),
        provider=provider or provider_for(voice_profile(profile_id)),
        normalizer=normalizer or Normalizer(),
        config=ServiceConfig(
            profile=voice_profile(profile_id),
            data_policy_attestation=data_policy,
            max_cost_usd=1.0,
        ),
    )


def guard_service(
    service: NarrationService,
    ledger: Ledger,
    *,
    confirm_provider_call: bool,
    cap_micro_usd: int = CAP_MICRO_USD,
) -> NarrationService:
    """The same service and cache, with every real provider call ledger-guarded."""
    return NarrationService(
        cache=service.cache,
        provider=LedgerGuardedProvider(
            service.provider,
            ledger,
            confirmed=confirm_provider_call,
            cap_micro_usd=cap_micro_usd,
            pricing_policy=service.config.pricing,
        ),
        normalizer=service.normalizer,
        config=service.config,
    )


def preflight_provider_call(
    service: NarrationService,
    row: JsonObject,
    *,
    ledger: Ledger,
    confirm_provider_call: bool,
    cap_micro_usd: int = CAP_MICRO_USD,
) -> BlockPlan:
    """Decide, before any intent or reservation exists, whether a call is needed.

    A cache hit (identical request) needs no call, no confirmation, no charge.
    An uncertain earlier attempt for the same request is refused here too, so
    it can never be silently re-sent. Otherwise confirmation and cap are
    required.
    """
    plan = service.plan_block(row)
    request_key = plan.request_hash[7:]
    intent = service.cache.root / "issue-191-call-intents" / request_key / "intent.json"
    if plan.cached:
        return plan
    if intent.exists():
        raise ProviderCallRefused(
            "an earlier provider attempt for this exact request has no verified "
            "result; it is preserved and will not be resynthesized automatically"
        )
    refuse_uncertain_prior_attempt(ledger, plan.request_hash)
    if not confirm_provider_call:
        raise ProviderCallRefused(
            f"a real provider call (about ${plan.estimated_cost_usd:.6f}, "
            f"{plan.characters} characters) is needed for the regenerated row; "
            "re-run with --confirm-provider-call to authorize it"
        )
    ledger.check(_micro(plan.estimated_cost_usd), cap_micro_usd)
    preflight = getattr(service.provider, "preflight", None)
    if callable(preflight):
        try:
            preflight(service._request(row))
        except SpeechProviderError as error:
            raise ProviderCallRefused(
                f"provider preflight failed before any call: {error}"
            ) from error
    return plan


def measure_replacement_row_v2(
    root: Path,
    *,
    row: JsonObject,
    service: NarrationService,
    project_root: Path,
) -> tuple[JsonObject, bytes, bytes]:
    """Measure the retained fresh asset (#182) and retain artifact + evidence.

    Returns the boundary evidence, the measurement artifact bytes and the
    provider timing bytes. Nothing is synthesized here; a refusal (connected
    speech, unverified lag, ...) leaves the cached asset untouched.
    """
    retained = _parse(_operator_bytes(root / "generation.json"))
    asset_key = f"{row['id']}/{retained['assetId']}"
    loaded = load_asset(service.cache, asset_key)
    artifact_path = (
        root / "narration-measurements" / f"{retained['assetId']}.measurement.json"
    )
    try:
        locator = artifact_path.resolve().relative_to(project_root.resolve()).as_posix()
        result = measure_asset(loaded, row, artifact_locator=locator)
    except (ValueError, MeasurementError) as error:
        raise ProofBuildError(
            f"regenerated row measurement refused: {error}"
        ) from error
    publish_immutable_output(artifact_path, result.artifact_bytes)
    publish_immutable_output(
        artifact_path.with_name(f"{retained['assetId']}.boundary-evidence.json"),
        _bytes(result.evidence),
    )
    return result.evidence, result.artifact_bytes, loaded.timing_bytes
