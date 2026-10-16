"""Issue-owned injected probe. No external bridge or production reconciler."""

import hashlib
import importlib.util
import json
import platform
import sys
from copy import deepcopy
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

PREFIX = "VERA Issue 141 Synthetic Probe "
TIMELINE = "VERA 141 Baseline"
BASELINE_ID = "88f7923d-55a7-471f-b09b-cf10f9fae8ad"
R1_ID = "aa2b8e36-83bd-4292-9e33-217c00ca192f"
CONTEXT_CAPTURE = "capture-20260930T204438.948629Z-current-duplicate-saved.json"
CONTEXT_CAPTURE_SHA256 = (
    "fab588ea4f4e10394b0ca878358cb55743cb8c1dbaa72cd4822320e7e9cae85f"
)
CONTEXT_BASELINE_CAPTURE = "capture-20260930T173943.043191Z.json"
CONTEXT_BASELINE_SHA256 = (
    "92c04d10bafe86499b7d11a27d457e655893ee6340d73a290a80e29e35887161"
)
MATRIX_NAME = "VERA 141 Batched Matrix"
MATRIX_PARTIAL_ID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_FIRST_ITEM_ID = "3f2de461-d510-46f8-939f-0c794d48e38b"
MATRIX_PARTIAL_CAPTURE = "capture-20260930T215628.608006Z-failure-postflight.json"
MATRIX_EMPTY_CAPTURE = "capture-20260930T215628.608006Z-empty-selected-matrix.json"
MATRIX_COMPLETE_CAPTURE = "capture-20260930T221137.773286Z-failure-postflight.json"
MATRIX_FINALIZE_HASHES = {
    MATRIX_COMPLETE_CAPTURE: (
        "e68f682b2f0b73bbf8ee883fd375ecd5325061c50c1cd2615fb9ee72e386e0d9"
    ),
    MATRIX_EMPTY_CAPTURE: (
        "cc834e8fd34b1bd84348d3dfde00648a2fff5d0fcb17eb6398137a615a4d0445"
    ),
    "native-matrix-20260930T221137.773286Z.jsonl": (
        "a67bbafcadc5cac195fc6b93e95abb6382f1a2adb5bdf6a2186ec25d8330a20b"
    ),
    CONTEXT_BASELINE_CAPTURE: CONTEXT_BASELINE_SHA256,
}
PICTURE_CAPTURE = "capture-20260930T223313.312609Z-saved.json"
PICTURE_CAPTURE_SHA256 = (
    "a29402d405ab8cf1bc1abedd4c1ed0c479e983e2ef3ba6fc41d1c2389d6d36d2"
)
R4_NAME = "VERA 141 R4 availability"
R4_IMPORT_SHA256 = "c54ed675ded4e6e7665965680c4991e274058862f7ad8a2d95831c9ec07b7942"
PICTURE_FRAMES = (0, 198, 199, 200)
PICTURE_CASES = {
    "opaque": {
        "uid": "861df236-2ca9-4bfc-b925-9499926a44fb",
        "mediaUid": "8366bbfd-ad50-4a17-9b8d-d05224943f0b",
        "filename": "cutaway.mov",
        "sha256": "771b4bbbe771b980831e0a7b6d93ef11e1315cd995df22c5c7fbf7c2bf62c88b",
        "track": 2,
        "start": 6050,
        "end": 6099,
        "duration": 49,
        "sourceEnd": 49,
        "marker": {
            "0": {
                "color": "Blue",
                "customData": '{"issue": 141, "occurrence": 4, "section": "R3-opaque"}',
                "duration": 1,
                "name": "141 R3-opaque item 4",
                "note": "Synthetic matrix occurrence",
            }
        },
        "frames": (49, 50, 98, 99, 100),
        "disableFrame": 50,
        "sectionStart": 6000,
    },
    "transparent": {
        "uid": "dcc94b55-ec47-4aff-bdda-8eb403ae4ba8",
        "mediaUid": "ce49c87d-edf6-4860-981c-891cc329c447",
        "filename": "overlay.png",
        "sha256": "071eb12b64238770244dead14fda01a0aeca3623f7962aab9edefa93b68d3140",
        "track": 3,
        "start": 6575,
        "end": 6700,
        "duration": 125,
        "sourceEnd": 0,
        "marker": {
            "0": {
                "color": "Blue",
                "customData": (
                    '{"issue": 141, "occurrence": 5, "section": "R3-transparent"}'
                ),
                "duration": 1,
                "name": "141 R3-transparent item 5",
                "note": "Synthetic matrix occurrence",
            }
        },
        "frames": (74, 75, 198, 199, 200),
        "disableFrame": 75,
        "sectionStart": 6500,
    },
    "effect": {
        "uid": "cbde93e8-d9e9-4ed8-aaa0-315c37dc9e34",
        "mediaUid": "ce49c87d-edf6-4860-981c-891cc329c447",
        "filename": "overlay.png",
        "sha256": "071eb12b64238770244dead14fda01a0aeca3623f7962aab9edefa93b68d3140",
        "track": 3,
        "start": 7075,
        "end": 7200,
        "duration": 125,
        "sourceEnd": 0,
        "marker": {
            "0": {
                "color": "Blue",
                "customData": '{"issue": 141, "occurrence": 5, "section": "R3-effect"}',
                "duration": 1,
                "name": "141 R3-effect item 5",
                "note": "Synthetic matrix occurrence",
            }
        },
        "sectionStart": 7000,
    },
}
MATRIX_CONTINUATION_HASHES = {
    MATRIX_PARTIAL_CAPTURE: (
        "3d32b4abab487b31abd581d439a5006923edfa6c3d355bb15bd6839bdb405638"
    ),
    MATRIX_EMPTY_CAPTURE: (
        "cc834e8fd34b1bd84348d3dfde00648a2fff5d0fcb17eb6398137a615a4d0445"
    ),
    "native-matrix-20260930T215628.608006Z.jsonl": (
        "1e456123a3e516a1d1e731fd53aaebd9d6ab9c9cc0cd36f289cd994c5f30931b"
    ),
}
MATRIX_SECTIONS = (
    "calibration",
    "R1-trim",
    "R1-move",
    "R1-razor",
    "R1-copy",
    "R2-linked",
    "R2-unlinked",
    "R2-picture-only",
    "R2-partial",
    "R2-residual",
    "R2-offset",
    "R2-retime",
    "R3-opaque",
    "R3-transparent",
    "R3-effect",
    "R3-disabled-cutaway",
    "R3-disabled-overlay",
    "R3-Graphic",
    "R3-boundary",
)
MATRIX_RECIPE = (
    ("base.mov", "video", 1, 0, 200, 0, True),
    ("repeated.wav", "audio", 1, 0, 200, 0, True),
    ("repeated.wav", "audio", 2, 0, 200, 0, False),
    ("bed.wav", "audio", 3, 0, 200, 0, True),
    ("cutaway.mov", "video", 2, 0, 50, 50, False),
    ("overlay.png", "video", 3, 0, 50, 75, False),
)
CONTEXT_ENVIRONMENT = [21, 1, 0, 14, ""]
ROOT = Path(__file__).resolve().parents[3]
SETTINGS = {
    "timelineFrameRate": "25",
    "timelineResolutionWidth": "1920",
    "timelineResolutionHeight": "1080",
    "timelineSampleRate": "48000",
}


def sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")


def validate_config(config):
    if config.get("externalScriptingSetting") != "None":
        raise ValueError("Operator must attest External Scripting None; no fallback")
    name = config.get("projectName", "")
    if (
        not name.startswith(PREFIX)
        or not name[len(PREFIX) :].strip()
        or name != name.strip()
        or any(value in name for value in "\r\n")
    ):
        raise ValueError("A uniquely named issue-141 synthetic project is required")
    if config.get("action") not in {
        "prepare",
        "resume-preparation",
        "observe",
        "native-repeat",
        "native-duplicate",
        "native-context",
        "native-matrix",
        "matrix-finalize",
        "picture-calibration",
        "picture-cases",
        "audio-cases",
        "output-discovery",
        "restore-pinned-cache",
        "matrix-reopen",
        "r4-availability",
        "r4-pool-read-only",
        "r4-finalize",
        "r4-transitions",
        "r4-recovery",
        "r4-range-repair",
        "r4-occurrence-remove",
        "r4-reprepare",
        "r4-wrong-bytes",
        "r5-freshness",
        "r5-capture-freshness",
        "r1-razor-prepare",
        "editorial-readback",
        "editorial-restore",
        "editorial-case-prepare",
        "editorial-case-restore",
        "editorial-copy-paste-position",
        "offline-cycle",
        "offline-picture-continuation",
        "matrix-checkpoint",
        "audio-output",
        "audio-output-continue",
        "av-output",
        "av-output-continue",
        "av-output-queue-from-settings",
        "audio-render-recovery",
        "audio-video-toggle-recovery",
        "audio-format-selection-recovery",
        "offline-picture",
    }:
        raise ValueError("Unknown bounded probe action")
    for key in ("mediaDir", "outputDir"):
        if not isinstance(config.get(key), str) or not Path(config[key]).is_absolute():
            raise ValueError(f"{key} must be absolute")


def settings_match(observed, requested):
    if not isinstance(observed, dict):
        return False
    for key, expected in requested.items():
        actual = observed.get(key)
        if key in SETTINGS or key == "timelinePlaybackFrameRate":
            if isinstance(actual, bool) or not isinstance(actual, (str, int, float)):
                return False
            try:
                if Decimal(str(actual)) != Decimal(expected):
                    return False
            except InvalidOperation:
                return False
        elif actual != expected:
            return False
    return True


def resume_project(resolve, config, output):
    # Bounded recovery of the recorded pre-import setter refusal, never generic retry.
    retained = {}
    for key, prefix in (
        ("resumeFailure", "preparation-failure-"),
        ("resumeJournal", "preparation-"),
    ):
        name = config.get(key, "")
        if Path(name).name != name or not name.startswith(prefix):
            raise ValueError("Unknown preparation evidence; refusing recovery")
        path = output / name
        if sha256(path) != config.get(key + "Sha256"):
            raise ValueError("Preparation evidence changed; refusing recovery")
        retained[key] = path.read_text(encoding="utf-8")
    failure = json.loads(retained["resumeFailure"])
    if failure.get("error") != "RuntimeError: SetSettings refused operation":
        raise ValueError("Only the recorded settings-setter refusal may continue")
    records = [json.loads(line) for line in retained["resumeJournal"].splitlines()]
    if [(row["method"], row["phase"]) for row in records] != [
        ("SetSettings", "request"),
        ("SetSettings", "failure"),
    ]:
        raise ValueError(
            "Prior preparation reached other operations; refusing recovery"
        )
    identity = json.loads((output / "identity.json").read_text(encoding="utf-8"))
    if identity != failure.get("identity") or (output / "prepared.json").exists():
        raise ValueError("Recovery identity/state differs from the recorded failure")
    project = require_current(resolve, config, identity)
    if project.GetTimelineCount() != 0:
        raise RuntimeError("Recovery project is not empty; stop without mutation")
    folder = project.GetMediaPool().GetRootFolder()
    if folder.GetClipList() != [] or folder.GetSubFolderList() != []:
        raise RuntimeError("Recovery media pool is not empty; stop without mutation")
    return project, identity


def read(obj, method, *args):
    try:
        value = getattr(obj, method)(*args)
        # Refuse opaque handles instead of converting them to invented identities.
        json.dumps(value, allow_nan=False)
        return {"value": value}
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


def source_evidence(locator, expected, *, offline=False):
    if (
        offline is True
        and isinstance(locator, str)
        and locator.startswith("OFFLINE - ")
    ):
        approved = locator.removeprefix("OFFLINE - ")
        if approved in expected:
            return {
                "status": "offline-locator-not-accessed",
                "approvedLocator": approved,
                "expectedSha256": expected[approved],
            }
    if locator not in expected:
        return {"status": "unapproved-locator-not-accessed"}
    path = Path(locator)
    if path.is_symlink():
        return {"status": "symlink-not-accessed"}
    try:
        digest = sha256(path)
        return {
            "status": "reachable",
            "sha256": digest,
            "hashMatches": digest == expected[locator],
        }
    except OSError as error:
        return {"status": "unavailable", "error": type(error).__name__}


def item_evidence(item, expected):
    calls = (
        "GetUniqueId",
        "GetName",
        "GetType",
        "GetTrackTypeAndIndex",
        "GetMarkers",
        "GetProperties",
        "GetSpeed",
        "GetClipEnabled",
        "GetSourceStartFrame",
        "GetSourceEndFrame",
        "GetSourceStartTime",
        "GetSourceEndTime",
        "GetFusionCompCount",
        "GetFusionCompNameList",
        "GetSourceAudioChannelMapping",
        "GetVoiceIsolationState",
    )
    result = {method: read(item, method) for method in calls}
    for method in (
        "GetStart",
        "GetEnd",
        "GetDuration",
        "GetLeftOffset",
        "GetRightOffset",
    ):
        result[method] = read(item, method)
        result[method + "(True)"] = read(item, method, True)
    try:
        linked = item.GetLinkedItems()
        if not isinstance(linked, (list, tuple)):
            raise ValueError("GetLinkedItems did not return a list")
        result["GetLinkedItems"] = [read(other, "GetUniqueId") for other in linked]
    except Exception as error:
        result["GetLinkedItems"] = {"error": f"{type(error).__name__}: {error}"}
    try:
        media = item.GetMediaPoolItem()
        if media is None:
            result["GetMediaPoolItem"] = {"value": None}
        else:
            result["GetMediaPoolItem"] = media_evidence(media, expected)
    except Exception as error:
        result["GetMediaPoolItem"] = {"error": f"{type(error).__name__}: {error}"}
    return result


def media_evidence(media, expected):
    result = {
        method: read(media, method)
        for method in (
            "GetUniqueId",
            "GetClipProperty",
            "GetMarkers",
            "GetAudioMapping",
        )
    }
    properties = result["GetClipProperty"].get("value")
    locator = properties.get("File Path") if isinstance(properties, dict) else None
    result["sourceBytes"] = source_evidence(
        locator,
        expected,
        offline=isinstance(properties, dict)
        and properties.get("Online Status") == "Offline",
    )
    return result


def require_current(resolve, config, identity):
    if not isinstance(identity.get("projectId"), str) or not identity["projectId"]:
        raise RuntimeError("Unknown project ID; refusing")
    project = resolve.GetProjectManager().GetCurrentProject()
    if project is None or project.GetName() != config["projectName"]:
        raise RuntimeError(
            "Select only the named issue-141 project; no automatic switch"
        )
    if project.GetUniqueId() != identity["projectId"]:
        raise RuntimeError("Same project name has a different ID; refusing")
    return project


def observe(resolve, config, identity, expected):
    project = require_current(resolve, config, identity)
    timelines = []
    count = project.GetTimelineCount()
    if not isinstance(count, int) or count < 1:
        raise RuntimeError("No readable probe timeline")
    for index in range(1, count + 1):
        timeline = project.GetTimelineByIndex(index)
        if timeline is None or not timeline.GetName().startswith("VERA 141 "):
            raise RuntimeError(
                "Unexpected timeline; refuse capture outside named probes"
            )
        raw = {
            method: read(timeline, method)
            for method in (
                "GetName",
                "GetUniqueId",
                "GetStartFrame",
                "GetEndFrame",
                "GetStartTimecode",
                "GetSettings",
                "GetMarkers",
            )
        }
        raw["tracks"] = []
        for kind in ("video", "audio", "subtitle"):
            track_count = timeline.GetTrackCount(kind)
            if not isinstance(track_count, int) or track_count < 0:
                raise RuntimeError(f"Unreadable {kind} track count")
            for track_index in range(1, track_count + 1):
                track = {"type": kind, "index": track_index}
                for method in ("GetTrackName", "GetIsTrackEnabled", "GetIsTrackLocked"):
                    track[method] = read(timeline, method, kind, track_index)
                if kind == "audio":
                    track["GetTrackSubType"] = read(
                        timeline, "GetTrackSubType", kind, track_index
                    )
                items = timeline.GetItemListInTrack(kind, track_index)
                if not isinstance(items, (list, tuple)):
                    raise RuntimeError(
                        "Unreadable track items; null is not an empty track"
                    )
                track["items"] = sorted(
                    (item_evidence(item, expected) for item in items),
                    key=lambda item: json.dumps(item["GetUniqueId"], sort_keys=True),
                )
                raw["tracks"].append(track)
        timelines.append(raw)
    require_current(resolve, config, identity)
    return {
        "projectId": project.GetUniqueId(),
        "projectName": project.GetName(),
        "GetSettings": read(project, "GetSettings"),
        "timelines": sorted(
            timelines, key=lambda value: json.dumps(value["GetUniqueId"])
        ),
    }


