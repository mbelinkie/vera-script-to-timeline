"""Focused real-media refusal and recovery checks for the Issue 178 matrix."""

import platform
import subprocess
from pathlib import Path

import pytest
from issue178_qualification_fixture import (
    _COMPILER_CLI,
    _NODE,
    prepare_qualification_case,
)
from issue178_refusal_recovery import run_package_refusals, run_refusal_recovery
from vera_timeline_agent import qualification_output_package_v2 as admission
from vera_timeline_agent.media_preparation import (
    MediaPreparationError,
    MediaTools,
    _qualified_tools,
)
from vera_timeline_agent.narration.models import identity_hash

pytestmark = pytest.mark.slow


def test_real_media_refusals_and_restart_recovery(tmp_path: Path) -> None:
    try:
        _qualified_tools(identity_hash(MediaTools().fingerprint()))
    except MediaPreparationError as error:
        if error.code == "unqualified_tools":
            pytest.skip(
                "real-media refusal checks require "
                "the locally qualified media-tool build"
            )
        raise

    result = run_refusal_recovery(tmp_path)

    assert result["schemaVersion"] == "issue178-media-refusal-recovery/v1"
    assert result["status"] == "passed"
    assert Path(result["resultPath"]).is_file()
    cases = result["cases"]
    assert {
        name: cases[name]["code"]
        for name in (
            "vfr",
            "unhandled50fps",
            "shortSource",
            "wrongOriginalBytes",
            "preparationTamper",
        )
    } == {
        "vfr": "unsupported_vfr_or_timebase",
        "unhandled50fps": "unsupported_conversion",
        "shortSource": "source_shortage",
        "wrongOriginalBytes": "source_hash_mismatch",
        "preparationTamper": "published_conflict",
    }
    assert all(
        cases[name]["noAttemptPublished"]
        for name in (
            "vfr",
            "unhandled50fps",
            "shortSource",
            "wrongOriginalBytes",
        )
    )
    assert cases["stagedRecovery"]["recoveryReencoded"] is True
    assert cases["stagedRecovery"]["recoveryReused"] is False
    assert cases["publishedRecovery"]["restartReused"] is True
    assert cases["publishedRecovery"]["restartEncoded"] is False
    assert cases["preparationTamper"]["corruptedSha256"]


def test_package_refusals_reuse_one_qualification_case(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(admission, "MATRIX_PREPARATION_ROOT", tmp_path)
    if platform.system() != "Darwin":
        pytest.skip("package admission fixture requires the qualified macOS host")
    if (
        not _NODE.is_file()
        or _NODE.is_symlink()
        or not _COMPILER_CLI.is_file()
        or not admission._FFMPEG.is_file()
        or not admission._FFPROBE.is_file()
    ):
        pytest.skip("pinned Node, compiler, or admission ffmpeg tools are unavailable")
    version = subprocess.run(
        [str(_NODE), "--version"],
        capture_output=True,
        timeout=5,
        check=False,
        env={"LANG": "C", "LC_ALL": "C", "PATH": str(_NODE.parent)},
    )
    if (
        version.returncode != 0
        or version.stdout.strip() != b"v24.19.0"
        or version.stderr
    ):
        pytest.skip("package admission fixture requires pinned Node 24.19.0")
    if (
        admission._hash_file(admission._FFMPEG) != admission._FFMPEG_SHA256
        or admission._hash_file(admission._FFPROBE) != admission._FFPROBE_SHA256
    ):
        pytest.skip("pinned admission ffmpeg tools do not match the qualification")
    try:
        _qualified_tools(identity_hash(MediaTools().fingerprint()))
    except MediaPreparationError as error:
        if error.code == "unqualified_tools":
            pytest.skip(
                "package fixture requires the locally qualified media-tool build"
            )
        raise

    qualification_case = prepare_qualification_case(
        tmp_path / "qualification-case", "mixed25_30"
    )
    result = run_package_refusals(qualification_case, tmp_path)

    assert result["schemaVersion"] == "issue178-package-refusals/v1"
    assert result["status"] == "passed"
    assert Path(result["resultPath"]).is_file()
    assert result["cases"]["wrongDerivedBytes"]["code"] == (
        "package_file_hash_mismatch"
    )
    assert (
        "package file hash mismatch" in result["cases"]["wrongDerivedBytes"]["detail"]
    )
    assert result["cases"]["staleOccurrenceSelection"]["code"] == (
        "MISSING_OCCURRENCE_BINDING"
    )
    assert result["cases"]["staleOccurrenceSelection"]["stage"] == (
        "compiler_semantics"
    )
    assert result["cases"]["staleWordAnchor"]["code"] == "STALE_WORD_ANCHOR"
    assert result["cases"]["staleWordAnchor"]["stage"] == "compiler_semantics"
