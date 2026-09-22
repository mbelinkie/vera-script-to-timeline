import json
from pathlib import Path

import pytest
from vera_timeline_agent.otio_package.package import (
    PackageBuildError,
    _validate_semantics,
    validate_build_report,
    validate_timeline_manifest,
)
from vera_timeline_agent.resolve_import_package.package import (
    ResolveImportPackageError,
    _validate_manifest_semantics,
)

DATA = Path(__file__).parent / "data" / "issue_7"


@pytest.mark.parametrize("target", ["studio", "free"])
def test_compiled_graphic_contracts_and_explicit_adapter_rejection(
    target: str, tmp_path: Path
) -> None:
    manifest = json.loads((DATA / f"normal.{target}.manifest.golden.json").read_text())
    report = json.loads((DATA / f"normal.{target}.report.golden.json").read_text())
    validate_timeline_manifest(manifest)
    validate_build_report(report)
    with pytest.raises(
        PackageBuildError, match="future verified graphic package adapter"
    ):
        _validate_semantics(manifest, tmp_path)
    with pytest.raises(
        ResolveImportPackageError, match="future verified graphic package adapter"
    ):
        _validate_manifest_semantics(manifest)
