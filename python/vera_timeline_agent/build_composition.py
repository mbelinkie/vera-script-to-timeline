"""Local, single-writer v2 build composition over the #35 durable job engine.

The engine owns scheduling, leases and stage completion. Each effect port owns
authoritative reconciliation; unknown is never interpreted as absent. Frozen
snapshots and completed stage receipts are rechecked before downstream effects.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, replace
from enum import StrEnum
from pathlib import Path
from typing import Any, Protocol

from .build_jobs import (
    ALL_STAGES,
    BuildJobError,
    BuildJobStore,
    BuildRequest,
    NeedsAction,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)
from .build_stage_receipt import (
    canonical_json,
    exact_receipt_matches,
    hash_file,
    receipt_bytes,
    require_hash,
)

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_VERSION_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:/-]{0,127}\Z")
_SNAPSHOT_VERSION = "vera-local-build-snapshot/v1"


def _identity(value: str, label: str) -> str:
    if not isinstance(value, str) or _ID.fullmatch(value) is None:
        raise BuildJobError(f"invalid {label}")
    return value


def _version(value: str) -> str:
    if (
        not isinstance(value, str)
        or _VERSION_NAME.fullmatch(value) is None
        or ".." in value
    ):
        raise BuildJobError("invalid adapter version")
    return value


def _safe_file(path: Path, roots: tuple[Path, ...]) -> Path:
    if not path.is_absolute() or any(
        part.is_symlink() for part in (path, *path.parents)
    ):
        raise BuildJobError(f"untrusted snapshot file path: {path}")
    if not any(path.is_relative_to(root) for root in roots):
        raise BuildJobError(f"snapshot file outside approved read roots: {path}")
    hash_file(path)
    return path


@dataclass(frozen=True)
class FrozenBuildSnapshot:
    snapshot_id: str
    raw: bytes
    project_id: str
    mode: str
    build_id: str
    build_class: str
    revision: str
    live_head_sequence: int
    head_hash: str
    settings_hash: str
    inputs: Mapping[str, Path]
    input_hashes: Mapping[str, str]
    adapter_versions: Mapping[str, str]
    write_root: Path

    @property
    def sha256(self) -> str:
        return self.snapshot_id

    def file(self, name: str) -> Path:
        try:
            return self.inputs[name]
        except KeyError as error:
            raise NeedsAction(f"frozen snapshot lacks {name}") from error


class SnapshotRepository:
    """Trusted creation and independent current-head lookup for immutable bytes.

    The repository is a local-agent-owned directory. Callers cannot supply a
    free-form snapshot JSON to the stage adapter. The head reader must consult
    project authority, not data from the submitted request.
    """

    def __init__(
        self,
        root: Path,
        *,
        read_roots: tuple[Path, ...],
        write_root: Path,
        live_head: Callable[[str], tuple[int, str, str]],
        live_settings: Callable[[str], str],
    ) -> None:
        self.root = root.absolute()
        self.read_roots = tuple(path.resolve(strict=True) for path in read_roots)
        self.write_root = write_root.absolute()
        self.live_head = live_head
        self.live_settings = live_settings
        if not self.read_roots or any(
            part.is_symlink()
            for part in (
                self.root,
                *self.root.parents,
                self.write_root,
                *self.write_root.parents,
            )
        ):
            raise BuildJobError("untrusted snapshot or output root")
        self.root.mkdir(parents=True, exist_ok=True)
        self.write_root.mkdir(parents=True, exist_ok=True)

    def freeze(
        self,
        *,
        project_id: str,
        mode: str,
        build_id: str,
        build_class: str,
        settings_hash: str,
        inputs: Mapping[str, Path],
        adapter_versions: Mapping[str, str],
    ) -> FrozenBuildSnapshot:
        _identity(project_id, "project ID")
        _identity(build_id, "build ID")
        if mode not in ("free", "studio") or build_class not in ("preview", "release"):
            raise BuildJobError("unrecognized build mode/class")
        require_hash(settings_hash, "settings")
        if self.live_settings(project_id) != settings_hash:
            raise BuildJobError("stale project settings")
        if not inputs or "document" not in inputs or "dependencies" not in inputs:
            raise BuildJobError("frozen document and dependencies are required")
        if not adapter_versions:
            raise BuildJobError("no pinned adapter versions")
        sequence, head_hash, revision = self.live_head(project_id)
        if type(sequence) is not int or sequence < 0:
            raise BuildJobError("invalid project live head sequence")
        require_hash(head_hash, "live head")
        _identity(revision, "revision")
        pinned = {
            _identity(name, "input name"): {
                "path": str(_safe_file(path, self.read_roots)),
                "sha256": hash_file(path),
            }
            for name, path in inputs.items()
        }
        versions = {
            _identity(name, "adapter name"): _version(version)
            for name, version in adapter_versions.items()
        }
        data = {
            "schemaVersion": _SNAPSHOT_VERSION,
            "projectId": project_id,
            "mode": mode,
            "buildId": build_id,
            "buildClass": build_class,
            "revision": revision,
            "liveHeadSequence": sequence,
            "liveHeadHash": head_hash,
            "settingsHash": settings_hash,
            "inputs": pinned,
            "adapterVersions": versions,
            "writeRoot": str(self.write_root),
        }
        raw = canonical_json(data)
        digest = hashlib.sha256(raw).hexdigest()
        publish_immutable_output(self.root / f"{digest}.json", raw)
        return self.load(project_id, digest)

    def load(self, project_id: str, snapshot_id: str) -> FrozenBuildSnapshot:
        _identity(project_id, "project ID")
        require_hash(snapshot_id, "snapshot ID")
        source = self.root / f"{snapshot_id}.json"
        if hash_file(source) != snapshot_id:
            raise BuildJobError("frozen snapshot is missing or changed")
        raw = source.read_bytes()

        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            value: dict[str, Any] = {}
            for key, item in pairs:
                if key in value:
                    raise BuildJobError("duplicate snapshot key")
                value[key] = item
            return value

        try:
            data = json.loads(raw, object_pairs_hook=unique)
        except (UnicodeError, ValueError) as error:
            raise BuildJobError("invalid snapshot encoding") from error
        if (
            not isinstance(data, dict)
            or set(data)
            != {
                "schemaVersion",
                "projectId",
                "mode",
                "buildId",
                "buildClass",
                "revision",
                "liveHeadSequence",
                "liveHeadHash",
                "settingsHash",
                "inputs",
                "adapterVersions",
                "writeRoot",
            }
            or raw != canonical_json(data)
            or data["schemaVersion"] != _SNAPSHOT_VERSION
        ):
            raise BuildJobError("unknown or noncanonical snapshot schema")
        if data["projectId"] != project_id or data["writeRoot"] != str(self.write_root):
            raise BuildJobError("snapshot project/output authority mismatch")
        if data["mode"] not in ("free", "studio") or data["buildClass"] not in (
            "preview",
            "release",
        ):
            raise BuildJobError("snapshot mode/class mismatch")
        _identity(data["buildId"], "build ID")
        _identity(data["revision"], "revision")
        require_hash(data["liveHeadHash"], "live head")
        require_hash(data["settingsHash"], "settings")
        if self.live_settings(project_id) != data["settingsHash"]:
            raise BuildJobError("stale project settings")
        if type(data["liveHeadSequence"]) is not int or data["liveHeadSequence"] < 0:
            raise BuildJobError("invalid snapshot sequence")
        if (
            not isinstance(data["inputs"], dict)
            or not {"document", "dependencies"} <= data["inputs"].keys()
        ):
            raise BuildJobError("snapshot has no document/dependencies")
        if not isinstance(data["adapterVersions"], dict) or not data["adapterVersions"]:
            raise BuildJobError("snapshot has no pinned adapters")
        versions = {
            _identity(name, "adapter"): _version(value)
            for name, value in data["adapterVersions"].items()
        }
        paths: dict[str, Path] = {}
        hashes: dict[str, str] = {}
        for name, item in data["inputs"].items():
            _identity(name, "input")
            if (
                not isinstance(item, dict)
                or set(item) != {"path", "sha256"}
                or not isinstance(item["path"], str)
            ):
                raise BuildJobError("invalid snapshot input descriptor")
            path = _safe_file(Path(item["path"]), self.read_roots)
            expected = require_hash(item["sha256"], "input")
            if hash_file(path) != expected:
                raise BuildJobError(f"stale frozen input: {name}")
            paths[name] = path
            hashes[name] = expected
        live = self.live_head(project_id)
        if live != (data["liveHeadSequence"], data["liveHeadHash"], data["revision"]):
            raise BuildJobError("stale project live head/revision")
        return FrozenBuildSnapshot(
            snapshot_id=snapshot_id,
            raw=raw,
            project_id=project_id,
            mode=data["mode"],
            build_id=data["buildId"],
            build_class=data["buildClass"],
            revision=data["revision"],
            live_head_sequence=data["liveHeadSequence"],
            head_hash=data["liveHeadHash"],
            settings_hash=data["settingsHash"],
            inputs=paths,
            input_hashes=hashes,
            adapter_versions=versions,
            write_root=self.write_root,
        )


class EffectState(StrEnum):
    ABSENT = "absent"  # Authority proves no effect occurred.
    VERIFIED = "verified"  # Independently reverified effect and files.
    UNCERTAIN = "uncertain"  # Might have occurred; prohibit replay.
    NEEDS_ACTION = "needs_action"  # Approval/capability missing.


@dataclass(frozen=True)
class StageEvidence:
    """Artifacts independently checked by the port and then rehashed by us."""

    adapter_id: str
    adapter_version: str
    inputs: Mapping[str, Path]
    outputs: Mapping[str, Path]
    attestation: Path | None = None


@dataclass(frozen=True)
class Inspection:
    state: EffectState
    evidence: StageEvidence | None = None
    reason: str = ""


class StagePort(Protocol):
    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        """Consult the effect's authority and independently verify its output."""

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        """Attempt the *same* stable effect key, after a proven absence check."""