def errors(value):
    found = []
    if isinstance(value, dict):
        if "error" in value:
            found.append(value["error"])
        if value.get("value", False) is None:
            found.append("null-getter-result-not-established")
        if value.get("status") in {
            "unapproved-locator-not-accessed",
            "symlink-not-accessed",
        }:
            found.append(value["status"])
        if value.get("hashMatches") is False:
            found.append("source-hash-mismatch")
        for child in value.values():
            found.extend(errors(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(errors(child))
    return found


def consistency(first, second, failures):
    if first != second:
        return "inconsistent-refused"
    if failures:
        return "incomplete-refused"
    return "equal-adjacent-reads"


def capture(resolve, config, identity, expected, output, stamp, environment):
    passes = []
    failure = None
    try:
        for _ in range(2):
            passes.append(observe(resolve, config, identity, expected))
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
    problems = errors(passes) + ([failure] if failure else [])
    status = (
        consistency(*passes, problems) if len(passes) == 2 else "incomplete-refused"
    )
    fingerprints = [
        hashlib.sha256(
            json.dumps(value, sort_keys=True, allow_nan=False).encode()
        ).hexdigest()
        for value in passes
    ]
    payload = {
        "kind": "real-injected-readback",
        "capturedAt": stamp,
        "stage": config.get("stage", "unlabelled"),
        "environment": environment,
        "passes": passes,
        "captureFailure": failure,
        "getterFailures": problems,
        "consistency": status,
        "contentFingerprints": fingerprints,
        "applicationRevisionToken": None,
        "limits": [
            "Equal adjacent reads do not prove atomicity or exclude ABA changes.",
            "No complete bus/mix/effect routing or rendered visibility proof.",
            "No deletion, speech removal or lineage is inferred.",
        ],
    }
    path = output / f"capture-{stamp}.json"
    write_json(path, payload)
    return {"status": status, "capturePath": str(path), "sha256": sha256(path)}


def native_repeat(resolve, config, identity, expected, output, stamp, environment):
    action = config["action"]
    if action not in {"native-repeat", "native-duplicate"}:
        raise ValueError("Unknown native probe action")
    prepared_path = output / "prepared.json"
    prepared = json.loads(prepared_path.read_text(encoding="utf-8"))
    prepared_identity = prepared.get("identity")
    if (
        not isinstance(prepared_identity, dict)
        or prepared_identity.get("projectId") != identity.get("projectId")
        or prepared_identity.get("projectName") != identity.get("projectName")
        or prepared.get("manifestSha256") != config.get("manifestSha256")
    ):
        raise RuntimeError("Prepared identity or manifest differs; refusing")
    identity = prepared_identity
    if environment.get("version") != [21, 1, 0, 14, ""]:
        raise RuntimeError("Expected installed Resolve 21.1.0 build 14; refusing")
    if identity.get("baselineTimelineId") != "88f7923d-55a7-471f-b09b-cf10f9fae8ad":
        raise RuntimeError("Unexpected prepared baseline timeline ID; refusing")

    baseline_path = output / "capture-20260930T173943.043191Z.json"
    if (
        sha256(baseline_path)
        != "92c04d10bafe86499b7d11a27d457e655893ee6340d73a290a80e29e35887161"
    ):
        raise RuntimeError("Private raw baseline changed or is missing; refusing")
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    if (
        baseline.get("consistency") != "equal-adjacent-reads"
        or len(baseline.get("passes", [])) != 2
    ):
        raise RuntimeError("Private raw baseline capture is incomplete; refusing")
    baseline_pass = baseline["passes"][0]
    if (
        baseline_pass.get("projectId") != identity["projectId"]
        or baseline_pass.get("projectName") != config["projectName"]
        or baseline_pass["timelines"][0].get("GetUniqueId", {}).get("value")
        != identity["baselineTimelineId"]
        or len(baseline_pass["timelines"]) != 1
    ):
        raise RuntimeError("Private raw baseline is not the expected single timeline")

    manager = resolve.GetProjectManager()
    project = require_current(resolve, config, identity)
    before_stage = (
        "reopened-before-duplicate" if action == "native-duplicate" else "before"
    )
    before_result = capture(
        resolve,
        config,
        identity,
        expected,
        output,
        stamp + "-" + before_stage,
        environment,
    )
    if before_result["status"] != "equal-adjacent-reads":
        raise RuntimeError("Initial native capture is incomplete; refusing")
    before_capture = json.loads(
        Path(before_result["capturePath"]).read_text(encoding="utf-8")
    )
    before_passes = before_capture.get("passes", [])
    if len(before_passes) != 2 or any(errors(value) for value in before_passes):
        raise RuntimeError("Initial native capture is incomplete; refusing")
    before_pass = before_passes[0]
    restore_cache = False
    pinned_cache_path = None
    cache_paths = (
        ("GetSettings", "value", "perfCacheClipsLocation"),
        ("timelines", 0, "GetSettings", "value", "perfCacheClipsLocation"),
    )
    if before_pass != baseline_pass:
        if action != "native-duplicate":
            raise RuntimeError(
                "Current project is not the prepared baseline-only state"
            )

        def setting_at(value, path):
            for part in path:
                value = value[part]
            return value

        try:
            current_cache = [setting_at(before_pass, path) for path in cache_paths]
            baseline_cache = [setting_at(baseline_pass, path) for path in cache_paths]
        except (IndexError, KeyError, TypeError):
            raise RuntimeError(
                "Cache location readback is incomplete; refusing"
            ) from None
        if (
            current_cache != ["CacheClip", "CacheClip"]
            or not all(isinstance(value, str) for value in baseline_cache)
            or baseline_cache[0] != baseline_cache[1]
        ):
            raise RuntimeError("Cache location change is outside the bounded case")
        try:
            cache_path = Path(baseline_cache[0])
            output_root = output.resolve(strict=True)
            if not cache_path.is_absolute():
                raise ValueError
            relative = cache_path.relative_to(output)
            if not relative.parts or ".." in relative.parts:
                raise ValueError
            cursor = output
            for part in relative.parts:
                cursor /= part
                if cursor.is_symlink():
                    raise ValueError
            resolved_cache_path = cache_path.resolve(strict=True)
            if (
                not resolved_cache_path.is_dir()
                or not resolved_cache_path.is_relative_to(output_root)
            ):
                raise ValueError
            pinned_cache_path = cache_path
        except (OSError, ValueError):
            raise RuntimeError(
                "Pinned cache directory is unsafe or outside the probe output"
            ) from None
        restored_pass = deepcopy(before_pass)
        for path in cache_paths:
            target = restored_pass
            for part in path[:-1]:
                target = target[part]
            target[path[-1]] = baseline_cache[0]
        if restored_pass != baseline_pass:
            raise RuntimeError("Project differs beyond the two cache locations")
        restore_cache = True

    journal = output / f"{action}-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    def mutate(obj, method, *args, audit_args=None):
        if method == "LoadProject":
            if manager.GetCurrentProject() is not None:
                raise RuntimeError("A project is loaded; refusing LoadProject")
        else:
            require_current(resolve, config, identity)
        retain(method, "request", args if audit_args is None else audit_args)
        try:
            result = getattr(obj, method)(*args)
            if result is None or result is False:
                raise RuntimeError(f"{method} refused operation")
            if method in {"DuplicateTimeline", "LoadProject"}:
                value = {
                    "GetName": read(result, "GetName"),
                    "GetUniqueId": read(result, "GetUniqueId"),
                }
            else:
                value = result
            retain(method, "return", value)
            return result
        except Exception as error:
            retain(method, "failure", f"{type(error).__name__}: {error}")
            raise

    reopened_capture = None
    cache_restoration_capture = None
    if action == "native-repeat":
        mutate(manager, "SaveProject")
        mutate(manager, "CloseProject", project, audit_args=[identity["projectId"]])
        current_after_close = manager.GetCurrentProject()
        retain(
            "GetCurrentProject(after CloseProject)",
            "readback",
            None
            if current_after_close is None
            else read(current_after_close, "GetUniqueId"),
        )
        if current_after_close is not None:
            raise RuntimeError("Resolve still has a project loaded after close; stop")
        reopened = mutate(manager, "LoadProject", config["projectName"])
        if (
            reopened.GetName() != config["projectName"]
            or reopened.GetUniqueId() != identity["projectId"]
            or manager.GetCurrentProject().GetUniqueId() != identity["projectId"]
        ):
            raise RuntimeError("Reopened project identity differs; stop")
        retain(
            "LoadProject(identity readback)",
            "readback",
            {
                "GetName": reopened.GetName(),
                "GetUniqueId": reopened.GetUniqueId(),
                "GetCurrentProject.UniqueId": manager.GetCurrentProject().GetUniqueId(),
            },
        )
        reopened_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-reopened",
            environment,
        )
        if reopened_capture["status"] != "equal-adjacent-reads":
            raise RuntimeError("Reopened capture is incomplete; stop")
    else:
        # The operator reopened the exact approved project. The guarded preflight
        # capture above is the retained comparison for this state.
        reopened = project

    if restore_cache:
        try:
            mutate(
                reopened,
                "SetSettings",
                {"perfCacheClipsLocation": str(pinned_cache_path)},
                audit_args=[{"perfCacheClipsLocation": str(pinned_cache_path)}],
            )
        except Exception:
            try:
                cache_restoration_capture = capture(
                    resolve,
                    config,
                    identity,
                    expected,
                    output,
                    stamp + "-cache-restoration",
                    environment,
                )
                retain(
                    "SetSettings(cache restoration capture)",
                    "readback",
                    cache_restoration_capture,
                )
            except Exception as capture_error:
                retain(
                    "SetSettings(cache restoration capture)",
                    "failure",
                    f"{type(capture_error).__name__}: {capture_error}",
                )
            raise
        cache_restoration_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-cache-restoration",
            environment,
        )
        retain(
            "SetSettings(cache restoration capture)",
            "readback",
            cache_restoration_capture,
        )
        restored = json.loads(
            Path(cache_restoration_capture["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if (
            cache_restoration_capture["status"] != "equal-adjacent-reads"
            or len(restored) != 2
            or any(errors(value) for value in restored)
            or restored != [baseline_pass, baseline_pass]
        ):
            raise RuntimeError("Cache setting restoration did not match baseline")

    original = None
    for index in range(1, reopened.GetTimelineCount() + 1):
        candidate = reopened.GetTimelineByIndex(index)
        if candidate.GetUniqueId() == identity["baselineTimelineId"]:
            original = candidate
    if original is None or reopened.GetTimelineCount() != 1:
        raise RuntimeError("Reopened project is not baseline-only; stop")
    duplicate_name = "VERA 141 R1 identity"
    if any(
        reopened.GetTimelineByIndex(index).GetName() == duplicate_name
        for index in range(1, reopened.GetTimelineCount() + 1)
    ):
        raise RuntimeError("R1 duplicate already exists; refusing")
    duplicate = mutate(original, "DuplicateTimeline", duplicate_name)
    duplicate_id = duplicate.GetUniqueId()
    if (
        duplicate.GetName() != duplicate_name
        or not isinstance(duplicate_id, str)
        or not duplicate_id
        or duplicate_id == identity["baselineTimelineId"]
    ):
        raise RuntimeError("Duplicate timeline identity differs; stop")
    duplicate_capture = capture(
        resolve,
        config,
        identity,
        expected,
        output,
        stamp + "-duplicated",
        environment,
    )
    if duplicate_capture["status"] != "equal-adjacent-reads":
        raise RuntimeError("Duplicate capture is incomplete; stop")
    duplicate_pass = json.loads(Path(duplicate_capture["capturePath"]).read_text())[
        "passes"
    ][0]
    timelines = duplicate_pass["timelines"]
    ids = {row.get("GetUniqueId", {}).get("value") for row in timelines}
    names = {row.get("GetName", {}).get("value") for row in timelines}
    if (
        len(timelines) != 2
        or ids != {identity["baselineTimelineId"], duplicate_id}
        or names != {TIMELINE, duplicate_name}
    ):
        raise RuntimeError("Duplicate readback does not bound both timelines; stop")

    mutate(reopened, "SetCurrentTimeline", duplicate, audit_args=[duplicate_id])
    current_timeline_id = reopened.GetCurrentTimeline().GetUniqueId()
    if current_timeline_id != duplicate_id:
        raise RuntimeError("Current timeline readback differs; stop")
    retain(
        "SetCurrentTimeline(readback)",
        "readback",
        {"GetCurrentTimeline.UniqueId": current_timeline_id},
    )
    mutate(manager, "SaveProject")
    final_capture = capture(
        resolve,
        config,
        identity,
        expected,
        output,
        stamp + "-current-duplicate-saved",
        environment,
    )
    return {
        "status": final_capture["status"],
        "action": action,
        "preflightStage": before_stage,
        "reopenEvidence": (
            "operator-managed; preflight state only, "
            "reopen sequence not independently verified"
            if action == "native-duplicate"
            else "native SaveProject/CloseProject/LoadProject sequence captured"
        ),
        "journal": str(journal),
        "captures": [
            before_result,
            *([] if reopened_capture is None else [reopened_capture]),
            *([] if cache_restoration_capture is None else [cache_restoration_capture]),
            duplicate_capture,
            final_capture,
        ],
        "duplicate": {"name": duplicate_name, "id": duplicate_id},
        "limits": [
            "Timeline duplication was exercised through the documented API.",
            "Equal adjacent reads do not prove atomicity or exclude ABA changes.",
            "Copied metadata and equal fingerprints do not prove source identity.",
        ],
    }


def _pass_timeline(value, timeline_id):
    matches = [
        timeline
        for timeline in value.get("timelines", [])
        if timeline.get("GetUniqueId", {}).get("value") == timeline_id
    ]
    if len(matches) != 1:
        raise RuntimeError("Pinned context does not contain the exact timeline")
    return matches[0]


def _usage_locations(value):
    """Return five source names and six captured Usage leaves."""
    locations = {}
    for track in value.get("tracks", []):
        for item in track.get("items", []):
            media = item.get("GetMediaPoolItem", {})
            properties = media.get("GetClipProperty", {}).get("value")
            if not isinstance(properties, dict):
                continue
            locator = properties.get("File Path")
            name = Path(locator).name if isinstance(locator, str) else None
            if name in {
                "base.mov",
                "cutaway.mov",
                "overlay.png",
                "bed.wav",
                "repeated.wav",
            }:
                locations.setdefault(name, []).append(properties.get("Usage"))
    return locations


def _baseline_usage_comparison(selected, pinned):
    """Verify and temporarily copy back only the recorded media Usage leaves."""
    selected_timeline = _pass_timeline(selected, BASELINE_ID)
    pinned_timeline = _pass_timeline(pinned, BASELINE_ID)
    expected = {
        "base.mov": (["2"], "1"),
        "cutaway.mov": (["2"], "1"),
        "overlay.png": (["2"], "1"),
        "bed.wav": (["2"], "1"),
        "repeated.wav": (["4", "4"], "2"),
    }
    selected_usage = _usage_locations(selected_timeline)
    pinned_usage = _usage_locations(pinned_timeline)
    if set(selected_usage) != set(expected) or set(pinned_usage) != set(expected):
        return False
    for name, (current, original) in expected.items():
        original_values = [original] * len(current)
        if selected_usage[name] != current or pinned_usage[name] != original_values:
            return False

    compared = deepcopy(selected)
    compared_timeline = _pass_timeline(compared, BASELINE_ID)
    for track in compared_timeline.get("tracks", []):
        for item in track.get("items", []):
            properties = (
                item.get("GetMediaPoolItem", {}).get("GetClipProperty", {}).get("value")
            )
            locator = (
                properties.get("File Path") if isinstance(properties, dict) else None
            )
            name = Path(locator).name if isinstance(locator, str) else None
            if name in expected:
                properties["Usage"] = expected[name][1]
    return compared_timeline == pinned_timeline


def native_context(resolve, config, identity, expected, output, stamp, environment):
    """Select baseline and R1 once each, capture both contexts, and compare."""
    if config["action"] != "native-context":
        raise ValueError("Unknown context calibration action")
    prepared = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
    prepared_identity = prepared.get("identity")
    if (
        not isinstance(prepared_identity, dict)
        or prepared_identity.get("projectId") != identity.get("projectId")
        or prepared_identity.get("projectName") != identity.get("projectName")
        or prepared.get("manifestSha256") != config.get("manifestSha256")
        or prepared.get("environment", {}).get("version") != CONTEXT_ENVIRONMENT
    ):
        raise RuntimeError("Prepared identity or Resolve build differs; refusing")
    identity = prepared_identity
    if environment.get("version") != CONTEXT_ENVIRONMENT:
        raise RuntimeError("Expected installed Resolve 21.1.0 build 14; refusing")
    if identity.get("baselineTimelineId") != BASELINE_ID:
        raise RuntimeError("Prepared baseline identity differs; refusing")

    pinned_path = output / CONTEXT_CAPTURE
    if sha256(pinned_path) != CONTEXT_CAPTURE_SHA256:
        raise RuntimeError("Pinned duplicate capture changed or is missing; refusing")
    pinned_capture = json.loads(pinned_path.read_text(encoding="utf-8"))
    pinned_passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(pinned_passes) != 2
        or pinned_passes[0] != pinned_passes[1]
        or any(errors(value) for value in pinned_passes)
        or len(pinned_passes[0].get("timelines", [])) != 2
        or pinned_passes[0].get("projectId") != identity.get("projectId")
        or _pass_timeline(pinned_passes[0], R1_ID) is None
    ):
        raise RuntimeError("Pinned duplicate capture is incomplete or unexpected")
    pinned = pinned_passes[0]

    baseline_path = output / CONTEXT_BASELINE_CAPTURE
    if sha256(baseline_path) != CONTEXT_BASELINE_SHA256:
        raise RuntimeError("Pinned original baseline changed or is missing; refusing")
    baseline_capture = json.loads(baseline_path.read_text(encoding="utf-8"))
    original_passes = baseline_capture.get("passes", [])
    if (
        baseline_capture.get("consistency") != "equal-adjacent-reads"
        or len(original_passes) != 2
        or original_passes[0] != original_passes[1]
        or any(errors(value) for value in original_passes)
        or len(original_passes[0].get("timelines", [])) != 1
        or original_passes[0].get("projectId") != identity.get("projectId")
        or _pass_timeline(original_passes[0], BASELINE_ID) is None
    ):
        raise RuntimeError("Pinned original baseline capture is incomplete")
    original_baseline = original_passes[0]

    project = require_current(resolve, config, identity)
    current = project.GetCurrentTimeline()
    selected_before = None if current is None else current.GetUniqueId()
    preflight = capture(
        resolve, config, identity, expected, output, stamp + "-preflight", environment
    )
    preflight_capture = json.loads(Path(preflight["capturePath"]).read_text())
    preflight_passes = preflight_capture.get("passes", [])
    if (
        preflight.get("status") != "equal-adjacent-reads"
        or len(preflight_passes) != 2
        or any(errors(value) for value in preflight_passes)
        or preflight_passes != [pinned, pinned]
        or selected_before != R1_ID
        or project.GetCurrentTimeline() is None
        or project.GetCurrentTimeline().GetUniqueId() != R1_ID
    ):
        return {
            "status": "context-mismatch-refused",
            "action": "native-context",
            "preflight": preflight,
            "selectedTimelineId": selected_before,
            "reason": (
                "Current state or selection does not exactly match pinned R1 capture"
            ),
        }

    journal = output / f"native-context-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    selections = []
    failed = None
    for name, timeline_id in (("baseline", BASELINE_ID), ("R1", R1_ID)):
        try:
            project = require_current(resolve, config, identity)
            timeline = next(
                project.GetTimelineByIndex(index)
                for index in range(1, project.GetTimelineCount() + 1)
                if project.GetTimelineByIndex(index).GetUniqueId() == timeline_id
            )
            retain("SetCurrentTimeline", "request", [timeline_id])
            result = project.SetCurrentTimeline(timeline)
            if result is None or result is False:
                raise RuntimeError("SetCurrentTimeline refused operation")
            retain("SetCurrentTimeline", "return", result)
            current = project.GetCurrentTimeline()
            selected_id = None if current is None else current.GetUniqueId()
            retain(
                "SetCurrentTimeline(readback)",
                "readback",
                {"selectedTimelineId": selected_id},
            )
            if selected_id != timeline_id:
                raise RuntimeError("Selected timeline ID differs")
            selected_capture = capture(
                resolve,
                config,
                identity,
                expected,
                output,
                stamp + "-selected-" + name,
                environment,
            )
            current = project.GetCurrentTimeline()
            if current is None or current.GetUniqueId() != timeline_id:
                raise RuntimeError("Selected timeline changed during capture")
            selections.append((name, selected_capture))
            if selected_capture["status"] != "equal-adjacent-reads":
                raise RuntimeError("Selected-context capture is incomplete")
        except Exception as error:
            failed = f"{type(error).__name__}: {error}"
            retain("selection/capture", "failure", failed)
            best_effort = None
            try:
                best_effort = capture(
                    resolve,
                    config,
                    identity,
                    expected,
                    output,
                    stamp + "-failure-best-effort",
                    environment,
                )
                retain("selection/capture(best effort)", "readback", best_effort)
            except Exception as capture_error:
                retain(
                    "selection/capture(best effort)",
                    "failure",
                    f"{type(capture_error).__name__}: {capture_error}",
                )
            return {
                "status": "selection-failed-refused",
                "action": "native-context",
                "journal": str(journal),
                "captures": [
                    preflight,
                    *[c for _, c in selections],
                    *([] if best_effort is None else [best_effort]),
                ],
                "failure": failed,
            }

    baseline_capture = json.loads(Path(selections[0][1]["capturePath"]).read_text())
    r1_capture = json.loads(Path(selections[1][1]["capturePath"]).read_text())
    baseline_passes = baseline_capture.get("passes", [])
    r1_passes = r1_capture.get("passes", [])
    if (
        len(baseline_passes) != 2
        or baseline_passes[0] != baseline_passes[1]
        or not _baseline_usage_comparison(baseline_passes[0], original_baseline)
        or len(r1_passes) != 2
        or r1_passes[0] != r1_passes[1]
        or r1_passes != [pinned, pinned]
    ):
        return {
            "status": "context-mismatch-refused",
            "action": "native-context",
            "journal": str(journal),
            "captures": [preflight, *[c for _, c in selections]],
            "reason": (
                "Selected baseline or reselected R1 differs beyond the exact allowlist"
            ),
        }
    return {
        "status": "equal-adjacent-reads",
        "action": "native-context",
        "journal": str(journal),
        "captures": [preflight, *[c for _, c in selections]],
        "comparisons": {
            "baseline": (
                "equal to pinned baseline except five sources/six verified Usage leaves"
            ),
            "R1": "exactly equal to pinned saved duplicate snapshot",
        },
    }


def _matrix_usage(timelines):
    values = {}
    filenames = {entry[0] for entry in MATRIX_RECIPE}
    for timeline in timelines:
        for track in timeline.get("tracks", []):
            for item in track.get("items", []):
                props = (
                    item.get("GetMediaPoolItem", {})
                    .get("GetClipProperty", {})
                    .get("value")
                )
                if isinstance(props, dict):
                    locator = props.get("File Path")
                    name = Path(locator).name if isinstance(locator, str) else None
                    if name in filenames:
                        values.setdefault(name, []).append(props.get("Usage"))
    return values


def _matrix_old_timelines_match(before, after):
    increments = {
        "base.mov": 19,
        "cutaway.mov": 19,
        "overlay.png": 19,
        "bed.wav": 19,
        "repeated.wav": 38,
    }
    before_timelines, after_timelines = (
        before.get("timelines", []),
        after.get("timelines", []),
    )
    if len(before_timelines) != 3 or len(after_timelines) != 3:
        return False
    preserved_ids = {BASELINE_ID, R1_ID}
    before_timelines = [
        row
        for row in before_timelines
        if row.get("GetUniqueId", {}).get("value") in preserved_ids
    ]
    after_timelines = [
        row
        for row in after_timelines
        if row.get("GetUniqueId", {}).get("value") in preserved_ids
    ]
    if len(before_timelines) != 2 or len(after_timelines) != 2:
        return False
    before_by_id = {
        row.get("GetUniqueId", {}).get("value"): row for row in before_timelines
    }
    after_by_id = {
        row.get("GetUniqueId", {}).get("value"): row for row in after_timelines
    }
    if set(before_by_id) != preserved_ids or set(after_by_id) != preserved_ids:
        return False
    before_usage, after_usage = (
        _matrix_usage(before_timelines),
        _matrix_usage([after_by_id.get(key, {}) for key in before_by_id]),
    )
    if set(before_usage) != set(increments) or set(after_usage) != set(increments):
        return False
    for name, increment in increments.items():
        if len(before_usage[name]) != len(after_usage[name]) or not before_usage[name]:
            return False
        if len(set(before_usage[name])) != 1 or len(set(after_usage[name])) != 1:
            return False
        try:
            if int(after_usage[name][0]) != int(before_usage[name][0]) + increment:
                return False
        except (TypeError, ValueError):
            return False
    for timeline_id, old in before_by_id.items():
        new = deepcopy(after_by_id.get(timeline_id))
        if not isinstance(new, dict):
            return False
        for track in new.get("tracks", []):
            for item in track.get("items", []):
                props = (
                    item.get("GetMediaPoolItem", {})
                    .get("GetClipProperty", {})
                    .get("value")
                )
                locator = props.get("File Path") if isinstance(props, dict) else None
                if isinstance(locator, str) and Path(locator).name in increments:
                    props["Usage"] = "__usage__"
        old_copy = deepcopy(old)
        for track in old_copy.get("tracks", []):
            for item in track.get("items", []):
                props = (
                    item.get("GetMediaPoolItem", {})
                    .get("GetClipProperty", {})
                    .get("value")
                )
                locator = props.get("File Path") if isinstance(props, dict) else None
                if isinstance(locator, str) and Path(locator).name in increments:
                    props["Usage"] = "__usage__"
        if new != old_copy:
            return False
    return True


def _marker_at(markers, frame):
    try:
        matches = [
            value for key, value in markers.items() if Decimal(str(key)) == frame
        ]
    except (AttributeError, InvalidOperation, TypeError):
        return {}
    return matches[0] if len(matches) == 1 else {}


def _validate_matrix_layout(
    timeline, expected_ids, source_ids, approved_sources, prior_ids
):
    tracks = timeline.get("tracks", [])
    if len(tracks) != 6:
        raise RuntimeError("Final matrix must have exactly six tracks")
    by_track = {(track.get("type"), track.get("index")): track for track in tracks}
    if set(by_track) != {
        (kind, index) for kind in ("video", "audio") for index in (1, 2, 3)
    }:
        raise RuntimeError("Final matrix track kinds/indices differ")
    if any(
        track.get("GetTrackSubType") != {"value": "stereo" if key[1] == 1 else "mono"}
        for key, track in by_track.items()
        if key[0] == "audio"
    ):
        raise RuntimeError("Final matrix audio formats differ from captured defaults")
    for track in tracks:
        if len(track.get("items", [])) != 19:
            raise RuntimeError("Each final matrix track must contain 19 items")

    seen = set()
    expected_locations = {}
    for section_index, section in enumerate(MATRIX_SECTIONS):
        start = section_index * 500
        for occurrence, (
            filename,
            kind,
            track_index,
            _src,
            duration,
            offset,
            enabled,
        ) in enumerate(MATRIX_RECIPE):
            expected_locations[(kind, track_index, start + offset)] = (
                filename,
                duration,
                enabled,
                section,
                occurrence,
            )
    found = set()
    for (kind, track_index), track in by_track.items():
        for item in track.get("items", []):
            item_id = item.get("GetUniqueId", {}).get("value")
            record = item.get("GetStart", {}).get("value")
            key = (kind, track_index, record)
            expected = expected_locations.get(key)
            if expected is None or key in found:
                raise RuntimeError("Final matrix contains an unexpected placement")
            found.add(key)
            filename, requested_duration, enabled, section, occurrence = expected
            if not isinstance(item_id, str) or item_id in prior_ids or item_id in seen:
                raise RuntimeError("Final matrix UID is missing, old or duplicated")
            seen.add(item_id)
            media = item.get("GetMediaPoolItem", {})
            props = media.get("GetClipProperty", {}).get("value", {})
            source_bytes = media.get("sourceBytes", {})
            if (
                Path(props.get("File Path", "")).name != filename
                or media.get("GetUniqueId", {}).get("value") != source_ids[filename]
                or props.get("File Path") not in approved_sources
                or source_bytes.get("sha256") != approved_sources[props["File Path"]]
                or source_bytes.get("hashMatches") is not True
            ):
                raise RuntimeError("Final matrix source UID/path/hash differs")
            expected_duration = (
                125 if filename == "overlay.png" else requested_duration - 1
            )
            expected_end = record + (
                125 if filename == "overlay.png" else requested_duration - 1
            )
            expected_source_end = (
                0 if filename == "overlay.png" else requested_duration - 1
            )
            if (
                item.get("GetDuration") != {"value": expected_duration}
                or item.get("GetEnd") != {"value": expected_end}
                or item.get("GetClipEnabled") != {"value": enabled}
                or item.get("GetSourceStartFrame") != {"value": 0}
                or item.get("GetSourceEndFrame") != {"value": expected_source_end}
            ):
                raise RuntimeError("Final matrix placement or enabled readback differs")
            marker = _marker_at(item.get("GetMarkers", {}).get("value", {}), 0)
            custom = json.dumps(
                {"issue": 141, "section": section, "occurrence": occurrence},
                sort_keys=True,
            )
            if marker.get("customData") != custom:
                raise RuntimeError("Final occurrence marker differs")
            links = {
                row.get("value")
                for row in item.get("GetLinkedItems", [])
                if isinstance(row, dict)
            }
            if occurrence in (0, 1):
                mate_key = ("audio", 1, record)
                mate = (
                    next(
                        other.get("GetUniqueId", {}).get("value")
                        for other in by_track[("audio", 1)].get("items", [])
                        if other.get("GetStart", {}).get("value") == mate_key[2]
                    )
                    if occurrence == 0
                    else next(
                        other.get("GetUniqueId", {}).get("value")
                        for other in by_track[("video", 1)].get("items", [])
                        if other.get("GetStart", {}).get("value") == record
                    )
                )
                if links != {mate}:
                    raise RuntimeError("Final base V1/A1 link differs")
            elif links:
                raise RuntimeError("Unexpected case-local link exists")
    if found != set(expected_locations) or seen != expected_ids:
        raise RuntimeError("Final matrix placement set or occurrence IDs differ")
    markers = timeline.get("GetMarkers", {}).get("value")
    if not isinstance(markers, dict) or len(markers) != 19:
        raise RuntimeError("Final matrix case markers are incomplete")
    for index, section in enumerate(MATRIX_SECTIONS):
        marker = _marker_at(markers, index * 500)
        custom = json.dumps(
            {"issue": 141, "section": section, "index": index}, sort_keys=True
        )
        if marker.get("name") != f"141 {section}" or marker.get("customData") != custom:
            raise RuntimeError("Final matrix case marker data differs")


class _R4PoolInventoryError(RuntimeError):
    def __init__(self, message, diagnostic):
        super().__init__(message)
        self.diagnostic = diagnostic


def _r4_pool_inventory(project, expected):
    """Read every pool folder, identifying timeline proxies by their linked item."""
    root = project.GetMediaPool().GetRootFolder()
    timeline_mappings = []
    timeline_pool_uids = set()
    for index in range(1, project.GetTimelineCount() + 1):
        timeline = project.GetTimelineByIndex(index)
        timeline_uid = read(timeline, "GetUniqueId")
        timeline_name = read(timeline, "GetName")
        pool_item = None
        try:
            pool_item = timeline.GetMediaPoolItem()
            pool_uid = read(pool_item, "GetUniqueId")
            pool_name = read(pool_item, "GetName")
            pool_properties = read(pool_item, "GetClipProperty")
        except Exception as error:
            pool_uid = {"error": f"{type(error).__name__}: {error}"}
            pool_name = pool_properties = {"error": "GetMediaPoolItem unreadable"}
        mapping = {
            "timelineUid": timeline_uid,
            "timelineName": timeline_name,
            "poolItemUid": pool_uid,
            "poolItemName": pool_name,
            "poolItemProperties": pool_properties,
        }
        timeline_mappings.append(mapping)
        value = pool_uid.get("value") if isinstance(pool_uid, dict) else None
        if isinstance(value, str) and value:
            timeline_pool_uids.add(value)
        if (
            not isinstance(timeline_uid.get("value"), str)
            or not isinstance(timeline_name.get("value"), str)
            or not isinstance(value, str)
            or not value
            or errors(mapping)
        ):
            raise _R4PoolInventoryError(
                "Timeline-to-pool-item mapping is unreadable",
                {
                    "timelineMappings": timeline_mappings,
                    "failedEntry": mapping,
                    "folders": [],
                    "items": [],
                },
            )
    folders, items, seen_objects, folder_uids = [], [], set(), set()

    def fail(message, entry):
        raise _R4PoolInventoryError(
            message,
            {
                "timelineMappings": timeline_mappings,
                "failedEntry": entry,
                "folders": folders,
                "items": items,
            },
        )

    def visit(folder):
        marker = id(folder)
        if marker in seen_objects:
            raise RuntimeError("Media-pool folder tree is cyclic or repeated")
        seen_objects.add(marker)
        folder_id = folder.GetUniqueId()
        folder_name = folder.GetName()
        if (
            not isinstance(folder_id, str)
            or not folder_id
            or folder_id in folder_uids
            or not isinstance(folder_name, str)
        ):
            raise RuntimeError("Media-pool folder identity is unreadable")
        folder_uids.add(folder_id)
        folders.append({"uid": folder_id, "name": folder_name})
        clips = folder.GetClipList()
        children = folder.GetSubFolderList()
        if not isinstance(clips, (list, tuple)) or not isinstance(
            children, (list, tuple)
        ):
            raise RuntimeError("Media-pool folder contents are unreadable")
        for clip in clips:
            uid = read(clip, "GetUniqueId")
            name = read(clip, "GetName")
            clip_properties = read(clip, "GetClipProperty")
            properties = clip_properties.get("value")
            evidence = (
                {
                    "GetUniqueId": uid,
                    "GetName": name,
                    "GetClipProperty": clip_properties,
                    "sourceBytes": {"status": "timeline-uid-not-hashed"},
                }
                if uid.get("value") in timeline_pool_uids
                else media_evidence(clip, expected)
            )
            if (
                not isinstance(uid.get("value"), str)
                or not uid["value"]
                or not isinstance(name.get("value"), str)
                or not isinstance(properties, dict)
                or (
                    uid.get("value") not in timeline_pool_uids
                    and not isinstance(properties.get("File Path"), str)
                )
                or errors(evidence)
            ):
                fail(
                    "Media-pool item identity/properties are unreadable",
                    {
                        "uid": uid,
                        "name": name,
                        "folderUid": folder_id,
                        "GetClipProperty": clip_properties,
                        "evidence": evidence,
                    },
                )
            items.append(
                {
                    "uid": uid["value"],
                    "name": name,
                    "folderUid": folder_id,
                    "evidence": evidence,
                }
            )
        for child in children:
            visit(child)

    if root is None:
        raise RuntimeError("Media-pool root is unreadable")
    visit(root)
    uids = [row["uid"] for row in items]
    if len(uids) != len(set(uids)):
        raise RuntimeError("Media-pool item UID is duplicated")
    return {
        "folders": folders,
        "items": items,
        "timelineMappings": timeline_mappings,
    }


def r4_prepare(resolve, config, identity, expected, output, stamp, environment):
    """Import the approved copy only when distinct, then make one V1 occurrence."""
    if config.get("action") != "r4-availability":
        raise ValueError("Unknown R4 availability action")
    prepared = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
    identity = prepared.get("identity", {})
    if (
        identity.get("projectId") != "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
        or prepared.get("manifestSha256") != config.get("manifestSha256")
        or environment.get("version") != CONTEXT_ENVIRONMENT
    ):
        raise RuntimeError("Pinned project, manifest, or Resolve build differs")
    pinned_path = output / PICTURE_CAPTURE
    if sha256(pinned_path) != PICTURE_CAPTURE_SHA256:
        raise RuntimeError("Pinned R4 checkpoint changed or is missing")
    pinned_capture = json.loads(pinned_path.read_text(encoding="utf-8"))
    passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(passes) != 2
        or passes[0] != passes[1]
        or any(errors(value) for value in passes)
        or passes[0].get("projectId") != identity["projectId"]
        or {
            row.get("GetUniqueId", {}).get("value")
            for row in passes[0].get("timelines", [])
        }
        != {MATRIX_PARTIAL_ID, BASELINE_ID, R1_ID}
    ):
        raise RuntimeError("Pinned R4 checkpoint is incomplete or inconsistent")
    pinned = passes[0]
    if _pass_timeline(pinned, MATRIX_PARTIAL_ID).get("GetName") != {
        "value": MATRIX_NAME
    }:
        raise RuntimeError("Pinned Matrix identity differs")
    source_path = Path(config["mediaDir"]) / "relink/base.mov"
    source_path = source_path.resolve(strict=True)
    if (
        expected.get(str(source_path)) != R4_IMPORT_SHA256
        or sha256(source_path) != R4_IMPORT_SHA256
    ):
        raise RuntimeError("Approved relink/base.mov hash differs")
    journal = output / f"r4-availability-{stamp}.jsonl"

    def record(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    def pool_inventory(project, phase):
        try:
            return _r4_pool_inventory(project, expected)
        except _R4PoolInventoryError as error:
            diagnostic_path = output / f"r4-pool-diagnostic-{stamp}-{phase}.json"
            write_json(
                diagnostic_path,
                {
                    "kind": "read-only-r4-pool-inventory-diagnostic",
                    "phase": phase,
                    "error": str(error),
                    **error.diagnostic,
                },
            )
            error.diagnostic_path = str(diagnostic_path)
            record(
                "MediaPoolInventory",
                "failure",
                {"phase": phase, "diagnosticPath": str(diagnostic_path)},
            )
            raise

    def refuse_context(reason, evidence):
        failure_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
        write_json(
            output / f"r4-refusal-{failure_stamp}.json",
            {
                "reason": reason,
                "evidence": evidence,
                "partialStateMayRemain": True,
                "instruction": "Stop; retain evidence. Do not retry or clean up.",
            },
        )
        record("ContextGuard", "failure", reason)
        raise RuntimeError(reason)

    context_baseline = None

    def canonical_observation(value):
        return json.loads(json.dumps(value, allow_nan=False))

    def same_timeline_content(current, original, uid):
        current, original = deepcopy(current), deepcopy(original)

        def remove_usage(value):
            if isinstance(value, dict):
                clip = value.get("GetClipProperty")
                props = clip.get("value") if isinstance(clip, dict) else None
                if isinstance(props, dict):
                    props.pop("Usage", None)
                for child in value.values():
                    remove_usage(child)
            elif isinstance(value, list):
                for child in value:
                    remove_usage(child)

        remove_usage(current)
        remove_usage(original)
        return _pass_timeline(current, uid) == _pass_timeline(original, uid)

    def live_state(
        expected_selected=MATRIX_PARTIAL_ID, compare_pinned=True, reject_source=True
    ):
        nonlocal context_baseline
        project = require_current(resolve, config, identity)
        selected = project.GetCurrentTimeline()
        allowed = (
            expected_selected
            if isinstance(expected_selected, tuple)
            else (expected_selected,)
        )
        if selected is None or selected.GetUniqueId() not in allowed:
            refuse_context(
                "Current timeline selection differs from expected context",
                {
                    "expected": allowed,
                    "selected": None if selected is None else selected.GetUniqueId(),
                },
            )
        reads = [
            canonical_observation(observe(resolve, config, identity, expected))
            for _ in range(2)
        ]
        if reads[0] != reads[1]:
            refuse_context("Adjacent live timeline reads differ", {"passes": reads})
        if compare_pinned and reads[0] != pinned:
            refuse_context(
                "Live read differs from pinned checkpoint", {"passes": reads}
            )
        if compare_pinned is False:
            reference = context_baseline or pinned
            if (
                reads[0].get("projectId") != reference.get("projectId")
                or reads[0].get("GetSettings") != reference.get("GetSettings")
                or any(
                    not same_timeline_content(reads[0], reference, uid)
                    for uid in (MATRIX_PARTIAL_ID, BASELINE_ID, R1_ID)
                )
            ):
                refuse_context(
                    "An original timeline changed from its same-context baseline",
                    {
                        "passes": reads,
                        "baseline": reference,
                    },
                )
        try:
            inventories = [
                pool_inventory(project, f"preflight-{index}") for index in range(2)
            ]
        except _R4PoolInventoryError as error:
            refuse_context(
                str(error),
                {
                    "diagnosticPath": getattr(error, "diagnostic_path", None),
                    "poolDiagnostic": error.diagnostic,
                },
            )
        if inventories[0] != inventories[1]:
            refuse_context(
                "Media-pool inventory changed between adjacent reads",
                {
                    "poolInventories": inventories,
                },
            )
        if compare_pinned:
            read_stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
            write_json(
                output / f"r4-readonly-{read_stamp}.json",
                {
                    "timelinePasses": reads,
                    "poolInventories": inventories,
                    "selectedTimelineUid": selected.GetUniqueId(),
                },
            )
        inventory = inventories[0]
        if reject_source and any(
            Path(
                row["evidence"]
                .get("GetClipProperty", {})
                .get("value", {})
                .get("File Path", "")
            ).name
            == source_path.name
            and row["evidence"]
            .get("GetClipProperty", {})
            .get("value", {})
            .get("File Path")
            == str(source_path)
            for row in inventory["items"]
        ):
            raise RuntimeError("Approved relink locator already exists in the pool")
        return project, inventory

    def mutate(obj, method, args, audit, guard=None):
        (guard or live_state)()
        record(method, "request", audit)
        try:
            value = getattr(obj, method)(*args)
            if value is None or value is False:
                raise RuntimeError(f"{method} refused operation")
            if method == "ImportMedia":
                result = [media_evidence(item, expected) for item in value]
            elif method == "CreateEmptyTimeline":
                result = {"uid": value.GetUniqueId(), "name": value.GetName()}
            elif method == "AppendToTimeline":
                result = [item.GetUniqueId() for item in value]
            else:
                result = value
            record(method, "return", result)
            return value
        except Exception as error:
            record(method, "failure", f"{type(error).__name__}: {error}")
            raise

    def require_existing_items_unchanged(before, after):
        before_items = {row["uid"]: row for row in before["items"]}
        after_items = {row["uid"]: row for row in after["items"]}
        if not before_items.keys() <= after_items.keys():
            raise RuntimeError("An existing pool item disappeared")
        for uid, old in before_items.items():
            new = after_items[uid]
            if old["name"] != new["name"] or old["folderUid"] != new["folderUid"]:
                raise RuntimeError("An existing pool item identity changed")
            old_evidence, new_evidence = (
                deepcopy(old["evidence"]),
                deepcopy(new["evidence"]),
            )
            for value in (old_evidence, new_evidence):
                props = value.get("GetClipProperty", {}).get("value")
                if isinstance(props, dict):
                    props.pop("Usage", None)
            if old_evidence != new_evidence:
                raise RuntimeError("An existing pool item changed beyond Usage")

    before_project, before_inventory = live_state()
    before_uids = {row["uid"] for row in before_inventory["items"]}
    imported = mutate(
        before_project.GetMediaPool(),
        "ImportMedia",
        ([str(source_path)],),
        [{"FilePath": "<synthetic-media>/relink/base.mov", "sha256": R4_IMPORT_SHA256}],
    )
    try:
        after_import = pool_inventory(before_project, "after-import")
    except Exception as error:
        record(
            "ImportMedia",
            "failure",
            f"post-import inventory: {type(error).__name__}: {error}",
        )
        raise
    write_json(output / f"r4-pool-after-import-{stamp}.json", after_import)
    require_existing_items_unchanged(before_inventory, after_import)
    if not isinstance(imported, (list, tuple)) or len(imported) != 1:
        record("ImportMedia", "failure", "expected exactly one returned item")
        raise RuntimeError(
            "ImportMedia did not return exactly one item; retained partial state"
        )
    imported_item = imported[0]
    imported_uid = imported_item.GetUniqueId()
    props = imported_item.GetClipProperty()
    returned_uids = [row["uid"] for row in after_import["items"]]
    evidence = media_evidence(imported_item, expected)
    if (
        not isinstance(imported_uid, str)
        or imported_uid in before_uids
        or {row["uid"] for row in after_import["items"]} - before_uids != {imported_uid}
        or returned_uids.count(imported_uid) != 1
        or read(imported_item, "GetName").get("value") != "base.mov"
        or props.get("File Path") != str(source_path)
        or evidence.get("sourceBytes", {}).get("sha256") != R4_IMPORT_SHA256
        or evidence.get("sourceBytes", {}).get("hashMatches") is not True
    ):
        record(
            "ImportMedia",
            "failure",
            "returned UID/path/hash did not prove a new exact item",
        )
        raise RuntimeError(
            "Import UID/path/hash is not a new exact item; retained partial state"
        )

    project, _ = live_state(compare_pinned=False, reject_source=False)
    pool = project.GetMediaPool()
    created = mutate(
        pool,
        "CreateEmptyTimeline",
        (R4_NAME,),
        R4_NAME,
        guard=lambda: live_state(compare_pinned=False, reject_source=False),
    )
    if (
        created.GetName() != R4_NAME
        or not created.GetUniqueId()
        or created.GetUniqueId() in {MATRIX_PARTIAL_ID, BASELINE_ID, R1_ID}
        or project.GetTimelineCount() != 4
    ):
        record(
            "CreateEmptyTimeline",
            "failure",
            "created timeline identity/count is ambiguous",
        )
        raise RuntimeError("Created R4 timeline identity/count is ambiguous")
    mutate(
        project,
        "SetCurrentTimeline",
        (created,),
        created.GetUniqueId(),
        guard=lambda: live_state(
            (MATRIX_PARTIAL_ID, created.GetUniqueId()),
            compare_pinned=None,
            reject_source=False,
        ),
    )
    if project.GetCurrentTimeline().GetUniqueId() != created.GetUniqueId():
        record("SetCurrentTimeline", "failure", "selection readback differs")
        raise RuntimeError("R4 timeline selection readback differs")
    for kind in ("video", "audio", "subtitle"):
        count = created.GetTrackCount(kind)
        if not isinstance(count, int) or count < 0:
            raise RuntimeError("R4 empty-timeline track inventory is unreadable")
        for index in range(1, count + 1):
            items = created.GetItemListInTrack(kind, index)
            if not isinstance(items, (list, tuple)) or items:
                raise RuntimeError("New R4 timeline is not empty before append")
    live_state(created.GetUniqueId(), compare_pinned=None, reject_source=False)
    context_reads = [
        canonical_observation(observe(resolve, config, identity, expected))
        for _ in range(2)
    ]
    if context_reads[0] != context_reads[1]:
        raise RuntimeError("Empty R4 selected-context reads differ")
    context_baseline = context_reads[0]
    write_json(output / f"r4-empty-selected-{stamp}.json", context_baseline)
    info = {
        "mediaPoolItem": imported_item,
        "startFrame": 0,
        "endFrame": 199,
        "mediaType": 1,
        "trackIndex": 1,
        "recordFrame": 0,
    }
    appended = mutate(
        pool,
        "AppendToTimeline",
        ([info],),
        [{**info, "mediaPoolItem": imported_uid}],
        guard=lambda: live_state(
            created.GetUniqueId(), compare_pinned=False, reject_source=False
        ),
    )
    if not isinstance(appended, (list, tuple)) or len(appended) != 1:
        record("AppendToTimeline", "failure", "expected exactly one returned item")
        raise RuntimeError("AppendToTimeline did not return exactly one item")
    placed = appended[0]
    placed_evidence = item_evidence(placed, expected)
    if (
        placed.GetMediaPoolItem().GetUniqueId() != imported_uid
        or placed.GetType() != "video"
        or placed.GetTrackTypeAndIndex() != ["video", 1]
        or placed.GetSourceStartFrame() != 0
        or placed.GetSourceEndFrame() != 199
        or placed.GetStart() != 0
        or placed.GetEnd() != 199
        or placed.GetDuration() != 199
    ):
        write_json(output / f"r4-placed-item-{stamp}.json", placed_evidence)
        record("AppendToTimeline", "failure", "source/record bounds differ")
        raise RuntimeError(
            "R4 item source/record bounds differ; retained partial state"
        )
    timeline_items = created.GetItemListInTrack("video", 1)
    if not isinstance(timeline_items, (list, tuple)) or len(timeline_items) != 1:
        raise RuntimeError("R4 must contain exactly one V1 item")
    for kind in ("video", "audio", "subtitle"):
        for index in range(1, created.GetTrackCount(kind) + 1):
            items = created.GetItemListInTrack(kind, index)
            if not isinstance(items, (list, tuple)) or (
                [item.GetUniqueId() for item in items]
                != [item.GetUniqueId() for item in timeline_items]
                if (kind, index) == ("video", 1)
                else bool(items)
            ):
                raise RuntimeError("R4 contains an extra or unreadable track item")
    project, _ = live_state(
        created.GetUniqueId(), compare_pinned=False, reject_source=False
    )
    record("SaveProject", "request", [])
    try:
        saved = resolve.GetProjectManager().SaveProject()
        record("SaveProject", "return", saved)
    except Exception as error:
        record("SaveProject", "failure", f"{type(error).__name__}: {error}")
        raise
    if saved is False or saved is None:
        raise RuntimeError("SaveProject refused operation")
    final = capture(
        resolve, config, identity, expected, output, stamp + "-after", environment
    )
    if final["status"] != "equal-adjacent-reads":
        raise RuntimeError("R4 final reads are inconsistent")
    final_state = json.loads(Path(final["capturePath"]).read_text(encoding="utf-8"))[
        "passes"
    ][0]
    r4_rows = [
        row
        for row in final_state.get("timelines", [])
        if row.get("GetUniqueId", {}).get("value") == created.GetUniqueId()
    ]
    if len(r4_rows) != 1 or r4_rows[0].get("GetName") != {"value": R4_NAME}:
        raise RuntimeError("Saved R4 timeline identity is missing or duplicated")
    captured_items = [
        item
        for track in r4_rows[0].get("tracks", [])
        for item in track.get("items", [])
    ]
    if (
        len(captured_items) != 1
        or any(
            track.get("items")
            and (track.get("type"), track.get("index")) != ("video", 1)
            for track in r4_rows[0].get("tracks", [])
        )
        or captured_items[0].get("GetUniqueId", {}).get("value") != placed.GetUniqueId()
        or captured_items[0].get("GetStart") != {"value": 0}
        or captured_items[0].get("GetEnd") != {"value": 199}
        or captured_items[0].get("GetDuration") != {"value": 199}
        or captured_items[0].get("GetSourceStartFrame") != {"value": 0}
        or captured_items[0].get("GetSourceEndFrame") != {"value": 199}
        or captured_items[0].get("GetMediaPoolItem", {}).get("GetUniqueId")
        != {"value": imported_uid}
    ):
        raise RuntimeError("Saved R4 occurrence differs from the requested V1 item")
    if any(
        not same_timeline_content(final_state, context_baseline, uid)
        for uid in (MATRIX_PARTIAL_ID, BASELINE_ID, R1_ID)
    ):
        raise RuntimeError("An original timeline changed; retained evidence")
    final_inventories = [
        pool_inventory(project, f"final-{index}") for index in range(2)
    ]
    if final_inventories[0] != final_inventories[1]:
        raise RuntimeError("Final media-pool inventories differ")
    require_existing_items_unchanged(before_inventory, final_inventories[0])
    write_json(output / f"r4-pool-final-{stamp}.json", {"passes": final_inventories})
    return {
        "status": final["status"],
        "journal": str(journal),
        "capture": final,
        "importedUid": imported_uid,
        "timelineUid": created.GetUniqueId(),
    }


def native_matrix(resolve, config, identity, expected, output, stamp, environment):
    """Create and verify the fixed, separated 19-case synthetic matrix."""
    if config.get("action") != "native-matrix":
        raise ValueError("Unknown native matrix action")
    prepared = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
    prepared_identity = prepared.get("identity")
    if (
        not isinstance(prepared_identity, dict)
        or prepared_identity.get("projectId") != identity.get("projectId")
        or prepared_identity.get("projectName") != identity.get("projectName")
        or prepared_identity.get("baselineTimelineId") != BASELINE_ID
        or prepared.get("manifestSha256") != config.get("manifestSha256")
        or environment.get("version") != CONTEXT_ENVIRONMENT
    ):
        raise RuntimeError("Prepared project or Resolve build differs; refusing")
    identity = prepared_identity
    pinned_path = output / CONTEXT_CAPTURE
    if sha256(pinned_path) != CONTEXT_CAPTURE_SHA256:
        raise RuntimeError("Pinned duplicate capture changed or is missing; refusing")
    pinned = json.loads(pinned_path.read_text(encoding="utf-8"))
    passes = pinned.get("passes", [])
    if (
        pinned.get("consistency") != "equal-adjacent-reads"
        or len(passes) != 2
        or passes[0] != passes[1]
        or any(errors(x) for x in passes)
        or len(passes[0].get("timelines", [])) != 2
        or {
            row.get("GetUniqueId", {}).get("value")
            for row in passes[0].get("timelines", [])
        }
        != {BASELINE_ID, R1_ID}
        or passes[0].get("projectId") != identity.get("projectId")
        or _pass_timeline(passes[0], R1_ID) is None
    ):
        raise RuntimeError("Pinned duplicate capture is incomplete; refusing")
    pinned_pass = passes[0]
    baseline_file = output / CONTEXT_BASELINE_CAPTURE
    if sha256(baseline_file) != CONTEXT_BASELINE_SHA256:
        raise RuntimeError("Pinned original baseline changed or is missing; refusing")

    # Tie each existing pool item to the raw baseline UID/path/hash and manifest.
    baseline_capture = json.loads(baseline_file.read_text(encoding="utf-8"))
    baseline_passes = baseline_capture.get("passes", [])
    if (
        baseline_capture.get("consistency") != "equal-adjacent-reads"
        or len(baseline_passes) != 2
        or baseline_passes[0] != baseline_passes[1]
        or any(errors(value) for value in baseline_passes)
        or baseline_passes[0].get("projectId") != identity.get("projectId")
        or len(baseline_passes[0].get("timelines", [])) != 1
    ):
        raise RuntimeError("Pinned baseline is incomplete; refusing")
    baseline_timeline = _pass_timeline(baseline_passes[0], BASELINE_ID)
    source_paths = {
        row[0]: str(Path(config["mediaDir"]) / row[0]) for row in MATRIX_RECIPE
    }
    files = {name: expected.get(locator) for name, locator in source_paths.items()}
    if any(not isinstance(digest, str) for digest in files.values()):
        raise RuntimeError("Matrix source locators are missing from the manifest")
    source_ids = {}
    for track in baseline_timeline.get("tracks", []):
        for occurrence in track.get("items", []):
            media = occurrence.get("GetMediaPoolItem", {})
            props = media.get("GetClipProperty", {}).get("value", {})
            locator = props.get("File Path")
            name = Path(locator).name if isinstance(locator, str) else ""
            if name not in files:
                continue
            if (
                locator != source_paths[name]
                or media.get("sourceBytes", {}).get("sha256") != files[name]
                or media.get("sourceBytes", {}).get("hashMatches") is not True
                or media.get("GetUniqueId", {}).get("value") is None
            ):
                raise RuntimeError("Baseline source identity or hash differs; refusing")
            media_id = media["GetUniqueId"]["value"]
            if name in source_ids and source_ids[name] != media_id:
                raise RuntimeError("Baseline source UID is inconsistent; refusing")
            source_ids[name] = media_id
    if set(source_ids) != {row[0] for row in MATRIX_RECIPE}:
        raise RuntimeError("Baseline does not identify all five matrix sources")

    continuing = config.get("stage") == "R1-R3-matrix-marker-continuation"
    checkpoint = pinned_pass
    expected_selected_id = R1_ID
    if continuing:
        for filename, digest in MATRIX_CONTINUATION_HASHES.items():
            if sha256(output / filename) != digest:
                raise RuntimeError("Pinned partial matrix evidence differs; refusing")
        checkpoint = json.loads((output / MATRIX_PARTIAL_CAPTURE).read_text())[
            "passes"
        ][0]
        expected_selected_id = MATRIX_PARTIAL_ID

    project = require_current(resolve, config, identity)
    current = project.GetCurrentTimeline()
    if current is None or current.GetUniqueId() != expected_selected_id:
        return {
            "status": "matrix-preflight-refused",
            "reason": "Pinned selection differs",
        }
    preflight = capture(
        resolve, config, identity, expected, output, stamp + "-preflight", environment
    )
    preflight_passes = json.loads(Path(preflight["capturePath"]).read_text()).get(
        "passes", []
    )
    if preflight.get("status") != "equal-adjacent-reads" or preflight_passes != [
        checkpoint,
        checkpoint,
    ]:
        return {"status": "matrix-preflight-refused", "preflight": preflight}
    if project.GetTimelineCount() != (3 if continuing else 2) or (
        not continuing
        and any(
            project.GetTimelineByIndex(i).GetName() == MATRIX_NAME
            for i in range(1, project.GetTimelineCount() + 1)
        )
    ):
        return {
            "status": "matrix-preflight-refused",
            "preflight": preflight,
            "reason": "Unexpected or already-created matrix timeline",
        }

    if (
        project.GetCurrentTimeline() is None
        or project.GetCurrentTimeline().GetUniqueId() != expected_selected_id
    ):
        return {
            "status": "matrix-preflight-refused",
            "preflight": preflight,
            "reason": "R1 selection changed during preflight",
        }

    journal = output / f"native-matrix-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    selection_state = {"matrixSelected": continuing}
    matrix_id = MATRIX_PARTIAL_ID if continuing else None

    def mutate(obj, method, *args, audit_args=None):
        require_current(resolve, config, identity)
        if method == "CreateEmptyTimeline":
            selected = project.GetCurrentTimeline()
            if selected is None or selected.GetUniqueId() != R1_ID:
                raise RuntimeError("R1 is no longer selected; refusing matrix creation")
        elif method == "SetCurrentTimeline":
            selected = project.GetCurrentTimeline()
            if (
                matrix is None
                or selection_state["matrixSelected"]
                or selected is None
                or selected.GetUniqueId() not in {R1_ID, matrix_id}
                or not args
                or args[0].GetUniqueId() != matrix_id
            ):
                raise RuntimeError("Unexpected timeline selection transition")
        elif matrix is not None:
            selected = project.GetCurrentTimeline()
            if selected is None or selected.GetUniqueId() != matrix_id:
                raise RuntimeError("Matrix is no longer selected; refusing mutation")
        retain(method, "request", args if audit_args is None else audit_args)
        try:
            value = getattr(obj, method)(*args)
            if value is None or value is False:
                raise RuntimeError(f"{method} refused operation")
            if method == "AppendToTimeline":
                summary = [read(item, "GetUniqueId") for item in value]
            elif method == "CreateEmptyTimeline":
                summary = {
                    "GetName": read(value, "GetName"),
                    "GetUniqueId": read(value, "GetUniqueId"),
                }
            else:
                summary = value
            retain(method, "return", summary)
            if method == "SetCurrentTimeline":
                selection_state["matrixSelected"] = True
            return value
        except Exception as error:
            retain(method, "failure", f"{type(error).__name__}: {error}")
            raise

    matrix = current if continuing else None
    empty_capture = None
    final_capture = None
    saved_capture = None
    try:
        pool = project.GetMediaPool()
        baseline = next(
            project.GetTimelineByIndex(i)
            for i in range(1, project.GetTimelineCount() + 1)
            if project.GetTimelineByIndex(i).GetUniqueId() == BASELINE_ID
        )
        by_id = {}
        for kind in ("video", "audio"):
            for index in range(1, baseline.GetTrackCount(kind) + 1):
                occurrences = baseline.GetItemListInTrack(kind, index)
                if not isinstance(occurrences, (list, tuple)):
                    raise RuntimeError("Baseline source occurrences are unreadable")
                for occurrence in occurrences:
                    media = occurrence.GetMediaPoolItem()
                    if media is None:
                        raise RuntimeError("Baseline source handle is missing")
                    by_id[media.GetUniqueId()] = media
        if set(by_id) != set(source_ids.values()):
            raise RuntimeError("Baseline contains unexpected source identities")
        sources = {}
        for filename, source_id in source_ids.items():
            source = by_id.get(source_id)
            if source is None:
                raise RuntimeError("Baseline media-pool UID is missing; refusing")
            evidence = media_evidence(source, expected)
            props = evidence.get("GetClipProperty", {}).get("value", {})
            locator = props.get("File Path") if isinstance(props, dict) else None
            if (
                locator != source_paths[filename]
                or source_evidence(locator, expected).get("sha256") != files[filename]
                or evidence.get("sourceBytes", {}).get("hashMatches") is not True
            ):
                raise RuntimeError(
                    "Current media-pool source differs from baseline; refusing"
                )
            sources[filename] = source
        if continuing:
            empty_capture = {
                "capturePath": str(output / MATRIX_EMPTY_CAPTURE),
                "sha256": MATRIX_CONTINUATION_HASHES[MATRIX_EMPTY_CAPTURE],
                "status": "equal-adjacent-reads",
            }
            empty_passes = json.loads((output / MATRIX_EMPTY_CAPTURE).read_text())[
                "passes"
            ]
        else:
            matrix = mutate(pool, "CreateEmptyTimeline", MATRIX_NAME)
            matrix_id = matrix.GetUniqueId()
            if (
                not matrix_id
                or matrix_id in {BASELINE_ID, R1_ID}
                or matrix.GetName() != MATRIX_NAME
            ):
                raise RuntimeError("Created matrix identity is unexpected")
            mutate(project, "SetCurrentTimeline", matrix, audit_args=[matrix_id])
            selected = project.GetCurrentTimeline()
            selected_id = None if selected is None else selected.GetUniqueId()
            retain(
                "SetCurrentTimeline(readback)",
                "readback",
                {"selectedTimelineId": selected_id},
            )
            if selected_id != matrix_id:
                raise RuntimeError("Matrix selection readback differs")
            mutate(matrix, "SetStartTimecode", "00:00:00:00")
            for kind in ("video", "audio"):
                for previous_count in range(matrix.GetTrackCount(kind), 3):
                    mutate(
                        matrix, "AddTrack", kind, *(["mono"] if kind == "audio" else [])
                    )
                    count = matrix.GetTrackCount(kind)
                    retain("GetTrackCount", "readback", {"type": kind, "count": count})
                    if count != previous_count + 1 or count > 3:
                        raise RuntimeError("Track count exceeded planned matrix")
                if matrix.GetTrackCount(kind) != 3:
                    raise RuntimeError("Could not establish three matrix tracks")
            empty_capture = capture(
                resolve,
                config,
                identity,
                expected,
                output,
                stamp + "-empty-selected-matrix",
                environment,
            )
            empty_passes = json.loads(
                Path(empty_capture["capturePath"]).read_text()
            ).get("passes", [])
        if empty_capture["status"] != "equal-adjacent-reads" or len(empty_passes) != 2:
            raise RuntimeError("Empty matrix before-capture is incomplete")
        if (
            empty_passes[0] != empty_passes[1]
            or any(errors(value) for value in empty_passes)
            or project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != matrix_id
        ):
            raise RuntimeError("Empty matrix capture or selected context differs")
        before = empty_passes[0]
        if len(before.get("timelines", [])) != 3 or {
            row.get("GetUniqueId", {}).get("value")
            for row in before.get("timelines", [])
        } != {BASELINE_ID, R1_ID, matrix_id}:
            raise RuntimeError(
                "Empty-matrix capture has unexpected timeline identities"
            )
        matrix_rows = [
            row
            for row in before["timelines"]
            if row.get("GetUniqueId", {}).get("value") == matrix_id
        ]
        if (
            len(matrix_rows) != 1
            or matrix_rows[0].get("GetName", {}).get("value") != MATRIX_NAME
            or any(track.get("items") for track in matrix_rows[0].get("tracks", []))
        ):
            raise RuntimeError("Matrix before-capture is not empty")
        before_old = [
            row
            for row in before.get("timelines", [])
            if row.get("GetUniqueId", {}).get("value") in {BASELINE_ID, R1_ID}
        ]
        if len(before_old) != 2 or any(errors(before_old)):
            raise RuntimeError("Old timelines are incomplete in matrix context")
        existing = None
        if continuing:
            prior_items = matrix.GetItemListInTrack("video", 1)
            if (
                not isinstance(prior_items, (list, tuple))
                or len(prior_items) != 1
                or prior_items[0].GetUniqueId() != MATRIX_FIRST_ITEM_ID
            ):
                raise RuntimeError("Pinned first matrix occurrence is unreadable")
            existing = prior_items[0]
        uid_set = {MATRIX_FIRST_ITEM_ID} if continuing else set()
        item_count = 1 if continuing else 0
        for section_index, section in enumerate(MATRIX_SECTIONS):
            start = section_index * 500
            if not (continuing and section_index == 0):
                mutate(
                    matrix,
                    "AddMarker",
                    start,
                    "Green",
                    f"141 {section}",
                    "Synthetic matrix case boundary",
                    1,
                    json.dumps(
                        {"issue": 141, "section": section, "index": section_index},
                        sort_keys=True,
                    ),
                )
            items = [existing] if continuing and section_index == 0 else []
            for occurrence_index, (
                filename,
                kind,
                track_index,
                source_start,
                duration,
                offset,
                enabled,
            ) in enumerate(MATRIX_RECIPE):
                if continuing and section_index == 0 and occurrence_index == 0:
                    continue
                info = {
                    "mediaPoolItem": sources[filename],
                    "mediaType": 1 if kind == "video" else 2,
                    "trackIndex": track_index,
                    "startFrame": source_start,
                    "endFrame": source_start + duration - 1,
                    "recordFrame": start + offset,
                }
                item = mutate(
                    pool,
                    "AppendToTimeline",
                    [info],
                    audit_args=[
                        {
                            **info,
                            "mediaPoolItem": source_ids[filename],
                            "section": section,
                            "occurrence": occurrence_index,
                        }
                    ],
                )
                if len(item) != 1:
                    raise RuntimeError("Append returned unexpected occurrence count")
                item = item[0]
                item_id = item.GetUniqueId()
                if not item_id or item_id in uid_set:
                    raise RuntimeError("Matrix occurrence UID is missing or repeated")
                uid_set.add(item_id)
                placed = item_evidence(item, expected)
                write_json(
                    output
                    / f"matrix-{section_index:02d}-item-{occurrence_index}-placed.json",
                    placed,
                )
                mutate(item, "SetClipEnabled", enabled)
                if item.GetClipEnabled() is not enabled:
                    raise RuntimeError("Matrix occurrence enabled readback differs")
                custom = json.dumps(
                    {"issue": 141, "section": section, "occurrence": occurrence_index},
                    sort_keys=True,
                )
                mutate(
                    item,
                    "AddMarker",
                    0,
                    "Blue",
                    f"141 {section} item {occurrence_index}",
                    "Synthetic matrix occurrence",
                    1,
                    custom,
                )
                after_item = item_evidence(item, expected)
                write_json(
                    output
                    / f"matrix-{section_index:02d}-item-{occurrence_index}-after.json",
                    after_item,
                )
                props = (
                    after_item["GetMediaPoolItem"]
                    .get("GetClipProperty", {})
                    .get("value", {})
                )
                source_bytes = after_item.get("GetMediaPoolItem", {}).get(
                    "sourceBytes", {}
                )
                if (
                    props.get("File Path") != source_paths[filename]
                    or source_bytes.get("sha256") != files[filename]
                    or source_bytes.get("hashMatches") is not True
                    or after_item.get("GetClipEnabled") != {"value": enabled}
                    or after_item.get("GetStart") != {"value": start + offset}
                    or after_item.get("GetDuration")
                    != {"value": (125 if filename == "overlay.png" else duration - 1)}
                    or after_item.get("GetEnd")
                    != {
                        "value": start
                        + offset
                        + (125 if filename == "overlay.png" else duration - 1)
                    }
                ):
                    raise RuntimeError(
                        "Matrix placement/source/enabled readback differs"
                    )
                marker = _marker_at(
                    after_item.get("GetMarkers", {}).get("value", {}), 0
                )
                if marker.get("customData") != custom:
                    raise RuntimeError("Occurrence marker readback differs")
                if after_item.get("GetSourceStartFrame") != {
                    "value": source_start
                } or after_item.get("GetSourceEndFrame") != {
                    "value": (0 if filename == "overlay.png" else duration - 1)
                }:
                    raise RuntimeError("Matrix source bounds differ")
                items.append(item)
                item_count += 1
            mutate(
                matrix,
                "SetClipsLinked",
                [items[0], items[1]],
                True,
                audit_args=[[items[0].GetUniqueId(), items[1].GetUniqueId()], True],
            )
            linked = [
                {other.GetUniqueId() for other in (x.GetLinkedItems() or [])}
                for x in items[:2]
            ]
            if linked != [{items[1].GetUniqueId()}, {items[0].GetUniqueId()}]:
                raise RuntimeError("Matrix A/V link readback differs")
        final_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-postflight",
            environment,
        )
        post_passes = json.loads(Path(final_capture["capturePath"]).read_text()).get(
            "passes", []
        )
        if final_capture["status"] != "equal-adjacent-reads" or len(post_passes) != 2:
            raise RuntimeError("Matrix postflight is incomplete")
        final = post_passes[0]
        if (
            project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != matrix_id
        ):
            raise RuntimeError("Matrix selection changed before postflight review")
        old_final = [
            row
            for row in final.get("timelines", [])
            if row.get("GetUniqueId", {}).get("value") in {BASELINE_ID, R1_ID}
        ]
        matrix_final = [
            row
            for row in final.get("timelines", [])
            if row.get("GetUniqueId", {}).get("value") == matrix_id
        ]
        if (
            len(final.get("timelines", [])) != 3
            or {
                row.get("GetUniqueId", {}).get("value")
                for row in final.get("timelines", [])
            }
            != {BASELINE_ID, R1_ID, matrix_id}
            or len(old_final) != 2
            or len(matrix_final) != 1
            or item_count != 114
            or len(uid_set) != 114
            or not _matrix_old_timelines_match(before, final)
        ):
            raise RuntimeError(
                "Matrix timeline count, old timeline state or UID guard differs"
            )
        final_matrix = matrix_final[0]
        tracks = final_matrix.get("tracks", [])
        if (
            len(tracks) != 6
            or sum(len(track.get("items", [])) for track in tracks) != 114
        ):
            raise RuntimeError("Final matrix track or occurrence counts differ")
        markers = final_matrix.get("GetMarkers", {}).get("value")
        if not isinstance(markers, dict) or len(markers) != 19:
            raise RuntimeError("Final matrix case markers are incomplete")
        marker_rows = list(markers.values())
        if {row.get("name") for row in marker_rows} != {
            f"141 {section}" for section in MATRIX_SECTIONS
        }:
            raise RuntimeError("Final matrix case marker names differ")
        final_ids = {
            item.get("GetUniqueId", {}).get("value")
            for track in tracks
            for item in track.get("items", [])
        }
        if final_ids != uid_set:
            raise RuntimeError("Final matrix occurrence identities differ")
        if final.get("projectId") != identity["projectId"]:
            raise RuntimeError("Matrix project identity changed")
        prior_ids = {
            item.get("GetUniqueId", {}).get("value")
            for row in before_old
            for track in row.get("tracks", [])
            for item in track.get("items", [])
        }
        _validate_matrix_layout(
            final_matrix,
            uid_set,
            source_ids,
            {source_paths[name]: files[name] for name in source_paths},
            prior_ids,
        )
        mutate(resolve.GetProjectManager(), "SaveProject")
        saved_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-saved-postflight",
            environment,
        )
        saved_passes = json.loads(Path(saved_capture["capturePath"]).read_text()).get(
            "passes", []
        )
        if (
            saved_capture["status"] != "equal-adjacent-reads"
            or len(saved_passes) != 2
            or saved_passes != [final, final]
            or project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != matrix_id
        ):
            raise RuntimeError(
                "Saved matrix readback differs from validated postflight"
            )
        write_json(
            output / "matrix-layout.json",
            {
                "timelineId": matrix_id,
                "sections": list(MATRIX_SECTIONS),
                "sectionSpacingFrames": 500,
                "occurrenceCount": item_count,
                "postflight": final_capture,
            },
        )
        return {
            "status": "equal-adjacent-reads",
            "action": "native-matrix",
            "journal": str(journal),
            "captures": [preflight, empty_capture, final_capture],
            "timeline": {"name": MATRIX_NAME, "id": matrix_id},
            "sections": len(MATRIX_SECTIONS),
            "occurrences": item_count,
        }
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        retain("native-matrix", "failure", failure)
        failure_capture = None
        try:
            failure_capture = capture(
                resolve,
                config,
                identity,
                expected,
                output,
                stamp + "-failure-postflight",
                environment,
            )
            retain("native-matrix(failure capture)", "readback", failure_capture)
        except Exception as capture_error:
            retain(
                "native-matrix(failure capture)",
                "failure",
                f"{type(capture_error).__name__}: {capture_error}",
            )
        return {
            "status": "matrix-partial-refused",
            "action": "native-matrix",
            "journal": str(journal),
            "captures": [
                preflight,
                *([] if empty_capture is None else [empty_capture]),
                *([] if final_capture is None else [final_capture]),
                *([] if saved_capture is None else [saved_capture]),
                *([] if failure_capture is None else [failure_capture]),
            ],
            "failure": failure,
            "instruction": (
                "Retain the partial matrix and evidence; do not rerun or clean up."
            ),
        }


