"""Fail-closed native controls for the installed EV24 Quote Box title.

The package carries only a transparent carrier still.  The Fusion graph is a
workstation dependency and is admitted by its installed, pinned bytes before
any Resolve mutation.  This module deliberately knows the small public
control surface of that graph; it does not copy the private template into a
release.
"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

QUOTE_BOX_SETTING_NAME = "EV24 Quote Box.setting"
QUOTE_BOX_SETTING_SHA256 = (
    "b089282e6ccab68426eb5f0b39168cb11c051e6798cbe08230b41bf640ff3754"
)
QUOTE_BOX_TEMPLATE_REVISION = f"sha256:{QUOTE_BOX_SETTING_SHA256}"
QUOTE_BOX_ROOT_TOOL = "EV24QuoteBox"
# Fusion resolves the macro InstanceOutput to this internal Merge.
QUOTE_BOX_RENDER_OUTPUT = "CitationOver"
QUOTE_BOX_CONTROLS_TOOL = "Controls"
QUOTE_BOX_CONTROL_NAMES = frozenset(
    {
        "Quote",
        "Speaker",
        "Citation",
        "QuoteSize",
        "BoxWidth",
        "PanelOpacity",
        "ItalicStart",
        "ItalicEnd",
    }
)
QUOTE_BOX_SIZE_CANDIDATES = (70, 58, 50)
# Match JavaScript String.trim() when translating authored citation offsets.
_CITATION_TRIM = (
    "\t\n\v\f\r \u00a0\u1680\u2000\u2001\u2002\u2003\u2004\u2005"
    "\u2006\u2007\u2008\u2009\u200a\u2028\u2029\u202f\u205f\u3000\ufeff"
)


class QuoteBoxNativeError(RuntimeError):
    """The installed quote-box graph or its controls are not trusted."""


@dataclass(frozen=True)
class QuoteBoxBinding:
    """The controls retained for post-save/reopen verification."""

    values: dict[str, str | int]
    panel_height: float


def installed_quote_box_setting() -> Path:
    """Return the only supported workstation installation location."""
    return (
        Path.home()
        / "Library/Application Support/Blackmagic Design/DaVinci Resolve"
        / "Fusion/Templates/Edit/Titles/Eurovision"
        / QUOTE_BOX_SETTING_NAME
    )


def verify_installed_quote_box_setting(path: Path | None = None) -> Path:
    """Verify the installed title bytes without exposing or packaging them."""
    setting = Path(path) if path is not None else installed_quote_box_setting()
    try:
        if setting.is_symlink() or not setting.is_file():
            raise QuoteBoxNativeError(f"installed {QUOTE_BOX_SETTING_NAME} is missing")
        actual = hashlib.sha256(setting.read_bytes()).hexdigest()
    except OSError as error:
        raise QuoteBoxNativeError(
            f"installed {QUOTE_BOX_SETTING_NAME} cannot be read safely"
        ) from error
    if actual != QUOTE_BOX_SETTING_SHA256:
        raise QuoteBoxNativeError(
            f"installed {QUOTE_BOX_SETTING_NAME} hash differs from the pinned revision"
        )
    return setting


def _string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise QuoteBoxNativeError(f"quote box {label} must be text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as error:
        raise QuoteBoxNativeError(
            f"quote box {label} contains invalid Unicode"
        ) from error
    return value


def _integer(value: object, label: str, *, positive: bool = False) -> int:
    if type(value) is not int or (positive and value < 1) or value < 0:
        raise QuoteBoxNativeError(f"quote box {label} must be a nonnegative integer")
    return value


def quote_box_controls(quote_box: Mapping[str, Any]) -> dict[str, str | int]:
    """Translate one frozen ``v2Event.quoteBox`` into Fusion control IDs."""
    if not isinstance(quote_box, Mapping):
        raise QuoteBoxNativeError("quote box values are missing")
    display_text = _string(quote_box.get("displayText"), "displayText")
    speaker_name = _string(quote_box.get("speakerName"), "speakerName").strip()
    speaker_title = _string(quote_box.get("speakerTitle"), "speakerTitle").strip()
    # Authoring defines italic positions over the trimmed Unicode citation.
    citation = _string(quote_box.get("citationText"), "citationText").strip(
        _CITATION_TRIM
    )
    italic = quote_box.get("italicSpan")
    if italic is None:
        italic_start = italic_end = 0
    elif isinstance(italic, Mapping):
        start = _integer(italic.get("start"), "italicSpan.start")
        end = _integer(italic.get("end"), "italicSpan.end")
        if start >= end:
            raise QuoteBoxNativeError("quote box italic span must be non-empty")
        if end > len(citation):
            raise QuoteBoxNativeError(
                "quote box italic span exceeds the trimmed citation"
            )
        # Authoring stores zero-based half-open positions. Fusion's follower
        # uses one-based inclusive positions, so only the start shifts.
        italic_start = start + 1 if start < end else 0
        italic_end = end if start < end else 0
    else:
        raise QuoteBoxNativeError("quote box italicSpan must be null or an object")
    speaker = (
        f"{speaker_name}, {speaker_title}"
        if speaker_name and speaker_title
        else speaker_name or speaker_title
    )
    return {
        "Quote": display_text,
        "Speaker": speaker,
        "Citation": citation,
        "QuoteSize": 70,
        "BoxWidth": 1600,
        "PanelOpacity": 82,
        "ItalicStart": italic_start,
        "ItalicEnd": italic_end,
    }


def _composition(item: Any) -> Any:
    try:
        if item.GetFusionCompCount() == 1:
            composition = item.GetFusionCompByIndex(1)
            if composition is not None:
                return composition
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            "quote box Fusion composition is unreadable"
        ) from error
    raise QuoteBoxNativeError("quote box requires exactly one Fusion composition")


def _root_tool(composition: Any) -> Any:
    try:
        tool = composition.FindTool(QUOTE_BOX_ROOT_TOOL)
        if tool is None or tool.GetAttrs("TOOLS_RegID") != "MacroOperator":
            raise QuoteBoxNativeError(f"expected {QUOTE_BOX_ROOT_TOOL} MacroOperator")
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            "quote box graph tool identity is unreadable"
        ) from error
    if not callable(getattr(tool, "SetInput", None)) or not callable(
        getattr(tool, "GetInput", None)
    ):
        raise QuoteBoxNativeError("quote box controls are not readable and writable")
    return tool


def _controls_tool(composition: Any) -> Any:
    """Return the nested Background that evaluates the private PanelH input."""
    try:
        tool = composition.FindTool(QUOTE_BOX_CONTROLS_TOOL)
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError("quote box Controls tool is unreadable") from error
    if tool is None:
        raise QuoteBoxNativeError("quote box Controls tool is missing")
    try:
        name = tool.GetAttrs("TOOLS_Name")
        registration = tool.GetAttrs("TOOLS_RegID")
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            "quote box Controls tool identity is unreadable"
        ) from error
    if name != QUOTE_BOX_CONTROLS_TOOL or registration != "Background":
        raise QuoteBoxNativeError(
            f"expected exactly one {QUOTE_BOX_CONTROLS_TOOL} Background"
        )
    if not callable(getattr(tool, "GetInput", None)):
        raise QuoteBoxNativeError("quote box Controls tool is not readable")
    return tool


def _outputs(composition: Any) -> list[Any]:
    try:
        tools = composition.GetToolList(False, "MediaOut")
        if isinstance(tools, dict):
            return list(tools.values())
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError("quote box MediaOut list is unreadable") from error
    raise QuoteBoxNativeError("quote box MediaOut list is malformed")


def _media_out(composition: Any, root: Any) -> Any:
    outputs = _outputs(composition)
    if len(outputs) > 1:
        raise QuoteBoxNativeError("quote box graph contains duplicate MediaOut tools")
    try:
        output = outputs[0] if outputs else composition.AddTool("MediaOut", 0, 0)
        if output is None or output.GetAttrs("TOOLS_RegID") != "MediaOut":
            raise QuoteBoxNativeError(
                "quote box MediaOut creation returned an incompatible tool"
            )
        if output.ConnectInput("Input", root) is False:
            raise QuoteBoxNativeError(
                "Resolve rejected the quote box MediaOut connection"
            )
    except QuoteBoxNativeError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError("could not connect quote box to MediaOut") from error
    return output


def _verify_media_out(item: Any) -> None:
    outputs = _outputs(_composition(item))
    if len(outputs) != 1:
        raise QuoteBoxNativeError("quote box graph must contain exactly one MediaOut")
    try:
        source = outputs[0].FindMainInput(1).GetConnectedOutput().GetTool()
        if (
            source.GetAttrs("TOOLS_Name") != QUOTE_BOX_RENDER_OUTPUT
            or source.GetAttrs("TOOLS_RegID") != "Merge"
        ):
            raise QuoteBoxNativeError(
                "quote box MacroOperator is not connected to MediaOut"
            )
    except QuoteBoxNativeError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            "quote box MediaOut connection is unreadable"
        ) from error


def discover_quote_box_controls(item: Any) -> Any:
    """Require the pinned macro and return its strict control facade."""
    composition = _composition(item)
    root = _root_tool(composition)
    _controls_tool(composition)
    return root


def _get_input(tool: Any, name: str, *, hold_frame: int | None = None) -> Any:
    try:
        if hold_frame is not None:
            try:
                return tool.GetInput(name, hold_frame)
            except TypeError:
                pass
        return tool.GetInput(name)
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(f"quote box control {name} cannot be read") from error


def _set_input(tool: Any, name: str, value: str | int) -> None:
    try:
        if tool.SetInput(name, value) is False:
            raise QuoteBoxNativeError(f"Resolve rejected quote box control {name}")
    except QuoteBoxNativeError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            f"quote box control {name} is not writable"
        ) from error


def _panel_height(tool: Any) -> float:
    value = _get_input(tool, "PanelH", hold_frame=18)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise QuoteBoxNativeError("quote box PanelH is not numeric")
    if not math.isfinite(float(value)) or value <= 0:
        raise QuoteBoxNativeError("quote box PanelH is invalid")
    return float(value)


def _read_controls(tool: Any, names: Sequence[str]) -> dict[str, Any]:
    return {name: _get_input(tool, name) for name in names}


def configure_quote_box(
    item: Any,
    setting: Path,
    quote_box: Mapping[str, Any],
    *,
    timeline_height: int,
    size_candidates: Sequence[int] = QUOTE_BOX_SIZE_CANDIDATES,
) -> QuoteBoxBinding:
    """Import, wire, size and immediately read back one quote-box item."""
    if type(timeline_height) is not int or timeline_height < 1:
        raise QuoteBoxNativeError("quote box timeline height is invalid")
    candidates = tuple(size_candidates)
    if not candidates or any(type(size) is not int or size < 1 for size in candidates):
        raise QuoteBoxNativeError("quote box size candidates are invalid")
    values = quote_box_controls(quote_box)
    try:
        if item.ImportFusionComp(str(setting)) is None:
            raise QuoteBoxNativeError(
                "Resolve rejected the pinned EV24 Quote Box setting"
            )
    except QuoteBoxNativeError:
        raise
    except (AttributeError, TypeError, ValueError) as error:
        raise QuoteBoxNativeError(
            "quote box item cannot import the pinned setting"
        ) from error
    composition = _composition(item)
    root = _root_tool(composition)
    controls = _controls_tool(composition)
    locked = False
    try:
        lock_result = composition.Lock()
        if lock_result is False:
            raise QuoteBoxNativeError(
                "Resolve rejected the quote box Fusion composition lock"
            )
        locked = True
        _media_out(composition, root)
    finally:
        if locked:
            try:
                composition.Unlock()
            except (AttributeError, TypeError, ValueError) as error:
                raise QuoteBoxNativeError(
                    "could not unlock the quote box Fusion composition"
                ) from error
    _verify_media_out(item)

    for name, value in values.items():
        if name != "QuoteSize":
            _set_input(root, name, value)
    selected: int | None = None
    selected_height: float | None = None
    for candidate in candidates:
        _set_input(root, "QuoteSize", candidate)
        height = _panel_height(controls)
        if height <= timeline_height:
            selected = candidate
            selected_height = height
            break
    if selected is None or selected_height is None:
        raise QuoteBoxNativeError(
            "quote box has no fitting Quote Size in the allowed native candidates"
        )
    values["QuoteSize"] = selected
    actual = _read_controls(root, tuple(QUOTE_BOX_CONTROL_NAMES))
    if any(actual.get(name) != expected for name, expected in values.items()):
        raise QuoteBoxNativeError("quote box controls differ immediately after write")
    return QuoteBoxBinding(values, selected_height)


def verify_quote_box(
    item: Any,
    expected: Mapping[str, str | int],
    *,
    timeline_height: int | None = None,
) -> None:
    """Verify graph wiring and controls after save/close/reopen."""
    _verify_media_out(item)
    composition = _composition(item)
    tool = _root_tool(composition)
    controls = _controls_tool(composition)
    if set(expected) != set(QUOTE_BOX_CONTROL_NAMES):
        raise QuoteBoxNativeError("quote box expected control set is incomplete")
    actual = _read_controls(tool, tuple(QUOTE_BOX_CONTROL_NAMES))
    if actual != dict(expected):
        raise QuoteBoxNativeError("reopened quote box controls differ")
    height = _panel_height(controls)
    if timeline_height is not None:
        if type(timeline_height) is not int or timeline_height < 1:
            raise QuoteBoxNativeError("quote box timeline height is invalid")
        if height > timeline_height:
            raise QuoteBoxNativeError("reopened quote box exceeds timeline height")