class BuildComposition:
    def __init__(self, snapshots: SnapshotRepository, ports: Mapping[str, StagePort]):
        self.snapshots = snapshots
        self.ports = dict(ports)

    def submit(self, store: BuildJobStore, request: BuildRequest) -> str:
        request.validate()
        frozen = self.snapshots.load(request.project_id, request.snapshot_id)
        if request.mode != frozen.mode:
            raise BuildJobError("build mode differs from frozen snapshot")
        if request.render or request.delivery:
            raise NeedsAction(
                "render and upload require separately verified #71 adapters"
            )
        return store.submit(request)

    def _port(self, name: str) -> StagePort:
        try:
            return self.ports[name]
        except KeyError as error:
            raise NeedsAction(
                f"verified {name} effect port is not installed"
            ) from error

    def _inspection(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        result = self._port(context.stage).inspect(context, snapshot)
        if result.state == EffectState.UNCERTAIN:
            raise UncertainResult(
                result.reason or f"{context.stage} effect is uncertain"
            )
        if result.state == EffectState.NEEDS_ACTION:
            raise NeedsAction(
                result.reason or f"{context.stage} requires authorization"
            )
        if result.state == EffectState.VERIFIED and result.evidence is None:
            raise BuildJobError("verified stage has no independently checked evidence")
        if result.state == EffectState.ABSENT and result.evidence is not None:
            raise BuildJobError("absent stage cannot present evidence")
        return result

    def _evidence_bytes(
        self,
        context: StageContext,
        snapshot: FrozenBuildSnapshot,
        evidence: StageEvidence,
    ) -> bytes:
        if (
            snapshot.adapter_versions.get(evidence.adapter_id)
            != evidence.adapter_version
        ):
            raise BuildJobError("stale/unapproved stage adapter version")

        def hashes(mapping: Mapping[str, Path]) -> dict[str, str]:
            if not mapping:
                raise BuildJobError("verified stage has no artifact mapping")
            values: dict[str, str] = {}
            for name, path in mapping.items():
                if not isinstance(path, Path) or not path.is_absolute():
                    raise BuildJobError("untrusted effect artifact path")
                if not (
                    path.is_relative_to(snapshot.write_root)
                    or (name in snapshot.inputs and path == snapshot.inputs[name])
                ):
                    raise BuildJobError("effect file outside frozen roots")
                values[name] = hash_file(path)
                if (
                    name in snapshot.input_hashes
                    and path == snapshot.inputs[name]
                    and values[name] != snapshot.input_hashes[name]
                ):
                    raise BuildJobError("effect input changed after freeze")
            return values

        return receipt_bytes(
            context,
            snapshot_sha256=snapshot.sha256,
            adapter_id=evidence.adapter_id,
            adapter_version=evidence.adapter_version,
            input_hashes=hashes(evidence.inputs),
            output_hashes=hashes(evidence.outputs),
            attestation_sha256=hash_file(evidence.attestation)
            if evidence.attestation
            else None,
        )

    def _prior(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        for stage in ALL_STAGES[: ALL_STAGES.index(context.stage)]:
            if stage not in self.ports:
                # The only omitted earlier stages are explicitly skipped optional
                # phases, never an unresolved core or native predecessor.
                if stage in ALL_STAGES[:5] or stage in (
                    "building_resolve_timeline",
                    "verifying_timeline",
                ):
                    raise NeedsAction(f"required predecessor port {stage} is missing")
                continue
            earlier = replace(
                context,
                stage=stage,
                stage_key=hashlib.sha256(
                    f"{context.project_id}\0{context.job_id}\0{stage}".encode()
                ).hexdigest(),
                output_path=context.output_path.parent.parent / stage / "output",
            )
            if not earlier.output_path.is_file():
                raise BuildJobError(f"missing completed predecessor receipt {stage}")
            result = self._inspection(earlier, snapshot)
            if result.state != EffectState.VERIFIED or result.evidence is None:
                raise UncertainResult(
                    f"prior {stage} effect is no longer independently verified"
                )
            expected = self._evidence_bytes(earlier, snapshot, result.evidence)
            if (
                earlier.output_path.is_symlink()
                or earlier.output_path.read_bytes() != expected
            ):
                raise BuildJobError(
                    f"completed predecessor receipt {stage} differs from evidence"
                )

    def reconcile(self, context: StageContext) -> bool:
        if context.job_kind != "build":
            raise BuildJobError("composition cannot handle an ingest job")
        if context.stage not in ALL_STAGES:
            raise BuildJobError("unknown build stage")
        snapshot = self.snapshots.load(context.project_id, context.snapshot_id)
        self._prior(context, snapshot)
        inspected = self._inspection(context, snapshot)
        if inspected.state == EffectState.ABSENT:
            if context.output_path.exists() or context.output_path.is_symlink():
                raise UncertainResult(
                    "receipt exists but external effect is not verified"
                )
            return False
        assert inspected.evidence is not None
        expected = self._evidence_bytes(context, snapshot, inspected.evidence)
        if context.output_path.exists():
            if (
                context.output_path.is_symlink()
                or context.output_path.read_bytes() != expected
            ):
                raise BuildJobError(
                    "stage receipt is inconsistent with verified effect"
                )
        else:
            # An interrupted worker can leave a verified effect without a local
            # stage receipt. Only the currently leased worker may publish it.
            context.renew_lease()
            publish_immutable_output(context.output_path, expected)
        if not exact_receipt_matches(
            context,
            context.output_path.read_bytes(),
            snapshot_sha256=snapshot.sha256,
            adapter_id=inspected.evidence.adapter_id,
            adapter_version=inspected.evidence.adapter_version,
            input_hashes={
                key: hash_file(path) for key, path in inspected.evidence.inputs.items()
            },
            output_hashes={
                key: hash_file(path) for key, path in inspected.evidence.outputs.items()
            },
            attestation_sha256=hash_file(inspected.evidence.attestation)
            if inspected.evidence.attestation
            else None,
        ):
            raise BuildJobError("stage proof mismatch")
        return True

    def execute(self, context: StageContext) -> None:
        snapshot = self.snapshots.load(context.project_id, context.snapshot_id)
        self._prior(context, snapshot)
        inspected = self._inspection(context, snapshot)
        if inspected.state != EffectState.ABSENT or context.output_path.exists():
            raise UncertainResult(
                "effect already exists or lacks authoritative absence"
            )
        context.renew_lease()
        self._port(context.stage).execute(context, snapshot)
