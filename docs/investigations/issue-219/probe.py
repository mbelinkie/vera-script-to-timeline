"""Isolated #219 probe. Four hardcoded schedules; no production cue interface.

Execute from the authorized Resolve bridge with an injected ``resolve`` object.
The source path comes from VERA219_TEMPLATE; bytes must match the one fixed pin.
All outputs go to the repository's ignored out/issue-219 directory.
"""

import hashlib
import json
import os
from fractions import Fraction
from pathlib import Path

if not __debug__:
    raise RuntimeError("Run this mutation probe without Python optimization flags")
import re
from datetime import UTC, datetime

PIN = "869bffd705ac949a58bcb25d6bc80de5027219792336f0d599be81162447440a"
DATA = "ITEM\tVALUE\nAlpha\t18\nBeta\t27\nGamma\t9"
DATA_HASH = "1aec6e192c64748a6102507e45c59bb5d193bb8ae5e43e3e5e2469672d220d64"
MANIFEST = "issue219-synthetic-targets-v1"
MANIFEST_HASH = "dc21391f032d35cadab909e590302bc7ed8a46567703da93b4f82846d7948424"
manifest_bytes = Path(__file__).with_name("target-manifest.json").read_bytes()
if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_HASH:
    raise ValueError("target manifest changed; explicit new reviewed revision required")
TARGETS = {t["id"]: t["bodyPosition"] for t in json.loads(manifest_bytes)["targets"]}
OUTPUT = Path(__file__).resolve().parents[3] / "out" / "issue-219"
PROJECT_NAME = "VERA Issue219 Target Probe 20261015"
VERSION = [21, 1, 1, 10, ""]


def cue(target, start, end, timing="interval"):
    return {
        "targets": [target],
        "state": "emphasis",
        "start": start,
        "end": end,
        "timing": timing,
    }


CASES = {
    "sequential": {
        "cues": [cue("target-a", 48, 72), cue("target-b", 72, 96)],
        "steps": [(0, ""), (48, "1"), (72, "2"), (96, "")],
        "samples": {0: "", 47: "", 48: "1", 71: "1", 72: "2", 95: "2", 96: "", 239: ""},
    },
    "start-only": {
        "cues": [
            cue("target-a", 48, 72, "until-next"),
            cue("target-b", 72, 240, "until-end"),
        ],
        "steps": [(0, ""), (48, "1"), (72, "2")],
        "samples": {
            0: "",
            47: "",
            48: "1",
            71: "1",
            72: "2",
            95: "2",
            96: "2",
            227: "2",
            228: "2",
            239: "2",
        },
    },
    "overlap": {
        "cues": [cue("target-a", 48, 96), cue("target-b", 72, 120)],
        "steps": [(0, ""), (48, "1"), (72, "1,2"), (96, "2"), (120, "")],
        "samples": {
            0: "",
            47: "",
            48: "1",
            71: "1",
            72: "1,2",
            95: "1,2",
            96: "2",
            119: "2",
            120: "",
            239: "",
        },
    },
    "continuation": {
        "cues": [cue("target-a", 48, 72), cue("target-a", 72, 96)],
        "steps": [(0, ""), (48, "1"), (96, "")],
        "samples": {0: "", 47: "", 48: "1", 71: "1", 72: "1", 95: "1", 96: "", 239: ""},
    },
}


