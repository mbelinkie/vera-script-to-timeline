"""#192 authenticated inference and fresh-target composition, no connection discovery.

The existing #190/#191 ports own effects and speech truth. This consumer never
unlocks their production refusals or turns local/fake evidence into qualification.
"""

from __future__ import annotations

import copy
import fcntl
import hashlib
import os
import shutil
import subprocess
import uuid
import wave
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from vera_timeline_agent.narration.models import canonical_json_bytes, identity_hash
from vera_timeline_agent.roundtrip_v2_audio import verify_selected_omission_v2
from vera_timeline_agent.roundtrip_v2_build import (
    R16_INPUTS,
    PreparedProofBuildV2,
    pin_bytes_v2,
)
from vera_timeline_agent.roundtrip_v2_native import NativeProofBoundaryV2
from vera_timeline_agent.roundtrip_v2_records import (
    ROOT,
    JsonObject,
    ReceiptVerifier,
    _file_hash,
    _open_file,
    _parse,
    fact,
    proof_source_hashes_v2,
    publish_immutable_output,
    shape,
)
from vera_timeline_agent.roundtrip_v2_revised_build import PreparedRevisedProofBuildV2
from vera_timeline_agent.v2_package import _compiler_hash

BRIDGE = ROOT / "packages/contracts/src/issue-192-proof-cli.ts"


