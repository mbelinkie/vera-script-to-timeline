from __future__ import annotations

from typing import Any

import pytest
from vera_timeline_agent.ev24_fusion_spike import (
    EV24_SETTING_SHA256,
    EV24_TEST_BADGE_ID,
    Ev24ConfigurationReport,
    Ev24Request,
    Ev24SpikeError,
    PreparedEv24Request,
    discover_ev24_controls,
    prepare_ev24_request,
    run_ev24_spike,
)
from vera_timeline_agent.studio_spike import (
    BLACKMAGIC_BUNDLE_ID,
    ConnectedFacts,
    LocalFacts,
)


def test_prepares_empty_overrides_without_taking_over_fusions_auto_fill() -> None:
    prepared = prepare_ev24_request(
        Ev24Request("standard", "finland", 2024, duration_frames=120)
    )

    assert prepared.semantic_snapshot == {"country": "finland", "year": 2024}
    assert prepared.control_values == {
        "Country": 16,
        "Year": 2024,
        "TopLine": "",
        "BottomLine": "",
    }


def test_prepares_otis_without_a_year_in_its_semantic_snapshot() -> None:
    prepared = prepare_ev24_request(Ev24Request("otis", "otis", duration_frames=64))

    assert prepared.semantic_snapshot == {"country": "otis"}
    assert prepared.control_values == {
        "Country": 53,
        "TopLine": "",
        "BottomLine": "",
    }


def test_rejects_unapproved_badges_and_invalid_semantics() -> None:
    with pytest.raises(Ev24SpikeError, match="declared package test badge"):
        prepare_ev24_request(
            Ev24Request("bad", "finland", 2024, badge_asset_id="asset_other")
        )
    with pytest.raises(Ev24SpikeError, match="otis"):
        prepare_ev24_request(Ev24Request("otis", "otis", 2024))
    with pytest.raises(Ev24SpikeError, match="year"):
        prepare_ev24_request(Ev24Request("missing", "finland"))

    badge = prepare_ev24_request(
        Ev24Request("badge", "malta", 2024, badge_asset_id=EV24_TEST_BADGE_ID)
    )
    assert badge.semantic_snapshot["badgeOverrideAsset"] == EV24_TEST_BADGE_ID
    assert badge.control_values["BadgeOverride"] == EV24_TEST_BADGE_ID


class _Tool:
    def __init__(
        self, name: str = "EV24LowerThird", registration_id: str = "MacroOperator"
    ) -> None:
        self.name = name
        self.registration_id = registration_id
        self.values: dict[str, object] = {
            "Country": 0,
            "Year": 2024,
            "TopLine": "",
            "BottomLine": "",
            "BadgeOverride": "",
        }

    def GetAttrs(self, key: str) -> str:
        return {"TOOLS_Name": self.name, "TOOLS_RegID": self.registration_id}[key]

    def SetInput(self, name: str, value: object) -> None:
        self.values[name] = value

    def GetInput(self, name: str) -> object:
        return self.values.get(name)


class _Composition:
    def __init__(self, tools: dict[Any, Any]) -> None:
        self.tools = tools

    def GetToolList(self, selected: bool) -> dict[Any, Any]:
        assert not selected
        return self.tools


class _Item:
    def __init__(self, tools: dict[Any, Any]) -> None:
        self.comp = _Composition(tools)

    def GetFusionCompCount(self) -> int:
        return 1

    def GetFusionCompByIndex(self, index: int) -> _Composition:
        assert index == 1
        return self.comp


def test_discovery_sets_and_reads_only_registered_macro_controls() -> None:
    tool = _Tool()
    controls = discover_ev24_controls(_Item({1: tool}))
    controls.set_values({"Country": 16, "TopLine": "", "BottomLine": ""})

    assert controls.read_values(("Country", "TopLine", "BottomLine")) == {
        "Country": 16,
        "TopLine": "",
        "BottomLine": "",
    }


