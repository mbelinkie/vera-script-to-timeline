"""Explicitly authorized, single-target Studio v2 composition boundary.

Native effects are delegated to the existing accepted #177/#109 route; no
native effect is inferred from a JSON file alone. One-use local reservation and
intent survive uncertain interruptions. A separately injected native readback
authority must confirm the saved/reopened target for final stage completion.
"""

from __future__ import annotations

import fcntl
import json
import math
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
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
from .build_studio_parent_driver import ParentStudioDriver
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
    # Older injected-None hosts do not have a backend submission. The Local
    # parent route requires each of these scoped, independently supplied pins.
    job_id: str | None = None
    target_id: str | None = None
    expires_at: float | None = None
    current_authority: Callable[[], bool] | None = field(default=None, repr=False)


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


def _intent_body(
    context: StageContext,
    snapshot: FrozenBuildSnapshot,
    auth: NativeAuthorization,
    target: Mapping[str, Any],
    digest: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "vera-native-build-intent/v1",
        "stageKey": context.stage_key,
        "jobId": snapshot.build_id,
        "targetId": auth.target_id or target["timelineName"],
        "requestId": auth.request_id,
        "attestationSha256": digest,
        "snapshotSha256": snapshot.sha256,
        "projectName": target["projectName"],
        "timelineName": target["timelineName"],
        "route": auth.route,
    }


