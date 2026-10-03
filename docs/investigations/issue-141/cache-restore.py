"""Restore the exact Issue 141 pinned Matrix cache preparation setting."""

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
MATRIX_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
BUILD = [21, 1, 0, 14, ""]
STABLE_NAME = "capture-20260930T234711.275916Z.json"
STABLE_SHA256 = "3d08f757c8e188bbc5c1584158f5ea29c23f5bb7745bf01bd5de42c6d6436a46"
SAVED_NAME = "capture-20260930T223313.312609Z-saved.json"
SAVED_SHA256 = "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
CACHE_KEY = "perfCacheClipsLocation"
CACHE_PATHS = (
    ("GetSettings", "value", CACHE_KEY),
    ("timelines", MATRIX_NAME, "GetSettings", "value", CACHE_KEY),
    ("timelines", "VERA 141 Baseline", "GetSettings", "value", CACHE_KEY),
    ("timelines", "VERA 141 R1 identity", "GetSettings", "value", CACHE_KEY),
)
TIMELINES = {
    "VERA 141 Batched Matrix": MATRIX_ID,
    "VERA 141 Baseline": "88f7923d-55a7-471f-b09b-cf10f9fae8ad",
    "VERA 141 R1 identity": "aa2b8e36-83bd-4292-9e33-217c00ca192f",
}


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _append(path, method, phase, value):
    with Path(path).open("a", encoding="utf-8") as stream:
        json.dump(
            {
                "at": datetime.now(UTC).isoformat(),
                "method": method,
                "phase": phase,
                "value": value,
            },
            stream,
            sort_keys=True,
            allow_nan=False,
        )
        stream.write("\n")


