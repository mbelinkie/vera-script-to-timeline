"""CN-192-R1 revised preparation: public compiler/package calls, distinct record.

Initial #190 guards remain intact. Native consumption of the new preflight is
separately handed off by #190; nothing here enables native creation or synthesis.
"""

from __future__ import annotations

import copy
import io
import platform
import shutil
import subprocess
import wave
from dataclasses import asdict
from pathlib import Path
from typing import TYPE_CHECKING

from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.roundtrip_v2_build import (
    BRIDGE,
    PRIVATE_PROFILES,
    R16_INPUTS,
    ProbeReader,
    pin_bytes_v2,
)
from vera_timeline_agent.roundtrip_v2_records import (
    JsonObject,
    ReceiptVerifier,
    _digest,
    _file_hash,
    _operator_bytes,
    _parse,
    fact,
    proof_source_hashes_v2,
    publish_immutable_output,
    shape,
)
from vera_timeline_agent.v2_package import build_v2_package, verify_v2_package
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import attest_package_v2

if TYPE_CHECKING:
    from vera_timeline_agent.roundtrip_v2_proof import ProofSessionV2


PREFLIGHT_KEYS = (
    "schemaVersion status evidenceLevel lane requestHash originalInputs executionInputs "
    "sourceHashes verifiedFiles manifestHash reportHash needs packageVerification unchecked revisionBinding"
)


def verify_revised_preflight_v2(
    preflight: JsonObject, *, authenticate: ReceiptVerifier, authority: bytes,
) -> None:
    """Public native consumer guard for the distinct reviewed revision version."""
    shape(preflight, PREFLIGHT_KEYS, "revised preflight")
    fact(
        preflight["schemaVersion"] == "issue-192-v2-revised-preflight/v1"
        and preflight["status"] == "prepared" and preflight["evidenceLevel"] == "local_prepared"
        and preflight["sourceHashes"] == proof_source_hashes_v2(),
        "current local revised preflight required",
    )
    revision = shape(preflight["revisionBinding"],
                     "lane originalFiles baselineInputs evidence candidate result decision",
                     "revised input/decision binding")
    originals = shape(revision["originalFiles"], "document dependencies", "original file pins")
    original_hashes = {key: _digest(pin_bytes_v2(pin)[1]) for key, pin in originals.items()}
    fact(original_hashes == preflight["originalInputs"], "original document AND dependencies changed")
    lane = revision["lane"]
    fact(lane == preflight["lane"] and lane in {"r16_private_revision", "synthetic_revision"}, "revised lane differs")
    fact((lane == "r16_private_revision") == (original_hashes == R16_INPUTS), "real R16 cannot be relabeled synthetic")
    baseline = shape(revision["baselineInputs"], "document dependencies", "baseline pins")
    for key, pin in baseline.items():
        raw = pin_bytes_v2(pin)[1]
        if lane == "r16_private_revision":
            fact(raw == pin_bytes_v2(originals[key])[1], "initial R16 baseline substitution")
    records = {key: _parse(pin_bytes_v2(revision[key])[1])
               for key in ("evidence", "candidate", "result", "decision")}
    execution = shape(preflight["executionInputs"], "document dependencies", "revised execution pins")
    saved = {key: _parse(pin_bytes_v2(pin)[1]) for key, pin in execution.items()}
    required = [*originals.values(), *baseline.values(), *execution.values(),
                *(revision[key] for key in ("evidence", "candidate", "result", "decision"))]
    fact(all(preflight["verifiedFiles"].get(pin["path"]) == pin["sha256"] for pin in required),
         "revised verified-file inventory omits a required original/decision/input")
    candidate, result, decision = (records[key] for key in ("candidate", "result", "decision"))
    fact(
        result["outcome"] == decision["outcome"] == "accept"
        and decision["proposalHash"] == candidate["proposal"]["proposalHash"]
        and result["decisionHash"] == identity_hash(decision)
        and saved["document"] == result["document"] == candidate["proposal"]["document"]
        and saved["dependencies"] == result["dependencies"] == candidate["proposal"]["dependencies"],
        "revised execution is not the exact accepted result",
    )
    for path, expected in preflight["verifiedFiles"].items():
        fact(_file_hash(Path(path)) == expected, "revised input/media/currentness pin differs")
    authenticate("revised_preflight", authority, copy.deepcopy(preflight))