@pytest.mark.parametrize(
    "tools, message",
    [
        ({}, "EV24 composition returned no tool map"),
        ({1: _Tool("Renamed")}, "expected exactly one"),
        ({1: _Tool(), 2: _Tool()}, "expected exactly one"),
    ],
)
def test_discovery_fails_closed_for_unknown_or_duplicated_graphs(
    tools: dict[Any, Any], message: str
) -> None:
    with pytest.raises(Ev24SpikeError, match=message):
        discover_ev24_controls(_Item(tools))


def test_discovery_fails_closed_for_missing_or_type_incompatible_controls() -> None:
    controls = discover_ev24_controls(_Item({1: _Tool()}))
    with pytest.raises(Ev24SpikeError, match="not available"):
        controls.set_values({"Unknown": "no"})

    class BadTool(_Tool):
        def SetInput(self, name: str, value: object) -> None:
            raise TypeError("wrong type")

    bad = discover_ev24_controls(_Item({1: BadTool()}))
    with pytest.raises(Ev24SpikeError, match="type-incompatible"):
        bad.set_values({"Country": 16})


def _local() -> LocalFacts:
    return LocalFacts(
        os_name="macOS",
        os_version="15.1",
        architecture="x86_64",
        app_path="/Applications/DaVinci Resolve/DaVinci Resolve.app",
        app_installed=True,
        install_source="blackmagic_package_receipt",
        bundle_name="DaVinci Resolve",
        bundle_identifier=BLACKMAGIC_BUNDLE_ID,
        bundle_version="21.1.0",
        bundle_build="21.1.00014",
        mas_receipt=False,
        package_receipt_id="com.blackmagic-design.ManifestLite",
        package_receipt_version="21.0.4",
        scripting_module_path="/sdk/DaVinciResolveScript.py",
        scripting_module_installed=True,
        scripting_docs_path="/sdk/README.txt",
        scripting_docs_installed=True,
    )


class _RecordingAdapter:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def connected_facts(self) -> ConnectedFacts:
        self.calls.append("connected")
        return ConnectedFacts("DaVinci Resolve Studio", "studio", "21.1.0", "14", True)

    def probe(self) -> None:
        self.calls.append("probe")

    def check_project_name_available(self, name: str) -> None:
        assert name == "EV24 audit"
        self.calls.append("available")

    def create_project(self, name: str) -> None:
        assert name == "EV24 audit"
        self.calls.append("create")

    def exercise(
        self, requests: tuple[PreparedEv24Request, ...]
    ) -> tuple[Ev24ConfigurationReport, ...]:
        self.calls.append("exercise")
        assert len(requests) == 4
        assert {request.request.duration_frames for request in requests} == {64, 120}
        assert requests[2].semantic_snapshot == {"country": "otis"}
        return tuple(
            Ev24ConfigurationReport(
                request.request.name,
                request.semantic_snapshot,
                f"sha256:{EV24_SETTING_SHA256}",
                "V4@0",
                request.request.duration_frames,
                request.control_values,
                request.request.badge_asset_id,
            )
            for request in requests
        )

    def save_close_reopen(self, name: str) -> None:
        assert name == "EV24 audit"
        self.calls.append("reopen")

    def verify_reopened(
        self, reports: tuple[Ev24ConfigurationReport, ...]
    ) -> tuple[str, ...]:
        self.calls.append("verify")
        assert len(reports) == 4
        return ()


def test_runner_keeps_preflight_nonmutating_then_retains_all_four_reports() -> None:
    adapter = _RecordingAdapter()
    preflight = run_ev24_spike(
        action="preflight",
        project_name="EV24 audit",
        local_facts=_local(),
        adapter_factory=lambda _: adapter,
    )
    assert preflight.status == "preflight_passed"
    assert adapter.calls == ["connected", "probe", "available"]

    adapter = _RecordingAdapter()
    result = run_ev24_spike(
        action="build",
        project_name="EV24 audit",
        local_facts=_local(),
        adapter_factory=lambda _: adapter,
    )
    assert result.status == "verified"
    assert result.verified
    assert adapter.calls == [
        "connected",
        "probe",
        "available",
        "create",
        "exercise",
        "reopen",
        "verify",
    ]
