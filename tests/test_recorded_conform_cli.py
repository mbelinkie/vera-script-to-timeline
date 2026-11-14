"""#47 synthetic immutable, deterministic offline publication tests."""

from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from test_recorded_conform import sample
from vera_timeline_agent.recorded_conform import ConformRefused
from vera_timeline_agent.recorded_conform_cli import build_preview
from vera_timeline_agent.recorded_word_evidence import canonical_json


def _case(tmp_path: Path) -> tuple[dict[str, Path], dict[str, Any]]:
    root, prepared, outputs = (
        tmp_path / name for name in ("inputs", "prepared", "outputs")
    )
    root.mkdir()
    prepared.mkdir()
    outputs.mkdir()
    data = sample()
    video = root / "made-up.mov"
    video.write_bytes(b"fictional-source-camera-bytes-only")
    sha = "sha256:" + hashlib.sha256(video.read_bytes()).hexdigest()
    data["videoSha"] = sha
    data["approvals"]["source"]["sha256"] = sha
    data["evidence"]["video"]["sha256"] = sha
    for row in ("row-1", "row-3"):
        data["approvals"]["decisions"][row]["active"]["source"]["sha256"] = sha
    # History must remain an exact before/after audit, not just a decisions
    # dictionary. Re-derive its snapshots from the exact mutated decisions.
    for event in data["approvals"]["history"]:
        event["after"] = copy.deepcopy(data["approvals"]["decisions"][event["rowId"]])
    take_script = root / "prompter.txt"
    take_script.write_bytes(data["sourceScript"])
    paths = {
        "takes": root / "takes.json",
        "video": video,
        "take_script": take_script,
        "script": root / "script-document.json",
        "prepared": prepared,
        "output_root": outputs,
    }
    paths["takes"].write_bytes(canonical_json(data["takes"]))
    (root / "approvals.json").write_bytes(canonical_json(data["approvals"]))
    (root / "take-word-marks.json").write_bytes(canonical_json(data["evidence"]))
    paths["script"].write_bytes(canonical_json(data["document"]))
    (prepared / "compiler-dependencies.json").write_bytes(
        canonical_json(data["dependencies"])
    )
    return paths, data


def _invoke(paths: dict[str, Path], output: Path, compiler: Any) -> dict:
    return build_preview(
        paths["takes"],
        paths["video"],
        paths["take_script"],
        paths["script"],
        paths["prepared"],
        output,
        compiler=compiler,
    )


def _needs_source_short(_script: Path, _dependencies: Path) -> dict:
    return {
        "ready": False,
        "diagnostics": [
            {"code": "SOURCE_INSUFFICIENT", "message": "fictional clip is too short"}
        ],
    }


def test_immutable_output_same_inputs_are_byte_identical_in_two_destinations(
    tmp_path,
) -> None:
    paths, _ = _case(tmp_path)
    a, b = paths["output_root"] / "first", paths["output_root"] / "second"
    first = _invoke(paths, a, _needs_source_short)
    assert first["requires_reconciliation"] is True
    assert first["compilerReady"] is False
    second = _invoke(paths, b, _needs_source_short)
    assert first == second
    files_a = sorted(p.relative_to(a) for p in a.rglob("*") if p.is_file())
    files_b = sorted(p.relative_to(b) for p in b.rglob("*") if p.is_file())
    assert files_a == files_b
    assert set(map(str, files_a)) >= {
        "snapshot.json",
        "impact.json",
        "impact.txt",
        "compiler-dependencies.json",
        "script-document.json",
        "NOT_DELIVERABLE.txt",
    }
    assert all((a / p).read_bytes() == (b / p).read_bytes() for p in files_a)
    assert len(list((a / "preview-only").glob("*.wav"))) == 2
    assert b"TIMING PREVIEW ONLY" in (a / "NOT_DELIVERABLE.txt").read_bytes()
    before = (a / "snapshot.json").read_bytes()
    with pytest.raises(ConformRefused, match="already exists"):
        _invoke(paths, a, _needs_source_short)
    assert (a / "snapshot.json").read_bytes() == before


def test_blocked_rows_report_both_and_never_publish_snapshot(tmp_path) -> None:
    paths, data = _case(tmp_path)
    docs = data["approvals"]
    docs["history"] = docs["history"][:1]
    docs["revision"] = 1
    docs["decisions"] = {"row-1": docs["decisions"]["row-1"]}
    (paths["takes"].parent / "approvals.json").write_bytes(canonical_json(docs))
    out = paths["output_root"] / "blocked"
    with pytest.raises(ConformRefused, match=r"row-2.*row-3"):
        _invoke(paths, out, _needs_source_short)
    assert not out.exists()


def test_wrong_source_hash_and_wrong_word_mapping_refuse_without_output(
    tmp_path,
) -> None:
    paths, data = _case(tmp_path)
    paths["video"].write_bytes(b"replacement-source-not-approved")
    out = paths["output_root"] / "wrong"
    with pytest.raises(ConformRefused, match=r"row-1.*row-3|source"):
        _invoke(paths, out, _needs_source_short)
    assert not out.exists()
    paths["video"].write_bytes(b"fictional-source-camera-bytes-only")
    bad = copy.deepcopy(data["evidence"])
    bad["rows"][0]["fullReads"][0]["marks"][1]["startS"] = None
    (paths["takes"].parent / "take-word-marks.json").write_bytes(canonical_json(bad))
    with pytest.raises(ConformRefused, match="invalid measured time"):
        _invoke(paths, out, _needs_source_short)
    assert not out.exists()


