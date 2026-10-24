"""Issue 292 probe; identities and representative inventory are not universal."""

from collections.abc import Callable
from typing import Any


class ProbeRefusal(ValueError):
    """Preflight refusal; Resolve has not been mutated."""


def _need(ok: object, reason: str) -> None:
    if not ok:
        raise ProbeRefusal(reason)


def validate_probe_request(
    declaration: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    _need(
        isinstance(declaration, dict)
        and isinstance(inventory, dict)
        and inventory.get("scope") == "292-representatives"
        and inventory.get("online") is True
        and inventory.get("completeWithinScope") is True,
        "292 representative inventory is offline or incomplete",
    )
    frame: Any = declaration.get("boundaryFrame")
    duration: Any = declaration.get("durationFrames")
    effect: Any = declaration.get("effect")
    alignment: Any = declaration.get("alignment")
    controls: Any = declaration.get("controls")
    _need(
        declaration.get("boundaryId")
        and declaration.get("outgoingId")
        and declaration.get("incomingId")
        and type(frame) is int
        and frame >= 0
        and type(duration) is int
        and duration > 0
        and duration % 2 == 0
        and alignment in {"left", "center", "right"}
        and isinstance(effect, dict)
        and isinstance(controls, dict),
        "invalid boundary, effect, duration, alignment, or controls",
    )
    _need(
        effect.get("category") in {"simple", "fusion"}
        and all(effect.get(k) for k in ("name", "sourceIdentity", "fingerprint")),
        "effect identity is incomplete",
    )
    rows: Any = inventory.get("effects")
    _need(isinstance(rows, list), "effect records are missing")
    application_matches = [
        r
        for r in rows
        if isinstance(r, dict)
        and (r.get("category"), r.get("name")) == (effect["category"], effect["name"])
    ]
    _need(
        len(application_matches) <= 1,
        "duplicate category/name AddTransition selectors are ambiguous",
    )
    ident = effect["category"], effect["name"], effect["sourceIdentity"]
    matches = [
        r
        for r in rows
        if isinstance(r, dict)
        and (r.get("category"), r.get("name"), r.get("sourceIdentity")) == ident
    ]
    _need(matches, "exact effect identity is missing; name-only matching is forbidden")
    _need(
        all(r.get("fingerprint") == effect["fingerprint"] for r in matches),
        "effect fingerprint changed",
    )
    _need(len(matches) == 1, "duplicate exact effect identities")
    record = matches[0]
    add = record.get("addTransition")
    _need(
        isinstance(add, dict)
        and add.get("type") == effect["name"]
        and add.get("category") == effect["category"]
        and record.get("observedType") == "transition",
        "effect application metadata does not match exact identity",
    )
    _need(
        not controls or effect["category"] == "fusion",
        "native transition controls are unverified",
    )
    specs: Any = record.get("controls", {})
    ids: set[Any] = set()
    for name, value in controls.items():
        spec: Any = specs.get(name) if isinstance(specs, dict) else None
        _need(isinstance(spec, dict), f"unknown control {name!r}")
        input_id, values = spec.get("id"), spec.get("values")
        valid = (
            spec.get("type") == "enum"
            and not {"min", "max", "range", "minimum", "maximum"}.intersection(spec)
            and type(input_id) in (str, int)
            and isinstance(values, list)
            and values
            and all(isinstance(v, str) for v in values)
            and input_id not in ids
            and value in values
        )
        _need(valid, f"unsupported or ambiguous control {name!r}")
        ids.add(input_id)
    _need(not controls or record.get("fusionToolName"), "Fusion tool name is missing")
    boundary_id: Any = declaration.get("boundaryId")
    bounds: Any = inventory.get("boundaries", {})
    boundary: Any = bounds.get(boundary_id) if isinstance(bounds, dict) else None
    out: Any = boundary.get("outgoing") if isinstance(boundary, dict) else None
    inc: Any = boundary.get("incoming") if isinstance(boundary, dict) else None
    _need(
        isinstance(boundary, dict)
        and boundary.get("frame") == frame
        and isinstance(out, dict)
        and isinstance(inc, dict)
        and out.get("id") == declaration["outgoingId"]
        and inc.get("id") == declaration["incomingId"]
        and out.get("trackId")
        and inc.get("trackId")
        and out.get("trackId") == inc.get("trackId")
        and out.get("endFrame") == frame
        and inc.get("startFrame") == frame,
        "items are not adjacent at the declared boundary",
    )
    right: Any = out.get("rightHandleFrames")
    left: Any = inc.get("leftHandleFrames")
    _need(
        type(right) is int and type(left) is int and right >= 0 and left >= 0,
        "boundary handle inventory is unknown",
    )
    half = duration // 2
    need_right = need_left = half if alignment == "center" else 0
    need_right = duration if alignment == "right" else need_right
    need_left = duration if alignment == "left" else need_left
    _need(
        right >= need_right and left >= need_left,
        "insufficient source handles for transition alignment",
    )
    start, end = frame - need_left, frame + need_right
    _need(start >= 0, "transition would start before frame zero")
    return {
        "requested": dict(declaration),
        "record": record,
        "startFrame": start,
        "endFrame": end,
        "boundaryFrame": frame,
    }


def _uncertain(
    plan: dict[str, Any], reason: str, observed: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "status": "uncertain",
        "mutationOccurred": True,
        "reason": reason,
        "requested": plan["requested"],
        "observed": observed,
    }


def _tool(transition: Any, record: dict[str, Any]) -> Any:
    tools = transition.GetFusionCompByIndex(1).GetToolList(False)
    name = record["fusionToolName"]
    found = [t for t in tools.values() if t.GetAttrs().get("TOOLS_Name") == name]
    if len(found) != 1:
        raise RuntimeError("expected exactly one inventoried Fusion group")
    return found[0]


def observe_transition(
    transition: Any, declaration: dict[str, Any], inventory: dict[str, Any]
) -> dict[str, Any]:
    """Read actual getters; after a write, any mismatch is an uncertain result."""
    plan = validate_probe_request(declaration, inventory)
    req, record = plan["requested"], plan["record"]
    try:
        actual: dict[str, Any] = {
            "name": transition.GetName(),
            "type": transition.GetType(),
            "startFrame": transition.GetStart(),
            "endFrame": transition.GetEnd(),
            "durationFrames": transition.GetDuration(),
            "controls": {},
        }
        if req["controls"]:
            tool = _tool(transition, record)
            actual["controls"] = {
                name: tool.GetInput(record["controls"][name]["id"])
                for name in req["controls"]
            }
    except Exception as exc:
        return _uncertain(plan, f"Resolve observation failed: {exc}")
    wanted = (
        req["effect"]["name"],
        record["observedType"],
        plan["startFrame"],
        plan["endFrame"],
        req["durationFrames"],
        req["controls"],
    )
    got = tuple(
        actual[key]
        for key in (
            "name",
            "type",
            "startFrame",
            "endFrame",
            "durationFrames",
            "controls",
        )
    )
    if got != wanted:
        return _uncertain(plan, "Resolve readback differed from request", actual)
    return {"status": "observed", "requested": req, "observed": actual}


def apply_transition(
    declaration: dict[str, Any],
    inventory: dict[str, Any],
    locate_boundary: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Locator verifies both stable marker IDs and live adjacency on each call.

    Its result contains IDs, outgoing/incoming TimelineItems, and the unique
    applied transition after AddTransition; locate by boundary/range, not name.
    """
    plan = validate_probe_request(declaration, inventory)
    _need(callable(locate_boundary), "live boundary locator is required")
    req, record = plan["requested"], plan["record"]
    try:
        before = locate_boundary(req)
        _need(
            before.get("outgoingId") == req["outgoingId"]
            and before.get("incomingId") == req["incomingId"],
            "live locator did not resolve both marker IDs",
        )
        out, inc = before["outgoing"], before["incoming"]
        _need(
            out.GetEnd() == inc.GetStart() == req["boundaryFrame"],
            "live clips are no longer adjacent",
        )
        _need(
            out.GetRightOffset() >= plan["endFrame"] - req["boundaryFrame"]
            and inc.GetLeftOffset() >= req["boundaryFrame"] - plan["startFrame"]
            and min(out.GetDuration(), inc.GetDuration()) >= req["durationFrames"],
            "live handles or adjacent event duration are insufficient",
        )
    except Exception as exc:
        raise ProbeRefusal(f"live boundary preflight failed: {exc}") from exc
    try:
        result = before["outgoing"].AddTransition(
            {
                "type": record["addTransition"]["type"],
                "category": record["addTransition"]["category"],
                "position": "end",
                "alignment": req["alignment"],
                "duration": req["durationFrames"],
            }
        )
        if result is None or result is False:
            return _uncertain(plan, "AddTransition returned no transition")
        after = locate_boundary(req)
        if (
            after.get("outgoingId") != req["outgoingId"]
            or after.get("incomingId") != req["incomingId"]
        ):
            return _uncertain(plan, "live locator changed after AddTransition")
        transition = after.get("transition")
        if transition is None:
            return _uncertain(plan, "live locator found no applied transition")
        if req["controls"]:
            tool = _tool(transition, record)
            for name, value in req["controls"].items():
                if tool.SetInput(record["controls"][name]["id"], value) is False:
                    return _uncertain(plan, f"SetInput failed for {name}")
        return observe_transition(transition, declaration, inventory)
    except Exception as exc:
        return _uncertain(plan, f"Resolve write or post-write check failed: {exc}")
