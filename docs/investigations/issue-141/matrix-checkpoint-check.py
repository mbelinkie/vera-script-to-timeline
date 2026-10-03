"""End-to-end fake checks for the Matrix checkpoint (never calls Resolve)."""

import hashlib
import importlib.util
import json
import shutil
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "matrix_checkpoint", HERE / "matrix-checkpoint.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
R4_EVIDENCE = HERE / "evidence/r4-post-append-read-only"
MATRIX_EVIDENCE = HERE / "evidence/matrix-finalize-success"
SOURCE = HERE / "inputs/relink/base.mov"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def replace_paths(value, old, new):
    if isinstance(value, dict):
        return {key: replace_paths(child, old, new) for key, child in value.items()}
    if isinstance(value, list):
        return [replace_paths(child, old, new) for child in value]
    if isinstance(value, str):
        return value.replace(old, new)
    return value


class Probe:
    ROOT = None
    mode = "normal"
    observations = 0

    @staticmethod
    def sha256(path):
        return sha(path)

    @staticmethod
    def errors(value):
        errors = []
        if isinstance(value, dict):
            if "error" in value:
                errors.append(value["error"])
            for child in value.values():
                errors.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                errors.extend(Probe.errors(child))
        return errors

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.GetProjectManager().GetCurrentProject()
        if Probe.mode == "project-drift" and project.state.selection_calls >= 1:
            project.name = "drifted project"
        if (
            project.uid != identity["projectId"]
            or project.name != config["projectName"]
        ):
            raise RuntimeError("project identity drift")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        state = resolve.state
        Probe.observations += 1
        result = deepcopy(
            state.r4_observation
            if state.selected == module.R4_UID
            else state.observation
        )
        if Probe.mode == "content-delta" and state.selected == module.MATRIX_UID:
            result["timelines"][1]["GetName"]["value"] = "changed historical timeline"
        if (
            Probe.mode == "unstable-after-select"
            and state.selected == module.MATRIX_UID
        ):
            result["GetSettings"]["value"]["read"] = Probe.observations
        return result

    @staticmethod
    def _r4_pool_inventory(project, expected):
        del expected
        return deepcopy(project.state.inventory)


class Timeline:
    def __init__(self, uid, name):
        self.uid, self.name = uid, name

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name


class Project:
    def __init__(self, state):
        self.state = state
        self.uid = module.PROJECT_ID
        self.name = state.project_name
        self.timelines = [
            Timeline(module.R4_UID, module.R4_NAME),
            Timeline(module.MATRIX_UID, module.MATRIX_NAME),
            Timeline(module.BASELINE_UID, "VERA 141 Baseline"),
            Timeline(module.R1_UID, "VERA 141 R1 identity"),
        ]

    def GetUniqueId(self):
        return self.uid

    def GetName(self):
        return self.name

    def GetTimelineCount(self):
        return len(self.timelines)

    def GetTimelineByIndex(self, index):
        return self.timelines[index - 1]

    def GetCurrentTimeline(self):
        return next(
            timeline
            for timeline in self.timelines
            if timeline.uid == self.state.selected
        )

    def SetCurrentTimeline(self, timeline):
        self.state.selection_calls += 1
        call = self.state.selection_calls
        if call == 1 and self.state.selection_mode in {
            "false-after-change",
            "raise-after-change",
        }:
            self.state.selected = timeline.uid
            if self.state.selection_mode == "raise-after-change":
                raise RuntimeError("injected selection exception after context changed")
            return False
        if call == 1 and self.state.selection_mode == "false-no-change":
            return False
        self.state.selected = timeline.uid
        return True


class Manager:
    def __init__(self, state):
        self.state = state

    def GetCurrentProject(self):
        return Project(self.state)


class Resolve:
    def __init__(self, state):
        self.state = state

    def GetProjectManager(self):
        return Manager(self.state)

    @staticmethod
    def GetProductName():
        return "DaVinci Resolve Studio"

    @staticmethod
    def GetVersion():
        return module.BUILD


class State:
    def __init__(
        self, config, observation, r4_observation, inventory, selection_mode="normal"
    ):
        self.project_name = config["projectName"]
        self.selected = module.R4_UID
        self.observation = observation
        self.r4_observation = r4_observation
        self.inventory = inventory
        self.selection_mode = selection_mode
        self.selection_calls = 0


