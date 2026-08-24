from __future__ import annotations

import copy
import subprocess
import sys

import pytest

from fixtures.validate_fixtures import (
    EXPECTED_KIND_COUNTS,
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
