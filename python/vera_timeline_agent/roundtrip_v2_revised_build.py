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
    ROOT,
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
from vera_timeline_agent.v2_package import (
    _compiler_hash,
    build_v2_package,
    verify_v2_package,
)
from vera_timeline_agent.workflow_v2 import load_verified_package_v2
from vera_timeline_agent.workflow_v2_cli import attest_package_v2

if TYPE_CHECKING:
    from vera_timeline_agent.roundtrip_v2_proof import ProofSessionV2


PREFLIGHT_KEYS = (
    "schemaVersion status evidenceLevel lane requestHash originalInputs "
    "executionInputs sourceHashes verifiedFiles manifestHash reportHash needs "
    "packageVerification unchecked revisionBinding"
)


def _evidence_hashes(cases: list[JsonObject]) -> JsonObject:
    # Acoustic measurements are fractional; the frozen contract hash is integer-only.
    raw = canonical_json_bytes(
        {
            "document": None,
            "dependencies": None,
            "evidence": cases,
            "mode": "evidence_hashes",
            "preparedMedia": [],
            "handoff": None,
            "omissionDecisionHash": "",
            "candidate": None,
            "decision": None,
            "history": [],
        }
    )
    completed = subprocess.run(
        [
            shutil.which("node") or "node",
            str(ROOT / "packages/contracts/src/issue-192-proof-cli.ts"),
            "-",
        ],
        input=raw,
        capture_output=True,
        check=False,
        timeout=120,
    )
    fact(completed.returncode == 0, "exact evidence hash bridge refused")
    output = shape(
        _parse(completed.stdout),
        "schemaVersion runtime inputHash result",
        "evidence hash result",
    )
    fact(
        output["schemaVersion"] == "issue-192-v2-pure-result/v1"
        and output["runtime"] == "v24.19.0"
        and output["inputHash"] == _digest(raw),
        "evidence hash input/runtime differs",
    )
    return shape(
        output["result"],
        "evidenceHash caseEvidenceHashes",
        "compiler evidence identities",
    )


