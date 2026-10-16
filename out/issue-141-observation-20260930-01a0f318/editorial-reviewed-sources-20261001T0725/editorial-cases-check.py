"""Fake-only R1-trim preparation, pin refusal, and drift checks."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "editorial_cases", HERE / "editorial-cases.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

R2_UIDS = {
    "video": "485076d1-5bdc-4136-8628-3b2aaa955c25",
    "audio": "c6280b39-7618-4136-81e3-17c855866c84",
}


class Store:
    def __init__(self, mode, case):
        self.mode = mode
        self.case = case
        self.playhead = "00:06:07:24"
        self.page = "edit"
        self.phase_mode = "success"
        self.calls = []
        self.project_name = "VERA Issue 141 Synthetic Probe fake"
        self.state = {
            "projectId": module.PROJECT_ID,
            "projectName": self.project_name,
            "GetSettings": {"value": {"timelineFrameRate": 25}},
            "timelines": [],
        }
        for uid, name in (
            (module.MATRIX_UID, module.MATRIX_NAME),
            (module.R4_UID, module.R4_NAME),
            (module.BASELINE_UID, "VERA 141 Baseline"),
            (module.R1_UID, "VERA 141 R1 identity"),
        ):
            self.state["timelines"].append(
                {
                    "GetUniqueId": {"value": uid},
                    "GetName": {"value": name},
                    "GetStartFrame": {"value": 0},
                    "GetEndFrame": {"value": 10000},
                    "GetSettings": {"value": {"timelineFrameRate": 25}},
                    "tracks": [],
                }
            )
        matrix = self.matrix_state()
        for kind, index in module.ALL_LOCKS:
            items = []
            if (kind, index) == ("video", 1):
                items = [self.item("video", "base.mov", "v-uid", "a-uid", case)]
            elif (kind, index) == ("audio", 1):
                items = [self.item("audio", "repeated.wav", "a-uid", "v-uid", case)]
            matrix["tracks"].append(
                {
                    "type": kind,
                    "index": index,
                    "GetIsTrackLocked": {"value": False},
                    "items": items,
                }
            )
        self.pool = {"items": [{"uid": "pool", "sourceBytes": {"hashMatches": True}}]}
        if case == "R2-linked":
            self.pool["items"] = [
                {
                    "uid": f"pool-{filename}",
                    "evidence": {
                        "GetClipProperty": {"value": {"Usage": "4"}},
                        "sourceBytes": {"hashMatches": True},
                    },
                }
                for filename in ("base.mov", "repeated.wav")
            ]

    def item(self, kind, filename, uid, linked, case):
        spec = module.CASES[case]
        if case == "R2-linked":
            uid = R2_UIDS[kind]
            linked = R2_UIDS["audio" if kind == "video" else "video"]
        return {
            "GetUniqueId": {"value": uid},
            "GetStart": {"value": spec["start"]},
            "GetEnd": {"value": spec["end"]},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {"value": 199},
            "GetLinkedItems": [{"value": linked}],
            "GetMarkers": {
                "value": {
                    "0": {
                        "customData": json.dumps(
                            {"issue": 141, "occurrence": 1, "section": case}
                        )
                    }
                }
            },
            "GetMediaPoolItem": {
                "GetUniqueId": {"value": f"pool-{filename}"},
                "GetClipProperty": {"value": {"File Name": filename}},
            },
        }

    def matrix_state(self):
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

    def SetCurrentTimecode(self, tc):
        self.store.calls.append(("SetCurrentTimecode", tc))
        self.store.playhead = tc
        return True

    def GetIsTrackLocked(self, kind, index):
        return next(
            row
            for row in self.store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == index
        )["GetIsTrackLocked"]["value"]

    def SetTrackLock(self, kind, index, locked):
        self.store.calls.append(("SetTrackLock", kind, index, locked))
        track = next(
            row
            for row in self.store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == index
        )
        if self.store.mode == "setter-false" and len(self.store.calls) == 2:
            return False
        track["GetIsTrackLocked"]["value"] = locked
        if self.store.mode == "drift" and len(self.store.calls) == 4:
            self.store.matrix_state()["GetEndFrame"]["value"] += 1
        return True

    def GetItemListInTrack(self, kind, index):
        track = next(
            row
            for row in self.store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == index
        )
        return [TimelineItem(self.store, item) for item in track["items"]]

    def DeleteClips(self, handles, ripple):
        self.store.calls.append(
            ("DeleteClips", [handle.GetUniqueId() for handle in handles], ripple)
        )
        if self.store.phase_mode == "delete-false":
            return False
        for handle in handles:
            for track in self.store.matrix_state()["tracks"]:
                track["items"] = [
                    item
                    for item in track["items"]
                    if item["GetUniqueId"]["value"] != handle.GetUniqueId()
                ]
            source_uid = handle.GetMediaPoolItem().GetUniqueId()
            source = next(
                row for row in self.store.pool["items"] if row["uid"] == source_uid
            )
            props = source["evidence"]["GetClipProperty"]["value"]
            props["Usage"] = str(int(props["Usage"]) - 1)
        return True


class TimelineItem:
    def __init__(self, store, row):
        self.store = store
        self.row = row

    def GetUniqueId(self):
        return self.row["GetUniqueId"]["value"]

    def GetMediaPoolItem(self):
        return MediaPoolItem(self.row["GetMediaPoolItem"]["GetUniqueId"]["value"])


class MediaPoolItem:
    def __init__(self, uid):
        self.uid = uid

    def GetUniqueId(self):
        return self.uid


class OtherTimeline:
    def __init__(self, row):
        self.row = row

    def GetUniqueId(self):
        return self.row["GetUniqueId"]["value"]

    def GetName(self):
        return self.row["GetName"]["value"]


class Project:
    def __init__(self, store):
        self.store = store

    def GetUniqueId(self):
        return module.PROJECT_ID

    def GetName(self):
        return self.store.project_name

    def IsRenderingInProgress(self):
        return False

    def GetTimelineCount(self):
        return len(self.store.state["timelines"])

    def GetTimelineByIndex(self, index):
        row = self.store.state["timelines"][index - 1]
        if row["GetUniqueId"]["value"] == module.MATRIX_UID:
            return Timeline(self.store)
        return OtherTimeline(row)

    def GetCurrentTimeline(self):
        return Timeline(self.store)

    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mov", "codec": "H264"}

    def GetRenderJobList(self):
        return []


def open_page(store, page):
    store.calls.append(("OpenPage", page))
    if store.phase_mode == "page-failure":
        return False
    store.page = page
    return True


def run_case(
    case="R1-trim",
    mode="success",
    *,
    wrong_pin=False,
    wrong_case=False,
    wrong_restore_target=False,
    restore_move=False,
    paste_test=False,
    deliver_page=False,
    page_failure=False,
    r2_phases=False,
    phase_mode="success",
):
    with tempfile.TemporaryDirectory(prefix="editorial-cases-") as temp:
        root = Path(temp)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        media = root / "out" / "issue-141-media-fake"
        media.mkdir()
        store = Store(mode, case)
        if deliver_page:
            store.page = "deliver"
        if page_failure:
            store.phase_mode = "page-failure"
        else:
            store.phase_mode = phase_mode
        pin_state = deepcopy(store.state)
        pair = {
            "selectedTimelineUid": module.MATRIX_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [pin_state, deepcopy(pin_state)],
            "poolPasses": [store.pool, deepcopy(store.pool)],
        }
        pin_path = output / "pin.json"
        pin_path.write_text(json.dumps(pair))

        def digest(path):
            return hashlib.sha256(Path(path).read_bytes()).hexdigest()

        project = Project(store)
        resolve = SimpleNamespace(
            GetProductName=lambda: "DaVinci Resolve Studio",
            GetVersion=lambda: module.BUILD,
            GetCurrentPage=lambda: store.page,
            OpenPage=lambda page: open_page(store, page),
            GetProjectManager=lambda: SimpleNamespace(
                GetCurrentProject=lambda: project
            ),
        )
        probe = SimpleNamespace(ROOT=root, sha256=digest)

        def timeline(state, uid):
            rows = [
                row for row in state["timelines"] if row["GetUniqueId"]["value"] == uid
            ]
            if len(rows) != 1:
                raise RuntimeError("timeline missing or duplicated")
            return rows[0]

        def read_pair(*_args):
            current = deepcopy(store.state)
            return {
                "selectedTimelineUid": module.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [current, deepcopy(current)],
                "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
            }

        reader = SimpleNamespace(
            _manifest=lambda *_args: (media, {"synthetic": "hash"}),
            _pin=lambda path, name, sha, _probe: (
                json.loads(path.read_text())
                if path.name == name and digest(path) == sha
                else (_ for _ in ()).throw(RuntimeError("pinned evidence changed"))
            ),
            _validate_read_pair=lambda value, _probe: (
                (value["timelinePasses"][0], value["poolPasses"][0])
                if value["timelinePasses"][0] == value["timelinePasses"][1]
                and value["poolPasses"][0] == value["poolPasses"][1]
                else (_ for _ in ()).throw(RuntimeError("inconsistent pair"))
            ),
            _timeline=timeline,
            _context=lambda _resolve, _config, _identity, _probe, uid: (
                project
                if project.GetCurrentTimeline().GetUniqueId() == uid
                else (_ for _ in ()).throw(RuntimeError("selection changed"))
            ),
            _read_pair=read_pair,
            _write=lambda path, value: path.write_text(json.dumps(value)),
        )
        config = {
            "action": "editorial-case-prepare",
            "case": "R1-move" if wrong_case else case,
            "externalScriptingSetting": "None",
            "projectName": store.project_name,
            "outputDir": str(output),
            "mediaDir": str(media),
            "priorPair": "pin.json",
            "priorPairSha256": "wrong" if wrong_pin else digest(pin_path),
        }
        try:
            result = module.prepare(resolve, config, probe=probe, reader=reader)
        except RuntimeError as error:
            if not (wrong_pin or wrong_case):
                raise
            return {"status": "refused-before-setters", "failure": str(error)}, store
        if r2_phases:
            assert case == "R2-linked"

            def write_pair(name):
                path = output / name
                current = deepcopy(store.state)
                value = {
                    "selectedTimelineUid": module.MATRIX_UID,
                    "timelineConsistency": "equal-adjacent-reads",
                    "poolConsistency": "equal-adjacent-reads",
                    "timelinePasses": [current, deepcopy(current)],
                    "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
                }
                path.write_text(json.dumps(value))
                return name, digest(path)

            def set_range(item, start, end, source_start, source_end):
                item["GetStart"]["value"] = start
                item["GetEnd"]["value"] = end
                item["GetSourceStartFrame"]["value"] = source_start
                item["GetSourceEndFrame"]["value"] = source_end

            target_uids = result["target"]["uids"]
            first_new = {"video": "first-video-right", "audio": "first-audio-right"}
            for kind, uid in target_uids.items():
                track = next(
                    row
                    for row in store.matrix_state()["tracks"]
                    if row["type"] == kind and row["index"] == 1
                )
                original = next(
                    item
                    for item in track["items"]
                    if item["GetUniqueId"]["value"] == uid
                )
                left, right = deepcopy(original), deepcopy(original)
                set_range(left, 2500, 2560, 0, 60)
                right["GetUniqueId"] = {"value": first_new[kind]}
                set_range(right, 2560, 2699, 60, 199)
                right["GetLinkedItems"] = [
                    {"value": first_new["audio" if kind == "video" else "video"]}
                ]
                track["items"] = [
                    item for item in track["items"] if item is not original
                ] + [left, right]
                track["items"].sort(
                    key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True)
                )
            for row in store.pool["items"]:
                props = row["evidence"]["GetClipProperty"]["value"]
                props["Usage"] = str(int(props["Usage"]) + 1)
            first_ref = write_pair("first-split.json")
            if phase_mode == "first-full-state-drift":
                store.matrix_state()["GetEndFrame"]["value"] += 1
                first_ref = write_pair("first-drift.json")
            prep_path = Path(result["directory"]) / "result.json"
            phase_config = {
                **config,
                "case": "R2-linked",
                "preparationResult": str(prep_path.relative_to(output)),
                "preparationResultSha256": digest(prep_path),
                "firstSplitPair": first_ref[0],
                "firstSplitPairSha256": first_ref[1],
            }
            if phase_mode == "wrong-first-source":
                store.matrix_state()["tracks"][0]["items"][0]["GetMediaPoolItem"][
                    "GetUniqueId"
                ]["value"] = "wrong-source"
                first_ref = write_pair("wrong-source-first.json")
                phase_config.update(
                    firstSplitPair=first_ref[0], firstSplitPairSha256=first_ref[1]
                )
            try:
                positioned = module.second_position(
                    resolve, phase_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if phase_mode not in {"wrong-first-source", "first-full-state-drift"}:
                    raise
                return {"prepare": result, "position_refusal": str(error)}, store
            if positioned["status"] != "second-position-ready":
                return {
                    "prepare": result,
                    "position_refusal": positioned["failure"],
                }, store
            position_path = Path(positioned["directory"]) / "result.json"
            phase_config.update(
                secondPositionResult=str(position_path.relative_to(output)),
                secondPositionResultSha256=digest(position_path),
            )
            second_new = {"video": "second-video-right", "audio": "second-audio-right"}
            for kind, first_uid in first_new.items():
                track = next(
                    row
                    for row in store.matrix_state()["tracks"]
                    if row["type"] == kind and row["index"] == 1
                )
                right = next(
                    item
                    for item in track["items"]
                    if item["GetUniqueId"]["value"] == first_uid
                )
                middle, tail = deepcopy(right), deepcopy(right)
                set_range(middle, 2560, 2570, 60, 70)
                tail["GetUniqueId"] = {"value": second_new[kind]}
                set_range(tail, 2570, 2699, 70, 199)
                tail["GetLinkedItems"] = [
                    {"value": second_new["audio" if kind == "video" else "video"]}
                ]
                track["items"] = [
                    item for item in track["items"] if item is not right
                ] + [middle, tail]
                track["items"].sort(
                    key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True)
                )
            for row in store.pool["items"]:
                props = row["evidence"]["GetClipProperty"]["value"]
                props["Usage"] = str(int(props["Usage"]) + 1)
            if phase_mode == "wrong-second-interval":
                for track in store.matrix_state()["tracks"]:
                    for item in track["items"]:
                        if item["GetUniqueId"]["value"] in first_new.values():
                            item["GetEnd"]["value"] = 2569
                            item["GetSourceEndFrame"]["value"] = 69
            if phase_mode == "second-full-state-drift":
                store.matrix_state()["GetName"]["value"] = "drift"
            if phase_mode == "wrong-interval-playhead":
                store.playhead = "00:01:42:19"
            second_ref = write_pair("second-split.json")
            phase_config.update(
                secondSplitPair=second_ref[0], secondSplitPairSha256=second_ref[1]
            )
            try:
                deleted = module.interval_delete(
                    resolve, phase_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if phase_mode not in {
                    "wrong-second-interval",
                    "second-full-state-drift",
                    "wrong-interval-playhead",
                }:
                    raise
                return {
                    "prepare": result,
                    "position": positioned,
                    "delete_refusal": str(error),
                }, store
            if phase_mode == "delete-false":
                assert deleted["status"] == "interval-delete-review-required", deleted
                assert deleted["deleteReturn"] is False
                return {
                    "prepare": result,
                    "position": positioned,
                    "delete": deleted,
                }, store
            if deleted["status"] != "interval-deleted-unsaved":
                return {
                    "prepare": result,
                    "position": positioned,
                    "delete": deleted,
                }, store
            post_path = Path(deleted["directory"]) / "after.json"
            restore_config = {
                **phase_config,
                "action": "editorial-case-restore",
                "postEditPair": str(post_path.relative_to(output)),
                "postEditPairSha256": digest(post_path),
            }
            restored = module.restore(
                resolve, restore_config, probe=probe, reader=reader
            )
            return (result, positioned, deleted, restored), store
        if paste_test:
            assert result["status"] == "case-prepared", result
            store.playhead = result["target"]["selectionTimecode"]
            copy_pair = {
                "selectedTimelineUid": module.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [deepcopy(store.state), deepcopy(store.state)],
                "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
            }
            copy_path = output / "post-copy.json"
            copy_path.write_text(json.dumps(copy_pair))
            selected_pair_path = output / "selected-pair.json"
            selected_pair_path.write_bytes(copy_path.read_bytes())
            selected_items = []
            for track in store.matrix_state()["tracks"]:
                for item in track["items"]:
                    if (
                        item["GetUniqueId"]["value"]
                        in result["target"]["uids"].values()
                    ):
                        selected_items.append(
                            {
                                "GetUniqueId": item["GetUniqueId"],
                                "GetLinkedItems": item["GetLinkedItems"],
                                "GetMediaPoolItem": item["GetMediaPoolItem"],
                            }
                        )
            if mode == "wrong-selection":
                selected_items[0]["GetUniqueId"] = {"value": "wrong"}
            selection = {
                "status": "editorial-readback-retained",
                "label": "r1-copy-selected",
                "readOnly": True,
                "failure": None,
                "pair": {
                    "path": str(selected_pair_path),
                    "sha256": digest(selected_pair_path),
                },
                "selectionShapes": [
                    {"type": "list", "count": 2},
                    {"type": "list", "count": 2},
                ],
                "selectionPasses": [
                    {
                        "playhead": "00:01:24:00",
                        "items": selected_items,
                    },
                    {
                        "playhead": "00:01:24:00",
                        "items": deepcopy(selected_items),
                    },
                ],
            }
            selection_path = output / "selection.json"
            selection_path.write_text(json.dumps(selection))
            paste_config = {
                **config,
                "action": "editorial-copy-paste-position",
                "preparationResult": str(
                    Path(result["directory"]).relative_to(output) / "result.json"
                ),
                "preparationResultSha256": digest(
                    Path(result["directory"]) / "result.json"
                ),
                "postCopyPair": "post-copy.json",
                "postCopyPairSha256": digest(copy_path),
                "selectionResult": "selection.json",
                "selectionResultSha256": digest(selection_path),
            }
            try:
                positioned = module.paste_position(
                    resolve, paste_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if mode != "wrong-selection":
                    raise
                return {"prepare": result, "position": str(error)}, store
            if not restore_move:
                return {"prepare": result, "position": positioned}, store
            post_path = output / "post-paste.json"
            post_path.write_text(
                json.dumps(
                    {
                        **copy_pair,
                        "timelinePasses": [
                            deepcopy(store.state),
                            deepcopy(store.state),
                        ],
                    }
                )
            )
            restore_config = {
                **paste_config,
                "action": "editorial-case-restore",
                "postEditPair": "post-paste.json",
                "postEditPairSha256": digest(post_path),
            }
            restored = module.restore(
                resolve, restore_config, probe=probe, reader=reader
            )
            return {
                "prepare": result,
                "position": positioned,
                "restore": restored,
            }, store
        if restore_move:
            assert result["status"] == "case-prepared", result
            target_key = (
                "splitPlayheadTimecode" if case == "R2-linked" else "selectionTimecode"
            )
            store.playhead = result["target"][target_key]
            for track in store.matrix_state()["tracks"]:
                for item in track["items"]:
                    if (
                        item["GetUniqueId"]["value"]
                        in result["target"]["uids"].values()
                    ):
                        item["GetStart"]["value"] += 25
                        item["GetEnd"]["value"] += 25
            edited_pair = {
                "selectedTimelineUid": module.MATRIX_UID,
                "timelineConsistency": "equal-adjacent-reads",
                "poolConsistency": "equal-adjacent-reads",
                "timelinePasses": [deepcopy(store.state), deepcopy(store.state)],
                "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
            }
            post_path = output / "post-edit.json"
            post_path.write_text(json.dumps(edited_pair))
            prep_path = Path(result["directory"]) / "result.json"
            if wrong_restore_target:
                preparation = json.loads(prep_path.read_text())
                preparation["target"][target_key] = "00:09:59:24"
                prep_path.write_text(json.dumps(preparation))
            restore_config = {
                **config,
                "action": "editorial-case-restore",
                "preparationResult": str(prep_path.relative_to(output)),
                "preparationResultSha256": digest(prep_path),
                "postEditPair": "post-edit.json",
                "postEditPairSha256": digest(post_path),
            }
            try:
                restored = module.restore(
                    resolve, restore_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if not wrong_restore_target:
                    raise
                return {"prepare": result, "restore_refusal": str(error)}, store
            return (result, restored), store
        return result, store


def demo():
    result, store = run_case()
    assert result["status"] == "case-prepared", result
    assert result["target"]["uids"] == {"video": "v-uid", "audio": "a-uid"}
    assert result["target"]["endFrame"] == 699
    assert result["target"]["trimPlayheadFrame"] == 674
    assert result["target"]["trimPlayheadTimecode"] == "00:00:26:24"
    assert store.calls == [
        ("SetTrackLock", "video", 2, True),
        ("SetTrackLock", "video", 3, True),
        ("SetTrackLock", "audio", 2, True),
        ("SetTrackLock", "audio", 3, True),
        ("SetCurrentTimecode", "00:00:26:24"),
    ]

    result, store = run_case(wrong_pin=True)
    assert result["status"] == "refused-before-setters"
    assert store.calls == []

    result, store = run_case(deliver_page=True, page_failure=True)
    assert result["status"] == "refused-partial-state-retained", result
    assert store.calls == [("OpenPage", "edit")]
    assert store.page == "deliver"

    result, store = run_case("R1-copy", deliver_page=True)
    assert result["status"] == "case-prepared", result
    assert result["originalPage"] == "deliver"
    assert store.calls[0] == ("OpenPage", "edit")
    assert store.calls.count(("OpenPage", "edit")) == 1

    (prepared, positioned, deleted, restored), store = run_case(
        "R2-linked", r2_phases=True, deliver_page=True
    )
    assert prepared["status"] == "case-prepared", prepared
    assert prepared["originalPage"] == "deliver"
    assert positioned["status"] == "second-position-ready", positioned
    assert positioned["target"]["timecode"] == "00:01:42:20"
    assert deleted["status"] == "interval-deleted-unsaved", deleted
    assert deleted["intervalUids"] == {
        "video": "first-video-right",
        "audio": "first-audio-right",
    }
    assert deleted["interval"] == {
        "recordStart": 2560,
        "recordEndRaw": 2570,
        "sourceStart": 60,
        "sourceEndRaw": 70,
    }
    assert [call[0] for call in store.calls].count("DeleteClips") == 1
    assert next(call for call in store.calls if call[0] == "DeleteClips") == (
        "DeleteClips",
        ["first-video-right", "first-audio-right"],
        False,
    )
    assert restored["status"] == "restored-unsaved", restored
    assert store.playhead == "00:06:07:24"
    assert store.page == "edit"

    for phase_mode, message in (
        ("wrong-first-source", "child ranges"),
        ("first-full-state-drift", "unrelated full state"),
        ("wrong-second-interval", "child ranges"),
        ("second-full-state-drift", "project inventory changed"),
        ("wrong-interval-playhead", "playhead differs"),
    ):
        result, store = run_case("R2-linked", r2_phases=True, phase_mode=phase_mode)
        assert message in result.get(
            "position_refusal", result.get("delete_refusal", "")
        ), result
        assert not any(call[0] == "DeleteClips" for call in store.calls)

    result, store = run_case("R2-linked", r2_phases=True, phase_mode="delete-false")
    assert result["delete"]["deleteReturn"] is False
    assert result["delete"]["status"] == "interval-delete-review-required"
    assert len([call for call in store.calls if call[0] == "DeleteClips"]) == 1

    result, store = run_case("R2-linked", wrong_case=True)
    assert result["status"] == "refused-before-setters"
    assert store.calls == []

    (prepared, restored), store = run_case("R2-linked", restore_move=True)
    assert prepared["status"] == "case-prepared", prepared
    assert prepared["target"]["uids"] == {
        "video": "485076d1-5bdc-4136-8628-3b2aaa955c25",
        "audio": "c6280b39-7618-4136-81e3-17c855866c84",
    }
    assert prepared["target"]["startFrame"] == 2500
    assert prepared["target"]["endFrame"] == 2699
    assert prepared["target"]["splitPlayheadFrame"] == 2560
    assert prepared["target"]["splitPlayheadTimecode"] == "00:01:42:10"
    assert store.calls[:5] == [
        ("SetTrackLock", "video", 2, True),
        ("SetTrackLock", "video", 3, True),
        ("SetTrackLock", "audio", 2, True),
        ("SetTrackLock", "audio", 3, True),
        ("SetCurrentTimecode", "00:01:42:10"),
    ]
    assert restored["status"] == "restored-unsaved", restored
    assert store.playhead == "00:06:07:24"
    assert all(
        track["GetIsTrackLocked"]["value"] is False
        for track in store.matrix_state()["tracks"]
    )

    result, store = run_case("R2-linked", restore_move=True, wrong_restore_target=True)
    assert result["restore_refusal"].startswith("Fresh post-edit state/source/playhead")
    assert len(store.calls) == 5

    result, store = run_case(mode="drift")
    assert result["status"] == "refused-partial-state-retained", result
    assert (
        result["failure"] == "Full postflight differs from the bounded case operation"
    )
    assert len(store.calls) == 5

    (prepared, restored), store = run_case("R1-move", restore_move=True)
    assert prepared["status"] == "case-prepared", prepared
    assert prepared["target"]["uids"] == {"video": "v-uid", "audio": "a-uid"}
    assert prepared["target"]["startFrame"] == 1000
    assert prepared["target"]["endFrame"] == 1199
    assert prepared["target"]["selectionFrame"] == 1100
    assert prepared["target"]["selectionTimecode"] == "00:00:44:00"
    assert restored["status"] == "restored-unsaved", restored
    assert store.playhead == "00:06:07:24"
    assert all(
        track["GetIsTrackLocked"]["value"] is False
        for track in store.matrix_state()["tracks"]
    )
    assert [
        (item["GetStart"]["value"], item["GetEnd"]["value"])
        for track in store.matrix_state()["tracks"]
        for item in track["items"]
    ] == [(1025, 1224), (1025, 1224)]

    copy, store = run_case("R1-copy", paste_test=True, restore_move=True)
    assert copy["prepare"]["status"] == "case-prepared", copy
    assert copy["prepare"]["target"]["uids"] == {
        "video": "v-uid",
        "audio": "a-uid",
    }
    assert copy["prepare"]["target"]["startFrame"] == 2000
    assert copy["prepare"]["target"]["endFrame"] == 2199
    assert copy["prepare"]["target"]["selectionTimecode"] == "00:01:24:00"
    assert copy["position"]["status"] == "paste-position-ready", copy
    assert copy["position"]["pasteRange"] == {
        "startFrame": 2250,
        "endFrame": 2449,
        "timecode": "00:01:30:00",
    }
    assert store.playhead == "00:06:07:24"
    assert copy["restore"]["status"] == "restored-unsaved", copy

    result, store = run_case("R1-copy", mode="wrong-selection", paste_test=True)
    assert result["prepare"]["status"] == "case-prepared", result
    assert "Selected clips are not the exact" in result["position"]
    assert len(store.calls) == 5
    print("R1 trim/move/copy and R2-linked fake checks passed; no native app launched.")


if __name__ == "__main__":
    demo()
