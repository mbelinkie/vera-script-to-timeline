"""Two native still samples of the exact offline R4 occurrence."""

import json
from datetime import UTC, datetime

R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
CAPTURE_NAME = "capture-20261001T012446.349239Z.json"
CAPTURE_SHA = "c3cb459f1dd6736014e15f687141b58cb1af74722836cb724112d093011a9008"
POOL_NAME = "r4-pool-read-only-20261001T012446.349239Z.json"
POOL_SHA = "6af8465205951d5bb7157c46916de09f6d6577d6695a58224d0ab29bc960e596"


def run(resolve, config, identity, expected, output, stamp, environment, *, probe):
    if config.get("action") != "offline-picture":
        raise RuntimeError("Exact offline picture action required")
    if identity.get("projectId") != "97037b5a-aab6-48a9-b7e4-4c5697ae10a0":
        raise RuntimeError("Exact synthetic project required")
    pins = []
    for name, digest in ((CAPTURE_NAME, CAPTURE_SHA), (POOL_NAME, POOL_SHA)):
        path = output / name
        if path.is_symlink() or probe.sha256(path) != digest:
            raise RuntimeError("Offline picture pin changed")
        value = json.loads(path.read_text())
        pairs = value.get("passes")
        if not isinstance(pairs, list) or len(pairs) != 2 or pairs[0] != pairs[1]:
            raise RuntimeError("Offline picture pin is not a complete equal pair")
        if probe.errors(pairs):
            raise RuntimeError("Offline picture pin has unresolved getters")
        pins.append(pairs[0])
    directory = output / f"offline-picture-{stamp}"
    directory.mkdir()
    journal = directory / "journal.jsonl"
    journal.open("x").close()

    def record(method, phase, value):
        with journal.open("a") as stream:
            stream.write(
                json.dumps(
                    {
                        "at": datetime.now(UTC).isoformat(),
                        "method": method,
                        "phase": phase,
                        "value": value,
                    },
                    allow_nan=False,
                )
                + "\n"
            )

    def guard():
        project = probe.require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != [21, 1, 0, 14, ""]
            or timeline is None
            or timeline.GetUniqueId() != R4_UID
            or resolve.GetCurrentPage() != "edit"
        ):
            raise RuntimeError("Exact selected R4/Edit/build context required")
        return project, timeline

    def snapshot(label):
        observations, inventories = [], []
        for _ in range(2):
            guard()
            observations.append(
                json.loads(
                    json.dumps(
                        probe.observe(resolve, config, identity, expected),
                        allow_nan=False,
                    )
                )
            )
            project, _ = guard()
            inventories.append(
                json.loads(
                    json.dumps(
                        probe._r4_pool_inventory(project, expected), allow_nan=False
                    )
                )
            )
            guard()
        payload = {"timelinePasses": observations, "poolPasses": inventories}
        probe.write_json(directory / f"{label}.json", payload)
        if observations != [pins[0], pins[0]] or inventories != [pins[1], pins[1]]:
            raise RuntimeError(
                "Offline sample full state differs from pinned checkpoint"
            )

    def call(obj, method, *args):
        guard()
        record(method, "request", list(args))
        try:
            value = getattr(obj, method)(*args)
            record(method, "return", value)
        except Exception as error:
            record(method, "failure", f"{type(error).__name__}: {error}")
            raise
        if value is not True:
            raise RuntimeError(f"{method} refused the bounded call")

    initial = None
    samples, failure, restored = [], None, False
    try:
        snapshot("preflight")
        pinned_timelines = [
            row
            for row in pins[0].get("timelines", [])
            if row.get("GetUniqueId") == {"value": R4_UID}
        ]
        if len(pinned_timelines) != 1:
            raise RuntimeError("Pinned R4 timeline identity is not unique")
        pinned = pinned_timelines[0]
        if (
            pinned.get("GetStartTimecode") != {"value": "00:00:00:00"}
            or pinned.get("GetStartFrame") != {"value": 0}
            or not isinstance(pinned.get("GetEndFrame", {}).get("value"), int)
            or pinned["GetEndFrame"]["value"] <= 50
        ):
            raise RuntimeError("Offline samples are outside the pinned program range")
        _, timeline = guard()
        initial = timeline.GetCurrentTimecode()
        if not isinstance(initial, str) or not initial:
            raise RuntimeError("Original playhead unreadable")
        record("GetCurrentTimecode", "initial", initial)
        for frame, timecode in ((0, "00:00:00:00"), (50, "00:00:02:00")):
            project, timeline = guard()
            call(timeline, "SetCurrentTimecode", timecode)
            if timeline.GetCurrentTimecode() != timecode:
                raise RuntimeError(
                    "Requested offline sample playhead did not read back"
                )
            destination = directory / f"frame-{frame:03d}.png"
            call(project, "ExportCurrentFrameAsStill", str(destination))
            guard()
            if timeline.GetCurrentTimecode() != timecode:
                raise RuntimeError("Playhead changed during offline sample export")
            if (
                destination.is_symlink()
                or not destination.is_file()
                or destination.stat().st_size <= 8
                or destination.read_bytes()[:8] != b"\x89PNG\r\n\x1a\n"
            ):
                raise RuntimeError("Offline sample export is not a regular PNG")
            sample = {
                "frame": frame,
                "timecode": timecode,
                "path": str(destination),
                "sha256": probe.sha256(destination),
                "bytes": destination.stat().st_size,
            }
            samples.append(sample)
            record("OfflinePicture", "sample", sample)
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        record("OfflinePicture", "refusal", failure)
    if initial is not None:
        try:
            _, timeline = guard()
            call(timeline, "SetCurrentTimecode", initial)
            restored = timeline.GetCurrentTimecode() == initial
            if not restored:
                raise RuntimeError("Original playhead restoration did not read back")
        except Exception as error:
            failure = f"{failure or ''}; restoration: {type(error).__name__}: {error}"
            record("OfflinePicture", "restore-refused", failure)
    try:
        snapshot("postflight")
    except Exception as error:
        failure = f"{failure or ''}; postflight: {type(error).__name__}: {error}"
        record("OfflinePicture", "postflight-refused", failure)
    result = {
        "status": "offline-picture-candidates-retained"
        if failure is None and restored and len(samples) == 2
        else "offline-picture-refused",
        "samples": samples,
        "restoredPlayhead": restored,
        "failure": failure,
        "journal": str(journal),
        "environment": environment,
        "limits": [
            "Sampled output needs host inspection; no general visibility claim."
        ],
    }
    probe.write_json(directory / "result.json", result)
    return result
