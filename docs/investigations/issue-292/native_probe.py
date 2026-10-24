"""Bounded native OTIO import proof using the Producer-edited synthetic seed.

Run in the issue-owned project only. This bypasses no production verifier:
it exercises Resolve's own import API, separate from VERA's cut-only package.
"""

import json
import sys
import uuid
from pathlib import Path

sys.path.insert(
    0,
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules",
)
import DaVinciResolveScript as dvr


def walk(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk(child)


def run():
    resolve = dvr.scriptapp("Resolve")
    assert resolve and resolve.GetVersion()[:4] == [21, 1, 1, 10]
    project = resolve.GetProjectManager().GetCurrentProject()
    assert project.GetName() == "VERA292Probe20261024A"
    assert not project.IsRenderingInProgress()
    root = Path.home() / ".local/share/vera/issue-292-transition-proof"
    declaration = json.loads(
        Path(__file__).with_name("native-declaration.json").read_text()
    )
    assert declaration == {
        "boundaryId": "292:native-red-blue:72",
        "boundaryFrame": 72,
        "effect": {"name": "Edge Wipe", "resolveType": 13},
        "durationFrames": 24,
        "alignment": "center",
        "controls": {"angle": 180},
    }, "Only the measured native case is qualified"
    seed = json.loads((root / "producer-angle90.otio").read_text())
    references = [x["target_url"] for x in walk(seed) if "target_url" in x]
    assert set(references) == {
        str(root / "red.mov"),
        str(root / "blue.mov"),
    }, "Synthetic source binding changed"
    transitions = [x for x in walk(seed) if x.get("OTIO_SCHEMA") == "Transition.1"]
    assert len(transitions) == 1
    transition = transitions[0]
    effect = transition["metadata"]["Resolve_OTIO"]["Effects"]
    assert transition["name"] == "Edge Wipe" and effect["Type"] == 13
    assert all(transition[k]["value"] == 12 for k in ("in_offset", "out_offset"))
    parameter = next(p for p in effect["Parameters"] if p["Parameter ID"] == "angle")
    assert parameter["Variant Type"] == "Int" and parameter["Parameter Value"] == 90
    parameter["Parameter Value"] = declaration["controls"]["angle"]
    name = "292-native-retained-" + uuid.uuid4().hex[:8]
    source = root / (name + ".otio")
    source.write_text(json.dumps(seed, indent=2))
    timeline = project.GetMediaPool().ImportTimelineFromFile(
        str(source), {"timelineName": name}
    )
    assert timeline
    items = timeline.GetItemListInTrack("video", 1)
    assert [(x.GetType(), x.GetStart(), x.GetEnd()) for x in items] == [
        ("video", 0, 72),
        ("transition", 60, 84),
        ("video", 72, 144),
    ]
    destination = root / (name + "-readback.otio")
    assert timeline.Export(str(destination), resolve.EXPORT_OTIO)
    actual = next(
        x
        for x in walk(json.loads(destination.read_text()))
        if x.get("OTIO_SCHEMA") == "Transition.1"
    )
    values = actual["metadata"]["Resolve_OTIO"]["Effects"]["Parameters"]
    assert (
        next(p["Parameter Value"] for p in values if p["Parameter ID"] == "angle")
        == 180
    )
    assert resolve.GetProjectManager().SaveProject()
    print(
        json.dumps(
            {
                "timeline": name,
                "requested": declaration,
                "observedAngle": 180,
                "observedSpan": [60, 84],
            }
        )
    )


if __name__ == "__main__":
    run()
