"""#190 local v2 preparation consumer; never grants native execution authority.

Original inputs remain separate from execution receipts and compiler outputs.
The two private profiles are finite consumers, never generic P5 production.
Probe/receipt authentication is an explicitly supplied trusted integration port;
an unavailable verifier refuses rather than assuming acoustic or probe truth.
"""

from __future__ import annotations

import copy
import io
import platform
import shutil
import subprocess
import wave
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    JsonObject,
    ProofBuildError,
    _digest,
    _parse,
)
from vera_timeline_agent.roundtrip_proof import _destination, publish_immutable_output
from vera_timeline_agent.roundtrip_v2_audio import ReceiptVerifier, fact, shape
from vera_timeline_agent.roundtrip_v2_records import (
    ProofNativeError,
    proof_source_hashes_v2,
)
from vera_timeline_agent.roundtrip_v2_records import (
    _file_hash as _secure_file_hash,
)
from vera_timeline_agent.roundtrip_v2_records import (
    _operator_bytes as _secure_bytes,
)
from vera_timeline_agent.v2_package import build_v2_package, verify_v2_package
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import attest_package_v2

BRIDGE = ROOT / "packages/contracts/src/issue-190-compile-cli.ts"
PRIVATE_PROFILES = {
    "issue-148-private-verified-reuse/v1",
    "issue-148-private-png-still-cfr/v1",
}
R16_INPUTS = {
    "document": "sha256:"
    "27b9d5ddfb097f254d44ce0b6428e461f9e948010e95e1a4c817a8c71e76fa71",
    "dependencies": "sha256:"
    "19c4e7f4777afbd756a67dbb558d73bd87a705c38c1d1dc3d2e330436f8876a9",
}
ProbeReader = Callable[[Path, JsonObject], JsonObject]


def _operator_bytes(path: Path, *, limit: int = 8 * 1024 * 1024) -> bytes:
    try:
        return _secure_bytes(path, limit=limit)
    except (OSError, ProofNativeError) as error:
        raise ProofBuildError(str(error)) from error


def _file_hash(path: Path) -> str:
    try:
        return _secure_file_hash(path)
    except (OSError, ProofNativeError) as error:
        raise ProofBuildError(str(error)) from error


def pin_bytes_v2(pin: JsonObject) -> tuple[Path, bytes]:
    shape(pin, "path sha256", "file pin")
    fact(isinstance(pin["path"], str), "explicit file path required")
    path = Path(pin["path"])
    fact(path.is_absolute(), "absolute file locator required")
    raw = _operator_bytes(path)
    fact(_digest(raw) == pin["sha256"], "file bytes differ from frozen pin")
    return path, raw


