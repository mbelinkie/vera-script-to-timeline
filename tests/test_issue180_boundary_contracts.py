from __future__ import annotations

import json
from pathlib import Path
from typing import get_type_hints

import pytest
from jsonschema import Draft202012Validator  # type: ignore[import-untyped]
from referencing import Registry, Resource
from vera_timeline_agent.generated.contracts import (
    BoundaryTokenEvidenceV1,
    BoundaryVerificationV1,
    CompilerDependenciesV2,
    NarrationBoundaryEvidenceV1,
    WordAudibleEndAnchor,
)

ROOT = Path(__file__).resolve().parents[1]
GOLDENS = ROOT / "tests/data/authoring_v2/issue_180"


def test_issue180_public_generated_evidence_shapes() -> None:
    assert "narrationBoundaryEvidence" in get_type_hints(CompilerDependenciesV2)
    assert {"audio", "tokens", "verification", "schemaVersion"} <= get_type_hints(
        NarrationBoundaryEvidenceV1
    ).keys()
    onset: BoundaryTokenEvidenceV1 = {
        "tokenId": "00000000-0000-4000-8000-000000000001",
        "startOffset": 0,
        "endOffset": 4,
        "quotedText": "beta",
        "onset": {"numerator": 1, "denominator": 1},
    }
    end_only: BoundaryTokenEvidenceV1 = {
        "tokenId": onset["tokenId"],
        "startOffset": 0,
        "endOffset": 4,
        "quotedText": "beta",
        "audibleEnd": {"numerator": 3, "denominator": 2},
    }
    assert onset["onset"] == {"numerator": 1, "denominator": 1}
    assert end_only["audibleEnd"] == {"numerator": 3, "denominator": 2}
    assert {"reviewId", "reviewRevision", "reviewArtifactHash"} <= get_type_hints(
        BoundaryVerificationV1
    ).keys()
    assert "affinity" in get_type_hints(WordAudibleEndAnchor)


@pytest.mark.parametrize("path", sorted(GOLDENS.glob("*.golden.json")))
def test_issue180_new_golden_schema_parity(path: Path) -> None:
    schemas = {}
    resources = []
    for schema_path in (ROOT / "contracts").glob("*.schema.json"):
        schema = json.loads(schema_path.read_text())
        schemas[schema_path.name] = schema
        resources.append((schema["$id"], Resource.from_contents(schema)))
    registry = Registry().with_resources(resources)
    value = json.loads(path.read_text())
    if ".input." in path.name:
        targets = [
            ("script-document-v2.schema.json", value["document"]),
            ("compiler-dependencies-v2.schema.json", value["dependencies"]),
        ]
    else:
        name = (
            "timeline-manifest-v2.schema.json"
            if ".manifest." in path.name
            else "build-report-v2.schema.json"
        )
        targets = [(name, value)]
    for name, target in targets:
        validator = Draft202012Validator(schemas[name], registry=registry)
        assert not list(validator.iter_errors(target)), path.name