def matrix_finalize(resolve, config, identity, expected, output, stamp, environment):
    """Validate the exact completed matrix checkpoint, then only save it."""
    if environment.get("version") != CONTEXT_ENVIRONMENT:
        raise RuntimeError("Resolve build differs from the completed checkpoint")
    for filename, digest in MATRIX_FINALIZE_HASHES.items():
        if sha256(output / filename) != digest:
            raise RuntimeError("Completed matrix evidence changed; refusing")
    checkpoint = json.loads((output / MATRIX_COMPLETE_CAPTURE).read_text())["passes"][0]
    before = json.loads((output / MATRIX_EMPTY_CAPTURE).read_text())["passes"][0]
    baseline = json.loads((output / CONTEXT_BASELINE_CAPTURE).read_text())["passes"][0]
    if checkpoint.get("projectId") != identity.get("projectId"):
        raise RuntimeError("Completed checkpoint project identity differs")
    journal = output / f"matrix-finalize-{stamp}.jsonl"
    journal.open("x").close()

    def retain(method, phase, value):
        with journal.open("a") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    captures = []
    try:
        project = require_current(resolve, config, identity)
        if project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID:
            raise RuntimeError("Completed matrix must remain selected")
        fresh = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-preflight",
            environment,
        )
        captures.append(fresh)
        if fresh["status"] != "equal-adjacent-reads" or json.loads(
            Path(fresh["capturePath"]).read_text()
        )["passes"] != [checkpoint, checkpoint]:
            raise RuntimeError("Fresh matrix observation differs; refusing save")
        if {t["GetUniqueId"]["value"] for t in checkpoint["timelines"]} != {
            BASELINE_ID,
            R1_ID,
            MATRIX_PARTIAL_ID,
        } or len(checkpoint["timelines"]) != 3:
            raise RuntimeError("Completed matrix timeline set differs")
        source_ids = {}
        for track in _pass_timeline(baseline, BASELINE_ID)["tracks"]:
            for item in track["items"]:
                media = item["GetMediaPoolItem"]
                name = Path(media["GetClipProperty"]["value"]["File Path"]).name
                source_ids[name] = media["GetUniqueId"]["value"]
        matrix = _pass_timeline(checkpoint, MATRIX_PARTIAL_ID)
        ids = {i["GetUniqueId"]["value"] for t in matrix["tracks"] for i in t["items"]}
        prior_ids = {
            i["GetUniqueId"]["value"]
            for timeline in before["timelines"]
            if timeline["GetUniqueId"]["value"] in {BASELINE_ID, R1_ID}
            for track in timeline["tracks"]
            for i in track["items"]
        }

        sources = {
            str(Path(config["mediaDir"]) / row[0]): expected[
                str(Path(config["mediaDir"]) / row[0])
            ]
            for row in MATRIX_RECIPE
        }
        if len(ids) != 114 or not _matrix_old_timelines_match(before, checkpoint):
            raise RuntimeError("Completed matrix count or preserved timelines differ")
        _validate_matrix_layout(matrix, ids, source_ids, sources, prior_ids)
        project = require_current(resolve, config, identity)
        if project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID:
            raise RuntimeError("Matrix selection changed before save")
        retain("SaveProject", "request", [])
        saved = resolve.GetProjectManager().SaveProject()
        retain("SaveProject", "return", saved)
        if saved is not True:
            raise RuntimeError("SaveProject refused the validated matrix")
        after = capture(
            resolve, config, identity, expected, output, stamp + "-saved", environment
        )
        captures.append(after)
        if after["status"] != "equal-adjacent-reads" or json.loads(
            Path(after["capturePath"]).read_text()
        )["passes"] != [checkpoint, checkpoint]:
            raise RuntimeError("Saved matrix observation differs")
        selected = require_current(resolve, config, identity).GetCurrentTimeline()
        if selected is None or selected.GetUniqueId() != MATRIX_PARTIAL_ID:
            raise RuntimeError("Matrix selection changed after save")
        write_json(
            output / "matrix-layout.json",
            {
                "timelineId": MATRIX_PARTIAL_ID,
                "sections": list(MATRIX_SECTIONS),
                "sectionSpacingFrames": 500,
                "occurrenceCount": 114,
                "postflight": after,
                "audioTrackFormats": ["stereo", "mono", "mono"],
            },
        )
        return {
            "status": "equal-adjacent-reads",
            "action": "matrix-finalize",
            "journal": str(journal),
            "captures": captures,
            "timelineId": MATRIX_PARTIAL_ID,
            "sections": 19,
            "occurrences": 114,
        }
    except Exception as error:
        detail = f"{type(error).__name__}: {error}"
        retain("matrix-finalize", "failure", detail)
        try:
            failure = capture(
                resolve,
                config,
                identity,
                expected,
                output,
                stamp + "-failure",
                environment,
            )
            captures.append(failure)
        except Exception as capture_error:
            retain(
                "matrix-finalize(failure capture)",
                "failure",
                f"{type(capture_error).__name__}: {capture_error}",
            )
        return {
            "status": "matrix-finalize-refused",
            "action": "matrix-finalize",
            "failure": detail,
            "journal": str(journal),
            "captures": captures,
            "instruction": "Retain evidence; do not rerun or alter the matrix.",
        }


