"""Matrix authority stays distinct from the earlier smoke and private profiles."""

from pathlib import Path

import pytest
from test_issue209_native import _approval
from vera_timeline_agent import qualification_output_native_v2 as native
from vera_timeline_agent import qualification_output_package_v2 as package
from vera_timeline_agent.qualification_output_records_v2 import _canonical


def test_matrix_grant_cannot_be_used_as_smoke_grant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(native, "NATIVE_STATE_ROOT", tmp_path / "native-state")
    approval, context = _approval(tmp_path, profile=package.MATRIX_PROFILE)
    raw = _canonical(approval)
    native.verify_operator_approval(
        raw,
        context=context,
        profile=package.MATRIX_PROFILE,
        admission_sha256=approval["admissionSha256"],
        release_manifest_sha256=approval["releaseManifestSha256"],
    )
    with pytest.raises(ValueError, match="profile"):
        native.verify_operator_approval(
            raw,
            context=context,
            profile=package.SYNTHETIC_PROFILE,
            admission_sha256=approval["admissionSha256"],
            release_manifest_sha256=approval["releaseManifestSha256"],
        )


def test_matrix_refuses_incomplete_preparation_inventory(tmp_path: Path) -> None:
    with pytest.raises(package.QualificationPackageError, match="path inventory"):
        package._prepared_matrix(
            {},
            {},
            {"preparationBindings": [{"requirementKey": "missing"}]},
            {},
            tmp_path,
            {},
            {},
            {},
        )
    assert list(tmp_path.iterdir()) == []