def preflight(
    case,
    *,
    data=DATA,
    manifest=MANIFEST,
    graph_ok=True,
    control_type="Text",
    asset_hash=PIN,
):
    """Refuse the whole issue-owned example before its first state write."""
    if hashlib.sha256(data.encode()).hexdigest() != DATA_HASH:
        raise ValueError("dataset changed; explicit new manifest required")
    if (
        manifest != MANIFEST
        or asset_hash != PIN
        or not graph_ok
        or control_type != "Text"
    ):
        raise ValueError("manifest/template/graph/control mismatch")
    cues = case["cues"]
    previous = -1
    for i, entry in enumerate(cues):
        start, end = entry["start"], entry["end"]
        if (
            type(start) is not int
            or type(end) is not int
            or not 0 <= start < end <= 240
            or start < previous
        ):
            raise ValueError("unordered or invalid frame interval")
        previous = start
        targets = entry["targets"]
        if (
            not targets
            or len(set(targets)) != len(targets)
            or any(t not in TARGETS for t in targets)
        ):
            raise ValueError("missing/unknown/duplicate target")
        if entry["state"] not in ("base", "emphasis"):
            raise ValueError("unknown state")
        timing = entry["timing"]
        if timing == "until-next":
            if i + 1 == len(cues) or end != cues[i + 1]["start"]:
                raise ValueError("explicit until-next endpoint mismatch")
        elif timing == "until-end":
            if end != 240:
                raise ValueError("explicit Graphic-end endpoint mismatch")
        elif timing != "interval":
            raise ValueError("missing start-only end policy")
        for other in cues[:i]:
            if (
                max(start, other["start"]) < min(end, other["end"])
                and set(targets) & set(other["targets"])
                and entry["state"] != other["state"]
            ):
                raise ValueError("contradictory states on one target")
    steps = case["steps"]
    if (
        not steps
        or steps[0][0] != 0
        or any(steps[i][0] >= steps[i + 1][0] for i in range(len(steps) - 1))
    ):
        raise ValueError("invalid hardcoded steps")
    # Check the fixed aggregate table; do not compile or accept external cue input.
    for frame in range(240):
        positions = {
            TARGETS[t]
            for c in cues
            if c["start"] <= frame < c["end"] and c["state"] == "emphasis"
            for t in c["targets"]
        }
        expected = ",".join(str(x) for x in sorted(positions))
        actual = [value for at, value in steps if at <= frame][-1]
        if actual != expected or (
            frame in case["samples"] and case["samples"][frame] != expected
        ):
            raise ValueError("hardcoded aggregate state mismatch")


def guarded_write(case, write, **kwargs):
    preflight(case, **kwargs)
    for step in case["steps"]:
        write(step)


def current(resolve, project_id):
    p = resolve.GetProjectManager().GetCurrentProject()
    if (
        not p
        or p.GetUniqueId() != project_id
        or p.GetName() != PROJECT_NAME
        or resolve.GetVersion() != VERSION
        or p.IsRenderingInProgress()
    ):
        raise ValueError("wrong project/version or active render")
    settings = p.GetSettings()
    if any(
        Fraction(str(settings[k])) != v
        for k, v in {
            "timelineFrameRate": 24,
            "timelineResolutionWidth": 1920,
            "timelineResolutionHeight": 1080,
        }.items()
    ):
        raise ValueError("wrong project frame profile")
    return p


def source():
    asset = Path(os.environ["VERA219_TEMPLATE"])
    raw = asset.read_bytes()
    if hashlib.sha256(raw).hexdigest() != PIN:
        raise ValueError("source pin mismatch")
    text = raw.decode()
    kinds = {
        "MacroOperator",
        "Background",
        "TextPlus",
        "RectangleMask",
        "FastNoise",
        "Merge",
        "Transform",
    }
    nodes = sorted(
        (n, k) for n, k in re.findall(r"^\s*(\w+) = (\w+) \{", text, re.M) if k in kinds
    )
    if len(nodes) != 127 or ("EV24Table", "MacroOperator") not in nodes:
        raise ValueError("source graph mismatch")
    return asset, nodes


