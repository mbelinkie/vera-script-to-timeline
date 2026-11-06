"""Explicitly authorized, single-target Studio v2 composition boundary.

Native effects are delegated to the existing accepted #177/#109 route; no
native effect is inferred from a JSON file alone. One-use local reservation and
intent survive uncertain interruptions. A separately injected native readback
authority must confirm the saved/reopened target for final stage completion.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .build_composition import (
    EffectState,
    FrozenBuildSnapshot,
    Inspection,
    StageEvidence,
)
from .build_jobs import (
    BuildJobError,
    NeedsAction,
    StageContext,
    UncertainResult,
    publish_immutable_output,
)
from .build_package_stage import VerifyPackageStagePort, package_receipt, package_root
from .build_stage_receipt import canonical_json, hash_file
from .workflow_v2 import load_verified_package_v2, run_workflow_delivery_v2
from .workflow_v2_parent import PARENT_STATE_ROOT
from .workflow_v2_parent import status as parent_status


@dataclass(frozen=True)
class NativeAuthorization:
    project_id: str
    snapshot_id: str
    attestation_sha256: str
    request_id: str
    approved_nonproduction: bool = False
    route: str = "None"


class NativeDriver(Protocol):
    def preflight(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        """Read-only, supported native app/package/target collision preflight."""

    def start(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        """One authorized existing #177 native operation, never an auto-retry."""

    def inspect_build(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        """Independent connected native status, not just an output file."""

    def readback(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        """Independent non-mutating native save/reopen and exact timing readback."""


class InjectedResolveDriver:
    """Installed None-mode Resolve API, with required caller-provided readback.

    The accepted `run_workflow_delivery_v2` owns native mutation. This facade
    does not pretend its returned result alone survives a lost response. A
    concrete host integration must supply independent target inspection.
    """

    def __init__(
        self,
        resolve: Any,
        inspect_native: Callable[[Path, str, str], Mapping[str, Any]],
        verify_native: Callable[[Path, str, str], Mapping[str, Any]],
        *,
        allow_fractional_native: bool = False,
    ) -> None:
        self.resolve = resolve
        self.inspect_native = inspect_native
        self.verify_native = verify_native
        self.allow_fractional_native = allow_fractional_native

    def preflight(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        return run_workflow_delivery_v2(
            self.resolve,
            attestation,
            digest,
            action="preflight",
            external_scripting="None",
            allow_fractional_native=self.allow_fractional_native,
        )

    def start(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        return run_workflow_delivery_v2(
            self.resolve,
            attestation,
            digest,
            action="build",
            authorize_new_nonproduction=True,
            external_scripting="None",
            allow_fractional_native=self.allow_fractional_native,
        )

    def inspect_build(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        return self.inspect_native(attestation, digest, request_id)

    def readback(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        return self.verify_native(attestation, digest, request_id)


def _stage_file(
    context: StageContext, snapshot: FrozenBuildSnapshot, stage: str, name: str
) -> Path:
    return snapshot.write_root / context.job_id / stage / name


def _target(
    context: StageContext, snapshot: FrozenBuildSnapshot
) -> tuple[Path, str, dict[str, Any]]:
    attestation = VerifyPackageStagePort.attestation(context, snapshot)
    digest = hash_file(attestation)
    verified = load_verified_package_v2(attestation, digest)
    if (
        verified.root != package_root(context, snapshot)
        or verified.attestation["buildId"] != snapshot.build_id
    ):
        raise BuildJobError("Studio request targets an unrelated package")
    return attestation, digest, verified.attestation


def _verified_result(
    result: Mapping[str, Any], attestation: Mapping[str, Any], digest: str
) -> bool:
    return (
        result.get("status") == "verified"
        and result.get("verified") is True
        and result.get("discrepancies") == []
        and result.get("buildId") == attestation["buildId"]
        and result.get("attestationSha256") == digest
        and result.get("projectName") == attestation["projectName"]
        and result.get("timelineName") == attestation["timelineName"]
    )


class _HostReservation:
    """Host-wide shared parent lock; retain unresolved records indefinitely."""

    def __init__(self, root: Path) -> None:
        self.root = root.absolute()

    def reserve(self, request_id: str, attestation_digest: str) -> None:
        if any(path.is_symlink() for path in (self.root, *self.root.parents)):
            raise BuildJobError("untrusted Resolve reservation directory")
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "dispatch.lock").open("a+") as guard:
            fcntl.flock(guard, fcntl.LOCK_EX)
            parent = self.root / "active.json"
            if parent.exists():
                active = json.loads(parent.read_bytes())
                if set(active) != {"requestPath", "requestSha256"}:
                    raise NeedsAction("untrusted host-wide Resolve parent reservation")
                try:
                    state = parent_status(
                        Path(active["requestPath"]), active["requestSha256"]
                    )
                except Exception as error:
                    raise UncertainResult(
                        "cannot verify prior native parent state"
                    ) from error
                if state.get("state") not in ("terminal", "not_started"):
                    raise NeedsAction(
                        "another native parent request remains active or uncertain"
                    )
            record = self.root / "composition-active.json"
            if record.exists():
                prior = json.loads(record.read_bytes())
                if not isinstance(prior, dict) or set(prior) != {
                    "requestId",
                    "attestationSha256",
                }:
                    raise NeedsAction("untrusted existing composition reservation")
                if not (
                    self.root / f"composition-finished-{prior['requestId']}.json"
                ).is_file():
                    raise NeedsAction("prior native composition has unresolved effects")
            temporary = self.root / f".composition-active-{request_id}.json"
            publish_immutable_output(
                temporary,
                canonical_json(
                    {
                        "requestId": request_id,
                        "attestationSha256": attestation_digest,
                    }
                ),
            )
            os.replace(temporary, record)
            directory = os.open(self.root, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)

    def finish(self, request_id: str, digest: str) -> None:
        active = self.root / "composition-active.json"
        if not active.is_file() or json.loads(active.read_bytes()) != {
            "requestId": request_id,
            "attestationSha256": digest,
        }:
            raise UncertainResult("native reservation identity changed")
        publish_immutable_output(
            self.root / f"composition-finished-{request_id}.json",
            canonical_json(
                {
                    "requestId": request_id,
                    "attestationSha256": digest,
                    "status": "verified",
                }
            ),
        )


class BuildStudioStagePort:
    def __init__(
        self,
        authorization: NativeAuthorization,
        driver: NativeDriver,
        *,
        host_state: Path = PARENT_STATE_ROOT,
    ) -> None:
        self.authorization = authorization
        self.driver = driver
        self.reservation = _HostReservation(host_state)

    def _authorized(self, snapshot: FrozenBuildSnapshot, digest: str) -> None:
        auth = self.authorization
        if (
            not auth.approved_nonproduction
            or auth.route != "None"
            or auth.project_id != snapshot.project_id
            or auth.snapshot_id != snapshot.snapshot_id
            or auth.attestation_sha256 != digest
        ):
            raise NeedsAction(
                "explicit frozen nonproduction native authorization "
                "and installed None route required"
            )

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "building_resolve_timeline":
            raise BuildJobError("wrong native build stage")
        attestation, digest, target = _target(context, snapshot)
        intent = _stage_file(context, snapshot, context.stage, "intent.json")
        result_path = _stage_file(
            context, snapshot, context.stage, "native-result.json"
        )
        if not intent.exists():
            if result_path.exists():
                return Inspection(
                    EffectState.UNCERTAIN, reason="native result without one-use intent"
                )
            return Inspection(EffectState.ABSENT)
        if intent.read_bytes() != canonical_json(
            {
                "schemaVersion": "vera-native-build-intent/v1",
                "stageKey": context.stage_key,
                "requestId": self.authorization.request_id,
                "attestationSha256": digest,
                "snapshotSha256": snapshot.sha256,
                "projectName": target["projectName"],
            }
        ):
            raise BuildJobError("native one-use request identity changed")
        if not result_path.is_file():
            # The response can be lost after the saved/reopened side effect.
            # Only independently verified connected native readback may recover
            # the receipt, never absence or a blind re-dispatch.
            live = self.driver.inspect_build(
                attestation, digest, self.authorization.request_id
            )
            if not _verified_result(live, target, digest):
                return Inspection(
                    EffectState.UNCERTAIN,
                    reason="native intent exists without independently "
                    "verified terminal result",
                )
            context.renew_lease()
            publish_immutable_output(result_path, canonical_json(dict(live)))
        stored = json.loads(result_path.read_bytes())
        if not _verified_result(stored, target, digest):
            return Inspection(
                EffectState.NEEDS_ACTION,
                reason="unverified/partial native target retained; "
                "inspect before retry",
            )
        live = self.driver.inspect_build(
            attestation, digest, self.authorization.request_id
        )
        if not _verified_result(live, target, digest):
            return Inspection(
                EffectState.UNCERTAIN, reason="native target no longer verified on host"
            )
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="resolve-v2",
                adapter_version="injected-none/v2",
                inputs={
                    "attestation": attestation,
                    "packageVerification": package_receipt(context, snapshot),
                },
                outputs={"intent": intent, "nativeResult": result_path},
                attestation=attestation,
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        attestation, digest, target = _target(context, snapshot)
        self._authorized(snapshot, digest)
        if (
            not self.authorization.request_id
            or any(
                character
                not in (
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"
                    "0123456789_-"
                )
                for character in self.authorization.request_id
            )
            or len(self.authorization.request_id) > 128
        ):
            raise BuildJobError("invalid native request identity")
        if _stage_file(context, snapshot, context.stage, "intent.json").exists():
            raise UncertainResult(
                "native one-use intent exists; refuse a second mutation"
            )
        context.renew_lease()
        self.reservation.reserve(self.authorization.request_id, digest)
        intent = _stage_file(context, snapshot, context.stage, "intent.json")
        publish_immutable_output(
            intent,
            canonical_json(
                {
                    "schemaVersion": "vera-native-build-intent/v1",
                    "stageKey": context.stage_key,
                    "requestId": self.authorization.request_id,
                    "attestationSha256": digest,
                    "snapshotSha256": snapshot.sha256,
                    "projectName": target["projectName"],
                }
            ),
        )
        preflight = self.driver.preflight(
            attestation, digest, self.authorization.request_id
        )
        if (
            preflight.get("status") != "preflight_passed"
            or preflight.get("attestationSha256") != digest
        ):
            raise NeedsAction(
                "read-only native preflight did not pass; reserved target retained"
            )
        context.renew_lease()
        result = self.driver.start(attestation, digest, self.authorization.request_id)
        result_path = _stage_file(
            context, snapshot, context.stage, "native-result.json"
        )
        publish_immutable_output(result_path, canonical_json(dict(result)))
        if not _verified_result(result, target, digest):
            raise NeedsAction(
                "native build returned unverified or partial target; "
                "do not retry mutation"
            )
        self.reservation.finish(self.authorization.request_id, digest)


class VerifyStudioStagePort:
    """Distinct independent readback of the same already-created target."""

    def __init__(
        self, authorization: NativeAuthorization, driver: NativeDriver
    ) -> None:
        self.authorization = authorization
        self.driver = driver

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "verifying_timeline":
            raise BuildJobError("wrong native verification stage")
        attestation, digest, target = _target(context, snapshot)
        record = _stage_file(context, snapshot, context.stage, "native-readback.json")
        if not record.exists():
            return Inspection(EffectState.ABSENT)
        saved = json.loads(record.read_bytes())
        if not _verified_result(saved, target, digest):
            return Inspection(
                EffectState.NEEDS_ACTION, reason="native readback has discrepancies"
            )
        current = self.driver.readback(
            attestation, digest, self.authorization.request_id
        )
        if not _verified_result(current, target, digest):
            return Inspection(
                EffectState.UNCERTAIN,
                reason="independent native readback no longer matches",
            )
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="resolve-v2-readback",
                adapter_version="injected-none-readback/v2",
                inputs={
                    "attestation": attestation,
                    "nativeResult": _stage_file(
                        context,
                        snapshot,
                        "building_resolve_timeline",
                        "native-result.json",
                    ),
                },
                outputs={"nativeReadback": record},
                attestation=attestation,
            ),
        )

    def execute(self, context: StageContext, snapshot: FrozenBuildSnapshot) -> None:
        attestation, digest, target = _target(context, snapshot)
        if (
            not self.authorization.approved_nonproduction
            or self.authorization.snapshot_id != snapshot.snapshot_id
            or self.authorization.attestation_sha256 != digest
        ):
            raise NeedsAction(
                "independent native readback is not bound to authorization"
            )
        context.renew_lease()
        result = self.driver.readback(
            attestation, digest, self.authorization.request_id
        )
        if not _verified_result(result, target, digest):
            raise NeedsAction("native save/reopen discrepancy; retain old target")
        publish_immutable_output(
            _stage_file(context, snapshot, context.stage, "native-readback.json"),
            canonical_json(dict(result)),
        )
