"""One pinned relink-only recovery for the partial Issue 141 R4 unlink."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_POOL_UID = "91853c24-9e0c-435c-8550-209a76425270"
ORIGINAL_UID = "9202163a-8381-43e6-9157-3a60f35c6f79"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ITEM_UID = "af55478a-0ba3-458a-a6e1-e47b2544111d"
MEDIA_SHA256 = "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942"
MEDIA_SIZE = 792_989
CAPTURE_NAME = "capture-20261001T003310.397326Z.json"
CAPTURE_SHA256 = "f3a321fcd5ae47c90e25b3dcf254a0d983ff0bdde8862700b2411c710b3fe0fa"
POOL_NAME = "r4-pool-read-only-20261001T003310.397326Z.json"
POOL_SHA256 = "ac6f4661f59f910029dae51dcc758bd1d766e8f810fb4996fcee1b18c681e751"
OFFLINE_CAPTURE_NAME = "capture-20261001T012446.349239Z.json"
OFFLINE_CAPTURE_SHA256 = (
    "c3cb459f1dd6736014e15f687141b58cb1af74722836cb724112d093011a9008"
)
OFFLINE_POOL_NAME = "r4-pool-read-only-20261001T012446.349239Z.json"
OFFLINE_POOL_SHA256 = "6af8465205951d5bb7157c46916de09f6d6577d6695a58224d0ab29bc960e596"
MATRIX_NAME = "capture-20260930T223313.312609Z-saved.json"
MATRIX_SHA256 = "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
TRANSITION_JOURNAL = "r4-transitions-20261001T012112.314811Z.jsonl"
TRANSITION_JOURNAL_SHA256 = (
    "efbfc5ba818225a9217c805d809e0b1a97470569d2b267a789fb0959add2a837"
)
UNLINK_CAPTURE = "r4-transitions-20261001T012112.314811Z-unlink-postflight.json"
UNLINK_CAPTURE_SHA256 = (
    "5f52acc7108910ddc84fca0b4cec30ff0ce77af8c55251a3f4a0868cd03a4f12"
)
REFUSAL_FILE = "r4-transitions-refusal-20261001T012112.314811Z.json"
REFUSAL_SHA256 = "f1dc4645b5af2003c7a4aa563d98fc14f1b5429659fcda4a55853905b8d6fbdb"
PLUGIN_RESULT = "vera-issue-141-observation-result-20261001T012111.805222Z.json"
PLUGIN_RESULT_SHA256 = (
    "66a55767b53acf9dfa300d0f5f8a10ccbb67870b62cfb3d7579d6879851e266d"
)
PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify_file(path, digest):
    if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
        raise RuntimeError(f"Pinned recovery evidence changed: {path.name}")


def _load(path, digest):
    _verify_file(path, digest)
    return json.loads(path.read_text(encoding="utf-8"))


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


def _timeline(state, uid):
    rows = [
        row
        for row in state.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == uid
    ]
    if len(rows) != 1:
        raise RuntimeError("Pinned timeline identity is missing or duplicated")
    return rows[0]


def _pool_item(inventory, uid):
    rows = [row for row in inventory.get("items", []) if row.get("uid") == uid]
    if len(rows) != 1:
        raise RuntimeError("Target pool item is missing or duplicated")
    return rows[0]


def _occurrence(state):
    timeline = _timeline(state, R4_UID)
    items = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if len(items) != 1:
        raise RuntimeError("R4 occurrence count differs from the pinned single item")
    track, item = items[0]
    if (
        (track.get("type"), track.get("index")) != ("video", 1)
        or item.get("GetUniqueId") != {"value": ITEM_UID}
        or item.get("GetMediaPoolItem", {}).get("GetUniqueId") != {"value": MEDIA_UID}
        or item.get("GetStart") != {"value": 0}
        or item.get("GetEnd") != {"value": 199}
        or item.get("GetDuration") != {"value": 199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
        or item.get("GetTrackTypeAndIndex") != {"value": ["video", 1]}
    ):
        raise RuntimeError("Pinned R4 occurrence identity or range differs")
    return timeline, item


def _normalize(state, baseline, media_path, offline):
    """Allow only target locator/status and source-evidence fields to differ."""
    current, expected = _canonical(state), _canonical(baseline)
    _, item = _occurrence(current)
    _, base_item = _occurrence(expected)
    current_media = item["GetMediaPoolItem"]
    base_media = base_item["GetMediaPoolItem"]
    props = current_media["GetClipProperty"]["value"]
    base_props = base_media["GetClipProperty"]["value"]
    if props.keys() != base_props.keys():
        return False
    if offline:
        expected_display = "OFFLINE - " + str(media_path / "relink/base.mov")
        if (
            props.get("File Name") != "base.mov"
            or props.get("File Path") != expected_display
            or props.get("Online Status") != "Offline"
            or props.get("Clip Directory") != str(media_path / "relink")
        ):
            return False
        for key, value in base_props.items():
            observed = props[key]
            if key in {"File Path", "Online Status"}:
                props[key] = value
            elif observed != value:
                return False
        source = current_media.get("sourceBytes", {})
        if source not in (
            {"status": "unapproved-locator-not-accessed"},
            {
                "status": "offline-locator-not-accessed",
                "approvedLocator": str(media_path / "relink/base.mov"),
                "expectedSha256": MEDIA_SHA256,
            },
        ):
            return False
        current_media["sourceBytes"] = _canonical(base_media.get("sourceBytes", {}))
    return current == expected


def _normalize_pool(inventory, baseline, media_path, offline):
    current, expected = _canonical(inventory), _canonical(baseline)
    row = _pool_item(current, MEDIA_UID)
    base_row = _pool_item(expected, MEDIA_UID)
    actual = row.get("evidence", {}).get("GetClipProperty", {}).get("value", {})
    prior = base_row.get("evidence", {}).get("GetClipProperty", {}).get("value", {})
    if actual.keys() != prior.keys():
        return False
    if offline:
        if (
            actual.get("File Name") != "base.mov"
            or actual.get("File Path")
            != "OFFLINE - " + str(media_path / "relink/base.mov")
            or actual.get("Online Status") != "Offline"
            or actual.get("Clip Directory") != str(media_path / "relink")
        ):
            return False
        for key, value in prior.items():
            observed = actual[key]
            if key in {"File Path", "Online Status"}:
                actual[key] = value
            elif observed != value:
                return False
        source = row["evidence"].get("sourceBytes", {})
        if source != {
            "status": "offline-locator-not-accessed",
            "approvedLocator": str(media_path / "relink/base.mov"),
            "expectedSha256": MEDIA_SHA256,
        }:
            return False
        row["evidence"]["sourceBytes"] = _canonical(
            base_row["evidence"].get("sourceBytes", {})
        )
    return current == expected


def _validate_setup(capture, pool, checkpoint, config, probe, media_path):
    cp, pp, mp = (
        capture.get("passes", []),
        pool.get("passes", []),
        checkpoint.get("passes", []),
    )
    if (
        capture.get("consistency") != "equal-adjacent-reads"
        or capture.get("captureFailure") is not None
        or capture.get("stage") != "R4-post-append-partial-state-read-only"
        or len(cp) != 2
        or cp[0] != cp[1]
        or probe.errors(cp)
        or pool.get("status") != "equal-read-only-pool-inventory"
        or len(pp) != 2
        or pp[0] != pp[1]
        or probe.errors(pp)
        or Path(pool.get("capture", {}).get("capturePath", "")).name != CAPTURE_NAME
        or pool.get("capture", {}).get("sha256") != CAPTURE_SHA256
        or len(mp) != 2
        or mp[0] != mp[1]
        or probe.errors(mp)
        or cp[0].get("projectId") != PROJECT_ID
        or cp[0].get("projectName") != config.get("projectName")
        or checkpoint.get("environment", {}).get("version") != BUILD
        or mp[0].get("projectId") != PROJECT_ID
        or mp[0].get("projectName") != config.get("projectName")
    ):
        raise RuntimeError("Original saved R4 setup pins are incomplete")
    base_state, base_pool = cp[0], pp[0]
    state_ids = {
        row.get("GetUniqueId", {}).get("value")
        for row in base_state.get("timelines", [])
    }
    expected_state_ids = {
        R4_UID,
        "29ae8331-b86e-4041-a548-960695cc7b24",
        "88f7923d-55a7-471f-b09b-cf10f9fae8ad",
        "aa2b8e36-83bd-4292-9e33-217c00ca192f",
    }
    if state_ids != expected_state_ids:
        raise RuntimeError("Pinned setup timeline identity set differs")
    _occurrence(base_state)
    if not _normalize(base_state, base_state, media_path, False):
        raise RuntimeError("Pinned setup state is invalid")
    target = _pool_item(base_pool, MEDIA_UID)
    if (
        len(
            [
                row
                for row in base_pool.get("items", [])
                if row.get("uid") == ORIGINAL_UID
            ]
        )
        != 1
    ):
        raise RuntimeError("Original shared source UID is missing or duplicated")
    if sum(row.get("uid") == MEDIA_UID for row in base_pool.get("items", [])) != 1:
        raise RuntimeError("Imported UID is missing or duplicated")
    mappings = [
        row
        for row in base_pool.get("timelineMappings", [])
        if row.get("timelineUid") == {"value": R4_UID}
    ]
    if len(mappings) != 1 or mappings[0].get("poolItemUid") != {"value": R4_POOL_UID}:
        raise RuntimeError("Pinned R4 timeline proxy mapping differs")
    evidence = target.get("evidence", {})
    props = evidence.get("GetClipProperty", {}).get("value", {})
    if (
        target.get("name", {}).get("value") != "base.mov"
        or props.get("File Name") != "base.mov"
        or props.get("File Path") != str(media_path / "relink/base.mov")
        or props.get("Online Status") != "Online"
        or evidence.get("sourceBytes", {}).get("sha256") != MEDIA_SHA256
        or evidence.get("sourceBytes", {}).get("hashMatches") is not True
    ):
        raise RuntimeError("Pinned imported pool item does not match approved source")
    original_names = {
        "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
        "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
        "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
    }
    matrix_timelines = {
        row.get("GetUniqueId", {}).get("value"): row
        for row in mp[0].get("timelines", [])
    }
    if set(matrix_timelines) != set(original_names):
        raise RuntimeError("Historical saved Matrix timeline identities differ")
    for uid, name in original_names.items():
        historical = matrix_timelines[uid]
        current = _timeline(base_state, uid)
        if (
            historical.get("GetName") != {"value": name}
            or current.get("GetName") != {"value": name}
            or probe.errors(historical)
        ):
            raise RuntimeError(
                "Original timeline identity differs from saved checkpoint"
            )
    return base_state, base_pool


def _media_guard(config, root, probe):
    media = Path(config.get("mediaDir", ""))
    if (
        not media.is_absolute()
        or media.is_symlink()
        or media.parent.is_symlink()
        or not media.is_dir()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only owned synthetic media is allowed")
    manifest_path = media / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or _sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic manifest is missing or changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("files")
    if (
        manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence"
        or not isinstance(entries, list)
        or not entries
    ):
        raise RuntimeError("Manifest does not identify approved synthetic sources")
    expected, seen = {}, set()
    for entry in entries:
        relative = Path(entry.get("path", ""))
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() in {"", "."}
            or relative.as_posix() in seen
        ):
            raise RuntimeError("Manifest source locator is unsafe or duplicated")
        seen.add(relative.as_posix())
        path = media / relative
        components = [
            media / Path(*relative.parts[:index])
            for index in range(1, len(relative.parts) + 1)
        ]
        if (
            any(component.is_symlink() for component in components)
            or not path.is_file()
            or not path.resolve(strict=True).is_relative_to(media.resolve())
            or not isinstance(entry.get("sha256"), str)
            or len(entry["sha256"]) != 64
            or any(char not in "0123456789abcdef" for char in entry["sha256"])
            or type(entry.get("sizeBytes")) is not int
            or path.stat().st_size != entry["sizeBytes"]
            or _sha256(path) != entry["sha256"]
        ):
            raise RuntimeError("Manifest source file hash or size differs")
        expected[str(path)] = entry["sha256"]
    relink_entries = [row for row in entries if row.get("path") == "relink/base.mov"]
    if len(relink_entries) != 1:
        raise RuntimeError("Manifest does not identify one approved relink source")
    entry = relink_entries[0]
    relink = media / "relink"
    source = relink / "base.mov"
    if (
        entry.get("sha256") != MEDIA_SHA256
        or entry.get("sizeBytes") != MEDIA_SIZE
        or relink.is_symlink()
        or not relink.is_dir()
        or {path.name for path in relink.iterdir()} != {"base.mov"}
        or source.is_symlink()
        or not source.is_file()
        or not source.resolve(strict=True).is_relative_to(media.resolve())
        or source.stat().st_size != MEDIA_SIZE
        or _sha256(source) != MEDIA_SHA256
    ):
        raise RuntimeError("Approved relink folder/file hash or size differs")
    return media, relink, source, expected


def run(resolve, config, *, probe):
    """Relink the exact pinned offline item once; do not save or retry."""
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != "r4-recovery"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or output.parent.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only the owned Issue 141 observation directory is allowed")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    journal = output / f"r4-recovery-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def record(method, phase, value):
        _append(journal, method, phase, value)

    def context():
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        project = probe.require_current(
            resolve,
            config,
            {"projectId": PROJECT_ID, "projectName": config["projectName"]},
        )
        timeline = project.GetCurrentTimeline()
        if timeline is None or timeline.GetUniqueId() != R4_UID:
            raise RuntimeError("Exact R4 availability timeline must remain selected")
        return project

    try:
        capture_path = output / CAPTURE_NAME
        setup_capture = _load(capture_path, CAPTURE_SHA256)
        setup_pool_pin = _load(output / POOL_NAME, POOL_SHA256)
        matrix_checkpoint = _load(output / MATRIX_NAME, MATRIX_SHA256)
        transition_journal_path = output / TRANSITION_JOURNAL
        unlink_path = output / UNLINK_CAPTURE
        refusal_path = output / REFUSAL_FILE
        plugin_result_path = PLUGIN_ROOT / PLUGIN_RESULT
        _verify_file(transition_journal_path, TRANSITION_JOURNAL_SHA256)
        unlink_capture = _load(unlink_path, UNLINK_CAPTURE_SHA256)
        refusal = _load(refusal_path, REFUSAL_SHA256)
        plugin_result = _load(plugin_result_path, PLUGIN_RESULT_SHA256)
        rows = [
            json.loads(line)
            for line in transition_journal_path.read_text(encoding="utf-8").splitlines()
        ]
        native_mutations = [
            row
            for row in rows
            if row.get("method") in {"UnlinkClips", "RelinkClips", "SaveProject"}
            and row.get("phase") in {"request", "return", "failure"}
        ]
        if (
            [(row.get("method"), row.get("phase")) for row in native_mutations]
            != [("UnlinkClips", "request"), ("UnlinkClips", "return")]
            or native_mutations[0].get("value", {}).get("uids") != [MEDIA_UID]
            or native_mutations[1].get("value") is not True
            or plugin_result.get("status") != "launcher-failed"
            or refusal.get("reason")
            != "RuntimeError: Unlink did not establish the pinned offline state"
            or unlink_capture.get("phase") != "UnlinkClips"
        ):
            raise RuntimeError("Pinned native unlink failure evidence differs")
        base_state, base_pool = _validate_setup(
            setup_capture,
            setup_pool_pin,
            matrix_checkpoint,
            config,
            probe,
            Path(config["mediaDir"]),
        )
        offline_capture = _load(output / OFFLINE_CAPTURE_NAME, OFFLINE_CAPTURE_SHA256)
        offline_pool_pin = _load(output / OFFLINE_POOL_NAME, OFFLINE_POOL_SHA256)
        offline_passes = offline_capture.get("passes", [])
        offline_pool_passes = offline_pool_pin.get("passes", [])
        if (
            offline_capture.get("stage") != "R4-offline-prefix-read-only"
            or offline_capture.get("consistency") != "equal-adjacent-reads"
            or offline_capture.get("captureFailure") is not None
            or len(offline_passes) != 2
            or offline_passes[0] != offline_passes[1]
            or probe.errors(offline_passes)
            or offline_pool_pin.get("status") != "equal-read-only-pool-inventory"
            or len(offline_pool_passes) != 2
            or offline_pool_passes[0] != offline_pool_passes[1]
            or probe.errors(offline_pool_passes)
            or offline_pool_pin.get("capture", {}).get("sha256")
            != OFFLINE_CAPTURE_SHA256
        ):
            raise RuntimeError("Full pinned offline read-only evidence is incomplete")
        pinned_offline, pinned_offline_pool = offline_passes[0], offline_pool_passes[0]
        if not _normalize(
            pinned_offline, base_state, Path(config["mediaDir"]), True
        ) or not _normalize_pool(
            pinned_offline_pool, base_pool, Path(config["mediaDir"]), True
        ):
            raise RuntimeError(
                "Pinned offline state differs outside target locator/status evidence"
            )
        unlink_passes = unlink_capture.get("timelinePasses", [])
        if len(unlink_passes) != 2 or not isinstance(unlink_passes[0], dict):
            raise RuntimeError(
                "Native unlink postflight does not retain the target occurrence"
            )
        _, offline_item = _occurrence(unlink_passes[0])
        offline_props = (
            offline_item.get("GetMediaPoolItem", {})
            .get("GetClipProperty", {})
            .get("value", {})
        )
        expected_display = "OFFLINE - " + str(
            Path(config["mediaDir"]) / "relink/base.mov"
        )
        if (
            offline_props.get("File Name") != "base.mov"
            or offline_props.get("File Path") != expected_display
            or offline_props.get("Online Status") != "Offline"
        ):
            raise RuntimeError("Pinned native state is not the exact offline target")
        media, folder, source, expected = _media_guard(config, root, probe)
        if not _normalize(
            unlink_passes[0], base_state, media, True
        ) or not _normalize_pool(pinned_offline_pool, base_pool, media, True):
            raise RuntimeError(
                "Pinned R4 offline evidence changes fields outside the target"
            )
        evidence = {
            "pins": {
                "setupCapture": {"name": CAPTURE_NAME, "sha256": CAPTURE_SHA256},
                "setupPool": {"name": POOL_NAME, "sha256": POOL_SHA256},
                "offlineCapture": {
                    "name": OFFLINE_CAPTURE_NAME,
                    "sha256": OFFLINE_CAPTURE_SHA256,
                },
                "offlinePool": {
                    "name": OFFLINE_POOL_NAME,
                    "sha256": OFFLINE_POOL_SHA256,
                },
                "matrix": {"name": MATRIX_NAME, "sha256": MATRIX_SHA256},
                "unlinkJournal": {
                    "name": TRANSITION_JOURNAL,
                    "sha256": TRANSITION_JOURNAL_SHA256,
                },
                "unlinkPostflight": {
                    "name": UNLINK_CAPTURE,
                    "sha256": UNLINK_CAPTURE_SHA256,
                },
                "refusal": {"name": REFUSAL_FILE, "sha256": REFUSAL_SHA256},
                "launcherResult": {
                    "name": PLUGIN_RESULT,
                    "sha256": PLUGIN_RESULT_SHA256,
                },
            },
            "nativeUnlink": {
                "result": True,
                "status": "Offline",
                "path": expected_display,
            },
            "media": {"path": str(source), "bytes": MEDIA_SIZE, "sha256": MEDIA_SHA256},
        }
    except Exception as error:
        record("R4Recovery", "preflight-refusal", f"{type(error).__name__}: {error}")
        raise

    def read_pair(label):
        timeline_passes, pool_passes = [], []
        for _ in range(2):
            try:
                project = context()
                timeline_passes.append(
                    _canonical(
                        probe.observe(
                            resolve,
                            dict(config, stage="R4-relink-only-recovery"),
                            {
                                "projectId": PROJECT_ID,
                                "projectName": config["projectName"],
                            },
                            expected,
                        )
                    )
                )
                project = context()
                pool_passes.append(
                    _canonical(probe._r4_pool_inventory(project, expected))
                )
                context()
            except Exception as error:
                failure = {"error": f"{type(error).__name__}: {error}"}
                diagnostic = getattr(error, "diagnostic", None)
                if diagnostic is not None:
                    failure["diagnostic"] = _canonical(diagnostic)
                timeline_passes.append(failure)
                pool_passes.append(failure)
                break
        value = {
            "label": label,
            "timelinePasses": timeline_passes,
            "poolPasses": pool_passes,
        }
        value["status"] = (
            "equal-adjacent-reads"
            if len(timeline_passes) == 2
            and len(pool_passes) == 2
            and timeline_passes[0] == timeline_passes[1]
            and pool_passes[0] == pool_passes[1]
            and not probe.errors(timeline_passes)
            and not probe.errors(pool_passes)
            else "incomplete-or-inconsistent-refused"
        )
        _write(output / f"r4-recovery-{stamp}-{label}.json", value)
        record("Capture", label, value)
        return value

    try:
        project = context()
        before = read_pair("preflight")
        if before["status"] != "equal-adjacent-reads":
            raise RuntimeError("Fresh offline preflight is incomplete")
        timelines, pools = before["timelinePasses"], before["poolPasses"]
        if timelines != [pinned_offline, pinned_offline] or pools != [
            pinned_offline_pool,
            pinned_offline_pool,
        ]:
            raise RuntimeError(
                "Fresh offline reads differ from the pinned full offline state"
            )
        if not all(_normalize(row, base_state, media, True) for row in timelines):
            raise RuntimeError(
                "Fresh offline timeline state differs outside allowed leaves"
            )
        if not all(_normalize_pool(row, base_pool, media, True) for row in pools):
            raise RuntimeError(
                "Fresh offline pool inventory differs outside allowed leaves"
            )
        for state, inventory in zip(timelines, pools, strict=True):
            _, item = _occurrence(state)
            props = item["GetMediaPoolItem"]["GetClipProperty"]["value"]
            pool_row = _pool_item(inventory, MEDIA_UID)
            bytes_evidence = pool_row.get("evidence", {}).get("sourceBytes", {})
            if (
                props.get("Online Status") != "Offline"
                or props.get("File Path") != expected_display
                or bytes_evidence
                != {
                    "status": "offline-locator-not-accessed",
                    "approvedLocator": str(source),
                    "expectedSha256": MEDIA_SHA256,
                }
            ):
                raise RuntimeError(
                    "Fresh Resolve evidence does not prove exact offline state"
                )
        project = context()
        target = project.GetMediaPool().GetRootFolder()
        handles, seen = [], set()

        def visit(folder_handle):
            if id(folder_handle) in seen:
                raise RuntimeError("Pool folder tree is cyclic or repeated")
            seen.add(id(folder_handle))
            clips = folder_handle.GetClipList()
            children = folder_handle.GetSubFolderList()
            if not isinstance(clips, (list, tuple)) or not isinstance(
                children, (list, tuple)
            ):
                raise RuntimeError("Pool folder contents are unreadable")
            for clip in clips:
                if clip.GetUniqueId() == MEDIA_UID:
                    handles.append(clip)
            for child in children:
                visit(child)

        visit(target)
        if len(handles) != 1 or handles[0].GetUniqueId() != MEDIA_UID:
            raise RuntimeError("Exact imported media handle is missing or duplicated")
        # Recheck source immediately before the one allowed mutation.
        if (
            source.is_symlink()
            or source.stat().st_size != MEDIA_SIZE
            or _sha256(source) != MEDIA_SHA256
        ):
            raise RuntimeError("Approved relink media changed before call")
        project = context()
        record(
            "RelinkClips",
            "request",
            {"uids": [MEDIA_UID], "folderPath": str(folder), "itemUid": ITEM_UID},
        )
        result, error = None, None
        try:
            result = project.GetMediaPool().RelinkClips([handles[0]], str(folder))
            record("RelinkClips", "return", result)
        except Exception as caught:
            error = caught
            record("RelinkClips", "failure", f"{type(caught).__name__}: {caught}")
        post = read_pair("postflight")
        if post["status"] != "equal-adjacent-reads":
            raise RuntimeError("Relink postflight is incomplete; no retry or save")
        for state, inventory in zip(
            post["timelinePasses"], post["poolPasses"], strict=True
        ):
            if state != base_state or inventory != base_pool:
                raise RuntimeError("Relink postflight differs from pinned online setup")
            _timeline_row, item = _occurrence(state)
            props = item["GetMediaPoolItem"]["GetClipProperty"]["value"]
            row = _pool_item(inventory, MEDIA_UID)
            pool_props = row["evidence"]["GetClipProperty"]["value"]
            for values in (props, pool_props):
                if (
                    values.get("Online Status") != "Online"
                    or values.get("File Path") != str(source)
                    or values.get("File Name") != "base.mov"
                ):
                    raise RuntimeError(
                        "Relink did not restore exact online identity/path"
                    )
            for value in (
                item["GetMediaPoolItem"].get("sourceBytes", {}),
                row["evidence"].get("sourceBytes", {}),
            ):
                if (
                    value.get("sha256") != MEDIA_SHA256
                    or value.get("hashMatches") is not True
                ):
                    raise RuntimeError(
                        "Relink byte evidence differs from approved source"
                    )
        if (
            source.is_symlink()
            or source.stat().st_size != MEDIA_SIZE
            or _sha256(source) != MEDIA_SHA256
        ):
            raise RuntimeError("Approved relink media changed after call")
        status = "relinked-online-unsaved"
        if result is not True or error is not None:
            status = "relink-refused-but-restored-online-unsaved"
        record(
            "R4Recovery",
            "complete",
            {
                "status": status,
                "return": result,
                "error": None if error is None else str(error),
            },
        )
        return {
            "status": status,
            "journal": str(journal),
            "preflight": str(output / f"r4-recovery-{stamp}-preflight.json"),
            "postflight": str(output / f"r4-recovery-{stamp}-postflight.json"),
            "evidence": evidence,
        }
    except Exception as error:
        record(
            "R4Recovery",
            "refusal",
            {"reason": f"{type(error).__name__}: {error}", "evidence": evidence},
        )
        _write(
            output / f"r4-recovery-refusal-{stamp}.json",
            {"reason": f"{type(error).__name__}: {error}", "evidence": evidence},
        )
        raise
