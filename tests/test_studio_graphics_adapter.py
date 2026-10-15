from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
import vera_timeline_agent.studio_graphics as graphics
from vera_timeline_agent.resolve_import_package.package import _canonical_json
from vera_timeline_agent.studio_spike import PublicResolveAdapter


class Input:
    def __init__(self, name: str, datatype: str) -> None:
        self.name, self.datatype = name, datatype

    def GetAttrs(self, key: str) -> str:
        return self.name if key == "INPS_ID" else self.datatype


class Tool:
    def __init__(self, name: str, registration: str) -> None:
        self.name, self.registration = name, registration
        self.values: dict[str, Any] = {
            "Country": 51,
            "Year": 2024,
            "TopLine": "",
            "BottomLine": "",
            "BadgeOverride": "",
        }

    def GetAttrs(self, key: str) -> str:
        return self.name if key == "TOOLS_Name" else self.registration

    def GetInputList(self) -> dict[int, Input]:
        return {
            i: Input(
                name,
                "Number"
                if name in {"Year", "Country"}
                else "Clip"
                if name == "BadgeOverride"
                else "Text",
            )
            for i, name in enumerate(self.values)
        }

    def GetInput(self, name: str) -> Any:
        return self.values[name]

    def SetInput(self, name: str, value: Any) -> None:
        self.values[name] = value

    def SaveSettings(self) -> dict[Any, Any]:
        return {1: "Lua array entry", "Tools": copy.deepcopy(self.values)}

    def ConnectInput(self, name: str, target: Any) -> bool:
        return True

    def FindMainInput(self, index: int) -> Tool:
        return self

    def GetConnectedOutput(self) -> Tool:
        return self

    def GetTool(self) -> Tool:
        return Tool("MasterTransform", "Transform")


class Composition:
    def __init__(self) -> None:
        self.root = Tool("EV24LowerThird", "MacroOperator")
        self.data: dict[str, Any] = {}
        self.prefix = ""

    def GetToolList(self, selected: bool) -> dict[int, Tool]:
        return {1: self.root, 2: Tool("MediaOut1", "MediaOut")}

    def Lock(self) -> None:
        pass

    def Unlock(self) -> None:
        pass

    def SetPrefs(self, prefs: dict[str, str]) -> None:
        self.prefix = prefs["Comp.Paths.Map.Templates:"]

    def MapPath(self, path: str) -> str:
        return self.prefix + path.removeprefix("Templates:/")

    def SetData(self, name: str, value: Any) -> None:
        self.data[name] = value

    def GetData(self, name: str) -> Any:
        return self.data[name]


class Seed:
    def __init__(self, identity: str) -> None:
        self.identity = identity
        self.comments = ""

    def GetMediaId(self) -> str:
        return self.identity

    def SetMetadata(self, key: str, value: str) -> bool:
        self.comments = value
        return True

    def GetMetadata(self, key: str) -> str:
        return self.comments


class Folder:
    def __init__(self, name: str) -> None:
        self.name = name
        self.children: list[Folder] = []
        self.seeds: list[Seed] = []

    def GetName(self) -> str:
        return self.name

    def GetSubFolderList(self) -> list[Folder]:
        return self.children

    def GetClipList(self) -> list[Seed]:
        return self.seeds


class Pool:
    def __init__(self) -> None:
        self.root = Folder("root")
        self.current = self.root

    def GetCurrentFolder(self) -> Folder:
        return self.current

    def GetRootFolder(self) -> Folder:
        return self.root

    def AddSubFolder(self, parent: Folder, name: str) -> Folder:
        folder = Folder(name)
        parent.children.append(folder)
        return folder

    def SetCurrentFolder(self, folder: Folder) -> bool:
        self.current = folder
        return True


class Item:
    def __init__(self, event: dict[str, Any]) -> None:
        self.comp = Composition()
        self.start = event["recordRange"]["startFrame"]
        self.duration = event["recordRange"]["durationFrames"]

    def GetStart(self, subframes: bool) -> int:
        return cast(int, self.start)

    def GetDuration(self, subframes: bool) -> int:
        return cast(int, self.duration)

    def ImportFusionComp(self, path: str) -> Composition:
        return self.comp

    def GetFusionCompCount(self) -> int:
        return 1

    def GetFusionCompByIndex(self, index: int) -> Composition:
        return self.comp

    def GetUniqueId(self) -> str:
        return "native-use-id"


class Timeline:
    def __init__(self) -> None:
        self.items: list[Item] = []

    def GetItemListInTrack(self, kind: str, index: int) -> list[Item]:
        assert (kind, index) == ("video", 4)
        return self.items