def inspect(comp, nodes, animated):
    tools = list(comp.GetToolList(False).values())
    outputs = [t for t in tools if t.GetAttrs("TOOLS_RegID") == "MediaOut"]
    modifiers = [t for t in tools if t.GetAttrs("TOOLS_RegID") == "BezierSpline"]
    remainder = sorted(
        (t.GetAttrs("TOOLS_Name"), t.GetAttrs("TOOLS_RegID"))
        for t in tools
        if t not in outputs + modifiers
    )
    if remainder != nodes or len(outputs) != 1 or len(modifiers) != int(animated):
        raise ValueError("live graph mismatch")
    macro = comp.FindTool("EV24Table")
    inp = next(
        i
        for i in macro.GetInputList().values()
        if i.GetAttrs()["INPS_ID"] == "HighlightRows"
    )
    if inp.GetAttrs()["INPS_DataType"] != "Text":
        raise ValueError("live control type mismatch")
    output_input = next(
        i
        for i in outputs[0].GetInputList().values()
        if i.GetAttrs()["INPS_ID"] == "Input"
    )
    connected = output_input.GetConnectedOutput()
    # Fusion resolves the macro's published output to this pinned internal Merge.
    if not connected or (
        connected.GetTool().GetAttrs("TOOLS_Name"),
        connected.GetTool().GetAttrs("TOOLS_RegID"),
    ) != ("DiagnosticOver", "Merge"):
        raise ValueError("wrong MediaOut source")
    if animated:
        connection = inp.GetConnectedOutput()
        if (
            not connection
            or connection.GetAttrs()["OUTS_DataType"] != "Text"
            or (
                connection.GetTool().GetAttrs("TOOLS_Name"),
                connection.GetTool().GetAttrs("TOOLS_RegID"),
            )
            != ("ControlsHighlightRows", "BezierSpline")
            or modifiers[0].GetAttrs("TOOLS_Name") != "ControlsHighlightRows"
        ):
            raise ValueError("wrong text animation binding")
    return macro, inp


def receipt(path, data):
    with path.open("x") as f:
        json.dump(data, f, indent=2, sort_keys=True, default=str)
        f.write("\n")


def prepare(resolve, project_id, run, name):
    """Create one fixed example per short bridge call; never retry an existing one."""
    if run not in ("run-a", "run-b") or name not in CASES:
        raise ValueError("only fixed repeat runs and cases are allowed")
    for case in CASES.values():
        preflight(case)
    asset, nodes = source()
    p = current(resolve, project_id)
    folder = OUTPUT / run
    if (folder / f"{name}-prepared.json").exists():
        raise ValueError("case already started; inspect it rather than retrying")
    names = {
        p.GetTimelineByIndex(i).GetName() for i in range(1, p.GetTimelineCount() + 1)
    }
    if f"219-{run}-{name}" in names:
        raise ValueError("timeline name already exists")
    pool = p.GetMediaPool()
    seeds = [
        x
        for x in pool.GetRootFolder().GetClipList()
        if x.GetClipProperty("Type") == "Still"
        and Path(x.GetClipProperty("File Path")).resolve()
        == (OUTPUT / "seed.png").resolve()
    ]
    if len(seeds) != 1:
        raise ValueError("exact private seed unavailable")
    folder.mkdir(exist_ok=True)
    result = {}
    case = CASES[name]
    tl = pool.CreateEmptyTimeline(f"219-{run}-{name}")
    assert tl and p.SetCurrentTimeline(tl) and tl.SetStartTimecode("00:00:00:00")
    assert seeds[0].SetMarkInOut(0, 240, "video")
    try:
        placed = pool.AppendToTimeline(
            [
                {
                    "mediaPoolItem": seeds[0],
                    "startFrame": 0,
                    "endFrame": 240,
                    "recordFrame": 0,
                    "trackIndex": 1,
                    "mediaType": 1,
                }
            ]
        )
    finally:
        assert seeds[0].ClearMarkInOut("video")
    assert len(placed) == 1
    item = placed[0]
    assert (item.GetStart(), item.GetDuration(), item.GetEnd()) == (0, 240, 240)
    comp = item.ImportFusionComp(str(asset))
    assert comp and item.GetFusionCompCount() == 1
    roots = [
        t
        for t in comp.GetToolList(False).values()
        if t.GetAttrs("TOOLS_RegID") == "MacroOperator"
    ]
    assert len(roots) == 1 and roots[0].GetAttrs("TOOLS_Name") == "EV24Table"
    outputs = [
        t
        for t in comp.GetToolList(False).values()
        if t.GetAttrs("TOOLS_RegID") == "MediaOut"
    ]
    assert len(outputs) <= 1
    output = outputs[0] if outputs else comp.AddTool("MediaOut", 0, 0)
    assert output.ConnectInput("Input", roots[0])
    macro, _ = inspect(comp, nodes, False)
    macro.SetInput("TableData", DATA)
    macro.SetInput("TableTitle", "SYNTHETIC TARGET PROBE")
    assert macro.AddModifier("HighlightRows", "BezierSpline")
    macro, inp = inspect(comp, nodes, True)
    guarded_write(case, lambda step: macro.SetInput("HighlightRows", step[1], step[0]))
    got = {f: macro.GetInput("HighlightRows", f) for f in case["samples"]}
    assert got == case["samples"], got
    assert macro.GetInput("TableData") == DATA
    assert (
        comp.GetAttrs()["COMPN_RenderStart"],
        comp.GetAttrs()["COMPN_RenderEnd"],
    ) == (0, 239)
    assert item.ExportFusionComp(str(folder / f"{name}.comp"), 1)
    result[name] = {
        "timeline_id": tl.GetUniqueId(),
        "frames": got,
        "keys": inp.GetKeyFrames(),
        "input_attrs": inp.GetAttrs(),
    }
    receipt(folder / f"{name}-prepared.json", result[name])
    assert resolve.GetProjectManager().SaveProject()
    return result


