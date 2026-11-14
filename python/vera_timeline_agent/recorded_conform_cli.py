"""#47: freeze a recorded-performance timing preview, without opening Resolve.

This command does not choose takes, modify approval history, prepare visual
media, deliver recorded sound or construct a native timeline.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from vera_timeline_agent.presenter_approvals import (
    ApprovalError,
    load_approvals,
    load_takes,
    observed_video,
)
from vera_timeline_agent.presenter_takes import TakesError, read_script
from vera_timeline_agent.recorded_conform import ConformRefused, conform_snapshot
from vera_timeline_agent.recorded_timing_adapter import (
    derived_dependencies,
    impact_report,
    impact_text,
    write_silent_carrier,
)
from vera_timeline_agent.recorded_word_evidence import canonical_json

Json = dict[str, Any]
_ROOT = Path(__file__).resolve().parents[2]
_COMPILER = _ROOT / "packages/contracts/src/issue-190-compile-cli.ts"


def _plain(path: Path, *, directory: bool = False, allow_absent: bool = False) -> Path:
    """Never read sources through symlink components or follow output links."""
    if not path.is_absolute():
        raise ConformRefused(f"absolute path required: {path}")
    for component in (path, *path.parents):
        if component.is_symlink():
            raise ConformRefused(f"symlink path refused: {path}")
    if not allow_absent:
        if not (path.is_dir() if directory else path.is_file()):
            raise ConformRefused(
                f"missing {'directory' if directory else 'regular file'}: {path}"
            )
    elif path.exists() or path.is_symlink():
        raise ConformRefused(f"output already exists (immutable): {path}")
    return path


def _json(path: Path) -> Json:
    try:
        data = json.loads(
            _plain(path).read_text(encoding="utf-8"),
            parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)),
        )
    except (UnicodeError, ValueError, OSError) as exc:
        raise ConformRefused(f"invalid JSON at {path.name}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConformRefused(f"expected JSON object: {path.name}")
    return data


def _hash_bytes(path: Path) -> str:
    h = hashlib.sha256()
    with _plain(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _compiler_result(document: Path, dependencies: Path) -> Json:
    """Execute unchanged pinned TS compiler; code 1 carries its diagnostics."""
    inputs = [f"sha256:{_hash_bytes(p)}" for p in (document, dependencies)]
    try:
        result = subprocess.run(
            ["node", str(_COMPILER), str(document), str(dependencies)],
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        raise ConformRefused("pinned offline V2 compiler unavailable") from exc
    if result.returncode not in (0, 1) or len(result.stdout) > 16_000_000:
        raise ConformRefused(f"compiler execution failed: {result.stderr[:1200]}")
    try:
        response = json.loads(result.stdout)
    except ValueError as exc:
        raise ConformRefused("compiler returned invalid JSON") from exc
    if (
        response.get("schemaVersion") != "issue-190-v2-compile/v1"
        or response.get("runtime") != "v24.19.0"
        or response.get("inputs") != inputs
        or inputs != [f"sha256:{_hash_bytes(p)}" for p in (document, dependencies)]
    ):
        raise ConformRefused("compiler runtime or frozen input digests mismatch")
    compiled = response.get("result", {})
    valid_plan = compiled.get("ok") is True
    needs = response.get("needs")
    needs_ready = isinstance(needs, dict) and needs.get("ok") is True
    ready = (
        valid_plan
        and needs_ready
        and compiled.get("report", {}).get("status") == "ready"
    )
    if not ready:
        # A valid temporal plan can be *report-blocked* when media has not
        # been prepared. In that case diagnostics live in result.report,
        # not result.diagnostics. Do not reject the measured timing preview.
        report_errors = (
            [
                diagnostic
                for diagnostic in compiled.get("report", {}).get("diagnostics", [])
                if diagnostic.get("severity") in ("blocking", "error")
            ]
            if valid_plan
            else []
        )
        diagnostics = (
            (
                report_errors
                + (
                    needs.get("diagnostics", [])
                    if isinstance(needs, dict) and not needs_ready
                    else []
                )
            )
            if valid_plan
            else compiled.get("diagnostics", [])
        )
        codes = {item.get("code") for item in diagnostics}
        allowed = {"SOURCE_INSUFFICIENT", "PREPARATION_HASH_MISMATCH"}
        if not codes or not codes <= allowed:
            raise ConformRefused(
                "V2 compiler rejected new timing: " + json.dumps(diagnostics)[:1200]
            )
        return {
            "ready": False,
            "diagnostics": diagnostics,
            **(
                {"manifest": compiled["manifest"], "report": compiled["report"]}
                if valid_plan
                else {}
            ),
        }
    return {
        "ready": True,
        "diagnostics": [],
        "manifest": compiled["manifest"],
        "report": compiled["report"],
    }


def _merge_compiled_events(impact: Json, old: Json | None, new: Json) -> None:
    """Compare real manifest placements, even with media-preparation blockers."""
    if old is None or "manifest" not in old or "manifest" not in new:
        return
    old_events = {
        event["eventId"]: event
        for event in old["manifest"]["events"]
        if event["kind"] not in ("narration", "music")
    }
    movements = []
    for event in new["manifest"]["events"]:
        previous = old_events.get(event["eventId"])
        if previous is None or event["kind"] in ("narration", "music"):
            continue
        a, b = previous["recordRange"], event["recordRange"]
        if a != b:
            movements.append(
                {
                    "eventId": event["eventId"],
                    "kind": event["kind"],
                    "ownerId": event["provenance"].get("slotId")
                    or event["provenance"].get("overlayEventId"),
                    "oldRecordRange": a,
                    "newRecordRange": b,
                    "deltaStartFrames": b["startFrame"] - a["startFrame"],
                }
            )
    impact["compiledEventMovements"] = movements


def _save_stage(stage: Path, name: str, content: bytes) -> None:
    (stage / name).write_bytes(content)


def build_preview(
    takes_path: Path,
    video_path: Path,
    take_script: Path,
    script: Path,
    prepared: Path,
    output: Path,
    framing_map: Path | None = None,
    *,
    compiler: Callable[[Path, Path], Json] = _compiler_result,
) -> Json:
    """Validate every input first, publish only into a new exclusive output."""
    takes_path = _plain(takes_path)
    video_path = _plain(video_path)
    take_script = _plain(take_script)
    script = _plain(script)
    prepared = _plain(prepared, directory=True)
    output = _plain(output, allow_absent=True)
    _plain(output.parent, directory=True)
    if output.parent == prepared or output.parent == takes_path.parent:
        # New outputs may be siblings of input directories, not nested into
        # the original #45 or compiled-preparation folder.
        raise ConformRefused("new output must be separate from immutable input folders")
    approvals_path = _plain(takes_path.with_name("approvals.json"))
    evidence_path = _plain(takes_path.with_name("take-word-marks.json"))
    dependency_path = _plain(prepared / "compiler-dependencies.json")
    fingerprint_paths = [
        takes_path,
        approvals_path,
        evidence_path,
        take_script,
        script,
        dependency_path,
    ]
    if framing_map is not None:
        fingerprint_paths.append(_plain(framing_map))
    fingerprint = {path: _hash_bytes(path) for path in fingerprint_paths}
    takes, approvals = load_takes(takes_path), load_approvals(approvals_path)
    evidence = _json(evidence_path)
    document, dependencies = _json(script), _json(dependency_path)
    framing = _json(_plain(framing_map)) if framing_map else None
    video_digest = observed_video(video_path)
    snap = conform_snapshot(
        takes,
        approvals,
        video_digest,
        evidence,
        take_script.read_bytes(),
        read_script(take_script),
        document,
        dependencies,
        framing=framing,
    )
    derived, carriers = derived_dependencies(snap, dependencies)
    impact = impact_report(snap, document, dependencies, derived)
    # Build the immutable content privately before reserving the destination.
    stage = Path(tempfile.mkdtemp(prefix=".vera47-", dir=output.parent))
    claimed = False
    published = False
    try:
        _save_stage(stage, "script-document.json", canonical_json(document))
        _save_stage(stage, "compiler-dependencies.json", canonical_json(derived))
        # Only the exact V2 compiler can call this ready. Source shortages and
        # changed preparation ranges remain explicitly not deliverable.
        outcome = compiler(
            stage / "script-document.json", stage / "compiler-dependencies.json"
        )
        old_outcome = None
        if "manifest" in outcome:
            _save_stage(
                stage,
                "original-compiler-dependencies.json",
                canonical_json(dependencies),
            )
            try:
                old_outcome = compiler(
                    stage / "script-document.json",
                    stage / "original-compiler-dependencies.json",
                )
            except ConformRefused:
                old_outcome = None  # the new proof is still independently valid
            (stage / "original-compiler-dependencies.json").unlink()
        impact["compilerReady"] = bool(outcome["ready"] and not impact["shortSources"])
        if "manifest" in outcome:
            # Real V2 requirements supersede conservative single-slot checks.
            impact["needsCompilerReview"] = []
            impact["requires_reconciliation"] = bool(
                impact["shortSources"] or not outcome["ready"]
            )
        else:
            impact["requires_reconciliation"] = True
        impact["compilerDiagnostics"] = outcome["diagnostics"]
        _merge_compiled_events(impact, old_outcome, outcome)
        _save_stage(stage, "snapshot.json", canonical_json(snap))
        _save_stage(stage, "impact.json", canonical_json(impact))
        _save_stage(stage, "impact.txt", impact_text(impact).encode("utf-8"))
        sound_dir = stage / "preview-only"
        sound_dir.mkdir()
        for carrier in carriers:
            write_silent_carrier(carrier, sound_dir)
        _save_stage(
            stage,
            "NOT_DELIVERABLE.txt",
            (
                b"OFFLINE RECORDED CONFORM TIMING PREVIEW ONLY.\n"
                b"The silence WAVs are timing carriers, NOT recorded presenter sound.\n"
                b"#48 must replace them with verified recorded audio.\n"
            ),
        )
        if any(_hash_bytes(path) != expected for path, expected in fingerprint.items()):
            raise ConformRefused(
                "source/approval/script/word evidence changed while preparing"
            )
        if observed_video(video_path) != video_digest:
            raise ConformRefused("original source video changed while preparing")
        _plain(output, allow_absent=True)
        # Reserve an unused name exclusively, then replace the *empty*
        # reservation with the complete same-filesystem stage atomically.
        # No partially populated snapshot is ever visible to a reader.
        output.mkdir()
        claimed = True
        os.replace(stage, output)
        published = True
        return impact
    except BaseException:
        if claimed and not published and output.is_dir() and not any(output.iterdir()):
            output.rmdir()
        raise
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--takes", type=Path, required=True)
    parser.add_argument("--video", type=Path, required=True)
    parser.add_argument("--take-script", type=Path, required=True)
    parser.add_argument("--script", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--framing-map", type=Path)
    args = parser.parse_args(argv)
    try:
        result = build_preview(
            args.takes.absolute(),
            args.video.absolute(),
            args.take_script.absolute(),
            args.script.absolute(),
            args.prepared.absolute(),
            args.out.absolute(),
            args.framing_map.absolute() if args.framing_map else None,
        )
        print(impact_text(result), end="")
        return 0 if not result["requires_reconciliation"] else 2
    except (
        ConformRefused,
        ApprovalError,
        TakesError,
        OSError,
        KeyError,
        TypeError,
    ) as exc:
        print(f"Recorded conform refused; no snapshot: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