def _read_pin(path, expected_hash, probe):
    if path.is_symlink() or not path.is_file() or _sha256(path) != expected_hash:
        raise RuntimeError(f"Pinned capture is missing or changed: {path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    passes = value.get("passes")
    if (
        value.get("consistency") != "equal-adjacent-reads"
        or not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or value.get("captureFailure") is not None
        or probe.errors(passes)
    ):
        raise RuntimeError(f"Pinned capture is incomplete: {path.name}")
    return passes[0]


def _timeline_map(observation):
    timelines = observation.get("timelines")
    if not isinstance(timelines, list) or len(timelines) != len(TIMELINES):
        raise RuntimeError("Pinned timeline set is incomplete")
    result = {}
    for timeline in timelines:
        name = timeline.get("GetName", {}).get("value")
        uid = timeline.get("GetUniqueId", {}).get("value")
        if name not in TIMELINES or uid != TIMELINES[name] or name in result:
            raise RuntimeError("Pinned timeline identity differs")
        result[name] = timeline
    if result.keys() != TIMELINES.keys():
        raise RuntimeError("Pinned timeline identity set differs")
    return result


def _setting(observation, path):
    value = observation
    for key in path:
        if key == "timelines":
            value = _timeline_map(value)
            continue
        value = value[key]
    return value


def _set_setting(observation, path, value):
    target = observation
    for key in path[:-1]:
        if key == "timelines":
            target = _timeline_map(target)
            continue
        target = target[key]
    target[path[-1]] = value


def _validate_pins(stable, saved):
    if (
        stable.get("projectId") != PROJECT_ID
        or stable.get("projectName") != saved.get("projectName")
        or saved.get("projectId") != PROJECT_ID
    ):
        raise RuntimeError("Pinned project identity differs")
    _timeline_map(stable)
    _timeline_map(saved)
    normalized = deepcopy(stable)
    stable_values = [_setting(stable, path) for path in CACHE_PATHS]
    saved_values = [_setting(saved, path) for path in CACHE_PATHS]
    if (
        stable_values != ["CacheClip"] * len(CACHE_PATHS)
        or not all(isinstance(value, str) and value for value in saved_values)
        or len(set(saved_values)) != 1
        or saved_values == stable_values
    ):
        raise RuntimeError("Pinned cache-setting values differ from the bounded case")
    for path, value in zip(CACHE_PATHS, saved_values, strict=True):
        _set_setting(normalized, path, value)
    if normalized != saved:
        raise RuntimeError("Pinned captures differ beyond the four cache fields")
    return saved_values[0]


def _validate_cache_path(value, output):
    try:
        path = Path(value)
        root = output.resolve(strict=True)
        if (
            not path.is_absolute()
            or ".." in path.parts
            or path.is_symlink()
            or not path.is_dir()
        ):
            raise ValueError
        relative = path.relative_to(output)
        if not relative.parts:
            raise ValueError
        cursor = output
        for part in relative.parts:
            cursor /= part
            if cursor.is_symlink():
                raise ValueError
        resolved = path.resolve(strict=True)
        if not resolved.is_dir() or not resolved.is_relative_to(root):
            raise ValueError
    except (OSError, ValueError, TypeError):
        raise RuntimeError(
            "Pinned cache directory is missing, symlinked, or outside outputDir"
        ) from None
    return str(path)


def run(resolve, config, *, probe):
    """Restore only the pinned project cache setting, retaining both reads."""
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != "restore-pinned-cache"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only an existing slice-owned output directory is allowed")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    journal = output / f"cache-restore-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()
    _append(journal, "CacheRestore", "start", {"stage": "restore-pinned-cache"})

    def refuse(error):
        _append(
            journal,
            "CacheRestore",
            "refusal",
            f"{type(error).__name__}: {error}",
        )
        raise error

    try:
        if resolve is None:
            raise RuntimeError("Injected Resolve object required")
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        stable = _read_pin(output / STABLE_NAME, STABLE_SHA256, probe)
        saved = _read_pin(output / SAVED_NAME, SAVED_SHA256, probe)
        cache_path = _validate_cache_path(_validate_pins(stable, saved), output)
        if config.get("projectName") != stable.get("projectName"):
            raise RuntimeError("Configured project name differs from pinned project")
        if not isinstance(config.get("manifestSha256"), str):
            raise RuntimeError("Synthetic media manifest hash is required")
        media = Path(config.get("mediaDir", ""))
        manifest_path = media / "manifest.json"
        if (
            not media.is_absolute()
            or media.is_symlink()
            or media.parent.resolve() != (root / "out").resolve()
            or not media.name.startswith("issue-141-media-")
            or probe.sha256(manifest_path) != config["manifestSha256"]
        ):
            raise RuntimeError("Synthetic media manifest differs; refusing")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
            raise RuntimeError("Only generated synthetic media is allowed")
        expected = {}
        for entry in manifest.get("files", []):
            relative = Path(entry["path"])
            path = media / relative
            if (
                relative.is_absolute()
                or ".." in relative.parts
                or path.is_symlink()
                or not path.resolve().is_relative_to(media.resolve())
            ):
                raise RuntimeError("Unsafe synthetic media manifest path")
            expected[str(path)] = entry["sha256"]
        if len(expected) != len(manifest.get("files", [])):
            raise RuntimeError("Synthetic media manifest contains duplicate paths")
        identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    except Exception as error:
        refuse(error)

    config_for_probe = dict(config, stage="restore-pinned-cache")

    def context_check():
        project = probe.require_current(resolve, config_for_probe, identity)
        selected = project.GetCurrentTimeline()
        if selected is None or selected.GetUniqueId() != MATRIX_ID:
            raise RuntimeError("Exact Matrix timeline must remain selected")
        return project

    def capture(label):
        passes = []
        for _ in range(2):
            try:
                context_check()
                passes.append(
                    _canonical(
                        probe.observe(resolve, config_for_probe, identity, expected)
                    )
                )
                context_check()
            except Exception as error:
                passes.append({"error": f"{type(error).__name__}: {error}"})
        failures = probe.errors(passes)
        payload = {
            "kind": "restore-pinned-cache-capture",
            "stage": config_for_probe["stage"],
            "label": label,
            "capturedAt": datetime.now(UTC).isoformat(),
            "passes": passes,
            "consistency": "equal-adjacent-reads"
            if passes[0] == passes[1] and not failures
            else "incomplete-or-inconsistent-refused",
            "getterFailures": failures,
        }
        path = output / f"cache-restore-{stamp}-{label}.json"
        _write(path, payload)
        return payload

    try:
        before = capture("preflight")
        _append(journal, "Preflight", "readback", before)
        if before["consistency"] != "equal-adjacent-reads" or before["passes"] != [
            stable,
            stable,
        ]:
            raise RuntimeError(
                "Fresh two-pass preflight differs from pinned stable capture"
            )
        project = context_check()
    except Exception as error:
        refuse(error)

    request = {"key": CACHE_KEY, "value": cache_path}
    _append(journal, "SetSetting", "request", request)
    setter_value = None
    setter_error = None
    try:
        setter_value = project.SetSetting(CACHE_KEY, cache_path)
        _append(journal, "SetSetting", "return", setter_value)
    except Exception as error:
        setter_error = error
        _append(
            journal,
            "SetSetting",
            "failure",
            f"{type(error).__name__}: {error}",
        )

    try:
        after = capture("postflight")
        _append(journal, "Postflight", "readback", after)
    except Exception as error:
        after = None
        _append(
            journal,
            "Postflight",
            "failure",
            f"{type(error).__name__}: {error}",
        )

    restored = (
        after is not None
        and after["consistency"] == "equal-adjacent-reads"
        and after["passes"] == [saved, saved]
    )
    if setter_error is not None or setter_value is not True or not restored:
        raise RuntimeError(
            "Pinned cache restoration refused or failed readback"
        ) from setter_error
    _append(journal, "CacheRestore", "complete", {"status": "restored-to-saved-pin"})
    return {
        "status": "restored-to-saved-pin",
        "journal": str(journal),
        "preflight": str(output / f"cache-restore-{stamp}-preflight.json"),
        "postflight": str(output / f"cache-restore-{stamp}-postflight.json"),
    }
