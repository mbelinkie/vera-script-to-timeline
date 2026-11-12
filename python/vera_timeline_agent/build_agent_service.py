"""Opt-in, loopback-only #382 transport for already authorized frozen jobs.

Transport leases never authorize native effects. This runner executes at most one
local stage, with explicitly injected #157 ports, and reports untrusted progress.
There is deliberately no background daemon, native auto-consent, or implicit retry.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import (
    HTTPRedirectHandler,
    ProxyHandler,
    Request,
    build_opener,
)

from .build_compile_stage import CompileStagePort
from .build_composition import BuildComposition, SnapshotRepository, StagePort
from .build_jobs import CORE_STAGES, STUDIO_STAGES, BuildJobStore, BuildRequest
from .build_media_stage import MediaStagePort
from .build_narration_stage import NarrationStagePort
from .build_package_stage import PackageStagePort, VerifyPackageStagePort
from .build_studio_stage import (
    BuildStudioStagePort,
    NativeAuthorization,
    VerifyStudioStagePort,
)
from .build_submission_inputs import (
    FrozenInputRefusal,
    TrustedBuildInputAuthority,
    checked_compiler_dependencies,
    frozen_source_file,
)

_SHA = re.compile(r"sha256:[a-f0-9]{64}\Z")
_AGENT = re.compile(r"sttag_[A-Za-z0-9_-]{43}\Z")
_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
_MAX_RESPONSE = 2 * 1024 * 1024


class AgentTransportRefusal(RuntimeError):
    """No remote error message, secret, local path, or SQL detail is exposed."""


@dataclass(frozen=True)
class QualifiedStagePipeline:
    """Real #157 ports supplied by the trusted local host, never the manifest.

    Media and provider authorization remain the ports' responsibility. Native
    ports must share one explicit permission and connected driver; this class
    does not mint permission or start Resolve.
    """

    narration: NarrationStagePort
    media: MediaStagePort
    package: PackageStagePort
    studio_build: BuildStudioStagePort | None = None
    studio_verify: VerifyStudioStagePort | None = None

    def resolved(
        self,
    ) -> tuple[dict[str, StagePort], dict[str, str], NativeAuthorization | None]:
        if (
            type(self.narration) is not NarrationStagePort
            or type(self.media) is not MediaStagePort
            or type(self.package) is not PackageStagePort
        ):
            raise AgentTransportRefusal("qualified core build ports required")
        ports: dict[str, StagePort] = {
            "generating_speech": self.narration,
            "resolving_media": self.media,
            "compiling": CompileStagePort(),
            "writing_interchange": self.package,
            "verifying_import_package": VerifyPackageStagePort(),
        }
        versions = {
            "narration-v2": self.narration.service.provider.adapter_version,
            "prepare-media-v2": "authoring-media-preparation/v1",
            "compiler-v2": "compiler/v2",
            "v2-package": "v2-package/v1",
            "v2-attestation": "vera-injected-delivery-attestation/v2",
        }
        if (self.studio_build is None) != (self.studio_verify is None):
            raise AgentTransportRefusal("both native build and readback ports required")
        native: NativeAuthorization | None = None
        if self.studio_build is not None and self.studio_verify is not None:
            if (
                type(self.studio_build) is not BuildStudioStagePort
                or type(self.studio_verify) is not VerifyStudioStagePort
                or self.studio_build.driver is not self.studio_verify.driver
                or self.studio_build.authorization != self.studio_verify.authorization
            ):
                raise AgentTransportRefusal("native ports do not share one authority")
            native = self.studio_build.authorization
            ports.update(
                building_resolve_timeline=self.studio_build,
                verifying_timeline=self.studio_verify,
            )
            versions.update(
                **{
                    "resolve-v2": "injected-none/v2",
                    "resolve-v2-readback": "injected-none-readback/v2",
                }
            )
        return ports, versions, native


def _uuid(value: str) -> str:
    if not isinstance(value, str) or _UUID.fullmatch(value) is None:
        raise AgentTransportRefusal("invalid scoped job identifier")
    return value


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise AgentTransportRefusal("duplicate transport field")
        obj[key] = value
    return obj


def _validated_selected_pins(raw: object) -> dict[str, tuple[str, str]]:
    """Strict canonical claims; the trusted accepted-source lookup is separate."""
    if not isinstance(raw, list) or len(raw) > 256:
        raise AgentTransportRefusal("invalid selected source pins")
    pins: dict[str, tuple[str, str]] = {}
    for entry in raw:
        if not isinstance(entry, dict) or set(entry) != {
            "sourceId",
            "revision",
            "sha256",
        }:
            raise AgentTransportRefusal("invalid selected source pin shape")
        source_id, revision, digest = (
            entry["sourceId"],
            entry["revision"],
            entry["sha256"],
        )
        if (
            not isinstance(source_id, str)
            or _UUID.fullmatch(source_id) is None
            or not isinstance(revision, str)
            or not 1 <= len(revision) <= 256
            or revision != revision.strip()
            or any(ord(ch) < 32 or ord(ch) == 127 or ch in "/\\" for ch in revision)
            or not isinstance(digest, str)
            or _SHA.fullmatch(digest) is None
            or source_id in pins
        ):
            raise AgentTransportRefusal("invalid selected source pin identity")
        pins[source_id] = (revision, digest)
    if list(pins) != sorted(pins):
        raise AgentTransportRefusal("noncanonical selected source ordering")
    return pins


def _same_frozen_authority(
    original: Mapping[str, Any], current: Mapping[str, Any]
) -> bool:
    return all(
        original.get(key) == current.get(key)
        for key in (
            "projectId",
            "jobId",
            "targetId",
            "snapshotDigest",
            "buildClass",
            "mode",
            "documentRevision",
            "documentDigest",
            "settingsRevision",
            "settingsDigest",
            "selectedSources",
        )
    )


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *_args: Any, **_kwargs: Any) -> None:
        return None


@dataclass(frozen=True)
class AgentCredentials:
    project_id: str
    token: str = field(repr=False)
    version: int = 1

    def __post_init__(self) -> None:
        _uuid(self.project_id)
        if (
            _AGENT.fullmatch(self.token) is None
            or type(self.version) is not int
            or self.version < 1
        ):
            raise AgentTransportRefusal("invalid local agent credentials")


class BuildTransport(Protocol):
    def poll(self) -> list[str]: ...
    def claim(self, job_id: str) -> tuple[int, str]: ...
    def frozen(self, job_id: str, epoch: int) -> dict[str, Any]: ...
    def progress(
        self,
        job_id: str,
        epoch: int,
        stage: str,
        status: str,
        digest: str | None,
        reason: str | None,
    ) -> None: ...


class LoopbackBuildTransport:
    """Private-only HTTP. No proxy, redirects, or credentials on disk."""

    def __init__(self, base_url: str, credentials: AgentCredentials) -> None:
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "http"
            or parsed.hostname != "127.0.0.1"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path != ""
            or parsed.query
            or parsed.fragment
            or parsed.port is None
            or parsed.port < 1024
            or parsed.port > 65535
            or parsed.netloc != f"127.0.0.1:{parsed.port}"
        ):
            raise AgentTransportRefusal("private loopback transport required")
        self._base = base_url
        self._credentials = credentials
        self._opener = build_opener(ProxyHandler({}), _NoRedirect())

    def _call(
        self, method: str, path: str, payload: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        data = (
            json.dumps(payload, separators=(",", ":")).encode()
            if payload is not None
            else None
        )
        headers = {
            "Authorization": f"Bearer {self._credentials.token}",
            "X-Agent-Credential-Version": str(self._credentials.version),
        }
        if data is not None:
            headers["Content-Type"] = "application/json"
        request = Request(self._base + path, data=data, headers=headers, method=method)
        try:
            with self._opener.open(request, timeout=8) as response:
                if response.status not in (200, 202):
                    raise AgentTransportRefusal("agent transport refused")
                raw = response.read(_MAX_RESPONSE + 1)
                if (
                    len(raw) > _MAX_RESPONSE
                    or response.headers.get("Cache-Control") != "no-store"
                ):
                    raise AgentTransportRefusal("unsafe agent response")
            result: Any = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique)
            if not isinstance(result, dict):
                raise AgentTransportRefusal("invalid agent response")
            return result
        except (HTTPError, URLError, UnicodeError, ValueError, OSError):
            raise AgentTransportRefusal(
                "agent transport unavailable or refused"
            ) from None

    def _root(self) -> str:
        return f"/v1/agent/projects/{self._credentials.project_id}"

    def poll(self) -> list[str]:
        jobs = self._call("GET", self._root() + "/queue").get("jobIds")
        if not isinstance(jobs, list) or len(jobs) > 50:
            raise AgentTransportRefusal("invalid queue response")
        return [_uuid(item) for item in jobs]

    def claim(self, job_id: str) -> tuple[int, str]:
        value = self._call("POST", self._root() + f"/jobs/{_uuid(job_id)}/claim")
        epoch, digest = value.get("leaseEpoch"), value.get("snapshotDigest")
        if (
            type(epoch) is not int
            or epoch < 1
            or not isinstance(digest, str)
            or not _SHA.fullmatch(digest)
        ):
            raise AgentTransportRefusal("invalid claim response")
        return epoch, digest

    def frozen(self, job_id: str, epoch: int) -> dict[str, Any]:
        if type(epoch) is not int or epoch < 1:
            raise AgentTransportRefusal("invalid lease epoch")
        return self._call(
            "GET", self._root() + f"/jobs/{_uuid(job_id)}/leases/{epoch}/frozen"
        )

    def progress(
        self,
        job_id: str,
        epoch: int,
        stage: str,
        status: str,
        digest: str | None,
        reason: str | None,
    ) -> None:
        if type(epoch) is not int or epoch < 1:
            raise AgentTransportRefusal("invalid lease epoch")
        self._call(
            "POST",
            self._root() + f"/jobs/{_uuid(job_id)}/leases/{epoch}/progress",
            {
                "status": status,
                "stageKey": stage,
                "receiptDigest": digest,
                "reasonCode": reason,
            },
        )


def _private_root(root: Path) -> Path:
    path = root.absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise AgentTransportRefusal("unsafe local build root")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    facts = path.stat()
    if (
        not stat.S_ISDIR(facts.st_mode)
        or (facts.st_mode & 0o777) != 0o700
        or facts.st_uid != os.getuid()
    ):
        raise AgentTransportRefusal("private build root required")
    return path


def _immutable(path: Path, raw: bytes) -> None:
    if len(raw) < 1 or len(raw) > 512 * 1024 or path.is_symlink():
        raise AgentTransportRefusal("invalid frozen input")
    try:
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
        )
    except FileExistsError:
        facts = path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(facts.st_mode)
            or facts.st_nlink != 1
            or (facts.st_mode & 0o777) != 0o600
            or path.read_bytes() != raw
        ):
            raise AgentTransportRefusal("frozen local input changed") from None
        return
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _checked_frozen(
    value: dict[str, Any], project_id: str, job_id: str, expected: str | None = None
) -> dict[str, Any]:
    if (
        value.get("projectId") != project_id
        or value.get("jobId") != job_id
        or value.get("mode") not in ("free", "studio")
        or value.get("buildClass") not in ("preview", "release")
        or not isinstance(value.get("documentJson"), str)
        or not isinstance(value.get("settingsJson"), str)
        or type(value.get("documentRevision")) is not int
        or value["documentRevision"] < 0
        or type(value.get("settingsRevision")) is not int
        or value["settingsRevision"] < 1
    ):
        raise AgentTransportRefusal("untrusted or unsupported frozen manifest")
    _validated_selected_pins(value.get("selectedSources"))
    for name, key in (
        ("documentJson", "documentDigest"),
        ("settingsJson", "settingsDigest"),
    ):
        digest = value.get(key)
        if (
            not isinstance(digest, str)
            or _SHA.fullmatch(digest) is None
            or "sha256:" + hashlib.sha256(value[name].encode("utf-8")).hexdigest()
            != digest
        ):
            raise AgentTransportRefusal("frozen input digest mismatch")
    snapshot = value.get("snapshotDigest")
    if (
        not isinstance(snapshot, str)
        or _SHA.fullmatch(snapshot) is None
        or (expected and snapshot != expected)
    ):
        raise AgentTransportRefusal("snapshot claim mismatch")
    target = value.get("targetId")
    _uuid(target if isinstance(target, str) else "")
    return value


class LocalBuildAgentService:
    """One-stage, manual transport bridge with SQLite receipt recovery."""

    def __init__(
        self,
        root: Path,
        project_id: str,
        transport: BuildTransport,
        ports: Mapping[str, StagePort] | None = None,
        adapter_versions: Mapping[str, str] | None = None,
        input_authority: TrustedBuildInputAuthority | None = None,
        accepted_source_roots: tuple[Path, ...] = (),
        pipeline: QualifiedStagePipeline | None = None,
        native_authorization: NativeAuthorization | None = None,
    ) -> None:
        self.root = _private_root(root)
        self.project_id = _uuid(project_id)
        self.transport = transport
        if pipeline is not None:
            if (
                ports is not None
                or adapter_versions is not None
                or native_authorization is not None
            ):
                raise AgentTransportRefusal("ambiguous local stage configuration")
            ports, adapter_versions, native_authorization = pipeline.resolved()
        self.ports = dict(ports or {})
        self.adapter_versions = dict(adapter_versions or {})
        self.native_authorization = native_authorization
        self.input_authority = input_authority
        self.accepted_source_roots = accepted_source_roots
        if bool(self.ports) != bool(self.adapter_versions):
            raise AgentTransportRefusal("no independently pinned local adapters")
        if self.ports and any(
            name not in CORE_STAGES + STUDIO_STAGES[:2] for name in self.ports
        ):
            raise AgentTransportRefusal("unrequested render or delivery adapter")
        self.store = BuildJobStore(self.root / "jobs")

    def run_one(
        self,
        job_id: str,
        *,
        resumed_epoch: int | None = None,
        resumed_digest: str | None = None,
    ) -> str:
        """Never retries an ambiguous external effect or upgrades native status."""
        _uuid(job_id)
        if resumed_epoch is None:
            epoch, expected = self.transport.claim(job_id)
        else:
            if resumed_digest is None or _SHA.fullmatch(resumed_digest) is None:
                raise AgentTransportRefusal(
                    "restart needs original server lease digest"
                )
            epoch, expected = resumed_epoch, resumed_digest
        manifest = _checked_frozen(
            self.transport.frozen(job_id, epoch), self.project_id, job_id, expected
        )
        # The backend lease is *never* permission to operate Resolve. #302's
        # installed native ports need explicit local authority, independently
        # pinned to this frozen snapshot below. No implicit render or upload.
        native = self.native_authorization
        if not self.ports or (
            manifest["mode"] == "studio"
            and (
                not all(stage in self.ports for stage in STUDIO_STAGES[:2])
                or not isinstance(native, NativeAuthorization)
                or not native.approved_nonproduction
                or native.route != "None"
                or native.project_id != self.project_id
                or not native.request_id
            )
        ):
            self.transport.progress(
                job_id,
                epoch,
                "transport",
                "needs_action",
                None,
                "native_or_adapter_authorization_required",
            )
            return "needs_action"
        authority = self.input_authority
        if authority is None:
            raise AgentTransportRefusal("trusted compiler metadata required")
        pins = _validated_selected_pins(manifest["selectedSources"])
        try:
            dependencies = checked_compiler_dependencies(
                authority.frozen_dependencies(self.project_id, job_id),
                manifest,
                pins,
            )
        except FrozenInputRefusal:
            raise AgentTransportRefusal(
                "trusted frozen build inputs unavailable"
            ) from None
        inputs = self.root / "inputs" / job_id
        if any(part.is_symlink() for part in (inputs, inputs.parent, self.root)):
            raise AgentTransportRefusal("unsafe local input ancestry")
        inputs.mkdir(mode=0o700, parents=True, exist_ok=True)
        if inputs.is_symlink() or (inputs.stat().st_mode & 0o777) != 0o700:
            raise AgentTransportRefusal("unsafe local input directory")
        submission = json.dumps(
            {
                key: manifest[key]
                for key in (
                    "projectId",
                    "jobId",
                    "targetId",
                    "snapshotDigest",
                    "buildClass",
                    "mode",
                    "documentRevision",
                    "documentDigest",
                    "settingsRevision",
                    "settingsDigest",
                    "selectedSources",
                )
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        for name, raw in (
            ("document", manifest["documentJson"].encode("utf-8")),
            ("settings", manifest["settingsJson"].encode("utf-8")),
            ("dependencies", dependencies),
            ("submission", submission),
        ):
            _immutable(inputs / f"{name}.json", raw)
        source_inputs: dict[str, Path] = {}
        try:
            for source_id, (revision, digest) in pins.items():
                path = inputs / f"source-{source_id}.bin"
                frozen_source_file(
                    authority,
                    self.project_id,
                    source_id,
                    revision,
                    digest,
                    self.accepted_source_roots,
                    path,
                )
                source_inputs[f"source:{source_id}"] = path
        except FrozenInputRefusal:
            raise AgentTransportRefusal(
                "trusted accepted source bytes unavailable"
            ) from None

        def current() -> dict[str, Any]:
            live = _checked_frozen(
                self.transport.frozen(job_id, epoch), self.project_id, job_id, expected
            )
            if not _same_frozen_authority(manifest, live):
                raise AgentTransportRefusal("frozen authority changed")
            try:
                if (
                    checked_compiler_dependencies(
                        authority.frozen_dependencies(self.project_id, job_id),
                        live,
                        pins,
                    )
                    != dependencies
                ):
                    raise FrozenInputRefusal("compiler metadata changed")
                for source_id, (revision, digest) in pins.items():
                    frozen_source_file(
                        authority,
                        self.project_id,
                        source_id,
                        revision,
                        digest,
                        self.accepted_source_roots,
                        None,
                    )
            except FrozenInputRefusal:
                raise AgentTransportRefusal("accepted source changed") from None
            return live

        repository = SnapshotRepository(
            self.root / "snapshots",
            read_roots=(inputs,),
            write_root=self.root / "outputs",
            live_head=lambda _: (
                current()["documentRevision"],
                manifest["documentDigest"][7:],
                str(manifest["documentRevision"]),
            ),
            live_settings=lambda _: current()["settingsDigest"][7:],
        )
        snapshot = repository.freeze(
            project_id=self.project_id,
            build_id=job_id,
            build_class=manifest["buildClass"],
            mode=manifest["mode"],
            settings_hash=manifest["settingsDigest"][7:],
            inputs={
                **{
                    name: inputs / f"{name}.json"
                    for name in ("document", "settings", "dependencies", "submission")
                },
                **source_inputs,
            },
            adapter_versions=self.adapter_versions,
        )
        if manifest["mode"] == "studio" and (
            native is None or native.snapshot_id != snapshot.snapshot_id
        ):
            self.transport.progress(
                job_id,
                epoch,
                "transport",
                "needs_action",
                None,
                "native_or_adapter_authorization_required",
            )
            return "needs_action"
        local_job = BuildComposition(repository, self.ports).submit(
            self.store,
            BuildRequest(
                self.project_id, snapshot.snapshot_id, job_id, manifest["mode"]
            ),
        )
        before = self.store.status(self.project_id, local_job)
        requested = [s["name"] for s in before["stages"] if s["status"] == "requested"]
        if not requested:
            return str(before["status"])
        stage = str(requested[0])
        if (
            stage
            not in CORE_STAGES
            + (STUDIO_STAGES[:2] if manifest["mode"] == "studio" else ())
            or stage not in self.ports
        ):
            raise AgentTransportRefusal("unsupported local stage")
        current()  # Recheck remote scope, accepted bytes and v2 metadata at dispatch.
        self.transport.progress(job_id, epoch, stage, "running", None, None)
        self.store.run_one(
            self.project_id,
            local_job,
            "qa-agent",
            BuildComposition(repository, self.ports),
        )
        after = self.store.status(self.project_id, local_job)
        completed = next(s for s in after["stages"] if s["name"] == stage)
        if completed["status"] == "complete":
            digest = "sha256:" + str(completed["sha256"])
            self.transport.progress(job_id, epoch, stage, "running", digest, None)
        else:
            # Local uncertain/partial output and SQLite history survive; there
            # is no re-dispatch or unverified native success transition.
            label = "waiting_reconcile" if after["status"] == "waiting" else "failed"
            self.transport.progress(
                job_id, epoch, stage, label, None, "local_stage_unverified"
            )
        return str(after["status"])
