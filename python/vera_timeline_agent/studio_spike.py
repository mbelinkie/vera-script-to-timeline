"""Bounded Resolve Studio scripting spike with a fail-closed safety boundary."""

from __future__ import annotations

import importlib.util
import json
import platform
import plistlib
import re
import subprocess
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from vera_timeline_agent.otio_package import verify_otio_package
from vera_timeline_agent.text_plus_template import (
    DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    TemplateValidationError,
    TextPlusTemplate,
    validate_text_plus_template,
)

DEFAULT_APP_PATH = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
DEFAULT_SCRIPTING_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
)
MANIFEST_NAME = "timeline-manifest.json"
BLACKMAGIC_RECEIPT_ID = "com.blackmagic-design.ManifestLite"
BLACKMAGIC_BUNDLE_ID = "com.blackmagic-design.DaVinciResolve"
TIMELINE_PAGES = frozenset({"cut", "edit", "color", "fairlight", "deliver"})
VERSION_PATTERN = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)")

JsonObject = dict[str, Any]


class StudioSpikeError(RuntimeError):
    """An actionable Studio spike error."""


@dataclass(frozen=True)
class LocalFacts:
    """Facts detectable without importing or connecting to Resolve."""

    os_name: str
    os_version: str
    architecture: str
    app_path: str
    app_installed: bool
    install_source: str
    bundle_name: str | None
    bundle_identifier: str | None
    bundle_version: str | None
    bundle_build: str | None
    mas_receipt: bool
    package_receipt_id: str | None
    package_receipt_version: str | None
    scripting_module_path: str
    scripting_module_installed: bool
    scripting_docs_path: str
    scripting_docs_installed: bool


@dataclass(frozen=True)
class ConnectedFacts:
    """Facts observed only through a successful supported API connection."""

    product_name: str
    edition: str
    version: str
    build: str
    scripting_available: bool
    suffix: str = ""


@dataclass(frozen=True)
class TextPlusPlacement:
    """Internal deterministic placement request for the pinned Text+ asset."""

    title_name: str
    track_id: str
    track_index: int
    record_frame: int
    duration_frames: int


@dataclass(frozen=True)
class TitlePlacementEvidence:
    """Public-API-observable evidence for one pinned Text+ placement."""

    title_name: str
    track_id: str
    track_index: int
    record_frame: int
    duration_frames: int
    asset_sha256: str
    fusion_tool_registration_ids: tuple[str, ...]


@dataclass(frozen=True)
class CapabilityResult:
    """Honest outcome from detection, preflight, assembly, or verification."""

    status: str
    message: str
    local: LocalFacts
    connected: ConnectedFacts | None = None
    project_name: str | None = None
    timeline_name: str | None = None
    verified: bool = False
    discrepancies: tuple[str, ...] = ()
    manual_completion: tuple[str, ...] = ()
    title_placement: TitlePlacementEvidence | None = None

    def to_json(self) -> str:
        """Serialize a stable human/machine-readable CLI result."""
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class ResolveAdapter(Protocol):
    """Narrow injectable boundary over the installed public Resolve API."""

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

    def insert_text_plus(
        self, placement: TextPlusPlacement, template: TextPlusTemplate
    ) -> TitlePlacementEvidence: ...

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None: ...

    def save_close_reopen(self, project_name: str) -> None: ...

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]: ...


AdapterFactory = Callable[[LocalFacts], ResolveAdapter]


def detect_local_capabilities(
    app_path: Path = DEFAULT_APP_PATH,
    scripting_root: Path = DEFAULT_SCRIPTING_ROOT,
) -> LocalFacts:
    """Inspect filesystem/OS facts without importing or connecting to Resolve."""
    plist_path = app_path / "Contents/Info.plist"
    bundle: Mapping[str, Any] = {}
    if plist_path.is_file():
        try:
            with plist_path.open("rb") as stream:
                loaded = plistlib.load(stream)
            if isinstance(loaded, dict):
                bundle = cast(Mapping[str, Any], loaded)
        except (OSError, plistlib.InvalidFileException):
            bundle = {}
    receipt = app_path / "Contents/_MASReceipt/receipt"
    module = scripting_root / "Modules/DaVinciResolveScript.py"
    docs = scripting_root / "README.txt"
    app_installed = app_path.is_dir()
    mas_receipt = receipt.is_file()
    package_receipt_id, package_receipt_version = _blackmagic_package_receipt()
    bundle_identifier = _optional_string(bundle.get("CFBundleIdentifier"))
    bundle_version = _optional_string(bundle.get("CFBundleShortVersionString"))
    bundle_build = _optional_string(bundle.get("CFBundleVersion"))
    if not app_installed:
        install_source = "missing"
    elif mas_receipt:
        install_source = "mac_app_store"
    elif (
        app_path == DEFAULT_APP_PATH
        and bundle_identifier == BLACKMAGIC_BUNDLE_ID
        and _bundle_identity(bundle_version, bundle_build) is not None
        and package_receipt_id == BLACKMAGIC_RECEIPT_ID
        and package_receipt_version == bundle_version
    ):
        install_source = "blackmagic_package_receipt"
    else:
        install_source = "unknown_non_mas"
    mac_version = platform.mac_ver()[0]
    return LocalFacts(
        os_name="macOS" if sys.platform == "darwin" else platform.system(),
        os_version=mac_version or platform.release(),
        architecture=platform.machine(),
        app_path=str(app_path),
        app_installed=app_installed,
        install_source=install_source,
        bundle_name=_optional_string(bundle.get("CFBundleDisplayName")),
        bundle_identifier=bundle_identifier,
        bundle_version=bundle_version,
        bundle_build=bundle_build,
        mas_receipt=mas_receipt,
        package_receipt_id=package_receipt_id,
        package_receipt_version=package_receipt_version,
        scripting_module_path=str(module),
        scripting_module_installed=module.is_file(),
        scripting_docs_path=str(docs),
        scripting_docs_installed=docs.is_file(),
    )


