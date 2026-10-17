"""Fail-closed semantic-control boundary for the registered EV24 lower third."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Protocol

from .studio_spike import (
    ConnectedFacts,
    LocalFacts,
    StudioSpikeError,
    detect_local_capabilities,
    load_resolve_adapter,
)

EV24_COUNTRIES = (
    "albania",
    "andorra",
    "armenia",
    "australia",
    "austria",
    "azerbaijan",
    "belarus",
    "belgium",
    "bosnia-and-herzegovina",
    "bulgaria",
    "canada",
    "croatia",
    "cyprus",
    "czechia",
    "denmark",
    "estonia",
    "finland",
    "france",
    "georgia",
    "germany",
    "greece",
    "hungary",
    "iceland",
    "ireland",
    "israel",
    "italy",
    "latvia",
    "lithuania",
    "luxembourg",
    "malta",
    "moldova",
    "monaco",
    "montenegro",
    "morocco",
    "netherlands",
    "north-macedonia",
    "norway",
    "poland",
    "portugal",
    "romania",
    "russia",
    "san-marino",
    "serbia",
    "serbia-and-montenegro",
    "slovakia",
    "slovenia",
    "spain",
    "sweden",
    "switzerland",
    "turkiye",
    "ukraine",
    "united-kingdom",
    "yugoslavia",
    "otis",
)
EV24_TEST_BADGE_ID = "ev24-package-test-badge"
EV24_CONTROL_NAMES = frozenset(
    {"Country", "Year", "TopLine", "BottomLine", "BadgeOverride"}
)
EV24_ROOT_TOOL = "EV24LowerThird"
# The pinned macro's MainOutput1 delegates to this internal Transform's Output.
EV24_RENDER_OUTPUT_TOOL = "MasterTransform"
EV24_SETTING_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages/contracts/assets/ev24-lower-third/EV24 Lower Third.setting"
)
EV24_TEST_BADGE_PATH = (
    Path(__file__).resolve().parents[2]
    / "packages/contracts/assets/ev24-lower-third/badge_override_test_only.png"
)
EV24_SETTING_SHA256 = "7abb4e07a3c6472fd93e6b752a8623855f2fa03a8591fff10e6e33746e7ff2df"
EV24_TEST_BADGE_SHA256 = (
    "a631b15479a795f0f614b7681d9210dac74bd2583b311f8c8861682543a58003"
)


class Ev24SpikeError(RuntimeError):
    """A pinned-template or documented-API check failed closed."""


@dataclass(frozen=True)
class Ev24Request:
    name: str
    country: str
    year: int | None = None
    top_line_override: str | None = None
    bottom_line_override: str | None = None
    badge_asset_id: str | None = None
    duration_frames: int = 120


@dataclass(frozen=True)
class PreparedEv24Request:
    request: Ev24Request
    semantic_snapshot: dict[str, str | int]
    control_values: dict[str, str | int]


@dataclass(frozen=True)
class Ev24ConfigurationReport:
    name: str
    semantic_snapshot: dict[str, str | int]
    graph_identity: str
    placement: str
    duration_frames: int
    control_readback: dict[str, str | int]
    badge_asset_identity: str | None


@dataclass(frozen=True)
class Ev24SpikeResult:
    status: str
    message: str
    local: LocalFacts
    setting_sha256: str
    connected: ConnectedFacts | None = None
    project_name: str | None = None
    verified: bool = False
    discrepancies: tuple[str, ...] = ()
    reports: tuple[Ev24ConfigurationReport, ...] = ()

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2, sort_keys=True) + "\n"


class Ev24Adapter(Protocol):
    def connected_facts(self) -> ConnectedFacts: ...

    def probe(self) -> None: ...

    def check_project_name_available(self, name: str) -> None: ...

    def create_project(self, name: str) -> None: ...

    def exercise(
        self, requests: tuple[PreparedEv24Request, ...]
    ) -> tuple[Ev24ConfigurationReport, ...]: ...

    def save_close_reopen(self, project_name: str) -> None: ...

    def verify_reopened(
        self, reports: tuple[Ev24ConfigurationReport, ...]
    ) -> tuple[str, ...]: ...


AdapterFactory = Callable[[LocalFacts], Ev24Adapter]


def prepare_ev24_request(request: Ev24Request) -> PreparedEv24Request:
    """Translate one typed request without exposing Fusion names to callers."""
    if request.country not in EV24_COUNTRIES:
        raise Ev24SpikeError("country is not a registered EV24 identity")
    if request.country == "otis":
        if request.year is not None:
            raise Ev24SpikeError("otis must omit year from the semantic snapshot")
    elif (
        not isinstance(request.year, int)
        or isinstance(request.year, bool)
        or request.year < 1
    ):
        raise Ev24SpikeError("year is required for every non-otis country")
    if not isinstance(request.name, str) or not request.name:
        raise Ev24SpikeError("configuration name is required")
    if request.duration_frames not in {64, 120}:
        raise Ev24SpikeError(
            "the capability spike permits only 64- or 120-frame placements"
        )
    for value in (request.top_line_override, request.bottom_line_override):
        if value is not None and not isinstance(value, str):
            raise Ev24SpikeError("text overrides must be strings")
    if request.badge_asset_id not in {None, EV24_TEST_BADGE_ID}:
        raise Ev24SpikeError("badge override must be the declared package test badge")
    snapshot: dict[str, str | int] = {"country": request.country}
    if request.year is not None:
        snapshot["year"] = request.year
    if request.top_line_override is not None:
        snapshot["topLineOverride"] = request.top_line_override
    if request.bottom_line_override is not None:
        snapshot["bottomLineOverride"] = request.bottom_line_override
    if request.badge_asset_id is not None:
        snapshot["badgeOverrideAsset"] = request.badge_asset_id
    controls: dict[str, str | int] = {
        "Country": EV24_COUNTRIES.index(request.country),
        "TopLine": request.top_line_override or "",
        "BottomLine": request.bottom_line_override or "",
    }
    if request.year is not None:
        controls["Year"] = request.year
    if request.badge_asset_id is not None:
        controls["BadgeOverride"] = request.badge_asset_id
    return PreparedEv24Request(request, snapshot, controls)


class Ev24Controls:
    """One discovered macro; it permits no control discovery fallbacks."""

    def __init__(self, tool: Any) -> None:
        self._tool = tool
        self.read_values(tuple(sorted(EV24_CONTROL_NAMES)))

    def set_values(self, values: Mapping[str, str | int]) -> None:
        for name, value in values.items():
            if name not in EV24_CONTROL_NAMES:
                raise Ev24SpikeError(f"registered control {name!r} is not available")
            try:
                self._tool.SetInput(name, value)
            except (AttributeError, TypeError, ValueError) as error:
                raise Ev24SpikeError(
                    f"registered control {name!r} is type-incompatible"
                ) from error

    def read_values(self, names: tuple[str, ...]) -> dict[str, Any]:
        values: dict[str, Any] = {}
        for name in names:
            if name not in EV24_CONTROL_NAMES:
                raise Ev24SpikeError(f"registered control {name!r} is not available")
            try:
                value = self._tool.GetInput(name)
            except (AttributeError, TypeError, ValueError) as error:
                raise Ev24SpikeError(
                    f"registered control {name!r} cannot be read"
                ) from error
            if (
                value is None
                or isinstance(value, bool)
                or not isinstance(value, (str, int, float))
            ):
                raise Ev24SpikeError(
                    f"registered control {name!r} returned an incompatible value"
                )
            values[name] = value
        return values


def discover_ev24_controls(item: Any) -> Ev24Controls:
    """Require precisely the one pinned EV24 macro and no substitute graph."""
    try:
        count = item.GetFusionCompCount()
    except (AttributeError, TypeError) as error:
        raise Ev24SpikeError(
            "timeline item exposes no Fusion composition count"
        ) from error
    if count != 1:
        raise Ev24SpikeError(
            f"expected exactly one EV24LowerThird composition, got {count!r}"
        )
    try:
        composition = item.GetFusionCompByIndex(1)
        tools = composition.GetToolList(False) if composition is not None else None
    except (AttributeError, TypeError) as error:
        raise Ev24SpikeError("EV24 composition cannot be discovered") from error
    if not isinstance(tools, dict) or not tools:
        raise Ev24SpikeError("EV24 composition returned no tool map")
    roots = []
    for tool in tools.values():
        try:
            name = tool.GetAttrs("TOOLS_Name")
            registration_id = tool.GetAttrs("TOOLS_RegID")
        except (AttributeError, TypeError) as error:
            raise Ev24SpikeError("EV24 graph tool identity is unreadable") from error
        if name == EV24_ROOT_TOOL:
            roots.append((tool, registration_id))
    if len(roots) != 1 or roots[0][1] != "MacroOperator":
        raise Ev24SpikeError("expected exactly one EV24LowerThird MacroOperator")
    tool = roots[0][0]
    if not callable(getattr(tool, "SetInput", None)) or not callable(
        getattr(tool, "GetInput", None)
    ):
        raise Ev24SpikeError("EV24LowerThird controls are not readable and writable")
    return Ev24Controls(tool)


def connect_ev24_to_media_out(item: Any) -> Any:
    """Wire the imported macro to the one timeline output Resolve needs to render it."""
    composition, tools = _ev24_composition_tools(item)
    root = _ev24_root_tool(tools)
    try:
        locked = composition.Lock()
    except (AttributeError, TypeError, ValueError) as error:
        raise Ev24SpikeError("could not lock the EV24 Fusion composition") from error
    if locked is False:
        raise Ev24SpikeError("Resolve rejected the EV24 Fusion composition lock")
    try:
        outputs = [
            tool
            for tool in tools.values()
            if tool.GetAttrs("TOOLS_RegID") == "MediaOut"
        ]
        if len(outputs) > 1:
            raise Ev24SpikeError("EV24 composition has duplicate MediaOut tools")
        if not outputs:
            output = composition.AddTool("MediaOut", 0, 0)
            if output is None or output.GetAttrs("TOOLS_RegID") != "MediaOut":
                raise Ev24SpikeError(
                    "EV24 output creation returned an incompatible tool"
                )
        else:
            output = outputs[0]
        connected = output.ConnectInput("Input", root)
        if connected is False:
            raise Ev24SpikeError(
                "Resolve rejected the EV24LowerThird-to-MediaOut connection"
            )
    except (AttributeError, TypeError, ValueError) as error:
        raise Ev24SpikeError("could not connect EV24LowerThird to MediaOut") from error
    finally:
        try:
            composition.Unlock()
        except (AttributeError, TypeError, ValueError) as error:
            raise Ev24SpikeError(
                "could not unlock the EV24 Fusion composition"
            ) from error
    _verify_ev24_media_out(item)
    return output


def _verify_ev24_media_out(item: Any) -> None:
    _, tools = _ev24_composition_tools(item)
    outputs = [
        tool for tool in tools.values() if tool.GetAttrs("TOOLS_RegID") == "MediaOut"
    ]
    if len(outputs) != 1:
        raise Ev24SpikeError("EV24 composition must contain exactly one MediaOut")
    try:
        source = outputs[0].FindMainInput(1).GetConnectedOutput().GetTool()
        source_name = source.GetAttrs("TOOLS_Name")
    except (AttributeError, TypeError, ValueError) as error:
        raise Ev24SpikeError("EV24 MediaOut connection is unreadable") from error
    if source_name != EV24_RENDER_OUTPUT_TOOL:
        raise Ev24SpikeError("EV24LowerThird is not connected to MediaOut")


def _ev24_composition_tools(item: Any) -> tuple[Any, dict[Any, Any]]:
    try:
        count = item.GetFusionCompCount()
        composition = item.GetFusionCompByIndex(1)
        tools = composition.GetToolList(False) if composition is not None else None
    except (AttributeError, TypeError) as error:
        raise Ev24SpikeError("EV24 composition cannot be discovered") from error
    if count != 1 or not isinstance(tools, dict) or not tools:
        raise Ev24SpikeError("expected exactly one EV24 Fusion composition with tools")
    return composition, tools


def _ev24_root_tool(tools: dict[Any, Any]) -> Any:
    roots = []
    for tool in tools.values():
        try:
            name = tool.GetAttrs("TOOLS_Name")
            registration_id = tool.GetAttrs("TOOLS_RegID")
        except (AttributeError, TypeError) as error:
            raise Ev24SpikeError("EV24 graph tool identity is unreadable") from error
        if name == EV24_ROOT_TOOL:
            roots.append((tool, registration_id))
    if len(roots) != 1 or roots[0][1] != "MacroOperator":
        raise Ev24SpikeError("expected exactly one EV24LowerThird MacroOperator")
    return roots[0][0]


def retained_ev24_requests() -> tuple[PreparedEv24Request, ...]:
    """The four issue-owned configurations; no caller-provided semantic surface."""
    return tuple(
        prepare_ev24_request(request)
        for request in (
            Ev24Request("standard-auto-fill-120", "finland", 2024, duration_frames=120),
            Ev24Request(
                "explicit-overrides-120",
                "malta",
                2024,
                top_line_override="The Code",
                bottom_line_override="Nemo",
                duration_frames=120,
            ),
            Ev24Request("otis-auto-fill-64", "otis", duration_frames=64),
            Ev24Request(
                "test-badge-64",
                "austria",
                2024,
                badge_asset_id=EV24_TEST_BADGE_ID,
                duration_frames=64,
            ),
        )
    )


def run_ev24_spike(
    *,
    action: str,
    project_name: str,
    local_facts: LocalFacts | None = None,
    adapter_factory: AdapterFactory | None = None,
) -> Ev24SpikeResult:
    """Run the bounded preflight or one retained, uniquely named audit project."""
    if action not in {"preflight", "build"}:
        raise Ev24SpikeError("action must be 'preflight' or 'build'")
    if not isinstance(project_name, str) or not project_name.strip():
        raise Ev24SpikeError("a nonempty unique project name is required")
    _verify_pinned_package()
    local = local_facts or detect_local_capabilities()
    local_stop = _local_ev24_stop(local)
    if local_stop is not None:
        return Ev24SpikeResult("stopped_safely", local_stop, local, EV24_SETTING_SHA256)
    if adapter_factory is None:
        adapter_factory = _load_public_ev24_adapter
    try:
        adapter = adapter_factory(local)
        connected = adapter.connected_facts()
    except Exception as error:
        return Ev24SpikeResult(
            "stopped_safely",
            "Could not connect through Resolve's supported external scripting API; "
            f"no project mutation occurred. Detail: {error}",
            local,
            EV24_SETTING_SHA256,
        )
    connected_stop = _connected_ev24_stop(connected)
    if connected_stop is not None:
        return Ev24SpikeResult(
            "stopped_safely", connected_stop, local, EV24_SETTING_SHA256, connected
        )
    try:
        adapter.probe()
        adapter.check_project_name_available(project_name)
    except Exception as error:
        return Ev24SpikeResult(
            "stopped_safely",
            f"EV24 preflight failed; no project mutation occurred: {error}",
            local,
            EV24_SETTING_SHA256,
            connected,
        )
    if action == "preflight":
        return Ev24SpikeResult(
            "preflight_passed",
            "EV24 semantic-input preflight passed without project mutation.",
            local,
            EV24_SETTING_SHA256,
            connected,
            project_name,
        )
    try:
        adapter.create_project(project_name)
        reports = adapter.exercise(retained_ev24_requests())
        adapter.save_close_reopen(project_name)
        discrepancies = adapter.verify_reopened(reports)
    except Exception as error:
        return Ev24SpikeResult(
            "mutation_failed",
            "EV24 spike failed after project creation. The uniquely named project "
            f"is retained for audit. Detail: {error}",
            local,
            EV24_SETTING_SHA256,
            connected,
            project_name,
        )
    return Ev24SpikeResult(
        "verified" if not discrepancies else "verification_failed",
        "EV24 audit project saved, reopened, and verified without discrepancies."
        if not discrepancies
        else "EV24 audit project reopened with discrepancies.",
        local,
        EV24_SETTING_SHA256,
        connected,
        project_name,
        verified=not discrepancies,
        discrepancies=discrepancies,
        reports=reports,
    )


def _verify_pinned_package() -> None:
    for path, expected in (
        (EV24_SETTING_PATH, EV24_SETTING_SHA256),
        (EV24_TEST_BADGE_PATH, EV24_TEST_BADGE_SHA256),
    ):
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError as error:
            raise Ev24SpikeError(
                f"registered EV24 package file is unavailable: {path.name}"
            ) from error
        if actual != expected:
            raise Ev24SpikeError(
                f"registered EV24 package file hash differs: {path.name}"
            )


def _local_ev24_stop(local: LocalFacts) -> str | None:
    if not local.app_installed or not local.scripting_module_installed:
        return "Resolve Studio and its supported scripting module must be installed."
    if local.bundle_version != "21.1.0" or local.bundle_build not in {
        "21.1.00014",
        "21.1.0.0014",
    }:
        return (
            "The registered EV24 template is pinned to Resolve Studio 21.1.0 build 14."
        )
    return None


def _connected_ev24_stop(connected: ConnectedFacts) -> str | None:
    if (
        connected.product_name != "DaVinci Resolve Studio"
        or connected.edition != "studio"
        or not connected.scripting_available
        or connected.version != "21.1.0"
        or connected.build != "14"
        or connected.suffix
    ):
        return (
            "Connected Resolve identity differs from the pinned Studio 21.1.0 "
            "build 14 baseline."
        )
    return None


def _load_public_ev24_adapter(local: LocalFacts) -> Ev24Adapter:
    base = load_resolve_adapter(local)
    resolve = getattr(base, "resolve", None)
    if resolve is None:
        raise StudioSpikeError("Resolve adapter does not expose the live API object")
    return PublicEv24Adapter(resolve)


class PublicEv24Adapter:
    """Place a pinned seed still on V4, then use documented ImportFusionComp."""

    def __init__(self, resolve: Any) -> None:
        self.resolve = resolve
        self.manager: Any = None
        self.project: Any = None
        self.pool: Any = None

    def connected_facts(self) -> ConnectedFacts:
        from .studio_spike import PublicResolveAdapter

        return PublicResolveAdapter(self.resolve).connected_facts()

    def probe(self) -> None:
        if self.resolve.GetCurrentPage() not in {
            "cut",
            "edit",
            "color",
            "fairlight",
            "deliver",
        }:
            raise Ev24SpikeError("Resolve must be on a documented timeline page")
        self.manager = self.resolve.GetProjectManager()
        _require_methods(
            self.manager,
            (
                "GetProjectListInCurrentFolder",
                "CreateProject",
                "SaveProject",
                "CloseProject",
                "LoadProject",
            ),
            "project manager",
        )
        if not isinstance(self.manager.GetProjectListInCurrentFolder(), (list, tuple)):
            raise Ev24SpikeError("project list returned an unsupported value")

    def check_project_name_available(self, name: str) -> None:
        if name in self.manager.GetProjectListInCurrentFolder():
            raise Ev24SpikeError(
                f"project already exists; refusing to overwrite or reuse it: {name}"
            )

    def create_project(self, name: str) -> None:
        self.check_project_name_available(name)
        self.project = self.manager.CreateProject(name)
        if self.project is None:
            raise Ev24SpikeError(f"CreateProject failed for {name}")
        self.pool = self.project.GetMediaPool()
        if self.pool is None:
            raise Ev24SpikeError("created project has no media pool")
        for key, value in {
            "timelineFrameRate": "23.976",
            "timelineResolutionWidth": "1920",
            "timelineResolutionHeight": "1080",
        }.items():
            if not self.project.SetSetting(key, value):
                raise Ev24SpikeError(f"SetSetting failed for {key}={value}")

    def exercise(
        self, requests: tuple[PreparedEv24Request, ...]
    ) -> tuple[Ev24ConfigurationReport, ...]:
        _require_methods(
            self.pool,
            ("ImportMedia", "CreateEmptyTimeline", "AppendToTimeline"),
            "media pool",
        )
        imported = self.pool.ImportMedia([str(EV24_TEST_BADGE_PATH)])
        if not isinstance(imported, (list, tuple)) or len(imported) != 1:
            raise Ev24SpikeError("could not import the declared EV24 test badge")
        seed = imported[0]
        _require_methods(seed, ("SetMarkInOut", "ClearMarkInOut"), "test badge")
        reports: list[Ev24ConfigurationReport] = []
        for request in requests:
            timeline = self._new_timeline(f"EV24 {request.request.name}")
            item = self._place_seed(seed, timeline, request.request.duration_frames)
            if item.ImportFusionComp(str(EV24_SETTING_PATH)) is None:
                raise Ev24SpikeError(
                    "ImportFusionComp rejected the pinned EV24 setting"
                )
            connect_ev24_to_media_out(item)
            controls = discover_ev24_controls(item)
            physical_controls = dict(request.control_values)
            if physical_controls.get("BadgeOverride") == EV24_TEST_BADGE_ID:
                physical_controls["BadgeOverride"] = str(EV24_TEST_BADGE_PATH)
            controls.set_values(physical_controls)
            actual = controls.read_values(tuple(physical_controls))
            if actual != physical_controls:
                raise Ev24SpikeError(
                    f"{request.request.name} control readback differs before save"
                )
            if (
                _exact_item_int(item, "GetStart") != 0
                or _exact_item_int(item, "GetDuration")
                != request.request.duration_frames
            ):
                raise Ev24SpikeError(
                    f"{request.request.name} did not retain exact V4 placement "
                    "or duration"
                )
            reports.append(
                Ev24ConfigurationReport(
                    request.request.name,
                    request.semantic_snapshot,
                    f"sha256:{EV24_SETTING_SHA256}",
                    "V4@0",
                    request.request.duration_frames,
                    dict(request.control_values),
                    request.request.badge_asset_id,
                )
            )
        return tuple(reports)

    def save_close_reopen(self, project_name: str) -> None:
        if not self.manager.SaveProject() or not self.manager.CloseProject(
            self.project
        ):
            raise Ev24SpikeError("SaveProject or CloseProject failed")
        self.project = self.manager.LoadProject(project_name)
        if self.project is None:
            raise Ev24SpikeError("LoadProject failed after save")

    def verify_reopened(
        self, reports: tuple[Ev24ConfigurationReport, ...]
    ) -> tuple[str, ...]:
        discrepancies: list[str] = []
        for report in reports:
            try:
                timeline = _timeline_by_name(self.project, f"EV24 {report.name}")
                items = list(timeline.GetItemListInTrack("video", 4) or [])
                if len(items) != 1:
                    discrepancies.append(
                        f"{report.name}: V4 does not contain exactly one item"
                    )
                    continue
                item = items[0]
                if (
                    _exact_item_int(item, "GetStart") != 0
                    or _exact_item_int(item, "GetDuration") != report.duration_frames
                ):
                    discrepancies.append(
                        f"{report.name}: V4 placement or duration differs"
                    )
                    continue
                _verify_ev24_media_out(item)
                controls = discover_ev24_controls(item)
                expected = dict(report.control_readback)
                if report.badge_asset_identity is not None:
                    expected["BadgeOverride"] = str(EV24_TEST_BADGE_PATH)
                if controls.read_values(tuple(expected)) != expected:
                    discrepancies.append(
                        f"{report.name}: semantic control readback differs"
                    )
            except (AttributeError, Ev24SpikeError, TypeError, ValueError) as error:
                discrepancies.append(
                    f"{report.name}: reopened inspection failed: {error}"
                )
        return tuple(discrepancies)

    def _new_timeline(self, name: str) -> Any:
        timeline = self.pool.CreateEmptyTimeline(name)
        if timeline is None or not timeline.SetStartTimecode("00:00:00:00"):
            raise Ev24SpikeError(f"could not create timeline {name}")
        while timeline.GetTrackCount("video") < 4:
            if not timeline.AddTrack("video"):
                raise Ev24SpikeError(f"could not add V4 for {name}")
        return timeline

    def _place_seed(self, seed: Any, timeline: Any, duration: int) -> Any:
        if not seed.SetMarkInOut(0, duration, "video"):
            raise Ev24SpikeError("could not set the temporary test-badge duration")
        try:
            placed = self.pool.AppendToTimeline(
                [
                    {
                        "mediaPoolItem": seed,
                        "startFrame": 0,
                        "endFrame": duration + 1,
                        "recordFrame": 0,
                        "trackIndex": 4,
                        "mediaType": 1,
                    }
                ]
            )
        finally:
            if not seed.ClearMarkInOut("video"):
                raise Ev24SpikeError(
                    "could not clear the temporary test-badge duration"
                )
        if not isinstance(placed, (list, tuple)) or len(placed) != 1:
            raise Ev24SpikeError("AppendToTimeline did not place exactly one EV24 seed")
        items = list(timeline.GetItemListInTrack("video", 4) or [])
        if len(items) != 1:
            raise Ev24SpikeError("EV24 seed was not placed exactly once on V4")
        return items[0]


def _require_methods(value: Any, names: tuple[str, ...], label: str) -> None:
    if value is None:
        raise Ev24SpikeError(f"{label} is unavailable")
    for name in names:
        if not callable(getattr(value, name, None)):
            raise Ev24SpikeError(f"{label} has no callable {name}")


def _exact_item_int(item: Any, method_name: str) -> int:
    value = getattr(item, method_name)(False)
    if not isinstance(value, int) or isinstance(value, bool):
        raise Ev24SpikeError(f"{method_name} returned a non-integer frame value")
    return value


def _timeline_by_name(project: Any, name: str) -> Any:
    matches = [
        project.GetTimelineByIndex(index)
        for index in range(1, int(project.GetTimelineCount()) + 1)
    ]
    found = [
        timeline
        for timeline in matches
        if timeline is not None and timeline.GetName() == name
    ]
    if len(found) != 1:
        raise Ev24SpikeError(
            f"expected exactly one timeline named {name!r}, got {len(found)}"
        )
    return found[0]
