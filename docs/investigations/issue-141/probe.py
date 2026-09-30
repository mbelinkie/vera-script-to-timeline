"""Issue-owned injected probe. No external bridge or production reconciler."""

import hashlib
import json
import platform
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

PREFIX = "VERA Issue 141 Synthetic Probe "
TIMELINE = "VERA 141 Baseline"
ROOT = Path(__file__).resolve().parents[3]
SETTINGS = {
    "timelineFrameRate": "25",
    "timelinePlaybackFrameRate": "25",
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
    if config.get("action") not in {"prepare", "resume-preparation", "observe"}:
        raise ValueError("Unknown bounded probe action")
    for key in ("mediaDir", "outputDir"):
        if not isinstance(config.get(key), str) or not Path(config[key]).is_absolute():
            raise ValueError(f"{key} must be absolute")


def settings_match(observed, requested):
    if not isinstance(observed, dict):
        return False
    for key, expected in requested.items():
        actual = observed.get(key)
        if key in SETTINGS:
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
    # Bounded recovery of the one recorded pre-import failure, never generic retry.
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
    if failure.get("error") != (
        "RuntimeError: Project time base/settings readback differs; stop preparation"
    ):
        raise ValueError("Only the recorded settings-check failure may continue")
    records = [json.loads(line) for line in retained["resumeJournal"].splitlines()]
    if [(row["method"], row["phase"]) for row in records] != [
        ("CreateProject", "request"),
        ("CreateProject", "return"),
        ("SetSettings", "request"),
        ("SetSettings", "return"),
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


def source_evidence(locator, expected):
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
    result["sourceBytes"] = source_evidence(locator, expected)
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
            requested = dict(SETTINGS)
            for key, directory in (
                ("projectMediaLocation", "media"),
                ("perfCacheClipsLocation", "cache"),
                ("colorGalleryStillsLocation", "gallery"),
            ):
                path = output / f"storage-{stamp}" / directory
                path.mkdir(parents=True, exist_ok=False)
                requested[key] = str(path)
            mutate(project, "SetSettings", requested)
            settings_readback = read(project, "GetSettings")
            settings_path = (
                output / "project-settings.json"
                if config["action"] == "prepare"
                else output / f"project-settings-{stamp}.json"
            )
            write_json(settings_path, settings_readback)
            settings_value = settings_readback.get("value")
            if not settings_match(settings_value, requested):
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
    else:
        if not (output / "prepared.json").is_file():
            raise RuntimeError(
                "Preparation is incomplete; stop and inspect its journal"
            )
        identity = json.loads(identity_path.read_text(encoding="utf-8"))
        require_current(resolve, config, identity)
    return capture(resolve, config, identity, expected, output, stamp, environment)