def setup(root, *, selection_mode="normal", mode="normal"):
    out = root / "out"
    output = out / "issue-141-observation-test"
    media = out / "issue-141-media-test"
    output.mkdir(parents=True)
    media.mkdir()
    (media / "relink").mkdir()
    shutil.copyfile(SOURCE, media / "relink/base.mov")
    media_path = str(media / "relink/base.mov")

    r4_capture = json.loads((R4_EVIDENCE / module.R4_CAPTURE_NAME).read_text())
    r4_pool = json.loads((R4_EVIDENCE / module.R4_POOL_NAME).read_text())
    matrix_capture = json.loads(
        (MATRIX_EVIDENCE / module.MATRIX_CAPTURE_NAME).read_text()
    )
    old_media = r4_capture["passes"][0]["timelines"]
    old_path = None
    for timeline in old_media:
        for track in timeline.get("tracks", []):
            for item in track.get("items", []):
                candidate = (
                    item.get("GetMediaPoolItem", {})
                    .get("GetClipProperty", {})
                    .get("value", {})
                    .get("File Path")
                )
                if candidate:
                    old_path = candidate
    assert old_path
    r4_capture = replace_paths(r4_capture, old_path, media_path)
    r4_pool = replace_paths(r4_pool, old_path, media_path)
    r4_capture = replace_paths(
        r4_capture, "<synthetic-media>/relink/base.mov", media_path
    )
    r4_pool = replace_paths(r4_pool, "<synthetic-media>/relink/base.mov", media_path)
    validator = module._r4_module()
    live_r4 = deepcopy(r4_capture["passes"][0])
    inventory = deepcopy(r4_pool["passes"][0])
    observation = deepcopy(matrix_capture["passes"][0])
    observation["timelines"].append(
        next(
            row
            for row in live_r4["timelines"]
            if row.get("GetUniqueId", {}).get("value") == module.R4_UID
        )
    )
    # Both captures are complete project snapshots. Keep R4 state current while
    # using the saved Matrix capture for the three historic timelines/settings.
    r4_row = next(
        row
        for row in observation["timelines"]
        if row.get("GetUniqueId", {}).get("value") == module.R4_UID
    )
    observation["timelines"].remove(r4_row)
    observation["timelines"].append(
        next(
            row
            for row in live_r4["timelines"]
            if row.get("GetUniqueId", {}).get("value") == module.R4_UID
        )
    )

    # Pin temporary fixtures by their exact bytes while preserving the real
    # validator formats and the cross-reference in the pool capture.
    write(output / module.R4_CAPTURE_NAME, r4_capture)
    module.R4_CAPTURE_SHA256 = sha(output / module.R4_CAPTURE_NAME)
    validator.CAPTURE_SHA256 = module.R4_CAPTURE_SHA256
    r4_pool["capture"]["sha256"] = module.R4_CAPTURE_SHA256
    r4_pool["capture"]["capturePath"] = str(output / module.R4_CAPTURE_NAME)
    write(output / module.R4_POOL_NAME, r4_pool)
    module.R4_POOL_SHA256 = sha(output / module.R4_POOL_NAME)
    validator.POOL_SHA256 = module.R4_POOL_SHA256
    module._r4_module = lambda: validator
    write(output / module.MATRIX_CAPTURE_NAME, matrix_capture)
    module.MATRIX_CAPTURE_SHA256 = sha(output / module.MATRIX_CAPTURE_NAME)

    manifest = {
        "kind": "generated-synthetic-inputs-not-Resolve-evidence",
        "files": [
            {"path": "relink/base.mov", "sha256": module._r4_module().MEDIA_SHA256}
        ],
    }
    write(media / "manifest.json", manifest)
    config = {
        "action": "matrix-checkpoint",
        "externalScriptingSetting": "None",
        "projectName": r4_capture["passes"][0]["projectName"],
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": sha(media / "manifest.json"),
    }

    finalizer_journal = output / module.FINALIZE_JOURNAL_NAME
    finalizer_journal.write_text(
        "\n".join(
            [
                json.dumps({"method": "SaveProject", "phase": "request", "value": {}}),
                json.dumps({"method": "SaveProject", "phase": "return", "value": True}),
                json.dumps(
                    {
                        "method": "R4Finalize",
                        "phase": "complete",
                        "value": {"status": "saved-pinned-r4-state"},
                    }
                ),
            ]
        )
        + "\n"
    )
    module.FINALIZE_JOURNAL_SHA256 = sha(finalizer_journal)
    result_root = root / "finalizer-result"
    result_root.mkdir()
    write(
        result_root / module.FINALIZE_RESULT_NAME, {"status": "saved-pinned-r4-state"}
    )
    module.FINALIZE_RESULT_SHA256 = sha(result_root / module.FINALIZE_RESULT_NAME)
    module.FINALIZE_RESULT_ROOT = result_root

    state = State(config, observation, live_r4, inventory, selection_mode)
    Probe.ROOT, Probe.mode, Probe.observations = root, mode, 0
    return output, config, state


