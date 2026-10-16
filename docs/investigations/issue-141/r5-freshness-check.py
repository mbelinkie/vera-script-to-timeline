"""Small fake for controlled metadata drift and guarded exact restoration."""

import importlib.util
import json
import tempfile
from pathlib import Path

HERE = Path(__file__).parent


def load(name, filename):
    spec = importlib.util.spec_from_file_location(name, HERE / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


fake = load("freshness_fake", "r4-range-repair-check.py")
module = load("freshness", "r5-freshness.py")
actual_probe = load("freshness_comparator", "probe.py")


def get_custom(self, frame):
    assert self.uid == fake.MODULE.MATRIX_UID and frame == 0
    return self._row()["GetMarkers"]["value"]["0"]["customData"]


def update_custom(self, frame, value):
    assert self.uid == fake.MODULE.MATRIX_UID and frame == 0
    store = self.store
    store.updates.append(value)
    if store.mode == "false":
        return False
    if store.mode == "throw":
        raise RuntimeError("injected marker update failure")
    self._row()["GetMarkers"]["value"]["0"]["customData"] = value
    if store.mode == "drift":
        store.state["GetSettings"]["value"]["unexpected"] = True
    return store.mode != "partial"


fake.TimelineHandle.GetMarkerCustomData = get_custom
fake.TimelineHandle.UpdateMarkerCustomData = update_custom
fake.Project.GetCurrentRenderFormatAndCodec = lambda self: {
    "format": "mov",
    "codec": "H264",
}
fake.Project.GetRenderJobList = lambda self: []
fake.Resolve.GetCurrentPage = lambda self: "edit"
fake.Probe.consistency = staticmethod(actual_probe.consistency)


def demo():
    for mode in ("true", "false", "throw", "partial", "drift", "bad-pin"):
        with tempfile.TemporaryDirectory() as directory:
            resolve, config, _ = fake._setup(Path(directory))
            store = resolve.store
            store.selected_uid = fake.MODULE.R4_UID
            store.mode, store.updates = mode, []
            matrix = next(
                t
                for t in store.state["timelines"]
                if t["GetUniqueId"] == {"value": fake.MODULE.MATRIX_UID}
            )
            matrix["GetMarkers"] = {"value": {"0": {"customData": "original"}}}
            output = Path(config["outputDir"])
            config["action"] = "r5-freshness"
            cap, pool = output / module.CAPTURE_NAME, output / module.POOL_NAME
            cap.write_text(
                json.dumps(
                    {
                        "consistency": "equal-adjacent-reads",
                        "passes": [store.state, store.state],
                    }
                )
            )
            pool.write_text(
                json.dumps(
                    {
                        "status": "equal-read-only-pool-inventory",
                        "capture": {"sha256": fake.digest(cap)},
                        "passes": [store.pool, store.pool],
                    }
                )
            )
            module.CAPTURE_SHA, module.POOL_SHA = fake.digest(cap), fake.digest(pool)
            module.READER_SHA = fake.digest(HERE / "r4-range-repair.py")
            if mode == "bad-pin":
                cap.write_text("changed pin")
                try:
                    module.run(resolve, config, probe=fake.Probe)
                except RuntimeError:
                    assert store.updates == []
                    continue
                raise AssertionError("bad pin did not refuse")
            result = module.run(resolve, config, probe=fake.Probe)
            assert result["status"] == (
                "controlled-change-refused-and-restored"
                if mode == "true"
                else "freshness-outcome-review-required"
            ), (mode, result)
            assert len(store.updates) == (2 if mode in {"true", "partial"} else 1), mode
            if mode in {"true", "partial", "false", "throw"}:
                assert matrix["GetMarkers"]["value"]["0"]["customData"] == "original"
            if mode in {"true", "partial", "drift"}:
                assert result["comparisonStatus"] == "inconsistent-refused"
            assert store.setter_calls == [] and store.selection_calls == []

    original_capture = actual_probe.capture
    original_observe = actual_probe.observe
    original_values = {
        name: getattr(actual_probe, name)
        for name in (
            "ROOT",
            "sha256",
            "errors",
            "consistency",
            "require_current",
            "_r4_pool_inventory",
        )
    }
    for fail_after_capture, mode in ((False, "true"), (True, "true"), (False, "drift")):
        with tempfile.TemporaryDirectory() as directory:
            resolve, config, _ = fake._setup(Path(directory))
            store = resolve.store
            store.selected_uid = fake.MODULE.R4_UID
            store.mode, store.updates = mode, []
            matrix = next(
                t
                for t in store.state["timelines"]
                if t["GetUniqueId"]["value"] == fake.MODULE.MATRIX_UID
            )
            matrix["GetMarkers"] = {"value": {"0": {"customData": "original"}}}
            output = Path(config["outputDir"])
            config["action"] = "r5-capture-freshness"
            cap, pool = output / module.CAPTURE_NAME, output / module.POOL_NAME
            cap.write_text(
                json.dumps(
                    {
                        "consistency": "equal-adjacent-reads",
                        "passes": [store.state, store.state],
                    }
                )
            )
            pool.write_text(
                json.dumps(
                    {
                        "status": "equal-read-only-pool-inventory",
                        "capture": {"sha256": fake.digest(cap)},
                        "passes": [store.pool, store.pool],
                    }
                )
            )
            module.CAPTURE_SHA, module.POOL_SHA = fake.digest(cap), fake.digest(pool)
            module.READER_SHA = fake.digest(HERE / "r4-range-repair.py")

            def observer(*args):
                return fake.Probe.observe(*args)

            actual_probe.ROOT = fake.Probe.ROOT
            actual_probe.sha256 = fake.digest
            actual_probe.errors = fake.Probe.errors
            actual_probe.consistency = actual_probe.__dict__["consistency"]
            actual_probe.require_current = fake.Probe.require_current
            actual_probe._r4_pool_inventory = fake.Probe._r4_pool_inventory
            actual_probe.observe = observer
            calls = []

            def capture(*args, calls=calls, fail_after_capture=fail_after_capture):
                calls.append(args)
                result = original_capture(*args)
                if fail_after_capture:
                    raise RuntimeError("injected capture wrapper failure")
                return result

            actual_probe.capture = capture
            try:
                result = module.run(resolve, config, probe=actual_probe)
                assert calls and result["captureLoopInvoked"] is True, result
                assert actual_probe.observe is observer
                assert result["captureObserverRestored"] is True
                if mode == "drift":
                    assert result["status"] == "freshness-outcome-review-required"
                    assert result["originalFullStateRestored"] is False
                    assert len(store.updates) == 1
                    continue
                assert matrix["GetMarkers"]["value"]["0"]["customData"] == "original"
                assert result["originalFullStateRestored"] is True
                if fail_after_capture:
                    assert result["captureFailure"] == (
                        "RuntimeError: injected capture wrapper failure"
                    )
                    assert result["status"] == "freshness-outcome-review-required"
                    assert result["rawCapturePath"]
                    assert (
                        len(
                            json.loads(Path(result["rawCapturePath"]).read_text())[
                                "passes"
                            ]
                        )
                        == 2
                    )
                else:
                    assert result["status"] == "controlled-change-refused-and-restored"
                    assert result["comparisonStatus"] == "inconsistent-refused"
                    assert result["rawCapturePath"]
                    raw = json.loads(Path(result["rawCapturePath"]).read_text())
                    assert len(raw["passes"]) == 2
                    assert raw["passes"][0] != raw["passes"][1]
            finally:
                actual_probe.capture = original_capture
                actual_probe.observe = original_observe
                for name, value in original_values.items():
                    setattr(actual_probe, name, value)
                module.CAPTURE_SHA, module.POOL_SHA = (
                    "690bac86a68ca1ba7a168071bf7df3fe01d172e7f258303183163c1bf25e90da",
                    "4b9fd9ba0f6bc006ceabf6d6658f1e971369de68d6042ad7042b3b25e0ec8437",
                )
                module.READER_SHA = fake.digest(HERE / "r4-range-repair.py")
    print("Controlled R5 freshness fake checks passed")


if __name__ == "__main__":
    demo()