def digest(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def read_pin(pin: JsonObject) -> JsonObject:
    # The shared strict parser is only a parser; it never authenticates a receipt.
    return _parse(pin_bytes_v2(pin)[1])


class ProofSessionV2:
    def __init__(
        self,
        root: Path,
        *,
        baseline: PreparedProofBuildV2,
        boundary: NativeProofBoundaryV2,
        authenticate: ReceiptVerifier,
        authority: bytes,
    ) -> None:
        self.root = root.absolute()
        self.baseline = baseline
        self.boundary = boundary
        self.authenticate = authenticate
        self.authority = authority
        self.sources = proof_source_hashes_v2()
        fact(
            baseline.sources == self.sources == boundary.code_hashes,
            "baseline/native/current source graphs differ",
        )
        fact(
            boundary.preflight["executionInputs"] == baseline.inputs,
            "native boundary belongs to another baseline",
        )
        for parent in (baseline.root, boundary.root):
            fact(
                not self.root.is_relative_to(parent)
                and not parent.is_relative_to(self.root),
                "session outputs overlap baseline or native evidence",
            )
        self.pins: dict[str, JsonObject] = {}
        self.capture_inputs: dict[str, tuple[JsonObject, JsonObject]] = {}
        self.read_sequence = 0
        self.case_sessions: dict[str, ProofSessionV2] = {}
        self.authenticated_evidence: dict[str, JsonObject] = {}
        self.capture_namespace = uuid.uuid4().hex
        self.staged_inputs: JsonObject | None = None
        for key, pin in baseline.inputs.items():
            pin_bytes_v2(pin)
            self.pins[f"baseline:{key}"] = copy.deepcopy(pin)
        baseline_facts = self._pure("baseline")
        self.document_hash = baseline_facts["documentHash"]
        self.dependencies_hash = baseline_facts["dependenciesHash"]
        self.document_json = baseline_facts["documentJson"].encode("utf-8")
        self.manifest = baseline_facts["manifest"]
        fact(
            self.manifest == boundary.package.manifest,
            "native package differs from actual baseline compiler",
        )
        self.binding_pin = self._remember(
            "binding", boundary.root / "binding.json", identity_hash(boundary.binding)
        )
        self._current()

    def _remember(self, name: str, path: Path, expected_hash: str) -> JsonObject:
        # #190's immutable output writer and pin reader preserve the opened bytes.
        pin = {"path": str(path.absolute()), "sha256": expected_hash}
        pin_bytes_v2(pin)
        self.pins[name] = pin
        return copy.deepcopy(pin)

    def _current(self) -> None:
        fact(proof_source_hashes_v2() == self.sources, "integration source changed")
        for pin in self.pins.values():
            fact(
                _file_hash(Path(pin["path"])) == pin["sha256"], "retained input changed"
            )

    def _pure(
        self,
        mode: str,
        *,
        evidence: JsonObject | list[JsonObject] | None = None,
        prepared_media: list[JsonObject] | None = None,
        handoff: JsonObject | None = None,
        omission_decision_hash: str = "",
        candidate: JsonObject | None = None,
        decision: JsonObject | None = None,
        history: list[str] | None = None,
    ) -> JsonObject:
        self._current()
        request = {
            "document": read_pin(self.pins["baseline:document"]),
            "dependencies": read_pin(self.pins["baseline:dependencies"]),
            "evidence": evidence,
            "mode": mode,
            "preparedMedia": prepared_media or [],
            "handoff": handoff,
            "omissionDecisionHash": omission_decision_hash,
            "candidate": candidate,
            "decision": decision,
            "history": history or [],
        }
        raw = canonical_json_bytes(request)
        path = self.root / "pure" / digest(raw)[7:] / "request.json"
        publish_immutable_output(path, raw)
        pin_bytes_v2({"path": str(path), "sha256": digest(raw)})
        result = subprocess.run(
            [shutil.which("node") or "node", str(BRIDGE), str(path)],
            capture_output=True,
            check=False,
            timeout=120,
        )
        fact(
            result.returncode == 0,
            "pure integration refused: " + result.stderr.decode(),
        )
        output = _parse(result.stdout)
        shape(output, "schemaVersion runtime inputHash result", "pure result")
        fact(
            output["schemaVersion"] == "issue-192-v2-pure-result/v1"
            and output["runtime"] == "v24.19.0"
            and output["inputHash"] == digest(raw),
            "pure subprocess input/runtime binding differs",
        )
        publish_immutable_output(path.with_name("result.json"), result.stdout)
        self._current()
        fact(isinstance(output["result"], dict), "pure object result required")
        return copy.deepcopy(cast(JsonObject, output["result"]))

    @contextmanager
    def _decision_lock(self) -> Iterator[None]:
        # The same no-follow primitive as #190; never follow an output ancestor.
        self.root.mkdir(parents=True, exist_ok=True)
        with os.fdopen(
            _open_file(self.root / "decision.lock", os.O_RDWR | os.O_CREAT, 0o600),
            "r+b",
        ) as stream:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    def capture(self, target: JsonObject, mapping: JsonObject, name: str) -> JsonObject:
        """Consume actual public adjacent read/capture; no supplied observation JSON."""
        self._current()
        receipt = self.boundary.capture(target, mapping, name)
        paths = {
            "rawJson": self.boundary.root / "observations" / f"{name}.json",
            "audioJson": self.boundary.root / "observations" / f"{name}.audio.json",
            "receiptJson": self.boundary.root / "observations" / f"{name}.receipt.json",
        }
        packet: JsonObject = {}
        hashes = {
            "rawJson": receipt["rawHash"],
            "audioJson": receipt["derivedAudioHash"],
            "receiptJson": identity_hash(receipt),
        }
        for key, path in paths.items():
            pin = self._remember(f"{name}:{key}", path, hashes[key])
            packet[key] = pin_bytes_v2(pin)[1].decode("utf-8")
        fact(
            receipt == _parse(packet["receiptJson"].encode())
            and receipt["rawHash"] == digest(packet["rawJson"].encode())
            and receipt["derivedAudioHash"] == digest(packet["audioJson"].encode()),
            "capture raw/derived/receipt correspondence differs",
        )
        self._current()
        self.capture_inputs[receipt["rawHash"]] = (
            copy.deepcopy(target),
            copy.deepcopy(mapping),
        )
        return packet

    def _observations_current(self, evidence: JsonObject | list[JsonObject]) -> None:
        if isinstance(evidence, list):
            fact(0 < len(evidence) <= 3, "isolated composition cases required")
            for case in evidence:
                owner = self.case_sessions.get(identity_hash(case))
                fact(owner is not None, "unregistered isolated case")
                assert owner is not None
                owner._observations_current(case)
            return
        self._current()
        key = identity_hash(evidence)
        pin = self.authenticated_evidence.get(key)
        fact(pin is not None, "case was not authenticated by this session")
        assert pin is not None
        fact(read_pin(pin) == evidence, "authenticated case bytes differ")
        fact(
            evidence["bindingJson"].encode() == pin_bytes_v2(self.binding_pin)[1],
            "authenticated case binding differs",
        )

        current = evidence["current"]
        raw_hash = digest(current["rawJson"].encode())
        fact(raw_hash in self.capture_inputs, "current observation not owned here")
        target, mapping = self.capture_inputs[raw_hash]
        self.read_sequence += 1
        actual = self.boundary.capture(
            target,
            mapping,
            f"integration_current_{self.capture_namespace}_{self.read_sequence}",
        )
        fact(
            actual["rawHash"] == raw_hash
            and actual["derivedAudioHash"] == digest(current["audioJson"].encode()),
            "native facts changed before inference consumption",
        )
        self.authenticate(
            "roundtrip_inference_currentness",
            self.authority,
            {
                "evidence": copy.deepcopy(evidence),
                "actualReceipt": actual,
                "sourcePins": self.sources,
            },
        )
        self._current()

    def compose(
        self,
        cases: list[tuple[ProofSessionV2, JsonObject]],
    ) -> list[JsonObject]:
        """Keep each isolated case's actual currentness owner at composition."""
        fact(0 < len(cases) <= 3, "isolated cases required")
        result: list[JsonObject] = []
        for owner, evidence in cases:
            fact(
                owner.document_hash == self.document_hash
                and owner.dependencies_hash == self.dependencies_hash
                and owner.sources == self.sources,
                "isolated cases do not share the frozen baseline",
            )
            owner._observations_current(evidence)
            self.case_sessions[identity_hash(evidence)] = owner
            result.append(copy.deepcopy(evidence))
        self._pure("infer", evidence=result)
        return result

    def evidence(
        self,
        baseline: JsonObject,
        current: JsonObject,
        *,
        omission_root: Path | None = None,
        profile_pin: JsonObject | None = None,
        row_id: str | None = None,
    ) -> JsonObject:
        """Authenticate all B1 facts, then obtain C only through the #191 verifier."""
        self._current()
        for packet in (baseline, current):
            shape(packet, "rawJson audioJson receiptJson", "observation packet")
            for raw in packet.values():
                fact(
                    any(
                        pin["sha256"] == digest(raw.encode())
                        for pin in self.pins.values()
                    ),
                    "observation not captured by this session",
                )
        binding_raw = pin_bytes_v2(self.binding_pin)[1]
        value: JsonObject = {
            "schemaVersion": "issue-192-v2-inference-evidence/v1",
            "documentHash": self.document_hash,
            "dependenciesHash": self.dependencies_hash,
            "bindingJson": binding_raw.decode(),
            "baseline": copy.deepcopy(baseline),
            "current": copy.deepcopy(current),
            "omission": None,
        }
        before_raw = _parse(baseline["rawJson"].encode())
        self._verify_exact_view(before_raw, self.boundary)
        self.authenticate(
            "roundtrip_inference_observations",
            self.authority,
            {
                "evidence": copy.deepcopy(value),
                "manifest": copy.deepcopy(self.manifest),
                "deliveryView": copy.deepcopy(self.boundary.package.view),
                "sourcePins": self.sources,
                "inputs": self.baseline.inputs,
            },
        )
        if omission_root is not None:
            fact(
                profile_pin is not None and row_id is not None, "C profile/row required"
            )
            assert profile_pin is not None and row_id is not None
            pin_bytes_v2(profile_pin)
            self.pins["omission:profile"] = copy.deepcopy(profile_pin)
            narration = [
                e
                for e in self.manifest["events"]
                if e["kind"] == "narration" and e["provenance"]["blockId"] == row_id
            ]
            fact(len(narration) == 1, "unique primary narration required")
            before, after = (
                _parse(packet["receiptJson"].encode()) for packet in (baseline, current)
            )
            omitted = verify_selected_omission_v2(
                omission_root,
                canonical_document_json=self.document_json,
                expected_document_hash=self.document_hash,
                baseline_hash=before["derivedAudioHash"],
                current_hash=after["derivedAudioHash"],
                profile_hash=profile_pin["sha256"],
                row_id=row_id,
                primary_source_id=narration[0]["provenance"]["sourceId"],
                target=before["target"],
                authenticate=self.authenticate,
            )
            fact(omitted["status"] == "verified", "selected omission evidence refused")
            for relative, expected in omitted["inputHashes"].items():
                path = omission_root / relative
                self.pins[f"omission:{relative}"] = {
                    "path": str(path.absolute()),
                    "sha256": expected,
                }
            value["omission"] = omitted
        else:
            fact(profile_pin is None and row_id is None, "unbound omission parameters")
        self._current()
        self._pure("infer", evidence=value)
        key = identity_hash(value)
        path = self.root / "authenticated-evidence" / f"{key[7:]}.json"
        publish_immutable_output(path, canonical_json_bytes(value))
        self.authenticated_evidence[key] = self._remember(
            f"authenticated-evidence:{key}",
            path,
            key,
        )
        self._observations_current(value)
        return value

    def stage(
        self,
        evidence: JsonObject | list[JsonObject],
        decision: JsonObject,
        *,
        prepared_media: list[JsonObject],
    ) -> JsonObject:
        """Explicit rejection returns before any whole-row generation or rebuild."""
        self._current()
        self._observations_current(evidence)
        inferred = self._pure("infer", evidence=evidence)
        shape(decision, "schemaVersion inferenceHash outcome", "inference decision")
        fact(
            decision["schemaVersion"] == "issue-192-v2-inference-decision/v1"
            and decision["inferenceHash"] == identity_hash(inferred)
            and decision["outcome"] in {"accept", "reject"},
            "stale or unsupported inference decision",
        )
        self.authenticate(
            "roundtrip_inference_decision",
            self.authority,
            {"decision": copy.deepcopy(decision), "inference": inferred},
        )
        decision_raw = canonical_json_bytes(decision)
        publish_immutable_output(self.root / "inference-decision.json", decision_raw)
        self._remember(
            "inference-decision",
            self.root / "inference-decision.json",
            digest(decision_raw),
        )
        if decision["outcome"] == "reject":
            return {
                "outcome": "reject",
                "nativeEffects": 0,
                "providerEffects": 0,
                "document": read_pin(self.pins["baseline:document"]),
                "dependencies": read_pin(self.pins["baseline:dependencies"]),
            }
        stage = self._pure(
            "stage",
            evidence=evidence,
            prepared_media=prepared_media,
            omission_decision_hash=digest(decision_raw),
        )
        if stage["regeneration"] is not None:
            self.staged_inputs = {}
            for key in ("document", "dependencies"):
                path = self.root / f"staged-{key}.json"
                publish_immutable_output(path, canonical_json_bytes(stage[key]))
                self.staged_inputs[key] = self._remember(
                    f"staged:{key}", path, identity_hash(stage[key])
                )
        return stage

    def proposal(
        self,
        evidence: JsonObject | list[JsonObject],
        *,
        prepared_media: list[JsonObject],
        handoff: JsonObject | None,
    ) -> JsonObject:
        self._current()
        self._observations_current(evidence)
        decision_pin = self.pins.get("inference-decision")
        fact(decision_pin is not None, "explicit accepted inference required")
        assert decision_pin is not None
        inferred = self._pure("infer", evidence=evidence)
        decision = read_pin(decision_pin)
        fact(
            decision["outcome"] == "accept"
            and decision["inferenceHash"] == identity_hash(inferred),
            "inference changed or rejected",
        )
        if inferred["omission"] is not None:
            fact(
                handoff is not None,
                "independently verified #191 whole-row handoff required",
            )
            self.authenticate(
                "roundtrip_row_handoff",
                self.authority,
                {
                    "handoff": copy.deepcopy(handoff),
                    "evidence": copy.deepcopy(evidence),
                },
            )
        return self._pure(
            "proposal",
            evidence=evidence,
            prepared_media=prepared_media,
            handoff=handoff,
            omission_decision_hash=decision_pin["sha256"],
        )

    def decide(
        self,
        evidence: JsonObject | list[JsonObject],
        candidate: JsonObject,
        decision: JsonObject,
        history: list[str],
    ) -> JsonObject:
        with self._decision_lock():
            fact(
                not (self.root / "revision-decision.json").exists()
                and not (self.root / "revision-result.json").exists(),
                "revision decision already consumed: "
                "retained read-only result required",
            )
            return self._decide_once(evidence, candidate, decision, history)

    def _decide_once(
        self,
        evidence: JsonObject | list[JsonObject],
        candidate: JsonObject,
        decision: JsonObject,
        history: list[str],
    ) -> JsonObject:
        self._current()
        self._observations_current(evidence)
        self.authenticate(
            "roundtrip_revision_decision",
            self.authority,
            {
                "evidence": evidence,
                "candidate": candidate,
                "decision": decision,
                "history": history,
            },
        )
        # Reserve the decision before computation; a partial attempt cannot be
        # silently retried with a different outcome or caller-supplied history.
        publish_immutable_output(
            self.root / "revision-decision.json", canonical_json_bytes(decision)
        )
        self._remember(
            "revision-decision",
            self.root / "revision-decision.json",
            identity_hash(decision),
        )
        for name, value in (
            ("revision-candidate", candidate),
            ("revision-evidence", {"cases": evidence}),
        ):
            path = self.root / f"{name}.json"
            publish_immutable_output(path, canonical_json_bytes(value))
            self._remember(name, path, identity_hash(value))
        result = self._pure(
            "decide",
            evidence=evidence,
            candidate=candidate,
            decision=decision,
            history=history,
        )
        publish_immutable_output(
            self.root / "revision-result.json", canonical_json_bytes(result)
        )
        self._remember(
            "revision-result", self.root / "revision-result.json", identity_hash(result)
        )
        return result

    def accepted_revision(
        self,
    ) -> tuple[JsonObject, JsonObject, JsonObject | list[JsonObject]]:
        """Reverify the actual inferred candidate and single-use accepted ledger."""
        self._current()
        for name in (
            "revision-result",
            "revision-candidate",
            "revision-evidence",
            "revision-decision",
        ):
            fact(name in self.pins, "complete accepted revision ledger required")
        candidate = read_pin(self.pins["revision-candidate"])
        evidence = read_pin(self.pins["revision-evidence"])["cases"]
        self._observations_current(evidence)
        request = candidate["proposal"]["request"]
        actual = self._pure(
            "proposal",
            evidence=evidence,
            prepared_media=request["preparedMedia"],
            handoff=request["handoff"],
            omission_decision_hash=request["commands"]["omission"]["decisionHash"]
            if request["commands"]["omission"] is not None
            else "",
        )
        result = read_pin(self.pins["revision-result"])
        decision = read_pin(self.pins["revision-decision"])
        fact(
            actual == candidate
            and result["outcome"] == decision["outcome"] == "accept"
            and result["document"] == candidate["proposal"]["document"]
            and result["dependencies"] == candidate["proposal"]["dependencies"]
            and decision["proposalHash"] == candidate["proposal"]["proposalHash"]
            and result["decisionHash"] == _compiler_hash(decision),
            "accepted inference/decision/result changed",
        )
        return result, candidate, cast(JsonObject | list[JsonObject], evidence)

    def prepare_rebuild(
        self,
        candidate: JsonObject,
        revised: PreparedProofBuildV2 | PreparedRevisedProofBuildV2,
    ) -> JsonObject:
        """Use public preparation; never reinterpret real R16 as fake."""
        self._current()
        self._require_accepted_rebuild(revised)
        result_pin = self.pins.get("revision-result")
        fact(result_pin is not None, "accepted revision result required")
        assert result_pin is not None
        result = read_pin(result_pin)
        proposal = candidate["proposal"]
        fact(
            result["outcome"] == "accept"
            and result["document"] == proposal["document"]
            and result["dependencies"] == proposal["dependencies"],
            "rebuild differs from explicit accepted revision",
        )
        fact(
            revised.document == result["document"]
            and revised.dependencies == result["dependencies"]
            and revised.sources == self.sources
            and revised.dependencies["build"]["buildId"]
            != self.baseline.dependencies["build"]["buildId"],
            "fresh revision/build/source pins differ",
        )
        for old in (self.baseline.root, self.boundary.root, self.root):
            fact(
                not revised.root.is_relative_to(old)
                and not old.is_relative_to(revised.root),
                "fresh build overlaps retained inputs/targets",
            )
        self.authenticate(
            "roundtrip_fresh_build",
            self.authority,
            {
                "proposal": proposal,
                "priorInputs": self.baseline.inputs,
                "revisedInputs": revised.inputs,
            },
        )
        package = revised.prepare_package()
        manifest_raw = pin_bytes_v2(
            {
                "path": str(revised.manifest_path),
                "sha256": digest(proposal["manifestJson"].encode()),
            }
        )[1]
        fact(
            manifest_raw.decode() == proposal["manifestJson"],
            "fresh actual compile differs from accepted preview",
        )
        pin_bytes_v2(
            {
                "path": str(revised.report_path),
                "sha256": digest(proposal["reportJson"].encode()),
            }
        )
        self._current()
        publish_immutable_output(
            self.root / "fresh-package.json", canonical_json_bytes(package)
        )
        self._remember(
            "fresh-package", self.root / "fresh-package.json", identity_hash(package)
        )
        return package

    def _require_accepted_rebuild(
        self, revised: PreparedProofBuildV2 | PreparedRevisedProofBuildV2
    ) -> None:
        actual, _, _ = self.accepted_revision()
        result_pin = self.pins.get("revision-result")
        fact(result_pin is not None, "accepted result required for effects")
        assert result_pin is not None
        result = read_pin(result_pin)
        approved_lane = (
            isinstance(revised, PreparedRevisedProofBuildV2)
            and revised.session is self
            and revised.original_files == self.baseline.request["originalFiles"]
        )
        synthetic_lane = (
            self.baseline.request["lane"]
            == revised.request["lane"]
            == "synthetic_local"
            and self.baseline.original != R16_INPUTS
        )
        fact(
            result == actual
            and result["outcome"] == "accept"
            and result["document"] == revised.document
            and result["dependencies"] == revised.dependencies
            and (approved_lane or synthetic_lane),
            "real revised consumer or changed/unaccepted result refused",
        )

    def request_fresh_delivery(
        self,
        revised: PreparedProofBuildV2 | PreparedRevisedProofBuildV2,
        fresh: NativeProofBoundaryV2,
    ) -> JsonObject:
        """Public delivery owns save/reopen and partial-target/read-only recovery."""
        self._current()
        self._require_accepted_rebuild(revised)
        fact(
            not isinstance(revised, PreparedRevisedProofBuildV2)
            or fresh.revised_preflight_hash is not None,
            "revised build requires the revised native consumer",
        )
        package_pin = self.pins.get("fresh-package")
        fact(package_pin is not None, "accepted fresh package required")
        assert package_pin is not None
        package = read_pin(package_pin)
        fact(
            fresh.preflight["executionInputs"] == revised.inputs
            and fresh.attestation_hash == package["attestationHash"]
            and str(fresh.attestation_path) == package["attestationPath"]
            and fresh.code_hashes == self.sources
            and fresh.package.attestation["buildId"]
            != self.boundary.package.attestation["buildId"]
            and fresh.binding["projectName"] != self.boundary.binding["projectName"]
            and fresh.binding["timelineName"] != self.boundary.binding["timelineName"],
            "fresh target request must retain prior edited target",
        )
        self.authenticate(
            "roundtrip_fresh_delivery",
            self.authority,
            {"priorBinding": self.boundary.binding, "freshBinding": fresh.binding},
        )
        result = fresh.deliver()
        self._current()
        return result

    def verify_reopened(
        self,
        fresh: NativeProofBoundaryV2,
        target: JsonObject,
        mapping: JsonObject,
        name: str,
    ) -> JsonObject:
        self._current()
        package_pin = self.pins.get("fresh-package")
        fact(
            package_pin is not None, "this revision's fresh package required for reopen"
        )
        assert package_pin is not None
        package = read_pin(package_pin)
        fact(
            fresh.attestation_hash == package["attestationHash"]
            and str(fresh.attestation_path) == package["attestationPath"],
            "reopened package is not the accepted fresh package",
        )
        receipt = fresh.capture(target, mapping, name)
        raw_pin = {
            "path": str(fresh.root / "observations" / f"{name}.json"),
            "sha256": receipt["rawHash"],
        }
        observed = read_pin(raw_pin)
        records = fresh.recover_delivery()["records"]
        fact(
            records.get("delivery-complete.json", {}).get("target") == target,
            "reopened target lacks owned verified delivery",
        )
        self._verify_exact_view(observed, fresh)
        self.authenticate(
            "roundtrip_reopened_verification",
            self.authority,
            {
                "receipt": receipt,
                "observation": observed,
                "priorBinding": self.boundary.binding,
                "freshBinding": fresh.binding,
            },
        )
        self._current()
        return {
            "schemaVersion": "issue-192-v2-reopened/v1",
            "status": "verified",
            "evidenceLevel": "injected_execution_unqualified",
            "receipt": receipt,
        }

    @staticmethod
    def _verify_exact_view(
        observed: JsonObject,
        fresh: NativeProofBoundaryV2,
    ) -> None:
        expected = {event["id"]: event for event in fresh.package.view["events"]}
        items = observed["items"]
        fact(
            len(items) == len(expected)
            and {i["eventId"] for i in items} == set(expected)
            and observed["timeline"] == fresh.package.manifest["timeline"],
            "reopened complete inventory/extent differs",
        )
        for item in items:
            event = expected[item["eventId"]]
            track = next(
                t for t in fresh.package.view["tracks"] if t["id"] == event["trackId"]
            )
            record, source = event["recordRange"], event["sourceRange"]
            fact(
                item["sourceId"] == event["sourceId"]
                and item["kind"] == track["kind"]
                and item["trackIndex"] == track["index"]
                and item["authoredEvent"] == event["v2Event"]
                and item["recordStart"] == record["startFrame"]
                and item["recordEnd"] == record["startFrame"] + record["durationFrames"]
                and item["sourceStart"] == source["startFrame"]
                and item["sourceEnd"]
                == source["startFrame"] + source["durationFrames"],
                "reopened source/record discrepancy",
            )
            authored = event["v2Event"]
            linked = {
                peer["itemUid"]
                for peer in items
                if peer is not item
                and {authored["kind"], peer["authoredEvent"]["kind"]}
                == {"primary_visual", "source_audio"}
                and authored["provenance"]["blockId"]
                == peer["authoredEvent"]["provenance"]["blockId"]
                and authored["provenance"]["payloadId"]
                == peer["authoredEvent"]["provenance"]["payloadId"]
            }
            fact(set(item["linkedUids"]) == linked, "reopened AV link topology differs")
            if item["kind"] == "audio":
                routes = [
                    r
                    for r in observed["controls"]["routes"]
                    if r["itemUid"] == item["itemUid"]
                ]
                with wave.open(item["sourcePath"], "rb") as stream:
                    channels = stream.getnchannels()
                fact(
                    len(routes) == 1
                    and channels in {1, 2}
                    and routes[0]["controls"]["gainDb"] == (event["gainDb"] or 0)
                    and routes[0]["controls"]["channelMap"]
                    == ("mono-dual" if channels == 1 else "stereo-direct"),
                    "reopened audio gain/channel mapping differs",
                )

    def recover_delivery(self, fresh: NativeProofBoundaryV2) -> JsonObject:
        self._current()
        return fresh.recover_delivery()