def verify(resolve, project_id, run, label):
    """Read existing examples only; retain private raw readback."""
    if run not in ("run-a", "run-b") or label not in (
        "before-reopen",
        "after-reopen",
        "after-render",
    ):
        raise ValueError("unknown fixed verification phase")
    _, nodes = source()
    p = current(resolve, project_id)
    result = {}
    for name, case in CASES.items():
        matches = [
            p.GetTimelineByIndex(i)
            for i in range(1, p.GetTimelineCount() + 1)
            if p.GetTimelineByIndex(i).GetName() == f"219-{run}-{name}"
        ]
        assert len(matches) == 1
        tl = matches[0]
        items = tl.GetItemListInTrack("video", 1)
        assert len(items) == 1
        item = items[0]
        assert (item.GetStart(), item.GetDuration(), item.GetEnd()) == (0, 240, 240)
        comp = item.GetFusionCompByIndex(1)
        macro, inp = inspect(comp, nodes, True)
        got = {f: macro.GetInput("HighlightRows", f) for f in case["samples"]}
        assert got == case["samples"] and macro.GetInput("TableData") == DATA
        controls = comp.FindTool("Controls")
        geometry = {
            key: controls.GetInput(key, 72)
            for key in ("BodyTop", "RowPitch", "TableLeft", "TableW")
        }
        result[name] = {
            "timeline_id": tl.GetUniqueId(),
            "frames": got,
            "keys": inp.GetKeyFrames(),
            "geometry": geometry,
        }
    receipt(OUTPUT / run / f"{label}.json", result)
    return result


def reopen(resolve, project_id):
    p = current(resolve, project_id)
    manager = resolve.GetProjectManager()
    assert manager.SaveProject() and manager.CloseProject(p)
    loaded = manager.LoadProject(PROJECT_NAME)
    assert loaded and loaded.GetUniqueId() == project_id
    return loaded.GetTimelineCount()


