"""Fake-only checks for the bounded audio-mapping mute helper."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path


MODULE = Path(__file__).with_name("audio-mapping-mute.py")
SPEC = importlib.util.spec_from_file_location("audio_mapping_mute", MODULE)
CODE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(CODE)


class Probe:
    def _pass_timeline(self, state, timeline_id):
        rows = [
            row
            for row in state.get("timelines", [])
            if row.get("GetUniqueId", {}).get("value") == timeline_id
        ]
        if len(rows) != 1:
            raise RuntimeError("fake timeline identity mismatch")
        return rows[0]

    def errors(self, value):
        if isinstance(value, dict):
            return "error" in value or any(self.errors(v) for v in value.values())
        if isinstance(value, list):
            return any(self.errors(v) for v in value)
        return False


class Source:
    def __init__(self, uid=CODE.TARGET_SOURCE_UID, name="repeated.wav"):
        self.uid = uid
        self.name = name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class Item:
    def __init__(self, uid=CODE.TARGET_UID, source=None, marker_name="141 R2-residual item 2", track=None):
        self.uid = uid
        self.source = source or Source()
        self.marker_name = marker_name
        self.track = track or CODE.TARGET_TRACK
        self.raw = json.dumps(
            {
                "embedded_audio_channels": 1,
                "linked_audio": {},
                "track_mapping": {
                    "1": {"channel_idx": [1], "mute": False, "type": "mono"}
                },
            },
            separators=(",", ":"),
            sort_keys=True,
        )
        self.calls = []
        self.start, self.end = CODE.TARGET_RANGE

    def GetUniqueId(self):
        return self.uid

    def GetMediaPoolItem(self):
        return self.source

    def GetTrackTypeAndIndex(self):
        return self.track

    def GetStart(self):
        return self.start

    def GetEnd(self):
        return self.end

    def GetMarkers(self):
        return {"200": {"name": self.marker_name, "customData": "synthetic"}}

    def GetSourceAudioChannelMapping(self):
        return self.raw

    def SetSourceAudioChannelMapping(self, raw):
        self.calls.append(raw)
        self.raw = raw
        return True


def _item_row(item, *, start=None):
    return {
        "GetUniqueId": {"value": item.uid},
        "GetName": {"value": "repeated.wav"},
        "GetTrackTypeAndIndex": {"value": item.track},
        "GetStart": {"value": item.start if start is None else start},
        "GetEnd": {"value": item.end},
        "GetMarkers": {"value": item.GetMarkers()},
        "GetSourceAudioChannelMapping": {"value": item.raw},
        "GetMediaPoolItem": {
            "GetUniqueId": {"value": item.source.uid},
            "GetClipProperty": {"value": {"File Name": item.source.name}},
        },
    }


def _pair(target, other=None):
    rows = [_item_row(target)]
    if other is not None:
        rows.append(_item_row(other))
    timeline = {
        "GetUniqueId": {"value": CODE.MATRIX_UID},
        "GetName": {"value": CODE.MATRIX_NAME},
        "tracks": [{"type": "audio", "index": 2, "items": rows}],
        "timelineInventory": CODE.PROTECTED_INVENTORY,
    }
    state = {
        "projectId": CODE.PROJECT_ID,
        "projectName": "VERA Issue 141 Synthetic Probe 20260930-01a0f318",
        "timelineInventory": CODE.PROTECTED_INVENTORY,
        "timelines": [timeline],
    }
    return {
        "selectedTimelineUid": CODE.MATRIX_UID,
        "timelineInventory": CODE.PROTECTED_INVENTORY,
        "timelineConsistency": "equal-adjacent-reads",
        "poolConsistency": "equal-adjacent-reads",
        "timelinePasses": [copy.deepcopy(state), copy.deepcopy(state)],
        "poolPasses": [{"items": []}, {"items": []}],
    }


def _set_target_row(pair, item, *, start=None):
    state = pair["timelinePasses"][0]
    timeline = state["timelines"][0]
    row = next(row for row in timeline["tracks"][0]["items"] if row["GetUniqueId"]["value"] == item.uid)
    row["GetSourceAudioChannelMapping"]["value"] = item.raw
    if start is not None:
        row["GetStart"]["value"] = start
    pair["timelinePasses"][1] = copy.deepcopy(pair["timelinePasses"][0])


class RunItem(Item):
    def __init__(self, *, setter_mode="success", **kwargs):
        super().__init__(**kwargs)
        self.setter_mode = setter_mode

    def SetSourceAudioChannelMapping(self, raw):
        self.calls.append(raw)
        if self.setter_mode in {"false", "false-restore-false"} and len(self.calls) == 1:
            return False
        if self.setter_mode == "false-restore-false" and len(self.calls) == 2:
            return False
        if self.setter_mode == "raise" and len(self.calls) == 1:
            raise RuntimeError("injected mapping setter failure")
        self.raw = raw
        return True


class RunStore:
    def __init__(self, *, setter_mode="success", readback_failure=False, drift=False):
        self.item = RunItem(setter_mode=setter_mode)
        self.other = Item(uid="other-1", source=Source(uid="source-2"), marker_name="other-marker")
        self.reads = 0
        self.readback_failure = readback_failure
        self.drift = drift
        self.drift_at = 2
        self.project = RunProject(self)

    def pair(self):
        pair = _pair(self.item, self.other)
        if self.drift and self.reads == self.drift_at:
            row = pair["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"][1]
            row["GetStart"]["value"] += 1
            pair["timelinePasses"][1] = copy.deepcopy(pair["timelinePasses"][0])
        return pair


class RunTimeline:
    def __init__(self, store):
        self.store = store

    def GetCurrentTimecode(self):
        return "00:00:00:00"

    def GetItemListInTrack(self, kind, index):
        assert [kind, index] == CODE.TARGET_TRACK
        return [self.store.item, self.store.other]


class RunProject:
    def __init__(self, store):
        self.store = store
        self.timeline = RunTimeline(store)

    def GetCurrentTimeline(self):
        return self.timeline


class RunResolve:
    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return CODE.BUILD

    def GetCurrentPage(self):
        return "edit"


class RunReader:
    def __init__(self, store):
        self.store = store

    def _pin(self, path, name, digest, probe):
        del path, name, digest, probe
        return self.store.pair()

    def _validate_read_pair(self, value, probe):
        del value, probe

    def _manifest(self, config, root, probe):
        del config, root, probe
        return None, {}

    def _context(self, resolve, config, identity, probe, selected_uid):
        del resolve, config, identity, probe, selected_uid
        return self.store.project

    def _read_pair(self, resolve, config, identity, expected, selected_uid, probe):
        del resolve, config, identity, expected, selected_uid, probe
        self.store.reads += 1
        if self.store.readback_failure and self.store.reads == 2:
            raise RuntimeError("injected mapping readback failure")
        return self.store.pair()


def _run_fake_case(*, setter_mode="success", readback_failure=False, drift=False, phase="roundtrip"):
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        checkpoint = output / "checkpoint.json"
        checkpoint.write_text("fake", encoding="utf-8")
        config = {
            "action": CODE.ACTION,
            "case": CODE.CASE,
            "externalScriptingSetting": "None",
            "timelineInventory": CODE.PROTECTED_INVENTORY,
            "projectName": "VERA Issue 141 Synthetic Probe 20260930-01a0f318",
            "outputDir": str(output),
            "mappingCheckpoint": str(checkpoint),
            "mappingCheckpointSha256": "fake-checkpoint",
            "mappingPhase": phase,
        }
        store = RunStore(
            setter_mode=setter_mode,
            readback_failure=readback_failure,
            drift=drift,
        )
        reader = RunReader(store)
        original_load_reader = CODE._load_reader
        Probe.ROOT = root
        CODE._load_reader = lambda here, probe: reader
        try:
            try:
                report = CODE.run(RunResolve(), config, probe=Probe())
                error = None
            except RuntimeError as caught:
                report = None
                error = caught
            evidence_dir = next(output.glob("audio-mapping-mute-*"))
            evidence = {
                path.name: path.read_bytes() for path in evidence_dir.iterdir()
            }
            result = json.loads(evidence["result.json"])
            journal = [
                json.loads(line)
                for line in evidence["journal.jsonl"].decode().splitlines()
            ]
            return report, error, result, journal, evidence, store
        finally:
            CODE._load_reader = original_load_reader


def _run_hold_restore_case():
    import tempfile

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        checkpoint = output / "checkpoint.json"
        checkpoint.write_text("fake", encoding="utf-8")
        config = {
            "action": CODE.ACTION, "case": CODE.CASE, "externalScriptingSetting": "None",
            "timelineInventory": CODE.PROTECTED_INVENTORY,
            "projectName": "VERA Issue 141 Synthetic Probe 20260930-01a0f318",
            "outputDir": str(output), "mappingCheckpoint": str(checkpoint),
            "mappingCheckpointSha256": "fake-checkpoint", "mappingPhase": "hold",
        }
        store = RunStore()
        reader = RunReader(store)
        original_load_reader = CODE._load_reader
        Probe.ROOT = root
        CODE._load_reader = lambda here, probe: reader
        try:
            config["mappingPhase"] = "wrong-phase"
            try:
                CODE.run(RunResolve(), config, probe=Probe())
            except RuntimeError as error:
                assert "Unsupported mappingPhase" in str(error)
            else:
                raise AssertionError("wrong mapping phase was accepted")
            assert len(store.item.calls) == 0
            config["mappingPhase"] = "hold"
            held = CODE.run(RunResolve(), config, probe=Probe())
            held_path = Path(held["evidence"]["result"])
            assert held["status"] == "mapping-muted-held-for-output"
            assert len(store.item.calls) == 1 and json.loads(store.item.raw)["track_mapping"]["1"]["mute"] is True
            try:
                CODE.run(RunResolve(), config, probe=Probe())
            except RuntimeError as error:
                assert "begin unmuted" in str(error)
            else:
                raise AssertionError("second hold was accepted")
            assert len(store.item.calls) == 1
            config.update(mappingPhase="restore", heldResult=str(held_path), heldResultSha256="wrong-hash")
            try:
                CODE.run(RunResolve(), config, probe=Probe())
            except RuntimeError as error:
                assert "hash-bound" in str(error)
            else:
                raise AssertionError("wrong held-result hash was accepted")
            assert len(store.item.calls) == 1
            store.drift = True
            store.drift_at = store.reads + 1
            config.update(mappingPhase="restore", heldResult=str(held_path),
                          heldResultSha256=hashlib.sha256(held_path.read_bytes()).hexdigest())
            try:
                CODE.run(RunResolve(), config, probe=Probe())
            except RuntimeError as error:
                assert "differs from exact held after pair" in str(error)
            else:
                raise AssertionError("unrelated held-state drift was accepted")
            assert len(store.item.calls) == 1
            store.drift = False
            config.update(mappingPhase="restore", heldResult=str(held_path),
                          heldResultSha256=hashlib.sha256(held_path.read_bytes()).hexdigest())
            assert held_path.parent.parent.resolve() == output.resolve()
            assert not held_path.is_symlink()
            assert CODE._file_sha256(held_path) == config["heldResultSha256"]
            checkpoint.write_text("fresh checkpoint", encoding="utf-8")
            config["mappingCheckpointSha256"] = "fresh-checkpoint"
            restored = CODE.run(RunResolve(), config, probe=Probe())
            assert restored["status"] == "mapping-muted-and-exactly-restored"
            assert len(store.item.calls) == 2 and json.loads(store.item.raw)["track_mapping"]["1"]["mute"] is False
            assert restored["restoredFullPair"] == held["beforeFullPair"]
            held_data = json.loads(held_path.read_text(encoding="utf-8"))
            held_data["status"] = "malformed"
            held_path.write_text(json.dumps(held_data), encoding="utf-8")
            config["heldResultSha256"] = hashlib.sha256(held_path.read_bytes()).hexdigest()
            try:
                CODE.run(RunResolve(), config, probe=Probe())
            except RuntimeError as error:
                assert "wrong phase or status" in str(error)
            else:
                raise AssertionError("malformed held status was accepted")
            assert len(store.item.calls) == 2
            return held, restored, store
        finally:
            CODE._load_reader = original_load_reader


def run():
    probe = Probe()
    target = Item()
    other = Item(uid="other-1", source=Source(uid="source-2"), marker_name="other-marker")
    before = _pair(target, other)
    descriptor = CODE._target_from_state(before["timelinePasses"][0], probe)
    assert descriptor["occurrenceUid"] == target.uid
    assert descriptor["markerName"] == "141 R2-residual item 2"

    muted = CODE._muted_mapping(descriptor["originalRawMapping"])
    assert CODE._mapping_delta_is_only_mute(descriptor["originalRawMapping"], muted)
    after = copy.deepcopy(before)
    _set_target_row(after, target)
    row = next(row for row in after["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"] if row["GetUniqueId"]["value"] == target.uid)
    row["GetSourceAudioChannelMapping"]["value"] = muted
    after["timelinePasses"][1] = copy.deepcopy(after["timelinePasses"][0])
    assert CODE._pair_with_only_target_mapping_change(before, after, target.uid, probe)

    target.SetSourceAudioChannelMapping(muted)
    assert target.raw == muted and len(target.calls) == 1
    target.SetSourceAudioChannelMapping(descriptor["originalRawMapping"])
    assert target.raw == descriptor["originalRawMapping"] and len(target.calls) == 2

    # Any unrelated item/range/source change is refused.
    drift = copy.deepcopy(after)
    drift["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"][1]["GetStart"]["value"] += 1
    drift["timelinePasses"][1] = copy.deepcopy(drift["timelinePasses"][0])
    try:
        CODE._pair_with_only_target_mapping_change(before, drift, target.uid, probe)
    except RuntimeError:
        pass
    else:
        raise AssertionError("unrelated range drift was accepted")

    bad_mapping = json.loads(muted)
    bad_mapping["track_mapping"]["1"]["channel_idx"] = [2]
    assert not CODE._mapping_delta_is_only_mute(
        descriptor["originalRawMapping"], json.dumps(bad_mapping, sort_keys=True, separators=(",", ":"))
    )

    # Duplicate marker and protected source refuse before a setter could run.
    duplicate = copy.deepcopy(before)
    duplicate["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"].append(
        copy.deepcopy(duplicate["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"][0])
    )
    try:
        CODE._target_from_state(duplicate["timelinePasses"][0], probe)
    except RuntimeError:
        pass
    else:
        raise AssertionError("duplicate marker was accepted")

    protected = Item(source=Source(CODE.PROTECTED_SOURCE_UID, CODE.PROTECTED_SOURCE_NAME))
    try:
        CODE._target_from_state(_pair(protected)["timelinePasses"][0], probe)
    except RuntimeError:
        pass
    else:
        raise AssertionError("protected source was accepted")

    for wrong in (
        Item(uid="wrong-uid"),
        Item(source=Source("wrong-source")),
        Item(track=["audio", 3]),
    ):
        try:
            CODE._target_from_state(_pair(wrong)["timelinePasses"][0], probe)
        except RuntimeError:
            pass
        else:
            raise AssertionError("changed target identity/track was accepted")
    range_drift = _pair(Item())
    range_drift["timelinePasses"][0]["timelines"][0]["tracks"][0]["items"][0]["GetEnd"]["value"] += 1
    try:
        CODE._target_from_state(range_drift["timelinePasses"][0], probe)
    except RuntimeError:
        pass
    else:
        raise AssertionError("target range drift was accepted")

    print("PASS: mapping delta, exact restoration, unrelated drift, duplicate marker, and protected source refusals")


    report, error, result, journal, evidence, store = _run_fake_case()
    assert error is None and report["status"] == "mapping-muted-and-exactly-restored"
    assert len(store.item.calls) == 2
    assert json.loads(store.item.calls[0])["track_mapping"]["1"]["mute"] is True
    assert json.loads(store.item.calls[1])["track_mapping"]["1"]["mute"] is False
    assert all(
        name in evidence
        for name in (
            "before-full-pair.json",
            "target.json",
            "after-muted-full-pair.json",
            "restored-full-pair.json",
            "result.json",
            "journal.jsonl",
        )
    )
    assert [
        (row["value"]["operation"], row["phase"])
        for row in journal
        if row["method"] == "SetSourceAudioChannelMapping"
        and row["phase"] in {"request", "return"}
    ] == [
        ("mute", "request"),
        ("mute", "return"),
        ("restore", "request"),
        ("restore", "return"),
    ]

    for kwargs, expected in (
        ({"setter_mode": "false"}, "refused"),
        ({"setter_mode": "false-restore-false"}, "refused"),
        ({"readback_failure": True}, "readback failure"),
        ({"drift": True}, "State changed outside the target mapping getter"),
    ):
        report, error, result, journal, evidence, store = _run_fake_case(**kwargs)
        assert report is None and error is not None
        assert expected in str(error)
        assert result["status"] == "mapping-operation-failed-evidence-retained"
        assert expected in result["failure"]
        assert all(
            name in evidence
            for name in ("before-full-pair.json", "target.json", "result.json", "journal.jsonl")
        )
        assert len(store.item.calls) == 2
        assert any(row["method"] == "MappingMutation" for row in journal)
        assert any(
            row["method"] == "SetSourceAudioChannelMapping"
            and row["phase"] == "restore-request"
            for row in journal
        )
        if kwargs.get("setter_mode") == "false-restore-false":
            assert expected in result["restoreFailure"]
            assert "restored-full-pair.json" in evidence
            assert any(row["phase"] == "after-restore-failure"
                       and row["value"]["equalsBefore"] is True for row in journal)
        if kwargs.get("drift"):
            assert "after-muted-full-pair.json" in evidence
            assert any(
                row["phase"] == "failure" for row in journal if row["method"] == "ReadPair"
            )

    print("PASS: [REDACTED] delta, exact restoration, failure retention, unrelated drift, duplicate marker, and protected source refusals")

    held, restored, store = _run_hold_restore_case()
    assert held["status"] == "mapping-muted-held-for-output"
    assert restored["status"] == "mapping-muted-and-exactly-restored"
    assert len(store.item.calls) == 2
    report, error, result, journal, evidence, store = _run_fake_case(
        setter_mode="false", phase="hold"
    )
    assert error is not None and "refused" in str(error)
    assert len(store.item.calls) == 2
    assert json.loads(store.item.raw)["track_mapping"]["1"]["mute"] is False
    assert "restored-full-pair.json" in evidence and result["status"] == "mapping-operation-failed-evidence-retained"
    print("PASS: held output state, exact one-call restore, second-hold/hash/status refusal, and hold-error restoration")

if __name__ == "__main__":
    run()