def verify_revised_preflight_v2(
    preflight: JsonObject,
    *,
    authenticate: ReceiptVerifier,
    authority: bytes,
) -> None:
    """Public native consumer guard for the distinct reviewed revision version."""
    shape(preflight, PREFLIGHT_KEYS, "revised preflight")
    fact(
        preflight["schemaVersion"] == "issue-192-v2-revised-preflight/v1"
        and preflight["status"] == "prepared"
        and preflight["evidenceLevel"] == "local_prepared"
        and preflight["sourceHashes"] == proof_source_hashes_v2(),
        "current local revised preflight required",
    )
    revision = shape(
        preflight["revisionBinding"],
        "lane request originalFiles baselineInputs baselineProof baselineNative "
        "stagedInputs evidence candidate result decision authenticatedCases",
        "revised input/decision binding",
    )
    originals = shape(
        revision["originalFiles"], "document dependencies", "original file pins"
    )
    original_hashes = {
        key: _digest(pin_bytes_v2(pin)[1]) for key, pin in originals.items()
    }
    fact(
        original_hashes == preflight["originalInputs"],
        "original document AND dependencies changed",
    )
    lane = revision["lane"]
    fact(
        lane == preflight["lane"]
        and lane in {"r16_private_revision", "synthetic_revision"},
        "revised lane differs",
    )
    fact(
        (lane == "r16_private_revision") == (original_hashes == R16_INPUTS),
        "real R16 cannot be relabeled synthetic",
    )
    baseline = shape(
        revision["baselineInputs"], "document dependencies", "baseline pins"
    )
    for key, pin in baseline.items():
        raw = pin_bytes_v2(pin)[1]
        if lane == "r16_private_revision":
            fact(
                raw == pin_bytes_v2(originals[key])[1],
                "initial R16 baseline substitution",
            )
    records = {
        key: _parse(pin_bytes_v2(revision[key])[1])
        for key in ("evidence", "candidate", "result", "decision")
    }
    execution = shape(
        preflight["executionInputs"], "document dependencies", "revised execution pins"
    )
    saved = {key: _parse(pin_bytes_v2(pin)[1]) for key, pin in execution.items()}
    required = [
        *originals.values(),
        *baseline.values(),
        *execution.values(),
        *(revision[key] for key in ("evidence", "candidate", "result", "decision")),
    ]
    fact(
        all(
            preflight["verifiedFiles"].get(pin["path"]) == pin["sha256"]
            for pin in required
        ),
        "revised verified-file inventory omits a required original/decision/input",
    )
    candidate, result, decision = (
        records[key] for key in ("candidate", "result", "decision")
    )
    evidence_record = shape(records["evidence"], "cases", "isolated evidence wrapper")
    cases = evidence_record["cases"]
    cases = cases if isinstance(cases, list) else [cases]
    fact(0 < len(cases) <= 3, "isolated inference cases required")
    authenticated = revision["authenticatedCases"]
    fact(
        isinstance(authenticated, list) and len(authenticated) == len(cases),
        "complete authenticated case inventory required",
    )
    for case, entry in zip(cases, authenticated, strict=True):
        shape(entry, "evidence binding omissionInputs", "authenticated case pins")
        _, evidence_raw = pin_bytes_v2(entry["evidence"])
        fact(
            _parse(evidence_raw) == case
            and _digest(evidence_raw) == identity_hash(case),
            "authenticated case identity differs",
        )
        fact(
            pin_bytes_v2(entry["binding"])[1] == case["bindingJson"].encode(),
            "authenticated case binding identity differs",
        )
        required.extend((entry["evidence"], entry["binding"]))
        if case["omission"] is None:
            fact(entry["omissionInputs"] == {}, "unexpected omission input pins")
            continue
        hashes = case["omission"]["inputHashes"]
        pins = entry["omissionInputs"]
        mandatory = {
            "profile.json",
            "review.json",
            "baseline.json",
            "current-a.json",
            "current-b.json",
            "baseline-receipt.json",
            "current-a-receipt.json",
            "current-b-receipt.json",
            "lift-receipt.json",
            "pristine.wav",
            "edited.wav",
            "pristine-receipt.json",
            "edited-receipt.json",
            "listening-receipt.json",
        }
        fact(
            isinstance(hashes, dict)
            and isinstance(pins, dict)
            and mandatory <= set(hashes)
            and set(pins) == set(hashes),
            "complete verified #191 omission inputs required",
        )
        profile = _parse(pin_bytes_v2(pins["profile.json"])[1])
        fact(
            pins["profile.json"]["sha256"] == case["omission"]["profileHash"]
            and isinstance(profile.get("sources"), list)
            and bool(profile["sources"])
            and {s["path"] for s in profile["sources"]} <= set(hashes),
            "complete verified #191 source inventory required",
        )
        for name, pin in pins.items():
            pin_bytes_v2(pin)
            fact(pin["sha256"] == hashes[name], "verified omission input pin differs")
            required.append(pin)
    evidence_hashes = _evidence_hashes(cases)
    shape(candidate, "inference proposal", "revision candidate")
    shape(
        decision, "schemaVersion proposalHash historyHash outcome", "accepted decision"
    )
    shape(
        result, "outcome document dependencies decisionHash history", "accepted result"
    )
    proposal = shape(
        candidate["proposal"],
        "schemaVersion baselineDocumentHash baselineDependenciesHash "
        "baselineLiveHeadSequence request document dependencies manifest report "
        "manifestJson reportJson comparison comparisonText proposalHash",
        "revision proposal",
    )
    inference = shape(
        candidate["inference"],
        "schemaVersion documentHash dependenciesHash evidenceHash "
        "caseEvidenceHashes commands omission",
        "composed inference",
    )
    fact(
        proposal["schemaVersion"] == "issue-202-v2-proposal/v1"
        and decision["schemaVersion"] == "issue-202-v2-decision/v1"
        and proposal["proposalHash"]
        == _compiler_hash({k: v for k, v in proposal.items() if k != "proposalHash"})
        and inference["documentHash"]
        == proposal["baselineDocumentHash"]
        == _compiler_hash(_parse(pin_bytes_v2(baseline["document"])[1]))
        and inference["dependenciesHash"]
        == proposal["baselineDependenciesHash"]
        == _compiler_hash(_parse(pin_bytes_v2(baseline["dependencies"])[1]))
        and inference["evidenceHash"] == evidence_hashes["evidenceHash"]
        and inference["caseEvidenceHashes"] == evidence_hashes["caseEvidenceHashes"],
        "proposal/inference/evidence/baseline identity differs",
    )
    fact(
        preflight["manifestHash"] == _digest(proposal["manifestJson"].encode())
        and preflight["reportHash"] == _digest(proposal["reportJson"].encode())
        and _parse(proposal["manifestJson"].encode()) == proposal["manifest"]
        and _parse(proposal["reportJson"].encode()) == proposal["report"],
        "actual revised compiler output identities differ",
    )
    fact(
        all(
            c["documentHash"] == inference["documentHash"]
            and c["dependenciesHash"] == inference["dependenciesHash"]
            for c in cases
        ),
        "isolated evidence baseline differs",
    )
    retained_hashes = set(preflight["verifiedFiles"].values())
    for case in cases:
        shape(
            case,
            "schemaVersion documentHash dependenciesHash bindingJson "
            "baseline current omission",
            "isolated evidence",
        )
        fact(
            _digest(case["bindingJson"].encode()) in retained_hashes,
            "isolated binding pin omitted",
        )
        for packet in (case["baseline"], case["current"]):
            shape(
                packet, "rawJson audioJson receiptJson", "isolated observation packet"
            )
            fact(
                all(
                    _digest(raw.encode()) in retained_hashes for raw in packet.values()
                ),
                "isolated raw/derived/receipt pin omitted",
            )
        if case["omission"] is not None:
            fact(
                case["omission"]["status"] == "verified"
                and all(
                    value in retained_hashes
                    for value in case["omission"]["inputHashes"].values()
                ),
                "C verified speech evidence input pin omitted",
            )
    request = _parse(pin_bytes_v2(revision["request"])[1])
    shape(
        request,
        "schemaVersion lane originalFiles executionInputs sourcePins media "
        "preparations narrationReceipts authority",
        "retained revised request",
    )
    fact(
        _digest(pin_bytes_v2(revision["request"])[1]) == preflight["requestHash"]
        and request["schemaVersion"] == "issue-192-v2-revised-build/v1"
        and request["lane"] == lane
        and request["originalFiles"] == originals
        and request["executionInputs"] == execution
        and request["sourcePins"] == preflight["sourceHashes"],
        "revised request ancestry differs",
    )
    baseline_proof = _parse(pin_bytes_v2(revision["baselineProof"])[1])
    baseline_native = _parse(pin_bytes_v2(revision["baselineNative"])[1])
    shape(
        baseline_proof,
        "schemaVersion evidenceLevel preflightHash requestHash package "
        "verification attestationPath attestationHash",
        "retained baseline proof",
    )
    shape(
        baseline_native,
        "schemaVersion attestationHash proofPackageHash sourceHashes evidenceRoot "
        "projectName timelineName authorityHash",
        "retained baseline native binding",
    )
    fact(
        baseline_proof["schemaVersion"] == "issue-189-v2-proof-package/v1"
        and baseline_native["schemaVersion"] == "issue-189-v2-native-binding/v1"
        and baseline_native["proofPackageHash"] == revision["baselineProof"]["sha256"]
        and baseline_native["sourceHashes"] == preflight["sourceHashes"]
        and baseline_native["attestationHash"] == baseline_proof["attestationHash"],
        "retained baseline package/target lineage differs",
    )
    prior_package = load_verified_package_v2(
        Path(baseline_proof["attestationPath"]), baseline_proof["attestationHash"][7:]
    )
    fact(
        prior_package.attestation["buildId"]
        != saved["dependencies"]["build"]["buildId"]
        and prior_package.manifest["document"]
        == _parse(pin_bytes_v2(baseline["dependencies"])[1])["document"],
        "revised build overwrites or differs from retained baseline",
    )
    for record_key in ("request", "baselineProof", "baselineNative"):
        required.append(revision[record_key])
    for pin in request["media"].values():
        required.append(pin)
    for group in [
        *request["preparations"].values(),
        *request["narrationReceipts"].values(),
    ]:
        required.extend(pin for pin in group.values() if pin is not None)
    required.append(request["authority"])
    if proposal["request"]["handoff"] is not None:
        staged = shape(
            revision["stagedInputs"], "document dependencies", "C staged input pins"
        )
        staged_document, staged_dependencies = (
            _parse(pin_bytes_v2(staged[k])[1]) for k in ("document", "dependencies")
        )
        handoff = proposal["request"]["handoff"]
        fact(
            handoff["request"]["revisedDocumentHash"] == _compiler_hash(staged_document)
            and handoff["priorDependenciesHash"] == _compiler_hash(staged_dependencies)
            and handoff["boundaryEvidence"]
            in saved["dependencies"].get("narrationBoundaryEvidence", []),
            "fresh C handoff is not bound to staged document AND dependencies",
        )
        required.extend(staged.values())
    else:
        fact(revision["stagedInputs"] is None, "unexpected staged speech inputs")
    fact(
        all(
            preflight["verifiedFiles"].get(pin["path"]) == pin["sha256"]
            for pin in required
        ),
        "required original/baseline/evidence/media/speech pin omitted",
    )
    fact(
        result["outcome"] == decision["outcome"] == "accept"
        and decision["proposalHash"] == candidate["proposal"]["proposalHash"]
        and result["decisionHash"] == _compiler_hash(decision)
        and saved["document"] == result["document"] == candidate["proposal"]["document"]
        and saved["dependencies"]
        == result["dependencies"]
        == candidate["proposal"]["dependencies"],
        "revised execution is not the exact accepted result",
    )
    for path, expected in preflight["verifiedFiles"].items():
        fact(
            _file_hash(Path(path)) == expected,
            "revised input/media/currentness pin differs",
        )
    authenticate("revised_preflight", authority, copy.deepcopy(preflight))
    authenticate(
        "revised_proof_lineage",
        authority,
        {
            "preflight": copy.deepcopy(preflight),
            "request": request,
            "baselineProof": baseline_proof,
            "baselineNative": baseline_native,
            "evidence": cases,
            "candidate": candidate,
            "result": result,
            "decision": decision,
        },
    )


