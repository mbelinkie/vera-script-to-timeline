"""#204 installed getter-only preflight; never authorizes native effects."""

from __future__ import annotations

import getpass
import hashlib
import json
import math
import os
import platform
import re
import stat
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from .workflow_package import SOURCE_PINS, write_immutable_json

REQUEST_SCHEMA = "vera-native-qualification-request/v1"
AUTHORITY_SCHEMA = "vera-native-qualification-authority/v1"
RESULT_SCHEMA = "vera-native-qualification-result/v1"
APPROVED_NOTE_HASH = "c8ec4e9abf427a5e99ba8951abcc463745938aa1f35a3c4613f7b037a80e2740"
APPROVED_SCOPE = (
    "separateinstalledqualificationroute STAGEDread-onlycapabilitypreflightfirst; "
    "nocreation/renderinguntilactualcapability/controls/formatreport"
)
RUNTIME_FILES = (
    "__init__.py",
    "studio_spike.py",
    "text_plus_template.py",
    "workflow_package.py",
    "workflow_delivery.py",
    "workflow_launcher.py",
    "workflow_v2.py",
    "workflow_v2_launcher.py",
    "native_qualification_v2.py",
)
SOURCE_FILES = (
    *(f"python/vera_timeline_agent/{name}" for name in RUNTIME_FILES),
    "python/vera_timeline_agent/workflow_v2_cli.py",
    "python/vera_timeline_agent/workflow_delivery_cli.py",
    "integrations/resolve/VERA Delivery v2.py",
    "docs/plans/issue-178-native-qualification-change-note.md",
)
_BINDING_KEYS = {
    "releaseRoot",
    "releaseSha256",
    "repositoryRoot",
    "repositorySourcePins",
    "target",
    "evidenceDir",
    "approvalPath",
    "approvalSha256",
}
_TARGET_KEYS = {"projectUid", "timelineUid", "projectName", "timelineName"}
_CONFIRMATIONS = {
    "readOnly": True,
    "savedDisposableNonproduction": True,
    "externalScripting": "None",
}
_MAX_BYTES = 2 * 1024 * 1024


def _require(ok: bool, reason: str) -> None:
    if not ok:
        raise ValueError(reason)