class PreparedProofBuildV2:
    def __init__(
        self,
        proof_root: Path,
        *,
        authenticate: ReceiptVerifier,
        read_probe: ProbeReader | None = None,
    ) -> None:
        self.root = proof_root.absolute()
        self.request_path = self.root / "proof-request-v2.json"
        self.raw = _operator_bytes(self.request_path)
        self.request = _parse(self.raw)
        shape(
            self.request,
            "schemaVersion lane originalInputs originalFiles executionInputs "
            "sourcePins "
            "media preparations narrationReceipts authority",
            "v2 proof request",
        )
        fact(
            self.request["schemaVersion"] == "issue-189-v2-prepared-build/v1"
            and self.request["lane"] in {"synthetic_local", "r16_private"},
            "explicit supported proof lane required",
        )
        self.authenticate = authenticate
        self.read_probe = read_probe
        self.node = shutil.which("node") or "node"
        self._runtime()
        self.sources = proof_source_hashes_v2()
        fact(self.request["sourcePins"] == self.sources, "source/tool pins differ")
        self.inputs = shape(
            self.request["executionInputs"], "document dependencies", "inputs"
        )
        self.original = shape(
            self.request["originalInputs"], "document dependencies", "original inputs"
        )
        self.document_path, document_raw = pin_bytes_v2(self.inputs["document"])
        self.dependencies_path, dependency_raw = pin_bytes_v2(
            self.inputs["dependencies"]
        )
        self.document, self.dependencies = _parse(document_raw), _parse(dependency_raw)
        original_files = shape(
            self.request["originalFiles"], "document dependencies", "original file pins"
        )
        original_bytes = {
            key: pin_bytes_v2(pin)[1] for key, pin in original_files.items()
        }
        fact(
            {key: _digest(raw) for key, raw in original_bytes.items()} == self.original,
            "retained original bytes differ",
        )
        fact(
            self.document.get("schemaVersion") == "script-document/v2"
            and self.dependencies.get("schemaVersion") == "compiler-dependencies/v2",
            "strict v2 inputs required",
        )
        if self.request["lane"] == "r16_private":
            fact(
                self.original == R16_INPUTS, "accepted R16 original identities required"
            )
            fact(
                document_raw == original_bytes["document"],
                "R16 document substitution requires new Producer approval",
            )
            fact(
                dependency_raw == original_bytes["dependencies"],
                "R16 dependency substitution requires new Producer approval",
            )
        else:
            fact(
                self.original
                == {key: pin["sha256"] for key, pin in self.inputs.items()},
                "synthetic original/execution binding differs",
            )
        fact(
            self.dependencies["compiler"]["sourceHash"]
            == self.sources["packages/contracts/src/compiler-core-v2.ts"],
            "accepted compiler source pin differs",
        )
        self.execution = self.root / "execution" / _digest(self.raw)[7:]
        self.manifest_path = self.execution / "timeline-manifest.json"
        self.report_path = self.execution / "build-report.json"
        self.preflight_path = self.execution / "preflight.json"
        self.package_root = self.execution / "package"
        self.attestation_path = self.execution / "package-attestation.json"
        _, authority = pin_bytes_v2(self.request["authority"])
        authenticate("proof_preparation", authority, copy.deepcopy(self.request))
        self.paths: dict[str, Path] = {}
        self.hashes: dict[Path, str] = {self.request_path: _digest(self.raw)}
        for pin in self.inputs.values():
            self.hashes[Path(pin["path"])] = pin["sha256"]
            fact(
                not Path(pin["path"]).is_relative_to(self.execution),
                "inputs cannot be outputs",
            )
        for pin in original_files.values():
            self.hashes[Path(pin["path"])] = pin["sha256"]
            fact(
                not Path(pin["path"]).is_relative_to(self.execution),
                "original inputs cannot be outputs",
            )
        self.hashes[Path(self.request["authority"]["path"])] = self.request[
            "authority"
        ]["sha256"]
        self._current()

    def _runtime(self) -> None:
        fact(
            platform.python_implementation() == "CPython"
            and platform.python_version() == "3.12.14",
            "locked CPython 3.12.14 required",
        )
        value = subprocess.run(
            [self.node, "--version"], capture_output=True, check=True, timeout=10
        )
        fact(value.stdout.strip() == b"v24.19.0", "locked Node 24.19.0 required")

    def _pin(self, pin: JsonObject, *, json_file: bool = False) -> tuple[Path, bytes]:
        path = Path(pin["path"])
        if json_file:
            path, raw = pin_bytes_v2(pin)
        else:
            shape(pin, "path sha256", "media pin")
            fact(path.is_absolute(), "absolute media path required")
            fact(_file_hash(path) == pin["sha256"], "media byte pin differs")
            raw = b""
        fact(
            not path.is_relative_to(self.execution),
            "evidence input cannot be execution output",
        )
        self.hashes[path] = pin["sha256"]
        return path, raw

    def _current(self) -> None:
        fact(proof_source_hashes_v2() == self.sources, "proof source changed")
        for path, digest in self.hashes.items():
            fact(_file_hash(path) == digest, "input changed during proof preparation")

    def _compile(self) -> JsonObject:
        result = subprocess.run(
            [
                self.node,
                str(BRIDGE),
                str(self.document_path),
                str(self.dependencies_path),
            ],
            capture_output=True,
            check=False,
            timeout=120,
        )
        fact(
            result.returncode in {0, 1} and bool(result.stdout),
            "compiler execution fault",
        )
        value = _parse(result.stdout)
        fact(
            value["schemaVersion"] == "issue-190-v2-compile/v1"
            and value["runtime"] == "v24.19.0"
            and value["inputs"]
            == [self.inputs[key]["sha256"] for key in ("document", "dependencies")],
            "compiler envelope binding differs",
        )
        fact(
            result.returncode == 0
            and value["result"]["ok"] is True
            and value["needs"]["ok"] is True,
            "accepted v2 compiler/media needs refused",
        )
        fact(
            all(
                item["sourceSufficiency"] == "sufficient"
                for item in value["needs"]["requirements"]
            ),
            "insufficient source cannot prepare proof",
        )
        return value

    def _verify_inputs(self, manifest: JsonObject) -> dict[str, Path]:
        media = self.request["media"]
        fact(
            isinstance(media, dict) and bool(media),
            "explicit complete media map required",
        )
        for key, pin in media.items():
            self.paths[key] = self._pin(pin)[0]
        for source in manifest["sources"]:
            fact(
                f"source:{source['id']}" in self.paths,
                "required source mapping missing",
            )
        sources = {s["id"]: s for s in manifest["sources"]}
        rows = {
            b["id"]: b
            for b in self.document["activeDraft"]["blocks"]
            if b["type"] == "narration"
        }
        timing = [
            *self.dependencies["narrationTimingMaps"],
            *self.dependencies.get("narrationBoundaryEvidence", []),
        ]
        fact(
            set(self.request["narrationReceipts"]) == set(rows),
            "complete narration receipts required",
        )
        for row in timing:
            block = rows[row["blockId"]]
            fact(
                row["blockRevision"] == block["version"]
                and row["textHash"] == _digest(block["text"].encode()),
                "stale narration timing",
            )
            audio = row["audio"]
            candidates = [
                s
                for s in sources.values()
                if s.get("narrationAudio", {}).get("audioHash") == row["audioHash"]
            ]
            fact(len(candidates) == 1, "unique narration asset source required")
            path = self.paths[f"source:{candidates[0]['id']}"]
            pcm = _operator_bytes(path, limit=64 * 1024 * 1024)
            fact(_digest(pcm) == row["audioHash"], "narration bytes differ")
            with wave.open(io.BytesIO(pcm), "rb") as stream:
                fact(
                    (
                        stream.getnchannels(),
                        stream.getsampwidth(),
                        stream.getframerate(),
                        stream.getnframes(),
                        stream.getcomptype(),
                    )
                    == (audio["channels"], 3, 48000, audio["durationSamples"], "NONE"),
                    "narration PCM profile/extent differs",
                )
                fact(
                    len(stream.readframes(stream.getnframes() + 1))
                    == audio["durationSamples"] * audio["channels"] * 3,
                    "truncated narration PCM",
                )
            pins = shape(
                self.request["narrationReceipts"][row["blockId"]],
                "timing review receipt",
                "narration receipt pins",
            )
            _, actual_timing = self._pin(pins["timing"], json_file=True)
            _, review = self._pin(pins["review"], json_file=True)
            _, receipt = self._pin(pins["receipt"], json_file=True)
            fact(
                _digest(actual_timing) == row["timingHash"],
                "provider timing bytes differ",
            )
            if row.get("schemaVersion") == "narration-boundary-evidence/v1":
                fact(
                    _digest(review) == row["verification"]["reviewArtifactHash"],
                    "boundary review artifact differs",
                )
            self.authenticate(
                "narration_preparation",
                receipt,
                {
                    "row": copy.deepcopy(row),
                    "timingHash": _digest(actual_timing),
                    "reviewHash": _digest(review),
                    "audioHash": row["audioHash"],
                },
            )

        bindings = {b["requirementKey"]: b for b in self.dependencies["preparedMedia"]}
        fact(
            set(self.request["preparations"]) == set(bindings),
            "complete preparation map required",
        )
        receipts: dict[str, Path] = {}
        for key, pins in self.request["preparations"].items():
            shape(pins, "receipt original delivered audio", "preparation pins")
            path, raw = self._pin(pins["receipt"], json_file=True)
            record = _parse(raw)
            binding = bindings[key]
            fact(
                record.get("recordVersion") == "authoring-media-preparation/v1"
                and record.get("requirementKey") == key
                and record.get("binding") == binding,
                "preparation receipt binding differs",
            )
            version = binding["profile"]["profileVersion"]
            fact(
                version in PRIVATE_PROFILES,
                "only finite accepted private preparation profiles supported",
            )
            fact(
                (
                    version == "issue-148-private-verified-reuse/v1"
                    and binding["mode"] == "verified_reuse"
                )
                or (
                    version == "issue-148-private-png-still-cfr/v1"
                    and binding["mode"] == "derived_cfr"
                    and binding["verification"]["decodedFrameCount"] == 1
                ),
                "private preparation mode/extent differs",
            )
            original, _ = self._pin(pins["original"])
            delivered, _ = self._pin(pins["delivered"])
            fact(
                _file_hash(original) == binding["originalSource"]["contentHash"]
                and _file_hash(delivered) == binding["verification"]["deliveredHash"],
                "original/delivered bytes differ",
            )
            fact(
                self.read_probe is not None,
                "actual probe port unavailable: operator handoff required",
            )
            assert self.read_probe is not None
            for subject, expected_probe in (
                (original, record["sourceProbe"]),
                (delivered, record["deliveredProbe"]),
            ):
                observed = self.read_probe(subject, copy.deepcopy(record["inputs"]))
                fact(
                    observed == expected_probe,
                    "actual decoded probe differs from receipt",
                )
            if record.get("audio") is not None:
                audio = record["audio"]
                fact(pins["audio"] is not None, "source audio PCM pin required")
                pcm_path, _ = self._pin(pins["audio"])
                pcm = _operator_bytes(pcm_path, limit=64 * 1024 * 1024)
                fact(
                    _digest(pcm) == audio["contentHash"],
                    "prepared source PCM bytes differ",
                )
                with wave.open(io.BytesIO(pcm), "rb") as stream:
                    fact(
                        (
                            stream.getnchannels(),
                            stream.getsampwidth(),
                            stream.getframerate(),
                            stream.getnframes(),
                            stream.getcomptype(),
                        )
                        == (
                            audio["channels"],
                            3,
                            48000,
                            audio["decodedSamples"],
                            "NONE",
                        ),
                        "source PCM format/sample count differs",
                    )
                    fact(
                        len(stream.readframes(stream.getnframes() + 1))
                        == audio["channels"] * 3 * audio["decodedSamples"],
                        "truncated source PCM",
                    )
            else:
                fact(pins["audio"] is None, "unbound source audio PCM")
            self.authenticate(
                "private_preparation",
                raw,
                {
                    "originalInputs": self.original,
                    "binding": binding,
                    "sourcePins": self.sources,
                },
            )
            receipts[key] = path
        return receipts

    def preflight(self) -> JsonObject:
        """Local preparation only; persist original byte pins and distinct execution."""
        self._current()
        first, second = self._compile(), self._compile()
        fact(first == second, "compiler outputs/media needs are not deterministic")
        compiled = first["result"]
        manifest = _parse(compiled["manifestJson"].encode())
        receipts = self._verify_inputs(manifest)
        self._current()
        _destination(self.preflight_path)
        publish_immutable_output(self.manifest_path, compiled["manifestJson"].encode())
        publish_immutable_output(self.report_path, compiled["reportJson"].encode())
        # Reuse the owning public verifier for complete materialization/receipt
        # semantics instead of duplicating #177's validation in this consumer.
        build_v2_package(
            self.manifest_path,
            self.report_path,
            self.document_path,
            self.dependencies_path,
            self.package_root,
            media_paths=self.paths,
            preparation_paths=receipts,
        )
        verification = verify_v2_package(self.package_root)
        self._current()
        result: JsonObject = {
            "schemaVersion": "issue-189-v2-preflight/v1",
            "status": "prepared",
            "evidenceLevel": "local_prepared",
            "lane": self.request["lane"],
            "requestHash": _digest(self.raw),
            "originalInputs": self.original,
            "executionInputs": self.inputs,
            "sourceHashes": self.sources,
            "verifiedFiles": {str(p): h for p, h in sorted(self.hashes.items())},
            "manifestHash": _file_hash(self.manifest_path),
            "reportHash": _file_hash(self.report_path),
            "needs": first["needs"],
            "packageVerification": asdict(verification),
            "unchecked": [
                "Studio native/control/save-reopen/render qualification #178",
                "actual edits/acoustic/provider/visual/listening gates #145",
            ],
        }
        publish_immutable_output(self.preflight_path, canonical_json_bytes(result))
        return copy.deepcopy(result)

    def prepare_package(self) -> JsonObject:
        preflight = self.preflight()
        receipts = self._verify_inputs(_parse(_operator_bytes(self.manifest_path)))
        self._current()
        built = build_v2_package(
            self.manifest_path,
            self.report_path,
            self.document_path,
            self.dependencies_path,
            self.package_root,
            media_paths=self.paths,
            preparation_paths=receipts,
        )
        verified = verify_v2_package(self.package_root)
        if not self.attestation_path.exists():
            attest_package_v2(self.package_root, self.attestation_path)
        loaded = load_verified_package_v2(
            self.attestation_path, _file_hash(self.attestation_path)[7:]
        )
        self._current()
        fact(
            loaded.root == self.package_root
            and loaded.manifest == _parse(_operator_bytes(self.manifest_path)),
            "public package differs from actual compiler",
        )
        result: JsonObject = {
            "schemaVersion": "issue-189-v2-proof-package/v1",
            "evidenceLevel": "local_prepared",
            "preflightHash": identity_hash(preflight),
            "requestHash": _digest(self.raw),
            "package": {
                "project_root": str(built.project_root),
                "build_id": built.build_id,
            },
            "verification": asdict(verified),
            "attestationPath": str(self.attestation_path),
            "attestationHash": _file_hash(self.attestation_path),
        }
        publish_immutable_output(
            self.execution / "proof-package.json", canonical_json_bytes(result)
        )
        return result
