from typing import get_type_hints

from vera_timeline_agent.generated.contracts import (
    BuildReportV2,
    CompilerDependenciesV2,
    CompilerResultV2,
    ScriptDocumentV2,
    TimelineManifestV2,
)
from vera_timeline_agent.generated.contracts import (
    __all__ as generated_exports,
)
from vera_timeline_agent.generated.contracts.compiler_dependencies_v2_schema import (
    NarrationTokenTimingMapV2,
    OccurrenceMediaResolutionV2,
    PreparedMediaBindingV1,
    PresenterAlignmentResolutionV1,
    RationalTime,
    SourceFrameMapV1,
    SupportingItemResultV2,
    VisualSequenceResolutionV2,
)


def _dependency_duration(dependencies: CompilerDependenciesV2) -> int:
    return dependencies["timeline"]["durationFrames"]


def _manifest_build_class(manifest: TimelineManifestV2) -> str:
    return manifest["buildClass"]


def _report_status(report: BuildReportV2) -> str:
    return report["status"]


def _compiled_manifest_id(result: CompilerResultV2) -> str:
    if result["kind"] == "compiled":
        return result["manifest"]["id"]
    return result["diagnostics"][0]["code"]


def _compiler_result_kind(result: CompilerResultV2) -> str:
    return result["kind"]


def test_issue171_python_v2_roots_are_public_typed_dicts() -> None:
    assert "schemaVersion" in get_type_hints(ScriptDocumentV2)
    assert "narrationTimingMaps" in get_type_hints(CompilerDependenciesV2)
    assert "events" in get_type_hints(TimelineManifestV2)
    assert "recoveryActions" in get_type_hints(BuildReportV2)
    assert "presenterAlignmentResolutions" in get_type_hints(CompilerDependenciesV2)
    assert "CompilerResultV2" in generated_exports

    assert (
        _dependency_duration.__annotations__["dependencies"] is CompilerDependenciesV2
    )
    assert _manifest_build_class.__annotations__["manifest"] is TimelineManifestV2
    assert _report_status.__annotations__["report"] is BuildReportV2
    assert callable(_compiled_manifest_id)
    assert _compiler_result_kind.__annotations__["result"] is CompilerResultV2


def test_issue171_python_v2_record_shapes_are_importable() -> None:
    for record, expected_fields in [
        (RationalTime, {"numerator", "denominator"}),
        (NarrationTokenTimingMapV2, {"tokens", "timingHash", "precision"}),
        (OccurrenceMediaResolutionV2, {"owner", "sourceFrameMap"}),
        (SourceFrameMapV1, {"packageVideoPtsOrigin", "decodedPackageFrameCount"}),
        (PreparedMediaBindingV1, {"mode", "verification", "timeMapping"}),
        (
            PresenterAlignmentResolutionV1,
            {
                "schemaVersion",
                "slotId",
                "takeId",
                "masterIdentity",
                "sourceStartFrame",
                "alignmentVersion",
                "precision",
                "expectedWord",
                "recognizedWord",
            },
        ),
        (VisualSequenceResolutionV2, {"boundaryDelta", "topmostAppearances"}),
        (SupportingItemResultV2, {"disposition", "recordRange", "reason"}),
    ]:
        assert expected_fields <= get_type_hints(record).keys()
