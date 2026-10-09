"""Generated root models for the VERA shared JSON contracts."""

from .authoring_project_settings_v1_schema import AuthoringProjectSettingsV1
from .build_report_v1_schema import BuildReportV1
from .build_report_v2_schema import BuildReportV2, CompilerResultV2
from .compiler_dependencies_v1_schema import CompilerDependenciesV1
from .compiler_dependencies_v2_schema import (
    BoundaryTokenEvidenceV1,
    BoundaryVerificationV1,
    CompilerDependenciesV2,
    NarrationBoundaryEvidenceV1,
)
from .prompter_export_v1_schema import PrompterExportV1
from .script_document_v1_schema import ScriptDocumentV1
from .script_document_v2_schema import ScriptDocumentV2, WordAudibleEndAnchor
from .timeline_manifest_v1_schema import TimelineManifestV1
from .timeline_manifest_v2_schema import TimelineManifestV2

__all__ = [
    "AuthoringProjectSettingsV1",
    "BoundaryTokenEvidenceV1",
    "BoundaryVerificationV1",
    "BuildReportV1",
    "BuildReportV2",
    "CompilerDependenciesV1",
    "CompilerDependenciesV2",
    "CompilerResultV2",
    "NarrationBoundaryEvidenceV1",
    "PrompterExportV1",
    "ScriptDocumentV1",
    "ScriptDocumentV2",
    "TimelineManifestV1",
    "TimelineManifestV2",
    "WordAudibleEndAnchor",
]
