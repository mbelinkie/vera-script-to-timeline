"""Generated root models for the VERA shared JSON contracts."""

from .alignment_artifact_v1_schema import AlignmentArtifactV1
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
from .port_refusal_v1_schema import PortRefusalV1
from .prompter_export_v1_schema import PrompterExportV1
from .public_page_capture_api_v1_schema import PublicPageCaptureApiV1
from .public_page_capture_provenance_v1_schema import PublicPageCaptureProvenanceV1
from .public_page_capture_worker_v1_schema import PublicPageCaptureWorkerV1
from .recognition_artifact_v1_schema import RecognitionArtifactV1
from .script_document_v1_schema import ScriptDocumentV1
from .script_document_v2_schema import ScriptDocumentV2, WordAudibleEndAnchor
from .script_reconciliation_v1_schema import ScriptReconciliationV1
from .shoot_registration_v1_schema import ShootRegistrationProjectV1
from .spotlight_evidence_v1_schema import SpotlightEvidenceV1
from .timeline_manifest_v1_schema import TimelineManifestV1
from .timeline_manifest_v2_schema import TimelineManifestV2

__all__ = [
    "AlignmentArtifactV1",
    "AuthoringProjectSettingsV1",
    "BoundaryTokenEvidenceV1",
    "BoundaryVerificationV1",
    "BuildReportV1",
    "BuildReportV2",
    "CompilerDependenciesV1",
    "CompilerDependenciesV2",
    "CompilerResultV2",
    "NarrationBoundaryEvidenceV1",
    "PortRefusalV1",
    "PrompterExportV1",
    "PublicPageCaptureApiV1",
    "PublicPageCaptureProvenanceV1",
    "PublicPageCaptureWorkerV1",
    "RecognitionArtifactV1",
    "ScriptDocumentV1",
    "ScriptDocumentV2",
    "ScriptReconciliationV1",
    "ShootRegistrationProjectV1",
    "SpotlightEvidenceV1",
    "TimelineManifestV1",
    "TimelineManifestV2",
    "WordAudibleEndAnchor",
]