def _check_authority(
    auth: NativeAuthorization,
    context: StageContext,
    snapshot: FrozenBuildSnapshot,
    digest: str,
) -> None:
    if (
        not auth.approved_nonproduction
        or auth.route not in ("None", "Local")
        or auth.project_id != snapshot.project_id
        or auth.snapshot_id != snapshot.snapshot_id
        or auth.attestation_sha256 != digest
        or (auth.job_id is not None and auth.job_id != snapshot.build_id)
        or (auth.target_id is None) != (auth.job_id is None)
    ):
        raise NeedsAction(
            "explicit exact native job/snapshot/attestation authority required"
        )
    if auth.target_id is not None:
        try:
            if hash_file(snapshot.file("submission")) != snapshot.input_hashes.get(
                "submission"
            ):
                raise NeedsAction("frozen native submission bytes changed")
            submission = json.loads(snapshot.file("submission").read_bytes())
        except (OSError, ValueError) as error:
            raise NeedsAction("native submission authority unavailable") from error
        if (
            not isinstance(submission, dict)
            or submission.get("jobId") != snapshot.build_id
            or submission.get("targetId") != auth.target_id
            or submission.get("mode") != "studio"
        ):
            raise NeedsAction("native target does not match frozen submission")
    if auth.route == "Local" and (
        not auth.job_id
        or not auth.target_id
        or auth.expires_at is None
        or auth.current_authority is None
    ):
        raise NeedsAction(
            "Local native authority requires current job/target and expiry"
        )
    if auth.expires_at is not None and (
        type(auth.expires_at) not in (int, float)
        or not math.isfinite(auth.expires_at)
        or time.time() >= auth.expires_at
    ):
        raise NeedsAction("native authorization expired")
    if auth.current_authority is not None and auth.current_authority() is not True:
        raise NeedsAction("native current authority revoked or stale")


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
            self.reserve_locked(request_id, attestation_digest)

    def reserve_locked(self, request_id: str, attestation_digest: str) -> None:
        """Reserve under the dispatch lock already held by the Local parent."""
        # A request ID identifies one native mutation for the lifetime of
        # this host state, even after a previous request finished. Otherwise
        # a new job could silently reuse a completed one-use authorization.
        finished = self.root / f"composition-finished-{request_id}.json"
        if finished.exists() or finished.is_symlink():
            raise NeedsAction("native request ID was already consumed")
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
            if state["state"] == "terminal" and state.get("verified") is not True:
                raise NeedsAction("prior native parent ended unverified")
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
        finished = self.root / f"composition-finished-{request_id}.json"
        expected = canonical_json(
            {
                "requestId": request_id,
                "attestationSha256": digest,
                "status": "verified",
            }
        )
        if finished.exists() or finished.is_symlink():
            # Re-reading an older verified job must stay possible after a new
            # request takes the active host slot. Never release that new slot.
            hash_file(finished)
            if finished.read_bytes() != expected:
                raise UncertainResult("native finished reservation differs")
            return
        active = self.root / "composition-active.json"
        if not active.is_file() or json.loads(active.read_bytes()) != {
            "requestId": request_id,
            "attestationSha256": digest,
        }:
            raise UncertainResult("native reservation identity changed")
        publish_immutable_output(finished, expected)


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

    def _authorized(
        self, context: StageContext, snapshot: FrozenBuildSnapshot, digest: str
    ) -> None:
        _check_authority(self.authorization, context, snapshot, digest)
        if self.authorization.route == "Local" and not isinstance(
            self.driver, ParentStudioDriver
        ):
            raise NeedsAction("Local route requires #302 guarded parent")
        if self.authorization.route == "None" and isinstance(
            self.driver, ParentStudioDriver
        ):
            raise NeedsAction("injected None route cannot dispatch Local parent")

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
        # Reconciliation is read-only, but it cannot promote a result after
        # local native authorization or the current frozen scope was revoked.
        self._authorized(context, snapshot, digest)
        if intent.read_bytes() != canonical_json(
            _intent_body(context, snapshot, self.authorization, target, digest)
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
                adapter_version=(
                    "parent-local/v1"
                    if self.authorization.route == "Local"
                    else "injected-none/v2"
                ),
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
        self._authorized(context, snapshot, digest)
        if (
            not self.authorization.request_id
            or any(
                character
                not in (
                    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
                )
                for character in self.authorization.request_id
            )
            or len(self.authorization.request_id) > 128
        ):
            raise BuildJobError("invalid native request identity")
        intent = _stage_file(context, snapshot, context.stage, "intent.json")
        if intent.exists():
            raise UncertainResult(
                "native one-use intent exists; refuse a second mutation"
            )
        context.renew_lease()
        request_id = self.authorization.request_id
        intent_bytes = canonical_json(
            _intent_body(context, snapshot, self.authorization, target, digest)
        )

        if isinstance(self.driver, ParentStudioDriver):

            def prepare_dispatch(root: Path) -> None:
                if root.absolute() != self.reservation.root:
                    raise BuildJobError(
                        "Local parent and composition state roots differ"
                    )
                if intent.exists() or intent.is_symlink():
                    raise UncertainResult("native one-use intent already exists")
                context.renew_lease()
                self._authorized(context, snapshot, digest)
                self.reservation.reserve_locked(request_id, digest)
                publish_immutable_output(intent, intent_bytes)

            result = self.driver.start(
                attestation, digest, request_id, before_dispatch=prepare_dispatch
            )
        else:
            self.reservation.reserve(request_id, digest)
            publish_immutable_output(intent, intent_bytes)
            preflight = self.driver.preflight(attestation, digest, request_id)
            if (
                preflight.get("status") != "preflight_passed"
                or preflight.get("attestationSha256") != digest
            ):
                raise NeedsAction(
                    "read-only native preflight did not pass; reserved target retained"
                )
            context.renew_lease()
            self._authorized(context, snapshot, digest)
            result = self.driver.start(attestation, digest, request_id)
        result_path = _stage_file(
            context, snapshot, context.stage, "native-result.json"
        )
        if not _verified_result(result, target, digest):
            # A Local parent can still be live after this foreground call.
            # Retain intent only; its later status can be reattached read-only.
            raise UncertainResult(
                "native build live, unknown or unverified; "
                "inspect existing parent, never restart"
            )
        publish_immutable_output(result_path, canonical_json(dict(result)))
        # The synchronous build result alone cannot release host-wide native
        # exclusion. Retain the reservation until a separate connected
        # save/reopen readback has verified this same target.


class VerifyStudioStagePort:
    """Distinct independent readback of the same already-created target."""

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

    def _authorized(
        self, context: StageContext, snapshot: FrozenBuildSnapshot, digest: str
    ) -> None:
        _check_authority(self.authorization, context, snapshot, digest)
        if self.authorization.route == "Local" and not isinstance(
            self.driver, ParentStudioDriver
        ):
            raise NeedsAction("Local readback requires #302 guarded parent")

    def inspect(
        self, context: StageContext, snapshot: FrozenBuildSnapshot
    ) -> Inspection:
        if context.stage != "verifying_timeline":
            raise BuildJobError("wrong native verification stage")
        attestation, digest, target = _target(context, snapshot)
        self._authorized(context, snapshot, digest)
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
        context.renew_lease()
        self.reservation.finish(self.authorization.request_id, digest)
        return Inspection(
            EffectState.VERIFIED,
            StageEvidence(
                adapter_id="resolve-v2-readback",
                adapter_version=(
                    "parent-local-readback/v1"
                    if self.authorization.route == "Local"
                    else "injected-none-readback/v2"
                ),
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
        self._authorized(context, snapshot, digest)
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
