from __future__ import annotations

import copy
from itertools import product
from typing import Any

import pytest
from vera_timeline_agent.studio_graphics_runtime import (
    StudioGraphicError,
    _graph_fingerprint,
)

# Minimized structure from the native witness; no authored template/fixture copy.
TOOLS = ("Tools", "EV24LowerThird", "Tools")
FLAG_FORMS = (
    ((*TOOLS, "ControlHub", "UserControls", "Country"), 256),
    ((*TOOLS, "ControlHub", "UserControls"), 3145984),
    ((*TOOLS, "Metrics", "UserControls"), 3145984),
)
RIBBON = (*TOOLS, "RibbonUnit")
BADGE_INPUT = {"BadgeImage": {"Value": 0.0, "__ctor": "Input", "__flags": 256}}


def settings() -> dict[str, Any]:
    return {
        "Tools": {
            "EV24LowerThird": {
                "Inputs": {"Country": {"Value": 16}, "Year": {"Value": 2024}},
                "Tools": {
                    "ControlHub": {
                        "UserControls": {"Country": {"LINKS_Name": "Country"}}
                    },
                    "Metrics": {"UserControls": {"Scale": {"INP_Default": 1}}},
                    "RibbonUnit": {"__ctor": "GroupOperator"},
                    "Title": {
                        "Inputs": {"StyledText": {"Expression": "ControlHub.Country"}},
                        "ViewInfo": {"Pos": [1, 2]},
                    },
                    "BadgeOverride": {"Clips": {}, "__ctor": "Loader"},
                    "Output": {"SourceOp": "Title", "Source": "Output"},
                },
            }
        }
    }


def at(value: dict[str, Any], path: tuple[str, ...]) -> Any:
    node: Any = value
    for key in path:
        node = node[key]
    return node


class Root:
    def __init__(self, value: Any) -> None:
        self.value = value
        self.reads = 0

    def SaveSettings(self) -> Any:
        self.reads += 1
        return self.value


def fingerprint(value: Any) -> str:
    return _graph_fingerprint(Root(value))


@pytest.mark.parametrize("forms", list(product((False, True), repeat=4)))
def test_exact_native_persistence_forms_have_one_fingerprint(
    forms: tuple[bool, ...],
) -> None:
    value = settings()
    for enabled, (path, flag) in zip(forms[:3], FLAG_FORMS, strict=True):
        if enabled:
            at(value, path)["__flags"] = flag
    if forms[3]:
        at(value, RIBBON)["Inputs"] = copy.deepcopy(BADGE_INPUT)
    assert fingerprint(value) == fingerprint(settings())


@pytest.mark.parametrize("path,expected", FLAG_FORMS)
@pytest.mark.parametrize("invalid", [None, True, False, 0, 1, "256", [], {}])
def test_other_flag_values_are_not_ignored(
    path: tuple[str, ...], expected: int, invalid: Any
) -> None:
    value = settings()
    at(value, path)["__flags"] = invalid
    assert fingerprint(value) != fingerprint(settings())
    at(value, path)["__flags"] = float(expected)
    assert fingerprint(value) != fingerprint(settings())
    at(value, path)["__flags"] = expected + 1
    assert fingerprint(value) != fingerprint(settings())


@pytest.mark.parametrize(
    "field,invalid",
    [
        ("Value", False),
        ("Value", True),
        ("Value", 0),
        ("Value", -0.0),
        ("Value", 1),
        ("Value", 1.0),
        ("Value", None),
        ("Value", "0"),
        ("__flags", 256.0),
        ("__flags", True),
        ("__flags", 257),
        ("__ctor", "InstanceInput"),
        ("SourceOp", "BadgeOverride"),
        ("Source", "Clip"),
        ("Expression", "ControlHub.Country"),
    ],
)
def test_changed_badge_input_remains_hash_visible(field: str, invalid: Any) -> None:
    value = settings()
    inputs = copy.deepcopy(BADGE_INPUT)
    inputs["BadgeImage"][field] = invalid
    at(value, RIBBON)["Inputs"] = inputs
    assert fingerprint(value) != fingerprint(settings())


@pytest.mark.parametrize("missing", ["Value", "__flags", "__ctor"])
def test_incomplete_badge_input_is_not_the_approved_form(missing: str) -> None:
    value = settings()
    inputs = copy.deepcopy(BADGE_INPUT)
    del inputs["BadgeImage"][missing]
    at(value, RIBBON)["Inputs"] = inputs
    assert fingerprint(value) != fingerprint(settings())


