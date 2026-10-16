"""One pinned attempt to import the retained audio render preset."""

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
MATRIX_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
BUILD = [21, 1, 0, 14, ""]
PIN_NAME = "matrix-checkpoint-20261001T015209.473668Z-matrix-observation.json"
PIN_SHA = "0220a23be312aea5906900dd094c8e21b363294bb11f9b0f1201ab23f40c4cbf"
FAILED_RUN = "audio-output-20261001T021255.680023Z"
EXPORT_RUN = "audio-output-20261001T015945.287072Z"
EXPORT_JOURNAL_SHA = "19bc611d3c32ac686f5f389f3dd414fff04bf3a899f50c962ef3b98a5f235509"
JOURNAL_SHA = "fda00cbecbea749aab7d61ae0185b00069e4f639908c7997cc5bffe4098f2f7f"
PREFLIGHT_SHA = "3dfc30798ca4769d719d52028b508f8eb8261bf2daf61a9a0255f52091d765b0"
XML_SHA = "1b3b21a728c3216f9782d87aa2feae977747c377901eb6b81ed5a83a2da06595"
RESULT_NAME = "vera-issue-141-observation-result-20261001T021255.149341Z.json"
RESULT_SHA = "0f58231798b54d00f7d4c43aeae99ef21895c1e1408108838176dce84d6762dc"
REFUSAL_RUN = "audio-render-recovery-20261001T023017.433448Z"
REFUSAL_JOURNAL_SHA = "a90db38f79037940895fd5eea58de1a53ca61c0340877a9ab7808f350bd2d142"
REFUSAL_RESULT_NAME = "vera-issue-141-observation-result-20261001T023017.194070Z.json"
REFUSAL_RESULT_SHA = "7428e71e67bfb894c3dccf15ab8921b9d4d8e4b78d822aa865d329da7809242f"
DIAGNOSTIC_NAME = "capture-20261001T023200.897507Z.json"
DIAGNOSTIC_SHA = "9aefdcdb5dcb25c7a38d7c2e573ccc9cde049c5806f652c4fac3260d2839bc4a"
IMPORT_RUN = "audio-render-recovery-20261001T023845.073023Z"
IMPORT_RESULT_NAME = "vera-issue-141-observation-result-20261001T023844.795069Z.json"
IMPORT_RESULT_SHA = "9f603d5e1169f0797c75b67c701e9bc4b440bed4cdcd10948fb8cff22ca2862d"
IMPORT_JOURNAL_SHA = "b6d1b995edd61715b884e337a945c95340373e55bb2e1aca76f89f3b4ac45a48"
IMPORT_POSTFLIGHT_SHA = (
    "b2c10cf1a53236ec1b05f17554e36e6f9a40e0ce005feb19b0fd096a04ecb7bc"
)
TOGGLE_RUN = "audio-render-recovery-20261001T024627.794573Z"
TOGGLE_RESULT_NAME = "vera-issue-141-observation-result-20261001T024627.450485Z.json"
TOGGLE_RESULT_SHA = "6fe2a03b0101aa70a9735b2ba184c167a109501093f5bb0f477ef36d8c96f2c9"
TOGGLE_JOURNAL_SHA = "fb698ab793fb3cbfc7a475507a0a2b985cc5a176ad52e557c7d2e5ec10e97a81"
PRESET_NAME = "VERA141_AUDIO_OUTPUT_20261001T015945.287072Z"
PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


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


def _sources(config, media):
    manifest = media / "manifest.json"
    if (
        manifest.is_symlink()
        or not manifest.is_file()
        or _sha256(manifest) != config.get("manifestSha256")
    ):
        raise RuntimeError("Synthetic media manifest changed")
    value = json.loads(manifest.read_text(encoding="utf-8"))
    if value.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise RuntimeError("Synthetic media manifest kind differs")
    expected, seen = {}, set()
    rows = value.get("files")
    if not isinstance(rows, list):
        raise RuntimeError("Synthetic media manifest file list is invalid")
    for row in rows:
        relative = Path(row["path"])
        path = media / relative
        components = [
            media / Path(*relative.parts[:i]) for i in range(1, len(relative.parts) + 1)
        ]
        if (
            not relative.parts
            or relative.is_absolute()
            or ".." in relative.parts
            or relative.as_posix() in seen
            or any(component.is_symlink() for component in components)
            or not path.is_file()
            or not path.resolve(strict=True).is_relative_to(media.resolve())
            or type(row.get("sizeBytes")) is not int
            or path.stat().st_size != row["sizeBytes"]
            or not isinstance(row.get("sha256"), str)
            or _sha256(path) != row["sha256"]
        ):
            raise RuntimeError("Synthetic source bytes or locator differ from manifest")
        expected[str(path)] = row["sha256"]
        seen.add(relative.as_posix())
    if not expected:
        raise RuntimeError("Synthetic media manifest has no source files")
    return expected


