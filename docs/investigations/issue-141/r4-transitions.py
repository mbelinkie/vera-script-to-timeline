"""One guarded unlink/relink cycle for the isolated Issue 141 R4 item."""

import json
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
BUILD = [21, 1, 0, 14, ""]
CAPTURE_NAME = "capture-20261001T003310.397326Z.json"
CAPTURE_SHA256 = "f3a321fcd5ae47c90e25b3dcf254a0d983ff0bdde8862700b2411c710b3fe0fa"
POOL_NAME = "r4-pool-read-only-20261001T003310.397326Z.json"
POOL_SHA256 = "ac6f4661f59f910029dae51dcc758bd1d766e8f810fb4996fcee1b18c681e751"
MATRIX_NAME = "capture-20260930T223313.312609Z-saved.json"
MATRIX_SHA256 = "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
FINALIZE_JOURNAL_NAME = "r4-finalize-20261001T005016.518644Z.jsonl"
FINALIZE_JOURNAL_SHA256 = (
    "82c3bfbf88497bc110a2198e5a685086e6a6f61cb7ec35af4314e95cb4ebf894"
)
FINALIZE_RESULT_NAME = "vera-issue-141-observation-result-20261001T005016.027177Z.json"
FINALIZE_RESULT_SHA256 = (
    "e9bfe830d653e706d8be7e6a601e139655e53adff55b30c8eb4346071050b9b3"
)
R4_UID = "64de8a4c-86bd-4f19-9d20-47b8940f610b"
R4_POOL_UID = "91853c24-9e0c-435c-8550-209a76425270"
MEDIA_UID = "81d81dc0-4c37-478b-8079-03debba5e780"
ORIGINAL_UID = "9202163a-8381-43e6-9157-3a60f35c6f79"
ITEM_UID = "af55478a-0ba3-458a-a6e1-e47b2544111d"
ORIGINAL_TIMELINES = {
    "29ae8331-b86e-4041-a548-960695cc7b24": "VERA 141 Batched Matrix",
    "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
    "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
}
MEDIA_SHA256 = "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942"
MEDIA_SIZE = 792_989
PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)


def _canonical(value):
    return json.loads(json.dumps(value, allow_nan=False))


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


def _load(path, digest, probe):
    if path.is_symlink() or not path.is_file() or probe.sha256(path) != digest:
        raise RuntimeError(f"Pinned evidence is missing or changed: {path.name}")
    return json.loads(path.read_text(encoding="utf-8"))


def _timeline(state, uid):
    rows = [
        row
        for row in state.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == uid
    ]
    if len(rows) != 1:
        raise RuntimeError("Timeline identity is missing or duplicated")
    return rows[0]


def _pool_item(inventory, uid):
    rows = [row for row in inventory.get("items", []) if row.get("uid") == uid]
    if len(rows) != 1:
        raise RuntimeError(f"Pool item {uid} is missing or duplicated")
    return rows[0]


def _occurrence(timeline):
    found = [
        (track, item)
        for track in timeline.get("tracks", [])
        for item in track.get("items", [])
    ]
    if len(found) != 1:
        raise RuntimeError("R4 must retain exactly one timeline occurrence")
    track, item = found[0]
    media_uid = item.get("GetMediaPoolItem", {}).get("GetUniqueId", {}).get("value")
    if (
        (track.get("type"), track.get("index")) != ("video", 1)
        or item.get("GetUniqueId", {}).get("value") != ITEM_UID
        or media_uid != MEDIA_UID
        or item.get("GetStart") != {"value": 0}
        or item.get("GetEnd") != {"value": 199}
        or item.get("GetDuration") != {"value": 199}
        or item.get("GetSourceStartFrame") != {"value": 0}
        or item.get("GetSourceEndFrame") != {"value": 199}
        or item.get("GetTrackTypeAndIndex") != {"value": ["video", 1]}
    ):
        raise RuntimeError("R4 occurrence identity or range differs")
    return item