class PreparedRevisedProofBuildV2:
    def __init__(
        self,
        root: Path,
        *,
        request_pin: JsonObject,
        session: ProofSessionV2,
        authenticate: ReceiptVerifier,
        read_probe: ProbeReader,
    ) -> None:
        self.root = root.absolute()
        path, self.raw = pin_bytes_v2(request_pin)
        fact(
            path == self.root / "revised-build-v2.json",
            "owned revised request path required",
        )
        self.request = _parse(self.raw)
        shape(
            self.request,
            "schemaVersion lane originalFiles executionInputs sourcePins media "
            "preparations narrationReceipts authority",
            "revised request",
        )
        fact(
            self.request["schemaVersion"] == "issue-192-v2-revised-build/v1",
            "explicit revised consumer required",
        )
        self.session = session
        fact(
            callable(authenticate) and callable(read_probe),
            "trusted revised authority/probe ports required",
        )
        self.authenticate, self.read_probe = authenticate, read_probe
        self.sources = proof_source_hashes_v2()
        fact(
            self.request["sourcePins"] == session.sources == self.sources,
            "revised source/config graph differs",
        )
        self.result, self.candidate, self.evidence = session.accepted_revision()
        self.original_files = shape(
            self.request["originalFiles"], "document dependencies", "original pins"
        )
        fact(
            self.original_files == session.baseline.request["originalFiles"],
            "retained original file identities differ",
        )
        self.original = {
            key: _digest(pin_bytes_v2(pin)[1])
            for key, pin in self.original_files.items()
        }
        expected_lane = (
            "r16_private_revision"
            if session.baseline.request["lane"] == "r16_private"
            else "synthetic_revision"
        )
        fact(
            self.request["lane"] == expected_lane
            and (expected_lane == "r16_private_revision")
            == (self.original == R16_INPUTS),
            "initial/revised real identity cannot be relabeled",
        )
        self.inputs = shape(
            self.request["executionInputs"], "document dependencies", "execution pins"
        )
        saved = {key: pin_bytes_v2(pin) for key, pin in self.inputs.items()}
        self.document_path, document_raw = saved["document"]
        self.dependencies_path, dependency_raw = saved["dependencies"]
        self.document, self.dependencies = _parse(document_raw), _parse(dependency_raw)
        fact(
            self.document == self.result["document"]
            and self.dependencies == self.result["dependencies"],
            "wrong or stale revised execution snapshot",
        )
        self.execution = self.root / "execution" / _digest(self.raw)[7:]
        self.manifest_path = self.execution / "timeline-manifest.json"
        self.report_path = self.execution / "build-report.json"
        self.preflight_path = self.execution / "preflight.json"
        self.package_root = self.execution / "package"
        self.attestation_path = self.execution / "package-attestation.json"
        for old in (session.root, session.baseline.root, session.boundary.root):
            fact(
                not self.root.is_relative_to(old) and not old.is_relative_to(self.root),
                "revised outputs overlap retained evidence",
            )
        self.hashes = {str(path): request_pin["sha256"]}
        for pin in [
            *self.original_files.values(),
            *self.inputs.values(),
            *session.pins.values(),
        ]:
            self.hashes[pin["path"]] = pin["sha256"]
            fact(
                not Path(pin["path"]).is_relative_to(self.execution),
                "input/output overlap",
            )
        for owner in session.case_sessions.values():
            for pin in owner.pins.values():
                self.hashes[pin["path"]] = pin["sha256"]
        self.baseline_proof_pin = {
            "path": str(session.baseline.execution / "proof-package.json"),
            "sha256": _file_hash(session.baseline.execution / "proof-package.json"),
        }
        self.baseline_native_pin = session.binding_pin
        self.authenticated_cases = []
        cases = self.evidence if isinstance(self.evidence, list) else [self.evidence]
        for case in cases:
            owner = session.case_sessions.get(identity_hash(case), session)
            owner._observations_current(case)
            entry = {
                "evidence": owner.authenticated_evidence[identity_hash(case)],
                "binding": owner.binding_pin,
                "omissionInputs": {
                    relative: owner.pins[f"omission:{relative}"]
                    for relative in case["omission"]["inputHashes"]
                }
                if case["omission"] is not None
                else {},
            }
            self.authenticated_cases.append(copy.deepcopy(entry))
        self.hashes[self.baseline_proof_pin["path"]] = self.baseline_proof_pin["sha256"]
        for path, expected in session.boundary.preflight["verifiedFiles"].items():
            self.hashes[path] = expected
        for path in (
            session.baseline.preflight_path,
            session.baseline.manifest_path,
            session.baseline.report_path,
            session.baseline.attestation_path,
        ):
            self.hashes[str(path)] = _file_hash(path)
        _, self.authority = pin_bytes_v2(self.request["authority"])
        self.hashes[self.request["authority"]["path"]] = self.request["authority"][
            "sha256"
        ]
        authenticate(
            "revised_preparation",
            self.authority,
            {
                "request": self.request,
                "candidate": self.candidate,
                "result": self.result,
                "sourcePins": self.sources,
            },
        )
        fact(
            platform.python_implementation() == "CPython"
            and platform.python_version() == "3.12.14",
            "locked CPython 3.12.14 required",
        )
        self.current()

    def current(self) -> None:
        fact(
            proof_source_hashes_v2() == self.sources,
            "revised preparation source changed",
        )
        for path, expected in self.hashes.items():
            fact(_file_hash(Path(path)) == expected, "revised frozen input changed")

    def _pin(self, pin: JsonObject, *, record: bool = False) -> tuple[Path, bytes]:
        shape(pin, "path sha256", "revised media/receipt pin")
        path = Path(pin["path"])
        fact(
            path.is_absolute() and not path.is_relative_to(self.execution),
            "independent absolute input required",
        )
        raw = pin_bytes_v2(pin)[1] if record else b""
        fact(_file_hash(path) == pin["sha256"], "media/receipt byte identity differs")
        self.hashes[str(path)] = pin["sha256"]
        return path, raw

    def _wav(self, path: Path, expected_hash: str, channels: int, samples: int) -> None:
        raw = _operator_bytes(path, limit=64 * 1024 * 1024)
        fact(_digest(raw) == expected_hash, "revised PCM bytes differ")
        with wave.open(io.BytesIO(raw), "rb") as stream:
            fact(
                (
                    stream.getnchannels(),
                    stream.getsampwidth(),
                    stream.getframerate(),
                    stream.getnframes(),
                    stream.getcomptype(),
                )
                == (channels, 3, 48000, samples, "NONE"),
                "revised complete PCM profile differs",
            )
            fact(
                len(stream.readframes(samples + 1)) == samples * channels * 3,
                "truncated revised PCM",
            )

    def _inputs(self, manifest: JsonObject) -> tuple[dict[str, Path], dict[str, Path]]:
        media = {key: self._pin(pin)[0] for key, pin in self.request["media"].items()}
        timings = [
            *self.dependencies["narrationTimingMaps"],
            *self.dependencies.get("narrationBoundaryEvidence", []),
        ]
        fact(
            set(self.request["narrationReceipts"]) == {r["blockId"] for r in timings},
            "complete revised narration receipts required",
        )
        for row in timings:
            source = [
                s
                for s in manifest["sources"]
                if s.get("narrationAudio", {}).get("narrationAssetId")
                == row["narrationAssetId"]
            ]
            fact(len(source) == 1, "unique revised narration source required")
            self._wav(
                media[f"source:{source[0]['id']}"],
                row["audioHash"],
                row["audio"]["channels"],
                row["audio"]["durationSamples"],
            )
            pins = shape(
                self.request["narrationReceipts"][row["blockId"]],
                "timing review receipt",
                "revised narration pins",
            )
            values = {key: self._pin(pin, record=True)[1] for key, pin in pins.items()}
            fact(
                _digest(values["timing"]) == row["timingHash"],
                "revised provider timing bytes differ",
            )
            if row.get("schemaVersion") == "narration-boundary-evidence/v1":
                fact(
                    _digest(values["review"])
                    == row["verification"]["reviewArtifactHash"],
                    "revised boundary review bytes differ",
                )
            self.authenticate(
                "narration_preparation",
                values["receipt"],
                {
                    "row": row,
                    "timingHash": _digest(values["timing"]),
                    "reviewHash": _digest(values["review"]),
                    "audioHash": row["audioHash"],
                },
            )
        bindings = {b["requirementKey"]: b for b in self.dependencies["preparedMedia"]}
        fact(
            set(bindings) == set(self.request["preparations"]),
            "complete revised preparation receipts required",
        )
        receipts = {}
        for key, pins in self.request["preparations"].items():
            shape(pins, "receipt original delivered audio", "revised preparation pins")
            path, raw = self._pin(pins["receipt"], record=True)
            record, binding = _parse(raw), bindings[key]
            fact(
                record.get("recordVersion") == "authoring-media-preparation/v1"
                and record.get("binding") == binding
                and record.get("requirementKey") == key
                and binding["profile"]["profileVersion"] in PRIVATE_PROFILES,
                "revised preparation/profile binding differs",
            )
            version = binding["profile"]["profileVersion"]
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
                "revised private preparation mode/extent differs",
            )
            original, delivered = (
                self._pin(pins[k])[0] for k in ("original", "delivered")
            )
            fact(
                _file_hash(original) == binding["originalSource"]["contentHash"]
                and _file_hash(delivered) == binding["verification"]["deliveredHash"],
                "revised source/delivered identity differs",
            )
            for subject, probe in (
                (original, record["sourceProbe"]),
                (delivered, record["deliveredProbe"]),
            ):
                fact(
                    self.read_probe(subject, copy.deepcopy(record["inputs"])) == probe,
                    "actual revised probe differs",
                )
            if record.get("audio") is not None:
                fact(pins["audio"] is not None, "revised source PCM pin required")
                audio = record["audio"]
                self._wav(
                    self._pin(pins["audio"])[0],
                    audio["contentHash"],
                    audio["channels"],
                    audio["decodedSamples"],
                )
            else:
                fact(pins["audio"] is None, "unbound revised source PCM")
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
        return media, receipts

    def preflight(self) -> JsonObject:
        self.current()
        outputs = []
        for _ in range(2):
            result = subprocess.run(
                [
                    shutil.which("node") or "node",
                    str(BRIDGE),
                    str(self.document_path),
                    str(self.dependencies_path),
                ],
                capture_output=True,
                check=False,
                timeout=120,
            )
            fact(result.returncode == 0, "revised public compiler/needs refused")
            output = _parse(result.stdout)
            fact(
                output["runtime"] == "v24.19.0"
                and output["inputs"]
                == [self.inputs[k]["sha256"] for k in ("document", "dependencies")]
                and output["result"]["ok"]
                and output["needs"]["ok"]
                and all(
                    r["sourceSufficiency"] == "sufficient"
                    for r in output["needs"]["requirements"]
                ),
                "revised compiler/input/sufficiency binding differs",
            )
            outputs.append(output)
        fact(outputs[0] == outputs[1], "revised compilation is not deterministic")
        compiled = outputs[0]["result"]
        fact(
            compiled["manifestJson"] == self.candidate["proposal"]["manifestJson"]
            and compiled["reportJson"] == self.candidate["proposal"]["reportJson"],
            "revised compilation differs from actual accepted proposal",
        )
        media, receipts = self._inputs(compiled["manifest"])
        publish_immutable_output(self.manifest_path, compiled["manifestJson"].encode())
        publish_immutable_output(self.report_path, compiled["reportJson"].encode())
        build_v2_package(
            self.manifest_path,
            self.report_path,
            self.document_path,
            self.dependencies_path,
            self.package_root,
            media_paths=media,
            preparation_paths=receipts,
        )
        verified = verify_v2_package(self.package_root)
        self.current()
        revision = {
            "lane": self.request["lane"],
            "originalFiles": self.original_files,
            "request": {
                "path": str(self.root / "revised-build-v2.json"),
                "sha256": _digest(self.raw),
            },
            "baselineInputs": self.session.baseline.inputs,
            "baselineProof": self.baseline_proof_pin,
            "baselineNative": self.baseline_native_pin,
            "stagedInputs": self.session.staged_inputs,
            "authenticatedCases": self.authenticated_cases,
            **{
                key: self.session.pins[f"revision-{key}"]
                for key in ("evidence", "candidate", "result", "decision")
            },
        }
        value = {
            "schemaVersion": "issue-192-v2-revised-preflight/v1",
            "status": "prepared",
            "evidenceLevel": "local_prepared",
            "lane": self.request["lane"],
            "requestHash": _digest(self.raw),
            "originalInputs": self.original,
            "executionInputs": self.inputs,
            "sourceHashes": self.sources,
            "verifiedFiles": self.hashes,
            "manifestHash": _file_hash(self.manifest_path),
            "reportHash": _file_hash(self.report_path),
            "needs": outputs[0]["needs"],
            "packageVerification": asdict(verified),
            "revisionBinding": revision,
            "unchecked": [
                "actual Studio/native qualification #178",
                "actual provider/acoustic/visual/listening/Producer gates #145",
            ],
        }
        verify_revised_preflight_v2(
            value, authenticate=self.authenticate, authority=self.authority
        )
        publish_immutable_output(self.preflight_path, canonical_json_bytes(value))
        return copy.deepcopy(value)

    def prepare_package(self) -> JsonObject:
        preflight = self.preflight()
        if not self.attestation_path.exists():
            attest_package_v2(self.package_root, self.attestation_path)
        loaded = load_verified_package_v2(
            self.attestation_path, _file_hash(self.attestation_path)[7:]
        )
        self.current()
        fact(
            loaded.manifest == self.candidate["proposal"]["manifest"],
            "revised public package differs from accepted manifest",
        )
        value = {
            "schemaVersion": "issue-192-v2-revised-proof-package/v1",
            "evidenceLevel": "local_prepared",
            "preflightHash": identity_hash(preflight),
            "requestHash": _digest(self.raw),
            "preflightPath": str(self.preflight_path),
            "preflightRawHash": _file_hash(self.preflight_path),
            "package": {
                "project_root": str(self.package_root),
                "build_id": self.dependencies["build"]["buildId"],
            },
            "verification": asdict(verify_v2_package(self.package_root)),
            "attestationPath": str(self.attestation_path),
            "attestationHash": _file_hash(self.attestation_path),
        }
        publish_immutable_output(
            self.execution / "proof-package.json", canonical_json_bytes(value)
        )
        return value
