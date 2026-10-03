from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path
from typing import Any

import pytest
from vera_timeline_agent.roundtrip_build import (
    PreparedBuild,
    ProofBuildError,
    load_operator_json,
)

ROOT = Path(__file__).resolve().parents[1]


def _write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")


def _inputs(root: Path) -> dict[str, Any]:
    root.mkdir()
    document = json.loads(
        (ROOT / "tests/data/slice_1_1/minimal.script-document.json").read_text()
    )
    dependencies = json.loads(
        (ROOT / "tests/data/slice_1_3/minimal.compiler-dependencies.json").read_text()
    )
    # Issue-owned controlled PCM and literal dependency input. Frozen fixtures
    # are read only and never rewritten into a different accepted golden.
    audio = root / "prepared-narration.wav"
    with wave.open(str(audio), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(3)
        stream.setframerate(48000)
        stream.writeframes(b"\0" * 96000 * 3)
    narration = dependencies["narration"][0]
    narration["audioHash"] = f"sha256:{hashlib.sha256(audio.read_bytes()).hexdigest()}"
    dependencies["build"]["timeline"].update(
        frameRate={"numerator": 25, "denominator": 1}, width=320, height=180
    )
    node = shutil.which("node")
    assert node is not None
    _write(
        root / "proof-request.json",
        {
            "schemaVersion": "issue-144-prepared-build/v1",
            "evidenceLevel": "synthetic_injected",
            "verifiedAt": "2026-10-03T00:00:00Z",
        },
    )
    _write(root / "script-document.json", document)
    _write(root / "compiler-dependencies.json", dependencies)
    # Source identity comes from the actual compiler, not a handwritten UUID.
    compiled = subprocess.run(
        [
            node,
            str(ROOT / "packages/contracts/src/issue-144-compile-cli.ts"),
            str(root / "script-document.json"),
            str(root / "compiler-dependencies.json"),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    manifest = json.loads(json.loads(compiled.stdout)["manifestJson"])
    source = next(source for source in manifest["sources"] if source["kind"] == "audio")
    _write(
        root / "materialization-plan.json",
        {
            source["id"]: {
                "artifactId": narration["assetId"],
                "origin": audio.name,
                "policy": "copy",
            }
        },
    )
    return document


@pytest.mark.parametrize(
    "raw",
    [
        b'{"a":1,"a":2}',
        b'\xef\xbb\xbf{"a":1}',
        b'{"a":NaN}',
        b'{"a":Infinity}',
        b'{"a":-Infinity}',
        b'{"a":1e400}',
        b'{"a":-1e400}',
    ],
)
def test_strict_operator_gate_refuses_ambiguous_bytes_without_changes(
    tmp_path: Path,
    raw: bytes,
) -> None:
    path = tmp_path / "operator.json"
    path.write_bytes(raw)
    with pytest.raises(ProofBuildError):
        load_operator_json(path)
    assert path.read_bytes() == raw
    assert list(tmp_path.iterdir()) == [path]


def test_wrong_node_refuses_before_any_job_or_snapshot(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    before = set(root.iterdir())
    with pytest.raises(ProofBuildError, match=r"Node v24\.19\.0"):
        PreparedBuild(root, node_executable=sys.executable)
    assert set(root.iterdir()) == before


def test_actual_compiler_and_package_run_all_core_stages_without_synthesis(
    tmp_path: Path,
) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    before = {path.name: path.read_bytes() for path in root.iterdir()}
    build = PreparedBuild(root)
    result = build.run()
    assert result["status"] == "waiting"
    stages = {row["name"]: row for row in result["stages"]}
    assert all(
        stages[name]["status"] == "complete"
        for name in (
            "generating_speech",
            "resolving_media",
            "compiling",
            "writing_interchange",
            "verifying_import_package",
        )
    )
    assert stages["building_resolve_timeline"]["status"] == "waiting"
    assert stages["verifying_timeline"]["status"] == "requested"
    assert {name for name, stage in stages.items() if stage["status"] != "skipped"} == {
        "generating_speech",
        "resolving_media",
        "compiling",
        "writing_interchange",
        "verifying_import_package",
        "building_resolve_timeline",
        "verifying_timeline",
    }
    assert all(
        stages[name]["status"] == "skipped"
        for name in (
            "rendering_mp4",
            "verifying_mp4",
            "uploading",
        )
    )
    for stage in stages.values():
        if stage["status"] == "complete":
            receipt = load_operator_json(Path(stage["path"]))
            assert receipt["evidenceLevel"] == "local_prepared"
            assert receipt["proofLane"] == "synthetic_injected"
    assert "#145" in result["lastError"]
    manifest = json.loads(build.manifest_path.read_text())
    assert manifest["timeline"]["durationFrames"] == 50
    assert build.package_root.is_dir()
    assert build.verified_package().build_id == manifest["buildId"]
    assert not build.intent_path.exists()
    for name, content in before.items():
        assert (root / name).read_bytes() == content
    replay = PreparedBuild(root)
    assert replay.run()["status"] == "waiting"
    assert replay.job_id == build.job_id


def test_speech_stage_refuses_missing_prepared_audio_before_compile(
    tmp_path: Path,
) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    build = PreparedBuild(root)
    (root / "prepared-narration.wav").unlink()
    result = build.run()
    assert result["status"] == "failed"
    assert not build.manifest_path.exists()
    assert not build.package_root.exists()
    assert not build.intent_path.exists()


def test_changed_input_cannot_resume_into_an_existing_package(tmp_path: Path) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    build = PreparedBuild(root)
    build.run()
    manifest_before = build.manifest_path.read_bytes()
    (root / "script-document.json").write_text("{}")
    with pytest.raises(ProofBuildError, match="changed"):
        build.run()
    assert build.manifest_path.read_bytes() == manifest_before
    assert not build.intent_path.exists()


def test_proof_import_does_not_load_any_synthesis_provider() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys; import vera_timeline_agent.roundtrip_build; "
            "assert 'boto3' not in sys.modules; "
            "assert 'vera_timeline_agent.narration.polly' not in sys.modules; "
            "assert 'vera_timeline_agent.narration.service' not in sys.modules",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


@pytest.mark.parametrize(
    "case",
    [
        "stale_revision",
        "wrong_text_hash",
        "wrong_audio_hash",
        "ambiguous_asset",
    ],
)
def test_bad_prepared_binding_refuses_before_compilation_or_package(
    tmp_path: Path,
    case: str,
) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    path = root / "compiler-dependencies.json"
    dependencies = json.loads(path.read_text())
    narration = dependencies["narration"][0]
    if case == "stale_revision":
        narration["blockRevision"] += 1
    elif case == "wrong_text_hash":
        narration["textHash"] = f"sha256:{'0' * 64}"
    elif case == "wrong_audio_hash":
        narration["audioHash"] = f"sha256:{'0' * 64}"
    else:
        plan_path = root / "materialization-plan.json"
        plan = json.loads(plan_path.read_text())
        plan["ambiguous-source"] = dict(next(iter(plan.values())))
        _write(plan_path, plan)
    _write(path, dependencies)
    build = PreparedBuild(root)
    result = build.run()
    assert result["status"] == "failed"
    assert (
        next(row for row in result["stages"] if row["name"] == "generating_speech")[
            "status"
        ]
        == "failed"
    )
    assert not build.manifest_path.exists()
    assert not build.package_root.exists()
    assert not build.intent_path.exists()


@pytest.mark.parametrize("name", ["compiler_output", "frozen_input"])
def test_altered_intermediate_cannot_replay_into_native_stage(
    tmp_path: Path,
    name: str,
) -> None:
    root = tmp_path / "proof"
    _inputs(root)
    build = PreparedBuild(root)
    build.run()
    package_before = {
        path.relative_to(build.package_root): path.read_bytes()
        for path in build.package_root.rglob("*")
        if path.is_file()
    }
    target = (
        build.manifest_path
        if name == "compiler_output"
        else build.run_root / "inputs/script-document.json"
    )
    target.write_text("{}\n")
    with pytest.raises(ProofBuildError, match="changed"):
        build.run()
    assert not build.intent_path.exists()
    assert {
        path.relative_to(build.package_root): path.read_bytes()
        for path in build.package_root.rglob("*")
        if path.is_file()
    } == package_before
