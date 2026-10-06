"""Issue144 synthetic whole-row generation into the existing build/promotion path."""

from __future__ import annotations

import re
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from vera_timeline_agent.build_jobs import NeedsAction
from vera_timeline_agent.narration.cache import CacheError
from vera_timeline_agent.narration.models import identity_hash
from vera_timeline_agent.narration.polly import PollyProvider
from vera_timeline_agent.narration.service import NarrationService
from vera_timeline_agent.roundtrip_build import (
    INPUT_NAMES,
    JsonObject,
    PreparedBuild,
    ProofBuildError,
    _digest,
    _file_hash,
    _operator_bytes,
    _parse,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_narration import replace_row_narration
from vera_timeline_agent.roundtrip_omission import OmissionProof, _fact
from vera_timeline_agent.roundtrip_proof import _destination, publish_immutable_output

if TYPE_CHECKING:
    from vera_timeline_agent.roundtrip_proof import ProofSession


class OmissionGeneration:
    def __init__(self, session: ProofSession, key: str) -> None:
        _fact(
            re.fullmatch(r"[a-f0-9]{64}", key) is not None,
            "valid decision key required",
        )
        self.session = session
        self.key = key
        self.directory = session.root / "decisions" / key
        stored = load_operator_json(self.directory / "receipt.json")
        self.proof = OmissionProof(session, baseline_hash=stored["baselineHash"])
        self.decision = self.proof.retained_decision(key)
        _fact(
            self.decision["status"] == "prepared_revision",
            "only an explicitly accepted omission can generate or rebuild",
        )
        self.prior = self.proof.build
        self.revision = Path(self.decision["revisionRoot"])
        self.input_path = self.directory / "generation-inputs.json"
        self.handoff_path = self.directory / "row-handoff.json"
        self.receipt_path = self.directory / "generation.json"

    def current(self) -> None:
        self.proof.current()
        _fact(
            _file_hash(self.session.pointer) == self.decision["baselinePointerHash"],
            "stale omission generation baseline",
        )

    def fresh(self, purpose: str) -> None:
        self.current()
        a, b = self.proof.capture(purpose, self.key, pristine=False)
        _fact(
            self.proof.proposal_inputs(a, b)
            == load_operator_json(self.directory / "inputs.json"),
            "edited omission observation changed before generation/rebuild",
        )
        self.current()

    def service_inputs(self) -> tuple[NarrationService, JsonObject]:
        service = self.session.narration_service
        if service is None:
            raise NeedsAction(
                "explicit local synthetic whole-row NarrationService required"
            )
        _fact(
            isinstance(service, NarrationService)
            and service.config.profile.provider == "issue144_synthetic"
            and service.config.profile.region == "local-test"
            and not isinstance(service.provider, PollyProvider),
            "only explicitly injected synthetic narration is allowed",
        )
        cache = service.cache.root
        _fact(
            cache.is_relative_to(self.session.root),
            "proof-local narration cache required",
        )
        _destination(cache / ".issue144-path-check")
        for path in cache.rglob("*"):
            _fact(
                not path.is_symlink()
                and (not path.is_file() or path.stat().st_nlink == 1),
                "independent narration cache files required",
            )
        document = load_operator_json(self.revision / "script-document.json")
        row = next(
            block
            for block in document["activeDraft"]["blocks"]
            if block["id"] == self.proof.row["id"]
        )
        request = service._request(row)
        provider_input = service.provider.prepare_input(request)
        binding = {
            "schemaVersion": "issue-144-generation-inputs/v1",
            "decisionHash": self.decision["decisionHash"],
            "reportHash": self.decision["reportHash"],
            "baselineSnapshotId": self.prior.snapshot_id,
            "revisedDocumentHash": _file_hash(self.revision / "script-document.json"),
            "sources": self.prior.source_hashes,
            "service": {
                "requestIdentity": request.identity(
                    provider_input, service.provider.adapter_version
                ),
                "config": asdict(service.config),
                "normalizer": {
                    "profileId": service.normalizer.profile_id,
                    "toolFingerprint": service.normalizer.tool_fingerprint,
                },
                "cacheRoot": str(cache),
            },
        }
        return service, binding

    def cache_replay(self, service: NarrationService, binding: JsonObject) -> None:
        # Cache locks deduplicate identical keys. This check prevents a retained
        # decision from silently synthesizing again when its cache is missing.
        request_hash = identity_hash(binding["service"]["requestIdentity"])
        try:
            synthesis = service.cache.read(
                "synthesis", request_hash[7:], "synthesis.json"
            )
            _fact(synthesis is not None, "retained synthesis cache is missing")
            if self.handoff_path.exists():
                retained = load_operator_json(self.handoff_path)
                _fact(
                    retained["baselineSnapshotId"] == self.prior.snapshot_id
                    and retained["revisedDocumentHash"]
                    == binding["revisedDocumentHash"]
                    and retained["sources"] == self.prior.source_hashes
                    and len(retained["replacements"]) == 1,
                    "retained whole-row handoff binding differs",
                )
                replacement = retained["replacements"][0]
                _fact(
                    replacement["blockId"] == self.proof.row["id"]
                    and replacement["requestHash"] == request_hash,
                    "retained row/request differs",
                )
                entry = service.cache.read(
                    "assets",
                    f"{replacement['blockId']}/{replacement['assetId']}",
                    "asset.json",
                )
                _fact(entry is not None, "retained asset cache is missing")
                assert entry is not None
                _fact(
                    replacement["assetRecordPath"] == str(entry.path / "asset.json")
                    and replacement["timingPath"] == str(entry.path / "timing.json")
                    and replacement["origin"] == str(entry.path / "narration.wav"),
                    "retained cache path differs",
                )
                for path_key, hash_key in (
                    ("assetRecordPath", "assetRecordHash"),
                    ("timingPath", "timingHash"),
                    ("origin", "audioHash"),
                ):
                    _fact(
                        _file_hash(Path(replacement[path_key]))
                        == replacement[hash_key],
                        "retained generated bytes changed",
                    )
        except CacheError as error:
            raise ProofBuildError(
                "retained narration cache verification failed"
            ) from error

    def materialization(self, manifest: JsonObject, handoff: JsonObject) -> JsonObject:
        replacement = handoff["replacements"][0]
        prior_sources = {
            source["id"]: source for source in self.proof.manifest["sources"]
        }
        plan: JsonObject = {}
        new = []
        for source in manifest["sources"]:
            if source["kind"] == "placeholder":
                continue
            if source["id"] in self.prior.plan:
                _fact(
                    source == prior_sources[source["id"]],
                    "unrelated compiled source changed",
                )
                plan[source["id"]] = self.prior.plan[source["id"]]
            else:
                _fact(
                    source["kind"] == "audio"
                    and source["path"]
                    == f"Media/Narration/{replacement['assetId']}.wav"
                    and source["contentHash"] == replacement["audioHash"],
                    "unexplained replacement source",
                )
                new.append(source["id"])
                plan[source["id"]] = {
                    "artifactId": replacement["assetId"],
                    "origin": replacement["origin"],
                    "policy": "copy",
                }
        _fact(len(new) == 1, "one actual new complete-row narration source required")
        return plan

    def cache_snapshot(
        self, service: NarrationService, handoff: JsonObject
    ) -> JsonObject:
        replacement = handoff["replacements"][0]
        try:
            asset = service.cache.read(
                "assets",
                f"{replacement['blockId']}/{replacement['assetId']}",
                "asset.json",
            )
            _fact(asset is not None, "retained asset cache is missing")
            assert asset is not None
            synthesis = service.cache.read(
                "synthesis", replacement["requestHash"][7:], "synthesis.json"
            )
            normalized = service.cache.read(
                "normalization",
                asset.metadata["asset"]["normalization_hash"][7:],
                "normalization.json",
            )
            result: JsonObject = {}
            for entry, record, expected_files in (
                (asset, "asset.json", {"narration.wav", "timing.json"}),
                (
                    synthesis,
                    "synthesis.json",
                    {
                        "provider-input.ssml",
                        "provider-audio.pcm",
                        "provider-timing.json",
                    },
                ),
                (normalized, "normalization.json", {"narration.wav"}),
            ):
                _fact(entry is not None, "retained generation cache entry is missing")
                assert entry is not None
                _fact(
                    set(entry.files) == expected_files,
                    "generation cache payload inventory differs",
                )
                for name in (record, *sorted(expected_files)):
                    result[str(entry.path / name)] = _file_hash(entry.path / name)
            return result
        except CacheError as error:
            raise ProofBuildError(
                "retained complete cache verification failed"
            ) from error

    def finalize(self, *, publish: bool) -> tuple[JsonObject, PreparedBuild]:
        service, binding = self.service_inputs()
        raw_binding = _receipt_bytes(binding)
        request_hash = identity_hash(binding["service"]["requestIdentity"])
        intent_path = (
            self.session.root / "generation-calls" / request_hash[7:] / "intent.json"
        )
        raw_intent = _receipt_bytes(
            {
                "schemaVersion": "issue-144-generation-call-intent/v1",
                "evidenceLevel": "synthetic_injected",
                "service": binding["service"],
            }
        )
        existing_intent = intent_path.exists() or intent_path.is_symlink()
        if existing_intent or not publish:
            _fact(
                _operator_bytes(intent_path) == raw_intent,
                "retained generation call intent differs",
            )
            self.cache_replay(service, binding)
        if publish:
            self.current()
            publish_immutable_output(self.input_path, raw_binding)
        else:
            _fact(
                _operator_bytes(self.input_path) == raw_binding,
                "retained generation inputs differ",
            )
        if not publish:
            stored = load_operator_json(self.receipt_path)
            _fact(
                stored["status"] == "finalized", "retained generation is not finalized"
            )
            for name in INPUT_NAMES:
                _fact(
                    _file_hash(self.revision / name) == stored["artifactHashes"][name],
                    "finalized build input changed",
                )
            _fact(
                self.cache_snapshot(service, load_operator_json(self.handoff_path))
                == stored["cacheInputs"],
                "retained complete cache metadata/payload changed",
            )

        def before_process() -> None:
            # Reserve the shared service request only after local validation,
            # immediately before the call that can synthesize. Decision-file
            # byte differences must never authorize another uncertain request.
            if publish:
                self.current()
                publish_immutable_output(intent_path, raw_intent)
            else:
                _fact(
                    _operator_bytes(intent_path) == raw_intent,
                    "retained generation call intent differs",
                )

        handoff = replace_row_narration(
            self.prior,
            self.revision / "script-document.json",
            service,
            proof_root=self.session.root,
            before_process=before_process,
        )
        raw_handoff = _receipt_bytes(handoff)
        if publish:
            self.current()
            publish_immutable_output(self.handoff_path, raw_handoff)
        else:
            _fact(
                _operator_bytes(self.handoff_path) == raw_handoff,
                "retained whole-row handoff differs",
            )
        # The host just recomputed the actual service/cache handoff. The child
        # only serializes/compiles it; a saved JSON claim is never substituted.
        cache_inputs = self.cache_snapshot(service, handoff)
        semantic = self.session._semantic(
            "finalize-omission",
            [
                self.revision / "script-document.json",
                self.prior.root / "compiler-dependencies.json",
                self.handoff_path,
            ],
        )
        _fact(semantic["ok"], "actual omission finalizer refused")
        manifest_raw = semantic["artifacts"]["timeline-manifest.json"].encode("utf-8")
        report_raw = semantic["artifacts"]["build-report.json"].encode("utf-8")
        plan = self.materialization(_parse(manifest_raw), handoff)
        artifacts = {
            "script-document.json": _operator_bytes(
                self.revision / "script-document.json"
            ),
            "compiler-dependencies.json": semantic["artifacts"][
                "compiler-dependencies.json"
            ].encode("utf-8"),
            "proof-request.json": _receipt_bytes(self.prior.request),
            "materialization-plan.json": _receipt_bytes(plan),
        }
        previews = {
            "timeline-manifest.json": manifest_raw,
            "build-report.json": report_raw,
        }
        for target, content in [
            (self.revision / name, raw) for name, raw in artifacts.items()
        ] + [
            (self.directory / "preview" / name, raw) for name, raw in previews.items()
        ]:
            if publish:
                publish_immutable_output(target, content)
            else:
                _fact(
                    _operator_bytes(target) == content,
                    "finalized canonical build/preview differs",
                )
        build = PreparedBuild(self.revision, node_executable=self.session.build.node)
        build._verify_speech()
        build._verify_media()
        _fact(
            _operator_bytes(self.input_path) == raw_binding
            and _operator_bytes(self.handoff_path) == raw_handoff
            and _operator_bytes(intent_path) == raw_intent,
            "generation inputs/handoff changed during finalization",
        )
        expected = {
            "schemaVersion": "issue-144-omission-generation/v1",
            "status": "finalized",
            "evidenceLevel": "synthetic_injected",
            "decisionKey": self.key,
            "generationInputHash": _digest(raw_binding),
            "callIntentHash": _digest(raw_intent),
            "handoffHash": _digest(raw_handoff),
            "cacheInputs": cache_inputs,
            "artifactHashes": {name: _digest(raw) for name, raw in artifacts.items()},
            "previewHashes": {name: _digest(raw) for name, raw in previews.items()},
            "semanticReceipt": semantic,
            "snapshotId": build.snapshot_id,
        }
        self.proof.current()
        _fact(
            self.cache_snapshot(service, handoff) == cache_inputs,
            "cache changed during finalization",
        )
        if publish:
            self.current()
            publish_immutable_output(self.receipt_path, _receipt_bytes(expected))
        else:
            _fact(
                load_operator_json(self.receipt_path) == expected,
                "retained generation receipt differs",
            )
        return expected, build

    def generate(self) -> JsonObject:
        if _file_hash(self.session.pointer) != self.decision["baselinePointerHash"]:
            _fact(
                self.receipt_path.exists(),
                "stale generation cannot create missing evidence",
            )
            return self.retained()[0]
        self.fresh("generate-omission")
        if self.receipt_path.exists():
            return self.retained()[0]
        return self.finalize(publish=True)[0]

    def retained(self) -> tuple[JsonObject, PreparedBuild]:
        _fact(
            self.receipt_path.exists(),
            "explicit whole-row generation must finish before rebuild",
        )
        return self.finalize(publish=False)

    @staticmethod
    def verify_preview(build: PreparedBuild, directory: Path) -> None:
        build._verify_compiler_files()
        for path, name in (
            (build.manifest_path, "timeline-manifest.json"),
            (build.report_path, "build-report.json"),
        ):
            _fact(
                _operator_bytes(path) == _operator_bytes(directory / "preview" / name),
                "durable compiler differs from verified preview",
            )