def _validate_original_timelines(setup, checkpoint, probe):
    setup_rows = {
        row.get("GetUniqueId", {}).get("value"): row
        for row in setup.get("timelines", [])
    }
    historical_rows = {
        row.get("GetUniqueId", {}).get("value"): row
        for row in checkpoint.get("timelines", [])
    }
    if set(setup_rows) != set(ORIGINAL_TIMELINES) | {R4_UID}:
        raise RuntimeError("Pinned setup timeline identity set differs")
    if set(historical_rows) != set(ORIGINAL_TIMELINES):
        raise RuntimeError("Saved Matrix checkpoint timeline identity set differs")
    for uid, name in ORIGINAL_TIMELINES.items():
        historical = historical_rows[uid]
        if (
            historical.get("GetName") != {"value": name}
            or historical.get("GetUniqueId") != {"value": uid}
            or probe.errors(historical)
            or not isinstance(historical.get("GetMarkers", {}).get("value"), dict)
            or not isinstance(historical.get("GetStartFrame", {}).get("value"), int)
            or not isinstance(historical.get("GetEndFrame", {}).get("value"), int)
        ):
            raise RuntimeError(
                "Saved Matrix historical identity/marker/range evidence differs"
            )
        if setup_rows[uid].get("GetName") != {"value": name}:
            raise RuntimeError("Pinned setup original timeline name differs")