def test_symlink_output_is_refused_without_touching_destination(tmp_path) -> None:
    paths, _ = _case(tmp_path)
    real = paths["output_root"] / "existing"
    real.mkdir()
    fake = paths["output_root"] / "linked"
    fake.symlink_to(real, target_is_directory=True)
    with pytest.raises(ConformRefused, match="symlink"):
        _invoke(paths, fake, _needs_source_short)
    assert not list(real.iterdir())


def test_symlink_in_output_parent_is_refused(tmp_path) -> None:
    paths, _ = _case(tmp_path)
    real = paths["output_root"] / "real"
    real.mkdir()
    link = paths["output_root"] / "link"
    link.symlink_to(real, target_is_directory=True)
    with pytest.raises(ConformRefused, match="symlink"):
        _invoke(paths, link / "fresh", _needs_source_short)
    assert not list(real.iterdir())


def test_source_changed_during_compiler_preview_refuses_publication(tmp_path) -> None:
    paths, _ = _case(tmp_path)
    out = paths["output_root"] / "changed-source"

    def compiler(_script: Path, _deps: Path) -> dict:
        paths["video"].write_bytes(b"source-was-replaced-during-the-preview")
        return _needs_source_short(_script, _deps)

    with pytest.raises(ConformRefused, match="original source video changed"):
        _invoke(paths, out, compiler)
    assert not out.exists()


def test_approval_changed_during_compiler_preview_refuses_publication(tmp_path) -> None:
    paths, _ = _case(tmp_path)
    out = paths["output_root"] / "changed-approval"

    def compiler(_script: Path, _deps: Path) -> dict:
        approvals = paths["takes"].with_name("approvals.json")
        approvals.write_bytes(approvals.read_bytes() + b" ")
        return _needs_source_short(_script, _deps)

    with pytest.raises(ConformRefused, match="changed while preparing"):
        _invoke(paths, out, compiler)
    assert not out.exists()


def test_framing_default_and_invalid_maps_stop_before_writing(tmp_path) -> None:
    paths, _ = _case(tmp_path)
    framing = tmp_path / "framing.json"
    framing.write_text(json.dumps({"row-1": "tight"}), encoding="utf-8")
    out = paths["output_root"] / "tight"
    response = build_preview(
        paths["takes"],
        paths["video"],
        paths["take_script"],
        paths["script"],
        paths["prepared"],
        out,
        framing,
        compiler=_needs_source_short,
    )
    assert response["rows"][0]["framing"] == "tight"
    assert response["rows"][1]["framing"] == "wide"
    bad = tmp_path / "wrong.json"
    bad.write_text(json.dumps({"row-4": "tight"}), encoding="utf-8")
    out_bad = paths["output_root"] / "bad"
    with pytest.raises(ConformRefused, match="unknown framing-map"):
        build_preview(
            paths["takes"],
            paths["video"],
            paths["take_script"],
            paths["script"],
            paths["prepared"],
            out_bad,
            bad,
            compiler=_needs_source_short,
        )
    assert not out_bad.exists()


def test_real_v2_compiler_accepts_valid_preview_narration_without_resolve(
    tmp_path,
) -> None:
    """Use the unchanged TS contract; only the picture is a temporary still."""
    root = Path(__file__).resolve().parents[1]
    if (
        shutil.which("node") is None
        or not (root / "node_modules").is_dir()
        or subprocess.run(
            ["node", "--version"],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        ).stdout.strip()
        != "v24.19.0"
    ):
        pytest.skip("bootstrap npm ci and pinned Node v24.19.0 for real compiler test")
    paths, data = _case(tmp_path)
    reference = json.loads(
        (
            root / "tests/data/authoring_v2/issue_173/compiler/"
            "presenter-still-project-default.input.golden.json"
        ).read_text()
    )
    doc, deps = data["document"], data["dependencies"]
    for block in doc["activeDraft"]["blocks"]:
        slot = block["primaryVisualSequence"]["slots"][0]
        slot["payload"] = {"kind": "on_camera", "presenterChoiceId": None}
    deps["occurrenceResolutions"] = []  # no extraneous source/media descriptors
    deps["authoringDefaults"]["presenterStill"] = reference["dependencies"][
        "authoringDefaults"
    ]["presenterStill"]
    paths["script"].write_bytes(canonical_json(doc))
    (paths["prepared"] / "compiler-dependencies.json").write_bytes(canonical_json(deps))
    output = paths["output_root"] / "accepted"
    result = build_preview(
        paths["takes"],
        paths["video"],
        paths["take_script"],
        paths["script"],
        paths["prepared"],
        output,
    )
    assert result["compilerReady"] is True
    assert result["requires_reconciliation"] is False
    assert result["compilerDiagnostics"] == []
    assert [r["newDurationFrames"] for r in result["rows"]] == [48, 96, 72]
    assert (output / "NOT_DELIVERABLE.txt").exists()
    assert (output / "snapshot.json").exists()