def queue_case(resolve, project_id, run, name):
    """Queue private exact-frame PNGs; this function never starts rendering.

    Require shared heavy-slot release separately before starting any render.
    A partial queue is an ambiguous mutation to inspect, never blindly retry.
    """
    if run not in ("run-a", "run-b") or name not in CASES:
        raise ValueError("unknown fixed run/case")
    case = CASES[name]
    preflight(case)
    _, nodes = source()
    p = current(resolve, project_id)
    prepared = json.loads((OUTPUT / run / f"{name}-prepared.json").read_text())
    matches = [
        p.GetTimelineByIndex(i)
        for i in range(1, p.GetTimelineCount() + 1)
        if p.GetTimelineByIndex(i).GetUniqueId() == prepared["timeline_id"]
    ]
    assert len(matches) == 1
    tl = matches[0]
    assert tl.GetName() == f"219-{run}-{name}" and tl.GetStartFrame() == 0
    items = tl.GetItemListInTrack("video", 1)
    assert len(items) == 1 and items[0].GetDuration() == 240
    macro, _ = inspect(items[0].GetFusionCompByIndex(1), nodes, True)
    assert macro.GetInput("TableData") == DATA
    assert {f: macro.GetInput("HighlightRows", f) for f in case["samples"]} == case[
        "samples"
    ]
    target = OUTPUT / run / "renders" / name
    target.mkdir(parents=True, exist_ok=False)
    before = {
        "format_codec": p.GetCurrentRenderFormatAndCodec(),
        "mode": p.GetCurrentRenderMode(),
    }
    receipt(
        target / "queue-intent.json",
        {"frames": case["samples"], "timeline_id": tl.GetUniqueId(), "before": before},
    )
    jobs = {}
    assert p.SetCurrentTimeline(tl)
    try:
        assert p.SetCurrentRenderMode(1)
        assert p.SetCurrentRenderFormatAndCodec("png", "RGB8")
        for frame in case["samples"]:
            settings = {
                "SelectAllFrames": False,
                "MarkIn": frame,
                "MarkOut": frame,
                "TargetDir": str(target),
                "CustomName": f"{name}-f{frame:03d}",
                "UseUniqueFilenames": False,
                "ReplaceExistingFilesInPlace": False,
                "ExportVideo": True,
                "ExportAudio": False,
                "ExportAlpha": False,
                "FormatWidth": 1920,
                "FormatHeight": 1080,
                "FrameRate": 24,
                "PixelAspectRatio": "square",
                "DataBurnIn": "None",
            }
            receipt(target / f"f{frame:03d}-intent.json", settings)
            assert p.SetRenderSettings(settings)
            job = p.AddRenderJob()
            assert isinstance(job, str) and job
            jobs[frame] = job
            receipt(
                target / f"f{frame:03d}-job.json",
                {"job": job, "frame": frame, "timeline_id": tl.GetUniqueId()},
            )
    finally:
        assert p.SetCurrentRenderFormatAndCodec(
            before["format_codec"]["format"], before["format_codec"]["codec"]
        )
        assert p.SetCurrentRenderMode(before["mode"])
    receipt(target / "queue-complete.json", jobs)
    assert resolve.GetProjectManager().SaveProject()
    return jobs


def render_jobs():
    jobs = []
    for run in ("run-a", "run-b"):
        for name, case in CASES.items():
            recorded = json.loads(
                (OUTPUT / run / "renders" / name / "queue-complete.json").read_text()
            )
            if set(recorded) != {str(f) for f in case["samples"]}:
                raise ValueError("incomplete frame queue")
            jobs.extend(recorded.values())
    if len(jobs) != 72 or len(set(jobs)) != 72:
        raise ValueError("wrong/duplicate render job inventory")
    return jobs


def start_render(resolve, project_id):
    """Only call after the owner has verified exclusive heavy-slot release."""
    p = current(resolve, project_id)
    jobs = render_jobs()
    actual = {job["JobId"] for job in p.GetRenderJobList()}
    if actual != set(jobs):
        raise ValueError("unexpected/missing render job; do not render all blindly")
    receipt(
        OUTPUT / "render-start-intent.json",
        {
            "project_id": project_id,
            "jobs": jobs,
            "version": resolve.GetVersion(),
            "started_at": datetime.now(UTC).isoformat(),
        },
    )
    assert p.StartRendering(jobs, False)
    return {"started": True, "jobs": len(jobs)}


def render_status(resolve, project_id):
    """One bounded observation per scheduled wake; never restart a job."""
    p = resolve.GetProjectManager().GetCurrentProject()
    if not p or p.GetUniqueId() != project_id or p.GetName() != PROJECT_NAME:
        raise ValueError("wrong project during render observation")
    statuses = {job: p.GetRenderJobStatus(job) for job in render_jobs()}
    observed = datetime.now(UTC)
    report = {
        "observed_at": observed.isoformat(),
        "rendering": p.IsRenderingInProgress(),
        "jobs": statuses,
    }
    receipt(
        OUTPUT / f"render-status-{observed.strftime('%Y%m%dT%H%M%S%fZ')}.json", report
    )
    counts = {}
    for state in statuses.values():
        key = state.get("JobStatus", "UNKNOWN")
        counts[key] = counts.get(key, 0) + 1
    return {"rendering": report["rendering"], "counts": counts}
