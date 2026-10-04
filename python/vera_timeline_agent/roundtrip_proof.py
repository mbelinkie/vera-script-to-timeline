"""Issue144 local visual proof workflow; native boundaries must be supplied.

The executable entry defaults to local stages and file-staged capture requests.
It does not connect to Resolve. Spoken omission and real WI qualification remain
separate required seams before the complete three-edit proof is accepted.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import re
import stat
import subprocess
import uuid
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vera_timeline_agent.build_jobs import (
    NeedsAction,
)
from vera_timeline_agent.build_jobs import (
    publish_immutable_output as _publish_accepted,
)
from vera_timeline_agent.roundtrip_build import (
    ROOT,
    PreparedBuild,
    ProofBuildError,
    _digest,
    _file_hash,
    _operator_bytes,
    _parse,
    _receipt_bytes,
    load_operator_json,
)
from vera_timeline_agent.roundtrip_native import NativeStages

JsonObject = dict[str, Any]
NativeProvider = Callable[[PreparedBuild], NativeStages]
Capture = Callable[[JsonObject], JsonObject]
ENTRY = ROOT / "packages/contracts/src/issue-144-proof-cli.ts"
SEMANTIC_SOURCES = (
    "./issue-144-proof-cli.ts",
    "./issue-144-semantics.ts",
    "./issue-144-text-revision.ts",
    "./issue-144-omission-build.ts",
    "./compiler-core.ts",
    "./script-validator.ts",
    "../../../contracts/script-document-v1.schema.json",
    "../../../contracts/compiler-dependencies-v1.schema.json",
    "../../../contracts/timeline-manifest-v1.schema.json",
    "../../../contracts/build-report-v1.schema.json",
)


class ProofProcessFault(ProofBuildError):
    """The semantic child process failed without evaluating a valid result."""


def _destination(path: Path) -> None:
    for component in (path.absolute(), *path.absolute().parents):
        if component.is_symlink():
            raise ProofBuildError(f"symbolic link is unsupported: {path}")
    if path.exists():
        _operator_bytes(path)
    path.parent.mkdir(parents=True, exist_ok=True)


def publish_immutable_output(path: Path, content: bytes) -> None:
    _destination(path)
    _publish_accepted(path, content)
    if _file_hash(path) != _digest(content):
        raise ProofBuildError("published proof artifact differs")


def _exclusive(path: Path, raw: bytes) -> None:
    _destination(path)
    descriptor = os.open(
        path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


def _replace_pointer(path: Path, value: JsonObject) -> None:
    if path.exists():
        _operator_bytes(path)
    temporary = path.parent / f".proof-pointer-{uuid.uuid4()}"
    _exclusive(temporary, _receipt_bytes(value))
    os.replace(temporary, path)
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(directory)
    finally:
        os.close(directory)


class ProofSession:
    """One proof directory, immutable evidence and an explicitly injected boundary."""

    def __init__(
        self,
        proof_root: Path,
        *,
        node_executable: str | None = None,
        native_provider: NativeProvider | None = None,
        capture: Capture | None = None,
        omission_evidence: Callable[[JsonObject], Path] | None = None,
    ) -> None:
        self.build = PreparedBuild(proof_root, node_executable=node_executable)
        self.root = self.build.root
        self.native_provider = native_provider
        self.capture = capture
        self.omission_evidence = omission_evidence
        self.pointer = self.root / "baseline.json"

    def run(self, action: str, *, decision_key: str | None = None) -> JsonObject:
        _destination(self.root / "proof.lock")
        descriptor = os.open(
            self.root / "proof.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            details = os.fstat(descriptor)
            if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
                raise ProofBuildError("independent local lock file required")
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise ProofBuildError("another proof operation is active") from error
            self.build._assert_current()
            if action == "build":
                adapter = (
                    self.native_provider(self.build) if self.native_provider else None
                )
                return self.build.run(adapter=adapter)
            if action == "bind-baseline":
                return self._bind()
            if action == "propose":
                return self._propose()
            if action == "decide":
                return self._decide()
            if action in {"bind-omission-evidence", "propose-omission"}:
                from vera_timeline_agent.roundtrip_omission import OmissionProof

                omission = OmissionProof(self)
                return (
                    omission.prepare()
                    if action == "bind-omission-evidence"
                    else omission.propose()
                )
            if action in {"rebuild", "promote"}:
                if decision_key is None or not re.fullmatch(
                    r"[a-f0-9]{64}", decision_key
                ):
                    raise ProofBuildError("explicit valid decision key required")
                return (
                    self._rebuild(decision_key)
                    if action == "rebuild"
                    else self._promote(decision_key)
                )
            if action == "status":
                return {
                    "status": "bound" if self.pointer.exists() else "unbound",
                    "baseline": load_operator_json(self.pointer)
                    if self.pointer.exists()
                    else None,
                    "evidenceLevel": self.build.request["evidenceLevel"],
                }
            raise ProofBuildError("unknown bounded proof action")
        finally:
            os.close(descriptor)

    def _ready(self, build: PreparedBuild) -> JsonObject:
        # Default adapter performs only retained local verification for a complete
        # job. It cannot create/retry a native target if the job is incomplete.
        status = build.run()
        if status["status"] != "complete":
            raise ProofBuildError("native build is not complete and verified")
        build._verify_media()
        build.verified_package()
        for row in status["stages"]:
            if row["name"] not in {"building_resolve_timeline", "verifying_timeline"}:
                continue
            receipt = load_operator_json(Path(row["path"]))
            for key, name in (
                ("resultHash", "native-result.json"),
                ("identityHash", "native-identity.json"),
                ("intentHash", "native-intent.json"),
            ):
                if receipt.get(key) != _file_hash(build.run_root / name):
                    raise ProofBuildError("native result/identity/intent changed")
        return load_operator_json(build.run_root / "native-identity.json")

    def _baseline(self, digest: str | None = None) -> tuple[JsonObject, PreparedBuild]:
        if digest is None:
            pointer = load_operator_json(self.pointer)
            if (
                set(pointer) != {"schemaVersion", "baselineHash"}
                or pointer["schemaVersion"] != "issue-144-baseline-pointer/v1"
            ):
                raise ProofBuildError("invalid baseline pointer")
            digest = pointer["baselineHash"]
        if not isinstance(digest, str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", digest
        ):
            raise ProofBuildError("invalid baseline identity")
        path = self.root / "baselines" / digest[7:] / "baseline.json"
        if _file_hash(path) != digest:
            raise ProofBuildError("baseline artifact changed")
        baseline = load_operator_json(path)
        build_root = (self.root / baseline["relativeBuildRoot"]).absolute()
        if not build_root.is_relative_to(self.root):
            raise ProofBuildError("foreign baseline build root")
        build = PreparedBuild(build_root, node_executable=self.build.node)
        if (
            build.snapshot_id != baseline["snapshotId"]
            or build.source_hashes != baseline["sources"]
        ):
            raise ProofBuildError("baseline inputs or implementation changed")
        if self._ready(build) != baseline["nativeIdentity"]:
            raise ProofBuildError("baseline native identity changed")
        return baseline, build

    def _occurrence_identity(
        self, observation: JsonObject, identity: JsonObject, evidence_level: str
    ) -> None:
        if (
            observation.get("projectUid") != identity["projectUid"]
            or observation.get("timelineUid") != identity["timelineUid"]
            or observation.get("evidenceLevel") != evidence_level
        ):
            raise ProofBuildError("capture target or evidence lane changed")
        items = observation.get("items")
        if not isinstance(items, list) or any(
            not isinstance(row, dict) for row in items
        ):
            raise ProofBuildError("capture occurrence inventory is missing")
        mapped = {
            row.get("eventId"): {
                "itemUid": row.get("itemUid"),
                "mediaUid": row.get("mediaUid"),
            }
            for row in items
        }
        if len(mapped) != len(items) or mapped != identity["occurrences"]:
            raise ProofBuildError(
                "capture occurrence identity differs from verified build"
            )

    def _fresh(
        self, build: PreparedBuild, purpose: str, binding: str
    ) -> tuple[JsonObject, JsonObject]:
        identity = self._ready(build)
        return self._capture_files(
            build,
            purpose,
            binding,
            validate=lambda observation: self._occurrence_identity(
                observation, identity, build.request["evidenceLevel"]
            ),
        )

    def _capture_files(
        self,
        build: PreparedBuild,
        purpose: str,
        binding: str,
        *,
        validate: Callable[[JsonObject], None],
        request_schema: str = "issue-144-capture-request/v1",
        response_schema: str = "issue-144-capture-response/v1",
    ) -> tuple[JsonObject, JsonObject]:
        """Shared reservation only; caller supplies its strict identity gate."""
        identity = self._ready(build)
        basis = {
            "schemaVersion": request_schema,
            "purpose": purpose,
            "binding": binding,
            "snapshotId": build.snapshot_id,
            "evidenceLevel": build.request["evidenceLevel"],
            "manifestPath": str(build.manifest_path),
            "manifestHash": _file_hash(build.manifest_path),
            "identityPath": str(build.run_root / "native-identity.json"),
            "identityHash": _file_hash(build.run_root / "native-identity.json"),
            "expectedIdentity": identity,
            "packageRoot": str(build.package_root),
            "sources": build.source_hashes,
        }
        directory = self.root / "captures" / _digest(_receipt_bytes(basis))[7:]
        _destination(directory / "request.json")
        directory.mkdir(parents=True, exist_ok=True)
        pending = [
            row
            for row in directory.iterdir()
            if row.is_dir()
            and not (row / "consumed.json").exists()
            and not (row / "refused.json").exists()
        ]
        if len(pending) > 1:
            raise ProofBuildError("ambiguous pending capture requests")
        attempt = pending[0] if pending else directory / str(uuid.uuid4())
        request_path = attempt / "request.json"
        if request_path.exists():
            request = load_operator_json(request_path)
            if {
                key: value for key, value in request.items() if key != "nonce"
            } != basis or request.get("nonce") != attempt.name:
                raise ProofBuildError("capture request changed")
        else:
            request = {**basis, "nonce": attempt.name}
            _exclusive(request_path, _receipt_bytes(request))
        response_path = attempt / "response.json"
        if self.capture is not None and not response_path.exists():
            response = self.capture(request)
            publish_immutable_output(response_path, _receipt_bytes(response))
        if not response_path.exists():
            raise NeedsAction(f"fresh guarded WI capture required: {request_path}")
        response = load_operator_json(response_path)
        if (
            set(response)
            != {"schemaVersion", "nonce", "requestHash", "observationA", "observationB"}
            or response["schemaVersion"] != response_schema
            or response["nonce"] != request["nonce"]
            or response["requestHash"] != _file_hash(request_path)
            or response["observationA"] != response["observationB"]
        ):
            publish_immutable_output(
                attempt / "refused.json",
                _receipt_bytes(
                    {
                        "responseHash": _file_hash(response_path),
                        "reason": "wrong request/nonce or unstable captures",
                    }
                ),
            )
            raise ProofBuildError(
                "capture nonce/request differs or adjacent reads changed"
            )
        for observation in (response["observationA"], response["observationB"]):
            validate(observation)
        build._assert_current()
        build._verify_media()
        publish_immutable_output(
            attempt / "consumed.json",
            _receipt_bytes(
                {
                    "requestHash": _file_hash(request_path),
                    "responseHash": _file_hash(response_path),
                }
            ),
        )
        return response["observationA"], response["observationB"]

    def _semantic(self, action: str, paths: list[Path]) -> JsonObject:
        raw = [_operator_bytes(path) for path in paths]
        for content in raw:
            _parse(content)
        self.build._assert_current()
        sources = {name: _file_hash(ENTRY.parent / name) for name in SEMANTIC_SOURCES}
        # Measured64-token single-row case: propose2.8s, decide2.4s. Larger
        # qualifying documents/rows can cost more; keep a bounded five-minute
        # process budget and report timeouts as faults, never semantic refusals.
        process = subprocess.run(
            [self.build.node, str(ENTRY), action, *map(str, paths)],
            capture_output=True,
            timeout=300,
            check=False,
        )
        if process.returncode not in {0, 1}:
            raise ProofProcessFault(
                f"semantic entry process fault: exit{process.returncode}"
            )
        envelope = _parse(process.stdout)
        if (
            envelope.get("schemaVersion") != "issue-144-semantic-cli/v1"
            or envelope.get("evidenceLevel") != "compiler_only"
            or envelope.get("runtime") != "v24.19.0"
            or envelope.get("action") != action
            or envelope.get("inputs")
            != {str(index): _digest(content) for index, content in enumerate(raw)}
            or envelope.get("sourceHashes") != sources
            or envelope.get("lockfileSha256") != _file_hash(ROOT / "package-lock.json")
            or envelope.get("ok") is not (process.returncode == 0)
        ):
            raise ProofBuildError("semantic entry receipt binding differs")
        result_bytes = envelope["resultJson"].encode("utf-8")
        if (
            _digest(result_bytes) != envelope["resultSha256"]
            or _parse(result_bytes) != envelope["result"]
        ):
            raise ProofBuildError("semantic result bytes differ")
        for name, text in envelope["artifacts"].items():
            allowed = (
                {
                    "compiler-dependencies.json",
                    "timeline-manifest.json",
                    "build-report.json",
                }
                if action == "finalize-omission"
                else {"script-document.json", "compiler-dependencies.json"}
            )
            if name not in allowed or _digest(text.encode("utf-8")) != envelope[
                "artifactHashes"
            ].get(name):
                raise ProofBuildError("canonical semantic artifact hash differs")
        if (
            any(
                _file_hash(path) != _digest(content)
                for path, content in zip(paths, raw, strict=True)
            )
            or {name: _file_hash(ENTRY.parent / name) for name in SEMANTIC_SOURCES}
            != sources
        ):
            raise ProofBuildError("semantic input/source changed during evaluation")
        self.build._assert_current()
        return envelope

    def _proof_inputs(
        self, baseline: JsonObject, build: PreparedBuild, a: JsonObject, b: JsonObject
    ) -> JsonObject:
        return {
            "baselineDocument": baseline["document"],
            "currentDocument": build.document,
            "dependencies": build.dependencies,
            "baselineManifest": load_operator_json(build.manifest_path),
            "baselineObservation": baseline["observation"],
            "observationA": a,
            "observationB": b,
        }

    def _publish_baseline(
        self, build: PreparedBuild, a: JsonObject, b: JsonObject
    ) -> str:
        identity = self._ready(build)
        manifest = load_operator_json(build.manifest_path)
        body = {
            "schemaVersion": "issue-144-visual-baseline/v1",
            "evidenceLevel": build.request["evidenceLevel"],
            "relativeBuildRoot": build.root.relative_to(self.root).as_posix(),
            "snapshotId": build.snapshot_id,
            "sources": build.source_hashes,
            "document": build.document,
            "observation": a,
            "nativeIdentity": identity,
        }
        inputs = self._proof_inputs(body, build, a, b)
        temporary = (
            self.root / "baseline-validation" / build.snapshot_id / "inputs.json"
        )
        publish_immutable_output(temporary, _receipt_bytes(inputs))
        checked = self._semantic("propose", [temporary])
        if not checked["ok"] or checked["result"]["rows"]:
            raise ProofBuildError(
                "new baseline does not reproduce the compiled manifest"
            )
        # Proof setup must have linked every ready use_source pair; an unchanged
        # observation alone does not establish that setup was performed.
        by_id = {row["eventId"]: row for row in a["items"]}
        for event in manifest["events"]:
            if (
                event["kind"] != "video"
                or event["provenance"]["authoringKind"] != "visual_event"
            ):
                continue
            group = [
                row
                for row in manifest["events"]
                if row["provenance"]["authoringId"]
                == event["provenance"]["authoringId"]
            ]
            if len(group) == 2:
                pair = [by_id[row["id"]] for row in group]
                if pair[0]["linkedUids"] != [pair[1]["itemUid"]] or pair[1][
                    "linkedUids"
                ] != [pair[0]["itemUid"]]:
                    raise ProofBuildError("isolated proof link setup is unverified")
        raw = _receipt_bytes(body)
        digest = _digest(raw)
        publish_immutable_output(
            self.root / "baselines" / digest[7:] / "baseline.json", raw
        )
        return digest

    def _bind(self) -> JsonObject:
        if self.pointer.exists():
            baseline, _ = self._baseline()
            if baseline["snapshotId"] != self.build.snapshot_id:
                raise ProofBuildError(
                    "baseline already advanced; cannot rebind original"
                )
            return {
                "status": "bound",
                "baselineHash": load_operator_json(self.pointer)["baselineHash"],
            }
        a, b = self._fresh(self.build, "bind-baseline", self.build.snapshot_id)
        digest = self._publish_baseline(self.build, a, b)
        if self.pointer.exists():
            raise ProofBuildError("baseline pointer appeared during verification")
        _replace_pointer(
            self.pointer,
            {"schemaVersion": "issue-144-baseline-pointer/v1", "baselineHash": digest},
        )
        return {"status": "bound", "baselineHash": digest}

    def _propose(self) -> JsonObject:
        baseline, build = self._baseline()
        prior_hash = _file_hash(self.pointer)
        a, b = self._fresh(build, "propose", prior_hash)
        inputs = self._proof_inputs(baseline, build, a, b)
        input_path = (
            self.root
            / "proposal-inputs"
            / _digest(_receipt_bytes(inputs))[7:]
            / "inputs.json"
        )
        publish_immutable_output(input_path, _receipt_bytes(inputs))
        envelope = self._semantic("propose", [input_path])
        if _file_hash(self.pointer) != prior_hash:
            raise ProofBuildError("baseline changed during proposal")
        digest = envelope["resultSha256"]
        report_path = self.root / "reports" / f"{digest[7:]}.json"
        publish_immutable_output(report_path, envelope["resultJson"].encode("utf-8"))
        receipt = {
            "status": "proposed" if envelope["ok"] else "refused",
            "reportHash": digest,
            "reportPath": str(report_path),
            "inputPath": str(input_path),
            "baselinePointerHash": prior_hash,
            "semanticReceipt": envelope,
        }
        publish_immutable_output(
            report_path.with_suffix(".receipt.json"), _receipt_bytes(receipt)
        )
        return receipt

    def _decide(self) -> JsonObject:
        decision_path = self.root / "decisions.json"
        raw = _operator_bytes(decision_path)
        decisions = _parse(raw)
        key = _digest(raw)[7:]
        directory = self.root / "decisions" / key
        receipt_path = directory / "receipt.json"
        if receipt_path.exists():
            # Identical completed replay returns retained evidence even after
            # promotion; it creates no row/revision and advances no baseline.
            return self._retained_decision(key)
        report_hash = decisions.get("reportHash")
        if not isinstance(report_hash, str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", report_hash
        ):
            raise ProofBuildError("explicit valid report hash required")
        report_path = self.root / "reports" / f"{report_hash[7:]}.json"
        if _file_hash(report_path) != report_hash:
            raise ProofBuildError("proposal report changed")
        proposal = load_operator_json(report_path.with_suffix(".receipt.json"))
        prior_hash = _file_hash(self.pointer)
        if prior_hash != proposal["baselinePointerHash"]:
            raise ProofBuildError("stale decision baseline")
        baseline, build = self._baseline()
        a, b = self._fresh(build, "decide", _digest(raw))
        input_path = directory / "inputs.json"
        publish_immutable_output(
            input_path, _receipt_bytes(self._proof_inputs(baseline, build, a, b))
        )
        envelope = self._semantic("decide", [input_path, report_path, decision_path])
        if not envelope["ok"]:
            raise ProofBuildError(f"decision refused: {envelope['result']}")
        result = envelope["result"]
        revision_root = directory / "build"
        if result["status"] == "revised":
            if set(envelope["artifacts"]) != {
                "script-document.json",
                "compiler-dependencies.json",
            }:
                raise ProofBuildError("canonical revision artifacts are missing")
            for name, text in envelope["artifacts"].items():
                publish_immutable_output(revision_root / name, text.encode("utf-8"))
            publish_immutable_output(
                revision_root / "proof-request.json", _receipt_bytes(build.request)
            )
            publish_immutable_output(
                revision_root / "materialization-plan.json", _receipt_bytes(build.plan)
            )
        if _file_hash(self.pointer) != prior_hash or _file_hash(
            decision_path
        ) != _digest(raw):
            raise ProofBuildError("baseline or decision changed during application")
        receipt = {
            "status": result["status"],
            "evidenceLevel": build.request["evidenceLevel"],
            "decisionKey": key,
            "decisionHash": _digest(raw),
            "reportHash": report_hash,
            "baselinePointerHash": prior_hash,
            "baselineHash": load_operator_json(self.pointer)["baselineHash"],
            "priorIdentity": baseline["nativeIdentity"],
            "revisionRoot": str(revision_root),
            "semanticReceipt": envelope,
        }
        publish_immutable_output(directory / "operator-decisions.json", raw)
        publish_immutable_output(receipt_path, _receipt_bytes(receipt))
        return receipt

    def _retained_decision(self, key: str) -> JsonObject:
        directory = self.root / "decisions" / key
        raw_path = directory / "operator-decisions.json"
        raw = _operator_bytes(raw_path)
        if _digest(raw)[7:] != key:
            raise ProofBuildError("retained decision key differs")
        decisions = _parse(raw)
        receipt = load_operator_json(directory / "receipt.json")
        report_hash = decisions.get("reportHash")
        if not isinstance(report_hash, str) or not re.fullmatch(
            r"sha256:[a-f0-9]{64}", report_hash
        ):
            raise ProofBuildError("retained decision report identity differs")
        report_path = self.root / "reports" / f"{report_hash[7:]}.json"
        if _file_hash(report_path) != report_hash:
            raise ProofBuildError("retained decision report changed")
        baseline, build = self._baseline(receipt["baselineHash"])
        input_path = directory / "inputs.json"
        inputs = load_operator_json(input_path)
        a, b = inputs["observationA"], inputs["observationB"]
        if inputs != self._proof_inputs(baseline, build, a, b):
            raise ProofBuildError("retained decision baseline inputs differ")
        for observation in (a, b):
            self._occurrence_identity(
                observation, baseline["nativeIdentity"], build.request["evidenceLevel"]
            )
        envelope = self._semantic("decide", [input_path, report_path, raw_path])
        expected = {
            "status": envelope["result"]["status"],
            "evidenceLevel": build.request["evidenceLevel"],
            "decisionKey": key,
            "decisionHash": _digest(raw),
            "reportHash": report_hash,
            "baselinePointerHash": _digest(
                _receipt_bytes(
                    {
                        "schemaVersion": "issue-144-baseline-pointer/v1",
                        "baselineHash": receipt["baselineHash"],
                    }
                )
            ),
            "baselineHash": receipt["baselineHash"],
            "priorIdentity": baseline["nativeIdentity"],
            "revisionRoot": str(directory / "build"),
            "semanticReceipt": envelope,
        }
        if not envelope["ok"] or receipt != expected:
            raise ProofBuildError("retained decision receipt binding differs")
        if receipt["status"] == "revised":
            for name, digest in envelope["artifactHashes"].items():
                if _file_hash(directory / "build" / name) != digest:
                    raise ProofBuildError("revised canonical input changed")
        return receipt

    def _decision(self, key: str) -> tuple[JsonObject, PreparedBuild]:
        directory = self.root / "decisions" / key
        receipt = self._retained_decision(key)
        if (
            receipt.get("decisionKey") != key
            or receipt.get("decisionHash")
            != _file_hash(directory / "operator-decisions.json")
            or receipt.get("status") != "revised"
            or receipt.get("revisionRoot") != str(directory / "build")
        ):
            raise ProofBuildError("rebuild decision identity differs")
        build = PreparedBuild(directory / "build", node_executable=self.build.node)
        for name, digest in receipt["semanticReceipt"]["artifactHashes"].items():
            if _file_hash(build.root / name) != digest:
                raise ProofBuildError("revised canonical input changed")
        return receipt, build

    def _rebuild(self, key: str) -> JsonObject:
        decision, build = self._decision(key)
        if _file_hash(self.pointer) != decision["baselinePointerHash"]:
            promoted = self.root / "decisions" / key / "promotion.json"
            if promoted.exists():
                self._verify_promotion(key, build)
                return load_operator_json(
                    self.root / "decisions" / key / "rebuild.json"
                )
            raise ProofBuildError("stale rebuild baseline")
        baseline, prior_build = self._baseline(decision["baselineHash"])
        a, b = self._fresh(prior_build, "rebuild", key)
        inputs = load_operator_json(self.root / "decisions" / key / "inputs.json")
        if inputs != self._proof_inputs(baseline, prior_build, a, b):
            raise ProofBuildError("edited observation changed before rebuild")
        adapter = self.native_provider(build) if self.native_provider else None
        result = build.run(adapter=adapter)
        if result["status"] != "complete":
            return {"status": result["status"], "decisionKey": key, "job": result}
        self._ready(build)
        receipt = {
            "status": "complete",
            "decisionKey": key,
            "snapshotId": build.snapshot_id,
            "identityHash": _file_hash(build.run_root / "native-identity.json"),
            "resultHash": _file_hash(build.run_root / "native-result.json"),
        }
        publish_immutable_output(
            self.root / "decisions" / key / "rebuild.json", _receipt_bytes(receipt)
        )
        return receipt

    def _verify_promotion(self, key: str, build: PreparedBuild) -> JsonObject:
        receipt = load_operator_json(self.root / "decisions" / key / "promotion.json")
        if (
            set(receipt) != {"status", "decisionKey", "baselineHash"}
            or receipt.get("status") != "promoted"
            or receipt.get("decisionKey") != key
        ):
            raise ProofBuildError("promotion receipt binding differs")
        _, promoted = self._baseline(receipt["baselineHash"])
        if promoted.root != build.root or promoted.snapshot_id != build.snapshot_id:
            raise ProofBuildError("promotion baseline refers to another build")
        return receipt

    def _promote(self, key: str) -> JsonObject:
        promotion = self.root / "decisions" / key / "promotion.json"
        decision, build = self._decision(key)
        if promotion.exists():
            return self._verify_promotion(key, build)
        rebuild_path = self.root / "decisions" / key / "rebuild.json"
        if not rebuild_path.exists():
            raise ProofBuildError("rebuild is not complete and verified")
        rebuilt = load_operator_json(rebuild_path)
        identity = self._ready(build)
        if (
            rebuilt.get("snapshotId") != build.snapshot_id
            or rebuilt.get("identityHash")
            != _file_hash(build.run_root / "native-identity.json")
            or rebuilt.get("resultHash")
            != _file_hash(build.run_root / "native-result.json")
        ):
            raise ProofBuildError("rebuilt target receipt changed")
        if (
            identity["projectUid"] == decision["priorIdentity"]["projectUid"]
            or identity["timelineUid"] == decision["priorIdentity"]["timelineUid"]
        ):
            raise ProofBuildError("rebuild did not produce a fresh target")
        a, b = self._fresh(build, "promote", key)
        digest = self._publish_baseline(build, a, b)
        receipt = {"status": "promoted", "decisionKey": key, "baselineHash": digest}
        expected = {
            "schemaVersion": "issue-144-baseline-pointer/v1",
            "baselineHash": digest,
        }
        # If interrupted after pointer replacement, verify the already-published
        # new baseline and finish the same promotion, without another advance.
        if load_operator_json(self.pointer) != expected:
            if _file_hash(self.pointer) != decision["baselinePointerHash"]:
                raise ProofBuildError("baseline changed before promotion")
            _replace_pointer(self.pointer, expected)
        publish_immutable_output(promotion, _receipt_bytes(receipt))
        return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description="Issue144 bounded file proof")
    parser.add_argument(
        "action",
        choices=(
            "build",
            "bind-baseline",
            "propose",
            "decide",
            "bind-omission-evidence",
            "propose-omission",
            "rebuild",
            "promote",
            "status",
        ),
    )
    parser.add_argument("--proof-root", required=True, type=Path)
    parser.add_argument("--node-executable")
    parser.add_argument("--decision-key")
    args = parser.parse_args()
    try:
        session = ProofSession(args.proof_root, node_executable=args.node_executable)
        result = session.run(args.action, decision_key=args.decision_key)
        print(json.dumps(result, sort_keys=True))
        return (
            0
            if result["status"] not in {"waiting", "needs_action", "failed", "refused"}
            else 2
        )
    except NeedsAction as error:
        print(json.dumps({"status": "needs_action", "reason": str(error)}))
        return 2
    except (ProofProcessFault, OSError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"status": "fault", "reason": str(error)}))
        return 70
    except (
        RuntimeError,
        ValueError,
        KeyError,
        TypeError,
    ) as error:
        print(json.dumps({"status": "refused", "reason": str(error)}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