def run_case(
    *,
    selection_mode="normal",
    mode="normal",
    mutate_pin=False,
    wrong_uid=False,
    drift=False,
):
    with tempfile.TemporaryDirectory() as temporary:
        output, config, state = setup(
            Path(temporary), selection_mode=selection_mode, mode=mode
        )
        if mutate_pin:
            paths = {
                "r4": output / module.R4_CAPTURE_NAME,
                "pool": output / module.R4_POOL_NAME,
                "matrix": output / module.MATRIX_CAPTURE_NAME,
                "finalizer-journal": output / module.FINALIZE_JOURNAL_NAME,
                "finalizer-result": module.FINALIZE_RESULT_ROOT
                / module.FINALIZE_RESULT_NAME,
            }
            paths[mutate_pin].write_text("{}")
        if wrong_uid:
            state.selected = "wrong-uid"
        if drift:
            Probe.mode = "project-drift"
        try:
            result = module.run(Resolve(state), config, probe=Probe)
        except Exception as error:
            refusal = json.loads(
                next(output.glob("matrix-checkpoint-*-result.json")).read_text()
            )
            return output, state, None, str(error), refusal
        matrix = json.loads((output / result["matrixObservation"]).read_text())
        return output, state, (result, matrix), None, None


def check():
    original = (
        module.R4_CAPTURE_SHA256,
        module.R4_POOL_SHA256,
        module.MATRIX_CAPTURE_SHA256,
        module.FINALIZE_JOURNAL_SHA256,
        module.FINALIZE_RESULT_SHA256,
        module.FINALIZE_RESULT_ROOT,
    )
    try:
        _output, state, success, error, _ = run_case()
        result, matrix = success
        assert error is None and result["status"] == "selected-matrix-checkpoint"
        assert state.selected == module.MATRIX_UID and state.selection_calls == 1
        assert matrix["selectedTimelineUid"] == module.MATRIX_UID
        assert len(matrix["timelinePasses"]) == len(matrix["poolPasses"]) == 2

        for kwargs in (
            {"mutate_pin": "r4"},
            {"mutate_pin": "pool"},
            {"mutate_pin": "matrix"},
            {"mutate_pin": "finalizer-journal"},
            {"mutate_pin": "finalizer-result"},
            {"wrong_uid": True},
        ):
            _, state, result, error, _ = run_case(**kwargs)
            assert error and result is None and state.selection_calls == 0

        for mode in ("false-after-change", "raise-after-change"):
            _, state, result, error, refusal = run_case(selection_mode=mode)
            assert error and result is None and state.selected == module.R4_UID
            assert state.selection_calls == 2
            assert refusal["restoredR4"]["selectedTimelineUid"] == module.R4_UID

        for mode in ("content-delta", "unstable-after-select"):
            _, state, result, error, refusal = run_case(mode=mode)
            assert error and result is None and state.selected == module.R4_UID
            assert state.selection_calls == 2
            if mode == "content-delta":
                assert refusal["evidence"]["differences"]

        _, state, result, error, refusal = run_case(drift=True)
        assert error and result is None and state.selection_calls == 1
        assert state.selected == module.MATRIX_UID
        assert refusal["restoredR4"]["error"]
    finally:
        (
            module.R4_CAPTURE_SHA256,
            module.R4_POOL_SHA256,
            module.MATRIX_CAPTURE_SHA256,
            module.FINALIZE_JOURNAL_SHA256,
            module.FINALIZE_RESULT_SHA256,
            module.FINALIZE_RESULT_ROOT,
        ) = original
    print(
        "Matrix checkpoint end-to-end fake acceptance passed (no live Resolve evidence)"
    )


if __name__ == "__main__":
    check()
