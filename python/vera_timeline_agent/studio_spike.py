"""Bounded Resolve Studio scripting spike with a fail-closed safety boundary."""

from __future__ import annotations

import importlib.util
import json
import platform
import plistlib
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol, cast

from vera_timeline_agent.otio_package import verify_otio_package

DEFAULT_APP_PATH = Path("/Applications/DaVinci Resolve/DaVinci Resolve.app")
DEFAULT_SCRIPTING_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/Developer/Scripting"
)
MANIFEST_NAME = "timeline-manifest.json"

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
    bundle_version: str | None
    bundle_build: str | None
    mas_receipt: bool
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

    def place_event(self, event: Mapping[str, Any]) -> None: ...

    def insert_fusion_title(self, title_name: str, record_frame: int) -> None: ...

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
    if not app_installed:
        install_source = "missing"
    elif mas_receipt:
        install_source = "mac_app_store"
    else:
        install_source = "blackmagic_standard"
    mac_version = platform.mac_ver()[0]
    return LocalFacts(
        os_name="macOS" if sys.platform == "darwin" else platform.system(),
        os_version=mac_version or platform.release(),
        architecture=platform.machine(),
        app_path=str(app_path),
        app_installed=app_installed,
        install_source=install_source,
        bundle_name=_optional_string(bundle.get("CFBundleDisplayName")),
        bundle_version=_optional_string(bundle.get("CFBundleShortVersionString")),
        bundle_build=_optional_string(bundle.get("CFBundleVersion")),
        mas_receipt=mas_receipt,
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
    connected_stop = _connected_studio_stop(connected)
    if connected_stop is not None:
        return CapabilityResult(
            status="stopped_safely",
            message=connected_stop,
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
        "The public API can insert a named Fusion title at the playhead but cannot "
        "enumerate stock Fusion titles or select/prove its destination video track.",
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
    try:
        adapter.create_project(resolved_project_name)
        adapter.configure_project(settings)
        adapter.create_bin("VERA Slice 0.4")
        adapter.create_bin("Accepted Media")
        adapter.import_media(sources)
        adapter.create_timeline(timeline_name)
        adapter.configure_tracks(cast(list[Mapping[str, Any]], manifest["tracks"]))
        for event in cast(list[Mapping[str, Any]], manifest["events"]):
            adapter.place_event(event)
        start_frame = cast(
            int, cast(Mapping[str, Any], manifest["timeline"])["startFrame"]
        )
        adapter.insert_fusion_title(fusion_title, start_frame)
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
    )


def load_resolve_adapter(local: LocalFacts) -> ResolveAdapter:
    """Import the vendor bridge and connect only after local safety checks pass."""
    module_path = Path(local.scripting_module_path)
    spec = importlib.util.spec_from_file_location("DaVinciResolveScript", module_path)
    if spec is None or spec.loader is None:
        raise StudioSpikeError(f"cannot load Resolve scripting module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    resolve = module.scriptapp("Resolve")
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
        self.fusion_title_id: str | None = None

    def connected_facts(self) -> ConnectedFacts:
        product = str(self.resolve.GetProductName())
        fields = list(self.resolve.GetVersion())
        version = ".".join(str(value) for value in fields[:3])
        build = str(fields[3]) if len(fields) > 3 else "unknown"
        edition = "studio" if "studio" in product.casefold() else "free"
        return ConnectedFacts(product, edition, version, build, True)

    def probe(self, settings: Mapping[str, str]) -> tuple[str, ...]:
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
            gaps.append(
                "No current project was available to nonmutatingly inspect Project "
                "settings and MediaPool method surfaces."
            )
            return tuple(gaps)
        if not callable(getattr(current, "GetSetting", None)):
            raise StudioSpikeError("current project has no callable GetSetting")
        for key in settings:
            if current.GetSetting(key) in (None, ""):
                raise StudioSpikeError(f"current project does not expose setting {key}")
        pool = current.GetMediaPool()
        if pool is None:
            raise StudioSpikeError("current project has no media pool")
        for method in ("ImportMedia", "CreateEmptyTimeline", "AddSubFolder"):
            if not callable(getattr(pool, method, None)):
                raise StudioSpikeError(f"media pool has no callable {method}")
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

    def place_event(self, event: Mapping[str, Any]) -> None:
        record = cast(Mapping[str, int], event["recordRange"])
        source = cast(Mapping[str, int], event.get("sourceRange", {}))
        start = source.get("startFrame", 0)
        duration = source.get("durationFrames", record["durationFrames"])
        info = {
            "mediaPoolItem": self.media_by_source[cast(str, event["sourceId"])],
            "startFrame": start,
            "endFrame": start + duration - 1,
            "mediaType": 2 if event["kind"] == "audio" else 1,
            "trackIndex": self._track_index(cast(str, event["trackId"])),
            "recordFrame": record["startFrame"],
        }
        placed = self.pool.AppendToTimeline([info])
        if not isinstance(placed, (list, tuple)) or len(placed) != 1:
            raise StudioSpikeError(f"AppendToTimeline failed for event {event['id']}")

    def _track_index(self, track_id: str) -> int:
        # Event adapters receive IDs, while the public API receives indices. The
        # manifest's accepted IDs have already been validated; retain their map.
        suffix_map = getattr(self, "_track_id_map", None)
        if suffix_map is None:
            raise StudioSpikeError("track ID map was not initialized")
        return cast(int, suffix_map[track_id])

    def insert_fusion_title(self, title_name: str, record_frame: int) -> None:
        if not self.timeline.SetCurrentTimecode(_frame_timecode(record_frame)):
            raise StudioSpikeError("could not position playhead for Fusion title")
        title = self.timeline.InsertFusionTitleIntoTimeline(title_name)
        if title is None:
            raise StudioSpikeError(f"Fusion title is unavailable: {title_name}")
        title_id = title.GetUniqueId()
        if not isinstance(title_id, str) or not title_id:
            raise StudioSpikeError("inserted Fusion title has no public unique ID")
        self.fusion_title_id = title_id

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
        if self.timeline.GetStartFrame() != expected_start:
            discrepancies.append("timeline start frame differs from manifest")
        if self.timeline.GetEndFrame() != expected_end:
            discrepancies.append("timeline end frame differs from manifest")
        self._verify_bins(discrepancies)
        expected_tracks = cast(list[Mapping[str, Any]], manifest["tracks"])
        for track in expected_tracks:
            kind, index, name = track["kind"], track["index"], track["name"]
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
        for (kind, index), expected_events in by_slot.items():
            actual_items = list(self.timeline.GetItemListInTrack(kind, index))
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
        title_ids = {
            item.GetUniqueId()
            for index in range(1, self.timeline.GetTrackCount("video") + 1)
            for item in self.timeline.GetItemListInTrack("video", index)
        }
        if self.fusion_title_id not in title_ids:
            discrepancies.append("inserted Fusion title was not found after reopen")
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


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _local_studio_stop(local: LocalFacts) -> str | None:
    if not local.app_installed:
        return "DaVinci Resolve is not installed at the configured application path."
    if local.install_source == "mac_app_store" or local.mas_receipt:
        return (
            "The Mac App Store Resolve build is not an allowed external-scripting "
            "target. Install supported standard desktop Resolve Studio; no API was "
            "imported."
        )
    if not local.scripting_module_installed:
        return (
            "Resolve's supported Python scripting module is missing; no API was "
            "imported."
        )
    if not local.scripting_docs_installed:
        return "Resolve scripting documentation is missing; this spike fails closed."
    return None


def _connected_studio_stop(connected: ConnectedFacts) -> str | None:
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
        "timelinePlaybackFrameRate": f"{rate_value:.3f}".rstrip("0").rstrip("."),
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
