"""Issue 37's generated Python surface; accepted type tests remain untouched."""

from typing import NotRequired, get_origin, get_type_hints

from vera_timeline_agent.generated.contracts import PrompterExportV1
from vera_timeline_agent.generated.contracts.script_document_v1_schema import (
    NarrationAnnotation,
    NarrationBlock,
    PerformanceBeat,
)


def test_prompter_root_exposes_the_approved_fields() -> None:
    assert set(get_type_hints(PrompterExportV1)) == {
        "schemaVersion",
        "sourceDocument",
        "settings",
        "textSha256",
        "beats",
    }


def test_annotation_and_beat_collections_remain_optional() -> None:
    fields = get_type_hints(NarrationBlock, include_extras=True)
    assert get_origin(fields["annotations"]) is NotRequired
    assert get_origin(fields["performanceBeats"]) is NotRequired
    assert set(get_type_hints(NarrationAnnotation)) == {
        "id",
        "kind",
        "range",
        "value",
        "includeInPrompter",
        "version",
    }
    assert set(get_type_hints(PerformanceBeat)) == {"id", "range", "version"}
