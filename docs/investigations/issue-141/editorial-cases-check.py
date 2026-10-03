"""Fake-only R1-trim preparation, pin refusal, and drift checks."""

import gzip
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
    "R2-linked": {
        "video": "485076d1-5bdc-4136-8628-3b2aaa955c25",
        "audio": "c6280b39-7618-4136-81e3-17c855866c84",
    },
    "R2-unlinked": {
        "video": "44bfdfa0-6aa6-40af-8916-679d557f18ee",
        "audio": "7c970634-6fcb-4117-9a51-221a482c7142",
    },
    "R2-picture": {
        "video": "381ff8e1-62dd-49c9-9745-7ad3984ee52a",
        "audio": "55229fb5-7478-47c9-984f-613cec35afb1",
    },
    "R2-partial": {
        "video": "ac20bfd7-e56d-4b0f-9ab5-7451fd9093fd",
        "audio": "d5d00807-e77d-4914-9b49-dd025ff5430d",
    },
    "R2-residual": {
        "video": "55ef1242-5a71-45e5-a1b4-d90300589de2",
        "audio": "09373858-39dd-474b-9eb8-56c5e523cc76",
    },
    "R3-Graphic": {
        "video": "70717d8e-6888-421b-825a-8e093beb2c45",
        "audio": "2e9c3451-1ed8-4e88-985d-ef5e7f3a070b",
    },
    "R3-boundary": {
        "video": "462ae76e-bf69-41be-b967-b70c163c0c1a",
        "audio": "b4f84273-a32c-48bd-acfe-7939fbbdc54b",
    },
    "R2-offset": {
        "video": "ccabcb9a-8e7d-462e-a8a1-4f6ce8c4f5f7",
        "audio": "f0b986dd-b580-42f9-a7f8-ba464cca7076",
    },
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
        if case in {"R3-boundary", "R3-boundary-A3"}:
            matrix["GetMarkers"] = {
                "value": {
                    "9000": {
                        "color": "Green",
                        "duration": 1,
                        "name": "141 R3-boundary",
                        "note": "Synthetic matrix case boundary",
                        "customData": json.dumps(
                            {"issue": 141, "section": "R3-boundary", "index": 18},
                            sort_keys=True,
                        ),
                    }
                }
            }
        for kind, index in module.ALL_LOCKS:
            items = []
            if (kind, index) == ("video", 1):
                items = [self.item("video", "base.mov", "v-uid", "a-uid", case)]
            elif (kind, index) == ("audio", 1):
                items = [self.item("audio", "repeated.wav", "a-uid", "v-uid", case)]
            elif (kind, index) == ("audio", 2) and case == "R2-residual":
                items = [self.layer_item("audio", "R2-residual", "residual-a2", False)]
            elif (kind, index) == ("video", 3) and case == "R3-Graphic":
                items = [self.layer_item("video", "R3-Graphic", "graphic-v3", False)]
            elif (kind, index) == ("video", 3) and case == "R3-boundary":
                items = [
                    self.layer_item("video", "R3-boundary-V3", "crossing-v3", False)
                ]
            elif (kind, index) == ("audio", 2) and case == "R3-boundary":
                items = [
                    self.layer_item("audio", "R3-boundary-A2", "crossing-a2", False)
                ]
            elif (kind, index) == ("audio", 3) and case in {
                "R3-boundary",
                "R3-boundary-A3",
            }:
                items = [self.layer_item("audio", "R3-boundary", "bed-a3", True)]
            matrix["tracks"].append(
                {
                    "type": kind,
                    "index": index,
                    "GetIsTrackEnabled": {"value": True},
                    "GetIsTrackLocked": {"value": False},
                    "items": items,
                }
            )
        self.pool = {"items": [{"uid": "pool", "sourceBytes": {"hashMatches": True}}]}
        if case in R2_UIDS:
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
        if case in {"R3-boundary", "R3-boundary-A3"}:
            self.pool["items"].append(
                {
                    "uid": "0438f3a0-b58f-4d6f-a36d-81e02cdeaf3f",
                    "evidence": {"GetClipProperty": {"value": {"Usage": "4"}}},
                    "sourceBytes": {"hashMatches": True},
                }
            )

    def item(self, kind, filename, uid, linked, case):
        spec = module.CASES[case]
        if case in R2_UIDS:
            uid = R2_UIDS[case][kind]
            linked = R2_UIDS[case]["audio" if kind == "video" else "video"]
        marker_case = module._marker_case(case)
        return {
            "GetUniqueId": {"value": uid},
            "GetStart": {"value": spec["start"]},
            "GetEnd": {"value": spec["end"]},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {"value": 199},
            "GetLinkedItems": [{"value": linked}],
            "GetSpeed": {"value": {"Percentage": 100.0, "PitchCorrection": True}},
            "GetMarkers": {
                "value": {
                    "0": {
                        "customData": json.dumps(
                            {"issue": 141, "occurrence": 1, "section": marker_case}
                        )
                    }
                }
            },
            "GetMediaPoolItem": {
                "GetUniqueId": {"value": f"pool-{filename}"},
                "GetClipProperty": {"value": {"File Name": filename, "Usage": "4"}},
            },
        }

    def layer_item(self, kind, marker, uid, enabled):
        specs = {
            "R2-residual": (4500, 4699, "pool-repeated.wav"),
            "R3-Graphic": (8575, 8700, "graphic-source"),
            "R3-boundary-V3": (9000, 9199, "graphic-source"),
            "R3-boundary-A2": (9000, 9199, "pool-repeated.wav"),
            "R3-boundary": (
                9000,
                9199,
                "0438f3a0-b58f-4d6f-a36d-81e02cdeaf3f",
            ),
        }
        start, end, source_uid = specs[marker]
        source_name = "bed.wav" if marker == "R3-boundary" else "layer.mov"
        return {
            "GetUniqueId": {"value": uid},
            "GetStart": {"value": start},
            "GetEnd": {"value": end},
            "GetSourceStartFrame": {"value": 0},
            "GetSourceEndFrame": {"value": 199},
            "GetLinkedItems": [],
            "GetClipEnabled": {"value": enabled},
            "GetMarkers": {
                "value": {
                    "0": {"customData": json.dumps({"issue": 141, "section": marker})}
                }
            },
            "GetMediaPoolItem": {
                "GetUniqueId": {"value": source_uid},
                "GetClipProperty": {
                    "value": {
                        "Clip Name": source_name,
                        "File Name": source_name,
                        "Usage": "4",
                    }
                },
            },
        }

    def matrix_state(self):
        return next(
            row
            for row in self.state["timelines"]
            if row["GetUniqueId"]["value"] == module.MATRIX_UID
        )

    def sync_usages(self):
        usage_by_uid = {
            row["uid"]: row["evidence"]["GetClipProperty"]["value"]["Usage"]
            for row in self.pool["items"]
            if "evidence" in row
        }
        for timeline in self.state["timelines"]:
            for track in timeline.get("tracks", []):
                for item in track.get("items", []):
                    source = item.get("GetMediaPoolItem", {})
                    uid = source.get("GetUniqueId", {}).get("value")
                    props = source.get("GetClipProperty", {}).get("value", {})
                    if uid in usage_by_uid and "Usage" in props:
                        props["Usage"] = usage_by_uid[uid]


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

    def GetMarkers(self):
        return {
            int(frame): value
            for frame, value in self.store.matrix_state()
            .get("GetMarkers", {})
            .get("value", {})
            .items()
        }

    def AddMarker(self, frame, color, name, note, duration, custom):
        self.store.calls.append(
            ("AddMarker", frame, color, name, note, duration, custom)
        )
        if self.store.mode == "marker-false":
            return False
        markers = self.store.matrix_state().setdefault("GetMarkers", {"value": {}})[
            "value"
        ]
        markers[str(frame)] = {
            "color": color,
            "duration": duration,
            "name": name,
            "note": note,
            "customData": custom,
        }
        if self.store.mode == "marker-drift":
            markers[str(frame)]["note"] = "unexpected"
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

    def SetClipsLinked(self, handles, linked):
        self.store.calls.append(
            ("SetClipsLinked", [handle.GetUniqueId() for handle in handles], linked)
        )
        if self.store.phase_mode == "unlink-false":
            return False
        for handle in handles:
            handle.row["GetLinkedItems"] = []
            if handle.GetUniqueId() == R2_UIDS[self.store.case]["video"]:
                del handle.row["GetSpeed"]["value"]["PitchCorrection"]
        return True