def run_delivery(
    package_dir: Path,
    mode: str,
    *,
    action: str = "preflight",
    adapter_factory: AdapterFactory | None = None,
    local_facts: LocalFacts | None = None,
    project_name: str | None = None,
    fusion_title: str = "Text+",
    fusion_title_track_id: str = "video-graphics",
    fusion_title_duration_frames: int | None = None,
    template_metadata: Path = DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
) -> CapabilityResult:
    """Verify the accepted package, then safely preflight or assemble Studio."""
    if mode not in {"free", "studio"}:
        raise StudioSpikeError("mode must be 'free' or 'studio'")
    if action not in {"preflight", "build"}:
        raise StudioSpikeError("action must be 'preflight' or 'build'")
    verify_otio_package(package_dir)
    local = local_facts or detect_local_capabilities()
    if mode == "free":
        return CapabilityResult(
            status="ready_to_import",
            message=(
                "Free delivery package verified. Resolve scripting was not imported, "
                "connected, or invoked. Complete the documented manual import."
            ),
            local=local,
        )

    stop = _local_studio_stop(local)
    if stop is not None:
        return CapabilityResult(status="stopped_safely", message=stop, local=local)
    manifest = _load_manifest(package_dir)
    timeline = cast(Mapping[str, Any], manifest["timeline"])
    if timeline["startFrame"] != 0:
        return CapabilityResult(
            status="stopped_safely",
            message=(
                "The bounded Studio spike supports only a frame-zero timeline start; "
                "no Resolve API was imported and no project mutation occurred."
            ),
            local=local,
        )
    try:
        template = validate_text_plus_template(
            template_metadata, require_validated_duration_rule=True
        )
        title_placement = _resolve_text_plus_placement(
            manifest,
            title_name=fusion_title,
            track_id=fusion_title_track_id,
            duration_frames=fusion_title_duration_frames,
        )
    except (StudioSpikeError, TemplateValidationError) as error:
        return CapabilityResult(
            status="stopped_safely",
            message=f"Pinned Text+ preflight failed before API connection: {error}",
            local=local,
        )
    resolved_project_name = project_name or f"VERA Studio Spike {manifest['buildId']}"
    timeline_name = f"VERA build {manifest['buildId']}"
    settings = _project_settings(timeline)
    if adapter_factory is None:
        adapter_factory = load_resolve_adapter
    try:
        adapter = adapter_factory(local)
        connected = adapter.connected_facts()
    except Exception as error:
        return CapabilityResult(
            status="stopped_safely",
            message=(
                "Could not connect through Resolve's supported external scripting API. "
                "Start standard desktop Resolve Studio and enable local external "
                f"scripting, then retry. No project mutation occurred. Detail: {error}"
            ),
            local=local,
        )
    connected_stop = _connected_studio_stop(local, connected)
    if connected_stop is not None:
        return CapabilityResult(
            status="stopped_safely",
            message=connected_stop,
            local=local,
            connected=connected,
        )
    template_stop = _template_connected_stop(template, connected)
    if template_stop is not None:
        return CapabilityResult(
            status="stopped_safely",
            message=template_stop,
            local=local,
            connected=connected,
        )
    try:
        probe_gaps = adapter.probe(settings)
        adapter.check_project_name_available(resolved_project_name)
    except Exception as error:
        return CapabilityResult(
            status="stopped_safely",
            message=(
                f"Supported-API preflight failed; no project mutation occurred: {error}"
            ),
            local=local,
            connected=connected,
        )
    manual = (
        "The public API cannot enumerate the local stock Fusion-title catalog. "
        "This build instead uses the producer-authored, hash-pinned Text+ template.",
        "The identity gate compares documented GetVersion fields "
        "[major, minor, patch, build, suffix] with the bundle marketing/build "
        "values. It supports the observed numeric macOS bundle build encoding and "
        "fails closed for other encodings or a nonempty suffix.",
        "The public API does not report its executable path; full version/build "
        "agreement still cannot prove the running process came from the "
        "receipt-associated bundle detected on disk.",
        *probe_gaps,
    )
    if action == "preflight":
        return CapabilityResult(
            status="preflight_passed",
            message="Studio preflight passed without project mutation.",
            local=local,
            connected=connected,
            manual_completion=manual,
        )

    sources = _resolved_sources(package_dir, manifest)
    title_evidence: TitlePlacementEvidence | None = None
    try:
        adapter.create_project(resolved_project_name)
        adapter.configure_project(settings)
        adapter.create_bin("VERA Slice 0.4")
        adapter.create_bin("Accepted Media")
        adapter.import_media(sources)
        adapter.create_timeline(timeline_name)
        adapter.configure_tracks(cast(list[Mapping[str, Any]], manifest["tracks"]))
        title_evidence = adapter.insert_text_plus(title_placement, template)
        adapter.place_events(cast(list[Mapping[str, Any]], manifest["events"]))
        for marker in cast(list[Mapping[str, Any]], manifest["markers"]):
            custom_data = json.dumps(
                {"markerId": marker["id"], "provenance": marker["provenance"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            adapter.add_marker(marker, custom_data)
        adapter.save_close_reopen(resolved_project_name)
        discrepancies = adapter.verify(manifest)
    except Exception as error:
        return CapabilityResult(
            status="mutation_failed",
            message=(
                "Studio build failed after project mutation was authorized. A partial "
                f"project may remain and must be inspected manually. Detail: {error}"
            ),
            local=local,
            connected=connected,
            project_name=resolved_project_name,
            timeline_name=timeline_name,
            manual_completion=manual,
            title_placement=title_evidence,
        )
    return CapabilityResult(
        status="verified" if not discrepancies else "verification_failed",
        message=(
            "Studio project saved, reopened, and verified for all "
            "public-API-observable spike requirements."
            if not discrepancies
            else "Studio project reopened but verification found discrepancies."
        ),
        local=local,
        connected=connected,
        project_name=resolved_project_name,
        timeline_name=timeline_name,
        verified=not discrepancies,
        discrepancies=discrepancies,
        manual_completion=manual,
        title_placement=title_evidence,
    )


def load_resolve_adapter(local: LocalFacts) -> ResolveAdapter:
    """Import the vendor bridge and connect only after local safety checks pass."""
    module_path = Path(local.scripting_module_path)
    spec = importlib.util.spec_from_file_location("DaVinciResolveScript", module_path)
    if spec is None or spec.loader is None:
        raise StudioSpikeError(f"cannot load Resolve scripting module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    previous_module = sys.modules.get(spec.name)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        if previous_module is None:
            sys.modules.pop(spec.name, None)
        else:
            sys.modules[spec.name] = previous_module
        raise
    loaded_module = sys.modules.get(spec.name, module)
    resolve = loaded_module.scriptapp("Resolve")
    if resolve is None:
        raise StudioSpikeError("Resolve returned no scripting connection")
    return PublicResolveAdapter(resolve)


class PublicResolveAdapter:
    """Thin checked wrapper around APIs documented by the installed SDK."""

    def __init__(self, resolve: Any) -> None:
        self.resolve = resolve
        self.manager: Any = None
        self.project: Any = None
        self.pool: Any = None
        self.timeline: Any = None
        self.media_by_source: dict[str, Any] = {}
        self.media_id_by_source: dict[str, str] = {}
        self.expected_project_name: str | None = None
        self.expected_timeline_name: str | None = None
        self.expected_settings: dict[str, str] = {}
        self.created_bins: list[str] = []
        self.title_placement_evidence: TitlePlacementEvidence | None = None
        self.text_plus_template: TextPlusTemplate | None = None

    def connected_facts(self) -> ConnectedFacts:
        product = self.resolve.GetProductName()
        if not isinstance(product, str) or not product:
            raise StudioSpikeError("GetProductName returned an invalid value")
        fields = self.resolve.GetVersion()
        if not isinstance(fields, (list, tuple)) or len(fields) != 5:
            raise StudioSpikeError(
                "GetVersion must return [major, minor, patch, build, suffix]"
            )
        numeric = fields[:4]
        if any(
            not isinstance(value, int) or isinstance(value, bool) or value < 0
            for value in numeric
        ) or not isinstance(fields[4], str):
            raise StudioSpikeError(
                "GetVersion returned malformed major/minor/patch/build/suffix fields"
            )
        major, minor, patch, build = cast(tuple[int, int, int, int], tuple(numeric))
        suffix = fields[4]
        version = f"{major}.{minor}.{patch}"
        edition = "studio" if "studio" in product.casefold() else "free"
        return ConnectedFacts(product, edition, version, str(build), True, suffix)

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
        if not callable(getattr(self.resolve, "GetCurrentPage", None)):
            raise StudioSpikeError("Resolve has no callable GetCurrentPage")
        current_page = self.resolve.GetCurrentPage()
        if current_page not in TIMELINE_PAGES:
            allowed = ", ".join(sorted(TIMELINE_PAGES))
            raise StudioSpikeError(
                "Resolve must already be on a timeline page before preflight "
                f"({allowed}); current page is {current_page!r}"
            )
        manager = self.resolve.GetProjectManager()
        if manager is None:
            raise StudioSpikeError("GetProjectManager returned no object")
        for method in (
            "GetProjectListInCurrentFolder",
            "GetCurrentProject",
            "CreateProject",
            "SaveProject",
            "CloseProject",
            "LoadProject",
        ):
            if not callable(getattr(manager, method, None)):
                raise StudioSpikeError(f"project manager has no callable {method}")
        if not isinstance(manager.GetProjectListInCurrentFolder(), (list, tuple)):
            raise StudioSpikeError("project-list probe returned an unsupported value")
        self.manager = manager
        gaps = [
            "Nonmutating preflight cannot prove project creation, setting mutation, "
            "media import, timeline assembly, or Fusion-title insertion; those calls "
            "are checked only after the producer authorizes the build."
        ]
        current = manager.GetCurrentProject()
        if current is None:
            raise StudioSpikeError(
                "an open current project is required to inspect Studio API surfaces"
            )
        if not callable(getattr(current, "GetSetting", None)):
            raise StudioSpikeError("current project has no callable GetSetting")
        for key in settings:
            if current.GetSetting(key) in (None, ""):
                raise StudioSpikeError(f"current project does not expose setting {key}")
        pool = current.GetMediaPool()
        if pool is None:
            raise StudioSpikeError("current project has no media pool")
        for method in (
            "ImportMedia",
            "CreateEmptyTimeline",
            "AddSubFolder",
            "GetRootFolder",
            "GetCurrentFolder",
            "SetCurrentFolder",
            "ImportFolderFromFile",
            "AppendToTimeline",
        ):
            if not callable(getattr(pool, method, None)):
                raise StudioSpikeError(f"media pool has no callable {method}")
        root = pool.GetRootFolder()
        if root is None:
            raise StudioSpikeError("current media pool has no root folder")
        for method in ("GetSubFolderList", "GetClipList"):
            if not callable(getattr(root, method, None)):
                raise StudioSpikeError(f"media pool root has no callable {method}")
        if not callable(getattr(current, "GetCurrentTimeline", None)):
            raise StudioSpikeError("current project has no callable GetCurrentTimeline")
        current_timeline = current.GetCurrentTimeline()
        if current_timeline is None:
            raise StudioSpikeError("current project has no timeline for API preflight")
        for method in ("GetTrackCount", "GetItemListInTrack"):
            if not callable(getattr(current_timeline, method, None)):
                raise StudioSpikeError(f"current timeline has no callable {method}")
        return tuple(gaps)

    def check_project_name_available(self, name: str) -> None:
        if name in self.manager.GetProjectListInCurrentFolder():
            raise StudioSpikeError(
                f"project already exists; refusing to overwrite or reuse it: {name}"
            )

    def create_project(self, name: str) -> None:
        self.check_project_name_available(name)
        self.project = self.manager.CreateProject(name)
        if self.project is None:
            raise StudioSpikeError(f"CreateProject failed for {name}")
        self.pool = self.project.GetMediaPool()
        if self.pool is None:
            raise StudioSpikeError("created project has no media pool")
        self.expected_project_name = name

    def configure_project(self, settings: Mapping[str, str]) -> None:
        for key, value in settings.items():
            if not self.project.SetSetting(key, value):
                raise StudioSpikeError(f"SetSetting failed for {key}={value}")
        self.expected_settings = dict(settings)

    def create_bin(self, name: str) -> None:
        parent = self.pool.GetCurrentFolder()
        folder = self.pool.AddSubFolder(parent, name)
        if folder is None or not self.pool.SetCurrentFolder(folder):
            raise StudioSpikeError(f"could not create/select media bin {name}")
        self.created_bins.append(name)

    def import_media(self, sources: Sequence[tuple[str, Path]]) -> None:
        paths = [str(path) for _, path in sources]
        imported = self.pool.ImportMedia(paths)
        if not isinstance(imported, (list, tuple)) or len(imported) != len(sources):
            raise StudioSpikeError("ImportMedia did not return one item per source")
        expected_by_path = {path.resolve(): source_id for source_id, path in sources}
        imported_by_path: dict[Path, Any] = {}
        for item in imported:
            file_path = item.GetClipProperty("File Path")
            if not isinstance(file_path, str) or not file_path:
                raise StudioSpikeError("imported media item has no File Path property")
            resolved = Path(file_path).resolve()
            if resolved in imported_by_path:
                raise StudioSpikeError(
                    f"ImportMedia returned duplicate path: {resolved}"
                )
            imported_by_path[resolved] = item
        if imported_by_path.keys() != expected_by_path.keys():
            raise StudioSpikeError(
                "ImportMedia returned paths that differ from sources"
            )
        self.media_by_source = {
            source_id: imported_by_path[path]
            for path, source_id in expected_by_path.items()
        }
        self.media_id_by_source = {}
        for source_id, item in self.media_by_source.items():
            media_id = item.GetMediaId()
            if not isinstance(media_id, str) or not media_id:
                raise StudioSpikeError(f"imported source has no media ID: {source_id}")
            self.media_id_by_source[source_id] = media_id

    def create_timeline(self, name: str) -> None:
        self.timeline = self.pool.CreateEmptyTimeline(name)
        if self.timeline is None:
            raise StudioSpikeError(f"CreateEmptyTimeline failed for {name}")
        if not self.timeline.SetStartTimecode("00:00:00:00"):
            raise StudioSpikeError("SetStartTimecode failed for frame-zero spike")
        if self.timeline.GetStartFrame() != 0:
            raise StudioSpikeError("timeline did not retain the frame-zero start")
        self.expected_timeline_name = name

    def configure_tracks(self, tracks: Sequence[Mapping[str, Any]]) -> None:
        self._track_id_map = {
            cast(str, track["id"]): cast(int, track["index"]) for track in tracks
        }
        grouped: dict[str, list[Mapping[str, Any]]] = {
            "video": [],
            "audio": [],
            "subtitle": [],
        }
        for track in tracks:
            grouped[cast(str, track["kind"])].append(track)
        for kind, values in grouped.items():
            for track in sorted(values, key=lambda value: cast(int, value["index"])):
                index = cast(int, track["index"])
                while self.timeline.GetTrackCount(kind) < index:
                    subtype = "stereo" if kind == "audio" else None
                    success = (
                        self.timeline.AddTrack(kind, subtype)
                        if subtype is not None
                        else self.timeline.AddTrack(kind)
                    )
                    if not success:
                        raise StudioSpikeError(f"AddTrack failed for {kind} {index}")
                if not self.timeline.SetTrackName(kind, index, track["name"]):
                    raise StudioSpikeError(f"SetTrackName failed for {kind} {index}")

    def place_events(self, events: Sequence[Mapping[str, Any]]) -> None:
        infos: list[dict[str, Any]] = []
        marked_stills: list[tuple[Any, str]] = []
        try:
            for event in events:
                record = cast(Mapping[str, int], event["recordRange"])
                source = cast(Mapping[str, int], event.get("sourceRange", {}))
                start = source.get("startFrame", 0)
                duration = source.get("durationFrames", record["durationFrames"])
                source_id = cast(str, event["sourceId"])
                media = self.media_by_source[source_id]
                if event["kind"] == "still":
                    # Resolve 21 ignores clipInfo.endFrame for a one-frame still and
                    # otherwise inserts the user-preference default (120 frames on
                    # the tested installation). A documented temporary MediaPoolItem
                    # mark range makes the authored occurrence duration explicit.
                    # Resolve 21 also treats the documented mark out value as an
                    # exclusive bound, matching clipInfo.endFrame.
                    if not media.SetMarkInOut(0, duration, "video"):
                        raise StudioSpikeError(
                            f"still event {event['id']} could not set the "
                            f"{duration}-frame range"
                        )
                    marked_stills.append((media, cast(str, event["id"])))
                infos.append(
                    {
                        "mediaPoolItem": media,
                        "startFrame": start,
                        # Resolve 21 treats clipInfo.endFrame as an exclusive bound
                        # for ordinary media. For a one-frame still it subtracts an
                        # additional frame when intersecting clipInfo with the
                        # temporary mark range, so the observed API requires one
                        # compensating frame to retain the authored duration.
                        "endFrame": start
                        + duration
                        + (1 if event["kind"] == "still" else 0),
                        "mediaType": 2 if event["kind"] == "audio" else 1,
                        "trackIndex": self._track_index(cast(str, event["trackId"])),
                        "recordFrame": record["startFrame"],
                    }
                )
            placed = self.pool.AppendToTimeline(infos)
        finally:
            for media, event_id in marked_stills:
                if not media.ClearMarkInOut("video"):
                    raise StudioSpikeError(
                        f"still event {event_id} could not clear its temporary range"
                    )
        if not isinstance(placed, (list, tuple)) or len(placed) != len(infos):
            raise StudioSpikeError("AppendToTimeline failed to place every event")

    def _track_index(self, track_id: str) -> int:
        # Event adapters receive IDs, while the public API receives indices. The
        # manifest's accepted IDs have already been validated; retain their map.
        suffix_map = getattr(self, "_track_id_map", None)
        if suffix_map is None:
            raise StudioSpikeError("track ID map was not initialized")
        return cast(int, suffix_map[track_id])

    def insert_text_plus(
        self, placement: TextPlusPlacement, template: TextPlusTemplate
    ) -> TitlePlacementEvidence:
        current_page = self.resolve.GetCurrentPage()
        if current_page not in TIMELINE_PAGES:
            raise StudioSpikeError(
                "Resolve left the supported timeline page before Fusion insertion"
            )
        if template.append_end_frame_delta is None:
            raise StudioSpikeError(
                "pinned Text+ template has no validated duration rule"
            )
        from .text_plus_validation import (
            append_template_item,
            fingerprint_fusion_item,
            import_template_generator,
        )

        generator = import_template_generator(self.pool, template)
        title = append_template_item(
            self.pool,
            generator,
            self.timeline,
            start_frame=0,
            end_frame=placement.duration_frames + template.append_end_frame_delta,
            record_frame=placement.record_frame,
            track_index=placement.track_index,
        )
        if title.GetStart(False) != placement.record_frame:
            raise StudioSpikeError("Text+ landed at an unexpected record frame")
        if title.GetDuration(False) != placement.duration_frames:
            raise StudioSpikeError("Text+ landed with an unexpected duration")
        fingerprint = fingerprint_fusion_item(title, template)
        evidence = TitlePlacementEvidence(
            title_name=placement.title_name,
            track_id=placement.track_id,
            track_index=placement.track_index,
            record_frame=placement.record_frame,
            duration_frames=placement.duration_frames,
            asset_sha256=template.sha256,
            fusion_tool_registration_ids=fingerprint.tool_registration_ids,
        )
        self.title_placement_evidence = evidence
        self.text_plus_template = template
        return evidence

    def add_marker(self, marker: Mapping[str, Any], custom_data: str) -> None:
        if not self.timeline.AddMarker(
            marker["frame"],
            marker["color"],
            marker["name"],
            marker["note"],
            1,
            custom_data,
        ):
            raise StudioSpikeError(f"AddMarker failed for {marker['id']}")

    def save_close_reopen(self, project_name: str) -> None:
        if not self.manager.SaveProject():
            raise StudioSpikeError("SaveProject failed")
        if not self.manager.CloseProject(self.project):
            raise StudioSpikeError("CloseProject failed after save")
        self.project = self.manager.LoadProject(project_name)
        if self.project is None:
            raise StudioSpikeError("LoadProject failed after close")
        self.pool = self.project.GetMediaPool()
        self.timeline = self.project.GetCurrentTimeline()
        if self.timeline is None:
            raise StudioSpikeError("reopened project has no current timeline")

    def verify(self, manifest: Mapping[str, Any]) -> tuple[str, ...]:
        discrepancies: list[str] = []
        if self.project.GetName() != self.expected_project_name:
            discrepancies.append("reopened project name differs from requested name")
        if self.timeline.GetName() != self.expected_timeline_name:
            discrepancies.append("reopened timeline name differs from requested name")
        for key, expected_value in self.expected_settings.items():
            actual = str(self.project.GetSetting(key))
            if actual != expected_value:
                discrepancies.append(
                    f"project setting {key}: expected {expected_value!r}, "
                    f"got {actual!r}"
                )
        timeline = cast(Mapping[str, Any], manifest["timeline"])
        expected_start = cast(int, timeline["startFrame"])
        expected_end = expected_start + cast(int, timeline["durationFrames"])
        if self.title_placement_evidence is not None:
            expected_end = max(
                expected_end,
                self.title_placement_evidence.record_frame
                + self.title_placement_evidence.duration_frames,
            )
        if self.timeline.GetStartFrame() != expected_start:
            discrepancies.append("timeline start frame differs from manifest")
        if self.timeline.GetEndFrame() != expected_end:
            discrepancies.append(
                "timeline end frame differs from manifest media and inserted title"
            )
        self._verify_bins(discrepancies)
        expected_tracks = cast(list[Mapping[str, Any]], manifest["tracks"])
        expected_track_counts = {
            kind: max(
                (
                    cast(int, track["index"])
                    for track in expected_tracks
                    if track["kind"] == kind
                ),
                default=0,
            )
            for kind in ("video", "audio", "subtitle")
        }
        actual_items_by_slot: dict[tuple[str, int], list[Any]] = {}
        for kind, expected_count in expected_track_counts.items():
            actual_count = self.timeline.GetTrackCount(kind)
            if actual_count != expected_count:
                discrepancies.append(
                    f"{kind} track count: expected {expected_count}, got {actual_count}"
                )
            for index in range(1, actual_count + 1):
                actual_items_by_slot[(kind, index)] = list(
                    self.timeline.GetItemListInTrack(kind, index)
                )
        for track in expected_tracks:
            kind, index, name = track["kind"], track["index"], track["name"]
            if cast(int, index) > self.timeline.GetTrackCount(cast(str, kind)):
                discrepancies.append(f"{kind} track {index} is missing")
                continue
            actual = self.timeline.GetTrackName(kind, index)
            if actual != name:
                discrepancies.append(
                    f"{kind} track {index}: expected {name!r}, got {actual!r}"
                )
        events = cast(list[Mapping[str, Any]], manifest["events"])
        by_slot: dict[tuple[str, int], list[Mapping[str, Any]]] = {}
        track_index = {
            cast(str, item["id"]): cast(int, item["index"]) for item in expected_tracks
        }
        for event in events:
            slot = (
                cast(str, event["trackKind"]),
                track_index[cast(str, event["trackId"])],
            )
            by_slot.setdefault(slot, []).append(event)
        title_matches: list[tuple[tuple[str, int], Any]] = []
        title_evidence = self.title_placement_evidence
        text_plus_template = self.text_plus_template
        if title_evidence is None or text_plus_template is None:
            discrepancies.append("pinned Text+ placement evidence is missing")
        else:
            try:
                from .text_plus_validation import find_imported_template_generator

                find_imported_template_generator(self.pool, text_plus_template)
            except (AttributeError, StudioSpikeError, TypeError, ValueError) as error:
                discrepancies.append(f"pinned Text+ template bin differs: {error}")
            for slot, items in actual_items_by_slot.items():
                if slot[0] != "video":
                    continue
                for item in items:
                    if _matches_text_plus_placement(
                        item,
                        title_evidence,
                        text_plus_template,
                    ):
                        title_matches.append((slot, item))
        if len(title_matches) != 1:
            discrepancies.append(
                "expected exactly one reopened pinned Text+ matching the inserted "
                f"public fingerprint, got {len(title_matches)}"
            )
        elif title_evidence is not None and title_matches[0][0] != (
            "video",
            title_evidence.track_index,
        ):
            discrepancies.append("reopened pinned Text+ is on the wrong video track")
        title_object_id = id(title_matches[0][1]) if len(title_matches) == 1 else None
        for slot, actual_slot_items in actual_items_by_slot.items():
            kind, index = slot
            expected_events = by_slot.get(slot, [])
            actual_items = [
                item for item in actual_slot_items if id(item) != title_object_id
            ]
            if len(actual_items) != len(expected_events):
                discrepancies.append(
                    f"{kind} track {index}: expected {len(expected_events)} manifest "
                    f"items, got {len(actual_items)}"
                )
                continue
            expected_order = sorted(
                expected_events, key=lambda item: item["recordRange"]["startFrame"]
            )
            actual_order = sorted(actual_items, key=lambda item: item.GetStart(False))
            for expected_event, actual in zip(
                expected_order, actual_order, strict=True
            ):
                record = expected_event["recordRange"]
                if actual.GetStart(False) != record["startFrame"]:
                    discrepancies.append(
                        f"event {expected_event['id']}: record start mismatch"
                    )
                if actual.GetDuration(False) != record["durationFrames"]:
                    discrepancies.append(
                        f"event {expected_event['id']}: duration mismatch"
                    )
                source = expected_event.get("sourceRange")
                if (
                    isinstance(source, Mapping)
                    and actual.GetSourceStartFrame() != source["startFrame"]
                ):
                    discrepancies.append(
                        f"event {expected_event['id']}: source start mismatch"
                    )
                media_item = actual.GetMediaPoolItem()
                actual_media_id = (
                    media_item.GetMediaId() if media_item is not None else None
                )
                expected_media_id = self.media_id_by_source.get(
                    cast(str, expected_event["sourceId"])
                )
                if actual_media_id != expected_media_id:
                    discrepancies.append(
                        f"event {expected_event['id']}: source media identity mismatch"
                    )
        actual_markers = self.timeline.GetMarkers()
        for marker in cast(list[Mapping[str, Any]], manifest["markers"]):
            custom = json.dumps(
                {"markerId": marker["id"], "provenance": marker["provenance"]},
                sort_keys=True,
                separators=(",", ":"),
            )
            found = self.timeline.GetMarkerByCustomData(custom)
            if not found:
                discrepancies.append(f"marker {marker['id']}: custom data not found")
                continue
            info = actual_markers.get(marker["frame"])
            expected_info = {
                "color": marker["color"],
                "duration": 1,
                "note": marker["note"],
                "name": marker["name"],
                "customData": custom,
            }
            if not isinstance(info, Mapping) or any(
                info.get(key) != value for key, value in expected_info.items()
            ):
                discrepancies.append(f"marker {marker['id']}: fields differ")
        return tuple(discrepancies)

    def _verify_bins(self, discrepancies: list[str]) -> None:
        folder = self.pool.GetRootFolder()
        for name in self.created_bins:
            children = folder.GetSubFolderList() if folder is not None else []
            folder = next(
                (child for child in children if child.GetName() == name), None
            )
            if folder is None:
                discrepancies.append(f"media bin path is missing at {name!r}")
                return


def _resolve_text_plus_placement(
    manifest: Mapping[str, Any],
    *,
    title_name: str,
    track_id: str,
    duration_frames: int | None,
) -> TextPlusPlacement:
    if title_name != "Text+":
        raise StudioSpikeError(
            "the pinned template supports only Text+; arbitrary Fusion titles "
            "are not available"
        )
    if not isinstance(track_id, str) or not track_id:
        raise StudioSpikeError("Fusion title track ID must be nonempty")
    tracks = cast(list[Mapping[str, Any]], manifest["tracks"])
    matches = [track for track in tracks if track["id"] == track_id]
    if len(matches) != 1:
        raise StudioSpikeError(
            f"Fusion title track ID must identify exactly one track: {track_id!r}"
        )
    track = matches[0]
    if track["kind"] != "video":
        raise StudioSpikeError("Fusion title destination must be a video track")
    timeline = cast(Mapping[str, Any], manifest["timeline"])
    resolved_duration = (
        cast(int, timeline["durationFrames"])
        if duration_frames is None
        else duration_frames
    )
    if (
        not isinstance(resolved_duration, int)
        or isinstance(resolved_duration, bool)
        or resolved_duration <= 0
    ):
        raise StudioSpikeError("Fusion title duration must be a positive integer")
    title_start = cast(int, timeline["startFrame"])
    title_end = title_start + resolved_duration
    for event in cast(list[Mapping[str, Any]], manifest["events"]):
        if event["trackId"] != track_id:
            continue
        record = cast(Mapping[str, int], event["recordRange"])
        event_start = record["startFrame"]
        event_end = event_start + record["durationFrames"]
        if title_start < event_end and event_start < title_end:
            raise StudioSpikeError(
                f"Fusion title overlaps manifest event {event['id']} on {track_id!r}"
            )
    return TextPlusPlacement(
        title_name=title_name,
        track_id=track_id,
        track_index=cast(int, track["index"]),
        record_frame=title_start,
        duration_frames=resolved_duration,
    )


def _template_connected_stop(
    template: TextPlusTemplate, connected: ConnectedFacts
) -> str | None:
    if template.validated_resolve_version is None:
        return (
            "The pinned Text+ template lacks a producer-accepted Resolve validation "
            "version; no project mutation occurred."
        )
    observed = f"{connected.version}.{int(connected.build):04d}"
    if observed != template.validated_resolve_version:
        return (
            "The pinned Text+ duration rule was validated only on Resolve "
            f"{template.validated_resolve_version}, not connected {observed}; no "
            "project mutation occurred."
        )
    return None


def _matches_text_plus_placement(
    item: Any, evidence: TitlePlacementEvidence, template: TextPlusTemplate
) -> bool:
    try:
        if (
            item.GetName() != evidence.title_name
            or item.GetStart(False) != evidence.record_frame
            or item.GetDuration(False) != evidence.duration_frames
        ):
            return False
        from .text_plus_validation import fingerprint_fusion_item

        fingerprint = fingerprint_fusion_item(item, template)
        return (
            fingerprint.tool_registration_ids == evidence.fusion_tool_registration_ids
        )
    except (AttributeError, StudioSpikeError, TypeError, ValueError):
        return False


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _bundle_identity(
    bundle_version: str | None, bundle_build: str | None
) -> tuple[int, int, int, int, str] | None:
    """Parse the observed numeric Resolve macOS bundle identity, or fail closed."""
    if bundle_version is None or bundle_build is None:
        return None
    version_match = VERSION_PATTERN.fullmatch(bundle_version)
    build_match = VERSION_PATTERN.fullmatch(bundle_build)
    if version_match is None or build_match is None:
        return None
    major, minor, patch = (int(value) for value in version_match.groups())
    build_major, build_minor, encoded_patch_build = (
        int(value) for value in build_match.groups()
    )
    encoded_patch, build = divmod(encoded_patch_build, 10_000)
    if (build_major, build_minor, encoded_patch) != (major, minor, patch):
        return None
    return major, minor, patch, build, ""


def _connected_identity(
    connected: ConnectedFacts,
) -> tuple[int, int, int, int, str] | None:
    if (
        not isinstance(connected.version, str)
        or not isinstance(connected.build, str)
        or not isinstance(connected.suffix, str)
        or not connected.build.isascii()
        or not connected.build.isdigit()
    ):
        return None
    version_match = VERSION_PATTERN.fullmatch(connected.version)
    if version_match is None:
        return None
    major, minor, patch = (int(value) for value in version_match.groups())
    return major, minor, patch, int(connected.build), connected.suffix


def _blackmagic_package_receipt() -> tuple[str | None, str | None]:
    try:
        result = subprocess.run(
            ["pkgutil", "--pkg-info-plist", BLACKMAGIC_RECEIPT_ID],
            check=True,
            capture_output=True,
            timeout=5,
        )
        value = plistlib.loads(result.stdout)
    except (OSError, subprocess.SubprocessError, plistlib.InvalidFileException):
        return None, None
    if not isinstance(value, dict):
        return None, None
    receipt_id = _optional_string(value.get("pkgid"))
    receipt_version = _optional_string(value.get("pkg-version"))
    if receipt_id != BLACKMAGIC_RECEIPT_ID:
        return None, None
    return receipt_id, receipt_version


def _fusion_title_fingerprint(item: Any) -> tuple[str, int, int, tuple[str, ...]]:
    name = item.GetName()
    start = item.GetStart(False)
    duration = item.GetDuration(False)
    composition_count = item.GetFusionCompCount()
    composition_names = item.GetFusionCompNameList()
    if (
        not isinstance(name, str)
        or not name
        or not isinstance(start, int)
        or not isinstance(duration, int)
        or duration <= 0
        or not isinstance(composition_count, int)
        or composition_count < 1
        or not isinstance(composition_names, (list, tuple))
        or len(composition_names) != composition_count
        or not all(isinstance(value, str) and value for value in composition_names)
    ):
        raise StudioSpikeError(
            "inserted Fusion title lacks a stable documented public fingerprint"
        )
    return name, start, duration, tuple(composition_names)


def _matches_fusion_title(
    item: Any, expected: tuple[str, int, int, tuple[str, ...]] | None
) -> bool:
    if expected is None:
        return False
    try:
        return _fusion_title_fingerprint(item) == expected
    except (AttributeError, StudioSpikeError, TypeError):
        return False


def _local_studio_stop(local: LocalFacts) -> str | None:
    if not local.app_installed:
        return "DaVinci Resolve is not installed at the configured application path."
    if local.install_source == "mac_app_store" or local.mas_receipt:
        return (
            "The Mac App Store Resolve build is not an allowed external-scripting "
            "target. Install supported standard desktop Resolve Studio; no API was "
            "imported."
        )
    if Path(local.app_path) != DEFAULT_APP_PATH:
        return (
            "The configured application path is not the standard default Resolve "
            "bundle path. A system-global package receipt cannot identify a custom "
            "or copied bundle, so the Studio spike fails closed before importing "
            "the API."
        )
    if local.install_source != "blackmagic_package_receipt":
        return (
            "Resolve exists, but no matching affirmative Blackmagic package receipt "
            "identifies this default bundle; the Studio spike fails closed before "
            "importing the API."
        )
    if local.bundle_identifier != BLACKMAGIC_BUNDLE_ID:
        return (
            "The configured bundle identifier is missing or does not identify "
            "standard desktop Resolve; the Studio spike fails closed before "
            "importing the API."
        )
    if _bundle_identity(local.bundle_version, local.bundle_build) is None:
        return (
            "The configured bundle version/build identity is missing or malformed; "
            "the Studio spike fails closed before importing the API."
        )
    if (
        local.package_receipt_id != BLACKMAGIC_RECEIPT_ID
        or local.package_receipt_version != local.bundle_version
    ):
        return (
            "The system package receipt does not affirmatively match the configured "
            "default bundle; the Studio spike fails closed before importing the API."
        )
    if not local.scripting_module_installed:
        return (
            "Resolve's supported Python scripting module is missing; no API was "
            "imported."
        )
    if not local.scripting_docs_installed:
        return "Resolve scripting documentation is missing; this spike fails closed."
    return None


def _connected_studio_stop(local: LocalFacts, connected: ConnectedFacts) -> str | None:
    if not connected.scripting_available:
        return (
            "External scripting is unavailable or disabled; no project mutation "
            "occurred."
        )
    if connected.edition != "studio":
        return (
            f"Connected product {connected.product_name!r} is not Studio; the verified "
            "package remains ready for manual Free import and no project mutation "
            "occurred."
        )
    local_identity = _bundle_identity(local.bundle_version, local.bundle_build)
    connected_identity = _connected_identity(connected)
    if connected_identity is None:
        return (
            "The connected Resolve returned a malformed version/build identity; no "
            "project mutation occurred."
        )
    if local_identity is None or connected_identity != local_identity:
        return (
            "The connected Resolve full version/build identity does not match the "
            "affirmatively detected bundle "
            f"({connected.version!r}, build {connected.build!r}, suffix "
            f"{connected.suffix!r} versus {local.bundle_version!r}, bundle build "
            f"{local.bundle_build!r}); no project mutation occurred."
        )
    return None


def _load_manifest(package_dir: Path) -> JsonObject:
    value = json.loads((package_dir / MANIFEST_NAME).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise StudioSpikeError("accepted package manifest is not an object")
    return cast(JsonObject, value)


def _resolved_sources(
    package_dir: Path, manifest: Mapping[str, Any]
) -> list[tuple[str, Path]]:
    return [
        (cast(str, source["id"]), (package_dir / cast(str, source["path"])).resolve())
        for source in cast(list[Mapping[str, Any]], manifest["sources"])
    ]


def _project_settings(timeline: Mapping[str, Any]) -> dict[str, str]:
    rate = cast(Mapping[str, int], timeline["frameRate"])
    rate_value = rate["numerator"] / rate["denominator"]
    return {
        "timelineFrameRate": f"{rate_value:.3f}".rstrip("0").rstrip("."),
        "timelineResolutionWidth": str(timeline["width"]),
        "timelineResolutionHeight": str(timeline["height"]),
        "timelineSampleRate": str(timeline["audioSampleRate"]),
    }


def _frame_timecode(frame: int) -> str:
    # The accepted spike starts at frame zero. Nonzero/drop-frame conversion is
    # deliberately not generalized without a manifest timecode-mode contract.
    if frame != 0:
        raise StudioSpikeError(
            "Fusion title insertion supports frame-zero spike placement only"
        )
    return "00:00:00:00"
