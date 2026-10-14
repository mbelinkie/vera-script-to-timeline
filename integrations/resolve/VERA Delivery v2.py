"""Repository-owned Workflow Integration v2; Resolve injects `resolve`."""

import hashlib
import json
import os
import stat
import sys
import uuid
from pathlib import Path
from typing import Any, cast

PLUGIN_ROOT = Path(
    "/Library/Application Support/Blackmagic Design/DaVinci Resolve/"
    "Workflow Integration Plugins"
)
# Resolve can exec a script without __file__; retain #107's documented root.
SCRIPT_PATH = Path(globals().get("__file__", str(PLUGIN_ROOT / "VERA Delivery v2.py")))


def within(path: Path, parent: Path) -> bool:
    if path.is_relative_to(parent):
        return True
    if not parent.exists():
        return False
    identity = (parent.stat().st_dev, parent.stat().st_ino)
    return any(
        p.exists() and (p.stat().st_dev, p.stat().st_ino) == identity
        for p in (path, *path.parents)
    )


def provenance_bytes(path: Path) -> bytes:
    if not path.is_absolute() or any(p.is_symlink() for p in (path, *path.parents)):
        raise RuntimeError("unsafe qualification input")
    before = path.lstat()
    with path.open("rb") as source:
        opened = os.fstat(source.fileno())
        if (
            not stat.S_ISREG(opened.st_mode)
            or opened.st_nlink != 1
            or opened.st_size > 2 * 1024 * 1024
            or (before.st_dev, before.st_ino) != (opened.st_dev, opened.st_ino)
        ):
            raise RuntimeError("hardlinked/changed/unbounded qualification input")
        payload = source.read(2 * 1024 * 1024 + 1)
        after = os.fstat(source.fileno())
    if len(payload) != opened.st_size or (opened.st_size, opened.st_mtime_ns) != (
        after.st_size,
        after.st_mtime_ns,
    ):
        raise RuntimeError("qualification input changed while reading")
    return payload


def qualification_object(payload: bytes) -> dict[str, Any]:
    def pairs(entries: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in entries:
            if key in value:
                raise RuntimeError("duplicate qualification key")
            value[key] = item
        return value

    parsed = json.loads(payload, object_pairs_hook=pairs)
    if not isinstance(parsed, dict):
        raise RuntimeError("qualification record must be an object")
    json.dumps(parsed, allow_nan=False)
    return cast(dict[str, Any], parsed)


def launch(injected_resolve: object) -> None:
    if any(
        path.is_symlink() for path in (SCRIPT_PATH, *SCRIPT_PATH.absolute().parents)
    ):
        raise RuntimeError("symbolic link in installed script path")
    root = SCRIPT_PATH.resolve().parent
    release_root = root / "vera-delivery-v2"
    if release_root.is_symlink():
        raise RuntimeError("symbolic link in installed release root")
    request_path = release_root / "request.json"
    if request_path.is_symlink():
        raise RuntimeError("symbolic link in installed request path")
    request_bytes = request_path.read_bytes()
    request = json.loads(request_bytes)
    qualification = (
        request.get("schemaVersion") == "vera-native-qualification-request/v1"
    )
    if qualification:
        request = qualification_object(request_bytes)
    binding = request["binding"] if qualification else request
    release_path = release_root / "release.json"
    if release_path.is_symlink():
        raise RuntimeError("symbolic link in installed release manifest")
    release_bytes = release_path.read_bytes()
    if hashlib.sha256(release_bytes).hexdigest() != binding["releaseSha256"]:
        raise RuntimeError("installed release hash differs from the operator request")
    release = json.loads(release_bytes)
    if (
        not isinstance(release, dict)
        or set(release) != {"schemaVersion", "deliveryVersion", "sourcePins", "files"}
        or release["schemaVersion"] != "vera-injected-delivery-release/v2"
        or release["deliveryVersion"] != "2"
    ):
        raise RuntimeError("unsupported installed release")
    for entry in release["files"]:
        path = root / entry["path"]
        if (
            not path.resolve().is_relative_to(root)
            or path.is_symlink()
            or path.stat().st_size != entry["sizeBytes"]
            or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]
        ):
            raise RuntimeError("installed source differs from the versioned release")
    runtime = release_root / "python"
    declared_files = {entry["path"] for entry in release["files"]}
    entries = list(release_root.rglob("*"))
    if any(
        path.is_symlink() or not (path.is_file() or path.is_dir()) for path in entries
    ):
        raise RuntimeError("unsupported entry in installed release")
    installed_files = {
        path.relative_to(root).as_posix()
        for path in entries
        if path.is_file()
        and path not in {release_path, request_path}
        and path.name != ".DS_Store"
    } | {SCRIPT_PATH.name}
    declared_directories = {
        parent.as_posix()
        for name in declared_files
        for parent in Path(name).parents
        if parent != Path(".")
    }
    installed_directories = {release_root.relative_to(root).as_posix()} | {
        path.relative_to(root).as_posix() for path in entries if path.is_dir()
    }
    if (
        installed_files != declared_files
        or installed_directories != declared_directories
    ):
        raise RuntimeError(
            "installed source inventory differs from release; reinstall clean release"
        )
    for name in tuple(sys.modules):
        if name == "vera_timeline_agent" or name.startswith("vera_timeline_agent."):
            raise RuntimeError("a VERA runtime is already loaded; restart Resolve")
    if qualification:
        # Retain exact input provenance before importing the installed controller.
        if (
            set(request)
            != {
                "schemaVersion",
                "issueNumber",
                "action",
                "binding",
                "authorityPath",
                "authoritySha256",
            }
            or type(request["issueNumber"]) is not int
            or request["issueNumber"] != 204
            or request["action"] != "capability_preflight"
        ):
            raise RuntimeError("unsupported read-only qualification request")
        authority_path = Path(request["authorityPath"])
        approval_path = Path(binding["approvalPath"])
        evidence = Path(binding["evidenceDir"])
        inputs = (
            authority_path,
            approval_path,
            evidence,
            Path(binding["repositoryRoot"]),
        )
        if any(
            not path.is_absolute()
            or any(part.is_symlink() for part in (path, *path.parents))
            for path in inputs
        ):
            raise RuntimeError("unsafe qualification provenance paths")
        if provenance_bytes(request_path) != request_bytes:
            raise RuntimeError("qualification request changed before import")
        authority_bytes = provenance_bytes(authority_path)
        authority = qualification_object(authority_bytes)
        if (
            set(authority)
            != {
                "schemaVersion",
                "issueNumber",
                "action",
                "operator",
                "issuedAt",
                "invocationId",
                "issuer",
                "binding",
                "confirmations",
            }
            or authority["schemaVersion"] != "vera-native-qualification-authority/v1"
            or type(authority["issueNumber"]) is not int
            or authority["issueNumber"] != 204
            or authority["action"] != "capability_preflight"
            or authority["confirmations"]
            != {
                "readOnly": True,
                "savedDisposableNonproduction": True,
                "externalScripting": "None",
            }
            or authority["confirmations"]["readOnly"] is not True
            or authority["confirmations"]["savedDisposableNonproduction"] is not True
        ):
            raise RuntimeError("invalid closed read-only operator authority")
        if (
            hashlib.sha256(authority_bytes).hexdigest() != request["authoritySha256"]
            or authority["binding"] != binding
            or hashlib.sha256(provenance_bytes(approval_path)).hexdigest()
            != binding["approvalSha256"]
            or within(evidence, root)
            or within(evidence, Path(binding["repositoryRoot"]))
            or within(evidence, Path(binding["releaseRoot"]))
            or within(root, evidence)
            or within(Path(binding["repositoryRoot"]), evidence)
            or within(Path(binding["releaseRoot"]), evidence)
            or within(authority_path, evidence)
            or within(approval_path, evidence)
        ):
            raise RuntimeError("qualification provenance mismatch/overlap")
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        started = evidence / f"bootstrap-started-{uuid.uuid4().hex}.json"
        with started.open("x", encoding="utf-8") as stream:
            json.dump(
                {
                    "requestSha256": hashlib.sha256(request_bytes).hexdigest(),
                    "authoritySha256": request["authoritySha256"],
                    "releaseSha256": binding["releaseSha256"],
                    "approvalSha256": binding["approvalSha256"],
                    "repositorySourcePins": binding["repositorySourcePins"],
                    "target": binding["target"],
                    "qualified": False,
                },
                stream,
                indent=2,
                sort_keys=True,
            )
        started.chmod(0o400)
    sys.dont_write_bytecode = True
    sys.pycache_prefix = None
    sys.path.insert(0, str(runtime))
    from vera_timeline_agent.workflow_v2_launcher import run_installed_request_v2

    report = run_installed_request_v2(
        injected_resolve,
        request_path,
        expected_request_sha256=hashlib.sha256(request_bytes).hexdigest(),
    )
    print(report)


