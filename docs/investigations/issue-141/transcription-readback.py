"""Read-only Resolve transcription getter observation for Issue 141."""

import hashlib
import importlib.util
import json
import platform
from datetime import UTC, datetime
from pathlib import Path
from string import hexdigits

ACTION = "transcription-readback"
PROJECT_ID = "97037b5a-aab6-48a9-b7e4-4c5697ae10a0"
PROJECT_NAME = "VERA Issue 141 Synthetic Probe 20260930-01a0f318"
MATRIX_UID = "29ae8331-b86e-4041-a548-960695cc7b24"
MATRIX_NAME = "VERA 141 Batched Matrix"
SOURCE_UID = "a7ad9e19-d49b-428b-9fd5-95c90d60e6f8"
SOURCE_NAME = "repeated.wav"
READER_FILE = "r4-range-repair.py"
READER_SHA256 = "06eff080c45e5c520a1c8c31787e4d4f1604198a3a98a9e3c8e025917fcf455b"


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


def _inside(path, parent):
    try:
        return Path(path).resolve(strict=True).is_relative_to(
            Path(parent).resolve(strict=True)
        )
    except (OSError, ValueError):
        return False


def _load_reader():
    path = Path(__file__).with_name(READER_FILE)
    if path.is_symlink() or _sha256(path) != READER_SHA256:
        raise RuntimeError("Pinned complete reader changed")
    spec = importlib.util.spec_from_file_location("transcription_readback_reader", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load pinned complete reader")
    reader = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    return reader


def _checkpoint(config, output, probe):
    checkpoint_path = config.get("checkpointPath")
    digest = config.get("checkpointSha256")
    if not isinstance(checkpoint_path, str) or not checkpoint_path:
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    path = Path(checkpoint_path)
    if not path.is_absolute():
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    if any(part == ".." for part in path.parts):
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    if path.is_symlink() or not path.is_file():
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    try:
        relative = path.relative_to(output)
    except ValueError as error:
        raise RuntimeError(
            "Contained current Matrix checkpoint binding is required"
        ) from error
    if not _inside(path, output):
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    cursor = output
    for part in relative.parts:
        cursor /= part
        if cursor.is_symlink():
            raise RuntimeError(
                "Contained current Matrix checkpoint binding is required"
            )
    if (
        not isinstance(digest, str)
        or len(digest) != 64
        or any(char not in hexdigits for char in digest)
        or probe.sha256(path) != digest
    ):
        raise RuntimeError("Contained current Matrix checkpoint binding is required")
    try:
        return path, json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Current Matrix checkpoint is unreadable") from error


def _validate_checkpoint(checkpoint, reader, probe):
    state, pool = reader._validate_read_pair(checkpoint, probe)
    expected = {
        reader.MATRIX_UID: reader.MATRIX_NAME,
        reader.R4_UID: reader.R4_NAME,
        "88f7923d-55a7-471f-b09b-cf10f9fae8ad": "VERA 141 Baseline",
        "aa2b8e36-83bd-4292-9e33-217c00ca192f": "VERA 141 R1 identity",
    }
    actual = {
        row.get("GetUniqueId", {}).get("value"): row.get("GetName", {}).get(
            "value"
        )
        for row in state.get("timelines", [])
    }
    if (
        checkpoint.get("selectedTimelineUid") != reader.MATRIX_UID
        or state.get("projectId") != reader.PROJECT_ID
        or state.get("projectName") != PROJECT_NAME
        or actual != expected
    ):
        raise RuntimeError("Complete current Matrix checkpoint identity is required")
    return state, pool


def _context(resolve, config, reader, probe, identity):
    project = reader._context(resolve, config, identity, probe, reader.MATRIX_UID)
    if project.IsRenderingInProgress() is not False:
        raise RuntimeError("Resolve must be idle")
    if project.GetRenderJobList() != []:
        raise RuntimeError("Resolve render queue must be empty")
    return project


def _capture(resolve, config, reader, probe, identity, expected):
    _context(resolve, config, reader, probe, identity)
    pair = reader._read_pair(
        resolve, config, identity, expected, reader.MATRIX_UID, probe
    )
    reader._validate_read_pair(pair, probe)
    _context(resolve, config, reader, probe, identity)
    return pair


def _pool_row(pool, uid, label):
    rows = [row for row in pool.get("items", []) if row.get("uid") == uid]
    if len(rows) != 1:
        raise RuntimeError(f"{label} pool identity is missing or duplicated")
    return rows[0]


def _target_handles(project, pool, expected, reader):
    timeline = project.GetCurrentTimeline()
    if timeline is None or timeline.GetUniqueId() != reader.MATRIX_UID:
        raise RuntimeError("Exact Matrix timeline must remain selected")

    mappings = [
        row
        for row in pool.get("timelineMappings", [])
        if row.get("timelineUid", {}).get("value") == reader.MATRIX_UID
    ]
    if len(mappings) != 1:
        raise RuntimeError("Retained Matrix timeline-to-pool mapping is missing")
    proxy_uid = mappings[0].get("poolItemUid", {}).get("value")
    if not isinstance(proxy_uid, str) or not proxy_uid:
        raise RuntimeError("Retained Matrix pool proxy UID is unreadable")

    proxy = timeline.GetMediaPoolItem()
    if proxy is None or proxy.GetUniqueId() != proxy_uid:
        raise RuntimeError("Live Matrix pool proxy differs from retained mapping")
    if proxy.GetName() != reader.MATRIX_NAME:
        raise RuntimeError("Live Matrix pool proxy name differs")

    source_row = _pool_row(pool, SOURCE_UID, "repeated.wav source")
    source_evidence = source_row.get("evidence", {})
    source_properties = source_evidence.get("GetClipProperty", {}).get("value", {})
    source_path = source_properties.get("File Path")
    source_bytes = source_evidence.get("sourceBytes", {})
    if (
        source_row.get("name", {}).get("value") != SOURCE_NAME
        or source_evidence.get("GetUniqueId") != {"value": SOURCE_UID}
        or source_properties.get("File Name") != SOURCE_NAME
        or source_path not in expected
        or source_bytes.get("sha256") != expected.get(source_path)
        or source_bytes.get("hashMatches") is not True
    ):
        raise RuntimeError("Verified repeated.wav source identity or hash changed")

    items = timeline.GetItemListInTrack("audio", 1)
    if not isinstance(items, (list, tuple)):
        raise RuntimeError("Matrix A1 occurrence list is unreadable")
    occurrences = []
    source_handle = None
    for item in items:
        track = item.GetTrackTypeAndIndex()
        if tuple(track) != ("audio", 1):
            raise RuntimeError("Matrix A1 occurrence has an unexpected track")
        media = item.GetMediaPoolItem()
        if media is None or media.GetUniqueId() != SOURCE_UID:
            continue
        if media.GetName() != SOURCE_NAME:
            raise RuntimeError("Exact repeated.wav source handle has wrong name")
        if source_handle is None:
            source_handle = media
        occurrences.append(
            {
                "itemUid": item.GetUniqueId(),
                "track": ["audio", 1],
            }
        )
    if not occurrences:
        raise RuntimeError("Verified repeated.wav source is absent from Matrix A1")

    return (
        {
            "source": {
                "handle": source_handle,
                "uid": SOURCE_UID,
                "name": SOURCE_NAME,
                "occurrence": occurrences[0],
                "occurrenceCount": len(occurrences),
                "sourcePath": source_path,
                "sha256": source_bytes["sha256"],
            },
            "matrixTimelinePoolProxy": {
                "handle": proxy,
                "uid": proxy_uid,
                "name": reader.MATRIX_NAME,
            },
        },
        {
            "sourceUid": SOURCE_UID,
            "sourceName": SOURCE_NAME,
            "sourcePath": source_path,
            "sourceSha256": source_bytes["sha256"],
            "verifiedMatrixA1Occurrences": occurrences,
            "matrixTimelinePoolProxyUid": proxy_uid,
        },
    )


def _transcription_state(value):
    if value is None:
        return "missing"
    if value in ({}, [], ""):
        return "empty"
    if isinstance(value, dict) and value.get("segments") == []:
        return "empty"
    return "value"


def _get_transcription(item, nested):
    try:
        value = item.GetTranscription(nested)
    except Exception as error:
        return {
            "state": "error",
            "raw": None,
            "error": f"{type(error).__name__}: {error}",
        }
    try:
        raw = _canonical(value)
    except Exception as error:
        return {
            "state": "error",
            "raw": None,
            "error": f"{type(error).__name__}: non-serializable transcription",
        }
    return {"state": _transcription_state(raw), "raw": raw}


def _transcriptions(targets):
    results = {}
    for label, target in targets.items():
        modes = {}
        for nested in (False, True):
            passes = [_get_transcription(target["handle"], nested) for _ in range(2)]
            equal = passes[0] == passes[1]
            modes[f"GetTranscription({nested})"] = {
                "argument": nested,
                "passes": passes,
                "state": passes[0]["state"] if equal else "unstable",
                "repeatConsistency": (
                    "equal-adjacent-reads" if equal else "unstable"
                ),
            }
        results[label] = modes
    return results


def _target_metadata(targets):
    return {
        label: {key: value for key, value in target.items() if key != "handle"}
        for label, target in targets.items()
    }


def run(resolve, config, *, probe):
    """Observe exact source and Matrix proxy transcriptions without mutation."""
    reader = _load_reader()
    root = Path(probe.ROOT).resolve()
    output = Path(config.get("outputDir", ""))
    if (
        config.get("action") != ACTION
        or config.get("externalScriptingSetting") != "None"
        or config.get("projectName") != PROJECT_NAME
        or not output.is_absolute()
        or output.is_symlink()
        or not output.is_dir()
        or output.parent.resolve() != (root / "out").resolve()
        or not output.name.startswith("issue-141-observation-")
        or resolve.GetProductName() != "DaVinci Resolve Studio"
        or resolve.GetVersion() != reader.BUILD
    ):
        raise RuntimeError("Exact Issue 141 transcription readback is required")

    media, expected = reader._manifest(config, root, probe)
    checkpoint_path, checkpoint = _checkpoint(config, output, probe)
    checkpoint_state, checkpoint_pool = _validate_checkpoint(checkpoint, reader, probe)

    identity = {"projectId": reader.PROJECT_ID, "projectName": PROJECT_NAME}
    environment = {
        "productName": resolve.GetProductName(),
        "resolveVersion": resolve.GetVersion(),
        "python": platform.python_version(),
        "externalScriptingSetting": "None",
    }
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S.%fZ")
    evidence = output / f"transcription-readback-{stamp}"
    evidence.mkdir(exist_ok=False)
    journal = evidence / "journal.jsonl"
    journal.touch()
    checkpoint_reference = str(checkpoint_path.relative_to(output))
    _append(
        journal,
        "TranscriptionReadback",
        "start",
        {
            "action": ACTION,
            "projectId": reader.PROJECT_ID,
            "projectName": PROJECT_NAME,
            "checkpoint": {
                "path": checkpoint_reference,
                "sha256": config["checkpointSha256"],
            },
            "manifestSha256": config.get("manifestSha256"),
            "environment": environment,
        },
    )

    project = _context(resolve, config, reader, probe, identity)
    before = _capture(resolve, config, reader, probe, identity, expected)
    before_state, before_pool = reader._validate_read_pair(before, probe)
    before_path = evidence / "before.json"
    _write(before_path, before)
    _append(
        journal,
        "FullReadback",
        "before",
        {"path": before_path.name, "sha256": probe.sha256(before_path)},
    )
    if before_state != checkpoint_state or before_pool != checkpoint_pool:
        raise RuntimeError("Fresh Matrix state differs from the retained checkpoint")

    targets, target_summary = _target_handles(project, before_pool, expected, reader)
    target_metadata = _target_metadata(targets)
    targets_path = evidence / "targets.json"
    _write(
        targets_path,
        {"summary": target_summary, "targets": target_metadata},
    )
    _append(
        journal,
        "TargetHandles",
        "verified",
        {"path": targets_path.name, "sha256": probe.sha256(targets_path)},
    )

    getter_results = _transcriptions(targets)
    getter_path = evidence / "transcriptions.json"
    _write(getter_path, getter_results)
    _append(
        journal,
        "GetTranscription",
        "readback",
        {
            "path": getter_path.name,
            "sha256": probe.sha256(getter_path),
            "note": "Adjacent raw equality is a bounded repeat, not an atomic token.",
        },
    )

    after = _capture(resolve, config, reader, probe, identity, expected)
    after_path = evidence / "after.json"
    _write(after_path, after)
    _append(
        journal,
        "FullReadback",
        "after",
        {"path": after_path.name, "sha256": probe.sha256(after_path)},
    )
    unchanged = after == before
    report = {
        "kind": "transcription-readback",
        "status": "transcription-readback-retained" if unchanged else "refused",
        "readOnly": True,
        "entry": {"action": ACTION, "externalScriptingSetting": "None"},
        "identity": identity,
        "environment": environment,
        "checkpoint": {
            "path": checkpoint_reference,
            "sha256": config["checkpointSha256"],
        },
        "manifest": {
            "path": str(media / "manifest.json"),
            "sha256": config.get("manifestSha256"),
            "sourceHashes": expected,
        },
        "matrixTimelineUid": reader.MATRIX_UID,
        "matrixTimelinePoolProxyUid": target_summary[
            "matrixTimelinePoolProxyUid"
        ],
        "targets": {"summary": target_summary, "handles": target_metadata},
        "before": {
            "path": before_path.name,
            "sha256": probe.sha256(before_path),
        },
        "after": {"path": after_path.name, "sha256": probe.sha256(after_path)},
        "fullTimelinePoolStateUnchanged": unchanged,
        "transcriptions": {
            "path": getter_path.name,
            "sha256": probe.sha256(getter_path),
            "results": getter_results,
        },
        "limits": [
            (
                "Missing, empty, getter-error, and unstable states are retained "
                "without speech or capability-failure inference."
            ),
            (
                "Equal adjacent raw GetTranscription reads are a bounded repeat, "
                "not an atomic token."
            ),
        ],
        "journal": journal.name,
    }
    _write(evidence / "result.json", report)
    _append(journal, "TranscriptionReadback", "complete", report)
    if not unchanged:
        raise RuntimeError("Full timeline or pool state changed during readback")
    return report