def _pin(path, probe):
    if (
        path.name != PIN_NAME
        or path.is_symlink()
        or not path.is_file()
        or _sha256(path) != PIN_SHA
    ):
        raise RuntimeError("Selected-Matrix checkpoint is missing or changed")
    value = json.loads(path.read_text(encoding="utf-8"))
    timelines, pools = value.get("timelinePasses"), value.get("poolPasses")
    if (
        value.get("selectedTimelineUid") != MATRIX_ID
        or value.get("timelineConsistency") != "equal-adjacent-reads"
        or value.get("poolConsistency") != "equal-adjacent-reads"
        or not isinstance(timelines, list)
        or len(timelines) != 2
        or timelines[0] != timelines[1]
        or probe.errors(timelines)
        or not isinstance(pools, list)
        or len(pools) != 2
        or pools[0] != pools[1]
        or probe.errors(pools)
        or timelines[0].get("projectId") != PROJECT_ID
    ):
        raise RuntimeError("Selected-Matrix checkpoint is incomplete")
    matrix = [
        row
        for row in timelines[0].get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == MATRIX_ID
    ]
    if len(matrix) != 1 or matrix[0].get("GetName") != {
        "value": "VERA 141 Batched Matrix"
    }:
        raise RuntimeError("Checkpoint does not identify the exact selected Matrix")
    return timelines[0], pools[0]