def _closed(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    _require(isinstance(value, dict) and set(value) == keys, f"invalid {label} fields")
    return cast(dict[str, Any], value)


def _text(value: Any, label: str) -> str:
    _require(
        isinstance(value, str) and bool(value.strip()) and len(value) <= 512,
        f"invalid {label}",
    )
    return cast(str, value)


def _hash(value: Any) -> str:
    _require(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        "invalid raw SHA-256",
    )
    return cast(str, value)


def _path(value: Any) -> Path:
    path = Path(_text(value, "absolute path"))
    _require(
        path.is_absolute() and str(path) == os.path.abspath(path),
        "path must be canonical absolute",
    )
    _require(
        not any(p.is_symlink() for p in (path, *path.parents)),
        "symbolic link in preflight path",
    )
    return path


def _read(path: Path) -> bytes:
    _path(str(path))
    try:
        fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    except OSError as error:
        raise ValueError("preflight input unavailable") from error
    try:
        before = os.fstat(fd)
        _require(before.st_nlink == 1, "hardlinked preflight input")
        _require(
            stat.S_ISREG(before.st_mode) and before.st_size <= _MAX_BYTES,
            "input is not a bounded regular file",
        )
        chunks = []
        total = 0
        while chunk := os.read(fd, 65536):
            total += len(chunk)
            _require(total <= _MAX_BYTES, "input grew beyond bound")
            chunks.append(chunk)
        after = os.fstat(fd)
        _require(
            (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
            == (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            and total == before.st_size,
            "input changed during read",
        )
        return b"".join(chunks)
    finally:
        os.close(fd)


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _within(path: Path, root: Path) -> bool:
    """Compare existing ancestry identity for APFS case and firmlink aliases."""
    if path.is_relative_to(root):
        return True
    if not root.exists():
        return False
    identity = (root.stat().st_dev, root.stat().st_ino)
    return any(
        candidate.exists()
        and (candidate.stat().st_dev, candidate.stat().st_ino) == identity
        for candidate in (path, *path.parents)
    )


def _object(payload: bytes) -> dict[str, Any]:
    def pairs(values: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in values:
            _require(key not in result, "duplicate JSON key")
            result[key] = value
        return result

    def invalid(value: str) -> None:
        raise ValueError(f"nonfinite JSON scalar: {value}")

    value = json.loads(payload, object_pairs_hook=pairs, parse_constant=invalid)
    _require(isinstance(value, dict), "preflight record must be an object")
    # Overflowing decimal floats are also rejected.
    json.dumps(value, allow_nan=False)
    return cast(dict[str, Any], value)


def _target(value: Any) -> dict[str, Any]:
    target = _closed(value, _TARGET_KEYS, "operator target")
    for key, item in target.items():
        _text(item, key)
    return target


def source_pins(repository: Path) -> dict[str, str]:
    _require(_path(str(repository)).is_dir(), "repository is unavailable")
    result = {name: _digest(_read(repository / name)) for name in SOURCE_FILES}
    _require(result[SOURCE_FILES[-1]] == APPROVED_NOTE_HASH, "approved note changed")
    return result


def _release(binding: dict[str, Any]) -> None:
    root = _path(binding["releaseRoot"])
    manifest_path = root / "vera-delivery-v2/release.json"
    payload = _read(manifest_path)
    _require(_digest(payload) == _hash(binding["releaseSha256"]), "release drift")
    manifest = _closed(
        _object(payload),
        {"schemaVersion", "deliveryVersion", "sourcePins", "files"},
        "release",
    )
    _require(
        manifest["schemaVersion"] == "vera-injected-delivery-release/v2"
        and manifest["deliveryVersion"] == "2"
        and manifest["sourcePins"] == SOURCE_PINS,
        "unsupported preflight release",
    )
    expected = {
        f"vera-delivery-v2/python/vera_timeline_agent/{name}": binding[
            "repositorySourcePins"
        ][f"python/vera_timeline_agent/{name}"]
        for name in RUNTIME_FILES
    }
    expected["VERA Delivery v2.py"] = binding["repositorySourcePins"][
        "integrations/resolve/VERA Delivery v2.py"
    ]
    entries = manifest["files"]
    _require(
        isinstance(entries, list) and len(entries) == len(expected),
        "incomplete declared preflight runtime",
    )
    declared = set()
    for entry in entries:
        entry = _closed(entry, {"path", "sha256", "sizeBytes"}, "release entry")
        name = entry["path"]
        _require(
            isinstance(name, str) and name in expected and name not in declared,
            "undeclared/duplicate release source",
        )
        payload = _read(root / name)
        _require(
            type(entry["sizeBytes"]) is int
            and len(payload) == entry["sizeBytes"]
            and _digest(payload) == entry["sha256"] == expected[name],
            "runtime source drift",
        )
        declared.add(name)
    allowed = declared | {
        "vera-delivery-v2/release.json",
        "vera-delivery-v2/request.json",
    }
    directories = {
        str(parent)
        for name in declared
        for parent in Path(name).parents
        if parent != Path(".")
    }
    for path in root.rglob("*"):
        _require(not path.is_symlink(), "symbolic link in release")
        if path.is_file() and path.name != ".DS_Store":
            _require(
                path.relative_to(root).as_posix() in allowed,
                "undeclared installed file",
            )
        else:
            _require(
                path.is_dir() or path.name == ".DS_Store", "unsupported release entry"
            )
            if path.is_dir():
                _require(
                    path.relative_to(root).as_posix() in directories,
                    "undeclared release directory",
                )


def _binding(value: Any) -> dict[str, Any]:
    binding = _closed(value, _BINDING_KEYS, "binding")
    _target(binding["target"])
    repository = _path(binding["repositoryRoot"])
    _require(binding["repositorySourcePins"] == source_pins(repository), "source drift")
    approval = _read(_path(binding["approvalPath"]))
    _require(_digest(approval) == _hash(binding["approvalSha256"]), "approval drift")
    approved = _closed(
        _object(approval),
        {
            "changeNote",
            "producerQuote",
            "noteSha256",
            "scope",
            "recordedAt",
            "ordinaryGuardsRetained",
        },
        "Producer approval",
    )
    _require(
        approved["changeNote"] == "CN-178-Q1"
        and approved["producerQuote"] == "Approve staged CN-178-Q1"
        and approved["noteSha256"] == APPROVED_NOTE_HASH
        and approved["scope"] == APPROVED_SCOPE
        and approved["ordinaryGuardsRetained"] is True,
        "staged approval required",
    )
    _release(binding)
    _require(
        datetime.fromisoformat(
            _text(approved["recordedAt"], "approval time")
        ).utcoffset()
        is not None,
        "approval time requires timezone",
    )
    evidence = _path(binding["evidenceDir"])
    _require(
        not _within(evidence, repository)
        and not _within(repository, evidence)
        and not _within(evidence, _path(binding["releaseRoot"]))
        and not _within(_path(binding["releaseRoot"]), evidence)
        and not _within(_path(binding["approvalPath"]), evidence),
        "evidence overlaps protected inputs",
    )
    _require(not evidence.exists() or evidence.is_dir(), "evidence is not a directory")
    return binding


def _authority(path: Path) -> tuple[dict[str, Any], str]:
    payload = _read(path)
    authority = _closed(
        _object(payload),
        {
            "schemaVersion",
            "issueNumber",
            "action",
            "operator",
            "issuedAt",
            "invocationId",
            "issuer",
            "binding",
            "confirmations",
        },
        "operator authority",
    )
    _require(
        authority["schemaVersion"] == AUTHORITY_SCHEMA
        and type(authority["issueNumber"]) is int
        and authority["issueNumber"] == 204
        and authority["action"] == "capability_preflight"
        and authority["confirmations"] == _CONFIRMATIONS,
        "explicit saved nonproduction read-only operator authority required",
    )
    confirmations = authority["confirmations"]
    _require(
        confirmations["readOnly"] is True
        and confirmations["savedDisposableNonproduction"] is True,
        "operator confirmations must be booleans",
    )
    _text(authority["operator"], "operator")
    _require(
        datetime.fromisoformat(authority["issuedAt"]).utcoffset() is not None,
        "operator authority needs timezone",
    )
    _require(
        str(uuid.UUID(authority["invocationId"])) == authority["invocationId"],
        "invalid operator invocation",
    )
    binding = _binding(authority["binding"])
    issuer = _closed(
        authority["issuer"],
        {"implementation", "pythonVersion", "hostUser", "toolSha256"},
        "authority issuer",
    )
    _require(
        issuer["implementation"] == "CPython"
        and issuer["pythonVersion"] == "3.12.14"
        and issuer["toolSha256"]
        == binding["repositorySourcePins"][
            "python/vera_timeline_agent/workflow_v2_cli.py"
        ],
        "authority requires independent locked operator preparation",
    )
    _text(issuer["hostUser"], "issuer host user")
    _require(
        not _within(path, _path(binding["evidenceDir"])),
        "authority must remain outside evidence",
    )
    return authority, _digest(payload)


def create_capability_authority(
    output: Path,
    *,
    release_root: Path,
    repository_root: Path,
    target: dict[str, Any],
    evidence_dir: Path,
    approval_path: Path,
    operator: str,
    confirm_saved_disposable: bool,
    confirm_read_only: bool,
    external_scripting_none: bool,
) -> Path:
    """Operator-only audited command; request preparation never invokes this."""
    _require(
        confirm_saved_disposable is True
        and confirm_read_only is True
        and external_scripting_none is True,
        "all explicit operator confirmations required",
    )
    _require(
        platform.python_implementation() == "CPython"
        and platform.python_version() == "3.12.14",
        "locked operator runtime required",
    )
    pins = source_pins(repository_root)
    binding = _binding(
        {
            "releaseRoot": str(release_root),
            "releaseSha256": _digest(
                _read(release_root / "vera-delivery-v2/release.json")
            ),
            "repositoryRoot": str(repository_root),
            "repositorySourcePins": pins,
            "target": _target(target),
            "evidenceDir": str(evidence_dir),
            "approvalPath": str(approval_path),
            "approvalSha256": _digest(_read(approval_path)),
        }
    )
    _path(str(output))
    _require(
        not _within(output, repository_root)
        and not _within(output, release_root)
        and not _within(output, evidence_dir),
        "authority overlaps protected root",
    )
    return write_immutable_json(
        output,
        {
            "schemaVersion": AUTHORITY_SCHEMA,
            "issueNumber": 204,
            "action": "capability_preflight",
            "operator": _text(operator, "operator"),
            "issuedAt": datetime.now(UTC).isoformat(),
            "invocationId": str(uuid.uuid4()),
            "issuer": {
                "implementation": platform.python_implementation(),
                "pythonVersion": platform.python_version(),
                "hostUser": getpass.getuser(),
                "toolSha256": pins["python/vera_timeline_agent/workflow_v2_cli.py"],
            },
            "binding": binding,
            "confirmations": _CONFIRMATIONS,
        },
    )


def prepare_capability_request(output: Path, *, authority_path: Path) -> Path:
    authority, digest = _authority(authority_path)
    _path(str(output))
    binding = authority["binding"]
    _require(
        not _within(output, _path(binding["repositoryRoot"]))
        and not _within(output, _path(binding["releaseRoot"]))
        and not _within(output, _path(binding["evidenceDir"]))
        and output not in {_path(binding["approvalPath"]), authority_path},
        "request overlaps protected input/evidence",
    )
    return write_immutable_json(
        output,
        {
            "schemaVersion": REQUEST_SCHEMA,
            "issueNumber": 204,
            "action": "capability_preflight",
            "binding": binding,
            "authorityPath": str(authority_path),
            "authoritySha256": digest,
        },
    )


def _request(path: Path, expected: str) -> dict[str, Any]:
    payload = _read(path)
    _require(_digest(payload) == _hash(expected), "request drift")
    request = _closed(
        _object(payload),
        {
            "schemaVersion",
            "issueNumber",
            "action",
            "binding",
            "authorityPath",
            "authoritySha256",
        },
        "preflight request",
    )
    _require(
        request["schemaVersion"] == REQUEST_SCHEMA
        and type(request["issueNumber"]) is int
        and request["issueNumber"] == 204
        and request["action"] == "capability_preflight",
        "unsupported preflight action",
    )
    authority, digest = _authority(_path(request["authorityPath"]))
    _require(
        digest == _hash(request["authoritySha256"])
        and request["binding"] == authority["binding"],
        "operator authority mismatch",
    )
    _require(
        not _within(path, _path(request["binding"]["evidenceDir"])),
        "request must remain outside evidence",
    )
    return request


class _Observations:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.value_bytes = 0

    def get(
        self,
        handle: Any,
        source: str,
        method: str,
        *args: Any,
        kind: str = "any",
        required: bool = False,
    ) -> Any:
        # Only hard-coded getter names below can reach the injected object.
        _require(method.startswith("Get"), "native effect forbidden")
        _require(len(self.rows) < 2000, "bounded observation inventory exhausted")
        row: dict[str, Any] = {
            "source": f"{source}.{method}",
            "arguments": list(args),
            "status": "unsupported",
            "value": None,
        }
        self.rows.append(row)
        try:
            getter = getattr(handle, method, None)
            _require(callable(getter), "documented getter unavailable")
            assert callable(getter)
            row["status"] = "ambiguous"
            value = getter(*args)
            if kind == "handle":
                _require(value is not None, "native handle unavailable")
                row["value"] = "native-handle"
            else:
                encoded = json.dumps(value, allow_nan=False)
                _require(
                    len(encoded.encode()) + self.value_bytes <= _MAX_BYTES // 3,
                    "getter values exceed retained evidence budget",
                )
                self.value_bytes += len(encoded.encode())
                row["value"] = value
            valid = (
                kind in {"any", "handle"}
                or (kind == "object" and isinstance(value, dict) and bool(value))
                or (kind == "list" and isinstance(value, list))
                or (kind == "bool" and type(value) is bool)
                or (kind == "count" and type(value) is int and 0 <= value <= 500)
                or (kind == "text" and isinstance(value, str) and bool(value))
            )
            row["status"] = "supported" if valid else "ambiguous"
            _require(valid, "getter returned incomplete/wrong-type evidence")
            return value
        except Exception as error:
            row["reason"] = str(error)
            if required:
                raise ValueError(f"{row['source']}: {error}") from error
            return None


def _context(
    resolve: Any, target: dict[str, Any], seen: _Observations
) -> tuple[Any, Any]:
    manager = seen.get(
        resolve, "resolve", "GetProjectManager", kind="handle", required=True
    )
    project = seen.get(
        manager, "manager", "GetCurrentProject", kind="handle", required=True
    )
    _require(
        seen.get(project, "project", "GetUniqueId", kind="text", required=True)
        == target["projectUid"]
        and seen.get(project, "project", "GetName", kind="text", required=True)
        == target["projectName"],
        "current project differs from operator target",
    )
    timeline = seen.get(
        project, "project", "GetCurrentTimeline", kind="handle", required=True
    )
    _require(
        seen.get(timeline, "timeline", "GetUniqueId", kind="text", required=True)
        == target["timelineUid"]
        and seen.get(timeline, "timeline", "GetName", kind="text", required=True)
        == target["timelineName"],
        "current timeline differs from operator target",
    )
    return project, timeline


def _gaps(
    rows: list[dict[str, Any]], items: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    gaps = []
    fields = [
        "enabled",
        "mute",
        "solo",
        "gainDb",
        "pan",
        "effects",
        "sends",
        "automation",
        "destination",
        "channelMap",
    ]
    for level in ("clip", "track", "bus", "master"):
        for field in fields:
            gaps.append(
                {
                    "field": f"{level}.{field}",
                    "status": "unsupported",
                    "sources": [],
                    "reason": "no complete documented control reader",
                }
            )
    gaps.append(
        {
            "field": "master.limiter",
            "status": "unsupported",
            "sources": [],
            "reason": "no documented current master limiter getter",
        }
    )
    for field in ["gainDb", "effects", "limiter", "automation", "destination"]:
        gaps.append(
            {
                "field": f"programme.{field}",
                "status": "unsupported",
                "sources": [],
                "reason": "no complete documented programme control reader",
            }
        )
    audio_items = [item for item in items if item["trackKind"] == "audio"]
    counts = [r for r in rows if r["source"] == "timeline:audio.GetTrackCount"]
    inventories = [
        r
        for r in rows
        if r["source"].startswith("track:audio:")
        and r["source"].endswith("GetItemListInTrack")
    ]
    parents = counts + inventories
    complete_audio = (
        len(counts) == 1
        and counts[0]["status"] == "supported"
        and len(inventories) == counts[0]["value"]
        and all(r["status"] == "supported" for r in parents)
    )
    for row in gaps:
        if row["field"] == "clip.effects":
            row.update(
                status="ambiguous",
                sources=[
                    r["source"] for r in rows if r["source"].endswith("GetProperties")
                ],
                reason="item properties expose selected effects only; not all effects",
            )
        if row["field"] == "track.enabled":
            sources = [
                r
                for r in rows
                if r["source"].startswith("track:audio:")
                and r["source"].endswith("GetIsTrackEnabled")
            ]
            row.update(
                status="supported"
                if complete_audio
                and sources
                and all(r["status"] == "supported" for r in sources)
                else "ambiguous",
                sources=[r["source"] for r in sources],
                reason="track-enable getter visibility; full mixer controls unproven",
            )
        if row["field"] in {
            "clip.enabled",
            "clip.gainDb",
            "clip.pan",
            "clip.channelMap",
        }:
            prop = {"clip.gainDb": "AudioVolume", "clip.pan": "AudioPan"}.get(
                row["field"]
            )
            sources = [
                r
                for r in rows
                if any(
                    r["source"].startswith(f"item:{item['uid']}.")
                    for item in audio_items
                )
                and (
                    r["source"].endswith("GetProperties")
                    if prop
                    else r["source"].endswith(
                        "GetClipEnabled"
                        if row["field"] == "clip.enabled"
                        else "GetSourceAudioChannelMapping"
                    )
                )
            ]
            visible = (
                complete_audio
                and bool(audio_items)
                and len(sources) == len(audio_items)
                and all(
                    r["status"] == "supported"
                    and (
                        prop is None
                        or (
                            isinstance(r["value"], dict)
                            and type(r["value"].get(prop)) in {int, float}
                            and math.isfinite(r["value"][prop])
                            and type(r["value"].get(f"{prop}Enabled")) is bool
                        )
                    )
                    for r in sources
                )
            )
            row.update(
                status="supported" if visible else "ambiguous",
                sources=[r["source"] for r in sources],
                reason="getter visibility only; effective route/mix remains unproven",
            )
            row["sources"] = [r["source"] for r in sources + parents]
    for field in (
        "AudioCodec",
        "AudioBitDepth",
        "AudioSampleRate",
        "FrameRate",
        "FormatWidth",
        "FormatHeight",
        "MarkIn",
        "MarkOut",
        "RenderMode",
        "OutputFilename",
        "ReplaceExistingFilesInPlace",
        "IsExportVideo",
        "IsExportAudio",
        "JobId",
        "TimelineName",
        "TargetDir",
    ):
        queue = next(
            (r for r in rows if r["source"] == "project.GetRenderJobList"), None
        )
        jobs = queue["value"] if queue and queue["status"] == "supported" else None
        visible = (
            isinstance(jobs, list)
            and bool(jobs)
            and all(isinstance(job, dict) and field in job for job in jobs)
        )
        gaps.append(
            {
                "field": f"render.queue.{field}",
                "status": "supported" if visible else "ambiguous",
                "sources": ["project.GetRenderJobList"],
                "reason": "existing job visibility; no candidate configured/exercised",
            }
        )
    for method in (
        "GetRenderFormats",
        "GetAudioRenderFormats",
        "GetRenderCodecs",
        "GetAudioRenderCodecs",
        "GetRenderResolutions",
        "GetCurrentRenderFormatAndCodec",
    ):
        methods = {method}
        if method in {
            "GetRenderCodecs",
            "GetAudioRenderCodecs",
            "GetRenderResolutions",
        }:
            methods.update({"GetRenderFormats", "GetAudioRenderFormats"})
        if method == "GetRenderResolutions":
            methods.update({"GetRenderCodecs", "GetAudioRenderCodecs"})
        matches = [
            r for r in rows if any(r["source"].endswith(f".{m}") for m in methods)
        ]
        gaps.append(
            {
                "field": f"render.candidates.{method}",
                "status": "supported"
                if matches
                and all(
                    any(r["source"].endswith(f".{m}") for r in matches) for m in methods
                )
                and all(
                    r["status"] == "supported" and bool(r["value"]) for r in matches
                )
                else "ambiguous",
                "sources": [r["source"] for r in matches],
                "reason": "enumeration only; PCM/picture settings/output unqualified",
            }
        )
    for field in ("actualOutputCadence", "actualPCMProfile", "actualPictureQuality"):
        gaps.append(
            {
                "field": f"render.{field}",
                "status": "unsupported",
                "sources": [],
                "reason": "no job or output produced by read-only preflight",
            }
        )
    return gaps


def run_capability_preflight(
    resolve: Any,
    request_path: Path,
    *,
    expected_request_sha256: str,
) -> Path:
    request = _request(request_path, expected_request_sha256)
    binding = request["binding"]
    evidence = _path(binding["evidenceDir"])
    evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
    run_id = uuid.uuid4().hex
    provenance = {
        "requestSha256": expected_request_sha256,
        "authoritySha256": request["authoritySha256"],
        "binding": binding,
    }
    write_immutable_json(evidence / f"started-{run_id}.json", provenance)
    seen = _Observations()
    result: dict[str, Any] = {
        "schemaVersion": RESULT_SCHEMA,
        "issueNumber": 204,
        "action": "capability_preflight",
        "qualified": False,
        "verified": False,
        "futureEffectsAuthorized": False,
        "status": "stopped_safely",
        "target": binding["target"],
        **provenance,
        "runtime": {
            "implementation": platform.python_implementation(),
            "pythonVersion": platform.python_version(),
            "platform": platform.platform(),
        },
    }
    items: list[dict[str, Any]] = []
    guarded_rows = 0

    def guard() -> tuple[Any, Any]:
        nonlocal guarded_rows
        _require(
            _request(request_path, expected_request_sha256) == request,
            "preflight inputs changed",
        )
        context = _context(resolve, binding["target"], seen)
        guarded_rows = len(seen.rows)
        return context

    try:
        product = seen.get(
            resolve, "resolve", "GetProductName", kind="text", required=True
        )
        version = seen.get(resolve, "resolve", "GetVersion", kind="list", required=True)
        _require(
            product == "DaVinci Resolve Studio"
            and len(version) == 5
            and all(type(n) is int for n in version[:4])
            and version == [21, 1, 1, 10, ""],
            "unsupported actual Studio product/version/build",
        )
        result["runtime"].update(product=product, version=version)
        project, timeline = guard()
        seen.get(project, "project", "GetSettings", kind="object")
        seen.get(timeline, "timeline", "GetSettings", kind="object")
        guard()
        for kind in ("video", "audio", "subtitle"):
            count = seen.get(
                timeline, f"timeline:{kind}", "GetTrackCount", kind, kind="count"
            )
            if count is None:
                continue
            for index in range(1, count + 1):
                label = f"track:{kind}:{index}"
                seen.get(timeline, label, "GetTrackName", kind, index, kind="text")
                seen.get(timeline, label, "GetIsTrackEnabled", kind, index, kind="bool")
                seen.get(timeline, label, "GetIsTrackLocked", kind, index, kind="bool")
                if kind == "audio":
                    seen.get(
                        timeline, label, "GetTrackSubType", kind, index, kind="text"
                    )
                # Native handles are serialized only as independently read item UIDs.
                inventory = {
                    "source": f"{label}.GetItemListInTrack",
                    "arguments": [kind, index],
                    "status": "unsupported",
                    "value": None,
                }
                seen.rows.append(inventory)
                try:
                    getter = getattr(timeline, "GetItemListInTrack", None)
                    _require(callable(getter), "documented item inventory unavailable")
                    assert callable(getter)
                    raw_items = getter(kind, index)
                except Exception as error:
                    inventory["reason"] = str(error)
                    continue
                if not isinstance(raw_items, list) or len(raw_items) + len(items) > 500:
                    inventory["reason"] = "item inventory unavailable or exceeds bound"
                    continue
                uids = []
                for item in raw_items:
                    uid = seen.get(
                        item, label, "GetUniqueId", kind="text", required=True
                    )
                    _require(
                        uid not in {i["uid"] for i in items},
                        "duplicate native item UID",
                    )
                    uids.append(uid)
                    items.append({"uid": uid, "trackKind": kind, "trackIndex": index})
                    seen.get(item, f"item:{uid}", "GetProperties", kind="object")
                    speed = seen.get(item, f"item:{uid}", "GetSpeed", kind="object")
                    if speed is not None and not (
                        type(speed.get("Percentage")) in {int, float}
                        and all(
                            type(speed.get(key)) is bool
                            for key in (
                                "PitchCorrection",
                                "StretchKeyframesToFit",
                                "RippleTimeline",
                            )
                        )
                    ):
                        seen.rows[-1].update(
                            status="ambiguous", reason="incomplete speed options"
                        )
                    seen.get(item, f"item:{uid}", "GetClipEnabled", kind="bool")
                    if kind == "audio":
                        channel = seen.get(
                            item,
                            f"item:{uid}",
                            "GetSourceAudioChannelMapping",
                            kind="text",
                        )
                        if channel is not None:
                            try:
                                mapping = _object(channel.encode())
                                tracks = mapping.get("track_mapping")
                                _require(
                                    isinstance(tracks, dict)
                                    and bool(tracks)
                                    and all(
                                        isinstance(k, str)
                                        and k.isdecimal()
                                        and isinstance(v, dict)
                                        and isinstance(v.get("channel_idx"), list)
                                        and bool(v["channel_idx"])
                                        and all(
                                            type(c) is int and c > 0
                                            for c in v["channel_idx"]
                                        )
                                        and type(v.get("mute")) is bool
                                        and isinstance(v.get("type"), str)
                                        for k, v in tracks.items()
                                    ),
                                    "incomplete channel map",
                                )
                            except ValueError as error:
                                seen.rows[-1].update(
                                    status="ambiguous", reason=str(error)
                                )
                inventory.update(status="supported", value=uids)
                guard()
        for format_method, codec_method in (
            ("GetRenderFormats", "GetRenderCodecs"),
            ("GetAudioRenderFormats", "GetAudioRenderCodecs"),
        ):
            formats = seen.get(project, "project", format_method, kind="object")
            if formats is None:
                continue
            format_row = seen.rows[-1]
            valid_formats = [
                ext
                for ext in formats.values()
                if isinstance(ext, str) and 0 < len(ext) <= 64
            ]
            if len(valid_formats) != len(formats) or len(formats) > 32:
                format_row.update(
                    status="ambiguous", reason="incomplete/bounded format identifiers"
                )
            for ext in sorted(set(valid_formats))[:32]:
                codecs = seen.get(
                    project, f"format:{ext}", codec_method, ext, kind="object"
                )
                if codecs is None:
                    continue
                _require(
                    len(codecs) <= 128
                    and all(
                        isinstance(c, str) and 0 < len(c) <= 128
                        for c in codecs.values()
                    ),
                    "ambiguous codec identifiers",
                )
                for codec in sorted(set(codecs.values())):
                    seen.get(
                        project,
                        f"codec:{ext}:{codec}",
                        "GetRenderResolutions",
                        ext,
                        codec,
                        kind="list",
                    )
                guard()
        seen.get(project, "project", "GetCurrentRenderFormatAndCodec", kind="object")
        seen.get(project, "project", "GetRenderJobList", kind="list")
        guard()
        result["status"] = "capability_gaps_observed"
    except Exception as error:
        result["reason"] = str(error)
        result["failureType"] = type(error).__name__
    for index, row in enumerate(seen.rows):
        row["contextVerified"] = index < guarded_rows
        if index >= guarded_rows and row["status"] == "supported":
            row.update(
                status="ambiguous", reason="read after last verified input/target guard"
            )
    result.update(
        observations=seen.rows,
        items=items,
        gaps=_gaps(seen.rows, items),
        lastGuardedRowCount=guarded_rows,
    )
    print(json.dumps(result, sort_keys=True))
    report = write_immutable_json(evidence / f"result-{run_id}.json", result)
    write_immutable_json(
        evidence / f"hashes-{run_id}.json",
        {
            "resultPath": str(report),
            "resultSha256": _digest(_read(report)),
            **provenance,
        },
    )
    return report
