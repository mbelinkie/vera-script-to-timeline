"""Stdlib fake acceptance checks for cache-restore.py."""

import hashlib
import importlib.util
import json
import tempfile
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location(
    "cache_restore", HERE / "cache-restore.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def _ok(condition, message):
    if not condition:
        raise AssertionError(message)


def _base_pass(cache_value):
    timelines = []
    for name, uid in module.TIMELINES.items():
        timelines.append(
            {
                "GetName": {"value": name},
                "GetUniqueId": {"value": uid},
                "GetSettings": {"value": {module.CACHE_KEY: cache_value}},
                "GetMarkers": {"value": {"17": {"range": [1, 2]}}},
            }
        )
    return {
        "projectId": module.PROJECT_ID,
        "projectName": "VERA Issue 141 Synthetic Probe fake",
        "GetSettings": {"value": {module.CACHE_KEY: cache_value}},
        "timelines": timelines,
        "tupleReadback": [1, 2],
    }


class Probe:
    ROOT = None

    @staticmethod
    def sha256(path):
        return hashlib.file_digest(Path(path).open("rb"), "sha256").hexdigest()

    @staticmethod
    def errors(value):
        found = []
        if isinstance(value, dict):
            if "error" in value:
                found.append(value["error"])
            for child in value.values():
                found.extend(Probe.errors(child))
        elif isinstance(value, list):
            for child in value:
                found.extend(Probe.errors(child))
        return found

    @staticmethod
    def require_current(resolve, config, identity):
        project = resolve.project
        if (
            project.uid != identity["projectId"]
            or project.name != config["projectName"]
        ):
            raise RuntimeError("wrong project identity")
        return project

    @staticmethod
    def observe(resolve, config, identity, expected):
        del config, identity, expected
        resolve.project.reads += 1
        value = deepcopy(resolve.project.snapshot)
        value["tupleReadback"] = tuple(value["tupleReadback"])
        for timeline in value["timelines"]:
            markers = timeline["GetMarkers"]["value"]
            timeline["GetMarkers"]["value"] = {
                int(key): marker for key, marker in markers.items()
            }
        return value


class Project:
    def __init__(self, snapshot, setter="apply", uid=None):
        self.snapshot = deepcopy(snapshot)
        self.uid = uid or module.PROJECT_ID
        self.name = "VERA Issue 141 Synthetic Probe fake"
        self.setter = setter
        self.reads = 0
        self.calls = []
        self.current = type(
            "Timeline", (), {"GetUniqueId": lambda _self: module.MATRIX_ID}
        )()

    def GetCurrentTimeline(self):
        return self.current

    def SetSetting(self, key, value):
        self.calls.append((key, value))
        if self.setter == "raise":
            raise RuntimeError("injected setter failure")
        if self.setter == "partial":
            for path in module.CACHE_PATHS[:1]:
                module._set_setting(self.snapshot, path, value)
            return False
        for path in module.CACHE_PATHS:
            module._set_setting(self.snapshot, path, value)
        if self.setter == "zero":
            return 0
        return True


class Resolve:
    def __init__(self, project):
        self.project = project

    @staticmethod
    def GetProductName():
        return "DaVinci Resolve Studio"

    @staticmethod
    def GetVersion():
        return module.BUILD


def _capture(path, observation):
    value = {
        "consistency": "equal-adjacent-reads",
        "captureFailure": None,
        "passes": [deepcopy(observation), deepcopy(observation)],
    }
    path.write_text(json.dumps(value), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _setup(root, *, stable=None, saved=None):
    out = root / "out"
    output = out / "issue-141-observation-fake"
    media = out / "issue-141-media-fake"
    output.mkdir(parents=True)
    media.mkdir()
    cache = output / "storage" / "cache"
    cache.mkdir(parents=True)
    stable = stable or _base_pass("CacheClip")
    saved = saved or _base_pass(str(cache))
    stable_hash = _capture(output / module.STABLE_NAME, stable)
    saved_hash = _capture(output / module.SAVED_NAME, saved)
    manifest = {"kind": "generated-synthetic-inputs-not-Resolve-evidence", "files": []}
    manifest_path = media / "manifest.json"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    return (
        output,
        media,
        stable,
        saved,
        stable_hash,
        saved_hash,
        hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
    )


def _run(project, output, media):
    config = {
        "outputDir": str(output),
        "mediaDir": str(media),
        "manifestSha256": hashlib.sha256(
            (media / "manifest.json").read_bytes()
        ).hexdigest(),
        "action": "restore-pinned-cache",
        "externalScriptingSetting": "None",
        "projectName": project.name,
    }
    return module.run(Resolve(project), config, probe=Probe)


def _patch_pins(stable_hash, saved_hash):
    module.STABLE_SHA256 = stable_hash
    module.SAVED_SHA256 = saved_hash


def _assert_refused_no_setter(
    root, *, stable=None, saved=None, pin_override=None, identity=None
):
    output, media, stable, saved, stable_hash, saved_hash, _ = _setup(
        root, stable=stable, saved=saved
    )
    _patch_pins(stable_hash, saved_hash)
    project = Project(stable, uid=identity)
    if pin_override:
        pin_override(output)
    try:
        _run(project, output, media)
    except Exception:
        pass
    else:
        raise AssertionError("expected refusal")
    _ok(not project.calls, "refusal must happen before SetSetting")


def check():
    original = (module.STABLE_SHA256, module.SAVED_SHA256)
    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, media, stable, saved, stable_hash, saved_hash, _ = _setup(Probe.ROOT)
        _patch_pins(stable_hash, saved_hash)
        project = Project(stable)
        result = _run(project, output, media)
        _ok(result["status"] == "restored-to-saved-pin", "success status")
        _ok(
            project.calls == [(module.CACHE_KEY, _setting_cache(saved))],
            "single exact setter",
        )
        _ok(project.reads == 4, "two-pass preflight and postflight")
        postflight = json.loads(Path(result["postflight"]).read_text(encoding="utf-8"))
        _ok(postflight["passes"] == [saved, saved], "retained canonical postflight")

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        _assert_refused_no_setter(Probe.ROOT, identity="wrong-id")

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        changed = _base_pass("CacheClip")
        changed["GetSettings"]["value"]["unrelated"] = "changed"
        _assert_refused_no_setter(Probe.ROOT, stable=changed)

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)

        def bad_hash(output):
            (output / module.STABLE_NAME).write_text("{}", encoding="utf-8")

        _assert_refused_no_setter(Probe.ROOT, pin_override=bad_hash)

    for bad_cache in ("missing", "symlink", "outside"):
        with tempfile.TemporaryDirectory() as temporary:
            Probe.ROOT = Path(temporary)
            output, media, stable, saved, stable_hash, saved_hash, _ = _setup(
                Probe.ROOT
            )
            cache = Path(_setting_cache(saved))
            if bad_cache == "missing":
                import shutil

                shutil.rmtree(cache)
            elif bad_cache == "symlink":
                import shutil

                shutil.rmtree(cache)
                target = Probe.ROOT / "cache-target"
                target.mkdir()
                cache.symlink_to(target)
            else:
                outside = Probe.ROOT / "outside-cache"
                outside.mkdir()
                saved = _base_pass(str(outside))
                saved_hash = _capture(output / module.SAVED_NAME, saved)
                stable_hash = hashlib.sha256(
                    (output / module.STABLE_NAME).read_bytes()
                ).hexdigest()
            _patch_pins(stable_hash, saved_hash)
            project = Project(stable)
            try:
                _run(project, output, media)
            except Exception:
                pass
            else:
                raise AssertionError("unsafe cache path must refuse")
            _ok(not project.calls, "unsafe cache path must not call setter")

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, media, stable, saved, stable_hash, saved_hash, _ = _setup(Probe.ROOT)
        _patch_pins(stable_hash, saved_hash)
        project = Project(stable, setter="zero")
        try:
            _run(project, output, media)
        except RuntimeError:
            pass
        else:
            raise AssertionError("non-boolean setter return must refuse")
        _ok(len(project.calls) == 1, "zero setter attempted once")
        postflight = next(output.glob("cache-restore-*-postflight.json"))
        _ok(
            json.loads(postflight.read_text())["passes"] == [saved, saved],
            "postflight retained after non-boolean setter return",
        )
        journal = next(output.glob("cache-restore-*.jsonl"))
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        _ok(
            any(
                row["method"] == "SetSetting"
                and row["phase"] == "return"
                and row["value"] == 0
                for row in records
            ),
            "non-boolean setter return retained",
        )

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, media, stable, saved, stable_hash, saved_hash, _ = _setup(Probe.ROOT)
        _patch_pins(stable_hash, saved_hash)
        project = Project(stable, setter="partial")
        try:
            _run(project, output, media)
        except RuntimeError:
            pass
        else:
            raise AssertionError("partial setter must refuse")
        _ok(len(project.calls) == 1, "partial setter attempted once")
        _ok(list(output.glob("cache-restore-*-postflight.json")), "postflight retained")
        journal = next(output.glob("cache-restore-*.jsonl"))
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        _ok(
            any(row["method"] == "Postflight" for row in records),
            "postflight journaled after refusal",
        )
        _ok(
            any(
                row["method"] == "SetSetting" and row["phase"] == "return"
                for row in records
            ),
            "false setter return retained",
        )

    with tempfile.TemporaryDirectory() as temporary:
        Probe.ROOT = Path(temporary)
        output, media, stable, saved, stable_hash, saved_hash, _ = _setup(Probe.ROOT)
        _patch_pins(stable_hash, saved_hash)
        project = Project(stable, setter="raise")
        try:
            _run(project, output, media)
        except RuntimeError:
            pass
        else:
            raise AssertionError("raising setter must refuse")
        _ok(len(project.calls) == 1, "raising setter attempted once")
        _ok(list(output.glob("cache-restore-*-postflight.json")), "postflight retained")
        journal = next(output.glob("cache-restore-*.jsonl"))
        records = [json.loads(line) for line in journal.read_text().splitlines()]
        _ok(
            any(row["method"] == "Postflight" for row in records),
            "postflight journaled after setter exception",
        )

    module.STABLE_SHA256, module.SAVED_SHA256 = original


def _setting_cache(observation):
    return module._setting(observation, module.CACHE_PATHS[0])


if __name__ == "__main__":
    check()
    print("cache-restore fake checks passed")