class PreparedRevisedProofBuildV2:
    def __init__(
        self, root: Path, *, request_pin: JsonObject, session: ProofSessionV2,
        authenticate: ReceiptVerifier, read_probe: ProbeReader,
    ) -> None:
        self.root = root.absolute()
        path, self.raw = pin_bytes_v2(request_pin)
        fact(path == self.root / "revised-build-v2.json", "owned revised request path required")
        self.request = _parse(self.raw)
        shape(self.request, "schemaVersion lane originalFiles executionInputs sourcePins media preparations narrationReceipts authority",
              "revised request")
        fact(self.request["schemaVersion"] == "issue-192-v2-revised-build/v1", "explicit revised consumer required")
        self.session = session
        fact(callable(authenticate) and callable(read_probe), "trusted revised authority/probe ports required")
        self.authenticate, self.read_probe = authenticate, read_probe
        self.sources = proof_source_hashes_v2()
        fact(self.request["sourcePins"] == session.sources == self.sources, "revised source/config graph differs")
        self.result, self.candidate, _ = session.accepted_revision()
        self.original_files = shape(self.request["originalFiles"], "document dependencies", "original pins")
        fact(self.original_files == session.baseline.request["originalFiles"], "retained original file identities differ")
        self.original = {key: _digest(pin_bytes_v2(pin)[1]) for key, pin in self.original_files.items()}
        expected_lane = "r16_private_revision" if session.baseline.request["lane"] == "r16_private" else "synthetic_revision"
        fact(self.request["lane"] == expected_lane and (expected_lane == "r16_private_revision") == (self.original == R16_INPUTS),
             "initial/revised real identity cannot be relabeled")
        self.inputs = shape(self.request["executionInputs"], "document dependencies", "execution pins")
        saved = {key: pin_bytes_v2(pin) for key, pin in self.inputs.items()}
        self.document_path, document_raw = saved["document"]
        self.dependencies_path, dependency_raw = saved["dependencies"]
        self.document, self.dependencies = _parse(document_raw), _parse(dependency_raw)
        fact(self.document == self.result["document"] and self.dependencies == self.result["dependencies"],
             "wrong or stale revised execution snapshot")
        self.execution = self.root / "execution" / _digest(self.raw)[7:]
        self.manifest_path = self.execution / "timeline-manifest.json"
        self.report_path = self.execution / "build-report.json"
        self.preflight_path = self.execution / "preflight.json"
        self.package_root = self.execution / "package"
        self.attestation_path = self.execution / "package-attestation.json"
        for old in (session.root, session.baseline.root, session.boundary.root):
            fact(not self.root.is_relative_to(old) and not old.is_relative_to(self.root), "revised outputs overlap retained evidence")
        self.hashes = {str(path): request_pin["sha256"]}
        for pin in [*self.original_files.values(), *self.inputs.values(), *session.pins.values()]:
            self.hashes[pin["path"]] = pin["sha256"]
            fact(not Path(pin["path"]).is_relative_to(self.execution), "input/output overlap")
        _, self.authority = pin_bytes_v2(self.request["authority"])
        self.hashes[self.request["authority"]["path"]] = self.request["authority"]["sha256"]
        authenticate("revised_preparation", self.authority, {"request": self.request, "candidate": self.candidate,
                                                             "result": self.result, "sourcePins": self.sources})
        fact(platform.python_implementation() == "CPython" and platform.python_version() == "3.12.14",
             "locked CPython 3.12.14 required")
        self.current()

    def current(self) -> None:
        fact(proof_source_hashes_v2() == self.sources, "revised preparation source changed")
        for path, expected in self.hashes.items():
            fact(_file_hash(Path(path)) == expected, "revised frozen input changed")

    def _pin(self, pin: JsonObject, *, record: bool = False) -> tuple[Path, bytes]:
        shape(pin, "path sha256", "revised media/receipt pin")
        path = Path(pin["path"])
        fact(path.is_absolute() and not path.is_relative_to(self.execution), "independent absolute input required")
        raw = pin_bytes_v2(pin)[1] if record else b""
        fact(_file_hash(path) == pin["sha256"], "media/receipt byte identity differs")
        self.hashes[str(path)] = pin["sha256"]
        return path, raw

    def _wav(self, path: Path, expected_hash: str, channels: int, samples: int) -> None:
        raw = _operator_bytes(path, limit=64 * 1024 * 1024)
        fact(_digest(raw) == expected_hash, "revised PCM bytes differ")
        with wave.open(io.BytesIO(raw), "rb") as stream:
            fact((stream.getnchannels(), stream.getsampwidth(), stream.getframerate(), stream.getnframes(), stream.getcomptype())
                 == (channels, 3, 48000, samples, "NONE"), "revised complete PCM profile differs")
            fact(len(stream.readframes(samples + 1)) == samples * channels * 3, "truncated revised PCM")

    def _inputs(self, manifest: JsonObject) -> tuple[dict[str, Path], dict[str, Path]]:
        media = {key: self._pin(pin)[0] for key, pin in self.request["media"].items()}
        timings = [*self.dependencies["narrationTimingMaps"], *self.dependencies.get("narrationBoundaryEvidence", [])]
        fact(set(self.request["narrationReceipts"]) == {r["blockId"] for r in timings}, "complete revised narration receipts required")
        for row in timings:
            source = [s for s in manifest["sources"] if s.get("narrationAudio", {}).get("narrationAssetId") == row["narrationAssetId"]]
            fact(len(source) == 1, "unique revised narration source required")
            self._wav(media[f"source:{source[0]['id']}"], row["audioHash"], row["audio"]["channels"], row["audio"]["durationSamples"])
            pins = shape(self.request["narrationReceipts"][row["blockId"]], "timing review receipt", "revised narration pins")
            values = {key: self._pin(pin, record=True)[1] for key, pin in pins.items()}
            fact(_digest(values["timing"]) == row["timingHash"], "revised provider timing bytes differ")
            if row.get("schemaVersion") == "narration-boundary-evidence/v1":
                fact(_digest(values["review"]) == row["verification"]["reviewArtifactHash"], "revised boundary review bytes differ")
            self.authenticate("narration_preparation", values["receipt"], {"row": row, "timingHash": _digest(values["timing"]),
                                                                          "reviewHash": _digest(values["review"]), "audioHash": row["audioHash"]})
        bindings = {b["requirementKey"]: b for b in self.dependencies["preparedMedia"]}
        fact(set(bindings) == set(self.request["preparations"]), "complete revised preparation receipts required")
        receipts = {}
        for key, pins in self.request["preparations"].items():
            shape(pins, "receipt original delivered audio", "revised preparation pins")
            path, raw = self._pin(pins["receipt"], record=True)
            record, binding = _parse(raw), bindings[key]
            fact(record.get("recordVersion") == "authoring-media-preparation/v1" and record.get("binding") == binding
                 and record.get("requirementKey") == key and binding["profile"]["profileVersion"] in PRIVATE_PROFILES,
                 "revised preparation/profile binding differs")
            version = binding["profile"]["profileVersion"]
            fact((version == "issue-148-private-verified-reuse/v1" and binding["mode"] == "verified_reuse")
                 or (version == "issue-148-private-png-still-cfr/v1" and binding["mode"] == "derived_cfr"
                     and binding["verification"]["decodedFrameCount"] == 1), "revised private preparation mode/extent differs")
            original, delivered = (self._pin(pins[k])[0] for k in ("original", "delivered"))
            fact(_file_hash(original) == binding["originalSource"]["contentHash"]
                 and _file_hash(delivered) == binding["verification"]["deliveredHash"], "revised source/delivered identity differs")
            for subject, probe in ((original, record["sourceProbe"]), (delivered, record["deliveredProbe"])):
                fact(self.read_probe(subject, copy.deepcopy(record["inputs"])) == probe, "actual revised probe differs")
            if record.get("audio") is not None:
                fact(pins["audio"] is not None, "revised source PCM pin required")
                audio = record["audio"]
                self._wav(self._pin(pins["audio"])[0], audio["contentHash"], audio["channels"], audio["decodedSamples"])
            else:
                fact(pins["audio"] is None, "unbound revised source PCM")
            self.authenticate("private_preparation", raw, {"originalInputs": self.original, "binding": binding, "sourcePins": self.sources})
            receipts[key] = path
        return media, receipts

    def preflight(self) -> JsonObject:
        self.current()
        outputs = []
        for _ in range(2):
            result = subprocess.run([shutil.which("node") or "node", str(BRIDGE), str(self.document_path), str(self.dependencies_path)],
                                    capture_output=True, check=False, timeout=120)
            fact(result.returncode == 0, "revised public compiler/needs refused")
            output = _parse(result.stdout)
            fact(output["runtime"] == "v24.19.0" and output["inputs"] == [self.inputs[k]["sha256"] for k in ("document", "dependencies")]
                 and output["result"]["ok"] and output["needs"]["ok"]
                 and all(r["sourceSufficiency"] == "sufficient" for r in output["needs"]["requirements"]), "revised compiler/input/sufficiency binding differs")
            outputs.append(output)
        fact(outputs[0] == outputs[1], "revised compilation is not deterministic")
        compiled = outputs[0]["result"]
        fact(compiled["manifestJson"] == self.candidate["proposal"]["manifestJson"]
             and compiled["reportJson"] == self.candidate["proposal"]["reportJson"], "revised compilation differs from actual accepted proposal")
        media, receipts = self._inputs(compiled["manifest"])
        publish_immutable_output(self.manifest_path, compiled["manifestJson"].encode())
        publish_immutable_output(self.report_path, compiled["reportJson"].encode())
        build_v2_package(self.manifest_path, self.report_path, self.document_path, self.dependencies_path,
                         self.package_root, media_paths=media, preparation_paths=receipts)
        verified = verify_v2_package(self.package_root)
        self.current()
        revision = {"lane": self.request["lane"], "originalFiles": self.original_files,
                    "baselineInputs": self.session.baseline.inputs,
                    **{key: self.session.pins[f"revision-{key}"]
                       for key in ("evidence", "candidate", "result", "decision")}}
        value = {"schemaVersion": "issue-192-v2-revised-preflight/v1", "status": "prepared", "evidenceLevel": "local_prepared",
                 "lane": self.request["lane"], "requestHash": _digest(self.raw), "originalInputs": self.original,
                 "executionInputs": self.inputs, "sourceHashes": self.sources, "verifiedFiles": self.hashes,
                 "manifestHash": _file_hash(self.manifest_path), "reportHash": _file_hash(self.report_path),
                 "needs": outputs[0]["needs"], "packageVerification": asdict(verified), "revisionBinding": revision,
                 "unchecked": ["actual Studio/native qualification #178", "actual provider/acoustic/visual/listening/Producer gates #145"]}
        verify_revised_preflight_v2(value, authenticate=self.authenticate, authority=self.authority)
        publish_immutable_output(self.preflight_path, canonical_json_bytes(value))
        return copy.deepcopy(value)

    def prepare_package(self) -> JsonObject:
        preflight = self.preflight()
        if not self.attestation_path.exists():
            attest_package_v2(self.package_root, self.attestation_path)
        loaded = load_verified_package_v2(self.attestation_path, _file_hash(self.attestation_path)[7:])
        self.current()
        fact(loaded.manifest == self.candidate["proposal"]["manifest"], "revised public package differs from accepted manifest")
        value = {"schemaVersion": "issue-189-v2-proof-package/v1", "evidenceLevel": "local_prepared",
                 "preflightHash": identity_hash(preflight), "requestHash": _digest(self.raw),
                 "package": {"project_root": str(self.package_root), "build_id": self.dependencies["build"]["buildId"]},
                 "verification": asdict(verify_v2_package(self.package_root)), "attestationPath": str(self.attestation_path),
                 "attestationHash": _file_hash(self.attestation_path)}
        publish_immutable_output(self.execution / "proof-package.json", canonical_json_bytes(value))
        return value
