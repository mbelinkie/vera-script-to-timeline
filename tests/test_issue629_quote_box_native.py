from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent import quote_box_native, workflow_v2
from vera_timeline_agent.build_jobs import BuildJobError
from vera_timeline_agent.quote_box_inputs import freeze_quote_box_inputs
from vera_timeline_agent.workflow_v2_cli import RUNTIME_FILES


class _Controls:
    def __init__(self, root: _Root) -> None:
        self.root = root
        self.hold_frames: list[int] = []

    def GetAttrs(self, key: str) -> str:
        return {"TOOLS_Name": "Controls", "TOOLS_RegID": "Background"}[key]

    def GetInput(self, name: str, frame: int) -> float:
        assert name == "PanelH"
        self.hold_frames.append(frame)
        size = self.root.values["QuoteSize"]
        assert type(size) is int
        return {70: 1200.0, 58: 1000.0, 50: 880.0}[size]


class _Root:
    def __init__(self) -> None:
        self.values: dict[str, object] = {
            "Quote": "",
            "Speaker": "",
            "Citation": "",
            "QuoteSize": 70,
            "BoxWidth": 1600,
            "PanelOpacity": 82,
            "ItalicStart": 0,
            "ItalicEnd": 0,
        }
        self.controls = _Controls(self)
        self.output = _FinalMerge()

    def GetAttrs(self, key: str) -> str:
        return {"TOOLS_Name": "EV24QuoteBox", "TOOLS_RegID": "MacroOperator"}[key]

    def GetChildrenList(self, selected: bool = False) -> dict[int, _Controls]:
        assert selected is False
        return {1: self.controls}

    def SetInput(self, name: str, value: str | int) -> None:
        if name not in self.values:
            raise KeyError(name)
        self.values[name] = value

    def GetInput(self, name: str, *_args: int) -> object:
        return self.values[name]


class _FinalMerge:
    def GetAttrs(self, key: str) -> str:
        return {"TOOLS_Name": "CitationOver", "TOOLS_RegID": "Merge"}[key]


class _ConnectedOutput:
    def __init__(self, source: _Root | _FinalMerge | None) -> None:
        self.source = source

    def GetTool(self) -> _Root | _FinalMerge | None:
        return self.source


class _MediaOut:
    def __init__(self) -> None:
        self.source: _Root | _FinalMerge | None = None

    def GetAttrs(self, key: str) -> str:
        return {"TOOLS_Name": "MediaOut1", "TOOLS_RegID": "MediaOut"}[key]

    def ConnectInput(self, name: str, source: _Root) -> bool:
        assert name == "Input"
        self.source = source.output
        return True

    def FindMainInput(self, index: int) -> _MediaOut:
        assert index == 1
        return self

    def GetConnectedOutput(self) -> _ConnectedOutput:
        return _ConnectedOutput(self.source)


class _Composition:
    def __init__(self, root: _Root) -> None:
        self.root = root
        self.media_out: _MediaOut | None = None
        self.locked = False

    def GetToolList(self, selected: bool, reg_id: str) -> dict[int, Any]:
        assert selected is False and reg_id == "MediaOut"
        return {1: self.media_out} if self.media_out else {}

    def FindTool(self, name: str) -> _Controls | _Root | None:
        tools: dict[str, _Controls | _Root] = {
            "Controls": self.root.controls,
            "EV24QuoteBox": self.root,
        }
        return tools.get(name)

    def Lock(self) -> None:
        self.locked = True

    def Unlock(self) -> None:
        self.locked = False

    def AddTool(self, registration: str, _x: int, _y: int) -> _MediaOut:
        assert registration == "MediaOut"
        self.media_out = _MediaOut()
        return self.media_out


class _Item:
    def __init__(self) -> None:
        self.root = _Root()
        self.composition = _Composition(self.root)

    def ImportFusionComp(self, path: str) -> bool:
        assert path.endswith("setting")
        return True

    def GetFusionCompCount(self) -> int:
        return 1

    def GetFusionCompByIndex(self, index: int) -> _Composition:
        assert index == 1
        return self.composition


def _quote() -> dict[str, Any]:
    return {
        "displayText": "A shortened quote",
        "speakerName": " Ada Lovelace ",
        "speakerTitle": " Mathematician ",
        "citationText": "  The café 🌍  ",
        "italicSpan": {"start": 4, "end": 10},
    }


def test_quote_controls_trim_citation_before_mapping_unicode_span() -> None:
    assert quote_box_native.quote_box_controls(_quote()) == {
        "Quote": "A shortened quote",
        "Speaker": "Ada Lovelace, Mathematician",
        "Citation": "The café 🌍",
        "QuoteSize": 70,
        "BoxWidth": 1600,
        "PanelOpacity": 82,
        "ItalicStart": 5,
        "ItalicEnd": 10,
    }


