"""Focused fake-Resolve execution of the guarded outer recovery."""

import copy
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
SOURCE = HERE / "render-outer-recovery.py"

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

m = load("render_outer_recovery", SOURCE)
probe = load("outer_probe", HERE / "probe.py")

class Timeline:
    def __init__(self, uid, name): self.uid, self.name = uid, name
    def GetUniqueId(self): return self.uid
    def GetName(self): return self.name

class Project:
    def __init__(self, base, mode="ok"):
        reader = load("outer_reader_constants", HERE / "r4-range-repair.py")
        self.uid, self.name = m.PROJECT_ID, m.PROJECT_NAME
        self.timelines = [Timeline(uid, name) for uid, name in reader.PROTECTED_TIMELINE_IDENTITIES.items()]
        self.presets, self.jobs, self.rendering = base + [m.PRESET], [], False
        self.mode, self.loads, self.deletes = mode, 0, 0
    def GetUniqueId(self): return self.uid
    def GetName(self): return self.name
    def GetCurrentTimeline(self): return self.timelines[0]
    def GetTimelineCount(self): return len(self.timelines)
    def GetTimelineByIndex(self, i): return self.timelines[i-1]
    def IsRenderingInProgress(self): return self.rendering
    def GetRenderJobList(self): return list(self.jobs)
    def GetRenderPresetList(self): return list(self.presets)
    def GetCurrentRenderFormatAndCodec(self):
        return {"format": "mov", "codec": "DNxHD" if self.mode == "wrong-format" else "H264"}
    def GetCurrentRenderMode(self): return 2 if self.mode == "wrong-mode" else 1
    def LoadRenderPreset(self, name):
        self.loads += 1
        return self.mode != "load-false"
    def DeleteRenderPreset(self, name):
        self.deletes += 1
        self.presets.remove(name)
        return True

class Manager:
    def __init__(self, project): self.project = project
    def GetCurrentProject(self): return self.project

class Resolve:
    def __init__(self, project): self.project = project
    def GetProjectManager(self): return Manager(self.project)
    def GetProductName(self): return "DaVinci Resolve Studio"
    def GetVersion(self): return m.BUILD

class Probe:
    ROOT = probe.ROOT
    sha256 = staticmethod(probe.sha256)
    errors = staticmethod(probe.errors)
    require_current = staticmethod(probe.require_current)


def check():
    compile(SOURCE.read_bytes(), str(SOURCE), "exec")
    root = Path(probe.ROOT).resolve()
    out = root / "out/issue-141-observation-20260930-01a0f318"
    attempt = out / m.ATTEMPT
    before_path, after_path = attempt / "full-pair-004.json", attempt / "full-pair-005.json"
    before, after = json.loads(before_path.read_text()), json.loads(after_path.read_text())
    original_journal, xml = attempt / "journal.jsonl", attempt / f"{m.PRESET}.drp/{m.PRESET}.xml"
    rows = [json.loads(line) for line in original_journal.read_text().splitlines()]
    base = next(r["value"] for r in rows if r.get("method") == "GetRenderPresetList" and r.get("phase") == "return")
    base = [name for name in base if name != m.PRESET]
    checkpoint_source = out / "av-calibration-checkpoint-after-r1-move-20261001T061824.json"
    manifest = root / "out/issue-141-media-20260930-01a0f318/manifest.json"
    config = {
        "action": "render-outer-recovery", "externalScriptingSetting": "None",
        "outputDir": str(out), "timelineInventory": "protected-six",
        "projectName": m.PROJECT_NAME, "mediaDir": str(manifest.parent),
        "manifestSha256": probe.sha256(manifest),
        "originalAttemptPath": str(attempt), "originalBeforePairPath": str(before_path),
        "originalAfterPairPath": str(after_path),
        "originalJournalSha256": probe.sha256(original_journal), "originalXmlSha256": probe.sha256(xml),
        "originalBeforePairSha256": probe.sha256(before_path), "originalAfterPairSha256": probe.sha256(after_path),
    }
    cp = copy.deepcopy(after)
    reader = load("outer_real_reader", HERE / "r4-range-repair.py")
    class FakeReader:
        def __getattr__(self, name): return getattr(reader, name)
        def _read_pair(self, resolve, cfg, identity, expected, uid, p):
            _, expected_actual = reader._manifest(cfg, root, p)
            assert expected == expected_actual and expected_actual
            # Keep the real project's exact context and six-timeline checks; replace capture I/O only.
            reader._context(resolve, cfg, identity, p, uid)
            value = copy.deepcopy(cp)
            if mode == "wrong-visible":
                value["timelinePasses"][0]["deliberateMismatch"] = True
                value["timelinePasses"][1]["deliberateMismatch"] = True
            if mode == "track-drift":
                value["timelinePasses"][0]["timelines"][0]["deliberateMismatch"] = True
                value["timelinePasses"][1]["timelines"][0]["deliberateMismatch"] = True
            return value
    for mode in ("ok", "load-false", "wrong-format", "wrong-mode", "wrong-visible", "track-drift", "wrong-project", "queued-job", "rendering", "preset-drift", "wrong-checkpoint-hash"):
        project = Project(base, mode)
        if mode == "wrong-project": project.uid = "wrong-project"
        if mode == "queued-job": project.jobs = [{"JobId": "unrelated"}]
        if mode == "rendering": project.rendering = True
        if mode == "preset-drift": project.presets.append("unrelated")
        resolve, p = Resolve(project), Probe()
        with tempfile.TemporaryDirectory(dir=attempt) as td:
            scratch = Path(td)
            pin = scratch / "checkpoint.json"
            pin.write_text(json.dumps(cp))
            cfg = {**config, "checkpointPath": str(pin), "checkpointName": pin.name,
                   "checkpointSha256": probe.sha256(pin), "journalPath": str(scratch / "recovery.jsonl")}
            if mode == "wrong-checkpoint-hash": cfg["checkpointSha256"] = "0" * 64
            if mode != "ok":
                try: m.run(resolve, cfg, probe=p, reader=FakeReader())
                except RuntimeError: pass
                else: raise AssertionError("false LoadRenderPreset accepted")
                assert project.deletes == 0
                assert project.loads == (1 if mode in {"load-false", "wrong-format", "wrong-mode"} else 0), mode
            else:
                result = m.run(resolve, cfg, probe=p, reader=FakeReader())
                assert result["status"] == "original-render-settings-restored"
                assert project.loads == 1 and project.deletes == 1 and project.presets == base
                entries = [json.loads(line) for line in (scratch / "recovery.jsonl").read_text().splitlines()]
                assert all(Path(row["value"]["path"]).is_file() and row["value"]["sha256"] == probe.sha256(row["value"]["path"]) for row in entries if row["method"] == "FullPair")
    print("PASS: [REDACTED] run() restored and deleted only its preset; false load retained it; real protected context, reader manifest, and pair validators ran")

if __name__ == "__main__": check()
