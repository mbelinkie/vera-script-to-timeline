"""Save-only continuation for the pinned Issue 141 R4 state."""

import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME_PREFIX = "VERA Issue 141 Synthetic Probe "
BUILD = [21, 1, 0, 14, ""]
CAPTURE_NAME = "capture-20261001T003310.397326Z.json"
CAPTURE_SHA256 = "f3a321fcd5ae47c90e25b3dcf254a0d983ff0bdde8862700b2411c710b3fe0fa"
POOL_NAME = "r4-pool-read-only-20261001T003310.397326Z.json"
POOL_SHA256 = "ac6f4661f59f910029dae51dcc758bd1d766e8f810fb4996fcee1b18c681e751"
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ITEM_UID = "af55478a-0ba3-458a-a6e1-e47b2544111d"
R4_POOL_UID = "91853c24-9e0c-435c-8550-209a76425270"
MEDIA_SHA256 = "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942"


def _write(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


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


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


def _load_pin(path, digest, probe):
    if path.is_symlink() or not path.is_file() or probe.sha256(path) != digest:
        raise RuntimeError(f"Pinned evidence is missing or changed: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _timeline(observation, uid):
    rows = [
        row
        for row in observation.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == uid
    ]
    if len(rows) != 1:
        raise RuntimeError("Pinned timeline identity is missing or duplicated")
    return rows[0]


def _validate_media(config, root, capture_pass, pool_pass, probe):
    media = Path(config.get("mediaDir", ""))
    if (
        not media.is_absolute()
        or media.is_symlink()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only slice-owned synthetic media is allowed")
    manifest_path = media / "manifest.json"
    if probe.sha256(manifest_path) != config.get("manifestSha256"):
        raise RuntimeError("Synthetic media manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Synthetic media manifest kind differs")
    entries = {}
    expected = {}
    for entry in manifest.get("files", []):
        relative = Path(entry.get("path", ""))
        path = media / relative
        digest = entry.get("sha256")
        if (
            relative.is_absolute()
            or ".." in relative.parts
            or not isinstance(digest, str)
            or path.is_symlink()
            or not path.resolve().is_relative_to(media.resolve())
            or str(relative) in entries
        ):
            raise RuntimeError(
                "Synthetic manifest contains an unsafe or duplicate path"
            )
        entries[str(relative)] = digest
        expected[str(path)] = digest
    if entries.get("relink/base.mov") != MEDIA_SHA256:
        raise RuntimeError("Approved generated relink copy is absent from manifest")
    source = media / "relink/base.mov"
    if source.is_symlink() or not source.resolve(strict=True).is_relative_to(
        media.resolve()
    ):
        raise RuntimeError("Approved generated relink copy is unsafe")
    if probe.sha256(source) != MEDIA_SHA256:
        raise RuntimeError("Approved generated relink copy bytes changed")

    timeline = _timeline(capture_pass, R4_UID)
    if timeline.get("GetName") != {"value": "VERA 141 R4 availability"}:
        raise RuntimeError("Pinned R4 timeline name differs")
    occurrences = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if len(occurrences) != 1:
        raise RuntimeError("Pinned R4 timeline must have exactly one occurrence")
    track, item = occurrences[0]
    if (
        (track.get("type"), track.get("index")) != ("video", 1)
        or item.get("GetUniqueId") != {"value": ITEM_UID}
        or item.get("GetTrackTypeAndIndex") != {"value": ["video", 1]}
        or item.get("GetStart") != {"value": 0}
        or item.get("GetEnd") != {"value": 199}
        or item.get("GetDuration") != {"value": 199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
    ):
        raise RuntimeError("Pinned R4 occurrence identity, track or bounds differ")
    media_evidence = item.get("GetMediaPoolItem", {})
    properties = media_evidence.get("GetClipProperty", {}).get("value", {})
    if (
        media_evidence.get("GetUniqueId") != {"value": MEDIA_UID}
        or properties.get("File Path") != str(source)
        or properties.get("Online Status") != "Online"
        or media_evidence.get("sourceBytes", {}).get("sha256") != MEDIA_SHA256
        or media_evidence.get("sourceBytes", {}).get("hashMatches") is not True
    ):
        raise RuntimeError("Pinned occurrence media UID/path/online/hash differs")

    matching = [
        row for row in pool_pass.get("items", []) if row.get("uid") == MEDIA_UID
    ]
    if len(matching) != 1:
        raise RuntimeError(
            "Pinned pool inventory lacks one distinct imported media UID"
        )
    pool_properties = (
        matching[0].get("evidence", {}).get("GetClipProperty", {}).get("value", {})
    )
    pool_bytes = matching[0].get("evidence", {}).get("sourceBytes", {})
    if (
        pool_properties.get("File Path") != str(source)
        or pool_properties.get("Online Status") != "Online"
        or pool_bytes.get("sha256") != MEDIA_SHA256
        or pool_bytes.get("hashMatches") is not True
    ):
        raise RuntimeError("Pinned pool media path/online/hash differs")
    timeline_mapping = [
        row
        for row in pool_pass.get("timelineMappings", [])
        if row.get("timelineUid", {}).get("value") == R4_UID
    ]
    if len(timeline_mapping) != 1 or timeline_mapping[0].get("poolItemUid") != {
        "value": R4_POOL_UID
    }:
        raise RuntimeError("Pinned R4 timeline proxy mapping differs")
    if R4_POOL_UID in {R4_UID, MEDIA_UID}:
        raise RuntimeError("Timeline proxy and imported media identities must differ")
    return expected


def _validate_capture(capture, probe):
    passes = capture.get("passes")
    if (
        capture.get("consistency") != "equal-adjacent-reads"
        or capture.get("captureFailure") is not None
        or not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or probe.errors(passes)
    ):
        raise RuntimeError("Pinned R4 timeline capture is incomplete or inconsistent")
    return passes[0]


def _validate_pool(pool, capture_path, probe):
    passes = pool.get("passes")
    reference = pool.get("capture", {})
    if (
        pool.get("status") != "equal-read-only-pool-inventory"
        or not isinstance(passes, list)
        or len(passes) != 2
        or passes[0] != passes[1]
        or probe.errors(passes)
        or Path(reference.get("capturePath", "")).name != capture_path.name
        or reference.get("sha256") != CAPTURE_SHA256
        or reference.get("status") != "equal-adjacent-reads"
    ):
        raise RuntimeError("Pinned R4 pool inventory is incomplete or inconsistent")
    return passes[0]


def run(resolve, config, *, probe):
    """Save the pinned R4 state once after exact fresh timeline and pool reads."""
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != "r4-finalize"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only an existing slice-owned output may be finalized")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    journal = output / f"r4-finalize-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()
    stamps = {
        "action": config["action"],
        "productName": resolve.GetProductName(),
        "version": resolve.GetVersion(),
        "capture": {"name": CAPTURE_NAME, "sha256": CAPTURE_SHA256},
        "pool": {"name": POOL_NAME, "sha256": POOL_SHA256},
        "externalScriptingSetting": config["externalScriptingSetting"],
    }
    _append(journal, "R4Finalize", "start", stamps)

    def refuse(error, evidence=None):
        reason = f"{type(error).__name__}: {error}"
        _append(
            journal, "R4Finalize", "refusal", {"reason": reason, "evidence": evidence}
        )
        _write(
            output / f"r4-finalize-refusal-{stamp}.json",
            {"reason": reason, "evidence": evidence, "stamps": stamps},
        )
        raise error

    try:
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        if not isinstance(config.get("projectName"), str) or not config[
            "projectName"
        ].startswith(PROJECT_NAME_PREFIX):
            raise RuntimeError("Named Issue 141 project is required")
        capture_path = output / CAPTURE_NAME
        capture = _load_pin(capture_path, CAPTURE_SHA256, probe)
        pool = _load_pin(output / POOL_NAME, POOL_SHA256, probe)
        pinned = _validate_capture(capture, probe)
        pinned_pool = _validate_pool(pool, capture_path, probe)
        if (
            pinned.get("projectId") != PROJECT_ID
            or pinned.get("projectName") != config["projectName"]
            or capture.get("environment", {}).get("version") != BUILD
            or capture.get("stage") != "R4-post-append-partial-state-read-only"
        ):
            raise RuntimeError("Pinned R4 project/build/stage identity differs")
        _timeline(pinned, R4_UID)
        expected = _validate_media(config, root, pinned, pinned_pool, probe)
        identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
    except Exception as error:
        refuse(error)

    config_for_probe = dict(config, stage="R4-save-only-finalization")

    def context_check():
        project = probe.require_current(resolve, config_for_probe, identity)
        current = project.GetCurrentTimeline()
        if current is None or current.GetUniqueId() != R4_UID:
            raise RuntimeError("Exact R4 timeline must remain selected")
        return project

    def read_pair():
        timeline_passes, pool_passes = [], []
        for _ in range(2):
            try:
                project = context_check()
                timeline_value = _canonical(
                    probe.observe(resolve, config_for_probe, identity, expected)
                )
                project = context_check()
                pool_value = _canonical(probe._r4_pool_inventory(project, expected))
                context_check()
            except Exception as error:
                failure = {"error": f"{type(error).__name__}: {error}"}
                timeline_passes.append(failure)
                pool_passes.append(failure)
                break
            timeline_passes.append(timeline_value)
            pool_passes.append(pool_value)
        payload = {
            "timelinePasses": timeline_passes,
            "poolPasses": pool_passes,
            "timelineConsistency": "equal-adjacent-reads"
            if len(timeline_passes) == 2
            and timeline_passes[0] == timeline_passes[1]
            and not probe.errors(timeline_passes)
            else "incomplete-or-inconsistent-refused",
            "poolConsistency": "equal-adjacent-reads"
            if len(pool_passes) == 2
            and pool_passes[0] == pool_passes[1]
            and not probe.errors(pool_passes)
            else "incomplete-or-inconsistent-refused",
        }
        return payload

    try:
        before = read_pair()
        _write(output / f"r4-finalize-{stamp}-preflight.json", before)
        _append(journal, "Preflight", "readback", before)
        if (
            before["timelineConsistency"] != "equal-adjacent-reads"
            or before["poolConsistency"] != "equal-adjacent-reads"
            or before["timelinePasses"] != [pinned, pinned]
            or before["poolPasses"] != [pinned_pool, pinned_pool]
        ):
            raise RuntimeError(
                "Fresh full R4 timeline/pool preflight differs from pins"
            )
        project = context_check()
    except Exception as error:
        refuse(error, before if "before" in locals() else None)

    _append(journal, "SaveProject", "request", {"projectId": PROJECT_ID})
    save_result, save_error = None, None
    try:
        save_result = resolve.GetProjectManager().SaveProject()
        _append(journal, "SaveProject", "return", save_result)
    except Exception as error:
        save_error = error
        _append(journal, "SaveProject", "failure", f"{type(error).__name__}: {error}")

    after = None
    try:
        after = read_pair()
        _write(output / f"r4-finalize-{stamp}-postflight.json", after)
        _append(journal, "Postflight", "readback", after)
    except Exception as error:
        _append(journal, "Postflight", "failure", f"{type(error).__name__}: {error}")
    unchanged = (
        after is not None
        and after["timelineConsistency"] == "equal-adjacent-reads"
        and after["poolConsistency"] == "equal-adjacent-reads"
        and after["timelinePasses"] == [pinned, pinned]
        and after["poolPasses"] == [pinned_pool, pinned_pool]
    )
    if save_error is not None or save_result is not True or not unchanged:
        error = RuntimeError("SaveProject refused or exact R4 postflight differed")
        _append(
            journal,
            "R4Finalize",
            "refusal",
            {
                "reason": str(error),
                "saveError": None if save_error is None else str(save_error),
                "unchanged": unchanged,
            },
        )
        _write(
            output / f"r4-finalize-refusal-{stamp}.json",
            {
                "reason": str(error),
                "saveResult": save_result,
                "saveError": None if save_error is None else str(save_error),
                "unchanged": unchanged,
                "stamps": stamps,
            },
        )
        raise error from save_error
    _append(journal, "R4Finalize", "complete", {"status": "saved-pinned-r4-state"})
    return {
        "status": "saved-pinned-r4-state",
        "journal": str(journal),
        "preflight": str(output / f"r4-finalize-{stamp}-preflight.json"),
        "postflight": str(output / f"r4-finalize-{stamp}-postflight.json"),
    }
