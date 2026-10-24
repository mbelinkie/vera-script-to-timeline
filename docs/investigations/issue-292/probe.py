"""Small live probe, not a production adapter or full installed inventory.

Run from repository root with: uv run python docs/investigations/issue-292/probe.py
Requires the issue-owned disposable project, synthetic media and installed fixture
described in ../issue-292-transitions.md. Creates a new timeline; never reuses one.
"""

import hashlib
import json
import sys
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
sys.path.insert(
    0,
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Developer/Scripting/Modules",
)
import DaVinciResolveScript as dvr  # noqa: E402

from scripts.issue292_transition_probe import apply_transition  # noqa: E402


def run():
    resolve = dvr.scriptapp("Resolve")
    assert resolve and resolve.GetVersion()[:4] == [21, 1, 1, 10]
    project = resolve.GetProjectManager().GetCurrentProject()
    assert project.GetName() == "VERA292Probe20261024A"
    assert not project.IsRenderingInProgress()
    root = Path.home() / ".local/share/vera/issue-292-transition-proof"
    declaration = json.loads(
        Path(__file__).with_name("custom-declaration.json").read_text()
    )
    installed = (
        Path.home()
        / "Library/Application Support/Blackmagic Design/DaVinci Resolve"
        / "Fusion/Templates/Edit/Transitions/VERA292 Curve Dissolve.setting"
    )
    fingerprint = hashlib.sha256(installed.read_bytes()).hexdigest()
    assert fingerprint == declaration["effect"]["fingerprint"]
    media_pool = project.GetMediaPool()
    media = {item.GetName(): item for item in media_pool.GetRootFolder().GetClipList()}
    for name in ("red.mov", "blue.mov", "narration.wav"):
        assert Path(media[name].GetClipProperty("File Path")).resolve() == root / name
    timeline = media_pool.CreateEmptyTimeline("292-retained-" + uuid.uuid4().hex[:8])
    assert timeline.SetStartTimecode("00:00:00:00")
    clips = media_pool.AppendToTimeline(
        [
            {
                "mediaPoolItem": media["red.mov"],
                "startFrame": 24,
                "endFrame": 96,
                "mediaType": 1,
                "recordFrame": 0,
            },
            {
                "mediaPoolItem": media["blue.mov"],
                "startFrame": 24,
                "endFrame": 96,
                "mediaType": 1,
                "recordFrame": 72,
            },
            {
                "mediaPoolItem": media["narration.wav"],
                "startFrame": 0,
                "endFrame": 144,
                "mediaType": 2,
                "recordFrame": 0,
            },
        ]
    )
    for clip, marker in zip(clips[:2], ("292:outgoing", "292:incoming"), strict=True):
        assert clip.AddMarker(0, "Blue", marker, "292 synthetic", 1, marker)
    assert timeline.AddMarker(
        72, "Blue", "Boundary 292", "fixed narration anchor", 1, "292:boundary"
    )
    # Metadata is measured from an already instantiated representative, not guessed.
    sample = next(
        project.GetTimelineByIndex(i)
        for i in range(1, project.GetTimelineCount() + 1)
        if project.GetTimelineByIndex(i).GetName() == "292-type-VERA292 Curve Dissolve"
    )
    transition = next(
        i for i in sample.GetItemListInTrack("video", 1) if i.GetType() == "transition"
    )
    group = transition.GetFusionCompByIndex(1).FindTool("VERA292CurveDissolve")
    attrs = {
        i.GetAttrs()["INPS_ID"]: i.GetAttrs() for i in group.GetInputList().values()
    }
    controls = {
        key: {
            "id": key,
            "type": "enum",
            "values": list(attrs[key]["INPIDT_ComboControl_ID"].values()),
        }
        for key in declaration["controls"]
    }
    inventory = {
        "scope": "292-representatives",
        "online": True,
        "completeWithinScope": True,
        "effects": [
            {
                **declaration["effect"],
                "fingerprint": fingerprint,
                "addTransition": {
                    "type": declaration["effect"]["name"],
                    "category": "fusion",
                },
                "observedType": "transition",
                "fusionToolName": "VERA292CurveDissolve",
                "controls": controls,
            }
        ],
        "boundaries": {
            "292:boundary": {
                "frame": 72,
                "outgoing": {
                    "id": "292:outgoing",
                    "trackId": "V1",
                    "endFrame": 72,
                    "rightHandleFrames": int(clips[0].GetRightOffset()),
                },
                "incoming": {
                    "id": "292:incoming",
                    "trackId": "V1",
                    "startFrame": 72,
                    "leftHandleFrames": int(clips[1].GetLeftOffset()),
                },
            }
        },
    }

    def locate(request):
        items = timeline.GetItemListInTrack("video", 1)
        out, inc = [
            next(i for i in items if i.GetMarkerByCustomData(request[key]))
            for key in ("outgoingId", "incomingId")
        ]
        assert out.GetEnd() == inc.GetStart() == request["boundaryFrame"]
        matches = [i for i in items if i.GetType() == "transition"]
        assert len(matches) <= 1
        return {
            "outgoingId": request["outgoingId"],
            "incomingId": request["incomingId"],
            "outgoing": out,
            "incoming": inc,
            "transition": matches[0] if matches else None,
        }

    result = apply_transition(declaration, inventory, locate)
    assert result["status"] == "observed", result
    assert clips[2].GetStart() == 0 and clips[2].GetEnd() == 144
    assert timeline.GetMarkers()[72]["customData"] == "292:boundary"
    assert all(
        i.GetType() != "transition" for i in timeline.GetItemListInTrack("audio", 1)
    )
    assert resolve.GetProjectManager().SaveProject()
    result["timeline"] = timeline.GetName()
    (root / (timeline.GetName() + ".json")).write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    run()
