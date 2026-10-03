"""Stdlib fake acceptance check for R4 availability setup; never launches Resolve."""

import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("probe", HERE / "probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
checkpoint = HERE / "evidence/matrix-finalize-success" / probe.PICTURE_CAPTURE
source = HERE / "inputs/relink/base.mov"


class Media:
    def __init__(self, uid, path):
        self.uid, self.path = uid, str(path)

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return Path(self.path).name

    def GetClipProperty(self):
        return {"File Path": self.path}

    def GetMarkers(self):
        return {}

    def GetAudioMapping(self):
        return {}


class Folder:
    def __init__(self, uid, name, clips=(), children=()):
        self.uid, self.name, self.clips, self.children = (
            uid,
            name,
            list(clips),
            list(children),
        )

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipList(self):
        return self.clips

    def GetSubFolderList(self):
        return self.children


class Item(Media):
    def __init__(self, uid, media, timeline):
        super().__init__(uid, media.path)
        self.media, self.timeline = media, timeline

    def GetType(self):
        return "video"

    def GetTrackTypeAndIndex(self):
        return ["video", 1]

    def GetStart(self):
        return 0

    def GetEnd(self):
        return 199

    def GetDuration(self):
        return 199

    def GetSourceStartFrame(self):
        return 0

    def GetSourceEndFrame(self):
        return 199

    def GetLeftOffset(self):
        return 0

    def GetRightOffset(self):
        return 0

    def GetStartTime(self):
        return 0

    def GetEndTime(self):
        return 0

    def GetMarkers(self):
        return {}

    def GetLinkedItems(self):
        return []

    def GetMediaPoolItem(self):
        return self.media

    def __getattr__(self, name):
        if name.startswith("Get"):
            return lambda *args: None
        raise AttributeError(name)


class Timeline:
    def __init__(self, uid, name):
        self.uid, self.name, self.items = uid, name, []
        self.pool_item = TimelinePoolItem(f"pool-{uid}", name)

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetMediaPoolItem(self):
        return self.pool_item

    def GetTrackCount(self, kind):
        return 1 if kind == "video" else 0

    def GetItemListInTrack(self, kind, index):
        return (
            [Item(item.uid, item.media, item.timeline) for item in self.items]
            if (kind, index) == ("video", 1)
            else []
        )


class TimelinePoolItem:
    """Resolve's pool proxy for a timeline; it has metadata but no file path."""

    def __init__(self, uid, name):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetClipProperty(self):
        return {"Usage": "1"}

    def GetMarkers(self):
        return {}

    def GetAudioMapping(self):
        return {}


class Pool:
    def __init__(self, project, imported_mode="new"):
        self.project, self.imported_mode, self.calls = project, imported_mode, []
        self.base = Media("base-existing", HERE / "inputs/base.mov")
        self.root = Folder(
            "root",
            "Root",
            [self.base, *(timeline.pool_item for timeline in project.timelines)],
            [Folder("nested", "nested")],
        )

    def GetRootFolder(self):
        return self.root

    def ImportMedia(self, entries):
        self.calls.append("ImportMedia")
        assert entries == [str(source.resolve())]
        if self.imported_mode == "empty":
            return []
        if self.imported_mode == "multiple":
            return [Media("x", source), Media("y", source)]
        if self.imported_mode == "dedup":
            return [self.base]
        if self.imported_mode == "collision":
            collision = Media("base-existing", source)
            self.root.clips.append(collision)
            return [collision]
        path = (
            HERE / "inputs/base.mov" if self.imported_mode == "wrong-path" else source
        )
        media = Media("new-import", path)
        self.root.children[0].clips.append(media)
        return [media]

    def CreateEmptyTimeline(self, name):
        self.calls.append("CreateEmptyTimeline")
        timeline = Timeline("new-timeline", name)
        self.project.timelines.append(timeline)
        self.root.clips.append(timeline.pool_item)
        self.project.current = timeline
        return timeline

    def AppendToTimeline(self, infos):
        self.calls.append("AppendToTimeline")
        info = infos[0]
        item = Item("one-occurrence", info["mediaPoolItem"], self.project.current)
        self.project.current.items.append(item)
        if self.imported_mode == "mutate-old":
            self.project.old_changed = True
        return [item]


class Project:
    def __init__(self, pinned, mode):
        self.pinned = pinned
        self.old_changed = False
        self.uid = pinned["projectId"]
        self.name = "VERA Issue 141 Synthetic Probe test"
        self.timelines = [
            Timeline(row["GetUniqueId"]["value"], row["GetName"]["value"])
            for row in pinned["timelines"]
        ]
        self.current = next(
            t for t in self.timelines if t.uid == probe.MATRIX_PARTIAL_ID
        )
        self.pool = Pool(self, mode)

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetCurrentTimeline(self):
        return self.current

    def SetCurrentTimeline(self, timeline):
        self.pool.calls.append("SetCurrentTimeline")
        self.current = timeline
        return True

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetMediaPool(self):
        return self.pool


class Manager:
    def __init__(self, project):
        self.project, self.calls = project, project.pool.calls

    def GetCurrentProject(self):
        return self.project

    def SaveProject(self):
        self.calls.append("SaveProject")
        return True


class Resolve:
    def __init__(self, project):
        self.manager = Manager(project)

    def GetProjectManager(self):
        return self.manager


def exercise(mode="new", *, changed_checkpoint=False, changed_project=False):
    with tempfile.TemporaryDirectory() as temp:
        out = Path(temp)
        shutil.copyfile(checkpoint, out / probe.PICTURE_CAPTURE)
        pinned = json.loads(checkpoint.read_text())["passes"][0]
        project = Project(pinned, mode)
        if mode == "unmapped-pool-entry":
            project.pool.root.clips.append(
                TimelinePoolItem("unmapped-pool-item", "unmapped")
            )
        if changed_project:
            project.uid = "wrong-project"
        prepared_identity = {
            "projectId": pinned["projectId"],
            "projectName": project.name,
        }
        (out / "prepared.json").write_text(
            json.dumps({"identity": prepared_identity, "manifestSha256": "manifest"})
        )
        config = {
            "action": "r4-availability",
            "projectName": project.name,
            "mediaDir": str((HERE / "inputs").resolve()),
            "manifestSha256": "manifest",
        }
        old_observe, old_capture = probe.observe, probe.capture
        old_sha256, old_source_evidence = probe.sha256, probe.source_evidence

        def observed(resolve, config, identity, expected):
            if changed_checkpoint:
                return {**pinned, "projectName": "changed"}
            state = deepcopy(pinned)
            rows = state["timelines"]
            if project.old_changed:
                rows[0]["GetStartFrame"]["value"] = "changed"
            for timeline in project.timelines:
                if timeline.uid not in {row["GetUniqueId"]["value"] for row in rows}:
                    rows.append(
                        {
                            "GetUniqueId": {"value": timeline.uid},
                            "GetName": {"value": timeline.name},
                        }
                    )
            for row in state["timelines"]:
                markers = row.get("GetMarkers", {}).get("value")
                if isinstance(markers, dict):
                    row["GetMarkers"]["value"] = {
                        int(key): value for key, value in markers.items()
                    }
                for track in row.get("tracks", []):
                    for item in track.get("items", []):
                        markers = item.get("GetMarkers", {}).get("value")
                        if isinstance(markers, dict):
                            item["GetMarkers"]["value"] = {
                                int(key): value for key, value in markers.items()
                            }
                        track_index = item.get("GetTrackTypeAndIndex", {}).get("value")
                        if isinstance(track_index, list):
                            item["GetTrackTypeAndIndex"]["value"] = tuple(track_index)
            return state

        def captured(resolve, config, identity, expected, output, stamp, environment):
            state = observed(resolve, config, identity, expected)
            for timeline in project.timelines:
                if timeline.uid == "new-timeline":
                    state["timelines"] = [
                        row
                        for row in state["timelines"]
                        if row["GetUniqueId"]["value"] != timeline.uid
                    ]
                    state["timelines"].append(
                        {
                            "GetUniqueId": {"value": timeline.uid},
                            "GetName": {"value": timeline.name},
                            "tracks": [
                                {
                                    "type": "video",
                                    "index": 1,
                                    "items": [
                                        probe.item_evidence(item, expected)
                                        for item in timeline.items
                                    ],
                                }
                            ],
                        }
                    )
            path = output / "fake-final.json"
            path.write_text(json.dumps({"passes": [state, state]}))
            return {"status": "equal-adjacent-reads", "capturePath": str(path)}

        probe.observe, probe.capture = observed, captured
        probe.sha256 = lambda path: (
            probe.PICTURE_CAPTURE_SHA256
            if Path(path).name == probe.PICTURE_CAPTURE
            else old_sha256(path)
        )
        if mode == "wrong-hash":
            probe.source_evidence = lambda locator, approved: (
                {"status": "reachable", "sha256": "0" * 64, "hashMatches": False}
                if Path(locator) == source.resolve()
                else old_source_evidence(locator, approved)
            )
        try:
            expected = {
                str(source.resolve()): probe.sha256(source),
                str((HERE / "inputs/base.mov").resolve()): probe.sha256(
                    HERE / "inputs/base.mov"
                ),
            }
            try:
                result = probe.r4_prepare(
                    Resolve(project),
                    config,
                    prepared_identity,
                    expected,
                    out,
                    mode,
                    {"version": probe.CONTEXT_ENVIRONMENT},
                )
                return result, project.pool.calls, project
            except (RuntimeError, ValueError) as error:
                if mode == "unmapped-pool-entry":
                    diagnostics = list(out.glob("r4-pool-diagnostic-*.json"))
                    assert len(diagnostics) == 1, diagnostics
                    diagnostic = json.loads(diagnostics[0].read_text())
                    assert diagnostic["timelineMappings"]
                    assert diagnostic["failedEntry"]["GetClipProperty"]["value"] == {
                        "Usage": "1"
                    }
                return f"{type(error).__name__}: {error}", project.pool.calls, project
        finally:
            probe.observe, probe.capture = old_observe, old_capture
            probe.sha256, probe.source_evidence = old_sha256, old_source_evidence


# Recursive inventory must include nested items and report every folder UID.
root = Folder(
    "r", "root", [Media("a", source)], [Folder("c", "child", [Media("b", source)])]
)
fake_project = type(
    "P",
    (),
    {
        "GetMediaPool": lambda self: type(
            "MP", (), {"GetRootFolder": lambda self: root}
        )(),
        "GetTimelineCount": lambda self: 0,
    },
)()
inventory = probe._r4_pool_inventory(
    fake_project, {str(source.resolve()): probe.sha256(source)}
)
assert [row["uid"] for row in inventory["folders"]] == ["r", "c"]
assert {row["uid"] for row in inventory["items"]} == {"a", "b"}


def inventory_project(timelines, clips):
    folder = Folder("root", "Root", clips)
    pool = type("Pool", (), {"GetRootFolder": lambda self: folder})()
    return type(
        "P",
        (),
        {
            "GetMediaPool": lambda self: pool,
            "GetTimelineCount": lambda self: len(timelines),
            "GetTimelineByIndex": lambda self, index: timelines[index - 1],
        },
    )()


mapped_timeline = Timeline("timeline-uid", "VERA 141 Matrix").pool_item
timeline_proxy = Timeline("timeline-uid", "VERA 141 Matrix")
pool_timeline_inventory = probe._r4_pool_inventory(
    inventory_project([timeline_proxy], [mapped_timeline]),
    {str(source.resolve()): probe.sha256(source)},
)
assert timeline_proxy.uid != mapped_timeline.GetUniqueId()
assert pool_timeline_inventory["timelineMappings"][0]["poolItemUid"] == {
    "value": mapped_timeline.GetUniqueId()
}
assert pool_timeline_inventory["items"][0]["evidence"]["sourceBytes"] == {
    "status": "timeline-uid-not-hashed"
}
assert (
    "File Path"
    not in pool_timeline_inventory["items"][0]["evidence"]["GetClipProperty"]["value"]
)


bad_timeline = Timeline("timeline-bad", "VERA 141 Matrix")
bad_clip = TimelinePoolItem("unmapped-pool-item", "unmapped")
try:
    probe._r4_pool_inventory(
        inventory_project([bad_timeline], [bad_clip]),
        {str(source.resolve()): probe.sha256(source)},
    )
except probe._R4PoolInventoryError as error:
    assert error.diagnostic["timelineMappings"][0]["poolItemUid"]["value"] == (
        bad_timeline.pool_item.GetUniqueId()
    )
    assert error.diagnostic["failedEntry"]["GetClipProperty"]["value"] == {"Usage": "1"}
else:
    raise AssertionError("unmapped pathless pool entry must retain diagnostic metadata")

result, calls, project = exercise()
assert result and calls == [
    "ImportMedia",
    "CreateEmptyTimeline",
    "SetCurrentTimeline",
    "AppendToTimeline",
    "SaveProject",
], (result, calls)
assert len(project.timelines[-1].items) == 1
assert [t.uid for t in project.timelines[:3]] == [
    probe.MATRIX_PARTIAL_ID,
    probe.BASELINE_ID,
    probe.R1_ID,
]

for mode in (
    "empty",
    "multiple",
    "dedup",
    "collision",
    "wrong-path",
    "wrong-hash",
    "unmapped-pool-entry",
):
    result, calls, project = exercise(mode)
    assert (
        not isinstance(result, dict)
        and "CreateEmptyTimeline" not in calls
        and "AppendToTimeline" not in calls
        and "SaveProject" not in calls
    ), (mode, result, calls)
result, calls, _ = exercise("mutate-old")
assert not isinstance(result, dict) and "SaveProject" not in calls
for kwargs in ({"changed_checkpoint": True}, {"changed_project": True}):
    result, calls, _ = exercise(**kwargs)
    assert not isinstance(result, dict) and not calls
print("R4 fake acceptance passed (no live Resolve evidence)")
