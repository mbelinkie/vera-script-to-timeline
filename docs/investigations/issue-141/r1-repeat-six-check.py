"""Focused offline guard and fake-API checks for r1-repeat-six.py."""

import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
MODULE = Path(__file__).with_name("r1-repeat-six.py")
PAIR = (
    ROOT / "out/issue-141-observation-20260930-01a0f318/"
    "protected-six-r4-pool-20261001T180848.009764Z/pair.json"
)
DUPLICATE_EVIDENCE = (
    ROOT / "out/issue-141-observation-20260930-01a0f318/"
    "r1-repeat-duplicate-20261002T122220.047704Z"
)
spec = importlib.util.spec_from_file_location("r1_repeat_six", MODULE)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def snapshot_import_smoke():
    snapshot = m.PROBE_SNAPSHOT
    assert snapshot.is_file() and not snapshot.is_symlink()
    assert m.digest(snapshot) == m.PROBE_SNAPSHOT_SHA256
    private_probe, reader = m._private_reader(MODULE.parent)
    assert Path(private_probe.__file__).resolve() == snapshot.resolve()
    assert private_probe.ROOT == ROOT
    assert not Path(reader.__file__).is_symlink()
    assert m.digest(Path(reader.__file__)) == m.READER_SHA256


def check():
    retained = json.loads(PAIR.read_text())
    assert len(retained["timelinePasses"][0]["timelines"]) == 6
    assert retained["timelineInventory"] == "protected-six"
    identities = {
        r["GetUniqueId"]["value"]: r["GetName"]["value"]
        for r in retained["timelinePasses"][0]["timelines"]
    }
    assert identities == m.TIMELINES
    assert m.digest(PAIR) == hashlib.sha256(PAIR.read_bytes()).hexdigest()
    try:
        m._pair(PAIR, "0" * 64, lambda: retained, retained["selectedTimelineUid"])
    except RuntimeError as error:
        assert "SHA-256" in str(error)
    else:
        raise AssertionError("bad checkpoint hash accepted")

    # Adapt only an in-memory copy to the required fresh selected-Matrix shape.
    fake_pin = copy.deepcopy(retained)
    fake_pin["selectedTimelineUid"] = m.MATRIX
    current = copy.deepcopy(fake_pin)

    class Timeline:
        def __init__(self, uid, name, owner=None):
            self.uid, self.name, self.owner = uid, name, owner

        def GetUniqueId(self):
            return self.uid

        def GetName(self):
            return self.name

        def DuplicateTimeline(self, name):
            self.owner.rows.append(Timeline("fake-new-uid", name, self.owner))
            return self.owner.rows[-1]

    class Project:
        def __init__(self):
            self.rows = [Timeline(uid, name, self) for uid, name in m.TIMELINES.items()]
            self.selected = m.MATRIX

        def GetUniqueId(self):
            return m.PROJECT

        def GetName(self):
            return "VERA Issue 141 Synthetic Probe 20260930-01a0f318"

        def GetCurrentTimeline(self):
            return next(x for x in self.rows if x.uid == self.selected)

        def GetTimelineByIndex(self, i):
            return self.rows[i - 1]

        def GetTimelineCount(self):
            return len(self.rows)

        def SetCurrentTimeline(self, timeline):
            self.selected = timeline.uid
            return True

    class Manager:
        def __init__(self):
            self.project = project

        def GetCurrentProject(self):
            return self.project

        def SaveProject(self):
            calls.append("SaveProject")
            return True

        def CloseProject(self, item):
            calls.append("CloseProject")
            self.project = None
            return True

        def LoadProject(self, name):
            calls.append(("LoadProject", name))
            self.project = project
            return project

    class Resolve:
        def __init__(self):
            self.manager = Manager()

        def GetProjectManager(self):
            return self.manager

    calls, project = [], Project()
    with tempfile.TemporaryDirectory() as directory:
        pinpath = Path(directory) / "pair.json"
        pinpath.write_text(json.dumps(fake_pin))
        journal = Path(directory) / "journal.jsonl"
        result = m.repeat_reopen(
            Resolve(),
            project,
            pinpath,
            m.digest(pinpath),
            lambda: copy.deepcopy(current),
            journal,
            idle=True,
            controls_unchanged=True,
            context_unchanged=True,
            resolve_build="21.1.0 build 14",
            external_scripting="None",
        )
        assert calls == [
            "SaveProject",
            "CloseProject",
            ("LoadProject", "VERA Issue 141 Synthetic Probe 20260930-01a0f318"),
        ]
        assert result["consistent"] and result["status"] == "stable-pair"
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        assert [x["action"] for x in records[:3]] == [
            "SaveProject",
            "SaveProject",
            "CloseProject",
        ]

        class SaveRefusal(Manager):
            def SaveProject(self):
                calls.append("SaveProject-refused")
                return False

        class RefusingResolve(Resolve):
            def __init__(self):
                self.manager = SaveRefusal()

        failed_journal = Path(directory) / "failed-journal.jsonl"
        try:
            m.repeat_reopen(
                RefusingResolve(),
                project,
                pinpath,
                m.digest(pinpath),
                lambda: copy.deepcopy(current),
                failed_journal,
                idle=True,
                controls_unchanged=True,
                context_unchanged=True,
                resolve_build="21.1.0 build 14",
                external_scripting="None",
            )
        except RuntimeError as error:
            assert "SaveProject refused" in str(error)
        else:
            raise AssertionError("fake SaveProject refusal accepted")
        failure_records = [
            json.loads(line) for line in failed_journal.read_text().splitlines()
        ]
        assert failure_records[-1]["action"] == "SaveProject"
        assert failure_records[-1]["phase"] == "failure"

        duplicate_project = Project()
        duplicate_reads = 0

        def duplicate_observe():
            nonlocal duplicate_reads
            duplicate_reads += 1
            observed = copy.deepcopy(current)
            observed["selectedTimelineUid"] = duplicate_project.selected
            if duplicate_project.GetTimelineCount() == 7:
                observed["timelineInventory"] = "protected-seven"
                source = next(
                    row
                    for row in observed["timelinePasses"][0]["timelines"]
                    if row["GetUniqueId"]["value"] == m.R1
                )
                extra = copy.deepcopy(source)
                extra["GetUniqueId"] = {"value": "fake-new-uid"}
                extra["GetName"] = {"value": m.REPEAT_NAME}
                occurrence_index = 0
                for track in extra.get("tracks", []):
                    for item in track.get("items", []):
                        occurrence_index += 1
                        item["GetUniqueId"] = {
                            "value": f"fake-occurrence-{occurrence_index}"
                        }
                for pass_state in observed["timelinePasses"]:
                    pass_state["timelines"].append(copy.deepcopy(extra))
            return observed

        duplicate_journal = Path(directory) / "duplicate-journal.jsonl"
        duplicate_result = m.second_duplicate(
            duplicate_project,
            pinpath,
            m.digest(pinpath),
            duplicate_observe,
            duplicate_journal,
            idle=True,
            controls_unchanged=True,
            context_unchanged=True,
            resolve_build="21.1.0 build 14",
            external_scripting="None",
        )
        assert duplicate_project.GetTimelineCount() == 7
        assert duplicate_result["oldSixPreserved"]
        assert duplicate_result["duplicateUid"] == "fake-new-uid"
        duplicate_records = [
            json.loads(line) for line in duplicate_journal.read_text().splitlines()
        ]
        assert any(
            x["action"] == "DuplicateTimeline" and x["phase"] == "request"
            for x in duplicate_records
        )

    try:
        m._guard(Project(), m.MATRIX, False, True, True)
    except RuntimeError as error:
        assert "guard" in str(error)
    else:
        raise AssertionError("busy job accepted")
    print("PASS: six inventory/hash, refusal, fake reopen/duplicate, failure journal")


