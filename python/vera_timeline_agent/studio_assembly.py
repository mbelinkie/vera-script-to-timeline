"""Assemble one verified Resolve import package through the Studio API."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from vera_timeline_agent.resolve_import_package import (
    MANIFEST_FILENAME,
    ResolveImportPackageError,
    verify_resolve_import_package,
)
from vera_timeline_agent.studio_spike import (
    BLACKMAGIC_BUNDLE_ID,
    DEFAULT_APP_PATH,
    ConnectedFacts,
    LocalFacts,
    _bundle_identity,
    _connected_studio_stop,
    _local_studio_stop,
    _project_settings,
    detect_local_capabilities,
    load_resolve_adapter,
)

JsonObject = dict[str, Any]


class StudioAssemblyError(RuntimeError):
    """An actionable Studio assembly error."""


@dataclass(frozen=True)
class StudioAssemblyResult:
    """Retained result from package preflight or one Studio assembly attempt."""

    status: str
    message: str
    local: LocalFacts
    build_id: str | None = None
    package_root: str | None = None
    connected: ConnectedFacts | None = None
    project_name: str | None = None
    timeline_name: str | None = None
    verified: bool = False
    discrepancies: tuple[str, ...] = ()
    manual_completion: tuple[str, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class StudioAssemblyAdapter(Protocol):
    """The subset of the accepted public Resolve adapter used by this slice."""

    def connected_facts(self) -> ConnectedFacts: ...

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]: ...

    def check_project_name_available(self, name: str) -> None: ...

    def create_project(self, name: str) -> None: ...

    def configure_project(self, settings: Mapping[str, str]) -> None: ...

    def create_bin(self, name: str) -> None: ...

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None: ...

    def create_timeline(self, name: str) -> None: ...

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None: ...

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None: ...

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None: ...

    def save_close_reopen(self, project_name: str) -> None: ...

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]: ...


AdapterFactory = Callable[[LocalFacts], StudioAssemblyAdapter]


def run_studio_assembly(
    package_root: Path | str,
    *,
    action: str = "preflight",
    adapter_factory: AdapterFactory | None = None,
    local_facts: LocalFacts | None = None,
) -> StudioAssemblyResult:
    """Verify a ready package, then preflight or create one new Studio target."""
    if action not in {"preflight", "build"}:
        raise StudioAssemblyError("action must be 'preflight' or 'build'")
    root = Path(package_root)
    local = local_facts or detect_local_capabilities()
    try:
        verification = verify_resolve_import_package(root)
        manifest = _load_manifest(root, verification.build_id)
    except (OSError, ValueError, ResolveImportPackageError) as error:
        return StudioAssemblyResult(
            "stopped_safely",
            "The supplied package is not a verified ready_to_import package; "
            f"no Resolve API was imported or invoked. Detail: {error}",
            local,
            package_root=str(root),
        )

    local_stop = _local_assembly_stop(local)
    if local_stop is not None:
        return _stopped(local_stop, local, verification.build_id, root)
    timeline = cast(Mapping[str, Any], manifest["timeline"])
    if timeline["startFrame"] != 0:
        return _stopped(
            "The Studio adapter supports only a frame-zero timeline start; no "
            "Resolve API was imported and no project mutation occurred.",
            local,
            verification.build_id,
            root,
        )
    settings = _project_settings(timeline)
    project_name = f"VERA Studio build {verification.build_id}"
    timeline_name = f"VERA build {verification.build_id}"
    if adapter_factory is None:
        adapter_factory = cast(AdapterFactory, load_resolve_adapter)
    try:
        adapter = adapter_factory(local)
        connected = adapter.connected_facts()
    except Exception as error:
        return _stopped(
            "Could not connect through Resolve's supported external scripting API. "
            "Start standard desktop Resolve Studio and enable local external "
            f"scripting, then retry. No project mutation occurred. Detail: {error}",
            local,
            verification.build_id,
            root,
        )
    connected_stop = _connected_studio_stop(local, connected)
    if connected_stop is not None:
        return _stopped(
            connected_stop, local, verification.build_id, root, connected=connected
        )
    try:
        probe_gaps = adapter.probe(settings)
        adapter.check_project_name_available(project_name)
    except Exception as error:
        return _stopped(
            f"Supported-API preflight failed; no project mutation occurred: {error}",
            local,
            verification.build_id,
            root,
            connected=connected,
        )
    manual = (
        "No Fusion graphic is inserted by this adapter: TimelineManifest v1 has "
        "no graphics event contract. The separately accepted #3 pinned-template "
        "capability remains available without inventing a product placement.",
        "This adapter never falls back to Resolve UI automation.",
        *probe_gaps,
    )
    if action == "preflight":
        return StudioAssemblyResult(
            "preflight_passed",
            "Studio preflight passed without project mutation.",
            local,
            verification.build_id,
            str(root),
            connected,
            project_name,
            timeline_name,
            manual_completion=manual,
        )

    try:
        adapter.create_project(project_name)
        adapter.configure_project(settings)
        adapter.create_bin("VERA Studio Assembly")
        adapter.create_bin("Package Media")
        adapter.import_media(_package_sources(root, manifest))
        adapter.create_timeline(timeline_name)
        adapter.configure_tracks(cast(list[Mapping[str, Any]], manifest["tracks"]))
        adapter.place_events(cast(list[Mapping[str, Any]], manifest["events"]))
        for marker in cast(list[Mapping[str, Any]], manifest["markers"]):
            adapter.add_marker(marker, _marker_custom_data(marker))
        adapter.save_close_reopen(project_name)
        discrepancies = adapter.verify(manifest)
    except Exception as error:
        return StudioAssemblyResult(
            "mutation_failed",
            "Studio build failed after project mutation was authorized. A partial "
            f"project may remain and must be inspected manually. Detail: {error}",
            local,
            verification.build_id,
            str(root),
            connected,
            project_name,
            timeline_name,
            manual_completion=manual,
        )
    return StudioAssemblyResult(
        "verified" if not discrepancies else "verification_failed",
        "Studio project saved, reopened, and verified against the package manifest."
        if not discrepancies
        else "Studio project reopened but verification found discrepancies.",
        local,
        verification.build_id,
        str(root),
        connected,
        project_name,
        timeline_name,
        verified=not discrepancies,
        discrepancies=discrepancies,
        manual_completion=manual,
    )


def _stopped(
    message: str,
    local: LocalFacts,
    build_id: str,
    package_root: Path,
    *,
    connected: ConnectedFacts | None = None,
) -> StudioAssemblyResult:
    return StudioAssemblyResult(
        "stopped_safely",
        message,
        local,
        build_id,
        str(package_root),
        connected,
    )


def _local_assembly_stop(local: LocalFacts) -> str | None:
    """Retain the accepted 21.1.0/14 baseline despite a stale installer receipt."""
    stop = _local_studio_stop(local)
    if stop is None or not _is_accepted_assembly_baseline(local):
        return stop
    return None


def _is_accepted_assembly_baseline(local: LocalFacts) -> bool:
    return (
        local.app_installed
        and not local.mas_receipt
        and Path(local.app_path) == DEFAULT_APP_PATH
        and local.bundle_identifier == BLACKMAGIC_BUNDLE_ID
        and _bundle_identity(local.bundle_version, local.bundle_build)
        == (21, 1, 0, 14, "")
        and local.scripting_module_installed
    )


def _load_manifest(package_root: Path, build_id: str) -> JsonObject:
    value = json.loads(
        (package_root / "Builds" / build_id / MANIFEST_FILENAME).read_text(
            encoding="utf-8"
        )
    )
    if not isinstance(value, dict):
        raise StudioAssemblyError("verified package manifest is not an object")
    return cast(JsonObject, value)


def _package_sources(
    package_root: Path, manifest: Mapping[str, Any]
) -> list[tuple[str, Path]]:
    sources: list[tuple[str, Path]] = []
    for source in cast(list[Mapping[str, Any]], manifest["sources"]):
        if source["kind"] == "placeholder":
            path = package_root / "Media" / "Placeholders" / f"{source['id']}.png"
        else:
            path = package_root / cast(str, source["path"])
        sources.append((cast(str, source["id"]), path.resolve()))
    return sources


def _marker_custom_data(marker: Mapping[str, Any]) -> str:
    return json.dumps(
        {"markerId": marker["id"], "provenance": marker["provenance"]},
        sort_keys=True,
        separators=(",", ":"),
    )
