from typing import get_type_hints

from vera_timeline_agent.generated.contracts import (
    BuildReportV1,
    ScriptDocumentV1,
    TimelineManifestV1,
)


def _document_id(document: ScriptDocumentV1) -> str:
    return document["id"]


def _manifest_build_id(manifest: TimelineManifestV1) -> str:
    return manifest["buildId"]


def _report_status(report: BuildReportV1) -> str:
    return report["status"]


def test_generated_typed_dicts_are_importable_and_expose_root_fields() -> None:
    assert "activeDraft" in get_type_hints(ScriptDocumentV1)
    assert "events" in get_type_hints(TimelineManifestV1)
    assert "eventResults" in get_type_hints(BuildReportV1)


def test_generated_types_are_usable_as_function_contracts() -> None:
    document: ScriptDocumentV1 = {
        "schemaVersion": "script-document/v1",
        "id": "00000000-0000-4000-8000-000000000001",
        "projectId": "00000000-0000-4000-8000-000000000002",
        "title": "TypedDict smoke sample",
        "activeDraft": {"blocks": []},
        "ideaOutline": [],
        "extras": [],
        "liveHeadSequence": 0,
        "liveStateVector": "",
        "liveContentHash": f"sha256:{'a' * 64}",
    }
    assert _document_id(document) == document["id"]

    # These functions are intentionally referenced so strict mypy checks each
    # generated root type as an ordinary application-facing annotation.
    assert callable(_manifest_build_id)
    assert callable(_report_status)
