from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from fixtures.validate_fixtures import (
    EXPECTED_KIND_COUNTS,
    FIXTURES_DIR,
    FixtureValidationError,
    descriptor_assets,
    ffprobe_available,
    load_descriptor,
    validate_descriptor,
    verify_hashes,
    verify_inventory,
    verify_media_metadata,
)


def test_descriptor_is_strictly_valid() -> None:
    validate_descriptor(load_descriptor())


def test_descriptor_rejects_unknown_and_missing_fields() -> None:
    descriptor = load_descriptor()
    with_unknown = copy.deepcopy(descriptor)
    with_unknown["unexpected"] = True
    with pytest.raises(FixtureValidationError, match=r"unknown=\['unexpected'\]"):
        validate_descriptor(with_unknown)

    with_missing_asset_field = copy.deepcopy(descriptor)
    del with_missing_asset_field["assets"][0]["provenance"]
    with pytest.raises(FixtureValidationError, match=r"missing=\['provenance'\]"):
        validate_descriptor(with_missing_asset_field)


def test_inventory_has_exact_required_kinds_and_no_undeclared_media() -> None:
    descriptor = load_descriptor()
    assets = descriptor_assets(descriptor)
    counts = {kind: 0 for kind in EXPECTED_KIND_COUNTS}
    for asset in assets:
        counts[asset["kind"]] += 1
    assert counts == EXPECTED_KIND_COUNTS
    assert len({asset["id"] for asset in assets}) == 6
    assert len({asset["role"] for asset in assets}) == 6
    verify_inventory(descriptor)


def test_inventory_rejects_undeclared_media_in_nested_directories(
    tmp_path: Path,
) -> None:
    fixture_root = tmp_path / "fixtures"
    shutil.copytree(FIXTURES_DIR / "media", fixture_root / "media")
    nested = fixture_root / "media" / "undeclared"
    nested.mkdir()
    (nested / "extra.mp4").write_bytes(b"not declared")

    with pytest.raises(FixtureValidationError, match=r"undeclared/extra\.mp4"):
        verify_inventory(load_descriptor(), fixture_root)


def test_checked_in_sizes_and_sha256_hashes_match() -> None:
    verify_hashes(load_descriptor())


def test_ffprobe_metadata_matches_descriptor() -> None:
    if not ffprobe_available():
        pytest.skip("FFprobe is not installed")
    verify_media_metadata(load_descriptor())


def test_standalone_verification_command() -> None:
    if not ffprobe_available():
        pytest.skip("FFprobe is not installed")
    result = subprocess.run(
        [sys.executable, "fixtures/validate_fixtures.py", "--require-ffprobe"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert result.stderr == ""
    assert (
        "3 video clips, 2 stills, 1 audio bed; hashes verified; "
        "FFprobe metadata verified"
    ) in result.stdout


def test_standalone_verifier_explicitly_reports_missing_ffprobe(
    tmp_path: Path,
) -> None:
    environment = {**os.environ, "PATH": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, "fixtures/validate_fixtures.py"],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert "hashes verified; FFprobe unavailable; metadata skipped" in result.stdout
    assert "metadata verified" not in result.stdout

    required = subprocess.run(
        [
            sys.executable,
            "fixtures/validate_fixtures.py",
            "--require-ffprobe",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    assert required.returncode == 1
    assert "FFprobe is required but was not found on PATH" in required.stderr
    assert "metadata verified" not in required.stdout
