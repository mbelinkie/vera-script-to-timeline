"""Bounded foreground bridge to the installed #302 Local Resolve parent.

The release and immutable Local request are prepared by the existing v2 CLI.
This adapter never prepares a second request, retries a native write, runs a
daemon, or treats the parent's result as a fresh independent readback.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from .build_jobs import NeedsAction, UncertainResult
from .build_stage_receipt import hash_file
from .resolve_native_owner import NativeOwnerError
from .workflow_v2 import load_verified_package_v2
from .workflow_v2_parent import ParentUnresolvedError, _request, start, status, wait


class ParentStudioDriver:
    """Use one immutable #302 request, with separately supplied app readback.

    ``reopened_readback`` must independently re-inspect the saved and reopened
    native target; no saved JSON, parent report or caller assertion substitutes
    for that connected inspector. ``None`` deliberately refuses verification.
    """

    def __init__(
        self,
        request_path: Path,
        request_sha256: str,
        request_id: str,
        resolve_python: Path,
        *,
        reopened_readback: Callable[[Path, str, str], Mapping[str, Any]] | None = None,
        wait_seconds: float = 0,
    ) -> None:
        if not 0 <= wait_seconds <= 50:
            raise ValueError("parent foreground wait must be between 0 and 50 seconds")
        self.request_path = request_path.absolute()
        self.request_sha256 = request_sha256
        self.request_id = request_id
        self.resolve_python = resolve_python
        self.reopened_readback = reopened_readback
        self.wait_seconds = wait_seconds

    def _validate(self, attestation: Path, digest: str, request_id: str) -> None:
        if request_id != self.request_id:
            raise NeedsAction("parent request identity changed")
        request = _request(self.request_path, self.request_sha256)
        package = load_verified_package_v2(attestation, digest)
        if (
            self.request_path
            != self.request_path.parent.parent / "vera-delivery-v2" / "request.json"
            or request.get("action") != "build"
            or request.get("authorizeNewNonproduction") is not True
            or request.get("externalScripting") != "Local"
            or request.get("attestationPath") != str(attestation.absolute())
            or request.get("attestationSha256") != digest
            or request.get("packageDir") != str(package.root)
            or request.get("projectName") != package.attestation["projectName"]
            or request.get("timelineName") != package.attestation["timelineName"]
            or request.get("projectName") != request.get("timelineName")
        ):
            raise NeedsAction(
                "Local parent request is not the exact disposable package"
            )
        if hash_file(attestation) != digest:
            raise NeedsAction("Local native attestation changed")

    def preflight(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        self._validate(attestation, digest, request_id)
        return {"status": "preflight_passed", "attestationSha256": digest}

    def start(
        self,
        attestation: Path,
        digest: str,
        request_id: str,
        *,
        before_dispatch: Callable[[Path], None] | None = None,
    ) -> Mapping[str, Any]:
        self._validate(attestation, digest, request_id)
        # #302 start is intentionally idempotent: if someone invokes it again
        # for a completed request, it returns the *old* success. A new VERA
        # native intent must never mistake that old result for its own write.
        request = _request(self.request_path, self.request_sha256)
        session = Path(request["evidenceDir"]) / "parent.json"
        if session.exists() or session.is_symlink():
            raise UncertainResult("Local parent request already consumed; inspect only")
        # #302 locks the host and runs the qualified Local worker. Repeated
        # starts are read-only in #302; this adapter refuses to credit them.
        preparing = False

        def prepare(root: Path) -> None:
            nonlocal preparing
            assert before_dispatch is not None
            preparing = True
            before_dispatch(root)

        try:
            result = start(
                self.request_path,
                self.request_sha256,
                self.resolve_python,
                independent_disposable=True,
                before_dispatch=prepare if before_dispatch is not None else None,
            )
        except ParentUnresolvedError as error:
            raise NeedsAction(
                "another native parent remains active or uncertain"
            ) from error
        except NativeOwnerError as error:
            if preparing:
                raise
            if error.reason == "owner_busy":
                raise NeedsAction(
                    "Resolve is busy; try again when it is idle"
                ) from error
            raise NeedsAction(str(error)) from error
        if before_dispatch is not None and not preparing:
            if result.get("state") == "busy":
                raise NeedsAction("another Local parent is dispatching")
            raise UncertainResult("Local parent returned without this attempt's intent")
        return self._terminal_result(result)

    @staticmethod
    def _terminal_result(result: Mapping[str, Any]) -> Mapping[str, Any]:
        if (
            result.get("state") == "terminal"
            and result.get("verified") is True
            and isinstance(result.get("result"), dict)
        ):
            return result["result"]  # type: ignore[no-any-return]
        return {
            "status": "unknown",
            "verified": False,
            "parentState": result.get("state"),
        }

    def inspect_build(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        self._validate(attestation, digest, request_id)
        return self._terminal_result(status(self.request_path, self.request_sha256))

    def resume(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        """Foreground wait, never dispatch; returns UNKNOWN on unresolved exit."""
        self._validate(attestation, digest, request_id)
        return self._terminal_result(
            wait(self.request_path, self.request_sha256, self.wait_seconds)
        )

    def readback(
        self, attestation: Path, digest: str, request_id: str
    ) -> Mapping[str, Any]:
        self._validate(attestation, digest, request_id)
        if (
            self.inspect_build(attestation, digest, request_id).get("verified")
            is not True
        ):
            raise UncertainResult(
                "Local parent lacks independently correlated completion"
            )
        if self.reopened_readback is None:
            raise NeedsAction(
                "independent connected reopened Studio inspector required"
            )
        return self.reopened_readback(attestation, digest, request_id)