def test_quote_controls_use_authoring_trim_rules() -> None:
    quote = _quote()
    quote["citationText"] = "\ufeffSource\u0085"
    quote["italicSpan"] = {"start": 0, "end": 7}
    controls = quote_box_native.quote_box_controls(quote)
    assert controls["Citation"] == "Source\u0085"
    assert (controls["ItalicStart"], controls["ItalicEnd"]) == (1, 7)


@pytest.mark.parametrize("index", [4, 5])
def test_quote_lane_rejects_layout_with_picture_on_or_above_v4(index: int) -> None:
    document = {
        "activeDraft": {
            "blocks": [
                {
                    "type": "narration",
                    "state": "active",
                    "overlayEvents": [{"quoteBox": _quote()}],
                }
            ]
        }
    }
    dependencies = {
        "tracks": [{"id": "child", "kind": "video", "index": index}],
        "roles": {
            "primaryRootTrackId": "root",
            "childTrackIds": ["child"],
            "overlayTrackIds": [],
        },
    }
    with pytest.raises(BuildJobError, match="need V4 above the primary picture tracks"):
        freeze_quote_box_inputs(document, dependencies)
    assert dependencies["tracks"] == [{"id": "child", "kind": "video", "index": index}]


@pytest.mark.parametrize(
    "span",
    [{"start": 4, "end": 4}, {"start": 4, "end": 11}, {"start": 10, "end": 4}],
)
def test_quote_controls_reject_invalid_trimmed_spans(span: dict[str, int]) -> None:
    quote = _quote()
    quote["italicSpan"] = span
    with pytest.raises(quote_box_native.QuoteBoxNativeError, match="italic span"):
        quote_box_native.quote_box_controls(quote)


def test_configure_quote_box_wires_graph_sizes_panel_and_verifies_reopen(
    tmp_path: Path,
) -> None:
    item = _Item()
    binding = quote_box_native.configure_quote_box(
        item,
        tmp_path / "EV24 Quote Box.setting",
        _quote(),
        timeline_height=1080,
    )

    assert binding.values["QuoteSize"] == 58
    assert binding.panel_height == 1000.0
    assert item.composition.locked is False
    assert item.composition.media_out is not None
    assert item.composition.media_out.source is item.root.output
    assert item.root.controls.hold_frames == [18, 18]
    quote_box_native.verify_quote_box(
        item,
        binding.values,
        timeline_height=1080,
    )
    assert item.root.controls.hold_frames[-1] == 18


def test_quote_box_rejects_missing_controls_and_missing_template(
    tmp_path: Path,
) -> None:
    item = _Item()
    item.root.controls = None  # type: ignore[assignment]
    with pytest.raises(quote_box_native.QuoteBoxNativeError, match="missing"):
        quote_box_native.discover_quote_box_controls(item)

    with pytest.raises(quote_box_native.QuoteBoxNativeError, match="missing"):
        quote_box_native.verify_installed_quote_box_setting(
            tmp_path / "missing.setting"
        )


def test_quote_box_reopen_rejects_wrong_media_out_source(tmp_path: Path) -> None:
    item = _Item()
    binding = quote_box_native.configure_quote_box(
        item,
        tmp_path / "EV24 Quote Box.setting",
        _quote(),
        timeline_height=1080,
    )
    assert item.composition.media_out is not None
    wrong_root = _Root()
    wrong_root.GetAttrs = lambda key: {  # type: ignore[method-assign]
        "TOOLS_Name": "OtherMacro",
        "TOOLS_RegID": "MacroOperator",
    }[key]
    item.composition.media_out.source = wrong_root
    with pytest.raises(quote_box_native.QuoteBoxNativeError, match="connected"):
        quote_box_native.verify_quote_box(item, binding.values)


def test_quote_box_native_transport_uses_v4_padding_and_one_frame_hold() -> None:
    view: dict[str, Any] = {
        "tracks": [
            {
                "id": "quote-graphics",
                "kind": "video",
                "index": 4,
                "name": "Quote Graphics",
            }
        ],
        "events": [{"kind": "quote_box", "sourceRange": {"startFrame": 0}}],
    }
    tracks = workflow_v2._native_otio_transport_tracks(view)
    assert {(track["kind"], track["index"]) for track in tracks} == {
        ("video", 1),
        ("video", 2),
        ("video", 3),
        ("video", 4),
    }
    assert workflow_v2._native_otio_single_frame_hold(
        view["events"][0],
        {"kind": "still"},
        {},
    )


def test_quote_box_native_runtime_is_in_release_inventory() -> None:
    assert "quote_box_native.py" in RUNTIME_FILES
