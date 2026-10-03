"""Fake-only checks for the bounded R1-razor state restoration."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "editorial_restore", HERE / "editorial-restore.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Store:
    def __init__(self, mode):
        self.mode = mode
        self.state = {
            "projectId": module.PROJECT_ID,
            "projectName": "VERA Issue 141 Synthetic Probe fake",
            "GetSettings": {"value": {"frameRate": "25"}},
            "timelines": [
                {
                    "GetUniqueId": {"value": uid},
                    "GetName": {"value": name},
                    "GetStartFrame": {"value": 0},
                    "tracks": [],
                }
                for uid, name in (
                    (module.MATRIX_UID, module.MATRIX_NAME),
                    (
                        "64de8a4c-86bd-4f19-9d20-47b8940f610b",
                        "VERA 141 R4 availability",
                    ),
                    (module.BASELINE_UID, "VERA 141 Baseline"),
                    (module.R1_UID, "VERA 141 R1 identity"),
                )
            ],
        }
        matrix = self.matrix()
        for kind, index, locked in (
            ("video", 1, False),
            ("video", 2, True),
            ("video", 3, True),
            ("audio", 1, False),
            ("audio", 2, True),
            ("audio", 3, True),
        ):
            matrix["tracks"].append(
                {
                    "type": kind,
                    "index": index,
                    "GetIsTrackLocked": {"value": locked},
                    "items": [],
                }
            )
        self.pool = {"items": [{"uid": "source", "sourceBytes": {"hashMatches": True}}]}
        self.playhead = "00:01:04:00"
        self.calls = []

    def matrix(self):
        return next(
            row
            for row in self.state["timelines"]
            if row["GetUniqueId"]["value"] == module.MATRIX_UID
        )


class Timeline:
    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return module.MATRIX_UID

    def GetCurrentTimecode(self):
        return self.store.playhead

    def SetCurrentTimecode(self, value):
        self.store.calls.append(("SetCurrentTimecode", value))
        self.store.playhead = value
        if self.store.mode == "drift":
            self.store.matrix()["GetStartFrame"]["value"] = 1
        return True

    def GetIsTrackLocked(self, kind, index):
        return next(
            row
            for row in self.store.matrix()["tracks"]
            if row["type"] == kind and row["index"] == index
        )["GetIsTrackLocked"]["value"]

    def SetTrackLock(self, kind, index, locked):
        self.store.calls.append(("SetTrackLock", kind, index, locked))
        if self.store.mode == "setter-false" and len(self.store.calls) == 2:
            return False
        row = next(
            row
            for row in self.store.matrix()["tracks"]
            if row["type"] == kind and row["index"] == index
        )
        row["GetIsTrackLocked"]["value"] = locked
        if self.store.mode == "drift" and len(self.store.calls) == 5:
            self.store.matrix()["GetStartFrame"]["value"] = 1
        return True


class Project:
    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return module.PROJECT_ID

    def GetName(self):
        return self.store.state["projectName"]

    def IsRenderingInProgress(self):
        return False

    def GetCurrentTimeline(self):
        return Timeline(self.store)

    def GetTimelineCount(self):
        return 4

    def GetTimelineByIndex(self, index):
        row = self.store.state["timelines"][index - 1]
        if row["GetUniqueId"]["value"] == module.MATRIX_UID:
            return Timeline(self.store)
        return OtherTimeline(row)

    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mov", "codec": "H264"}

    def GetRenderJobList(self):
        return []


class OtherTimeline:
    def __init__(self, row):
        self.row = row

    def GetUniqueId(self):
        return self.row["GetUniqueId"]["value"]

    def GetName(self):
        return self.row["GetName"]["value"]


def run_case(mode):
    with tempfile.TemporaryDirectory(prefix="editorial-restore-") as temp:
        root = Path(temp)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        media = root / "out" / "issue-141-media-fake"
        media.mkdir()
        module.SPLIT_PAIR = "split/pair.json"
        module.PREPARATION = "prepare/result.json"
        module._reader = lambda _probe: reader
        store = Store(mode)
        pool = deepcopy(store.pool)
        split_state = deepcopy(store.state)
        # The fake live state begins at the pinned post-split state.
        store.state = deepcopy(split_state)
        pair = {
            "selectedTimelineUid": module.MATRIX_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [split_state, deepcopy(split_state)],
            "poolPasses": [pool, deepcopy(pool)],
        }
        prepared = {
            "status": "prepared-for-editorial-selection",
            "noEditorialCommandDispatched": True,
            "originalLocks": dict(module.ORIGINAL_LOCKS),
            "originalPlayhead": "00:06:07:24",
            "split": {"timecode": "00:01:04:00"},
        }
        pair_path = output / module.SPLIT_PAIR
        pair_path.parent.mkdir()
        pair_path.write_text(json.dumps(pair))
        prep_path = output / module.PREPARATION
        prep_path.parent.mkdir()
        prep_path.write_text(json.dumps(prepared))
        def digest(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        module.SPLIT_PAIR_SHA = digest(pair_path)
        module.PREPARATION_SHA = digest(prep_path)

        project = Project(store)
        resolve = SimpleNamespace(
            GetProductName=lambda: "DaVinci Resolve Studio",
            GetVersion=lambda: module.BUILD,
            GetCurrentPage=lambda: "edit",
            GetProjectManager=lambda: SimpleNamespace(
                GetCurrentProject=lambda: project
            ),
        )
        probe = SimpleNamespace(ROOT=root, sha256=digest)

        def timeline(state, uid):
            rows = [
                row
                for row in state["timelines"]
                if row["GetUniqueId"]["value"] == uid
            ]
            if len(rows) != 1:
                raise RuntimeError("timeline missing or duplicated")
            return rows[0]

        reader = SimpleNamespace(
            PROJECT_ID=module.PROJECT_ID,
            BUILD=module.BUILD,
            MATRIX_UID=module.MATRIX_UID,
            MATRIX_NAME=module.MATRIX_NAME,
            R4_UID="64de8a4c-86bd-4f19-9d20-47b8940f610b",
            R4_NAME="VERA 141 R4 availability",
            _manifest=lambda _config, _root, _probe: (media, {"synthetic": "hash"}),
            _pin=lambda path, name, sha, check_probe: (
                json.loads(path.read_text())
                if path.name == name and digest(path) == sha
                else (_ for _ in ()).throw(RuntimeError("bad pin"))
            ),
            _equal_pair=lambda values, _probe, _label: values[0]
            if len(values) == 2 and values[0] == values[1]
            else (_ for _ in ()).throw(RuntimeError("bad equal pair")),
            _validate_read_pair=lambda pair_value, _probe: (
                (pair_value["timelinePasses"][0], pair_value["poolPasses"][0])
                if pair_value.get("timelineConsistency") == "equal-adjacent-reads"
                and pair_value.get("poolConsistency") == "equal-adjacent-reads"
                and pair_value["timelinePasses"][0] == pair_value["timelinePasses"][1]
                and pair_value["poolPasses"][0] == pair_value["poolPasses"][1]
                else (_ for _ in ()).throw(RuntimeError("inconsistent pair"))
            ),
            _timeline=timeline,
            _context=lambda _resolve, _config, _identity, _probe, selected_uid: (
                project
                if project.GetCurrentTimeline().GetUniqueId() == selected_uid
                else (_ for _ in ()).throw(RuntimeError("selection changed"))
            ),
            _read_pair=lambda *_args: {
                "selectedTimelineUid": module.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [deepcopy(store.state), deepcopy(store.state)],
                "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
            },
            _write=lambda path, value: path.write_text(json.dumps(value)),
        )
        config = {
            "action": "editorial-restore",
            "externalScriptingSetting": "None",
            "projectName": store.state["projectName"],
            "outputDir": str(output),
            "mediaDir": str(media),
        }
        result = module.run(resolve, config, probe=probe)
        return result, store


def demo():
    result, store = run_case("success")
    assert result["status"] == "restored-unsaved", result
    assert result["setters"] == ["SetTrackLock"] * 4 + ["SetCurrentTimecode"]
    assert store.calls == [
        ("SetTrackLock", "video", 2, False),
        ("SetTrackLock", "video", 3, False),
        ("SetTrackLock", "audio", 2, False),
        ("SetTrackLock", "audio", 3, False),
        ("SetCurrentTimecode", "00:06:07:24"),
    ]

    result, store = run_case("drift")
    assert result["status"] == "refused-partial-state-retained", result
    assert result["failure"] == "Full postflight differs from the bounded restoration"
    assert len(store.calls) == 5

    result, store = run_case("setter-false")
    assert result["status"] == "refused-partial-state-retained", result
    assert "SetTrackLock did not return true" in result["failure"]
    assert len(store.calls) == 2
    print("Editorial restoration fake checks passed; no native application launched.")


if __name__ == "__main__":
    demo()
