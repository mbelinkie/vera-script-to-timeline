#!/usr/bin/env python3
"""Rebuild/re-admit immutable #312 synthetic source under current compiler.

No native Resolve effects. Three strictly one-use phases retain private inputs,
compilation, media inventory, preparation proofs, and sealed admission. A
refusal leaves the stage for inspection: do not retry the same stage.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Any

from vera_timeline_agent.qualification_output_package_v2 import (
    MATRIX_PROFILE,
    admit_qualification_package_v2,
    load_qualification_package_v2,
)
from vera_timeline_agent.v2_package import build_v2_package, verify_v2_package

ORIGINAL = Path(
    "/Volumes/Family 1A/CodexRulz/vera-issue312/"
    "reverse-current-code-20261027/package-current-S-approved-v2/package"
)
PREPS = (
    Path.home() / "Library/Application Support/VERA/qualification-output-preparation/"
    "issue178-20261016-01/cases/issue312-package-current-S-approved-v2/published"
)
SPEECH = (
    Path.home()
    / ".codex/worktrees/f861/VERA Script to Timeline/out/issue312/rehearsal-speech-v1"
)
NODE = Path.home() / ".local/share/vera/toolchains/node-v24.19.0-darwin-x64/bin/node"


def refuse_if(value: bool, reason: str) -> None:
    if value:
        raise RuntimeError(reason)


def _once(path: Path, data: bytes) -> None:
    with path.open("xb") as fd:
        os.fchmod(fd.fileno(), 0o600)
        fd.write(data)
        fd.flush()
        os.fsync(fd.fileno())


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value, sort_keys=True, ensure_ascii=False, separators=(",", ":")
        ).encode()
        + b"\n"
    )


def _source() -> tuple[Path, dict[str, Any], dict[str, Any]]:
    verified = verify_v2_package(ORIGINAL)
    builds = list((ORIGINAL / "Builds").iterdir())
    refuse_if(
        len(builds) != 1
        or not builds[0].is_dir()
        or builds[0].name != verified.build_id,
        "original synthetic build inventory differs",
    )
    build = builds[0]
    old_manifest = json.loads((build / "timeline-manifest.json").read_bytes())
    deps = json.loads((build / "compiler-dependencies.json").read_bytes())
    refuse_if(
        len(old_manifest["events"]) != 11
        or len(old_manifest["tracks"]) != 6
        or old_manifest["timeline"]["durationFrames"] != 1407,
        "source synthetic geometry differs",
    )
    return build, old_manifest, deps


def _evidence(
    old_manifest: dict[str, Any], deps: dict[str, Any]
) -> tuple[dict[str, Path], dict[str, dict[str, Path]]]:
    refuse_if(
        len(old_manifest["preparationBindings"]) != 6
        or len(deps["narrationBoundaryEvidence"]) != 3,
        "original evidence inventory differs",
    )
    preps: dict[str, Path] = {}
    for row in old_manifest["preparationBindings"]:
        requirement = row["requirementKey"]
        key = requirement.removeprefix("sha256:")
        path = PREPS / key / "receipt.json"
        refuse_if(
            path.is_symlink() or not path.is_file() or requirement in preps,
            "original preparation receipt is missing or ambiguous",
        )
        preps[requirement] = path
    narration: dict[str, dict[str, Path]] = {}
    for row in deps["narrationBoundaryEvidence"]:
        block = row["blockId"]
        refuse_if(
            row["verification"].get("method") != "measured_audio_boundaries/v1",
            "original narration method differs",
        )
        timing = (
            SPEECH / "cache" / row["audio"]["locator"].rsplit("/", 1)[0] / "timing.json"
        )
        measurement = SPEECH / row["verification"]["measurementArtifactLocator"]
        refuse_if(
            any(p.is_symlink() or not p.is_file() for p in (timing, measurement))
            or block in narration,
            "original narration evidence missing or ambiguous",
        )
        narration[block] = {"timing": timing, "measurement": measurement}
    return preps, narration


def _one_match(directory: Path, name: str) -> Path:
    matches = [
        p for p in directory.glob(name + ".*") if p.is_file() and not p.is_symlink()
    ]
    refuse_if(len(matches) != 1, "original media is missing or ambiguous")
    return matches[0]


def compile_current(root: Path) -> dict[str, Any]:
    refuse_if(root.exists() or root.is_symlink(), "new private compile root required")
    repo = Path.cwd()
    core = repo / "packages/contracts/src/compiler-core-v2.ts"
    cli = repo / "packages/contracts/src/issue-190-compile-cli.ts"
    refuse_if(
        not core.is_file() or not cli.is_file() or not NODE.is_file(),
        "current pinned compiler tools unavailable",
    )
    build, old_manifest, deps = _source()
    _evidence(old_manifest, deps)
    with subprocess.Popen(
        [str(NODE), "--version"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={"PATH": str(NODE.parent), "LANG": "C", "LC_ALL": "C"},
    ) as child:
        stdout, _ = child.communicate(timeout=8)
        refuse_if(
            child.returncode != 0 or stdout.strip() != b"v24.19.0",
            "Node runtime differs",
        )
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    inputs = root / "inputs"
    inputs.mkdir(mode=0o700)
    old_doc = json.loads((build / "script-document.json").read_bytes())
    next_deps = copy.deepcopy(deps)
    next_deps["compiler"]["sourceHash"] = (
        "sha256:" + hashlib.sha256(core.read_bytes()).hexdigest()
    )
    doc = inputs / "script-document-v2.json"
    dependencies = inputs / "compiler-dependencies-v2.json"
    _once(doc, _json_bytes(old_doc))
    _once(dependencies, _json_bytes(next_deps))
    env = {"PATH": str(NODE.parent), "LANG": "C", "LC_ALL": "C"}
    outcome = subprocess.run(
        [str(NODE), str(cli), str(doc), str(dependencies)],
        capture_output=True,
        env=env,
        timeout=60,
        check=False,
    )
    if outcome.returncode != 0:
        _once(
            root / "compile-refusal.txt",
            outcome.stderr[:32768] + outcome.stdout[:32768],
        )
        raise RuntimeError(
            "current compiler refused original, independently pinned inputs"
        )
    envelope = json.loads(outcome.stdout)
    refuse_if(
        not envelope["result"]["ok"] or not envelope["needs"]["ok"],
        "current compiler returned refusal",
    )
    compiled = envelope["result"]
    manifest = json.loads(compiled["manifestJson"])
    refuse_if(
        manifest["timeline"] != old_manifest["timeline"]
        or len(manifest["events"]) != 11
        or len(manifest["tracks"]) != 6
        or len(manifest["preparationBindings"]) != 6
        or {e["eventId"] for e in manifest["events"]}
        != {e["eventId"] for e in old_manifest["events"]}
        or {s["id"] for s in manifest["sources"]}
        != {s["id"] for s in old_manifest["sources"]},
        "new compiler changed original approved synthetic identities or geometry",
    )
    _once(inputs / "timeline-manifest-v2.json", compiled["manifestJson"].encode())
    _once(inputs / "build-report-v2.json", compiled["reportJson"].encode())
    _once(
        root / "source-provenance.json",
        _json_bytes(
            {
                "schema": "vera.472-current-compiler/v1",
                "oldCompilerSourceHash": deps["compiler"]["sourceHash"],
                "newCompilerSourceHash": next_deps["compiler"]["sourceHash"],
                "originalBuildId": build.name,
                "currentBuildId": manifest["buildId"],
                "frameCount": 1407,
                "events": 11,
                "tracks": 6,
                "originalMediaUnmodified": True,
            }
        ),
    )
    return {
        "state": "current_compiler_verified",
        "buildId": manifest["buildId"],
        "nativeEffects": False,
    }


def package_current(root: Path) -> dict[str, Any]:
    build, old_manifest, original_dependencies = _source()
    preps, _ = _evidence(old_manifest, original_dependencies)
    inputs = root / "inputs"
    manifest = json.loads((inputs / "timeline-manifest-v2.json").read_bytes())
    deps = json.loads((inputs / "compiler-dependencies-v2.json").read_bytes())
    refuse_if(
        manifest["timeline"] != old_manifest["timeline"]
        or {e["eventId"] for e in manifest["events"]}
        != {e["eventId"] for e in old_manifest["events"]}
        or {s["id"] for s in manifest["sources"]}
        != {s["id"] for s in old_manifest["sources"]}
        or deps["compiler"]["sourceHash"]
        != "sha256:"
        + hashlib.sha256(
            (Path.cwd() / "packages/contracts/src/compiler-core-v2.ts").read_bytes()
        ).hexdigest(),
        "recompiled input/source geometry differs",
    )
    dest = root / "package"
    refuse_if(dest.exists() or dest.is_symlink(), "package stage already started")
    paths: dict[str, Path] = {}
    for source in manifest["sources"]:
        name = source["id"]
        if "narrationAudio" in source:
            paths["source:" + name] = _one_match(ORIGINAL / "Media/Narration", name)
        else:
            paths["source:" + name] = _one_match(ORIGINAL / "Media/Resolved", name)
            paths["original:" + name] = _one_match(build / "Preparation/original", name)
    for event in manifest["events"]:
        kind, name = event["kind"], event["eventId"]
        if kind == "placeholder":
            paths["event:" + name] = _one_match(ORIGINAL / "Media/Resolved", name)
        elif kind == "source_audio":
            paths["event:" + name] = _one_match(ORIGINAL / "Media/Narration", name)
        elif kind not in {"primary_visual", "overlay_visual", "narration"}:
            raise RuntimeError("new compiler introduced unsupported event type")
    result = build_v2_package(
        inputs / "timeline-manifest-v2.json",
        inputs / "build-report-v2.json",
        inputs / "script-document-v2.json",
        inputs / "compiler-dependencies-v2.json",
        dest,
        media_paths=paths,
        preparation_paths=preps,
    )
    checked = verify_v2_package(dest)
    refuse_if(
        checked.build_id != result.build_id or checked.event_count != 11,
        "new package is not independently verified",
    )
    return {
        "state": "current_package_verified",
        "buildId": checked.build_id,
        "nativeEffects": False,
    }


def admit_current(root: Path) -> dict[str, Any]:
    _, old_manifest, deps = _source()
    preps, narr = _evidence(old_manifest, deps)
    package = root / "package"
    verify_v2_package(package)
    dest = root / "admitted"
    refuse_if(dest.exists() or dest.is_symlink(), "admission stage already attempted")
    a = admit_qualification_package_v2(
        dest,
        profile=MATRIX_PROFILE,
        package_root=package,
        preparation_paths=preps,
        narration_evidence_paths=narr,
    )
    digest = hashlib.sha256(a.admission_path.read_bytes()).hexdigest()
    verified = load_qualification_package_v2(a.admission_path, digest)
    refuse_if(
        verified.profile != MATRIX_PROFILE
        or verified.manifest["timeline"]["durationFrames"] != 1407
        or len(verified.manifest["events"]) != 11,
        "fresh admission differs from current compiled source",
    )
    return {
        "state": "current_package_admitted_and_authenticated",
        "admissionSha256": digest,
        "nativeEffects": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stage", choices=("compile", "package", "admit"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.stage == "compile":
            result = compile_current(args.root)
        elif args.stage == "package":
            result = package_current(args.root)
        else:
            result = admit_current(args.root)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        print(
            json.dumps({"state": "failed_closed", "reason": str(error)}, sort_keys=True)
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