class TimelineItem:
    def __init__(self, store, row):
        self.store = store
        self.row = row

    def GetUniqueId(self):
        return self.row["GetUniqueId"]["value"]

    def GetMediaPoolItem(self):
        return MediaPoolItem(self.row["GetMediaPoolItem"]["GetUniqueId"]["value"])

    def GetLinkedItems(self):
        return self.row.get("GetLinkedItems", [])

    def GetClipEnabled(self):
        return self.row.get("GetClipEnabled", {}).get("value")

    def SetClipEnabled(self, enabled):
        self.store.calls.append(("SetClipEnabled", self.GetUniqueId(), enabled))
        if self.store.mode in {"clip-enable-false", "locked-clip-enable-false"}:
            return False
        if self.store.mode == "locked-layer-requires-unlock":
            track = next(
                row
                for row in self.store.matrix_state()["tracks"]
                if self.row in row["items"]
            )
            if track["GetIsTrackLocked"]["value"]:
                return False
        self.row["GetClipEnabled"] = {"value": enabled}
        if self.store.mode == "clip-enable-drift":
            self.row["GetClipEnabled"] = {"value": not enabled}
        return True


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
    named_sequence=False,
    held_context=False,
    review_preparation=False,
    review_drift=False,
):
    with tempfile.TemporaryDirectory(prefix="editorial-cases-") as temp:
        root = Path(temp)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        media = root / "out" / "issue-141-media-fake"
        media.mkdir()
        store = Store(mode, case)
        if mode in {"locked-layer-requires-unlock", "locked-clip-enable-false"}:
            layer_kind, layer_index = (
                ("audio", 2) if case == "R2-residual" else ("video", 3)
            )
            next(
                row
                for row in store.matrix_state()["tracks"]
                if row["type"] == layer_kind and row["index"] == layer_index
            )["GetIsTrackLocked"]["value"] = True
        if held_context:
            store.playhead = "00:01:30:00"
            for row in store.matrix_state()["tracks"]:
                if (row["type"], row["index"]) in module.LOCKS:
                    row["GetIsTrackLocked"]["value"] = True
        if mode == "wrong-primary-lock":
            next(
                row
                for row in store.matrix_state()["tracks"]
                if row["type"] == "video" and row["index"] == 1
            )["GetIsTrackLocked"]["value"] = True
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
            store.sync_usages()
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
            if not (
                wrong_pin
                or wrong_case
                or mode == "wrong-primary-lock"
                or (held_context and case.startswith("R1-"))
            ):
                raise
            return {"status": "refused-before-setters", "failure": str(error)}, store
        if review_preparation:
            refusal = deepcopy(result)
            refusal.update(
                status="refused-partial-state-retained",
                failure="Full postflight differs from the bounded case operation",
            )
            refusal_path = output / "partial-result.json"
            refusal_path.write_text(json.dumps(refusal))
            journal_path = Path(refusal["journal"])
            if review_drift:
                store.matrix_state()["GetSettings"]["value"]["timelineFrameRate"] = 24
            review_config = {
                **config,
                "action": "editorial-case-review-preparation",
                "partialResult": "partial-result.json",
                "partialResultSha256": digest(refusal_path),
                "journalSha256": digest(journal_path),
                "afterPairSha256": refusal["preparedPair"]["sha256"],
            }
            calls_before_review = deepcopy(store.calls)
            try:
                reviewed = module.review_preparation(
                    resolve, review_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                assert store.calls == calls_before_review
                if not review_drift:
                    raise
                return {"status": "review-refused", "failure": str(error)}, store
            assert not review_drift
            assert store.calls == calls_before_review
            return reviewed, store
        if named_sequence:
            return exercise_named_sequence(
                case,
                result,
                store,
                output,
                config,
                resolve,
                probe,
                reader,
                digest,
                phase_mode,
            ), store
        if r2_phases and case in module.R2_SINGLE and case != "R2-offset":
            case_spec = module.R2_SINGLE[case]
            target_kind = case_spec["track"]
            target_uid = result["target"]["uids"][target_kind]
            source_uid = result["target"]["sourceUids"][target_kind]
            start, end = module.CASES[case]["start"], module.CASES[case]["end"]
            cut_start, cut_end = case_spec["cutStart"], case_spec["cutEnd"]

            def write_pair(name):
                store.sync_usages()
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

            def set_range(item, item_start, item_end, source_start, source_end):
                item["GetStart"]["value"] = item_start
                item["GetEnd"]["value"] = item_end
                item["GetSourceStartFrame"]["value"] = source_start
                item["GetSourceEndFrame"]["value"] = source_end

            target_track = next(
                row
                for row in store.matrix_state()["tracks"]
                if row["type"] == target_kind and row["index"] == 1
            )
            parent = next(
                item
                for item in target_track["items"]
                if item["GetUniqueId"]["value"] == target_uid
            )
            first_right_uid = f"{case}-first-right"
            left, right = deepcopy(parent), deepcopy(parent)
            set_range(left, start, start + cut_start, 0, cut_start)
            if phase_mode == "wrong-first-range":
                left["GetEnd"]["value"] -= 1
            right["GetUniqueId"] = {"value": first_right_uid}
            set_range(right, start + cut_start, end, cut_start, 199)
            target_track["items"] = [
                item for item in target_track["items"] if item is not parent
            ] + [left, right]
            target_track["items"].sort(
                key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True)
            )
            source = next(
                row for row in store.pool["items"] if row["uid"] == source_uid
            )
            props = source["evidence"]["GetClipProperty"]["value"]
            props["Usage"] = str(int(props["Usage"]) + 1)
            if phase_mode == "untouched-track-change":
                untouched = "audio" if target_kind == "video" else "video"
                track = next(
                    row
                    for row in store.matrix_state()["tracks"]
                    if row["type"] == untouched and row["index"] == 1
                )
                track["items"][0]["GetEnd"]["value"] += 1
            first_ref = write_pair("single-first-split.json")
            prep_path = Path(result["directory"]) / "result.json"
            phase_config = {
                **config,
                "case": case,
                "preparationResult": str(prep_path.relative_to(output)),
                "preparationResultSha256": digest(prep_path),
                "firstSplitPair": first_ref[0],
                "firstSplitPairSha256": first_ref[1],
            }
            try:
                positioned = module.second_position(
                    resolve, phase_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if phase_mode not in {"untouched-track-change", "wrong-first-range"}:
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
            target_track = next(
                row
                for row in store.matrix_state()["tracks"]
                if row["type"] == target_kind and row["index"] == 1
            )
            first_right = next(
                item
                for item in target_track["items"]
                if item["GetUniqueId"]["value"] == first_right_uid
            )
            middle, tail = deepcopy(first_right), deepcopy(first_right)
            set_range(middle, start + cut_start, start + cut_end, cut_start, cut_end)
            tail["GetUniqueId"] = {"value": f"{case}-second-right"}
            set_range(tail, start + cut_end, end, cut_end, 199)
            target_track["items"] = [
                item for item in target_track["items"] if item is not first_right
            ] + [middle, tail]
            target_track["items"].sort(
                key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True)
            )
            props["Usage"] = str(int(props["Usage"]) + 1)
            if phase_mode == "wrong-second-range":
                middle["GetEnd"]["value"] -= 1
                middle["GetSourceEndFrame"]["value"] -= 1
            second_ref = write_pair("single-second-split.json")
            phase_config.update(
                secondSplitPair=second_ref[0], secondSplitPairSha256=second_ref[1]
            )
            try:
                deleted = module.interval_delete(
                    resolve, phase_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                if phase_mode not in {"wrong-second-range", "untouched-track-change"}:
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
        if r2_phases:
            assert case == "R2-linked"

            def write_pair(name):
                store.sync_usages()
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


def retained_boundary_source_check():
    pair_path = (
        Path(__file__).resolve().parents[3]
        / "out/issue-141-observation-20260930-01a0f318"
        / "r3-graphic-context-20261001T200750.808432Z/pair.json"
    )
    expected_sha = "b45c1e45ace27f59052618536cd0121646b4995297b6eb2628d87b3686d7e78b"
    assert pair_path.is_file()
    assert hashlib.sha256(pair_path.read_bytes()).hexdigest() == expected_sha
    pair = json.loads(pair_path.read_text())
    state = pair["timelinePasses"][0]
    reader = SimpleNamespace(
        _timeline=lambda value, uid: next(
            row
            for row in value["timelines"]
            if row["GetUniqueId"]["value"] == uid
        )
    )
    item = module._target_boundary_a3(state, reader)
    source = item["GetMediaPoolItem"]
    assert "GetName" not in source
    assert source["GetClipProperty"]["value"]["Clip Name"] == "bed.wav"

    wrong_state = deepcopy(state)
    wrong_item = module._marked_item(wrong_state, reader, "audio", 3, "R3-boundary")
    wrong_item["GetMediaPoolItem"]["GetClipProperty"]["value"]["Clip Name"] = (
        "wrong.wav"
    )
    try:
        module._target_boundary_a3(wrong_state, reader)
    except RuntimeError as error:
        assert str(error) == "Exact enabled R3-boundary A3 crossing bed changed"
    else:
        raise AssertionError("Wrong retained source name was accepted")


def exercise_named_sequence(
    case, preparation, store, output, base_config, resolve, probe, reader, digest, mode
):
    def write_pair(name):
        store.sync_usages()
        path = output / name
        current = deepcopy(store.state)
        pair = {
            "selectedTimelineUid": module.MATRIX_UID,
            "timelineConsistency": "equal-adjacent-reads",
            "poolConsistency": "equal-adjacent-reads",
            "timelinePasses": [current, deepcopy(current)],
            "poolPasses": [deepcopy(store.pool), deepcopy(store.pool)],
        }
        path.write_text(json.dumps(pair))
        return name, digest(path)

    def selection(name, label, pair_ref, rows, *, corrupt=False):
        selected = deepcopy(rows)
        if corrupt:
            selected[0]["GetUniqueId"]["value"] = "wrong-selected-uid"
        record = {
            "status": "editorial-readback-retained",
            "label": label,
            "readOnly": True,
            "failure": None,
            "pair": {
                "path": str((output / pair_ref[0]).resolve()),
                "sha256": pair_ref[1],
            },
            "selectionPasses": [{"items": selected}, {"items": deepcopy(selected)}],
            "selectionShapes": [{"type": "list", "count": len(selected)}] * 2,
        }
        path = output / name
        path.write_text(json.dumps(record))
        return name, digest(path)

    def track(kind, index=1):
        return next(
            row
            for row in store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == index
        )

    def split_linked(cut, right_uids, *, second=False):
        start, end = module.CASES[case]["start"], module.CASES[case]["end"]
        for kind in ("video", "audio"):
            rows = track(kind)["items"]
            uid = right_uids[kind] if second else preparation["target"]["uids"][kind]
            parent = next(row for row in rows if row["GetUniqueId"]["value"] == uid)
            left_bounds = (
                (start + 60, start + cut, 60, cut)
                if second
                else (start, start + cut, 0, cut)
            )
            right_bounds = (start + cut, end, cut, 199)
            right_uid = right_uids[kind] if not second else f"{case}-{kind}-tail"
            left = module._razor_child(parent, parent, *left_bounds)
            right = deepcopy(parent)
            right["GetUniqueId"] = {"value": right_uid}
            right = module._razor_child(parent, right, *right_bounds)
            rows[:] = [row for row in rows if row is not parent] + [left, right]
            rows.sort(key=lambda row: row["GetUniqueId"]["value"])
        left_ids = {
            kind: next(
                row["GetUniqueId"]["value"]
                for row in track(kind)["items"]
                if row["GetStart"]["value"] == start
            )
            for kind in ("video", "audio")
        }
        right_ids = {
            kind: next(
                row["GetUniqueId"]["value"]
                for row in track(kind)["items"]
                if row["GetStart"]["value"] == start + cut
            )
            for kind in ("video", "audio")
        }
        for kind in ("video", "audio"):
            left = next(
                row
                for row in track(kind)["items"]
                if row["GetUniqueId"]["value"] == left_ids[kind]
            )
            right = next(
                row
                for row in track(kind)["items"]
                if row["GetUniqueId"]["value"] == right_ids[kind]
            )
            left["GetLinkedItems"] = [
                {"value": left_ids["audio" if kind == "video" else "video"]}
            ]
            right["GetLinkedItems"] = [
                {"value": right_ids["audio" if kind == "video" else "video"]}
            ]
        for source_uid in preparation["target"]["sourceUids"].values():
            pool_row = next(
                row for row in store.pool["items"] if row["uid"] == source_uid
            )
            usage = pool_row["evidence"]["GetClipProperty"]["value"]["Usage"]
            pool_row["evidence"]["GetClipProperty"]["value"]["Usage"] = str(
                int(usage) + 1
            )
        return left_ids, right_ids

    prep_path = Path(preparation["directory"]) / "result.json"
    prep_ref = str(prep_path.relative_to(output)), digest(prep_path)
    prepared_ref = (
        preparation["preparedPair"]["path"],
        preparation["preparedPair"]["sha256"],
    )
    initial_items = [
        next(
            row
            for row in track(kind)["items"]
            if row["GetUniqueId"]["value"] == preparation["target"]["uids"][kind]
        )
        for kind in ("video", "audio")
    ]
    first_selection = selection(
        "named-first-selection.json",
        {
            "R2-residual": "r2-residual-selected",
            "R3-Graphic": "r3-graphic-selected",
            "R3-boundary": "r3-boundary-selected",
        }[case],
        prepared_ref,
        initial_items,
        corrupt=mode == "wrong-first-selection-id",
    )
    first_config = {
        **base_config,
        "preparationResult": prep_ref[0],
        "preparationResultSha256": prep_ref[1],
        "firstSelectionResult": first_selection[0],
        "firstSelectionResultSha256": first_selection[1],
    }
    try:
        ready_first = module.named_split_ready(
            resolve, first_config, probe=probe, reader=reader
        )
    except RuntimeError as error:
        if mode != "wrong-first-selection-id":
            raise
        return {"preparation": preparation, "first_ready_refusal": str(error)}
    assert ready_first["status"] == "split-ready"
    start = module.CASES[case]["start"]
    cut = module.R2_LINKED_SPLITS[case][0]
    _, right_ids = split_linked(
        cut, {k: f"{case}-{k}-right" for k in ("video", "audio")}
    )
    first_pair = write_pair("named-first-split.json")
    first_config.update(
        firstSplitPair=first_pair[0], firstSplitPairSha256=first_pair[1]
    )
    if case != "R2-residual":
        review = module.named_split_review(
            resolve, first_config, probe=probe, reader=reader
        )
        if case != "R3-boundary":
            return {"preparation": preparation, "ready": ready_first, "review": review}
        review_path = output / "base-split-review.json"
        if mode == "wrong-a3-base-split":
            review["ranges"] = [[9000, 9101, 0, 101], [9101, 9199, 101, 199]]
        review_path.write_text(json.dumps(review))
        review_ref = (review_path.name, digest(review_path))
        base_restore = module.restore(
            resolve,
            {
                **first_config,
                "action": "editorial-case-restore",
                "postEditPair": first_pair[0],
                "postEditPairSha256": first_pair[1],
            },
            probe=probe,
            reader=reader,
        )
        restore_path = Path(base_restore["directory"]) / "result.json"
        restore_ref = (str(restore_path.relative_to(output)), digest(restore_path))
        a3_config = {
            **base_config,
            "case": "R3-boundary-A3",
            "priorPair": base_restore["restoredPair"]["path"],
            "priorPairSha256": base_restore["restoredPair"]["sha256"],
            "baseSplitResult": review_ref[0],
            "baseSplitResultSha256": review_ref[1],
            "baseRestoreResult": restore_ref[0],
            "baseRestoreResultSha256": restore_ref[1],
        }
        if mode == "missing-a3-base-split":
            a3_config.pop("baseSplitResult")
            a3_config.pop("baseSplitResultSha256")
        a3_preparation = module.prepare_boundary_a3(
            resolve, a3_config, probe=probe, reader=reader
        )
        a3_preparation_path = Path(a3_preparation["directory"]) / "result.json"
        a3_prepared_ref = a3_preparation["preparedPair"]
        a3_prepared_pin = reader._pin(
            output / a3_prepared_ref["path"],
            Path(a3_prepared_ref["path"]).name,
            a3_prepared_ref["sha256"],
            probe,
        )
        a3_prepared_state, _ = reader._validate_read_pair(a3_prepared_pin, probe)
        a3_prepared_track_lock = next(
            row
            for row in next(
                timeline
                for timeline in a3_prepared_state["timelines"]
                if timeline["GetUniqueId"]["value"] == module.MATRIX_UID
            )["tracks"]
            if row["type"] == "audio" and row["index"] == 3
        )["GetIsTrackLocked"]["value"]
        a3_prep_ref = (
            str(a3_preparation_path.relative_to(output)),
            digest(a3_preparation_path),
        )
        bed = next(
            row
            for row in track("audio", 3)["items"]
            if row["GetUniqueId"]["value"] == a3_preparation["target"]["uid"]
        )
        a3_selection = selection(
            "a3-selection.json",
            "r3-boundary-a3-selected",
            (
                a3_preparation["preparedPair"]["path"],
                a3_preparation["preparedPair"]["sha256"],
            ),
            [bed],
        )
        a3_config.update(
            preparationResult=a3_prep_ref[0],
            preparationResultSha256=a3_prep_ref[1],
            selectionResult=a3_selection[0],
            selectionResultSha256=a3_selection[1],
        )
        if mode == "missing-a3-marker":
            del store.matrix_state()["GetMarkers"]["value"]["9100"]
            try:
                module.boundary_a3_split_ready(
                    resolve, a3_config, probe=probe, reader=reader
                )
            except RuntimeError as error:
                return {"a3_ready_refusal": str(error)}
            raise AssertionError("A3 split-ready accepted a missing authored marker")
        a3_ready = module.boundary_a3_split_ready(
            resolve, a3_config, probe=probe, reader=reader
        )
        parent_uid = a3_preparation["target"]["uid"]
        parent = next(
            row
            for row in track("audio", 3)["items"]
            if row["GetUniqueId"]["value"] == parent_uid
        )
        left = module._razor_child(parent, parent, 9000, 9100, 0, 100)
        right = deepcopy(parent)
        right["GetUniqueId"] = {"value": "bed-a3-right"}
        right = module._razor_child(parent, right, 9100, 9199, 100, 199)
        track("audio", 3)["items"] = [
            row
            for row in track("audio", 3)["items"]
            if row["GetUniqueId"]["value"] != parent_uid
        ] + [left, right]
        pool_row = next(
            row
            for row in store.pool["items"]
            if row["uid"] == "0438f3a0-b58f-4d6f-a36d-81e02cdeaf3f"
        )
        usage = pool_row["evidence"]["GetClipProperty"]["value"]["Usage"]
        pool_row["evidence"]["GetClipProperty"]["value"]["Usage"] = str(int(usage) + 1)
        a3_split = write_pair("a3-split.json")
        a3_config.update(splitPair=a3_split[0], splitPairSha256=a3_split[1])
        a3_review = module.boundary_a3_split_review(
            resolve, a3_config, probe=probe, reader=reader
        )
        a3_after = module.restore(
            resolve,
            {
                **a3_config,
                "action": "editorial-case-restore",
                "postEditPair": a3_split[0],
                "postEditPairSha256": a3_split[1],
            },
            probe=probe,
            reader=reader,
        )
        return {
            "preparation": preparation,
            "ready": ready_first,
            "review": review,
            "a3Preparation": a3_preparation,
            "a3PreparedA3Lock": a3_prepared_track_lock,
            "a3Ready": a3_ready,
            "a3Review": a3_review,
            "a3Restore": a3_after,
        }

    position = module.second_position(resolve, first_config, probe=probe, reader=reader)
    position_path = Path(position["directory"]) / "result.json"
    second_selection = selection(
        "named-second-selection.json",
        "r2-residual-second-selected",
        (
            position["secondPositionPair"]["path"],
            position["secondPositionPair"]["sha256"],
        ),
        [
            next(
                row
                for row in track(kind)["items"]
                if row["GetUniqueId"]["value"] == right_ids[kind]
            )
            for kind in ("video", "audio")
        ],
        corrupt=mode == "wrong-second-selection-id",
    )
    second_config = {
        **first_config,
        "secondPositionResult": str(position_path.relative_to(output)),
        "secondPositionResultSha256": digest(position_path),
        "selectionResult": second_selection[0],
        "selectionResultSha256": second_selection[1],
        "stage": "second",
    }
    try:
        ready_second = module.named_split_ready(
            resolve, second_config, probe=probe, reader=reader
        )
    except RuntimeError as error:
        if mode != "wrong-second-selection-id":
            raise
        return {
            "preparation": preparation,
            "ready": ready_first,
            "position": position,
            "second_ready_refusal": str(error),
        }
    split_linked(70, right_ids, second=True)
    if mode == "source-drift":
        track("video")["items"][0]["GetMediaPoolItem"]["GetUniqueId"]["value"] = (
            "wrong-source"
        )
    elif mode == "marker-drift":
        track("video")["items"][0]["GetMarkers"]["value"]["0"]["customData"] = "{}"
    elif mode == "usage-drift":
        next(
            row
            for row in store.pool["items"]
            if row["uid"] == preparation["target"]["sourceUids"]["video"]
        )["evidence"]["GetClipProperty"]["value"]["Usage"] = "99"
    elif mode == "properties-drift":
        track("audio", 2)["items"][0]["GetClipEnabled"]["value"] = False
    second_pair = write_pair("named-second-split.json")
    selection_middle = selection(
        "named-interval-selection.json",
        "r2-residual-interval-selected",
        second_pair,
        [
            next(
                row
                for row in track(kind)["items"]
                if row["GetStart"]["value"] == (
                    start + 70
                    if mode == "diagnostic-tail-selection"
                    else start + 60
                )
            )
            for kind in ("video", "audio")
        ],
    )
    review_config = {
        **second_config,
        "stage": "first",
        "firstSplitPair": first_pair[0],
        "firstSplitPairSha256": first_pair[1],
        "secondSplitPair": second_pair[0],
        "secondSplitPairSha256": second_pair[1],
        "firstSelectionResult": first_selection[0],
        "firstSelectionResultSha256": first_selection[1],
        "selectionResult": second_selection[0],
        "selectionResultSha256": second_selection[1],
    }
    if mode in {"source-drift", "marker-drift", "usage-drift", "properties-drift"}:
        try:
            module.named_split_review(
                resolve, review_config, probe=probe, reader=reader
            )
        except RuntimeError as error:
            return {"review_refusal": str(error), "ready": ready_second}
        raise AssertionError(f"{mode} did not refuse during split review")
    review = module.named_split_review(
        resolve, review_config, probe=probe, reader=reader
    )
    if mode in {"interval-wrong-source", "interval-wrong-range"}:
        pair_path = output / second_pair[0]
        pair_data = json.loads(pair_path.read_text())
        for state in pair_data["timelinePasses"]:
            matrix = next(
                timeline
                for timeline in state["timelines"]
                if timeline["GetUniqueId"]["value"] == module.MATRIX_UID
            )
            item = next(
                row
                for timeline_track in matrix["tracks"]
                if timeline_track["type"] == "video" and timeline_track["index"] == 1
                for row in timeline_track["items"]
                if row["GetStart"]["value"] == start + 60
            )
            if mode == "interval-wrong-source":
                item["GetMediaPoolItem"]["GetUniqueId"]["value"] = (
                    "wrong-interval-source"
                )
            else:
                item["GetEnd"]["value"] += 1
        pair_path.write_text(json.dumps(pair_data))
        second_pair = (second_pair[0], digest(pair_path))
        selection_path = output / selection_middle[0]
        selection_data = json.loads(selection_path.read_text())
        selection_data["pair"]["sha256"] = second_pair[1]
        selection_path.write_text(json.dumps(selection_data))
        selection_middle = (selection_middle[0], digest(selection_path))
    delete_config = {
        **review_config,
        "secondSplitPair": second_pair[0],
        "secondSplitPairSha256": second_pair[1],
        "selectionResult": selection_middle[0],
        "selectionResultSha256": selection_middle[1],
    }
    if mode == "interval-live-drift":
        track("audio")["items"][0]["GetEnd"]["value"] += 1
    try:
        deleted = module.interval_delete(
            resolve, delete_config, probe=probe, reader=reader
        )
    except RuntimeError as error:
        if mode not in {
            "interval-wrong-source", "interval-wrong-range", "interval-live-drift"
        }:
            raise
        return {"ready": ready_second, "review": review, "delete_refusal": str(error)}
    if mode in {
        "interval-wrong-source", "interval-wrong-range", "interval-live-drift"
    }:
        raise AssertionError(f"{mode} did not refuse interval deletion")
    residual_restore = module.restore(
        resolve,
        {
            **delete_config,
            "action": "editorial-case-restore",
            "postEditPair": deleted["afterPair"]["path"],
            "postEditPairSha256": deleted["afterPair"]["sha256"],
        },
        probe=probe,
        reader=reader,
    )
    return {
        "preparation": preparation,
        "firstReady": ready_first,
        "position": position,
        "secondReady": ready_second,
        "review": review,
        "delete": deleted,
        "restore": residual_restore,
    }


def retained_usage_delta_check():
    fixture = (
        HERE
        / "evidence/r1-copy-paste-stopped"
        / "r1-copy-pasted-20261001T072554.638674Z/pair.json.gz"
    )
    with gzip.open(fixture, "rt", encoding="utf-8") as source:
        pair = json.load(source)
    matrix = next(
        row
        for row in pair["timelinePasses"][0]["timelines"]
        if row.get("GetUniqueId", {}).get("value") == module.MATRIX_UID
    )
    source_uids = {
        item["GetMediaPoolItem"]["GetUniqueId"]["value"]
        for track in matrix["tracks"]
        if (track["type"], track["index"]) in {("video", 1), ("audio", 1)}
        for item in track["items"]
    }
    expected_pair = deepcopy(pair)

    def apply_r1_usage(value):
        if isinstance(value, dict):
            uid = value.get("GetUniqueId", {}).get("value")
            props = value.get("GetClipProperty", {}).get("value")
            if uid in source_uids and isinstance(props, dict):
                props["Usage"] = str(int(props["Usage"]) + 1)
            for child in value.values():
                apply_r1_usage(child)
        elif isinstance(value, list):
            for child in value:
                apply_r1_usage(child)

    apply_r1_usage(expected_pair)
    after = module._usage_delta(pair, source_uids, 1)
    assert after["timelinePasses"] == expected_pair["timelinePasses"]

    parent = {
        field: {"value": 0}
        for field in (
            "GetStart",
            "GetStart(True)",
            "GetEnd",
            "GetEnd(True)",
            "GetDuration",
            "GetDuration(True)",
            "GetSourceStartFrame",
            "GetSourceStartTime",
            "GetSourceEndFrame",
            "GetSourceEndTime",
            "GetLeftOffset",
            "GetLeftOffset(True)",
            "GetRightOffset",
            "GetRightOffset(True)",
        )
    }
    parent["GetSourceEndFrame"] = {"value": 199}
    parent["GetRightOffset"] = {"value": 1}
    parent["GetRightOffset(True)"] = {"value": 1.0}
    observed = deepcopy(parent)
    for field, value in {
        "GetStart": 1500,
        "GetStart(True)": 1500.0,
        "GetEnd": 1600,
        "GetEnd(True)": 1600.0,
        "GetDuration": 100,
        "GetDuration(True)": 100.0,
        "GetSourceStartFrame": 0,
        "GetSourceStartTime": 0.0,
        "GetSourceEndFrame": 100,
        "GetSourceEndTime": 4.0,
        "GetLeftOffset": 0,
        "GetLeftOffset(True)": 0.0,
        "GetRightOffset": 100,
        "GetRightOffset(True)": 100.0,
    }.items():
        observed[field] = {"value": value}
    expected_child = module._razor_child(parent, observed, 1500, 1600, 0, 100)
    assert expected_child == observed, {
        key: (expected_child[key], observed[key])
        for key in expected_child
        if expected_child[key] != observed.get(key)
    }
    observed["GetDuration"] = {"value": 59}
    assert module._razor_child(parent, observed, 1500, 1600, 0, 100) != observed
    # Native R2 right children derive seconds as start plus duration.
    child = module._razor_child(parent, parent, 2560, 2699, 60, 199)
    assert child["GetSourceEndTime"] == {"value": 7.959999999999999}
    assert child["GetSourceEndFrame"] == {"value": 199}


def retained_razor_children_check():
    evidence = HERE / "evidence/r1-razor-success"
    prepared = json.loads((evidence / "prepared-pair.json").read_text())
    split = json.loads((evidence / "split-pair.json").read_text())
    matrix_uid = "29ae8331-b86e-4041-a548-960695cc7b24"
    old_uids = {
        "video": "33270bc5-52d0-4361-a6e3-96eb2b6d4a91",
        "audio": "4d08e64a-85fd-4dfe-ac80-77e4d9d28835",
    }

    def matrix(pair):
        return next(
            timeline
            for timeline in pair["timelinePasses"][0]["timelines"]
            if timeline.get("GetUniqueId", {}).get("value") == matrix_uid
        )

    def track(state, kind):
        return next(
            row for row in state["tracks"] if row["type"] == kind and row["index"] == 1
        )

    before, after = matrix(prepared), matrix(split)
    for kind, old_uid in old_uids.items():
        parent = next(
            item
            for item in track(before, kind)["items"]
            if item.get("GetUniqueId", {}).get("value") == old_uid
        )
        actual_children = [
            item
            for item in track(after, kind)["items"]
            if item.get("GetStart", {}).get("value") in (1500, 1600)
            and item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
            == parent["GetMediaPoolItem"]["GetUniqueId"]["value"]
        ]
        assert len(actual_children) == 2, (kind, len(actual_children))
        ranges = ((1500, 1600, 0, 100), (1600, 1699, 100, 199))
        actual_children.sort(key=lambda item: item["GetStart"]["value"])
        source_uid = parent["GetMediaPoolItem"]["GetUniqueId"]["value"]
        for child, bounds in zip(actual_children, ranges, strict=True):
            expected = module._razor_child(parent, child, *bounds)
            expected = module._usage_delta(expected, {source_uid}, 1)
            assert expected == child, (kind, child.get("GetUniqueId"))


def retained_residual_resume_schema_check():
    result, store = run_case("R2-residual", held_context=True)
    target = result["target"]
    state = deepcopy(store.state)
    matrix = next(
        row for row in state["timelines"]
        if row.get("GetUniqueId", {}).get("value") == module.MATRIX_UID
    )

    def track(kind):
        return next(row for row in matrix["tracks"] if row["type"] == kind and row["index"] == 1)

    children = {}
    for kind in ("video", "audio"):
        parent = next(
            item for item in track(kind)["items"]
            if item["GetUniqueId"]["value"] == target["uids"][kind]
        )
        left = module._razor_child(parent, parent, 4500, 4560, 0, 60)
        right_observed = deepcopy(parent)
        right_observed["GetUniqueId"] = {"value": f"retained-{kind}-right"}
        right = module._razor_child(parent, right_observed, 4560, 4699, 60, 199)
        children[kind] = [left, right]
        track(kind)["items"] = [item for item in track(kind)["items"] if item is not parent] + [left, right]

    for position in range(2):
        for kind in ("video", "audio"):
            other = "audio" if kind == "video" else "video"
            children[kind][position]["GetLinkedItems"] = [
                {"value": children[other][position]["GetUniqueId"]["value"]}
            ]
    for source_uid in target["sourceUids"].values():
        row = next(item for item in store.pool["items"] if item["uid"] == source_uid)
        props = row["evidence"]["GetClipProperty"]["value"]
        props["Usage"] = str(int(props["Usage"]) + 1)

    reader = SimpleNamespace(
        _timeline=lambda value, _reader: next(
            row for row in value["timelines"]
            if row.get("GetUniqueId", {}).get("value") == module.MATRIX_UID
        )
    )
    retained = module._residual_first_children(state, reader, target)
    assert {
        kind: [item["GetUniqueId"]["value"] for item in rows]
        for kind, rows in retained.items()
    } == {
        kind: [item["GetUniqueId"]["value"] for item in rows]
        for kind, rows in children.items()
    }

    wrong_range = deepcopy(state)
    wrong_range_matrix = reader._timeline(wrong_range, reader)
    wrong_video = next(row for row in wrong_range_matrix["tracks"] if row["type"] == "video" and row["index"] == 1)
    next(item for item in wrong_video["items"] if item["GetStart"]["value"] == 4560)["GetEnd"]["value"] = 4698
    try:
        module._residual_first_children(wrong_range, reader, target)
    except RuntimeError as error:
        assert "child ranges changed" in str(error)
    else:
        raise AssertionError("Residual resume accepted an unrelated range change")

    wrong_marker = deepcopy(state)
    wrong_marker_matrix = reader._timeline(wrong_marker, reader)
    wrong_video = next(row for row in wrong_marker_matrix["tracks"] if row["type"] == "video" and row["index"] == 1)
    next(item for item in wrong_video["items"] if item["GetStart"]["value"] == 4500)["GetMarkers"]["value"]["0"]["customData"] = "{}"
    try:
        module._residual_first_children(wrong_marker, reader, target)
    except RuntimeError as error:
        assert "child identity or markers changed" in str(error)
    else:
        raise AssertionError("Residual resume accepted an unrelated marker change")


def demo():
    retained_boundary_source_check()
    retained_usage_delta_check()
    retained_razor_children_check()
    retained_residual_resume_schema_check()
    reviewed, store = run_case("R2-unlinked", review_preparation=True)
    assert reviewed["status"] == "case-prepared", reviewed
    assert reviewed["reviewOnly"] is True
    assert reviewed["reviewedFrom"]["refusal"]["status"] == (
        "refused-partial-state-retained"
    )
    assert reviewed["reviewReadback"]["stateMatchesPreparedPin"] is True
    assert [call[0] for call in store.calls].count("SetClipsLinked") == 1
    video = next(
        item
        for track in store.matrix_state()["tracks"]
        if track["type"] == "video" and track["index"] == 1
        for item in track["items"]
    )
    assert "PitchCorrection" not in video["GetSpeed"]["value"]

    refused, store = run_case(
        "R2-unlinked", review_preparation=True, review_drift=True
    )
    assert refused["status"] == "review-refused", refused
    assert "exact prepared pin" in refused["failure"]
    assert [call[0] for call in store.calls].count("SetClipsLinked") == 1

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

    for case, expected_uid in (
        ("R2-residual", "residual-a2"),
        ("R3-Graphic", "graphic-v3"),
    ):
        result, store = run_case(case)
        assert result["status"] == "case-prepared", result
        assert result["target"]["enabledClips"][0]["uid"] == expected_uid
        assert store.calls[0] == ("SetClipEnabled", expected_uid, True)
        layer = next(
            item
            for track in store.matrix_state()["tracks"]
            for item in track["items"]
            if item["GetUniqueId"]["value"] == expected_uid
        )
        assert layer["GetClipEnabled"] == {"value": True}

    for case, kind, index, uid in (
        ("R2-residual", "audio", 2, "residual-a2"),
        ("R3-Graphic", "video", 3, "graphic-v3"),
    ):
        result, store = run_case(case, mode="locked-layer-requires-unlock")
        assert result["status"] == "case-prepared", result
        assert result["originalLocks"][f"{kind}:{index}"] is True
        unlock_call = ("SetTrackLock", kind, index, False)
        enable_call = ("SetClipEnabled", uid, True)
        relock_call = ("SetTrackLock", kind, index, True)
        assert store.calls.index(unlock_call) < store.calls.index(enable_call)
        assert store.calls.index(enable_call) < store.calls.index(relock_call)
        final_lock = next(
            row
            for row in store.matrix_state()["tracks"]
            if row["type"] == kind and row["index"] == index
        )["GetIsTrackLocked"]["value"]
        assert final_lock is True

    refused, store = run_case(
        "R3-Graphic", mode="locked-clip-enable-false"
    )
    assert refused["status"] == "refused-partial-state-retained", refused
    assert refused["originalLocks"]["video:3"] is True
    assert refused["failure"] == "RuntimeError: SetClipEnabled did not return true"
    assert refused["setters"] == ["SetTrackLock", "SetClipEnabled"]
    assert store.calls[:2] == [
        ("SetTrackLock", "video", 3, False),
        ("SetClipEnabled", "graphic-v3", True),
    ]
    assert refused["preparedPair"]["sha256"]
    assert refused["preparedPair"]["path"].endswith("/after.json")

    result, store = run_case("R3-boundary")
    assert result["status"] == "case-prepared", result
    assert result["target"]["addedMarker"] == {
        "frame": 9100,
        "value": {
            "color": "Blue",
            "duration": 1,
            "name": "141 R3 exact section boundary",
            "note": "Synthetic authored boundary at local frame 100",
            "customData": json.dumps(
                {"issue": 141, "section": "R3-boundary", "boundaryLocalFrame": 100},
                sort_keys=True,
            ),
        },
    }
    assert (
        store.matrix_state()["GetMarkers"]["value"]["9100"]
        == result["target"]["addedMarker"]["value"]
    )

    for case, mode, label in (
        ("R2-residual", "clip-enable-false", "SetClipEnabled did not return true"),
        ("R3-boundary", "marker-false", "AddMarker did not return true"),
        ("R3-boundary", "marker-drift", "AddMarker did not read back"),
    ):
        result, store = run_case(case, mode=mode)
        assert result["status"] == "refused-partial-state-retained", result
        assert label in result["failure"], result

    result, store = run_case("R3-boundary", mode="drift")
    assert result["status"] == "refused-partial-state-retained", result
    assert (
        result["failure"] == "Full postflight differs from the bounded case operation"
    )
    assert (
        store.matrix_state()["GetMarkers"]["value"]["9100"]["name"]
        == "141 R3 exact section boundary"
    )

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

    result, store = run_case("R2-picture", wrong_case=True)
    assert result["status"] == "refused-before-setters"
    assert store.calls == []

    result, store = run_case("R2-unlinked", phase_mode="unlink-false")
    assert result["status"] == "refused-partial-state-retained", result
    assert "SetClipsLinked did not return true" in result["failure"]
    assert [call[0] for call in store.calls] == ["SetClipsLinked"]

    for case, target_track in (
        ("R2-unlinked", "audio"),
        ("R2-picture", "video"),
        ("R2-partial", "audio"),
    ):
        (prepared, positioned, deleted, restored), store = run_case(
            case, r2_phases=True
        )
        assert prepared["status"] == "case-prepared", prepared
        assert prepared["target"]["targetTrack"] == target_track
        assert prepared["target"]["unlinkPrepared"] is True
        assert prepared["target"]["splitPlayheadFrame"] == (
            module.CASES[case]["start"] + module.R2_SINGLE[case]["cutStart"]
        )
        assert positioned["status"] == "second-position-ready", positioned
        assert positioned["target"]["splitFrame"] == (
            module.CASES[case]["start"] + module.R2_SINGLE[case]["cutEnd"]
        )
        assert deleted["status"] == "interval-deleted-unsaved", deleted
        assert deleted["intervalUid"] == f"{case}-first-right"
        assert deleted["sourceUid"] == prepared["target"]["sourceUids"][target_track]
        assert [call[0] for call in store.calls].count("SetClipsLinked") == 1
        assert [call[0] for call in store.calls].count("DeleteClips") == 1
        assert restored["status"] == "restored-unsaved", restored
        assert all(
            track["GetIsTrackLocked"]["value"] is False
            for track in store.matrix_state()["tracks"]
        )

    result, store = run_case("R2-offset")
    assert result["status"] == "case-prepared", result
    assert result["target"]["targetTrack"] == "audio"
    assert result["target"]["selectionTimecode"] == "00:03:24:00"
    assert [call[0] for call in store.calls].count("SetClipsLinked") == 1
    assert not any(call[0] == "DeleteClips" for call in store.calls)
    assert all(
        track["GetIsTrackLocked"]["value"]
        == ((track["type"], track["index"]) != ("audio", 1))
        for track in store.matrix_state()["tracks"]
    )

    for phase_mode, expected in (
        ("wrong-first-range", "target-track child ranges changed"),
        ("wrong-second-range", "target-track child ranges changed"),
        ("untouched-track-change", "unrelated state or source Usage"),
    ):
        result, store = run_case("R2-unlinked", r2_phases=True, phase_mode=phase_mode)
        refusal = result.get("position_refusal", result.get("delete_refusal", ""))
        assert expected in refusal, result
        assert not any(call[0] == "DeleteClips" for call in store.calls)

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

    (held_prepared, held_restored), store = run_case(
        "R2-linked", restore_move=True, held_context=True
    )
    assert held_prepared["status"] == "case-prepared", held_prepared
    assert held_prepared["originalPlayhead"] == "00:01:30:00"
    assert held_prepared["originalLocks"] == {
        "video:1": False,
        "video:2": True,
        "video:3": True,
        "audio:1": False,
        "audio:2": True,
        "audio:3": True,
    }
    assert held_restored["status"] == "restored-unsaved", held_restored
    assert store.playhead == "00:01:30:00"
    assert {
        f"{track['type']}:{track['index']}": track["GetIsTrackLocked"]["value"]
        for track in store.matrix_state()["tracks"]
    } == held_prepared["originalLocks"]
    assert [
        (item["GetStart"]["value"], item["GetEnd"]["value"])
        for track in store.matrix_state()["tracks"]
        if track["index"] == 1
        for item in track["items"]
    ] == [(2525, 2724), (2525, 2724)]
    assert held_restored["restoredPair"]["sha256"]

    refused, store = run_case("R2-linked", mode="wrong-primary-lock")
    assert refused["status"] == "refused-before-setters", refused
    assert "unlocked V1/A1" in refused["failure"]
    assert store.calls == []
    refused, store = run_case("R1-trim", held_context=True)
    assert refused["status"] == "refused-before-setters", refused
    assert "requires the unlocked Matrix" in refused["failure"]
    assert store.calls == []

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

    residual, store = run_case("R2-residual", named_sequence=True, held_context=True)
    assert residual["firstReady"]["status"] == "split-ready", residual
    assert residual["position"]["status"] == "second-position-ready", residual
    assert residual["secondReady"]["status"] == "split-ready", residual
    assert residual["review"]["status"] == "split-readback-retained", residual
    assert residual["review"]["ranges"] == [
        [4500, 4560, 0, 60],
        [4560, 4570, 60, 70],
        [4570, 4699, 70, 199],
    ]
    assert residual["delete"]["status"] == "interval-deleted-unsaved", residual
    assert residual["restore"]["status"] == "restored-unsaved", residual
    assert residual["restore"]["originalPlayhead"] == "00:01:30:00"
    assert store.playhead == "00:01:30:00"
    assert all(
        track["GetIsTrackLocked"]["value"]
        == ((track["type"], track["index"]) in module.LOCKS)
        for track in store.matrix_state()["tracks"]
    )
    assert residual["delete"]["intervalUids"] == {
        "video": "R2-residual-video-right",
        "audio": "R2-residual-audio-right",
    }
    delete_call = next(call for call in store.calls if call[0] == "DeleteClips")
    assert delete_call == (
        "DeleteClips",
        ["R2-residual-video-right", "R2-residual-audio-right"],
        False,
    )
    assert next(
        row
        for row in store.matrix_state()["tracks"]
        if row["type"] == "audio" and row["index"] == 2
    )["items"][0]["GetClipEnabled"] == {"value": True}

    diagnostic, store = run_case(
        "R2-residual",
        named_sequence=True,
        held_context=True,
        phase_mode="diagnostic-tail-selection",
    )
    assert diagnostic["delete"]["selectionDiagnostic"] == {
        "diagnosticOnly": True,
        "selectedUids": ["R2-residual-video-tail", "R2-residual-audio-tail"],
        "selectionMatchesInterval": False,
    }, diagnostic
    assert next(call for call in store.calls if call[0] == "DeleteClips") == (
        "DeleteClips",
        ["R2-residual-video-right", "R2-residual-audio-right"],
        False,
    )
    assert diagnostic["delete"]["status"] == "interval-deleted-unsaved"
    assert diagnostic["restore"]["status"] == "restored-unsaved"
    assert diagnostic["restore"]["originalPlayhead"] == "00:01:30:00"
    assert store.playhead == "00:01:30:00"
    protected_a2 = next(
        row for row in store.matrix_state()["tracks"]
        if row["type"] == "audio" and row["index"] == 2
    )
    assert protected_a2["items"][0]["GetClipEnabled"] == {"value": True}

    for mode in (
        "interval-wrong-source", "interval-wrong-range", "interval-live-drift"
    ):
        refused, store = run_case(
            "R2-residual", named_sequence=True, phase_mode=mode
        )
        assert "delete_refusal" in refused, refused
        assert not any(call[0] == "DeleteClips" for call in store.calls)

    for mode, stage in (
        ("wrong-first-selection-id", "first_ready_refusal"),
        ("wrong-second-selection-id", "second_ready_refusal"),
    ):
        refused, _ = run_case("R2-residual", named_sequence=True, phase_mode=mode)
        assert stage in refused, refused
        assert "selected UIDs" in refused[stage], refused
    for mode, expected in (
        ("source-drift", "child ranges changed"),
        ("marker-drift", "child identity or markers changed"),
        ("usage-drift", "source Usage"),
        ("properties-drift", "split changed unrelated state"),
    ):
        refused, _ = run_case("R2-residual", named_sequence=True, phase_mode=mode)
        assert "review_refusal" in refused, refused
        assert expected in refused["review_refusal"], refused

    graphic, store = run_case("R3-Graphic", named_sequence=True)
    assert graphic["ready"]["status"] == "split-ready", graphic
    assert graphic["review"]["status"] == "split-readback-retained", graphic
    crossing = next(
        item
        for track in store.matrix_state()["tracks"]
        if track["type"] == "video" and track["index"] == 3
        for item in track["items"]
        if item["GetUniqueId"]["value"] == "graphic-v3"
    )
    assert crossing["GetClipEnabled"] == {"value": True}

    boundary, store = run_case("R3-boundary", named_sequence=True, held_context=True)
    assert boundary["review"]["status"] == "split-readback-retained", boundary
    assert boundary["a3Ready"]["status"] == "split-ready", boundary
    assert boundary["a3Review"]["status"] == "split-readback-retained", boundary
    assert boundary["a3Restore"]["status"] == "restored-unsaved", boundary
    assert boundary["a3PreparedA3Lock"] is False
    assert boundary["a3Review"]["ranges"] == [
        [9000, 9100, 0, 100],
        [9100, 9199, 100, 199],
    ]
    assert (
        store.matrix_state()["GetMarkers"]["value"]["9100"]
        == boundary["preparation"]["target"]["addedMarker"]["value"]
    )
    assert next(
        item
        for track in store.matrix_state()["tracks"]
        if track["type"] == "video" and track["index"] == 3
        for item in track["items"]
    )["GetClipEnabled"] == {"value": False}
    assert store.playhead == "00:01:30:00"
    assert {
        f"{track['type']}:{track['index']}": track["GetIsTrackLocked"]["value"]
        for track in store.matrix_state()["tracks"]
    } == {
        "video:1": False,
        "video:2": True,
        "video:3": True,
        "audio:1": False,
        "audio:2": True,
        "audio:3": True,
    }
    assert ("SetTrackLock", "audio", 3, False) in store.calls
    assert next(
        item
        for track in store.matrix_state()["tracks"]
        if track["type"] == "audio" and track["index"] == 2
        for item in track["items"]
    )["GetClipEnabled"] == {"value": False}

    refused, _ = run_case(
        "R3-boundary", named_sequence=True, phase_mode="missing-a3-marker"
    )
    assert "a3_ready_refusal" in refused, refused
    try:
        run_case("R3-boundary", named_sequence=True, phase_mode="wrong-a3-base-split")
    except RuntimeError as error:
        assert "preceding R3-boundary base split review" in str(error), error
    else:
        raise AssertionError("A3 preparation accepted a mismatched base-split review")
    try:
        run_case("R3-boundary", named_sequence=True, phase_mode="missing-a3-base-split")
    except RuntimeError as error:
        assert "approved-output evidence pin" in str(error), error
    else:
        raise AssertionError("A3 preparation accepted missing base-split evidence")
    print("R1-R3 guarded fake checks passed; no native app launched.")


if __name__ == "__main__":
    demo()
