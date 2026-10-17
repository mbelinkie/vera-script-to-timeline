import json
from pathlib import Path

import pytest
from vera_timeline_agent.v2_package import V2PackageError, _validate_inputs


@pytest.mark.parametrize("field", ["class", "content", "snapshot", "pointer"])
def test_new_graphic_content_cannot_bypass_unimplemented_evidence_packaging(
    field: str,
) -> None:
    """A pure compiler success is not permission to export retained evidence."""
    root = Path(__file__).parent / "data/authoring_v2/issue_173/compiler"
    stem = "visual-only-graphic-still-ntsc-default"
    pair = json.loads((root / f"{stem}.input.golden.json").read_text())
    manifest = json.loads((root / f"{stem}.manifest.golden.json").read_text())
    report = json.loads((root / f"{stem}.report.golden.json").read_text())
    dependencies = pair["dependencies"]
    if field == "class":
        dependencies["occurrenceResolutions"][0]["graphicContentClass"] = "derived"
    elif field == "content":
        dependencies["resolvedGraphicContents"] = [{"provenance": {"kind": "manual"}}]
    elif field == "snapshot":
        dependencies["graphicProvenanceSnapshots"] = [{"retained": "synthetic"}]
    else:
        manifest["events"][0]["provenance"]["graphicProvenanceHash"] = (
            "sha256:" + "a" * 64
        )
    with pytest.raises(V2PackageError, match="verified evidence-package adapter"):
        _validate_inputs(pair["document"], dependencies, manifest, report)