def _file_guard(config, root, probe):
    media = Path(config.get("mediaDir", ""))
    if (
        not media.is_absolute()
        or media.is_symlink()
        or media.parent.is_symlink()
        or not media.is_dir()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only slice-owned synthetic media is allowed")
    manifest_path = media / "manifest.json"
    if (
        manifest_path.is_symlink()
        or not manifest_path.is_file()
        or probe.sha256(manifest_path) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic media manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Synthetic media manifest kind differs")
    entry = next(
        (
            row
            for row in manifest.get("files", [])
            if row.get("path") == "relink/base.mov"
        ),
        None,
    )
    if (
        entry is None
        or entry.get("sha256") != MEDIA_SHA256
        or entry.get("sizeBytes") != MEDIA_SIZE
    ):
        raise RuntimeError("Approved relink copy is not pinned by manifest")
    relink = media / "relink"
    source = relink / "base.mov"
    if (
        relink.is_symlink()
        or not relink.is_dir()
        or {path.name for path in relink.iterdir()} != {"base.mov"}
        or source.is_symlink()
        or not source.is_file()
        or not source.resolve(strict=True).is_relative_to(media.resolve())
        or source.stat().st_size != MEDIA_SIZE
        or probe.sha256(source) != MEDIA_SHA256
    ):
        raise RuntimeError("Approved relink folder or file bytes differ")
    return media, relink, source


def _validate_online_state(state, inventory, media_path, *, offline=False):
    timeline = _timeline(state, R4_UID)
    if timeline.get("GetName") != {"value": "VERA 141 R4 availability"}:
        raise RuntimeError("R4 timeline name differs")
    occurrence = _occurrence(timeline)
    media_evidence = occurrence.get("GetMediaPoolItem", {})
    pool_row = _pool_item(inventory, MEDIA_UID)
    pool_evidence = pool_row.get("evidence", {})
    props = media_evidence.get("GetClipProperty", {}).get("value", {})
    pool_props = pool_evidence.get("GetClipProperty", {}).get("value", {})
    for values in (props, pool_props):
        path = values.get("File Path")
        if offline:
            if (
                values.get("Online Status") != "Offline"
                or path not in ("", str(media_path / "relink/base.mov"))
                or values.get("File Name") != "base.mov"
            ):
                raise RuntimeError("Explicit offline locator/status is ambiguous")
        elif (
            values.get("Online Status") != "Online"
            or path != str(media_path / "relink/base.mov")
            or values.get("File Name") != "base.mov"
        ):
            raise RuntimeError(
                "Imported media is not explicitly online at approved path"
            )
    if (
        media_evidence.get("GetUniqueId") != {"value": MEDIA_UID}
        or pool_row.get("uid") != MEDIA_UID
        or pool_row.get("name", {}).get("value") != "base.mov"
    ):
        raise RuntimeError("Imported pool-item identity differs")
    mappings = [
        row
        for row in inventory.get("timelineMappings", [])
        if row.get("timelineUid") == {"value": R4_UID}
    ]
    if len(mappings) != 1 or mappings[0].get("poolItemUid") != {"value": R4_POOL_UID}:
        raise RuntimeError("R4 timeline-to-pool-proxy identity differs")
    if not offline and any(
        evidence.get("sourceBytes", {}).get("sha256") != MEDIA_SHA256
        or evidence.get("sourceBytes", {}).get("hashMatches") is not True
        for evidence in (media_evidence, pool_evidence)
    ):
        raise RuntimeError("Online imported media hash evidence differs")
    return timeline, occurrence, pool_row


def _normalize_offline(current, baseline, media_path):
    current, baseline = deepcopy(current), deepcopy(baseline)
    path_fields = {"Clip Directory", "File Path", "Online Status"}

    def normalize_props(actual, expected):
        if actual.keys() != expected.keys():
            raise RuntimeError("Offline properties added or removed unrelated keys")
        for key, value in expected.items():
            observed = actual[key]
            if observed == value:
                continue
            if key not in path_fields:
                raise RuntimeError(
                    f"Offline transition changed unrelated property {key}"
                )
            if key == "Online Status" and observed != "Offline":
                raise RuntimeError("Offline status is not explicit")
            if key == "File Path" and observed not in (
                "",
                str(media_path / "relink/base.mov"),
            ):
                raise RuntimeError("Offline item exposes an unexpected path")
            if key == "Clip Directory" and observed not in (
                "",
                str(media_path / "relink"),
            ):
                raise RuntimeError("Offline item exposes an unexpected directory")
            actual[key] = value

    current_timeline = _timeline(current, R4_UID)
    baseline_timeline = _timeline(baseline, R4_UID)
    current_occurrence = _occurrence(current_timeline)
    baseline_occurrence = _occurrence(baseline_timeline)
    for current_evidence, baseline_evidence in (
        (
            current_occurrence["GetMediaPoolItem"],
            baseline_occurrence["GetMediaPoolItem"],
        ),
    ):
        normalize_props(
            current_evidence["GetClipProperty"]["value"],
            baseline_evidence["GetClipProperty"]["value"],
        )
        current_evidence["sourceBytes"] = deepcopy(baseline_evidence["sourceBytes"])
    return current == baseline


def _normalize_offline_pool(current, baseline, media_path):
    current, baseline = deepcopy(current), deepcopy(baseline)
    current_row = _pool_item(current, MEDIA_UID)
    baseline_row = _pool_item(baseline, MEDIA_UID)
    current_evidence, baseline_evidence = (
        current_row["evidence"],
        baseline_row["evidence"],
    )
    actual = current_evidence["GetClipProperty"]["value"]
    expected = baseline_evidence["GetClipProperty"]["value"]
    if actual.keys() != expected.keys():
        raise RuntimeError("Offline pool properties added or removed keys")
    allowed = {
        "Online Status": {"Offline"},
        "File Path": {"", str(media_path / "relink/base.mov")},
        "Clip Directory": {"", str(media_path / "relink")},
    }
    for key, value in expected.items():
        observed = actual[key]
        if observed == value:
            continue
        if key in allowed and observed in allowed[key]:
            actual[key] = value
        else:
            raise RuntimeError(
                f"Offline pool transition changed unrelated property {key}"
            )
    current_evidence["sourceBytes"] = deepcopy(baseline_evidence["sourceBytes"])
    return current == baseline


def _find_media_handle(project, uid):
    root = project.GetMediaPool().GetRootFolder()
    found = []
    seen = set()

    def visit(folder):
        if id(folder) in seen:
            raise RuntimeError("Pool folder tree is cyclic or repeated")
        seen.add(id(folder))
        clips = folder.GetClipList()
        children = folder.GetSubFolderList()
        if not isinstance(clips, (list, tuple)) or not isinstance(
            children, (list, tuple)
        ):
            raise RuntimeError("Pool folder contents are unreadable")
        for clip in clips:
            if clip.GetUniqueId() == uid:
                found.append(clip)
        for child in children:
            visit(child)

    if root is None:
        raise RuntimeError("Media-pool root is unavailable")
    visit(root)
    if len(found) != 1:
        raise RuntimeError("Exact imported pool-item handle is missing or duplicated")
    return found[0]


def run(resolve, config, *, probe):
    """Unlink and relink only the exact new R4 pool item, then save restored state."""
    output = Path(config.get("outputDir", ""))
    root = Path(probe.ROOT).resolve()
    if (
        config.get("action") != "r4-transitions"
        or config.get("externalScriptingSetting") != "None"
        or not output.is_absolute()
        or output.is_symlink()
        or output.parent.is_symlink()
        or not output.is_dir()
        or (root / "out").is_symlink()
        or not (root / "out").is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
    ):
        raise RuntimeError("Only an existing slice-owned observation may be used")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    journal = output / f"r4-transitions-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()
    stamps = {
        "version": resolve.GetVersion(),
        "setupCapture": {"name": CAPTURE_NAME, "sha256": CAPTURE_SHA256},
        "setupPool": {"name": POOL_NAME, "sha256": POOL_SHA256},
        "finalizeJournal": {
            "name": FINALIZE_JOURNAL_NAME,
            "sha256": FINALIZE_JOURNAL_SHA256,
        },
        "finalizeResult": {
            "name": FINALIZE_RESULT_NAME,
            "sha256": FINALIZE_RESULT_SHA256,
        },
    }

    def refuse(error, evidence=None):
        reason = f"{type(error).__name__}: {error}"
        _append(
            journal,
            "R4Transitions",
            "refusal",
            {"reason": reason, "evidence": evidence},
        )
        _write(
            output / f"r4-transitions-refusal-{stamp}.json",
            {"reason": reason, "evidence": evidence, "stamps": stamps},
        )
        raise error

    _append(journal, "R4Transitions", "start", stamps)
    try:
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        if (
            not isinstance(FINALIZE_JOURNAL_SHA256, str)
            or not isinstance(FINALIZE_RESULT_SHA256, str)
            or FINALIZE_JOURNAL_NAME.startswith("PENDING")
            or FINALIZE_RESULT_NAME.startswith("PENDING")
        ):
            raise RuntimeError(
                "Successful save-finalization journal/result pins are pending"
            )
        capture_path = output / CAPTURE_NAME
        capture = _load(capture_path, CAPTURE_SHA256, probe)
        pool_pin = _load(output / POOL_NAME, POOL_SHA256, probe)
        checkpoint = _load(output / MATRIX_NAME, MATRIX_SHA256, probe)
        finalize_journal_path = output / FINALIZE_JOURNAL_NAME
        finalize_result_path = PLUGIN_ROOT / FINALIZE_RESULT_NAME
        if (
            finalize_journal_path.is_symlink()
            or not finalize_journal_path.is_file()
            or probe.sha256(finalize_journal_path) != FINALIZE_JOURNAL_SHA256
            or finalize_result_path.is_symlink()
            or not finalize_result_path.is_file()
            or probe.sha256(finalize_result_path) != FINALIZE_RESULT_SHA256
        ):
            raise RuntimeError("Successful save-finalization evidence differs")
        journal_rows = [
            json.loads(line)
            for line in finalize_journal_path.read_text(encoding="utf-8").splitlines()
        ]
        result_value = json.loads(finalize_result_path.read_text(encoding="utf-8"))
        save_requests = [
            row
            for row in journal_rows
            if row.get("method") == "SaveProject" and row.get("phase") == "request"
        ]
        save_returns = [
            row
            for row in journal_rows
            if row.get("method") == "SaveProject" and row.get("phase") == "return"
        ]
        if not any(
            row.get("method") == "R4Finalize"
            and row.get("phase") == "complete"
            and row.get("value", {}).get("status") == "saved-pinned-r4-state"
            for row in journal_rows
        ) or (
            result_value.get("status") != "saved-pinned-r4-state"
            or len(save_requests) != 1
            or len(save_returns) != 1
            or save_returns[0].get("value") is not True
        ):
            raise RuntimeError("Save-finalization completion is not evidenced")
        capture_passes = capture.get("passes", [])
        setup = (
            capture_passes[0]
            if len(capture_passes) == 2 and capture_passes[0] == capture_passes[1]
            else None
        )
        inventory_passes = pool_pin.get("passes", [])
        setup_pool = (
            inventory_passes[0]
            if len(inventory_passes) == 2 and inventory_passes[0] == inventory_passes[1]
            else None
        )
        if (
            capture.get("consistency") != "equal-adjacent-reads"
            or capture.get("captureFailure") is not None
            or capture.get("stage") != "R4-post-append-partial-state-read-only"
            or setup is None
            or probe.errors(setup)
            or setup_pool is None
            or probe.errors(setup_pool)
            or pool_pin.get("status") != "equal-read-only-pool-inventory"
            or Path(pool_pin.get("capture", {}).get("capturePath", "")).name
            != capture_path.name
            or pool_pin.get("capture", {}).get("sha256") != CAPTURE_SHA256
            or setup.get("projectId") != PROJECT_ID
            or setup.get("projectName") != config.get("projectName")
            or capture.get("environment", {}).get("version") != BUILD
        ):
            raise RuntimeError("Pinned R4 setup capture or inventory is incomplete")
        checkpoint_passes = checkpoint.get("passes", [])
        if (
            checkpoint.get("consistency") != "equal-adjacent-reads"
            or checkpoint.get("captureFailure") is not None
            or len(checkpoint_passes) != 2
            or checkpoint_passes[0] != checkpoint_passes[1]
            or checkpoint_passes[0].get("projectId") != PROJECT_ID
            or checkpoint_passes[0].get("projectName") != config.get("projectName")
            or checkpoint.get("environment", {}).get("version") != BUILD
            or probe.errors(checkpoint_passes)
        ):
            raise RuntimeError("Historical saved Matrix checkpoint is incomplete")
        _validate_original_timelines(setup, checkpoint_passes[0], probe)
        media_path, relink_folder, source = _file_guard(config, root, probe)
        if source.stat().st_size != MEDIA_SIZE:
            raise RuntimeError("Approved relink media byte length differs")
        _validate_online_state(setup, setup_pool, media_path)
        if (
            MEDIA_UID == ORIGINAL_UID
            or _pool_item(setup_pool, ORIGINAL_UID).get("uid") != ORIGINAL_UID
        ):
            raise RuntimeError(
                "New imported UID is not distinct from original shared source"
            )
        if (
            len(
                [
                    row
                    for row in setup_pool.get("items", [])
                    if row.get("uid") == MEDIA_UID
                ]
            )
            != 1
        ):
            raise RuntimeError("New imported UID must appear exactly once")
        identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}
        manifest = json.loads(
            (media_path / "manifest.json").read_text(encoding="utf-8")
        )
        expected = {
            str(media_path / entry["path"]): entry["sha256"]
            for entry in manifest["files"]
        }
    except Exception as error:
        refuse(error)

    config_live = dict(config, stage="R4-unlink-relink-transition")

    def context():
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Resolve product/build changed during transition")
        project = probe.require_current(resolve, config_live, identity)
        selected = project.GetCurrentTimeline()
        if selected is None or selected.GetUniqueId() != R4_UID:
            raise RuntimeError("Exact isolated R4 timeline must remain selected")
        return project

    def read_pair():
        timelines, pools = [], []
        for _ in range(2):
            try:
                project = context()
                timelines.append(
                    _canonical(probe.observe(resolve, config_live, identity, expected))
                )
                project = context()
                pools.append(_canonical(probe._r4_pool_inventory(project, expected)))
                context()
            except Exception as error:
                failure = {"error": f"{type(error).__name__}: {error}"}
                diagnostic = getattr(error, "diagnostic", None)
                if diagnostic is not None:
                    try:
                        failure["diagnostic"] = _canonical(diagnostic)
                    except (TypeError, ValueError):
                        failure["diagnostic"] = str(diagnostic)
                timelines.append(failure)
                pools.append(failure)
                break
        return {"timelinePasses": timelines, "poolPasses": pools}

    def capture(label, phase):
        state = read_pair()
        state["phase"] = phase
        state["status"] = (
            "equal-adjacent-reads"
            if len(state["timelinePasses"]) == 2
            and len(state["poolPasses"]) == 2
            and state["timelinePasses"][0] == state["timelinePasses"][1]
            and state["poolPasses"][0] == state["poolPasses"][1]
            else "incomplete-or-inconsistent-refused"
        )
        path = output / f"r4-transitions-{stamp}-{label}.json"
        _write(path, state)
        _append(journal, phase, "readback", {"path": str(path), "state": state})
        return state

    def assert_state(state, offline):
        if state["status"] != "equal-adjacent-reads":
            raise RuntimeError("Transition readback is incomplete or inconsistent")
        timeline_values = state["timelinePasses"]
        pool_values = state["poolPasses"]
        if offline:
            checks = [
                _normalize_offline(value, setup, media_path)
                for value in timeline_values
            ] + [
                _normalize_offline_pool(value, setup_pool, media_path)
                for value in pool_values
            ]
            if not all(checks):
                raise RuntimeError(
                    "Offline readback differs beyond availability leaves"
                )
            for timeline_value, pool_value in zip(
                timeline_values, pool_values, strict=True
            ):
                _validate_online_state(
                    timeline_value, pool_value, media_path, offline=True
                )
        else:
            if timeline_values != [setup, setup] or pool_values != [
                setup_pool,
                setup_pool,
            ]:
                raise RuntimeError("Online readback differs from accepted setup")
            for timeline_value, pool_value in zip(
                timeline_values, pool_values, strict=True
            ):
                _validate_online_state(timeline_value, pool_value, media_path)
        if probe.sha256(source) != MEDIA_SHA256 or source.stat().st_size != MEDIA_SIZE:
            raise RuntimeError("Approved source bytes changed during transition")

    def transition(method, phase, recovery=False):
        project = context()
        guard = {"timelinePasses": [], "poolPasses": []}
        for _ in range(2):
            project = context()
            guard["timelinePasses"].append(
                _canonical(probe.observe(resolve, config_live, identity, expected))
            )
            project = context()
            guard["poolPasses"].append(
                _canonical(probe._r4_pool_inventory(project, expected))
            )
        if method == "RelinkClips":
            if (
                guard["timelinePasses"][0] != guard["timelinePasses"][1]
                or guard["poolPasses"][0] != guard["poolPasses"][1]
                or not _normalize_offline(guard["timelinePasses"][0], setup, media_path)
                or not _normalize_offline_pool(
                    guard["poolPasses"][0], setup_pool, media_path
                )
            ):
                raise RuntimeError(
                    "Relink preflight no longer matches the verified offline state"
                )
        elif guard["timelinePasses"] != [setup, setup] or guard["poolPasses"] != [
            setup_pool,
            setup_pool,
        ]:
            raise RuntimeError(
                "Transition preflight no longer matches the accepted online state"
            )
        _file_guard(config, root, probe)
        inventory = guard["poolPasses"][0]
        project = context()
        handle = _find_media_handle(project, MEDIA_UID)
        if handle.GetUniqueId() != MEDIA_UID:
            raise RuntimeError("Resolved transition handle has a different UID")
        row = _pool_item(inventory, MEDIA_UID)
        if method == "RelinkClips":
            args = ([handle], str(relink_folder))
            audit = {
                "uids": [MEDIA_UID],
                "folderPath": str(relink_folder),
                "folderUid": row.get("folderUid"),
                "recovery": recovery,
            }
        else:
            args = ([handle],)
            audit = {"uids": [MEDIA_UID], "folderUid": row.get("folderUid")}
        _append(journal, method, "request", audit)
        result, error = None, None
        try:
            result = getattr(project.GetMediaPool(), method)(*args)
            _append(journal, method, "return", result)
        except Exception as caught:
            error = caught
            _append(journal, method, "failure", f"{type(caught).__name__}: {caught}")
        post = capture(f"{phase}-postflight", method)
        return result, error, post

    failure_evidence = None
    completion_status = "restored-online-and-saved"
    try:
        before = capture("before", "InitialPreflight")
        assert_state(before, offline=False)
        unlink_result, unlink_error, offline_state = transition("UnlinkClips", "unlink")
        failure_evidence = {
            "unlinkResult": unlink_result,
            "unlinkError": None if unlink_error is None else str(unlink_error),
            "readback": offline_state,
        }
        try:
            assert_state(offline_state, offline=True)
        except Exception as error:
            raise RuntimeError(
                "Unlink did not establish the pinned offline state"
            ) from error
        if unlink_result is not True or unlink_error is not None:
            recovery_result, recovery_error, recovery_state = transition(
                "RelinkClips", "recovery-relink", recovery=True
            )
            assert_state(recovery_state, offline=False)
            completion_status = "recovered-online-after-unlink-return-refusal"
            if recovery_result is not True or recovery_error is not None:
                completion_status = (
                    "recovered-online-after-unlink-and-recovery-return-refusal"
                )
                _append(
                    journal,
                    "R4Transitions",
                    "recovery-restored",
                    {"status": "verified-online-after-recovery-return-refusal"},
                )
        else:
            relink_result, relink_error, online_state = transition(
                "RelinkClips", "planned-relink"
            )
            assert_state(online_state, offline=False)
            if relink_result is not True or relink_error is not None:
                completion_status = "restored-online-after-relink-return-refusal"
                _append(
                    journal,
                    "R4Transitions",
                    "relink-return-refused-restored",
                    {
                        "result": relink_result,
                        "error": None if relink_error is None else str(relink_error),
                        "state": "verified-online",
                    },
                )
        context()
        final_state = capture("final-before-save", "PreSave")
        assert_state(final_state, offline=False)
        _append(journal, "SaveProject", "request", {"projectId": PROJECT_ID})
        save_result, save_error = None, None
        try:
            context()
            save_result = resolve.GetProjectManager().SaveProject()
            _append(journal, "SaveProject", "return", save_result)
        except Exception as error:
            save_error = error
            _append(
                journal, "SaveProject", "failure", f"{type(error).__name__}: {error}"
            )
        saved_state = capture("post-save", "PostSave")
        assert_state(saved_state, offline=False)
        if save_result is not True or save_error is not None:
            raise RuntimeError(
                "SaveProject refused the restored online state"
            ) from save_error
    except Exception as error:
        refuse(error, failure_evidence)
    _append(journal, "R4Transitions", "complete", {"status": completion_status})
    return {"status": completion_status, "journal": str(journal)}
