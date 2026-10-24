from collections.abc import Callable
from copy import deepcopy
from types import SimpleNamespace as NS
from typing import Any

import pytest

from scripts.issue292_transition_probe import (
    ProbeRefusal,
    apply_transition,
    validate_probe_request,
)

NAME, TOOL = "VERA292 Curve Dissolve", "VERA292CurveDissolve"


def setup_probe(
    duration: int = 24,
    alignment: str = "center",
    controls: dict[str, Any] | None = None,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    Any,
    Any,
    dict[str, Any],
    Callable[[dict[str, Any]], dict[str, Any]],
]:
    controls = {"Curve": "Easing"} if controls is None else controls
    identity = {
        "category": "fusion",
        "name": NAME,
        "sourceIdentity": "VERA292/CurveDissolve.setting",
        "fingerprint": "v1",
    }
    declaration = dict(
        boundaryId="cut-72",
        boundaryFrame=72,
        outgoingId="out-marker",
        incomingId="in-marker",
        effect=identity.copy(),
        durationFrames=duration,
        alignment=alignment,
        controls=controls,
    )
    row = dict(
        **identity,
        addTransition={"type": NAME, "category": "fusion"},
        observedType="transition",
        fusionToolName=TOOL,
        controls={
            "Curve": {
                "id": "Curve",
                "type": "enum",
                "values": ["Linear", "Easing", "Custom"],
            }
        },
    )
    boundary = {
        "frame": 72,
        "outgoing": {
            "id": "out-marker",
            "trackId": "V1",
            "endFrame": 72,
            "rightHandleFrames": 24,
        },
        "incoming": {
            "id": "in-marker",
            "trackId": "V1",
            "startFrame": 72,
            "leftHandleFrames": 24,
        },
    }
    inventory = {
        "scope": "292-representatives",
        "online": True,
        "completeWithinScope": True,
        "effects": [row],
        "boundaries": {"cut-72": boundary},
    }
    state: dict[str, Any] = {
        "values": {"Curve": "Linear"},
        "writes": [],
        "calls": [],
        "added": False,
    }

    def set_input(key: str, value: Any) -> bool:
        state["writes"].append((key, value))
        state["values"][key] = value
        return True

    tool = NS(
        GetAttrs=lambda: {"TOOLS_Name": TOOL},
        SetInput=set_input,
        GetInput=lambda key: state["values"][key],
        GetInputList=lambda: {
            1: NS(
                GetAttrs=lambda: {
                    "INPS_ID": "Curve",
                    "INPS_DataType": "FuID",
                    "INPB_External": True,
                    "INPB_Disabled": False,
                    "INPIDT_ComboControl_ID": {1: "Linear", 2: "Easing", 3: "Custom"},
                }
            )
        },
    )
    comp = NS(GetToolList=lambda _selected: {1: tool})
    half = duration // 2
    start = 72 - (
        duration if alignment == "left" else half if alignment == "center" else 0
    )
    end = 72 + (
        duration if alignment == "right" else half if alignment == "center" else 0
    )
    transition = NS(
        GetName=lambda: NAME,
        GetType=lambda: "transition",
        GetStart=lambda: state.get("start", start),
        GetEnd=lambda: state.get("end", end),
        GetDuration=lambda: duration,
        GetFusionCompByIndex=lambda index: comp,
        GetFusionCompCount=lambda: state.get("fusionCount", 1),
    )
    outgoing = NS(
        GetEnd=lambda: 72,
        GetRightOffset=lambda: 24,
        GetDuration=lambda: 72,
    )
    incoming = NS(GetStart=lambda: 72, GetLeftOffset=lambda: 24, GetDuration=lambda: 72)

    def add(*args: Any) -> bool:
        state["calls"].append(args)
        state["added"] = True
        state["existingTransition"] = transition
        return True

    outgoing.AddTransition = add

    def locate(_request: dict[str, Any]) -> dict[str, Any]:
        if outgoing.GetEnd() != 72 or incoming.GetStart() != 72:
            raise RuntimeError("clips are not adjacent")
        return {
            "outgoingId": "out-marker",
            "incomingId": "in-marker",
            "outgoing": outgoing,
            "incoming": incoming,
            "transition": transition
            if state["added"]
            else state.get("existingTransition"),
        }

    return declaration, inventory, outgoing, transition, state, locate


def test_offline_and_incomplete_inventory_refuse_without_write() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    inv["online"] = False
    with pytest.raises(ProbeRefusal, match="offline or incomplete"):
        apply_transition(d, inv, locate)
    inv["online"] = True
    inv["completeWithinScope"] = False
    with pytest.raises(ProbeRefusal):
        apply_transition(d, inv, locate)
    assert not state["calls"]


def test_missing_changed_and_duplicate_effect_identities_refuse() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    d["effect"]["sourceIdentity"] = "unknown"
    with pytest.raises(ProbeRefusal, match="identity is missing"):
        apply_transition(d, inv, locate)
    d["effect"]["sourceIdentity"] = inv["effects"][0]["sourceIdentity"]
    inv["effects"][0]["fingerprint"] = "changed"
    with pytest.raises(ProbeRefusal, match="fingerprint changed"):
        apply_transition(d, inv, locate)
    inv["effects"][0]["fingerprint"] = "v1"
    inv["effects"].append(deepcopy(inv["effects"][0]))
    with pytest.raises(ProbeRefusal, match="duplicate"):
        apply_transition(d, inv, locate)
    assert not state["calls"]


