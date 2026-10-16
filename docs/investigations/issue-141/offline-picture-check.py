"""Focused offline-picture guard/restoration check; no Resolve evidence."""

import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location(
    "offline_picture", HERE / "offline-picture.py"
)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class Native:
    def __init__(self, mode):
        self.mode, self.calls, self.timecode = mode, [], "00:00:01:00"
        self.drift = False

    def GetCurrentTimeline(self):
        return self

    def GetUniqueId(self):
        return "different" if self.drift else MODULE.R4_UID

    def GetCurrentTimecode(self):
        return self.timecode

    def SetCurrentTimecode(self, value):
        self.calls.append(("SetCurrentTimecode", value))
        self.timecode = value
        return True

    def ExportCurrentFrameAsStill(self, path):
        self.calls.append(("ExportCurrentFrameAsStill", path))
        if self.mode == "export-false":
            return False
        Path(path).write_bytes(b"\x89PNG\r\n\x1a\nsynthetic-fake-not-real-image")
        self.drift = self.mode == "context-drift"
        return True

    def GetProductName(self):
        return "DaVinci Resolve Studio"

    def GetVersion(self):
        return [21, 1, 0, 14, ""]

    def GetCurrentPage(self):
        return "edit"


def state(mode):
    invalid_range = mode == "out-of-program-range"
    return {
        "state": "changed" if mode == "state-drift" else "offline",
        "timelines": [
            {
                "GetUniqueId": {"value": MODULE.R4_UID},
                "GetStartTimecode": {
                    "value": "01:00:00:00" if invalid_range else "00:00:00:00"
                },
                "GetStartFrame": {"value": 90000 if invalid_range else 0},
                "GetEndFrame": {"value": 90000 if invalid_range else 199},
            }
        ],
    }


class Probe:
    @staticmethod
    def sha256(path):
        return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    @staticmethod
    def require_current(resolve, *_):
        return resolve

    @staticmethod
    def errors(_):
        return []

    @staticmethod
    def observe(resolve, *_):
        return state(resolve.mode)

    @staticmethod
    def _r4_pool_inventory(*_):
        return {"pool": "offline"}

    @staticmethod
    def write_json(path, value):
        with path.open("x") as stream:
            json.dump(value, stream)


for mode in (
    "success",
    "state-drift",
    "export-false",
    "context-drift",
    "out-of-program-range",
):
    with tempfile.TemporaryDirectory() as directory:
        output = Path(directory)
        for name, pinned in (
            (
                MODULE.CAPTURE_NAME,
                state(
                    "out-of-program-range"
                    if mode == "out-of-program-range"
                    else "success"
                ),
            ),
            (MODULE.POOL_NAME, {"pool": "offline"}),
        ):
            path = output / name
            path.write_text(json.dumps({"passes": [pinned, pinned]}))
            if name == MODULE.CAPTURE_NAME:
                MODULE.CAPTURE_SHA = Probe.sha256(path)
            else:
                MODULE.POOL_SHA = Probe.sha256(path)
        native = Native(mode)
        result = MODULE.run(
            native,
            {"action": "offline-picture"},
            {"projectId": "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"},
            {},
            output,
            "test",
            {"fake": True},
            probe=Probe,
        )
        if mode == "success":
            assert result["status"] == "offline-picture-candidates-retained"
            assert len(result["samples"]) == 2 and result["restoredPlayhead"]
            assert native.timecode == "00:00:01:00"
            assert [
                call[1] for call in native.calls if call[0] == "SetCurrentTimecode"
            ] == ["00:00:00:00", "00:00:02:00", "00:00:01:00"]
        else:
            assert result["status"] == "offline-picture-refused"
            if mode in {"state-drift", "out-of-program-range"}:
                assert native.calls == []
            elif mode == "export-false":
                assert native.timecode == "00:00:01:00" and result["restoredPlayhead"]
            else:
                assert not result["restoredPlayhead"]
                assert len(native.calls) == 2
print("Offline picture fake guards passed (no live Resolve evidence)")