try:
    launch(globals().get("resolve"))
except Exception as error:
    failure = {
        "status": "workflow_v2_launcher_failed",
        "verified": False,
        "detail": str(error),
    }
    # Retain bootstrap failures without importing unverified installed code.
    try:
        config = json.loads(
            (SCRIPT_PATH.resolve().parent / "vera-delivery-v2/request.json").read_text()
        )
        if config.get("schemaVersion") == "vera-native-qualification-request/v1":
            binding = config["binding"]
            # A tampered request's unsafe output cannot replace its bound safe receipt.
            try:
                authority = provenance_bytes(Path(config["authorityPath"]))
                if hashlib.sha256(authority).hexdigest() == config["authoritySha256"]:
                    binding = json.loads(authority)["binding"]
            except Exception:
                pass
            evidence = Path(binding["evidenceDir"])
            protected_roots = [
                SCRIPT_PATH.resolve().parent,
                Path(binding["repositoryRoot"]).resolve(),
                Path(binding["releaseRoot"]).resolve(),
                Path(binding["approvalPath"]).resolve(),
                Path(config["authorityPath"]).resolve(),
            ]
            if any(within(path, evidence) for path in protected_roots):
                raise RuntimeError("qualification evidence contains protected input")
        else:
            evidence = Path(config["evidenceDir"])
            package = Path(config["packageDir"]).resolve()
            protected_roots = [package]
            attestation_path = Path(config["attestationPath"])
            if attestation_path.exists():
                protected_roots.append(
                    Path(
                        json.loads(attestation_path.read_text())["packageDir"]
                    ).resolve()
                )
        if (
            not evidence.is_absolute()
            or any(
                path.is_symlink() for path in (evidence, *evidence.absolute().parents)
            )
            or any(within(evidence, root) for root in protected_roots)
        ):
            raise RuntimeError("unsafe evidence directory")
        evidence.mkdir(mode=0o700, parents=True, exist_ok=True)
        path = evidence / f"bootstrap-refusal-{uuid.uuid4().hex}.json"
        with path.open("x", encoding="utf-8") as stream:
            json.dump(failure, stream, indent=2, sort_keys=True)
        path.chmod(0o400)
        failure["reportPath"] = str(path)
    except Exception:
        failure["reportRetention"] = "unavailable; retain this Console output"
    print(json.dumps(failure, indent=2, sort_keys=True))