def matrix_reopen(resolve, config, identity, expected, output, stamp, environment):
    """Save, close, and safely reopen the pinned completed matrix project."""
    if config.get("action") != "matrix-reopen":
        raise ValueError("Unknown matrix reopen action")
    if environment.get("version") != CONTEXT_ENVIRONMENT:
        raise RuntimeError("Resolve build differs from the saved matrix capture")
    prepared = json.loads((output / "prepared.json").read_text(encoding="utf-8"))
    prepared_identity = prepared.get("identity")
    if (
        not isinstance(prepared_identity, dict)
        or prepared_identity.get("projectId") != identity.get("projectId")
        or prepared_identity.get("projectName") != identity.get("projectName")
        or prepared_identity.get("baselineTimelineId") != BASELINE_ID
        or prepared.get("manifestSha256") != config.get("manifestSha256")
        or prepared.get("environment", {}).get("version") != CONTEXT_ENVIRONMENT
    ):
        raise RuntimeError("Prepared project identity or build differs; refusing")
    identity = prepared_identity
    if (
        not isinstance(identity.get("projectId"), str)
        or not identity["projectId"]
        or identity.get("baselineTimelineId") != BASELINE_ID
    ):
        raise RuntimeError("Prepared project identity differs; refusing")
    pinned_path = output / PICTURE_CAPTURE
    if sha256(pinned_path) != PICTURE_CAPTURE_SHA256:
        raise RuntimeError("Pinned saved matrix capture changed or is missing")
    pinned_capture = json.loads(pinned_path.read_text(encoding="utf-8"))
    pinned_passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(pinned_passes) != 2
        or pinned_passes[0] != pinned_passes[1]
        or any(errors(value) for value in pinned_passes)
        or pinned_passes[0].get("projectId") != identity.get("projectId")
        or len(pinned_passes[0].get("timelines", [])) != 3
        or {
            row.get("GetUniqueId", {}).get("value")
            for row in pinned_passes[0].get("timelines", [])
        }
        != {BASELINE_ID, R1_ID, MATRIX_PARTIAL_ID}
    ):
        raise RuntimeError("Pinned saved matrix capture is incomplete")
    pinned = pinned_passes[0]

    journal = output / f"matrix-reopen-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    def handoff_snapshot(manager):
        candidate = manager.GetCurrentProject()
        if candidate is None:
            return None
        uid = candidate.GetUniqueId()
        name = candidate.GetName()
        count = candidate.GetTimelineCount()
        if (
            not isinstance(uid, str)
            or not uid
            or not isinstance(name, str)
            or not name
            or type(count) is not int
            or count != 0
        ):
            raise RuntimeError("Automatic handoff project is unreadable or populated")
        pool = candidate.GetMediaPool()
        root = pool.GetRootFolder()
        clips = root.GetClipList()
        folders = root.GetSubFolderList()
        if not isinstance(clips, (list, tuple)) or not isinstance(
            folders, (list, tuple)
        ):
            raise RuntimeError("Automatic handoff root contents are unreadable")
        result = {
            "projectId": uid,
            "projectName": name,
            "timelineCount": count,
            "rootClipCount": len(clips),
            "rootSubfolderCount": len(folders),
        }
        if result["rootClipCount"] or result["rootSubfolderCount"]:
            raise RuntimeError("Automatic handoff project is populated")
        if uid == identity["projectId"]:
            raise RuntimeError("Automatic handoff is the approved project")
        return result

    manager = resolve.GetProjectManager()
    captures = []
    stage = "preflight"
    try:
        project = require_current(resolve, config, identity)
        if (
            project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            raise RuntimeError("Completed matrix must be current before save")
        fresh = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-preflight",
            environment,
        )
        captures.append(fresh)
        fresh_passes = json.loads(
            Path(fresh["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if fresh.get("status") != "equal-adjacent-reads" or fresh_passes != [
            pinned,
            pinned,
        ]:
            raise RuntimeError("Fresh matrix state differs from the pinned save")
        project = require_current(resolve, config, identity)
        if (
            project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            raise RuntimeError("Matrix context changed immediately before save")
        retain("SaveProject", "request", [])
        try:
            saved = manager.SaveProject()
            if saved is not True:
                raise RuntimeError("SaveProject refused the approved project")
            retain("SaveProject", "return", saved)
        except Exception as error:
            retain("SaveProject", "failure", f"{type(error).__name__}: {error}")
            raise

        stage = "pre-close"
        project = require_current(resolve, config, identity)
        if (
            project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            raise RuntimeError("Completed matrix selection changed before close")
        close_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-pre-close",
            environment,
        )
        captures.append(close_capture)
        close_passes = json.loads(
            Path(close_capture["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if close_capture.get("status") != "equal-adjacent-reads" or close_passes != [
            pinned,
            pinned,
        ]:
            raise RuntimeError("Matrix state changed before close")
        project = require_current(resolve, config, identity)
        if (
            project.GetCurrentTimeline() is None
            or project.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            raise RuntimeError("Matrix context changed immediately before close")
        retain("CloseProject", "request", [identity["projectId"]])
        try:
            closed = manager.CloseProject(project)
            if closed is not True:
                raise RuntimeError("CloseProject refused the approved project")
            retain("CloseProject", "return", closed)
        except Exception as error:
            retain("CloseProject", "failure", f"{type(error).__name__}: {error}")
            raise

        stage = "handoff"
        handoff = handoff_snapshot(manager)
        retain("automatic handoff", "readback", handoff)
        repeated_handoff = handoff_snapshot(manager)
        retain("automatic handoff recheck", "readback", repeated_handoff)
        if repeated_handoff != handoff:
            raise RuntimeError("Automatic handoff changed before load")

        stage = "load"
        retain("LoadProject", "request", [config["projectName"]])
        try:
            loaded = manager.LoadProject(config["projectName"])
            if loaded is None:
                raise RuntimeError("LoadProject did not return the approved project")
        except Exception as error:
            retain("LoadProject", "failure", f"{type(error).__name__}: {error}")
            raise
        loaded_identity = {
            "projectId": loaded.GetUniqueId(),
            "projectName": loaded.GetName(),
        }
        current = manager.GetCurrentProject()
        current_identity = (
            None
            if current is None
            else {"projectId": current.GetUniqueId(), "projectName": current.GetName()}
        )
        retain(
            "LoadProject(identity readback)",
            "readback",
            {"returned": loaded_identity, "current": current_identity},
        )
        approved = {
            "projectId": identity["projectId"],
            "projectName": config["projectName"],
        }
        if loaded_identity != approved or current_identity != approved:
            raise RuntimeError("Loaded/current project identity differs")

        stage = "reopened-capture"
        if current.GetTimelineCount() != 3:
            raise RuntimeError("Reopened project timeline count differs")
        found = {}
        for index in range(1, current.GetTimelineCount() + 1):
            item = current.GetTimelineByIndex(index)
            if item is None:
                raise RuntimeError("Reopened project timeline is unreadable")
            found[item.GetUniqueId()] = item.GetName()
        expected_timelines = {
            BASELINE_ID: TIMELINE,
            R1_ID: "VERA 141 R1 identity",
            MATRIX_PARTIAL_ID: MATRIX_NAME,
        }
        if found != expected_timelines:
            raise RuntimeError("Reopened project timeline identities differ")
        if (
            current.GetCurrentTimeline() is None
            or current.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            retain("SetCurrentTimeline", "request", [MATRIX_PARTIAL_ID])
            target = next(
                current.GetTimelineByIndex(index)
                for index in range(1, current.GetTimelineCount() + 1)
                if current.GetTimelineByIndex(index).GetUniqueId() == MATRIX_PARTIAL_ID
            )
            require_current(resolve, config, identity)
            if current.SetCurrentTimeline(target) is not True:
                raise RuntimeError("SetCurrentTimeline refused the pinned matrix")
            if current.GetCurrentTimeline().GetUniqueId() != MATRIX_PARTIAL_ID:
                raise RuntimeError("Selected matrix identity differs after reopen")
            retain("SetCurrentTimeline", "return", True)
        reopened = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-reopened",
            environment,
        )
        captures.append(reopened)
        reopened_capture = json.loads(
            Path(reopened["capturePath"]).read_text(encoding="utf-8")
        )
        reopened_passes = reopened_capture.get("passes", [])
        if (
            reopened.get("status") != "equal-adjacent-reads"
            or len(reopened_passes) != 2
            or reopened_passes[0] != reopened_passes[1]
            or any(errors(value) for value in reopened_passes)
        ):
            raise RuntimeError("Reopened raw capture is incomplete or unstable")
        raw_comparison = (
            "exact-match" if reopened_passes[0] == pinned else "differences-retained"
        )
        retain("reopened capture comparison", "readback", raw_comparison)
        write_json(
            output / f"matrix-reopen-{stamp}.json",
            {
                "kind": "pinned-matrix-reopen-observation",
                "project": approved,
                "build": environment["version"],
                "handoff": handoff,
                "rawComparison": raw_comparison,
                "captures": captures,
                "limits": [
                    "Reopen capture differences are retained without repair or "
                    "inference."
                ],
            },
        )
        return {
            "status": "equal-adjacent-reads",
            "action": "matrix-reopen",
            "journal": str(journal),
            "evidence": str(output / f"matrix-reopen-{stamp}.json"),
            "captures": captures,
            "rawComparison": raw_comparison,
        }
    except Exception as error:
        detail = f"{type(error).__name__}: {error}"
        retain("matrix-reopen", "failure", {"stage": stage, "error": detail})
        write_json(
            output / f"matrix-reopen-{stamp}.json",
            {
                "kind": "pinned-matrix-reopen-observation",
                "project": {
                    "projectId": identity.get("projectId"),
                    "projectName": config.get("projectName"),
                },
                "build": environment.get("version"),
                "stage": stage,
                "captures": captures,
                "failure": detail,
                "instruction": "Retain evidence; do not retry or alter either project.",
            },
        )
        return {
            "status": "matrix-reopen-refused",
            "action": "matrix-reopen",
            "journal": str(journal),
            "evidence": str(output / f"matrix-reopen-{stamp}.json"),
            "captures": captures,
            "failure": detail,
        }


def picture_calibration(
    resolve, config, identity, expected, output, stamp, environment
):
    """Export four fixed PNG candidates from the unedited calibration section."""
    if config.get("action") != "picture-calibration":
        raise ValueError("Unknown picture calibration action")
    if environment.get("version") != CONTEXT_ENVIRONMENT:
        raise RuntimeError("Resolve build differs from the pinned matrix capture")
    pinned_path = output / PICTURE_CAPTURE
    if sha256(pinned_path) != PICTURE_CAPTURE_SHA256:
        raise RuntimeError("Pinned saved matrix capture changed or is missing")
    pinned_capture = json.loads(pinned_path.read_text(encoding="utf-8"))
    pinned_passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(pinned_passes) != 2
        or pinned_passes[0] != pinned_passes[1]
        or any(errors(value) for value in pinned_passes)
        or pinned_passes[0].get("projectId") != identity.get("projectId")
        or len(pinned_passes[0].get("timelines", [])) != 3
        or _pass_timeline(pinned_passes[0], MATRIX_PARTIAL_ID) is None
    ):
        raise RuntimeError("Pinned saved matrix capture is incomplete")
    pinned = pinned_passes[0]

    journal = output / f"picture-calibration-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    project = None
    timeline = None
    initial_timecode = None
    initial_page = None
    output_dir = None
    captures = []
    exports = []

    def guard():
        current_project = require_current(resolve, config, identity)
        if current_project.GetUniqueId() != identity.get("projectId"):
            raise RuntimeError("Project identity changed during still calibration")
        current_timeline = current_project.GetCurrentTimeline()
        if (
            current_timeline is None
            or current_timeline.GetUniqueId() != MATRIX_PARTIAL_ID
        ):
            raise RuntimeError("Pinned matrix is no longer selected")
        return current_project, current_timeline

    def audited_call(target, method, args=()):
        guard()
        retain(method, "request", list(args))
        try:
            value = getattr(target, method)(*args)
            if value is None or value is False:
                raise RuntimeError(f"{method} refused operation")
            json.dumps(value, allow_nan=False)
            retain(method, "return", value)
            return value
        except Exception as error:
            retain(method, "failure", f"{type(error).__name__}: {error}")
            raise

    failure = None
    try:
        project, timeline = guard()
        selected_capture = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-preflight",
            environment,
        )
        captures.append(selected_capture)
        selected_passes = json.loads(
            Path(selected_capture["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if (
            selected_capture.get("status") != "equal-adjacent-reads"
            or len(selected_passes) != 2
            or any(errors(value) for value in selected_passes)
            or selected_passes != [pinned, pinned]
        ):
            retain(
                "preflight",
                "failure",
                "Current matrix differs from pinned saved capture",
            )
            failure = (
                "RuntimeError: Current two-pass content differs from pinned "
                "saved matrix"
            )
            write_json(
                output / f"picture-calibration-{stamp}.json",
                {
                    "kind": "candidate-still-export-calibration-not-compositing-proof",
                    "frames": list(PICTURE_FRAMES),
                    "initialTimecode": None,
                    "initialPage": None,
                    "restored": False,
                    "outputDirectory": None,
                    "exports": [],
                    "captures": captures,
                    "failure": failure,
                    "limits": [
                        "PNG bytes do not establish which timeline sample Resolve "
                        "exported.",
                        "Candidate stills do not prove compositing or general still "
                        "export behavior.",
                    ],
                },
            )
            return {
                "status": "picture-preflight-refused",
                "action": "picture-calibration",
                "journal": str(journal),
                "evidence": str(output / f"picture-calibration-{stamp}.json"),
                "captures": captures,
                "failure": failure,
            }
        project, timeline = guard()
        initial_timecode = audited_call(timeline, "GetCurrentTimecode")
        if not isinstance(initial_timecode, str) or not initial_timecode:
            raise RuntimeError("Initial timeline timecode is unreadable")
        initial_page = audited_call(resolve, "GetCurrentPage")
        if not isinstance(initial_page, str) or not initial_page:
            raise RuntimeError("Current Resolve page is unreadable")
        before = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-content-before",
            environment,
        )
        captures.append(before)
        before_passes = json.loads(
            Path(before["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if before.get("status") != "equal-adjacent-reads" or before_passes != [
            pinned,
            pinned,
        ]:
            raise RuntimeError("Content changed before still export")

        output_dir = output / f"picture-calibration-{stamp}"
        output_dir.mkdir(exist_ok=False)
        for frame in PICTURE_FRAMES:
            project, timeline = guard()
            hours, remainder = divmod(frame, 25 * 60 * 60)
            minutes, remainder = divmod(remainder, 25 * 60)
            seconds, frames = divmod(remainder, 25)
            timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
            audited_call(timeline, "SetCurrentTimecode", (timecode,))
            current_timecode = audited_call(timeline, "GetCurrentTimecode")
            current_page = audited_call(resolve, "GetCurrentPage")
            if current_timecode != timecode or current_page != initial_page:
                raise RuntimeError(
                    "Requested timecode or Resolve page readback differs"
                )
            destination = output_dir / f"frame-{frame:03d}.png"
            audited_call(project, "ExportCurrentFrameAsStill", (str(destination),))
            project, timeline = guard()
            after_timecode = audited_call(timeline, "GetCurrentTimecode")
            after_page = audited_call(resolve, "GetCurrentPage")
            if after_timecode != timecode or after_page != initial_page:
                raise RuntimeError("Timecode or page changed during still export")
            if destination.is_symlink() or not destination.is_file():
                raise RuntimeError("Export did not create a regular PNG file")
            size = destination.stat().st_size
            digest = sha256(destination)
            with destination.open("rb") as stream:
                header = stream.read(8)
            evidence = {
                "frame": frame,
                "timecode": timecode,
                "path": str(destination),
                "exists": True,
                "size": size,
                "sha256": digest,
                "pngHeaderHex": header.hex(),
                "pngHeaderMatches": header == b"\x89PNG\r\n\x1a\n",
                "resolvePage": after_page,
            }
            retain("ExportCurrentFrameAsStill(output)", "readback", evidence)
            if size <= 8 or not evidence["pngHeaderMatches"]:
                raise RuntimeError("Export output is empty or lacks a PNG header")
            exports.append(evidence)

    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        retain("picture-calibration", "failure", failure)

    restored = False
    if initial_timecode is not None:
        try:
            project, timeline = guard()
            audited_call(timeline, "SetCurrentTimecode", (initial_timecode,))
            restored_timecode = audited_call(timeline, "GetCurrentTimecode")
            restored_page = audited_call(resolve, "GetCurrentPage")
            restored = (
                restored_timecode == initial_timecode and restored_page == initial_page
            )
            retain(
                "timecode restoration",
                "readback",
                {
                    "timecode": restored_timecode,
                    "page": restored_page,
                    "matchesInitial": restored,
                },
            )
            if not restored and failure is None:
                failure = "RuntimeError: Initial timecode/page restoration differs"
        except Exception as error:
            retain(
                "timecode restoration",
                "failure",
                f"{type(error).__name__}: {error}",
            )
            if failure is None:
                failure = f"{type(error).__name__}: {error}"

    try:
        post = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-content-after",
            environment,
        )
        captures.append(post)
        post_passes = json.loads(
            Path(post["capturePath"]).read_text(encoding="utf-8")
        ).get("passes", [])
        if (
            post.get("status") != "equal-adjacent-reads"
            or post_passes != [pinned, pinned]
        ) and failure is None:
            failure = "RuntimeError: Post-export matrix content differs"
    except Exception as error:
        retain(
            "post-export content capture", "failure", f"{type(error).__name__}: {error}"
        )
        if failure is None:
            failure = f"{type(error).__name__}: {error}"

    write_json(
        output / f"picture-calibration-{stamp}.json",
        {
            "kind": "candidate-still-export-calibration-not-compositing-proof",
            "frames": list(PICTURE_FRAMES),
            "initialTimecode": initial_timecode,
            "initialPage": initial_page,
            "restored": restored,
            "outputDirectory": None if output_dir is None else str(output_dir),
            "exports": exports,
            "captures": captures,
            "failure": failure,
            "limits": [
                "PNG bytes do not establish which timeline sample Resolve exported.",
                "Candidate stills do not prove compositing or general still export "
                "behavior.",
            ],
        },
    )
    return {
        "status": "candidate-exports-retained"
        if failure is None
        else "picture-calibration-refused",
        "action": "picture-calibration",
        "journal": str(journal),
        "evidence": str(output / f"picture-calibration-{stamp}.json"),
        "outputDirectory": None if output_dir is None else str(output_dir),
        "captures": captures,
        "exports": exports,
        "failure": failure,
        "compositing": "not established",
    }


def picture_cases(resolve, config, identity, expected, output, stamp, environment):
    """Exercise only the pinned opaque, transparent, and opacity cases."""
    if config.get("action") != "picture-cases":
        raise ValueError("Unknown picture cases action")
    if environment.get("version") != CONTEXT_ENVIRONMENT:
        raise RuntimeError("Resolve build differs from the pinned matrix capture")
    pinned_path = output / PICTURE_CAPTURE
    if sha256(pinned_path) != PICTURE_CAPTURE_SHA256:
        raise RuntimeError("Pinned saved matrix capture changed or is missing")
    pinned_capture = json.loads(pinned_path.read_text(encoding="utf-8"))
    pinned_passes = pinned_capture.get("passes", [])
    if (
        pinned_capture.get("consistency") != "equal-adjacent-reads"
        or len(pinned_passes) != 2
        or pinned_passes[0] != pinned_passes[1]
        or any(errors(value) for value in pinned_passes)
        or pinned_passes[0].get("projectId") != identity.get("projectId")
    ):
        raise RuntimeError("Pinned saved matrix capture is incomplete")
    pinned = pinned_passes[0]
    pinned_timeline = _pass_timeline(pinned, MATRIX_PARTIAL_ID)
    if len(pinned_timeline.get("tracks", [])) != 6:
        raise RuntimeError("Pinned matrix track layout differs")
    pinned_items = {
        item["GetUniqueId"]["value"]: item
        for track in pinned_timeline["tracks"]
        for item in track["items"]
    }
    for name, spec in PICTURE_CASES.items():
        item = pinned_items.get(spec["uid"])
        if (
            item is None
            or item.get("GetStart") != {"value": spec["start"]}
            or item.get("GetEnd") != {"value": spec["end"]}
            or item.get("GetDuration") != {"value": spec["duration"]}
            or item.get("GetSourceStartFrame") != {"value": 0}
            or item.get("GetSourceEndFrame") != {"value": spec["sourceEnd"]}
            or item.get("GetTrackTypeAndIndex") != {"value": ["video", spec["track"]]}
            or item.get("GetType") != {"value": "video"}
            or item.get("GetClipEnabled") != {"value": False}
            or item.get("GetMarkers") != {"value": spec["marker"]}
            or item.get("GetProperties", {}).get("value", {}).get("Opacity") != 100.0
        ):
            raise RuntimeError(f"Pinned {name} target layout or state differs")
        media = item.get("GetMediaPoolItem", {})
        props = media.get("GetClipProperty", {}).get("value", {})
        if (
            media.get("GetUniqueId") != {"value": spec["mediaUid"]}
            or props.get("File Name") != spec["filename"]
            or Path(props.get("File Path", "")).name != spec["filename"]
        ):
            raise RuntimeError(f"Pinned {name} source identity differs")

    journal = output / f"picture-cases-{stamp}.jsonl"
    journal.open("x", encoding="utf-8").close()

    def retain(method, phase, value):
        with journal.open("a", encoding="utf-8") as stream:
            json.dump(
                {
                    "at": datetime.now(UTC).isoformat(),
                    "method": method,
                    "phase": phase,
                    "value": value,
                },
                stream,
                sort_keys=True,
            )
            stream.write("\n")

    captures = []
    exports = []
    failure = None
    output_dir = None
    initial_timecode = None
    initial_page = None
    states = {name: {"enabled": False, "opacity": 100.0} for name in PICTURE_CASES}
    possibly_changed = set()
    expected_pass = deepcopy(pinned)

    def context():
        project = require_current(resolve, config, identity)
        timeline = project.GetCurrentTimeline()
        if timeline is None or timeline.GetUniqueId() != MATRIX_PARTIAL_ID:
            raise RuntimeError("Pinned matrix is no longer selected")
        return project, timeline

    def target_object(name, *, mutable=True):
        project, timeline = context()
        spec = PICTURE_CASES[name]
        items = timeline.GetItemListInTrack("video", spec["track"])
        matches = [item for item in (items or []) if item.GetUniqueId() == spec["uid"]]
        if len(matches) != 1:
            raise RuntimeError(f"Exact {name} occurrence is not uniquely present")
        item = matches[0]
        media = item.GetMediaPoolItem()
        locator = media.GetClipProperty().get("File Path")
        if (
            media.GetUniqueId() != spec["mediaUid"]
            or not isinstance(locator, str)
            or Path(locator).name != spec["filename"]
            or expected.get(locator) != spec["sha256"]
            or sha256(locator) != spec["sha256"]
            or item.GetStart() != spec["start"]
            or item.GetEnd() != spec["end"]
            or item.GetDuration() != spec["duration"]
            or item.GetSourceStartFrame() != 0
            or item.GetSourceEndFrame() != spec["sourceEnd"]
            or item.GetTrackTypeAndIndex() != ["video", spec["track"]]
            or item.GetType() != "video"
            or len(item.GetMarkers()) != 1
            or _marker_at(item.GetMarkers(), 0) != _marker_at(spec["marker"], 0)
        ):
            raise RuntimeError(f"Exact {name} target identity changed")
        properties = item.GetProperties()
        baseline_properties = pinned_items[spec["uid"]]["GetProperties"]["value"]
        if (
            not isinstance(properties, dict)
            or {**properties, "Opacity": baseline_properties["Opacity"]}
            != baseline_properties
        ):
            raise RuntimeError(f"Unexpected {name} target properties")
        if mutable and (
            item.GetClipEnabled() is not states[name]["enabled"]
            or properties.get("Opacity") != states[name]["opacity"]
        ):
            raise RuntimeError(f"Unexpected {name} mutable state")
        return project, timeline, item

    def capture_state(label):
        result = capture(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp + "-" + label,
            environment,
        )
        captures.append(result)
        passes = json.loads(Path(result["capturePath"]).read_text(encoding="utf-8"))
        if (
            result.get("status") != "equal-adjacent-reads"
            or passes.get("consistency") != "equal-adjacent-reads"
            or passes.get("passes") != [expected_pass, expected_pass]
            or any(errors(value) for value in passes.get("passes", []))
        ):
            raise RuntimeError(f"{label} content differs from its exact expected state")
        return result

    def audited(target_name, method, args=(), *, mutable=True):
        # Re-resolve project/timeline and the exact target before every native call.
        project, timeline = context()
        if target_name is None:
            current = (
                timeline
                if method in {"SetCurrentTimecode", "GetCurrentTimecode"}
                else resolve
            )
        else:
            project, _timeline, item = target_object(target_name, mutable=mutable)
            current = project if method == "ExportCurrentFrameAsStill" else item
        retain(method, "request", list(args))
        try:
            value = getattr(current, method)(*args)
            if value is None or value is False:
                raise RuntimeError(f"{method} refused operation")
            json.dumps(value, allow_nan=False)
            retain(method, "return", value)
            return value
        except Exception as error:
            retain(method, "failure", f"{type(error).__name__}: {error}")
            raise

    def change(name, *, enabled=None, opacity=None, label):
        capture_state(label + "-before")
        _project, _timeline, item = target_object(name)
        spec = PICTURE_CASES[name]
        if enabled is not None and states[name]["enabled"] != enabled:
            possibly_changed.add(name)
            audited(name, "SetClipEnabled", (enabled,))
            _project, _timeline, item = target_object(name, mutable=False)
            if item.GetClipEnabled() is not enabled:
                raise RuntimeError(f"{name} enabled readback differs")
            states[name]["enabled"] = enabled
            target = next(
                entry
                for entry in expected_pass["timelines"]
                if entry["GetUniqueId"]["value"] == MATRIX_PARTIAL_ID
            )
            next(
                item_capture
                for track in target["tracks"]
                for item_capture in track["items"]
                if item_capture["GetUniqueId"]["value"] == spec["uid"]
            )["GetClipEnabled"]["value"] = enabled
            if item.GetProperties().get("Opacity") != states[name]["opacity"]:
                raise RuntimeError(f"{name} opacity changed with enable state")
            capture_state(label + "-after-enabled")
        if opacity is not None and states[name]["opacity"] != opacity:
            _project, _timeline, item = target_object(name)
            possibly_changed.add(name)
            audited(name, "SetProperties", ({"Opacity": opacity},))
            _project, _timeline, item = target_object(name, mutable=False)
            if item.GetProperties().get("Opacity") != opacity:
                raise RuntimeError(f"{name} opacity readback differs")
            states[name]["opacity"] = opacity
            target = next(
                entry
                for entry in expected_pass["timelines"]
                if entry["GetUniqueId"]["value"] == MATRIX_PARTIAL_ID
            )
            target_item = next(
                item_capture
                for track in target["tracks"]
                for item_capture in track["items"]
                if item_capture["GetUniqueId"]["value"] == spec["uid"]
            )
            target_item["GetProperties"]["value"]["Opacity"] = opacity
            capture_state(label + "-after-opacity")
        if enabled is None and opacity is None:
            raise RuntimeError("Empty picture case transition")

    failure_state = None
    try:
        context()
        for name in PICTURE_CASES:
            target_object(name)
        capture_state("preflight")
        initial_timecode = audited(None, "GetCurrentTimecode")
        if not isinstance(initial_timecode, str) or not initial_timecode:
            raise RuntimeError("Initial timeline timecode is unreadable")
        initial_page = audited(None, "GetCurrentPage")
        if not isinstance(initial_page, str) or not initial_page:
            raise RuntimeError("Current Resolve page is unreadable")
        output_dir = output / f"picture-cases-{stamp}"
        output_dir.mkdir(exist_ok=False)

        def export(name, local_frame, label):
            spec = PICTURE_CASES[name]
            absolute_frame = spec["sectionStart"] + local_frame
            hours, remainder = divmod(absolute_frame, 25 * 60 * 60)
            minutes, remainder = divmod(remainder, 25 * 60)
            seconds, frames = divmod(remainder, 25)
            timecode = f"{hours:02d}:{minutes:02d}:{seconds:02d}:{frames:02d}"
            _project, timeline, _item = target_object(name)
            page_before = audited(None, "GetCurrentPage")
            if page_before != initial_page:
                raise RuntimeError("Resolve page changed before still sample")
            audited(None, "SetCurrentTimecode", (timecode,))
            _project, timeline, _item = target_object(name)
            current_timecode = timeline.GetCurrentTimecode()
            current_page = resolve.GetCurrentPage()
            retain(
                "playhead/page readback",
                "return",
                {
                    "timecode": current_timecode,
                    "page": current_page,
                },
            )
            if current_timecode != timecode or current_page != initial_page:
                raise RuntimeError("Requested timecode or Resolve page differs")
            destination = output_dir / f"{label}-local-{local_frame:03d}.png"
            audited(name, "ExportCurrentFrameAsStill", (str(destination),))
            _project, timeline, _item = target_object(name)
            after_timecode = timeline.GetCurrentTimecode()
            after_page = resolve.GetCurrentPage()
            if after_timecode != timecode or after_page != initial_page:
                raise RuntimeError("Timecode or page changed during still export")
            if destination.is_symlink() or not destination.is_file():
                raise RuntimeError("Export did not create a regular PNG file")
            with destination.open("rb") as stream:
                header = stream.read(8)
            record = {
                "case": name,
                "localFrame": local_frame,
                "timelineFrame": absolute_frame,
                "timecode": timecode,
                "path": str(destination),
                "size": destination.stat().st_size,
                "sha256": sha256(destination),
                "pngHeaderHex": header.hex(),
                "pngHeaderMatches": header == b"\x89PNG\r\n\x1a\n",
                "resolvePage": after_page,
            }
            retain("ExportCurrentFrameAsStill(output)", "readback", record)
            if record["size"] <= 8 or not record["pngHeaderMatches"]:
                raise RuntimeError("Export output is empty or lacks a PNG header")
            exports.append(record)

        change("opaque", enabled=True, label="opaque-enable")
        for frame in PICTURE_CASES["opaque"]["frames"]:
            export("opaque", frame, "opaque-enabled")
        change("opaque", enabled=False, label="opaque-disable")
        export("opaque", PICTURE_CASES["opaque"]["disableFrame"], "opaque-disabled")

        change("transparent", enabled=True, label="transparent-enable")
        for frame in PICTURE_CASES["transparent"]["frames"]:
            export("transparent", frame, "transparent-enabled")
        change("transparent", enabled=False, label="transparent-disable")
        export(
            "transparent",
            PICTURE_CASES["transparent"]["disableFrame"],
            "transparent-disabled",
        )

        change("effect", enabled=True, label="effect-enable")
        change("effect", opacity=25.0, label="effect-opacity-25")
        export("effect", 75, "effect-opacity-25")
        export("effect", 100, "effect-opacity-25")
        change("effect", opacity=100.0, label="effect-opacity-restore")
        change("effect", enabled=False, label="effect-disable")
    except Exception as error:
        failure = f"{type(error).__name__}: {error}"
        failure_state = deepcopy(states)
        retain("picture-cases", "failure", failure)

    # Restore every touched target and playhead only while identities remain exact.
    if possibly_changed:
        for name in reversed(tuple(PICTURE_CASES)):
            if name not in possibly_changed:
                continue
            try:
                _project, _timeline, item = target_object(name, mutable=False)
                if item.GetClipEnabled() is not False:
                    audited(name, "SetClipEnabled", (False,), mutable=False)
                _project, _timeline, item = target_object(name, mutable=False)
                if item.GetProperties().get("Opacity") != 100.0:
                    audited(name, "SetProperties", ({"Opacity": 100.0},), mutable=False)
                states[name] = {"enabled": False, "opacity": 100.0}
                target = next(
                    entry
                    for entry in expected_pass["timelines"]
                    if entry["GetUniqueId"]["value"] == MATRIX_PARTIAL_ID
                )
                target_item = next(
                    item_capture
                    for track in target["tracks"]
                    for item_capture in track["items"]
                    if item_capture["GetUniqueId"]["value"]
                    == PICTURE_CASES[name]["uid"]
                )
                target_item["GetClipEnabled"]["value"] = False
                target_item["GetProperties"]["value"]["Opacity"] = 100.0
                capture_state(f"restore-{name}")
            except Exception as error:
                retain(
                    "target restoration",
                    "failure",
                    {
                        "target": name,
                        "error": f"{type(error).__name__}: {error}",
                    },
                )
                if failure is None:
                    failure = f"{type(error).__name__}: {error}"

    if initial_timecode is not None:
        try:
            _project, timeline = context()
            retain("SetCurrentTimecode", "request", [initial_timecode])
            restored = timeline.SetCurrentTimecode(initial_timecode)
            retain("SetCurrentTimecode", "return", restored)
            if restored is None or restored is False:
                raise RuntimeError("Timecode restoration refused")
            timecode = timeline.GetCurrentTimecode()
            page = resolve.GetCurrentPage()
            if timecode != initial_timecode or page != initial_page:
                raise RuntimeError("Initial timecode/page restoration differs")
            retain(
                "timecode restoration",
                "readback",
                {
                    "timecode": timecode,
                    "page": page,
                    "matchesInitial": True,
                },
            )
        except Exception as error:
            retain(
                "timecode restoration",
                "failure",
                f"{type(error).__name__}: {error}",
            )
            if failure is None:
                failure = f"{type(error).__name__}: {error}"

    try:
        if expected_pass != pinned:
            raise RuntimeError("Final expected content state is not the pinned matrix")
        capture_state("final")
    except Exception as error:
        retain("final content capture", "failure", f"{type(error).__name__}: {error}")
        if failure is None:
            failure = f"{type(error).__name__}: {error}"

    evidence = output / f"picture-cases-{stamp}.json"
    write_json(
        evidence,
        {
            "kind": "bounded-picture-case-stills-not-compositing-proof",
            "cases": {
                name: {key: value for key, value in spec.items() if key != "marker"}
                for name, spec in PICTURE_CASES.items()
            },
            "captures": captures,
            "exports": exports,
            "outputDirectory": None if output_dir is None else str(output_dir),
            "initialTimecode": initial_timecode,
            "initialPage": initial_page,
            "finalContentMatchesPinned": failure is None,
            "failure": failure,
            "failureState": failure_state,
            "limits": [
                "PNG bytes do not establish which timeline sample Resolve exported.",
                "Opacity 25 tests the named Inspector property only, not arbitrary "
                "OFX effects.",
                "Actual PNG appearance requires separate host inspection.",
            ],
        },
    )
    return {
        "status": (
            "candidate-case-exports-retained"
            if failure is None
            else "picture-cases-refused"
        ),
        "action": "picture-cases",
        "journal": str(journal),
        "evidence": str(evidence),
        "outputDirectory": None if output_dir is None else str(output_dir),
        "captures": captures,
        "exports": exports,
        "failure": failure,
    }


def run(resolve, config):
    validate_config(config)
    if resolve is None or "studio" not in resolve.GetProductName().casefold():
        raise RuntimeError("Injected Resolve Studio object required")
    output = Path(config["outputDir"])
    media_root = Path(config["mediaDir"])
    for path, prefix in (
        (media_root, "issue-141-media-"),
        (output, "issue-141-observation-"),
    ):
        if (
            path.parent != ROOT / "out"
            or not path.name.startswith(prefix)
            or path.is_symlink()
            or path.resolve().parent != (ROOT / "out").resolve()
        ):
            raise ValueError(
                "Only slice-owned directories under this checkout's out are allowed"
            )
    if sha256(media_root / "manifest.json") != config.get("manifestSha256"):
        raise ValueError(
            "Preparation manifest changed; refusing before Resolve mutation"
        )
    manifest = json.loads((media_root / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("kind") != "generated-synthetic-inputs-not-Resolve-evidence":
        raise ValueError("Only generated issue-141 synthetic inputs are allowed")
    expected = {}
    for entry in manifest["files"]:
        relative = Path(entry["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError("Unsafe synthetic manifest locator")
        path = media_root / relative
        if path.is_symlink() or not path.resolve().is_relative_to(media_root.resolve()):
            raise ValueError("Synthetic media must remain inside the slice directory")
        expected[str(path)] = entry["sha256"]
    if len(expected) != len(manifest["files"]):
        raise ValueError("Duplicate synthetic manifest paths")
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    environment = {
        "productName": resolve.GetProductName(),
        "version": resolve.GetVersion(),
        "python": platform.python_version(),
        "externalScripting": "None",
        "externalScriptingEvidence": "operator config attestation, not API readback",
        "installedDocs": manifest["installedDocs"],
    }
    identity_path = output / "identity.json"
    if config["action"] in {"prepare", "resume-preparation"}:
        for locator in expected:
            if source_evidence(locator, expected).get("hashMatches") is not True:
                raise ValueError(
                    "Synthetic media changed; no project mutation occurred"
                )
        manager = resolve.GetProjectManager()
        if config["action"] == "prepare":
            names = manager.GetProjectListInCurrentFolder()
            if not isinstance(names, (list, tuple)) or config["projectName"] in names:
                raise RuntimeError(
                    "Unreadable project list or existing project; refusing reuse"
                )
            output.mkdir(parents=True, exist_ok=False)
            identity = {}
            project = None
        else:
            project, identity = resume_project(resolve, config, output)
        journal = output / f"preparation-{stamp}.jsonl"

        def mutate(obj, method, *args, audit_args=None):
            if identity:
                require_current(resolve, config, identity)

            def retain(phase, value):
                with journal.open("a", encoding="utf-8") as stream:
                    json.dump(
                        {
                            "at": datetime.now(UTC).isoformat(),
                            "method": method,
                            "phase": phase,
                            "value": value,
                        },
                        stream,
                        sort_keys=True,
                    )
                    stream.write("\n")

            retain("request", args if audit_args is None else audit_args)
            try:
                value = getattr(obj, method)(*args)
                if value is None or value is False:
                    raise RuntimeError(f"{method} refused operation")
                if method == "AppendToTimeline":
                    result = [read(item, "GetUniqueId") for item in value]
                elif method == "ImportMedia":
                    result = [media_evidence(item, expected) for item in value]
                elif method in {"CreateProject", "CreateEmptyTimeline"}:
                    result = {
                        "GetUniqueId": read(value, "GetUniqueId"),
                        "GetName": read(value, "GetName"),
                    }
                else:
                    result = value
                retain("return", result)
                return value
            except Exception as error:
                retain("failure", f"{type(error).__name__}: {error}")
                raise

        try:
            if config["action"] == "prepare":
                project = mutate(manager, "CreateProject", config["projectName"])
                identity = {
                    "projectId": project.GetUniqueId(),
                    "projectName": project.GetName(),
                }
                if (
                    not isinstance(identity["projectId"], str)
                    or not identity["projectId"]
                    or identity["projectName"] != config["projectName"]
                ):
                    raise RuntimeError(
                        "Created project identity could not be established"
                    )
                write_json(identity_path, identity)
            before = read(project, "GetSettings")
            write_json(output / f"project-settings-before-{stamp}.json", before)
            if not settings_match(
                before.get("value"), {"timelinePlaybackFrameRate": "25"}
            ):
                raise RuntimeError(
                    "Operator required: set Playback frame rate to 25 "
                    "in Project Settings"
                )
            requested = dict(SETTINGS)
            for key, directory in (
                ("projectMediaLocation", "media"),
                ("perfCacheClipsLocation", "cache"),
                ("colorGalleryStillsLocation", "gallery"),
            ):
                path = output / f"storage-{stamp}" / directory
                path.mkdir(parents=True, exist_ok=False)
                requested[key] = str(path)
            for key, value in requested.items():
                try:
                    mutate(project, "SetSettings", {key: value})
                finally:
                    settings_after = read(project, "GetSettings")
                    write_json(
                        output / f"project-settings-{stamp}-{key}.json", settings_after
                    )
                if not settings_match(settings_after.get("value"), {key: value}):
                    raise RuntimeError(f"Setting readback differs for {key}; stop")
            settings_readback = read(project, "GetSettings")
            settings_path = (
                output / "project-settings.json"
                if config["action"] == "prepare"
                else output / f"project-settings-{stamp}.json"
            )
            write_json(settings_path, settings_readback)
            settings_value = settings_readback.get("value")
            if not settings_match(
                settings_value, {**requested, "timelinePlaybackFrameRate": "25"}
            ):
                raise RuntimeError(
                    "Project time base/settings readback differs; stop preparation"
                )
            pool = project.GetMediaPool()
            imported = {}
            for filename in (
                "base.mov",
                "cutaway.mov",
                "repeated.wav",
                "bed.wav",
                "overlay.png",
            ):
                items = mutate(pool, "ImportMedia", [str(media_root / filename)])
                if len(items) != 1:
                    raise RuntimeError("Expected exactly one synthetic import")
                props = items[0].GetClipProperty()
                if not isinstance(props, dict) or props.get("File Path") != str(
                    media_root / filename
                ):
                    raise RuntimeError("Import returned an unexpected source locator")
                imported[filename] = items[0]
            timeline = mutate(pool, "CreateEmptyTimeline", TIMELINE)
            mutate(
                project,
                "SetCurrentTimeline",
                timeline,
                audit_args=[timeline.GetUniqueId()],
            )
            mutate(timeline, "SetStartTimecode", "00:00:00:00")
            for kind in ("video", "audio"):
                count = timeline.GetTrackCount(kind)
                if not isinstance(count, int) or not 0 <= count <= 3:
                    raise RuntimeError("Unexpected initial track count")
                for previous in range(count, 3):
                    mutate(
                        timeline,
                        "AddTrack",
                        kind,
                        *(["mono"] if kind == "audio" else []),
                    )
                    if timeline.GetTrackCount(kind) != previous + 1:
                        raise RuntimeError(
                            "AddTrack returned success without matching count"
                        )
            placed = []
            for filename, kind, track, source, duration, record, enabled in (
                ("base.mov", 1, 1, 0, 200, 0, True),
                ("repeated.wav", 2, 1, 0, 200, 0, True),
                ("repeated.wav", 2, 2, 0, 200, 0, False),
                ("bed.wav", 2, 3, 0, 200, 0, True),
                ("cutaway.mov", 1, 2, 0, 50, 50, False),
                ("overlay.png", 1, 3, 0, 50, 75, False),
            ):
                info = {
                    "mediaPoolItem": imported[filename],
                    "mediaType": kind,
                    "trackIndex": track,
                    "startFrame": source,
                    "endFrame": source + duration - 1,
                    "recordFrame": record,
                }
                audit = {**info, "mediaPoolItem": imported[filename].GetUniqueId()}
                items = mutate(pool, "AppendToTimeline", [info], audit_args=[audit])
                if len(items) != 1:
                    raise RuntimeError("Expected exactly one appended occurrence")
                item = items[0]
                write_json(
                    output / f"preparation-item-{len(placed)}-before.json",
                    item_evidence(item, expected),
                )
                mutate(item, "SetClipEnabled", enabled)
                if item.GetClipEnabled() is not enabled:
                    raise RuntimeError("Clip enabled readback differs")
                mutate(
                    item,
                    "AddMarker",
                    0,
                    "Blue",
                    f"141 occurrence {len(placed)}",
                    "Synthetic probe",
                    1,
                    json.dumps({"issue": 141, "occurrence": len(placed)}),
                )
                write_json(
                    output / f"preparation-item-{len(placed)}-after.json",
                    item_evidence(item, expected),
                )
                placed.append(item)
            mutate(
                timeline,
                "SetClipsLinked",
                placed[:2],
                True,
                audit_args=[[item.GetUniqueId() for item in placed[:2]], True],
            )
            mutate(
                timeline,
                "AddMarker",
                100,
                "Blue",
                "141 section boundary",
                "Exact 4s / 100f boundary",
                1,
                '{"issue":141,"section":"boundary-100"}',
            )
            mutate(manager, "SaveProject")
            identity["baselineTimelineId"] = timeline.GetUniqueId()
            write_json(
                output / "prepared.json",
                {
                    "identity": identity,
                    "environment": environment,
                    "manifestSha256": sha256(media_root / "manifest.json"),
                    "settings": requested,
                },
            )
        except Exception as error:
            write_json(
                output / f"preparation-failure-{stamp}.json",
                {
                    "error": f"{type(error).__name__}: {error}",
                    "identity": identity,
                    "environment": environment,
                    "partialProjectMayRemain": True,
                    "instruction": (
                        "Stop; retain the journal. "
                        "Do not rerun prepare or delete the project."
                    ),
                },
            )
            raise
    elif config["action"] == "matrix-reopen":
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return matrix_reopen(
            resolve, config, identity, expected, output, stamp, environment
        )
    elif config["action"] == "matrix-finalize":
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return matrix_finalize(
            resolve, config, identity, expected, output, stamp, environment
        )
    elif config["action"] == "picture-calibration":
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return picture_calibration(
            resolve, config, identity, expected, output, stamp, environment
        )
    elif config["action"] == "picture-cases":
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return picture_cases(
            resolve, config, identity, expected, output, stamp, environment
        )
    elif config["action"] == "audio-cases":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("audio-cases.py")
        if sha256(module_path) != (
            "643f520f051c0c7435d921dc1964e0b940abd75305a5cf7be3693ec41bbf6fa6"
        ):
            raise RuntimeError("Pinned audio-cases module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_audio_cases", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned audio-cases module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp,
            environment,
            probe=sys.modules[__name__],
        )
    elif config["action"] == "output-discovery":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("output-discovery.py")
        if sha256(module_path) != (
            "777d2dc93be950c7df9f36445e3a6bac6fa344d7f4a1e524a436dec163dbb571"
        ):
            raise RuntimeError("Pinned output-discovery module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_output_discovery", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned output-discovery module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "restore-pinned-cache":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("cache-restore.py")
        if sha256(module_path) != (
            "29e651d0940a97fe93956056e9c39c16b31f507202ac502553dce8a6776befc7"
        ):
            raise RuntimeError("Pinned cache-restore module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_cache_restore", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned cache-restore module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "offline-picture":
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("offline-picture.py")
        if sha256(module_path) != (
            "bb9b9ee84fc2bdeb46fd112585777347b08704abd5eacf0cb5c1e8520b6f4cbd"
        ):
            raise RuntimeError("Pinned offline picture module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_offline_picture", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned offline picture module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(
            resolve,
            config,
            identity,
            expected,
            output,
            stamp,
            environment,
            probe=sys.modules[__name__],
        )
    elif config["action"] in {"audio-output", "audio-output-continue"}:
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("audio-output.py")
        if sha256(module_path) != (
            "0740a4b74b967e4037f0e09f45d4d527e1f660f0ac486f81954f5c8d226cb5b1"
        ):
            raise RuntimeError("Pinned audio output module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_audio_output", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned audio output module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] in {
        "audio-render-recovery",
        "audio-video-toggle-recovery",
        "audio-format-selection-recovery",
    }:
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("audio-render-recovery.py")
        if sha256(module_path) != (
            "e13e01998c03b0171ed5304e69baad9af6aab688aa18ac1aaf616e2c06528d84"
        ):
            raise RuntimeError("Pinned audio recovery module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_audio_render_recovery", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned audio recovery module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "matrix-checkpoint":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("matrix-checkpoint.py")
        if sha256(module_path) != (
            "ae61cd242cabf948450ad3936e2c9cb71645bf5c0bfc7ec37a8a84012f5b1259"
        ):
            raise RuntimeError("Pinned Matrix checkpoint module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_matrix_checkpoint", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned Matrix checkpoint module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] in {
        "r4-wrong-bytes",
        "av-output",
        "av-output-continue",
        "av-output-queue-from-settings",
        "r5-freshness",
        "r5-capture-freshness",
        "r1-razor-prepare",
        "editorial-readback",
        "editorial-restore",
        "editorial-case-prepare",
        "editorial-case-restore",
        "editorial-copy-paste-position",
        "offline-cycle",
        "offline-picture-continuation",
    }:
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        owned_modules = {
            "av-output": (
                "av-output.py",
                "9cc6d6cc1d53f47e5633311c85947a2a00803e875c4a055d10bf9057e622e272",
            ),
            "editorial-case-prepare": (
                "editorial-cases.py",
                "203dfa7928d21894a836985c86a7652f26cbe7982b49d89530184fbadf28b4ea",
            ),
            "editorial-restore": (
                "editorial-restore.py",
                "7038d01f9df7cfebb483faf4b0097e0090cd0b974b513423c2f57d0be820dc9d",
            ),
            "r1-razor-prepare": (
                "r1-razor.py",
                "4df6c36f820621700d554c6fecdcc1e36623ba2f8986a0da9d443ecd3780bd73",
            ),
            "editorial-readback": (
                "editorial-readback.py",
                "fe451be3adb75217f461e16f0e78a561786baa1d23e49e32f773a6b94cb541d4",
            ),
            "r4-wrong-bytes": (
                "r4-wrong-bytes.py",
                "205dad3bd856a19f4e78f70e530d95ecce2956ac5ce8db6334198021b9b0e00a",
            ),
            "r5-freshness": (
                "r5-freshness.py",
                "dc5e0e4f6db0011a6ceffe4ddf1da9990b850680864d395fe7d741411130a101",
            ),
            "offline-cycle": (
                "offline-cycle.py",
                "0cb39d2479a15071052523b2525bcde392c07f71d68ad9843245b61195ded092",
            ),
        }
        module_key = {
            "editorial-case-restore": "editorial-case-prepare",
            "av-output-continue": "av-output",
            "av-output-queue-from-settings": "av-output",
            "editorial-copy-paste-position": "editorial-case-prepare",
            "r5-capture-freshness": "r5-freshness",
            "offline-picture-continuation": "offline-cycle",
        }.get(config["action"], config["action"])
        filename, digest = owned_modules[module_key]
        module_path = Path(__file__).with_name(filename)
        if module_path.is_symlink() or sha256(module_path) != digest:
            raise RuntimeError("Pinned bounded probe module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_bounded_probe", module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-reprepare":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-reprepare.py")
        if sha256(module_path) != (
            "23fb53b666175438cb104bd787fb7563ba99153d034e12a6fd284545fe61f632"
        ):
            raise RuntimeError("Pinned R4 re-preparation module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_reprepare", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 re-preparation module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-occurrence-remove":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-removal.py")
        if sha256(module_path) != (
            "6a0089d56cbfdc72d3360f843337eb84fa47fac62af91c85c0683e8156072a6e"
        ):
            raise RuntimeError("Pinned R4 removal module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_removal", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 removal module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-range-repair":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-range-repair.py")
        if sha256(module_path) != (
            "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"
        ):
            raise RuntimeError("Pinned R4 range-repair module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_range_repair", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 range-repair module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-recovery":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-recovery.py")
        if sha256(module_path) != (
            "adb3f429769c440a40d30e40481e3da508c4b49c1b51204df65be68f5b8bf7ff"
        ):
            raise RuntimeError("Pinned R4 recovery module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_recovery", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 recovery module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-transitions":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-transitions.py")
        if sha256(module_path) != (
            "12798b1288d41e70b01226202b5ee723b70219b90a6067405c816ac02e800af6"
        ):
            raise RuntimeError("Pinned R4 transitions module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_transitions", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 transitions module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-finalize":
        if not (output / "prepared.json").is_file():
            raise RuntimeError("Preparation is incomplete; inspect its journal")
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        module_path = Path(__file__).with_name("r4-finalize.py")
        if sha256(module_path) != (
            "4e9587bcb5d78258fabf50de57d0c14b6ae9769de3c06281d4fc05f5971ab420"
        ):
            raise RuntimeError("Pinned R4 finalize module changed; refusing")
        spec = importlib.util.spec_from_file_location(
            "issue141_r4_finalize", module_path
        )
        if spec is None or spec.loader is None:
            raise RuntimeError("Could not load pinned R4 finalize module")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module.run(resolve, config, probe=sys.modules[__name__])
    elif config["action"] == "r4-pool-read-only":
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        project = require_current(resolve, config, identity)
        if environment["version"] != CONTEXT_ENVIRONMENT:
            raise RuntimeError("Pinned Resolve build differs")

        def read_context():
            current = require_current(resolve, config, identity)
            selected = current.GetCurrentTimeline()
            return {
                "currentPage": read(resolve, "GetCurrentPage"),
                "selectedTimelineUid": read(selected, "GetUniqueId"),
                "playhead": read(selected, "GetCurrentTimecode"),
                "formatCodec": read(current, "GetCurrentRenderFormatAndCodec"),
                "jobs": read(current, "GetRenderJobList"),
                "rendering": read(current, "IsRenderingInProgress"),
            }

        context_before = read_context()
        captured = capture(
            resolve, config, identity, expected, output, stamp, environment
        )
        inventories = [
            json.loads(json.dumps(_r4_pool_inventory(project, expected)))
            for _ in range(2)
        ]
        require_current(resolve, config, identity)
        context_after = read_context()
        status = (
            "equal-read-only-pool-inventory"
            if inventories[0] == inventories[1]
            and captured["status"] == "equal-adjacent-reads"
            and not errors(inventories)
            and context_before == context_after
            and not errors(context_before)
            else "incomplete-or-inconsistent-refused"
        )
        path = output / f"r4-pool-read-only-{stamp}.json"
        write_json(
            path,
            {
                "capture": captured,
                "passes": inventories,
                "status": status,
                "contextBefore": context_before,
                "contextAfter": context_after,
            },
        )
        return {"status": status, "capture": captured, "inventoryPath": str(path)}
    elif config["action"] == "r4-availability":
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return r4_prepare(
            resolve, config, identity, expected, output, stamp, environment
        )
    elif config["action"] in {
        "native-repeat",
        "native-duplicate",
        "native-context",
        "native-matrix",
    }:
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
        return (
            native_repeat(
                resolve, config, identity, expected, output, stamp, environment
            )
            if config["action"] in {"native-repeat", "native-duplicate"}
            else native_context(
                resolve, config, identity, expected, output, stamp, environment
            )
            if config["action"] == "native-context"
            else native_matrix(
                resolve, config, identity, expected, output, stamp, environment
            )
        )
    else:
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
    project = require_current(resolve, config, identity)
    selected = project.GetCurrentTimeline()
    environment["context"] = {
        "currentPage": read(resolve, "GetCurrentPage"),
        "selectedTimelineUid": (
            read(selected, "GetUniqueId") if selected is not None else {"value": None}
        ),
        "playhead": read(selected, "GetCurrentTimecode"),
        "renderState": {
            method: read(project, method)
            for method in (
                "GetCurrentRenderFormatAndCodec",
                "GetCurrentRenderMode",
                "GetRenderJobList",
                "IsRenderingInProgress",
                "GetRenderPresetList",
            )
        },
    }
    return capture(resolve, config, identity, expected, output, stamp, environment)