def run(resolve, config, *, probe):
    select_format = config.get("action") == "audio-format-selection-recovery"
    toggle = config.get("action") == "audio-video-toggle-recovery" or select_format
    root = Path(probe.ROOT).resolve()
    output, media = Path(config.get("outputDir", "")), Path(config.get("mediaDir", ""))
    if (
        config.get("action")
        not in {
            "audio-render-recovery",
            "audio-video-toggle-recovery",
            "audio-format-selection-recovery",
        }
        or config.get("externalScriptingSetting") != "None"
        or not config.get("projectName", "").startswith(probe.PREFIX)
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
        or not media.is_absolute()
        or media.is_symlink()
        or not media.is_dir()
        or media.parent.resolve() != (root / "out").resolve()
        or not media.name.startswith("issue-141-media-")
    ):
        raise RuntimeError("Only owned Issue 141 paths and action are allowed")

    pin_path = Path(config.get("checkpointPath", ""))
    if not pin_path.is_absolute() or pin_path.parent.resolve() != output.resolve():
        raise RuntimeError("Selected-Matrix checkpoint path is not owned")
    pinned_timeline, pinned_pool = _pin(pin_path, probe)
    expected = _sources(config, media)
    prior = output / FAILED_RUN
    journal_path, preflight_path = prior / "journal.jsonl", prior / "preflight.json"
    export_dir = output / EXPORT_RUN
    export_journal = export_dir / "journal.jsonl"
    preset_dir = export_dir / f"{PRESET_NAME}.drp"
    xml_path = preset_dir / f"{PRESET_NAME}.xml"
    result_path = PLUGIN_ROOT / RESULT_NAME
    refusal_dir = output / REFUSAL_RUN
    refusal_journal = refusal_dir / "journal.jsonl"
    refusal_result_path = PLUGIN_ROOT / REFUSAL_RESULT_NAME
    diagnostic_path = output / DIAGNOSTIC_NAME
    if (
        prior.is_symlink()
        or not prior.is_dir()
        or journal_path.is_symlink()
        or not journal_path.is_file()
        or preflight_path.is_symlink()
        or not preflight_path.is_file()
        or export_dir.is_symlink()
        or not export_dir.is_dir()
        or export_journal.is_symlink()
        or not export_journal.is_file()
        or _sha256(export_journal) != EXPORT_JOURNAL_SHA
        or preset_dir.is_symlink()
        or not preset_dir.is_dir()
        or xml_path.is_symlink()
        or not xml_path.is_file()
        or {p.name for p in preset_dir.iterdir()} != {xml_path.name}
        or result_path.is_symlink()
        or not result_path.is_file()
        or refusal_dir.is_symlink()
        or not refusal_dir.is_dir()
        or refusal_journal.is_symlink()
        or not refusal_journal.is_file()
        or refusal_result_path.is_symlink()
        or not refusal_result_path.is_file()
        or diagnostic_path.is_symlink()
        or not diagnostic_path.is_file()
        or _sha256(journal_path) != JOURNAL_SHA
        or _sha256(preflight_path) != PREFLIGHT_SHA
        or _sha256(xml_path) != XML_SHA
        or _sha256(result_path) != RESULT_SHA
        or _sha256(refusal_journal) != REFUSAL_JOURNAL_SHA
        or _sha256(refusal_result_path) != REFUSAL_RESULT_SHA
        or _sha256(diagnostic_path) != DIAGNOSTIC_SHA
    ):
        raise RuntimeError("Pinned failed-run recovery inputs changed")
    journal_rows = [json.loads(line) for line in journal_path.read_text().splitlines()]
    expected_head = [
        ("SyntheticManifest", "verified"),
        ("AudioOutput", "start"),
        ("Capture", "preflight"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("PresetRecovery", "verified-existing"),
        ("RenderPresetRecovery", "verified"),
    ]
    expected_tail = [
        ("SetRenderSettings", "request"),
        ("SetRenderSettings", "return"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("LoadRenderPreset", "request"),
        ("LoadRenderPreset", "return"),
        ("GetCurrentRenderFormatAndCodec", "request"),
        ("GetCurrentRenderFormatAndCodec", "return"),
        ("GetCurrentRenderMode", "request"),
        ("GetCurrentRenderMode", "return"),
        ("GetRenderJobList", "request"),
        ("GetRenderJobList", "return"),
        ("IsRenderingInProgress", "request"),
        ("IsRenderingInProgress", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("AudioOutput", "prequeue-restoration-failure"),
        ("AudioOutput", "restoration-failure"),
    ]
    if [
        (r.get("method"), r.get("phase")) for r in journal_rows
    ] != expected_head + expected_tail:
        raise RuntimeError(
            "Failed-run journal does not show the pinned one-shot refusal"
        )
    failed_preset_rows = [
        r["value"]
        for r in journal_rows
        if r.get("method") == "GetRenderPresetList" and r.get("phase") == "return"
    ]
    if (
        len(failed_preset_rows) != 3
        or failed_preset_rows[0] != failed_preset_rows[1]
        or failed_preset_rows[1] != failed_preset_rows[2]
    ):
        raise RuntimeError("Pinned preset list evidence is incomplete")
    export_events = list(map(json.loads, export_journal.read_text().splitlines()))
    export_transition = [
        r
        for r in export_events
        if r.get("method")
        in {"GetRenderPresetList", "SaveAsNewRenderPreset", "ExportRenderPreset"}
    ]
    if [(r.get("method"), r.get("phase")) for r in export_transition] != [
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("SaveAsNewRenderPreset", "request"),
        ("SaveAsNewRenderPreset", "return"),
        ("GetRenderPresetList", "request"),
        ("GetRenderPresetList", "return"),
        ("ExportRenderPreset", "request"),
        ("ExportRenderPreset", "return"),
    ]:
        raise RuntimeError("Pinned original preset export transition differs")
    export_rows = [
        r
        for r in export_transition
        if r.get("method") == "GetRenderPresetList" and r.get("phase") == "return"
    ]
    if (
        len(export_rows) != 2
        or export_rows[1].get("value")
        != [*export_rows[0].get("value", []), PRESET_NAME]
        or failed_preset_rows[0] != export_rows[1].get("value")
        or export_transition[2].get("value") != [PRESET_NAME]
        or export_transition[3].get("value") is not True
        or export_transition[6].get("value", [None])[0] != PRESET_NAME
        or Path(export_transition[6].get("value", ["", ""])[1]) != preset_dir
        or export_transition[7].get("value") is not True
    ):
        raise RuntimeError("Pinned original preset-list transition differs")
    original_presets = export_rows[0]["value"]
    if (
        original_presets.count(PRESET_NAME)
        or failed_preset_rows[0].count(PRESET_NAME) != 1
    ):
        raise RuntimeError("Retained preset identity is absent or duplicated")
    failed = json.loads(result_path.read_text(encoding="utf-8"))
    if failed.get(
        "status"
    ) != "launcher-failed" or "Post-settings refusal" not in failed.get("detail", ""):
        raise RuntimeError("Pinned failure result does not authorize this recovery")
    old_preflight = json.loads(preflight_path.read_text(encoding="utf-8"))
    if old_preflight.get("passes") != [pinned_timeline, pinned_timeline]:
        raise RuntimeError("Prior complete selected-Matrix preflight changed")
    refusal_rows = [
        json.loads(line) for line in refusal_journal.read_text().splitlines()
    ]
    if [(r.get("method"), r.get("phase")) for r in refusal_rows] != [
        ("Capture", "preflight"),
        ("Recovery", "refusal"),
        ("Recovery", "complete"),
    ]:
        raise RuntimeError("Pinned no-import refusal journal sequence differs")
    refusal = json.loads(refusal_result_path.read_text(encoding="utf-8"))
    refusal_reason = "RuntimeError: Exact selected Matrix/Edit context required"
    if (
        refusal_rows[0].get("value", {}).get("timelinePasses")
        != [{"error": refusal_reason}]
        or refusal_rows[0].get("value", {}).get("poolPasses")
        != [{"error": refusal_reason}]
        or refusal_rows[1].get("value") != refusal_reason
        or refusal_rows[2].get("value")
        != {"status": "preflight-refused-no-import", "importCalled": False}
        or refusal.get("status") != "preflight-refused-no-import"
        or refusal.get("importCalled") is not False
        or refusal.get("failure") != refusal_reason
    ):
        raise RuntimeError("Pinned no-import refusal does not match page guard")
    diagnostic = json.loads(diagnostic_path.read_text(encoding="utf-8"))
    diagnostic_context = diagnostic.get("environment", {}).get("context", {})
    diagnostic_render = diagnostic_context.get("renderState", {})
    if (
        diagnostic.get("stage") != "after-audio-recovery-context-refusal"
        or diagnostic.get("consistency") != "equal-adjacent-reads"
        or diagnostic.get("captureFailure") is not None
        or diagnostic.get("getterFailures") != []
        or diagnostic.get("passes") != [pinned_timeline, pinned_timeline]
        or diagnostic_context.get("currentPage") != {"value": "deliver"}
        or diagnostic_context.get("selectedTimelineUid") != {"value": MATRIX_ID}
        or diagnostic_render.get("GetCurrentRenderFormatAndCodec")
        != {"value": {"format": "unknown", "codec": ""}}
        or diagnostic_render.get("GetCurrentRenderMode") != {"value": 1}
        or diagnostic_render.get("GetRenderJobList") != {"value": []}
        or diagnostic_render.get("IsRenderingInProgress") != {"value": False}
        or diagnostic_render.get("GetRenderPresetList")
        != {"value": failed_preset_rows[0]}
    ):
        raise RuntimeError("Pinned Deliver-page diagnostic differs from Matrix state")

    if toggle:
        import_dir = output / IMPORT_RUN
        import_result_path = PLUGIN_ROOT / IMPORT_RESULT_NAME
        for path, digest in (
            (import_result_path, IMPORT_RESULT_SHA),
            (import_dir / "journal.jsonl", IMPORT_JOURNAL_SHA),
            (import_dir / "postflight.json", IMPORT_POSTFLIGHT_SHA),
        ):
            if (
                import_dir.is_symlink()
                or path.is_symlink()
                or not path.is_file()
                or _sha256(path) != digest
            ):
                raise RuntimeError("Pinned refused import evidence changed")
        import_result = json.loads(import_result_path.read_text())
        import_postflight = json.loads((import_dir / "postflight.json").read_text())
        if (
            import_result.get("status") != "import-unresolved-or-refused"
            or import_result.get("importCalled") is not True
            or import_result.get("importReturn") is not False
            or import_result.get("importError") is not None
            or import_result.get("timelineAndPoolUnchanged") is not True
            or import_result.get("xmlSha256After") != XML_SHA
            or import_postflight.get("timelinePasses")
            != [pinned_timeline, pinned_timeline]
            or import_postflight.get("poolPasses") != [pinned_pool, pinned_pool]
        ):
            raise RuntimeError(
                "Refused import did not retain the exact content checkpoint"
            )

    if select_format:
        for path, digest in (
            (PLUGIN_ROOT / TOGGLE_RESULT_NAME, TOGGLE_RESULT_SHA),
            (output / TOGGLE_RUN / "journal.jsonl", TOGGLE_JOURNAL_SHA),
            (output / TOGGLE_RUN / "postflight.json", IMPORT_POSTFLIGHT_SHA),
        ):
            if path.is_symlink() or not path.is_file() or _sha256(path) != digest:
                raise RuntimeError("Pinned video-toggle outcome changed")
        prior_toggle = json.loads((PLUGIN_ROOT / TOGGLE_RESULT_NAME).read_text())
        if (
            prior_toggle.get("status") != "video-toggle-unresolved-or-refused"
            or prior_toggle.get("setterCalled") is not True
            or prior_toggle.get("setterReturn") is not True
            or prior_toggle.get("setterError") is not None
            or prior_toggle.get("importCalled") is not False
            or prior_toggle.get("timelineAndPoolUnchanged") is not True
        ):
            raise RuntimeError("Video-toggle outcome does not support format selection")

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"audio-render-recovery-{stamp}"
    evidence.mkdir()
    journal = evidence / "journal.jsonl"
    journal.open("x").close()

    def record(method, phase, value):
        _append(journal, method, phase, value)

    identity = {"projectId": PROJECT_ID, "projectName": config["projectName"]}

    def context():
        if (
            resolve.GetProductName() != "DaVinci Resolve Studio"
            or resolve.GetVersion() != BUILD
        ):
            raise RuntimeError("Exact Resolve Studio 21.1.0 build 14 required")
        project = probe.require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if (
            timeline is None
            or timeline.GetUniqueId() != MATRIX_ID
            or resolve.GetCurrentPage() != "deliver"
        ):
            raise RuntimeError("Exact selected Matrix/Deliver context required")
        return project

    def capture(label):
        timeline_passes, pool_passes = [], []
        for _ in range(2):
            try:
                project = context()
                timeline_passes.append(
                    _canonical(probe.observe(resolve, config, identity, expected))
                )
                project = context()
                pool_passes.append(
                    _canonical(probe._r4_pool_inventory(project, expected))
                )
                context()
            except Exception as error:
                failure = {"error": f"{type(error).__name__}: {error}"}
                timeline_passes.append(failure)
                pool_passes.append(failure)
                break
        result = {
            "label": label,
            "timelinePasses": timeline_passes,
            "poolPasses": pool_passes,
        }
        _write(evidence / f"{label}.json", result)
        record("Capture", label, result)
        valid = (
            timeline_passes == [pinned_timeline, pinned_timeline]
            and pool_passes == [pinned_pool, pinned_pool]
            and not probe.errors(result)
        )
        return valid, result

    def render_state(project):
        state = {}
        for method, key in (
            ("GetCurrentRenderFormatAndCodec", "formatCodec"),
            ("GetCurrentRenderMode", "mode"),
            ("GetRenderJobList", "jobs"),
            ("IsRenderingInProgress", "rendering"),
            ("GetRenderPresetList", "presets"),
        ):
            record(method, "request", [])
            try:
                state[key] = getattr(project, method)()
                record(method, "return", state[key])
            except Exception as error:
                record(method, "failure", f"{type(error).__name__}: {error}")
                state[key] = {"error": f"{type(error).__name__}: {error}"}
        return state

    result = {
        "status": "recovery-unresolved",
        "importReturn": None,
        "importError": None,
        "importCalled": False,
        "setterCalled": False,
        "setterReturn": None,
        "setterError": None,
    }
    try:
        before_ok, _ = capture("preflight")
        project = context()
        before_render = render_state(project)
        expected_presets = failed_preset_rows[0]
        if not before_ok:
            raise RuntimeError("Fresh complete timeline/pool/source preflight differs")
        if (
            before_render.get("formatCodec") != {"format": "unknown", "codec": ""}
            or before_render.get("mode") != 1
            or before_render.get("jobs") != []
            or before_render.get("rendering") is not False
            or before_render.get("presets") != expected_presets
            or expected_presets.count(PRESET_NAME) != 1
        ):
            raise RuntimeError(
                "Exact unknown-format, idle, preset-list precondition differs"
            )
        context()
        before_xml = _sha256(xml_path)
        if before_xml != XML_SHA:
            raise RuntimeError("Owned render-preset XML changed before import")
        if toggle:
            method = (
                "SetCurrentRenderFormatAndCodec"
                if select_format
                else "SetRenderSettings"
            )
            args = ("mov", "H264") if select_format else ({"ExportVideo": True},)
            record(method, "request", list(args))
            result["setterCalled"] = True
            try:
                result["setterReturn"] = getattr(project, method)(*args)
                record(method, "return", result["setterReturn"])
            except Exception as error:
                result["setterError"] = f"{type(error).__name__}: {error}"
                record(method, "failure", result["setterError"])
        else:
            record("ImportRenderPreset", "request", [str(xml_path)])
            result["importCalled"] = True
            try:
                import_return = resolve.ImportRenderPreset(str(xml_path))
                result["importReturn"] = import_return
                record("ImportRenderPreset", "return", import_return)
            except Exception as error:
                result["importError"] = f"{type(error).__name__}: {error}"
                record("ImportRenderPreset", "failure", result["importError"])
        result["xmlSha256Before"] = before_xml
        try:
            project = probe.require_current(resolve, config, identity)
            after_render = render_state(project)
        except Exception as error:
            after_render = {"error": f"{type(error).__name__}: {error}"}
        try:
            after_ok, _ = capture("postflight")
        except Exception as error:
            after_ok = False
            result["postflightError"] = f"{type(error).__name__}: {error}"
        after_xml = (
            _sha256(xml_path)
            if xml_path.is_file() and not xml_path.is_symlink()
            else None
        )
        result["xmlSha256After"] = after_xml
        result["renderStateAfter"] = after_render
        result["timelineAndPoolUnchanged"] = after_ok
        restored = (
            (
                result["setterReturn"] is True
                if toggle
                else result["importReturn"] is True
            )
            and (
                result["setterError"] is None
                if toggle
                else result["importError"] is None
            )
            and after_ok
            and after_xml == XML_SHA
            and after_render.get("formatCodec") == {"format": "mov", "codec": "H264"}
            and after_render.get("mode") == 1
            and after_render.get("jobs") == []
            and after_render.get("rendering") is False
            and after_render.get("presets") == expected_presets
        )
        if select_format:
            result["status"] = (
                "format-selected-content-unchanged"
                if restored
                else "format-selection-unresolved-or-refused"
            )
        elif toggle:
            result["status"] = (
                "video-enabled-known-format-content-unchanged"
                if restored
                else "video-toggle-unresolved-or-refused"
            )
        else:
            result["status"] = (
                "import-restored-known-format-content-unchanged"
                if restored
                else "import-unresolved-or-refused"
            )
        result["limits"] = [
            "No public getter proves equality of every hidden render setting."
            " The original ExportVideo boolean was not separately observed."
        ]
    except Exception as error:
        result["status"] = "preflight-refused-no-import"
        result["failure"] = f"{type(error).__name__}: {error}"
        record("Recovery", "refusal", result["failure"])
        before_ok = False
        after_xml = (
            _sha256(xml_path)
            if xml_path.is_file() and not xml_path.is_symlink()
            else None
        )
        result["xmlSha256After"] = after_xml
        result["timelineAndPoolUnchanged"] = False
    result["journal"] = str(journal)
    record(
        "Recovery",
        "complete",
        {"status": result["status"], "importCalled": result["importCalled"]},
    )
    _write(evidence / "result.json", result)
    return result