def adapter_shape_check():
    original = copy.deepcopy(m.TIMELINES)
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        output = root / "out" / "issue-141-observation-fake"
        output.mkdir(parents=True)
        pin = json.loads(PAIR.read_text())
        pin["selectedTimelineUid"] = m.MATRIX
        checkpoint = output / "checkpoint.json"
        checkpoint.write_text(json.dumps(pin))
        manifest = output / "manifest.json"
        manifest.write_text("{}")

        class Timeline:
            def __init__(self, uid, name, owner): self.uid, self.name, self.owner = uid, name, owner
            def GetUniqueId(self): return self.uid
            def GetName(self): return self.name
            def GetCurrentTimecode(self): return "00:00:00:00"
            def GetSelectedClips(self): return []
            def GetTrackCount(self, kind): return 0
            def DuplicateTimeline(self, name):
                row = Timeline("fake-new-uid", name, self.owner); self.owner.rows.append(row); return row

        class Project:
            def __init__(self):
                self.rows = [Timeline(uid, name, self) for uid, name in m.TIMELINES.items()]
                self.selected = m.MATRIX
                self.uid, self.queue = m.PROJECT, []
            def GetUniqueId(self): return self.uid
            def GetName(self): return "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
            def GetTimelineCount(self): return len(self.rows)
            def GetTimelineByIndex(self, index): return self.rows[index - 1]
            def GetCurrentTimeline(self): return next(row for row in self.rows if row.uid == self.selected)
            def SetCurrentTimeline(self, row): self.selected = row.uid; return True
            def IsRenderingInProgress(self): return False
            def GetRenderJobList(self): return self.queue
        project = Project()
        probe = SimpleNamespace(
            ROOT=root, PROTECTED_INVENTORY="protected-six",
            PROTECTED_TIMELINE_IDENTITIES=copy.deepcopy(m.TIMELINES),
            sha256=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
            require_current=lambda resolve, config, identity: resolve.manager.project,
            item_evidence=lambda item, expected: {"uid": item},
        )

        class Manager:
            def __init__(self): self.project = project
            def GetCurrentProject(self): return self.project
            def SaveProject(self): return True
            def CloseProject(self, current): self.project = None; return True
            def LoadProject(self, name): self.project = project; return project
        class Resolve:
            manager = Manager()
            def GetProjectManager(self): return self.manager
            def GetProductName(self): return "DaVinci Resolve Studio"
            def GetVersion(self): return m.BUILD
            def GetCurrentPage(self): return "edit"
        resolve = Resolve()

        class Reader:
            PROTECTED_INVENTORY = "protected-six"
            PROTECTED_TIMELINE_IDENTITIES = copy.deepcopy(m.TIMELINES)
            def _manifest(self, config, root, probe): return Path(config["mediaDir"]), {}
            def _read_pair(self, resolve, config, identity, expected, selected, probe):
                value = copy.deepcopy(pin); value["selectedTimelineUid"] = selected
                if project.GetTimelineCount() == 7:
                    source = next(row for row in value["timelinePasses"][0]["timelines"] if row["GetUniqueId"]["value"] == m.R1)
                    extra = copy.deepcopy(source)
                    extra["GetUniqueId"], extra["GetName"] = {"value": "fake-new-uid"}, {"value": m.REPEAT_NAME}
                    for ti, track in enumerate(extra.get("tracks", [])):
                        for ii, item in enumerate(track.get("items", [])): item["GetUniqueId"] = {"value": f"new-{ti}-{ii}"}
                    for state in value["timelinePasses"]: state["timelines"].append(copy.deepcopy(extra))
                    value["timelineInventory"] = m.PROTECTED_SEVEN
                return value
        reader = Reader()
        config = {"action": m.ACTION_DUPLICATE, "externalScriptingSetting": "None",
                  "outputDir": str(output), "projectName": project.GetName(),
                  "repeatCheckpoint": str(checkpoint),
                  "repeatCheckpointSha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
                  "mediaDir": str(output), "manifestSha256": hashlib.sha256(manifest.read_bytes()).hexdigest()}
        config["repeatExpectedContext"] = m._native_context(resolve, project, m.MATRIX, probe, {})
        def refused(candidate):
            with patch.object(m, "_private_reader", return_value=(probe, reader)):
                try: m.run(resolve, candidate, probe=probe)
                except RuntimeError: pass
                else: raise AssertionError("Unsafe repeat adapter request accepted")
            assert project.GetTimelineCount() == 6
        refused(dict(config, repeatCheckpointSha256="0" * 64))
        refused(dict(config, repeatExpectedContext={**config["repeatExpectedContext"], "page": "deliver"}))
        project.queue = ["foreign-job"]
        refused(config)
        project.queue = []
        project.uid = "wrong-project"
        refused(config)
        project.uid = m.PROJECT
        pin = copy.deepcopy(pin)
        pin["timelinePasses"][0]["timelines"].pop()
        pin["timelinePasses"][1]["timelines"].pop()
        checkpoint.write_text(json.dumps(pin))
        config["repeatCheckpointSha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        refused(config)
        pin = json.loads(PAIR.read_text()); pin["selectedTimelineUid"] = m.MATRIX
        checkpoint.write_text(json.dumps(pin))
        config["repeatCheckpointSha256"] = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        with patch.object(m, "_private_reader", return_value=(probe, reader)):
            result = m.run(resolve, config, probe=probe)
        assert result["duplicateUid"] == "fake-new-uid"
        assert all(len(pair["timelinePasses"][0]["timelines"]) == 7 for pair in (result["immediateAfter"], result["after"]))
        assert all(pair["timelineInventory"] == m.PROTECTED_SEVEN for pair in (result["immediateAfter"], result["after"]))
        assert m.TIMELINES == original
        project.rows = [Timeline(uid, name, project) for uid, name in original.items()]
        config["action"] = m.ACTION_REOPEN
        with patch.object(m, "_private_reader", return_value=(probe, reader)):
            reopened = m.run(resolve, config, probe=probe)
        assert reopened["status"] == "stable-pair"
        assert len(reopened["postLoadObservations"]) == 2


def restore_selection_adapter_check():
    target_pin = json.loads((DUPLICATE_EVIDENCE / "pair-01.json").read_text())["pair"]
    current_pin = json.loads((DUPLICATE_EVIDENCE / "pair-03.json").read_text())["pair"]

    class Timeline:
        def __init__(self, uid, name, owner):
            self.uid, self.name, self.owner = uid, name, owner

        def GetUniqueId(self): return self.uid
        def GetName(self): return self.name
        def GetCurrentTimecode(self): return "00:00:00:00"
        def GetSelectedClips(self): return []
        def GetTrackCount(self, kind): return 0

    class Project:
        def __init__(self):
            self.rows = [Timeline(uid, name, self) for uid, name in m.TIMELINES.items()]
            self.selected, self.queue = m.R1, []
            self.set_calls, self.set_result = [], True

        def GetUniqueId(self): return m.PROJECT
        def GetName(self): return "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
        def GetTimelineCount(self): return len(self.rows)
        def GetTimelineByIndex(self, index): return self.rows[index - 1]
        def GetCurrentTimeline(self): return next(row for row in self.rows if row.uid == self.selected)
        def SetCurrentTimeline(self, row):
            self.set_calls.append(row.uid)
            if self.set_result:
                self.selected = row.uid
            return self.set_result
        def IsRenderingInProgress(self): return False
        def GetRenderJobList(self): return self.queue

    project = Project()

    class Manager:
        def __init__(self): self.project = project
        def GetCurrentProject(self): return self.project

    class Resolve:
        def __init__(self): self.manager = Manager()
        def GetProjectManager(self): return self.manager
        def GetProductName(self): return "DaVinci Resolve Studio"
        def GetVersion(self): return m.BUILD
        def GetCurrentPage(self): return "edit"

    resolve = Resolve()
    probe = SimpleNamespace(
        ROOT=None,
        sha256=lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        require_current=lambda current_resolve, config, identity: project,
        item_evidence=lambda item, expected: {"uid": item},
    )

    class Reader:
        def __init__(self):
            self.current_pin = copy.deepcopy(current_pin)
            self.target_pin = copy.deepcopy(target_pin)

        def _manifest(self, config, root, private_probe): return Path(config["mediaDir"]), {}
        def _read_pair(self, resolve, config, identity, expected, selected, private_probe):
            value = copy.deepcopy(self.current_pin if selected == m.R1 else self.target_pin)
            value["selectedTimelineUid"] = selected
            return value

    reader = Reader()

    def write_pair(path, value):
        path.write_text(json.dumps(value, indent=2, sort_keys=True))

    def invoke(config, *, expect_error):
        project.set_calls.clear()
        with patch.object(m, "_private_reader", return_value=(probe, reader)):
            try:
                result = m.run(resolve, config, probe=probe)
            except RuntimeError:
                if not expect_error:
                    raise
                return None
        if expect_error:
            raise AssertionError("unsafe Matrix restoration accepted")
        return result

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        probe.ROOT = root
        output = root / "out" / "issue-141-observation-restore"
        output.mkdir(parents=True)
        manifest = output / "manifest.json"
        manifest.write_text("{}")
        checkpoint = output / "current-r1.json"
        target = output / "target-matrix.json"
        write_pair(checkpoint, current_pin)
        write_pair(target, target_pin)
        project.selected = m.MATRIX
        target_context = m._native_context(resolve, project, m.MATRIX, probe, {})
        project.selected = m.R1
        current_context = m._native_context(resolve, project, m.R1, probe, {})
        config = {
            "action": m.ACTION_RESTORE_SELECTION,
            "externalScriptingSetting": "None",
            "outputDir": str(output),
            "projectName": project.GetName(),
            "repeatCheckpoint": str(checkpoint),
            "repeatCheckpointSha256": m.digest(checkpoint),
            "repeatExpectedContext": current_context,
            "restoreTargetPair": str(target),
            "restoreTargetPairSha256": m.digest(target),
            "restoreTargetContext": target_context,
            "mediaDir": str(output),
            "manifestSha256": m.digest(manifest),
        }

        result = invoke(config, expect_error=False)
        assert result["status"] == "restored-selection"
        assert result["pairExactlyEqual"] and result["contextExactlyEqual"]
        assert result["after"] == target_pin
        assert project.set_calls == [m.MATRIX]

        project.selected = m.R1
        stale_current = copy.deepcopy(current_pin)
        stale_current["timelinePasses"][0]["timelines"][0]["GetName"] = {"value": "stale"}
        reader.current_pin = stale_current
        invoke(config, expect_error=True)
        assert project.set_calls == []
        reader.current_pin = current_pin

        target.write_text(json.dumps({**target_pin, "selectedTimelineUid": m.MATRIX}))
        invoke(config, expect_error=True)
        assert project.set_calls == []
        write_pair(target, target_pin)
        config["restoreTargetPairSha256"] = m.digest(target)

        wrong_uid = copy.deepcopy(target_pin)
        wrong_uid["selectedTimelineUid"] = m.R1
        write_pair(target, wrong_uid)
        config["restoreTargetPairSha256"] = m.digest(target)
        invoke(config, expect_error=True)
        assert project.set_calls == []
        write_pair(target, target_pin)
        config["restoreTargetPairSha256"] = m.digest(target)

        project.queue = ["foreign-job"]
        project.selected = m.R1
        invoke(config, expect_error=True)
        assert project.set_calls == []
        project.queue = []

        project.selected = m.R1
        project.set_result = False
        invoke(config, expect_error=True)
        assert project.set_calls == [m.MATRIX]
        assert project.selected == m.R1


def selected_context_regression():
    directory = ROOT / "out/issue-141-observation-20260930-01a0f318/r1-repeat-duplicate-20261002T122220.047704Z"
    before = json.loads((directory / "pair-01.json").read_text())["pair"]
    selected = json.loads((directory / "pair-03.json").read_text())["pair"]
    original = copy.deepcopy(selected)
    assert m._r1_signature(before) == m._r1_signature(selected)
    assert selected == original, "comparison mutated retained raw fields"
    for field in ("GetUniqueId", "GetSourceStartFrame", "GetSourceEndFrame", "GetStart", "GetEnd", "GetClipEnabled", "GetMarkers"):
        changed = copy.deepcopy(selected)
        row = next(row for row in changed["timelinePasses"][0]["timelines"] if row["GetUniqueId"]["value"] == m.R1)
        item = row["tracks"][0]["items"][0]
        item[field] = {"value": "unrelated-change"}
        assert m._r1_signature(before) != m._r1_signature(changed), field
    changed = copy.deepcopy(selected)
    row = next(row for row in changed["timelinePasses"][0]["timelines"] if row["GetUniqueId"]["value"] == m.R1)
    item = next(track for track in row["tracks"] if track["type"] == "audio")["items"][0]
    item["GetProperties"]["value"]["UnlistedAudioProperty"] = 1
    assert m._r1_signature(before) != m._r1_signature(changed)


if __name__ == "__main__":
    snapshot_import_smoke()
    check()
    adapter_shape_check()
    restore_selection_adapter_check()
    selected_context_regression()
    print("PASS: R1 fake API guards and real selected-context regression; no native dispatch")