def test_duplicate_add_transition_selector_refuses_before_write() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    duplicate = deepcopy(inv["effects"][0])
    duplicate["sourceIdentity"] = "other/CurveDissolve.setting"
    duplicate["fingerprint"] = "v2"
    inv["effects"].append(duplicate)

    with pytest.raises(ProbeRefusal, match="duplicate category/name"):
        apply_transition(d, inv, locate)
    assert not state["calls"]


def test_native_controls_and_values_absent_from_live_enum_refuse() -> None:
    d, inv, _, _, _, _ = setup_probe()
    d["effect"]["category"] = inv["effects"][0]["category"] = "simple"
    inv["effects"][0]["addTransition"]["category"] = "simple"
    with pytest.raises(ProbeRefusal, match="native transition controls"):
        validate_probe_request(d, inv)
    d, inv, _out, _, state, locate = setup_probe(controls={"Curve": "Smooth"})
    with pytest.raises(ProbeRefusal, match="unsupported or ambiguous"):
        apply_transition(d, inv, locate)
    assert not state["calls"]


def test_gap_and_short_handles_refuse_without_removing_occurrence() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    inv["boundaries"]["cut-72"]["incoming"]["startFrame"] = 78
    with pytest.raises(ProbeRefusal, match="not adjacent"):
        apply_transition(d, inv, locate)
    inv["boundaries"]["cut-72"]["incoming"]["startFrame"] = 72
    inv["boundaries"]["cut-72"]["incoming"]["leftHandleFrames"] = 11
    with pytest.raises(ProbeRefusal, match="insufficient source handles"):
        apply_transition(d, inv, locate)
    assert not state["calls"]

    d, inv, _out, _, state, locate = setup_probe()
    locate(d)["incoming"].GetStart = lambda: 73
    with pytest.raises(ProbeRefusal, match="live boundary preflight"):
        apply_transition(d, inv, locate)
    assert not state["calls"]
    for available in (0, 2):
        d, inv, _out, _, state, locate = setup_probe()
        boundary = inv["boundaries"]["cut-72"]
        boundary["outgoing"]["rightHandleFrames"] = available
        boundary["incoming"]["leftHandleFrames"] = available
        with pytest.raises(ProbeRefusal, match="insufficient source handles"):
            apply_transition(d, inv, locate)
        assert not state["calls"]


def test_alignment_ranges_use_the_correct_handle_side() -> None:
    for align, expected in {
        "left": (48, 72, 0, 24),
        "center": (60, 84, 12, 12),
        "right": (72, 96, 24, 0),
    }.items():
        d, inv, *_ = setup_probe(alignment=align, controls={})
        b = inv["boundaries"]["cut-72"]
        b["outgoing"]["rightHandleFrames"], b["incoming"]["leftHandleFrames"] = (
            expected[2:]
        )
        plan = validate_probe_request(d, inv)
        assert (plan["startFrame"], plan["endFrame"]) == expected[:2]


def test_apply_sets_control_and_returns_actual_observation() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    proof = apply_transition(d, inv, locate)
    assert state["calls"] == [
        (
            {
                "type": NAME,
                "category": "fusion",
                "position": "end",
                "alignment": "center",
                "duration": 24,
            },
        )
    ]
    assert state["writes"] == [("Curve", "Easing")]
    assert proof["status"] == "observed"
    assert (
        proof["requested"]["controls"]
        == proof["observed"]["controls"]
        == {"Curve": "Easing"}
    )


def test_readback_mismatch_returns_uncertain_after_write() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    state["end"] = 85
    proof = apply_transition(d, inv, locate)
    assert proof["status"] == "uncertain" and proof["mutationOccurred"] is True
    assert state["calls"]


def test_existing_transition_is_preserved_without_writes() -> None:
    d, inv, _out, _, state, locate = setup_probe()
    existing = object()
    state["existingTransition"] = existing
    with pytest.raises(ProbeRefusal, match="already has a transition"):
        apply_transition(d, inv, locate)
    assert state["existingTransition"] is existing
    assert not state["calls"] and not state["writes"]


def test_same_name_wrong_family_is_not_observed() -> None:
    d, inv, _out, _, state, locate = setup_probe(controls={})
    state["fusionCount"] = 0
    assert apply_transition(d, inv, locate)["status"] == "uncertain"


def test_changed_embedded_control_metadata_refuses_control_write() -> None:
    d, inv, _out, tr, state, locate = setup_probe()
    tr.GetFusionCompByIndex(1).GetToolList(False)[1].GetInputList = lambda: {}
    assert apply_transition(d, inv, locate)["status"] == "uncertain"
    assert state["calls"] and not state["writes"]


def test_missing_transition_observation_refuses_before_write() -> None:
    d, inv, _out, _, state, locate = setup_probe()

    def unknown(request: dict[str, Any]) -> dict[str, Any]:
        result = locate(request)
        del result["transition"]
        return result

    with pytest.raises(ProbeRefusal, match="already has a transition"):
        apply_transition(d, inv, unknown)
    assert not state["calls"] and not state["writes"]


@pytest.mark.parametrize(
    "changed",
    [
        {"INPS_DataType": "Number"},
        {"INPB_Disabled": True},
        {"INPIDT_ComboControl_ID": {1: "Linear", 2: "Other"}},
    ],
)
def test_changed_control_attributes_do_not_write_values(
    changed: dict[str, Any],
) -> None:
    d, inv, _out, tr, state, locate = setup_probe()
    tool = tr.GetFusionCompByIndex(1).GetToolList(False)[1]
    attrs = tool.GetInputList()[1].GetAttrs() | changed
    tool.GetInputList = lambda: {1: NS(GetAttrs=lambda: attrs)}
    assert apply_transition(d, inv, locate)["status"] == "uncertain"
    assert state["calls"] and not state["writes"]