@pytest.fixture
def adapter(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> graphics.PublicStudioGraphicAdapter:
    data = Path(__file__).parent / "data/issue_7"
    manifest = json.loads((data / "otis.studio.manifest.golden.json").read_text())
    report = json.loads((data / "otis.studio.report.golden.json").read_text())
    transport, _ = graphics.transport_artifacts(manifest, report)
    package = graphics.StudioGraphicPackage(tmp_path, manifest, report, {}, transport)
    monkeypatch.setattr(
        graphics, "_package_digest", lambda template: "sha256:" + "a" * 64
    )
    result = graphics.PublicStudioGraphicAdapter(None, package)
    result.pool, result.timeline = Pool(), Timeline()
    monkeypatch.setattr(graphics, "verify_studio_graphic_package", lambda root: package)

    def import_media(base: Any, sources: list[tuple[str, Path]]) -> None:
        base.media_by_source = {identity: Seed(identity) for identity, _ in sources}
        base.media_id_by_source = {identity: identity for identity, _ in sources}
        base.pool.current.seeds.extend(base.media_by_source.values())

    def place(base: Any, events: list[dict[str, Any]]) -> None:
        for event in events:
            if event["trackId"] == "video-4":
                base.timeline.items.append(Item(event))

    monkeypatch.setattr(PublicResolveAdapter, "import_media", import_media)
    monkeypatch.setattr(PublicResolveAdapter, "place_events", place)
    monkeypatch.setattr(PublicResolveAdapter, "verify", lambda base, manifest: ())
    return result


@pytest.mark.parametrize(
    "failure",
    [
        None,
        "identity",
        "graph",
        "values",
        "atlas",
        "bin",
        "provenance",
        "duration",
        "track",
    ],
)
def test_adapter_persistence_and_exact_occurrence_verification(
    adapter: graphics.PublicStudioGraphicAdapter,
    failure: str | None,
) -> None:
    adapter.import_media(
        [
            (source["id"], Path(source.get("path", "atlas.png")))
            for source in adapter.graphic_package.manifest["sources"]
        ]
    )
    adapter.place_events(adapter.graphic_package.transport["events"])
    timeline = cast(Timeline, adapter.timeline)
    # Simulate the application returning fresh objects after project reopen.
    timeline.items = copy.deepcopy(timeline.items)
    comp = timeline.items[0].comp
    if failure == "identity":
        comp.data["VERA.Graphic"] = "other-use"
    elif failure == "graph":
        comp.root.values["OtherNode"] = "unexpected graph"
    elif failure == "values":
        comp.root.values["TopLine"] = "changed text"
    elif failure == "atlas":
        comp.prefix = "/foreign/template/"
    elif failure == "bin":
        adapter.pool.root.children[0].name = "foreign-bin"
    elif failure == "provenance":
        adapter.pool.root.children[0].seeds[0].comments = "wrong-package"
    elif failure == "duration":
        timeline.items[0].duration -= 1
    elif failure == "track":
        timeline.items = []
    discrepancies = adapter.verify(adapter.graphic_package.transport)
    if failure:
        assert discrepancies
        assert not adapter.graphic_observations
    else:
        assert discrepancies == ()
        observed = adapter.graphic_observations[0]
        assert (
            observed["graphicUseId"]
            == adapter.graphic_package.manifest["events"][0]["id"]
        )
        assert observed["controlReadback"] == {
            "Country": 53,
            "TopLine": "The Code",
            "BottomLine": "Nemo",
        }
        assert observed["durationFrames"] == 120
        assert observed["track"] == "V4"
        assert observed["verifiedAfterReopen"] is True


def test_runtime_rejects_badge_before_creating_any_occurrence(
    adapter: graphics.PublicStudioGraphicAdapter,
) -> None:
    event = adapter.graphic_package.manifest["events"][0]
    event["semanticSnapshot"]["values"]["badgeOverrideAssetId"] = "asset_custom"
    event["semanticSnapshotHash"] = graphics._hash(
        _canonical_json(event["semanticSnapshot"])
    )
    with pytest.raises(graphics.StudioGraphicError, match="BADGE_OVERRIDE_DEFERRED"):
        adapter.place_events(adapter.graphic_package.transport["events"])
    assert adapter.timeline.items == []


def test_run_boundary_preserves_result_and_actual_observations(
    adapter: graphics.PublicStudioGraphicAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from vera_timeline_agent.studio_assembly import StudioAssemblyResult
    from vera_timeline_agent.studio_spike import LocalFacts

    local = cast(LocalFacts, None)
    monkeypatch.setattr(graphics, "_local_ev24_stop", lambda facts: None)
    monkeypatch.setattr(
        graphics, "load_resolve_adapter", lambda facts: SimpleNamespace(resolve=None)
    )

    def run(root: Path, *, action: str, adapter_factory: Any) -> StudioAssemblyResult:
        implementation = adapter_factory(local)
        implementation.graphic_observations = [{"observed": True}]
        return StudioAssemblyResult(
            "verified",
            "verified",
            local,
            verified=True,
            manual_completion=("No Fusion graphic legacy note", "actual limitation"),
        )

    monkeypatch.setattr(graphics, "run_studio_assembly", run)
    result = graphics.run_studio_graphics(adapter.graphic_package.root, action="build")
    assert result.verified
    assert result.graphic_observations == ({"observed": True},)
    assert result.manual_completion == ("actual limitation",)
    assert result.compiler_manifest_hash.startswith("sha256:")


def test_local_ev24_version_gate_precedes_api_import(
    adapter: graphics.PublicStudioGraphicAdapter,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from vera_timeline_agent.studio_spike import LocalFacts

    monkeypatch.setattr(
        graphics, "_local_ev24_stop", lambda facts: "wrong EV24 version"
    )

    def forbidden(facts: LocalFacts) -> Any:
        raise AssertionError("API must not be loaded")

    def run(root: Path, *, action: str, adapter_factory: Any) -> Any:
        return adapter_factory(cast(LocalFacts, None))

    monkeypatch.setattr(graphics, "load_resolve_adapter", forbidden)
    monkeypatch.setattr(graphics, "run_studio_assembly", run)
    with pytest.raises(graphics.StudioGraphicError, match="wrong EV24 version"):
        graphics.run_studio_graphics(adapter.graphic_package.root)
