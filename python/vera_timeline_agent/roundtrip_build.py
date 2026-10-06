"""Issue 144 prepared-input stages on the accepted durable build/package APIs.

This module has no synthesis, acquisition or default native adapter. Native
assembly is a separate explicit seam; a prepared package is not a proof baseline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import stat
import subprocess
import sys
import wave
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from vera_timeline_agent.build_jobs import (
    BuildJobStore,
    BuildRequest,
    NeedsAction,
    StageAdapter,
    StageContext,
    publish_immutable_output,
)
from vera_timeline_agent.resolve_import_package import (
    ResolveImportVerification,
    build_resolve_import_package,
    verify_resolve_import_package,
)

ROOT = Path(__file__).resolve().parents[2]
COMPILER_ENTRY = ROOT / "packages/contracts/src/issue-144-compile-cli.ts"
INPUT_NAMES = (
    "proof-request.json",
    "script-document.json",
    "compiler-dependencies.json",
    "materialization-plan.json",
)
CODE_PATHS = (
    Path(__file__).resolve(),
    COMPILER_ENTRY,
    ROOT / "packages/contracts/src/compiler-core.ts",
    ROOT / "packages/contracts/src/script-validator.ts",
    ROOT / "python/vera_timeline_agent/build_jobs.py",
    ROOT / "python/vera_timeline_agent/studio_assembly.py",
    ROOT / "python/vera_timeline_agent/studio_spike.py",
    ROOT / "python/vera_timeline_agent/roundtrip_native.py",
    ROOT / "python/vera_timeline_agent/roundtrip_proof.py",
    ROOT / "python/vera_timeline_agent/roundtrip_narration.py",
    ROOT / "python/vera_timeline_agent/roundtrip_audio.py",
    ROOT / "python/vera_timeline_agent/roundtrip_omission.py",
    ROOT / "python/vera_timeline_agent/roundtrip_generation.py",
    ROOT / "python/vera_timeline_agent/roundtrip_wi.py",
    ROOT / "python/vera_timeline_agent/roundtrip_driver.py",
    ROOT / "packages/contracts/src/script-validator-cli.ts",
    *(
        ROOT / "python/vera_timeline_agent/narration" / name
        for name in (
            "service.py",
            "cache.py",
            "compiler_dependencies.py",
            "models.py",
            "normalize.py",
            "provider.py",
            "polly.py",
        )
    ),
    ROOT / "packages/contracts/src/issue-144-proof-cli.ts",
    ROOT / "packages/contracts/src/issue-144-semantics.ts",
    ROOT / "packages/contracts/src/issue-144-text-revision.ts",
    ROOT / "packages/contracts/src/issue-144-omission-build.ts",
    ROOT / "packages/contracts/src/issue-144-composition.ts",
    ROOT / "python/vera_timeline_agent/resolve_import_package/package.py",
    ROOT / "package-lock.json",
    ROOT / "uv.lock",
    *(
        ROOT / "contracts" / name
        for name in (
            "script-document-v1.schema.json",
            "compiler-dependencies-v1.schema.json",
            "timeline-manifest-v1.schema.json",
            "build-report-v1.schema.json",
        )
    ),
)
JsonObject = dict[str, Any]


class ProofBuildError(RuntimeError):
    """A prepared-input or receipt refusal, without native mutation."""


def _receipt_bytes(value: object) -> bytes:
    # Issue-owned receipts only. Never reserialize accepted compiler outputs or
    # use this serializer for a ScriptDocument revision/content hash.
    return (
        json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False, allow_nan=False)
        + "\n"
    ).encode("utf-8")


def _digest(content: bytes) -> str:
    return f"sha256:{hashlib.sha256(content).hexdigest()}"


def _regular(path: Path) -> Path:
    absolute = path.absolute()
    for component in (absolute, *absolute.parents):
        if component.is_symlink():
            raise ProofBuildError(f"symbolic link is unsupported: {path}")
    details = absolute.stat()
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise ProofBuildError(f"independent regular file required: {path}")
    return absolute


def _file_hash(path: Path) -> str:
    path = _regular(path)
    before = path.stat()
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    after = path.stat()
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ):
        raise ProofBuildError(f"file changed while hashing: {path}")
    return f"sha256:{digest.hexdigest()}"


def _object(pairs: list[tuple[str, Any]]) -> JsonObject:
    value: JsonObject = {}
    for key, item in pairs:
        if key in value:
            raise ProofBuildError(f"duplicate JSON key: {key}")
        value[key] = item
    return value


def _constant(value: str) -> None:
    raise ProofBuildError(f"non-finite JSON number: {value}")


def _number(value: str) -> float:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProofBuildError(f"non-finite JSON numeral: {value}")
    return parsed


def _integer(value: str) -> int:
    parsed = int(value)
    if abs(parsed) > 2**53 - 1:
        raise ProofBuildError("JSON integer exceeds the exact JavaScript range")
    return parsed


def _parse(raw: bytes) -> JsonObject:
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_object,
            parse_constant=_constant,
            parse_float=_number,
            parse_int=_integer,
        )
    except (UnicodeError, ValueError) as error:
        raise ProofBuildError(f"invalid operator JSON: {error}") from error
    if not isinstance(value, dict):
        raise ProofBuildError("operator file must contain one JSON object")
    return cast(JsonObject, value)


def _operator_bytes(path: Path) -> bytes:
    try:
        _regular(path)
        if path.stat().st_size > 8 * 1024 * 1024:
            raise ProofBuildError(f"operator JSON exceeds bounded 8 MiB: {path}")
        return path.read_bytes()
    except OSError as error:
        raise ProofBuildError(f"operator file unavailable: {path}") from error


def load_operator_json(path: Path) -> JsonObject:
    return _parse(_operator_bytes(path))


class PreparedBuild:
    """One hash-bound local request with five real core stages and no native default."""

    def __init__(self, proof_root: Path, *, node_executable: str | None = None) -> None:
        self.root = proof_root.absolute()
        if self.root.is_symlink() or not self.root.is_dir():
            raise ProofBuildError("proof root must be an existing local directory")
        self.node = node_executable or shutil.which("node") or "node"
        self._check_runtime()
        self.raw = {name: _operator_bytes(self.root / name) for name in INPUT_NAMES}
        self.values = {name: _parse(raw) for name, raw in self.raw.items()}
        request = self.values["proof-request.json"]
        if set(request) != {"schemaVersion", "evidenceLevel", "verifiedAt"} or (
            request["schemaVersion"] != "issue-144-prepared-build/v1"
            or request["evidenceLevel"] not in {"synthetic_injected", "real_issue145"}
            or not isinstance(request["verifiedAt"], str)
        ):
            raise ProofBuildError("invalid bounded proof request")
        self.request = request
        self.document = self.values["script-document.json"]
        self.dependencies = self.values["compiler-dependencies.json"]
        self.input_hashes = {name: _digest(raw) for name, raw in self.raw.items()}
        self.source_hashes = self._code_hashes()
        self.snapshot_id = _digest(
            _receipt_bytes(
                {
                    "inputs": self.input_hashes,
                    "sources": self.source_hashes,
                }
            )
        )[7:]
        self.run_root = self.root / "runs" / self.snapshot_id
        self.manifest_path = self.run_root / "compiled" / "timeline-manifest.json"
        self.report_path = self.run_root / "compiled" / "build-report.json"
        self.package_root = self.run_root / "package"
        self.intent_path = self.run_root / "native-intent.json"
        self.plan: JsonObject = {}
        self.origins: dict[str, Path] = {}
        self.media_hashes: dict[str, str] = {}
        for source_id, entry in self.values["materialization-plan.json"].items():
            if (
                not isinstance(entry, dict)
                or set(entry)
                != {
                    "artifactId",
                    "origin",
                    "policy",
                }
                or any(
                    not isinstance(entry[key], str) or not entry[key] for key in entry
                )
                or entry["policy"] not in {"copy", "clone_or_copy"}
            ):
                raise ProofBuildError(f"invalid materialization entry: {source_id}")
            origin = Path(entry["origin"])
            if not origin.is_absolute():
                origin = self.root / origin
            self.origins[source_id] = origin
            self.media_hashes[source_id] = _file_hash(origin)
            self.plan[source_id] = {**entry, "origin": str(origin)}
        self.store: BuildJobStore | None = None
        self.job_id = ""

    def _check_runtime(self) -> None:
        if sys.version_info[:3] != (3, 12, 14):
            raise ProofBuildError("Issue 144 requires pinned Python 3.12.14")
        try:
            runtime = subprocess.run(
                [self.node, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise ProofBuildError(
                "Node v24.19.0 is required before compilation"
            ) from error
        if runtime.returncode or runtime.stdout.strip() != "v24.19.0":
            raise ProofBuildError("Node v24.19.0 is required before compilation")

    def _code_hashes(self) -> dict[str, str]:
        return {
            path.relative_to(ROOT).as_posix(): _file_hash(path) for path in CODE_PATHS
        }

    def _assert_current(self) -> None:
        for name, expected in self.input_hashes.items():
            if _file_hash(self.root / name) != expected:
                raise ProofBuildError(f"input changed: {name}")
            frozen = self.run_root / "inputs" / name
            if frozen.exists() and _file_hash(frozen) != expected:
                raise ProofBuildError(f"frozen input changed: {name}")
        if self._code_hashes() != self.source_hashes:
            raise ProofBuildError("proof source or lockfile changed")

    def _verify_media(self) -> None:
        for source_id, origin in self.origins.items():
            if _file_hash(origin) != self.media_hashes[source_id]:
                raise ProofBuildError(f"prepared media changed: {source_id}")

    def _verify_speech(self) -> None:
        self._verify_media()
        blocks = {
            block["id"]: block
            for block in self.document["activeDraft"]["blocks"]
            if block["type"] == "narration"
        }
        seen: set[str] = set()
        for dependency in self.dependencies["narration"]:
            block_id = dependency["blockId"]
            if block_id in seen or block_id not in blocks:
                raise ProofBuildError("unknown or duplicate narration block")
            seen.add(block_id)
            block = blocks[block_id]
            if dependency["status"] != "ready" or (
                dependency["blockRevision"] != block["version"]
                or dependency["textHash"] != _digest(block["text"].encode("utf-8"))
            ):
                raise ProofBuildError(
                    "prepared narration text/revision binding is stale"
                )
            candidates = [
                identity
                for identity, entry in self.plan.items()
                if entry["artifactId"] == dependency["assetId"]
            ]
            if len(candidates) != 1:
                raise ProofBuildError(
                    "narration asset needs one materialization artifactId"
                )
            identity = candidates[0]
            if self.media_hashes[identity] != dependency["audioHash"]:
                raise ProofBuildError("prepared narration audio hash differs")
            with wave.open(str(self.origins[identity]), "rb") as stream:
                actual = (
                    stream.getnchannels(),
                    stream.getsampwidth(),
                    stream.getframerate(),
                    stream.getnframes(),
                )
            audio = dependency["audio"]
            if actual != (1, 3, 48000, audio["durationSamples"]) or (
                audio["channels"] != 1 or audio["sampleRate"] != 48000
            ):
                raise ProofBuildError(
                    "prepared narration must be matching PCM24 mono 48k"
                )
        if seen != set(blocks):
            raise ProofBuildError("prepared narration dependencies are incomplete")

    def _compile(self) -> JsonObject:
        self._check_runtime()
        completed = subprocess.run(
            [
                self.node,
                str(COMPILER_ENTRY),
                str(self.run_root / "inputs/script-document.json"),
                str(self.run_root / "inputs/compiler-dependencies.json"),
            ],
            capture_output=True,
            timeout=120,
            check=False,
        )
        if completed.returncode not in {0, 1} or not completed.stdout:
            raise ProofBuildError(
                f"compiler execution fault (exit {completed.returncode})"
            )
        result = _parse(completed.stdout)
        if result.get("schemaVersion") != "issue-144-compile/v1" or (
            result.get("evidenceLevel") != "compiler_only"
            or result.get("runtime") != "v24.19.0"
            or result.get("inputs")
            != {
                "scriptSha256": self.input_hashes["script-document.json"],
                "dependenciesSha256": self.input_hashes["compiler-dependencies.json"],
            }
        ):
            raise ProofBuildError("compiler envelope does not bind this request")
        if completed.returncode == 1 and result.get("ok") is False:
            publish_immutable_output(
                self.run_root / "compiler-refusal.json", completed.stdout
            )
            raise ProofBuildError("actual compiler refused; see compiler-refusal.json")
        if completed.returncode or result.get("ok") is not True:
            raise ProofBuildError(
                "compiler failure was not a valid deterministic refusal"
            )
        manifest_bytes = result["manifestJson"].encode("utf-8")
        report_bytes = result["reportJson"].encode("utf-8")
        if result["outputs"] != {
            "manifestSha256": _digest(manifest_bytes),
            "reportSha256": _digest(report_bytes),
        }:
            raise ProofBuildError("compiler output byte hashes differ")
        manifest = _parse(manifest_bytes)
        sources = {
            source["id"]: source
            for source in manifest["sources"]
            if source["kind"] != "placeholder"
        }
        if set(sources) != set(self.plan) or any(
            source["contentHash"] != self.media_hashes[identity]
            for identity, source in sources.items()
        ):
            raise ProofBuildError(
                "materialization identity/bytes differ from actual compile"
            )
        self._assert_current()
        self._verify_media()
        publish_immutable_output(self.manifest_path, manifest_bytes)
        publish_immutable_output(self.report_path, report_bytes)
        return result

    def verified_package(self) -> ResolveImportVerification:
        self._verify_compiler_files()
        verification = verify_resolve_import_package(self.package_root)
        build_root = self.package_root / "Builds" / verification.build_id
        if (
            build_root / "timeline-manifest.json"
        ).read_bytes() != self.manifest_path.read_bytes() or (
            (build_root / "build-report.json").read_bytes()
            != self.report_path.read_bytes()
        ):
            raise ProofBuildError("package does not contain exact compiler bytes")
        return verification

    def _verify_compiler_files(self, result: JsonObject | None = None) -> None:
        if result is None:
            if self.store is None:
                raise ProofBuildError(
                    "compiler stage must precede package verification"
                )
            stages = self.store.status(self.document["projectId"], self.job_id)[
                "stages"
            ]
            stage = next(row for row in stages if row["name"] == "compiling")
            if stage["status"] != "complete" or not stage["path"]:
                raise ProofBuildError("compiler stage has no completed receipt")
            result = cast(JsonObject, load_operator_json(Path(stage["path"]))["result"])
        if result.get("outputs") != {
            "manifestSha256": _file_hash(self.manifest_path),
            "reportSha256": _file_hash(self.report_path),
        }:
            raise ProofBuildError("compiler output files changed")

    def reconcile(self, context: StageContext) -> bool:
        self._assert_current()
        if not context.output_path.exists():
            return False
        receipt = load_operator_json(context.output_path)
        if receipt.get("stageKey") != context.stage_key or (
            receipt.get("snapshotId") != self.snapshot_id
            or receipt.get("stage") != context.stage
            or receipt.get("evidenceLevel") != "local_prepared"
            or receipt.get("proofLane") != self.request["evidenceLevel"]
        ):
            raise ProofBuildError("stage receipt belongs to a different request")
        self._verify_media()
        if context.stage == "compiling":
            self._verify_compiler_files(receipt["result"])
        if context.stage in {"writing_interchange", "verifying_import_package"}:
            self.verified_package()
        return True

    def execute(self, context: StageContext) -> None:
        self._assert_current()
        if context.stage == "generating_speech":
            self._verify_speech()
            result: JsonObject = {
                "policy": "verify_prepared_only",
                "media": self.media_hashes,
            }
        elif context.stage == "resolving_media":
            self._verify_media()
            result = {"policy": "verify_local_only", "media": self.media_hashes}
        elif context.stage == "compiling":
            # The nested compiler_only envelope describes compiler outputs;
            # the outer local_prepared receipt describes this durable stage.
            result = self._compile()
        elif context.stage == "writing_interchange":
            self._verify_media()
            plan_path = self.run_root / "package-plan.json"
            publish_immutable_output(plan_path, _receipt_bytes(self.plan))
            package = build_resolve_import_package(
                self.manifest_path,
                self.report_path,
                plan_path,
                self.package_root,
                verified_at=self.request["verifiedAt"],
            )
            result = {
                "buildId": package.build_id,
                "verificationHash": _file_hash(package.verification_path),
            }
        elif context.stage == "verifying_import_package":
            result = asdict(self.verified_package())
        else:
            raise NeedsAction(
                "Native assembly/verification requires the explicit #145 seam"
            )
        self._assert_current()
        self._verify_media()
        publish_immutable_output(
            context.output_path,
            _receipt_bytes(
                {
                    "schemaVersion": "issue-144-prepared-stage/v1",
                    "snapshotId": self.snapshot_id,
                    "stageKey": context.stage_key,
                    "stage": context.stage,
                    "evidenceLevel": "local_prepared",
                    "proofLane": self.request["evidenceLevel"],
                    "result": result,
                }
            ),
        )

    def preflight(self) -> JsonObject:
        """Validate local inputs/compiler bytes without creating or running a job."""
        self._assert_current()
        for name, raw in self.raw.items():
            publish_immutable_output(self.run_root / "inputs" / name, raw)
        self._verify_speech()
        compiled = self._compile()
        result = {
            "schemaVersion": "issue-144-local-preflight/v1",
            "status": "prepared",
            "evidenceLevel": "local_prepared",
            "proofLane": self.request["evidenceLevel"],
            "snapshotId": self.snapshot_id,
            "inputs": self.input_hashes,
            "sources": self.source_hashes,
            "outputs": compiled["outputs"],
            "unchecked": [
                "zero-start 25fps complete programme at most1562frames",
                "ready audio/video only; no stills/Fusion/placeholders",
                "1-8 independent mono48k PCM16/24 frame-aligned audio sources",
                "selected primary row at most64tokens and complete word supports",
                "two distinct use_source visuals plus one muted full-row companion",
                "unique supported linked move/trim and interior omission",
                "qualified native/control/support/calibration/render/"
                "provider boundaries",
            ],
        }
        self._assert_current()
        self._verify_media()
        publish_immutable_output(
            self.run_root / "preflight.json", _receipt_bytes(result)
        )
        return result

    def _recovery_blocked(self, job: JsonObject, reason: str) -> JsonObject:
        return {
            "schemaVersion": "issue-144-job-recovery/v1",
            "status": "recovery_blocked",
            "evidenceLevel": self.request["evidenceLevel"],
            "snapshotId": self.snapshot_id,
            "reason": reason,
            "job": job,
        }

    def run(
        self, *, adapter: StageAdapter | None = None, resume: bool = False
    ) -> JsonObject:
        self._assert_current()
        for name, raw in self.raw.items():
            publish_immutable_output(self.run_root / "inputs" / name, raw)
        job_path = self.run_root / "build-job.json"
        if resume and (not job_path.exists() or not (self.root / "jobs").is_dir()):
            raise ProofBuildError(
                "no matching retained job; build before explicit resume"
            )
        self.store = BuildJobStore(self.root / "jobs")
        if resume:
            retained = load_operator_json(job_path)
            if set(retained) != {
                "schemaVersion",
                "snapshotId",
                "projectId",
                "jobId",
            } or (
                retained["schemaVersion"] != "issue-144-build-job/v1"
                or retained["snapshotId"] != self.snapshot_id
                or retained["projectId"] != self.document["projectId"]
                or not isinstance(retained["jobId"], str)
            ):
                raise ProofBuildError("retained job identity differs")
            self.job_id = retained["jobId"]
        else:
            self.job_id = self.store.submit(
                BuildRequest(
                    project_id=self.document["projectId"],
                    snapshot_id=self.snapshot_id,
                    idempotency_key=self.snapshot_id,
                    mode="studio",
                    render=False,
                    delivery=False,
                )
            )
            publish_immutable_output(
                job_path,
                _receipt_bytes(
                    {
                        "schemaVersion": "issue-144-build-job/v1",
                        "snapshotId": self.snapshot_id,
                        "projectId": self.document["projectId"],
                        "jobId": self.job_id,
                    }
                ),
            )
        previous = self.store.status(self.document["projectId"], self.job_id)
        if previous["snapshotId"] != self.snapshot_id or previous["mode"] != "studio":
            raise ProofBuildError("durable job does not bind this snapshot")
        if previous["events"] and previous["events"][-1]["kind"] == "integrity_failed":
            return self._recovery_blocked(previous, "retained job integrity failed")
        # Retain #35's canonical path/hash checks before any custom replay
        # callback, including a read-only native inspection.
        if not self.store._verify_completed(self.document["projectId"], self.job_id):
            return self._recovery_blocked(
                self.store.status(self.document["projectId"], self.job_id),
                "retained completed-stage integrity failed",
            )
        previous = self.store.status(self.document["projectId"], self.job_id)
        if any(stage["status"] == "complete" for stage in previous["stages"]):
            self._verify_media()
        if any(
            stage["name"] == "compiling" and stage["status"] == "complete"
            for stage in previous["stages"]
        ):
            self._verify_compiler_files()
        if any(
            stage["name"] == "verifying_import_package"
            and stage["status"] == "complete"
            for stage in previous["stages"]
        ):
            self.verified_package()
        if previous["status"] in {"waiting", "failed"} or resume or adapter is not None:
            from vera_timeline_agent.roundtrip_native import NativeStages

            if isinstance(adapter, NativeStages):
                reason = adapter.recovery_reason(self.job_id)
            elif (
                self.intent_path.exists()
                or self.intent_path.is_symlink()
                or (self.run_root / "native-result.json").exists()
                or (self.run_root / "native-result.json").is_symlink()
            ):
                reason = "explicit native boundary required to classify retained intent"
            else:
                reason = None
            if reason is not None:
                return self._recovery_blocked(previous, reason)
        if adapter is not None:
            for stage in previous["stages"]:
                if stage["status"] != "complete":
                    continue
                context = StageContext(
                    project_id=self.document["projectId"],
                    job_id=self.job_id,
                    snapshot_id=self.snapshot_id,
                    stage=stage["name"],
                    stage_key=hashlib.sha256(
                        f"{self.document['projectId']}\0{self.job_id}\0{stage['name']}".encode()
                    ).hexdigest(),
                    output_path=self.store._output_path(self.job_id, stage["name"]),
                    attempt_id=0,
                    lease_epoch=0,
                    report_progress=lambda _: None,
                    renew_lease=lambda: None,
                )
                if not adapter.reconcile(context):
                    raise ProofBuildError("completed stage no longer reconciles")
        if resume:
            if previous["status"] in {"waiting", "failed"}:
                if adapter is None:
                    raise ProofBuildError(
                        "explicit native boundary required before resume"
                    )
                self.store.resume(self.document["projectId"], self.job_id)
            elif previous["status"] != "complete":
                raise ProofBuildError(
                    "only a waiting, failed or complete job can resume"
                )
        while self.store.run_one(
            self.document["projectId"],
            self.job_id,
            "issue144-prepared-build",
            adapter or self,
        ):
            pass
        self._assert_current()
        result = self.store.status(self.document["projectId"], self.job_id)
        if result["status"] in {"waiting", "failed"}:
            from vera_timeline_agent.roundtrip_native import NativeStages

            if isinstance(adapter, NativeStages):
                reason = adapter.recovery_reason(self.job_id)
                if reason is not None:
                    return self._recovery_blocked(result, reason)
        return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proof-root", type=Path, required=True)
    parser.add_argument("--node-executable")
    args = parser.parse_args()
    try:
        build = PreparedBuild(args.proof_root, node_executable=args.node_executable)
        result = build.run()
        print(_receipt_bytes(result).decode("utf-8"), end="")
        return 0 if result["status"] == "complete" else 2
    except (OSError, ValueError, KeyError, TypeError, ProofBuildError) as error:
        print(f"PROOF_REFUSED: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