@pytest.mark.parametrize("inputs", [{}, [], {"BadgeImage": 0}, {"Other": BADGE_INPUT}])
def test_other_ribbon_inputs_remain_hash_visible(inputs: Any) -> None:
    value = settings()
    at(value, RIBBON)["Inputs"] = inputs
    assert fingerprint(value) != fingerprint(settings())


def test_additional_ribbon_input_is_not_discarded() -> None:
    value = settings()
    at(value, RIBBON)["Inputs"] = {
        **copy.deepcopy(BADGE_INPUT),
        "Other": {"Value": 0},
    }
    assert fingerprint(value) != fingerprint(settings())


@pytest.mark.parametrize(
    "path,field,changed",
    [
        ((*TOOLS, "ControlHub", "UserControls", "Country"), "LINKS_Name", "Other"),
        ((*TOOLS, "Metrics", "UserControls", "Scale"), "INP_Default", 2),
        (("Tools", "EV24LowerThird", "Inputs", "Country"), "Value", 17),
        (("Tools", "EV24LowerThird", "Inputs", "Year"), "Value", 2025),
        ((*TOOLS, "Title", "Inputs", "StyledText"), "Expression", "Other.Country"),
        ((*TOOLS, "Title", "ViewInfo"), "Pos", [2, 1]),
        ((*TOOLS, "Output"), "SourceOp", "Other"),
        ((*TOOLS, "Output"), "Source", "Mask"),
        ((*TOOLS, "BadgeOverride"), "Clips", {"1": "unexpected.png"}),
        (RIBBON, "__ctor", "OtherOperator"),
        (TOOLS, "ExtraNode", {}),
        ((*TOOLS, "ControlHub", "UserControls", "Country"), "Extra", 0),
    ],
)
def test_other_graph_fields_remain_hash_visible(
    path: tuple[str, ...], field: str, changed: Any
) -> None:
    value = settings()
    at(value, path)[field] = changed
    assert fingerprint(value) != fingerprint(settings())


@pytest.mark.parametrize("path,flag", FLAG_FORMS)
def test_identical_flags_at_different_paths_are_not_ignored(
    path: tuple[str, ...], flag: int
) -> None:
    value = settings()
    value["Other"] = copy.deepcopy(value["Tools"]["EV24LowerThird"])
    baseline = copy.deepcopy(value)
    at(value, ("Other", *path[2:]))["__flags"] = flag
    assert fingerprint(value) != fingerprint(baseline)


def test_identical_badge_input_at_a_different_node_is_not_ignored() -> None:
    value = settings()
    at(value, TOOLS)["OtherRibbon"] = {}
    baseline = copy.deepcopy(value)
    at(value, (*TOOLS, "OtherRibbon"))["Inputs"] = copy.deepcopy(BADGE_INPUT)
    assert fingerprint(value) != fingerprint(baseline)


def test_other_changes_remain_visible_when_all_approved_forms_are_present() -> None:
    value = settings()
    for path, flag in FLAG_FORMS:
        at(value, path)["__flags"] = flag
    at(value, RIBBON)["Inputs"] = copy.deepcopy(BADGE_INPUT)
    at(value, (*TOOLS, "Title", "Inputs", "StyledText"))["Expression"] = "Other"
    assert fingerprint(value) != fingerprint(settings())


def test_ambiguous_lua_keys_are_rejected_even_inside_an_approved_form() -> None:
    value = settings()
    at(value, RIBBON)["Inputs"] = copy.deepcopy(BADGE_INPUT)
    at(value, (*RIBBON, "Inputs", "BadgeImage")).update({1: 0, "1": 0})
    with pytest.raises(StudioGraphicError, match="ambiguous table keys"):
        fingerprint(value)


def test_single_read_and_no_mutation_of_native_settings() -> None:
    value = settings()
    for path, flag in FLAG_FORMS:
        at(value, path)["__flags"] = flag
    at(value, RIBBON)["Inputs"] = copy.deepcopy(BADGE_INPUT)
    original = copy.deepcopy(value)
    root = Root(value)
    _graph_fingerprint(root)
    assert root.reads == 1
    assert value == original


@pytest.mark.parametrize("invalid", [None, [], "settings"])
def test_unavailable_settings_still_fail_closed(invalid: Any) -> None:
    with pytest.raises(StudioGraphicError, match="settings are unavailable"):
        fingerprint(invalid)
