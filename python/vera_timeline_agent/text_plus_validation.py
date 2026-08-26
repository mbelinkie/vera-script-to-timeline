"""Real-Resolve validation for the pinned Text+ media-pool template path."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from typing import Any, Protocol

from .studio_spike import (
    TIMELINE_PAGES,
    ConnectedFacts,
    LocalFacts,
    PublicResolveAdapter,
    StudioSpikeError,
    _connected_studio_stop,
    _local_studio_stop,
    detect_local_capabilities,
    load_resolve_adapter,
)
from .text_plus_template import (
    DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    TextPlusTemplate,
    validate_text_plus_template,
)


@dataclass(frozen=True)
class FusionFingerprint:
    """Documented Fusion graph identity used for stock/template comparison."""

    composition_count: int
    tool_registration_ids: tuple[str, ...]
    text_plus_tools: int


@dataclass(frozen=True)
class DurationObservation:
    """One requested/end-frame/observed-duration tuple."""

    requested_frames: int
    end_frame: int
    observed_duration_frames: int


@dataclass(frozen=True)
class TextPlusValidationEvidence:
    """Evidence produced by one mutation-authorized validation project."""

    asset_sha256: str
    authoring_resolve_version: str
    stock_fingerprint: FusionFingerprint
    template_fingerprint: FusionFingerprint
    duration_observations: tuple[DurationObservation, ...]
    append_end_frame_delta: int
    canonical_timeline_name: str
    canonical_track_index: int
    canonical_record_frame: int
    canonical_duration_frames: int


@dataclass(frozen=True)
class TextPlusValidationResult:
    """Stable CLI result for preflight, validation, or verification."""

    status: str
    message: str
    local: LocalFacts
    asset_sha256: str
    connected: ConnectedFacts | None = None
    project_name: str | None = None
    verified: bool = False
    discrepancies: tuple[str, ...] = ()
    evidence: TextPlusValidationEvidence | None = None

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class TextPlusValidationAdapter(Protocol):
    def connected_facts(self) -> ConnectedFacts: ...

    def probe(self, template: TextPlusTemplate) -> tuple[str, ...]: ...

    def check_project_name_available(self, name: str) -> None: ...

    def create_project(self, name: str) -> None: ...

    def validate(self, template: TextPlusTemplate) -> TextPlusValidationEvidence: ...

    def save_close_reopen(self, project_name: str) -> None: ...

    def verify_reopened(
        self, template: TextPlusTemplate, evidence: TextPlusValidationEvidence
    ) -> tuple[str, ...]: ...


ValidationAdapterFactory = Callable[[LocalFacts], TextPlusValidationAdapter]


def run_text_plus_validation(
    *,
    action: str,
    project_name: str,
    template_metadata: Any = DEFAULT_TEXT_PLUS_TEMPLATE_METADATA,
    local_facts: LocalFacts | None = None,
    adapter_factory: ValidationAdapterFactory | None = None,
) -> TextPlusValidationResult:
    """Preflight or run one retained, uniquely named Text+ validation project."""
    if action not in {"preflight", "build"}:
        raise StudioSpikeError("action must be 'preflight' or 'build'")
    if not isinstance(project_name, str) or not project_name.strip():
        raise StudioSpikeError("a nonempty unique project name is required")
    template = validate_text_plus_template(template_metadata)
    local = local_facts or detect_local_capabilities()
    local_stop = _local_studio_stop(local)
    if local_stop is not None:
        return TextPlusValidationResult(
            "stopped_safely", local_stop, local, template.sha256
        )
    if adapter_factory is None:
        adapter_factory = _load_public_validation_adapter
    try:
        adapter = adapter_factory(local)
        connected = adapter.connected_facts()
    except Exception as error:
        return TextPlusValidationResult(
            "stopped_safely",
            "Could not connect through Resolve's supported external scripting API; "
            f"no project mutation occurred. Detail: {error}",
            local,
            template.sha256,
        )
    connected_stop = _connected_studio_stop(local, connected)
    if connected_stop is not None:
        return TextPlusValidationResult(
            "stopped_safely",
            connected_stop,
            local,
            template.sha256,
            connected=connected,
        )
    try:
        adapter.probe(template)
        adapter.check_project_name_available(project_name)
    except Exception as error:
        return TextPlusValidationResult(
            "stopped_safely",
            f"Text+ validation preflight failed; no project mutation occurred: {error}",
            local,
            template.sha256,
            connected=connected,
        )
    if action == "preflight":
        return TextPlusValidationResult(
            "preflight_passed",
            "Text+ validation preflight passed without project mutation.",
            local,
            template.sha256,
            connected=connected,
            project_name=project_name,
        )
    try:
        adapter.create_project(project_name)
        evidence = adapter.validate(template)
        adapter.save_close_reopen(project_name)
        discrepancies = adapter.verify_reopened(template, evidence)
    except Exception as error:
        return TextPlusValidationResult(
            "mutation_failed",
            "Text+ validation failed after project creation. The uniquely named "
            f"project is retained for audit. Detail: {error}",
            local,
            template.sha256,
            connected=connected,
            project_name=project_name,
        )
    return TextPlusValidationResult(
        "verified" if not discrepancies else "verification_failed",
        (
            "Pinned Text+ validation passed and the retained project was reopened "
            "without discrepancies."
            if not discrepancies
            else "Pinned Text+ validation reopened with discrepancies."
        ),
        local,
        template.sha256,
        connected=connected,
        project_name=project_name,
        verified=not discrepancies,
        discrepancies=discrepancies,
        evidence=evidence,
    )


def _load_public_validation_adapter(local: LocalFacts) -> TextPlusValidationAdapter:
    base = load_resolve_adapter(local)
    resolve = getattr(base, "resolve", None)
    if resolve is None:
        raise StudioSpikeError("Resolve adapter does not expose the live API object")
    return PublicTextPlusValidationAdapter(resolve)


class PublicTextPlusValidationAdapter:
    """Checked public-API implementation of the retained capability validation."""

    STOCK_TIMELINE = "VERA Text+ stock comparison"
    MATRIX_TIMELINE = "VERA Text+ duration matrix"
    CANONICAL_TIMELINE = "VERA Text+ canonical V4"

    def __init__(self, resolve: Any) -> None:
        self.resolve = resolve
        self.manager: Any = None
        self.project: Any = None
        self.pool: Any = None

    def connected_facts(self) -> ConnectedFacts:
        return PublicResolveAdapter(self.resolve).connected_facts()

    def probe(self, template: TextPlusTemplate) -> tuple[str, ...]:
        if self.resolve.GetCurrentPage() not in TIMELINE_PAGES:
            raise StudioSpikeError("Resolve must be on a documented timeline page")
        manager = self.resolve.GetProjectManager()
        if manager is None:
            raise StudioSpikeError("GetProjectManager returned no object")
        _require_methods(
            manager,
            (
                "GetProjectListInCurrentFolder",
                "GetCurrentProject",
                "CreateProject",
                "SaveProject",
                "CloseProject",
                "LoadProject",
            ),
            "project manager",
        )
        if not isinstance(manager.GetProjectListInCurrentFolder(), (list, tuple)):
            raise StudioSpikeError("project list returned an unsupported value")
        current = manager.GetCurrentProject()
        if current is None:
            raise StudioSpikeError(
                "open the producer-authored Text+ project for nonmutating preflight"
            )
        pool = current.GetMediaPool()
        if pool is None:
            raise StudioSpikeError("current project has no media pool")
        _require_methods(
            pool,
            (
                "GetRootFolder",
                "SetCurrentFolder",
                "ImportFolderFromFile",
                "CreateEmptyTimeline",
                "AppendToTimeline",
            ),
            "media pool",
        )
        root = pool.GetRootFolder()
        _require_methods(root, ("GetSubFolderList", "GetClipList"), "media folder")
        timeline = current.GetCurrentTimeline()
        if timeline is None:
            raise StudioSpikeError("current project has no timeline for API preflight")
        _require_methods(
            timeline,
            (
                "AddTrack",
                "GetTrackCount",
                "GetItemListInTrack",
                "InsertFusionTitleIntoTimeline",
                "SetCurrentTimecode",
            ),
            "timeline",
        )
        fusion_item = _find_existing_fusion_item(timeline)
        fingerprint_fusion_item(fusion_item, template)
        self.manager = manager
        return ()

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
        settings = {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }
        for key, value in settings.items():
            if not self.project.SetSetting(key, value):
                raise StudioSpikeError(f"SetSetting failed for {key}={value}")

    def validate(self, template: TextPlusTemplate) -> TextPlusValidationEvidence:
        stock_timeline = self._new_timeline(self.STOCK_TIMELINE, 1)
        if not stock_timeline.SetCurrentTimecode("00:00:00:00"):
            raise StudioSpikeError("could not set stock comparison playhead")
        stock_item = stock_timeline.InsertFusionTitleIntoTimeline("Text+")
        if stock_item is None:
            raise StudioSpikeError("stock Text+ insertion failed")
        stock_fingerprint = fingerprint_fusion_item(stock_item, template)

        generator = import_template_generator(self.pool, template)
        matrix_timeline = self._new_timeline(self.MATRIX_TIMELINE, 3)
        observations: list[DurationObservation] = []
        template_fingerprint: FusionFingerprint | None = None
        matching_deltas: list[int] = []
        for track_index, end_frame in enumerate((23, 24, 25), start=1):
            item = append_template_item(
                self.pool,
                generator,
                matrix_timeline,
                start_frame=0,
                end_frame=end_frame,
                record_frame=0,
                track_index=track_index,
            )
            observed = _exact_item_int(item, "GetDuration")
            observations.append(DurationObservation(24, end_frame, observed))
            if template_fingerprint is None:
                template_fingerprint = fingerprint_fusion_item(item, template)
            if observed == 24:
                matching_deltas.append(end_frame - 24)
        if len(matching_deltas) != 1:
            raise StudioSpikeError(
                "duration matrix did not identify exactly one 24-frame end rule"
            )
        if template_fingerprint != stock_fingerprint:
            raise StudioSpikeError(
                "pinned-template Fusion graph differs from stock Text+"
            )
        delta = matching_deltas[0]
        canonical = self._new_timeline(self.CANONICAL_TIMELINE, 4)
        canonical_item = append_template_item(
            self.pool,
            generator,
            canonical,
            start_frame=0,
            end_frame=72 + delta,
            record_frame=0,
            track_index=4,
        )
        canonical_duration = _exact_item_int(canonical_item, "GetDuration")
        canonical_start = _exact_item_int(canonical_item, "GetStart")
        observations.append(DurationObservation(72, 72 + delta, canonical_duration))
        if canonical_duration != 72 or canonical_start != 0:
            raise StudioSpikeError(
                "canonical Text+ did not land at frame 0 for exactly 72 frames"
            )
        if fingerprint_fusion_item(canonical_item, template) != stock_fingerprint:
            raise StudioSpikeError("canonical Text+ fingerprint differs from stock")
        _verify_single_track_item(canonical, 4)
        return TextPlusValidationEvidence(
            asset_sha256=template.sha256,
            authoring_resolve_version=template.authoring_resolve_version,
            stock_fingerprint=stock_fingerprint,
            template_fingerprint=template_fingerprint,
            duration_observations=tuple(observations),
            append_end_frame_delta=delta,
            canonical_timeline_name=self.CANONICAL_TIMELINE,
            canonical_track_index=4,
            canonical_record_frame=0,
            canonical_duration_frames=72,
        )

    def save_close_reopen(self, project_name: str) -> None:
        if not self.manager.SaveProject():
            raise StudioSpikeError("SaveProject failed")
        if not self.manager.CloseProject(self.project):
            raise StudioSpikeError("CloseProject failed after save")
        self.project = self.manager.LoadProject(project_name)
        if self.project is None:
            raise StudioSpikeError("LoadProject failed after close")
        self.pool = self.project.GetMediaPool()

    def verify_reopened(
        self, template: TextPlusTemplate, evidence: TextPlusValidationEvidence
    ) -> tuple[str, ...]:
        discrepancies: list[str] = []
        try:
            generator = find_imported_template_generator(self.pool, template)
            if generator.GetName() != template.expected_clip_name:
                discrepancies.append("reopened template clip name differs")
            timeline = _timeline_by_name(self.project, evidence.canonical_timeline_name)
            items = list(
                timeline.GetItemListInTrack("video", evidence.canonical_track_index)
                or []
            )
            if len(items) != 1:
                discrepancies.append(
                    "reopened canonical V4 does not contain exactly one item"
                )
            else:
                item = items[0]
                if _exact_item_int(item, "GetStart") != evidence.canonical_record_frame:
                    discrepancies.append("reopened canonical title start differs")
                if (
                    _exact_item_int(item, "GetDuration")
                    != evidence.canonical_duration_frames
                ):
                    discrepancies.append("reopened canonical title duration differs")
                if (
                    fingerprint_fusion_item(item, template)
                    != evidence.stock_fingerprint
                ):
                    discrepancies.append("reopened canonical fingerprint differs")
            for index in range(1, timeline.GetTrackCount("video") + 1):
                if index == evidence.canonical_track_index:
                    continue
                if list(timeline.GetItemListInTrack("video", index) or []):
                    discrepancies.append(
                        f"reopened canonical timeline has an unexpected V{index} item"
                    )
        except (AttributeError, StudioSpikeError, TypeError, ValueError) as error:
            discrepancies.append(f"reopened validation inspection failed: {error}")
        return tuple(discrepancies)

    def _new_timeline(self, name: str, video_tracks: int) -> Any:
        timeline = self.pool.CreateEmptyTimeline(name)
        if timeline is None:
            raise StudioSpikeError(f"CreateEmptyTimeline failed for {name}")
        if not timeline.SetStartTimecode("00:00:00:00"):
            raise StudioSpikeError(f"SetStartTimecode failed for {name}")
        while timeline.GetTrackCount("video") < video_tracks:
            if not timeline.AddTrack("video"):
                raise StudioSpikeError(f"AddTrack failed for {name}")
        return timeline


def fingerprint_fusion_item(item: Any, template: TextPlusTemplate) -> FusionFingerprint:
    """Fingerprint a title through documented TimelineItem/Fusion APIs."""
    count = item.GetFusionCompCount()
    if count != template.expected_fusion_compositions:
        raise StudioSpikeError(
            f"expected {template.expected_fusion_compositions} Fusion composition, "
            f"got {count!r}"
        )
    composition = item.GetFusionCompByIndex(1)
    if composition is None:
        raise StudioSpikeError("GetFusionCompByIndex(1) returned no composition")
    tools = composition.GetToolList(False)
    if not isinstance(tools, dict) or not tools:
        raise StudioSpikeError("Fusion composition returned no tool map")
    registration_ids: list[str] = []
    for tool in tools.values():
        registration_id = tool.GetAttrs("TOOLS_RegID")
        if not isinstance(registration_id, str) or not registration_id:
            raise StudioSpikeError("Fusion tool has no documented registration ID")
        registration_ids.append(registration_id)
    text_plus_count = sum(value == "TextPlus" for value in registration_ids)
    if text_plus_count != template.expected_text_plus_tools:
        raise StudioSpikeError(
            f"expected {template.expected_text_plus_tools} TextPlus tool, "
            f"got {text_plus_count}"
        )
    sorted_ids = tuple(sorted(registration_ids))
    if sorted_ids != template.expected_tool_registration_ids:
        raise StudioSpikeError(
            "Fusion tool registration IDs differ from pinned template provenance"
        )
    return FusionFingerprint(count, sorted_ids, text_plus_count)


def import_template_generator(pool: Any, template: TextPlusTemplate) -> Any:
    """Import the pinned DRB and return its single direct generator clip."""
    root = pool.GetRootFolder()
    if root is None:
        raise StudioSpikeError("media pool has no root folder")
    if _folders_named(root, template.expected_bin_name):
        raise StudioSpikeError(
            f"template bin already exists: {template.expected_bin_name!r}"
        )
    current = pool.GetCurrentFolder()
    if not pool.SetCurrentFolder(root):
        raise StudioSpikeError("could not select media-pool root for template import")
    try:
        if not pool.ImportFolderFromFile(str(template.asset_path), ""):
            raise StudioSpikeError("ImportFolderFromFile rejected the Text+ template")
    finally:
        if current is not None and not pool.SetCurrentFolder(current):
            raise StudioSpikeError("could not restore the previous media-pool folder")
    return find_imported_template_generator(pool, template)


def find_imported_template_generator(pool: Any, template: TextPlusTemplate) -> Any:
    root = pool.GetRootFolder()
    matches = _folders_named(root, template.expected_bin_name)
    if len(matches) != 1:
        raise StudioSpikeError(
            f"expected exactly one imported bin {template.expected_bin_name!r}, "
            f"got {len(matches)}"
        )
    folder = matches[0]
    if list(folder.GetSubFolderList() or []):
        raise StudioSpikeError("imported Text+ template bin contains subfolders")
    clips = list(folder.GetClipList() or [])
    if len(clips) != 1:
        raise StudioSpikeError(
            f"expected exactly one imported template clip, got {len(clips)}"
        )
    if clips[0].GetName() != template.expected_clip_name:
        raise StudioSpikeError(
            f"imported template clip name differs from {template.expected_clip_name!r}"
        )
    return clips[0]


def append_template_item(
    pool: Any,
    generator: Any,
    timeline: Any,
    *,
    start_frame: int,
    end_frame: int,
    record_frame: int,
    track_index: int,
) -> Any:
    """Append exactly one generator through documented clipInfo fields."""
    before = list(timeline.GetItemListInTrack("video", track_index) or [])
    if any(_exact_item_int(item, "GetStart") == record_frame for item in before):
        raise StudioSpikeError(
            "requested Text+ slot is already occupied on the destination track"
        )
    values = [
        {
            "mediaPoolItem": generator,
            "startFrame": start_frame,
            "endFrame": end_frame,
            "recordFrame": record_frame,
            "trackIndex": track_index,
            "mediaType": 1,
        }
    ]
    placed = pool.AppendToTimeline(values)
    if not isinstance(placed, (list, tuple)) or len(placed) != 1:
        raise StudioSpikeError("AppendToTimeline did not return exactly one Text+ item")
    track_items = list(timeline.GetItemListInTrack("video", track_index) or [])
    if len(track_items) != len(before) + 1:
        raise StudioSpikeError(
            "destination track item count did not increase by exactly one"
        )
    candidates = [
        item
        for item in track_items
        if _exact_item_int(item, "GetStart") == record_frame
    ]
    if len(candidates) != 1:
        raise StudioSpikeError(
            "could not identify exactly one Text+ item at the requested frame"
        )
    return candidates[0]


def _require_methods(value: Any, names: tuple[str, ...], label: str) -> None:
    for name in names:
        if not callable(getattr(value, name, None)):
            raise StudioSpikeError(f"{label} has no callable {name}")


def _find_existing_fusion_item(timeline: Any) -> Any:
    for index in range(1, timeline.GetTrackCount("video") + 1):
        for item in timeline.GetItemListInTrack("video", index) or []:
            if callable(getattr(item, "GetFusionCompCount", None)):
                count = item.GetFusionCompCount()
                if isinstance(count, int) and count > 0:
                    return item
    raise StudioSpikeError(
        "current timeline has no Fusion item for nonmutating composition preflight"
    )


def _folders_named(root: Any, name: str) -> list[Any]:
    matches: list[Any] = []
    pending = list(root.GetSubFolderList() or []) if root is not None else []
    visited = 0
    while pending:
        folder = pending.pop(0)
        visited += 1
        if visited > 256:
            raise StudioSpikeError("media-pool folder traversal exceeded safety limit")
        if folder.GetName() == name:
            matches.append(folder)
        pending.extend(list(folder.GetSubFolderList() or []))
    return matches


def _exact_item_int(item: Any, method_name: str) -> int:
    value = getattr(item, method_name)(False)
    if not isinstance(value, int) or isinstance(value, bool):
        raise StudioSpikeError(f"{method_name} returned a non-integer frame value")
    return value


def _verify_single_track_item(timeline: Any, index: int) -> None:
    for current in range(1, timeline.GetTrackCount("video") + 1):
        items = list(timeline.GetItemListInTrack("video", current) or [])
        if current == index:
            if len(items) != 1:
                raise StudioSpikeError(
                    f"canonical timeline does not contain exactly one item on V{index}"
                )
        elif items:
            raise StudioSpikeError(
                f"canonical timeline contains an unexpected item on V{current}"
            )


def _timeline_by_name(project: Any, name: str) -> Any:
    matches = [
        project.GetTimelineByIndex(index)
        for index in range(1, int(project.GetTimelineCount()) + 1)
    ]
    named = [timeline for timeline in matches if timeline.GetName() == name]
    if len(named) != 1:
        raise StudioSpikeError(
            f"expected exactly one reopened timeline named {name!r}, got {len(named)}"
        )
    return named[0]
