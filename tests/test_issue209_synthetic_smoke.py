"""Real-source smoke input for the ordinary v2 package admission path."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from issue209_synthetic_smoke import prepare_synthetic_smoke
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent.qualification_output_package_v2 import (
    SYNTHETIC_PROFILE,
    admit_qualification_package_v2,
    load_qualification_package_v2,
)
from vera_timeline_agent.v2_package import (
    verify_v2_package,
)

pytestmark = pytest.mark.slow


def test_authenticated_111_frame_source_audio_package_is_ready(tmp_path: Path) -> None:
    from issue209_synthetic_smoke import _EXECUTION_DEPENDENCIES

    if not _EXECUTION_DEPENDENCIES.is_file():
        pytest.skip("requires retained local synthetic source inputs")
    output_root = tmp_path / "issue209-synthetic-smoke"
    case = prepare_synthetic_smoke(output_root)

    document = json.loads(case.document_path.read_text(encoding="utf-8"))
    dependencies = json.loads(case.dependencies_path.read_text(encoding="utf-8"))
    manifest = json.loads(case.manifest_path.read_text(encoding="utf-8"))
    report = json.loads(case.report_path.read_text(encoding="utf-8"))

    assert case.build.build_id == manifest["buildId"]
    assert verify_v2_package(case.package_root).build_id == case.build.build_id
    assert len(document["activeDraft"]["blocks"]) == 1
    assert document["activeDraft"]["blocks"][0]["type"] == "visual_only"
    assert document["activeDraft"]["blocks"][0]["payload"]["audioPolicy"] == "full"
    assert document["extras"] == []
    assert document["ideaOutline"] == []
    assert dependencies["narrationBoundaryEvidence"] == []
    assert dependencies["narrationTimingMaps"] == []
    assert len(dependencies["preparedMedia"]) == 1
    assert len(dependencies["occurrenceResolutions"]) == 1
    assert (
        dependencies["authoringDefaults"]["presenterStill"]
        == document["scriptSettings"]["presenterStillOverride"]
    )
    assert manifest["timeline"]["durationFrames"] == 111
    assert len(manifest["events"]) == 2
    assert {event["kind"] for event in manifest["events"]} == {
        "primary_visual",
        "source_audio",
    }
    source_audio = next(
        event for event in manifest["events"] if event["kind"] == "source_audio"
    )
    assert source_audio["audio"]["audioPolicy"] == "full"
    assert source_audio["audio"]["gainDb"] == 0
    assert source_audio["audio"]["sampleRange"] == {
        "startFrame": 11629618,
        "endFrame": 11851840,
    }
    assert report["status"] == "ready"
    assert report["diagnostics"] == []
    assert report["recoveryActions"] == []
    assert set(case.preparation_paths) == {
        dependencies["preparedMedia"][0]["requirementKey"]
    }
    assert all(path.is_file() for path in case.preparation_paths.values())
    assert all(path.is_file() for path in case.media_paths.values())
    assert case.package_root.is_dir()

    for source_path in (
        case.original_document_path,
        case.original_dependencies_path,
        case.execution_document_path,
        case.execution_dependencies_path,
    ):
        assert source_path.is_file()
        assert not source_path.resolve().is_relative_to(output_root.resolve())

    admitted = admit_qualification_package_v2(
        tmp_path / "admitted",
        profile=SYNTHETIC_PROFILE,
        package_root=case.package_root,
    )
    assert admitted.disposition == "verified_synthetic"
    assert admitted.diagnostics == ()
    assert (
        admitted.view_raw
        == (
            case.package_root / "Builds" / case.build.build_id / "delivery-view.json"
        ).read_bytes()
    )
    assert all(
        path.is_relative_to(admitted.package_root / "PublicPackage")
        for path in admitted.source_paths.values()
    )
    admitted.assert_current()
    path, digest = admitted.serialize_native_admission()
    reopened = load_qualification_package_v2(path, digest)
    assert reopened.admission == admitted.admission
    assert reopened.source_entries == admitted.source_entries
    # Exercise the installed stdlib admission boundary on the real host wrapper.
    admitted_native = native._admission_profile(
        {
            "profile": admitted.profile,
            "package": admitted.native_package_ref(),
            "context": {key: native._hash(raw) for key, raw in admitted.blobs.items()},
            "inputs": {
                "originalDocumentPath": str(admitted.original_document_path),
                "originalDependenciesPath": str(admitted.original_dependencies_path),
                "executionDocumentPath": str(admitted.execution_document_path),
                "executionDependenciesPath": str(admitted.execution_dependencies_path),
            },
        }
    )
    assert admitted_native["sourceRoot"] == admitted.package_root / "PublicPackage"
