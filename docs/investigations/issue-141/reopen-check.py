"""Guarded matrix-reopen fake-native checks; never calls Resolve."""

import json
import tempfile
from pathlib import Path

import probe

PROJECT_ID = "approved-project"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe reopen-check"
IDS = (probe.BASELINE_ID, probe.R1_ID, probe.MATRIX_PARTIAL_ID)
ENVIRONMENT = {"version": probe.CONTEXT_ENVIRONMENT}
PASS = {
    "projectId": PROJECT_ID,
    "timelines": [
        {"GetUniqueId": {"value": timeline_id}, "GetName": {"value": name}}
        for timeline_id, name in zip(
            IDS,
            (probe.TIMELINE, "VERA 141 R1 identity", probe.MATRIX_NAME),
            strict=True,
        )
    ],
}


class Timeline:
    def __init__(self, uid, name):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class Folder:
    def GetClipList(self):
        return []

    def GetSubFolderList(self):
        return []


class Pool:
    def GetRootFolder(self):
        return Folder()


class Project:
    def __init__(self, uid=PROJECT_ID, name=PROJECT_NAME):
        self.uid, self.name = uid, name
        self.timelines = [
            Timeline(uid, label)
            for uid, label in zip(
                IDS,
                (probe.TIMELINE, "VERA 141 R1 identity", probe.MATRIX_NAME),
                strict=True,
            )
        ]
        self.current = self.timelines[-1]
        self.selections = 0

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetCurrentTimeline(self):
        return self.current

    def SetCurrentTimeline(self, timeline):
        self.selections += 1
        self.current = timeline
        return True

    def GetMediaPool(self):
        return Pool()


class Handoff(Project):
    def __init__(self, uid="handoff", name="Untitled Project", count=0):
        super().__init__(uid, name)
        self.timelines = []
        self.count = count

    def GetTimelineCount(self):
        return self.count


class Manager:
    def __init__(self, *, handoffs=(None, None), loaded=None, current_loaded=None):
        self.project = Project()
        self.handoffs = list(handoffs)
        self.loaded = loaded or Project()
        self.current_loaded = current_loaded or self.loaded
        self.mutations = []
        self.handoff_reads = 0

    def GetCurrentProject(self):
        if self.project is None and self.handoff_reads < len(self.handoffs):
            result = self.handoffs[self.handoff_reads]
            self.handoff_reads += 1
            return result
        return self.project

    def SaveProject(self):
        self.mutations.append("SaveProject")
        return True

    def CloseProject(self, project):
        self.mutations.append(("CloseProject", project.GetUniqueId()))
        self.project = None
        return True

    def LoadProject(self, name):
        self.mutations.append(("LoadProject", name))
        self.project = self.current_loaded
        return self.loaded


class Resolve:
    def __init__(self, manager):
        self.manager = manager

    def GetProjectManager(self):
        return self.manager


def run_case(
    *, handoffs=(None, None), loaded=None, current_loaded=None, changed_fresh=False
):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        (output / "prepared.json").write_text(
            json.dumps(
                {
                    "identity": {
                        "projectId": PROJECT_ID,
                        "projectName": PROJECT_NAME,
                        "baselineTimelineId": probe.BASELINE_ID,
                    },
                    "manifestSha256": "manifest",
                    "environment": {"version": probe.CONTEXT_ENVIRONMENT},
                }
            ),
            encoding="utf-8",
        )
        pinned_path = output / probe.PICTURE_CAPTURE
        pinned_path.write_text(
            json.dumps(
                {
                    "consistency": "equal-adjacent-reads",
                    "passes": [PASS, PASS],
                }
            ),
            encoding="utf-8",
        )
        old_hash = probe.PICTURE_CAPTURE_SHA256
        probe.PICTURE_CAPTURE_SHA256 = probe.sha256(pinned_path)
        manager = Manager(
            handoffs=handoffs, loaded=loaded, current_loaded=current_loaded
        )
        captures = 0

        def capture(_resolve, _config, _identity, _expected, _output, stamp, _env):
            nonlocal captures
            captures += 1
            value = PASS
            if changed_fresh and captures == 1:
                value = {**PASS, "changed": True}
            path = output / f"capture-{stamp}.json"
            path.write_text(json.dumps({"passes": [value, value]}), encoding="utf-8")
            return {"status": "equal-adjacent-reads", "capturePath": str(path)}

        old_capture = probe.capture
        probe.capture = capture
        try:
            result = probe.matrix_reopen(
                Resolve(manager),
                {
                    "action": "matrix-reopen",
                    "projectName": PROJECT_NAME,
                    "manifestSha256": "manifest",
                },
                {"projectId": PROJECT_ID, "projectName": PROJECT_NAME},
                {},
                output,
                "fake",
                ENVIRONMENT,
            )
            return result, manager
        finally:
            probe.capture = old_capture
            probe.PICTURE_CAPTURE_SHA256 = old_hash


result, manager = run_case()
assert result["status"] == "equal-adjacent-reads", result
assert manager.mutations == [
    "SaveProject",
    ("CloseProject", PROJECT_ID),
    ("LoadProject", PROJECT_NAME),
], manager.mutations

result, manager = run_case(handoffs=(Handoff(), Handoff()))
assert result["status"] == "equal-adjacent-reads", result

for bad_handoffs in (
    (Handoff(count=1), Handoff(count=1)),
    ("unreadable", "unreadable"),
    (Handoff(), Handoff(uid="changed")),
):
    result, manager = run_case(handoffs=bad_handoffs)
    assert result["status"] == "matrix-reopen-refused", result
    assert not any(
        isinstance(call, tuple) and call[0] == "LoadProject"
        for call in manager.mutations
    ), manager.mutations

wrong_loaded = Project(uid="wrong-project")
result, manager = run_case(loaded=wrong_loaded)
assert result["status"] == "matrix-reopen-refused", result
assert wrong_loaded.selections == 0
assert all("-reopened" not in capture["capturePath"] for capture in result["captures"])

wrong_current = Project(uid="wrong-current-project")
result, manager = run_case(current_loaded=wrong_current)
assert result["status"] == "matrix-reopen-refused", result
assert wrong_current.selections == 0
assert all("-reopened" not in capture["capturePath"] for capture in result["captures"])

result, manager = run_case(changed_fresh=True)
assert result["status"] == "matrix-reopen-refused", result
assert manager.mutations == [], manager.mutations

print("matrix reopen fake-native checks passed")
